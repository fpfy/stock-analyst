"""
check_database_structure.py - 检查数据库结构
"""

import sqlite3
import os

def check_database_structure():
    """检查数据库表结构"""
    db_path = "database/stock_analysis.db"
    
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取所有表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print(f"📊 数据库中的表 ({len(tables)} 个):")
        for table in tables:
            table_name = table[0]
            print(f"  - {table_name}")
            
            # 获取表结构
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            print(f"    列 ({len(columns)} 个):")
            for col in columns:
                col_name = col[1]
                col_type = col[2]
                print(f"      - {col_name}: {col_type}")
            
            # 获取数据量
            try:
                # 白名单验证：table_name来自sqlite_master，仅包含字母数字下划线
                safe_name = ''.join(c for c in table_name if c.isalnum() or c == '_')
                if safe_name:
                    cursor.execute(f"SELECT COUNT(*) FROM '{safe_name}'")
                    count = cursor.fetchone()[0]
                    print(f"    数据量: {count}")
            except Exception as e:
                pass
            
            print()
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 检查数据库失败: {e}")

if __name__ == "__main__":
    check_database_structure()