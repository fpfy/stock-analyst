"""
补全指定股票的最新 valuation_data 和 technical_indicators
只处理 688266.SH 和 301666.SZ
"""
import sqlite3
import time
import os
from datetime import datetime

# 统一限流器
try:
    from rate_limiter import tushare_limiter
except ImportError:
    class _Dummy:
        def wait(self, **kw): time.sleep(1.5)
    tushare_limiter = _Dummy()

import tushare as ts

DB_PATH = os.path.join(os.path.dirname(__file__), 'database', 'stock_analysis.db')
TOKEN = os.environ.get('TUSHARE_TOKEN', '')
ts.set_token(TOKEN)
pro = ts.pro_api()

CODES = ['688266.SH', '301666.SZ']


def backfill_valuation(code):
    """补全 valuation_data"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 已有最新日期
    cur.execute("SELECT MAX(trade_date) FROM valuation_data WHERE ts_code = ?", (code,))
    row = cur.fetchone()
    latest = row[0] if row and row[0] else None
    print(f"[{code}] valuation_data latest={latest}")

    # 拉取最近60个交易日
    tushare_limiter.wait(min_interval=0.8, max_interval=1.5)
    try:
        df = pro.daily_basic(ts_code=code, start_date='20260101' if not latest else latest,
                            end_date=datetime.now().strftime('%Y%m%d'))
    except Exception as e:
        print(f"[{code}] daily_basic error: {e}")
        conn.close()
        return 0

    if df is None or df.empty:
        print(f"[{code}] daily_basic empty")
        conn.close()
        return 0

    inserted = 0
    for _, row in df.iterrows():
        td = str(row['trade_date'])
        cur.execute("""
            INSERT OR IGNORE INTO valuation_data
            (ts_code, trade_date, close, pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm, total_mv, circ_mv)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            code, td,
            float(row['close']) if 'close' in row and row['close'] is not None else None,
            float(row['pe']) if 'pe' in row and row['pe'] is not None else None,
            float(row['pe_ttm']) if 'pe_ttm' in row and row['pe_ttm'] is not None else None,
            float(row['pb']) if 'pb' in row and row['pb'] is not None else None,
            float(row['ps']) if 'ps' in row and row['ps'] is not None else None,
            float(row['ps_ttm']) if 'ps_ttm' in row and row['ps_ttm'] is not None else None,
            float(row['dv_ratio']) if 'dv_ratio' in row and row['dv_ratio'] is not None else None,
            float(row['dv_ttm']) if 'dv_ttm' in row and row['dv_ttm'] is not None else None,
            float(row['total_mv']) if 'total_mv' in row and row['total_mv'] is not None else None,
            float(row['circ_mv']) if 'circ_mv' in row and row['circ_mv'] is not None else None,
        ))
        inserted += cur.rowcount

    conn.commit()
    cur.execute("SELECT COUNT(*), MAX(trade_date), MIN(pe), MAX(pe) FROM valuation_data WHERE ts_code = ?", (code,))
    r = cur.fetchone()
    print(f"[{code}] valuation_data: total={r[0]} max_date={r[1]} pe_range={r[2]}~{r[3]}")
    conn.close()
    return inserted


def backfill_technical(code):
    """补全 technical_indicators（通过 daily 数据计算或直接拉取）"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 检查是否已有数据
    cur.execute("SELECT COUNT(*) FROM technical_indicators WHERE ts_code = ?", (code,))
    existing = cur.fetchone()[0]
    print(f"[{code}] technical_indicators existing={existing}")

    if existing > 0:
        print(f"[{code}] technical_indicators 已有数据，跳过")
        conn.close()
        return 0

    # 尝试从 daily 数据计算
    print(f"[{code}] 尝试从 daily 数据计算技术指标...")
    try:
        from technical_calculator import TechnicalCalculator
        calc = TechnicalCalculator(code)
        calc.calculate_all()
        calc.save_to_db(cur)
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM technical_indicators WHERE ts_code = ?", (code,))
        r = cur.fetchone()
        print(f"[{code}] technical_indicators 计算完成: total={r[0]}")
        conn.close()
        return r[0]
    except ImportError:
        print(f"[{code}] technical_calculator 不可用，尝试从 tushare 拉取...")
        # 回退：从 tushare 拉取技术指标（如果支持）
        conn.close()
        return 0


def main():
    print("=" * 60)
    print("补全 valuation_data + technical_indicators")
    print("=" * 60)

    for code in CODES:
        print(f"\n--- {code} ---")
        v = backfill_valuation(code)
        t = backfill_technical(code)
        print(f"[{code}] valuation +{v}, technical +{t}")


if __name__ == '__main__':
    main()
