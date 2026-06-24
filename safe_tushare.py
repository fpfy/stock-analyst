"""
SafeTusharePro：tushare Pro API 安全包装器
自动限流 + 429 退避，无需修改现有调用方式
"""
import time
import logging
from safe_api_call import safe_api_call

logger = logging.getLogger(__name__)


class SafeTusharePro:
    """包装 tushare pro_api 实例，所有方法自动限流"""

    def __init__(self, pro):
        self._pro = pro
        self._source = "tushare"

    def __getattr__(self, name):
        """
        拦截所有方法调用，自动注入 safe_api_call
        """
        attr = getattr(self._pro, name)

        if callable(attr):
            def wrapper(*args, **kwargs):
                return safe_api_call(
                    attr,
                    source=self._source,
                    max_retries=3,
                    *args,
                    **kwargs
                )
            return wrapper
        return attr


def wrap_tushare_pro(pro):
    """将现有 pro 实例包装为安全版本"""
    return SafeTusharePro(pro)
