"""历史数据修复导入 v3：按 SQLite 真实字段映射 CSV 列（只做验证式导入）"""
import csv, os, sqlite3
from pathlib import Path
BASE = Path(__file__).resolve().parent
DB_PATH = BASE / 'database' / 'stock_analysis.db'

INSERT_FIN = """
INSERT OR REPLACE INTO financial_data
(ts_code,end_date,ann_date,roe,roa,gross_margin,net_margin,debt_ratio,
 revenue_yoy,net_profit_yoy,eps,bps,total_assets,total_liab,
 current_assets,current_liab,operating_cf)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""

INSERT_VAL = """
INSERT OR REPLACE INTO valuation_data
(ts_code,trade_date,close,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,total_mv,circ_mv)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
"""

def _f(v):
    try: return float(v)
    except Exception: return None


def import_financial():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    before = c.execute('SELECT COUNT(*) FROM financial_data').fetchone()[0]
    files = [f for f in os.listdir(BASE / 'data_raw') if f.startswith('financial_raw_')]
    if not files:
        print('未找到财务CSV'); return
    p = BASE / 'data_raw' / files[0]
    rows = errs = 0
    with open(p, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            try:
                c.execute(INSERT_FIN, (
                    row.get('ts_code',''), row.get('end_date',''), row.get('ann_date',''),
                    _f(row.get('roe_yearly')), _f(row.get('roa')),
                    _f(row.get('grossprofit_margin')), _f(row.get('netprofit_margin')), _f(row.get('debt_ratio')),
                    _f(row.get('revenue_yoy')), _f(row.get('netprofit_yoy')),
                    _f(row.get('eps')), _f(row.get('bps')),
                    _f(row.get('total_assets')), _f(row.get('total_liab')),
                    _f(row.get('current_assets')), _f(row.get('current_liab')),
                    _f(row.get('operating_cf'))
                ))
                rows += 1
            except Exception as e:
                errs += 1
                if errs <= 5:
                    print('ERR', row.get('ts_code'), row.get('end_date'), e)
    conn.commit()
    after = c.execute('SELECT COUNT(*) FROM financial_data').fetchone()[0]
    conn.close()
    print(f'财务导入: +{rows} 条, 失败: {errs} | {before} -> {after}')


def import_valuation():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    before = c.execute('SELECT COUNT(*) FROM valuation_data').fetchone()[0]
    files = [f for f in os.listdir(BASE / 'data_raw') if f.startswith('valuation_raw_')]
    if not files:
        print('未找到估值CSV'); return
    p = BASE / 'data_raw' / files[0]
    rows = errs = 0
    with open(p, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            try:
                c.execute(INSERT_VAL, (
                    row.get('ts_code',''), row.get('trade_date',''),
                    _f(row.get('close')), _f(row.get('pe')), _f(row.get('pe_ttm')), _f(row.get('pb')),
                    _f(row.get('ps')), _f(row.get('ps_ttm')),
                    _f(row.get('dv_ratio')), _f(row.get('dv_ttm')),
                    _f(row.get('total_mv')), _f(row.get('circ_mv'))
                ))
                rows += 1
            except Exception as e:
                errs += 1
                if errs <= 5:
                    print('ERR', row.get('ts_code'), row.get('trade_date'), e)
    conn.commit()
    after = c.execute('SELECT COUNT(*) FROM valuation_data').fetchone()[0]
    conn.close()
    print(f'估值导入: +{rows} 条, 失败: {errs} | {before} -> {after}')


if __name__ == '__main__':
    print('[1/2] 财务CSV导入...')
    import_financial()
    print('[2/2] 估值CSV导入...')
    import_valuation()
