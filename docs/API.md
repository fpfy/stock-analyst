# 股票分析系统 - API文档

## 📚 目录
1. [概述](#概述)
2. [核心API](#核心api)
3. [使用示例](#使用示例)
4. [错误处理](#错误处理)
5. [性能指南](#性能指南)

---

## 概述

本文档描述股票分析系统的核心API接口，供二次开发使用。

### 基础信息
- **Base URL**: N/A（本地模块调用）
- **Python版本**: 3.11+
- **依赖**: 见requirements.txt

---

## 核心API

### 1. 性能优化模块

#### QueryCache
查询结果缓存类

**方法**：
- `get(query, params)` - 获取缓存
- `set(query, params, result)` - 设置缓存
- `clear()` - 清空缓存
- `get_stats()` - 获取统计信息

**示例**：
```python
from performance_optimizer import query_cache

# 设置缓存
query_cache.set("SELECT * FROM stocks WHERE id=?", (1,), {"id": 1, "name": "Test"})

# 获取缓存
result = query_cache.get("SELECT * FROM stocks WHERE id=?", (1,))

# 获取统计
stats = query_cache.get_stats()
print(f"命中率: {stats['hit_rate']}")
```

#### APICache
API调用缓存类

**方法**：
- `get(api_name, params)` - 获取缓存
- `set(api_name, params, result)` - 设置缓存
- `clear()` - 清空缓存
- `get_stats()` - 获取统计信息

**示例**：
```python
from performance_optimizer import api_cache

# 缓存API结果
api_cache.set("get_stock_price", {"ts_code": "000001.SZ"}, {"price": 10.5})

# 获取缓存
result = api_cache.get("get_stock_price", {"ts_code": "000001.SZ"})
```

#### 装饰器

##### @cache_query
查询缓存装饰器

```python
from performance_optimizer import cache_query

@cache_query(ttl=300)
def get_stock_data(ts_code):
    # 查询数据库
    return data
```

**参数**：
- `ttl`: 缓存过期时间（秒），默认300

##### @cache_api
API缓存装饰器

```python
from performance_optimizer import cache_api

@cache_api(ttl=3600)
def fetch_stock_price(ts_code):
    # 调用API
    return data
```

**参数**：
- `ttl`: 缓存过期时间（秒），默认3600

##### @monitor_performance
性能监控装饰器

```python
from performance_optimizer import monitor_performance

@monitor_performance
def heavy_computation():
    # 耗时操作
    pass
```

---

### 2. 系统监控模块

#### SystemMonitor
系统监控器类

**方法**：
- `collect_system_metrics()` - 收集系统指标
- `collect_database_metrics()` - 收集数据库指标
- `check_health()` - 检查健康状态
- `get_metrics_summary(hours)` - 获取指标摘要
- `generate_health_report()` - 生成健康报告

**示例**：
```python
from system_monitor import SystemMonitor

monitor = SystemMonitor()

# 收集指标
sys_metrics = monitor.collect_system_metrics()
print(f"CPU: {sys_metrics.cpu_percent}%")

# 检查健康
health = monitor.check_health()
print(f"状态: {health['status']}")

# 生成报告
report = monitor.generate_health_report()
print(report)
```

**返回值**：

SystemMetrics:
- `timestamp`: datetime
- `cpu_percent`: float
- `memory_percent`: float
- `memory_used_mb`: float
- `disk_percent`: float
- `disk_used_gb`: float

DatabaseMetrics:
- `timestamp`: datetime
- `db_size_mb`: float
- `table_count`: int
- `total_records`: int
- `slow_queries`: int

---

### 3. 可视化模块

#### VisualizationEngine
可视化引擎类

**方法**：
- `create_performance_chart(data, title)` - 创建性能图表
- `create_portfolio_allocation_chart(growth_pct, value_pct)` - 创建配置饼图
- `create_technical_chart(stock_code, price_data, indicators)` - 创建技术分析图
- `create_dashboard(metrics)` - 创建仪表板
- `export_to_excel(data, filename)` - 导出Excel
- `export_to_pdf(content, filename)` - 导出PDF

**示例**：
```python
from visualization import VisualizationEngine

viz = VisualizationEngine()

# 创建仪表板
dashboard = viz.create_dashboard({
    "cpu_percent": 50,
    "memory_percent": 60,
    "disk_percent": 70,
    "db_size_mb": 200,
    "total_records": 1000000,
    "status": "healthy"
})
```

---

### 4. 预警系统模块

#### AlertSystem
预警系统类

**方法**：
- `add_rule(rule)` - 添加规则
- `remove_rule(rule_name)` - 移除规则
- `check_alerts(data)` - 检查预警
- `add_notification_channel(channel)` - 添加通知渠道
- `get_recent_alerts(hours)` - 获取最近预警
- `get_alerts_by_level(level)` - 按级别获取
- `get_alerts_by_type(alert_type)` - 按类型获取
- `get_stats()` - 获取统计

**示例**：
```python
from alert_system import AlertSystem, AlertRule, AlertLevel, AlertType

alert_system = AlertSystem()

# 添加自定义规则
rule = AlertRule(
    name="自定义预警",
    alert_type=AlertType.PRICE_MOVEMENT,
    level=AlertLevel.WARNING,
    condition=lambda data: data.get("price", 0) > 100,
    message_template="价格超过100元: {price}"
)
alert_system.add_rule(rule)

# 检查预警
alerts = alert_system.check_alerts({
    "ts_code": "000001.SZ",
    "price": 105
})
```

#### Alert
预警信息类

**属性**：
- `alert_id`: str
- `alert_type`: AlertType
- `level`: AlertLevel
- `title`: str
- `message`: str
- `ts_code`: str
- `stock_name`: str
- `data`: dict
- `timestamp`: datetime

---

### 5. 增强版主系统

#### EnhancedStockAnalysisSystem
增强版股票分析系统

**方法**：
- `run_daily_analysis()` - 运行每日分析
- `run_performance_report()` - 生成性能报告
- `get_system_status()` - 获取系统状态
- `shutdown()` - 关闭系统

**示例**：
```python
from enhanced_main import EnhancedStockAnalysisSystem

system = EnhancedStockAnalysisSystem()

# 运行每日分析
system.run_daily_analysis()

# 获取系统状态
status = system.get_system_status()
print(status)
```

---

## 使用示例

### 示例1：完整分析流程
```python
from enhanced_main import EnhancedStockAnalysisSystem

system = EnhancedStockAnalysisSystem()

try:
    # 运行每日分析
    system.run_daily_analysis()
    
    # 获取系统状态
    status = system.get_system_status()
    print(f"系统状态: {status['health']['status']}")
    
finally:
    # 确保正确关闭
    system.shutdown()
```

### 示例2：自定义预警
```python
from alert_system import AlertSystem, AlertLevel, AlertType

alert_system = AlertSystem()

# 添加自定义通知渠道
def email_notification(alert):
    # 发送邮件逻辑
    pass

alert_system.add_notification_channel(email_notification)

# 检查数据
data = {
    "ts_code": "000001.SZ",
    "price_change_pct": 8.5
}

alerts = alert_system.check_alerts(data)
```

### 示例3：性能监控
```python
from performance_optimizer import monitor_performance

@monitor_performance
def my_function():
    # 你的代码
    pass

# 获取性能统计
from performance_optimizer import performance_monitor
stats = performance_monitor.get_stats()
print(f"平均执行时间: {stats['avg_execution_time']:.3f}秒")
```

---

## 错误处理

### 标准异常
所有API抛出标准Python异常：
- `ValueError` - 参数错误
- `RuntimeError` - 运行时错误
- `ConnectionError` - 连接错误

### 错误处理示例
```python
from system_monitor import SystemMonitor

try:
    monitor = SystemMonitor()
    health = monitor.check_health()
except ConnectionError as e:
    print(f"连接失败: {e}")
except RuntimeError as e:
    print(f"运行错误: {e}")
```

---

## 性能指南

### 1. 缓存使用
```python
# 对于频繁访问的数据，使用缓存
@cache_query(ttl=300)
def get_frequently_accessed_data():
    pass
```

### 2. 批量操作
```python
# 批量查询减少数据库访问
def batch_query(ts_codes):
    # 使用IN查询
    pass
```

### 3. 异步处理
```python
# 对于耗时操作，考虑异步处理
import asyncio

async def async_analysis():
    pass
```

---

## 更新日志

### v1.0 (2026-06-20)
- ✅ 初始版本发布
- ✅ 性能优化模块
- ✅ 系统监控模块
- ✅ 可视化模块
- ✅ 预警系统模块
- ✅ 增强版主系统

---

**文档版本**：v1.0  
**最后更新**：2026-06-20  
**维护者**：开发团队
