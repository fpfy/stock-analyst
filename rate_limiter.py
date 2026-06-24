"""
统一请求限流工具
解决 Tushare、腾讯、东方财富等 API 的频率限制问题
"""

import time
import random
import logging
from threading import Lock
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    令牌桶式限流器
    - 支持最小间隔、随机抖动
    - 线程安全
    - 可配置不同 API 的限流策略
    - 内置 429 退避重试支持
    """

    # 各数据源默认配置
    DEFAULTS = {
        "tushare":     {"min_interval": 2.0, "max_interval": 4.0, "max_per_minute": 30},
        "tencent":     {"min_interval": 1.5, "max_interval": 3.0, "max_per_minute": 30},
        "eastmoney":   {"min_interval": 1.5, "max_interval": 3.0, "max_per_minute": 30},
        "akshare":     {"min_interval": 1.0, "max_interval": 2.0, "max_per_minute": 40},
        "http":        {"min_interval": 1.0, "max_interval": 2.0, "max_per_minute": 60},
    }

    _instances = {}
    _lock = Lock()

    def __new__(cls, name: str = "default"):
        with cls._lock:
            if name not in cls._instances:
                cls._instances[name] = super().__new__(cls)
            return cls._instances[name]

    def __init__(self, name: str = "default"):
        if hasattr(self, '_initialized'):
            return
        self.name = name
        self._last_call = 0.0
        self._call_count = 0
        self._window_start = time.time()
        self._lock = Lock()
        self._initialized = True

    def wait(self,
             min_interval: Optional[float] = None,
             max_interval: Optional[float] = None,
             jitter: bool = True,
             max_per_minute: Optional[int] = None):
        """
        等待直到可以发起下一个请求

        Args:
            min_interval: 最小间隔秒数 (默认按数据源配置)
            max_interval: 最大间隔秒数 (默认按数据源配置，启用随机抖动时使用)
            jitter: 是否启用随机抖动 (默认 True，避免整点并发)
            max_per_minute: 每分钟最大请求数 (默认按数据源配置)
        """
        # 使用数据源默认配置
        defaults = self.DEFAULTS.get(self.name, self.DEFAULTS["http"])
        min_interval = min_interval if min_interval is not None else defaults["min_interval"]
        max_interval = max_interval if max_interval is not None else defaults["max_interval"]
        max_per_minute = max_per_minute if max_per_minute is not None else defaults["max_per_minute"]

        with self._lock:
            now = time.time()

            # 分钟级限流检查
            if now - self._window_start >= 60:
                self._window_start = now
                self._call_count = 0
            if self._call_count >= max_per_minute:
                wait_time = 60 - (now - self._window_start)
                if wait_time > 0:
                    logger.debug(f"[{self.name}] 分钟限流触发({max_per_minute}/min)，等待 {wait_time:.1f}s")
                    time.sleep(wait_time)
                self._window_start = time.time()
                self._call_count = 0

            # 计算需要等待的时间
            elapsed = now - self._last_call
            if jitter:
                target_interval = random.uniform(min_interval, max_interval)
            else:
                target_interval = min_interval

            if elapsed < target_interval:
                sleep_time = target_interval - elapsed
                logger.debug(f"[{self.name}] 限流等待 {sleep_time:.2f}s (目标间隔 {target_interval:.2f}s)")
                time.sleep(sleep_time)

            self._last_call = time.time()
            self._call_count += 1

    def retry_with_backoff(self, func, *args, max_retries: int = 3, base_delay: float = 2.0, **kwargs):
        """
        带指数退避的重试执行器，专门处理 429 错误

        Args:
            func: 要调用的函数
            max_retries: 最大重试次数
            base_delay: 基础延迟秒数
            *args, **kwargs: 传给 func 的参数

        Returns:
            func 的返回值

        Raises:
            最后一次异常
        """
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                # 请求前等待
                self.wait()
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                error_msg = str(e).lower()
                # 判断是否为 429/限频错误
                is_rate_limit = (
                    '429' in error_msg or
                    'too many requests' in error_msg or
                    '每分钟' in error_msg or
                    'rate limit' in error_msg or
                    '频率' in error_msg
                )
                if is_rate_limit and attempt < max_retries:
                    # 指数退避：2s, 4s, 8s... + 随机抖动
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"[{self.name}] 检测到限频 (第{attempt+1}/{max_retries}次重试)，等待 {delay:.1f}s: {e}")
                    time.sleep(delay)
                    continue
                # 非限频错误或重试耗尽，直接抛出
                raise

        raise last_exception


# 预定义的限流器实例（单例，按名称复用）
tushare_limiter     = RateLimiter("tushare")
tencent_limiter     = RateLimiter("tencent")
eastmoney_limiter   = RateLimiter("eastmoney")
akshare_limiter     = RateLimiter("akshare")
http_limiter        = RateLimiter("http")


def get_limiter(source: str) -> RateLimiter:
    """根据数据源名称获取对应的限流器"""
    limiters = {
        "tushare": tushare_limiter,
        "tencent": tencent_limiter,
        "eastmoney": eastmoney_limiter,
        "akshare": akshare_limiter,
        "http": http_limiter,
    }
    return limiters.get(source.lower(), http_limiter)