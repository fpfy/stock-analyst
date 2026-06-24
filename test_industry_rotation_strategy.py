"""
test_industry_rotation_strategy.py - 行业轮动策略测试
"""
import unittest
import sqlite3
import tempfile
import os
from industry_rotation_strategy import IndustryRotationStrategy

class TestIndustryRotationStrategy(unittest.TestCase):
    """行业轮动策略测试类"""
    
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
            # 白酒行业股票
            ('600519.SH', '2026-06-17', 1800, 1820, 1790, 1810, 1000000, 1810000000),
            ('600519.SH', '2026-06-16', 1790, 1810, 1780, 1800, 1100000, 1980000000),
            ('000858.SZ', '2026-06-17', 250, 255, 248, 252, 800000, 201600000),
            ('000858.SZ', '2026-06-16', 248, 252, 245, 250, 900000, 225000000),
            ('000568.SZ', '2026-06-17', 120, 122, 118, 121, 1200000, 145200000),
            ('000568.SZ', '2026-06-16', 118, 121, 116, 120, 1300000, 156000000),
            ('000596.SZ', '2026-06-17', 35, 36, 34, 35.5, 500000, 17750000),
            ('000596.SZ', '2026-06-16', 34, 35, 33, 34.5, 600000, 20700000),
            
            # 银行行业股票
            ('601398.SH', '2026-06-17', 5.2, 5.3, 5.1, 5.25, 2000000, 10500000),
            ('601398.SH', '2026-06-16', 5.1, 5.2, 5.0, 5.15, 2100000, 10815000),
            ('601939.SH', '2026-06-17', 4.8, 4.9, 4.7, 4.85, 1800000, 8730000),
            ('601939.SH', '2026-06-16', 4.7, 4.8, 4.6, 4.75, 1900000, 9025000),
            
            # 科技行业股票
            ('002415.SZ', '2026-06-17', 45, 46, 44, 45.5, 1500000, 68250000),
            ('002415.SZ', '2026-06-16', 44, 45, 43, 44.5, 1600000, 71200000),
            ('600536.SH', '2026-06-17', 38, 39, 37, 38.5, 1200000, 46200000),
            ('600536.SH', '2026-06-16', 37, 38, 36, 37.5, 1300000, 48750000),
        ]
        
        self.cursor.executemany('''
            INSERT INTO daily_quotes (ts_code, trade_date, open, high, low, close, volume, amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', test_data)
        
        self.conn.commit()
        
        # 创建行业轮动策略实例
        self.rotation_strategy = IndustryRotationStrategy(self.temp_db.name)
    
    def tearDown(self):
        """清理测试环境"""
        self.conn.close()
        self.rotation_strategy.close()
        # 等待一下让文件释放
        import time
        time.sleep(0.1)
        try:
            os.unlink(self.temp_db.name)
        except Exception:
            pass  # 忽略删除失败的情况
    
    def test_calculate_industry_momentum(self):
        """测试计算行业动量"""
        # 测试白酒行业
        momentum = self.rotation_strategy.calculate_industry_momentum('白酒')
        self.assertNotIn('error', momentum)
        self.assertEqual(momentum['industry_name'], '白酒')
        self.assertIn('avg_momentum', momentum)
        self.assertIn('momentum_std', momentum)
        self.assertIn('momentum_score', momentum)
        
        # 测试银行行业
        momentum = self.rotation_strategy.calculate_industry_momentum('银行')
        self.assertNotIn('error', momentum)
        self.assertEqual(momentum['industry_name'], '银行')
        
        # 测试不存在的行业
        momentum = self.rotation_strategy.calculate_industry_momentum('不存在的行业')
        self.assertIn('error', momentum)
    
    def test_get_industry_momentum_ranking(self):
        """测试获取行业动量排名"""
        ranking = self.rotation_strategy.get_industry_momentum_ranking()
        self.assertIsInstance(ranking, list)
        self.assertGreater(len(ranking), 0)
        
        # 检查排名是否正确
        for i in range(len(ranking) - 1):
            self.assertGreaterEqual(ranking[i]['momentum_score'], ranking[i + 1]['momentum_score'])
        
        # 检查每个行业都有排名
        for industry in ranking:
            self.assertIn('rank', industry)
            self.assertGreaterEqual(industry['rank'], 1)
    
    def test_generate_rotation_signals(self):
        """测试生成轮动信号"""
        signals = self.rotation_strategy.generate_rotation_signals()
        self.assertIn('momentum_ranking', signals)
        self.assertIn('industry_ranking', signals)
        self.assertIn('combined_signals', signals)
        self.assertIn('rotation_timing', signals)
        self.assertIn('market_regime', signals)
        
        # 检查信号完整性
        self.assertIsInstance(signals['momentum_ranking'], list)
        self.assertIsInstance(signals['industry_ranking'], list)
        self.assertIsInstance(signals['combined_signals'], list)
        self.assertIn(signals['rotation_timing'], ['strong_rotation', 'moderate_rotation', 'stable_rotation', 'weak_rotation'])
        self.assertIn(signals['market_regime'], ['bull_market', 'bear_market', 'sideways_market'])
    
    def test_combine_signals(self):
        """测试信号合并"""
        momentum_ranking = self.rotation_strategy.get_industry_momentum_ranking()
        industry_ranking = self.rotation_strategy.industry_analysis.get_industry_ranking()
        
        combined_signals = self.rotation_strategy._combine_signals(momentum_ranking, industry_ranking)
        
        self.assertIsInstance(combined_signals, list)
        self.assertGreater(len(combined_signals), 0)
        
        # 检查合并信号的结构
        for signal in combined_signals:
            self.assertIn('industry_name', signal)
            self.assertIn('industry_score', signal)
            self.assertIn('momentum_score', signal)
            self.assertIn('combined_score', signal)
            self.assertIn('score_rank', signal)
        
        # 检查排名是否正确
        for i in range(len(combined_signals) - 1):
            self.assertGreaterEqual(combined_signals[i]['combined_score'], combined_signals[i + 1]['combined_score'])
    
    def test_detect_rotation_timing(self):
        """测试轮动时机检测"""
        momentum_ranking = self.rotation_strategy.get_industry_momentum_ranking()
        timing = self.rotation_strategy._detect_rotation_timing(momentum_ranking)
        
        self.assertIn(timing, ['strong_rotation', 'moderate_rotation', 'stable_rotation', 'weak_rotation'])
    
    def test_detect_market_regime(self):
        """测试市场状态检测"""
        momentum_ranking = self.rotation_strategy.get_industry_momentum_ranking()
        regime = self.rotation_strategy._detect_market_regime(momentum_ranking)
        
        self.assertIn(regime, ['bull_market', 'bear_market', 'sideways_market'])
    
    def test_generate_portfolio_allocation(self):
        """测试生成配置建议"""
        allocation = self.rotation_strategy.generate_portfolio_allocation()
        
        self.assertIn('allocation', allocation)
        self.assertIn('top_industries', allocation)
        self.assertIn('rotation_timing', allocation)
        self.assertIn('market_regime', allocation)
        self.assertIn('rebalance_date', allocation)
        self.assertIn('expected_return', allocation)
        self.assertIn('risk_level', allocation)
        
        # 检查配置权重
        self.assertIsInstance(allocation['allocation'], dict)
        self.assertAlmostEqual(sum(allocation['allocation'].values()), 1.0, places=5)
        
        # 检查风险水平
        self.assertIn(allocation['risk_level'], ['high', 'medium', 'low'])
    
    def test_calculate_expected_return(self):
        """测试预期收益率计算"""
        top_industries = [
            {'industry_score': 80, 'momentum_score': 0.1},
            {'industry_score': 70, 'momentum_score': 0.05},
            {'industry_score': 60, 'momentum_score': 0.02}
        ]
        
        expected_return = self.rotation_strategy._calculate_expected_return(top_industries)
        self.assertIsInstance(expected_return, float)
        self.assertGreaterEqual(expected_return, 0)
    
    def test_calculate_risk_level(self):
        """测试风险水平计算"""
        # 测试高风险
        high_risk_industries = [
            {'industry_score': 90, 'momentum_score': 0.2},
            {'industry_score': 50, 'momentum_score': -0.1}
        ]
        risk_level = self.rotation_strategy._calculate_risk_level(high_risk_industries)
        self.assertEqual(risk_level, 'high')
        
        # 测试中等风险
        medium_risk_industries = [
            {'industry_score': 80, 'momentum_score': 0.1},
            {'industry_score': 70, 'momentum_score': 0.05}
        ]
        risk_level = self.rotation_strategy._calculate_risk_level(medium_risk_industries)
        self.assertEqual(risk_level, 'medium')
        
        # 测试低风险
        low_risk_industries = [
            {'industry_score': 75, 'momentum_score': 0.08},
            {'industry_score': 73, 'momentum_score': 0.07}
        ]
        risk_level = self.rotation_strategy._calculate_risk_level(low_risk_industries)
        self.assertEqual(risk_level, 'low')
    
    def test_generate_rotation_report(self):
        """测试生成轮动策略报告"""
        report = self.rotation_strategy.generate_rotation_report()
        
        self.assertIsInstance(report, str)
        self.assertIn('行业轮动策略报告', report)
        self.assertIn('市场状态分析', report)
        self.assertIn('行业动量排名', report)
        self.assertIn('行业评分排名', report)
        self.assertIn('综合信号排名', report)
        self.assertIn('行业配置建议', report)
        self.assertIn('投资建议', report)


if __name__ == '__main__':
    unittest.main()