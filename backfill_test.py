"""验证 backfill_history.py 的前100只，防止全量跑崩"""
import os, sqlite3, time
sys_path = os.path.dirname(os.path.abspath(__file__))
os.chdir(sys_path)

import tushare as ts
from rate_limiter import tushare_limiter

ts.set_token(os.environ.get('TUSHARE_TOKEN', ''))
pro = ts.pro_api()

conn = sqlite3.connect('database/stock_analysis.db')
c = conn.cursor()

c.execute('SELECT ts_code FROM stock_basic WHERE is_st=0 LIMIT 50')
stocks = [r[0] for r in c.fetchall()]
print(f'测试股票数: {len(stocks)}')

success = 0
for i, ts_code in enumerate(stocks):
    try:
        # 请求前限流
        tushare_limiter.wait(min_interval=1.5, max_interval=3.0)
        df = pro.fina_indicator(ts_code=ts_code, start_date='20230101', end_date='20251231',
            fields='ts_code,end_date,roe_yearly,revenue_yoy,netprofit_yoy,debt_ratio,eps,bps,total_liab,current_assets,current_liab,operating_cf')
        if df is not None and not df.empty:
            df = df[df['end_date'].isin(['20231231','20240331','20240630','20240930','20241231','20250331','20250630','20250930','20251231'])]
            for _, row in df.iterrows():
                c.execute('INSERT OR IGNORE INTO financial_data (ts_code,end_date,ann_date,roe,revenue_yoy,net_profit_yoy,debt_ratio,eps,bps,total_liab,current_assets,current_liab,operating_cf) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (row.get('ts_code'), row.get('end_date'), row.get('end_date'),
                     row.get('roe_yearly'), row.get('revenue_yoy'), row.get('netprofit_yoy'),
                     row.get('debt_ratio'), row.get('eps'), row.get('bps'),
                     row.get('total_liab'), row.get('current_assets'), row.get('current_liab'),
                     row.get('operating_cf')))
            conn.commit()
            success += 1
    except Exception as e:
        print(f'err {ts_code}: {e}')
    if (i+1) % 10 == 0:
        print(f'进度 {i+1}/{len(stocks)} 成功{success}')

c.execute('SELECT COUNT(DISTINCT end_date), COUNT(DISTINCT ts_code) FROM financial_data')
print('财务总期数/股票:', c.fetchone())
conn.close()
