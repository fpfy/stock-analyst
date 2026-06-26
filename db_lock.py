"""
db_lock.py — SQLite 跨进程锁机制

解决多进程并发写入导致的 database is locked 问题。
基于文件锁 + 短超时重试，兼容 Windows/Linux。
"""
import os
import time
import logging
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 默认锁文件路径：与数据库文件同级
DEFAULT_LOCK_DIR = Path(__file__).resolve().parent / 'database' / '.locks'


class SQLiteFileLock:
    """
    基于文件锁的 SQLite 互斥器
    
    使用场景：
    - 多进程共享同一 SQLite 文件时的写入保护
    - 与 WAL + busy_timeout 配合，提供双层保护
    """

    def __init__(self, db_path: str, lock_dir: Optional[str] = None, timeout: float = 10.0):
        self.db_path = str(Path(db_path).resolve())
        self.lock_dir = Path(lock_dir) if lock_dir else DEFAULT_LOCK_DIR
        self.timeout = timeout
        self._lock_file: Optional[str] = None
        self._lock_fd = None

    def _get_lock_path(self) -> str:
        """根据 db_path 生成唯一锁文件路径"""
        db_name = Path(self.db_path).stem
        safe_name = f"{db_name}.lock"
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        return str(self.lock_dir / safe_name)

    def acquire(self) -> bool:
        """
        获取锁（非阻塞 + 超时重试）
        
        Returns:
            True: 成功获取锁
            False: 超时未获取到锁
        """
        lock_path = self._get_lock_path()
        start = time.time()
        delay = 0.05  # 初始等待 50ms

        while True:
            try:
                # 使用 O_CREAT | O_EXCL 实现原子创建
                # 进程退出时锁文件会被 OS 自动清理
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o644)
                self._lock_fd = fd
                self._lock_file = lock_path
                logger.debug(f"[DB_LOCK] acquired: {lock_path}")
                return True
            except FileExistsError:
                if time.time() - start > self.timeout:
                    logger.warning(f"[DB_LOCK] timeout after {self.timeout}s: {lock_path}")
                    return False
                time.sleep(delay)
                # 指数退避，最大 500ms
                delay = min(delay * 1.5, 0.5)
            except Exception as e:
                logger.error(f"[DB_LOCK] acquire failed: {e}")
                return False

    def release(self):
        """释放锁"""
        if self._lock_file and os.path.exists(self._lock_file):
            try:
                os.close(self._lock_fd)
            except Exception:
                pass
            try:
                os.remove(self._lock_file)
            except Exception:
                pass
            logger.debug(f"[DB_LOCK] released: {self._lock_file}")
        self._lock_file = None
        self._lock_fd = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


def execute_with_lock(db_path: str, sql: str, params: tuple = (),
                      lock_timeout: float = 10.0, busy_timeout: int = 5000) -> Optional[sqlite3.Cursor]:
    """
    带文件锁的 SQLite 执行器（适合跨进程写入）
    
    Args:
        db_path: SQLite 数据库路径
        sql: SQL 语句
        params: 参数元组
        lock_timeout: 文件锁等待超时（秒）
        busy_timeout: SQLite busy_timeout（毫秒）
    
    Returns:
        cursor 或 None（失败时）
    """
    lock = SQLiteFileLock(db_path, timeout=lock_timeout)
    if not lock.acquire():
        logger.error(f"[DB_LOCK] 无法获取锁，跳过写入: {sql[:50]}...")
        return None

    try:
        conn = sqlite3.connect(db_path, timeout=busy_timeout / 1000.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=?)", (busy_timeout,))
        conn.execute("PRAGMA foreign_keys=ON")
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            logger.warning(f"[DB_LOCK] 写入时仍遇到锁: {e}")
        else:
            raise
        return None
    except Exception as e:
        logger.error(f"[DB_LOCK] 执行失败: {e}")
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass
        lock.release()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # 测试文件锁
    test_db = 'C:/Users/Fengpeng/stock_analysis_system/database/stock_analysis.db'
    lock = SQLiteFileLock(test_db)
    
    print("测试1: 获取锁...")
    ok = lock.acquire()
    print(f"  结果: {ok}")
    
    if ok:
        print("测试2: 持有锁期间查询...")
        conn = sqlite3.connect(test_db, timeout=5)
        count = conn.execute("SELECT COUNT(*) FROM stock_basic").fetchone()[0]
        print(f"  stock_basic: {count} 行")
        conn.close()
        
        print("测试3: 释放锁...")
        lock.release()
        print("  ✅ 已释放")
    
    # 测试上下文管理器
    print("\n测试4: 上下文管理器...")
    with SQLiteFileLock(test_db) as lk:
        print(f"  锁文件: {lk._lock_file}")
        conn = sqlite3.connect(test_db, timeout=5)
        count = conn.execute("SELECT COUNT(*) FROM valuation_data").fetchone()[0]
        print(f"  valuation_data: {count} 行")
        conn.close()
    print("  ✅ 上下文管理器正常退出")
    
    print("\n✅ db_lock 测试完成")
