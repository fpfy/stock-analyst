"""
debug_growth_final_steps.py - 调试成长股策略的最后步骤
找出为什么成长股策略在最后步骤失败
"""

import logging
import sys
import os
from datetime import datetime

# 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from test_config import get_test_config
from stock_selector import GrowthStockSelector
from data_source_manager import DataSourceManager

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def debug_growth_final_steps():
    """调试成长股策略的最后步骤"""
    db_path = "database/stock_analysis.db"
    
    try:
        # 临时使用测试配置
        import config
        original_config = config.GROWTH_STRATEGY
        config.GROWTH_STRATEGY = get_test_config("growth")
        
        logger.info("=== 调试成长股策略的最后步骤 ===")
        
        # 创建数据管理器
        data_manager = DataSourceManager(db_path)
        
        # 创建成长股选股器（在配置替换后创建）
        selector = GrowthStockSelector()
        
        # 1. 获取股票池
        logger.info("1. 获取股票池...")
        stock_pool = selector._get_stock_pool()
        logger.info(f"股票池数量: {len(stock_pool)}")
        
        # 2. 应用筛选条件
        logger.info("2. 应用筛选条件...")
        filtered_stocks = selector._apply_filters(stock_pool)
        logger.info(f"筛选后股票数量: {len(filtered_stocks)}")
        
        if len(filtered_stocks) == 0:
            logger.error("❌ 筛选后股票数量为0，无法继续")
            # 检查配置是否正确
            logger.info(f"当前配置: {config.GROWTH_STRATEGY}")
            return
        
        # 3. 计算评分
        logger.info("3. 计算评分...")
        scored_stocks = selector._calculate_scores(filtered_stocks)
        logger.info(f"评分完成股票数量: {len(scored_stocks)}")
        
        # 4. 选择最优股票
        logger.info("4. 选择最优股票...")
        position_ratio = 0.3
        selected_stocks = selector._select_top_stocks(scored_stocks, position_ratio)
        logger.info(f"最终选中股票数量: {len(selected_stocks)}")
        
        # 5. 检查计算目标价步骤
        logger.info("5. 检查计算目标价步骤...")
        
        # 先检查选中的股票
        if len(selected_stocks) == 0:
            logger.error("❌ 没有选中的股票，无法计算目标价")
            return
        
        # 显示选中的股票
        logger.info("选中的股票:")
        for i, stock in enumerate(selected_stocks, 1):
            logger.info(f"  {i}. {stock.get('name', '')} ({stock.get('ts_code', '')}) - 评分: {stock.get('score', 0):.2f}")
        
        # 尝试计算目标价（但不保存到数据库）
        logger.info("6. 尝试计算目标价...")
        
        for stock in selected_stocks[:2]:  # 只测试前两只股票
            try:
                ts_code = stock['ts_code']
                logger.info(f"正在计算 {stock['name']} ({ts_code}) 的目标价...")
                
                # 获取当前价格
                current_price = selector._get_current_price(ts_code)
                logger.info(f"当前价格: {current_price}")
                
                if current_price:
                    # 简单的目标价计算（基于评分）
                    score = stock.get('score', 50)
                    target_price = current_price * (1 + score / 1000)  # 基于评分的简单目标价
                    stop_loss_price = current_price * 0.9  # 简单的止损价
                    
                    logger.info(f"目标价: {target_price:.2f}, 止损价: {stop_loss_price:.2f}")
                else:
                    logger.warning(f"无法获取 {ts_code} 的当前价格")
                
            except Exception as e:
                logger.error(f"计算 {stock['name']} 目标价失败: {e}")
        
        # 恢复原始配置
        config.GROWTH_STRATEGY = original_config
        
        logger.info("✅ 调试完成")
        
    except Exception as e:
        logger.error(f"调试失败: {e}")
        import traceback
        traceback.print_exc()
        # 确保配置被恢复
        try:
            config.GROWTH_STRATEGY = original_config
        except Exception:
            pass

if __name__ == "__main__":
    debug_growth_final_steps()