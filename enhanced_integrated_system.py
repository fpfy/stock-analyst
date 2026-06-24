"""
enhanced_integrated_system.py - 增强版股票分析及交易策略系统
集成API频率控制，解决调用超限问题
"""

import logging
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json
import time

# 导入API频率控制模块
from api_frequency_control import (
    APILimiter, 
    api_limiter, 
    batch_processor, 
    concurrent_processor, 
    APIMonitor,
    safe_api_call
)

from macro_market_analyzer import MacroMarketAnalyzer
from dual_strategy_selector import DualStrategySelector
from observation_pool_tracker import ObservationPoolTracker
from comprehensive_trading_strategy import ComprehensiveTradingStrategy

logger = logging.getLogger(__name__)

class EnhancedIntegratedStockAnalysisSystem:
    """增强版股票分析及交易策略系统"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化增强版系统
        
        Args:
            config: 系统配置
        """
        self.config = config or self._get_default_config()
        
        # 初始化API限流器
        self.api_limiter = APILimiter(
            max_calls_per_minute=self.config.get('minute_limit', 30),
            max_calls_per_hour=self.config.get('hour_limit', 200),
            max_calls_per_day=self.config.get('day_limit', 1000)
        )
        
        # 初始化API监控系统
        self.api_monitor = APIMonitor()
        
        # 初始化各个分析模块
        db_path = self.config.get('db_path', 'database/stock_analysis.db') if self.config else 'database/stock_analysis.db'
        macro_config = self.config.get('macro_config', {}) if self.config else {}
        strategy_config = self.config.get('strategy_config', {}) if self.config else {}
        observation_config = self.config.get('observation_config', {}) if self.config else {}
        trading_config = self.config.get('trading_config', {}) if self.config else {}
        
        self.macro_analyzer = MacroMarketAnalyzer(db_path)
        self.strategy_selector = DualStrategySelector(db_path)
        self.observation_tracker = ObservationPoolTracker(db_path)
        self.trading_strategy = ComprehensiveTradingStrategy(db_path)
        
        # 统计信息
        self.total_analysis_count = 0
        self.successful_analysis_count = 0
        self.failed_analysis_count = 0
        
        logger.info("增强版股票分析系统初始化完成")
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            'minute_limit': 30,      # 每分钟API调用限制
            'hour_limit': 200,       # 每小时API调用限制
            'day_limit': 1000,       # 每天API调用限制
            'batch_size': 10,        # 批次大小
            'batch_delay': 1.0,      # 批次间延迟
            'max_workers': 3,       # 最大并发数
            'macro_config': {
                'use_ai_analysis': True,
                'ai_analysis_limit': 5  # 宏观分析AI调用限制
            },
            'strategy_config': {
                'use_ai_analysis': True,
                'ai_analysis_limit': 20  # 选股策略AI调用限制
            },
            'observation_config': {
                'use_ai_analysis': True,
                'ai_analysis_limit': 15  # 观察池AI调用限制
            },
            'trading_config': {
                'use_ai_analysis': True,
                'ai_analysis_limit': 10  # 交易策略AI调用限制
            }
        }
    
    @api_limiter(max_calls_per_minute=30, max_calls_per_hour=200)
    def run_macro_analysis(self, date: Optional[str] = None) -> Dict:
        """
        运行宏观分析，带API限流
        
        Args:
            date: 分析日期
            
        Returns:
            宏观分析结果
        """
        logger.info(f"开始宏观分析，日期: {date}")
        
        start_time = time.time()
        
        try:
            # 检查API调用限制
            if not self.api_limiter.check_limit():
                logger.warning("达到API调用限制，等待中...")
                time.sleep(5)
                return {"error": "API调用限制", "status": "limited"}
            
            # 执行宏观分析
            result = self.macro_analyzer.generate_analysis_report()
            
            # 记录成功调用
            duration = time.time() - start_time
            self.api_monitor.log_call('macro_analysis', True, duration)
            self.api_limiter.increment()
            
            self.total_analysis_count += 1
            self.successful_analysis_count += 1
            
            logger.info(f"宏观分析完成，耗时: {duration:.2f}秒")
            return result
            
        except Exception as e:
            # 记录失败调用
            duration = time.time() - start_time
            self.api_monitor.log_call('macro_analysis', False, duration, str(e))
            
            self.total_analysis_count += 1
            self.failed_analysis_count += 1
            
            logger.error(f"宏观分析失败: {e}")
            return {"error": str(e), "status": "failed"}
    
    def run_strategy_selection(self, macro_result: Dict, date: Optional[str] = None) -> Dict:
        """
        运行策略选择，带API限流
        
        Args:
            macro_result: 宏观分析结果（暂时不使用）
            date: 分析日期
            
        Returns:
            策略选择结果
        """
        logger.info(f"开始策略选择，日期: {date}")
        
        start_time = time.time()
        
        try:
            # 检查API调用限制
            if not self.api_limiter.check_limit():
                logger.warning("达到API调用限制，等待中...")
                time.sleep(5)
                return {"error": "API调用限制", "status": "limited"}
            
            # 执行策略选择
            result = self.strategy_selector.run_dual_strategy_selection()
            
            # 记录成功调用
            duration = time.time() - start_time
            self.api_monitor.log_call('strategy_selection', True, duration)
            self.api_limiter.increment()
            
            self.total_analysis_count += 1
            self.successful_analysis_count += 1
            
            logger.info(f"策略选择完成，耗时: {duration:.2f}秒")
            return result
            
        except Exception as e:
            # 记录失败调用
            duration = time.time() - start_time
            self.api_monitor.log_call('strategy_selection', False, duration, str(e))
            
            self.total_analysis_count += 1
            self.failed_analysis_count += 1
            
            logger.error(f"策略选择失败: {e}")
            return {"error": str(e), "status": "failed"}
    
    def batch_strategy_selection(self, macro_result: Dict, date: Optional[str] = None) -> Dict:
        """
        批量策略选择，避免API调用超限
        
        Args:
            macro_result: 宏观分析结果
            date: 分析日期
            
        Returns:
            策略选择结果
        """
        logger.info(f"开始批量策略选择，日期: {date}")
        
        def single_strategy_selection(macro_data):
            """单个策略选择"""
            return self.run_strategy_selection(macro_data, date)
        
        # 使用批量处理器
        results = batch_processor(
            [macro_result],  # 输入数据
            single_strategy_selection,
            batch_size=self.config['batch_size'],
            delay=self.config['batch_delay'],
            max_workers=self.config['max_workers']
        )
        
        return results[0] if results else {"error": "批量处理失败", "status": "failed"}
    
    @api_limiter(max_calls_per_minute=30, max_calls_per_hour=200)
    def run_observation_tracking(self, strategy_result: Dict, date: Optional[str] = None) -> Dict:
        """
        运行观察池跟踪，带API限流
        
        Args:
            strategy_result: 策略选择结果
            date: 分析日期
            
        Returns:
            观察池跟踪结果
        """
        logger.info(f"开始观察池跟踪，日期: {date}")
        
        start_time = time.time()
        
        try:
            # 检查API调用限制
            if not self.api_limiter.check_limit():
                logger.warning("达到API调用限制，等待中...")
                time.sleep(5)
                return {"error": "API调用限制", "status": "limited"}
            
            # 执行观察池跟踪
            result = self.observation_tracker.track_observation_pool(strategy_result, date)
            
            # 记录成功调用
            duration = time.time() - start_time
            self.api_monitor.log_call('observation_tracking', True, duration)
            self.api_limiter.increment()
            
            self.total_analysis_count += 1
            self.successful_analysis_count += 1
            
            logger.info(f"观察池跟踪完成，耗时: {duration:.2f}秒")
            return result
            
        except Exception as e:
            # 记录失败调用
            duration = time.time() - start_time
            self.api_monitor.log_call('observation_tracking', False, duration, str(e))
            
            self.total_analysis_count += 1
            self.failed_analysis_count += 1
            
            logger.error(f"观察池跟踪失败: {e}")
            return {"error": str(e), "status": "failed"}
    
    def batch_observation_tracking(self, strategy_result: Dict, date: Optional[str] = None) -> Dict:
        """
        批量观察池跟踪，避免API调用超限
        
        Args:
            strategy_result: 策略选择结果
            date: 分析日期
            
        Returns:
            观察池跟踪结果
        """
        logger.info(f"开始批量观察池跟踪，日期: {date}")
        
        def single_observation_tracking(strategy_data):
            """单个观察池跟踪"""
            return self.run_observation_tracking(strategy_data, date)
        
        # 使用批量处理器
        results = batch_processor(
            [strategy_result],  # 输入数据
            single_observation_tracking,
            batch_size=self.config['batch_size'],
            delay=self.config['batch_delay'],
            max_workers=self.config['max_workers']
        )
        
        return results[0] if results else {"error": "批量处理失败", "status": "failed"}
    
    @api_limiter(max_calls_per_minute=30, max_calls_per_hour=200)
    def run_trading_strategy(self, observation_result: Dict, date: Optional[str] = None) -> Dict:
        """
        运行交易策略，带API限流
        
        Args:
            observation_result: 观察池跟踪结果
            date: 分析日期
            
        Returns:
            交易策略结果
        """
        logger.info(f"开始交易策略分析，日期: {date}")
        
        start_time = time.time()
        
        try:
            # 检查API调用限制
            if not self.api_limiter.check_limit():
                logger.warning("达到API调用限制，等待中...")
                time.sleep(5)
                return {"error": "API调用限制", "status": "limited"}
            
            # 执行交易策略
            result = self.trading_strategy.generate_trading_strategy(observation_result, date)
            
            # 记录成功调用
            duration = time.time() - start_time
            self.api_monitor.log_call('trading_strategy', True, duration)
            self.api_limiter.increment()
            
            self.total_analysis_count += 1
            self.successful_analysis_count += 1
            
            logger.info(f"交易策略分析完成，耗时: {duration:.2f}秒")
            return result
            
        except Exception as e:
            # 记录失败调用
            duration = time.time() - start_time
            self.api_monitor.log_call('trading_strategy', False, duration, str(e))
            
            self.total_analysis_count += 1
            self.failed_analysis_count += 1
            
            logger.error(f"交易策略分析失败: {e}")
            return {"error": str(e), "status": "failed"}
    
    def batch_trading_strategy(self, observation_result: Dict, date: Optional[str] = None) -> Dict:
        """
        批量交易策略分析，避免API调用超限
        
        Args:
            observation_result: 观察池跟踪结果
            date: 分析日期
            
        Returns:
            交易策略结果
        """
        logger.info(f"开始批量交易策略分析，日期: {date}")
        
        def single_trading_strategy(observation_data):
            """单个交易策略分析"""
            return self.run_trading_strategy(observation_data, date)
        
        # 使用批量处理器
        results = batch_processor(
            [observation_result],  # 输入数据
            single_trading_strategy,
            batch_size=self.config['batch_size'],
            delay=self.config['batch_delay'],
            max_workers=self.config['max_workers']
        )
        
        return results[0] if results else {"error": "批量处理失败", "status": "failed"}
    
    def run_complete_analysis(self, date: Optional[str] = None) -> Dict:
        """
        运行完整分析流程，包含API频率控制
        
        Args:
            date: 分析日期
            
        Returns:
            完整分析结果
        """
        logger.info(f"开始完整分析流程，日期: {date}")
        
        start_time = time.time()
        
        try:
            # 第一步：宏观分析
            logger.info("第一步：宏观分析")
            macro_result = self.run_macro_analysis(date)
            if macro_result.get('status') == 'failed':
                return macro_result
            
            # 第二步：策略选择
            logger.info("第二步：策略选择")
            strategy_result = self.batch_strategy_selection(macro_result, date)
            if strategy_result.get('status') == 'failed':
                return strategy_result
            
            # 第三步：观察池跟踪
            logger.info("第三步：观察池跟踪")
            observation_result = self.batch_observation_tracking(strategy_result, date)
            if observation_result.get('status') == 'failed':
                return observation_result
            
            # 第四步：交易策略
            logger.info("第四步：交易策略")
            trading_result = self.batch_trading_strategy(observation_result, date)
            if trading_result.get('status') == 'failed':
                return trading_result
            
            # 记录完整分析成功
            duration = time.time() - start_time
            logger.info(f"完整分析流程完成，总耗时: {duration:.2f}秒")
            
            return {
                "status": "success",
                "macro_analysis": macro_result,
                "strategy_selection": strategy_result,
                "observation_tracking": observation_result,
                "trading_strategy": trading_result,
                "duration": duration,
                "analysis_date": date or datetime.now().strftime('%Y-%m-%d')
            }
            
        except Exception as e:
            logger.error(f"完整分析流程失败: {e}")
            return {"error": str(e), "status": "failed"}
    
    def get_system_stats(self) -> Dict:
        """获取系统统计信息"""
        api_stats = self.api_monitor.get_stats()
        limiter_stats = self.api_limiter.get_current_usage()
        
        return {
            "total_analysis_count": self.total_analysis_count,
            "successful_analysis_count": self.successful_analysis_count,
            "failed_analysis_count": self.failed_analysis_count,
            "success_rate": self.successful_analysis_count / max(self.total_analysis_count, 1),
            "api_stats": api_stats,
            "limiter_stats": limiter_stats,
            "config": self.config
        }
    
    def check_system_health(self) -> Dict:
        """检查系统健康状态"""
        stats = self.get_system_stats()
        
        health_status = {
            "overall_status": "healthy",
            "issues": [],
            "warnings": []
        }
        
        # 检查API成功率
        if stats['success_rate'] < 0.9:
            health_status["overall_status"] = "degraded"
            health_status["issues"].append(f"API成功率过低: {stats['success_rate']:.2%}")
        
        # 检查API错误
        if stats['api_stats']['recent_errors'] > 10:
            health_status["overall_status"] = "degraded"
            health_status["issues"].append(f"API错误过多: {stats['api_stats']['recent_errors']}")
        
        # 检查API使用率
        usage_rate = stats['limiter_stats']['minute_calls'] / stats['limiter_stats']['max_minute']
        if usage_rate > 0.8:
            health_status["warnings"].append(f"API使用率过高: {usage_rate:.2%}")
        
        return health_status
    
    def reset_stats(self):
        """重置统计信息"""
        self.total_analysis_count = 0
        self.successful_analysis_count = 0
        self.failed_analysis_count = 0
        self.api_monitor = APIMonitor()
        logger.info("系统统计信息已重置")


