"""
alert_system.py - 预警通知系统
提供股票预警、系统预警、多渠道通知功能
"""

import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """预警级别"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertType(Enum):
    """预警类型"""
    PRICE_MOVEMENT = "price_movement"  # 价格异动
    VOLUME_SPIKE = "volume_spike"  # 成交量异动
    TECHNICAL_SIGNAL = "technical_signal"  # 技术信号
    FUNDAMENTAL_CHANGE = "fundamental_change"  # 基本面变化
    SENTIMENT_CHANGE = "sentiment_change"  # 舆情变化
    SYSTEM_ERROR = "system_error"  # 系统错误
    PERFORMANCE_DEGRADATION = "performance_degradation"  # 性能降级


@dataclass
class Alert:
    """预警信息"""
    alert_id: str
    alert_type: AlertType
    level: AlertLevel
    title: str
    message: str
    ts_code: Optional[str] = None
    stock_name: Optional[str] = None
    data: Optional[Dict] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type.value,
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "ts_code": self.ts_code,
            "stock_name": self.stock_name,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        }


class AlertRule:
    """预警规则"""
    
    def __init__(self, name: str, alert_type: AlertType, level: AlertLevel,
                 condition: callable, message_template: str):
        self.name = name
        self.alert_type = alert_type
        self.level = level
        self.condition = condition
        self.message_template = message_template
        self.enabled = True
    
    def check(self, data: Dict) -> Optional[Alert]:
        """检查规则"""
        if not self.enabled:
            return None
        
        try:
            if self.condition(data):
                return Alert(
                    alert_id=f"{self.name}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    alert_type=self.alert_type,
                    level=self.level,
                    title=self.name,
                    message=self.message_template.format(**data),
                    ts_code=data.get("ts_code"),
                    stock_name=data.get("stock_name"),
                    data=data
                )
        except Exception as e:
            logger.error(f"检查预警规则失败 [{self.name}]: {e}")
        
        return None


class AlertSystem:
    """预警系统"""
    
    def __init__(self, db_path: str = "database/stock_analysis.db"):
        self.db_path = db_path
        self.rules: List[AlertRule] = []
        self.alerts: List[Alert] = []
        self.notification_channels: List[callable] = []
        self.max_alerts = 10000  # 最多保存的预警数量
        
        # 初始化默认规则
        self._init_default_rules()
    
    def _init_default_rules(self):
        """初始化默认预警规则"""
        # 价格异动规则
        self.add_rule(AlertRule(
            name="价格大幅上涨",
            alert_type=AlertType.PRICE_MOVEMENT,
            level=AlertLevel.WARNING,
            condition=lambda data: data.get("price_change_pct", 0) > 5,
            message_template="{stock_name}({ts_code}) 价格大幅上涨 {price_change_pct:.2f}%"
        ))
        
        self.add_rule(AlertRule(
            name="价格大幅下跌",
            alert_type=AlertType.PRICE_MOVEMENT,
            level=AlertLevel.CRITICAL,
            condition=lambda data: data.get("price_change_pct", 0) < -5,
            message_template="{stock_name}({ts_code}) 价格大幅下跌 {price_change_pct:.2f}%"
        ))
        
        # 成交量异动规则
        self.add_rule(AlertRule(
            name="成交量暴增",
            alert_type=AlertType.VOLUME_SPIKE,
            level=AlertLevel.WARNING,
            condition=lambda data: data.get("volume_ratio", 1) > 3,
            message_template="{stock_name}({ts_code}) 成交量暴增，是平均的 {volume_ratio:.1f} 倍"
        ))
        
        # 技术信号规则
        self.add_rule(AlertRule(
            name="突破20日均线",
            alert_type=AlertType.TECHNICAL_SIGNAL,
            level=AlertLevel.INFO,
            condition=lambda data: data.get("break_ma20", False),
            message_template="{stock_name}({ts_code}) 突破20日均线，当前价 {current_price:.2f}"
        ))
        
        self.add_rule(AlertRule(
            name="跌破20日均线",
            alert_type=AlertType.TECHNICAL_SIGNAL,
            level=AlertLevel.WARNING,
            condition=lambda data: data.get("break_ma20_down", False),
            message_template="{stock_name}({ts_code}) 跌破20日均线，当前价 {current_price:.2f}"
        ))
        
        # 系统性能规则
        self.add_rule(AlertRule(
            name="系统CPU使用率过高",
            alert_type=AlertType.PERFORMANCE_DEGRADATION,
            level=AlertLevel.WARNING,
            condition=lambda data: data.get("cpu_percent", 0) > 80,
            message_template="系统CPU使用率过高: {cpu_percent:.1f}%"
        ))
        
        logger.info(f"已初始化 {len(self.rules)} 个预警规则")
    
    def add_rule(self, rule: AlertRule):
        """添加预警规则"""
        self.rules.append(rule)
        logger.info(f"添加预警规则: {rule.name}")
    
    def remove_rule(self, rule_name: str):
        """移除预警规则"""
        self.rules = [r for r in self.rules if r.name != rule_name]
        logger.info(f"移除预警规则: {rule_name}")
    
    def enable_rule(self, rule_name: str):
        """启用规则"""
        for rule in self.rules:
            if rule.name == rule_name:
                rule.enabled = True
                logger.info(f"启用预警规则: {rule_name}")
                break
    
    def disable_rule(self, rule_name: str):
        """禁用规则"""
        for rule in self.rules:
            if rule.name == rule_name:
                rule.enabled = False
                logger.info(f"禁用预警规则: {rule_name}")
                break
    
    def check_alerts(self, data: Dict) -> List[Alert]:
        """检查所有规则"""
        triggered_alerts = []
        
        for rule in self.rules:
            alert = rule.check(data)
            if alert:
                triggered_alerts.append(alert)
                self.alerts.append(alert)
                
                # 发送通知
                self._send_notifications(alert)
        
        # 保持预警列表在限制内
        if len(self.alerts) > self.max_alerts:
            self.alerts = self.alerts[-self.max_alerts:]
        
        return triggered_alerts
    
    def _send_notifications(self, alert: Alert):
        """发送通知"""
        for channel in self.notification_channels:
            try:
                channel(alert)
            except Exception as e:
                logger.error(f"发送通知失败: {e}")
    
    def add_notification_channel(self, channel: callable):
        """添加通知渠道"""
        self.notification_channels.append(channel)
        logger.info(f"添加通知渠道: {channel.__name__}")
    
    def get_recent_alerts(self, hours: int = 24) -> List[Dict]:
        """获取最近的预警"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_alerts = [
            alert.to_dict() for alert in self.alerts
            if alert.timestamp > cutoff_time
        ]
        return recent_alerts
    
    def get_alerts_by_level(self, level: AlertLevel) -> List[Dict]:
        """按级别获取预警"""
        return [
            alert.to_dict() for alert in self.alerts
            if alert.level == level
        ]
    
    def get_alerts_by_type(self, alert_type: AlertType) -> List[Dict]:
        """按类型获取预警"""
        return [
            alert.to_dict() for alert in self.alerts
            if alert.alert_type == alert_type
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取预警统计"""
        total = len(self.alerts)
        by_level = {}
        by_type = {}
        
        for alert in self.alerts:
            level_key = alert.level.value
            type_key = alert.alert_type.value
            
            by_level[level_key] = by_level.get(level_key, 0) + 1
            by_type[type_key] = by_type.get(type_key, 0) + 1
        
        return {
            "total_alerts": total,
            "by_level": by_level,
            "by_type": by_type,
            "rules_count": len(self.rules),
            "notification_channels": len(self.notification_channels)
        }


def console_notification(alert: Alert):
    """控制台通知"""
    level_icons = {
        AlertLevel.INFO: "ℹ️",
        AlertLevel.WARNING: "⚠️",
        AlertLevel.CRITICAL: "🚨",
        AlertLevel.EMERGENCY: "🆘"
    }
    icon = level_icons.get(alert.level, "📢")
    print(f"{icon} [{alert.level.value.upper()}] {alert.title}")
    print(f"   {alert.message}")
    if alert.ts_code:
        print(f"   股票: {alert.stock_name}({alert.ts_code})")
    print()


def log_notification(alert: Alert):
    """日志通知"""
    level_map = {
        AlertLevel.INFO: logging.INFO,
        AlertLevel.WARNING: logging.WARNING,
        AlertLevel.CRITICAL: logging.CRITICAL,
        AlertLevel.EMERGENCY: logging.CRITICAL
    }
    log_level = level_map.get(alert.level, logging.INFO)
    
    logger.log(log_level, f"[{alert.alert_type.value}] {alert.title}: {alert.message}")


if __name__ == "__main__":
    # 测试预警系统
    logging.basicConfig(level=logging.INFO)
    
    logger.info("🧪 测试预警系统...")
    
    # 创建预警系统
    alert_system = AlertSystem()
    
    # 添加通知渠道
    alert_system.add_notification_channel(console_notification)
    alert_system.add_notification_channel(log_notification)
    
    # 测试预警检查
    test_data_1 = {
        "ts_code": "000001.SZ",
        "stock_name": "平安银行",
        "price_change_pct": 6.5,
        "volume_ratio": 2.5
    }
    
    alerts = alert_system.check_alerts(test_data_1)
    logger.info(f"触发预警数: {len(alerts)}")
    
    # 测试下跌预警
    test_data_2 = {
        "ts_code": "600519.SH",
        "stock_name": "贵州茅台",
        "price_change_pct": -7.2,
        "volume_ratio": 4.5
    }
    
    alerts = alert_system.check_alerts(test_data_2)
    logger.info(f"触发预警数: {len(alerts)}")
    
    # 显示统计
    stats = alert_system.get_stats()
    logger.info(f"预警统计: {stats}")
