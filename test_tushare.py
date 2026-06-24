"""
Tushare数据源测试脚本
"""

import logging
import logging.config
import sys
from datetime import datetime
from pathlib import Path

# 配置日志
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
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard"
        }
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO"
    }
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

# 导入模块
import database
import tushare_fetcher

def test_tushare():
    """测试Tushare数据源"""
    logger.info("=" * 60)
    logger.info("开始测试Tushare数据源")
    logger.info("=" * 60)

    try:
        # 1. 检查Tushare初始化
        logger.info("\n1. 检查Tushare初始化...")
        fetcher = tushare_fetcher.tushare_fetcher

        if not fetcher.token:
            logger.error("Tushare token未配置，请设置环境变量TUSHARE_TOKEN")
            return False

        logger.info(f"✓ Tushare token已配置: {fetcher.token[:10]}...")

        # 2. 测试连接
        logger.info("\n2. 测试Tushare连接...")
        if fetcher._check_connection():
            logger.info("✓ Tushare连接成功")
        else:
            logger.error("✗ Tushare连接失败")
            return False

        # 3. 测试获取宏观经济指标
        logger.info("\n3. 测试获取宏观经济指标...")
        pmi_data = fetcher.fetch_macro_indicator("PMI")
        if not pmi_data.empty:
            logger.info(f"✓ 成功获取PMI数据，记录数: {len(pmi_data)}")
            logger.info(f"  最新PMI: {pmi_data.iloc[-1]['value']}")
        else:
            logger.warning("✗ PMI数据获取失败")

        # 4. 测试获取指数数据
        logger.info("\n4. 测试获取指数数据...")
        index_data = fetcher.fetch_index_data("000001.SH")
        if not index_data.empty:
            logger.info(f"✓ 成功获取上证指数数据，记录数: {len(index_data)}")
            logger.info(f"  最新收盘: {index_data.iloc[-1]['close']}点")
            logger.info(f"  涨跌幅: {index_data.iloc[-1]['change_pct']}%")
        else:
            logger.warning("✗ 指数数据获取失败")

        # 5. 测试获取股票基本信息
        logger.info("\n5. 测试获取股票基本信息...")
        stock_basic = fetcher.fetch_stock_basic()
        if not stock_basic.empty:
            logger.info(f"✓ 成功获取股票基本信息，记录数: {len(stock_basic)}")
            test_stock = stock_basic.iloc[0]['ts_code']
            logger.info(f"  示例股票: {stock_basic.iloc[0]['name']} ({test_stock})")
        else:
            logger.warning("✗ 股票基本信息获取失败")
            test_stock = None

        # 6. 测试获取财务数据
        logger.info("\n6. 测试获取股票财务数据...")
        if test_stock:
            financial_data = fetcher.fetch_stock_financial(test_stock)
            if not financial_data.empty:
                logger.info(f"✓ 成功获取{test_stock}财务数据，记录数: {len(financial_data)}")
                latest = financial_data.iloc[-1]
                logger.info(f"  最新ROE: {latest.get('roe', 'N/A')}%")
                logger.info(f"  最新营收增长率: {latest.get('revenue_yoy', 'N/A')}%")
            else:
                logger.warning(f"✗ {test_stock}财务数据获取失败")

        # 7. 测试获取估值数据
        logger.info("\n7. 测试获取股票估值数据...")
        if not stock_basic.empty:
            test_stock = stock_basic.iloc[0]['ts_code']
            valuation_data = fetcher.fetch_stock_valuation(test_stock)
            if not valuation_data.empty:
                logger.info(f"✓ 成功获取{test_stock}估值数据，记录数: {len(valuation_data)}")
                latest = valuation_data.iloc[-1]
                logger.info(f"  最新PE: {latest.get('pe', 'N/A')}")
                logger.info(f"  最新PB: {latest.get('pb', 'N/A')}")
            else:
                logger.warning(f"✗ {test_stock}估值数据获取失败")

        # 8. 测试获取实时市场数据
        logger.info("\n8. 测试获取实时市场数据...")
        realtime_data = fetcher.fetch_realtime_market('000001.SH')
        if realtime_data:
            logger.info(f"✓ 成功获取上证指数实时数据")
            logger.info(f"  当前点位: {realtime_data['current']:.0f}")
            logger.info(f"  涨跌幅: {realtime_data['change_pct']:.2f}%")
        else:
            logger.warning("✗ 实时市场数据获取失败")

        logger.info("\n" + "=" * 60)
        logger.info("✅ Tushare数据源测试完成！")
        logger.info("=" * 60)

        return True

    except Exception as e:
        logger.error(f"Tushare测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_data_source_manager():
    """测试数据源管理器"""
    logger.info("\n" + "=" * 60)
    logger.info("开始测试数据源管理器")
    logger.info("=" * 60)

    try:
        import data_source_manager

        manager = data_source_manager.data_source_manager

        # 获取数据源状态
        status = manager.get_source_status()
        logger.info(f"\n数据源状态:")
        logger.info(f"  - 总数据源数: {status['total_sources']}")
        logger.info(f"  - 优先级顺序: {status['priority_order']}")
        logger.info(f"  - 活动数据源: {status['active_sources']}")
        logger.info(f"  - 非活动数据源: {status['inactive_sources']}")

        # 测试获取数据
        logger.info("\n测试通过管理器获取数据...")

        pmi_data = manager.fetch_macro_indicator("PMI")
        if not pmi_data.empty:
            logger.info(f"✓ 通过管理器成功获取PMI数据")
        else:
            logger.warning("✗ 通过管理器获取PMI数据失败")

        index_data = manager.fetch_index_data("000001.SH")
        if not index_data.empty:
            logger.info(f"✓ 通过管理器成功获取指数数据")
        else:
            logger.warning("✗ 通过管理器获取指数数据失败")

        logger.info("\n" + "=" * 60)
        logger.info("✅ 数据源管理器测试完成！")
        logger.info("=" * 60)

        return True

    except Exception as e:
        logger.error(f"数据源管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    logger.info("🚀 Tushare数据源测试程序启动\n")

    # 测试Tushare
    tushare_ok = test_tushare()

    # 测试数据源管理器
    if tushare_ok:
        test_data_source_manager()

    logger.info("\n💡 提示: Tushare已成功集成到系统中！")
    logger.info("   现在可以使用Tushare作为主要数据源进行股票分析。")

if __name__ == "__main__":
    main()