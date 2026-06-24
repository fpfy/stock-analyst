"""
integrated_stock_analysis_system.py - 股票分析及交易策略系统集成模块
完整实现3步流程：宏观分析→双策略选股→观察池跟踪+综合交易策略
集成API频率控制，防止调用超限
"""

import logging
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json
import time

from macro_market_analyzer import MacroMarketAnalyzer
from dual_strategy_selector import DualStrategySelector
from observation_pool_tracker import ObservationPoolTracker
from comprehensive_trading_strategy import ComprehensiveTradingStrategy
from api_frequency_control import APILimiter, api_limiter, batch_processor, APIMonitor

logger = logging.getLogger(__name__)

class IntegratedStockAnalysisSystem:
    """集成股票分析系统"""
    
    def __init__(self, db_path: str = "database/stock_analysis.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # 初始化API频率控制
        self.api_limiter = APILimiter(
            max_calls_per_minute=30,    # 每分钟30次
            max_calls_per_hour=200,     # 每小时200次
            max_calls_per_day=10000     # 每天10000次
        )
        self.api_monitor = APIMonitor()
        
        # 初始化各个模块
        self.macro_analyzer = MacroMarketAnalyzer(db_path)
        self.dual_selector = DualStrategySelector(db_path)
        self.observation_tracker = ObservationPoolTracker(db_path)
        self.strategy_generator = ComprehensiveTradingStrategy(db_path)
        
        # 系统配置
        self.config = {
            'enable_growth_strategy': True,
            'enable_value_strategy': True,
            'max_stocks_per_strategy': 20,
            'min_score_threshold': 70,
            'update_frequency': 1,  # 天
            'auto_save_results': True,
            # API频率控制配置
            'api_config': {
                'max_calls_per_minute': 30,
                'max_calls_per_hour': 200,
                'max_calls_per_day': 10000,
                'batch_size': 10,
                'batch_delay': 1.0,
                'max_workers': 3
            }
        }
        
        # 系统运行状态
        self.system_status = {
            'last_run_time': None,
            'last_run_status': 'idle',
            'total_processed_stocks': 0,
            'successful_runs': 0,
            'failed_runs': 0,
            'api_calls_count': 0,
            'api_success_rate': 0.0
        }
        
        # 统计信息
        self.total_analysis_count = 0
        self.successful_analysis_count = 0
        self.failed_analysis_count = 0
        
    def run_full_analysis_pipeline(self) -> Dict:
        """运行完整的分析流程"""
        try:
            logger.info("开始运行完整的股票分析流程...")
            
            # 1. 宏观经济与大盘分析
            logger.info("步骤1: 宏观经济与大盘分析")
            macro_results = self._run_macro_analysis()
            
            # 2. 双策略选股
            logger.info("步骤2: 双策略选股")
            selection_results = self._run_dual_strategy_selection(macro_results)
            
            # 3. 观察池跟踪
            logger.info("步骤3: 观察池跟踪")
            observation_results = self._run_observation_tracking(selection_results)
            
            # 4. 综合交易策略生成
            logger.info("步骤4: 综合交易策略生成")
            strategy_results = self._run_comprehensive_strategy(observation_results)
            
            # 5. 生成完整报告
            logger.info("步骤5: 生成完整报告")
            final_report = self._generate_complete_report({
                'macro_results': macro_results,
                'selection_results': selection_results,
                'observation_results': observation_results,
                'strategy_results': strategy_results
            })
            
            # 6. 保存系统状态
            self._save_system_status('success')
            
            logger.info("完整分析流程执行完成")
            
            return {
                'success': True,
                'report': final_report,
                'macro_results': macro_results,
                'selection_results': selection_results,
                'observation_results': observation_results,
                'strategy_results': strategy_results,
                'system_status': self.system_status
            }
            
        except Exception as e:
            logger.error(f"完整分析流程执行失败: {e}")
            self._save_system_status('failed')
            return {
                'success': False,
                'error': str(e),
                'system_status': self.system_status
            }
            
    def _run_macro_analysis(self) -> Dict:
        """运行宏观经济分析，带API限流"""
        try:
            start_time = time.time()
            
            # 检查API调用限制
            if not self.api_limiter.check_limit():
                logger.warning("达到API调用限制，跳过宏观分析")
                return {'success': False, 'error': 'API调用限制达到'}
            
            # 获取宏观数据
            self.macro_analyzer.fetch_all_macro_data()
            
            # 使用API限流器包装宏观分析
            @api_limiter(max_calls_per_minute=30, max_calls_per_hour=200)
            def analyze_macro_data():
                return self.macro_analyzer.analyze_market()
            
            macro_result = analyze_macro_data()
            
            # 记录API调用
            duration = time.time() - start_time
            self.api_monitor.log_call('macro_analysis', True, duration)
            
            # 更新统计信息
            self.total_analysis_count += 1
            self.successful_analysis_count += 1
            
            logger.info(f"宏观分析完成，耗时: {duration:.2f}秒")
            return macro_result
            
        except Exception as e:
            duration = time.time() - start_time
            self.api_monitor.log_call('macro_analysis', False, duration, str(e))
            
            # 更新统计信息
            self.total_analysis_count += 1
            self.failed_analysis_count += 1
            
            logger.error(f"宏观分析失败: {e}")
            return {'success': False, 'error': str(e)}
            
    def _run_dual_strategy_selection(self, macro_results: Dict) -> Dict:
        """运行双策略选股，带API限流"""
        try:
            start_time = time.time()
            
            # 检查API调用限制
            if not self.api_limiter.check_limit():
                logger.warning("达到API调用限制，跳过双策略选股")
                return {'success': False, 'error': 'API调用限制达到'}
            
            # 使用API限流器包装策略选择
            @api_limiter(max_calls_per_minute=30, max_calls_per_hour=200)
            def select_strategies():
                return self.dual_selector.run_dual_strategy_selection()
            
            selection_results = select_strategies()
            
            # 使用批量处理器处理选股结果
            def process_stock_selection(stock_data):
                return f"选股结果: {stock_data}"
            
            processed_results = batch_processor(
                selection_results,
                process_stock_selection,
                batch_size=self.config['api_config']['batch_size'],
                delay=self.config['api_config']['batch_delay'],
                max_workers=self.config['api_config']['max_workers']
            )
            
            # 记录API调用
            duration = time.time() - start_time
            self.api_monitor.log_call('strategy_selection', True, duration)
            
            # 更新统计信息
            self.total_analysis_count += 1
            self.successful_analysis_count += 1
            
            logger.info(f"双策略选股完成，耗时: {duration:.2f}秒")
            return {
                'growth_stocks': selection_results.get('growth_stocks', []),
                'value_stocks': selection_results.get('value_stocks', []),
                'all_stocks': selection_results.get('all_selected_stocks', []),
                'processed_results': processed_results,
                'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            duration = time.time() - start_time
            self.api_monitor.log_call('strategy_selection', False, duration, str(e))
            
            # 更新统计信息
            self.total_analysis_count += 1
            self.failed_analysis_count += 1
            
            logger.error(f"双策略选股失败: {e}")
            return {'success': False, 'error': str(e)}
            
    def _run_observation_tracking(self, selection_results: Dict) -> Dict:
        """运行观察池跟踪，带API限流"""
        try:
            start_time = time.time()
            
            # 检查API调用限制
            if not self.api_limiter.check_limit():
                logger.warning("达到API调用限制，跳过观察池跟踪")
                return {'success': False, 'error': 'API调用限制达到'}
            
            # 使用API限流器包装观察池跟踪
            @api_limiter(max_calls_per_minute=30, max_calls_per_hour=200)
            def track_observation():
                return self.observation_tracker.run_observation_tracking()
            
            observation_results = track_observation()
            
            # 使用并发处理器处理观察池数据
            def process_observation_data(obs_data):
                return f"观察数据: {obs_data}"
            
            processed_observation = concurrent_processor(
                observation_results,
                process_observation_data,
                max_workers=self.config['api_config']['max_workers'],
                delay=self.config['api_config']['batch_delay']
            )
            
            # 记录API调用
            duration = time.time() - start_time
            self.api_monitor.log_call('observation_tracking', True, duration)
            
            # 更新统计信息
            self.total_analysis_count += 1
            self.successful_analysis_count += 1
            
            logger.info(f"观察池跟踪完成，耗时: {duration:.2f}秒")
            return {
                'observation_stocks': observation_results.get('observation_stocks', []),
                'signals': observation_results.get('signals', []),
                'processed_observation': processed_observation,
                'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            duration = time.time() - start_time
            self.api_monitor.log_call('observation_tracking', False, duration, str(e))
            
            # 更新统计信息
            self.total_analysis_count += 1
            self.failed_analysis_count += 1
            
            logger.error(f"观察池跟踪失败: {e}")
            return {'success': False, 'error': str(e)}
            
    def _run_comprehensive_strategy(self, observation_results: Dict) -> Dict:
        """运行综合交易策略，带API限流"""
        try:
            start_time = time.time()
            
            # 检查API调用限制
            if not self.api_limiter.check_limit():
                logger.warning("达到API调用限制，跳过综合交易策略")
                return {'success': False, 'error': 'API调用限制达到'}
            
            # 从观察池获取股票列表
            observation_stocks = []
            for ts_code, stock_info in observation_results.get('observation_stocks', {}).items():
                observation_stocks.append(stock_info.get('basic_info', {}))
                
            # 使用API限流器包装综合交易策略
            @api_limiter(max_calls_per_minute=30, max_calls_per_hour=200)
            def generate_trading_strategy():
                return self.strategy_generator.generate_trading_strategy(observation_stocks)
            
            strategy_results = generate_trading_strategy()
            
            # 使用安全API调用处理策略结果
            def process_strategy_result(strategy_data):
                return safe_api_call(
                    lambda x: f"策略结果: {x}",
                    strategy_data,
                    api_name='strategy_processing',
                    max_retries=3,
                    retry_delay=0.5
                )
            
            processed_strategies = batch_processor(
                strategy_results,
                process_strategy_result,
                batch_size=self.config['api_config']['batch_size'],
                delay=self.config['api_config']['batch_delay'],
                max_workers=self.config['api_config']['max_workers']
            )
            
            # 记录API调用
            duration = time.time() - start_time
            self.api_monitor.log_call('comprehensive_strategy', True, duration)
            
            # 更新统计信息
            self.total_analysis_count += 1
            self.successful_analysis_count += 1
            
            logger.info(f"综合交易策略完成，耗时: {duration:.2f}秒")
            return {
                'trading_signals': strategy_results.get('trading_signals', []),
                'portfolio_recommendations': strategy_results.get('portfolio_recommendations', []),
                'risk_assessments': strategy_results.get('risk_assessments', []),
                'processed_strategies': processed_strategies,
                'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            duration = time.time() - start_time
            self.api_monitor.log_call('comprehensive_strategy', False, duration, str(e))
            
            # 更新统计信息
            self.total_analysis_count += 1
            self.failed_analysis_count += 1
            
            logger.error(f"综合交易策略失败: {e}")
            return {'success': False, 'error': str(e)}
            
            logger.info(f"综合交易策略完成，生成{len(results['trading_signals'])}个交易信号")
            return results
        except Exception as e:
            logger.error(f"综合交易策略失败: {e}")
            return {'error': str(e)}
            
    def _generate_complete_report(self, all_results: Dict) -> str:
        """生成完整分析报告，带API限流"""
        try:
            start_time = time.time()
            
            # 检查API调用限制
            if not self.api_limiter.check_limit():
                logger.warning("达到API调用限制，跳过报告生成")
                return "报告生成失败：API调用限制达到"
            
            # 使用API限流器包装报告生成
            @api_limiter(max_calls_per_minute=30, max_calls_per_hour=200)
            def generate_report():
                report = []
                report.append("# 股票分析及交易策略系统 - 完整分析报告")
                report.append(f"**分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                report.append("")
                
                # 执行摘要
                report.append("## 执行摘要")
                if all_results['macro_results'].get('market_state'):
                    report.append(f"- **市场状态**: {all_results['macro_results']['market_state']}")
                if all_results['selection_results'].get('summary'):
                    summary = all_results['selection_results']['summary']
                    report.append(f"- **选股结果**: 成长股{summary.get('total_growth_stocks', 0)}只，价值股{summary.get('total_value_stocks', 0)}只")
                if all_results['strategy_results'].get('trading_signals'):
                    signals = all_results['strategy_results']['trading_signals']
                    signal_counts = {}
                    for signal in signals:
                        signal_type = signal.get('trading_signal', 'N/A')
                        signal_counts[signal_type] = signal_counts.get(signal_type, 0) + 1
                    report.append(f"- **交易信号**: 总计{len(signals)}个信号")
                    for signal_type, count in signal_counts.items():
                        report.append(f"  - {signal_type}: {count}个")
                
                # API统计信息
                api_stats = self.api_monitor.get_stats()
                report.append(f"- **API调用统计**: 总计{api_stats['total_calls']}次，成功率{api_stats['success_rate']:.1%}")
                
                report.append("")
                
                # 宏观分析结果
                report.append("## 宏观经济分析")
                if all_results['macro_results'].get('report'):
                    report.append(all_results['macro_results']['report'])
                
                # 选股结果
                report.append("## 选股结果")
                if all_results['selection_results'].get('growth_stocks'):
                    report.append("### 成长股策略")
                    for stock in all_results['selection_results']['growth_stocks'][:5]:  # 显示前5只
                        report.append(f"- {stock.get('name', 'N/A')}: {stock.get('score', 0):.1f}分")
                
                if all_results['selection_results'].get('value_stocks'):
                    report.append("### 价值股策略")
                    for stock in all_results['selection_results']['value_stocks'][:5]:  # 显示前5只
                        report.append(f"- {stock.get('name', 'N/A')}: {stock.get('score', 0):.1f}分")
                
                # 观察池跟踪
                report.append("## 观察池跟踪")
                if all_results['observation_results'].get('signals'):
                    report.append(f"- **观察信号**: {len(all_results['observation_results']['signals'])}个")
                
                # 交易策略
                report.append("## 综合交易策略")
                if all_results['strategy_results'].get('trading_signals'):
                    report.append("### 交易信号")
                    for signal in all_results['strategy_results']['trading_signals'][:3]:  # 显示前3个
                        report.append(f"- {signal.get('stock_name', 'N/A')}: {signal.get('signal', 'N/A')}")
                
                # 系统状态
                report.append("## 系统状态")
                report.append(f"- **总分析次数**: {self.total_analysis_count}")
                report.append(f"- **成功分析次数**: {self.successful_analysis_count}")
                report.append(f"- **失败分析次数**: {self.failed_analysis_count}")
                report.append(f"- **成功率**: {(self.successful_analysis_count/max(1, self.total_analysis_count)):.1%}")
                
                return '\n'.join(report)
            
            report_content = generate_report()
            
            # 记录API调用
            duration = time.time() - start_time
            self.api_monitor.log_call('report_generation', True, duration)
            
            logger.info(f"报告生成完成，耗时: {duration:.2f}秒")
            return report_content
            
        except Exception as e:
            duration = time.time() - start_time
            self.api_monitor.log_call('report_generation', False, duration, str(e))
            
            logger.error(f"报告生成失败: {e}")
            return f"报告生成失败：{str(e)}"
            
    def get_api_statistics(self) -> Dict:
        """获取API调用统计信息"""
        return self.api_monitor.get_stats()
    
    def get_system_health(self) -> Dict:
        """获取系统健康状态"""
        api_stats = self.api_monitor.get_stats()
        
        # 计算成功率
        success_rate = (self.successful_analysis_count / max(1, self.total_analysis_count)) * 100
        
        # 检查API限制状态
        limit_status = "正常"
        if not self.api_limiter.check_limit():
            limit_status = "达到限制"
        
        return {
            'api_calls': api_stats['total_calls'],
            'api_success_rate': api_stats['success_rate'] * 100,
            'analysis_success_rate': success_rate,
            'total_analysis_count': self.total_analysis_count,
            'successful_analysis_count': self.successful_analysis_count,
            'failed_analysis_count': self.failed_analysis_count,
            'api_limit_status': limit_status,
            'last_run_time': self.system_status['last_run_time'],
            'system_status': self.system_status['last_run_status']
        }
    
    def reset_api_limits(self):
        """重置API限制计数器"""
        self.api_limiter.reset()
        self.api_monitor = APIMonitor()
        logger.info("API限制计数器已重置")
    
    def save_system_status(self, status: str):
        """保存系统状态"""
        self.system_status['last_run_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.system_status['last_run_status'] = status
        
        # 更新API统计信息
        api_stats = self.api_monitor.get_stats()
        self.system_status['api_calls_count'] = api_stats['total_calls']
        self.system_status['api_success_rate'] = api_stats['success_rate']
        
        # 保存到数据库
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO system_status 
                (run_time, status, total_calls, success_rate, analysis_count)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                self.system_status['last_run_time'],
                status,
                api_stats['total_calls'],
                api_stats['success_rate'],
                self.total_analysis_count
            ))
            self.conn.commit()
        except Exception as e:
            logger.error(f"保存系统状态失败: {e}")
    
    def close(self):
        """关闭系统连接"""
        try:
            self.conn.close()
            logger.info("系统连接已关闭")
        except Exception as e:
            logger.error(f"关闭系统连接失败: {e}")
        report.append(f"- **处理股票数量**: {len(all_results['observation_results'].get('observation_stocks', {}))}")
        report.append(f"- **交易信号数量**: {len(all_results['strategy_results'].get('trading_signals', []))}")
        report.append("")
        
        # 最终建议
        report.append("## 6. 最终投资建议")
        final_recommendations = self._generate_final_recommendations(all_results)
        report.append(final_recommendations)
        
        return "\n".join(report)
        
    def _generate_final_recommendations(self, all_results: Dict) -> str:
        """生成最终投资建议"""
        recommendations = []
        
        try:
            # 获取强烈买入和买入建议
            strong_buy = all_results['strategy_results']['portfolio_recommendations'].get('strong_buy', [])
            buy = all_results['strategy_results']['portfolio_recommendations'].get('buy', [])
            
            if strong_buy:
                recommendations.append("### 重点配置")
                recommendations.append("建议优先配置以下股票：")
                for rec in strong_buy[:5]:
                    recommendations.append(f"- {rec['ts_code']}: 仓位{rec['position_size']*100:.1f}%")
                    
            if buy:
                recommendations.append("### 积极配置")
                recommendations.append("建议积极配置以下股票：")
                for rec in buy[:5]:
                    recommendations.append(f"- {rec['ts_code']}: 仓位{rec['position_size']*100:.1f}%")
                    
            # 风险提示
            risk_assessments = all_results['strategy_results'].get('risk_assessments', {})
            portfolio_risk = risk_assessments.get('portfolio_risk', 'medium')
            
            recommendations.append("### 风险提示")
            recommendations.append(f"- **组合风险**: {portfolio_risk}")
            
            if portfolio_risk == 'high':
                recommendations.append("- 建议降低整体仓位，控制风险")
            elif portfolio_risk == 'low':
                recommendations.append("- 可以适当增加仓位，把握机会")
            else:
                recommendations.append("- 维持当前仓位，密切关注市场变化")
                
            return "\n".join(recommendations)
            
        except Exception as e:
            logger.error(f"生成最终建议失败: {e}")
            return "无法生成最终建议"
            
    def _save_system_status(self, status: str):
        """保存系统状态"""
        try:
            self.system_status['last_run_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.system_status['last_run_status'] = status
            
            if status == 'success':
                self.system_status['successful_runs'] += 1
            else:
                self.system_status['failed_runs'] += 1
                
            # 创建系统状态表
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_date TEXT NOT NULL,
                    run_status TEXT NOT NULL,
                    total_processed_stocks INTEGER,
                    successful_runs INTEGER,
                    failed_runs INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 保存状态
            self.cursor.execute("""
                INSERT INTO system_status (
                    run_date, run_status, total_processed_stocks,
                    successful_runs, failed_runs
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                self.system_status['last_run_time'],
                self.system_status['last_run_status'],
                self.system_status['total_processed_stocks'],
                self.system_status['successful_runs'],
                self.system_status['failed_runs']
            ))
            
            self.conn.commit()
            logger.info("系统状态已保存")
            
        except Exception as e:
            logger.error(f"保存系统状态失败: {e}")
            
    def get_system_status(self) -> Dict:
        """获取系统状态"""
        return self.system_status.copy()
        
    def run_quick_analysis(self) -> str:
        """运行快速分析（只生成宏观报告和选股结果）"""
        try:
            logger.info("开始运行快速分析...")
            
            # 1. 宏观分析
            macro_results = self._run_macro_analysis()
            
            # 2. 双策略选股
            selection_results = self._run_dual_strategy_selection(macro_results)
            
            # 生成快速报告
            quick_report = self._generate_quick_report(macro_results, selection_results)
            
            logger.info("快速分析完成")
            return quick_report
            
        except Exception as e:
            logger.error(f"快速分析失败: {e}")
            return f"快速分析失败: {str(e)}"
            
    def _generate_quick_report(self, macro_results: Dict, selection_results: Dict) -> str:
        """生成快速分析报告"""
        report = []
        report.append("# 快速股票分析报告")
        report.append(f"**分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # 市场状态
        report.append("## 市场状态")
        if macro_results.get('market_state'):
            report.append(f"**当前市场**: {macro_results['market_state']}")
        if macro_results.get('position_allocation'):
            allocation = macro_results['position_allocation']
            report.append(f"**仓位建议**: 成长股{allocation['growth']*100:.0f}%，价值股{allocation['value']*100:.0f}%")
        report.append("")
        
        # 选股结果
        report.append("## 选股结果")
        if selection_results.get('summary'):
            summary = selection_results['summary']
            report.append(f"**成长股**: {summary['total_growth_stocks']}只")
            report.append(f"**价值股**: {summary['total_value_stocks']}只")
            report.append(f"**平均评分**: 成长股{summary['avg_growth_score']:.1f}，价值股{summary['avg_value_score']:.1f}")
        report.append("")
        
        # 重点股票
        if selection_results.get('growth_stocks'):
            report.append("### 重点成长股")
            report.append("| 股票代码 | 股票名称 | 评分 |")
            report.append("|----------|----------|------|")
            for stock in selection_results['growth_stocks'][:5]:
                ts_code = stock.get('ts_code', 'N/A')
                name = stock.get('name', 'N/A')
                score = stock.get('strategy_score', 0)
                report.append(f"| {ts_code} | {name} | {score:.1f} |")
            report.append("")
            
        if selection_results.get('value_stocks'):
            report.append("### 重点价值股")
            report.append("| 股票代码 | 股票名称 | 评分 |")
            report.append("|----------|----------|------|")
            for stock in selection_results['value_stocks'][:5]:
                ts_code = stock.get('ts_code', 'N/A')
                name = stock.get('name', 'N/A')
                score = stock.get('strategy_score', 0)
                report.append(f"| {ts_code} | {name} | {score:.1f} |")
            report.append("")
        
        return "\n".join(report)
        
    def close(self):
        """关闭系统连接"""
        self.macro_analyzer.close()
        self.dual_selector.close()
        self.observation_tracker.close()
        self.strategy_generator.close()
        if hasattr(self, 'conn'):
            self.conn.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # 测试集成系统
    system = IntegratedStockAnalysisSystem()
    
    try:
        print("=== 运行完整分析流程 ===")
        full_results = system.run_full_analysis_pipeline()
        
        if full_results['success']:
            print("完整分析流程执行成功！")
            print("报告预览（前1000字符）:")
            print(full_results['report'][:1000] + "...")
            
            # 保存完整报告到文件
            with open('complete_analysis_report.md', 'w', encoding='utf-8') as f:
                f.write(full_results['report'])
            print("完整报告已保存到 complete_analysis_report.md")
        else:
            print(f"完整分析流程执行失败: {full_results['error']}")
            
        print("\n=== 运行快速分析 ===")
        quick_report = system.run_quick_analysis()
        print("快速分析报告:")
        print(quick_report)
        
        # 保存快速报告到文件
        with open('quick_analysis_report.md', 'w', encoding='utf-8') as f:
            f.write(quick_report)
        print("快速分析报告已保存到 quick_analysis_report.md")
        
    except Exception as e:
        logger.error(f"系统测试失败: {e}")
    finally:
        system.close()