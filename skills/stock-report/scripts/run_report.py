"""
stock-report 入口脚本
用法：
  python run_report.py --type daily
  python run_report.py --type macro
  python run_report.py --type backtest --start 2024-01-01 --end 2024-12-31
  python run_report.py --type papertrader --start 2024-01-01 --end 2024-12-31
  python run_report.py --type valuation --code 000651.SZ
  python run_report.py --type technical --code 000651.SZ
"""
import sys
import os
import argparse
from datetime import date

# 脚本位于 skills/stock-report/scripts/run_report.py
# 往上3级到达项目根目录 C:/Users/fengpeng/stock_analysis_system
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR)))
sys.path.insert(0, PROJECT_ROOT)


def run_daily():
    """生成当日日报（基于 stock-analysis 的 main_v3.py）"""
    os.chdir(PROJECT_ROOT)
    import main_v3
    result = main_v3.main()
    if result and isinstance(result, dict):
        print(f"日报已生成: {result.get('report_path', 'N/A')}")
    return result


def run_macro():
    """生成宏观分析报告"""
    os.chdir(PROJECT_ROOT)
    from macro_analyzer import MacroAnalyzer
    analyzer = MacroAnalyzer()
    analyzer.fetch_pmi(months=24)

    report_date = date.today().isoformat()
    report_path = os.path.join(PROJECT_ROOT, 'reports', f'macro_report_{report_date}.md')
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# 宏观分析报告 {report_date}\n\n")
        f.write(f"## 市场状态\n\n")
        f.write(f"- **PMI 趋势**: {analyzer.pmi_trend}\n")
        f.write(f"- **市场状态**: {analyzer.market_state}\n")
        f.write(f"- **成长仓位上限**: {analyzer.get_position_cap('growth'):.0%}\n")
        f.write(f"- **价值仓位上限**: {analyzer.get_position_cap('value'):.0%}\n\n")
        f.write(f"## 仓位配置建议\n\n")
        state = analyzer.market_state
        if state == '强多':
            f.write("- 成长股: 40% | 价值股: 35% | 现金: 25%\n")
        elif state == '震荡':
            f.write("- 成长股: 30% | 价值股: 25% | 现金: 45%\n")
        elif state == '弱空':
            f.write("- 成长股: 15% | 价值股: 20% | 现金: 65%\n")
        else:
            f.write("- 成长股: 20% | 价值股: 20% | 现金: 60%\n")

    print(f"宏观报告已生成: {report_path}")


def run_backtest(start, end):
    """生成回测报告"""
    os.chdir(PROJECT_ROOT)
    import backtest_v3
    sys.argv = [
        "backtest_v3.py",
        "--strategy", "all",
        "--start", start,
        "--end", end,
        "--hold-days", "30",
    ]
    backtest_v3.main()


def run_papertrader(start, end):
    """生成模拟交易报告"""
    os.chdir(PROJECT_ROOT)
    import papertrader_final
    sys.argv = [
        "papertrader_final.py",
        "--start-date", start,
        "--end-date", end,
        "--cash", "1000000",
    ]
    papertrader_final.main()


def run_valuation(ts_code):
    """生成估值分析报告"""
    os.chdir(PROJECT_ROOT)
    import sqlite3
    from stock_valuation import ValuationAnalyzer

    conn = sqlite3.connect('database/stock_analysis.db')
    cursor = conn.cursor()
    analyzer = ValuationAnalyzer(cursor, ts_code=ts_code)

    result = analyzer.valuation_score()
    report_date = date.today().isoformat()
    report_path = os.path.join(PROJECT_ROOT, 'reports', f'valuation_{ts_code}_{report_date}.md')
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# 估值分析报告 {ts_code} {report_date}\n\n")
        f.write(f"## 估值分位\n\n")
        f.write(f"- **PE 当前**: {result.get('pe_current', 'N/A')}\n")
        f.write(f"- **PE 分位**: {result.get('pe_score', 'N/A')}%\n")
        f.write(f"- **PB 当前**: {result.get('pb_current', 'N/A')}\n")
        f.write(f"- **PB 分位**: {result.get('pb_score', 'N/A')}%\n")
        f.write(f"- **股息率**: {result.get('dividend_score', 'N/A')}\n\n")
        f.write(f"## 估值评分\n\n")
        f.write(f"- **综合评分**: {result.get('valuation_score', 'N/A')}/100\n")
        f.write(f"- **评级**: {result.get('rating', 'N/A')}\n")
        f.write(f"- **是否低估**: {'是' if result.get('is_undervalued') else '否'}\n\n")

        anomaly = result.get('anomaly', {})
        if anomaly.get('is_anomaly'):
            f.write(f"## 异常检测\n\n")
            f.write(f"- **异常类型**: {anomaly.get('anomaly_type')}\n")
            f.write(f"- **偏离度**: {anomaly.get('deviation_pct', 0):.1%}\n")
            f.write(f"- **严重程度**: {anomaly.get('severity')}\n")

    print(f"估值报告已生成: {report_path}")


def run_technical(ts_code):
    """生成技术评分报告"""
    os.chdir(PROJECT_ROOT)
    import sqlite3
    from technical_scorer import TechnicalScorer

    conn = sqlite3.connect('database/stock_analysis.db')
    cursor = conn.cursor()
    scorer = TechnicalScorer(cursor)

    dims = scorer.score_technical(ts_code)
    total = sum(dims.values())
    grade = scorer.get_technical_grade(total)

    report_date = date.today().isoformat()
    report_path = os.path.join(PROJECT_ROOT, 'reports', f'technical_{ts_code}_{report_date}.md')
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# 技术评分报告 {ts_code} {report_date}\n\n")
        f.write(f"## 综合评分\n\n")
        f.write(f"- **总分**: {total}/100\n")
        f.write(f"- **评级**: {grade}\n\n")
        f.write(f"## 分项评分\n\n")
        for k, v in dims.items():
            f.write(f"- {k}: {v}\n")

    print(f"技术评分报告已生成: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="stock-report Skill 入口")
    parser.add_argument("--type", required=True,
                        choices=["daily", "macro", "backtest", "papertrader",
                                 "valuation", "technical"])
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--code", default="000651.SZ", help="股票代码（valuation/technical 类型需要）")
    args = parser.parse_args()

    if args.type == "daily":
        run_daily()
    elif args.type == "macro":
        run_macro()
    elif args.type == "backtest":
        run_backtest(args.start, args.end)
    elif args.type == "papertrader":
        run_papertrader(args.start, args.end)
    elif args.type == "valuation":
        run_valuation(args.code)
    elif args.type == "technical":
        run_technical(args.code)


if __name__ == "__main__":
    main()
