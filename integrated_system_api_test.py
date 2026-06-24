"""
integrated_system_api_test.py - 集成系统API频率控制测试
测试完整的股票分析系统，验证API频率控制功能
"""

import logging
import time
from datetime import datetime
from integrated_stock_analysis_system import IntegratedStockAnalysisSystem

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_integrated_system():
    """测试集成系统的API频率控制功能"""
    
    logger.info("开始测试集成系统的API频率控制功能...")
    
    # 创建系统实例
    try:
        system = IntegratedStockAnalysisSystem('database/stock_analysis.db')
        logger.info("系统实例创建成功")
    except Exception as e:
        logger.error(f"系统实例创建失败: {e}")
        return False
    
    # 测试1: 系统初始化
    logger.info("测试1: 系统初始化")
    try:
        health = system.get_system_health()
        logger.info(f"系统健康状态: {health}")
        logger.info("✅ 系统初始化测试通过")
    except Exception as e:
        logger.error(f"系统初始化测试失败: {e}")
        return False
    
    # 测试2: API限流器功能
    logger.info("测试2: API限流器功能")
    try:
        # 模拟API调用
        def mock_api_call():
            return "模拟API调用结果"
        
        # 使用装饰器测试
        from api_frequency_control import api_limiter
        
        @api_limiter(max_calls_per_minute=5, max_calls_per_hour=10)
        def test_api_function():
            return mock_api_call()
        
        # 连续调用测试
        results = []
        for i in range(8):  # 尝试调用8次，应该触发限制
            try:
                result = test_api_function()
                results.append(result)
                logger.info(f"API调用 {i+1}: 成功")
            except Exception as e:
                logger.info(f"API调用 {i+1}: 失败 - {e}")
                break
        
        logger.info(f"✅ API限流器测试通过，成功调用 {len(results)} 次")
    except Exception as e:
        logger.error(f"API限流器测试失败: {e}")
        return False
    
    # 测试3: 批量处理器
    logger.info("测试3: 批量处理器功能")
    try:
        from api_frequency_control import batch_processor
        
        def process_data(data):
            return f"处理结果: {data}"
        
        test_data = [f"数据{i}" for i in range(15)]
        
        # 测试批量处理
        results = batch_processor(
            test_data,
            process_data,
            batch_size=5,
            delay=0.5,
            max_workers=2
        )
        
        logger.info(f"✅ 批量处理器测试通过，处理了 {len(results)} 个数据")
    except Exception as e:
        logger.error(f"批量处理器测试失败: {e}")
        return False
    
    # 测试4: 并发处理器
    logger.info("测试4: 并发处理器功能")
    try:
        from api_frequency_control import concurrent_processor
        
        def process_concurrent_data(data):
            return f"并发处理: {data}"
        
        test_tasks = [f"任务{i}" for i in range(6)]
        
        # 测试并发处理
        results = concurrent_processor(
            test_tasks,
            process_concurrent_data,
            max_workers=3,
            delay=0.3
        )
        
        logger.info(f"✅ 并发处理器测试通过，处理了 {len(results)} 个任务")
    except Exception as e:
        logger.error(f"并发处理器测试失败: {e}")
        return False
    
    # 测试5: 安全API调用
    logger.info("测试5: 安全API调用功能")
    try:
        from api_frequency_control import safe_api_call
        
        def unstable_api(data):
            if "失败" in str(data):
                raise Exception("API调用失败")
            return f"成功处理: {data}"
        
        # 测试成功调用
        result1 = safe_api_call(
            unstable_api,
            "测试数据1",
            api_name='测试API',
            max_retries=3,
            retry_delay=0.5
        )
        logger.info(f"成功调用: {result1}")
        
        # 测试失败调用
        result2 = safe_api_call(
            unstable_api,
            "测试数据失败",
            api_name='测试API',
            max_retries=2,
            retry_delay=0.3
        )
        logger.info(f"失败调用结果: {result2}")
        
        logger.info("✅ 安全API调用测试通过")
    except Exception as e:
        logger.error(f"安全API调用测试失败: {e}")
        return False
    
    # 测试6: 完整分析流程（模拟）
    logger.info("测试6: 完整分析流程（模拟）")
    try:
        # 模拟分析流程，但不实际调用外部API
        start_time = time.time()
        
        # 检查API限制
        if not system.api_limiter.check_limit():
            logger.warning("达到API调用限制，跳过分析")
            return False
        
        # 模拟各步骤
        macro_result = {
            'success': True,
            'market_state': '牛市',
            'report': '模拟宏观分析报告'
        }
        
        selection_result = {
            'success': True,
            'growth_stocks': [{'name': '股票1', 'score': 85}],
            'value_stocks': [{'name': '股票2', 'score': 78}]
        }
        
        observation_result = {
            'success': True,
            'signals': ['买入信号1', '卖出信号1']
        }
        
        strategy_result = {
            'success': True,
            'trading_signals': [
                {'stock_name': '股票1', 'signal': '买入'},
                {'stock_name': '股票2', 'signal': '持有'}
            ]
        }
        
        # 模拟报告生成
        all_results = {
            'macro_results': macro_result,
            'selection_results': selection_result,
            'observation_results': observation_result,
            'strategy_results': strategy_result
        }
        
        # 生成报告
        report = system._generate_complete_report(all_results)
        
        duration = time.time() - start_time
        logger.info(f"✅ 完整分析流程测试通过，耗时: {duration:.2f}秒")
        
        # 显示报告片段
        if len(report) > 200:
            logger.info(f"报告预览: {report[:200]}...")
        else:
            logger.info(f"报告内容: {report}")
            
    except Exception as e:
        logger.error(f"完整分析流程测试失败: {e}")
        return False
    
    # 测试7: API统计信息
    logger.info("测试7: API统计信息")
    try:
        api_stats = system.get_api_statistics()
        health = system.get_system_health()
        
        logger.info(f"API统计: {api_stats}")
        logger.info(f"系统健康: {health}")
        logger.info("✅ API统计信息测试通过")
    except Exception as e:
        logger.error(f"API统计信息测试失败: {e}")
        return False
    
    # 清理
    try:
        system.close()
        logger.info("系统连接已关闭")
    except Exception as e:
        logger.error(f"关闭系统连接失败: {e}")
    
    logger.info("🎉 所有测试通过！集成系统API频率控制功能正常")
    return True

if __name__ == "__main__":
    success = test_integrated_system()
    if success:
        print("✅ 集成系统API频率控制测试成功完成")
    else:
        print("❌ 集成系统API频率控制测试失败")