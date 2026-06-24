"""
performance_optimizer.py - 性能优化模块
提供查询缓存、API缓存、内存优化等功能
"""

import logging
import time
import hashlib
import json
from functools import wraps
from typing import Any, Callable, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class QueryCache:
    """SQL查询结果缓存"""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        """
        初始化查询缓存
        
        Args:
            max_size: 最大缓存条目数
            ttl_seconds: 缓存过期时间（秒）
        """
        self.cache: Dict[str, tuple] = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.hit_count = 0
        self.miss_count = 0
    
    def _generate_key(self, query: str, params: tuple = None) -> str:
        """生成缓存键"""
        key_data = f"{query}:{params}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, query: str, params: tuple = None) -> Optional[Any]:
        """获取缓存结果"""
        key = self._generate_key(query, params)
        
        if key in self.cache:
            result, timestamp = self.cache[key]
            
            # 检查是否过期
            if datetime.now() - timestamp < timedelta(seconds=self.ttl_seconds):
                self.hit_count += 1
                logger.debug(f"缓存命中: {key[:16]}...")
                return result
            else:
                # 过期，删除缓存
                del self.cache[key]
                logger.debug(f"缓存过期: {key[:16]}...")
        
        self.miss_count += 1
        return None
    
    def set(self, query: str, params: tuple, result: Any):
        """设置缓存结果"""
        key = self._generate_key(query, params)
        
        # 如果缓存已满，删除最旧的条目
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.cache.items(), key=lambda x: x[1][1])[0]
            del self.cache[oldest_key]
        
        self.cache[key] = (result, datetime.now())
        logger.debug(f"缓存设置: {key[:16]}...")
    
    def clear(self):
        """清空缓存"""
        self.cache.clear()
        logger.info("缓存已清空")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total * 100) if total > 0 else 0
        
        return {
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": f"{hit_rate:.2f}%",
            "cache_size": len(self.cache),
            "max_size": self.max_size
        }


