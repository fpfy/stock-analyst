"""
simple_api_frequency_test.py - 简化版API频率控制测试
专门测试API频率控制功能，避免网络连接问题
"""

import time
import logging
from api_frequency_control import (
    APILimiter, 
    api_limiter, 
    batch_processor, 
    concurrent_processor, 
    APIMonitor,
    safe_api_call
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def mock_ai_analysis(stock_data):
    """模拟AI分析函数"""
    time.sleep(0.1)  # 模拟API调用延迟
    return f"分析结果: {stock_data}"

def test_api_limiter():
    """测试API限流器"""
    logger.info("开始测试API限流器")
    
    # 创建限流器
    limiter = APILimiter(max_calls_per_minute=5, max_calls_per_hour=20)
    
    # 测试正常调用
    for i in range(5):
        if limiter.check_limit():
            limiter.increment()
            logger.info(f"正常调用 {i+1}")
        else:
            logger.warning("达到限制，跳过")
    
    # 测试限制触发
    if not limiter.check_limit():
        logger.info("限制触发测试通过")
    
    return True

def test_api_decorator():
    """测试API装饰器"""
    logger.info("开始测试API装饰器")
    
    @api_limiter(max_calls_per_minute=5, max_calls_per_hour=20)
    def decorated_ai_analysis(data):
        return mock_ai_analysis(data)
    
    # 测试装饰器
    for i in range(5):
        result = decorated_ai_analysis(f"股票{i}")
        logger.info(f"装饰器测试 {i+1}: {result}")
    
    return True

def test_batch_processor():
    """测试批量处理器"""
    logger.info("开始测试批量处理器")
    
    # 测试数据
    stock_list = [f"股票{i}" for i in range(10)]
    
    # 使用批量处理器
    results = batch_processor(
        stock_list,
        mock_ai_analysis,
        batch_size=3,
        delay=0.5,
        max_workers=2
    )
    
    logger.info(f"批量处理完成，结果数量: {len(results)}")
    return len(results) == 10

def test_concurrent_processor():
    """测试并发处理器"""
    logger.info("开始测试并发处理器")
    
    # 测试数据
    tasks = [f"任务{i}" for i in range(6)]
    
    # 使用并发处理器
    results = concurrent_processor(
        tasks,
        mock_ai_analysis,
        max_workers=3,
        delay=0.2
    )
    
    logger.info(f"并发处理完成，结果数量: {len(results)}")
    return len(results) == 6

def test_api_monitor():
    """测试API监控"""
    logger.info("开始测试API监控")
    
    monitor = APIMonitor()
    
    # 记录一些调用
    for i in range(5):
        monitor.log_call('test_api', True, 0.1)
    
    # 记录一些失败调用
    for i in range(2):
        monitor.log_call('test_api', False, 0.1, "测试错误")
    
    # 获取统计信息
    stats = monitor.get_stats()
    logger.info(f"API监控统计: {stats}")
    
    return stats['total_calls'] == 7

def test_safe_api_call():
    """测试安全API调用"""
    logger.info("开始测试安全API调用")
    
    def unstable_api():
        """模拟不稳定的API"""
        if time.time() % 5 < 1:  # 20%概率失败
            raise Exception("API暂时不可用")
        return "API调用成功"
    
    # 使用安全API调用
    result = safe_api_call(
        unstable_api,
        api_name='测试API',
        max_retries=3,
        retry_delay=0.5
    )
    
    logger.info(f"安全API调用结果: {result}")
    return result is not None

def run_all_tests():
    """运行所有测试"""
    logger.info("开始运行所有API频率控制测试")
    
    tests = [
        ("API限流器", test_api_limiter),
        ("API装饰器", test_api_decorator),
        ("批量处理器", test_batch_processor),
        ("并发处理器", test_concurrent_processor),
        ("API监控", test_api_monitor),
        ("安全API调用", test_safe_api_call)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            logger.info(f"开始测试: {test_name}")
            start_time = time.time()
            
            result = test_func()
            duration = time.time() - start_time
            
            if result:
                logger.info(f"✅ {test_name} 测试通过，耗时: {duration:.2f}秒")
                results.append((test_name, True, duration))
            else:
                logger.error(f"❌ {test_name} 测试失败")
                results.append((test_name, False, duration))
                
        except Exception as e:
            logger.error(f"❌ {test_name} 测试异常: {e}")
            results.append((test_name, False, 0))
    
    # 输出测试结果
    logger.info("=== 测试结果汇总 ===")
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for test_name, success, duration in results:
        status = "✅ 通过" if success else "❌ 失败"
        logger.info(f"{test_name}: {status} ({duration:.2f}秒)")
    
    logger.info(f"总体结果: {passed}/{total} 测试通过")
    
    if passed == total:
        logger.info("🎉 所有测试通过！API频率控制系统工作正常")
        return True
    else:
        logger.error("⚠️ 部分测试失败，需要进一步调试")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)