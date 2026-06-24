"""
拉取更长时间跨度的估值数据（PE/PB等）
分批拉取，每次90天，覆盖过去3年
"""

import logging
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

# 统一限流器
from rate_limiter import tushare_limiter

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# 获取所有股票代码
db_path = Path(__file__).parent / "database" / "stock_analysis.db"
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()
cursor.execute("SELECT ts_code FROM stock_basic WHERE is_st=0 AND (ts_code LIKE '%.SH' OR ts_code LIKE '%.SZ')")
stocks = [r[0] for r in cursor.fetchall()]
conn.close()

logger.info(f"需要拉取估值数据的股票: {len(stocks)}只")

# 初始化Tushare
import tushare as ts
import os
token = os.environ.get('TUSHARE_TOKEN', '')
ts.set_token(token)
pro = ts.pro_api()
logger.info("Tushare初始化成功")

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# 时间策略：拉取过去3年的估值数据
# 每次拉取90天，分12个批次覆盖3年（但实际上只有已有数据的补充）
today = datetime.now()
# 已有数据最早日期: 20260316，从那之前再拉2年+的年度数据

# 分段拉取：2024Q1, 2024Q2, 2024Q3, 2024Q4, 2025Q1, 2025Q2, 2025H2, 2026H1
# 每个季度最后一个月拉取
# 用月末日期以确保包含整季度数据

time_periods = [
    # (start, end, label)
    ('20240101', '20240331', '2024Q1'),
    ('20240401', '20240630', '2024Q2'),
    ('20240701', '20240930', '2024Q3'),
    ('20241001', '20241231', '2024Q4'),
    ('20250101', '20250315', '2025H1'),
    ('20250316', '20250611', '2025H2(已有)'),
]

# 只拉取还没有数据的时间段
existing_dates = set()
cursor.execute("SELECT DISTINCT trade_date FROM valuation_data")
for r in cursor.fetchall():
    existing_dates.add(r[0])

# 对每个时间段，只拉取还没有数据的那些交易日中的第一只股票的估值数据
# 实际上，我们需要判断该日期是否已拉取过全部股票

# 简化策略：先检查哪些日期已经有数据
cursor.execute("SELECT MIN(trade_date) FROM valuation_data")
min_existing = cursor.fetchone()[0]
logger.info(f"已有数据最早日期: {min_existing}")

# 如果已有数据最早是20260316，那么我们需要拉取2024-01-01到2026-03-15的数据
target_start = '20240101'
target_end = '20260315'

logger.info(f"目标拉取区间: {target_start} ~ {target_end}")

# 分批拉取（每次90天）
batch_starts = []
s = datetime.strptime(target_start, '%Y%m%d')
e = datetime.strptime(target_end, '%Y%m%d')
while s < e:
    batch_end = min(s + timedelta(days=89), e)
    batch_starts.append((s.strftime('%Y%m%d'), batch_end.strftime('%Y%m%d')))
    s = batch_end + timedelta(days=1)

logger.info(f"将分 {len(batch_starts)} 批拉取")
for bs, be in batch_starts:
    logger.info(f"  {bs} ~ {be}")

# 只取前几批测试（先跑第一批）
conn2 = sqlite3.connect(str(db_path))
c = conn2.cursor()

total_stocks = len(stocks)
for batch_idx, (start_date, end_date) in enumerate(batch_starts):
    logger.info(f"\n{'='*60}")
    logger.info(f"第{batch_idx+1}/{len(batch_starts)}批: {start_date} ~ {end_date}")
    logger.info(f"{'='*60}")
    
    success = 0
    error = 0
    skip = 0
    
    for i, ts_code in enumerate(stocks):
        try:
            # 请求前限流
            tushare_limiter.wait(min_interval=1.5, max_interval=3.0)
            data = pro.daily_basic(ts_code=ts_code, start_date=start_date, end_date=end_date)
            if data is not None and not data.empty:
                records = 0
                for _, row in data.iterrows():
                    trade_date = str(row['trade_date'])
                    if trade_date in existing_dates:
                        continue  # 跳过已有的
                    try:
                        c.execute('''INSERT OR IGNORE INTO valuation_data 
                        (ts_code, trade_date, close, pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm, total_mv, circ_mv)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (ts_code, trade_date,
                         float(row['close']) if 'close' in row and row['close'] is not None else None,
                         float(row['pe']) if 'pe' in row and row['pe'] is not None else None,
                         float(row['pe_ttm']) if 'pe_ttm' in row and row['pe_ttm'] is not None else None,
                         float(row['pb']) if 'pb' in row and row['pb'] is not None else None,
                         float(row['ps']) if 'ps' in row and row['ps'] is not None else None,
                         float(row['ps_ttm']) if 'ps_ttm' in row and row['ps_ttm'] is not None else None,
                         float(row['dv_ratio']) if 'dv_ratio' in row and row['dv_ratio'] is not None else None,
                         float(row['dv_ttm']) if 'dv_ttm' in row and row['dv_ttm'] is not None else None,
                         float(row['total_mv']) if 'total_mv' in row and row['total_mv'] is not None else None,
                         float(row['circ_mv']) if 'circ_mv' in row and row['circ_mv'] is not None else None))
                        records += 1
                    except Exception: pass
                if records > 0:
                    success += 1
                else:
                    skip += 1
            else:
                skip += 1
            if (i + 1) % 200 == 0:
                c.execute("SELECT COUNT(DISTINCT trade_date) FROM valuation_data")
                date_count = c.fetchone()[0]
                logger.info(f"  进度: {i+1}/{total_stocks} 成功:{success} 跳过:{skip} 失败:{error} (总天数:{date_count})")
        except Exception as e:
            error += 1
            if (i + 1) % 200 == 0:
                logger.error(f"  错误: {e}")
    
    conn2.commit()
    
    c.execute("SELECT COUNT(DISTINCT trade_date) FROM valuation_data")
    date_count = c.fetchone()[0]
    c.execute("SELECT MIN(trade_date), MAX(trade_date) FROM valuation_data")
    mm = c.fetchone()
    logger.info(f"第{batch_idx+1}批完成. 总交易日:{date_count}, 时间范围:{mm[0]}~{mm[1]}")
    
    # 更新已存在的日期集合
    cursor = conn2.cursor()
    cursor.execute("SELECT DISTINCT trade_date FROM valuation_data")
    existing_dates = set(r[0] for r in cursor.fetchall())

conn2.commit()
c.execute("SELECT COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date) FROM valuation_data")
final = c.fetchone()
logger.info(f"\n{'='*60}")
logger.info(f"✅ 全部完成!")
logger.info(f"总交易日: {final[0]}")
logger.info(f"时间范围: {final[1]} ~ {final[2]}")
c.execute("SELECT COUNT(*), COUNT(DISTINCT ts_code) FROM valuation_data")
total_rec, total_stk = c.fetchone()
logger.info(f"总记录数: {total_rec}, 覆盖股票: {total_stk}只")
conn2.close()