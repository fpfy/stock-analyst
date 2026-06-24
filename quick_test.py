"""
quick_test.py - 快速测试数据源管理器
测试实际数据源的可用性
"""

import logging
from data_source_manager import DataSourceManager

logging.basicConfig(level=logging.INFO)

def test_data_sources():
    """测试数据源管理器"""
    print("=== 数据源管理器快速测试 ===")
    
    manager = DataSourceManager()
    
    try:
        # 测试宏观数据
        print("\n1. 宏观经济数据:")
        macro_data = manager.get_macro_data()
        for key, value in macro_data.items():
            print(f"  {key}: {value}")
        
        # 测试指数数据
        print("\n2. 主要指数数据:")
        indices = manager.get_market_indices()
        for code, data in indices.items():
            print(f"  {data['name']}: {data['close']} ({data['change_pct']:.2f}%)")
        
        # 测试市场状态
        print("\n3. 市场状态:")
        market_state = manager.get_market_state()
        print(f"  当前市场状态: {market_state}")
        
        # 测试仓位分配
        print("\n4. 动态仓位分配:")
        allocation = manager.get_dynamic_position_allocation()
        print(f"  成长股: {allocation['growth']*100:.0f}%")
        print(f"  价值股: {allocation['value']*100:.0f}%")
        
        # 测试股票列表
        print("\n5. 股票列表:")
        stocks = manager.get_stocks_list()
        print(f"  股票总数: {len(stocks)}")
        if len(stocks) > 0:
            print(f"  前5只股票:")
            for i, (_, row) in enumerate(stocks.head().iterrows()):
                print(f"    {i+1}. {row['code']} - {row['name']}")
        
        # 测试融资融券数据
        print("\n6. 融资融券数据:")
        margin_data = manager.get_margin_data()
        if margin_data.get('market_sentiment'):
            sentiment = margin_data['market_sentiment']
            print(f"  上涨家数比例: {sentiment['up_ratio']:.2f}")
            print(f"  下跌家数比例: {sentiment['down_ratio']:.2f}")
            print(f"  总股票数: {sentiment['total_stocks']}")
        else:
            print("  融资融券数据获取失败")
        
        print("\n=== 测试完成 ===")
        
    except Exception as e:
        print(f"测试失败: {e}")
    finally:
        manager.close()

if __name__ == "__main__":
    test_data_sources()