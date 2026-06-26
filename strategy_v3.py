"""
双体系融合策略引擎 - V3版
借鉴选股策略完整框架_双体系融合文件
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from math import log, exp

logger = logging.getLogger(__name__)

# ===== 一、系统核心配置（可外部覆盖） =====

# 市场周期划分 & 对应仓位配置（来自框架第八章）
MARKET_CYCLE_CONFIG = {
    'BULL_EARLY': {
        'name': '牛市初期',
        'growth_pct': 0.70,
        'value_pct': 0.20,
        'cash_pct': 0.10,
        'desc': '放量+普涨'
    },
    'BULL_MID': {
        'name': '牛市中期',
        'growth_pct': 0.50,
        'value_pct': 0.40,
        'cash_pct': 0.10,
        'desc': '板块轮动'
    },
    'BULL_LATE': {
        'name': '牛市末期',
        'growth_pct': 0.20,
        'value_pct': 0.60,
        'cash_pct': 0.20,
        'desc': '放量滞涨→防御'
    },
    'BEAR_EARLY': {
        'name': '熊市初期',
        'growth_pct': 0.00,
        'value_pct': 0.30,
        'cash_pct': 0.70,
        'desc': '放量下跌→清仓止损'
    },
    'BEAR_MID': {
        'name': '熊市中后期',
        'growth_pct': 0.00,
        'value_pct': 0.50,
        'cash_pct': 0.50,
        'desc': '缩量阴跌→逢低吸纳'
    },
    'BEAR_LATE': {
        'name': '熊市末期',
        'growth_pct': 0.30,
        'value_pct': 0.40,
        'cash_pct': 0.30,
        'desc': '地量恐慌→左侧布局'
    },
    'OSCILLATION': {
        'name': '震荡市',
        'growth_pct': 0.30,
        'value_pct': 0.40,
        'cash_pct': 0.30,
        'desc': '窄幅波动→波段操作(GARP+高股息)'
    },
    'LIQUIDITY_EASY': {
        'name': '流动性宽松',
        'growth_pct': 0.70,
        'value_pct': 0.20,
        'cash_pct': 0.10,
        'desc': '降息→加仓成长'
    },
    'LIQUIDITY_TIGHT': {
        'name': '流动性紧缩',
        'growth_pct': 0.20,
        'value_pct': 0.60,
        'cash_pct': 0.20,
        'desc': '加息→防御为主'
    }
}

# 排除的行业（周期/传统/金融）— 已清空，不设行业黑名单
EXCLUDED_INDUSTRIES = []

# 优先行业（成长赛道）— 已清空，不设行业白名单
PREFERRED_INDUSTRIES_HIGH = []
PREFERRED_INDUSTRIES_MEDIUM = []
PREFERRED_INDUSTRIES_LOW = []


# ===== 二、策略路由（框架第四章 阶段1） =====

class StrategyRouter:
    """策略路由判定器"""

    def __init__(self, cursor):
        self.cursor = cursor

    def route(self, ts_code):
        """
        判断股票适合走成长通道还是价值通道
        返回: ('growth', score) / ('value', score) / ('both', score) / ('none', 0)
        """
        # 获取营收CAGR
        cagr = self._calc_revenue_cagr(ts_code)
        # 获取PE历史分位
        pe_percentile = self._calc_pe_percentile(ts_code)
        # 获取行业
        industry = self._get_industry(ts_code)
        is_growth_industry = self._is_growth_industry(industry)

        # 三指标分流（放宽后）
        growth_eligible = cagr and cagr >= 10 and is_growth_industry
        value_eligible = pe_percentile is not None and pe_percentile < 40
        # 价值股基本面门槛：PE<20 或 PB<2 或 股息率>2%
        self.cursor.execute("""
            SELECT pe, pb, dv_ttm FROM valuation_data
            WHERE ts_code = ? AND trade_date = (
                SELECT MAX(trade_date) FROM valuation_data WHERE ts_code = ?
            )
        """, (ts_code, ts_code))
        vrow = self.cursor.fetchone()
        pe_val, pb_val, dv_val = (vrow if vrow else (None, None, None))
        value_fundamental = (
            (pe_val is not None and pe_val < 20) or
            (pb_val is not None and pb_val < 2) or
            (dv_val is not None and dv_val > 2)
        )
        if value_fundamental:
            value_eligible = True

        if growth_eligible and value_eligible:
            return ('both', 70)
        elif growth_eligible:
            return ('growth', 60)
        elif value_eligible:
            return ('value', 60)
        else:
            return ('none', 0)

    def _calc_revenue_cagr(self, ts_code, periods=3):
        """计算近N年营收CAGR"""
        self.cursor.execute("""
            SELECT end_date, revenue_yoy
            FROM financial_data
            WHERE ts_code = ? AND revenue_yoy IS NOT NULL
            ORDER BY end_date DESC
            LIMIT ?
        """, (ts_code, periods))

        rows = self.cursor.fetchall()
        if len(rows) < periods:
            return None

        # 从营收增速反推CAGR（近似值）
        # 如果3年都有营收增速数据，取几何平均
        growths = [1 + r[1] / 100 for r in rows if r[1] is not None]
        if len(growths) < periods:
            return None

        cagr = (growths[0] * growths[1] * growths[2]) ** (1 / 3) - 1
        return cagr * 100

    def _calc_pe_percentile(self, ts_code):
        """计算近5年PE历史百分位（当前只有60天数据，先用60天近似）"""
        self.cursor.execute("""
            SELECT pe
            FROM valuation_data
            WHERE ts_code = ? AND pe IS NOT NULL AND pe > 0
            ORDER BY trade_date ASC
        """, (ts_code,))

        pe_values = [r[0] for r in self.cursor.fetchall()]
        if len(pe_values) < 20:
            return None

        current_pe = pe_values[-1]
        count_below = sum(1 for p in pe_values if p <= current_pe)
        percentile = (count_below / len(pe_values)) * 100
        return percentile

    def _get_industry(self, ts_code):
        self.cursor.execute("SELECT industry FROM stock_basic WHERE ts_code = ?", (ts_code,))
        row = self.cursor.fetchone()
        return row[0] if row else None

    def _is_growth_industry(self, industry):
        # 不设行业白名单，统一交由六维评分和财务指标判定
        return True


# ===== 三、成长股六维加权评分（框架第三章） =====

class GrowthScorer:
    """成长股六维加权评分"""

    WEIGHTS = {
        'revenue_growth': 0.20,   # ①营收增长 20%
        'profit_quality': 0.25,   # ②盈利质量 25%
        'market_space': 0.15,     # ③市场空间 15%
        'competitive': 0.20,      # ④竞争优势 20%
        'management': 0.10,       # ⑤管理层 10%
        'valuation': 0.10,        # ⑥估值合理 10%
    }

    def __init__(self, cursor):
        self.cursor = cursor

    def score(self, ts_code, name, industry, roe, revenue_yoy, net_profit_yoy,
              gross_margin, pe, close=None, total_mv=None):
        """计算六维加权总分（满分100）"""
        scores = {}
        reasons = []

        # ① 营收增长（25%）
        revenue_score = self._score_revenue_growth(ts_code, revenue_yoy)
        scores['revenue_growth'] = revenue_score
        if revenue_score >= 20:
            reasons.append(f"营收增长优秀")
        elif revenue_score >= 12:
            reasons.append(f"营收增长良好")
        else:
            reasons.append(f"营收增长一般")

        # ② 盈利质量（20%）
        profit_score = self._score_profit_quality(ts_code, roe, net_profit_yoy, revenue_yoy)
        scores['profit_quality'] = profit_score
        if profit_score >= 16:
            reasons.append("盈利质量优秀")
        elif profit_score >= 10:
            reasons.append("盈利质量良好")
        else:
            reasons.append("盈利质量一般")

        # ③ 市场空间（20%）- 用行业替代判断
        market_score = self._score_market_space(industry)
        scores['market_space'] = market_score
        if market_score >= 16:
            reasons.append("行业空间大")
        elif market_score >= 10:
            reasons.append("行业空间中等")
        else:
            reasons.append("行业空间有限")

        # ④ 竞争优势（15%）- 用毛利率+护城河替代
        competitive_score = self._score_competitive(gross_margin, roe)
        scores['competitive'] = competitive_score
        if competitive_score >= 12:
            reasons.append("竞争优势强")
        elif competitive_score >= 8:
            reasons.append("有一定优势")
        else:
            reasons.append("竞争优势一般")

        # ⑤ 管理层（15%）- 暂用ROE作为代理指标
        management_score = self._score_management(roe)
        scores['management'] = management_score
        if management_score >= 12:
            reasons.append("管理效率高")
        elif management_score >= 8:
            reasons.append("管理效率良好")

        # ⑥ 估值合理（5%）
        valuation_score = self._score_valuation(ts_code, pe, revenue_yoy, net_profit_yoy)
        scores['valuation'] = valuation_score
        if valuation_score < 3:
            reasons.append("估值偏高")

        # 加权总分
        total = sum(scores[dim] * self.WEIGHTS[dim] for dim in scores)

        return round(total, 1), scores, reasons

    def _score_revenue_growth(self, ts_code, current_yoy):
        """营收增长评分（满分100，权重25%）"""
        # 3年营收CAGR为主，当前增速为辅
        self.cursor.execute("""
            SELECT revenue_yoy FROM financial_data
            WHERE ts_code = ? AND revenue_yoy IS NOT NULL
            ORDER BY end_date DESC LIMIT 3
        """, (ts_code,))
        rows = [r[0] for r in self.cursor.fetchall()]
        if len(rows) >= 3:
            avg_growth = sum(rows) / len(rows)
        else:
            avg_growth = current_yoy or 0

        if avg_growth >= 30:
            return 95
        elif avg_growth >= 25:
            return 85
        elif avg_growth >= 20:
            return 75
        elif avg_growth >= 15:
            return 60
        elif avg_growth >= 10:
            return 40
        elif avg_growth >= 5:
            return 20
        return 0

    def _score_profit_quality(self, ts_code, roe, net_profit_yoy, revenue_yoy):
        """盈利质量评分（满分100，权重20%）"""
        score = 50  # 基础分

        # ROE
        if roe and roe >= 30:
            score += 30
        elif roe and roe >= 20:
            score += 20
        elif roe and roe >= 15:
            score += 10

        # 净利润增速>营收增速
        if net_profit_yoy and revenue_yoy:
            if net_profit_yoy > revenue_yoy:
                score += 20
            elif net_profit_yoy > revenue_yoy * 0.5:
                score += 10

        return min(score, 100)

    def _score_market_space(self, industry):
        """市场空间评分（满分100，权重20%）— 不设行业白名单，统一给中性基础分"""
        if not industry:
            return 30
        return 30  # 所有行业统一基础分，不再按行业名单加分

    def _score_competitive(self, gross_margin, roe):
        """竞争优势评分（满分100，权重15%）"""
        score = 40

        if gross_margin:
            if gross_margin >= 80:
                score += 35
            elif gross_margin >= 60:
                score += 25
            elif gross_margin >= 40:
                score += 15
            elif gross_margin >= 30:
                score += 5

        if roe and roe >= 25:
            score += 15
        elif roe and roe >= 15:
            score += 10

        return min(score, 100)

    def _score_management(self, roe):
        """管理层评分（满分100，权重15%）
        暂用ROE代理，后续可扩展为股权激励+增持检查"""
        if roe and roe >= 30:
            return 85
        elif roe and roe >= 20:
            return 70
        elif roe and roe >= 15:
            return 55
        elif roe and roe >= 10:
            return 40
        return 25

    def _score_valuation(self, ts_code, pe, revenue_yoy, net_profit_yoy):
        """估值合理评分（满分100，权重5%）
        用PEG近似：PE / (营收增速 + 净利润增速)/2 """
        if not pe or pe <= 0:
            return 50

        avg_growth = 0
        if revenue_yoy and net_profit_yoy:
            avg_growth = (revenue_yoy + net_profit_yoy) / 200  # 转为小数

        if avg_growth > 0:
            peg = pe / avg_growth
        else:
            peg = pe / 10  # 无增长数据时假设10%增速

        # PEG<1.5满分，1.5-2.0及格，>2.0低分
        if peg < 1.0:
            return 100
        elif peg < 1.5:
            return 80
        elif peg < 2.0:
            return 50
        elif peg < 3.0:
            return 20
        return 0

    def summary(self, total_score, dim_scores):
        """生成评级摘要"""
        if total_score >= 85:
            return "强烈推荐", "★★★★★"
        elif total_score >= 70:
            return "推荐纳入", "★★★★☆"
        elif total_score >= 55:
            return "观察", "★★★☆☆"
        elif total_score >= 40:
            return "谨慎", "★★☆☆☆"
        return "放弃", "★☆☆☆☆"


# ===== 四、价值股六维检查（框架第二章 - 初步实现） =====

class ValueScorer:
    """价值股检查（实现六维中的核心量化部分）"""

    def __init__(self, cursor):
        self.cursor = cursor

    def check_debt_safety(self, ts_code):
        """
        负债结构安全性检查（框架维度六 - 一票否决）
        从已有字段推算
        返回: (通过: bool, 问题列表: list)
        """
        self.cursor.execute("""
            SELECT debt_ratio FROM financial_data
            WHERE ts_code = ? AND debt_ratio IS NOT NULL
            ORDER BY end_date DESC LIMIT 1
        """, (ts_code,))
        row = self.cursor.fetchone()
        debt_ratio = row[0] if row else None

        issues = []

        # 1. 有息负债率（用资产负债率近似）
        if debt_ratio:
            if debt_ratio >= 70:
                issues.append(f"资产负债率≥70%({debt_ratio:.1f}%) - 💀一票否决!")
                return False, issues
            elif debt_ratio >= 60:
                issues.append(f"资产负债率≥60%({debt_ratio:.1f}%) - 预警")

        # 2. 流动比率/速动比率——从数据库已有字段推算
        # 用debt_ratio反向判断流动性风险
        if debt_ratio and debt_ratio > 70:
            issues.append(f"资产负债率较高({debt_ratio:.1f}%) - 流动性风险")
            return False, issues

        return True, issues

    def score_value(self, ts_code, name, industry, pe, pb, dividend_yield, roe, debt_ratio):
        """价值股综合评分"""
        score = 50
        reasons = []

        # PE评分
        if pe and pe <= 8:
            score += 15
            reasons.append(f"PE极低({pe:.1f})")
        elif pe and pe <= 12:
            score += 10
            reasons.append(f"PE低估({pe:.1f})")
        elif pe and pe <= 15:
            score += 5
            reasons.append(f"PE偏低({pe:.1f})")

        # PB评分
        if pb and pb <= 1.0:
            score += 10
            reasons.append(f"PB破净/接近({pb:.2f})")
        elif pb and pb <= 1.5:
            score += 5
            reasons.append(f"PB适中({pb:.2f})")

        # 股息率
        if dividend_yield and dividend_yield >= 6:
            score += 15
            reasons.append(f"股息率极高({dividend_yield:.1f}%)")
        elif dividend_yield and dividend_yield >= 4:
            score += 10
            reasons.append(f"股息率高({dividend_yield:.1f}%)")
        elif dividend_yield and dividend_yield >= 3:
            score += 5
            reasons.append(f"股息率良好({dividend_yield:.1f}%)")

        # ROE
        if roe and roe >= 20:
            score += 10
            reasons.append(f"ROE优异({roe:.1f}%)")
        elif roe and roe >= 15:
            score += 5
            reasons.append(f"ROE良好({roe:.1f}%)")

        # 负债率
        if debt_ratio and debt_ratio <= 40:
            score += 10
            reasons.append(f"负债率低({debt_ratio:.1f}%)")
        elif debt_ratio and debt_ratio <= 50:
            score += 5

        return min(score, 100), reasons


# ===== 五、选股流水线（框架第四章） =====

class UnifiedPipeline:
    """统一选股决策流水线"""

    def __init__(self, cursor):
        self.cursor = cursor
        self.router = StrategyRouter(cursor)
        self.growth_scorer = GrowthScorer(cursor)
        self.value_scorer = ValueScorer(cursor)

    def run_pipeline(self, ts_code, name, industry, roe, revenue_yoy, net_profit_yoy,
                     gross_margin, close, pe, pb, dv_ttm, debt_ratio, total_mv):
        """运行完整流水线"""
        result = {
            'ts_code': ts_code,
            'name': name,
            'industry': industry,
        }

        # 阶段0: 行业排除（已禁用，不设行业黑名单）
        # 所有行业统一交由六维评分和财务指标判定

        # 阶段1: 策略路由
        route, route_score = self.router.route(ts_code)
        result['route'] = route
        result['route_score'] = route_score

        if route == 'none':
            result['excluded'] = True
            result['reason'] = '策略路由判定: 不满足成长或价值通道'
            return result

        # 阶段2: 按通道评估
        if route in ('growth', 'both'):
            growth_total, dim_scores, growth_reasons = self.growth_scorer.score(
                ts_code, name, industry, roe, revenue_yoy, net_profit_yoy,
                gross_margin, pe, close, total_mv
            )
            result['growth_score'] = growth_total
            result['growth_dims'] = dim_scores
            result['growth_reasons'] = growth_reasons

            # 成长股纳入标准: ≥70分
            result['growth_grade'], stars = self.growth_scorer.summary(growth_total, dim_scores)
            result['growth_eligible'] = growth_total >= 70

        if route in ('value', 'both'):
            # 负债检查（一票否决）
            debt_ok, debt_issues = self.value_scorer.check_debt_safety(ts_code)
            result['debt_ok'] = debt_ok
            result['debt_issues'] = debt_issues

            if debt_ok:
                value_score, value_reasons = self.value_scorer.score_value(
                    ts_code, name, industry, pe, pb, dv_ttm, roe, debt_ratio
                )
                result['value_score'] = value_score
                result['value_reasons'] = value_reasons
                # 价值股纳入标准: 评分≥75
                result['value_eligible'] = value_score >= 75
            else:
                result['value_eligible'] = False
                result['value_reasons'] = debt_issues

        # 阶段3: 最终判定
        result['final_eligible'] = False
        if route == 'growth' and result.get('growth_eligible'):
            result['final_eligible'] = True
            result['final_strategy'] = '成长'
        elif route == 'value' and result.get('value_eligible'):
            result['final_eligible'] = True
            result['final_strategy'] = '价值'
        elif route == 'both':
            growth_eligible = result.get('growth_eligible', False)
            value_eligible = result.get('value_eligible', False)
            if growth_eligible and value_eligible:
                # 双通道取更优
                gs = result.get('growth_score', 0)
                vs = result.get('value_score', 0)
                result['final_eligible'] = True
                result['final_strategy'] = '成长' if gs >= vs else '价值'
            elif growth_eligible:
                result['final_eligible'] = True
                result['final_strategy'] = '成长'
            elif value_eligible:
                result['final_eligible'] = True
                result['final_strategy'] = '价值'

        return result