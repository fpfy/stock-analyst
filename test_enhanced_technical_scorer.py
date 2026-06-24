"""
test_enhanced_technical_scorer.py - 增强版技术面评分系统测试
"""
import sqlite3
import logging
from enhanced_technical_scorer import EnhancedTechnicalScorer

logger = logging.getLogger(__name__)

def test_enhanced_technical_scorer():
    """测试增强版技术面评分系统"""
    print("=== 增强版技术面评分系统测试 ===")
    
    conn = sqlite3.connect('database/stock_analysis.db')
    cursor = conn.cursor()
    
    # 创建增强版技术面评分器
    ets = EnhancedTechnicalScorer(cursor)
    
    # 测试股票列表
    test_stocks = ['000651.SZ', '000568.SZ', '600036.SH', '600519.SH']
    
    for ts_code in test_stocks:
        print(f"\n--- 测试股票: {ts_code} ---")
        
        try:
            # 增强版技术面评分
            result = ets.score_technical_enhanced(ts_code)
            
            print(f"总评分: {result['total_score']:.1f}")
            print(f"评级: {result['rating']}")
            print(f"信号: {result['signal']}")
            print(f"技术指标评分: {result['technical_indicators_score']['total']:.1f}")
            print(f"量价关系评分: {result['volume_price_score']['total']:.1f}")
            print(f"突破信号评分: {result['breakout_score']['total']:.1f}")
            print(f"支撑阻力位评分: {result['support_resistance_score']['total']:.1f}")
            print(f"详细分析: {result['analysis']}")
            
        except Exception as e:
            print(f"增强版技术面评分失败: {e}")
    
    conn.close()

def test_batch_scoring():
    """测试批量评分功能"""
    print("\n=== 批量评分测试 ===")
    
    conn = sqlite3.connect('database/stock_analysis.db')
    cursor = conn.cursor()
    
    ets = EnhancedTechnicalScorer(cursor)
    
    # 批量评分
    test_stocks = ['000651.SZ', '000568.SZ', '600036.SH', '600519.SH']
    batch_results = ets.batch_score_technical(test_stocks)
    
    print(f"批量评分结果数量: {len(batch_results)}")
    
    for result in batch_results:
        if 'error' in result:
            print(f"{result['ts_code']}: 评分失败 - {result['error']}")
        else:
            print(f"{result['ts_code']}: {result['total_score']:.1f}分 ({result['rating']})")
    
    conn.close()

def test_top_stocks():
    """测试获取评分最高的股票"""
    print("\n=== 获取评分最高的股票 ===")
    
    conn = sqlite3.connect('database/stock_analysis.db')
    cursor = conn.cursor()
    
    ets = EnhancedTechnicalScorer(cursor)
    
    # 获取评分最高的股票
    test_stocks = ['000651.SZ', '000568.SZ', '600036.SH', '600519.SH']
    top_stocks = ets.get_top_stocks(test_stocks, top_n=3)
    
    print(f"评分最高的股票（前3名）:")
    for i, stock in enumerate(top_stocks, 1):
        print(f"{i}. {stock['ts_code']}: {stock['total_score']:.1f}分 ({stock['rating']})")
        print(f"   信号: {stock['signal']}")
        print(f"   技术指标: {stock['technical_indicators_score']['total']:.1f}")
        print(f"   量价关系: {stock['volume_price_score']['total']:.1f}")
        print(f"   突破信号: {stock['breakout_score']['total']:.1f}")
        print(f"   支撑阻力: {stock['support_resistance_score']['total']:.1f}")
        print()
    
    conn.close()

def test_score_comparison():
    """测试评分对比"""
    print("\n=== 评分对比分析 ===")
    
    conn = sqlite3.connect('database/stock_analysis.db')
    cursor = conn.cursor()
    
    ets = EnhancedTechnicalScorer(cursor)
    
    test_stocks = ['000651.SZ', '000568.SZ', '600036.SH', '600519.SH']
    
    print("股票评分对比:")
    print("=" * 80)
    print(f"{'股票代码':<10} {'总分':<6} {'评级':<8} {'信号':<6} {'技术指标':<8} {'量价关系':<8} {'突破信号':<8} {'支撑阻力':<8}")
    print("-" * 80)
    
    for ts_code in test_stocks:
        try:
            result = ets.score_technical_enhanced(ts_code)
            print(f"{ts_code:<10} {result['total_score']:<6.1f} {result['rating']:<8} {result['signal']:<6} {result['technical_indicators_score']['total']:<8.1f} {result['volume_price_score']['total']:<8.1f} {result['breakout_score']['total']:<8.1f} {result['support_resistance_score']['total']:<8.1f}")
        except Exception as e:
            print(f"{ts_code:<10} 错误: {e}")
    
    print("=" * 80)
    
    conn.close()

def main():
    """主函数"""
    print("开始增强版技术面评分系统测试...")
    
    # 测试增强版技术面评分系统
    test_enhanced_technical_scorer()
    
    # 测试批量评分功能
    test_batch_scoring()
    
    # 测试获取评分最高的股票
    test_top_stocks()
    
    # 测试评分对比
    test_score_comparison()
    
    print("增强版技术面评分系统测试完成!")

if __name__ == "__main__":
    main()