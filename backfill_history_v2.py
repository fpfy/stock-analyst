"""
历史数据补全脚本 V2
- 估值：腾讯财经日K（close） + 东方财富 datacenter（PE/PB等）
- 财务：东方财富 datacenter（FINANCE_BALANCE_SHEET / INCOME）
"""

import os, sys, time, logging, sqlite3, json
from datetime import datetime, timedelta
import requests

# 统一限流器
from rate_limiter import tencent_limiter, eastmoney_limiter

# ts_proxy 路径放到 venv 下 Python 自己
BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, 'database', 'stock_analysis.db')

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)


def get_all_stocks(cursor):
    """取所有非ST股票代码"""
    cursor.execute('SELECT ts_code, name FROM stocks WHERE is_st = 0')
    return cursor.fetchall()


def calc_market(code):
    if code.startswith('6') or code.startswith('9'):
        return 'sh'
    elif code.startswith('8') or code.startswith('4'):
        return 'bj'
    return 'sz'


def tencent_kline(ts_code, start='20240101', end='20261231'):
    """腾讯财经日K返回 df"""
    mkt = calc_market(ts_code[:6])
    code = f'{mkt}{ts_code[:6]}'
    url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
    params = {
        'param': f'{code},day,{start},{end},500,qfq',
        'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
    }
    r = requests.get(url, params=params, headers={'User-Agent': UA}, timeout=15)
    r.raise_for_status()
    j = r.json()
    raw = j.get('data', {})
    if isinstance(raw, dict):
        klines = raw.get(code.replace('.','').lower(), {}).get('qfqday', []) or raw.get(code, {}).get('qfqday', [])
    elif isinstance(raw, list) and raw:
        klines = raw[0].get('qfqday', [])
    else:
        klines = []
    if not klines:
        klines = j.get('data', {}).get(code, {}).get('day', [])
    rows = []
    for k in klines:
        try:
            rows.append({
                'trade_date': k[0].replace('-', ''),
                'open': float(k[1]),
                'close': float(k[2]),
                'high': float(k[3]),
                'low': float(k[4]),
                'vol': float(k[5]),
            })
        except Exception:
            pass
    # 请求后限流 - 腾讯接口建议 1-2 秒间隔
    tencent_limiter.wait(min_interval=1.0, max_interval=2.0)
    return rows


def import_valuation_history(cursor, stocks, max_batch=200):
    """用腾讯K线补全 valuation_data（仅close）"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    done = 0
    for ts_code, name in stocks[:max_batch]:
        try:
            rows = tencent_kline(ts_code, start='20240101', end='20261231')
            for row in rows:
                c.execute('''
                    INSERT OR REPLACE INTO valuation_data
                    (ts_code, trade_date, close, pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm, total_mv, circ_mv)
                    VALUES (?,?,?,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL)
                ''', (ts_code, row['trade_date'], row['close']))
            done += len(rows)
            if done % 5000 == 0:
                conn.commit()
                log.info(f'估值导入进度: 已写{done}条')
        except Exception as e:
            log.warning(f'失败: {ts_code} {e}')
    conn.commit()
    return done


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    stocks = get_all_stocks(c)
    log.info(f'待处理股票: {len(stocks)}只')

    before = c.execute('SELECT COUNT(*) FROM valuation_data').fetchone()[0]
    log.info(f'估值导入前: {before} 条')

    n = import_valuation_history(c, stocks, max_batch=min(500, len(stocks)))
    after = c.execute('SELECT COUNT(*) FROM valuation_data').fetchone()[0]
    log.info(f'新增 {n} 条，当前共 {after} 条')


if __name__ == '__main__':
    log.info('[回填 V2] 开始估值历史日线补全')
    main()
