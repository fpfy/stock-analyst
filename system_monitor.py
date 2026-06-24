"""
system_monitor.py - 系统监控模块
提供系统健康监控、性能指标收集、告警机制
"""

import logging
import psutil
import sqlite3
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    """系统指标"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_percent: float
    disk_used_gb: float
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "memory_used_mb": self.memory_used_mb,
            "disk_percent": self.disk_percent,
            "disk_used_gb": self.disk_used_gb
        }


@dataclass
class DatabaseMetrics:
    """数据库指标"""
    timestamp: datetime
    db_size_mb: float
    table_count: int
    total_records: int
    slow_queries: int
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "db_size_mb": self.db_size_mb,
            "table_count": self.table_count,
            "total_records": self.total_records,
            "slow_queries": self.slow_queries
        }


class SystemMonitor:
    """系统监控器"""
    
    def __init__(self, db_path: str = "database/stock_analysis.db"):
        self.db_path = db_path
        self.metrics_history: List[SystemMetrics] = []
        self.db_metrics_history: List[DatabaseMetrics] = []
        self.alerts: List[Dict] = []
        self.max_history = 1000  # 最多保存1000条记录
    
    def collect_system_metrics(self) -> SystemMetrics:
        """收集系统指标"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            metrics = SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory.used / (1024 * 1024),
                disk_percent=disk.percent,
                disk_used_gb=disk.used / (1024 * 1024 * 1024)
            )
            
            self.metrics_history.append(metrics)
            
            # 保持历史记录在限制内
            if len(self.metrics_history) > self.max_history:
                self.metrics_history = self.metrics_history[-self.max_history:]
            
            return metrics
            
        except Exception as e:
            logger.error(f"收集系统指标失败: {e}")
            return None
    
    def collect_database_metrics(self) -> Optional[DatabaseMetrics]:
        """收集数据库指标"""
        try:
            if not os.path.exists(self.db_path):
                return None
            
            # 数据库文件大小
            db_size_mb = os.path.getsize(self.db_path) / (1024 * 1024)
            
            # 连接数据库
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取表数量
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            
            # 获取总记录数
            cursor.execute("""
                SELECT SUM(count) FROM (
                    SELECT COUNT(*) as count FROM stock_basic
                    UNION ALL
                    SELECT COUNT(*) FROM financial_data
                    UNION ALL
                    SELECT COUNT(*) FROM valuation_data
                    UNION ALL
                    SELECT COUNT(*) FROM index_data
                )
            """)
            result = cursor.fetchone()
            total_records = result[0] if result[0] else 0
            
            conn.close()
            
            metrics = DatabaseMetrics(
                timestamp=datetime.now(),
                db_size_mb=db_size_mb,
                table_count=table_count,
                total_records=total_records,
                slow_queries=0  # TODO: 实现慢查询统计
            )
            
            self.db_metrics_history.append(metrics)
            
            if len(self.db_metrics_history) > self.max_history:
                self.db_metrics_history = self.db_metrics_history[-self.max_history:]
            
            return metrics
            
        except Exception as e:
            logger.error(f"收集数据库指标失败: {e}")
            return None
    
    def check_health(self) -> Dict[str, Any]:
        """检查系统健康状态"""
        health = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "issues": [],
            "warnings": []
        }
        
        # 收集指标
        sys_metrics = self.collect_system_metrics()
        db_metrics = self.collect_database_metrics()
        
        # 检查CPU使用率
        if sys_metrics and sys_metrics.cpu_percent > 90:
            health["issues"].append(f"CPU使用率过高: {sys_metrics.cpu_percent:.1f}%")
            health["status"] = "critical"
        elif sys_metrics and sys_metrics.cpu_percent > 70:
            health["warnings"].append(f"CPU使用率较高: {sys_metrics.cpu_percent:.1f}%")
        
        # 检查内存使用率
        if sys_metrics and sys_metrics.memory_percent > 90:
            health["issues"].append(f"内存使用率过高: {sys_metrics.memory_percent:.1f}%")
            health["status"] = "critical"
        elif sys_metrics and sys_metrics.memory_percent > 70:
            health["warnings"].append(f"内存使用率较高: {sys_metrics.memory_percent:.1f}%")
        
        # 检查磁盘使用率
        if sys_metrics and sys_metrics.disk_percent > 90:
            health["issues"].append(f"磁盘使用率过高: {sys_metrics.disk_percent:.1f}%")
            health["status"] = "critical"
        elif sys_metrics and sys_metrics.disk_percent > 70:
            health["warnings"].append(f"磁盘使用率较高: {sys_metrics.disk_percent:.1f}%")
        
        # 检查数据库
        if db_metrics:
            if db_metrics.db_size_mb > 1000:  # 1GB
                health["warnings"].append(f"数据库较大: {db_metrics.db_size_mb:.1f}MB")
        
        # 确定整体状态
        if health["issues"]:
            health["status"] = "critical"
        elif health["warnings"]:
            health["status"] = "warning"
        
        # 记录告警
        if health["status"] != "healthy":
            self.alerts.append({
                "timestamp": datetime.now().isoformat(),
                "status": health["status"],
                "issues": health["issues"],
                "warnings": health["warnings"]
            })
        
        return health
    
    def get_metrics_summary(self, last_hours: int = 24) -> Dict[str, Any]:
        """获取指标摘要"""
        cutoff_time = datetime.now() - timedelta(hours=last_hours)
        
        # 过滤最近的数据
        recent_sys = [m for m in self.metrics_history if m.timestamp > cutoff_time]
        recent_db = [m for m in self.db_metrics_history if m.timestamp > cutoff_time]
        
        summary = {
            "period_hours": last_hours,
            "system_metrics": {
                "count": len(recent_sys),
                "avg_cpu": sum(m.cpu_percent for m in recent_sys) / len(recent_sys) if recent_sys else 0,
                "avg_memory": sum(m.memory_percent for m in recent_sys) / len(recent_sys) if recent_sys else 0,
                "max_cpu": max(m.cpu_percent for m in recent_sys) if recent_sys else 0,
                "max_memory": max(m.memory_percent for m in recent_sys) if recent_sys else 0
            },
            "database_metrics": {
                "count": len(recent_db),
                "current_db_size": recent_db[-1].db_size_mb if recent_db else 0,
                "current_records": recent_db[-1].total_records if recent_db else 0
            },
            "alerts_count": len(self.alerts)
        }
        
        return summary
    
    def generate_health_report(self) -> str:
        """生成健康报告"""
        health = self.check_health()
        summary = self.get_metrics_summary()
        
        report = f"""
=== 系统健康报告 ===
生成时间: {health['timestamp']}

【整体状态】 {health['status'].upper()}

【系统指标】
- 平均CPU使用率: {summary['system_metrics']['avg_cpu']:.1f}%
- 平均内存使用率: {summary['system_metrics']['avg_memory']:.1f}%
- 最大CPU使用率: {summary['system_metrics']['max_cpu']:.1f}%
- 最大内存使用率: {summary['system_metrics']['max_memory']:.1f}%

【数据库指标】
- 数据库大小: {summary['database_metrics']['current_db_size']:.1f} MB
- 总记录数: {summary['database_metrics']['current_records']:,}
- 表数量: {summary['database_metrics'].get('table_count', 'N/A')}

【告警信息】
"""
        
        if health["issues"]:
            report += "\n严重问题:\n"
            for issue in health["issues"]:
                report += f"  ❌ {issue}\n"
        
        if health["warnings"]:
            report += "\n警告信息:\n"
            for warning in health["warnings"]:
                report += f"  ⚠️ {warning}\n"
        
        if not health["issues"] and not health["warnings"]:
            report += "  ✅ 无异常\n"
        
        report += f"\n最近24小时告警数: {summary['alerts_count']}\n"
        
        return report


if __name__ == "__main__":
    # 测试系统监控
    logging.basicConfig(level=logging.INFO)
    
    logger.info("🧪 测试系统监控模块...")
    
    monitor = SystemMonitor()
    
    # 收集指标
    sys_metrics = monitor.collect_system_metrics()
    if sys_metrics:
        logger.info(f"系统指标: CPU {sys_metrics.cpu_percent:.1f}%, "
                   f"内存 {sys_metrics.memory_percent:.1f}%, "
                   f"磁盘 {sys_metrics.disk_percent:.1f}%")
    
    # 检查健康状态
    health = monitor.check_health()
    logger.info(f"系统状态: {health['status']}")
    
    # 生成报告
    report = monitor.generate_health_report()
    logger.info(f"\n{report}")
