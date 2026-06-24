"""
test_industry_analysis.py - 行业分析模块测试
"""
import unittest
import sqlite3
import tempfile
import os
from industry_analysis import IndustryAnalysis

class TestIndustryAnalysis(unittest.TestCase):
    """行业分析模块测试类"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建临时数据库
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # 创建测试数据库
        self.conn = sqlite3.connect(self.temp_db.name)
        self.cursor = self.conn.cursor()
        
        # 创建测试表
        self.cursor.execute('''
            CREATE TABLE daily_quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_code TEXT,
                trade_date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL
            )
        ''')
        
        # 插入测试数据
        test_data = [
            ('600519.SH', '2026-06-17', 1800, 1820, 1790, 1810, 1000000, 1810000000),
            ('600519.SH', '2026-06-16', 1790, 1810, 1780, 1800, 1100000, 1980000000),
            ('000858.SZ', '2026-06-17', 250, 255, 248, 252, 800000, 201600000),
            ('000858.SZ', '2026-06-16', 248, 252, 245, 250, 900000, 225000000),
            ('000568.SZ', '2026-06-17', 120, 122, 118, 121, 1200000, 145200000),
            ('000568.SZ', '2026-06-16', 118, 121, 116, 120, 1300000, 156000000),
            ('000596.SZ', '2026-06-17', 35, 36, 34, 35.5, 500000, 17750000),
            ('000596.SZ', '2026-06-16', 34, 35, 33, 34.5, 600000, 20700000),
        ]
        
        self.cursor.executemany('''
            INSERT INTO daily_quotes (ts_code, trade_date, open, high, low, close, volume, amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', test_data)
        
        self.conn.commit()
        
        # 创建行业分析实例
        self.industry_analysis = IndustryAnalysis(self.temp_db.name)
    
    def tearDown(self):
        """清理测试环境"""
        self.conn.close()
        self.industry_analysis.close()
        # 等待一下让文件释放
        import time
        time.sleep(0.1)
        try:
            os.unlink(self.temp_db.name)
        except Exception:
            pass  # 忽略删除失败的情况
    
    def test_get_industry_stocks(self):
        """测试获取行业股票列表"""
        stocks = self.industry_analysis.get_industry_stocks('白酒')
        self.assertIn('600519.SH', stocks)
        self.assertIn('000858.SZ', stocks)
        self.assertIn('000568.SZ', stocks)
        
        # 测试不存在的行业
        stocks = self.industry_analysis.get_industry_stocks('不存在的行业')
        self.assertEqual(stocks, [])
    
    def test_calculate_industry_strength(self):
        """测试计算行业强度"""
        # 测试白酒行业
        strength = self.industry_analysis.calculate_industry_strength('白酒')
        self.assertNotIn('error', strength)
        self.assertEqual(strength['industry_name'], '白酒')
        self.assertEqual(strength['stock_count'], 4)
        self.assertIn(strength['strength_level'], ['强势', '偏强', '平稳', '偏弱', '弱势'])
        
        # 测试不存在的行业
        strength = self.industry_analysis.calculate_industry_strength('不存在的行业')
        self.assertIn('error', strength)
    
    def test_score_industry(self):
        """测试行业评分"""
        score = self.industry_analysis.score_industry('白酒')
        self.assertNotIn('error', score)
        self.assertEqual(score['industry_name'], '白酒')
        self.assertIn('total_score', score)
        self.assertIn('fundamental_score', score)
        self.assertIn('technical_score', score)
        self.assertIn('valuation_score', score)
        self.assertIn('policy_score', score)
        self.assertIn('recommendation', score)
        self.assertIn(score['recommendation'], ['强烈推荐', '推荐', '中性', '谨慎', '回避'])
    
    def test_get_industry_ranking(self):
        """测试行业排名"""
        ranking = self.industry_analysis.get_industry_ranking()
        self.assertIsInstance(ranking, list)
        self.assertGreater(len(ranking), 0)
        
        # 检查排名是否正确
        for i in range(len(ranking) - 1):
            self.assertGreaterEqual(ranking[i]['total_score'], ranking[i + 1]['total_score'])
        
        # 检查每个行业都有排名
        for industry in ranking:
            self.assertIn('rank', industry)
            self.assertGreaterEqual(industry['rank'], 1)
    
    def test_calculate_industry_rotation(self):
        """测试行业轮动信号"""
        rotation = self.industry_analysis.calculate_industry_rotation()
        self.assertIn('rotation_signals', rotation)
        self.assertIn('top_industries', rotation)
        self.assertIn('bottom_industries', rotation)
        self.assertIn('market_cycle', rotation)
        
        # 检查市场周期（包括unknown情况）
        self.assertIn(rotation['market_cycle'], ['bull_market', 'bear_market', 'sideways_market', 'unknown'])
    
    def test_generate_industry_report(self):
        """测试生成行业报告"""
        report = self.industry_analysis.generate_industry_report()
        self.assertIsInstance(report, str)
        self.assertIn('行业分析报告', report)
        self.assertIn('行业排名', report)
        self.assertIn('行业轮动信号', report)
        self.assertIn('投资建议', report)
    
    def test_industry_recommendation_levels(self):
        """测试行业推荐等级"""
        # 测试高分行业
        high_score = {'total_score': 85}
        recommendation = self.industry_analysis._get_industry_recommendation(high_score['total_score'])
        self.assertEqual(recommendation, '强烈推荐')
        
        # 测试中等分行业
        mid_score = {'total_score': 65}
        recommendation = self.industry_analysis._get_industry_recommendation(mid_score['total_score'])
        self.assertEqual(recommendation, '中性')
        
        # 测试低分行业
        low_score = {'total_score': 45}
        recommendation = self.industry_analysis._get_industry_recommendation(low_score['total_score'])
        self.assertEqual(recommendation, '回避')
    
    def test_strength_levels(self):
        """测试强度等级"""
        # 测试强势
        strength = self.industry_analysis._get_strength_level(0.06)
        self.assertEqual(strength, '强势')
        
        # 测试偏强
        strength = self.industry_analysis._get_strength_level(0.03)
        self.assertEqual(strength, '偏强')
        
        # 测试平稳
        strength = self.industry_analysis._get_strength_level(0.01)
        self.assertEqual(strength, '平稳')
        
        # 测试平稳
        strength = self.industry_analysis._get_strength_level(-0.01)
        self.assertEqual(strength, '平稳')
        
        # 测试弱势
        strength = self.industry_analysis._get_strength_level(-0.06)
        self.assertEqual(strength, '弱势')


if __name__ == '__main__':
    unittest.main()