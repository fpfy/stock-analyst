"""
stock-valuation 实现：基于 value_six_dim_v2.py + main_v3.py 估值逻辑提取

依赖：tushare、sqlite3、valuation_data 表
"""
import sqlite3
from typing import Optional, Dict


class ValuationAnalyzer:
    """估值分析器：PE/PB/股息率分位、估值三角、异常检测"""

    def __init__(self, cursor: sqlite3.Cursor, ts_code: str):
        self.cursor = cursor
        self.ts_code = ts_code

    # ============================================================
    # 方法1：percentile_analysis — PE/PB 历史分位
    # ============================================================
    def percentile_analysis(self) -> Dict:
        """
        PE历史分位计算（优先近3年，回退全历史）
        返回: dict 含 pe_percentile / pb_percentile / dividend_yield / is_undervalued
        """
        result = {
            'pe_percentile': None,
            'pb_percentile': None,
            'dividend_yield': None,
            'pe_current': None,
            'pb_current': None,
            'pe_median': None,
            'pb_median': None,
            'is_undervalued': False,
        }

        # PE 分位
        self.cursor.execute("""
            SELECT pe FROM valuation_data
            WHERE ts_code = ? AND pe IS NOT NULL AND pe > 0 AND pe < 10000
            ORDER BY trade_date ASC
        """, (self.ts_code,))
        pe_values = [r[0] for r in self.cursor.fetchall()]
        if len(pe_values) >= 5:
            current_pe = pe_values[-1]
            count_below = sum(1 for p in pe_values if p <= current_pe)
            all_time_pct = (count_below / len(pe_values)) * 100
            if len(pe_values) >= 250:
                recent = pe_values[-250:]
                count_below_recent = sum(1 for p in recent if p <= current_pe)
                recent_pct = (count_below_recent / len(recent)) * 100
                percentile = min(all_time_pct, recent_pct)
            else:
                percentile = all_time_pct
            result['pe_percentile'] = round(percentile, 1)
            result['pe_current'] = round(current_pe, 2)
            result['pe_median'] = round(sorted(pe_values)[len(pe_values) // 2], 2)

        # PB 分位（同逻辑）
        self.cursor.execute("""
            SELECT pb FROM valuation_data
            WHERE ts_code = ? AND pb IS NOT NULL AND pb > 0 AND pb < 100
            ORDER BY trade_date ASC
        """, (self.ts_code,))
        pb_values = [r[0] for r in self.cursor.fetchall()]
        if len(pb_values) >= 5:
            current_pb = pb_values[-1]
            count_below = sum(1 for p in pb_values if p <= current_pb)
            all_time_pct = (count_below / len(pb_values)) * 100
            if len(pb_values) >= 250:
                recent = pb_values[-250:]
                count_below_recent = sum(1 for p in recent if p <= current_pb)
                recent_pct = (count_below_recent / len(recent)) * 100
                percentile = min(all_time_pct, recent_pct)
            else:
                percentile = all_time_pct
            result['pb_percentile'] = round(percentile, 1)
            result['pb_current'] = round(current_pb, 2)
            result['pb_median'] = round(sorted(pb_values)[len(pb_values) // 2], 2)

        # 股息率（取最近一期）
        self.cursor.execute("""
            SELECT dv_ttm FROM valuation_data
            WHERE ts_code = ? AND dv_ttm IS NOT NULL
            ORDER BY trade_date DESC LIMIT 1
        """, (self.ts_code,))
        row = self.cursor.fetchone()
        if row and row[0] is not None:
            result['dividend_yield'] = round(float(row[0]), 4)

        # 低估判定：PE 分位 < 30 或 PB 分位 < 30
        pe_pct = result.get('pe_percentile')
        pb_pct = result.get('pb_percentile')
        if pe_pct is not None and pe_pct < 30:
            result['is_undervalued'] = True
        elif pb_pct is not None and pb_pct < 30:
            result['is_undervalued'] = True

        return result

    # ============================================================
    # 方法2：triangular_analysis — 估值三角评分
    # ============================================================
    def triangular_analysis(self) -> Dict:
        """
        PE/PB/股息率三维估值评分
        返回: dict 含 valuation_score / rating
        """
        pct = self.percentile_analysis()
        score = 0

        # PE 分位（40%）
        pe_pct = pct.get('pe_percentile')
        if pe_pct is not None:
            if pe_pct < 20:
                score += 40
            elif pe_pct < 40:
                score += 30
            elif pe_pct < 60:
                score += 20
            elif pe_pct < 80:
                score += 10

        # PB 分位（30%）
        pb_pct = pct.get('pb_percentile')
        if pb_pct is not None:
            if pb_pct < 20:
                score += 30
            elif pb_pct < 40:
                score += 22
            elif pb_pct < 60:
                score += 15
            elif pb_pct < 80:
                score += 8

        # 股息率（30%）
        dy = pct.get('dividend_yield')
        if dy is not None:
            dy_pct = dy * 100
            if dy_pct >= 4:
                score += 30
            elif dy_pct >= 3:
                score += 22
            elif dy_pct >= 2:
                score += 15
            elif dy_pct >= 1:
                score += 8

        if score >= 75:
            rating = '低估'
        elif score >= 50:
            rating = '合理'
        else:
            rating = '高估'

        return {
            'valuation_score': score,
            'pe_score': pct.get('pe_percentile'),
            'pb_score': pct.get('pb_percentile'),
            'dividend_score': pct.get('dividend_yield'),
            'rating': rating,
            'is_undervalued': pct.get('is_undervalued', False),
        }

    # ============================================================
    # 方法3：detect_anomaly — 估值异常检测
    # ============================================================
    def detect_anomaly(self, window: int = 250) -> Dict:
        """
        检测 PE/PB 是否显著偏离历史均值
        window: 滚动窗口天数，默认 250（约1年）
        """
        result = {
            'is_anomaly': False,
            'anomaly_type': None,
            'deviation_pct': 0.0,
            'severity': 'low',
        }

        self.cursor.execute("""
            SELECT pe FROM valuation_data
            WHERE ts_code = ? AND pe IS NOT NULL AND pe > 0 AND pe < 10000
            ORDER BY trade_date DESC LIMIT ?
        """, (self.ts_code, window))
        pe_values = [r[0] for r in self.cursor.fetchall()]
        if len(pe_values) < 20:
            return result

        current_pe = pe_values[0]
        avg_pe = sum(pe_values) / len(pe_values)
        if avg_pe > 0:
            deviation = (current_pe - avg_pe) / avg_pe
            result['deviation_pct'] = round(deviation, 4)
            if abs(deviation) > 0.5:
                result['is_anomaly'] = True
                result['severity'] = 'high'
                result['anomaly_type'] = 'pe_spike'
            elif abs(deviation) > 0.3:
                result['is_anomaly'] = True
                result['severity'] = 'medium'
                result['anomaly_type'] = 'pe_spike'

        return result

    # ============================================================
    # 综合估值评分（供 stock-analysis 直接调用）
    # ============================================================
    def valuation_score(self) -> Dict:
        """
        返回综合估值结果，供选股流程直接使用
        """
        tri = self.triangular_analysis()
        anomaly = self.detect_anomaly()
        return {
            **tri,
            'anomaly': anomaly,
            'ts_code': self.ts_code,
        }
