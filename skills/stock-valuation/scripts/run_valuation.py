"""
stock-valuation CLI 入口
用法：
  python run_valuation.py --code 000651.SZ
  python run_valuation.py --code 000651.SZ --method all
"""
import sys
import os
import argparse

# 脚本位于 skills/stock-valuation/scripts/run_valuation.py
# 往上3级定位项目根目录 C:/Users/fengpeng/stock_analysis_system
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR)))
sys.path.insert(0, PROJECT_ROOT)


def main():
    parser = argparse.ArgumentParser(description="stock-valuation Skill 入口")
    parser.add_argument("--code", required=True, help="股票代码，如 000651.SZ")
    parser.add_argument("--method", default="all",
                        choices=["percentile", "triangular", "anomaly", "all"])
    args = parser.parse_args()

    import sqlite3
    from stock_valuation import ValuationAnalyzer

    conn = sqlite3.connect('database/stock_analysis.db')
    cursor = conn.cursor()
    analyzer = ValuationAnalyzer(cursor, ts_code=args.code)

    if args.method in ("percentile", "all"):
        r = analyzer.percentile_analysis()
        print(f"[估值分位] PE={r.get('pe_current')} 分位={r.get('pe_percentile')}%  "
              f"PB={r.get('pb_current')} 分位={r.get('pb_percentile')}%  "
              f"股息率={r.get('dividend_yield')}")

    if args.method in ("triangular", "all"):
        r = analyzer.triangular_analysis()
        print(f"[估值三角] 评分={r.get('valuation_score')} 评级={r.get('rating')}  "
              f"低估={r.get('is_undervalued')}")

    if args.method in ("anomaly", "all"):
        r = analyzer.detect_anomaly()
        print(f"[异常检测] 异常={r.get('is_anomaly')} 类型={r.get('anomaly_type')}  "
              f"偏离={r.get('deviation_pct', 0):.1%} 严重={r.get('severity')}")


if __name__ == "__main__":
    main()
