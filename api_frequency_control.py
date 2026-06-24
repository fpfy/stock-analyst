"""
api_frequency_control.py - API调用频率控制模块
防止大模型API调用频率超限，实现智能限流和并发控制
"""

import time
import threading
import queue
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from functools import wraps
import random
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class APILimiter:
    """API调用频率控制器"""
    
    def __init__(self, max_calls_per_minute: int = 60, max_calls_per_hour: int = 3600, 
                 max_calls_per_day: int = 10000):
        """
        初始化API限流器
        
        Args:
            max_calls_per_minute: 每分钟最大调用次数
            max_calls_per_hour: 每小时最大调用次数
            max_calls_per_day: 每天最大调用次数
        """
        self.max_calls_per_minute = max_calls_per_minute
        self.max_calls_per_hour = max_calls_per_hour
        self.max_calls_per_day = max_calls_per_day
        
        # 时间窗口计数器
        self.minute_calls = 0
        self.hour_calls = 0
        self.day_calls = 0
        
        # 时间窗口开始时间
        self.minute_start = datetime.now()
        self.hour_start = datetime.now()
        self.day_start = datetime.now()
        
        # 锁机制
        self.lock = threading.Lock()
        
        logger.info(f"API限流器初始化: {max_calls_per_minute}/分钟, {max_calls_per_hour}/小时, {max_calls_per_day}/天")
    
    def check_limit(self) -> bool:
        """检查是否超出调用限制"""
        now = datetime.now()
        
        with self.lock:
            # 检查分钟窗口
            if (now - self.minute_start).seconds >= 60:
                self.minute_calls = 0
                self.minute_start = now
            
            # 检查小时窗口
            if (now - self.hour_start).seconds >= 3600:
                self.hour_calls = 0
                self.hour_start = now
            
            # 检查天窗口
            if (now - self.day_start).days >= 1:
                self.day_calls = 0
                self.day_start = now
            
            # 检查各窗口限制
            if self.minute_calls >= self.max_calls_per_minute:
                logger.warning(f"达到分钟调用限制: {self.minute_calls}/{self.max_calls_per_minute}")
                return False
            
            if self.hour_calls >= self.max_calls_per_hour:
                logger.warning(f"达到小时调用限制: {self.hour_calls}/{self.max_calls_per_hour}")
                return False
            
            if self.day_calls >= self.max_calls_per_day:
                logger.warning(f"达到天调用限制: {self.day_calls}/{self.max_calls_per_day}")
                return False
            
            return True
    
    def increment(self):
        """增加调用计数"""
        with self.lock:
            self.minute_calls += 1
            self.hour_calls += 1
            self.day_calls += 1
    
    def get_current_usage(self) -> Dict[str, int]:
        """获取当前使用情况"""
        with self.lock:
            return {
                'minute_calls': self.minute_calls,
                'hour_calls': self.hour_calls,
                'day_calls': self.day_calls,
                'max_minute': self.max_calls_per_minute,
                'max_hour': self.max_calls_per_hour,
                'max_day': self.max_calls_per_day
            }

class APIThreadPool:
    """API调用线程池"""
    
    def __init__(self, max_workers: int = 5, api_limiter: APILimiter = None):
        """
        初始化API线程池
        
        Args:
            max_workers: 最大工作线程数
            api_limiter: API限流器
        """
        self.max_workers = max_workers
        self.api_limiter = api_limiter or APILimiter()
        self.task_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.workers = []
        self.running = False
        
        # 统计信息
        self.total_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        
        logger.info(f"API线程池初始化: 最大工作线程数={max_workers}")
    
    def add_task(self, func: Callable, *args, **kwargs):
        """添加任务到队列"""
        self.task_queue.put((func, args, kwargs))
        self.total_tasks += 1
    
    def start(self):
        """启动线程池"""
        if self.running:
            return
        
        self.running = True
        
        # 启动工作线程
        for i in range(self.max_workers):
            worker = threading.Thread(target=self._worker, name=f"API-Worker-{i}")
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
        
        logger.info(f"API线程池已启动，工作线程数={len(self.workers)}")
    
    def stop(self):
        """停止线程池"""
        self.running = False
        
        # 等待所有任务完成
        while not self.task_queue.empty():
            time.sleep(0.1)
        
        # 等待所有工作线程完成
        for worker in self.workers:
            worker.join(timeout=5)
        
        logger.info("API线程池已停止")
    
    def _worker(self):
        """工作线程函数"""
        while self.running:
            try:
                # 从队列获取任务，设置超时避免无限等待
                task_data = self.task_queue.get(timeout=1)
                func, args, kwargs = task_data
                
                # 检查API调用限制
                while not self.api_limiter.check_limit():
                    logger.warning("达到API调用限制，等待中...")
                    time.sleep(5)  # 等待5秒后重试
                
                # 执行任务
                try:
                    result = func(*args, **kwargs)
                    self.result_queue.put(('success', result))
                    self.completed_tasks += 1
                    self.api_limiter.increment()
                    
                    # 添加随机延迟，避免请求过于集中
                    time.sleep(random.uniform(0.1, 0.5))
                    
                except Exception as e:
                    self.result_queue.put(('error', str(e)))
                    self.failed_tasks += 1
                    logger.error(f"任务执行失败: {e}")
                
                self.task_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"工作线程异常: {e}")
    
    def get_results(self) -> List[Any]:
        """获取所有结果"""
        results = []
        while not self.result_queue.empty():
            try:
                result_type, result = self.result_queue.get_nowait()
                results.append((result_type, result))
            except queue.Empty:
                break
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_tasks': self.total_tasks,
            'completed_tasks': self.completed_tasks,
            'failed_tasks': self.failed_tasks,
            'queue_size': self.task_queue.qsize(),
            'worker_count': len(self.workers),
            'api_usage': self.api_limiter.get_current_usage()
        }

