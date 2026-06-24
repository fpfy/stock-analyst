"""
db_manager.py - 统一数据库连接管理器
解决SQLite并发访问导致的database is locked问题
"""

import sqlite3
import threading
from typing import Optional
from contextlib import contextmanager
from pathlib import Path

class DatabaseManager:
    """线程安全的SQLite连接管理器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, db_path: str = "database/stock_analysis.db"):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.db_path = Path(db_path)
                cls._instance._local = threading.local()
                cls._instance._init_db()
            return cls._instance
    
    def _init_db(self):
        """初始化数据库连接，启用WAL模式"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # 使用check_same_thread=False允许跨线程共享连接
        conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=30  # 等待30秒后放弃，而不是立即报错
        )
        conn.row_factory = sqlite3.Row
        
        # 启用WAL模式，允许多个读同时进行，写操作不阻塞读
        conn.execute("PRAGMA journal_mode=WAL")
        # 设置繁忙超时
        conn.execute("PRAGMA busy_timeout=30000")
        # 启用外键约束
        conn.execute("PRAGMA foreign_keys=ON")
        # 设置同步模式为NORMAL，平衡性能和安全性
        conn.execute("PRAGMA synchronous=NORMAL")
        
        self._local.conn = conn
        self._local.cursor = conn.cursor()
    
    def get_connection(self) -> sqlite3.Connection:
        """获取当前线程的连接"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._init_db()
        return self._local.conn
    
    def get_cursor(self) -> sqlite3.Cursor:
        """获取当前线程的游标"""
        if not hasattr(self._local, 'cursor') or self._local.cursor is None:
            self._init_db()
        return self._local.cursor
    
    @contextmanager
    def transaction(self):
        """事务上下文管理器，确保原子性操作"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
    
    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """执行SQL语句，自动重试"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                cursor = self.get_cursor()
                cursor.execute(sql, params)
                return cursor
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    import time
                    time.sleep(0.1 * (attempt + 1))  # 指数退避
                    continue
                raise
    
    def executemany(self, sql: str, params_list: list) -> sqlite3.Cursor:
        """批量执行SQL"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                cursor = self.get_cursor()
                cursor.executemany(sql, params_list)
                return cursor
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    import time
                    time.sleep(0.1 * (attempt + 1))
                    continue
                raise
    
    def close(self):
        """关闭连接"""
        if hasattr(self._local, 'conn') and self._local.conn:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None
            self._local.cursor = None
    
    def vacuum(self):
        """压缩数据库"""
        conn = self.get_connection()
        conn.execute("VACUUM")
    
    def analyze(self):
        """更新统计信息"""
        conn = self.get_connection()
        conn.execute("ANALYZE")


# 全局单例
db_manager = DatabaseManager()


def get_db() -> DatabaseManager:
    """获取数据库管理器实例"""
    return db_manager


@contextmanager
def get_cursor():
    """便捷的游标上下文管理器"""
    manager = DatabaseManager()
    cursor = manager.get_cursor()
    try:
        yield cursor
    finally:
        cursor.close()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("=== 统一数据库管理器测试 ===")
    
    # 测试单例模式
    db1 = DatabaseManager()
    db2 = DatabaseManager()
    print(f"单例模式: {db1 is db2}")
    
    # 测试连接
    cursor = db1.get_cursor()
    cursor.execute("SELECT COUNT(*) FROM stock_basic")
    count = cursor.fetchone()[0]
    print(f"stock_basic 记录数: {count}")
    
    # 测试事务
    with db1.transaction() as cur:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cur.fetchall()
        print(f"数据库表数量: {len(tables)}")
    
    print("✅ 数据库管理器测试完成")
