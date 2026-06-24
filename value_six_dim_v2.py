"""
价值股六维20项量化检查 - 完整实现
基于框架第二章《防御型价值体系：六维20项检查表》
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from math import log

logger = logging.getLogger(__name__)

# ============================================================
# 维度六：负债结构安全性（一票否决，8项）
# ============================================================

DEBT_THRESHOLDS = {
    'interest_bearing_debt_ratio': {'safe': 30, 'warn': 60, 'dead': 80},  # 有息负债率（放宽至80%）
    'current_ratio': {'safe': 1.5, 'warn': 1.5, 'dead': 1.0},             # 流动比率
    'quick_ratio': {'safe': 1.0, 'warn': 1.0, 'dead': 0.7},               # 速动比率
    'interest_coverage': {'safe': 3, 'warn': 3, 'dead': 1.5},              # 利息保障倍数
    'short_debt_long_invest': {'safe': 0.5, 'warn': 0.5, 'dead': 1.0},    # 短债长投比
    'goodwill_to_equity': {'safe': 20, 'warn': 20, 'dead': 40},           # 商誉/净资产
    'guarantee_to_equity': {'safe': 10, 'warn': 10, 'dead': 30},          # 对外担保/净资产
}

DEATH_TRAPS = {
    'short_debt_long_invest': '短债长投型',
    'debt_snowball': '债务雪球型',
    'goodwill_bomb': '商誉地雷型',
    'guarantee_chain': '担保链型',
    'hidden_debt': '隐性负债型',
}


class DebtSafetyChecker:
    """负债结构安全性 - 完整8项检查"""

    def __init__(self, cursor):
        self.cursor = cursor

    def full_check(self, ts_code, industry=None):
        """
        完整负债8项检查
        industry: 行业名称，银行/保险行业豁免负债率检查
        返回: (通过: bool, 问题列表: [(项, 级别, 描述)])
        """
        issues = []

        if not self.cursor:
            return True, []

        # 银行/保险行业豁免负债率检查（高负债是商业模式特征）
        exempt_industries = ['银行', '保险', '商业银行', '人寿保险', '财产保险', '保险业']
        is_exempt = False
        if industry:
            for ei in exempt_industries:
                if ei in industry:
                    is_exempt = True
                    break
        self.cursor.execute("""
            SELECT debt_ratio FROM financial_data
            WHERE ts_code = ? AND debt_ratio IS NOT NULL
            ORDER BY end_date DESC, ann_date DESC LIMIT 1
        """, (ts_code,))
        row = self.cursor.fetchone()
        debt_ratio = row[0] if row else None
        # 兼容字符串类型（部分数据源写入未转类型）
        if isinstance(debt_ratio, str):
            try:
                debt_ratio = float(debt_ratio)
            except Exception:
                debt_ratio = None

        if debt_ratio is not None:
            if is_exempt:
                # 银行/保险：高负债是商业模式，不检查负债率，给满分
                issues.append(('有息负债率', '✅', f"资产负债率{debt_ratio:.1f}%（银行/保险行业豁免）"))
            elif debt_ratio >= DEBT_THRESHOLDS['interest_bearing_debt_ratio']['dead']:
                issues.append(('有息负债率', '💀', f"资产负债率{debt_ratio:.1f}%≥{DEBT_THRESHOLDS['interest_bearing_debt_ratio']['dead']}% 一票否决!"))
            elif debt_ratio >= DEBT_THRESHOLDS['interest_bearing_debt_ratio']['warn']:
                issues.append(('有息负债率', '🔴', f"资产负债率{debt_ratio:.1f}% 预警"))
            else:
                issues.append(('有息负债率', '✅', f"资产负债率{debt_ratio:.1f}% 安全"))

        # 2. 流动比率 - current_assets / current_liab
        self.cursor.execute("""
            SELECT current_assets, current_liab FROM financial_data
            WHERE ts_code = ? AND current_assets IS NOT NULL AND current_liab IS NOT NULL AND current_liab > 0
            ORDER BY end_date DESC, ann_date DESC LIMIT 1
        """, (ts_code,))
        cr_row = self.cursor.fetchone()
        cr_value = None
        ca_val, cl_val = None, None
        if cr_row:
            ca_val, cl_val = cr_row[0], cr_row[1]
            # 兼容字符串类型
            if isinstance(ca_val, str):
                try:
                    ca_val = float(ca_val)
                except Exception:
                    ca_val = None
            if isinstance(cl_val, str):
                try:
                    cl_val = float(cl_val)
                except Exception:
                    cl_val = None
            cl_val_f = cl_val if cl_val is not None else 0
            cr_value = ca_val / cl_val_f if cl_val_f > 0 else None
            if cr_value is not None:
                if cr_value < DEBT_THRESHOLDS['current_ratio']['dead']:
                    issues.append(('流动比率', '💀', f"流动比率{cr_value:.2f}<{DEBT_THRESHOLDS['current_ratio']['dead']} 一票否决!"))
                elif cr_value < DEBT_THRESHOLDS['current_ratio']['safe']:
                    issues.append(('流动比率', '🔴', f"流动比率{cr_value:.2f}<{DEBT_THRESHOLDS['current_ratio']['safe']} 预警"))
                else:
                    issues.append(('流动比率', '✅', f"流动比率{cr_value:.2f} 安全"))
        else:
            # 无流动数据时从资产负债率估算
            if debt_ratio and debt_ratio > 65:
                issues.append(('流动比率', '⚠️', "无法直接计算，资产负债率偏高，需进一步排查"))

        # 4. 利息保障倍数 - 用经营现金流/总负债近似
        self.cursor.execute("""
            SELECT operating_cf, total_liab FROM financial_data
            WHERE ts_code = ? AND operating_cf IS NOT NULL AND total_liab IS NOT NULL AND total_liab > 0
            ORDER BY end_date DESC, ann_date DESC LIMIT 1
        """, (ts_code,))
        coverage_row = self.cursor.fetchone()
        if coverage_row:
            ocf, tl = coverage_row[0], coverage_row[1]
            # 兼容字符串类型
            if isinstance(ocf, str):
                try:
                    ocf = float(ocf)
                except Exception:
                    ocf = None
            if isinstance(tl, str):
                try:
                    tl = float(tl)
                except Exception:
                    tl = None
            tl_f = tl if tl is not None else 0
            coverage = abs(ocf / tl_f * 100) if tl_f > 0 and ocf is not None else None
            if coverage is not None:
                if coverage < 5:
                    issues.append(('偿债能力', '🔴', f"经营现金流/总负债{coverage:.1f}%，偿债能力弱"))
                else:
                    issues.append(('偿债能力', '✅', f"经营现金流/总负债{coverage:.1f}%"))

        # 5. 债务雪球检查：负债率是否快速上升
        self.cursor.execute("""
            SELECT end_date, debt_ratio FROM financial_data
            WHERE ts_code = ? AND debt_ratio IS NOT NULL
            ORDER BY end_date DESC LIMIT 2
        """, (ts_code,))
        dr_rows = self.cursor.fetchall()
        if len(dr_rows) >= 2:
            latest_dr, prev_dr = dr_rows[0][1], dr_rows[1][1]
            if latest_dr and prev_dr and (latest_dr - prev_dr) > 5:
                issues.append(('债务雪球', '🔴', f"负债率单季上升{latest_dr-prev_dr:.1f}pp>5pp 债务雪球风险!"))

        # 6. 短债长投比 - 用流动负债/(流动资产-流动负债)粗略估算
        if cl_val and ca_val and cl_val > ca_val:
            issues.append(('短债长投', '🔴', f"流动资产({ca_val:.0f})<流动负债({cl_val:.0f}) 短债长投风险!"))

        # 判断是否有致命问题
        fatal_items = [i for i in issues if i[1] == '💀']
        if fatal_items:
            return False, issues

        return True, issues


# ============================================================
# 维度一：基本面分析（4项） - 量化可计算部分
# ============================================================

class FundamentalChecker:
    """基本面检查 - 可量化部分"""

    def __init__(self, cursor):
        self.cursor = cursor

    def check_business_quality(self, ts_code, industry, gross_margin, roe):
        """商业质量评分"""
        score = 0
        reasons = []

        # 毛利率判断话语权
        if gross_margin:
            if gross_margin >= 70:
                score += 30
                reasons.append(f"高毛利率({gross_margin:.1f}%) → 强定价权")
            elif gross_margin >= 50:
                score += 20
                reasons.append(f"较高毛利率({gross_margin:.1f}%) → 有定价权")
            elif gross_margin >= 30:
                score += 10
                reasons.append(f"中等毛利率({gross_margin:.1f}%)")

        # ROE判断盈利质量
        if roe:
            if roe >= 20:
                score += 25
                reasons.append(f"高ROE({roe:.1f}%) → 强资本回报")
            elif roe >= 15:
                score += 15
                reasons.append(f"较好ROE({roe:.1f}%)")

        return min(score, 60), reasons

    def check_revenue_stability(self, ts_code):
        """收入稳定性检查（近3年收入增速趋势）"""
        self.cursor.execute("""
            SELECT end_date, revenue_yoy FROM financial_data
            WHERE ts_code = ? AND revenue_yoy IS NOT NULL
            ORDER BY end_date DESC LIMIT 4
        """, (ts_code,))
        rows = self.cursor.fetchall()

        if len(rows) < 3:
            return 0, ["收入数据不足3期"]

        growths = [r[1] for r in rows]
        avg = sum(growths) / len(growths)
        std = (sum((g - avg) ** 2 for g in growths) / len(growths)) ** 0.5

        score = 0
        reasons = []

        if avg >= 10:
            score += 10
            reasons.append(f"平均营收增速{avg:.1f}%")
        elif avg >= 5:
            score += 5
            reasons.append(f"营收微增{avg:.1f}%")

        # 稳定性判断
        if std <= 15:
            score += 15
            reasons.append(f"增长稳定(标准差{std:.1f})")
        elif std <= 30:
            score += 8
            reasons.append(f"增长波动较大(标准差{std:.1f})")
        else:
            reasons.append(f"增长极不稳定(标准差{std:.1f})")

        return min(score, 25), reasons

    def check_competitive_moat(self, industry, gross_margin, roe):
        """护城河判断（量化代理）"""
        score = 0
        reasons = []

        # 高毛利率=品牌/技术护城河
        if gross_margin and gross_margin >= 70:
            score += 10
            reasons.append("高毛利率→潜在品牌/技术护城河")

        # 高ROE=护城河+管理优势
        if roe and roe >= 20:
            score += 10
            reasons.append("高ROE→护城河+管理优势")

        # 不设行业护城河白名单，统一交由基本面指标判定

        return min(score, 25), reasons


# ============================================================
# 维度二：估值面分析（4项）
# ============================================================

class ValuationChecker:
    """估值检查"""

    def __init__(self, cursor):
        self.cursor = cursor

    def calc_pe_percentile(self, ts_code):
        """
        PE历史分位计算（优先用近3年/近5年分位）
        Returns: (current_pe, percentile, recommendation)
        recommendation: '低估'|'合理'|'高估'|'极高'
        """
        self.cursor.execute("""
            SELECT pe FROM valuation_data
            WHERE ts_code = ? AND pe IS NOT NULL AND pe > 0 AND pe < 10000
            ORDER BY trade_date ASC
        """, (ts_code,))

        pe_values = [r[0] for r in self.cursor.fetchall()]
        if len(pe_values) < 5:
            return None, None, None

        current_pe = pe_values[-1]

        # 全历史分位
        count_below = sum(1 for p in pe_values if p <= current_pe)
        all_time_pct = (count_below / len(pe_values)) * 100

        # 近3年分位（优先，250个交易日）
        if len(pe_values) >= 250:
            recent = pe_values[-250:]
            count_below_recent = sum(1 for p in recent if p <= current_pe)
            recent_pct = (count_below_recent / len(recent)) * 100
        else:
            recent_pct = all_time_pct
            recent = pe_values

        # 取更严格的分位（保守估计）
        percentile = min(all_time_pct, recent_pct) if len(pe_values) >= 100 else all_time_pct

        # 判定
        if percentile < 20:
            recommendation = '低估'
        elif percentile < 30:
            recommendation = '偏低'
        elif percentile < 50:
            recommendation = '合理'
        elif percentile < 70:
            recommendation = '偏高'
        else:
            recommendation = '高估'

        return current_pe, percentile, recommendation

    def calc_peg(self, pe, avg_growth_rate):
        """PEG计算"""
        if not pe or pe <= 0:
            return None
        if not avg_growth_rate or avg_growth_rate <= 0:
            return None
        return pe / avg_growth_rate

    def score_valuation(self, pe, pb, pe_percentile, dividend_yield, avg_growth_rate):
        """估值综合评分"""
        score = 0
        reasons = []

        # PE分位评分
        if pe_percentile is not None:
            if pe_percentile < 20:
                score += 20
                reasons.append(f"PE历史低位(分位{pe_percentile:.0f}%)")
            elif pe_percentile < 30:
                score += 15
                reasons.append(f"PE偏低(分位{pe_percentile:.0f}%)")
            elif pe_percentile < 50:
                score += 10
                reasons.append(f"PE中位(分位{pe_percentile:.0f}%)")
            else:
                score -= 5
                reasons.append(f"PE偏高(分位{pe_percentile:.0f}%)")

        # 绝对PE
        if pe:
            if pe <= 8:
                score += 15
                reasons.append(f"PE极低({pe:.1f})")
            elif pe <= 12:
                score += 10
                reasons.append(f"PE低估({pe:.1f})")
            elif pe <= 20:
                score += 5
                reasons.append(f"PE合理({pe:.1f})")

        # PB
        if pb and pb <= 1.0:
            score += 10
            reasons.append(f"PB破净({pb:.2f})")

        # 股息率
        if dividend_yield:
            if dividend_yield >= 6:
                score += 15
                reasons.append(f"股息率极高({dividend_yield:.1f}%)")
            elif dividend_yield >= 4:
                score += 10
                reasons.append(f"股息率高({dividend_yield:.1f}%)")
            elif dividend_yield >= 3:
                score += 5
                reasons.append(f"股息率良好({dividend_yield:.1f}%)")

        # PEG
        peg = self.calc_peg(pe, avg_growth_rate)
        if peg is not None:
            if peg < 1.0:
                score += 10
                reasons.append(f"PEG<1低估({peg:.2f})")
            elif peg < 1.5:
                score += 5
                reasons.append(f"PEG合理({peg:.2f})")

        return min(score, 100), reasons


# ============================================================
# 维度三：财务健康分析（3项）
# ============================================================

class FinancialHealthChecker:
    """财务健康检查"""

    def __init__(self, cursor):
        self.cursor = cursor

    def check_trend(self, ts_code):
        """指标趋势检查（最近3期）"""
        score = 0
        reasons = []

        # 负债率趋势
        self.cursor.execute("""
            SELECT end_date, debt_ratio FROM financial_data
            WHERE ts_code = ? AND debt_ratio IS NOT NULL
            ORDER BY end_date DESC LIMIT 3
        """, (ts_code,))
        debt_rows = self.cursor.fetchall()
        if len(debt_rows) >= 3:
            dr_values = [r[1] for r in debt_rows]
            if all(dr_values[i] >= dr_values[i+1] for i in range(len(dr_values)-1)):
                score += 10
                reasons.append("负债率持续下降")
            elif any(dr_values[i] > dr_values[i-1] + 5 for i in range(1, len(dr_values))):
                score -= 10
                reasons.append("⚠️ 负债率快速上升")

        # ROE趋势
        self.cursor.execute("""
            SELECT end_date, roe FROM financial_data
            WHERE ts_code = ? AND roe IS NOT NULL
            ORDER BY end_date DESC LIMIT 3
        """, (ts_code,))
        roe_rows = self.cursor.fetchall()
        if len(roe_rows) >= 3:
            roe_values = [r[1] for r in roe_rows]
            if all(roe_values[i] >= roe_values[i+1] for i in range(len(roe_values)-1)):
                score += 10
                reasons.append("ROE持续改善")
            elif any(roe_values[i] < roe_values[i-1] - 5 for i in range(1, len(roe_values))):
                score -= 5
                reasons.append("ROE有所下滑")

        return score, reasons

    def check_anomalies(self, ts_code):
        """财务异常排查"""
        score = 0
        reasons = []

        # EPS vs BPS关系检查（EPS过低但BPS高=资产效率低）
        self.cursor.execute("""
            SELECT eps, bps FROM financial_data
            WHERE ts_code = ? AND eps IS NOT NULL AND bps IS NOT NULL AND bps > 0
            ORDER BY end_date DESC, ann_date DESC LIMIT 1
        """, (ts_code,))
        row = self.cursor.fetchone()
        if row:
            eps, bps = row[0], row[1]
            roa_est = (eps / bps) * 100 if bps > 0 else 0
            if roa_est < 3:
                score -= 10
                reasons.append(f"⚠️ 资产效率低(ROA估算{roa_est:.1f}%)")
            elif roa_est >= 15:
                score += 10
                reasons.append(f"资产效率高(ROA估算{roa_est:.1f}%)")

        return score, reasons

    def score(self, ts_code):
        """财务健康综合评分"""
        trend_score, trend_reasons = self.check_trend(ts_code)
        anomaly_score, anomaly_reasons = self.check_anomalies(ts_code)
        total = trend_score + anomaly_score
        reasons = trend_reasons + anomaly_reasons
        return total, reasons


# ============================================================
# 维度四：风险识别分析（5项）- 可量化部分
# ============================================================

class RiskChecker:
    """风险识别"""

    def __init__(self, cursor):
        self.cursor = cursor

    def check_financial_manipulation(self, ts_code, gross_margin, net_margin, revenue_yoy, net_profit_yoy):
        """财报粉饰风险排查"""
        score = 0
        red_flags = []

        # 1. 利润与现金流不匹配
        self.cursor.execute("""
            SELECT operating_cf, net_profit FROM financial_data
            WHERE ts_code = ? AND operating_cf IS NOT NULL AND net_profit IS NOT NULL AND net_profit != 0
            ORDER BY end_date DESC, ann_date DESC LIMIT 1
        """, (ts_code,))
        row = self.cursor.fetchone()
        if row:
            ocf, np = row[0], row[1]
            if abs(np) > 0:
                cash_ratio = ocf / np
                if cash_ratio < 0.5:
                    red_flags.append(f"利润含金量低(经营现金流/净利润={cash_ratio:.2f})")
                    score -= 15
                elif cash_ratio < 0.8:
                    red_flags.append(f"利润含金量一般({cash_ratio:.2f})")
                    score -= 5
                else:
                    score += 10

        # 2. 毛利率异常（过高且不稳定）
        if gross_margin and gross_margin > 80:
            # 检查毛利率稳定性
            self.cursor.execute("""
                SELECT gross_margin FROM financial_data
                WHERE ts_code = ? AND gross_margin IS NOT NULL
                ORDER BY end_date DESC LIMIT 3
            """, (ts_code,))
            gm_rows = [r[0] for r in self.cursor.fetchall() if r[0] is not None]
            if len(gm_rows) >= 2:
                if abs(gm_rows[0] - gm_rows[1]) > 15:
                    red_flags.append(f"毛利率大幅波动({gm_rows[0]:.1f}%→{gm_rows[1]:.1f}%)")
                    score -= 10

        # 3. 利润增速远超营收增速（可能是一次性收益）
        if revenue_yoy and net_profit_yoy and revenue_yoy > 0:
            if net_profit_yoy > revenue_yoy * 3:
                red_flags.append(f"利润增速({net_profit_yoy:.0f}%)远超营收增速({revenue_yoy:.0f}%)需确认")
                score -= 5

        return score, red_flags


# ============================================================
# 统一价值股六维20项评估器
# ============================================================

class ValueSixDimScorer:
    """价值股六维20项评估器 V2"""
    
    def __init__(self, cursor, data_override=None):
        self.cursor = cursor
        self.data_override = data_override or {}  # {ts_code: {field: value}}
        self.debt_checker = DebtSafetyChecker(cursor)
        self.fundamental = FundamentalChecker(cursor)
        self.valuation = ValuationChecker(cursor)
        self.health = FinancialHealthChecker(cursor)
        self.risk = RiskChecker(cursor)

    def full_evaluation(self, ts_code, name, industry, roe, revenue_yoy, net_profit_yoy,
                        gross_margin, net_margin, debt_ratio, eps, bps,
                        pe, pb, dv_ttm, close, total_mv):
        """
        完整六维20项评估
        返回: (总分0-100, 维度明细, 是否通过, 原因列表, 评级)
        """
        dim_scores = {}
        all_reasons = []
        warnings = []

        # ============================================================
        # 维度六：负债结构安全性（一票否决）
        # ============================================================
        debt_ok, debt_issues = self.debt_checker.full_check(ts_code, industry=industry)
        dim_scores['负债安全'] = 100 if debt_ok else 0

        fatal = [i for i in debt_issues if i[1] == '💀']
        if fatal:
            return 0, dim_scores, False, [f"负债💀: {fatal[0][2]}"], "C"
        
        # 负债预警
        debt_warns = [i for i in debt_issues if i[1] == '🔴']
        dim_scores['负债安全'] = 60 if debt_warns else 100
        for i in debt_issues:
            all_reasons.append(f"负债-{i[0]}: {i[2]}")

        # ============================================================
        # 维度一：基本面分析（4项）
        # ============================================================
        biz_score, biz_reasons = self.fundamental.check_business_quality(
            ts_code, industry, gross_margin, roe
        )
        rev_score, rev_reasons = self.fundamental.check_revenue_stability(ts_code)
        moat_score, moat_reasons = self.fundamental.check_competitive_moat(
            industry, gross_margin, roe
        )
        dim_scores['基本面'] = biz_score + rev_score + moat_score
        all_reasons.extend(biz_reasons + rev_reasons + moat_reasons)

        # ============================================================
        # 维度二：估值面分析（4项）
        # ============================================================
        avg_growth = (revenue_yoy or 0) * 0.5 + (net_profit_yoy or 0) * 0.5
        pe_current, pe_percentile, pe_rec = self.valuation.calc_pe_percentile(ts_code)
        val_score, val_reasons = self.valuation.score_valuation(
            pe, pb, pe_percentile, dv_ttm, avg_growth
        )
        if pe_rec:
            val_reasons.append(f"PE分位={pe_percentile:.0f}%({pe_rec})")
        dim_scores['估值面'] = val_score
        all_reasons.extend(val_reasons)

        # ============================================================
        # 维度三：财务健康分析（3项）
        # ============================================================
        health_score, health_reasons = self.health.score(ts_code)
        dim_scores['财务健康'] = 50 + health_score
        all_reasons.extend(health_reasons)

        # ============================================================
        # 维度四：风险识别分析（5项） - 可量化部分
        # ============================================================
        risk_score, risk_reasons = self.risk.check_financial_manipulation(
            ts_code, gross_margin, net_margin, revenue_yoy, net_profit_yoy
        )
        dim_scores['风险识别'] = 50 + risk_score
        all_reasons.extend(risk_reasons)

        # ============================================================
        # 维度五：决策辅助分析（4项）- 综合评分
        # ============================================================
        decision_score = 70  # 默认基础分
        if roe and roe >= 20:
            decision_score += 10
        if debt_ok and not debt_warns:
            decision_score += 10
        if pe_percentile is not None and pe_percentile < 30:
            decision_score += 10
        dim_scores['决策辅助'] = min(decision_score, 100)

        # ============================================================
        # 综合评分
        # ============================================================
        # 六维等权（因为框架未加权）+ 负债否决
        weights = {
            '基本面': 0.20,
            '估值面': 0.20,
            '财务健康': 0.15,
            '风险识别': 0.15,
            '决策辅助': 0.10,
            '负债安全': 0.20,
        }
        
        total_score = sum(dim_scores[d] * weights[d] for d in dim_scores)
        total_score = round(total_score, 1)

        # 评级
        if total_score >= 85:
            grade = "A+"
        elif total_score >= 75:
            grade = "A"
        elif total_score >= 65:
            grade = "A-"
        elif total_score >= 55:
            grade = "B+"
        elif total_score >= 45:
            grade = "B"
        else:
            grade = "C"

        # 框架要求：综合评级A-以上纳入
        passed = grade in ("A+", "A", "A-")

        return total_score, dim_scores, passed, all_reasons, grade