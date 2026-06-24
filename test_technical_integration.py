"""
test_technical_integration.py - 技术面整合测试脚本
"""
import sqlite3
import logging
from technical_integration import TechnicalIntegration

logger = logging.getLogger(__name__)

def test_technical_integration():
    """测试技术面整合功能"""
    print("=== 技术面整合测试 ===")
    
    conn = sqlite3.connect('database/stock_analysis.db')
    cursor = conn.cursor()
    
    # 创建技术面整合器
    ti = TechnicalIntegration(cursor)
    
    # 测试股票列表
    test_stocks = ['000651.SZ', '000568.SZ', '600036.SH', '600519.SH']
    
    # 测试成长股策略
    print("\n--- 成长股策略测试 ---")
    growth_results = ti.integrate_technical_analysis(test_stocks, 'growth')
    
    # 测试价值股策略
    print("\n--- 价值股策略测试 ---")
    value_results = ti.integrate_technical_analysis(test_stocks, 'value')
    
    # 生成报告
    print("\n--- 生成技术面整合报告 ---")
    growth_report = ti.generate_technical_report(growth_results)
    value_report = ti.generate_technical_report(value_results)
    
    # 输出结果
    print("\n成长股策略结果:")
    for result in growth_results:
        print(f"  {result['ts_code']}: {result['trading_advice']['signal']} - {result['comprehensive_score']['total_score']:.1f}分")
    
    print("\n价值股策略结果:")
    for result in value_results:
        print(f"  {result['ts_code']}: {result['trading_advice']['signal']} - {result['comprehensive_score']['total_score']:.1f}分")
    
    # 输出报告
    print("\n成长股策略报告:")
    print(growth_report)
    
    print("\n价值股策略报告:")
    print(value_report)
    
    conn.close()

def test_individual_analysis():
    """测试个股详细分析"""
    print("\n=== 个股详细分析测试 ===")
    
    conn = sqlite3.connect('database/stock_analysis.db')
    cursor = conn.cursor()
    
    # 创建技术面整合器
    ti = TechnicalIntegration(cursor)
    
    # 测试股票
    test_stock = '000651.SZ'
    
    try:
        # 获取基本面数据
        fundamental_data = ti._get_fundamental_data(test_stock)
        print(f"基本面数据: {fundamental_data}")
        
        # 获取技术面数据
        technical_data = ti._get_technical_data(test_stock)
        print(f"技术面数据: {technical_data}")
        
        # 获取量价数据
        volume_price_data = ti._get_volume_price_data(test_stock)
        print(f"量价数据: {volume_price_data}")
        
        # 计算综合评分
        comprehensive_score = ti._get_comprehensive_score(
            test_stock, 'growth', fundamental_data, technical_data, volume_price_data
        )
        print(f"综合评分: {comprehensive_score}")
        
        # 生成交易建议
        trading_advice = ti._generate_trading_advice(
            test_stock, 'growth', fundamental_data, technical_data, 
            volume_price_data, comprehensive_score
        )
        print(f"交易建议: {trading_advice}")
        
    except Exception as e:
        print(f"个股分析失败: {e}")
    
    conn.close()

def test_scoring_system():
    """测试评分系统"""
    print("\n=== 评分系统测试 ===")
    
    conn = sqlite3.connect('database/stock_analysis.db')
    cursor = conn.cursor()
    
    # 创建技术面整合器
    ti = TechnicalIntegration(cursor)
    
    # 测试股票
    test_stocks = ['000651.SZ', '000568.SZ', '600036.SH', '600519.SH']
    
    for ts_code in test_stocks:
        try:
            print(f"\n--- {ts_code} 评分分析 ---")
            
            # 获取数据
            fundamental_data = ti._get_fundamental_data(ts_code)
            technical_data = ti._get_technical_data(ts_code)
            volume_price_data = ti._get_volume_price_data(ts_code)
            
            # 计算各模块评分
            fundamental_score = ti._score_fundamental_data(ts_code, 'growth', fundamental_data)
            technical_score = ti._score_technical_data(ts_code, 'growth', technical_data)
            volume_price_score = ti._score_volume_price_data(ts_code, 'growth', volume_price_data)
            
            print(f"基本面评分: {fundamental_score:.1f}/40")
            print(f"技术面评分: {technical_score:.1f}/35")
            print(f"量价评分: {volume_price_score:.1f}/25")
            
            # 计算综合评分
            comprehensive_score = ti._get_comprehensive_score(
                ts_code, 'growth', fundamental_data, technical_data, volume_price_data
            )
            print(f"综合评分: {comprehensive_score['total_score']:.1f}/100")
            
        except Exception as e:
            print(f"评分分析失败: {e}")
    
    conn.close()

def test_strategy_comparison():
    """测试策略对比"""
    print("\n=== 策略对比测试 ===")
    
    conn = sqlite3.connect('database/stock_analysis.db')
    cursor = conn.cursor()
    
    # 创建技术面整合器
    ti = TechnicalIntegration(cursor)
    
    # 测试股票
    test_stocks = ['000651.SZ', '000568.SZ', '600036.SH', '600519.SH']
    
    # 对比两种策略
    growth_results = ti.integrate_technical_analysis(test_stocks, 'growth')
    value_results = ti.integrate_technical_analysis(test_stocks, 'value')
    
    print("\n策略对比结果:")
    print("| 股票代码 | 成长股策略 | 价值股策略 | 差异 |")
    print("|----------|------------|------------|------|")
    
    for i, (growth_result, value_result) in enumerate(zip(growth_results, value_results)):
        ts_code = growth_result['ts_code']
        growth_score = growth_result['comprehensive_score']['total_score']
        value_score = value_result['comprehensive_score']['total_score']
        difference = growth_score - value_score
        
        print(f"| {ts_code} | {growth_score:.1f} | {value_score:.1f} | {difference:+.1f} |")
    
    conn.close()

def test_report_generation():
    """测试报告生成"""
    print("\n=== 报告生成测试 ===")
    
    conn = sqlite3.connect('database/stock_analysis.db')
    cursor = conn.cursor()
    
    # 创建技术面整合器
    ti = TechnicalIntegration(cursor)
    
    # 测试股票
    test_stocks = ['000651.SZ', '000568.SZ', '600036.SH', '600519.SH']
    
    # 生成成长股报告
    growth_results = ti.integrate_technical_analysis(test_stocks, 'growth')
    growth_report = ti.generate_technical_report(growth_results)
    
    # 生成价值股报告
    value_results = ti.integrate_technical_analysis(test_stocks, 'value')
    value_report = ti.generate_technical_report(value_results)
    
    # 保存报告
    with open('growth_technical_report.md', 'w', encoding='utf-8') as f:
        f.write(growth_report)
    
    with open('value_technical_report.md', 'w', encoding='utf-8') as f:
        f.write(value_report)
    
    print("报告生成完成:")
    print("- growth_technical_report.md")
    print("- value_technical_report.md")
    
    conn.close()

def main():
    """主函数"""
    print("开始技术面整合测试...")
    
    # 测试技术面整合功能
    test_technical_integration()
    
    # 测试个股详细分析
    test_individual_analysis()
    
    # 测试评分系统
    test_scoring_system()
    
    # 测试策略对比
    test_strategy_comparison()
    
    # 测试报告生成
    test_report_generation()
    
    print("技术面整合测试完成!")

if __name__ == "__main__":
    main()