def api_limiter(max_calls_per_minute: int = 60, max_calls_per_hour: int = 3600):
    """
    API调用限流装饰器
    
    Args:
        max_calls_per_minute: 每分钟最大调用次数
        max_calls_per_hour: 每小时最大调用次数
    """
    def decorator(func):
        limiter = APILimiter(max_calls_per_minute, max_calls_per_hour)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 检查调用限制
            while not limiter.check_limit():
                logger.warning(f"达到API调用限制，等待中... (当前: {limiter.get_current_usage()})")
                time.sleep(5)  # 等待5秒后重试
            
            try:
                result = func(*args, **kwargs)
                limiter.increment()
                return result
            except Exception as e:
                logger.error(f"API调用失败: {e}")
                raise
        
        return wrapper
    return decorator

def batch_processor(items: List[Any], process_func: Callable, 
                   batch_size: int = 10, delay: float = 1.0,
                   max_workers: int = 3) -> List[Any]:
    """
    批量处理器，避免一次性调用过多API
    
    Args:
        items: 待处理项目列表
        process_func: 处理函数
        batch_size: 批次大小
        delay: 批次间延迟（秒）
        max_workers: 最大并发数
    
    Returns:
        处理结果列表
    """
    results = []
    total_items = len(items)
    
    logger.info(f"开始批量处理: {total_items}个项目，批次大小={batch_size}")
    
    for i in range(0, total_items, batch_size):
        batch = items[i:i + batch_size]
        logger.info(f"处理批次 {i//batch_size + 1}/{(total_items + batch_size - 1)//batch_size}: {len(batch)}个项目")
        
        # 处理当前批次
        batch_results = []
        for item in batch:
            try:
                result = process_func(item)
                batch_results.append(result)
                
                # 添加延迟避免API调用过于频繁
                time.sleep(delay)
                
            except Exception as e:
                logger.error(f"处理项目失败: {e}")
                batch_results.append(None)
        
        results.extend(batch_results)
        
        # 批次间延迟
        if i + batch_size < total_items:
            logger.info(f"批次间延迟 {delay} 秒...")
            time.sleep(delay)
    
    logger.info(f"批量处理完成: {len(results)}/{total_items} 个项目成功处理")
    return results

def concurrent_processor(items: List[Any], process_func: Callable,
                       max_workers: int = 3, delay: float = 0.5) -> List[Any]:
    """
    并发处理器，控制并发数量和调用频率
    
    Args:
        items: 待处理项目列表
        process_func: 处理函数
        max_workers: 最大并发数
        delay: 并发任务间延迟（秒）
    
    Returns:
        处理结果列表
    """
    results = [None] * len(items)
    total_items = len(items)
    
    logger.info(f"开始并发处理: {total_items}个项目，最大并发数={max_workers}")
    
    def worker(start_idx, end_idx):
        for i in range(start_idx, end_idx):
            try:
                result = process_func(items[i])
                results[i] = result
                
                # 添加延迟避免API调用过于频繁
                time.sleep(delay)
                
            except Exception as e:
                logger.error(f"处理项目 {i} 失败: {e}")
                results[i] = None
    
    # 分配任务给工作线程
    threads = []
    items_per_thread = (total_items + max_workers - 1) // max_workers
    
    for i in range(max_workers):
        start_idx = i * items_per_thread
        end_idx = min((i + 1) * items_per_thread, total_items)
        
        if start_idx < total_items:
            thread = threading.Thread(target=worker, args=(start_idx, end_idx))
            thread.daemon = True
            thread.start()
            threads.append(thread)
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    logger.info(f"并发处理完成: {len([r for r in results if r is not None])}/{total_items} 个项目成功处理")
    return results

