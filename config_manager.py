"""
config_manager.py - 安全的配置管理器
提供上下文管理器来安全地替换和恢复配置
"""

import contextlib
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def patch_config(config_dict: Dict[str, Any], module_name: str = 'config'):
    """
    安全地替换和恢复配置的上下文管理器
    
    Args:
        config_dict: 要设置的配置字典
        module_name: 配置模块名称，默认为'config'
    
    Yields:
        None
    """
    try:
        # 动态导入配置模块
        import importlib
        config_module = importlib.import_module(module_name)
        
        # 保存原始配置
        original_configs = {}
        for key, value in config_dict.items():
            if hasattr(config_module, key):
                original_configs[key] = getattr(config_module, key)
        
        # 设置新配置
        for key, value in config_dict.items():
            setattr(config_module, key, value)
        
        logger.debug(f"✅ 配置已替换: {list(config_dict.keys())}")
        yield
        
    except Exception as e:
        logger.error(f"❌ 配置替换失败: {e}")
        raise
        
    finally:
        # 恢复原始配置
        if 'original_configs' in locals():
            for key, value in original_configs.items():
                setattr(config_module, key, value)
            
            logger.debug(f"✅ 配置已恢复: {list(original_configs.keys())}")
        else:
            # 如果发生异常，尝试恢复已知的关键配置
            try:
                for key, value in original_configs.items():
                    setattr(config_module, key, value)
                logger.debug("✅ 异常时配置已恢复")
            except Exception as e:
                logger.error(f"❌ 配置恢复失败: {e}")


def safe_getattr(obj: Any, attr: str, default: Any = None) -> Any:
    """
    安全地获取对象属性
    
    Args:
        obj: 目标对象
        attr: 属性名
        default: 默认值
    
    Returns:
        属性值或默认值
    """
    try:
        return getattr(obj, attr, default)
    except Exception as e:
        logger.warning(f"获取属性 {attr} 失败: {e}")
        return default