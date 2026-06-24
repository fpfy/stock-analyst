"""
财务数据获取问题诊断和修复脚本
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def diagnose_financial_data():
    """诊断财务数据问题"""
    db_path = Path(__file__).parent / "database" / "stock_analysis.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    print("=== 财务数据问题诊断 ===")
    
    # 1. 检查财务数据表结构
    cursor.execute("PRAGMA table_info(financial_data)")
    columns = cursor.fetchall()
    print("财务数据表结构:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    # 2. 检查有哪些股票有财务数据
    cursor.execute("SELECT f.ts_code, s.name FROM financial_data f JOIN stock_basic s ON f.ts_code = s.ts_code GROUP BY f.ts_code")
    financial_stocks = cursor.fetchall()
    print(f"\n有财务数据的股票: {len(financial_stocks)}只")
    for ts_code, name in financial_stocks:
        print(f"  {ts_code} - {name}")
    
    # 3. 检查最近的数据
    cursor.execute("SELECT ts_code, end_date, roe, revenue_yoy FROM financial_data ORDER BY end_date DESC LIMIT 5")
    recent_data = cursor.fetchall()
    print(f"\n最近财务数据:")
    for row in recent_data:
        print(f"  {row[0]} | {row[1]} | ROE:{row[2]:.1f}% | 营收增长:{row[3]:.1f}%")
    
    # 4. 检查Tushare API字段映射
    print(f"\n=== Tushare API字段映射检查 ===")
    
    # 检查实际获取的数据字段
    cursor.execute("SELECT * FROM financial_data LIMIT 1")
    sample = cursor.fetchone()
    if sample:
        columns = [desc[0] for desc in cursor.description]
        print("财务数据字段:", columns)
    
    conn.close()

def test_financial_fetch():
    """测试财务数据获取"""
    try:
        import realtime_fetcher
        
        fetcher = realtime_fetcher.data_fetcher
        
        # 测试获取几只股票的财务数据
        test_stocks = ['000001.SZ', '000002.SZ', '000858.SZ']
        
        for ts_code in test_stocks:
            print(f"\n测试获取 {ts_code} 的财务数据...")
            try:
                data = fetcher.fetch_stock_financial(ts_code)
                if not data.empty:
                    print(f"✓ {ts_code} 获取成功，记录数: {len(data)}")
                    print(f"  字段: {list(data.columns)}")
                    if 'roe' in data.columns:
                        latest_roe = data['roe'].iloc[-1] if not data['roe'].isna().all() else 'N/A'
                        print(f"  最新ROE: {latest_roe}")
                else:
                    print(f"- {ts_code} 数据为空")
            except Exception as e:
                print(f"✗ {ts_code} 获取失败: {e}")
    
    except Exception as e:
        print(f"测试失败: {e}")

def fix_financial_data():
    """修复财务数据获取"""
    print("\n=== 修复财务数据获取 ===")
    
    # 重新运行批量财务数据获取
    try:
        import batch_data_fetch
        
        fetcher = batch_data_fetch.BatchDataFetcher()
        
        # 只获取财务数据
        stocks = fetcher.get_stock_list(limit=100)  # 先测试100只
        print(f"重新获取 {len(stocks)} 只股票的财务数据...")
        
        success_count = fetcher.batch_fetch_financial(stocks)
        
        print(f"财务数据获取完成: {success_count}只")
        
        # 验证结果
        fetcher.verify_data()
        
    except Exception as e:
        print(f"修复失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🔍 开始诊断财务数据问题...")
    
    # 1. 诊断问题
    diagnose_financial_data()
    
    # 2. 测试获取
    print(f"\n🧪 测试财务数据获取...")
    test_financial_fetch()
    
    # 3. 修复问题
    print(f"\n🔧 开始修复...")
    fix_financial_data()