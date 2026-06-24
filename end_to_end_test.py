"""
end_to_end_test.py - 系统端到端测试
验证完整的三步流程：宏观分析 → 双策略选股 → 观察池跟踪 → 综合交易策略
"""

import logging
import time
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any
import sys
import os

# 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api_frequency_control import APILimiter, APIMonitor
from integrated_stock_analysis_system import IntegratedStockAnalysisSystem
from macro_market_analyzer import MacroMarketAnalyzer
from dual_strategy_selector import DualStrategySelector
from observation_pool_tracker import ObservationPoolTracker
from comprehensive_trading_strategy import ComprehensiveTradingStrategy

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EndToEndTester:
    """端到端测试类"""
    
    def __init__(self, db_path: str = "database/stock_analysis.db"):
        self.db_path = db_path
        self.api_limiter = APILimiter(max_calls_per_minute=30, max_calls_per_hour=200)
        self.api_monitor = APIMonitor()
        self.test_results = []
        
        # 初始化系统组件
        try:
            self.system = IntegratedStockAnalysisSystem(db_path)
            self.macro_analyzer = MacroMarketAnalyzer(db_path)
            self.strategy_selector = DualStrategySelector(db_path)
            self.observation_tracker = ObservationPoolTracker(db_path)
            self.trading_strategy = ComprehensiveTradingStrategy(db_path)
            logger.info("✅ 所有系统组件初始化成功")
        except Exception as e:
            logger.error(f"❌ 系统组件初始化失败: {e}")
            raise
    
    def test_database_connection(self) -> bool:
        """测试数据库连接"""
        logger.info("测试1: 数据库连接")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查关键表是否存在
            required_tables = ['stock_basic', 'financial_data', 'valuation_data', 'index_data']
            for table in required_tables:
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
                if not cursor.fetchone():
                    logger.error(f"❌ 缺少必要表: {table}")
                    return False
            
            # 检查数据量
            cursor.execute("SELECT COUNT(*) FROM stock_basic")
            stock_count = cursor.fetchone()[0]
            logger.info(f"📊 数据库中有 {stock_count} 只股票")
            
            conn.close()
            logger.info("✅ 数据库连接测试通过")
            return True
            
        except Exception as e:
            logger.error(f"❌ 数据库连接失败: {e}")
            return False
    
    def test_macro_analysis(self) -> bool:
        """测试宏观经济分析"""
        logger.info("测试2: 宏观经济分析")
        
        try:
            start_time = time.time()
            
            # 检查API限制
            if not self.api_limiter.check_limit():
                logger.warning("达到API限制，跳过宏观分析测试")
                return False
            
            # 执行宏观分析
            results = self.macro_analyzer.generate_analysis_report()
            
            duration = time.time() - start_time
            
            # 只有在实际API调用成功后才计数
            if results and 'error' not in results:
                self.api_limiter.increment()
                self.api_monitor.log_call("macro_analysis", True, duration)
            else:
                self.api_monitor.log_call("macro_analysis", False, duration)
            
            # 验证结果
            if not results or 'error' in results:
                logger.error(f"❌ 宏观分析失败: {results.get('error', '未知错误')}")
                return False
            
            # 检查关键字段
            required_fields = ['market_state', 'economic_cycle', 'market_sentiment']
            for field in required_fields:
                if field not in results:
                    logger.error(f"❌ 宏观分析缺少字段: {field}")
                    return False
            
            logger.info(f"✅ 宏观分析测试通过 (耗时: {duration:.2f}秒)")
            logger.info(f"   市场状态: {results['market_state']}")
            logger.info(f"   经济周期: {results['economic_cycle']}")
            logger.info(f"   市场情绪: {results['market_sentiment']}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 宏观分析异常: {e}")
            return False
    
    def test_strategy_selection(self) -> bool:
        """测试双策略选股"""
        logger.info("测试3: 双策略选股")
        
        try:
            start_time = time.time()
            
            # 检查API限制
            if not self.api_limiter.check_limit():
                logger.warning("达到API限制，跳过策略选股测试")
                return False
            
            # 执行双策略选股
            results = self.strategy_selector.run_dual_strategy_selection()
            
            duration = time.time() - start_time
            
            # 只有在实际API调用成功后才计数
            if results and 'error' not in results:
                self.api_limiter.increment()
                self.api_monitor.log_call("strategy_selection", True, duration)
            else:
                self.api_monitor.log_call("strategy_selection", False, duration)
            
            # 验证结果
            if not results or 'error' in results:
                logger.error(f"❌ 双策略选股失败: {results.get('error', '未知错误')}")
                return False
            
            # 检查关键字段
            required_fields = ['growth_stocks', 'value_stocks', 'position_allocation']
            for field in required_fields:
                if field not in results:
                    logger.error(f"❌ 双策略选股缺少字段: {field}")
                    return False
            
            # 检查选股数量
            growth_count = len(results['growth_stocks'])
            value_count = len(results['value_stocks'])
            
            if growth_count == 0 and value_count == 0:
                logger.error("❌ 双策略选股结果为空")
                return False
            
            logger.info(f"✅ 双策略选股测试通过 (耗时: {duration:.2f}秒)")
            logger.info(f"   成长股数量: {growth_count}")
            logger.info(f"   价值股数量: {value_count}")
            logger.info(f"   仓位配置: {results['position_allocation']}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 双策略选股异常: {e}")
            return False
    
    def test_observation_tracking(self) -> bool:
        """测试观察池跟踪"""
        logger.info("测试4: 观察池跟踪")
        
        try:
            start_time = time.time()
            
            # 检查API限制
            if not self.api_limiter.check_limit():
                logger.warning("达到API限制，跳过观察池测试")
                return False
            
            # 执行观察池跟踪
            results = self.observation_tracker.update_observation_pool()
            
            duration = time.time() - start_time
            
            # 只有在实际API调用成功后才计数
            if results and 'error' not in results:
                self.api_limiter.increment()
                self.api_monitor.log_call("observation_tracking", True, duration)
            else:
                self.api_monitor.log_call("observation_tracking", False, duration)
            
            # 验证结果
            if not results or 'error' in results:
                logger.error(f"❌ 观察池跟踪失败: {results.get('error', '未知错误')}")
                return False
            
            # 检查关键字段
            required_fields = ['observation_stocks', 'signals', 'analysis_summary']
            for field in required_fields:
                if field not in results:
                    logger.error(f"❌ 观察池跟踪缺少字段: {field}")
                    return False
            
            # 检查观察池数量
            observation_count = len(results['observation_stocks'])
            
            if observation_count == 0:
                logger.warning("⚠️ 观察池为空，可能数据不足")
            
            logger.info(f"✅ 观察池跟踪测试通过 (耗时: {duration:.2f}秒)")
            logger.info(f"   观察池数量: {observation_count}")
            logger.info(f"   信号数量: {len(results['signals'])}")
            logger.info(f"   分析摘要: {results['analysis_summary'][:100]}...")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 观察池跟踪异常: {e}")
            return False
    
    def test_trading_strategy(self) -> bool:
        """测试综合交易策略"""
        logger.info("测试5: 综合交易策略")
        
        try:
            start_time = time.time()
            
            # 检查API限制
            if not self.api_limiter.check_limit():
                logger.warning("达到API限制，跳过交易策略测试")
                return False
            
            # 执行综合交易策略
            results = self.trading_strategy.generate_comprehensive_strategy()
            
            duration = time.time() - start_time
            
            # 只有在实际API调用成功后才计数
            if results and 'error' not in results:
                self.api_limiter.increment()
                self.api_monitor.log_call("trading_strategy", True, duration)
            else:
                self.api_monitor.log_call("trading_strategy", False, duration)
            
            # 验证结果
            if not results or 'error' in results:
                logger.error(f"❌ 综合交易策略失败: {results.get('error', '未知错误')}")
                return False
            
            # 检查关键字段
            required_fields = ['trading_signals', 'risk_assessment', 'portfolio_recommendation']
            for field in required_fields:
                if field not in results:
                    logger.error(f"❌ 综合交易策略缺少字段: {field}")
                    return False
            
            # 检查交易信号
            signal_count = len(results['trading_signals'])
            
            logger.info(f"✅ 综合交易策略测试通过 (耗时: {duration:.2f}秒)")
            logger.info(f"   交易信号数量: {signal_count}")
            logger.info(f"   风险评估: {results['risk_assessment']}")
            logger.info(f"   投资建议: {results['portfolio_recommendation'][:100]}...")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 综合交易策略异常: {e}")
            return False
    
    def test_complete_workflow(self) -> bool:
        """测试完整工作流程"""
        logger.info("测试6: 完整工作流程")
        
        try:
            start_time = time.time()
            
            # 执行完整的三步流程
            workflow_results = {}
            
            # 步骤1: 宏观分析
            logger.info("步骤1: 宏观经济分析")
            workflow_results['macro'] = self.test_macro_analysis()
            
            # 步骤2: 双策略选股
            logger.info("步骤2: 双策略选股")
            workflow_results['strategy'] = self.test_strategy_selection()
            
            # 步骤3: 观察池跟踪
            logger.info("步骤3: 观察池跟踪")
            workflow_results['observation'] = self.test_observation_tracking()
            
            # 步骤4: 综合交易策略
            logger.info("步骤4: 综合交易策略")
            workflow_results['trading'] = self.test_trading_strategy()
            
            duration = time.time() - start_time
            
            # 统计结果
            successful_steps = sum(workflow_results.values())
            total_steps = len(workflow_results)
            
            logger.info(f"✅ 完整工作流程测试完成 (耗时: {duration:.2f}秒)")
            logger.info(f"   成功步骤: {successful_steps}/{total_steps}")
            
            # 记录详细结果
            for step, success in workflow_results.items():
                status = "✅ 通过" if success else "❌ 失败"
                logger.info(f"   {step}: {status}")
            
            return successful_steps == total_steps
            
        except Exception as e:
            logger.error(f"❌ 完整工作流程异常: {e}")
            return False
    
    def generate_test_report(self) -> Dict:
        """生成测试报告"""
        logger.info("生成测试报告")
        
        # 获取API统计信息
        api_stats = self.api_monitor.get_stats()
        
        test_report = {
            'test_timestamp': datetime.now().isoformat(),
            'total_tests': len(self.test_results),
            'successful_tests': sum(1 for r in self.test_results if r['success']),
            'failed_tests': sum(1 for r in self.test_results if not r['success']),
            'test_results': self.test_results,
            'api_statistics': api_stats,
            'system_health': self.system.get_system_health() if hasattr(self, 'system') else None
        }
        
        # 保存报告
        report_filename = f"end_to_end_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_filename, 'w', encoding='utf-8') as f:
            f.write(f"=== 端到端测试报告 ===\n")
            f.write(f"测试时间: {test_report['test_timestamp']}\n")
            f.write(f"总测试数: {test_report['total_tests']}\n")
            f.write(f"成功测试: {test_report['successful_tests']}\n")
            f.write(f"失败测试: {test_report['failed_tests']}\n")
            f.write(f"成功率: {test_report['successful_tests']/test_report['total_tests']*100:.1f}%\n")
            f.write("\n=== API统计 ===\n")
            f.write(f"总调用次数: {api_stats['total_calls']}\n")
            f.write(f"成功调用: {api_stats['successful_calls']}\n")
            f.write(f"失败调用: {api_stats['failed_calls']}\n")
            f.write(f"成功率: {api_stats['success_rate']*100:.1f}%\n")
            f.write(f"平均耗时: {api_stats['avg_duration']:.2f}秒\n")
        
        logger.info(f"测试报告已保存: {report_filename}")
        return test_report
    
    def run_all_tests(self) -> bool:
        """运行所有测试"""
        logger.info("🚀 开始端到端测试...")
        
        tests = [
            ("数据库连接", self.test_database_connection),
            ("宏观经济分析", self.test_macro_analysis),
            ("双策略选股", self.test_strategy_selection),
            ("观察池跟踪", self.test_observation_tracking),
            ("综合交易策略", self.test_trading_strategy),
            ("完整工作流程", self.test_complete_workflow)
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        for test_name, test_func in tests:
            try:
                logger.info(f"\n{'='*50}")
                logger.info(f"正在执行: {test_name}")
                logger.info(f"{'='*50}")
                
                success = test_func()
                self.test_results.append({
                    'test_name': test_name,
                    'success': success,
                    'timestamp': datetime.now().isoformat()
                })
                
                if success:
                    passed_tests += 1
                    logger.info(f"✅ {test_name} 通过")
                else:
                    logger.error(f"❌ {test_name} 失败")
                    
            except Exception as e:
                logger.error(f"❌ {test_name} 异常: {e}")
                self.test_results.append({
                    'test_name': test_name,
                    'success': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
        
        # 生成测试报告
        test_report = self.generate_test_report()
        
        # 输出总结
        logger.info(f"\n{'='*50}")
        logger.info("🎯 测试总结")
        logger.info(f"{'='*50}")
        logger.info(f"总测试数: {total_tests}")
        logger.info(f"通过测试: {passed_tests}")
        logger.info(f"失败测试: {total_tests - passed_tests}")
        logger.info(f"成功率: {passed_tests/total_tests*100:.1f}%")
        
        if passed_tests == total_tests:
            logger.info("🎉 所有测试通过！系统运行正常")
            return True
        else:
            logger.warning("⚠️ 部分测试失败，需要修复")
            return False

def main():
    """主函数"""
    logger.info("🚀 开始系统端到端测试...")
    
    try:
        # 创建测试器
        tester = EndToEndTester()
        
        # 运行所有测试
        success = tester.run_all_tests()
        
        if success:
            print("✅ 端到端测试全部通过！系统可以正常运行")
            return True
        else:
            print("❌ 端到端测试部分失败，需要修复")
            return False
            
    except Exception as e:
        logger.error(f"测试执行异常: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)