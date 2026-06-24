"""
ops_automation.py - 运维自动化脚本
提供系统运维、数据更新、性能优化等功能
"""

import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from logging_config import setup_logging
from system_monitor import SystemMonitor
from performance_optimizer import query_cache, api_cache
from alert_system import AlertSystem, console_notification

setup_logging()
logger = logging.getLogger(__name__)


class OpsAutomation:
    """运维自动化"""
    
    def __init__(self):
        self.monitor = SystemMonitor()
        self.alert_system = AlertSystem()
        self.alert_system.add_notification_channel(console_notification)
        
        # 目录配置
        self.backup_dir = Path("backups")
        self.log_dir = Path("logs")
        self.reports_dir = Path("reports")
        
        # 创建目录
        self.backup_dir.mkdir(exist_ok=True)
        self.log_dir.mkdir(exist_ok=True)
        self.reports_dir.mkdir(exist_ok=True)
    
    def daily_maintenance(self):
        """日常维护任务"""
        logger.info("🔧 开始日常维护...")
        
        try:
            # 1. 系统健康检查
            self._health_check()
            
            # 2. 清理临时文件
            self._cleanup_temp_files()
            
            # 3. 清理过期缓存
            self._cleanup_cache()
            
            # 4. 生成维护报告
            self._generate_maintenance_report()
            
            logger.info("✅ 日常维护完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 日常维护失败: {e}", exc_info=True)
            return False
    
    def _health_check(self):
        """健康检查"""
        logger.info("🏥 执行健康检查...")
        
        health = self.monitor.check_health()
        
        # 发送预警（如果需要）
        if health['status'] in ['warning', 'critical']:
            self.alert_system.check_alerts({
                "cpu_percent": health.get('cpu_percent', 0),
                "memory_percent": health.get('memory_percent', 0),
                "disk_percent": health.get('disk_percent', 0)
            })
        
        logger.info(f"系统状态: {health['status']}")
    
    def _cleanup_temp_files(self):
        """清理临时文件"""
        logger.info("🧹 清理临时文件...")
        
        # 清理超过7天的临时文件
        cutoff_date = datetime.now() - timedelta(days=7)
        
        temp_dirs = [
            self.reports_dir / "charts",
            Path("data") / "temp"
        ]
        
        for temp_dir in temp_dirs:
            if temp_dir.exists():
                for file in temp_dir.glob("*"):
                    if file.is_file():
                        mtime = datetime.fromtimestamp(file.stat().st_mtime)
                        if mtime < cutoff_date:
                            file.unlink()
                            logger.debug(f"删除临时文件: {file}")
        
        logger.info("临时文件清理完成")
    
    def _cleanup_cache(self):
        """清理过期缓存"""
        logger.info("🗑️ 清理过期缓存...")
        
        # 清理缓存
        query_cache.clear()
        api_cache.clear()
        
        logger.info("缓存清理完成")
    
    def _generate_maintenance_report(self):
        """生成维护报告"""
        logger.info("📊 生成维护报告...")
        
        # 收集指标
        sys_metrics = self.monitor.collect_system_metrics()
        db_metrics = self.monitor.collect_database_metrics()
        
        # 磁盘清理
        disk_usage = shutil.disk_usage(".")
        
        report = f"""
=== 日常维护报告 ===
时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

【系统指标】
- CPU使用率: {sys_metrics.cpu_percent if sys_metrics else 'N/A'}%
- 内存使用率: {sys_metrics.memory_percent if sys_metrics else 'N/A'}%
- 内存使用: {sys_metrics.memory_used_mb if sys_metrics else 'N/A'} MB

【磁盘空间】
- 总容量: {disk_usage.total / (1024**3):.2f} GB
- 已使用: {disk_usage.used / (1024**3):.2f} GB
- 可用: {disk_usage.free / (1024**3):.2f} GB
- 使用率: {disk_usage.used / disk_usage.total * 100:.1f}%

【数据库】
- 大小: {db_metrics.db_size_mb if db_metrics else 'N/A'} MB
- 记录数: {db_metrics.total_records if db_metrics else 'N/A':,}
- 表数: {db_metrics.table_count if db_metrics else 'N/A'}
"""
        
        # 保存报告
        report_file = self.reports_dir / f"maintenance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        report_file.write_text(report, encoding='utf-8')
        
        logger.info(f"维护报告已保存: {report_file}")
    
    def backup_database(self):
        """备份数据库"""
        logger.info("💾 开始数据库备份...")
        
        try:
            import sqlite3
            
            db_path = "database/stock_analysis.db"
            backup_gz = self.backup_dir / f"stock_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db.gz"
            
            # 直接压缩备份
            import gzip
            backup_data = open(db_path, 'rb').read()
            with gzip.open(backup_gz, 'wb') as f_out:
                f_out.write(backup_data)
        
            logger.info(f"✅ 备份完成: {backup_gz}")
            return str(backup_gz)
            
        except Exception as e:
            logger.error(f"❌ 备份失败: {e}", exc_info=True)
            return ""
    
    def optimize_database(self):
        """优化数据库"""
        logger.info("🔧 开始数据库优化...")
        
        try:
            import sqlite3
            
            db_path = "database/stock_analysis.db"
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 分析数据库
            cursor.execute("ANALYZE")
            
            # 清理碎片
            cursor.execute("VACUUM")
            
            # 重建索引（可选）
            # cursor.execute("REINDEX")
            
            conn.commit()
            conn.close()
            
            logger.info("✅ 数据库优化完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 数据库优化失败: {e}", exc_info=True)
            return False
    
    def check_data_quality(self):
        """检查数据质量"""
        logger.info("🔍 检查数据质量...")
        
        try:
            import sqlite3
            
            db_path = "database/stock_analysis.db"
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            issues = []
            
            # 检查stock_basic表
            cursor.execute("SELECT COUNT(*) FROM stock_basic")
            total = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM stock_basic WHERE ts_code IS NULL")
            null_ts_code = cursor.fetchone()[0]
            
            if null_ts_code > 0:
                issues.append(f"stock_basic表有{null_ts_code}条记录ts_code为空")
            
            # 检查financial_data表
            cursor.execute("SELECT COUNT(*) FROM financial_data WHERE end_date IS NULL")
            null_end_date = cursor.fetchone()[0]
            
            if null_end_date > 0:
                issues.append(f"financial_data表有{null_end_date}条记录end_date为空")
            
            conn.close()
            
            if issues:
                logger.warning("发现数据质量问题:")
                for issue in issues:
                    logger.warning(f"  - {issue}")
                return False
            else:
                logger.info("✅ 数据质量检查通过")
                return True
                
        except Exception as e:
            logger.error(f"❌ 数据质量检查失败: {e}", exc_info=True)
            return False
    
    def run_full_ops(self):
        """执行完整运维流程"""
        logger.info("🚀 开始完整运维流程...")
        
        results = {
            "health_check": self._health_check(),
            "cleanup": self._cleanup_temp_files(),
            "cache_cleanup": self._cleanup_cache(),
            "backup": bool(self.backup_database()),
            "optimize": self.optimize_database(),
            "data_quality": self.check_data_quality()
        }
        
        # 生成运维报告
        self._generate_ops_report(results)
        
        logger.info("✅ 完整运维流程完成")
        return results
    
    def _generate_ops_report(self, results):
        """生成运维报告"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = self.reports_dir / f"ops_{timestamp}.txt"
        
        report = f"""
