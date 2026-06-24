"""
数据库初始化与管理模块
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import config

logger = logging.getLogger(__name__)

class DatabaseManager:
    """数据库管理类"""

    def __init__(self, db_path: Optional[Path] = None):
        """
        初始化数据库管理器

        Args:
            db_path: 数据库文件路径，默认使用配置中的路径
        """
        self.db_path = db_path or config.DB_PATH
        self.conn = None
        self._init_database()

    def _get_connection(self):
        """获取数据库连接（单连接 + busy_timeout + WAL，减少 locked）"""
        if self.conn is None:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.execute("PRAGMA busy_timeout=5000")
            self.conn.execute("PRAGMA wal_autocheckpoint=1000")
        return self.conn

    @staticmethod
    def _write(cursor, conn, sql, params):
        try:
            cursor.execute(sql, params)
            conn.commit()
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            raise

    def write(self, sql, params=()):
        conn = self._get_connection()
        cursor = conn.cursor()
        DatabaseManager._write(cursor, conn, sql, params)
        cursor.close()
        return cursor.lastrowid

    def _init_database(self):
        """初始化数据库表结构"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 1. 创建大盘状态表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,  -- BULL/OSCILLATION/BEAR
                risk_level TEXT,
                macro_score REAL,
                technical_score REAL,
                composite_score REAL,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. 创建宏观经济数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS macro_indicators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                indicator_name TEXT NOT NULL,
                date TEXT NOT NULL,
                value REAL,
                year TEXT,
                month TEXT,
                source TEXT DEFAULT 'AkShare',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(indicator_name, date)
            )
        """)

        # 3. 创建指数数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS index_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                index_code TEXT NOT NULL,
                index_name TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL,
                change_pct REAL,
                ma5 REAL,
                ma10 REAL,
                ma20 REAL,
                ma60 REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(index_code, date)
            )
        """)

        # 4. 创建股票基本信息表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_basic (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_code TEXT NOT NULL UNIQUE,
                symbol TEXT,
                name TEXT,
                area TEXT,
                industry TEXT,
                market TEXT,
                list_date TEXT,
                is_st INTEGER DEFAULT 0,
                update_date TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 5. 创建财务数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS financial_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_code TEXT NOT NULL,
                ann_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                revenue REAL,
                revenue_yoy REAL,
                net_profit REAL,
                net_profit_yoy REAL,
                roe REAL,
                roa REAL,
                gross_margin REAL,
                net_margin REAL,
                debt_ratio REAL,
                eps REAL,
                bps REAL,
                total_assets REAL,
                total_liab REAL,
                current_assets REAL,
                current_liab REAL,
                operating_cf REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ts_code, ann_date, end_date)
            )
        """)

        # 6. 创建估值数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS valuation_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                close REAL,
                pe REAL,
                pe_ttm REAL,
                pb REAL,
                ps REAL,
                ps_ttm REAL,
                dv_ratio REAL,
                dv_ttm REAL,
                total_mv REAL,
                circ_mv REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ts_code, trade_date)
            )
        """)

        # 7. 创建选股结果表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_selection (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                selection_date TEXT NOT NULL,
                ts_code TEXT NOT NULL,
                strategy_type TEXT NOT NULL,  -- GROWTH/VALUE
                score REAL,
                rank INTEGER,
                position_ratio REAL,
                target_price REAL,
                stop_loss_price REAL,
                reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(selection_date, ts_code, strategy_type)
            )
        """)

        # 8. 创建观察池表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watch_pool (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_code TEXT NOT NULL UNIQUE,
                name TEXT,
                pool_type TEXT NOT NULL,  -- GROWTH/VALUE
                entry_date TEXT NOT NULL,
                current_status TEXT DEFAULT 'OBSERVING',  -- OBSERVING/POSITION/CLOSED
                entry_price REAL,
                current_price REAL,
                position_ratio REAL,
                last_update TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 9. 创建技术指标表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS technical_indicators (
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ts_code, trade_date)
            )
        """)

        # 10. 创建舆情数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sentiment_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_code TEXT NOT NULL,
                news_date TEXT NOT NULL,
                title TEXT,
                summary TEXT,
                sentiment_score REAL,  -- -1到1之间，负数表示负面，正数表示正面
                sentiment_label TEXT,  -- POSITIVE/NEGATIVE/NEUTRAL
                source TEXT,
                url TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 11. 创建交易策略表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trading_strategy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL,
                ts_code TEXT NOT NULL,
                action TEXT NOT NULL,  -- BUY/HOLD/SELL/REDUCE
                current_price REAL,
                target_price REAL,
                stop_loss_price REAL,
                position_ratio REAL,
                priority TEXT,  -- HIGH/MEDIUM/LOW
                reason TEXT,
                risk_warning TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(report_date, ts_code)
            )
        """)

        # 12. 创建执行日志表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS execution_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_name TEXT NOT NULL,
                execution_time TEXT NOT NULL,
                status TEXT NOT NULL,  -- SUCCESS/FAILED
                message TEXT,
                execution_time_seconds REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 创建索引以提高查询性能
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_status_date ON market_status(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_macro_indicators_name_date ON macro_indicators(indicator_name, date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_index_data_code_date ON index_data(index_code, date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_selection_date ON stock_selection(selection_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_watch_pool_code ON watch_pool(ts_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_technical_indicators_code_date ON technical_indicators(ts_code, trade_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trading_strategy_date ON trading_strategy(report_date)")

        conn.commit()
        logger.info(f"数据库初始化完成: {self.db_path}")

    def execute_query(self, query: str, params: tuple = (), commit: bool = False) -> List[Dict[str, Any]]:
        """
        执行查询语句

        Args:
            query: SQL查询语句
            params: 查询参数
            commit: 是否提交事务

        Returns:
            查询结果列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            if commit:
                conn.commit()
                return cursor.fetchall()
            results = cursor.fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"查询执行失败: {e}")
            if commit:
                conn.rollback()
            raise

    def insert_data(self, table: str, data: Dict[str, Any]) -> int:
        """
        插入数据到指定表

        Args:
            table: 表名
            data: 数据字典

        Returns:
            插入的记录ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        values = tuple(data.values())

        query = f"""
            INSERT INTO {table} ({columns})
            VALUES ({placeholders})
        """

        try:
            cursor.execute(query, values)
            conn.commit()
            logger.debug(f"插入数据成功: {table}, ID={cursor.lastrowid}")
            return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            logger.warning(f"数据已存在，跳过插入: {e}")
            return 0
        except Exception as e:
            logger.error(f"插入数据失败: {e}")
            conn.rollback()
            raise

    def update_data(self, table: str, data: Dict[str, Any], condition: str, params: tuple = ()) -> int:
        """
        更新表数据

        Args:
            table: 表名
            data: 更新数据字典
            condition: WHERE条件
            params: 条件参数

        Returns:
            影响的行数
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        set_clause = ', '.join([f"{key} = ?" for key in data.keys()])
        values = tuple(data.values()) + params

        query = f"""
            UPDATE {table}
            SET {set_clause}
            WHERE {condition}
        """

        try:
            cursor.execute(query, values)
            conn.commit()
            affected = cursor.rowcount
            logger.debug(f"更新数据成功: {table}, 影响行数={affected}")
            return affected
        except Exception as e:
            logger.error(f"更新数据失败: {e}")
            conn.rollback()
            raise

    def delete_data(self, table: str, condition: str, params: tuple = ()) -> int:
        """
        删除表数据

        Args:
            table: 表名
            condition: WHERE条件
            params: 条件参数

        Returns:
            影响的行数
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = f"""
            DELETE FROM {table}
            WHERE {condition}
        """

        try:
            cursor.execute(query, params)
            conn.commit()
            affected = cursor.rowcount
            logger.debug(f"删除数据成功: {table}, 影响行数={affected}")
            return affected
        except Exception as e:
            logger.error(f"删除数据失败: {e}")
            conn.rollback()
            raise

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            try:
                self.conn.commit()
                self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except Exception:
                pass
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None
            logger.info("数据库连接已关闭")

    def get_cursor(self):
        """获取数据库游标（兼容统一调用接口）"""
        return self._get_connection().cursor()

    def get_connection(self):
        """获取数据库连接（兼容统一调用接口）"""
        return self._get_connection()

    def __enter__(self):
        """支持上下文管理器"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出时自动关闭连接"""
        self.close()

# 全局数据库实例
db = DatabaseManager()