#!/usr/bin/env python3
"""补全基准指数历史数据到 index_data 表"""

import os
import sys
import time
import sqlite3
import logging
from datetime import datetime

# 确保能导入项目内模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'database', 'stock_analysis.db')
DB_PATH = os.path.abspath(DB_PATH)

# 需要补全的基准指数
BENCHMARK_CODES = [
    ('000001.SH', '上证指数'),
    ('000300.SH', '沪深300'),
    ('399001.SZ', '深证成指'),
]

# 补全起始日期（覆盖回测周期 2020 年至今）
FETCH_START_DATE = '20200101'
FETCH_END_DATE = datetime.now().strftime('%Y%m%d')


def get_tushare_client():
    """初始化 Tushare Pro API 客户端"""
    token = os.getenv('TUSHARE_TOKEN', '').strip()
    if not token:
        raise RuntimeError('TUSHARE_TOKEN 未配置，无法拉取指数数据')
    import tushare as ts
    return ts.pro_api(token)


def fetch_index_daily(pro, ts_code, start_date, end_date):
    """调用 index_daily 获取单只指数日线"""
    import tushare as ts
    df = pro.index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    if df is None or df.empty:
        logger.warning(f'{ts_code} 在 {start_date}~{end_date} 无数据返回')
        return []
    # 统一列名映射到 index_data 表结构
    records = []
    for _, row in df.iterrows():
        records.append({
            'index_code': row.get('ts_code', ts_code),
            'index_name': BENCHMARK_CODES[[c[0] for c in BENCHMARK_CODES].index(ts_code)][1],
            'date': row.get('trade_date'),
            'open': float(row['open']) if row.get('open') is not None else None,
            'high': float(row['high']) if row.get('high') is not None else None,
            'low': float(row['low']) if row.get('low') is not None else None,
            'close': float(row['close']) if row.get('close') is not None else None,
            'volume': float(row['vol']) if row.get('vol') is not None else None,
            'amount': float(row['amount']) if row.get('amount') is not None else None,
            'change_pct': float(row['pct_chg']) if row.get('pct_chg') is not None else None,
            'ma5': None,
            'ma10': None,
            'ma20': None,
            'ma60': None,
        })
    return records


def insert_index_data(conn, records):
    """插入指数数据，避免重复"""
    if not records:
        return 0
    cursor = conn.cursor()
    inserted = 0
    for rec in records:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO index_data
                    (index_code, index_name, date, open, high, low, close,
                     volume, amount, change_pct, ma5, ma10, ma20, ma60)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rec['index_code'], rec['index_name'], rec['date'],
                rec['open'], rec['high'], rec['low'], rec['close'],
                rec['volume'], rec['amount'], rec['change_pct'],
                rec['ma5'], rec['ma10'], rec['ma20'], rec['ma60']
            ))
            if cursor.rowcount > 0:
                inserted += 1
        except Exception as e:
            logger.warning(f"插入失败 {rec['index_code']} {rec['date']}: {e}")
    conn.commit()
    return inserted


def main():
    logger.info('开始补全基准指数历史数据')
    logger.info(f'目标日期范围: {FETCH_START_DATE} ~ {FETCH_END_DATE}')

    pro = get_tushare_client()
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")

    total_inserted = 0
    for ts_code, name in BENCHMARK_CODES:
        logger.info(f'正在拉取 {name} ({ts_code}) ...')
        try:
            records = fetch_index_daily(pro, ts_code, FETCH_START_DATE, FETCH_END_DATE)
            logger.info(f'{name} 获取到 {len(records)} 条记录')
            inserted = insert_index_data(conn, records)
            logger.info(f'{name} 实际插入 {inserted} 条新记录')
            total_inserted += inserted
        except Exception as e:
            logger.error(f'{name} 拉取失败: {e}')
        finally:
            time.sleep(2)  # Tushare 限流

    conn.close()
    logger.info(f'全部完成，共插入 {total_inserted} 条基准数据')

    # 验证结果
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()
    for ts_code, name in BENCHMARK_CODES:
        cursor.execute('''
            SELECT MIN(date), MAX(date), COUNT(*)
            FROM index_data
            WHERE index_code = ?
        ''', (ts_code,))
        row = cursor.fetchone()
        logger.info(f'{name} ({ts_code}): {row[0]} ~ {row[1]} ({row[2]} rows)')
    conn.close()


if __name__ == '__main__':
    main()
