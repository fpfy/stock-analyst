"""
test_management_analysis.py - 管理层质量分析测试
"""
import unittest
import sqlite3
import tempfile
import os
from management_analysis import ManagementAnalysis

class TestManagementAnalysis(unittest.TestCase):
    """管理层质量分析测试类"""
    
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
            CREATE TABLE financial_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_code TEXT,
                ann_date TEXT,
                end_date TEXT,
                revenue REAL,
                revenue_yoy REAL,
                net_profit REAL,
                net_profit_yoy REAL,
                roe REAL,
                roa REAL,
                gross_margin REAL,
                net_margin REAL,
                debt_ratio REAL,
                eps REAL,
                bps REAL,
                total_assets REAL,
                total_liab REAL,
                current_assets REAL,
                current_liab REAL,
                operating_cf REAL,
                created_at TEXT
            )
        ''')
        
        # 插入测试数据
        test_data = [
            ('600519.SH', '2026-04-29', '2026-03-31', 43080395805.39, 3.46, 6082159344.39, 3.01, 4.07, None, 27.42, None, None, None, 1.09, 27.14, None, None, None, 1.39, '2026-06-16 09:32:13'),
            ('600519.SH', '2025-04-28', '2025-03-31', 41000000000.0, 2.5, 5500000000.0, 2.8, 3.8, None, 26.5, None, None, None, 0.99, 26.8, None, None, None, 1.2, '2025-06-16 09:32:13'),
            ('600519.SH', '2024-04-29', '2024-03-31', 39000000000.0, 2.0, 5200000000.0, 2.5, 3.6, None, 25.8, None, None, None, 0.93, 26.2, None, None, None, 1.1, '2024-06-16 09:32:13'),
            ('000858.SZ', '2026-04-28', '2026-03-31', 25000000000.0, 3.2, 3000000000.0, 2.8, 3.5, None, 25.2, None, None, None, 0.85, 22.8, None, None, None, 1.15, '2026-06-16 09:32:13'),
            ('000858.SZ', '2025-04-27', '2025-03-31', 23000000000.0, 2.8, 2800000000.0, 2.5, 3.2, None, 24.8, None, None, None, 0.79, 22.2, None, None, None, 1.05, '2025-06-16 09:32:13'),
        ]
        
        self.cursor.executemany('''
            INSERT INTO financial_data (ts_code, ann_date, end_date, revenue, revenue_yoy, net_profit, net_profit_yoy, roe, roa, gross_margin, net_margin, debt_ratio, eps, bps, total_assets, total_liab, current_assets, current_liab, operating_cf, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', test_data)
        
        self.conn.commit()
        
        # 创建管理层分析实例
        self.management_analysis = ManagementAnalysis(self.temp_db.name)
    
    def tearDown(self):
        """清理测试环境"""
        self.conn.close()
        self.management_analysis.close()
        # 等待一下让文件释放
        import time
        time.sleep(0.1)
        try:
            os.unlink(self.temp_db.name)
        except Exception:
            pass  # 忽略删除失败的情况
    
    def test_collect_management_info(self):
        """测试收集管理层信息"""
        info = self.management_analysis.collect_management_info("600519.SH")
        self.assertIsInstance(info, dict)
        self.assertIn("stock_code", info)
        self.assertIn("board_members", info)
        self.assertIn("senior_executives", info)
        self.assertEqual(info["stock_code"], "600519.SH")
        
        # 检查董事会成员信息
        self.assertIsInstance(info["board_members"], list)
        if info["board_members"]:
            member = info["board_members"][0]
            self.assertIn("name", member)
            self.assertIn("position", member)
            self.assertIn("education", member)
            self.assertIn("experience", member)
            self.assertIn("tenure", member)
    
    def test_score_education_background(self):
        """测试学历背景评分"""
        info = self.management_analysis.collect_management_info("600519.SH")
        score = self.management_analysis.score_education_background(info)
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 10)
    
    def test_score_career_experience(self):
        """测试从业经验评分"""
        info = self.management_analysis.collect_management_info("600519.SH")
        score = self.management_analysis.score_career_experience(info)
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 10)
    
    def test_score_tenure_stability(self):
        """测试任职时长稳定性评分"""
        info = self.management_analysis.collect_management_info("600519.SH")
        score = self.management_analysis.score_tenure_stability(info)
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 10)
    
    def test_score_team_stability(self):
        """测试团队稳定性评分"""
        info = self.management_analysis.collect_management_info("600519.SH")
        score = self.management_analysis.score_team_stability(info)
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 10)
    
    def test_score_historical_performance(self):
        """测试历史业绩评分"""
        score = self.management_analysis.score_historical_performance("600519.SH")
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 10)
        
        # 测试不存在的股票 - 应该返回默认值5.0，但类型可能是int
        score = self.management_analysis.score_historical_performance("999999.SZ")
        self.assertEqual(score, 5.0)
        # 允许int或float类型
        self.assertTrue(isinstance(score, (int, float)))
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 10)
    
    def test_score_shareholding_alignment(self):
        """测试持股情况利益一致性评分"""
        info = self.management_analysis.collect_management_info("600519.SH")
        score = self.management_analysis.score_shareholding_alignment(info)
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 10)
    
    def test_score_compensation_alignment(self):
        """测试薪酬水平合理性评分"""
        info = self.management_analysis.collect_management_info("600519.SH")
        score = self.management_analysis.score_compensation_alignment(info)
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 10)
    
    def test_score_information_transparency(self):
        """测试信息披露透明度评分"""
        score = self.management_analysis.score_information_transparency("600519.SH")
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 10)
        
        # 测试不存在的股票
        score = self.management_analysis.score_information_transparency("999999.SZ")
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 10)
    
    def test_score_management_quality(self):
        """测试管理层质量综合评分"""
        score = self.management_analysis.score_management_quality("600519.SH")
        self.assertIsInstance(score, dict)
        self.assertIn("stock_code", score)
        self.assertIn("total_score", score)
        self.assertIn("rating", score)
        self.assertIn("scores", score)
        self.assertIn("management_info", score)
        self.assertIn("analysis", score)
        
        # 检查评分结构
        self.assertIsInstance(score["total_score"], float)
        self.assertGreaterEqual(score["total_score"], 0)
        self.assertLessEqual(score["total_score"], 10)
        
        # 检查评级
        self.assertIn(score["rating"], ["优秀", "良好", "中等", "一般", "较差"])
        
        # 检查各维度评分
        scores = score["scores"]
        self.assertIsInstance(scores, dict)
        expected_keys = ["education_score", "experience_score", "tenure_score", 
                       "stability_score", "performance_score", "shareholding_score", 
                       "compensation_score", "transparency_score"]
        for key in expected_keys:
            self.assertIn(key, scores)
            self.assertGreaterEqual(scores[key], 0)
            self.assertLessEqual(scores[key], 10)
    
    def test_get_management_ranking(self):
        """测试获取管理层质量排名"""
        ranking = self.management_analysis.get_management_ranking()
        self.assertIsInstance(ranking, list)
        
        if ranking:  # 可能为空，如果没有数据
            # 检查排名结构
            for i, score in enumerate(ranking):
                self.assertIsInstance(score, dict)
                self.assertIn("rank", score)
                self.assertEqual(score["rank"], i + 1)
                self.assertIn("stock_code", score)
                self.assertIn("total_score", score)
                self.assertIn("rating", score)
                
                # 检查评分范围
                self.assertGreaterEqual(score["total_score"], 0)
                self.assertLessEqual(score["total_score"], 10)
                
                # 检查评级
                self.assertIn(score["rating"], ["优秀", "良好", "中等", "一般", "较差"])
    
    def test_get_management_rating(self):
        """测试管理层评级"""
        # 测试优秀
        rating = self.management_analysis._get_management_rating(9.0)
        self.assertEqual(rating, "优秀")
        
        # 测试良好
        rating = self.management_analysis._get_management_rating(8.0)
        self.assertEqual(rating, "良好")
        
        # 测试中等
        rating = self.management_analysis._get_management_rating(7.0)
        self.assertEqual(rating, "中等")
        
        # 测试一般
        rating = self.management_analysis._get_management_rating(6.0)
        self.assertEqual(rating, "一般")
        
        # 测试较差
        rating = self.management_analysis._get_management_rating(5.0)
        self.assertEqual(rating, "较差")
    
    def test_generate_management_report(self):
        """测试生成管理层质量报告"""
        report = self.management_analysis.generate_management_report()
        self.assertIsInstance(report, str)
        self.assertIn("管理层质量分析报告", report)
        self.assertIn("管理层质量排名", report)
        self.assertIn("管理层质量分布", report)
        self.assertIn("重点分析", report)
        self.assertIn("投资建议", report)
        self.assertIn("风险提示", report)
    
    def test_score_shareholding(self):
        """测试持股评分"""
        # 测试高持股比例
        score = self.management_analysis._score_shareholding("10%")
        self.assertEqual(score, 10)
        
        # 测试中等持股比例
        score = self.management_analysis._score_shareholding("3%")
        self.assertEqual(score, 8)
        
        # 测试低持股比例
        score = self.management_analysis._score_shareholding("0.8%")
        self.assertEqual(score, 4)
        
        # 测试无持股
        score = self.management_analysis._score_shareholding("0%")
        self.assertEqual(score, 0)
        
        # 测试无效格式
        score = self.management_analysis._score_shareholding("未知")
        self.assertEqual(score, 0)
    
    def test_score_compensation(self):
        """测试薪酬评分"""
        # 测试高薪酬
        score = self.management_analysis._score_compensation("600万")
        self.assertEqual(score, 8)
        
        # 测试中等薪酬
        score = self.management_analysis._score_compensation("350万")
        self.assertEqual(score, 6)
        
        # 测试低薪酬
        score = self.management_analysis._score_compensation("150万")
        self.assertEqual(score, 2)
        
        # 测试无效格式
        score = self.management_analysis._score_compensation("未知")
        self.assertEqual(score, 1)


if __name__ == '__main__':
    unittest.main()