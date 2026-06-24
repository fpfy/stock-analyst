"""
test_config.py - 测试配置文件
使用更宽松的筛选条件，确保测试时有足够的股票
"""

# 测试用的成长股策略配置（更宽松）
TEST_GROWTH_STRATEGY = {
    "revenue_growth_min": 5,       # 营收增长率最小值(%)
    "profit_growth_min": 5,        # 净利润增长率最小值(%)
    "roe_min": 5,                  # ROE最小值(%)
    "gross_margin_min": 20,        # 毛利率最小值(%)
    "peg_max": 3.0,                # PEG最大值
    "preferred_sectors": [
        "软件服务", "全国地产", "电气设备", "医药商业",
        "元器件", "家用电器", "汽车配件", "建筑工程",
        "房产服务", "环境保护", "其他建材", "农业综合"
    ],
    "max_stocks": 10,              # 最多选出多少只股票
    "min_market_cap": 20,          # 最小市值(亿元)
    "exclude_st": True             # 排除ST股票
}

# 测试用的价值股策略配置（更宽松）
TEST_VALUE_STRATEGY = {
    "pe_max": 20,                  # PE最大值
    "pb_max": 3.0,                 # PB最大值
    "dividend_yield_min": 2.0,     # 股息率最小值(%)
    "roe_min": 8,                  # ROE最小值(%)
    "debt_ratio_max": 70,          # 负债率最大值(%)
    "preferred_sectors": [
        "银行", "房地产", "公用事业", "交通运输", 
        "钢铁", "煤炭", "有色金属", "化工"
    ],
    "max_stocks": 10,              # 最多选出多少只股票
    "min_market_cap": 50,          # 最小市值(亿元)
    "exclude_st": True             # 排除ST股票
}

# 测试用的宏观分析配置
TEST_MACRO_CONFIG = {
    "data_update_time": "09:00",
    "analysis_trigger_time": "10:00",
    "report_generation_time": "15:00",
    "enable_sentiment_analysis": True,
    "enable_technical_analysis": True,
    "risk_levels": ["low", "medium", "high"]
}

# API测试配置
TEST_API_CONFIG = {
    "max_calls_per_minute": 30,
    "max_calls_per_hour": 200,
    "max_calls_per_day": 10000,
    "batch_size": 5,
    "max_workers": 2,
    "retry_attempts": 2,
    "request_timeout": 30
}

# 数据库测试配置
TEST_DB_CONFIG = {
    "db_path": "database/stock_analysis.db",
    "backup_enabled": True,
    "backup_interval": "24h",
    "cleanup_interval": "168h",  # 7天清理一次
    "enable_logging": True
}

# 测试结果配置
TEST_RESULT_CONFIG = {
    "save_results": True,
    "result_dir": "test_results",
    "enable_logging": True,
    "log_level": "INFO",
    "max_result_files": 10
}

# 获取测试配置的函数
def get_test_config(config_type: str):
    """获取测试配置"""
    if config_type == "growth":
        return TEST_GROWTH_STRATEGY
    elif config_type == "value":
        return TEST_VALUE_STRATEGY
    elif config_type == "macro":
        return TEST_MACRO_CONFIG
    elif config_type == "api":
        return TEST_API_CONFIG
    elif config_type == "db":
        return TEST_DB_CONFIG
    elif config_type == "result":
        return TEST_RESULT_CONFIG
    else:
        raise ValueError(f"未知的配置类型: {config_type}")

# 导出测试配置
__all__ = [
    'TEST_GROWTH_STRATEGY',
    'TEST_VALUE_STRATEGY', 
    'TEST_MACRO_CONFIG',
    'TEST_API_CONFIG',
    'TEST_DB_CONFIG',
    'TEST_RESULT_CONFIG',
    'get_test_config'
]