"""
更新指定股票 valuation_data 到最新，并重建 trading_strategy 建议。
"""
import sqlite3, os, time
from datetime import datetime

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

CODES = ['000651.SZ', '000568.SZ', '001309.SZ', '688266.SH', '002582.SZ', '301308.SZ']

def backfill_valuation(code):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT MAX(trade_date) FROM valuation_data WHERE ts_code = ?", (code,))
    row = cur.fetchone()
    latest = row[0] if row and row[0] else None
    print(f"[{code}] valuation_data latest={latest}")

    start = latest if latest else '20240101'
    end = datetime.now().strftime('%Y%m%d')
    tushare_limiter.wait(min_interval=0.8, max_interval=1.5)
    try:
        df = pro.daily_basic(ts_code=code, start_date=start, end_date=end)
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
    cur.execute("SELECT COUNT(*), MAX(trade_date) FROM valuation_data WHERE ts_code = ?", (code,))
    r = cur.fetchone()
    print(f"[{code}] valuation_data: total={r[0]} max_date={r[1]}")
    conn.close()
    return inserted

def update_trading_strategy_prices():
    """用 valuation_data 最新价格更新 trading_strategy 的 current_price，不改变 report_date"""
    import time
    time.sleep(2)  # 等待主流程数据库连接完全释放
    max_retries = 8
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(DB_PATH, timeout=30)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            # 先执行 checkpoint，确保 WAL 文件数据合并到主数据库
            try:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                conn.commit()
            except Exception:
                pass
            cur = conn.cursor()

            updated = 0
            for code in CODES:
                cur.execute("""
                    SELECT MAX(trade_date), close FROM valuation_data WHERE ts_code = ?
                """, (code,))
                row = cur.fetchone()
                if not row or not row[0] or row[1] is None:
                    print(f"[{code}] no valuation_data for price update")
                    continue
                trade_date, close = row
                cur.execute("""
                    UPDATE trading_strategy
                    SET current_price = ?
                    WHERE ts_code = ? AND action = 'BUY'
                """, (close, code))
                updated += cur.rowcount
            conn.commit()
            conn.close()
            print(f"trading_strategy price updated rows={updated}")
            return
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                wait = 2 + attempt * 3
                print(f"[REFRESH] database locked, retry {attempt+1}/{max_retries}, wait {wait}s")
                time.sleep(wait)
            else:
                raise

def main():
    print("="*60)
    print("更新 valuation_data 并刷新 trading_strategy 价格")
    print("="*60)
    for code in CODES:
        print(f"\n--- {code} ---")
        v = backfill_valuation(code)
        print(f"[{code}] valuation +{v}")
    update_trading_strategy_prices()
    print("="*60)
    print("更新完成")

if __name__ == '__main__':
    main()
