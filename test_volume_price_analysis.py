"""
test_volume_price_analysis.py - 量价分析模块测试
"""
import sqlite3
import logging
from volume_price_analysis import VolumePriceAnalysis

logger = logging.getLogger(__name__)

def test_volume_price_analysis():
    """测试量价分析模块"""
    print("=== 量价分析模块测试 ===")
    
    conn = sqlite3.connect('database/stock_analysis.db')
    cursor = conn.cursor()
    
    # 创建量价分析器
    vpa = VolumePriceAnalysis(cursor)
    
    # 测试股票列表
    test_stocks = ['000651.SZ', '000568.SZ', '600036.SH', '600519.SH']
    
    for ts_code in test_stocks:
        print(f"\n--- 测试股票: {ts_code} ---")
        
        try:
            # 1. 测试量价关系分析
            print("\n1. 量价关系分析:")
            volume_price = vpa.calculate_volume_price_relationship(ts_code)
            print(f"量价关系: {volume_price['relationship']}")
            print(f"相关系数: {volume_price['correlation']:.4f}")
            print(f"置信度: {volume_price['confidence']:.4f}")
            print(f"配合度: {volume_price['coordination']:.4f}")
            print(f"趋势一致性: {volume_price['trend_consistency']:.4f}")
            print(f"分析描述: {volume_price['analysis']}")
            
            # 2. 测试突破信号检测
            print("\n2. 突破信号检测:")
            breakout = vpa.detect_breakout_signals(ts_code)
            print(f"突破信号: {breakout['signal']}")
            print(f"置信度: {breakout['confidence']:.4f}")
            print(f"向上突破: {breakout['upward_breakout']}")
            print(f"向下突破: {breakout['downward_breakout']}")
            print(f"突破强度: {breakout['breakout_strength']:.4f}")
            print(f"关键价位: {breakout['key_levels']}")
            print(f"分析描述: {breakout['analysis']}")
            
            # 3. 测试支撑阻力位识别
            print("\n3. 支撑阻力位识别:")
            support_resistance = vpa.identify_support_resistance(ts_code)
            if support_resistance['status'] == 'success':
                print(f"当前价格: {support_resistance['current_price']:.2f}")
                print(f"价格范围: {support_resistance['price_range']}")
                print(f"支撑位: {support_resistance['support_levels']}")
                print(f"阻力位: {support_resistance['resistance_levels']}")
                print(f"动态支撑阻力位: {support_resistance['dynamic_levels']}")
                print(f"分析描述: {support_resistance['analysis']}")
            else:
                print("数据不足，无法识别支撑阻力位")
            
            # 4. 测试综合信号
            print("\n4. 综合信号:")
            comprehensive = vpa.get_volume_price_signals(ts_code)
            print(f"综合信号: {comprehensive['comprehensive_signal']['signal']}")
            print(f"置信度: {comprehensive['comprehensive_signal']['confidence']:.4f}")
            print(f"综合评分: {comprehensive['comprehensive_signal']['score']}")
            print(f"信号描述: {comprehensive['comprehensive_signal']['description']}")
            
        except Exception as e:
            print(f"量价分析失败: {e}")
    
    conn.close()

def test_specific_analysis():
    """测试特定分析功能"""
    print("\n=== 特定分析功能测试 ===")
    
    conn = sqlite3.connect('database/stock_analysis.db')
    cursor = conn.cursor()
    
    vpa = VolumePriceAnalysis(cursor)
    
    # 测试某只股票的详细分析
    test_stock = '000651.SZ'
    print(f"\n详细分析股票: {test_stock}")
    
    # 获取历史数据
    historical_data = vpa.get_historical_data(test_stock, 10)
    print(f"历史数据（前5条）: {historical_data[:5]}")
    
    # 测试相关性计算
    price_changes = [0.01, -0.02, 0.03, -0.01, 0.02]
    volume_changes = [0.02, -0.01, 0.04, -0.02, 0.03]
    correlation = vpa.calculate_correlation(price_changes, volume_changes)
    print(f"测试相关性计算: {correlation:.4f}")
    
    # 测试趋势计算
    trend = vpa.calculate_trend(historical_data)
    print(f"趋势计算结果: {trend}")
    
    conn.close()

def main():
    """主函数"""
    print("开始量价分析模块测试...")
    
    # 测试量价分析模块
    test_volume_price_analysis()
    
    # 测试特定分析功能
    test_specific_analysis()
    
    print("量价分析模块测试完成!")

if __name__ == "__main__":
    main()