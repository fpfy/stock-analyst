"""
CSV -> database/stock_analysis.db 导入器
用于 backfill_history.py / download_history.py 生成的历史数据文件
"""
import csv, os, argparse
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'stock_analysis.db')

FIN_HEADERS = [
    'ts_code','end_date','ann_date','roe_yearly','roa','grossprofit_margin','netprofit_margin','debt_ratio',
    'revenue_yoy','netprofit_yoy','op_yoy','eps','bps','total_assets','total_liab',
    'current_assets','current_liab','operating_cf'
]

VAL_HEADERS = [
    'ts_code','trade_date','close','pe','pe_ttm','pb','ps','ps_ttm','dv_ratio','dv_ttm','total_mv','circ_mv'
]


def import_financial_csv(csv_path):
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS financial_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_code TEXT, ann_date TEXT, end_date TEXT,
            revenue REAL, revenue_yoy REAL, net_profit REAL, net_profit_yoy REAL, op_yoy REAL,
            roe REAL, roa REAL, gross_margin REAL, net_margin REAL, debt_ratio REAL,
            eps REAL, bps REAL, total_assets REAL, total_liab REAL,
            current_assets REAL, current_liab REAL, operating_cf REAL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(ts_code, end_date)
        )
    ''')
    rows = 0
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                def _flt(v):
                    try: return float(v)
                    except Exception: return None
                c.execute('''
                    INSERT OR REPLACE INTO financial_data
                    (ts_code,end_date,ann_date,roe,roa,gross_margin,net_margin,debt_ratio,
                     revenue_yoy,net_profit_yoy,op_yoy,eps,bps,total_assets,total_liab,
                     current_assets,current_liab,operating_cf)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ''', (
                    row.get('ts_code',''),
                    row.get('end_date',''),
                    row.get('ann_date',''),
                    _flt(row.get('roe_yearly')), _flt(row.get('roa')), _flt(row.get('grossprofit_margin')),
                    _flt(row.get('netprofit_margin')), _flt(row.get('debt_ratio')),
                    _flt(row.get('revenue_yoy')), _flt(row.get('netprofit_yoy')), _flt(row.get('op_yoy')),
                    _flt(row.get('eps')), _flt(row.get('bps')),
                    _flt(row.get('total_assets')), _flt(row.get('total_liab')),
                    _flt(row.get('current_assets')), _flt(row.get('current_liab')),
                    _flt(row.get('operating_cf'))
                ))
                rows += 1
            except Exception: pass
    conn.commit()
    conn.close()
    print(f'财务导入完成: {rows} 条，来自 {csv_path}')


def import_valuation_csv(csv_path):
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS valuation_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_code TEXT, trade_date TEXT, close REAL,
            pe REAL, pe_ttm REAL, pb REAL,
            ps REAL, ps_ttm REAL, dv_ratio REAL, dv_ttm REAL,
            total_mv REAL, circ_mv REAL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(ts_code, trade_date)
        )
    ''')
    rows = 0
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                def _flt(v):
                    try: return float(v)
                    except Exception: return None
                c.execute('''
                    INSERT OR REPLACE INTO valuation_data
                    (ts_code,trade_date,close,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,total_mv,circ_mv)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ''', (
                    row.get('ts_code',''),
                    row.get('trade_date',''),
                    _flt(row.get('close')), _flt(row.get('pe')), _flt(row.get('pe_ttm')),
                    _flt(row.get('pb')), _flt(row.get('ps')), _flt(row.get('ps_ttm')),
                    _flt(row.get('dv_ratio')), _flt(row.get('dv_ttm')),
                    _flt(row.get('total_mv')), _flt(row.get('circ_mv'))
                ))
                rows += 1
            except Exception: pass
    conn.commit()
    conn.close()
    print(f'估值导入完成: {rows} 条，来自 {csv_path}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--type', choices=['financial','valuation','both'], default='both')
    args = parser.parse_args()
    if args.type in ('financial','both'):
        for fn in sorted(os.listdir('data_raw')):
            if fn.startswith('financial_raw_'):
                import_financial_csv(os.path.join('data_raw', fn))
    if args.type in ('valuation','both'):
        for fn in sorted(os.listdir('data_raw')):
            if fn.startswith('valuation_raw_'):
                import_valuation_csv(os.path.join('data_raw', fn))
