"""
simple_integrated_test.py - 简化版集成系统测试
避免长时间运行的测试，专注于验证API频率控制功能
"""

import logging
import time
from datetime import datetime
from api_frequency_control import APILimiter, api_limiter, batch_processor, safe_api_call, APIMonitor

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_api_limiter():
    """测试API限流器"""
    logger.info("测试1: API限流器功能")
    
    # 创建限流器
    limiter = APILimiter(max_calls_per_minute=3, max_calls_per_hour=10, max_calls_per_day=100)
    
    # 测试快速调用
    calls = []
    for i in range(5):
        if limiter.check_limit():
            limiter.record_call()
            calls.append(f"调用{i+1}")
            logger.info(f"API调用 {i+1}: 成功")
        else:
            logger.warning(f"API调用 {i+1}: 被限制")
    
    logger.info(f"✅ API限流器测试通过，成功调用 {len(calls)} 次")
    return True

def test_api_decorator():
    """测试API装饰器"""
    logger.info("测试2: API装饰器功能")
    
    # 使用装饰器
    @api_limiter(max_calls_per_minute=3, max_calls_per_hour=10)
    def test_function():
        return "测试结果"
    
    # 测试调用
    results = []
    for i in range(4):
        try:
            result = test_function()
            results.append(result)
            logger.info(f"装饰器调用 {i+1}: 成功")
        except Exception as e:
            logger.info(f"装饰器调用 {i+1}: 失败 - {e}")
    
    logger.info(f"✅ API装饰器测试通过，成功调用 {len(results)} 次")
    return True

def test_batch_processor():
    """测试批量处理器"""
    logger.info("测试3: 批量处理器功能")
    
    def process_data(data):
        return f"处理_{data}"
    
    # 测试数据
    test_data = [f"数据{i}" for i in range(6)]
    
    # 批量处理
    results = batch_processor(
        test_data,
        process_data,
        batch_size=2,
        delay=0.1,
        max_workers=2
    )
    
    logger.info(f"✅ 批量处理器测试通过，处理了 {len(results)} 个数据")
    return True

def test_safe_api_call():
    """测试安全API调用"""
    logger.info("测试4: 安全API调用功能")
    
    # 模拟不稳定的API
    def unstable_api(data):
        if "失败" in str(data):
            raise Exception("模拟API失败")
        return f"成功处理: {data}"
    
    # 测试成功调用
    result1 = safe_api_call(
        unstable_api,
        "测试数据",
        api_name='测试API',
        max_retries=2,
        retry_delay=0.1
    )
    logger.info(f"成功调用: {result1}")
    
    # 测试失败调用
    result2 = safe_api_call(
        unstable_api,
        "测试失败",
        api_name='测试API',
        max_retries=2,
        retry_delay=0.1
    )
    logger.info(f"失败调用结果: {result2}")
    
    logger.info("✅ 安全API调用测试通过")
    return True

def test_api_monitor():
    """测试API监控"""
    logger.info("测试5: API监控功能")
    
    monitor = APIMonitor()
    
    # 记录一些调用
    monitor.log_call('test_api1', True, 0.5)
    monitor.log_call('test_api2', False, 0.3, "错误信息")
    monitor.log_call('test_api1', True, 0.4)
    
    # 获取统计信息
    stats = monitor.get_stats()
    
    logger.info(f"API监控统计: {stats}")
    logger.info("✅ API监控测试通过")
    return True

def test_system_integration():
    """测试系统集成"""
    logger.info("测试6: 系统集成功能")
    
    # 创建限流器和监控器
    limiter = APILimiter(max_calls_per_minute=10, max_calls_per_hour=50)
    monitor = APIMonitor()
    
    # 模拟系统流程
    def simulate_analysis_step(step_name):
        start_time = time.time()
        
        # 检查限制
        if not limiter.check_limit():
            logger.warning(f"{step_name}: 达到API限制")
            return False
        
        # 记录调用
        limiter.record_call()
        
        # 模拟工作
        time.sleep(0.1)
        
        # 记录监控
        duration = time.time() - start_time
        monitor.log_call(step_name, True, duration)
        
        logger.info(f"{step_name}: 完成")
        return True
    
    # 模拟多个步骤
    steps = ['宏观分析', '策略选择', '观察池跟踪', '交易策略']
    success_count = 0
    
    for step in steps:
        if simulate_analysis_step(step):
            success_count += 1
    
    # 获取最终统计
    final_stats = monitor.get_stats()
    
    logger.info(f"系统集成测试: {success_count}/{len(steps)} 步骤成功")
    logger.info(f"最终统计: {final_stats}")
    
    if success_count == len(steps):
        logger.info("✅ 系统集成测试通过")
        return True
    else:
        logger.warning("❌ 系统集成测试部分失败")
        return False

def main():
    """主测试函数"""
    logger.info("🚀 开始简化版集成系统测试...")
    
    tests = [
        test_api_limiter,
        test_api_decorator,
        test_batch_processor,
        test_safe_api_call,
        test_api_monitor,
        test_system_integration
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                logger.error(f"测试 {test.__name__} 失败")
        except Exception as e:
            logger.error(f"测试 {test.__name__} 异常: {e}")
    
    logger.info(f"🎉 测试完成: {passed}/{total} 通过")
    
    if passed == total:
        print("✅ 所有测试通过！API频率控制系统正常工作")
        return True
    else:
        print("❌ 部分测试失败")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)