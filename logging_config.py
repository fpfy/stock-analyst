"""
logging_config.py - 统一的日志配置
确保所有模块使用一致的日志级别和格式
"""

import os
import logging
from typing import Optional


def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    log_format: Optional[str] = None
) -> logging.Logger:
    """
    设置统一的日志配置
    
    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件路径
        log_format: 日志格式
    
    Returns:
        Logger: 配置好的日志器
    """
    
    # 确定日志级别
    if log_level is None:
        log_level = os.getenv('LOG_LEVEL', 'INFO')
    
    # 确定日志格式
    if log_format is None:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    
    # 确定日志文件
    if log_file is None:
        log_file = os.getenv('LOG_FILE', 'logs/stock_analysis.log')
    
    # 确保日志目录存在
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # 配置日志级别
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # 配置根日志器
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=[
            logging.StreamHandler(),  # 控制台输出
            logging.FileHandler(log_file, encoding='utf-8')  # 文件输出
        ]
    )
    
    # 创建日志器
    logger = logging.getLogger(__name__)
    
    # 设置第三方库的日志级别
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('sqlite3').setLevel(logging.WARNING)
    
    logger.info(f"日志配置完成 - 级别: {log_level}, 文件: {log_file}")
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的日志器
    
    Args:
        name: 日志器名称
    
    Returns:
        Logger: 日志器实例
    """
    return logging.getLogger(name)


# 预定义的日志配置
def setup_debug_logging():
    """设置调试日志"""
    return setup_logging('DEBUG', 'logs/debug.log')


def setup_info_logging():
    """设置信息日志"""
    return setup_logging('INFO', 'logs/info.log')


def setup_error_logging():
    """设置错误日志"""
    return setup_logging('ERROR', 'logs/error.log')


# 初始化默认日志配置
default_logger = setup_logging()