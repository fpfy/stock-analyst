"""
debug_growth_strategy.py - 调试成长股策略
找出为什么成长股筛选后股票数量为0
"""

import logging
import pandas as pd
import sqlite3
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def debug_growth_strategy():
    """调试成长股策略"""
    db_path = "database/stock_analysis.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        logger.info("=== 调试成长股策略 ===")
        
        # 1. 检查股票基础数据
        logger.info("1. 检查股票基础数据...")
        cursor.execute("SELECT COUNT(*) FROM stock_basic WHERE is_st = 0")
        non_st_count = cursor.fetchone()[0]
        logger.info(f"非ST股票数量: {non_st_count}")
        
        # 2. 检查财务数据
        logger.info("2. 检查财务数据...")
        cursor.execute("SELECT COUNT(*) FROM financial_data")
        financial_count = cursor.fetchone()[0]
        logger.info(f"财务数据记录数: {financial_count}")
        
        # 3. 检查最新的财务数据
        logger.info("3. 检查最新财务数据...")
        cursor.execute("""
            SELECT COUNT(*) 
            FROM financial_data f
            JOIN (
                SELECT ts_code, MAX(end_date) as max_date
                FROM financial_data
                GROUP BY ts_code
            ) latest ON f.ts_code = latest.ts_code AND f.end_date = latest.max_date
        """)
        latest_financial_count = cursor.fetchone()[0]
        logger.info(f"最新财务数据股票数: {latest_financial_count}")
        
        # 4. 检查具体的财务指标
        logger.info("4. 检查财务指标...")
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN roe >= 15 THEN 1 END) as roe_good,
                COUNT(CASE WHEN revenue_yoy >= 20 THEN 1 END) as revenue_good,
                COUNT(CASE WHEN net_profit_yoy >= 20 THEN 1 END) as profit_good,
                COUNT(CASE WHEN gross_margin >= 40 THEN 1 END) as margin_good
            FROM financial_data
            WHERE end_date = (
                SELECT MAX(end_date) FROM financial_data
            )
        """)
        indicator_stats = cursor.fetchone()
        logger.info(f"财务指标统计: 总数={indicator_stats[0]}, ROE≥15%={indicator_stats[1]}, 营收≥20%={indicator_stats[2]}, 净利≥20%={indicator_stats[3]}, 毛利率≥40%={indicator_stats[4]}")
        
        # 5. 查看一些具体的股票数据
        logger.info("5. 查看具体股票数据...")
        cursor.execute("""
            SELECT f.ts_code, s.name, s.industry, f.roe, f.revenue_yoy, f.net_profit_yoy, f.gross_margin
            FROM financial_data f
            JOIN stock_basic s ON f.ts_code = s.ts_code
            WHERE f.end_date = (
                SELECT MAX(end_date) FROM financial_data
            )
            AND f.roe IS NOT NULL
            AND f.revenue_yoy IS NOT NULL
            AND f.net_profit_yoy IS NOT NULL
            AND f.gross_margin IS NOT NULL
            LIMIT 10
        """)
        sample_stocks = cursor.fetchall()
        
        logger.info("示例股票数据:")
        for stock in sample_stocks:
            logger.info(f"  {stock[1]} ({stock[0]}) - 行业: {stock[2]}, ROE: {stock[3]:.2f}, 营收增长: {stock[4]:.2f}%, 净利增长: {stock[5]:.2f}%, 毛利率: {stock[6]:.2f}%")
        
        # 6. 检查成长股筛选条件
        logger.info("6. 检查成长股筛选条件...")
        cursor.execute("""
            SELECT COUNT(*) 
            FROM financial_data f
            JOIN stock_basic s ON f.ts_code = s.ts_code
            WHERE f.end_date = (
                SELECT MAX(end_date) FROM financial_data
            )
            AND s.is_st = 0
            AND f.roe >= 10
            AND f.revenue_yoy >= 10
            AND f.net_profit_yoy >= 10
            AND f.gross_margin >= 30
        """)
        growth_filtered_count = cursor.fetchone()[0]
        logger.info(f"通过成长股筛选的股票数量: {growth_filtered_count}")
        
        if growth_filtered_count > 0:
            cursor.execute("""
                SELECT f.ts_code, s.name, s.industry, f.roe, f.revenue_yoy, f.net_profit_yoy, f.gross_margin
                FROM financial_data f
                JOIN stock_basic s ON f.ts_code = s.ts_code
                WHERE f.end_date = (
                    SELECT MAX(end_date) FROM financial_data
                )
                AND s.is_st = 0
                AND f.roe >= 10
                AND f.revenue_yoy >= 10
                AND f.net_profit_yoy >= 10
                AND f.gross_margin >= 30
                LIMIT 5
            """)
            growth_stocks = cursor.fetchall()
            logger.info("通过筛选的成长股示例:")
            for stock in growth_stocks:
                logger.info(f"  {stock[1]} ({stock[0]}) - 行业: {stock[2]}, ROE: {stock[3]:.2f}, 营收增长: {stock[4]:.2f}%, 净利增长: {stock[5]:.2f}%, 毛利率: {stock[6]:.2f}%")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"调试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_growth_strategy()