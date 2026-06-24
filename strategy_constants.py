"""
strategy_constants.py - 策略配置常量
提取硬编码的配置值，便于维护和调整
"""

# 成长股策略常量
GROWTH_CONSTANTS = {
    "TARGET_PRICE_MULTIPLIER": 0.001,      # 目标价系数
    "STOP_LOSS_RATIO": 0.9,                # 止损比例
    "DEFAULT_POSITION_RATIO": 0.3,          # 默认仓位比例
    "DEFAULT_MAX_STOCKS": 10,               # 默认最大选股数量
    "MIN_MARKET_CAP": 20,                   # 最小市值(亿元)
    "EXCLUDE_ST": True                      # 排除ST股票
}

# 价值股策略常量
VALUE_CONSTANTS = {
    "TARGET_PRICE_MULTIPLIER": 0.001,      # 目标价系数
    "STOP_LOSS_RATIO": 0.85,               # 止损比例（价值股更保守）
    "DEFAULT_POSITION_RATIO": 0.7,          # 默认仓位比例
    "DEFAULT_MAX_STOCKS": 10,               # 默认最大选股数量
    "MIN_MARKET_CAP": 50,                   # 最小市值(亿元)
    "EXCLUDE_ST": True                      # 排除ST股票
}

# 宏观分析常量
MACRO_CONSTANTS = {
    "DATA_UPDATE_TIME": "09:00",           # 数据更新时间
    "ANALYSIS_TRIGGER_TIME": "10:00",      # 分析触发时间
    "REPORT_GENERATION_TIME": "15:00",     # 报告生成时间
    "ENABLE_SENTIMENT_ANALYSIS": True,      # 启用情绪分析
    "ENABLE_TECHNICAL_ANALYSIS": True,      # 启用技术分析
    "RISK_LEVELS": ["low", "medium", "high"]  # 风险等级
}

# API常量
API_CONSTANTS = {
    "MAX_CALLS_PER_MINUTE": 30,            # 每分钟最大调用次数
    "MAX_CALLS_PER_HOUR": 200,             # 每小时最大调用次数
    "MAX_CALLS_PER_DAY": 10000,            # 每天最大调用次数
    "BATCH_SIZE": 5,                       # 批处理大小
    "MAX_WORKERS": 2,                      # 最大工作线程数
    "RETRY_ATTEMPTS": 2,                    # 重试次数
    "REQUEST_TIMEOUT": 30                  # 请求超时时间(秒)
}

# 数据库常量
DB_CONSTANTS = {
    "BACKUP_ENABLED": True,                # 启用备份
    "BACKUP_INTERVAL": "24h",              # 备份间隔
    "CLEANUP_INTERVAL": "168h",            # 清理间隔(7天)
    "ENABLE_LOGGING": True                 # 启用日志
}

# 测试常量
TEST_CONSTANTS = {
    "LOG_LEVEL": "INFO",                   # 日志级别
    "MAX_RESULT_FILES": 10,                # 最大结果文件数
    "SAVE_RESULTS": True,                  # 保存结果
    "ENABLE_LOGGING": True                 # 启用日志
}

# 获取常量的函数
def get_growth_constant(key: str):
    """获取成长股策略常量"""
    return GROWTH_CONSTANTS.get(key)

def get_value_constant(key: str):
    """获取价值股策略常量"""
    return VALUE_CONSTANTS.get(key)

def get_macro_constant(key: str):
    """获取宏观分析常量"""
    return MACRO_CONSTANTS.get(key)

def get_api_constant(key: str):
    """获取API常量"""
    return API_CONSTANTS.get(key)

def get_db_constant(key: str):
    """获取数据库常量"""
    return DB_CONSTANTS.get(key)

def get_test_constant(key: str):
    """获取测试常量"""
    return TEST_CONSTANTS.get(key)

# 导出常量
__all__ = [
    'GROWTH_CONSTANTS',
    'VALUE_CONSTANTS', 
    'MACRO_CONSTANTS',
    'API_CONSTANTS',
    'DB_CONSTANTS',
    'TEST_CONSTANTS',
    'get_growth_constant',
    'get_value_constant',
    'get_macro_constant',
    'get_api_constant',
    'get_db_constant',
    'get_test_constant'
]