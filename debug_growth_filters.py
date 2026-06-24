"""
debug_growth_filters.py - 详细调试成长股筛选过程
"""

import logging
import pandas as pd
import sqlite3
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def debug_growth_filters():
    """详细调试成长股筛选过程"""
    db_path = "database/stock_analysis.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        logger.info("=== 详细调试成长股筛选过程 ===")
        
        # 1. 检查行业数据
        logger.info("1. 检查行业数据...")
        cursor.execute("SELECT DISTINCT industry FROM stock_basic WHERE industry IS NOT NULL AND industry != '' LIMIT 20")
        industries = cursor.fetchall()
        logger.info(f"数据库中的行业示例: {[i[0] for i in industries]}")
        
        # 2. 检查测试配置中的行业
        test_sectors = ["计算机", "电子", "通信", "电力设备", "医药生物", "食品饮料", "机械设备", "有色金属", "化工", "建材"]
        logger.info(f"测试配置中的行业: {test_sectors}")
        
        # 3. 检查行业匹配情况
        logger.info("2. 检查行业匹配情况...")
        matched_stocks = []
        for sector in test_sectors:
            cursor.execute("SELECT COUNT(*) FROM stock_basic WHERE industry = ? AND is_st = 0", (sector,))
            count = cursor.fetchone()[0]
            if count > 0:
                cursor.execute("SELECT ts_code, name FROM stock_basic WHERE industry = ? AND is_st = 0 LIMIT 3", (sector,))
                stocks = cursor.fetchall()
                logger.info(f"行业 {sector}: {count} 只股票, 示例: {stocks}")
                matched_stocks.extend(stocks)
        
        logger.info(f"匹配的股票总数: {len(matched_stocks)}")
        
        # 4. 检查财务数据与股票的关联
        logger.info("3. 检查财务数据与股票的关联...")
        if matched_stocks:
            sample_ts_codes = [s[0] for s in matched_stocks[:5]]
            placeholders = ','.join(['?' for _ in sample_ts_codes])
            
            cursor.execute(f"""
                SELECT s.ts_code, s.name, s.industry, f.roe, f.revenue_yoy, f.net_profit_yoy, f.gross_margin
                FROM stock_basic s
                LEFT JOIN financial_data f ON s.ts_code = f.ts_code
                WHERE s.ts_code IN ({placeholders})
                AND f.end_date = (
                    SELECT MAX(end_date) FROM financial_data WHERE ts_code = s.ts_code
                )
            """, sample_ts_codes)
            
            financial_data = cursor.fetchall()
            
            logger.info("股票财务数据关联情况:")
            for stock in financial_data:
                logger.info(f"  {stock[1]} ({stock[0]}) - 行业: {stock[2]}, ROE: {stock[3]}, 营收增长: {stock[4]}, 净利增长: {stock[5]}, 毛利率: {stock[6]}")
        
        # 5. 模拟成长股筛选过程
        logger.info("4. 模拟成长股筛选过程...")
        
        # 步骤1: 获取股票池
        if test_sectors:  # 确保列表不为空
            placeholders = ','.join(['?' for _ in test_sectors])
            cursor.execute(f"""
                SELECT ts_code, symbol, name, industry, is_st
                FROM stock_basic
                WHERE is_st = 0
                AND industry IN ({placeholders})
                LIMIT 10
            """, test_sectors)
        else:
            cursor.execute("""
                SELECT ts_code, symbol, name, industry, is_st
                FROM stock_basic
                WHERE is_st = 0
                LIMIT 10
            """)
        
        stock_pool = cursor.fetchall()
        logger.info(f"初始股票池数量: {len(stock_pool)}")
        
        # 步骤2: 应用筛选条件
        filtered_count = 0
        for stock in stock_pool:
            ts_code = stock[0]
            industry = stock[3]
            
            # 获取财务数据
            cursor.execute("""
                SELECT roe, revenue_yoy, net_profit_yoy, gross_margin
                FROM financial_data
                WHERE ts_code = ?
                AND end_date = (
                    SELECT MAX(end_date) FROM financial_data WHERE ts_code = ?
                )
            """, (ts_code, ts_code))
            
            financial = cursor.fetchone()
            
            if financial:
                roe, revenue_yoy, net_profit_yoy, gross_margin = financial
                
                # 检查筛选条件
                roe_ok = roe and roe >= 8
                revenue_ok = revenue_yoy and revenue_yoy >= 10
                profit_ok = net_profit_yoy and net_profit_yoy >= 10
                margin_ok = gross_margin and gross_margin >= 25
                
                if roe_ok and revenue_ok and profit_ok and margin_ok:
                    filtered_count += 1
                    logger.info(f"✅ 通过筛选: {stock[1]} - ROE: {roe}, 营收: {revenue_yoy}, 净利: {net_profit_yoy}, 毛利率: {gross_margin}")
                else:
                    logger.info(f"❌ 未通过筛选: {stock[1]} - ROE: {roe}(≥8:{roe_ok}), 营收: {revenue_yoy}(≥10:{revenue_ok}), 净利: {net_profit_yoy}(≥10:{profit_ok}), 毛利率: {gross_margin}(≥25:{margin_ok})")
        
        logger.info(f"最终筛选结果: {filtered_count} 只股票通过筛选")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"调试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_growth_filters()