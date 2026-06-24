"""
technical_indicators.py - 技术指标计算模块
实现主要技术指标：MA、MACD、RSI、布林带、成交量比等
"""
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from math import sqrt, pow

logger = logging.getLogger(__name__)

class TechnicalIndicators:
    """技术指标计算器"""
    
    def __init__(self, cursor):
        self.cursor = cursor
        
    def get_price_data(self, ts_code: str, start_date: str, end_date: str) -> List[Tuple]:
        """获取指定时间段的股价数据"""
        self.cursor.execute("""
            SELECT trade_date, open, high, low, close, volume, amount
            FROM daily_quotes
            WHERE ts_code = ? AND trade_date BETWEEN ? AND ?
            ORDER BY trade_date ASC
        """, (ts_code, start_date, end_date))
        return self.cursor.fetchall()
    
    def calculate_ma(self, ts_code: str, periods: List[int] = [5, 10, 20, 60]) -> Dict[int, List[float]]:
        """
        计算移动平均线
        periods: 周期列表，如[5, 10, 20, 60]
        返回: {period: [ma_values]}
        """
        # 获取足够的历史数据（最多需要60天）
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=max(periods) + 30)).strftime('%Y-%m-%d')
        
        price_data = self.get_price_data(ts_code, start_date, end_date)
        if not price_data:
            return {}
        
        # 计算各周期MA
        ma_results = {}
        for period in periods:
            ma_values = []
            for i in range(len(price_data)):
                if i < period - 1:
                    ma_values.append(None)
                else:
                    # 计算过去period天的收盘价平均值
                    close_sum = sum(price_data[j][4] for j in range(i - period + 1, i + 1))
                    ma_values.append(close_sum / period)
            
            ma_results[period] = ma_values
        
        return ma_results
    
    def calculate_ema(self, ts_code: str, periods: List[int] = [12, 26]) -> Dict[int, List[float]]:
        """
        计算指数移动平均线
        periods: 周期列表，如[12, 26]
        返回: {period: [ema_values]}
        """
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=max(periods) + 30)).strftime('%Y-%m-%d')
        
        price_data = self.get_price_data(ts_code, start_date, end_date)
        if not price_data:
            return {}
        
        ema_results = {}
        for period in periods:
            ema_values = []
            multiplier = 2 / (period + 1)
            
            for i in range(len(price_data)):
                if i == 0:
                    # 第一天EMA等于收盘价
                    ema_values.append(price_data[i][4])
                else:
                    # EMA = (今日收盘价 × 平滑系数) + (昨日EMA × (1-平滑系数))
                    ema = price_data[i][4] * multiplier + ema_values[-1] * (1 - multiplier)
                    ema_values.append(ema)
            
            ema_results[period] = ema_values
        
        return ema_results
    
    def calculate_macd(self, ts_code: str, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Dict[str, List[float]]:
        """
        计算MACD指标
        fast_period: 快线周期，默认12
        slow_period: 慢线周期，默认26
        signal_period: 信号线周期，默认9
        返回: {'macd': [], 'signal': [], 'histogram': []}
        """
        # 计算快线和慢线的EMA
        ema_fast = self.calculate_ema(ts_code, [fast_period])
        ema_slow = self.calculate_ema(ts_code, [slow_period])
        
        if not ema_fast or not ema_slow:
            return {}
        
        # 获取价格数据用于对应日期
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=max(fast_period, slow_period) + 30)).strftime('%Y-%m-%d')
        price_data = self.get_price_data(ts_code, start_date, end_date)
        
        if not price_data:
            return {}
        
        # 计算MACD线、信号线和柱状图
        macd_values = []
        signal_values = []
        histogram_values = []
        
        # 确保数据长度一致
        min_length = min(len(ema_fast[fast_period]), len(ema_slow[slow_period]), len(price_data))
        
        for i in range(min_length):
            if ema_fast[fast_period][i] is not None and ema_slow[slow_period][i] is not None:
                macd = ema_fast[fast_period][i] - ema_slow[slow_period][i]
                macd_values.append(macd)
            else:
                macd_values.append(None)
        
        # 计算信号线（MACD的EMA）
        if macd_values:
            signal_multiplier = 2 / (signal_period + 1)
            for i in range(len(macd_values)):
                if i == 0:
                    signal_values.append(macd_values[i])
                else:
                    signal = macd_values[i] * signal_multiplier + signal_values[-1] * (1 - signal_multiplier)
                    signal_values.append(signal)
        else:
            signal_values = [None] * len(macd_values)
        
        # 计算柱状图（MACD - Signal）
        histogram_values = []
        for i in range(len(macd_values)):
            if macd_values[i] is not None and signal_values[i] is not None:
                histogram = macd_values[i] - signal_values[i]
                histogram_values.append(histogram)
            else:
                histogram_values.append(None)
        
        return {
            'macd': macd_values,
            'signal': signal_values,
            'histogram': histogram_values
        }
    
    def calculate_rsi(self, ts_code: str, period: int = 14) -> List[float]:
        """
        计算RSI指标
        period: 计算周期，默认14
        返回: [rsi_values]
        """
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=period + 30)).strftime('%Y-%m-%d')
        
        price_data = self.get_price_data(ts_code, start_date, end_date)
        if not price_data:
            return []
        
        rsi_values = []
        
        for i in range(len(price_data)):
            if i < period:
                rsi_values.append(None)
                continue
            
            # 计算过去period天的涨跌幅
            gains = []
            losses = []
            
            for j in range(i - period + 1, i + 1):
                close_change = price_data[j][4] - price_data[j-1][4]
                if close_change > 0:
                    gains.append(close_change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(close_change))
            
            # 计算平均涨跌幅
            avg_gain = sum(gains) / period
            avg_loss = sum(losses) / period
            
            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            
            rsi_values.append(rsi)
        
        return rsi_values
    
    def calculate_bollinger_bands(self, ts_code: str, period: int = 20, std_dev: float = 2) -> Dict[str, List[float]]:
        """
        计算布林带
        period: 计算周期，默认20
        std_dev: 标准差倍数，默认2
        返回: {'upper': [], 'middle': [], 'lower': []}
        """
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=period + 30)).strftime('%Y-%m-%d')
        
        price_data = self.get_price_data(ts_code, start_date, end_date)
        if not price_data:
            return {}
        
        upper_values = []
        middle_values = []
        lower_values = []
        
        for i in range(len(price_data)):
            if i < period - 1:
                upper_values.append(None)
                middle_values.append(None)
                lower_values.append(None)
                continue
            
            # 计算过去period天的收盘价
            closes = [price_data[j][4] for j in range(i - period + 1, i + 1)]
            
            # 计算简单移动平均线
            middle = sum(closes) / period
            middle_values.append(middle)
            
            # 计算标准差
            variance = sum(pow(close - middle, 2) for close in closes) / period
            std_deviation = sqrt(variance)
            
            # 计算布林带上下轨
            upper = middle + (std_dev * std_deviation)
            lower = middle - (std_dev * std_deviation)
            
            upper_values.append(upper)
            lower_values.append(lower)
        
        return {
            'upper': upper_values,
            'middle': middle_values,
            'lower': lower_values
        }
    
    def calculate_volume_ratio(self, ts_code: str, period: int = 20) -> List[float]:
        """
        计算量比
        period: 计算周期，默认20
        返回: [volume_ratio_values]
        """
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=period + 30)).strftime('%Y-%m-%d')
        
        price_data = self.get_price_data(ts_code, start_date, end_date)
        if not price_data:
            return []
        
        volume_ratio_values = []
        
        for i in range(len(price_data)):
            if i < period:
                volume_ratio_values.append(None)
                continue
            
            # 计算今日成交量
            today_volume = price_data[i][5]
            
            # 计算过去period天的平均成交量
            avg_volume = sum(price_data[j][5] for j in range(i - period + 1, i)) / period
            
            if avg_volume == 0:
                volume_ratio = 0
            else:
                volume_ratio = today_volume / avg_volume
            
            volume_ratio_values.append(volume_ratio)
        
        return volume_ratio_values
    
    def calculate_kdj(self, ts_code: str, period: int = 9) -> Dict[str, List[float]]:
        """
        计算KDJ指标
        period: 计算周期，默认9
        返回: {'k': [], 'd': [], 'j': []}
        """
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=period + 30)).strftime('%Y-%m-%d')
        
        price_data = self.get_price_data(ts_code, start_date, end_date)
        if not price_data:
            return {}
        
        k_values = []
        d_values = []
        j_values = []
        
        for i in range(len(price_data)):
            if i < period:
                k_values.append(None)
                d_values.append(None)
                j_values.append(None)
                continue
            
            # 计算RSV
            period_high = max(price_data[j][2] for j in range(i - period + 1, i + 1))
            period_low = min(price_data[j][3] for j in range(i - period + 1, i + 1))
            period_close = price_data[i][4]
            
            if period_high == period_low:
                rsv = 0
            else:
                rsv = (period_close - period_low) / (period_high - period_low) * 100
            
            # 计算K值
            if i == period:
                k = rsv
            else:
                k = (k_values[-1] * 2 + rsv) / 3
            
            # 计算D值
            if i == period:
                d = rsv
            else:
                d = (d_values[-1] * 2 + k) / 3
            
            # 计算J值
            j = 3 * k - 2 * d
            
            k_values.append(k)
            d_values.append(d)
            j_values.append(j)
        
        return {
            'k': k_values,
            'd': d_values,
            'j': j_values
        }
    
    def calculate_williams_r(self, ts_code: str, period: int = 14) -> List[float]:
        """
        计算威廉指标
        period: 计算周期，默认14
        返回: [williams_r_values]
        """
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=period + 30)).strftime('%Y-%m-%d')
        
        price_data = self.get_price_data(ts_code, start_date, end_date)
        if not price_data:
            return []
        
        williams_r_values = []
        
        for i in range(len(price_data)):
            if i < period:
                williams_r_values.append(None)
                continue
            
            # 计算周期内最高价和最低价
            period_high = max(price_data[j][2] for j in range(i - period + 1, i + 1))
            period_low = min(price_data[j][3] for j in range(i - period + 1, i + 1))
            period_close = price_data[i][4]
            
            if period_high == period_low:
                williams_r = 0
            else:
                williams_r = (period_high - period_close) / (period_high - period_low) * 100
            
            williams_r_values.append(williams_r)
        
        return williams_r_values
    
    def calculate_atr(self, ts_code: str, period: int = 14) -> List[float]:
        """
        计算平均真实波幅
        period: 计算周期，默认14
        返回: [atr_values]
        """
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=period + 30)).strftime('%Y-%m-%d')
        
        price_data = self.get_price_data(ts_code, start_date, end_date)
        if not price_data:
            return []
        
        tr_values = []
        atr_values = []
        
        for i in range(len(price_data)):
            if i == 0:
                tr_values.append(None)
                atr_values.append(None)
                continue
            
            # 计算真实波幅
            high = price_data[i][2]
            low = price_data[i][3]
            prev_close = price_data[i-1][4]
            
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_values.append(tr)
        
        # 计算ATR
        for i in range(len(tr_values)):
            if i < period:
                atr_values.append(None)
                continue
            
            atr = sum(tr_values[i - period + 1:i + 1]) / period
            atr_values.append(atr)
        
        return atr_values
    
    def get_latest_technical_indicators(self, ts_code: str) -> Dict:
        """
        获取最新的技术指标值
        返回: 包含所有最新技术指标的字典
        """
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=100)).strftime('%Y-%m-%d')
        
        price_data = self.get_price_data(ts_code, start_date, end_date)
        if not price_data:
            return {}
        
        # 计算各技术指标
        ma_results = self.calculate_ma(ts_code)
        macd_results = self.calculate_macd(ts_code)
        rsi_results = self.calculate_rsi(ts_code)
        bb_results = self.calculate_bollinger_bands(ts_code)
        volume_ratio_results = self.calculate_volume_ratio(ts_code)
        kdj_results = self.calculate_kdj(ts_code)
        williams_r_results = self.calculate_williams_r(ts_code)
        atr_results = self.calculate_atr(ts_code)
        
        # 获取最新值（去掉None值）
        latest_values = {}
        
        # MA值
        for period, values in ma_results.items():
            valid_values = [v for v in values if v is not None]
            if valid_values:
                latest_values[f'ma_{period}'] = valid_values[-1]
        
        # MACD值
        for key, values in macd_results.items():
            valid_values = [v for v in values if v is not None]
            if valid_values:
                latest_values[f'macd_{key}'] = valid_values[-1]
        
        # RSI值
        valid_rsi = [v for v in rsi_results if v is not None]
        if valid_rsi:
            latest_values['rsi'] = valid_rsi[-1]
        
        # 布林带值
        for key, values in bb_results.items():
            valid_values = [v for v in values if v is not None]
            if valid_values:
                latest_values[f'bb_{key}'] = valid_values[-1]
        
        # 量比值
        valid_volume_ratio = [v for v in volume_ratio_results if v is not None]
        if valid_volume_ratio:
            latest_values['volume_ratio'] = valid_volume_ratio[-1]
        
        # KDJ值
        for key, values in kdj_results.items():
            valid_values = [v for v in values if v is not None]
            if valid_values:
                latest_values[f'kdj_{key}'] = valid_values[-1]
        
        # 威廉指标值
        valid_williams_r = [v for v in williams_r_results if v is not None]
        if valid_williams_r:
            latest_values['williams_r'] = valid_williams_r[-1]
        
        # ATR值
        valid_atr = [v for v in atr_results if v is not None]
        if valid_atr:
            latest_values['atr'] = valid_atr[-1]
        
        return latest_values
    
    def analyze_trend(self, ts_code: str) -> Dict[str, str]:
        """
        分析趋势
        返回: 趋势分析结果
        """
        latest_indicators = self.get_latest_technical_indicators(ts_code)
        if not latest_indicators:
            return {'trend': 'unknown', 'signal': 'unknown'}
        
        trend_signals = []
        
        # MA趋势分析
        ma_20 = latest_indicators.get('ma_20')
        ma_60 = latest_indicators.get('ma_60')
        if ma_20 and ma_60:
            if ma_20 > ma_60:
                trend_signals.append('ma_bullish')
            else:
                trend_signals.append('ma_bearish')
        
        # MACD趋势分析
        macd = latest_indicators.get('macd_macd')
        signal = latest_indicators.get('macd_signal')
        if macd is not None and signal is not None:
            if macd > signal:
                trend_signals.append('macd_bullish')
            else:
                trend_signals.append('macd_bearish')
        
        # RSI趋势分析
        rsi = latest_indicators.get('rsi')
        if rsi is not None:
            if rsi < 30:
                trend_signals.append('rsi_oversold')
            elif rsi > 70:
                trend_signals.append('rsi_overbought')
        
        # 布林带分析
        bb_upper = latest_indicators.get('bb_upper')
        bb_middle = latest_indicators.get('bb_middle')
        bb_lower = latest_indicators.get('bb_lower')
        close = self.get_latest_close(ts_code)
        
        if all([bb_upper, bb_middle, bb_lower, close]):
            if close < bb_lower:
                trend_signals.append('bb_oversold')
            elif close > bb_upper:
                trend_signals.append('bb_overbought')
        
        # 综合判断趋势
        bullish_signals = sum(1 for signal in trend_signals if 'bullish' in signal or 'oversold' in signal)
        bearish_signals = sum(1 for signal in trend_signals if 'bearish' in signal or 'overbought' in signal)
        
        if bullish_signals > bearish_signals:
            trend = 'bullish'
        elif bearish_signals > bullish_signals:
            trend = 'bearish'
        else:
            trend = 'neutral'
        
        # 生成交易信号
        if trend == 'bullish' and 'rsi_oversold' in trend_signals:
            signal = 'buy'
        elif trend == 'bearish' and 'rsi_overbought' in trend_signals:
            signal = 'sell'
        else:
            signal = 'hold'
        
        return {
            'trend': trend,
            'signals': trend_signals,
            'signal': signal
        }
    
    def get_latest_close(self, ts_code: str) -> Optional[float]:
        """获取最新收盘价"""
        self.cursor.execute("""
            SELECT close FROM daily_quotes
            WHERE ts_code = ?
            ORDER BY trade_date DESC
            LIMIT 1
        """, (ts_code,))
        row = self.cursor.fetchone()
        return row[0] if row else None