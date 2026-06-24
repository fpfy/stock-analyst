"""
comprehensive_trading_strategy.py - 综合交易策略生成模块
整合基本面、技术面、舆情等多维度分析，生成最终交易策略
"""

import logging
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import numpy as np
from enum import Enum

from observation_pool_tracker import ObservationPoolTracker
from macro_market_analyzer import MacroMarketAnalyzer

logger = logging.getLogger(__name__)

class SignalType(Enum):
    """交易信号类型"""
    STRONG_BUY = "强烈买入"
    BUY = "买入"
    HOLD = "持有"
    SELL = "卖出"
    STRONG_SELL = "强烈卖出"
    WAIT = "观望"

class RiskLevel(Enum):
    """风险等级"""
    LOW = "低风险"
    MEDIUM = "中等风险"
    HIGH = "高风险"

class ComprehensiveTradingStrategy:
    """综合交易策略生成器"""
    
    def __init__(self, db_path: str = "database/stock_analysis.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # 初始化观察池跟踪器
        self.observation_tracker = ObservationPoolTracker(db_path)
        
        # 初始化宏观分析器
        self.macro_analyzer = MacroMarketAnalyzer(db_path)
        
        # 策略参数
        self.signal_weights = {
            'technical': 0.4,      # 技术面权重
            'fundamental': 0.35,    # 基本面权重
            'market': 0.15,        # 市场环境权重
            'sentiment': 0.1       # 舆情权重
        }
        
        # 风险控制参数
        self.position_limits = {
            'max_single_position': 0.10,  # 单只股票最大仓位
            'max_sector_concentration': 0.30,  # 单个行业最大仓位
            'stop_loss_threshold': 0.08,  # 止损阈值
            'take_profit_threshold': 0.15  # 止盈阈值
        }
        
        # 交易策略结果
        self.trading_signals = []
        self.portfolio_recommendations = {}
        self.risk_assessments = {}
        
    def generate_trading_strategy(self, observation_stocks: List[Dict]) -> Dict:
        """生成综合交易策略"""
        try:
            logger.info("开始生成综合交易策略...")
            
            # 1. 添加股票到观察池
            self.observation_tracker.add_stocks_to_observation(observation_stocks)
            
            # 2. 更新观察池数据
            self.observation_tracker.update_observation_pool()
            
            # 3. 生成交易信号
            self.trading_signals = self._generate_trading_signals()
            
            # 4. 生成投资组合建议
            self.portfolio_recommendations = self._generate_portfolio_recommendations()
            
            # 5. 进行风险评估
            self.risk_assessments = self._perform_risk_assessment()
            
            # 6. 生成最终策略报告
            strategy_report = self._generate_strategy_report()
            
            # 7. 保存策略结果
            self._save_strategy_results(strategy_report)
            
            logger.info("综合交易策略生成完成")
            
            return {
                'report': strategy_report,
                'trading_signals': self.trading_signals,
                'portfolio_recommendations': self.portfolio_recommendations,
                'risk_assessments': self.risk_assessments
            }
            
        except Exception as e:
            logger.error(f"生成交易策略失败: {e}")
            return {}
            
    def _generate_trading_signals(self) -> List[Dict]:
        """生成交易信号"""
        signals = []
        
        try:
            for ts_code, stock_info in self.observation_tracker.observation_stocks.items():
                # 获取各维度数据
                tech_signal = self._get_technical_signal(ts_code)
                fundamental_signal = self._get_fundamental_signal(ts_code)
                market_signal = self._get_market_signal(ts_code)
                sentiment_signal = self._get_sentiment_signal(ts_code)
                
                # 计算综合信号
                composite_signal = self._calculate_composite_signal(
                    tech_signal, fundamental_signal, market_signal, sentiment_signal
                )
                
                # 确定交易信号
                trading_signal = self._determine_trading_signal(composite_signal, stock_info)
                
                # 计算仓位建议
                position_size = self._calculate_position_size(trading_signal, stock_info)
                
                signal = {
                    'ts_code': ts_code,
                    'stock_name': stock_info['basic_info'].get('name', 'N/A'),
                    'strategy_type': stock_info['strategy_type'],
                    'technical_signal': tech_signal,
                    'fundamental_signal': fundamental_signal,
                    'market_signal': market_signal,
                    'sentiment_signal': sentiment_signal,
                    'composite_score': composite_signal['score'],
                    'trading_signal': trading_signal['signal'],
                    'signal_strength': trading_signal['strength'],
                    'position_size': position_size,
                    'risk_level': trading_signal['risk_level'],
                    'reasoning': trading_signal['reasoning'],
                    'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                signals.append(signal)
                
            # 按信号强度排序
            signals.sort(key=lambda x: self._signal_priority(x['trading_signal']), reverse=True)
            
            return signals
            
        except Exception as e:
            logger.error(f"生成交易信号失败: {e}")
            return []
            
    def _get_technical_signal(self, ts_code: str) -> Dict:
        """获取技术面信号"""
        try:
            # 获取最新技术面数据
            query = """
                SELECT signal, strength, score, ma_trend, volume_trend, rsi_signal, macd_signal
                FROM technical_signals
                WHERE ts_code = ?
                ORDER BY trade_date DESC
                LIMIT 1
            """
            
            self.cursor.execute(query, (ts_code,))
            row = self.cursor.fetchone()
            
            if row:
                return {
                    'signal': row[0],
                    'strength': row[1],
                    'score': row[2],
                    'ma_trend': row[3],
                    'volume_trend': row[4],
                    'rsi_signal': row[5],
                    'macd_signal': row[6]
                }
            else:
                return {'signal': 'wait', 'strength': 'unknown', 'score': 0}
                
        except Exception as e:
            logger.error(f"获取技术面信号失败: {e}")
            return {'signal': 'wait', 'strength': 'unknown', 'score': 0}
            
    def _get_fundamental_signal(self, ts_code: str) -> Dict:
        """获取基本面信号"""
        try:
            # 获取最新基本面数据
            query = """
                SELECT roe_yearly, netprofit_yoy, revenue_yoy, pe_ttm, pb, dividend_yield, debt_ratio
                FROM financial_data
                WHERE ts_code = ?
                ORDER BY trade_date DESC
                LIMIT 1
            """
            
            self.cursor.execute(query, (ts_code,))
            row = self.cursor.fetchone()
            
            if row:
                return {
                    'roe_yearly': row[0],
                    'netprofit_yoy': row[1],
                    'revenue_yoy': row[2],
                    'pe_ttm': row[3],
                    'pb': row[4],
                    'dividend_yield': row[5],
                    'debt_ratio': row[6]
                }
            else:
                return {}
                
        except Exception as e:
            logger.error(f"获取基本面信号失败: {e}")
            return {}
            
    def _get_market_signal(self, ts_code: str) -> Dict:
        """获取市场环境信号"""
        try:
            # 获取宏观市场状态
            market_state = self.macro_analyzer.market_state
            
            # 获取行业相对表现
            query = """
                SELECT industry_name, industry_pe, industry_pb
                FROM industry_data
                WHERE ts_code = ?
                ORDER BY trade_date DESC
                LIMIT 1
            """
            
            self.cursor.execute(query, (ts_code,))
            row = self.cursor.fetchone()
            
            if row:
                return {
                    'market_state': market_state,
                    'industry_name': row[0],
                    'industry_pe': row[1],
                    'industry_pb': row[2]
                }
            else:
                return {'market_state': market_state}
                
        except Exception as e:
            logger.error(f"获取市场信号失败: {e}")
            return {'market_state': 'unknown'}
            
    def _get_sentiment_signal(self, ts_code: str) -> Dict:
        """获取舆情信号"""
        try:
            # 简化的舆情分析（实际应该接入舆情API）
            query = """
                SELECT sentiment_score, news_count, social_mentions
                FROM sentiment_data
                WHERE ts_code = ?
                ORDER BY date DESC
                LIMIT 1
            """
            
            self.cursor.execute(query, (ts_code,))
            row = self.cursor.fetchone()
            
            if row:
                return {
                    'sentiment_score': row[0],
                    'news_count': row[1],
                    'social_mentions': row[2]
                }
            else:
                return {'sentiment_score': 0.5, 'news_count': 0, 'social_mentions': 0}
                
        except Exception as e:
            logger.error(f"获取舆情信号失败: {e}")
            return {'sentiment_score': 0.5, 'news_count': 0, 'social_mentions': 0}
            
    def _calculate_composite_signal(self, tech_signal: Dict, fundamental_signal: Dict, 
                                   market_signal: Dict, sentiment_signal: Dict) -> Dict:
        """计算综合信号"""
        try:
            score = 0
            details = []
            
            # 技术面评分
            tech_score = tech_signal.get('score', 0)
            score += tech_score * self.signal_weights['technical']
            details.append(f"技术面: {tech_score:.1f}")
            
            # 基本面评分
            fundamental_score = self._score_fundamental(fundamental_signal)
            score += fundamental_score * self.signal_weights['fundamental']
            details.append(f"基本面: {fundamental_score:.1f}")
            
            # 市场环境评分
            market_score = self._score_market_environment(market_signal)
            score += market_score * self.signal_weights['market']
            details.append(f"市场环境: {market_score:.1f}")
            
            # 舆情评分
            sentiment_score = sentiment_signal.get('sentiment_score', 0.5) * 100
            score += sentiment_score * self.signal_weights['sentiment']
            details.append(f"舆情: {sentiment_score:.1f}")
            
            return {
                'score': round(score, 2),
                'details': details
            }
            
        except Exception as e:
            logger.error(f"计算综合信号失败: {e}")
            return {'score': 0, 'details': []}
            
    def _score_fundamental(self, fundamental_data: Dict) -> float:
        """基本面评分"""
        score = 0
        
        try:
            # ROE评分 (25%)
            if fundamental_data.get('roe_yearly'):
                roe = fundamental_data['roe_yearly']
                score += min(roe * 250, 25)
                
            # 净利润增长评分 (25%)
            if fundamental_data.get('netprofit_yoy'):
                profit_growth = fundamental_data['netprofit_yoy']
                score += min(profit_growth * 250, 25)
                
            # 营收增长评分 (20%)
            if fundamental_data.get('revenue_yoy'):
                revenue_growth = fundamental_data['revenue_yoy']
                score += min(revenue_growth * 200, 20)
                
            # 估值评分 (20%)
            if fundamental_data.get('pe_ttm') and fundamental_data['pe_ttm'] > 0:
                pe = fundamental_data['pe_ttm']
                if pe <= 15:
                    score += 20
                elif pe <= 25:
                    score += 10
                else:
                    score += 5
                    
            # 股息率评分 (10%)
            if fundamental_data.get('dividend_yield'):
                dividend_yield = fundamental_data['dividend_yield']
                score += min(dividend_yield * 1000, 10)
                
        except Exception as e:
            logger.error(f"基本面评分失败: {e}")
            
        return round(score, 2)
        
    def _score_market_environment(self, market_data: Dict) -> float:
        """市场环境评分"""
        try:
            score = 0
            
            # 市场状态评分
            market_state = market_data.get('market_state', 'unknown')
            state_scores = {
                '强多': 100,
                '偏多': 80,
                '震荡': 60,
                '偏空': 40,
                '弱空': 20,
                'unknown': 50
            }
            score += state_scores.get(market_state, 50)
            
            # 行业相对评分
            if market_data.get('industry_pe'):
                industry_pe = market_data['industry_pe']
                if industry_pe <= 20:
                    score += 20
                elif industry_pe <= 30:
                    score += 10
                else:
                    score += 5
                    
            return min(score, 100)
            
        except Exception as e:
            logger.error(f"市场环境评分失败: {e}")
            return 50
            
    def _determine_trading_signal(self, composite_signal: Dict, stock_info: Dict) -> Dict:
        """确定交易信号"""
        try:
            score = composite_signal['score']
            
            # 根据分数确定信号
            if score >= 85:
                signal = SignalType.STRONG_BUY
                strength = 'strong'
                risk_level = RiskLevel.LOW if stock_info['strategy_type'] == 'value' else RiskLevel.MEDIUM
                reasoning = "综合评分很高，各维度表现优秀，建议强烈买入"
            elif score >= 70:
                signal = SignalType.BUY
                strength = 'medium'
                risk_level = RiskLevel.LOW if stock_info['strategy_type'] == 'value' else RiskLevel.MEDIUM
                reasoning = "综合评分较高，各维度表现良好，建议买入"
            elif score >= 50:
                signal = SignalType.HOLD
                strength = 'weak'
                risk_level = RiskLevel.MEDIUM
                reasoning = "综合评分中等，建议继续观察"
            elif score >= 30:
                signal = SignalType.SELL
                strength = 'medium'
                risk_level = RiskLevel.MEDIUM
                reasoning = "综合评分较低，建议减仓"
            else:
                signal = SignalType.STRONG_SELL
                strength = 'strong'
                risk_level = RiskLevel.HIGH
                reasoning = "综合评分很低，建议卖出"
                
            return {
                'signal': signal.value,
                'strength': strength,
                'risk_level': risk_level.value,
                'reasoning': reasoning
            }
            
        except Exception as e:
            logger.error(f"确定交易信号失败: {e}")
            return {
                'signal': SignalType.WAIT.value,
                'strength': 'unknown',
                'risk_level': RiskLevel.MEDIUM.value,
                'reasoning': "无法确定交易信号"
            }
            
    def _calculate_position_size(self, trading_signal: Dict, stock_info: Dict) -> float:
        """计算仓位大小"""
        try:
            base_position = 0.05  # 基础仓位5%
            
            # 根据信号强度调整
            if trading_signal['strength'] == 'strong':
                if trading_signal['signal'] in [SignalType.STRONG_BUY.value, SignalType.STRONG_SELL.value]:
                    base_position = 0.08
            elif trading_signal['strength'] == 'medium':
                if trading_signal['signal'] in [SignalType.BUY.value, SignalType.SELL.value]:
                    base_position = 0.06
            else:
                base_position = 0.04
                
            # 根据策略类型调整
            if stock_info['strategy_type'] == 'value':
                base_position *= 1.2  # 价值股可以适当增加仓位
            else:
                base_position *= 0.9  # 成长股适当减少仓位
                
            # 根据风险等级调整
            if trading_signal['risk_level'] == RiskLevel.HIGH.value:
                base_position *= 0.5
            elif trading_signal['risk_level'] == RiskLevel.LOW.value:
                base_position *= 1.2
                
            # 限制最大仓位
            return min(base_position, self.position_limits['max_single_position'])
            
        except Exception as e:
            logger.error(f"计算仓位大小失败: {e}")
            return 0.05
            
    def _signal_priority(self, signal: str) -> int:
        """获取信号优先级"""
        priority_map = {
            SignalType.STRONG_BUY.value: 5,
            SignalType.BUY.value: 4,
            SignalType.HOLD.value: 3,
            SignalType.SELL.value: 2,
            SignalType.STRONG_SELL.value: 1,
            SignalType.WAIT.value: 0
        }
        return priority_map.get(signal, 0)
        
    def _generate_portfolio_recommendations(self) -> Dict:
        """生成投资组合建议"""
        try:
            recommendations = {
                'strong_buy': [],
                'buy': [],
                'hold': [],
                'reduce': [],
                'avoid': []
            }
            
            for signal in self.trading_signals:
                ts_code = signal['ts_code']
                signal_type = signal['trading_signal']
                position_size = signal['position_size']
                
                if signal_type == SignalType.STRONG_BUY.value:
                    recommendations['strong_buy'].append({
                        'ts_code': ts_code,
                        'position_size': position_size,
                        'score': signal['composite_score']
                    })
                elif signal_type == SignalType.BUY.value:
                    recommendations['buy'].append({
                        'ts_code': ts_code,
                        'position_size': position_size,
                        'score': signal['composite_score']
                    })
                elif signal_type == SignalType.HOLD.value:
                    recommendations['hold'].append({
                        'ts_code': ts_code,
                        'position_size': position_size,
                        'score': signal['composite_score']
                    })
                elif signal_type == SignalType.SELL.value:
                    recommendations['reduce'].append({
                        'ts_code': ts_code,
                        'position_size': position_size,
                        'score': signal['composite_score']
                    })
                else:
                    recommendations['avoid'].append({
                        'ts_code': ts_code,
                        'position_size': position_size,
                        'score': signal['composite_score']
                    })
                    
            # 按评分排序
            for category in recommendations:
                recommendations[category].sort(key=lambda x: x['score'], reverse=True)
                
            return recommendations
            
        except Exception as e:
            logger.error(f"生成投资组合建议失败: {e}")
            return {}
            
    def _perform_risk_assessment(self) -> Dict:
        """进行风险评估"""
        try:
            risk_assessment = {
                'portfolio_risk': 'medium',
                'concentration_risk': 'low',
                'market_risk': 'medium',
                'individual_risks': []
            }
            
            # 计算组合风险
            total_position = sum(signal['position_size'] for signal in self.trading_signals)
            if total_position > 0.8:
                risk_assessment['portfolio_risk'] = 'high'
            elif total_position < 0.4:
                risk_assessment['portfolio_risk'] = 'low'
                
            # 检查集中度风险
            sector_positions = {}
            for signal in self.trading_signals:
                # 这里简化处理，实际应该获取行业信息
                sector = 'unknown'
                if sector not in sector_positions:
                    sector_positions[sector] = 0
                sector_positions[sector] += signal['position_size']
                
            max_sector_position = max(sector_positions.values()) if sector_positions else 0
            if max_sector_position > self.position_limits['max_sector_concentration']:
                risk_assessment['concentration_risk'] = 'high'
                
            # 市场风险评估
            market_state = self.macro_analyzer.market_state
            if market_state in ['强多', '偏多']:
                risk_assessment['market_risk'] = 'low'
            elif market_state in ['偏空', '弱空']:
                risk_assessment['market_risk'] = 'high'
                
            # 个股风险评估
            for signal in self.trading_signals:
                individual_risk = {
                    'ts_code': signal['ts_code'],
                    'risk_level': signal['risk_level'],
                    'position_size': signal['position_size']
                }
                risk_assessment['individual_risks'].append(individual_risk)
                
            return risk_assessment
            
        except Exception as e:
            logger.error(f"风险评估失败: {e}")
            return {}
            
    def _generate_strategy_report(self) -> str:
        """生成策略报告"""
        report = []
        report.append("# 综合交易策略报告")
        report.append(f"**策略生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # 市场环境
        report.append("## 市场环境分析")
        market_state = self.macro_analyzer.market_state
        report.append(f"**当前市场状态**: {market_state}")
        
        if market_state == '强多':
            report.append("- **市场特征**: 经济强劲复苏，积极布局")
        elif market_state == '偏多':
            report.append("- **市场特征**: 经济温和复苏，稳健配置")
        elif market_state == '震荡':
            report.append("- **市场特征**: 经济基础不稳，谨慎操作")
        elif market_state == '偏空':
            report.append("- **市场特征**: 经济下行压力，防御为主")
        else:
            report.append("- **市场特征**: 数据不足，谨慎观望")
        report.append("")
        
        # 交易信号汇总
        report.append("## 交易信号汇总")
        signal_counts = {}
        for signal in self.trading_signals:
            signal_type = signal['trading_signal']
            signal_counts[signal_type] = signal_counts.get(signal_type, 0) + 1
            
        for signal_type, count in signal_counts.items():
            report.append(f"- **{signal_type}**: {count}只股票")
        report.append("")
        
        # 强烈买入建议
        if self.portfolio_recommendations['strong_buy']:
            report.append("## 强烈买入建议")
            report.append("| 股票代码 | 股票名称 | 仓位建议 | 综合评分 |")
            report.append("|----------|----------|----------|----------|")
            
            for rec in self.portfolio_recommendations['strong_buy'][:5]:
                # 获取股票名称
                stock_name = "N/A"
                for signal in self.trading_signals:
                    if signal['ts_code'] == rec['ts_code']:
                        stock_name = signal['stock_name']
                        break
                        
                report.append(f"| {rec['ts_code']} | {stock_name} | {rec['position_size']*100:.1f}% | {rec['score']:.1f} |")
            report.append("")
            
        # 买入建议
        if self.portfolio_recommendations['buy']:
            report.append("## 买入建议")
            report.append("| 股票代码 | 股票名称 | 仓位建议 | 综合评分 |")
            report.append("|----------|----------|----------|----------|")
            
            for rec in self.portfolio_recommendations['buy'][:5]:
                stock_name = "N/A"
                for signal in self.trading_signals:
                    if signal['ts_code'] == rec['ts_code']:
                        stock_name = signal['stock_name']
                        break
                        
                report.append(f"| {rec['ts_code']} | {stock_name} | {rec['position_size']*100:.1f}% | {rec['score']:.1f} |")
            report.append("")
            
        # 风险评估
        report.append("## 风险评估")
        report.append(f"- **组合风险等级**: {self.risk_assessments.get('portfolio_risk', 'medium')}")
        report.append(f"- **集中度风险**: {self.risk_assessments.get('concentration_risk', 'low')}")
        report.append(f"- **市场风险**: {self.risk_assessments.get('market_risk', 'medium')}")
        report.append("")
        
        # 操作建议
        report.append("## 操作建议")
        report.append("### 建议操作")
        if self.portfolio_recommendations['strong_buy']:
            report.append(f"- **重点配置**: {len(self.portfolio_recommendations['strong_buy'])}只强烈买入股票")
        if self.portfolio_recommendations['buy']:
            report.append(f"- **积极配置**: {len(self.portfolio_recommendations['buy'])}只买入股票")
        if self.portfolio_recommendations['reduce']:
            report.append(f"- **减仓操作**: {len(self.portfolio_recommendations['reduce'])}只建议减仓股票")
            
        report.append("")
        report.append("### 风险控制")
        report.append(f"- **单只股票最大仓位**: {self.position_limits['max_single_position']*100:.0f}%")
        report.append(f"- **止损阈值**: {self.position_limits['stop_loss_threshold']*100:.0f}%")
        report.append(f"- **止盈阈值**: {self.position_limits['take_profit_threshold']*100:.0f}%")
        
        return "\n".join(report)
        
    def _save_strategy_results(self, strategy_report: str):
        """保存策略结果"""
        try:
            # 创建策略结果表
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS trading_strategy_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_date TEXT NOT NULL,
                    market_state TEXT,
                    signals_count INTEGER,
                    strong_buy_count INTEGER,
                    buy_count INTEGER,
                    hold_count INTEGER,
                    sell_count INTEGER,
                    strong_sell_count INTEGER,
                    portfolio_risk TEXT,
                    strategy_report TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 统计信号数量
            signal_counts = {}
            for signal in self.trading_signals:
                signal_type = signal['trading_signal']
                signal_counts[signal_type] = signal_counts.get(signal_type, 0) + 1
                
            # 保存策略结果
            self.cursor.execute("""
                INSERT INTO trading_strategy_results (
                    strategy_date, market_state, signals_count,
                    strong_buy_count, buy_count, hold_count, sell_count, strong_sell_count,
                    portfolio_risk, strategy_report
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().strftime('%Y-%m-%d'),
                self.macro_analyzer.market_state,
                len(self.trading_signals),
                signal_counts.get('强烈买入', 0),
                signal_counts.get('买入', 0),
                signal_counts.get('持有', 0),
                signal_counts.get('卖出', 0),
                signal_counts.get('强烈卖出', 0),
                self.risk_assessments.get('portfolio_risk', 'medium'),
                strategy_report
            ))
            
            self.conn.commit()
            logger.info("交易策略结果已保存到数据库")
            
        except Exception as e:
            logger.error(f"保存策略结果失败: {e}")
            
    def close(self):
        """关闭连接"""
        self.observation_tracker.close()
        self.macro_analyzer.close()
        if hasattr(self, 'conn'):
            self.conn.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # 测试综合交易策略
    strategy_generator = ComprehensiveTradingStrategy()
    
    try:
        # 测试股票数据
        test_stocks = [
            {'ts_code': '000001.SZ', 'name': '平安银行', 'strategy_type': 'value'},
            {'ts_code': '000002.SZ', 'name': '万科A', 'strategy_type': 'value'},
            {'ts_code': '300750.SZ', 'name': '宁德时代', 'strategy_type': 'growth'},
            {'ts_code': '600000.SH', 'name': '浦发银行', 'strategy_type': 'value'},
            {'ts_code': '000858.SZ', 'name': '五粮液', 'strategy_type': 'value'}
        ]
        
        # 生成交易策略
        results = strategy_generator.generate_trading_strategy(test_stocks)
        
        # 输出策略报告
        print(results['report'])
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
    finally:
        strategy_generator.close()