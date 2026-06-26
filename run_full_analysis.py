"""
run_full_analysis.py — 总控脚本
串联：选股 → 回测 → 模拟交易 → 日报生成
"""
import os
import sys
import json
import datetime
import logging
import traceback
import time
import sqlite3
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(PROJECT_ROOT / 'reports' / 'run_full_analysis.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

DB_PATH = PROJECT_ROOT / 'database' / 'stock_analysis.db'
REPORTS_DIR = PROJECT_ROOT / 'reports'


def run_step(name, func):
    """统一执行步骤，捕获异常不中断流程"""
    logger.info(f"{'='*60}")
    logger.info(f"▶ {name}")
    logger.info(f"{'='*60}")
    try:
        result = func()
        logger.info(f"✅ {name} 完成")
        return result
    except Exception as e:
        logger.error(f"❌ {name} 失败: {e}")
        logger.debug(traceback.format_exc())
        return None


def step_selection():
    """步骤1：选股（调用 main_v3.py 的分析逻辑）"""
    try:
        # 方式A：导入并运行主分析器
        from main_v3 import AdvancedAnalyzer
        analyzer = AdvancedAnalyzer()
        result = analyzer.run()
        if result:
            return {
                'growth_count': len(result.get('growth_stocks', [])),
                'value_count': len(result.get('value_stocks', [])),
                'report_path': result.get('report_path'),
                'market_cycle': result.get('market_cycle')
            }
        return {'growth_count': 0, 'value_count': 0}
    except Exception as e:
        logger.warning(f"主分析器运行失败，尝试降级方案: {e}")
        # 方式B：直接从 selection_bridge 读取最新选股结果
        try:
            from selection_bridge import get_latest_selection
            latest = get_latest_selection(limit=50)
            growth = [s for s in latest if s.get('strategy_type') == '成长']
            value = [s for s in latest if s.get('strategy_type') == '价值']
            return {
                'growth_count': len(growth),
                'value_count': len(value),
                'source': 'selection_bridge',
                'stocks': latest
            }
        except Exception as e2:
            logger.error(f"降级方案也失败: {e2}")
            return {'growth_count': 0, 'value_count': 0, 'error': str(e2)}


def step_backtest():
    """步骤2：回测（调用 backtest_v3_runner.py）"""
    try:
        # 直接导入并运行回测
        from backtest_v3 import run_backtest
        report = run_backtest()
        return {'report': report}
    except Exception as e:
        logger.error(f"回测失败: {e}")
        return {'error': str(e)}


def step_paper_trade():
    """步骤3：模拟交易（调用 papertrader_final.py --single-day）"""
    try:
        from papertrader_final import PaperTraderFinal
        from selection_bridge import get_latest_selection, RISK_CONFIG
        
        # 获取当日选股建议
        suggestions = get_latest_selection(limit=20)
        if not suggestions:
            logger.warning("无选股建议，跳过模拟交易")
            return {'status': 'skipped', 'reason': 'no_selection'}
        
        # 步骤间延迟，避免数据库锁竞争
        time.sleep(3)
    
        # 运行单日交易
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        trader = PaperTraderFinal(initial_cash=1_000_000)
        result = trader.run_single_day(today)
        trader.close()
    
        return {
            'status': 'success',
            'date': today,
            'nav': result.get('nav'),
            'cash': result.get('cash'),
            'holdings_count': result.get('holdings_count'),
            'trade_count': result.get('trade_count')
        }
    except Exception as e:
        logger.error(f"模拟交易失败: {e}")
        return {'error': str(e)}


def step_report(selection_result, backtest_result, papertrade_result):
    """步骤4：生成日报"""
    try:
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        report_date = today.replace('-', '')
        report_path = REPORTS_DIR / f'daily_report_{report_date}.md'
        html_report_path = REPORTS_DIR / f'daily_report_{report_date}.html'
        
        # 读取最新回测报告路径
        latest_backtest = None
        if backtest_result and 'report' in backtest_result:
            latest_backtest = backtest_result['report']
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"# 每日分析报告\n\n")
            f.write(f"> 生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # 1. 选股结果
            f.write(f"## 一、选股结果\n\n")
            if selection_result:
                f.write(f"- 成长股: {selection_result.get('growth_count', 0)} 只\n")
                f.write(f"- 价值股: {selection_result.get('value_count', 0)} 只\n")
                if selection_result.get('source') == 'selection_bridge':
                    f.write(f"- 数据来源: selection_bridge 最新选股\n")
                    stocks = selection_result.get('stocks', [])
                    if stocks:
                        f.write(f"\n| 股票 | 通道 | 六维评分 | 融合评分 | 技术 | 筹码 | 宏观 |\n")
                        f.write(f"|:---|:---:|:---:|:---:|:---:|:---:|:---:|\n")
                        for s in stocks[:10]:
                            tech = s.get('technical_score', '-')
                            chip = s.get('chip_score', '-')
                            macro = s.get('macro_score', '-')
                            fusion = s.get('fusion_score', '-')
                            f.write(f"| {s.get('ts_code')} | {s.get('strategy_type', '-')} | {s.get('six_dim_score', '-'):.1f} | {fusion} | {tech} | {chip} | {macro} |\n")
            else:
                f.write(f"- 选股结果: 无\n")
            
            # 1.1 三模型融合摘要
            if selection_result and selection_result.get('stocks'):
                stocks = selection_result['stocks']
                fusion_scores = [s.get('fusion_score') for s in stocks if s.get('fusion_score') is not None]
                if fusion_scores:
                    avg_fusion = sum(fusion_scores) / len(fusion_scores)
                    f.write(f"\n### 三模型融合摘要\n\n")
                    f.write(f"- 融合评分均值: {avg_fusion:.2f}\n")
                    f.write(f"- 技术面均分: {sum(s.get('technical_score', 50) for s in stocks if s.get('technical_score')) / max(len(stocks), 1):.2f}\n")
                    f.write(f"- 筹码面均分: {sum(s.get('chip_score', 50) for s in stocks if s.get('chip_score')) / max(len(stocks), 1):.2f}\n")
                    f.write(f"- 宏观面均分: {sum(s.get('macro_score', 50) for s in stocks if s.get('macro_score')) / max(len(stocks), 1):.2f}\n")
            
            # 1.2 市场状态
            try:
                from market_status_detector import get_market_status
                market_status = get_market_status()
                f.write(f"\n### 市场状态\n\n")
                f.write(f"- 当前状态: **{market_status['status']}**\n")
                f.write(f"- 风险等级: {market_status['risk_level']}\n")
                f.write(f"- 近5日涨跌: {market_status['recent_5d']:.2f}%\n")
                f.write(f"- 近10日涨跌: {market_status['recent_10d']:.2f}%\n")
                f.write(f"- 近20日涨跌: {market_status['recent_20d']:.2f}%\n")
                f.write(f"- 描述: {market_status['description']}\n")
                f.write(f"\n> 权重动态调整: 牛市技术50%/筹码30%/宏观20%，熊市技术30%/筹码20%/宏观50%，震荡市技术40%/筹码30%/宏观30%\n")
            except Exception as e:
                logger.warning(f"市场状态获取失败: {e}")
            
            # 1.3 高频代理变量
            try:
                import pandas as pd
                proxy_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'macro_factors_with_proxies.parquet')
                if os.path.exists(proxy_path):
                    proxy_df = pd.read_parquet(proxy_path)
                    latest_date = proxy_df['trade_date'].max()
                    latest = proxy_df[proxy_df['trade_date'] == latest_date]
                    
                    f.write(f"\n### 高频代理变量（{latest_date.strftime('%Y-%m-%d')}）\n\n")
                    
                    for col in ['pmi_proxy', 'ppi_proxy', 'liquidity_proxy']:
                        if col in latest.columns:
                            val = latest[col].iloc[0]
                            if pd.notna(val):
                                if col == 'pmi_proxy':
                                    desc = f"PMI代理: {val:.1f} (范围40-55)"
                                elif col == 'ppi_proxy':
                                    desc = f"PPI代理: {val:.1f} (范围-5到+5)"
                                else:
                                    desc = f"流动性代理: {val:.4f}"
                                f.write(f"- {desc}\n")
                    f.write(f"\n> 代理变量用于弥补官方月度数据滞后，提升宏观信号时效性\n")
            except Exception as e:
                logger.warning(f"高频代理展示失败: {e}")
            
            # 1.4 宏观因子信号
            try:
                import pandas as pd
                macro_factors_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'macro_factors.parquet')
                if os.path.exists(macro_factors_path):
                    factors = pd.read_parquet(macro_factors_path)
                    latest_date = factors['trade_date'].max()
                    latest = factors[factors['trade_date'] == latest_date]
                    
                    f.write(f"\n### 宏观因子信号（{latest_date.strftime('%Y-%m-%d')}）\n\n")
                    
                    signal_cols = [c for c in latest.columns if c.endswith('_signal')]
                    for col in signal_cols:
                        if col in latest.columns:
                            val = latest[col].iloc[0]
                            if pd.notna(val):
                                direction = "看多" if val > 0 else "看空" if val < 0 else "中性"
                                f.write(f"- {col.replace('_signal', '')}: {direction} ({val:.2f})\n")
            except Exception as e:
                logger.warning(f"宏观因子信号展示失败: {e}")
            
            # 2. 回测结果摘要
            f.write(f"\n## 二、回测摘要\n\n")
            if backtest_result and 'report' in backtest_result:
                f.write(f"- 回测报告: 已生成\n")
                f.write(f"- 详细内容: `reports/backtest_v3_20260625.md`\n")
            else:
                f.write(f"- 回测状态: 失败或无数据\n")
            
            # 3. 模拟交易结果
            f.write(f"\n## 三、模拟交易\n\n")
            if papertrade_result:
                if papertrade_result.get('status') == 'success':
                    f.write(f"- 日期: {papertrade_result.get('date')}\n")
                    f.write(f"- 净值: {papertrade_result.get('nav', 0):,.0f}\n")
                    f.write(f"- 现金: {papertrade_result.get('cash', 0):,.0f}\n")
                    f.write(f"- 持仓数: {papertrade_result.get('holdings_count', 0)}\n")
                    f.write(f"- 交易数: {papertrade_result.get('trade_count', 0)}\n")
                else:
                    f.write(f"- 状态: {papertrade_result.get('status', 'unknown')}\n")
                    f.write(f"- 原因: {papertrade_result.get('reason', '-')}\n")
            else:
                f.write(f"- 状态: 未执行\n")
            
            # 4. 操作建议
            f.write(f"\n## 四、操作建议\n\n")
            growth_count = selection_result.get('growth_count', 0) if selection_result else 0
            value_count = selection_result.get('value_count', 0) if selection_result else 0
            
            if growth_count > 0 or value_count > 0:
                f.write(f"- 候选池: 成长{growth_count}只 + 价值{value_count}只\n")
                f.write(f"- 建议: 关注评分≥70分的标的，触发买入信号后执行建仓\n")
                f.write(f"- 风险: 严格执行止损止盈，单股仓位不超过15%\n")
            else:
                f.write(f"- 建议: 当前无合格标的，保持观望\n")
            
            f.write(f"\n---\n*本报告由 run_full_analysis.py 自动生成*\n")
        
        logger.info(f"📄 日报已生成: {report_path}")
        
        # 生成 HTML 可视化日报
        try:
            from html_report_generator import generate_html_report
            html_result = generate_html_report()
            logger.info(f"🌐 HTML报告已生成: {html_result.get('report_path', 'unknown')}")
        except Exception as e:
            logger.warning(f"HTML报告生成失败: {e}")
        
        return {'report_path': str(report_path), 'html_report_path': str(html_report_path)}
    
    except Exception as e:
        logger.error(f"日报生成失败: {e}")
        return {'error': str(e)}


