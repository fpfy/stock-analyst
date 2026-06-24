"""
stock-analysis 组合入口：宏观→选股→回测→模拟交易 一键串联

用法：
  python run_full_analysis.py                           # 完整流程：宏观+选股
  python run_full_analysis.py --with-backtest           # 选股后自动回测
  python run_full_analysis.py --with-paper             # 选股后自动模拟交易
  python run_full_analysis.py --all                    # 全流程：宏观+选股+回测+模拟
  python run_full_analysis.py --quick                  # 快速验证（max-stocks 10）
  python run_full_analysis.py --max-stocks 30          # 自定义选股数量
  python run_full_analysis.py --all --max-stocks 20    # 全流程+自定义数量
"""
import sys
import os
import argparse
import logging

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, PROJECT_ROOT)


def run_macro():
    """宏观分析"""
    os.chdir(PROJECT_ROOT)
    from macro_analyzer import MacroAnalyzer
    analyzer = MacroAnalyzer()
    analyzer.fetch_pmi()
    print(f"[宏观] 市场状态: {analyzer.market_state}, PMI趋势: {analyzer.pmi_trend}")
    return analyzer


def refresh_live_prices():
    """基于 valuation_data 刷新 trading_strategy 的 current_price，确保后续模拟盘使用真实数据"""
    os.chdir(PROJECT_ROOT)
    import importlib.util
    spec = importlib.util.spec_from_file_location("update_live_prices", os.path.join(PROJECT_ROOT, "update_live_prices.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.update_trading_strategy_prices()


def run_selection(quick=False, max_stocks=None):
    """双通道选股

    Returns:
        {'market_cycle': str, 'growth_stocks': list, 'value_stocks': list, 'report_path': str}
    """
    os.chdir(PROJECT_ROOT)
    import main_v3
    args = ["main_v3.py"]
    if quick:
        args += ["--max-stocks", "10"]
    elif max_stocks:
        args += ["--max-stocks", str(max_stocks)]
    sys.argv = args
    return main_v3.main()


def run_backtest(shared_conn=None, selection_result=None):
    """策略回测

    Args:
        shared_conn: 共享数据库连接
        selection_result: 选股结果字典（来自 run_selection），用于联动回测
    """
    os.chdir(PROJECT_ROOT)
    import backtest_v3
    from selection_bridge import get_backtest_strategy_fn
    from pathlib import Path

    db_path = Path(__file__).parent.parent.parent.parent / "database" / "stock_analysis.db"

    # 若提供了选股结果，优先使用 selection_bridge 的 strategy_fn 实现联动
    strategy_fn = None
    if selection_result is not None:
        try:
            strategy_fn = get_backtest_strategy_fn()
            logger.info(f"[run_full_analysis] 使用选股联动回测，策略函数已注入")
        except Exception as e:
            logger.warning(f"[run_full_analysis] 加载选股权重失败，回退内置策略: {e}")

    if shared_conn is not None:
        engine = backtest_v3.BacktestEngine(str(db_path), strategy_fn=strategy_fn, conn=shared_conn)
    else:
        engine = backtest_v3.BacktestEngine(str(db_path), strategy_fn=strategy_fn)

    try:
        engine.run_quarterly_backtest()
        report = engine.generate_report()
    finally:
        if shared_conn is None:
            engine.close()
        else:
            try:
                engine.conn.commit()
            except Exception:
                pass
            engine.conn = None
            engine.cursor = None

    return report


def run_papertrader(shared_conn=None):
    """模拟交易"""
    os.chdir(PROJECT_ROOT)

    # 单连接共享模式下，不再重建 database.db 单例，避免与主流程连接脱节
    try:
        import database
        if getattr(database, 'db', None) is not None:
            try:
                database.db.close()
            except Exception:
                pass
        database.db = database.DatabaseManager()
    except Exception as e:
        print(f"[PAPER] 重建数据库单例失败: {e}")

    import papertrader_final
    from datetime import date
    today = date.today().isoformat()

    sys.argv = [
        "papertrader_final.py",
        "--single-day", today,
        "--cash", "1000000",
    ]

    max_retries = 3
    for attempt in range(max_retries):
        try:
            if shared_conn is not None:
                trader = papertrader_final.PaperTraderFinal(conn=shared_conn)
            else:
                trader = papertrader_final.PaperTraderFinal()
            try:
                return trader.run_single_day(today)
            finally:
                if shared_conn is None:
                    trader.close()
                else:
                    try:
                        if getattr(trader, '_conn', None) is not None:
                            trader._commit_with_retry()
                    except Exception:
                        pass
                    trader._conn = None
        except Exception as e:
            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                wait = 2 + attempt * 2
                print(f"[PAPER] 模拟交易第{attempt+1}次重试，等待{wait}秒")
                import time
                time.sleep(wait)
            else:
                return {
                    "error": str(e),
                    "date": today,
                    "nav": None,
                    "cash": None,
                    "holdings_count": 0,
                    "actions": [],
                    "trade_count": 0,
                }


def main():
    parser = argparse.ArgumentParser(description="Stock-Analysis 组合入口")
    parser.add_argument("--with-backtest", action="store_true", help="选股后执行回测")
    parser.add_argument("--with-paper", action="store_true", help="选股后执行模拟交易")
    parser.add_argument("--all", action="store_true", help="全流程：宏观+选股+回测+模拟")
    parser.add_argument("--quick", action="store_true", help="快速验证（max-stocks 10）")
    parser.add_argument("--max-stocks", type=int, default=None, help="选股最大数量（默认不限）")
    parser.add_argument("--market-regime", type=str, default=None, choices=['bull', 'bear', 'sideways'], help="强制指定市场状态（默认自动判断）")
    args = parser.parse_args()

    # 根据大盘状态动态调整止盈参数（每日自动更新）
    try:
        from selection_bridge import get_dynamic_risk_config
        config = get_dynamic_risk_config(args.market_regime)
        print(f"[动态风控] 已根据大盘状态自动调整参数")
        print(f"[动态风控] 成长股：激活阈值={config['成长']['trailing_activation_pct']:.0%}, 回撤阈值={config['成长']['trailing_drop_pct']:.0%}")
        print(f"[动态风控] 价值股：激活阈值={config['价值']['trailing_activation_pct']:.0%}, 回撤阈值={config['价值']['trailing_drop_pct']:.0%}")
    except Exception as e:
        print(f"[动态风控] 参数调整失败: {e}，使用默认震荡市参数")

    # 快速验证模式默认 max_stocks=10
    max_stocks = 10 if args.quick else args.max_stocks

    steps = []
    if args.all:
        steps = ["macro", "selection", "refresh_prices", "backtest", "paper"]
    elif args.with_backtest and args.with_paper:
        steps = ["macro", "selection", "refresh_prices", "backtest", "paper"]
    elif args.with_backtest:
        steps = ["macro", "selection", "refresh_prices", "backtest"]
    elif args.with_paper:
        steps = ["macro", "selection", "refresh_prices", "paper"]
    else:
        steps = ["macro", "selection"]

    print(f"=== Stock-Analysis 组合入口 ===")
    print(f"执行步骤: {' → '.join(steps)}")
    if max_stocks:
        print(f"选股数量限制: {max_stocks}")

    report_path = None
    papertrader_result = None

    for step in steps:
        print(f"\n--- 步骤: {step} ---")
        if step == "macro":
            run_macro()
        elif step == "selection":
            selection_result = run_selection(quick=args.quick, max_stocks=max_stocks)
            if isinstance(selection_result, dict):
                report_path = selection_result.get('report_path')
            # 关闭主流程数据库连接，避免 refresh_prices 阶段出现 database is locked
            try:
                import database as _db
                if getattr(_db, 'db', None) is not None:
                    try:
                        _db.db.close()
                    except Exception:
                        pass
            except Exception:
                pass
        elif step == "refresh_prices":
            refresh_live_prices()
        elif step == "backtest":
            # 选股结果直接注入回测引擎，实现选股→回测联动
            run_backtest(shared_conn=None, selection_result=selection_result)
        elif step == "paper":
            papertrader_result = run_papertrader(shared_conn=None)

    # 将模拟交易结果追加到主报告
    if papertrader_result and report_path:
        if papertrader_result.get('error'):
            _append_papertrader_error(report_path, papertrader_result['error'])
        else:
            _append_papertrader_section(report_path, papertrader_result)

    print(f"\n=== 全部步骤完成 ===")


def _append_papertrader_error(report_path, error):
    """将模拟交易错误信息追加到主报告"""
    try:
        with open(str(report_path), 'a', encoding='utf-8') as f:
            f.write("\n## 五、模拟交易结果\n\n")
            f.write(f"> ⚠️ **模拟交易执行失败**\n\n")
            f.write(f"错误信息: {error}\n\n")
        print(f"[报告] 模拟交易错误信息已追加: {report_path}")
    except Exception as e:
        print(f"[报告] 追加错误信息失败: {e}")


def _append_papertrader_section(report_path, papertrader_result):
    """将模拟交易结果追加到主报告"""
    try:
        performance = papertrader_result.get('performance') or {}
        result = papertrader_result.get('result')
        
        with open(str(report_path), 'a', encoding='utf-8') as f:
            f.write("\n## 五、模拟交易结果\n\n")
            
            # 标题行：兼容单日和批量模式
            if isinstance(result, list):
                date_label = f"{papertrader_result.get('date', 'N/A')} 至 2026-06-23"
            else:
                date_label = papertrader_result.get('date', 'N/A')
            f.write(f"> **模拟交易日期**: {date_label}\n\n")
            
            if performance:
                f.write("| 指标 | 数值 |\n")
                f.write("|:---|:---:|\n")
                f.write(f"| 初始资金 | {performance.get('initial_cash', 0):,.0f} |\n")
                f.write(f"| 当前净值 | {performance.get('current_nav', 0):,.0f} |\n")
                f.write(f"| 总收益率 | {performance.get('total_return_pct', 0):+.2f}% |\n")
                f.write(f"| 总交易数 | {performance.get('total_trades', 0)} |\n")
                f.write(f"| 当前持仓 | {performance.get('active_positions', 0)}只 |\n")
                f.write(f"| 胜率 | {performance.get('win_rate_pct', 0):.1f}% |\n")
                f.write(f"| 最大回撤 | {performance.get('max_drawdown_pct', 0):.2f}% |\n")
                f.write(f"| 夏普比率 | {performance.get('sharpe_ratio', 0):.2f} |\n")
                f.write(f"| 波动率 | {performance.get('volatility_pct', 0):.2f}% |\n")
                f.write("\n")
            
            # 单日交易明细
            if isinstance(result, dict) and result.get('actions'):
                f.write("### 当日交易明细\n\n")
                f.write("| 时间 | 股票 | 操作 | 价格 | 股数 | 金额 | 原因 | 盈亏 |\n")
                f.write("|:---|:---|:---|:---:|:---:|:---:|:---|:---:|\n")
                for action in result.get('actions', []):
                    profit = action.get('profit_pct')
                    profit_str = f"{profit:+.2f}%" if profit is not None else "N/A"
                    f.write(
                        f"| {action.get('date', '')} | {action.get('ts_code', '')} | "
                        f"{action.get('action', '')} | {action.get('price', 0):.2f} | "
                        f"{action.get('shares', 0)} | {action.get('amount', 0):,.0f} | "
                        f"{action.get('reason', '')} | {profit_str} |\n"
                    )
                f.write("\n")
            
            # 当前持仓
            if isinstance(result, dict) and result.get('holdings_count', 0) > 0:
                f.write(f"### 当前持仓\n\n")
                f.write(f"持仓数: {result.get('holdings_count', 0)}只\n\n")
                f.write(f"当日净值: {result.get('nav', 0):,.0f}\n\n")
                f.write(f"现金余额: {result.get('cash', 0):,.0f}\n\n")
            
            f.write("\n")
        
        print(f"[报告] 模拟交易信息已追加: {report_path}")
    except Exception as e:
        print(f"[报告] 追加模拟交易信息失败: {e}")


if __name__ == "__main__":
    main()
