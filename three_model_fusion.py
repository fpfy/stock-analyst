#!/usr/bin/env python3
"""
三模型融合模块
目的：将技术面、资金流/筹码面、宏观面三个模型融合为统一评分
输入：
  1. 技术面：technical_indicators 表（趋势、信号、MACD、RSI、布林带）
  2. 筹码/资金流：daily_quotes 表量价关系推导（换手率、量比、大单净流入）
  3. 宏观面：macro_factors 表 + 行业敏感度矩阵
输出：三模型融合评分，用于观察池最终排序
"""

import os
import sys
import logging
from typing import Dict, List, Optional

sys.path.insert(0, r'C:\Users\Fengpeng\stock_analysis_system')
logger = logging.getLogger(__name__)


class ThreeModelFusion:
    """三模型融合：技术 + 筹码/资金流 + 宏观"""

    def __init__(self, db_path: str = None):
        import sqlite3
        self.db_path = db_path or r'C:\Users\Fengpeng\stock_analysis_system\database\stock_analysis.db'
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.cursor = self.conn.cursor()

    def _get_latest_technical(self, ts_code: str) -> Optional[Dict]:
        """获取最新技术面评分"""
        self.cursor.execute("""
            SELECT trade_date, trend, signal, macd_hist, rsi, boll_upper, boll_mid, boll_lower
            FROM technical_indicators
            WHERE ts_code = ?
            ORDER BY trade_date DESC LIMIT 1
        """, (ts_code,))
        r = self.cursor.fetchone()
        if not r:
            return None
        cols = ['trade_date', 'trend', 'signal', 'macd_hist', 'rsi', 'boll_upper', 'boll_mid', 'boll_lower']
        return dict(zip(cols, r))

    def _get_latest_chip_metrics(self, ts_code: str) -> Optional[Dict]:
        """从 daily_quotes 推导筹码/资金流指标（近20日）"""
        self.cursor.execute("""
            SELECT trade_date, close, volume, amount, pct_change
            FROM daily_quotes
            WHERE ts_code = ?
            ORDER BY trade_date DESC LIMIT 20
        """, (ts_code,))
        rows = self.cursor.fetchall()
        if not rows or len(rows) < 5:
            return None
        cols = ['trade_date', 'close', 'volume', 'amount', 'pct_change']
        data = [dict(zip(cols, r)) for r in rows]
        # 最近一日指标
        latest = data[0]
        # 量能指标：今日成交量 / 近20日均量
        avg_vol = sum(d['volume'] for d in data) / len(data)
        vol_ratio = latest['volume'] / avg_vol if avg_vol > 0 else 1.0
        # 换手率（近似）：成交额 / (股价 * 股本) 这里用成交额作为相对活跃度
        # 大单净流入近似：pct_change * volume（正负号代表资金方向）
        net_inflow = latest['pct_change'] * latest['volume'] if latest['pct_change'] else 0
        return {
            'trade_date': latest['trade_date'],
            'close': latest['close'],
            'volume': latest['volume'],
            'amount': latest['amount'],
            'pct_change': latest['pct_change'],
            'vol_ratio': vol_ratio,
            'net_inflow_proxy': net_inflow,
            'avg_vol': avg_vol,
        }

    def _get_macro_score(self, ts_code: str) -> Optional[Dict]:
        """获取宏观评分（基于行业敏感度矩阵）"""
        try:
            # 获取该股票的行业
            self.cursor.execute("""
                SELECT industry_code FROM stock_basic WHERE ts_code = ?
            """, (ts_code,))
            row = self.cursor.fetchone()
            if not row:
                return None
            industry_code = row[0]

            # 加载最新宏观敏感度
            factors_path = os.path.join(os.path.dirname(self.db_path), '..', 'data', 'industry_sensitivity_rolling_ols.parquet')
            if not os.path.exists(factors_path):
                return {'industry_code': industry_code, 'macro_score': 50.0}
            
            factors = pd.read_parquet(factors_path)
            latest = factors[factors['industry_code'] == industry_code]
            if latest.empty:
                return {'industry_code': industry_code, 'macro_score': 50.0}
            
            # 简化：取各因子beta均值作为宏观敏感度
            beta_cols = [c for c in latest.columns if c.endswith('_beta')]
            if beta_cols:
                macro_score = latest[beta_cols].mean().mean()
                # 归一化到0-100（假设beta范围约-0.5到0.5）
                macro_score = max(0, min(100, (macro_score + 0.5) * 100))
            else:
                macro_score = 50.0
            
            return {'industry_code': industry_code, 'macro_score': round(macro_score, 2)}
        except Exception as e:
            logger.debug(f"获取宏观评分失败 {ts_code}: {e}")
            return None

    def score_technical(self, tech: Dict) -> float:
        """技术面评分 0-100"""
        if not tech:
            return 50.0
        score = 50.0
        # 趋势加分
        if tech.get('trend') == 'bullish':
            score += 15
        elif tech.get('trend') == 'bearish':
            score -= 15
        # 信号加分
        if tech.get('signal') == 'buy':
            score += 15
        elif tech.get('signal') == 'sell':
            score -= 15
        # MACD柱状图
        macd_hist = tech.get('macd_hist') or 0
        if macd_hist > 0:
            score += min(macd_hist * 10, 10)
        else:
            score += max(macd_hist * 10, -10)
        # RSI过滤
        rsi = tech.get('rsi')
        if rsi is not None:
            if rsi >= 70:
                score -= 5  # 超买
            elif rsi <= 30:
                score += 5  # 超卖
        # 布林带位置
        close = tech.get('close') or tech.get('boll_mid')
        if close and tech.get('boll_upper') and tech.get('boll_lower'):
            if close > tech['boll_upper']:
                score -= 5
            elif close < tech['boll_lower']:
                score += 5
        return max(0, min(100, score))

    def score_chip(self, chip: Dict) -> float:
        """筹码/资金流评分 0-100"""
        if not chip:
            return 50.0
        score = 50.0
        # 量比：放量加分，缩水减分
        vol_ratio = chip.get('vol_ratio', 1.0)
        if vol_ratio > 1.5:
            score += 10
        elif vol_ratio < 0.6:
            score -= 10
        # 资金净流入近似
        net_inflow = chip.get('net_inflow_proxy', 0)
        if net_inflow > 0:
            score += min(net_inflow / 1e6, 10)  # 归一化
        else:
            score += max(net_inflow / 1e6, -10)
        # 涨跌幅
        pct = chip.get('pct_change') or 0
        if pct > 0:
            score += min(pct * 2, 10)
        else:
            score += max(pct * 2, -10)
        return max(0, min(100, score))

    def score_macro(self, macro: Dict) -> float:
        """宏观评分 0-100"""
        if not macro:
            return 50.0
        raw = macro.get('macro_score', 50)
        # 归一化到0-100
        return max(0, min(100, raw))

    def fuse(self, ts_code: str, weights: Dict[str, float] = None, market_status: str = None) -> Optional[Dict]:
        """
        三模型融合评分
        weights: 各模型权重，默认 技术40% + 筹码30% + 宏观30%
        market_status: 市场状态 ('bull'/'bear'/'neutral')，用于动态调整权重
        """
        if weights is None:
            weights = {'technical': 0.40, 'chip': 0.30, 'macro': 0.30}
        
        # 根据市场状态动态调整权重
        if market_status == 'bull':
            # 牛市：加重技术面，减少宏观
            weights = {'technical': 0.50, 'chip': 0.30, 'macro': 0.20}
        elif market_status == 'bear':
            # 熊市：加重宏观，减少技术
            weights = {'technical': 0.30, 'chip': 0.20, 'macro': 0.50}
        elif market_status == 'neutral':
            # 震荡市：均衡
            weights = {'technical': 0.40, 'chip': 0.30, 'macro': 0.30}
        
        # 获取三个模型数据
        tech = self._get_latest_technical(ts_code)
        chip = self._get_latest_chip_metrics(ts_code)
        macro = self._get_macro_score(ts_code)

        if not tech and not chip and not macro:
            return None

        t_score = self.score_technical(tech)
        c_score = self.score_chip(chip)
        m_score = self.score_macro(macro)

        # 若某模型缺失，动态调整权重：把缺失模型的权重按比例分给现有模型
        avail = {'technical': tech, 'chip': chip, 'macro': macro}
        present_keys = [k for k, v in avail.items() if v]
        if len(present_keys) < 3:
            w_sum = sum(weights[k] for k in present_keys)
            if w_sum > 0:
                w = {k: weights[k] / w_sum if k in present_keys else 0.0 for k in weights}
            else:
                return None
        else:
            w = weights

        total = t_score * w.get('technical', 0) + c_score * w.get('chip', 0) + m_score * w.get('macro', 0)
        return {
            'ts_code': ts_code,
            'technical_score': round(t_score, 2),
            'chip_score': round(c_score, 2),
            'macro_score': round(m_score, 2),
            'total_score': round(total, 2),
            'weights': w,
            'technical': tech,
            'chip': chip,
            'macro': macro,
        }

    def batch_fuse(self, ts_codes: List[str], weights: Dict[str, float] = None) -> List[Dict]:
        """批量融合评分"""
        results = []
        for ts_code in ts_codes:
            r = self.fuse(ts_code, weights)
            if r:
                results.append(r)
        results.sort(key=lambda x: x['total_score'], reverse=True)
        return results

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    fusion = ThreeModelFusion()
    # 以当前持仓为例
    fusion.cursor.execute("SELECT DISTINCT ts_code FROM holdings WHERE status='持有中'")
    codes = [r[0] for r in fusion.cursor.fetchall()]
    print(f'三模型融合评分 ({len(codes)} 只):')
    for r in fusion.batch_fuse(codes):
        print(f"  {r['ts_code']} | 技术{r['technical_score']:5.1f} | 筹码{r['chip_score']:5.1f} | 宏观{r['macro_score']:5.1f} | 总分{r['total_score']:6.1f}")
    fusion.close()
