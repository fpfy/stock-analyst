"""
test_dual_strategy_selector.py - 使用测试配置的双策略选股器
"""

import logging
import sys
import os
from datetime import datetime
from typing import Dict, List, Tuple

# 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from test_config import get_test_config
from dual_strategy_selector import DualStrategySelector
from data_source_manager import DataSourceManager
from config_manager import patch_config

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TestDualStrategySelector:
    """使用测试配置的双策略选股器"""
    
    def __init__(self, db_path: str = "database/stock_analysis.db"):
        self.db_path = db_path
        self.data_manager = DataSourceManager(db_path)
        
        # 使用测试配置
        self.test_growth_config = get_test_config("growth")
        self.test_value_config = get_test_config("value")
        
        # 初始化原始选股器
        self.selector = DualStrategySelector(db_path)
    
    def test_strategy_selection(self) -> Dict:
        """测试双策略选股"""
        logger.info("🧪 开始测试双策略选股...")
        
        try:
            # 使用上下文管理器安全地替换配置
            with patch_config({
                'GROWTH_STRATEGY': self.test_growth_config,
                'VALUE_STRATEGY': self.test_value_config
            }):
                # 执行双策略选股
                results = self.selector.run_dual_strategy_selection()
            
            if results and 'error' not in results:
                logger.info("✅ 双策略选股测试成功")
                logger.info(f"   成长股数量: {len(results.get('growth_stocks', []))}")
                logger.info(f"   价值股数量: {len(results.get('value_stocks', []))}")
                logger.info(f"   仓位配置: {results.get('position_allocation', {})}")
                
                # 显示选中的股票
                growth_stocks = results.get('growth_stocks', [])
                value_stocks = results.get('value_stocks', [])
                
                if growth_stocks:
                    logger.info("📈 成长股:")
                    for i, stock in enumerate(growth_stocks[:3], 1):
                        logger.info(f"   {i}. {stock.get('name', '')} ({stock.get('ts_code', '')}) - 评分: {stock.get('growth_score', 0):.2f}")
                
                if value_stocks:
                    logger.info("📊 价值股:")
                    for i, stock in enumerate(value_stocks[:3], 1):
                        logger.info(f"   {i}. {stock.get('name', '')} ({stock.get('ts_code', '')}) - 评分: {stock.get('value_score', 0):.2f}")
                
                return results
            else:
                logger.error(f"❌ 双策略选股失败: {results.get('error', '未知错误')}")
                return results
                
        except Exception as e:
            logger.error(f"❌ 双策略选股测试异常: {e}")
            return {'error': str(e)}


def main():
    """主函数"""
    logger.info("🚀 开始双策略选股测试...")
    
    try:
        # 创建测试选股器
        test_selector = TestDualStrategySelector()
        
        # 执行测试
        results = test_selector.test_strategy_selection()
        
        if results and 'error' not in results:
            print("✅ 双策略选股测试通过！")
            return True
        else:
            print("❌ 双策略选股测试失败")
            return False
            
    except Exception as e:
        logger.error(f"测试执行异常: {e}")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)