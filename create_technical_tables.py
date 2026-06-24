"""
create_technical_tables.py - 创建技术指标数据库表结构
"""
import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

def create_technical_tables(db_path: str = "database/stock_analysis.db"):
    """创建技术指标相关的数据库表"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 启用WAL模式
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        
        # 1. 检查并更新技术指标表（如果需要）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS technical_indicators_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                ma5 REAL,
                ma10 REAL,
                ma20 REAL,
                ma60 REAL,
                macd REAL,
                macd_signal REAL,
                macd_hist REAL,
                rsi REAL,
                boll_upper REAL,
                boll_mid REAL,
                boll_lower REAL,
                volume_ma5 REAL,
                volume_ma20 REAL,
                trend TEXT,
                signal TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ts_code, trade_date)
            )
        """)
        
        # 2. 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_technical_indicators_ts_code 
            ON technical_indicators_new(ts_code)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_technical_indicators_trade_date 
            ON technical_indicators_new(trade_date)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_technical_indicators_trend 
            ON technical_indicators_new(trend)
        """)
        
        # 3. 创建股票基本表（如果不存在）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_basic (
                ts_code TEXT PRIMARY KEY,
                symbol TEXT,
                name TEXT,
                industry TEXT,
                area TEXT,
                market TEXT,
                list_date TEXT,
                is_hs TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 4. 创建日线行情表（如果不存在）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL,
                pct_change REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ts_code, trade_date)
            )
        """)
        
        # 5. 创建日线行情索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_daily_quotes_ts_code 
            ON daily_quotes(ts_code)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_daily_quotes_trade_date 
            ON daily_quotes(trade_date)
        """)
        
        # 6. 创建回测结果表（如果不存在）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backtest_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT,
                ts_code TEXT,
                trade_date TEXT,
                action TEXT,
                price REAL,
                shares INTEGER,
                amount REAL,
                profit_pct REAL,
                cumulative_return REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 7. 创建回测结果索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_backtest_results_strategy 
            ON backtest_results(strategy_name)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_backtest_results_ts_code 
            ON backtest_results(ts_code)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_backtest_results_trade_date 
            ON backtest_results(trade_date)
        """)
        
        # 提交更改
        conn.commit()
        logger.info("技术指标数据库表创建成功")
        
        # 重命名表
        cursor.execute("DROP TABLE IF EXISTS technical_indicators")
        cursor.execute("ALTER TABLE technical_indicators_new RENAME TO technical_indicators")
        conn.commit()
        logger.info("技术指标表重命名成功")
        
    except Exception as e:
        logger.error(f"创建技术指标数据库表失败: {e}")
        conn.rollback()
        raise
    
    finally:
        conn.close()

def check_tables_exist(db_path: str = "database/stock_analysis.db") -> Dict[str, bool]:
    """检查数据库表是否存在"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        tables = {}
        
        # 检查技术指标表
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='technical_indicators'
        """)
        tables['technical_indicators'] = cursor.fetchone() is not None
        
        # 检查股票基本表
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='stock_basic'
        """)
        tables['stock_basic'] = cursor.fetchone() is not None
        
        # 检查日线行情表
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='daily_quotes'
        """)
        tables['daily_quotes'] = cursor.fetchone() is not None
        
        # 检查回测结果表
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='backtest_results'
        """)
        tables['backtest_results'] = cursor.fetchone() is not None
        
        return tables
    
    finally:
        conn.close()

def main():
    """主函数"""
    db_path = "database/stock_analysis.db"
    
    # 检查数据库文件是否存在
    if not Path(db_path).exists():
        logger.error(f"数据库文件不存在: {db_path}")
        return
    
    # 检查表是否存在
    tables = check_tables_exist(db_path)
    logger.info("数据库表检查结果:")
    for table_name, exists in tables.items():
        logger.info(f"  {table_name}: {'存在' if exists else '不存在'}")
    
    # 创建表
    create_technical_tables(db_path)
    
    # 再次检查表是否存在
    tables = check_tables_exist(db_path)
    logger.info("创建后的数据库表状态:")
    for table_name, exists in tables.items():
        logger.info(f"  {table_name}: {'存在' if exists else '不存在'}")

if __name__ == "__main__":
    main()