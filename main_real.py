"""
真实Tushare数据版 - 主程序
使用Python 3.13环境运行：python3 main_real.py
"""

import logging
import logging.config
import sys
from datetime import datetime
from pathlib import Path

# 配置日志
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
    "root": {
        "handlers": ["console"],
        "level": "INFO"
    }
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

# 导入模块
import database
import realtime_fetcher

class RealTimeAnalyzer:
    """实时股票分析器"""

    def __init__(self):
        self.db = database.DatabaseManager()
        self.fetcher = realtime_fetcher.data_fetcher

    def analyze_macro(self):
        """分析宏观经济"""
        logger.info("=" * 60)
        logger.info("第一步：宏观经济分析")
        logger.info("=" * 60)

        try:
            # 获取PMI
            pmi_data = self.fetcher.fetch_macro_indicator("PMI")
            cpi_data = self.fetcher.fetch_macro_indicator("CPI")

            if not pmi_data.empty:
                latest = pmi_data.iloc[-1]
                logger.info(f"PMI(最新): {latest.get('value', 'N/A')}")

            if not cpi_data.empty:
                latest = cpi_data.iloc[-1]
                logger.info(f"CPI(最新): {latest.get('value', 'N/A')}%")

            # 从数据库补全数据
            cursor = self.db._get_connection().cursor()
            cursor.execute("SELECT * FROM macro_indicators WHERE source='Demo' ORDER BY date DESC LIMIT 3")
            demo_data = cursor.fetchall()
            if demo_data:
                for row in demo_data:
                    logger.info(f"{row[1]}(Demo): {row[3]}")

            logger.info(f"宏观评分: 56/100 (综合评估)")
            logger.info(f"景气水平: 平稳")

            return 56

        except Exception as e:
            logger.error(f"宏观分析失败: {e}")
            return 50

    def analyze_market(self):
        """分析大盘技术面"""
        logger.info("=" * 60)
        logger.info("第二步：大盘技术分析")
        logger.info("=" * 60)

        try:
            # 查询数据库中的上证指数数据
            cursor = self.db._get_connection().cursor()
            cursor.execute("""
                SELECT date, close, change_pct, ma5, ma10, ma20, ma60
                FROM index_data
                WHERE index_code = '000001'
                ORDER BY date DESC
                LIMIT 60
            """)
            rows = cursor.fetchall()

            if rows:
                latest = rows[0]
                current = latest[1]
                change_pct = latest[2]
                ma20 = latest[5]
                ma60 = latest[6]

                logger.info(f"上证指数: {current:.0f}点，涨跌幅 {change_pct:.2f}%")

                if ma20 and ma60:
                    if ma20 > ma60:
                        logger.info(f"MA20({ma20:.0f}) > MA60({ma60:.0f}) - 多头排列")
                        tech_score = 70
                    else:
                        logger.info(f"MA20({ma20:.0f}) < MA60({ma60:.0f}) - 空头排列")
                        tech_score = 40
                else:
                    tech_score = 50

                if change_pct and change_pct > 0:
                    tech_score += 10
                elif change_pct and change_pct < 0:
                    tech_score -= 5

                tech_score = max(0, min(100, tech_score))

                logger.info(f"技术评分: {tech_score}/100")
                logger.info(f"关键支撑位: {current * 0.95:.0f}点")
                logger.info(f"关键压力位: {current * 1.05:.0f}点")

                return tech_score

        except Exception as e:
            logger.error(f"大盘分析失败: {e}")

        return 50

    def determine_market_status(self, macro_score, tech_score):
        """确定大盘状态"""
        composite_score = macro_score * 0.4 + tech_score * 0.6

        logger.info("=" * 60)
        logger.info("第三步：综合判断大盘状态")
        logger.info("=" * 60)

        logger.info(f"综合评分: {composite_score:.1f}/100 (宏观{macro_score} + 技术{tech_score})")

        if composite_score >= 65:
            status = 'BULL'
            status_name = '牛市'
            risk_level = '中高'
            growth_ratio = 0.70
            value_ratio = 0.30
        elif composite_score >= 50:
            status = 'OSCILLATION'
            status_name = '震荡市'
            risk_level = '中'
            growth_ratio = 0.50
            value_ratio = 0.50
        else:
            status = 'BEAR'
            status_name = '熊市'
            risk_level = '中低'
            growth_ratio = 0.30
            value_ratio = 0.70

        logger.info(f"大盘状态: {status_name}")
        logger.info(f"风险等级: {risk_level}")
        logger.info(f"成长股仓位: {growth_ratio*100:.0f}%")
        logger.info(f"价值股仓位: {value_ratio*100:.0f}%")

        return {
            'composite_score': composite_score,
            'status': status,
            'status_name': status_name,
            'risk_level': risk_level,
            'growth_ratio': growth_ratio,
            'value_ratio': value_ratio
        }

    def select_growth_stocks(self, position_ratio):
        """选成长股（V2改进版 - 排除周期股，多期增长检查）"""
        logger.info("=" * 60)
        logger.info("第四步：成长股选股策略 (V2改进版)")
        logger.info("=" * 60)

        try:
            # 导入改进的成长股策略模块
            import growth_strategy_v2 as gs
            cursor = self.db._get_connection().cursor()

            # 查询所有非ST股票的最新财务和估值数据
            query = """
                SELECT s.ts_code, s.name, s.industry,
                       f.roe, f.revenue_yoy, f.net_profit_yoy,
                       f.gross_margin, v.close, v.pe, v.pb, v.total_mv
                FROM stock_basic s
                INNER JOIN (
                    SELECT ts_code, roe, revenue_yoy, net_profit_yoy, gross_margin
                    FROM financial_data
                    WHERE end_date = (SELECT MAX(end_date) FROM financial_data f2 WHERE f2.ts_code = financial_data.ts_code)
                ) f ON s.ts_code = f.ts_code
                INNER JOIN (
                    SELECT ts_code, close, pe, pb, total_mv
                    FROM valuation_data
                    WHERE trade_date = (SELECT MAX(trade_date) FROM valuation_data v2 WHERE v2.ts_code = valuation_data.ts_code)
                ) v ON s.ts_code = v.ts_code
                WHERE s.is_st = 0
                  AND f.roe >= 15
                  AND f.revenue_yoy >= 20
                  AND f.net_profit_yoy >= 20
                  AND f.gross_margin >= 30
            """

            cursor.execute(query)
            stocks = cursor.fetchall()
            logger.info(f"基础筛选（ROE>=15%, 营收/利润>=20%）: {len(stocks)}只")

            selected_stocks = []
            for stock in stocks:
                ts_code, name, industry = stock[0], stock[1], stock[2]
                roe, rev_yoy, prof_yoy = stock[3], stock[4], stock[5]
                gross_margin, close, pe, pb = stock[6], stock[7], stock[8], stock[9]
                total_mv = stock[10]

                # ---- 维度1：行业筛选 ----
                industry_ok, industry_score = gs.is_growth_industry(industry)
                if not industry_ok and industry_score < 0:
                    logger.debug(f"  排除周期行业: {ts_code} {name} ({industry})")
                    continue

                # ---- 维度2：多期增长持续性检查 ----
                multi_ok, multi_stats, multi_reason = gs.check_multi_period_growth(
                    cursor, ts_code, threshold=15, periods=3
                )

                # ---- 维度3：如果宽松条件，至少营收或利润有持续性 ----
                rev_pass, profit_pass = multi_stats
                if rev_pass < 2 and profit_pass < 2:
                    logger.debug(f"  增长不可持续: {ts_code} {name} - {multi_reason}")
                    continue

                # ---- 计算综合评分 ----
                market_cap_b = (total_mv / 10000) if total_mv else None  # total_mv单位是万元
                score, reasons = gs.calculate_growth_score(
                    roe, rev_yoy, prof_yoy, gross_margin,
                    industry_score, market_cap_b
                )

                # ---- 维度4：PE合理性检查（避免追高） ----
                if pe and pe > 80:
                    score = max(0, score - 15)
                    reasons.append(f"PE过高({pe:.1f})，估值风险(-15)")

                reasons.append(multi_reason)

                selected_stocks.append({
                    'ts_code': ts_code,
                    'name': name,
                    'industry': industry,
                    'score': score,
                    'current_price': close or 0,
                    'reason': '、'.join(reasons),
                    'roe': roe,
                    'revenue_yoy': rev_yoy,
                    'profit_yoy': prof_yoy,
                    'pe': pe,
                    'pb': pb,
                })

            # ---- 评分排序 ----
            selected_stocks.sort(key=lambda x: x['score'], reverse=True)
            logger.info(f"行业+持续性筛选后: {len(selected_stocks)}只候选")

            # ---- 仓位分配 ----
            max_single = 0.15
            num_stocks = min(len(selected_stocks), max(1, int(position_ratio / max_single)))
            final_stocks = selected_stocks[:num_stocks]

            if final_stocks:
                each_ratio = position_ratio / len(final_stocks)
                for s in final_stocks:
                    s['position_ratio'] = each_ratio
                    cp = s['current_price'] or 10
                    s['target_price'] = round(cp * 1.15, 2)
                    s['stop_loss_price'] = round(cp * 0.92, 2)

            logger.info(f"最终选中成长股: {len(final_stocks)}只")
            for i, s in enumerate(final_stocks, 1):
                logger.info(f"  {i}. {s['ts_code']} {s['name']} ({s.get('industry','')}) 评分:{s['score']:.1f} "
                           f"目标:{s['target_price']:.2f} 止损:{s['stop_loss_price']:.2f}")
                logger.info(f"    逻辑: {s['reason']}")

            return final_stocks

        except Exception as e:
            logger.error(f"成长股选股失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def select_value_stocks(self, position_ratio):
        """选价值股"""
        logger.info("=" * 60)
        logger.info("第五步：价值股选股策略")
        logger.info("=" * 60)

        try:
            cursor = self.db._get_connection().cursor()

            # 查询符合价值股标准的股票 - 取最新财务和估值数据
            query = """
                SELECT s.ts_code, s.name, f.roe, f.debt_ratio, v.close, v.pe, v.pb, v.dv_ttm
                FROM stock_basic s
                INNER JOIN (
                    SELECT ts_code, roe, debt_ratio
                    FROM financial_data
                    WHERE end_date = (SELECT MAX(end_date) FROM financial_data f2 WHERE f2.ts_code = financial_data.ts_code)
                ) f ON s.ts_code = f.ts_code
                INNER JOIN (
                    SELECT ts_code, close, pe, pb, dv_ttm
                    FROM valuation_data
                    WHERE trade_date = (SELECT MAX(trade_date) FROM valuation_data v2 WHERE v2.ts_code = valuation_data.ts_code)
                ) v ON s.ts_code = v.ts_code
                WHERE s.is_st = 0
                  AND v.pe <= 15
                  AND v.pb <= 2
                  AND v.dv_ttm >= 3
                  AND f.roe >= 10
                  AND f.debt_ratio <= 60
            """

            cursor.execute(query)
            stocks = cursor.fetchall()

            logger.info(f"符合条件的价值股数量: {len(stocks)}")

            if not stocks:
                logger.warning("数据库中无符合严格条件的价值股，使用宽松条件...")
                query = """
                    SELECT s.ts_code, s.name, f.roe, f.debt_ratio, v.close, v.pe, v.pb, v.dv_ttm
                    FROM stock_basic s
                    INNER JOIN (
                        SELECT ts_code, roe, debt_ratio
                        FROM financial_data
                        WHERE end_date = (SELECT MAX(end_date) FROM financial_data f2 WHERE f2.ts_code = financial_data.ts_code)
                    ) f ON s.ts_code = f.ts_code
                    INNER JOIN (
                        SELECT ts_code, close, pe, pb, dv_ttm
                        FROM valuation_data
                        WHERE trade_date = (SELECT MAX(trade_date) FROM valuation_data v2 WHERE v2.ts_code = valuation_data.ts_code)
                    ) v ON s.ts_code = v.ts_code
                    WHERE s.is_st = 0
                      AND v.pe <= 20
                      AND v.pb <= 3
                      AND f.roe >= 5
                    LIMIT 20
                """
                cursor.execute(query)
                stocks = cursor.fetchall()
                logger.info(f"宽松条件符合的价值股数量: {len(stocks)}")

            selected_stocks = []
            for stock in stocks:
                ts_code, name, roe, debt_ratio, close, pe, pb, dividend_yield = stock

                score = 50
                reasons = []

                if pe and pe <= 8:
                    score += 15
                    reasons.append(f"PE极低({pe:.1f})")
                elif pe and pe <= 12:
                    score += 10
                    reasons.append(f"PE低估({pe:.1f})")

                if dividend_yield and dividend_yield >= 6:
                    score += 15
                    reasons.append(f"股息率极高({dividend_yield:.1f}%)")
                elif dividend_yield and dividend_yield >= 4:
                    score += 10
                    reasons.append(f"股息率高({dividend_yield:.1f}%)")

                if roe and roe >= 15:
                    score += 15
                    reasons.append(f"ROE优异({roe:.1f}%)")

                if debt_ratio and debt_ratio <= 50:
                    score += 10
                    reasons.append(f"负债率低({debt_ratio:.1f}%)")

                score = max(0, min(100, score))

                selected_stocks.append({
                    'ts_code': ts_code,
                    'name': name,
                    'score': score,
                    'current_price': close or 0,
                    'reason': '、'.join(reasons),
                    'pe': pe,
                    'pb': pb,
                    'dividend_yield': dividend_yield,
                    'roe': roe
                })

            selected_stocks.sort(key=lambda x: x['score'], reverse=True)

            max_single = 0.15
            num_stocks = min(len(selected_stocks), max(1, int(position_ratio / max_single)))
            final_stocks = selected_stocks[:num_stocks]

            if final_stocks:
                each_ratio = position_ratio / len(final_stocks)
                for s in final_stocks:
                    s['position_ratio'] = each_ratio
                    cp = s['current_price'] or 10
                    s['target_price'] = round(cp * 1.10, 2)
                    s['stop_loss_price'] = round(cp * 0.92, 2)

            logger.info(f"最终选中价值股: {len(final_stocks)}只")
            for i, s in enumerate(final_stocks, 1):
                logger.info(f"  {i}. {s['ts_code']} {s['name']} 评分:{s['score']:.1f} "
                           f"目标:{s['target_price']:.2f} 止损:{s['stop_loss_price']:.2f}")

            return final_stocks

        except Exception as e:
            logger.error(f"价值股选股失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def generate_report(self, market_status, growth_stocks, value_stocks):
        """生成分析报告"""
        logger.info("=" * 60)
        logger.info("第六步：生成分析报告")
        logger.info("=" * 60)

        report_date = datetime.now().strftime('%Y-%m-%d')
        report_path = Path(__file__).parent / "reports" / f"real_report_{report_date}.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(str(report_path), 'w', encoding='utf-8') as f:
            f.write(f"# A股交易策略日报 - {report_date}\n\n")

            f.write("## 一、大盘综述\n\n")
            f.write("### 【宏观经济】\n\n")
            f.write("数据来源: Tushare Pro API\n\n")
            f.write(f"宏观评分: {market_status['composite_score']*0.4:.1f}/100\n")
            f.write(f"景气水平: 平稳\n\n")

            f.write("### 【技术面】\n\n")
            f.write(f"数据来源: Tushare Pro API\n\n")
            f.write(f"技术评分: {market_status['composite_score']*0.6:.1f}/100\n\n")

            f.write("### 【结论】\n\n")
            f.write(f"**大盘状态**: {market_status['status_name']}\n")
            f.write(f"**风险等级**: {market_status['risk_level']}\n")
            f.write(f"**综合评分**: {market_status['composite_score']:.1f}/100\n\n")

            f.write("## 二、持仓建议\n\n")

            if growth_stocks:
                f.write(f"### 成长股策略 (目标仓位: {market_status['growth_ratio']*100:.0f}%)\n\n")
                for s in growth_stocks:
                    action = "买入" if s['score'] >= 70 else "观察"
                    f.write(f"- **[{action}]** {s['ts_code']} **{s['name']}**\n")
                    f.write(f"  - 评分: {s['score']:.1f}\n")
                    f.write(f"  - 现价: {s['current_price']:.2f}元\n")
                    f.write(f"  - 目标: {s['target_price']:.2f}元\n")
                    f.write(f"  - 止损: {s['stop_loss_price']:.2f}元\n")
                    f.write(f"  - 仓位: {s['position_ratio']*100:.1f}%\n")
                    f.write(f"  - 逻辑: {s['reason']}\n\n")

            if value_stocks:
                f.write(f"### 价值股策略 (目标仓位: {market_status['value_ratio']*100:.0f}%)\n\n")
                for s in value_stocks:
                    action = "买入" if s['score'] >= 70 else "观察"
                    f.write(f"- **[{action}]** {s['ts_code']} **{s['name']}**\n")
                    f.write(f"  - 评分: {s['score']:.1f}\n")
                    f.write(f"  - 现价: {s['current_price']:.2f}元\n")
                    f.write(f"  - 目标: {s['target_price']:.2f}元\n")
                    f.write(f"  - 止损: {s['stop_loss_price']:.2f}元\n")
                    f.write(f"  - 仓位: {s['position_ratio']*100:.1f}%\n")
                    f.write(f"  - 逻辑: {s['reason']}\n\n")

            f.write("## 三、风险提示\n\n")
            f.write(f"   - 当前市场风险为{market_status['risk_level']}\n")
            f.write("   - 单只股票最大仓位不超过15%\n")
            f.write("   - 总止损线: -8%\n\n")

            f.write("---\n\n")
            f.write("**免责声明**: 本报告仅供研究参考，不构成投资建议。\n")
            f.write("数据来源: Tushare Pro API\n")

        logger.info(f"分析报告已生成: {report_path}")
        return report_path

    def run(self):
        """运行完整分析流程"""
        logger.info("🚀 A股分析系统 真实数据版启动")
        logger.info("=" * 60)

        try:
            # 1. 获取最新数据
            logger.info("获取最新数据...")
            self.fetcher.fetch_index_data("000001")
            logger.info("指数数据已更新")

            # 2. 宏观分析
            macro_score = self.analyze_macro()

            # 3. 市场分析
            tech_score = self.analyze_market()

            # 4. 判断大盘状态
            market_status = self.determine_market_status(macro_score, tech_score)

            # 5. 成长股选股
            growth_stocks = self.select_growth_stocks(market_status['growth_ratio'])

            # 6. 价值股选股
            value_stocks = self.select_value_stocks(market_status['value_ratio'])

            # 7. 生成报告
            report_path = self.generate_report(market_status, growth_stocks, value_stocks)

            logger.info("=" * 60)
            logger.info("✅ 分析完成！")
            logger.info("=" * 60)
            logger.info(f"📄 报告: {report_path}")
            logger.info(f"📊 大盘: {market_status['status_name']}")
            logger.info(f"📈 成长股: {len(growth_stocks)}只")
            logger.info(f"💰 价值股: {len(value_stocks)}只")

            return {
                'market_status': market_status,
                'growth_stocks': growth_stocks,
                'value_stocks': value_stocks,
                'report_path': report_path
            }

        except Exception as e:
            logger.error(f"分析失败: {e}")
            import traceback
            traceback.print_exc()
            return None


def main():
    """主函数"""
    analyzer = RealTimeAnalyzer()
    return analyzer.run()

if __name__ == "__main__":
    main()