class APIMonitor:
    """API调用监控器"""
    
    def __init__(self):
        self.call_history = []
        self.error_history = []
        self.start_time = datetime.now()
    
    def log_call(self, api_name: str, success: bool, duration: float, error_msg: str = None):
        """记录API调用"""
        call_record = {
            'timestamp': datetime.now(),
            'api_name': api_name,
            'success': success,
            'duration': duration,
            'error_msg': error_msg
        }
        
        self.call_history.append(call_record)
        
        # 记录错误历史
        if not success and error_msg:
            self.error_history.append({
                'timestamp': datetime.now(),
                'api_name': api_name,
                'error_msg': error_msg
            })
        
        # 限制错误历史记录数量
        if len(self.error_history) > 100:
            self.error_history = self.error_history[-100:]
    
    def check_limit(self) -> bool:
        """检查API调用限制"""
        current_time = datetime.now()
        
        # 检查分钟限制
        minute_calls = len([c for c in self.call_history 
                          if (current_time - c['timestamp']).seconds < 60])
        
        # 检查小时限制
        hour_calls = len([c for c in self.call_history 
                        if (current_time - c['timestamp']).seconds < 3600])
        
        # 检查天限制
        day_calls = len([c for c in self.call_history 
                       if (current_time - c['timestamp']).days < 1])
        
        # 如果超过任何限制，返回False
        if minute_calls >= 30 or hour_calls >= 200 or day_calls >= 10000:
            return False
        
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_calls = len(self.call_history)
        successful_calls = len([c for c in self.call_history if c['success']])
        failed_calls = total_calls - successful_calls
        
        if total_calls > 0:
            success_rate = successful_calls / total_calls
            avg_duration = sum(c['duration'] for c in self.call_history) / total_calls
        else:
            success_rate = 0
            avg_duration = 0
        
        recent_errors = len([c for c in self.error_history 
                           if (datetime.now() - c['timestamp']).seconds < 3600])
        
        return {
            'total_calls': total_calls,
            'successful_calls': successful_calls,
            'failed_calls': failed_calls,
            'success_rate': success_rate,
            'avg_duration': avg_duration,
            'recent_errors': recent_errors,
            'uptime_seconds': (datetime.now() - self.start_time).seconds
        }
    
    def get_recent_errors(self, hours: int = 1) -> List[Dict[str, Any]]:
        """获取最近错误"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [c for c in self.error_history if c['timestamp'] > cutoff_time]

# 全局API监控器
global_api_monitor = APIMonitor()

def safe_api_call(api_func: Callable, api_name: str = "API", 
                 max_retries: int = 3, retry_delay: float = 5.0,
                 timeout: float = 30.0) -> Any:
    """
    安全的API调用，包含重试机制和错误处理
    
    Args:
        api_func: API调用函数
        api_name: API名称（用于日志）
        max_retries: 最大重试次数
        retry_delay: 重试延迟（秒）
        timeout: 超时时间（秒）
    
    Returns:
        API调用结果
    """
    start_time = time.time()
    
    for attempt in range(max_retries):
        try:
            logger.info(f"调用 {api_name} (尝试 {attempt + 1}/{max_retries})")
            
            # 检查API调用限制
            if not global_api_monitor.check_limit():
                logger.warning(f"达到API调用限制，等待中...")
                time.sleep(retry_delay)
                continue
            
            # 执行API调用
            result = api_func()
            
            # 记录成功调用
            duration = time.time() - start_time
            global_api_monitor.log_call(api_name, True, duration)
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            
            # 记录失败调用
            global_api_monitor.log_call(api_name, False, duration, error_msg)
            
            logger.error(f"API调用失败 (尝试 {attempt + 1}/{max_retries}): {error_msg}")
            
            if attempt < max_retries - 1:
                logger.info(f"等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
            else:
                logger.error(f"API调用失败，达到最大重试次数: {max_retries}")
                raise
    
    raise Exception(f"API调用失败，达到最大重试次数: {max_retries}")

if __name__ == "__main__":
    # 测试API限流器
    print("=== API限流器测试 ===")
    limiter = APILimiter(max_calls_per_minute=5, max_calls_per_hour=10)
    
    # 模拟API调用
    for i in range(8):
        if limiter.check_limit():
            limiter.increment()
            print(f"调用 {i+1}: 成功 (当前使用: {limiter.get_current_usage()})")
        else:
            print(f"调用 {i+1}: 被限制 (当前使用: {limiter.get_current_usage()})")
        time.sleep(1)
    
    # 测试批量处理器
    print("\n=== 批量处理器测试 ===")
    test_items = list(range(20))
    
    def mock_process(item):
        time.sleep(0.1)
        return item * 2
    
    results = batch_processor(test_items, mock_process, batch_size=5, delay=0.5)
    print(f"批量处理结果: {len(results)} 个项目")
    
    # 测试并发处理器
    print("\n=== 并发处理器测试 ===")
    results = concurrent_processor(test_items, mock_process, max_workers=2, delay=0.2)
    print(f"并发处理结果: {len(results)} 个项目")
    
    # 测试API监控
    print("\n=== API监控测试 ===")
    print(f"统计信息: {global_api_monitor.get_stats()}")
    print(f"最近错误: {global_api_monitor.get_recent_errors()}")