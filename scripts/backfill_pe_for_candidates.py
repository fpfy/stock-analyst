"""
补充缺失的PE/PB数据，只针对符合基础条件的候选股票。
避免429：单线程、sleep(2)、每次只查1只、失败即跳过。
"""
import sqlite3
import os
import time
import tushare as ts
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database', 'stock_analysis.db')
TOKEN = os.environ.get('TUSHARE_TOKEN', '')
ts.set_token(TOKEN)
pro = ts.pro_api()

# 符合基础财务条件但缺失PE的股票（从数据库查询）
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute('''
    SELECT v.ts_code, v.trade_date
    FROM valuation_data v
    JOIN financial_data f ON v.ts_code = f.ts_code 
        AND f.end_date = (SELECT MAX(end_date) FROM financial_data f2 WHERE f2.ts_code = f.ts_code)
    WHERE v.trade_date = (SELECT MAX(trade_date) FROM valuation_data v2 WHERE v2.ts_code = v.ts_code)
      AND (v.pe IS NULL OR v.pe <= 0)
      AND f.roe >= 10
      AND f.revenue_yoy >= 10
    ORDER BY f.roe DESC
''')
candidates = c.fetchall()
conn.close()

print(f"待补全PE的候选股票: {len(candidates)}只")
for code, date in candidates:
    print(f"  {code} 最新日期:{date}")

# 逐只补全
updated = 0
failed = 0

for ts_code, latest_date in candidates:
    print(f"\n[{ts_code}] 开始补全...")
    
    # 从最新日期往前补60天
    start_date = latest_date
    end_date = datetime.now().strftime('%Y%m%d')
    
    try:
        time.sleep(2)  # 严格遵守限流
        df = pro.daily_basic(ts_code=ts_code, start_date=start_date, end_date=end_date)
        
        if df is None or df.empty:
            print(f"[{ts_code}] 无数据返回")
            failed += 1
            continue
        
        # 更新数据库
        conn = sqlite3.connect(DB_PATH, timeout=30)
        c = conn.cursor()
        
        for _, row in df.iterrows():
            td = str(row['trade_date'])
            pe = float(row['pe']) if 'pe' in row and row['pe'] is not None else None
            pb = float(row['pb']) if 'pb' in row and row['pb'] is not None else None
            pe_ttm = float(row['pe_ttm']) if 'pe_ttm' in row and row['pe_ttm'] is not None else None
            pb_ttm = float(row['pb_ttm']) if 'pb_ttm' in row and row['pb_ttm'] is not None else None
            dv_ratio = float(row['dv_ratio']) if 'dv_ratio' in row and row['dv_ratio'] is not None else None
            dv_ttm = float(row['dv_ttm']) if 'dv_ttm' in row and row['dv_ttm'] is not None else None
            total_mv = float(row['total_mv']) if 'total_mv' in row and row['total_mv'] is not None else None
            circ_mv = float(row['circ_mv']) if 'circ_mv' in row and row['circ_mv'] is not None else None
            
            c.execute('''
                UPDATE valuation_data 
                SET pe=?, pb=?, pe_ttm=?, dv_ratio=?, dv_ttm=?, total_mv=?, circ_mv=?
                WHERE ts_code=? AND trade_date=?
            ''', (pe, pb, pe_ttm, dv_ratio, dv_ttm, total_mv, circ_mv, ts_code, td))
            
            if c.rowcount > 0:
                updated += c.rowcount
        
        conn.commit()
        conn.close()
        print(f"[{ts_code}] 更新 {c.rowcount} 条记录")
        
    except Exception as e:
        print(f"[{ts_code}] 失败: {e}")
        failed += 1
        continue

print(f"\n=== 补全完成 ===")
print(f"成功: {updated} 条")
print(f"失败: {failed} 只")

# 验证结果
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute('''
    SELECT COUNT(DISTINCT v.ts_code)
    FROM valuation_data v
    JOIN financial_data f ON v.ts_code = f.ts_code 
        AND f.end_date = (SELECT MAX(end_date) FROM financial_data f2 WHERE f2.ts_code = f.ts_code)
    WHERE v.trade_date = (SELECT MAX(trade_date) FROM valuation_data v2 WHERE v2.ts_code = v.ts_code)
      AND v.pe IS NOT NULL AND v.pe > 0
      AND f.roe >= 10
      AND f.revenue_yoy >= 10
''')
count = c.fetchone()[0]
print(f"补全后符合条件且有PE的股票: {count} 只")
conn.close()
