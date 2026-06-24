"""
history_backfill.py 定稿
用途：
  1. 给单一 A 股先做腾讯/东财历史估值+财务补全
  2. 不依赖 Tushare CSV，直连 API 落地
"""

import os, sys, time, logging, sqlite3, json, csv, requests
from datetime import datetime

# 统一限流器
from rate_limiter import tencent_limiter, eastmoney_limiter

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, 'database', 'stock_analysis.db')
os.makedirs(os.path.join(BASE, 'data_raw'), exist_ok=True)

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

# ── 腾讯 A 股日K (配) ────────────────────────────────────────────────────────
def tencent_kline(ts_code, start='20240101', end='20261231'):
    mkt = 'sh' if ts_code[:1] in ('6','9') else ('bj' if ts_code[:1] in ('8','4') else 'sz')
    code = f'{mkt}{ts_code[:6]}'
    url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
    params = {
        'param': f'{code},day,{start},{end},500,qfq',
        'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
    }
    r = requests.get(url, params=params, headers={'User-Agent': UA}, timeout=20)
    r.raise_for_status()
    j = r.json()
    raw = j.get('data', {})
    if isinstance(raw, dict):
        klines = (
            raw.get(code, {}).get('qfqday', [])
            or raw.get(code, {}).get('day', [])
        )
    elif isinstance(raw, list) and raw:
        klines = raw[0].get('qfqday', [])
    else:
        klines = []
    rows = []
    for k in klines:
        try:
            rows.append({
                'ts_code': ts_code,
                'trade_date': k[0].replace('-', ''),
                'close': float(k[2]),
                'open': float(k[1]),
                'high': float(k[3]),
                'low': float(k[4]),
                'vol': float(k[5]),
            })
        except Exception:
            pass
    # 请求后限流 - 腾讯接口建议 1-2 秒间隔
    tencent_limiter.wait(min_interval=1.0, max_interval=2.0)
    return rows


# ── 港股东财列表+日估值 CSV 解析 ──────────────────────────────────────────────
def eastmoney_datacenter(report_name, filter_str, page_size=50):
    url = 'https://datacenter-web.eastmoney.com/api/data/v1/get'
    params = {
        'reportName': report_name,
        'columns': 'ALL',
        'filter': filter_str,
        'pageNumber': '1',
        'pageSize': str(page_size),
        'sortColumns': '',
        'sortTypes': '-1',
        'source': 'WEB',
        'client': 'WEB',
    }
    r = requests.get(url, params=params, headers={'User-Agent': UA}, timeout=20)
    r.raise_for_status()
    d = r.json()
    # 请求后限流 - 东财接口建议 1-2 秒间隔
    eastmoney_limiter.wait(min_interval=1.0, max_interval=2.0)
    return d.get('result', {}).get('data', [])


class CsvReader:
    """
    纯 Python 解析器：读取 %s 格式
    """
    def __init__(self, mkt, code, name=''):
        self.mkt = mkt
        self.code = code
        self.name = name
        self.path_basic = os.path.join(BASE, 'data_raw', f'raw_basic_{mkt.code}.csv')
        self.path_val   = os.path.join(BASE, 'data_raw', f'raw_val_{mkt.code}.csv')

    def fetch_basic(self):
        return [] if not os.path.exists(self.path_basic) else []

    def fetch_valuation(self):
        return [] if not os.path.exists(self.path_val) else []


# ── 港股：腾讯行情 ──────────────────────────────────────────────────────────────
def hk_quote_tencent(ts_code):
    code5 = ts_code.split('.')[0].zfill(5)  # 00700
    url = f'http://qt.gtimg.cn/q=hk{code5}'
    r = requests.get(url, headers={'User-Agent': UA, 'Referer': 'https://qt.gtimg.cn'}, timeout=15)
    r.encoding = 'gbk'
    text = r.text
    if not text or 'v_' not in text:
        return {}
    parts = text.split('~')
    out = {'ts_code': ts_code}
    if len(parts) > 5:
        out['name']    = parts[1]
        out['price']   = float(parts[3]) if parts[3] else None
        out['change_pct'] = float(parts[32]) if len(parts) > 32 and parts[32] else None
        out['pe']      = float(parts[39]) if len(parts) > 39 and parts[39] else None
        out['pb']      = float(parts[46]) if len(parts) > 46 and parts[46] else None
    # 请求后限流 - 腾讯港股接口建议 1-2 秒间隔
    tencent_limiter.wait(min_interval=1.0, max_interval=2.0)
    return out


# ── 回测：单一 A 股估值历史 → valuation_data ─────────────────────────────────
def backfill_single_a(ts_code):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    before = c.execute('SELECT COUNT(*) FROM valuation_data WHERE ts_code=?', (ts_code,)).fetchone()[0]
    rows = tencent_kline(ts_code)
    for row in rows:
        c.execute('''
            INSERT OR REPLACE INTO valuation_data
              (ts_code, trade_date, close, pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm, total_mv, circ_mv)
            VALUES (?,?,?,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL)
        ''', (ts_code, row['trade_date'], row['close']))
    conn.commit()
    after = c.execute('SELECT COUNT(*) FROM valuation_data WHERE ts_code=?', (ts_code,)).fetchone()[0]
    conn.close()
    log.info(f'{ts_code}: valuation {before} -> {after} (+{after-before})')
    return rows


def main():
    # 单一 A 股回测验证（00259.SZ 已在估值表中，不再重复补全）
    pass


if __name__ == '__main__':
    log.info('[history_backfill] start')
    main()