def test_enhanced_system():
    """测试增强版系统"""
    logger.info("开始测试增强版股票分析系统")
    
    # 创建系统实例
    system = EnhancedIntegratedStockAnalysisSystem()
        
    # 测试配置
    test_config = {
        'max_calls_per_minute': 5,    # 降低限制用于测试
        'max_calls_per_hour': 20,
        'max_calls_per_day': 100,
        'batch_size': 2,
        'batch_delay': 0.5,
        'max_workers': 2
    }
        
    system.api_limiter = APILimiter(
        max_calls_per_minute=test_config['max_calls_per_minute'],
        max_calls_per_hour=test_config['max_calls_per_hour'],
        max_calls_per_day=test_config['max_calls_per_day']
    )
    
    try:
        # 运行完整分析流程
        result = system.run_complete_analysis()
        
        if result.get('status') == 'success':
            logger.info("✅ 增强版系统测试成功")
            print("🎉 增强版系统测试成功！")
            print(f"📊 分析结果: {result}")
        else:
            logger.error(f"❌ 增强版系统测试失败: {result}")
            print(f"❌ 增强版系统测试失败: {result}")
        
        # 获取系统统计信息
        stats = system.get_system_stats()
        print(f"📈 系统统计信息: {stats}")
        
        # 检查系统健康状态
        health = system.check_system_health()
        print(f"🏥 系统健康状态: {health}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ 增强版系统测试异常: {e}")
        print(f"❌ 增强版系统测试异常: {e}")
        return {"error": str(e), "status": "failed"}


if __name__ == "__main__":
    test_enhanced_system()