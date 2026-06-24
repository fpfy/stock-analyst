"""
test_technical_indicators.py - 技术指标测试脚本
使用模拟数据测试技术指标计算功能
"""
import sqlite3
import logging
from datetime import datetime, timedelta
from technical_indicators import TechnicalIndicators
import math
import random

logger = logging.getLogger(__name__)

def create_sample_data():
    """创建示例数据"""
    conn = sqlite3.connect('database/stock_analysis.db')
    cursor = conn.cursor()
    
    # 启用WAL模式
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    
    # 插入示例股票
    sample_stocks = [
        ('000651.SZ', '格力电器', '家用电器', '广东', '深圳主板', '2006-06-01'),
        ('000568.SZ', '泸州老窖', '食品饮料', '四川', '深圳主板', '1994-05-09'),
        ('600036.SH', '招商银行', '银行', '广东', '上海主板', '2002-04-09'),
        ('600519.SH', '贵州茅台', '食品饮料', '贵州', '上海主板', '2001-08-27'),
    ]
    
    for ts_code, name, industry, area, market, list_date in sample_stocks:
        cursor.execute("""
            INSERT OR REPLACE INTO stock_basic 
            (ts_code, name, industry, area, market, list_date, update_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ts_code, name, industry, area, market, list_date, datetime.now().strftime('%Y-%m-%d')))
    
    # 生成模拟日线数据
    end_date = datetime.now()
    start_date = end_date - timedelta(days=100)
    
    for ts_code, name, industry, area, market, list_date in sample_stocks:
        current_date = max(datetime.strptime(list_date, '%Y-%m-%d'), start_date)
        
        while current_date <= end_date:
            # 生成模拟价格数据
            base_price = 30 + hash(ts_code) % 70  # 基础价格30-100
            day_of_year = current_date.timetuple().tm_yday
            price_factor = 1 + 0.1 * math.sin(day_of_year / 30)  # 正弦波动
            
            close = base_price * price_factor
            open_price = close * (0.98 + 0.04 * random.random())
            high = close * (1.02 + 0.03 * random.random())
            low = close * (0.98 - 0.03 * random.random())
            volume = 1000000 + 500000 * random.random()
            amount = close * volume
            pct_change = (close - open_price) / open_price * 100
            
            cursor.execute("""
                INSERT OR REPLACE INTO daily_quotes
                (ts_code, trade_date, open, high, low, close, volume, amount, pct_change)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ts_code,
                current_date.strftime('%Y-%m-%d'),
                open_price,
                high,
                low,
                close,
                volume,
                amount,
                pct_change
            ))
            
            current_date += timedelta(days=1)
    
    conn.commit()
    conn.close()

def test_technical_indicators():
    """测试技术指标计算"""
    print("=== 技术指标测试 ===")
    
    conn = sqlite3.connect('database/stock_analysis.db')
    cursor = conn.cursor()
    
    # 创建技术指标计算器
    ti = TechnicalIndicators(cursor)
    
    # 测试股票列表
    test_stocks = ['000651.SZ', '000568.SZ', '600036.SH', '600519.SH']
    
    for ts_code in test_stocks:
        print(f"\n--- 测试股票: {ts_code} ---")
        
        try:
            # 获取技术指标
            indicators = ti.get_latest_technical_indicators(ts_code)
            print(f"技术指标: {indicators}")
            
            # 分析趋势
            trend_analysis = ti.analyze_trend(ts_code)
            print(f"趋势分析: {trend_analysis}")
            
        except Exception as e:
            print(f"计算技术指标失败: {e}")
    
    # 测试趋势分析
    print("\n--- 趋势分析测试 ---")
    try:
        bullish_stocks = []
        for ts_code in test_stocks:
            trend_analysis = ti.analyze_trend(ts_code)
            if trend_analysis['trend'] == 'bullish':
                bullish_stocks.append({
                    'ts_code': ts_code,
                    'trend': trend_analysis['trend'],
                    'signal': trend_analysis['signal']
                })
        
        print(f"看涨股票数量: {len(bullish_stocks)}")
        for stock in bullish_stocks:
            print(f"  {stock['ts_code']}: {stock['trend']}, {stock['signal']}")
            
    except Exception as e:
        print(f"趋势分析失败: {e}")
    
    conn.close()

def main():
    """主函数"""
    import math
    import random
    
    print("开始技术指标测试...")
    
    # 创建示例数据
    print("创建示例数据...")
    create_sample_data()
    
    # 测试技术指标
    print("测试技术指标...")
    test_technical_indicators()
    
    print("技术指标测试完成!")

if __name__ == "__main__":
    main()