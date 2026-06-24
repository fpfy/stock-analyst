"""
technical_scorer.py - 技术面评分系统
基于技术指标进行综合评分
"""
import sqlite3
import logging
from typing import Dict, List, Optional
from technical_indicators import TechnicalIndicators

logger = logging.getLogger(__name__)

class TechnicalScorer:
    """技术面评分器"""
    
    def __init__(self, cursor):
        self.cursor = cursor
        self.ti = TechnicalIndicators(cursor)
    
    def score_ma_trend(self, ts_code: str) -> int:
        """评分：MA趋势（20分）"""
        indicators = self.ti.get_latest_technical_indicators(ts_code)
        if not indicators:
            return 0
        
        ma_5 = indicators.get('ma_5')
        ma_10 = indicators.get('ma_10')
        ma_20 = indicators.get('ma_20')
        ma_60 = indicators.get('ma_60')
        
        score = 0
        
        # MA多头排列（5分）
        if all([ma_5, ma_10, ma_20, ma_60]):
            if ma_5 > ma_10 > ma_20 > ma_60:
                score += 5
            elif ma_5 > ma_10 > ma_20:
                score += 3
            elif ma_10 > ma_20:
                score += 1
        
        # MA短期趋势（5分）
        if ma_5 and ma_10:
            if ma_5 > ma_10:
                score += 5
            elif ma_5 < ma_10:
                score -= 2
        
        # MA中期趋势（5分）
        if ma_20 and ma_60:
            if ma_20 > ma_60:
                score += 5
            elif ma_20 < ma_60:
                score -= 2
        
        # MA长期趋势（5分）
        if ma_60:
            if ma_60 > 0:
                score += 5
            else:
                score -= 2
        
        return max(0, min(20, score))
    
    def score_macd(self, ts_code: str) -> int:
        """评分：MACD（15分）"""
        indicators = self.ti.get_latest_technical_indicators(ts_code)
        if not indicators:
            return 0
        
        macd = indicators.get('macd_macd')
        signal = indicators.get('macd_signal')
        histogram = indicators.get('macd_histogram')
        
        score = 0
        
        # MACD金叉（5分）
        if macd is not None and signal is not None:
            if macd > signal:
                score += 5
            else:
                score -= 2
        
        # MACD柱状图（5分）
        if histogram is not None:
            if histogram > 0:
                score += 5
            elif histogram < 0:
                score -= 2
        
        # MACD强度（5分）
        if macd is not None:
            if abs(macd) > 1:
                score += 5
            elif abs(macd) > 0.5:
                score += 2
            else:
                score -= 1
        
        return max(0, min(15, score))
    
    def score_rsi(self, ts_code: str) -> int:
        """评分：RSI（10分）"""
        indicators = self.ti.get_latest_technical_indicators(ts_code)
        if not indicators:
            return 0
        
        rsi = indicators.get('rsi')
        
        if rsi is None:
            return 0
        
        score = 0
        
        # RSI超卖（5分）
        if rsi < 30:
            score += 5
        elif rsi < 40:
            score += 3
        elif rsi < 50:
            score += 1
        elif rsi > 70:
            score -= 3
        elif rsi > 80:
            score -= 5
        
        # RSI趋势（5分）
        if rsi > 50:
            score += 5
        elif rsi < 50:
            score -= 2
        
        return max(0, min(10, score))
    
    def score_bollinger_bands(self, ts_code: str) -> int:
        """评分：布林带（10分）"""
        indicators = self.ti.get_latest_technical_indicators(ts_code)
        if not indicators:
            return 0
        
        bb_upper = indicators.get('bb_upper')
        bb_middle = indicators.get('bb_middle')
        bb_lower = indicators.get('bb_lower')
        close = self.ti.get_latest_close(ts_code)
        
        if not all([bb_upper, bb_middle, bb_lower, close]):
            return 0
        
        score = 0
        
        # 价格位置（5分）
        if close < bb_lower:
            score += 5  # 超卖
        elif close < bb_middle:
            score += 3  # 低位
        elif close > bb_upper:
            score -= 5  # 超买
        elif close > bb_middle:
            score -= 2  # 高位
        
        # 布林带宽度（5分）
        bb_width = bb_upper - bb_lower
        bb_middle_value = bb_middle
        if bb_middle_value > 0:
            bb_width_ratio = bb_width / bb_middle_value
            if bb_width_ratio < 0.1:
                score += 5  # 窄幅震荡
            elif bb_width_ratio < 0.2:
                score += 3  # 正常波动
            else:
                score -= 2  # 宽幅震荡
        
        return max(0, min(10, score))
    
    def score_volume(self, ts_code: str) -> int:
        """评分：成交量（15分）"""
        indicators = self.ti.get_latest_technical_indicators(ts_code)
        if not indicators:
            return 0
        
        volume_ratio = indicators.get('volume_ratio')
        close = self.ti.get_latest_close(ts_code)
        
        if volume_ratio is None or close is None:
            return 0
        
        score = 0
        
        # 量比（5分）
        if volume_ratio > 2:
            score += 5  # 放量
        elif volume_ratio > 1.5:
            score += 3  # 温和放量
        elif volume_ratio > 1:
            score += 1  # 正常量
        else:
            score -= 2  # 缩量
        
        # 量价配合（5分）
        # 这里需要获取前几天的数据来判断量价配合
        # 简化处理：假设量比>1.5且价格上涨为量价配合
        if volume_ratio > 1.5 and close > 0:
            score += 5
        
        # 成交量趋势（5分）
        # 这里需要获取历史成交量数据来判断趋势
        # 简化处理：假设量比>1.2为放量趋势
        if volume_ratio > 1.2:
            score += 5
        elif volume_ratio < 0.8:
            score -= 2
        
        return max(0, min(15, score))
    
    def score_kdj(self, ts_code: str) -> int:
        """评分：KDJ（10分）"""
        indicators = self.ti.get_latest_technical_indicators(ts_code)
        if not indicators:
            return 0
        
        k = indicators.get('kdj_k')
        d = indicators.get('kdj_d')
        j = indicators.get('kdj_j')
        
        score = 0
        
        # KDJ金叉（5分）
        if k is not None and d is not None:
            if k > d:
                score += 5
            else:
                score -= 2
        
        # KDJ超卖（5分）
        if k is not None and k < 20:
            score += 5
        elif k is not None and k < 30:
            score += 3
        elif k is not None and k > 80:
            score -= 5
        elif k is not None and k > 70:
            score -= 3
        
        return max(0, min(10, score))
    
    def score_williams_r(self, ts_code: str) -> int:
        """评分：威廉指标（5分）"""
        indicators = self.ti.get_latest_technical_indicators(ts_code)
        if not indicators:
            return 0
        
        williams_r = indicators.get('williams_r')
        
        if williams_r is None:
            return 0
        
        score = 0
        
        # 威廉指标超卖（5分）
        if williams_r < -80:
            score += 5
        elif williams_r < -50:
            score += 3
        elif williams_r > -20:
            score -= 5
        elif williams_r > 0:
            score -= 3
        
        return max(0, min(5, score))
    
    def score_atr(self, ts_code: str) -> int:
        """评分：ATR波动率（5分）"""
        indicators = self.ti.get_latest_technical_indicators(ts_code)
        if not indicators:
            return 0
        
        atr = indicators.get('atr')
        close = self.ti.get_latest_close(ts_code)
        
        if atr is None or close is None:
            return 0
        
        score = 0
        
        # ATR相对波动率（5分）
        atr_ratio = atr / close if close > 0 else 0
        
        if atr_ratio < 0.02:
            score += 5  # 低波动
        elif atr_ratio < 0.05:
            score += 3  # 正常波动
        elif atr_ratio < 0.1:
            score += 1  # 高波动
        else:
            score -= 2  # 极高波动
        
        return max(0, min(5, score))
    
    def score_technical(self, ts_code: str) -> Dict[str, int]:
        """
        技术面综合评分
        返回：各分项评分和总分
        """
        try:
            # 计算各分项评分
            ma_score = self.score_ma_trend(ts_code)
            macd_score = self.score_macd(ts_code)
            rsi_score = self.score_rsi(ts_code)
            bb_score = self.score_bollinger_bands(ts_code)
            volume_score = self.score_volume(ts_code)
            kdj_score = self.score_kdj(ts_code)
            williams_r_score = self.score_williams_r(ts_code)
            atr_score = self.score_atr(ts_code)
            
            # 计算总分
            total_score = (ma_score + macd_score + rsi_score + bb_score + 
                          volume_score + kdj_score + williams_r_score + atr_score)
            
            # 生成评分详情
            score_details = {
                'ma_trend': ma_score,
                'macd': macd_score,
                'rsi': rsi_score,
                'bollinger_bands': bb_score,
                'volume': volume_score,
                'kdj': kdj_score,
                'williams_r': williams_r_score,
                'atr': atr_score,
                'total': total_score
            }
            
            return score_details
            
        except Exception as e:
            logger.error(f"计算股票 {ts_code} 技术面评分失败: {e}")
            return {}
    
    def get_technical_grade(self, total_score: int) -> str:
        """
        根据总分获取技术面评级
        返回：评级字符串
        """
        if total_score >= 90:
            return "强烈推荐"
        elif total_score >= 75:
            return "推荐"
        elif total_score >= 60:
            return "观察"
        elif total_score >= 45:
            return "谨慎"
        else:
            return "放弃"
    
    def get_technical_reasons(self, score_details: Dict[str, int]) -> List[str]:
        """
        获取技术面评分理由
        返回：理由列表
        """
        reasons = []
        
        # MA趋势理由
        ma_score = score_details.get('ma_trend', 0)
        if ma_score >= 15:
            reasons.append("MA趋势强劲")
        elif ma_score >= 10:
            reasons.append("MA趋势良好")
        elif ma_score < 5:
            reasons.append("MA趋势较弱")
        
        # MACD理由
        macd_score = score_details.get('macd', 0)
        if macd_score >= 12:
            reasons.append("MACD金叉强势")
        elif macd_score >= 8:
            reasons.append("MACD金叉形成")
        elif macd_score < 5:
            reasons.append("MACD死叉")
        
        # RSI理由
        rsi_score = score_details.get('rsi', 0)
        if rsi_score >= 8:
            reasons.append("RSI超卖机会")
        elif rsi_score >= 5:
            reasons.append("RSI相对低位")
        elif rsi_score < 3:
            reasons.append("RSI超买风险")
        
        # 布林带理由
        bb_score = score_details.get('bollinger_bands', 0)
        if bb_score >= 8:
            reasons.append("布林带超卖")
        elif bb_score >= 5:
            reasons.append("布林带低位")
        elif bb_score < 3:
            reasons.append("布林带超买")
        
        # 成交量理由
        volume_score = score_details.get('volume', 0)
        if volume_score >= 12:
            reasons.append("放量上涨")
        elif volume_score >= 8:
            reasons.append("温和放量")
        elif volume_score < 5:
            reasons.append("缩量调整")
        
        return reasons
    
    def analyze_technical_signals(self, ts_code: str) -> Dict[str, str]:
        """
        分析技术面信号
        返回：信号分析结果
        """
        score_details = self.score_technical(ts_code)
        if not score_details:
            return {'signal': 'unknown', 'grade': 'unknown', 'reasons': []}
        
        total_score = score_details.get('total', 0)
        grade = self.get_technical_grade(total_score)
        reasons = self.get_technical_reasons(score_details)
        
        # 生成交易信号
        if total_score >= 80:
            signal = "buy"
        elif total_score >= 60:
            signal = "hold"
        elif total_score >= 40:
            signal = "wait"
        else:
            signal = "sell"
        
        return {
            'signal': signal,
            'grade': grade,
            'total_score': total_score,
            'reasons': reasons,
            'score_details': score_details
        }