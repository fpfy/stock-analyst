"""
test_technical_scorer.py - 技术面评分系统测试
"""
import sqlite3
import logging
from technical_scorer import TechnicalScorer

logger = logging.getLogger(__name__)

def test_technical_scorer():
    """测试技术面评分系统"""
    print("=== 技术面评分系统测试 ===")
    
    conn = sqlite3.connect('database/stock_analysis.db')
    cursor = conn.cursor()
    
    # 创建技术面评分器
    scorer = TechnicalScorer(cursor)
    
    # 测试股票列表
    test_stocks = ['000651.SZ', '000568.SZ', '600036.SH', '600519.SH']
    
    for ts_code in test_stocks:
        print(f"\n--- 测试股票: {ts_code} ---")
        
        try:
            # 计算技术面评分
            score_details = scorer.score_technical(ts_code)
            print(f"技术面评分详情: {score_details}")
            
            # 获取评级
            total_score = score_details.get('total', 0)
            grade = scorer.get_technical_grade(total_score)
            print(f"技术面评级: {grade} ({total_score}分)")
            
            # 获取评分理由
            reasons = scorer.get_technical_reasons(score_details)
            print(f"评分理由: {reasons}")
            
            # 分析技术面信号
            signal_analysis = scorer.analyze_technical_signals(ts_code)
            print(f"技术面信号: {signal_analysis}")
            
        except Exception as e:
            print(f"计算技术面评分失败: {e}")
    
    conn.close()

def main():
    """主函数"""
    print("开始技术面评分系统测试...")
    
    # 测试技术面评分系统
    test_technical_scorer()
    
    print("技术面评分系统测试完成!")

if __name__ == "__main__":
    main()