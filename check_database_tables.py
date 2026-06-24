"""
check_database_tables.py - 检查数据库表结构
"""

import sqlite3
import os

def check_database_tables():
    """检查数据库表结构"""
    db_path = "database/stock_analysis.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("=== 数据库表结构检查 ===")
        
        # 获取所有表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print(f"数据库中的表: {[t[0] for t in tables]}")
        
        # 检查stock_selection表是否存在
        if 'stock_selection' in [t[0] for t in tables]:
            print("✅ stock_selection表存在")
            
            # 检查表结构
            cursor.execute("PRAGMA table_info(stock_selection)")
            columns = cursor.fetchall()
            print("stock_selection表结构:")
            for col in columns:
                print(f"  {col}")
            
            # 检查数据量
            cursor.execute("SELECT COUNT(*) FROM stock_selection")
            count = cursor.fetchone()[0]
            print(f"stock_selection表数据量: {count}")
        else:
            print("❌ stock_selection表不存在")
            
        conn.close()
        
    except Exception as e:
        print(f"检查失败: {e}")

if __name__ == "__main__":
    check_database_tables()