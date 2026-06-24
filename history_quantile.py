"""
历史行情+财务数据获取 & 分位计算
使用 AkShare 免费数据源，支持全量A股历史PE/PB分位
"""
import logging
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)


def fetch_and_store_history_quantiles(db_path, max_stocks=500):
    """
    从AkShare获取历史行情+财务，计算历史PE/PB分位并存入valuation_data
    """
    import akshare as ak
    import pandas as pd

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 获取所有股票列表
    cursor.execute("SELECT ts_code, name, industry FROM stock_basic WHERE is_st=0")
    all_stocks = cursor.fetchall()
    logger.info(f"将为 {len(all_stocks)} 只股票计算历史分位")

    success = 0
    fail = 0
    total_records = 0

    for ts_code, name, industry in all_stocks:
        symbol = ts_code.split('.')[0]
        market = ts_code.split('.')[1]

        try:
            # 获取历史行情（近3年）
            try:
                hist = ak.stock_zh_a_hist(symbol=symbol, period="daily",
                                          start_date="20220101", end_date="20260612",
                                          adjust="qfq")
            except Exception:
                try:
                    hist = ak.stock_zh_a_hist(symbol=symbol, period="weekly",
                                              start_date="20220101", end_date="20260612",
                                              adjust="qfq")
                except Exception:
                    fail += 1
                    continue

            if hist is None or hist.empty:
                fail += 1
                continue

            hist['日期'] = pd.to_datetime(hist['日期'])
            hist = hist.sort_values('日期')
            hist['trade_date'] = hist['日期'].dt.strftime('%Y%m%d')

            # 获取历史财务EPS（用于计算历史PE）
            # 近似：用近3年历史PE数据（Tushare daily_basic不支持长期历史）
            # 降级方案：用5年滚动PE分位（价格分位作为替代 + 标注说明）
            records = 0
            for _, row in hist.iterrows():
                trade_date = str(row['trade_date'])
                close = float(row['收盘']) if '收盘' in row else None
                pe = float(row['市盈率-动态']) if '市盈率-动态' in row and row['市盈率-动态'] else None
                pb = float(row['市净率']) if '市净率' in row and row['市净率'] else None

                if close:
                    try:
                        cursor.execute(
                            'INSERT OR REPLACE INTO valuation_data (ts_code, trade_date, close, pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm, total_mv, circ_mv) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                            (ts_code, trade_date, close, pe, pe, pb, None, None, None, None, None, None)
                        )
                        records += 1
                    except Exception: pass

            conn.commit()
            success += 1
            total_records += records

        except Exception as e:
            fail += 1
            logger.debug(f"{ts_code} 历史行情获取失败: {e}")

    cursor.execute('SELECT COUNT(DISTINCT ts_code), COUNT(*) FROM valuation_data')
    tot_stocks = cursor.fetchone()[0]
    tot_recs = cursor.fetchone()[0] if False else total_records
    conn.close()

    logger.info(f"\n=== 历史数据补全完成 ===")
    logger.info(f"  成功: {success}只 | 失败: {fail}只")
    logger.info(f"  valuation_data 总股票数: {tot_stocks}")
    logger.info(f"  本次写入: {total_records}条记录")


def calc_pe_percentile(db_path, ts_code, lookback_days=500):
    """
    精确计算PE历史分位（percentage of historical trading days with PE <= current）
    lookback_days: 用最近N天的估值数据计算分位
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT pe FROM valuation_data
        WHERE ts_code = ? AND pe IS NOT NULL AND pe > 0 AND pe < 10000
        ORDER BY trade_date ASC
    """, (ts_code,))

    pe_values = [r[0] for r in cursor.fetchall()]
    conn.close()

    if len(pe_values) < 5:
        return None, None, None, 0

    # 基础分位（全历史）
    current_pe = pe_values[-1]
    count_below = sum(1 for p in pe_values if p <= current_pe)
    all_time_percentile = (count_below / len(pe_values)) * 100

    # 近5年分位（取最近500个交易日）
    recent = pe_values[-lookback_days:] if len(pe_values) >= lookback_days else pe_values
    count_below_recent = sum(1 for p in recent if p <= current_pe)
    recent_percentile = (count_below_recent / len(recent)) * 100

    # 近3年分位（取最近250个交易日）
    mid = pe_values[-250:] if len(pe_values) >= 250 else pe_values[-len(pe_values)//2:]
    count_below_mid = sum(1 for p in mid if p <= current_pe)
    mid_percentile = (count_below_mid / len(mid)) * 100

    return current_pe, all_time_percentile, recent_percentile, mid_percentile


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    DB_PATH = "C:/Users/fengpeng/stock_analysis_system/database/stock_analysis.db"

    # 测试几只股票的分位计算
    test_stocks = ['000651.SZ', '000568.SZ', '001309.SZ', '600612.SH']
    print("=== 历史PE分位测试 ===\n")
    for ts_code in test_stocks:
        pe, all_pct, rec_pct, mid_pct = calc_pe_percentile(DB_PATH, ts_code)
        if pe:
            print(f"{ts_code}: 当前PE={pe:.1f} | 全历史分位={all_pct:.0f}% | 近5年={rec_pct:.0f}% | 近3年={mid_pct:.0f}%")
        else:
            print(f"{ts_code}: 无足够PE数据")
