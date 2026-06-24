"""
integration_tests.py - 系统集成测试
验证各模块协同工作是否正常
"""

import logging
import sys
import os
import sqlite3
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from logging_config import setup_logging
from performance_optimizer import query_cache, api_cache, performance_monitor
from system_monitor import SystemMonitor
from visualization import VisualizationEngine
from alert_system import AlertSystem, console_notification
from config import DB_PATH
from datetime import datetime, timedelta

setup_logging()
logger = logging.getLogger(__name__)


class IntegrationTester:
    """集成测试器"""
    
    def __init__(self):
        self.test_results = []
        self.passed = 0
        self.failed = 0
    
    def log_result(self, test_name: str, passed: bool, message: str = ""):
        """记录测试结果"""
        status = "✅ PASS" if passed else "❌ FAIL"
        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "message": message
        })
        
        if passed:
            self.passed += 1
            logger.info(f"{status}: {test_name}")
        else:
            self.failed += 1
            logger.error(f"{status}: {test_name} - {message}")
    
    def test_database_connection(self) -> bool:
        """测试数据库连接"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM stock_basic")
            count = cursor.fetchone()[0]
            conn.close()
            
            self.log_result(
                "数据库连接测试",
                True,
                f"连接成功，stock_basic表有 {count} 条记录"
            )
            return True
        except Exception as e:
            self.log_result("数据库连接测试", False, str(e))
            return False
    
    def test_performance_modules(self) -> bool:
        """测试性能优化模块"""
        try:
            # 测试查询缓存（使用正确的装饰器方式）
            from performance_optimizer import cache_query
            
            @cache_query(ttl=60)
            def test_query(params):
                return f"result_{params}"
            
            result1 = test_query("test")
            result2 = test_query("test")
            
            if result1 != result2:
                self.log_result("性能模块-查询缓存", False, "缓存结果不一致")
                return False
            
            # 测试API缓存
            from performance_optimizer import cache_api
            
            @cache_api(ttl=60)
            def test_api(param):
                return f"api_{param}"
            
            result3 = test_api("test")
            result4 = test_api("test")
            
            if result3 != result4:
                self.log_result("性能模块-API缓存", False, "API缓存结果不一致")
                return False
            
            # 测试性能监控
            stats = performance_monitor.get_stats()
            if "total_functions" not in stats:
                self.log_result("性能模块-监控", False, "性能统计缺失")
                return False
            
            self.log_result("性能优化模块测试", True)
            return True
            
        except Exception as e:
            self.log_result("性能优化模块测试", False, str(e))
            return False
    
    def test_system_monitor(self) -> bool:
        """测试系统监控模块"""
        try:
            monitor = SystemMonitor()
            
            # 测试系统指标收集
            sys_metrics = monitor.collect_system_metrics()
            if not sys_metrics:
                self.log_result("系统监控-指标收集", False, "未收集到系统指标")
                return False
            
            # 测试数据库指标收集
            db_metrics = monitor.collect_database_metrics()
            if not db_metrics:
                self.log_result("系统监控-数据库指标", False, "未收集到数据库指标")
                return False
            
            # 测试健康检查
            health = monitor.check_health()
            if "status" not in health:
                self.log_result("系统监控-健康检查", False, "健康检查结果缺失status字段")
                return False
            
            # 测试报告生成
            report = monitor.generate_health_report()
            if not report or len(report) < 100:
                self.log_result("系统监控-报告生成", False, "健康报告过短")
                return False
            
            self.log_result("系统监控模块测试", True)
            return True
            
        except Exception as e:
            self.log_result("系统监控模块测试", False, str(e))
            return False
    
    def test_visualization(self) -> bool:
        """测试可视化模块"""
        try:
            viz = VisualizationEngine()
            
            # 测试性能图表
            chart1 = viz.create_performance_chart(
                {"labels": ["1", "2", "3"], "values": [10, 20, 15]},
                "测试图表"
            )
            if not chart1:
                self.log_result("可视化-性能图表", False, "图表生成失败")
                return False
            
            # 测试配置图表
            chart2 = viz.create_portfolio_allocation_chart(70, 30)
            if not chart2:
                self.log_result("可视化-配置图表", False, "配置图表生成失败")
                return False
            
            # 测试仪表板
            dashboard = viz.create_dashboard({
                "cpu_percent": 50,
                "memory_percent": 60,
                "disk_percent": 70,
                "db_size_mb": 200,
                "total_records": 1000000,
                "status": "healthy"
            })
            if not dashboard:
                self.log_result("可视化-仪表板", False, "仪表板生成失败")
                return False
            
            self.log_result("可视化模块测试", True)
            return True
            
        except Exception as e:
            self.log_result("可视化模块测试", False, str(e))
            return False
    
    def test_alert_system(self) -> bool:
        """测试预警系统"""
        try:
            alert_system = AlertSystem()
            
            # 测试预警检查
            test_data = {
                "ts_code": "000001.SZ",
                "stock_name": "测试股票",
                "price_change_pct": 6.5,
                "volume_ratio": 3.5
            }
            
            alerts = alert_system.check_alerts(test_data)
            if len(alerts) == 0:
                self.log_result("预警系统-检查", False, "未触发任何预警")
                return False
            
            # 测试统计
            stats = alert_system.get_stats()
            if "total_alerts" not in stats:
                self.log_result("预警系统-统计", False, "统计信息缺失")
                return False
            
            # 测试获取最近预警
            recent = alert_system.get_recent_alerts(hours=1)
            if not isinstance(recent, list):
                self.log_result("预警系统-查询", False, "最近预警查询失败")
                return False
            
            self.log_result("预警系统模块测试", True, f"触发 {len(alerts)} 个预警")
            return True
            
        except Exception as e:
            self.log_result("预警系统模块测试", False, str(e))
            return False
    
    def test_module_integration(self) -> bool:
        """测试模块集成"""
        try:
            # 导入增强版主系统
            from enhanced_main import EnhancedStockAnalysisSystem
            
            # 初始化系统
            system = EnhancedStockAnalysisSystem()
            
            # 测试系统状态获取
            status = system.get_system_status()
            if "health" not in status or "performance" not in status:
                self.log_result("模块集成-状态获取", False, "系统状态不完整")
                return False
            
            # 测试性能报告
            report = system.run_performance_report()
            if not report or "系统指标" not in report:
                self.log_result("模块集成-性能报告", False, "性能报告生成失败")
                return False
            
            # 关闭系统
            system.shutdown()
            
            self.log_result("模块集成测试", True)
            return True
            
        except Exception as e:
            self.log_result("模块集成测试", False, str(e))
            return False
    
    def run_all_tests(self):
        """运行所有测试"""
        logger.info("🚀 开始运行集成测试...")
        
        self.test_database_connection()
        self.test_performance_modules()
        self.test_system_monitor()
        self.test_visualization()
        self.test_alert_system()
        self.test_module_integration()
        
        # 输出测试摘要
        logger.info("\n" + "="*50)
        logger.info("📊 集成测试结果摘要")
        logger.info("="*50)
        logger.info(f"总计: {self.passed + self.failed} 个测试")
        logger.info(f"通过: {self.passed} 个")
        logger.info(f"失败: {self.failed} 个")
        logger.info(f"通过率: {self.passed/(self.passed + self.failed)*100:.1f}%")
        logger.info("="*50)
        
        return self.failed == 0


if __name__ == "__main__":
    tester = IntegrationTester()
    success = tester.run_all_tests()
    
    # 输出详细结果
    print("\n=== 详细测试结果 ===")
    for result in tester.test_results:
        status = "✅" if result["passed"] else "❌"
        print(f"{status} {result['test']}")
        if result["message"]:
            print(f"   {result['message']}")
    
    sys.exit(0 if success else 1)
