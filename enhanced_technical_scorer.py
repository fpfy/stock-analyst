"""
enhanced_technical_scorer.py - 增强版技术面评分系统
整合量价分析到技术面评分系统中
"""
import sqlite3
import logging
from typing import Dict, List, Optional
from technical_indicators import TechnicalIndicators
from volume_price_analysis import VolumePriceAnalysis

logger = logging.getLogger(__name__)

class EnhancedTechnicalScorer:
    """增强版技术面评分器"""
    
    def __init__(self, cursor):
        self.cursor = cursor
        self.ti = TechnicalIndicators(cursor)
        self.vpa = VolumePriceAnalysis(cursor)
    
    def score_technical_enhanced(self, ts_code: str) -> Dict[str, any]:
        """
        增强版技术面综合评分
        整合技术指标和量价分析
        """
        # 1. 基础技术指标评分
        technical_indicators = self.ti.get_latest_technical_indicators(ts_code)
        ti_score = self.score_technical_indicators(technical_indicators)
        
        # 2. 量价关系评分
        volume_price = self.vpa.calculate_volume_price_relationship(ts_code)
        vp_score = self.score_volume_price_relationship(volume_price)
        
        # 3. 突破信号评分
        breakout = self.vpa.detect_breakout_signals(ts_code)
        breakout_score = self.score_breakout_signals(breakout)
        
        # 4. 支撑阻力位评分
        support_resistance = self.vpa.identify_support_resistance(ts_code)
        sr_score = self.score_support_resistance(support_resistance)
        
        # 5. 综合评分
        total_score = self.calculate_total_score(ti_score, vp_score, breakout_score, sr_score)
        
        # 6. 生成评级和信号
        rating = self.get_rating(total_score)
        signal = self.get_signal(total_score, breakout, support_resistance)
        
        # 7. 生成详细分析
        analysis = self.generate_detailed_analysis(
            technical_indicators, volume_price, breakout, support_resistance, total_score
        )
        
        return {
            'ts_code': ts_code,
            'total_score': total_score,
            'rating': rating,
            'signal': signal,
            'technical_indicators_score': ti_score,
            'volume_price_score': vp_score,
            'breakout_score': breakout_score,
            'support_resistance_score': sr_score,
            'technical_indicators': technical_indicators,
            'volume_price': volume_price,
            'breakout': breakout,
            'support_resistance': support_resistance,
            'analysis': analysis,
            'generated_at': self.get_current_timestamp()
        }
    
    def score_technical_indicators(self, ti: Dict) -> Dict[str, float]:
        """技术指标评分"""
        score_details = {}
        total_score = 0
        
        # MA趋势评分 (25分)
        ma_trend_score = self.score_ma_trend(ti)
        score_details['ma_trend'] = ma_trend_score
        total_score += ma_trend_score
        
        # MACD评分 (20分)
        macd_score = self.score_macd(ti)
        score_details['macd'] = macd_score
        total_score += macd_score
        
        # RSI评分 (15分)
        rsi_score = self.score_rsi(ti)
        score_details['rsi'] = rsi_score
        total_score += rsi_score
        
        # 布林带评分 (15分)
        bollinger_score = self.score_bollinger_bands(ti)
        score_details['bollinger_bands'] = bollinger_score
        total_score += bollinger_score
        
        # KDJ评分 (10分)
        kdj_score = self.score_kdj(ti)
        score_details['kdj'] = kdj_score
        total_score += kdj_score
        
        # 威廉指标评分 (5分)
        williams_score = self.score_williams_r(ti)
        score_details['williams_r'] = williams_score
        total_score += williams_score
        
        # ATR评分 (5分)
        atr_score = self.score_atr(ti)
        score_details['atr'] = atr_score
        total_score += atr_score
        
        # 成交量评分 (5分)
        volume_score = self.score_volume(ti)
        score_details['volume'] = volume_score
        total_score += volume_score
        
        return {
            'total': total_score,
            'details': score_details,
            'max_score': 100
        }
    
    def score_volume(self, ti: Dict) -> float:
        """成交量评分"""
        score = 0
        
        # 检查成交量变化
        volume = ti.get('volume', 0)
        avg_volume = ti.get('avg_volume', 0)
        
        # 成交量放大
        if volume > avg_volume * 1.5:
            score += 5
        # 成交量温和放大
        elif volume > avg_volume * 1.2:
            score += 3
        # 成交量萎缩
        elif volume < avg_volume * 0.5:
            score -= 5
        # 成交量温和萎缩
        elif volume < avg_volume * 0.8:
            score -= 3
        
        return score
    
    def score_ma_trend(self, ti: Dict) -> float:
        """MA趋势评分"""
        score = 0
        
        # 检查MA排列
        if ti.get('ma5', 0) > ti.get('ma10', 0) > ti.get('ma20', 0) > ti.get('ma60', 0):
            score = 25  # 完美多头排列
        elif ti.get('ma5', 0) > ti.get('ma10', 0) > ti.get('ma20', 0):
            score = 20  # 短期多头排列
        elif ti.get('ma10', 0) > ti.get('ma20', 0):
            score = 15  # 中期多头排列
        elif ti.get('ma20', 0) > ti.get('ma60', 0):
            score = 10  # 长期多头排列
        elif ti.get('ma5', 0) < ti.get('ma10', 0) < ti.get('ma20', 0) < ti.get('ma60', 0):
            score = -25  # 完美空头排列
        elif ti.get('ma5', 0) < ti.get('ma10', 0) < ti.get('ma20', 0):
            score = -20  # 短期空头排列
        else:
            score = 5  # 横盘整理
        
        return score
    
    def score_macd(self, ti: Dict) -> float:
        """MACD评分"""
        score = 0
        
        macd = ti.get('macd', 0)
        signal = ti.get('macd_signal', 0)
        hist = ti.get('macd_hist', 0)
        
        # MACD金叉
        if macd > signal and hist > 0:
            score += 10
        # MACD死叉
        elif macd < signal and hist < 0:
            score -= 10
        
        # MACD柱状图强度
        if abs(hist) > 0.5:
            score += 5
        elif abs(hist) > 0.2:
            score += 2
        
        # MACD趋势
        if macd > 0:
            score += 5
        elif macd < 0:
            score -= 5
        
        return max(-20, min(20, score))
    
    def score_rsi(self, ti: Dict) -> float:
        """RSI评分"""
        rsi = ti.get('rsi', 50)
        score = 0
        
        # RSI超卖
        if rsi < 30:
            score = 15
        # RSI超买
        elif rsi > 70:
            score = -15
        # RSI正常区间
        elif 30 <= rsi <= 50:
            score = 5
        else:
            score = -5
        
        return score
    
    def score_bollinger_bands(self, ti: Dict) -> float:
        """布林带评分"""
        score = 0
        
        upper = ti.get('boll_upper', 0)
        middle = ti.get('boll_mid', 0)
        lower = ti.get('boll_lower', 0)
        close = ti.get('close', 0)
        
        # 价格位置
        if close > upper:
            score = 15  # 强势突破上轨
        elif close < lower:
            score = -15  # 跌破下轨
        elif close > middle:
            score = 5  # 中轨上方
        else:
            score = -5  # 中轨下方
        
        # 布林带宽度
        width = (upper - lower) / middle if middle > 0 else 0
        if width > 0.1:
            score += 5  # 高波动
        elif width < 0.05:
            score -= 5  # 低波动
        
        return score
    
    def score_kdj(self, ti: Dict) -> float:
        """KDJ评分"""
        score = 0
        
        k = ti.get('kdj_k', 50)
        d = ti.get('kdj_d', 50)
        j = ti.get('kdj_j', 50)
        
        # KDJ金叉
        if k > d and k > 20 and d > 20:
            score += 10
        # KDJ死叉
        elif k < d and k < 80 and d < 80:
            score -= 10
        
        # KDJ超买超卖
        if k > 80 or d > 80:
            score -= 5
        elif k < 20 or d < 20:
            score += 5
        
        return score
    
    def score_williams_r(self, ti: Dict) -> float:
        """威廉指标评分"""
        wr = ti.get('williams_r', 50)
        score = 0
        
        # 超卖
        if wr < -80:
            score = 5
        # 超买
        elif wr > -20:
            score = -5
        
        return score
    
    def score_atr(self, ti: Dict) -> float:
        """ATR评分"""
        atr = ti.get('atr', 0)
        score = 0
        
        # ATR相对大小
        if atr > 0.05:
            score = 5  # 高波动
        elif atr < 0.01:
            score = -5  # 低波动
        
        return score
    
    def score_volume_price_relationship(self, vp: Dict) -> Dict[str, float]:
        """量价关系评分"""
        score_details = {}
        total_score = 0
        
        # 相关性评分 (30分)
        correlation_score = self.score_correlation(vp['correlation'])
        score_details['correlation'] = correlation_score
        total_score += correlation_score
        
        # 配合度评分 (30分)
        coordination_score = self.score_coordination(vp['coordination'])
        score_details['coordination'] = coordination_score
        total_score += coordination_score
        
        # 趋势一致性评分 (20分)
        trend_score = self.score_trend_consistency(vp['trend_consistency'])
        score_details['trend_consistency'] = trend_score
        total_score += trend_score
        
        # 量价关系类型评分 (20分)
        relationship_score = self.score_relationship_type(vp['relationship'])
        score_details['relationship_type'] = relationship_score
        total_score += relationship_score
        
        return {
            'total': total_score,
            'details': score_details,
            'max_score': 100
        }
    
    def score_correlation(self, correlation: float) -> float:
        """相关性评分"""
        if correlation > 0.7:
            return 30
        elif correlation > 0.5:
            return 20
        elif correlation > 0.3:
            return 10
        elif correlation > 0.1:
            return 5
        elif correlation > -0.1:
            return 0
        elif correlation > -0.3:
            return -5
        elif correlation > -0.5:
            return -10
        else:
            return -20
    
    def score_coordination(self, coordination: float) -> float:
        """配合度评分"""
        if coordination > 0.7:
            return 30
        elif coordination > 0.5:
            return 20
        elif coordination > 0.3:
            return 10
        elif coordination > 0.1:
            return 5
        elif coordination > -0.1:
            return 0
        elif coordination > -0.3:
            return -5
        elif coordination > -0.5:
            return -10
        else:
            return -20
    
    def score_trend_consistency(self, consistency: float) -> float:
        """趋势一致性评分"""
        if consistency > 0.8:
            return 20
        elif consistency > 0.6:
            return 15
        elif consistency > 0.4:
            return 10
        elif consistency > 0.2:
            return 5
        else:
            return 0
    
    def score_relationship_type(self, relationship: str) -> float:
        """量价关系类型评分"""
        scores = {
            'positive_strong': 20,
            'positive_weak': 10,
            'neutral': 0,
            'negative_weak': -10,
            'negative_strong': -20
        }
        return scores.get(relationship, 0)
    
    def score_breakout_signals(self, breakout: Dict) -> Dict[str, float]:
        """突破信号评分"""
        score_details = {}
        total_score = 0
        
        # 突破信号评分 (50分)
        signal_score = self.score_breakout_signal(breakout['signal'])
        score_details['signal'] = signal_score
        total_score += signal_score
        
        # 突破强度评分 (30分)
        strength_score = self.score_breakout_strength(breakout['breakout_strength'])
        score_details['strength'] = strength_score
        total_score += strength_score
        
        # 置信度评分 (20分)
        confidence_score = self.score_breakout_confidence(breakout['confidence'])
        score_details['confidence'] = confidence_score
        total_score += confidence_score
        
        return {
            'total': total_score,
            'details': score_details,
            'max_score': 100
        }
    
    def score_breakout_signal(self, signal: str) -> float:
        """突破信号评分"""
        scores = {
            'strong_upward_breakout': 50,
            'weak_upward_breakout': 30,
            'no_breakout': 0,
            'weak_downward_breakout': -30,
            'strong_downward_breakout': -50
        }
        return scores.get(signal, 0)
    
    def score_breakout_strength(self, strength: float) -> float:
        """突破强度评分"""
        if strength > 10:
            return 30
        elif strength > 5:
            return 20
        elif strength > 0:
            return 10
        elif strength > -5:
            return -10
        elif strength > -10:
            return -20
        else:
            return -30
    
    def score_breakout_confidence(self, confidence: float) -> float:
        """突破置信度评分"""
        return confidence * 20
    
    def score_support_resistance(self, sr: Dict) -> Dict[str, float]:
        """支撑阻力位评分"""
        if sr['status'] != 'success':
            return {'total': 0, 'details': {}, 'max_score': 100}
        
        score_details = {}
        total_score = 0
        
        # 当前价格位置评分 (40分)
        position_score = self.score_price_position(sr)
        score_details['position'] = position_score
        total_score += position_score
        
        # 支撑阻力位强度评分 (30分)
        strength_score = self.score_sr_strength(sr)
        score_details['strength'] = strength_score
        total_score += strength_score
        
        # 动态支撑阻力位评分 (30分)
        dynamic_score = self.score_dynamic_sr(sr)
        score_details['dynamic'] = dynamic_score
        total_score += dynamic_score
        
        return {
            'total': total_score,
            'details': score_details,
            'max_score': 100
        }
    
    def score_price_position(self, sr: Dict) -> float:
        """价格位置评分"""
        current_price = sr['current_price']
        support_levels = [s['price'] for s in sr['support_levels']]
        resistance_levels = [r['price'] for r in sr['resistance_levels']]
        
        # 检查是否接近支撑位
        for support in support_levels:
            if abs(current_price - support) / support < 0.02:
                return 40
        
        # 检查是否接近阻力位
        for resistance in resistance_levels:
            if abs(current_price - resistance) / resistance < 0.02:
                return -40
        
        # 中间位置
        return 0
    
    def score_sr_strength(self, sr: Dict) -> float:
        """支撑阻力位强度评分"""
        total_strength = 0
        
        for support in sr['support_levels']:
            total_strength += support['strength']
        
        for resistance in sr['resistance_levels']:
            total_strength += resistance['strength']
        
        return total_strength / (len(sr['support_levels']) + len(sr['resistance_levels'])) * 30
    
    def score_dynamic_sr(self, sr: Dict) -> float:
        """动态支撑阻力位评分"""
        current_price = sr['current_price']
        dynamic_support = sr['dynamic_levels']['dynamic_support']
        dynamic_resistance = sr['dynamic_levels']['dynamic_resistance']
        
        # 接近动态支撑位
        if abs(current_price - dynamic_support) / dynamic_support < 0.02:
            return 30
        # 接近动态阻力位
        elif abs(current_price - dynamic_resistance) / dynamic_resistance < 0.02:
            return -30
        
        return 0
    
    def calculate_total_score(self, ti_score: Dict, vp_score: Dict, breakout_score: Dict, sr_score: Dict) -> float:
        """计算综合评分"""
        # 权重分配
        weights = {
            'technical_indicators': 0.4,    # 40%
            'volume_price': 0.3,            # 30%
            'breakout': 0.2,                # 20%
            'support_resistance': 0.1       # 10%
        }
        
        total_score = (
            ti_score['total'] * weights['technical_indicators'] +
            vp_score['total'] * weights['volume_price'] +
            breakout_score['total'] * weights['breakout'] +
            sr_score['total'] * weights['support_resistance']
        )
        
        return total_score
    
    def get_rating(self, score: float) -> str:
        """获取评级"""
        if score >= 90:
            return '强烈推荐'
        elif score >= 75:
            return '推荐'
        elif score >= 60:
            return '观察'
        elif score >= 45:
            return '谨慎'
        else:
            return '放弃'
    
    def get_signal(self, score: float, breakout: Dict, sr: Dict) -> str:
        """获取交易信号"""
        if score >= 80:
            return '买入'
        elif score >= 60:
            return '持有'
        elif score >= 40:
            return '观望'
        else:
            return '卖出'
    
    def generate_detailed_analysis(self, ti: Dict, vp: Dict, breakout: Dict, sr: Dict, total_score: float) -> str:
        """生成详细分析"""
        analysis = f"技术面综合分析（总分：{total_score:.1f}）\n"
        analysis += "=" * 50 + "\n"
        
        # 技术指标分析
        analysis += "\n1. 技术指标分析：\n"
        analysis += f"   MA趋势：{self.get_ma_trend_description(ti)}\n"
        analysis += f"   MACD：{self.get_macd_description(ti)}\n"
        analysis += f"   RSI：{self.get_rsi_description(ti)}\n"
        analysis += f"   布林带：{self.get_bollinger_description(ti)}\n"
        
        # 量价关系分析
        analysis += "\n2. 量价关系分析：\n"
        analysis += f"   量价关系：{vp['analysis']}\n"
        
        # 突破信号分析
        analysis += "\n3. 突破信号分析：\n"
        analysis += f"   突破信号：{breakout['analysis']}\n"
        
        # 支撑阻力位分析
        if sr['status'] == 'success':
            analysis += "\n4. 支撑阻力位分析：\n"
            analysis += f"   {sr['analysis']}\n"
        
        # 综合建议
        analysis += "\n5. 综合建议：\n"
        if total_score >= 80:
            analysis += "   强烈推荐买入，技术面表现优异"
        elif total_score >= 60:
            analysis += "   建议持有，技术面表现良好"
        elif total_score >= 40:
            analysis += "   谨慎观望，技术面表现一般"
        else:
            analysis += "   建议卖出，技术面表现不佳"
        
        return analysis
    
    def get_ma_trend_description(self, ti: Dict) -> str:
        """获取MA趋势描述"""
        ma5 = ti.get('ma5', 0)
        ma10 = ti.get('ma10', 0)
        ma20 = ti.get('ma20', 0)
        ma60 = ti.get('ma60', 0)
        
        if ma5 > ma10 > ma20 > ma60:
            return "完美多头排列"
        elif ma5 > ma10 > ma20:
            return "短期多头排列"
        elif ma10 > ma20:
            return "中期多头排列"
        elif ma20 > ma60:
            return "长期多头排列"
        elif ma5 < ma10 < ma20 < ma60:
            return "完美空头排列"
        elif ma5 < ma10 < ma20:
            return "短期空头排列"
        else:
            return "横盘整理"
    
    def get_macd_description(self, ti: Dict) -> str:
        """获取MACD描述"""
        macd = ti.get('macd', 0)
        signal = ti.get('macd_signal', 0)
        hist = ti.get('macd_hist', 0)
        
        if macd > signal and hist > 0:
            return "MACD金叉，多头信号"
        elif macd < signal and hist < 0:
            return "MACD死叉，空头信号"
        else:
            return "MACD中性"
    
    def get_rsi_description(self, ti: Dict) -> str:
        """获取RSI描述"""
        rsi = ti.get('rsi', 50)
        
        if rsi < 30:
            return "RSI超卖，可能反弹"
        elif rsi > 70:
            return "RSI超买，可能回调"
        else:
            return "RSI正常区间"
    
    def get_bollinger_description(self, ti: Dict) -> str:
        """获取布林带描述"""
        upper = ti.get('boll_upper', 0)
        middle = ti.get('boll_mid', 0)
        lower = ti.get('boll_lower', 0)
        close = ti.get('close', 0)
        
        if close > upper:
            return "价格突破上轨，强势"
        elif close < lower:
            return "价格跌破下轨，弱势"
        elif close > middle:
            return "价格位于中轨上方，偏多"
        else:
            return "价格位于中轨下方，偏空"
    
    def get_current_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def batch_score_technical(self, ts_codes: List[str]) -> List[Dict]:
        """批量技术面评分"""
        results = []
        
        for ts_code in ts_codes:
            try:
                result = self.score_technical_enhanced(ts_code)
                results.append(result)
            except Exception as e:
                logger.error(f"评分失败 {ts_code}: {e}")
                results.append({
                    'ts_code': ts_code,
                    'error': str(e),
                    'generated_at': self.get_current_timestamp()
                })
        
        return results
    
    def get_top_stocks(self, ts_codes: List[str], top_n: int = 10) -> List[Dict]:
        """获取评分最高的股票"""
        results = self.batch_score_technical(ts_codes)
        
        # 过滤掉评分失败的股票
        valid_results = [r for r in results if 'error' not in r]
        
        # 按评分排序
        valid_results.sort(key=lambda x: x['total_score'], reverse=True)
        
        return valid_results[:top_n]