"""
macro_market_analyzer.py - 宏观经济与大盘分析增强模块
集成PMI、主要指数、市场情绪等多维度分析
输出：大盘状态判断 + 动态仓位分配建议
"""

import logging
from data_source_manager import DataSourceManager
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

class MacroMarketAnalyzer:
    """宏观经济与大盘状态综合分析器"""
    
    def __init__(self, db_path: str = "database/stock_analysis.db"):
        self.db_path = db_path
        self.data_manager = DataSourceManager(db_path)
        
        # 宏观数据
        self.macro_data = {}
        self.market_state = None
        self.position_allocation = {}
        
        # 分析结果
        self.analysis_results = {}
        
    def fetch_all_macro_data(self):
        """获取所有宏观经济数据"""
        try:
            logger.info("开始获取宏观经济数据...")
            
            # 使用数据源管理器获取宏观数据
            self.macro_data = self.data_manager.get_macro_data()
            
            # 获取市场状态
            self.market_state = self.data_manager.get_market_state()
            
            # 获取动态仓位分配
            self.position_allocation = self.data_manager.get_dynamic_position_allocation()
            
            logger.info("宏观经济数据获取完成")
            
        except Exception as e:
            logger.error(f"获取宏观经济数据失败: {e}")
            
    def analyze_market_cycle(self):
        """分析经济周期"""
        try:
            if not self.macro_data:
                self.fetch_all_macro_data()
            
            cycle_indicators = {
                'expansion': 0,
                'contraction': 0,
                'stable': 0
            }
            
            # PMI分析
            if self.macro_data.get('pmi'):
                pmi_trend = self.macro_data['pmi']['trend']
                if pmi_trend == 'expansion':
                    cycle_indicators['expansion'] += 1
                elif pmi_trend == 'contraction':
                    cycle_indicators['contraction'] += 1
                else:
                    cycle_indicators['stable'] += 1
            
            # GDP分析
            if self.macro_data.get('gdp'):
                gdp_growth = self.macro_data['gdp']['growth']
                if gdp_growth and gdp_growth > 6:
                    cycle_indicators['expansion'] += 1
                elif gdp_growth and gdp_growth < 4:
                    cycle_indicators['contraction'] += 1
                else:
                    cycle_indicators['stable'] += 1
            
            # CPI分析
            if self.macro_data.get('cpi'):
                cpi_growth = self.macro_data['cpi']['growth']
                if cpi_growth and cpi_growth > 3:
                    cycle_indicators['contraction'] += 1  # 通胀过热，可能收缩
                elif cpi_growth and cpi_growth < 1:
                    cycle_indicators['expansion'] += 1  # 通货紧缩，可能刺激
                else:
                    cycle_indicators['stable'] += 1
            
            # 判断经济周期
            max_indicator = max(cycle_indicators.values())
            if max_indicator >= 2:
                for cycle, count in cycle_indicators.items():
                    if count == max_indicator:
                        return cycle
            else:
                return 'stable'
                
        except Exception as e:
            logger.error(f"分析经济周期失败: {e}")
            return 'unknown'
    
    def analyze_market_sentiment(self):
        """分析市场情绪"""
        try:
            if not self.macro_data:
                self.fetch_all_macro_data()
            
            # 获取主要指数数据
            indices = self.data_manager.get_market_indices()
            
            sentiment_indicators = {
                'bullish': 0,
                'bearish': 0,
                'neutral': 0
            }
            
            # 分析主要指数走势
            for code, data in indices.items():
                if data.get('change_pct'):
                    if data['change_pct'] > 1:
                        sentiment_indicators['bullish'] += 1
                    elif data['change_pct'] < -1:
                        sentiment_indicators['bearish'] += 1
                    else:
                        sentiment_indicators['neutral'] += 1
            
            # 分析融资融券数据
            margin_data = self.data_manager.get_margin_data()
            if margin_data.get('market_sentiment'):
                sentiment = margin_data['market_sentiment']
                if sentiment['up_ratio'] > 0.6:
                    sentiment_indicators['bullish'] += 1
                elif sentiment['down_ratio'] > 0.6:
                    sentiment_indicators['bearish'] += 1
                else:
                    sentiment_indicators['neutral'] += 1
            
            # 判断市场情绪
            max_indicator = max(sentiment_indicators.values())
            if max_indicator >= 2:
                for sentiment, count in sentiment_indicators.items():
                    if count == max_indicator:
                        return sentiment
            else:
                return 'neutral'
                
        except Exception as e:
            logger.error(f"分析市场情绪失败: {e}")
            return 'unknown'
    
    def generate_analysis_report(self):
        """生成分析报告"""
        try:
            if not self.macro_data:
                self.fetch_all_macro_data()
            
            report = {
                'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'market_state': self.market_state,
                'economic_cycle': self.analyze_market_cycle(),
                'market_sentiment': self.analyze_market_sentiment(),
                'position_allocation': self.position_allocation,
                'macro_indicators': self.macro_data,
                'market_indices': self.data_manager.get_market_indices(),
                'recommendations': self._generate_recommendations()
            }
            
            self.analysis_results = report
            return report
            
        except Exception as e:
            logger.error(f"生成分析报告失败: {e}")
            return {}
    
    def _generate_recommendations(self):
        """生成投资建议"""
        try:
            recommendations = []
            
            # 基于市场状态的建议
            if self.market_state == '强多':
                recommendations.append("市场强势，可适当提高仓位")
            elif self.market_state == '偏多':
                recommendations.append("市场偏多，可维持正常仓位")
            elif self.market_state == '震荡':
                recommendations.append("市场震荡，建议控制仓位")
            elif self.market_state == '偏空':
                recommendations.append("市场偏空，建议降低仓位")
            elif self.market_state == '弱空':
                recommendations.append("市场弱势，建议谨慎操作")
            
            # 基于经济周期的建议
            economic_cycle = self.analyze_market_cycle()
            if economic_cycle == 'expansion':
                recommendations.append("经济扩张期，成长股相对占优")
            elif economic_cycle == 'contraction':
                recommendations.append("经济收缩期，价值股相对占优")
            else:
                recommendations.append("经济稳定期，均衡配置")
            
            # 基于市场情绪的建议
            sentiment = self.analyze_market_sentiment()
            if sentiment == 'bullish':
                recommendations.append("市场情绪乐观，可适当积极")
            elif sentiment == 'bearish':
                recommendations.append("市场情绪悲观，建议谨慎")
            else:
                recommendations.append("市场情绪中性，按计划执行")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"生成投资建议失败: {e}")
            return []
    
    def get_market_signals(self):
        """获取市场信号"""
        try:
            if not self.analysis_results:
                self.generate_analysis_report()
            
            signals = {
                'market_state': self.market_state,
                'economic_cycle': self.analyze_market_cycle(),
                'market_sentiment': self.analyze_market_sentiment(),
                'position_allocation': self.position_allocation,
                'signals': self._generate_trading_signals()
            }
            
            return signals
            
        except Exception as e:
            logger.error(f"获取市场信号失败: {e}")
            return {}
    
    def _generate_trading_signals(self):
        """生成交易信号"""
        try:
            signals = []
            
            # 基于市场状态生成信号
            if self.market_state == '强多':
                signals.append({
                    'type': 'market',
                    'signal': 'strong_bull',
                    'description': '市场强势，适合积极做多',
                    'strength': 'high'
                })
            elif self.market_state == '偏多':
                signals.append({
                    'type': 'market',
                    'signal': 'bull',
                    'description': '市场偏多，适合适度做多',
                    'strength': 'medium'
                })
            elif self.market_state == '震荡':
                signals.append({
                    'type': 'market',
                    'signal': 'neutral',
                    'description': '市场震荡，适合高抛低吸',
                    'strength': 'low'
                })
            elif self.market_state == '偏空':
                signals.append({
                    'type': 'market',
                    'signal': 'bear',
                    'description': '市场偏空，适合谨慎做空',
                    'strength': 'medium'
                })
            elif self.market_state == '弱空':
                signals.append({
                    'type': 'market',
                    'signal': 'strong_bear',
                    'description': '市场弱势，建议空仓观望',
                    'strength': 'high'
                })
            
            # 基于经济周期生成信号
            economic_cycle = self.analyze_market_cycle()
            if economic_cycle == 'expansion':
                signals.append({
                    'type': 'economy',
                    'signal': 'expansion',
                    'description': '经济扩张期，成长股占优',
                    'strength': 'medium'
                })
            elif economic_cycle == 'contraction':
                signals.append({
                    'type': 'economy',
                    'signal': 'contraction',
                    'description': '经济收缩期，价值股占优',
                    'strength': 'medium'
                })
            
            return signals
            
        except Exception as e:
            logger.error(f"生成交易信号失败: {e}")
            return []
    
    def save_analysis_results(self):
        """保存分析结果"""
        try:
            if not self.analysis_results:
                self.generate_analysis_report()
            
            # 保存到数据库
            self.data_manager.cursor.execute("""
                INSERT OR REPLACE INTO macro_analysis 
                (analysis_date, market_state, economic_cycle, market_sentiment, 
                 position_allocation_json, recommendations_json, analysis_results_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                self.analysis_results['analysis_date'],
                self.analysis_results['market_state'],
                self.analysis_results['economic_cycle'],
                self.analysis_results['market_sentiment'],
                str(self.analysis_results['position_allocation']),
                str(self.analysis_results['recommendations']),
                str(self.analysis_results)
            ))
            
            self.data_manager.conn.commit()
            logger.info("分析结果保存成功")
            
        except Exception as e:
            logger.error(f"保存分析结果失败: {e}")
    
    def close(self):
        """关闭连接"""
        self.data_manager.close()


if __name__ == "__main__":
    # 测试模块
    logging.basicConfig(level=logging.INFO)
    
    analyzer = MacroMarketAnalyzer()
    
    try:
        print("=== 宏观经济与大盘分析测试 ===")
        
        # 获取宏观数据
        analyzer.fetch_all_macro_data()
        
        # 生成分析报告
        report = analyzer.generate_analysis_report()
        
        print("\n=== 分析报告 ===")
        print(f"分析时间: {report['analysis_date']}")
        print(f"市场状态: {report['market_state']}")
        print(f"经济周期: {report['economic_cycle']}")
        print(f"市场情绪: {report['market_sentiment']}")
        print(f"仓位分配: {report['position_allocation']}")
        
        print("\n=== 投资建议 ===")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"{i}. {rec}")
        
        print("\n=== 主要指数 ===")
        for code, data in report['market_indices'].items():
            print(f"{data['name']}: {data['close']} ({data['change_pct']:.2f}%)")
        
        print("\n=== 宏观指标 ===")
        for key, value in report['macro_indicators'].items():
            print(f"{key}: {value}")
        
        # 获取市场信号
        signals = analyzer.get_market_signals()
        print("\n=== 交易信号 ===")
        for signal in signals['signals']:
            print(f"{signal['type']}: {signal['signal']} - {signal['description']} ({signal['strength']})")
        
    except Exception as e:
        print(f"测试失败: {e}")
    finally:
        analyzer.close()