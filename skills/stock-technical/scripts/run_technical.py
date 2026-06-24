"""
stock-technical 入口脚本
用法：
  python run_technical.py --code 000651.SZ
  python run_technical.py --code 600519.SH --days 120
"""
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def main():
    parser = __import__('argparse').ArgumentParser(description="stock-technical Skill 入口")
    parser.add_argument("--code", required=True, help="股票代码，如 000651.SZ")
    parser.add_argument("--days", type=int, default=60, help="回溯天数")
    args = parser.parse_args()

    os.chdir(PROJECT_ROOT)

    import sqlite3
    from technical_scorer import TechnicalScorer

    conn = sqlite3.connect('database/stock_analysis.db')
    cursor = conn.cursor()

    scorer = TechnicalScorer(cursor)
    dims = scorer.score_technical(args.code)
    total = sum(dims.values())
    grade = scorer.get_technical_grade(total)
    signals = scorer.analyze_technical_signals(args.code)

    print(f"股票: {args.code}")
    print(f"综合评分: {total}/100 ({grade})")
    print(f"交易信号: {signals.get('signal', 'N/A')}")
    print("分项评分:")
    for k, v in dims.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
