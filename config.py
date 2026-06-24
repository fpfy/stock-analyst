"""
A股分析系统主配置文件
"""

import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent.absolute()

# 数据目录配置
DATA_DIR = BASE_DIR / "data"
DB_DIR = BASE_DIR / "database"
REPORTS_DIR = BASE_DIR / "reports"
LOGS_DIR = BASE_DIR / "logs"

# 创建必要的目录
for dir_path in [DATA_DIR, DB_DIR, REPORTS_DIR, LOGS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# 数据库配置
DB_PATH = DB_DIR / "stock_analysis.db"

# 数据源配置
DATA_SOURCE = {
    "name": "Multi",
    "update_time": "15:30",  # 每日收盘后更新
    "market": "A股",
    # 数据源优先级
    "priority": ["Tushare", "AkShare"],
    # Tushare配置
    "tushare": {
        "enabled": True,
        "token_env": "TUSHARE_TOKEN",
        "token": os.environ.get('TUSHARE_TOKEN', ''),
        "api_level": "pro"  # pro或std
    },
    # AkShare配置
    "akshare": {
        "enabled": True,
        "fallback": True  # 作为备用数据源
    }
}

# 大盘状态定义
MARKET_STATUS = {
    "BULL": {
        "name": "牛市",
        "growth_ratio": 0.70,  # 成长股占比70%
        "value_ratio": 0.30,   # 价值股占比30%
        "risk_level": "中高"
    },
    "OSCILLATION": {
        "name": "震荡市",
        "growth_ratio": 0.50,  # 成长股占比50%
        "value_ratio": 0.50,   # 价值股占比50%
        "risk_level": "中"
    },
    "BEAR": {
        "name": "熊市",
        "growth_ratio": 0.30,  # 成长股占比30%
        "value_ratio": 0.70,   # 价值股占比70%
        "risk_level": "中低"
    }
}

# 成长股策略参数
GROWTH_STRATEGY = {
    "revenue_growth_min": 20,      # 营收增长率最小值(%)
    "profit_growth_min": 20,       # 净利润增长率最小值(%)
    "roe_min": 15,                 # ROE最小值(%)
    "gross_margin_min": 40,        # 毛利率最小值(%)
    "peg_max": 2.0,                # PEG最大值
    "preferred_sectors": [
        "计算机", "电子", "通信",
        "电力设备", "医药生物",
        "食品饮料"
    ],
    "max_stocks": 10,              # 最多选出多少只股票
    "min_market_cap": 50,          # 最小市值(亿元)
    "exclude_st": True             # 排除ST股票
}

# 价值股策略参数
VALUE_STRATEGY = {
    "pe_max": 15,                  # PE最大值
    "pb_max": 2.0,                 # PB最大值
    "dividend_yield_min": 3.0,     # 股息率最小值(%)
    "roe_min": 10,                 # ROE最小值(%)
    "debt_ratio_max": 60,          # 负债率最大值(%)
    "preferred_sectors": [
        "银行", "房地产", "公用事业",
        "交通运输", "钢铁", "煤炭"
    ],
    "max_stocks": 10,              # 最多选出多少只股票
    "min_market_cap": 100,         # 最小市值(亿元)
    "exclude_st": True             # 排除ST股票
}

# 技术分析参数
TECHNICAL_ANALYSIS = {
    "ma_periods": [5, 10, 20, 60],  # 均线周期
    "rsi_period": 14,               # RSI周期
    "macd_params": {
        "fast": 12,
        "slow": 26,
        "signal": 9
    },
    "bollinger_period": 20,         # 布林带周期
    "bollinger_std": 2              # 布林带标准差倍数
}

# 风险控制参数
RISK_CONTROL = {
    "max_single_position": 0.15,    # 单只股票最大仓位(15%)
    "stop_loss_ratio": -0.08,       # 止损线(-8%)
    "max_drawdown": -0.10,          # 最大回撤(-10%)
    "rebalance_frequency": "weekly"  # 再平衡频率
}

# 宏观经济指标权重
MACRO_INDICATORS_WEIGHT = {
    "PMI": 0.20,
    "CPI": 0.15,
    "PPI": 0.10,
    "M2_GROWTH": 0.15,
    "GDP_GROWTH": 0.20,
    "INDUSTRIAL_PROFIT": 0.10,
    "NEW_LOAN": 0.10
}

# 大盘技术指标权重
MARKET_TECHNICAL_WEIGHT = {
    "MA_TREND": 0.30,
    "VOLUME": 0.20,
    "MACD": 0.20,
    "RSI": 0.15,
    "BREADTH": 0.15
}

# 报告配置
REPORT_CONFIG = {
    "template_dir": BASE_DIR / "templates",
    "output_format": "markdown",
    "include_charts": True,
    "font_family": "SimHei",  # 支持中文
    "figure_dpi": 100
}

# 日志配置
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        }
    },
    "handlers": {
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "stock_analysis.log"),
            "maxBytes": 10485760,
            "backupCount": 5,
            "formatter": "standard",
            "encoding": "utf-8"
        },
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard"
        }
    },
    "root": {
        "handlers": ["file", "console"],
        "level": "INFO"
    }
}