=== 运维自动化报告 ===
时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

【执行结果】
- 健康检查: {'✅ 通过' if results.get('health_check') else '❌ 失败'}
- 文件清理: {'✅ 完成' if results.get('cleanup') else '❌ 失败'}
- 缓存清理: {'✅ 完成' if results.get('cache_cleanup') else '❌ 失败'}
- 数据库备份: {'✅ 完成' if results.get('backup') else '❌ 失败'}
- 数据库优化: {'✅ 完成' if results.get('optimize') else '❌ 失败'}
- 数据质量检查: {'✅ 通过' if results.get('data_quality') else '⚠️ 存在问题'}
"""
        
        report_file.write_text(report, encoding='utf-8')
        logger.info(f"运维报告已保存: {report_file}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="运维自动化工具")
    parser.add_argument("--task", choices=[
        "daily", "backup", "optimize", "quality", "full"
    ], default="daily", help="任务类型")
    args = parser.parse_args()
    
    ops = OpsAutomation()
    
    try:
        if args.task == "daily":
            ops.daily_maintenance()
        elif args.task == "backup":
            ops.backup_database()
        elif args.task == "optimize":
            ops.optimize_database()
        elif args.task == "quality":
            ops.check_data_quality()
        elif args.task == "full":
            ops.run_full_ops()
    finally:
        # 清理
        query_cache.clear()
        api_cache.clear()
