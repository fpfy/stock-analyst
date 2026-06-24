"""
enhanced_main.py - 增强版主入口
整合性能优化、监控、可视化和预警系统
"""

import logging
import sys
import os
from datetime import datetime

# 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from logging_config import setup_logging
from performance_optimizer import query_cache, api_cache, performance_monitor, get_performance_report
from system_monitor import SystemMonitor
from visualization import VisualizationEngine
from alert_system import AlertSystem, console_notification, log_notification
from typing import Dict

# 初始化日志
setup_logging()
logger = logging.getLogger(__name__)


class EnhancedStockAnalysisSystem:
    """增强版股票分析系统"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.monitor = SystemMonitor()
        self.viz = VisualizationEngine()
        self.alert_system = AlertSystem()
        
        # 配置通知渠道
        self.alert_system.add_notification_channel(console_notification)
        self.alert_system.add_notification_channel(log_notification)
        
        logger.info("🚀 增强版股票分析系统初始化完成")
    
    def run_daily_analysis(self):
        """运行每日分析"""
        logger.info("📊 开始每日分析...")
        
        try:
            # 1. 系统健康检查
            health = self.monitor.check_health()
            logger.info(f"系统状态: {health['status']}")
            
            # 2. 运行核心分析流程
            # TODO: 调用核心分析模块
            
            # 3. 生成可视化报告
            metrics = {
                "cpu_percent": health.get("cpu_percent", 0),
                "memory_percent": health.get("memory_percent", 0),
                "disk_percent": health.get("disk_percent", 0),
                "db_size_mb": health.get("db_size_mb", 0),
                "total_records": health.get("total_records", 0),
                "status": health.get("status", "healthy")
            }
            
            dashboard_file = self.viz.create_dashboard(metrics)
            logger.info(f"仪表板已生成: {dashboard_file}")
            
            # 4. 检查预警
            # TODO: 根据分析结果检查预警
            
            # 5. 生成性能报告
            perf_report = get_performance_report()
            logger.info(f"\n{perf_report}")
            
            logger.info("✅ 每日分析完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 每日分析失败: {e}", exc_info=True)
            
            # 发送系统错误预警
            alert = self.alert_system.check_alerts({
                "cpu_percent": 0,
                "error_message": str(e)
            })
            
            return False
    
    def run_performance_report(self):
        """生成性能报告"""
        logger.info("📈 生成性能报告...")
        
        # 收集系统指标
        sys_metrics = self.monitor.collect_system_metrics()
        db_metrics = self.monitor.collect_database_metrics()
        
        # 获取性能统计
        perf_stats = performance_monitor.get_stats()
        cache_stats = {
            "query_cache": query_cache.get_stats(),
            "api_cache": api_cache.get_stats()
        }
        
        # 生成报告
        report = f"""
=== 增强版股票分析系统 - 性能报告 ===
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
运行时间: {(datetime.now() - self.start_time).total_seconds():.0f}秒

【系统指标】
- CPU使用率: {sys_metrics.cpu_percent if sys_metrics else 'N/A'}%
- 内存使用率: {sys_metrics.memory_percent if sys_metrics else 'N/A'}%
- 磁盘使用率: {sys_metrics.disk_percent if sys_metrics else 'N/A'}%

【数据库指标】
- 数据库大小: {db_metrics.db_size_mb if db_metrics else 'N/A'} MB
- 总记录数: {db_metrics.total_records if db_metrics else 'N/A':,}

【性能统计】
- 函数调用数: {perf_stats['total_functions']}
- API调用数: {perf_stats['total_api_calls']}
- 平均执行时间: {perf_stats['avg_execution_time']:.3f}秒
- 平均API时间: {perf_stats['avg_api_time']:.3f}秒
- 慢查询数: {perf_stats['slow_queries_count']}

【缓存统计】
- 查询缓存命中率: {cache_stats['query_cache']['hit_rate']}
- API缓存命中率: {cache_stats['api_cache']['hit_rate']}

【预警统计】
- 总预警数: {len(self.alert_system.alerts)}
"""
        
        logger.info(report)
        return report
    
    def get_system_status(self) -> Dict:
        """获取系统状态"""
        health = self.monitor.check_health()
        perf_stats = performance_monitor.get_stats()
        alert_stats = self.alert_system.get_stats()
        
        return {
            "health": health,
            "performance": perf_stats,
            "alerts": alert_stats,
            "uptime": (datetime.now() - self.start_time).total_seconds()
        }
    
    def shutdown(self):
        """关闭系统"""
        logger.info("🛑 关闭系统...")
        
        # 生成最终报告
        final_report = self.run_performance_report()
        
        # 清理缓存
        query_cache.clear()
        api_cache.clear()
        
        logger.info("✅ 系统已关闭")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="增强版股票分析系统")
    parser.add_argument("--mode", choices=["daily", "performance", "status"], 
                       default="daily", help="运行模式")
    args = parser.parse_args()
    
    # 初始化系统
    system = EnhancedStockAnalysisSystem()
    
    try:
        if args.mode == "daily":
            system.run_daily_analysis()
        elif args.mode == "performance":
            system.run_performance_report()
        elif args.mode == "status":
            status = system.get_system_status()
            print(f"系统状态: {status}")
    finally:
        system.shutdown()


if __name__ == "__main__":
    main()
