"""
财务数据批量获取脚本 - 专门获取财务数据
"""

import sqlite3
import logging
import time
from datetime import datetime
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

class FinancialDataFetcher:
    """财务数据批量获取器"""
    
    def __init__(self):
        self.db_path = Path(__file__).parent / "database" / "stock_analysis.db"
        self.conn = sqlite3.connect(str(self.db_path))
        self.cursor = self.conn.cursor()
        
        # 导入数据获取器
        import realtime_fetcher
        self.fetcher = realtime_fetcher.data_fetcher
        
        logger.info("财务数据获取器初始化完成")
    
    def get_stocks_with_valuation(self):
        """获取有估值数据的股票列表"""
        self.cursor.execute("""
            SELECT DISTINCT ts_code 
            FROM valuation_data 
            WHERE ts_code IN (SELECT ts_code FROM stock_basic WHERE is_st = 0)
            ORDER BY ts_code
        """)
        stocks = [row[0] for row in self.cursor.fetchall()]
        logger.info(f"获取有估值数据的股票: {len(stocks)}只")
        return stocks
    
    def batch_fetch_financial_data(self, stock_codes, batch_size=10):
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
                
                # 节流控制 - 财务数据API限制更严格
                time.sleep(0.5)
                
            except Exception as e:
                error_count += 1
                logger.error(f"✗ {ts_code} 财务数据获取失败: {e}")
                if i % 20 == 0:
                    logger.info(f"错误统计: {error_count}/{i+1}")
        
        logger.info(f"财务数据获取完成: 成功 {success_count}, 失败 {error_count}")
        return success_count
    
    def verify_financial_data(self):
        """验证财务数据"""
        logger.info("=== 财务数据验证 ===")
        
        # 检查各财务指标的数据量
        metrics = [
            "ROE",
            "revenue_yoy", 
            "net_profit_yoy",
            "gross_margin",
            "debt_ratio"
        ]
        
        for metric in metrics:
            self.cursor.execute(f"""
                SELECT COUNT(*) 
                FROM financial_data 
                WHERE {metric} IS NOT NULL AND {metric} != ''
            """)
            count = self.cursor.fetchone()[0]
            logger.info(f"{metric}: {count}条有效数据")
        
        # 查看最新的财务数据日期
        self.cursor.execute("SELECT MAX(end_date) FROM financial_data")
        latest_date = self.cursor.fetchone()[0]
        if latest_date:
            logger.info(f"最新财务数据日期: {latest_date}")
    
    def run_financial_fetch(self):
        """运行财务数据获取"""
        logger.info("🚀 开始批量获取财务数据")
        logger.info("=" * 60)
        
        try:
            # 1. 获取有估值数据的股票
            stocks = self.get_stocks_with_valuation()
            if not stocks:
                logger.error("未找到有估值数据的股票")
                return
            
            # 2. 批量获取财务数据
            logger.info("\n开始批量获取财务数据...")
            success_count = self.batch_fetch_financial_data(stocks)
            
            # 3. 验证数据
            logger.info("\n验证数据完整性...")
            self.verify_financial_data()
            
            logger.info("\n" + "=" * 60)
            logger.info("✅ 财务数据获取完成！")
            logger.info(f"成功获取: {success_count}只股票")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"财务数据获取失败: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.conn.close()

def main():
    """主函数"""
    fetcher = FinancialDataFetcher()
    fetcher.run_financial_fetch()

if __name__ == "__main__":
    main()