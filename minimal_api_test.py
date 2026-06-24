"""
minimal_api_test.py - 最小化API频率控制测试
只测试核心功能，避免任何超时
"""

import logging
from api_frequency_control import APILimiter, api_limiter, batch_processor, safe_api_call, APIMonitor

# 配置日志
logging.basicConfig(level=logging.WARNING)  # 减少日志输出

def test_core_functionality():
    """测试核心功能"""
    print("🚀 开始最小化API频率控制测试...")
    
    # 测试1: 基础限流器
    print("测试1: 基础限流器")
    limiter = APILimiter(max_calls_per_minute=2, max_calls_per_hour=5)
    
    success_count = 0
    for i in range(3):
        if limiter.check_limit():
            limiter.increment()
            success_count += 1
            print(f"✅ 调用 {i+1}: 成功")
        else:
            print(f"❌ 调用 {i+1}: 被限制")
    
    print(f"限流器测试结果: {success_count}/3 成功")
    
    # 测试2: 批量处理器
    print("测试2: 批量处理器")
    def process_item(x):
        return f"item_{x}"
    
    data = [1, 2, 3]
    results = batch_processor(data, process_item, batch_size=1, delay=0.01, max_workers=1)
    print(f"批量处理结果: {len(results)}/3 成功")
    
    # 测试3: 安全API调用
    print("测试3: 安全API调用")
    def simple_api(x):
        return f"result_{x}"
    
    result = safe_api_call(lambda: simple_api("test"), "test", max_retries=1)
    print(f"安全API调用结果: {result}")
    
    # 测试4: API监控
    print("测试4: API监控")
    monitor = APIMonitor()
    monitor.log_call("test", True, 0.1)
    stats = monitor.get_stats()
    print(f"API监控统计: {stats}")
    
    print("🎉 所有核心功能测试完成！")
    return True

if __name__ == "__main__":
    test_core_functionality()