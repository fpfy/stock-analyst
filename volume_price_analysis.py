"""
volume_price_analysis.py - 量价分析模块
实现量价关系分析、突破信号检测、支撑阻力位识别等功能
"""
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from technical_indicators import TechnicalIndicators

logger = logging.getLogger(__name__)

class VolumePriceAnalysis:
    """量价分析器"""
    
    def __init__(self, cursor):
        self.cursor = cursor
        self.ti = TechnicalIndicators(cursor)
    
    def get_historical_data(self, ts_code: str, days: int = 30) -> List[Dict]:
        """获取历史价格和成交量数据"""
        self.cursor.execute("""
            SELECT trade_date, open, high, low, close, volume, amount, pct_change
            FROM daily_quotes 
            WHERE ts_code = ? 
            ORDER BY trade_date DESC 
            LIMIT ?
        """, (ts_code, days))
        
        columns = [desc[0] for desc in self.cursor.description]
        results = []
        
        for row in self.cursor.fetchall():
            result = dict(zip(columns, row))
            results.append(result)
        
        return results
    
    def calculate_volume_price_relationship(self, ts_code: str) -> Dict[str, float]:
        """
        分析量价关系
        返回：量价关系分析结果
        """
        data = self.get_historical_data(ts_code, 20)
        if len(data) < 10:
            return {'relationship': 'insufficient_data', 'confidence': 0}
        
        # 计算价格变化和成交量变化
        price_changes = []
        volume_changes = []
        
        for i in range(1, len(data)):
            price_change = (data[i]['close'] - data[i-1]['close']) / data[i-1]['close']
            volume_change = (data[i]['volume'] - data[i-1]['volume']) / data[i-1]['volume']
            price_changes.append(price_change)
            volume_changes.append(volume_change)
        
        # 计算量价相关性
        correlation = self.calculate_correlation(price_changes, volume_changes)
        
        # 分析量价关系类型
        if correlation > 0.5:
            relationship = 'positive_strong'  # 强正相关
        elif correlation > 0.2:
            relationship = 'positive_weak'    # 弱正相关
        elif correlation > -0.2:
            relationship = 'neutral'         # 中性
        elif correlation > -0.5:
            relationship = 'negative_weak'    # 弱负相关
        else:
            relationship = 'negative_strong'  # 强负相关
        
        # 计算量价配合度
        coordination = self.calculate_volume_price_coordination(data)
        
        # 计算量价趋势一致性
        trend_consistency = self.calculate_trend_consistency(data)
        
        return {
            'relationship': relationship,
            'correlation': correlation,
            'confidence': abs(correlation),
            'coordination': coordination,
            'trend_consistency': trend_consistency,
            'analysis': self.get_volume_price_description(relationship, coordination, trend_consistency)
        }
    
    def calculate_correlation(self, x: List[float], y: List[float]) -> float:
        """计算两个序列的相关系数"""
        if len(x) != len(y) or len(x) < 2:
            return 0
        
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi ** 2 for xi in x)
        sum_y2 = sum(yi ** 2 for yi in y)
        
        numerator = n * sum_xy - sum_x * sum_y
        denominator = (n * sum_x2 - sum_x ** 2) ** 0.5 * (n * sum_y2 - sum_y ** 2) ** 0.5
        
        if denominator == 0:
            return 0
        
        return numerator / denominator
    
    def calculate_volume_price_coordination(self, data: List[Dict]) -> float:
        """计算量价配合度"""
        if len(data) < 2:
            return 0
        
        coordination_score = 0
        total_checks = 0
        
        for i in range(1, len(data)):
            price_change = data[i]['close'] - data[i-1]['close']
            volume_change = data[i]['volume'] - data[i-1]['volume']
            
            # 量价同向（价格上涨，成交量增加；价格下跌，成交量减少）
            if (price_change > 0 and volume_change > 0) or (price_change < 0 and volume_change < 0):
                coordination_score += 1
            # 量价反向（价格上涨，成交量减少；价格下跌，成交量增加）
            elif (price_change > 0 and volume_change < 0) or (price_change < 0 and volume_change > 0):
                coordination_score -= 0.5
            
            total_checks += 1
        
        return coordination_score / total_checks if total_checks > 0 else 0
    
    def calculate_trend_consistency(self, data: List[Dict]) -> float:
        """计算趋势一致性"""
        if len(data) < 3:
            return 0
        
        # 计算短期趋势（5日）
        short_term_trend = self.calculate_trend(data[:5])
        # 计算中期趋势（10日）
        medium_term_trend = self.calculate_trend(data[:10])
        # 计算长期趋势（20日）
        long_term_trend = self.calculate_trend(data)
        
        # 计算趋势一致性
        consistency = 0
        if short_term_trend == medium_term_trend:
            consistency += 0.4
        if short_term_trend == long_term_trend:
            consistency += 0.3
        if medium_term_trend == long_term_trend:
            consistency += 0.3
        
        return consistency
    
    def calculate_trend(self, data: List[Dict]) -> str:
        """计算趋势方向"""
        if len(data) < 2:
            return 'neutral'
        
        first_price = data[0]['close']
        last_price = data[-1]['close']
        
        change_rate = (last_price - first_price) / first_price
        
        if change_rate > 0.02:
            return 'bullish'
        elif change_rate < -0.02:
            return 'bearish'
        else:
            return 'neutral'
    
    def get_volume_price_description(self, relationship: str, coordination: float, trend_consistency: float) -> str:
        """获取量价关系描述"""
        descriptions = {
            'positive_strong': '量价强正相关，价格上涨时成交量同步放大',
            'positive_weak': '量价弱正相关，价格与成交量有一定同向性',
            'neutral': '量价关系中性，价格与成交量无明显关联',
            'negative_weak': '量价弱负相关，价格上涨时成交量可能减少',
            'negative_strong': '量价强负相关，价格上涨时成交量明显减少'
        }
        
        base_desc = descriptions.get(relationship, '量价关系不明确')
        
        if coordination > 0.5:
            base_desc += '，量价配合良好'
        elif coordination < -0.5:
            base_desc += '，量价配合较差'
        
        if trend_consistency > 0.7:
            base_desc += '，趋势一致性高'
        elif trend_consistency < 0.4:
            base_desc += '，趋势一致性低'
        
        return base_desc
    
    def detect_breakout_signals(self, ts_code: str) -> Dict[str, any]:
        """
        检测突破信号
        返回：突破信号检测结果
        """
        data = self.get_historical_data(ts_code, 30)
        if len(data) < 20:
            return {'signal': 'insufficient_data', 'confidence': 0}
        
        # 计算关键价位
        key_levels = self.calculate_key_levels(data)
        
        # 检测向上突破
        upward_breakout = self.detect_upward_breakout(data, key_levels)
        
        # 检测向下突破
        downward_breakout = self.detect_downward_breakout(data, key_levels)
        
        # 计算突破强度
        breakout_strength = self.calculate_breakout_strength(data, upward_breakout, downward_breakout)
        
        # 生成突破信号
        signal = self.generate_breakout_signal(upward_breakout, downward_breakout, breakout_strength)
        
        return {
            'signal': signal['type'],
            'confidence': signal['confidence'],
            'upward_breakout': upward_breakout,
            'downward_breakout': downward_breakout,
            'breakout_strength': breakout_strength,
            'key_levels': key_levels,
            'analysis': signal['description']
        }
    
    def calculate_key_levels(self, data: List[Dict]) -> Dict[str, float]:
        """计算关键价位"""
        highs = [d['high'] for d in data]
        lows = [d['low'] for d in data]
        closes = [d['close'] for d in data]
        
        # 计算支撑位
        support_levels = []
        # 计算阻力位
        resistance_levels = []
        
        # 简单支撑位计算：近期低点
        for i in range(5, len(data)-5):
            local_low = min([d['low'] for d in data[i-5:i+5]])
            support_levels.append(local_low)
        
        # 简单阻力位计算：近期高点
        for i in range(5, len(data)-5):
            local_high = max([d['high'] for d in data[i-5:i+5]])
            resistance_levels.append(local_high)
        
        # 去重并排序
        support_levels = sorted(list(set(support_levels)))
        resistance_levels = sorted(list(set(resistance_levels)))
        
        return {
            'support': support_levels[:3] if support_levels else [],  # 取前3个支撑位
            'resistance': resistance_levels[:3] if resistance_levels else [],  # 取前3个阻力位
            'current_price': data[0]['close'],
            'price_range': {
                'min': min(lows),
                'max': max(highs),
                'avg': sum(closes) / len(closes)
            }
        }
    
    def detect_upward_breakout(self, data: List[Dict], key_levels: Dict) -> Dict[str, any]:
        """检测向上突破"""
        current_price = data[0]['close']
        resistance_levels = key_levels['resistance']
        
        if not resistance_levels:
            return {'detected': False, 'level': None, 'strength': 0}
        
        # 检测是否突破阻力位
        for resistance in resistance_levels:
            if current_price > resistance * 1.02:  # 突破2%
                # 计算突破强度
                strength = (current_price - resistance) / resistance
                volume_confirm = self.confirm_breakout_volume(data, 'upward')
                
                return {
                    'detected': True,
                    'level': resistance,
                    'strength': strength,
                    'volume_confirm': volume_confirm,
                    'date': data[0]['trade_date']
                }
        
        return {'detected': False, 'level': None, 'strength': 0}
    
    def detect_downward_breakout(self, data: List[Dict], key_levels: Dict) -> Dict[str, any]:
        """检测向下突破"""
        current_price = data[0]['close']
        support_levels = key_levels['support']
        
        if not support_levels:
            return {'detected': False, 'level': None, 'strength': 0}
        
        # 检测是否跌破支撑位
        for support in support_levels:
            if current_price < support * 0.98:  # 跌破2%
                # 计算突破强度
                strength = (support - current_price) / support
                volume_confirm = self.confirm_breakout_volume(data, 'downward')
                
                return {
                    'detected': True,
                    'level': support,
                    'strength': strength,
                    'volume_confirm': volume_confirm,
                    'date': data[0]['trade_date']
                }
        
        return {'detected': False, 'level': None, 'strength': 0}
    
    def confirm_breakout_volume(self, data: List[Dict], direction: str) -> bool:
        """确认突破成交量"""
        if len(data) < 3:
            return False
        
        current_volume = data[0]['volume']
        avg_volume = sum(d['volume'] for d in data[1:4]) / 3
        
        # 方向向上，需要放量
        if direction == 'upward':
            return current_volume > avg_volume * 1.5
        # 方向向下，放量或缩量都可以
        else:
            return current_volume > avg_volume * 0.8
    
    def calculate_breakout_strength(self, data: List[Dict], upward_breakout: Dict, downward_breakout: Dict) -> float:
        """计算突破强度"""
        strength = 0
        
        if upward_breakout['detected']:
            strength += upward_breakout['strength'] * 10
        if downward_breakout['detected']:
            strength -= downward_breakout['strength'] * 10
        
        # 添加成交量确认
        if len(data) >= 3:
            current_volume = data[0]['volume']
            avg_volume = sum(d['volume'] for d in data[1:4]) / 3
            volume_ratio = current_volume / avg_volume
            
            if volume_ratio > 1.5:
                strength += 2  # 放量突破加分
            elif volume_ratio < 0.8:
                strength -= 1  # 缩量突破减分
        
        return strength
    
    def generate_breakout_signal(self, upward_breakout: Dict, downward_breakout: Dict, strength: float) -> Dict[str, any]:
        """生成突破信号"""
        if upward_breakout['detected'] and strength > 5:
            return {
                'type': 'strong_upward_breakout',
                'confidence': min(1.0, strength / 10),
                'description': f'强烈向上突破阻力位{upward_breakout["level"]:.2f}，建议买入'
            }
        elif upward_breakout['detected'] and strength > 0:
            return {
                'type': 'weak_upward_breakout',
                'confidence': min(1.0, strength / 10),
                'description': f'向上突破阻力位{upward_breakout["level"]:.2f}，关注后续走势'
            }
        elif downward_breakout['detected'] and strength < -5:
            return {
                'type': 'strong_downward_breakout',
                'confidence': min(1.0, abs(strength) / 10),
                'description': f'强烈向下突破支撑位{downward_breakout["level"]:.2f}，建议卖出'
            }
        elif downward_breakout['detected'] and strength < 0:
            return {
                'type': 'weak_downward_breakout',
                'confidence': min(1.0, abs(strength) / 10),
                'description': f'向下突破支撑位{downward_breakout["level"]:.2f}，谨慎观望'
            }
        else:
            return {
                'type': 'no_breakout',
                'confidence': 0,
                'description': '未检测到明显的突破信号'
            }
    
    def identify_support_resistance(self, ts_code: str) -> Dict[str, any]:
        """
        识别支撑阻力位
        返回：支撑阻力位识别结果
        """
        data = self.get_historical_data(ts_code, 60)
        if len(data) < 20:
            return {'status': 'insufficient_data'}
        
        # 计算支撑位
        support_levels = self.calculate_support_levels(data)
        
        # 计算阻力位
        resistance_levels = self.calculate_resistance_levels(data)
        
        # 计算动态支撑阻力位
        dynamic_levels = self.calculate_dynamic_levels(data)
        
        # 生成支撑阻力位分析
        analysis = self.generate_support_resistance_analysis(support_levels, resistance_levels, dynamic_levels)
        
        return {
            'status': 'success',
            'support_levels': support_levels,
            'resistance_levels': resistance_levels,
            'dynamic_levels': dynamic_levels,
            'analysis': analysis,
            'current_price': data[0]['close'],
            'price_range': {
                'min': min(d['low'] for d in data),
                'max': max(d['high'] for d in data),
                'avg': sum(d['close'] for d in data) / len(data)
            }
        }
    
    def calculate_support_levels(self, data: List[Dict]) -> List[Dict]:
        """计算支撑位"""
        supports = []
        
        # 使用前20个数据点计算支撑位
        recent_data = data[:20]
        
        # 找到局部低点作为支撑位
        for i in range(2, len(recent_data)-2):
            if (recent_data[i]['low'] < recent_data[i-1]['low'] and 
                recent_data[i]['low'] < recent_data[i-2]['low'] and
                recent_data[i]['low'] < recent_data[i+1]['low'] and
                recent_data[i]['low'] < recent_data[i+2]['low']):
                
                # 计算支撑位强度
                strength = self.calculate_support_strength(recent_data, i)
                
                supports.append({
                    'price': recent_data[i]['low'],
                    'date': recent_data[i]['trade_date'],
                    'strength': strength,
                    'type': 'historical'
                })
        
        # 添加动态支撑位（基于移动平均线）
        ma20 = sum(d['close'] for d in recent_data[:20]) / 20
        supports.append({
            'price': ma20 * 0.98,  # MA20下方2%
            'date': data[0]['trade_date'],
            'strength': 0.7,
            'type': 'moving_average'
        })
        
        # 按强度排序
        supports.sort(key=lambda x: x['strength'], reverse=True)
        
        return supports[:3]  # 返回前3个支撑位
    
    def calculate_resistance_levels(self, data: List[Dict]) -> List[Dict]:
        """计算阻力位"""
        resistances = []
        
        # 使用前20个数据点计算阻力位
        recent_data = data[:20]
        
        # 找到局部高点作为阻力位
        for i in range(2, len(recent_data)-2):
            if (recent_data[i]['high'] > recent_data[i-1]['high'] and 
                recent_data[i]['high'] > recent_data[i-2]['high'] and
                recent_data[i]['high'] > recent_data[i+1]['high'] and
                recent_data[i]['high'] > recent_data[i+2]['high']):
                
                # 计算阻力位强度
                strength = self.calculate_resistance_strength(recent_data, i)
                
                resistances.append({
                    'price': recent_data[i]['high'],
                    'date': recent_data[i]['trade_date'],
                    'strength': strength,
                    'type': 'historical'
                })
        
        # 添加动态阻力位（基于移动平均线）
        ma20 = sum(d['close'] for d in recent_data[:20]) / 20
        resistances.append({
            'price': ma20 * 1.02,  # MA20上方2%
            'date': data[0]['trade_date'],
            'strength': 0.7,
            'type': 'moving_average'
        })
        
        # 按强度排序
        resistances.sort(key=lambda x: x['strength'], reverse=True)
        
        return resistances[:3]  # 返回前3个阻力位
    
    def calculate_support_strength(self, data: List[Dict], index: int) -> float:
        """计算支撑位强度"""
        support_price = data[index]['low']
        
        # 计算支撑位测试次数
        test_count = 0
        for i in range(index+1, len(data)):
            if abs(data[i]['low'] - support_price) / support_price < 0.02:
                test_count += 1
        
        # 计算支撑位强度
        strength = 0.5 + (test_count * 0.1)
        
        # 限制强度范围
        return min(1.0, strength)
    
    def calculate_resistance_strength(self, data: List[Dict], index: int) -> float:
        """计算阻力位强度"""
        resistance_price = data[index]['high']
        
        # 计算阻力位测试次数
        test_count = 0
        for i in range(index+1, len(data)):
            if abs(data[i]['high'] - resistance_price) / resistance_price < 0.02:
                test_count += 1
        
        # 计算阻力位强度
        strength = 0.5 + (test_count * 0.1)
        
        # 限制强度范围
        return min(1.0, strength)
    
    def calculate_dynamic_levels(self, data: List[Dict]) -> Dict[str, float]:
        """计算动态支撑阻力位"""
        current_price = data[0]['close']
        
        # 计算波动率
        volatility = self.calculate_volatility(data)
        
        # 动态支撑位 = 当前价格 - 波动率 * 2
        dynamic_support = current_price - volatility * 2
        
        # 动态阻力位 = 当前价格 + 波动率 * 2
        dynamic_resistance = current_price + volatility * 2
        
        return {
            'dynamic_support': dynamic_support,
            'dynamic_resistance': dynamic_resistance,
            'volatility': volatility
        }
    
    def calculate_volatility(self, data: List[Dict]) -> float:
        """计算波动率"""
        if len(data) < 2:
            return 0
        
        returns = []
        for i in range(1, len(data)):
            returns.append((data[i]['close'] - data[i-1]['close']) / data[i-1]['close'])
        
        # 计算标准差
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        volatility = variance ** 0.5
        
        return volatility
    
    def generate_support_resistance_analysis(self, supports: List[Dict], resistances: List[Dict], dynamic: Dict) -> str:
        """生成支撑阻力位分析"""
        analysis = "支撑阻力位分析：\n"
        
        # 支撑位分析
        if supports:
            analysis += f"主要支撑位：{supports[0]['price']:.2f}（强度：{supports[0]['strength']:.2f}）\n"
            if len(supports) > 1:
                analysis += f"次要支撑位：{supports[1]['price']:.2f}\n"
        
        # 阻力位分析
        if resistances:
            analysis += f"主要阻力位：{resistances[0]['price']:.2f}（强度：{resistances[0]['strength']:.2f}）\n"
            if len(resistances) > 1:
                analysis += f"次要阻力位：{resistances[1]['price']:.2f}\n"
        
        # 动态分析
        analysis += f"动态支撑位：{dynamic['dynamic_support']:.2f}\n"
        analysis += f"动态阻力位：{dynamic['dynamic_resistance']:.2f}\n"
        analysis += f"当前波动率：{dynamic['volatility']:.4f}\n"
        
        return analysis
    
    def get_volume_price_signals(self, ts_code: str) -> Dict[str, any]:
        """
        获取量价综合信号
        返回：量价分析综合结果
        """
        # 量价关系分析
        volume_price = self.calculate_volume_price_relationship(ts_code)
        
        # 突破信号检测
        breakout = self.detect_breakout_signals(ts_code)
        
        # 支撑阻力位识别
        support_resistance = self.identify_support_resistance(ts_code)
        
        # 综合分析
        comprehensive_analysis = self.generate_comprehensive_analysis(
            volume_price, breakout, support_resistance
        )
        
        return {
            'ts_code': ts_code,
            'volume_price_analysis': volume_price,
            'breakout_signals': breakout,
            'support_resistance': support_resistance,
            'comprehensive_signal': comprehensive_analysis,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def generate_comprehensive_analysis(self, volume_price: Dict, breakout: Dict, support_resistance: Dict) -> Dict[str, any]:
        """生成综合分析"""
        signal = 'hold'
        confidence = 0
        description = ''
        
        # 综合评分
        score = 0
        
        # 量价关系评分
        if volume_price['relationship'] == 'positive_strong':
            score += 30
        elif volume_price['relationship'] == 'positive_weak':
            score += 15
        elif volume_price['relationship'] == 'negative_strong':
            score -= 30
        elif volume_price['relationship'] == 'negative_weak':
            score -= 15
        
        # 突破信号评分
        if breakout['signal'] == 'strong_upward_breakout':
            score += 40
            signal = 'buy'
            confidence = breakout['confidence']
        elif breakout['signal'] == 'weak_upward_breakout':
            score += 20
            confidence = breakout['confidence']
        elif breakout['signal'] == 'strong_downward_breakout':
            score -= 40
            signal = 'sell'
            confidence = breakout['confidence']
        elif breakout['signal'] == 'weak_downward_breakout':
            score -= 20
            confidence = breakout['confidence']
        
        # 支撑阻力位评分
        if support_resistance['status'] == 'success':
            current_price = support_resistance['current_price']
            
            # 检查是否接近支撑位
            for support in support_resistance['support_levels']:
                if abs(current_price - support['price']) / support['price'] < 0.02:
                    score += 20
                    break
            
            # 检查是否接近阻力位
            for resistance in support_resistance['resistance_levels']:
                if abs(current_price - resistance['price']) / resistance['price'] < 0.02:
                    score -= 20
                    break
        
        # 确定最终信号
        if score >= 50:
            signal = 'buy'
            confidence = min(1.0, score / 100)
        elif score <= -50:
            signal = 'sell'
            confidence = min(1.0, abs(score) / 100)
        elif score >= 20:
            signal = 'hold'
            confidence = min(1.0, score / 100)
        else:
            signal = 'wait'
            confidence = min(1.0, abs(score) / 100)
        
        # 生成描述
        description = self.generate_signal_description(signal, confidence, volume_price, breakout, support_resistance)
        
        return {
            'signal': signal,
            'confidence': confidence,
            'score': score,
            'description': description
        }
    
    def generate_signal_description(self, signal: str, confidence: float, volume_price: Dict, breakout: Dict, support_resistance: Dict) -> str:
        """生成信号描述"""
        descriptions = {
            'buy': '买入信号',
            'sell': '卖出信号',
            'hold': '持有信号',
            'wait': '观望信号'
        }
        
        base_desc = f"{descriptions.get(signal, '信号不明确')}（置信度：{confidence:.2f}）\n"
        
        # 添加量价分析
        if volume_price['relationship'] != 'insufficient_data':
            base_desc += f"量价关系：{volume_price['analysis']}\n"
        
        # 添加突破分析
        if breakout['signal'] != 'insufficient_data':
            base_desc += f"突破信号：{breakout['analysis']}\n"
        
        # 添加支撑阻力分析
        if support_resistance['status'] == 'success':
            base_desc += f"支撑阻力：{support_resistance['analysis']}\n"
        
        return base_desc