"""
批量数据获取脚本 - 拉取全市场股票的估值和财务数据
"""

import sqlite3
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
import sys

# 统一限流器
from rate_limiter import tushare_limiter

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

class BatchDataFetcher:
    """批量数据获取器"""
    
    def __init__(self):
        self.db_path = Path(__file__).parent / "database" / "stock_analysis.db"
        self.conn = sqlite3.connect(str(self.db_path))
        self.cursor = self.conn.cursor()
        
        # 导入数据获取器
        import realtime_fetcher
        self.fetcher = realtime_fetcher.data_fetcher
        
        logger.info("批量数据获取器初始化完成")
    
    def get_stock_list(self, limit=None):
        """获取股票列表"""
        query = "SELECT ts_code FROM stock_basic WHERE is_st = 0"
        if limit:
            query += f" LIMIT {limit}"
        
        self.cursor.execute(query)
        stocks = [row[0] for row in self.cursor.fetchall()]
        logger.info(f"获取股票列表: {len(stocks)}只")
        return stocks
    
    def batch_fetch_valuation(self, stock_codes, batch_size=20):
        """批量获取估值数据"""
        logger.info(f"开始批量获取 {len(stock_codes)} 只股票的估值数据...")
        
        success_count = 0
        error_count = 0
        
        for i, ts_code in enumerate(stock_codes):
            try:
                logger.info(f"进度: {i+1}/{len(stock_codes)} - {ts_code}")
                
                # 获取估值数据
                data = self.fetcher.fetch_stock_valuation(ts_code)

                if not data.empty:
                    logger.info(f"✓ {ts_code} 估值数据获取成功")
                    success_count += 1
                else:
                    logger.debug(f"- {ts_code} 估值数据为空")

                # 节流控制 - 使用统一限流器 (1-3秒随机间隔)
                tushare_limiter.wait(min_interval=1.0, max_interval=3.0)
                
            except Exception as e:
                error_count += 1
                logger.error(f"✗ {ts_code} 估值数据获取失败: {e}")
                if i % 10 == 0:
                    logger.info(f"错误统计: {error_count}/{i+1}")
        
        logger.info(f"估值数据获取完成: 成功 {success_count}, 失败 {error_count}")
        return success_count
    
    def batch_fetch_financial(self, stock_codes, batch_size=20):
        """批量获取财务数据"""
        logger.info(f"开始批量获取 {len(stock_codes)} 只股票的财务数据...")
        
        success_count = 0
        error_count = 0
        
        for i, ts_code in enumerate(stock_codes):
            try:
                logger.info(f"进度: {i+1}/{len(stock_codes)} - {ts_code}")
                
                # 获取财务数据
                data = self.fetcher.fetch_stock_financial(ts_code)

                if not data.empty:
                    logger.info(f"✓ {ts_code} 财务数据获取成功")
                    success_count += 1
                else:
                    logger.debug(f"- {ts_code} 财务数据为空")

                # 节流控制 - 使用统一限流器 (1-3秒随机间隔)
                tushare_limiter.wait(min_interval=1.0, max_interval=3.0)
                
            except Exception as e:
                error_count += 1
                logger.error(f"✗ {ts_code} 财务数据获取失败: {e}")
                if i % 10 == 0:
                    logger.info(f"错误统计: {error_count}/{i+1}")
        
        logger.info(f"财务数据获取完成: 成功 {success_count}, 失败 {error_count}")
        return success_count
    
    def update_progress(self, stage, total, current):
        """更新进度"""
        percentage = (current / total) * 100
        logger.info(f"{stage}: {current}/{total} ({percentage:.1f}%)")
    
    def verify_data(self):
        """验证数据完整性"""
        logger.info("=== 数据完整性验证 ===")
        
        # 检查各表数据量
        checks = [
            ("股票基本信息", "SELECT COUNT(*) FROM stock_basic"),
            ("有估值数据的股票", "SELECT COUNT(DISTINCT ts_code) FROM valuation_data"),
            ("有财务数据的股票", "SELECT COUNT(DISTINCT ts_code) FROM financial_data"),
            ("指数数据", "SELECT COUNT(*) FROM index_data"),
        ]
        
        for name, query in checks:
            self.cursor.execute(query)
            count = self.cursor.fetchone()[0]
            logger.info(f"{name}: {count}")
        
        # 检查估值数据的最新日期
        self.cursor.execute("SELECT MAX(trade_date) FROM valuation_data")
        latest_date = self.cursor.fetchone()[0]
        if latest_date:
            logger.info(f"估值数据最新日期: {latest_date}")
        
        # 检查财务数据的最新日期
        self.cursor.execute("SELECT MAX(end_date) FROM financial_data")
        latest_financial = self.cursor.fetchone()[0]
        if latest_financial:
            logger.info(f"财务数据最新日期: {latest_financial}")
    
    def run_batch_fetch(self, stock_limit=500):
        """运行批量数据获取"""
        logger.info("🚀 开始批量数据获取")
        logger.info("=" * 60)
        
        try:
            # 1. 获取股票列表
            stocks = self.get_stock_list(stock_limit)
            if not stocks:
                logger.error("未找到可用的股票")
                return
            
            # 2. 批量获取估值数据
            logger.info("\n第一步：批量获取估值数据")
            valuation_success = self.batch_fetch_valuation(stocks)
            
            # 3. 批量获取财务数据
            logger.info("\n第二步：批量获取财务数据")
            financial_success = self.batch_fetch_financial(stocks)
            
            # 4. 验证数据
            logger.info("\n第三步：验证数据完整性")
            self.verify_data()
            
            logger.info("\n" + "=" * 60)
            logger.info("✅ 批量数据获取完成！")
            logger.info(f"估值数据: {valuation_success}只股票")
            logger.info(f"财务数据: {financial_success}只股票")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"批量数据获取失败: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.conn.close()

def main():
    """主函数"""
    fetcher = BatchDataFetcher()
    fetcher.run_batch_fetch(stock_limit=500)  # 先拉取500只股票的数据

if __name__ == "__main__":
    main()