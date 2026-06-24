"""
历史数据补齐脚本（优化版）
按报告期批量拉取财务，大幅降低Tushare调用频次
"""

import os, sys, time, logging, sqlite3
from datetime import datetime, timedelta

# 统一限流器
from rate_limiter import tushare_limiter

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'stock_analysis.db')

FIN_NEEDED = [
    '20230331', '20230630', '20230930', '20231231',
    '20240331', '20240630', '20240930', '20241231',
    '20250331', '20250630', '20250930', '20251231',
]
VAL_START = '20220101'
VAL_END   = '20260612'

# ============================================================
# 1. 财务：按报告期批量拉取（ann_date处于报告期公布的月份区间内）
# ============================================================
def fetch_missing_financial():
    import tushare as ts
    token = os.environ.get('TUSHARE_TOKEN', '')
    if not token:
        logger.error('TUSHARE_TOKEN 未设置')
        return
    ts.set_token(token)
    pro = ts.pro_api()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT DISTINCT end_date FROM financial_data ORDER BY end_date')
    existing = {r[0] for r in cursor.fetchall()}
    needed = [p for p in FIN_NEEDED if p not in existing]
    if not needed:
        logger.info('财务数据已完整，无需补全')
        conn.close()
        return

    logger.info(f'需要补的财务报告期: {needed}')

    total_success = 0
    total_fail = 0
    for period in needed:
        year = int(period[:4])
        month = int(period[4:6]) if period[4:6] != '12' else 12
        date_str = period
        logger.info(f'--- 拉取 {period} ---')
        try:
            # 请求前限流 - 每个周期一次 API 调用
            tushare_limiter.wait(min_interval=1.5, max_interval=3.0)
            # 按报告期日期筛选（end_date=period）
            df = pro.fina_indicator(
                end_date=period,
                fields='ts_code,end_date,ann_date,'
                       'roe_yearly,roa,grossprofit_margin,netprofit_margin,debt_ratio,'
                       'revenue_yoy,netprofit_yoy,op_yoy,'
                       'eps,bps,total_assets,total_liab,current_assets,current_liab,operating_cf'
            )
            if df is None or df.empty:
                logger.warning(f'  空')
                continue
            df = df[df['end_date'] == period]
            count = 0
            for _, row in df.iterrows():
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO financial_data
                        (ts_code,end_date,ann_date,
                         roe,roa,gross_margin,net_margin,debt_ratio,
                         revenue_yoy,net_profit_yoy,op_yoy,
                         eps,bps,total_assets,total_liab,
                         current_assets,current_liab,operating_cf)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ''', (
                        row.get('ts_code',''),
                        str(row.get('end_date','')),
                        str(row.get('ann_date','')),
                        row.get('roe_yearly'), row.get('roa'),
                        row.get('grossprofit_margin'), row.get('netprofit_margin'), row.get('debt_ratio'),
                        row.get('revenue_yoy'), row.get('netprofit_yoy'), row.get('op_yoy'),
                        row.get('eps'), row.get('bps'),
                        row.get('total_assets'), row.get('total_liab'),
                        row.get('current_assets'), row.get('current_liab'),
                        row.get('operating_cf')
                    ))
                    count += 1
                except Exception: pass
            conn.commit()
            logger.info(f'  +{count}')
            total_success += count
            time.sleep(1)
        except Exception as e:
            total_fail += 1
            logger.error(f'  失败: {e}')
            time.sleep(2)

    conn.close()
    logger.info(f'财务完成: 成功{total_success}条, 失败{total_fail}次')


# ============================================================
# 2. 估值：用 AkShare 补全历史日线
# ============================================================
def fetch_missing_valuation():
    import akshare as ak
    import pandas as pd

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT ts_code, symbol FROM stock_basic WHERE is_st=0')
    stocks = cursor.fetchall()
    logger.info(f'估值补全: 共 {len(stocks)} 只')

    success = 0
    fail = 0
    skip = 0

    for idx, (ts_code, symbol) in enumerate(stocks):
        try:
            hist = ak.stock_zh_a_hist(
                symbol=symbol,
                period='daily',
                start_date=VAL_START,
                end_date=VAL_END,
                adjust='qfq'
            )
            if hist is None or hist.empty:
                skip += 1
                continue
            hist['日期'] = pd.to_datetime(hist['日期'])
            hist = hist.sort_values('日期')
            count = 0
            for _, row in hist.iterrows():
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO valuation_data
                        (ts_code, trade_date, close, pe, pe_ttm, pb)
                        VALUES (?,?,?,?,?,?)
                    ''', (
                        ts_code,
                        row['日期'].strftime('%Y%m%d'),
                        float(row['收盘']) if pd.notna(row.get('收盘')) else None,
                        float(row['市盈率-动态']) if pd.notna(row.get('市盈率-动态')) else None,
                        float(row['市盈率-动态']) if pd.notna(row.get('市盈率-动态')) else None,
                        float(row['市净率']) if pd.notna(row.get('市净率')) else None,
                    ))
                    count += 1
                except Exception: pass
            conn.commit()
            success += 1
            if success % 100 == 0:
                logger.info(f'  进度: {success}/{len(stocks)} (+{count})')
        except Exception as e:
            fail += 1
        time.sleep(0.22)

    cursor.execute('SELECT COUNT(DISTINCT trade_date) FROM valuation_data')
    days = cursor.fetchone()[0]
    conn.close()
    logger.info(f'估值完成: 成功{success} 跳过{skip} 失败{fail} 交易日{days}')


if __name__ == '__main__':
    logger.info('=== 历史数据补齐开始 ===')
    fetch_missing_financial()
    fetch_missing_valuation()
    logger.info('=== 历史数据补齐结束 ===')
