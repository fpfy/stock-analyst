"""
test_backtest_engine.py - 回测引擎测试
验证回测引擎的核心功能
"""

import unittest
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backtest_engine import BacktestEngine, SignalType, PositionStatus
import pandas as pd

class TestBacktestEngine(unittest.TestCase):
    """回测引擎测试类"""
    
    def setUp(self):
        """测试初始化"""
        self.engine = BacktestEngine()
        self.engine.set_backtest_params("2026-03-09", "2026-03-13", 1000000)
        
        # 添加测试策略
        def test_strategy(ts_code, trade_date):
            return {'signal': 'buy', 'strength': 'strong', 'score': 80, 'strategy_type': 'growth'}
        
        self.engine.add_strategy("test_strategy", test_strategy)
    
    def test_backtest_engine_initialization(self):
        """测试回测引擎初始化"""
        self.assertIsNotNone(self.engine)
        self.assertEqual(self.engine.start_date, "2026-03-09")
        self.assertEqual(self.engine.end_date, "2026-03-13")
        self.assertEqual(self.engine.initial_capital, 1000000)
        self.assertEqual(len(self.engine.strategies), 1)
    
    def test_get_trading_dates(self):
        """测试获取交易日期"""
        dates = self.engine.get_trading_dates()
        self.assertIsInstance(dates, list)
        self.assertGreater(len(dates), 0)
        
        # 检查日期格式
        for date in dates:
            self.assertEqual(len(date), 10)  # YYYY-MM-DD格式
    
    def test_get_daily_data(self):
        """测试获取日线数据"""
        daily_data = self.engine.get_daily_data("000651.SZ", "2026-06-01", "2026-06-18")
        self.assertIsInstance(daily_data, pd.DataFrame)
        
        if not daily_data.empty:
            expected_columns = ['trade_date', 'open', 'high', 'low', 'close', 'volume', 'amount']
            self.assertEqual(list(daily_data.columns), expected_columns)
    
    def test_portfolio_creation(self):
        """测试投资组合创建"""
        self.assertEqual(len(self.engine.portfolios), 0)
        
        # 运行回测
        results = self.engine.run_backtest(["test_strategy"])
        self.assertEqual(len(self.engine.portfolios), 1)
        
        # 检查投资组合
        portfolio = list(self.engine.portfolios.values())[0]
        self.assertEqual(portfolio.total_capital, 1000000)
        self.assertEqual(portfolio.available_cash, 1000000)
        self.assertEqual(len(portfolio.positions), 0)
        self.assertEqual(len(portfolio.trades), 0)
    
    def test_signal_generation(self):
        """测试信号生成"""
        signal = self.engine.get_technical_signals("000651.SZ", "2026-06-18", "growth")
        self.assertIsInstance(signal, dict)
        self.assertIn('signal', signal)
        self.assertIn('strength', signal)
        self.assertIn('score', signal)
    
    def test_performance_metrics_calculation(self):
        """测试性能指标计算"""
        # 创建模拟的投资组合
        from backtest_engine import Portfolio, Position, PositionStatus
        
        portfolio = Portfolio(
            portfolio_id="test",
            total_capital=1000000,
            available_cash=950000,
            positions={},
            trades=[],
            total_value=1000000
        )
        
        # 添加一个持仓
        position = Position(
            ts_code="000651.SZ",
            quantity=1000,
            avg_price=10.0,
            current_price=12.0,
            market_value=12000,
            unrealized_pnl=2000,
            position_status=PositionStatus.LONG
        )
        portfolio.positions["000651.SZ"] = position
        
        # 将投资组合添加到引擎中
        self.engine.portfolios["test"] = portfolio
        
        # 更新总价值
        portfolio.update_total_value()
        
        # 计算性能指标
        results = self.engine.calculate_performance_metrics()
        self.assertIsInstance(results, dict)
        self.assertGreater(len(results), 0)
        
        # 检查指标
        for strategy_name, metrics in results.items():
            self.assertIn('total_return', metrics)
            self.assertIn('annual_return', metrics)
            self.assertIn('win_rate', metrics)
            self.assertIn('total_trades', metrics)
            self.assertIn('max_drawdown', metrics)
    
    def test_report_generation(self):
        """测试报告生成"""
        # 创建模拟结果
        results = {
            "test_strategy": {
                'total_return': 0.15,
                'annual_return': 0.20,
                'win_rate': 0.60,
                'total_trades': 10,
                'max_drawdown': 0.05,
                'final_value': 1150000,
                'total_trades_count': 15,
                'positions_count': 3
            }
        }
        
        report = self.engine.generate_report(results)
        self.assertIsInstance(report, str)
        self.assertIn("回测报告", report)
        self.assertIn("test_strategy", report)
        self.assertIn("15.00%", report)
    
    def test_results_saving(self):
        """测试结果保存"""
        # 创建模拟结果
        results = {
            "test_strategy": {
                'total_return': 0.15,
                'annual_return': 0.20,
                'win_rate': 0.60,
                'total_trades': 10,
                'max_drawdown': 0.05,
                'final_value': 1150000,
                'total_trades_count': 15,
                'positions_count': 3
            }
        }
        
        # 测试保存功能
        filename = self.engine.save_results(results, "test_backtest_report.md")
        self.assertTrue(os.path.exists(filename))
        
        # 清理测试文件
        if os.path.exists(filename):
            os.remove(filename)
    
    def test_multiple_strategies(self):
        """测试多策略回测"""
        # 添加第二个策略
        def test_strategy2(ts_code, trade_date):
            return {'signal': 'sell', 'strength': 'weak', 'score': 30, 'strategy_type': 'value'}
        
        self.engine.add_strategy("test_strategy2", test_strategy2)
        
        # 运行多策略回测
        results = self.engine.run_backtest(["test_strategy", "test_strategy2"])
        
        self.assertEqual(len(results), 2)
        self.assertIn("test_strategy", results)
        self.assertIn("test_strategy2", results)
    
    def test_error_handling(self):
        """测试错误处理"""
        # 测试无效的股票代码
        signal = self.engine.get_technical_signals("INVALID.CODE", "2026-06-18", "growth")
        self.assertIsInstance(signal, dict)
        
        # 测试无效的日期
        daily_data = self.engine.get_daily_data("000651.SZ", "2020-01-01", "2020-01-01")
        self.assertIsInstance(daily_data, pd.DataFrame)
    
    def tearDown(self):
        """测试清理"""
        # 关闭数据库连接
        if hasattr(self.engine, 'conn'):
            self.engine.conn.close()

if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)