def main():
    import argparse
    parser = argparse.ArgumentParser(description='股票分析系统全流程总控')
    parser.add_argument('--skip-selection', action='store_true', 
                       help='跳过选股步骤，直接运行回测+模拟交易+日报')
    parser.add_argument('--skip-backtest', action='store_true',
                       help='跳过回测步骤')
    parser.add_argument('--skip-papertrade', action='store_true',
                       help='跳过模拟交易步骤')
    parser.add_argument('--skip-report', action='store_true',
                       help='跳过日报生成步骤')
    parser.add_argument('--date', type=str, default=None,
                       help='指定日期 (YYYY-MM-DD)，默认今天')
    
    args = parser.parse_args()
    
    start_time = datetime.datetime.now()
    today = args.date or datetime.datetime.now().strftime('%Y-%m-%d')
    
    logger.info("=" * 70)
    logger.info(f"🚀 全流程分析开始 [{today}]")
    logger.info("=" * 70)
    
    selection_result = None
    backtest_result = None
    papertrade_result = None
    report_result = None
    
    # 步骤1：选股
    if not args.skip_selection:
        selection_result = run_step("步骤1：选股", step_selection)
    else:
        logger.info("⏭️  跳过选股（--skip-selection）")
    
    # 步骤2：回测
    if not args.skip_backtest:
        backtest_result = run_step("步骤2：回测", step_backtest)
    else:
        logger.info("⏭️  跳过回测（--skip-backtest）")
    
    # 步骤3：模拟交易
    if not args.skip_papertrade:
        papertrade_result = run_step("步骤3：模拟交易", step_paper_trade)
    else:
        logger.info("⏭️  跳过模拟交易（--skip-papertrade）")
    
    # 步骤4：日报生成
    if not args.skip_report:
        report_result = run_step("步骤4：日报生成", lambda: step_report(selection_result, backtest_result, papertrade_result))
    else:
        logger.info("⏭️  跳过日报生成（--skip-report）")
    
    # 汇总
    elapsed = (datetime.datetime.now() - start_time).total_seconds()
    logger.info("=" * 70)
    logger.info("✅ 全流程分析完成")
    logger.info("=" * 70)
    logger.info(f"⏱️  耗时: {elapsed:.1f}秒")
    logger.info(f"📊 选股: 成长{selection_result.get('growth_count', 0) if selection_result else 0}只 + 价值{selection_result.get('value_count', 0) if selection_result else 0}只")
    logger.info(f"📈 回测: {'成功' if backtest_result and 'error' not in backtest_result else '失败'}")
    logger.info(f"💼 模拟交易: {papertrade_result.get('status', 'unknown') if papertrade_result else '未执行'}")
    if report_result and 'report_path' in report_result:
        logger.info(f"📄 日报: {report_result['report_path']}")
    
    # 汇总结果字典
    summary = {
        'selection': selection_result,
        'backtest': backtest_result,
        'papertrade': papertrade_result,
        'report': report_result,
        'elapsed_seconds': elapsed
    }
    
    # 将 Path 对象转为字符串，避免 JSON 序列化失败
    def _convert(obj):
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, dict):
            return {k: _convert(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_convert(v) for v in obj]
        return obj

    return _convert(summary)


if __name__ == '__main__':
    result = main()
    print(json.dumps(result, ensure_ascii=False, indent=2))
