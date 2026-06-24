"""
technical_integration.py - 技术面数据整合模块
将技术面数据整合到现有选股流程中
"""
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from technical_indicators import TechnicalIndicators
from volume_price_analysis import VolumePriceAnalysis
from enhanced_technical_scorer import EnhancedTechnicalScorer

logger = logging.getLogger(__name__)

class TechnicalIntegration:
    """技术面数据整合器"""
    
    def __init__(self, cursor):
        self.cursor = cursor
        self.ti = TechnicalIndicators(cursor)
        self.vpa = VolumePriceAnalysis(cursor)
        self.ets = EnhancedTechnicalScorer(cursor)
    
    def integrate_technical_analysis(self, stock_list: List[str], 
                                  strategy_type: str = 'growth') -> List[Dict]:
        """
        整合技术面分析到选股流程
        返回：整合后的股票分析结果
        """
        try:
            results = []
            
            for ts_code in stock_list:
                try:
                    # 获取基本面数据
                    fundamental_data = self._get_fundamental_data(ts_code)
                    
                    # 获取技术面数据
                    technical_data = self._get_technical_data(ts_code)
                    
                    # 获取量价数据
                    volume_price_data = self._get_volume_price_data(ts_code)
                    
                    # 获取综合评分
                    comprehensive_score = self._get_comprehensive_score(
                        ts_code, strategy_type, fundamental_data, 
                        technical_data, volume_price_data
                    )
                    
                    # 生成交易建议
                    trading_advice = self._generate_trading_advice(
                        ts_code, strategy_type, fundamental_data, 
                        technical_data, volume_price_data, comprehensive_score
                    )
                    
                    # 构建结果
                    result = {
                        'ts_code': ts_code,
                        'fundamental_data': fundamental_data,
                        'technical_data': technical_data,
                        'volume_price_data': volume_price_data,
                        'comprehensive_score': comprehensive_score,
                        'trading_advice': trading_advice,
                        'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    results.append(result)
                    
                except Exception as e:
                    logger.error(f"整合股票 {ts_code} 技术面分析失败: {e}")
                    continue
            
            # 按综合评分排序
            results.sort(key=lambda x: x['comprehensive_score']['total_score'], reverse=True)
            
            return results
            
        except Exception as e:
            logger.error(f"技术面整合失败: {e}")
            return []
    
    def get_integrated_signal(self, ts_code: str, trade_date: str, strategy_type: str = 'growth') -> Dict:
        """
        获取单个股票的技术面信号
        返回：技术面信号字典
        """
        try:
            # 获取交易日期前一个交易日
            prev_date_query = """
                SELECT MAX(trade_date) 
                FROM daily_quotes 
                WHERE ts_code = ? AND trade_date < ?
            """
            self.cursor.execute(prev_date_query, (ts_code, trade_date))
            prev_date = self.cursor.fetchone()[0]
            
            if not prev_date:
                return {'signal': 'wait', 'strength': 'unknown', 'score': 0}
            
            # 获取该股票在指定日期的技术面分析结果
            results = self.integrate_technical_analysis([ts_code], strategy_type)
            
            if results and len(results) > 0:
                result = results[0]
                comprehensive_score = result.get('comprehensive_score', {})
                total_score = comprehensive_score.get('total_score', 0)
                
                # 根据总分生成信号
                if total_score >= 80:
                    signal = 'buy'
                    strength = 'strong'
                elif total_score >= 60:
                    signal = 'buy'
                    strength = 'medium'
                elif total_score >= 40:
                    signal = 'hold'
                    strength = 'medium'
                else:
                    signal = 'wait'
                    strength = 'weak'
                
                return {
                    'signal': signal,
                    'strength': strength,
                    'score': total_score,
                    'strategy_type': strategy_type,
                    'details': result
                }
            else:
                return {'signal': 'wait', 'strength': 'unknown', 'score': 0}
                
        except Exception as e:
            logger.error(f"获取股票 {ts_code} 技术面信号失败: {e}")
            return {'signal': 'wait', 'strength': 'unknown', 'score': 0}
    
    def _get_fundamental_data(self, ts_code: str) -> Dict:
        """获取基本面数据"""
        try:
            # 获取财务指标
            self.cursor.execute("""
                SELECT roe, net_profit_yoy, eps, 
                       total_liab, total_assets,
                       net_margin, revenue_yoy
                FROM financial_data 
                WHERE ts_code = ? AND end_date = (
                    SELECT MAX(end_date) 
                    FROM financial_data 
                    WHERE ts_code = ?
                )
            """, (ts_code, ts_code))
            
            financial_row = self.cursor.fetchone()
            if financial_row:
                columns = ['roe', 'net_profit_yoy', 'eps', 
                          'total_liab', 'total_assets', 'net_margin', 'revenue_yoy']
                fundamental_data = dict(zip(columns, financial_row))
            else:
                fundamental_data = {}
            
            # 获取估值指标
            self.cursor.execute("""
                SELECT pe_ttm, pb, ps_ttm, ps, 
                       total_mv, circ_mv
                FROM valuation_data 
                WHERE ts_code = ? AND trade_date = (
                    SELECT MAX(trade_date) 
                    FROM valuation_data 
                    WHERE ts_code = ?
                )
            """, (ts_code, ts_code))
            
            valuation_row = self.cursor.fetchone()
            if valuation_row:
                columns = ['pe_ratio_ttm', 'pb_ratio_lf', 'ps_ratio_ttm', 
                          'ps_ratio', 'total_mv', 'circ_mv']
                fundamental_data.update(dict(zip(columns, valuation_row)))
            
            return fundamental_data
            
        except Exception as e:
            logger.error(f"获取股票 {ts_code} 基本面数据失败: {e}")
            return {}
    
    def _get_technical_data(self, ts_code: str) -> Dict:
        """获取技术面数据"""
        try:
            # 获取最新技术指标
            technical_indicators = self.ti.get_latest_technical_indicators(ts_code)
            
            # 获取增强版技术面评分
            enhanced_analysis = self.ets.score_technical_enhanced(ts_code)
            
            return {
                'indicators': technical_indicators,
                'enhanced_analysis': enhanced_analysis
            }
            
        except Exception as e:
            logger.error(f"获取股票 {ts_code} 技术面数据失败: {e}")
            return {}
    
    def _get_volume_price_data(self, ts_code: str) -> Dict:
        """获取量价数据"""
        try:
            # 获取量价关系分析
            volume_price_analysis = self.vpa.calculate_volume_price_relationship(ts_code)
            
            # 获取突破信号
            breakthrough_signals = self.vpa.detect_breakout_signals(ts_code)
            
            # 获取支撑阻力位
            support_resistance = self.vpa.identify_support_resistance(ts_code)
            
            return {
                'volume_price_analysis': volume_price_analysis,
                'breakthrough_signals': breakthrough_signals,
                'support_resistance': support_resistance
            }
            
        except Exception as e:
            logger.error(f"获取股票 {ts_code} 量价数据失败: {e}")
            return {}
    
    def _get_comprehensive_score(self, ts_code: str, strategy_type: str,
                               fundamental_data: Dict, technical_data: Dict,
                               volume_price_data: Dict) -> Dict:
        """
        计算综合评分
        根据策略类型调整各模块权重
        """
        try:
            # 基本面评分（40分）
            fundamental_score = self._score_fundamental_data(
                ts_code, strategy_type, fundamental_data
            )
            
            # 技术面评分（35分）
            technical_score = self._score_technical_data(
                ts_code, strategy_type, technical_data
            )
            
            # 量价评分（25分）
            volume_price_score = self._score_volume_price_data(
                ts_code, strategy_type, volume_price_data
            )
            
            # 根据策略类型调整权重
            if strategy_type == 'growth':
                # 成长股策略：基本面权重更高
                weights = {
                    'fundamental': 0.45,
                    'technical': 0.35,
                    'volume_price': 0.20
                }
            else:
                # 价值股策略：技术面和量价权重更高
                weights = {
                    'fundamental': 0.35,
                    'technical': 0.40,
                    'volume_price': 0.25
                }
            
            # 计算加权总分
            total_score = (
                fundamental_score * weights['fundamental'] +
                technical_score * weights['technical'] +
                volume_price_score * weights['volume_price']
            )
            
            return {
                'total_score': round(total_score, 2),
                'fundamental_score': round(fundamental_score, 2),
                'technical_score': round(technical_score, 2),
                'volume_price_score': round(volume_price_score, 2),
                'weights': weights,
                'strategy_type': strategy_type
            }
            
        except Exception as e:
            logger.error(f"计算股票 {ts_code} 综合评分失败: {e}")
            return {'total_score': 0, 'fundamental_score': 0, 'technical_score': 0, 'volume_price_score': 0}
    
    def _score_fundamental_data(self, ts_code: str, strategy_type: str,
                               fundamental_data: Dict) -> float:
        """基本面评分（满分40分）"""
        try:
            score = 0
            
            # ROE评分（10分）
            roe = fundamental_data.get('roe', 0)
            if roe > 15:
                score += 10
            elif roe > 10:
                score += 7
            elif roe > 5:
                score += 4
            elif roe > 0:
                score += 1
            
            # 净利润增长评分（8分）
            netprofit_growth = fundamental_data.get('net_profit_yoy', 0)
            if netprofit_growth > 30:
                score += 8
            elif netprofit_growth > 20:
                score += 6
            elif netprofit_growth > 10:
                score += 4
            elif netprofit_growth > 0:
                score += 2
            
            # PE评分（8分）
            pe_ratio = fundamental_data.get('pe_ratio_ttm', 0)
            if strategy_type == 'growth':
                # 成长股：PE可以较高
                if pe_ratio < 50:
                    score += 8
                elif pe_ratio < 80:
                    score += 5
                elif pe_ratio < 100:
                    score += 2
            # PE评分（10分）
            pe_ratio = fundamental_data.get('pe_ratio_ttm', 0)
            if pe_ratio and pe_ratio < 15:
                score += 10
            elif pe_ratio and pe_ratio < 25:
                score += 5
            elif pe_ratio and pe_ratio < 35:
                score += 2
            elif pe_ratio:
                score -= 5
            
            # PB评分（6分）
            pb_ratio = fundamental_data.get('pb_ratio_lf', 0)
            if pb_ratio and pb_ratio < 2:
                score += 6
            elif pb_ratio and pb_ratio < 4:
                score += 4
            elif pb_ratio and pb_ratio < 6:
                score += 2
            elif pb_ratio:
                score -= 2
            
            # 负债率评分（8分）
            total_assets = fundamental_data.get('total_assets', 0)
            total_liab = fundamental_data.get('total_liab', 0)
            if total_assets and total_liab and total_assets > 0:
                liability_ratio = total_liab / total_assets
                if liability_ratio < 0.3:
                    score += 8
                elif liability_ratio < 0.5:
                    score += 5
                elif liability_ratio < 0.7:
                    score += 2
                else:
                    score -= 3
            
            return min(40, max(0, score))
            
        except Exception as e:
            logger.error(f"基本面评分失败: {e}")
            return 0
    
    def _score_technical_data(self, ts_code: str, strategy_type: str,
                             technical_data: Dict) -> float:
        """技术面评分（满分35分）"""
        try:
            enhanced_signals = technical_data.get('enhanced_signals', {})
            total_score = enhanced_signals.get('total_score', 0)
            
            # 将100分制转换为35分制
            normalized_score = (total_score / 100) * 35
            
            return min(35, max(0, normalized_score))
            
        except Exception as e:
            logger.error(f"技术面评分失败: {e}")
            return 0
    
    def _score_volume_price_data(self, ts_code: str, strategy_type: str,
                                volume_price_data: Dict) -> float:
        """量价评分（满分25分）"""
        try:
            score = 0
            
            # 量价关系评分（10分）
            volume_price_analysis = volume_price_data.get('volume_price_analysis', {})
            relationship = volume_price_analysis.get('relationship', 'unknown')
            coordination = volume_price_analysis.get('coordination', 0)
            trend_consistency = volume_price_analysis.get('trend_consistency', 0)
            
            # 根据量价关系评分
            if relationship == 'strong_positive':
                score += 10
            elif relationship == 'weak_positive':
                score += 5
            elif relationship == 'neutral':
                score += 0
            elif relationship == 'weak_negative':
                score -= 5
            elif relationship == 'strong_negative':
                score -= 10
            
            # 根据配合度评分
            if coordination > 0.5:
                score += 5
            elif coordination > 0.3:
                score += 2
            elif coordination < 0.3:
                score -= 3
            
            # 根据趋势一致性评分
            if trend_consistency > 0.7:
                score += 5
            elif trend_consistency > 0.5:
                score += 2
            elif trend_consistency < 0.3:
                score -= 3
            
            # 突破信号评分（8分）
            breakthrough_signals = volume_price_data.get('breakthrough_signals', {})
            signal_type = breakthrough_signals.get('signal', 'no_breakout')
            
            if signal_type == 'upward_breakout':
                score += 8
            elif signal_type == 'downward_breakout':
                score -= 8
            
            # 支撑阻力位评分（7分）
            support_resistance = volume_price_data.get('support_resistance', {})
            current_price = support_resistance.get('current_price', 0)
            support_levels = support_resistance.get('support_levels', [])
            resistance_levels = support_resistance.get('resistance_levels', [])
            
            if support_levels and current_price > min([s['price'] for s in support_levels]) * 0.98:
                score += 7
            elif resistance_levels and current_price < min([r['price'] for r in resistance_levels]) * 1.02:
                score -= 5
            
            return min(25, max(0, score))
            
        except Exception as e:
            logger.error(f"量价评分失败: {e}")
            return 0
    
    def _generate_trading_advice(self, ts_code: str, strategy_type: str,
                               fundamental_data: Dict, technical_data: Dict,
                               volume_price_data: Dict, comprehensive_score: Dict) -> Dict:
        """生成交易建议"""
        try:
            total_score = comprehensive_score.get('total_score', 0)
            
            # 确定信号
            if total_score >= 30:
                signal = 'buy'
                strength = 'strong'
            elif total_score >= 20:
                signal = 'buy'
                strength = 'medium'
            elif total_score >= 15:
                signal = 'hold'
                strength = 'medium'
            elif total_score >= 10:
                signal = 'wait'
                strength = 'medium'
            else:
                signal = 'sell'
                strength = 'weak'
            
            # 生成理由
            reasons = []
            
            # 基本面理由
            roe = fundamental_data.get('roe_yearly', 0)
            if roe > 15:
                reasons.append(f"ROE高达{roe:.1f}%，盈利能力强")
            elif roe > 10:
                reasons.append(f"ROE{roe:.1f}%，盈利能力良好")
            
            # 技术面理由
            enhanced_signals = technical_data.get('enhanced_signals', {})
            technical_grade = enhanced_signals.get('grade', 'unknown')
            if technical_grade in ['强烈推荐', '推荐']:
                reasons.append(f"技术面{technical_grade}")
            
            # 量价理由
            volume_price_analysis = volume_price_data.get('volume_price_analysis', {})
            volume_trend = volume_price_analysis.get('volume_trend', 'unknown')
            price_trend = volume_price_analysis.get('price_trend', 'unknown')
            
            if volume_trend == 'increasing' and price_trend == 'increasing':
                reasons.append("量价齐升，趋势强劲")
            elif volume_trend == 'decreasing' and price_trend == 'increasing':
                reasons.append("价涨量缩，注意风险")
            
            # 风险提示
            risk_factors = []
            
            # 高估值风险
            pe_ratio = fundamental_data.get('pe_ratio_ttm', 0)
            if pe_ratio and pe_ratio > 50:
                risk_factors.append(f"PE比率{pe_ratio:.1f}，估值较高")
            
            # 高负债风险
            total_assets = fundamental_data.get('total_assets', 0)
            total_liab = fundamental_data.get('total_liab', 0)
            if total_assets and total_liab and total_assets > 0:
                liability_ratio = total_liab / total_assets
                if liability_ratio > 0.7:
                    risk_factors.append(f"负债率{liability_ratio:.1%}，风险较高")
            
            # 技术面风险
            rsi = technical_data.get('indicators', {}).get('rsi', 0)
            if rsi > 70:
                risk_factors.append(f"RSI{rsi:.1f}，技术面超买")
            
            return {
                'signal': signal,
                'strength': strength,
                'score': total_score,
                'reasons': reasons,
                'risk_factors': risk_factors,
                'strategy_type': strategy_type
            }
            
        except Exception as e:
            logger.error(f"生成交易建议失败: {e}")
            return {'signal': 'unknown', 'strength': 'unknown', 'score': 0, 'reasons': [], 'risk_factors': []}
    
    def generate_technical_report(self, results: List[Dict]) -> str:
        """生成技术面整合报告"""
        try:
            if not results:
                return "没有有效的分析结果"
            
            report_lines = []
            report_lines.append("# 技术面整合分析报告")
            report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report_lines.append(f"分析股票数量: {len(results)}")
            report_lines.append("")
            
            # 统计信息
            buy_count = sum(1 for r in results if r['trading_advice']['signal'] == 'buy')
            hold_count = sum(1 for r in results if r['trading_advice']['signal'] == 'hold')
            wait_count = sum(1 for r in results if r['trading_advice']['signal'] == 'wait')
            sell_count = sum(1 for r in results if r['trading_advice']['signal'] == 'sell')
            
            report_lines.append("## 信号统计")
            report_lines.append(f"- 买入信号: {buy_count}只股票")
            report_lines.append(f"- 持有信号: {hold_count}只股票")
            report_lines.append(f"- 观望信号: {wait_count}只股票")
            report_lines.append(f"- 卖出信号: {sell_count}只股票")
            report_lines.append("")
            
            # 排名前10的股票
            report_lines.append("## 排名前10的股票")
            report_lines.append("| 排名 | 股票代码 | 总分 | 信号 | 主要理由 |")
            report_lines.append("|------|----------|------|------|----------|")
            
            for i, result in enumerate(results[:10]):
                ts_code = result['ts_code']
                score = result['comprehensive_score']['total_score']
                signal = result['trading_advice']['signal']
                strength = result['trading_advice']['strength']
                
                signal_text = f"{signal}({strength})"
                reasons = ", ".join(result['trading_advice']['reasons'][:2])
                
                report_lines.append(f"| {i+1} | {ts_code} | {score:.1f} | {signal_text} | {reasons} |")
            
            report_lines.append("")
            
            # 详细分析
            report_lines.append("## 详细分析")
            for result in results[:5]:
                ts_code = result['ts_code']
                score = result['comprehensive_score']['total_score']
                signal = result['trading_advice']['signal']
                strength = result['trading_advice']['strength']
                
                report_lines.append(f"### {ts_code}")
                report_lines.append(f"- **总分**: {score:.1f}")
                report_lines.append(f"- **信号**: {signal}({strength})")
                report_lines.append(f"- **基本面得分**: {result['comprehensive_score']['fundamental_score']:.1f}")
                report_lines.append(f"- **技术面得分**: {result['comprehensive_score']['technical_score']:.1f}")
                report_lines.append(f"- **量价得分**: {result['comprehensive_score']['volume_price_score']:.1f}")
                
                reasons = result['trading_advice']['reasons']
                if reasons:
                    report_lines.append("- **主要理由**:")
                    for reason in reasons:
                        report_lines.append(f"  - {reason}")
                
                risk_factors = result['trading_advice']['risk_factors']
                if risk_factors:
                    report_lines.append("- **风险提示**:")
                    for risk in risk_factors:
                        report_lines.append(f"  - {risk}")
                
                report_lines.append("")
            
            return "\n".join(report_lines)
            
        except Exception as e:
            logger.error(f"生成技术面整合报告失败: {e}")
            return "生成报告失败"