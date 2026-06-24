"""
weekly_ops.py - 周度运维自动化
执行每周的运维任务：报告生成、数据备份、性能分析、趋势监控
"""

import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from logging_config import setup_logging
from system_monitor import SystemMonitor
from performance_optimizer import performance_monitor, query_cache, api_cache
from alert_system import AlertSystem, console_notification

setup_logging()
logger = logging.getLogger(__name__)


class WeeklyOps:
    """周度运维自动化"""
    
    def __init__(self):
        self.monitor = SystemMonitor()
        self.alert_system = AlertSystem()
        self.alert_system.add_notification_channel(console_notification)
        
        self.reports_dir = Path("reports")
        self.reports_dir.mkdir(exist_ok=True)
    
    def run_weekly_report(self) -> Dict:
        """生成周度运维报告"""
        logger.info("📊 生成周度运维报告...")
        
        now = datetime.now()
        week_start = now - timedelta(days=7)
        
        # 收集数据
        sys_metrics = self.monitor.collect_system_metrics()
        db_metrics = self.monitor.collect_database_metrics()
        perf_stats = performance_monitor.get_stats()
        cache_stats = {
            "query_cache": query_cache.get_stats(),
            "api_cache": api_cache.get_stats()
        }
        alert_stats = self.alert_system.get_stats()
        
        report = {
            "report_type": "weekly",
            "generated_at": now.isoformat(),
            "period": {
                "start": week_start.isoformat(),
                "end": now.isoformat()
            },
            "system_metrics": {
                "cpu_percent": sys_metrics.cpu_percent if sys_metrics else None,
                "memory_percent": sys_metrics.memory_percent if sys_metrics else None,
                "memory_used_mb": sys_metrics.memory_used_mb if sys_metrics else None,
                "disk_percent": sys_metrics.disk_percent if sys_metrics else None,
                "disk_used_gb": sys_metrics.disk_used_gb if sys_metrics else None,
            },
            "database_metrics": {
                "db_size_mb": db_metrics.db_size_mb if db_metrics else None,
                "table_count": db_metrics.table_count if db_metrics else None,
                "total_records": db_metrics.total_records if db_metrics else None,
                "slow_queries": db_metrics.slow_queries if db_metrics else None,
            },
            "performance_stats": perf_stats,
            "cache_stats": cache_stats,
            "alert_stats": alert_stats,
            "health_status": self.monitor.check_health()
        }
        
        # 保存JSON报告
        report_file = self.reports_dir / f"weekly_ops_{now.strftime('%Y%m%d')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # 生成Markdown摘要
        md_report = self._generate_markdown_summary(report)
        md_file = self.reports_dir / f"weekly_ops_{now.strftime('%Y%m%d')}.md"
        md_file.write_text(md_report, encoding='utf-8')
        
        logger.info(f"周度报告已生成: {report_file}")
        logger.info(f"Markdown摘要: {md_file}")
        
        return report
    
    def _generate_markdown_summary(self, report: Dict) -> str:
        """生成Markdown格式摘要"""
        now = datetime.now()
        health = report.get("health_status", {})
        sys_m = report.get("system_metrics", {})
        db_m = report.get("database_metrics", {})
        perf = report.get("performance_stats", {})
        alerts = report.get("alert_stats", {})
        
        md = f"""# 周度运维报告

**生成时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}

## 系统健康状态

- **状态**: {health.get('status', 'unknown').upper()}
- **CPU使用率**: {sys_m.get('cpu_percent', 'N/A')}%
- **内存使用率**: {sys_m.get('memory_percent', 'N/A')}%
- **磁盘使用率**: {sys_m.get('disk_percent', 'N/A')}%

## 数据库状态

- **数据库大小**: {db_m.get('db_size_mb', 'N/A')} MB
- **总记录数**: {db_m.get('total_records', 'N/A'):,}
- **表数量**: {db_m.get('table_count', 'N/A')}
- **慢查询数**: {db_m.get('slow_queries', 'N/A')}

## 性能统计

- **函数调用数**: {perf.get('total_functions', 0)}
- **API调用数**: {perf.get('total_api_calls', 0)}
- **平均执行时间**: {perf.get('avg_execution_time', 0):.3f}秒
- **慢查询数**: {perf.get('slow_queries_count', 0)}
- **运行时间**: {perf.get('uptime', 0):.0f}秒

## 缓存统计

- **查询缓存命中率**: {report.get('cache_stats', {}).get('query_cache', {}).get('hit_rate', 'N/A')}
- **API缓存命中率**: {report.get('cache_stats', {}).get('api_cache', {}).get('hit_rate', 'N/A')}

## 预警统计

- **总预警数**: {alerts.get('total_alerts', 0)}
- **按级别分布**: {alerts.get('by_level', {})}
- **按类型分布**: {alerts.get('by_type', {})}

## 建议

"""
        
        # 添加自动建议
        suggestions = []
        
        if sys_m.get('cpu_percent', 0) > 80:
            suggestions.append("- ⚠️ CPU使用率较高，建议检查是否有异常进程")
        
        if sys_m.get('memory_percent', 0) > 85:
            suggestions.append("- ⚠️ 内存使用率较高，建议增加内存或优化内存使用")
        
        if db_m.get('db_size_mb', 0) > 500:
            suggestions.append("- ⚠️ 数据库较大，建议考虑数据归档或分区")
        
        if perf.get('slow_queries_count', 0) > 10:
            suggestions.append("- ⚠️ 慢查询较多，建议优化数据库索引")
        
        if not suggestions:
            suggestions.append("- ✅ 系统运行正常，无需特别关注")
        
        md += "\n".join(suggestions)
        
        return md
    
    def cleanup_old_reports(self, keep_days: int = 30):
        """清理旧报告"""
        logger.info(f"🧹 清理 {keep_days} 天前的旧报告...")
        
        cutoff = datetime.now() - timedelta(days=keep_days)
        cleaned = 0
        
        for pattern in ["weekly_ops_*.json", "weekly_ops_*.md"]:
            for file in self.reports_dir.glob(pattern):
                mtime = datetime.fromtimestamp(file.stat().st_mtime)
                if mtime < cutoff:
                    file.unlink()
                    cleaned += 1
                    logger.debug(f"删除旧报告: {file.name}")
        
        logger.info(f"✅ 清理完成，删除 {cleaned} 个文件")
        return cleaned
    
    def generate_capacity_plan(self) -> Dict:
        """生成容量规划建议"""
        logger.info("📈 生成容量规划建议...")
        
        db_metrics = self.monitor.collect_database_metrics()
        sys_metrics = self.monitor.collect_system_metrics()
        
        plan = {
            "generated_at": datetime.now().isoformat(),
            "current_status": {
                "db_size_mb": db_metrics.db_size_mb if db_metrics else 0,
                "total_records": db_metrics.total_records if db_metrics else 0,
                "cpu_percent": sys_metrics.cpu_percent if sys_metrics else 0,
                "memory_percent": sys_metrics.memory_percent if sys_metrics else 0,
            },
            "recommendations": []
        }
        
        # 数据库容量建议
        db_size = db_metrics.db_size_mb if db_metrics else 0
        if db_size > 1000:
            plan["recommendations"].append({
                "area": "database",
                "priority": "high",
                "suggestion": "数据库超过1GB，建议实施数据归档策略",
                "action": "archive_old_data"
            })
        elif db_size > 500:
            plan["recommendations"].append({
                "area": "database",
                "priority": "medium",
                "suggestion": "数据库超过500MB，建议监控增长趋势",
                "action": "monitor_growth"
            })
        
        # 内存建议
        mem = sys_metrics.memory_percent if sys_metrics else 0
        if mem > 85:
            plan["recommendations"].append({
                "area": "memory",
                "priority": "high",
                "suggestion": "内存使用率过高，建议升级内存或优化应用",
                "action": "upgrade_memory"
            })
        
        # CPU建议
        cpu = sys_metrics.cpu_percent if sys_metrics else 0
        if cpu > 80:
            plan["recommendations"].append({
                "area": "cpu",
                "priority": "medium",
                "suggestion": "CPU使用率较高，建议优化计算密集型任务",
                "action": "optimize_cpu"
            })
        
        # 保存容量规划
        plan_file = self.reports_dir / f"capacity_plan_{datetime.now().strftime('%Y%m%d')}.json"
        with open(plan_file, 'w', encoding='utf-8') as f:
            json.dump(plan, f, indent=2, ensure_ascii=False)
        
        logger.info(f"容量规划已保存: {plan_file}")
        return plan
    
    def run_weekly_ops(self):
        """执行周度运维"""
        logger.info("🚀 开始周度运维...")
        
        results = {
            "weekly_report": bool(self.run_weekly_report()),
            "cleanup": self.cleanup_old_reports(),
            "capacity_plan": self.generate_capacity_plan()
        }
        
        logger.info("✅ 周度运维完成")
        return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="周度运维工具")
    parser.add_argument("--task", choices=["report", "cleanup", "capacity", "full"], 
                       default="full", help="任务类型")
    args = parser.parse_args()
    
    ops = WeeklyOps()
    
    try:
        if args.task == "report":
            ops.run_weekly_report()
        elif args.task == "cleanup":
            ops.cleanup_old_reports()
        elif args.task == "capacity":
            ops.generate_capacity_plan()
        elif args.task == "full":
            ops.run_weekly_ops()
    finally:
        query_cache.clear()
        api_cache.clear()
