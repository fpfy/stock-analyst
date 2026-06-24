"""
双体系融合 - 主程序 V3版
完全重写，借鉴选股策略完整框架_双体系融合文件
"""

import logging
import logging.config
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
import pandas as pd

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard"
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"}
}
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

import database
import realtime_fetcher
from strategy_v3 import (
    UnifiedPipeline, StrategyRouter, GrowthScorer, ValueScorer,
    MARKET_CYCLE_CONFIG, EXCLUDED_INDUSTRIES
)
from value_six_dim_v2 import ValueSixDimScorer


class AdvancedAnalyzer:
    """双体系融合分析器 V3"""

    def __init__(self):
        self.db = database.DatabaseManager()
        self.fetcher = realtime_fetcher.data_fetcher
        self.cursor = self.db._get_connection().cursor()
        self.pipeline = UnifiedPipeline(self.cursor)

    def analyze_macro(self):
        """宏观经济分析"""
        logger.info("=" * 60)
        logger.info("阶段0: 宏观周期判断")
        logger.info("=" * 60)

        try:
            # 获取CPI数据
            cpi_data = self.fetcher.fetch_macro_indicator("CPI")
            cpi_latest = None
            if not cpi_data.empty and 'value' in cpi_data.columns:
                last_val = cpi_data['value'].iloc[-1]
                cpi_latest = float(last_val) if last_val else None
                logger.info(f"CPI(最新): {cpi_latest}%")

            # 宏观评分（0-100）
            macro_score = 56  # 暂用默认值
            logger.info(f"宏观评分: {macro_score}/100")

            return macro_score

        except Exception as e:
            logger.error(f"宏观分析失败: {e}")
            return 50

    def analyze_technical(self):
        """大盘技术分析"""
        logger.info("=" * 60)
        logger.info("大盘技术分析")
        logger.info("=" * 60)

        try:
            self.cursor.execute("""
                SELECT date, close, change_pct, ma5, ma10, ma20, ma60, volume
                FROM index_data
                WHERE index_code = '000001'
                ORDER BY date DESC
                LIMIT 60
            """)
            rows = self.cursor.fetchall()

            if not rows:
                logger.warning("无指数数据")
                return 50

            latest = rows[0]
            close, chg_pct = latest[1], latest[2]
            ma20, ma60 = latest[5], latest[6]

            logger.info(f"上证指数: {close:.0f}点, 涨跌幅 {chg_pct:.2f}%")

            # 市场周期判断（框架第八章）
            # 基于MA20/MA60和涨跌幅
            is_bull = ma20 and ma60 and ma20 > ma60

            if is_bull:
                if chg_pct and chg_pct > 2:
                    market_cycle = 'BULL_EARLY'
                    logger.info("市场状态: 牛市初期 (放量上涨)")
                elif chg_pct and 0 < chg_pct <= 2:
                    market_cycle = 'BULL_MID'
                    logger.info("市场状态: 牛市中期 (温和上涨)")
                else:
                    market_cycle = 'OSCILLATION'
                    logger.info("市场状态: 震荡市 (MA多头但微跌)")
            else:
                if chg_pct and chg_pct < -2:
                    market_cycle = 'BEAR_EARLY'
                    logger.info("市场状态: 熊市初期 (放量下跌)")
                else:
                    market_cycle = 'OSCILLATION'
                    logger.info("市场状态: 震荡市 (MA空头)")
                    market_cycle = 'BEAR_MID'

            # 仓位配置
            cycle_config = MARKET_CYCLE_CONFIG.get(market_cycle, MARKET_CYCLE_CONFIG['OSCILLATION'])
            logger.info(f"确认状态: {cycle_config['name']} - {cycle_config['desc']}")
            logger.info(f"仓位分配: 成长{cycle_config['growth_pct']*100:.0f}% + "
                       f"价值{cycle_config['value_pct']*100:.0f}% + 现金{cycle_config['cash_pct']*100:.0f}%")
            logger.info(f"MA20({ma20:.0f}) vs MA60({ma60:.0f}): {'多头排列' if is_bull else '空头排列'}")

            tech_score = 65 if is_bull else 45
            return tech_score, market_cycle, cycle_config

        except Exception as e:
            logger.error(f"技术分析失败: {e}")
            return 50, 'OSCILLATION', MARKET_CYCLE_CONFIG['OSCILLATION']

    def select_growth_stocks(self, position_ratio):
        """成长股六维加权选股（混合模式：本地优先，云端兜底）"""
        logger.info("=" * 60)
        logger.info("成长通道: 六维加权评分（混合模式）")
        logger.info("=" * 60)

        try:
            # 1. 本地 SQL：优先读取本地财务/估值数据，避免全量云端拉取
            query = """
                SELECT s.ts_code, s.name, s.industry,
                       f.roe, f.revenue_yoy, f.net_profit_yoy,
                       f.gross_margin, v.close, v.pe, v.pb, v.dv_ttm, v.total_mv, f.debt_ratio
                FROM stock_basic s
                INNER JOIN (
                    SELECT ts_code, roe, revenue_yoy, net_profit_yoy, gross_margin, debt_ratio
                    FROM financial_data
                    WHERE end_date = (SELECT MAX(end_date) FROM financial_data f2 WHERE f2.ts_code = financial_data.ts_code)
                ) f ON s.ts_code = f.ts_code
                INNER JOIN (
                    SELECT ts_code, close, pe, pb, dv_ttm, total_mv
                    FROM valuation_data
                    WHERE trade_date = (SELECT MAX(trade_date) FROM valuation_data v2 WHERE v2.ts_code = valuation_data.ts_code)
                ) v ON s.ts_code = v.ts_code
                WHERE s.is_st = 0
                  AND (s.list_date IS NULL OR s.list_date < DATE('now', '-3 years'))
                  AND f.roe >= 10
                  AND f.revenue_yoy >= 10
            """
            self.cursor.execute(query)
            stocks = self.cursor.fetchall()
            logger.info(f"本地 SQL 基础筛选（ROE>=10%,营收>=10%）: {len(stocks)}只候选")

            # 2. 如果本地无结果，再云端 stock_basic + 小批量补全
            if not stocks:
                logger.info("本地无候选，云端 stock_basic 兜底...")
                basic_df = self.fetcher.fetch_stock_basic()
                if basic_df is None or basic_df.empty:
                    logger.warning("云端 stock_basic 为空，回退纯本地")
                    return self._select_growth_stocks_local(position_ratio)

                basic_df['is_st'] = basic_df['name'].apply(
                    lambda x: 1 if isinstance(x, str) and ('ST' in x or '退' in x) else 0
                )
                basic_df = basic_df[
                    (basic_df['is_st'] == 0) &
                    ((basic_df['list_date'].isna()))
                     (basic_df['list_date'] < (datetime.now() - pd.Timedelta(days=3*365)).strftime('%Y%m%d'))
                ].copy()
                candidate_codes = basic_df['ts_code'].tolist()
                logger.info(f"云端 stock_basic 候选: {len(candidate_codes)}只")

                # 只取前200只云端补全，避免429
                sample_codes = candidate_codes[:200]
                logger.info(f"云端补全样本: {len(sample_codes)}只")
                fina_df = self.fetcher.fetch_candidate_basic_and_financial(sample_codes)
                val_df = self.fetcher.fetch_candidate_valuation(sample_codes)
                if not fina_df.empty or not val_df.empty:
                    merged = fina_df if not fina_df.empty else pd.DataFrame()
                    if not val_df.empty:
                        merged = merged.merge(val_df, on='ts_code', how='outer') if not merged.empty else val_df
                    for _, row in merged.iterrows():
                        code = row['ts_code']
                        name = row.get('name', '')
                        industry = row.get('industry', '')
                        roe = row.get('roe')
                        rev_yoy = row.get('revenue_yoy')
                        prof_yoy = row.get('net_profit_yoy')
                        gm = row.get('gross_margin')
                        close = row.get('close')
                        pe = row.get('pe')
                        pb = row.get('pb')
                        dv_ttm = row.get('dv_ttm')
                        total_mv = row.get('total_mv')
                        debt_ratio = row.get('debt_ratio')
                        if roe is not None and rev_yoy is not None and roe >= 10 and rev_yoy >= 10:
                            stocks.append((code, name, industry, roe, rev_yoy, prof_yoy, gm, close, pe, pb, dv_ttm, total_mv, debt_ratio))
                    logger.info(f"云端补全后候选: {len(stocks)}只")

            eligible = []
            excluded_by_industry = 0

            for stock in stocks:
                ts_code, name, industry = stock[0], stock[1], stock[2]
                roe, rev_yoy, prof_yoy = stock[3], stock[4], stock[5]
                gm, close, pe, pb = stock[6], stock[7], stock[8], stock[9]
                dv_ttm, total_mv, debt_ratio = stock[10], stock[11], stock[12]

                # 行业排除
                excluded = False
                if industry:
                    for excl in EXCLUDED_INDUSTRIES:
                        if excl in industry:
                            excluded = True
                            break
                if excluded:
                    excluded_by_industry += 1
                    continue

                # 运行流水线
                result = self.pipeline.run_pipeline(
                    ts_code, name, industry,
                    roe, rev_yoy, prof_yoy, gm,
                    close, pe, pb, dv_ttm, debt_ratio, total_mv
                )

                if result.get('route') == 'excluded':
                    excluded_by_industry += 1
                    continue

                if result.get('final_eligible') and result.get('final_strategy') == '成长':
                    eligible.append(result)

            logger.info(f"行业排除: {excluded_by_industry}只")
            logger.info(f"成长通道合格: {len(eligible)}只")

            # 排序取前N
            eligible.sort(key=lambda x: x.get('growth_score', 0), reverse=True)

            max_single = 0.15
            num_stocks = min(len(eligible), max(1, int(position_ratio / max_single)))
            final = eligible[:num_stocks]

            logger.info(f"最终选中成长股: {len(final)}只")
            for s in final:
                grade = s.get('growth_grade', '')
                reasons = '、'.join(s.get('growth_reasons', []))[:60]
                logger.info(f"  {s['ts_code']} {s['name']} ({s.get('industry','')}) "
                            f"评分:{s.get('growth_score',0):.1f} [{grade}] {reasons}")

            return final

        except Exception as e:
            logger.error(f"成长股选股失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _select_growth_stocks_local(self, position_ratio):
        """本地回退：从 SQL 读取成长股"""
        query = """
            SELECT s.ts_code, s.name, s.industry,
                   f.roe, f.revenue_yoy, f.net_profit_yoy,
                   f.gross_margin, v.close, v.pe, v.pb, v.dv_ttm, v.total_mv, f.debt_ratio
            FROM stock_basic s
            INNER JOIN (
                SELECT ts_code, roe, revenue_yoy, net_profit_yoy, gross_margin, debt_ratio
                FROM financial_data
                WHERE end_date = (SELECT MAX(end_date) FROM financial_data f2 WHERE f2.ts_code = financial_data.ts_code)
            ) f ON s.ts_code = f.ts_code
            INNER JOIN (
                SELECT ts_code, close, pe, pb, dv_ttm, total_mv
                FROM valuation_data
                WHERE trade_date = (SELECT MAX(trade_date) FROM valuation_data v2 WHERE v2.ts_code = valuation_data.ts_code)
            ) v ON s.ts_code = v.ts_code
            WHERE s.is_st = 0
              AND (s.list_date IS NULL OR s.list_date < DATE('now', '-3 years'))
              AND f.roe >= 10
              AND f.revenue_yoy >= 10
        """
        self.cursor.execute(query)
        stocks = self.cursor.fetchall()

        eligible = []
        excluded_by_industry = 0

        for stock in stocks:
            ts_code, name, industry = stock[0], stock[1], stock[2]
            roe, rev_yoy, prof_yoy = stock[3], stock[4], stock[5]
            gm, close, pe, pb = stock[6], stock[7], stock[8], stock[9]
            dv_ttm, total_mv, debt_ratio = stock[10], stock[11], stock[12]

            result = self.pipeline.run_pipeline(
                ts_code, name, industry, roe, rev_yoy, prof_yoy,
                gm, close, pe, pb, dv_ttm, debt_ratio, total_mv
            )

            if result.get('route') == 'excluded':
                excluded_by_industry += 1
                continue

            if result.get('final_eligible') and result.get('final_strategy') == '成长':
                eligible.append(result)

        logger.info(f"[本地回退] 成长通道合格: {len(eligible)}只")
        eligible.sort(key=lambda x: x.get('growth_score', 0), reverse=True)
        max_single = 0.15
        num_stocks = min(len(eligible), max(1, int(position_ratio / max_single)))
        return eligible[:num_stocks]

    def select_value_stocks(self, position_ratio):
        """价值股选股（六维20项 - V2完整版，混合模式）"""
        logger.info("=" * 60)
        logger.info("价值通道: 六维20项完整评估（混合模式）")
        logger.info("=" * 60)

        try:
            # 初始化六维评估器
            value_six_dim = ValueSixDimScorer(self.cursor)

            # 1. 本地 SQL：优先读取本地财务/估值数据
            query = """
                SELECT s.ts_code, s.name, s.industry,
                       f.roe, f.debt_ratio, v.close, v.pe, v.pb, v.dv_ttm, v.total_mv,
                       f.revenue_yoy, f.net_profit_yoy, f.gross_margin, f.net_margin,
                       f.eps, f.bps
                FROM stock_basic s
                INNER JOIN (
                    SELECT ts_code, roe, debt_ratio, revenue_yoy, net_profit_yoy,
                           gross_margin, net_margin, eps, bps
                    FROM financial_data
                    WHERE end_date = (SELECT MAX(end_date) FROM financial_data f2 WHERE f2.ts_code = financial_data.ts_code)
                ) f ON s.ts_code = f.ts_code
                INNER JOIN (
                    SELECT ts_code, close, pe, pb, dv_ttm, total_mv
                    FROM valuation_data
                    WHERE trade_date = (SELECT MAX(trade_date) FROM valuation_data v2 WHERE v2.ts_code = valuation_data.ts_code)
                ) v ON s.ts_code = v.ts_code
                WHERE s.is_st = 0
                  AND (s.list_date IS NULL OR s.list_date < DATE('now', '-3 years'))
            """
            self.cursor.execute(query)
            stocks = self.cursor.fetchall()
            logger.info(f"本地 SQL 基础筛选: {len(stocks)}只候选")

            # 2. 如果本地无结果，再云端 stock_basic + 小批量补全
            if not stocks:
                logger.info("本地无候选，云端 stock_basic 兜底...")
                basic_df = self.fetcher.fetch_stock_basic()
                if basic_df is None or basic_df.empty:
                    logger.warning("云端 stock_basic 为空，回退纯本地")
                    return self._select_value_stocks_local(position_ratio)

                basic_df['is_st'] = basic_df['name'].apply(
                    lambda x: 1 if isinstance(x, str) and ('ST' in x or '退' in x) else 0
                )
                basic_df = basic_df[
                    (basic_df['is_st'] == 0) &
                     (basic_df['list_date'] < (datetime.now() - pd.Timedelta(days=3*365)).strftime('%Y%m%d'))
                    ((basic_df['list_date'].isna()))
                ].copy()
                candidate_codes = basic_df['ts_code'].tolist()

                # 只取前200只云端补全，避免429
                sample_codes = candidate_codes[:200]
                logger.info(f"云端补全样本: {len(sample_codes)}只")
                fina_df = self.fetcher.fetch_candidate_basic_and_financial(sample_codes)
                val_df = self.fetcher.fetch_candidate_valuation(sample_codes)
                if not fina_df.empty or not val_df.empty:
                    merged = fina_df if not fina_df.empty else pd.DataFrame()
                    if not val_df.empty:
                        merged = merged.merge(val_df, on='ts_code', how='outer') if not merged.empty else val_df
                    for _, row in merged.iterrows():
                        code = row['ts_code']
                        name = row.get('name', '')
                        industry = row.get('industry', '')
                        roe = row.get('roe')
                        debt_ratio = row.get('debt_ratio')
                        close = row.get('close')
                        pe = row.get('pe')
                        pb = row.get('pb')
                        dv_ttm = row.get('dv_ttm')
                        total_mv = row.get('total_mv')
                        rev_yoy = row.get('revenue_yoy')
                        prof_yoy = row.get('net_profit_yoy')
                        gm = row.get('gross_margin')
                        net_margin = row.get('net_margin')
                        eps = row.get('eps')
                        bps = row.get('bps')
                        stocks.append((code, name, industry, roe, debt_ratio, close, pe, pb, dv_ttm, total_mv,
                                      rev_yoy, prof_yoy, gm, net_margin, eps, bps))
                    logger.info(f"云端补全后候选: {len(stocks)}只")

            eligible = []
            excluded_by_industry = 0
            failed_debt = 0

            for stock in stocks:
                ts_code, name, industry = stock[0], stock[1], stock[2]
                roe, debt_ratio = stock[3], stock[4]
                close, pe, pb, dv_ttm, total_mv = stock[5], stock[6], stock[7], stock[8], stock[9]
                rev_yoy, prof_yoy, gm, net_margin = stock[10], stock[11], stock[12], stock[13]
                eps, bps = stock[14], stock[15]

                # 行业排除
                excluded = False
                if industry:
                    for excl in EXCLUDED_INDUSTRIES:
                        if excl in industry:
                            excluded = True
                            break
                if excluded:
                    excluded_by_industry += 1
                    continue

                # 六维20项完整评估（缺失时给默认值，避免崩溃）
                pe_val = float(pe) if pe is not None else 999.0
                pb_val = float(pb) if pb is not None else 99.0
                dv_ttm_val = float(dv_ttm) if dv_ttm is not None else 0.0
                total_mv_val = float(total_mv) if total_mv is not None else 0.0
                roe_val = float(roe) if roe is not None else 0.0
                debt_val = float(debt_ratio) if debt_ratio is not None else 100.0
                rev_yoy_val = float(rev_yoy) if rev_yoy is not None else 0.0
                prof_yoy_val = float(prof_yoy) if prof_yoy is not None else 0.0
                gm_val = float(gm) if gm is not None else 0.0
                net_margin_val = float(net_margin) if net_margin is not None else 0.0
                eps_val = float(eps) if eps is not None else 0.0
                bps_val = float(bps) if bps is not None else 0.0
                close_val = float(close) if close is not None else 0.0

                total_score, dim_scores, passed, reasons, grade = value_six_dim.full_evaluation(
                    ts_code, name, industry, roe_val, rev_yoy_val, prof_yoy_val,
                    gm_val, net_margin_val, debt_val, eps_val, bps_val,
                    pe_val, pb_val, dv_ttm_val, close_val, total_mv_val
                )

                if not passed:
                    failed_debt += 1
                    continue

                if total_score >= 55:
                    eligible.append({
                        'ts_code': ts_code,
                        'name': name,
                        'industry': industry,
                        'score': total_score,
                        'grade': grade,
                        'dim_scores': dim_scores,
                        'current_price': close or 0,
                        'reasons': reasons[:5],
                        'pe': pe,
                        'pb': pb,
                        'roe': roe,
                        'dividend_yield': dv_ttm,
                    })

            logger.info(f"行业排除: {excluded_by_industry}只, 负债否决: {failed_debt}只")
            logger.info(f"六维20项合格(B以上): {len(eligible)}只")

            eligible.sort(key=lambda x: x['score'], reverse=True)

            max_single = 0.15
            num_stocks = min(len(eligible), max(1, int(position_ratio / max_single)))
            final = eligible[:num_stocks]

            logger.info(f"最终选中价值股: {len(final)}只")
            for s in final:
                dims = s.get('dim_scores', {})
                dim_str = ' | '.join(f"{k}{v:.0f}" for k, v in list(dims.items())[:4])
                logger.info(f"  {s['ts_code']} {s['name']} ({s.get('industry','')}) "
                           f"评级{s['grade']} 总分:{s['score']:.1f}")
                logger.info(f"    六维: {dim_str}")
                if s.get('reasons'):
                    logger.info(f"    逻辑: {'; '.join(str(r) for r in s['reasons'][:4])}")

            return final

        except Exception as e:
            logger.error(f"价值股选股失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def generate_operation_advice(self, stock, strategy_type='成长', deep_analysis=None):
        """为单只股票生成详细的操作建议
        deep_analysis: 四层分析结果，用于决策合成
        """
        ts_code = stock.get('ts_code', '')
        name = stock.get('name', '')
        industry = stock.get('industry', '')
        score = stock.get('growth_score', stock.get('score', 0))
        grade = stock.get('growth_grade', stock.get('grade', 'B'))
        dims = stock.get('growth_dims', stock.get('dim_scores', {}))
        
        # 提取四维评分
        deep_score = None
        deep_conclusion = ''
        if deep_analysis and deep_analysis.get('status') == '完成':
            deep_score = deep_analysis.get('overall_score')
            overall = deep_score
            if overall >= 75:
                deep_conclusion = "四维分析优秀"
            elif overall >= 60:
                deep_conclusion = "四维分析良好"
            elif overall >= 45:
                deep_conclusion = "四维分析存在短板"
            else:
                deep_conclusion = "四维分析评分偏低"

        # 维度提取（兼容两种字段格式）
        if isinstance(dims, dict) and 'revenue_growth' in dims:
            # 成长通道格式
            rev = dims.get('revenue_growth', 0)
            profit = dims.get('profit_quality', 0)
            market = dims.get('market_space', 0)
            competitive = dims.get('competitive', 0)
            mgmt = dims.get('management', 0)
            valuation = dims.get('valuation', 0)
        elif isinstance(dims, dict):
            # 价值通道格式（六维20项子项映射到6维）
            rev = dims.get('营收能力', dims.get('营收增长', 0))
            profit = dims.get('盈利质量', 0)
            market = dims.get('行业空间', 0)
            competitive = dims.get('竞争壁垒', 0)
            mgmt = dims.get('管理效率', 0)
            valuation = dims.get('PE-PB分位', dims.get('估值合理性', 0))
        else:
            rev = profit = market = competitive = mgmt = valuation = 0

        # ===== 决策合成：成长评分 + 四维评分 =====
        # 如果四维评分存在且 < 55，强制降级（四维更全面）
        if deep_score is not None and deep_score < 55:
            final_score = deep_score  # 以四维为准
            action_type = "观望"
            advice = [
                f"**决策合成**: 成长通道评分 {score:.0f} + 四维分析 {deep_score:.0f} → 最终 {deep_score:.0f}",
                f"**结论**: {deep_conclusion}，当前不具备买入条件",
                ""
            ]
            advice.append("**观望理由**:")
            if deep_score < 45:
                advice.append("- 四维综合评分偏低，公司存在明显短板")
            else:
                advice.append("- 四维分析显示存在短板，需等待基本面进一步确认")
            advice.append("- 建议等待营收增速回升、盈利质量改善或估值回调至合理区间")
            advice.append("")
            advice.append("**买入条件（满足以下任一）**:")
            advice.append("  - 营收增速连续2季度回升")
            advice.append("  - 盈利质量改善，ROE>15%")
            advice.append("  - 估值回调至历史30%分位以下")
            advice.append("")
            advice.append("**卖出/止损纪律**:")
            advice.append("- 若已持仓，反弹至MA60附近且量能萎缩时减仓")
            advice.append("- 固定止损: 买入价下跌7%，无条件执行")
            advice.append("")
            advice.append("**跟踪要点**:")
            if rev < 60:
                advice.append(f"- ⚠️ 营收增长({rev:.0f})偏弱，关注季度财报是否持续改善")
            if profit < 60:
                advice.append(f"- ⚠️ 盈利质量({profit:.0f})一般，关注ROE和经营现金流变化")
            if market < 50:
                advice.append(f"- ⚠️ 行业空间({market:.0f})有限，关注行业政策变化")
            
            return {
                'action_type': action_type,
                'entry_price': '等待更好时机',
                'stop_loss_pct': -7 if strategy_type == '成长' else -15,
                'advice': '\n'.join(advice)
            }

        # 基于维度评分的操作建议
        advice = []
        action_type = "观望"
        entry_price = "当前价附近"
        stop_loss_pct = -7 if strategy_type == '成长' else -15

        # ===== 泽璟制药 (688266.SH) 特殊定制 =====
        if ts_code == '688266.SH':
            # 即使成长评分高，四维评分低时降级为观望
            if deep_score is not None and deep_score < 55:
                action_type = "观望"
                advice = [
                    f"**决策合成**: 成长通道 {score:.0f} + 四维分析 {deep_score:.0f} → 以四维为准",
                    f"**结论**: {deep_conclusion}，综合评估为观望",
                    ""
                ]
                advice.append("**观望理由**:")
                advice.append("- 四维分析显示商业模式不稳定，收入波动极大")
                advice.append("- 估值依赖临床进展，不确定性高")
                advice.append("- 建议等待扭亏为盈确认后再做决策")
                advice.append("")
                advice.append("**若参与（高风险偏好）**:")
                advice.append("- 仓位: 总仓位不超过5-10%")
                advice.append("- 入场: 89-90元区间小仓位")
                advice.append("- 目标: 140-150元（机构均价方向）")
                advice.append("- 止损: 固定-10%，移动止损（盈利>20%后上移至+15%）")
                advice.append("")
                advice.append("**关键跟踪**: ZG006临床数据、艾伯维合作进展")
                advice.append("")
                advice.append("**风险提示**:")
                advice.append("- 以上分析仅为基于公开信息的客观整理与逻辑推演，不构成任何投资建议")
                advice.append("- 泽璟制药目前仍处于亏损状态，核心价值高度依赖ZG006的临床进展")
                advice.append("- 创新药从II期临床到最终上市的成功率存在极大不确定性")
                advice.append("- 公司前五大客户集中度高达81.34%，创始人已披露减持计划")
            else:
                action_type = "轻仓试探"
                entry_price = "89-90元区间"
                stop_loss_pct = -10
                advice.append("**投资建议**: 轻仓试探或观望为主，总仓位不超过5-10%")
                advice.append("**核心逻辑**: 公司仍处亏损状态，估值高度依赖ZG006的临床进展，波动风险极大")
                advice.append("**买入条件**: 89-90元区间可小仓位参与，目标价参考机构均价140-150元方向")
                advice.append("**关键跟踪**: 需密切关注ZG006后续临床数据及艾伯维合作进展")
                advice.append("**稳健建议**: 稳健型投资者建议等待扭亏为盈确认后再做决策")
                advice.append("")
                advice.append("**风险提示**:")
                advice.append("- 以上分析仅为基于公开信息的客观整理与逻辑推演，不构成任何投资建议")
                advice.append("- 泽璟制药目前仍处于亏损状态，核心价值高度依赖ZG006的临床进展和全球商业化前景")
                advice.append("- 创新药从II期临床到最终上市的成功率存在极大不确定性")
                advice.append("- 公司前五大客户集中度高达81.34%，创始人已披露减持计划，机构持仓分歧明显")
            return {
                'action_type': action_type,
                'entry_price': entry_price,
                'stop_loss_pct': stop_loss_pct,
                'advice': '\n'.join(advice)
            }

        # 判断操作类型和条件（通用逻辑）
        if score >= 75 and rev >= 80 and profit >= 80:
            action_type = "强烈推荐"
            entry_price = "回调至MA20附近或突破前高时"
            advice.append(f"**买入条件**: 营收增长({rev:.0f})与盈利质量({profit:.0f})双高，建议在回调至MA20附近或放量突破前高时建仓")
            advice.append(f"**初始仓位**: 总仓位的50%，若继续下跌5%可加仓至75%")
        elif score >= 65 and market >= 60 and competitive >= 60:
            action_type = "推荐"
            entry_price = "突破关键阻力位时"
            advice.append(f"**买入条件**: 行业空间({market:.0f})与竞争优势({competitive:.0f})良好，建议在放量突破关键阻力位时追入")
            advice.append(f"**初始仓位**: 总仓位的30%，突破后确认趋势再加仓20%")
        elif score >= 55 and valuation >= 50:
            action_type = "谨慎推荐"
            entry_price = "估值合理区间分批"
            advice.append(f"**买入条件**: 估值({valuation:.0f})进入合理区间，建议在PE/PB分位低于30%时分批建仓")
            advice.append(f"**初始仓位**: 总仓位的20%，每下跌5%补仓一次，最多补3次")
        else:
            action_type = "观望"
            entry_price = "等待更好时机"
            advice.append(f"**买入条件**: 当前评分({score:.0f})未达推荐标准，建议等待以下信号之一:")
            advice.append("  - 营收增速连续2季度回升")
            advice.append("  - 盈利质量改善，ROE>15%")
            advice.append("  - 估值回调至历史30%分位以下")

        # 卖出条件
        advice.append(f"\n**卖出条件**:")
        if score >= 70:
            advice.append(f"- **止盈目标**: 涨幅达30%时减仓50%，涨幅达50%时全部清仓")
            advice.append(f"- **趋势破位**: 收盘价跌破MA20且3日内未收回，清仓离场")
            advice.append(f"- **业绩拐点**: 单季度营收增速低于10%或净利润下滑，立即减仓")
        else:
            advice.append(f"- **反弹卖出**: 反弹至MA60附近且量能萎缩时减仓")
            advice.append(f"- **止损离场**: 若买入后下跌{abs(stop_loss_pct)}%，无条件止损")

        # 止损条件
        advice.append(f"\n**止损纪律**:")
        advice.append(f"- **固定止损**: 买入价下跌{abs(stop_loss_pct)}%，无条件执行止损")
        advice.append(f"- **移动止损**: 盈利超过15%后，将止损上移至成本价+10%（锁定利润）")
        advice.append(f"- **时间止损**: 买入后5日内未达预期（未涨3%），重新评估是否持有")

        # 跟踪要点
        advice.append(f"\n**跟踪要点**:")
        if rev < 60:
            advice.append(f"- ⚠️ 营收增长({rev:.0f})偏弱，需关注季度财报是否持续改善")
        if profit < 60:
            advice.append(f"- ⚠️ 盈利质量({profit:.0f})一般，需关注ROE和经营现金流变化")
        if market < 50:
            advice.append(f"- ⚠️ 行业空间({market:.0f})有限，需关注行业政策变化")
        if competitive < 50:
            advice.append(f"- ⚠️ 竞争优势({competitive:.0f})不足，需关注市场份额变化")

        return {
            'action_type': action_type,
            'entry_price': entry_price,
            'stop_loss_pct': stop_loss_pct,
            'advice': '\n'.join(advice)
        }

    def generate_report(self, market_cycle, cycle_config, growth_stocks, value_stocks, deep_results=None):
        """生成V3版分析报告"""
        if deep_results is None:
            deep_results = {}
        logger.info("=" * 60)
        logger.info("生成分析报告")
        logger.info("=" * 60)

        report_date = datetime.now().strftime('%Y-%m-%d')
        report_path = Path(__file__).parent / "reports" / f"v3_report_{report_date}.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(str(report_path), 'w', encoding='utf-8') as f:
            f.write(f"# A股交易策略日报 - V3双体系融合版\n")
            f.write(f"> {report_date}\n\n")

            f.write("## 一、宏观周期判断\n\n")
            f.write(f"**市场状态**: {cycle_config['name']}\n")
            f.write(f"**特征描述**: {cycle_config['desc']}\n\n")

            f.write(f"**仓位配置**:\n")
            f.write(f"- 成长股仓位: {cycle_config['growth_pct']*100:.0f}%\n")
            f.write(f"- 价值股仓位: {cycle_config['value_pct']*100:.0f}%\n")
            f.write(f"- 现金仓位:   {cycle_config['cash_pct']*100:.0f}%\n\n")

            if cycle_config['growth_pct'] > 0:
                f.write("## 二、成长通道选股结果\n\n")
                f.write(f"| 股票 | 行业 | 综合评分 | 评级 | 营收增长 | 盈利质量 | 市场空间 | 竞争优势 | 管理层 | 估值 |\n")
                f.write(f"|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|\n")
                for s in growth_stocks:
                    dims = s.get('growth_dims', {})
                    f.write(f"| **{s['name']}** {s['ts_code']} | {s.get('industry','')} | "
                           f"**{s.get('growth_score',0):.0f}** | {s.get('growth_grade','')} | "
                           f"{dims.get('revenue_growth',0):.0f} | {dims.get('profit_quality',0):.0f} | "
                           f"{dims.get('market_space',0):.0f} | {dims.get('competitive',0):.0f} | "
                           f"{dims.get('management',0):.0f} | {dims.get('valuation',0):.0f} |\n")

            # 新增：成长股详细操作建议
            if growth_stocks:
                f.write("\n## 二附、成长股操作建议\n\n")
                f.write(f"> **震荡市策略**: 仓位控制30%，精选高成长个股，严格止损\n\n")
                for s in growth_stocks:
                    deep = deep_results.get(s['ts_code'], {})
                    advice = self.generate_operation_advice(s, '成长', deep_analysis=deep)
                    f.write(f"### {s['name']} ({s['ts_code']}) — {advice['action_type']}\n\n")
                    f.write(f"{advice['advice']}\n\n")

            if cycle_config['value_pct'] > 0:
                f.write("\n## 三、价值通道选股结果\n\n")
                f.write("| 股票 | 行业 | 评级 | 总分 | 基本面 | 估值面 | 财务健康 | 风险识别 | 负债安全 | PE | PB | 股息率 |\n")
                f.write("|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|\n")
                for s in value_stocks:
                    dims = s.get('dim_scores', {})
                    f.write(f"| **{s['name']}** {s['ts_code']} | {s.get('industry','')} | "
                           f"**{s.get('grade','')}** | **{s['score']:.0f}** | "
                           f"{dims.get('基本面',0):.0f} | {dims.get('估值面',0):.0f} | "
                           f"{dims.get('财务健康',0):.0f} | {dims.get('风险识别',0):.0f} | "
                           f"{dims.get('负债安全',0):.0f} | "
                           f"{s.get('pe','N/A')} | {s.get('pb','N/A')} | {s.get('dividend_yield','N/A')} |\n")

            # 新增：价值股详细操作建议
            if value_stocks:
                f.write("\n## 三附、价值股操作建议\n\n")
                f.write(f"> **震荡市策略**: 仓位控制40%，精选低估值高股息个股，安全边际优先\n\n")
                for s in value_stocks:
                    advice = self.generate_operation_advice(s, '价值')
                    f.write(f"### {s['name']} ({s['ts_code']}) — {advice['action_type']}\n\n")
                    f.write(f"{advice['advice']}\n\n")

            # 新增：深度公司分析（四层框架）
            if deep_results:
                f.write("\n## 四、深度公司分析\n\n")
                f.write("> **分析框架**: 行业研究 → 商业模式 → 同行业对比 → 估值-成长匹配\n\n")
                for code, analysis in deep_results.items():
                    if analysis.get('status') != '完成':
                        continue
                    name = growth_stocks[[s['ts_code'] for s in growth_stocks].index(code)]['name'] if code in [s['ts_code'] for s in growth_stocks] else \
                           value_stocks[[s['ts_code'] for s in value_stocks].index(code)]['name'] if code in [s['ts_code'] for s in value_stocks] else code
                    f.write(f"### {name} ({code})\n\n")
                    
                    ind = analysis.get('industry_analysis', {})
                    biz = analysis.get('business_model', {})
                    peer = analysis.get('peer_comparison', {})
                    val = analysis.get('valuation_match', {})
                    
                    f.write(f"**综合评分**: {analysis.get('overall_score', 'N/A')}/100\n\n")
                    
                    f.write(f"#### 1. 行业研究\n\n")
                    f.write(f"- **行业**: {ind.get('industry', 'N/A')} | **景气度**: {ind.get('industry_status', 'N/A')} | **样本数**: {ind.get('peer_count', 0)}家\n")
                    f.write(f"- **公司地位**: {ind.get('company_position', 'N/A')}（行业评分 {ind.get('industry_score', 'N/A')}）\n")
                    f.write(f"- **关键指标分位**: ROE {ind.get('roe_percentile', 'N/A')}% | 营收增速 {ind.get('revenue_percentile', 'N/A')}% | 盈利 {ind.get('profit_percentile', 'N/A')}% | 毛利率 {ind.get('margin_percentile', 'N/A')}%\n")
                    f.write(f"- **行业平均营收增速**: {ind.get('industry_avg_revenue_yoy', 'N/A')}%\n\n")
                    
                    f.write(f"#### 2. 商业模式分析\n\n")
                    f.write(f"- **盈利质量**: 经营现金流/净利润 = {biz.get('profit_cf_ratio', 'N/A')} | **趋势**: {biz.get('profit_trend', 'N/A')}\n")
                    f.write(f"- **收入稳定性**: 营收增速标准差 = {biz.get('revenue_stability_std', 'N/A')} | **经营现金流**: {'正向' if biz.get('cf_health', 0) > 0 else '负向'}\n")
                    f.write(f"- **财务结构**: 资产负债率 {biz.get('debt_ratio', 'N/A')} | 流动比率 {biz.get('current_ratio', 'N/A')}\n")
                    f.write(f"- **最新财务**: 营收增速 {biz.get('latest_revenue_yoy', 'N/A')}% | 净利润增速 {biz.get('latest_net_profit_yoy', 'N/A')}% | 毛利率 {biz.get('latest_gross_margin', 'N/A')}%\n")
                    f.write(f"- **商业模式评分**: {biz.get('biz_score', 'N/A')}/100\n\n")
                    
                    f.write(f"#### 3. 同行业对比\n\n")
                    f.write(f"- **估值分位**: PE {peer.get('pe_percentile', 'N/A')}% | PB {peer.get('pb_percentile', 'N/A')}%（越低越好）\n")
                    f.write(f"- **质量分位**: ROE {peer.get('roe_percentile', 'N/A')}% | 毛利率 {peer.get('margin_percentile', 'N/A')}%（越高越好）\n")
                    f.write(f"- **成长分位**: 营收增速 {peer.get('revenue_percentile', 'N/A')}% | 利润增速 {peer.get('profit_percentile', 'N/A')}%\n")
                    f.write(f"- **综合竞争力**: {peer.get('competitive_score', 'N/A')}/100\n")
                    f.write(f"- **PEG**: {peer.get('peg', 'N/A')} | 行业平均PE: {peer.get('industry_avg_pe', 'N/A')}\n")
                    if peer.get('valuation_premium_pct') is not None:
                        f.write(f"- **估值溢价**: {peer.get('valuation_premium_pct', 'N/A')}%（相对行业平均）\n\n")
                    
                    f.write(f"#### 4. 估值-成长匹配\n\n")
                    f.write(f"- **当前PE**: {val.get('pe', 'N/A')} | **PB**: {val.get('pb', 'N/A')}\n")
                    f.write(f"- **PEG**: {val.get('peg', 'N/A')} | **合理PE区间**: {val.get('reasonable_pe_range', 'N/A')}\n")
                    f.write(f"- **近4期平均利润增速**: {val.get('avg_profit_yoy_4q', 'N/A')}%\n")
                    f.write(f"- **估值判断**: {val.get('valuation_status', 'N/A')}\n")
                    f.write(f"- **估值评分**: {val.get('valuation_score', 'N/A')}/100\n\n")
                    
                    # 综合结论
                    overall = analysis.get('overall_score', 50)
                    if overall >= 75:
                        conclusion = "四维分析优秀，行业龙头地位稳固，商业模式健康，估值合理，建议重点关注"
                    elif overall >= 60:
                        conclusion = "整体质地良好，部分维度存在短板，建议结合技术面择机参与"
                    elif overall >= 45:
                        conclusion = "存在明显短板（行业/商业模式/估值任一维度偏弱），需谨慎对待"
                    else:
                        conclusion = "综合评分偏低，建议回避或等待基本面改善信号"
                    f.write(f"**综合结论**: {conclusion}\n\n")
                    f.write("---\n\n")

        logger.info(f"报告已生成: {report_path}")
        return report_path

    def run(self):
        """运行完整分析"""
        logger.info("🚀 双体系融合分析系统 V3")
        logger.info("=" * 60)

        try:
            # 1. 更新指数数据
            logger.info("获取最新数据...")
            self.fetcher.fetch_index_data("000001")

            # 2. 宏观分析
            macro_score = self.analyze_macro()

            # 3. 技术分析 + 市场周期判定
            tech_score, market_cycle, cycle_config = self.analyze_technical()

            # 4. 成长股选股
            growth_position = cycle_config['growth_pct']
            growth_stocks = self.select_growth_stocks(growth_position) if growth_position > 0 else []

            # 5. 价值股选股
            value_position = cycle_config['value_pct']
            value_stocks = self.select_value_stocks(value_position) if value_position > 0 else []

            # 5.5 深度公司分析（四层框架）
            try:
                from deep_company_analysis import DeepCompanyAnalyzer
                deep_analyzer = DeepCompanyAnalyzer(self.db)
                all_codes = [s['ts_code'] for s in growth_stocks] + [s['ts_code'] for s in value_stocks]
                deep_results = {}
                for code in all_codes:
                    try:
                        deep_results[code] = deep_analyzer.full_analysis(code)
                    except Exception as e:
                        logger.debug(f"深度分析跳过 {code}: {e}")
                logger.info(f"📊 深度公司分析完成: {len(deep_results)}/{len(all_codes)}只")
            except Exception as e:
                logger.warning(f"深度公司分析模块加载失败: {e}")
                deep_results = {}

            # 6. 同步到观察池 + 预警检查（Phase 3）
            try:
                from portfolio_manager import sync_portfolio, WatchListManager, HoldingsManager, AlertManager, StrategyGenerator
                sync_portfolio(self.db, growth_stocks, value_stocks)

                watch_mgr = WatchListManager(self.db)
                holdings_mgr = HoldingsManager(self.db)
                alert_mgr = AlertManager(self.db)
                strategy_generator = StrategyGenerator(self.db)

                # 批量观察池信号检查（统一延迟，减少锁竞争）
                watch_all = watch_mgr.get_watch_list(status='观察中')
                for w in watch_all:
                    try:
                        watch_mgr.update_watch_signals(w[0])
                        import time; time.sleep(0.3)
                    except Exception as e:
                        logger.debug(f"信号检查异常 {w[0]}: {e}")

                # 对现有持仓运行预警检查
                alert_mgr.run_all_checks()

                # 生成当日交易策略
                strategies = strategy_generator.generate_strategies(
                    market_cycle=getattr(self, '_last_market_cycle', None),
                    macro_score=getattr(self, '_last_macro_score', None),
                    tech_score=getattr(self, '_last_tech_score', None),
                )

                logger.info(f"👁️ 观察池: {len(watch_all)}只")
                logger.info(f"🧭 当日交易策略: {len(strategies)}条")
                logger.info(f"💼 预警检查完成")
            except Exception as e:
                logger.warning(f"Phase 3集成失败: {e}")

            # 7. 同步选股结果到 trading_strategy + watch_list（解决选股与回测/模拟脱节）
            try:
                from selection_bridge import persist_selection_results
                report_date_for_persist = datetime.now().strftime('%Y-%m-%d')
                persist_result = persist_selection_results(growth_stocks, value_stocks, report_date_for_persist)
                logger.info(f"[Bridge] 选股持久化: 成长{persist_result.get('growth_count',0)}只 "
                            f"+ 价值{persist_result.get('value_count',0)}只")
            except Exception as e:
                logger.warning(f"选股持久化失败: {e}")

            # 8. 生成报告
            report_path = self.generate_report(market_cycle, cycle_config, growth_stocks, value_stocks, deep_results)

            logger.info("=" * 60)
            logger.info("✅ 双体系分析完成！")
            logger.info("=" * 60)
            logger.info(f"📄 报告: {report_path}")
            logger.info(f"📊 市场: {cycle_config['name']}")
            logger.info(f"📈 成长股: {len(growth_stocks)}只")
            logger.info(f"💰 价值股: {len(value_stocks)}只")

            return {
                'market_cycle': market_cycle,
                'growth_stocks': growth_stocks,
                'value_stocks': value_stocks,
                'report_path': report_path
            }

        except Exception as e:
            logger.error(f"分析失败: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            try:
                if hasattr(self, 'db') and self.db is not None:
                    # 先执行 WAL checkpoint，确保 WAL 文件数据合并到主数据库，降低后续 papertrader 锁冲突
                    try:
                        if getattr(self.db, 'conn', None) is not None:
                            self.db.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                            self.db.conn.commit()
                    except Exception as e:
                        logger.debug(f"分析器 WAL checkpoint 异常: {e}")
                    self.db.close()
                    logger.info("分析器数据库连接已释放")
            except Exception as e:
                logger.debug(f"分析器连接关闭异常: {e}")


def main():
    analyzer = AdvancedAnalyzer()
    return analyzer.run()

if __name__ == "__main__":
    main()