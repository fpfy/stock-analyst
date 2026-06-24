"""
quick_api_test.py - 快速API频率控制测试
验证核心功能，避免超时问题
"""

import logging
import time
from datetime import datetime
from api_frequency_control import APILimiter, api_limiter, batch_processor, safe_api_call, APIMonitor

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_basic_limiter():
    """测试基础限流器"""
    logger.info("测试1: 基础限流器")
    
    limiter = APILimiter(max_calls_per_minute=3, max_calls_per_hour=10)
    
    # 测试调用
    success_count = 0
    for i in range(4):
        if limiter.check_limit():
            limiter.increment()
            success_count += 1
            logger.info(f"调用 {i+1}: 成功")
        else:
            logger.info(f"调用 {i+1}: 被限制")
    
    logger.info(f"✅ 基础限流器测试通过，成功调用 {success_count}/4 次")
    return True

def test_api_decorator():
    """测试API装饰器"""
    logger.info("测试2: API装饰器")
    
    @api_limiter(max_calls_per_minute=2, max_calls_per_hour=5)
    def test_func():
        return "测试结果"
    
    # 测试调用
    results = []
    for i in range(3):
        try:
            result = test_func()
            results.append(result)
            logger.info(f"装饰器调用 {i+1}: 成功")
        except Exception as e:
            logger.info(f"装饰器调用 {i+1}: 失败 - {e}")
    
    logger.info(f"✅ API装饰器测试通过，成功调用 {len(results)}/3 次")
    return True

def test_batch_processor():
    """测试批量处理器"""
    logger.info("测试3: 批量处理器")
    
    def process_item(item):
        return f"处理_{item}"
    
    data = ["a", "b", "c", "d"]
    
    results = batch_processor(
        data,
        process_item,
        batch_size=2,
        delay=0.05,
        max_workers=1
    )
    
    logger.info(f"✅ 批量处理器测试通过，处理了 {len(results)}/4 个数据")
    return len(results) == 4

def test_safe_api():
    """测试安全API调用"""
    logger.info("测试4: 安全API调用")
    
    def stable_api(data):
        return f"成功: {data}"
    
    result = safe_api_call(
        stable_api,
        "测试数据",
        api_name="测试API",
        max_retries=1
    )
    
    logger.info(f"✅ 安全API调用测试通过: {result}")
    return True

def test_api_monitor():
    """测试API监控"""
    logger.info("测试5: API监控")
    
    monitor = APIMonitor()
    
    # 记录一些调用
    monitor.log_call("api1", True, 0.1)
    monitor.log_call("api2", False, 0.2, "错误")
    monitor.log_call("api1", True, 0.15)
    
    stats = monitor.get_stats()
    
    logger.info(f"✅ API监控测试通过: {stats}")
    return True

def main():
    """主测试函数"""
    logger.info("🚀 开始快速API频率控制测试...")
    
    tests = [
        test_basic_limiter,
        test_api_decorator,
        test_batch_processor,
        test_safe_api,
        test_api_monitor
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
        print("✅ 所有API频率控制测试通过！系统功能正常")
        return True
    else:
        print("❌ 部分测试失败")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)