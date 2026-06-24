"""
独立财务数据批量获取脚本
直接使用Tushare Pro API，不依赖现有系统的插入逻辑
"""
import time
import logging
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# 统一限流器
from rate_limiter import tushare_limiter

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def fetch_all_financial_data():
    """直接拉取所有股票财务数据"""
    
    # 1. 初始化Tushare
    import tushare as ts
    import os
    
    token = os.environ.get('TUSHARE_TOKEN', '')
    if not token:
        logger.error("TUSHARE_TOKEN 未设置")
        return
    
    ts.set_token(token)
    pro = ts.pro_api()
    logger.info("Tushare API初始化成功")
    
    # 2. 连接数据库
    db_path = Path(__file__).parent / "database" / "stock_analysis.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # 3. 获取已存在的股票列表
    cursor.execute("SELECT ts_code, name FROM stock_basic WHERE is_st = 0")
    all_stocks = cursor.fetchall()
    logger.info(f"数据库中共有 {len(all_stocks)} 只股票")
    
    # 4. 检查哪些股票已有财务数据
    cursor.execute("SELECT DISTINCT ts_code FROM financial_data")
    existing = set(row[0] for row in cursor.fetchall())
    logger.info(f"已有财务数据的股票: {len(existing)}只")
    
    # 5. 获取需要处理的股票
    to_fetch = [(code, name) for code, name in all_stocks if code not in existing]
    logger.info(f"需要获取财务数据的股票: {len(to_fetch)}只")
    
    # 6. 批量获取财务数据
    success_count = 0
    error_count = 0
    batch_size = 20
    
    total = min(len(to_fetch), 1500)  # 限制总获取量
    
    for i, (ts_code, name) in enumerate(to_fetch[:total]):
        try:
            # 进度
            if i % 20 == 0:
                logger.info(f"进度: {i}/{total} 成功:{success_count} 失败:{error_count}")
            
            # 获取财务数据
            data = pro.fina_indicator(ts_code=ts_code, limit=4)  # 最近4个季度
            
            if data is not None and not data.empty:
                # 准备插入数据
                for _, row in data.iterrows():
                    try:
                        # 映射字段
                        end_date = str(row.get('end_date', ''))
                        record = {
                            'ts_code': ts_code,
                            'ann_date': str(row.get('ann_date', end_date)),
                            'end_date': end_date,
                            'roe': row.get('roe_dt'),
                            'roa': row.get('roa'),
                            'gross_margin': row.get('grossprofit_margin'),
                            'net_margin': row.get('netprofit_margin'),
                            'revenue_yoy': row.get('or_yoy'),
                            'net_profit_yoy': row.get('profit_dedt'),
                            'debt_ratio': row.get('debt_to_assets'),
                            'eps': row.get('eps'),
                            'bps': row.get('bps'),
                        }
                        
                        cursor.execute("""
                            INSERT OR IGNORE INTO financial_data
                            (ts_code, ann_date, end_date, roe, roa, gross_margin, net_margin,
                             revenue_yoy, net_profit_yoy, debt_ratio, eps, bps)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            record['ts_code'], record['ann_date'], record['end_date'],
                            record['roe'], record['roa'], record['gross_margin'], record['net_margin'],
                            record['revenue_yoy'], record['net_profit_yoy'], record['debt_ratio'],
                            record['eps'], record['bps']
                        ))
                    except Exception:
                        pass
                
                success_count += 1
                if success_count % 50 == 0:
                    conn.commit()
                    logger.info(f"✓ 已提交 {success_count} 只股票")
            else:
                error_count += 1
            
            # 节流 - 使用统一限流器 (1-3秒随机间隔)
            tushare_limiter.wait(min_interval=1.0, max_interval=3.0)
            
        except Exception as e:
            error_count += 1
            if error_count % 20 == 1:
                logger.error(f"✗ 第{i}个错误: {ts_code} - {e}")
    
    # 提交
    conn.commit()
    
    logger.info(f"======= 财务数据获取完成 =======")
    logger.info(f"成功: {success_count} 只股票")
    logger.info(f"失败: {error_count} 只股票")
    
    # 验证
    cursor.execute("SELECT COUNT(DISTINCT ts_code) FROM financial_data")
    final_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM financial_data")
    total_records = cursor.fetchone()[0]
    logger.info(f"数据库中共有 {final_count} 只股票的财务数据，总记录数: {total_records}")
    
    conn.close()

if __name__ == "__main__":
    logger.info("🚀 开始批量获取财务数据...")
    logger.info("=" * 60)
    fetch_all_financial_data()
    logger.info("=" * 60)
    logger.info("✅ 完成！")