class APICache:
    """API调用结果缓存"""
    
    def __init__(self, ttl_seconds: int = 3600):
        """
        初始化API缓存
        
        Args:
            ttl_seconds: 缓存过期时间（秒），默认1小时
        """
        self.cache: Dict[str, tuple] = {}
        self.ttl_seconds = ttl_seconds
        self.hit_count = 0
        self.miss_count = 0
    
    def _generate_key(self, api_name: str, params: Dict) -> str:
        """生成缓存键"""
        key_data = f"{api_name}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, api_name: str, params: Dict) -> Optional[Any]:
        """获取缓存结果"""
        key = self._generate_key(api_name, params)
        
        if key in self.cache:
            result, timestamp = self.cache[key]
            
            # 检查是否过期
            if datetime.now() - timestamp < timedelta(seconds=self.ttl_seconds):
                self.hit_count += 1
                logger.debug(f"API缓存命中: {api_name}")
                return result
            else:
                # 过期，删除缓存
                del self.cache[key]
                logger.debug(f"API缓存过期: {api_name}")
        
        self.miss_count += 1
        return None
    
    def set(self, api_name: str, params: Dict, result: Any):
        """设置缓存结果"""
        key = self._generate_key(api_name, params)
        self.cache[key] = (result, datetime.now())
        logger.debug(f"API缓存设置: {api_name}")
    
    def clear(self):
        """清空缓存"""
        self.cache.clear()
        logger.info("API缓存已清空")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total * 100) if total > 0 else 0
        
        return {
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": f"{hit_rate:.2f}%",
            "cache_size": len(self.cache)
        }


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics: Dict[str, list] = {
            "execution_time": [],
            "memory_usage": [],
            "api_calls": []
        }
        self.start_time = time.time()
    
    def record_execution(self, func_name: str, duration: float):
        """记录函数执行时间"""
        self.metrics["execution_time"].append({
            "function": func_name,
            "duration": duration,
            "timestamp": datetime.now()
        })
        
        # 只保留最近1000条记录
        if len(self.metrics["execution_time"]) > 1000:
            self.metrics["execution_time"] = self.metrics["execution_time"][-1000:]
    
    def record_api_call(self, api_name: str, duration: float):
        """记录API调用"""
        self.metrics["api_calls"].append({
            "api": api_name,
            "duration": duration,
            "timestamp": datetime.now()
        })
        
        if len(self.metrics["api_calls"]) > 1000:
            self.metrics["api_calls"] = self.metrics["api_calls"][-1000:]
    
    def get_slow_queries(self, threshold: float = 1.0) -> list:
        """获取慢查询"""
        return [
            m for m in self.metrics["execution_time"]
            if m["duration"] > threshold
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        exec_times = [m["duration"] for m in self.metrics["execution_time"]]
        api_times = [m["duration"] for m in self.metrics["api_calls"]]
        
        return {
            "total_functions": len(exec_times),
            "total_api_calls": len(api_times),
            "avg_execution_time": sum(exec_times) / len(exec_times) if exec_times else 0,
            "avg_api_time": sum(api_times) / len(api_times) if api_times else 0,
            "max_execution_time": max(exec_times) if exec_times else 0,
            "max_api_time": max(api_times) if api_times else 0,
            "slow_queries_count": len(self.get_slow_queries()),
            "uptime": time.time() - self.start_time
        }
    
    def cleanup_old_records(self, max_records: int = 1000):
        """清理旧记录，只保留最近N条"""
        for key in self.metrics:
            if len(self.metrics[key]) > max_records:
                self.metrics[key] = self.metrics[key][-max_records:]
        
        return {
            "execution_time_count": len(self.metrics["execution_time"]),
            "api_calls_count": len(self.metrics["api_calls"]),
            "memory_usage_count": len(self.metrics["memory_usage"])
        }


# 全局实例
query_cache = QueryCache()
api_cache = APICache()
performance_monitor = PerformanceMonitor()


def cache_query(ttl: int = 300):
    """查询缓存装饰器"""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            query = kwargs.get('query', args[0] if args else '')
            params = kwargs.get('params', args[1] if len(args) > 1 else None)
            
            # 尝试从缓存获取
            cached_result = query_cache.get(query, params)
            if cached_result is not None:
                return cached_result
            
            # 执行查询
            result = func(*args, **kwargs)
            
            # 缓存结果
            query_cache.set(query, params, result)
            
            return result
        return wrapper
    return decorator


def cache_api(ttl: int = 3600):
    """API缓存装饰器"""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            api_name = func.__name__
            params = kwargs.copy()
            
            # 尝试从缓存获取
            cached_result = api_cache.get(api_name, params)
            if cached_result is not None:
                return cached_result
            
            # 执行API调用
            start_time = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            # 记录性能
            performance_monitor.record_api_call(api_name, duration)
            
            # 缓存结果
            api_cache.set(api_name, params, result)
            
            return result
        return wrapper
    return decorator


def monitor_performance(func: Callable):
    """性能监控装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start_time
        
        # 记录性能
        performance_monitor.record_execution(func.__name__, duration)
        
        # 记录慢查询
        if duration > 1.0:
            logger.warning(f"慢查询检测: {func.__name__} 耗时 {duration:.2f}秒")
        
        return result
    return wrapper


def get_performance_report() -> str:
    """生成性能报告"""
    stats = performance_monitor.get_stats()
    query_stats = query_cache.get_stats()
    api_stats = api_cache.get_stats()
    
    report = f"""
=== 性能报告 ===

【执行统计】
- 总函数调用数: {stats['total_functions']}
- 总API调用数: {stats['total_api_calls']}
- 平均执行时间: {stats['avg_execution_time']:.3f}秒
- 平均API时间: {stats['avg_api_time']:.3f}秒
- 最大执行时间: {stats['max_execution_time']:.3f}秒
- 最大API时间: {stats['max_api_time']:.3f}秒
- 慢查询数量: {stats['slow_queries_count']}
- 系统运行时间: {stats['uptime']:.0f}秒

【查询缓存】
- 命中次数: {query_stats['hit_count']}
- 未命中次数: {query_stats['miss_count']}
- 命中率: {query_stats['hit_rate']}
- 缓存大小: {query_stats['cache_size']}/{query_stats['max_size']}

【API缓存】
- 命中次数: {api_stats['hit_count']}
- 未命中次数: {api_stats['miss_count']}
- 命中率: {api_stats['hit_rate']}
- 缓存大小: {api_stats['cache_size']}

【慢查询列表】
"""
    
    slow_queries = performance_monitor.get_slow_queries()
    if slow_queries:
        for q in slow_queries[:10]:  # 只显示前10个
            report += f"  - {q['function']}: {q['duration']:.3f}秒 (时间: {q['timestamp']})\n"
    else:
        report += "  无慢查询\n"
    
    return report


if __name__ == "__main__":
    # 测试性能优化模块
    logging.basicConfig(level=logging.INFO)
    
    logger.info("🧪 测试性能优化模块...")
    
    # 测试查询缓存
    @cache_query()
    def test_query(params):
        time.sleep(0.1)  # 模拟查询延迟
        return f"result_{params}"
    
    # 第一次调用（未命中缓存）
    start = time.time()
    result1 = test_query("test")
    duration1 = time.time() - start
    logger.info(f"第一次调用: {duration1:.3f}秒")
    
    # 第二次调用（命中缓存）
    start = time.time()
    result2 = test_query("test")
    duration2 = time.time() - start
    logger.info(f"第二次调用: {duration2:.3f}秒")
    
    # 测试API缓存
    @cache_api()
    def test_api(param):
        time.sleep(0.1)  # 模拟API延迟
        return f"api_result_{param}"
    
    # 第一次调用（未命中缓存）
    start = time.time()
    result3 = test_api("test")
    duration3 = time.time() - start
    logger.info(f"API第一次调用: {duration3:.3f}秒")
    
    # 第二次调用（命中缓存）
    start = time.time()
    result4 = test_api("test")
    duration4 = time.time() - start
    logger.info(f"API第二次调用: {duration4:.3f}秒")
    
    # 显示性能报告
    logger.info("\n" + get_performance_report())
