"""
统一 API 安全调用包装器
将 tushare / akshare / requests 调用统一接入 RateLimiter 与 429 退避
"""
import time
import logging
from rate_limiter import get_limiter

logger = logging.getLogger(__name__)

# 默认限流器
_tushare_limiter = get_limiter("tushare")
_http_limiter = get_limiter("http")
_akshare_limiter = get_limiter("akshare")

_SOURCE_MAP = {
    "tushare": _tushare_limiter,
    "pro": _tushare_limiter,      # pro = tushare
    "ts": _tushare_limiter,       # ts = tushare
    "akshare": _akshare_limiter,
    "ak": _akshare_limiter,
    "http": _http_limiter,
    "requests": _http_limiter,
}


def _limiter_for(source: str):
    """按调用来源选择限流器"""
    return _SOURCE_MAP.get(source.lower(), _http_limiter)


def safe_api_call(func, source: str = "tushare", max_retries: int = 3, **kwargs):
    """
    安全调用 API，自动限流 + 429 退避重试

    Args:
        func: API 调用函数
        source: 数据源标识，默认 'tushare'
        max_retries: 429 错误最大重试次数
        **kwargs: 传给 func 的参数

    Returns:
        func 的返回值（DataFrame 或 dict）

    Raises:
        最后一次非限频异常
    """
    limiter = _limiter_for(source)
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            limiter.wait()
            return func(**kwargs)
        except Exception as e:
            last_exception = e
            error_msg = str(e).lower()
            is_rate_limit = (
                '429' in error_msg or
                'too many requests' in error_msg or
                '每分钟' in error_msg or
                'rate limit' in error_msg or
                '频率' in error_msg or
                '访问频率' in error_msg
            )
            if is_rate_limit and attempt < max_retries:
                delay = 2.0 * (2 ** attempt)
                logger.warning(
                    f"[safe_api_call] 限频第{attempt+1}次重试，"
                    f"等待 {delay:.1f}s: {e}"
                )
                time.sleep(delay)
                continue
            # 非限频或重试耗尽，直接抛出
            raise

    raise last_exception
