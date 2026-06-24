"""
演示版本 - 不依赖外部数据源，使用模拟数据展示系统功能
"""

import logging
import logging.config
import sys
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np
import sqlite3

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

# 项目路径
BASE_DIR = Path(__file__).parent.absolute()
DB_DIR = BASE_DIR / "database"
REPORTS_DIR = BASE_DIR / "reports"

# 创建目录
DB_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

class DemoSystem:
    """演示系统类"""

    def __init__(self):
        """初始化演示系统"""
        self.db_path = DB_DIR / "stock_analysis_demo.db"
        self.conn = sqlite3.connect(str(self.db_path))
        self._init_demo_data()

    def _init_demo_data(self):
        """初始化演示数据"""
        logger.info("初始化演示数据...")

        # 插入宏观指标数据
        cursor = self.conn.cursor()

        # PMI数据
        cursor.executemany("""
            INSERT OR REPLACE INTO macro_indicators (indicator_name, date, value, year, month, source)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            ('PMI', '2026-05-01', 50.8, '2026', '5', 'Demo'),
            ('PMI', '2026-04-01', 50.4, '2026', '4', 'Demo'),
            ('PMI', '2026-03-01', 50.1, '2026', '3', 'Demo'),
        ])

        # CPI数据
        cursor.executemany("""
            INSERT OR REPLACE INTO macro_indicators (indicator_name, date, value, year, month, source)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            ('CPI', '2026-05-01', 0.3, '2026', '5', 'Demo'),
            ('CPI', '2026-04-01', 0.2, '2026', '4', 'Demo'),
            ('CPI', '2026-03-01', 0.1, '2026', '3', 'Demo'),
        ])

        # M2数据
        cursor.executemany("""
            INSERT OR REPLACE INTO macro_indicators (indicator_name, date, value, year, month, source)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            ('M2_GROWTH', '2026-05-01', 6.2, '2026', '5', 'Demo'),
            ('M2_GROWTH', '2026-04-01', 7.1, '2026', '4', 'Demo'),
            ('M2_GROWTH', '2026-03-01', 8.0, '2026', '3', 'Demo'),
        ])

        # 指数数据
        cursor.executemany("""
            INSERT OR REPLACE INTO index_data
            (index_code, index_name, date, open, high, low, close, volume, amount, change_pct, ma5, ma10, ma20, ma60)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            ('000001', '上证指数', '2026-06-11', 3260, 3285, 3255, 3278, 450000000000, 5200000000000, 0.55, 3265, 3258, 3245, 3200),
            ('000001', '上证指数', '2026-06-10', 3240, 3270, 3235, 3260, 430000000000, 4900000000000, 0.62, 3260, 3252, 3240, 3195),
            ('399001', '深证成指', '2026-06-11', 10800, 10920, 10780, 10895, 520000000000, 6200000000000, 0.88, 10820, 10785, 10720, 10550),
        ])

        # 股票基本信息
        cursor.executemany("""
            INSERT OR REPLACE INTO stock_basic (ts_code, symbol, name, industry, is_st, update_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            ('600519', '600519', '贵州茅台', '食品饮料', 0, '2026-06-12'),
            ('300750', '300750', '宁德时代', '电力设备', 0, '2026-06-12'),
            ('002594', '002594', '比亚迪', '汽车', 0, '2026-06-12'),
            ('600036', '600036', '招商银行', '银行', 0, '2026-06-12'),
            ('688981', '688981', '中芯国际', '电子', 0, '2026-06-12'),
            ('601318', '601318', '中国平安', '非银金融', 0, '2026-06-12'),
            ('000858', '000858', '五粮液', '食品饮料', 0, '2026-06-12'),
            ('600030', '600030', '中信证券', '非银金融', 0, '2026-06-12'),
            ('300059', '300059', '东方财富', '非银金融', 0, '2026-06-12'),
            ('601088', '601088', '中国神华', '煤炭', 0, '2026-06-12'),
        ])

        # 财务数据
        cursor.executemany("""
            INSERT OR REPLACE INTO financial_data
            (ts_code, ann_date, end_date, roe, roa, gross_margin, net_margin, revenue_yoy, net_profit_yoy, debt_ratio, eps, bps)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            # 成长股数据
            ('300750', '2026-04-30', '2025-12-31', 22.5, 12.3, 28.5, 15.2, 48.5, 89.2, 58.3, 8.95, 45.2),
            ('002594', '2026-04-30', '2025-12-31', 18.7, 8.9, 22.1, 8.9, 56.3, 45.8, 62.1, 4.52, 28.3),
            ('688981', '2026-04-30', '2025-12-31', 16.8, 7.2, 32.4, 12.8, 35.6, 28.9, 42.5, 1.25, 8.5),
            # 价值股数据
            ('600036', '2026-04-30', '2025-12-31', 14.2, 1.2, 65.8, 42.3, 5.6, 8.2, 92.1, 3.85, 32.5),
            ('601088', '2026-04-30', '2025-12-31', 11.5, 6.8, 42.5, 25.8, 3.2, 6.5, 38.2, 2.15, 18.9),
            ('600030', '2026-04-30', '2025-12-31', 8.9, 1.5, 55.2, 28.6, 4.8, 5.9, 85.6, 1.58, 15.2),
        ])

        # 估值数据
        cursor.executemany("""
            INSERT OR REPLACE INTO valuation_data
            (ts_code, trade_date, close, pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm, total_mv, circ_mv)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            # 成长股估值
            ('300750', '2026-06-11', 210.5, 23.5, 22.8, 4.65, 5.2, 5.1, 0.8, 0.9, 9250, 8950),
            ('002594', '2026-06-11', 285.3, 63.1, 58.5, 10.08, 3.2, 3.1, 0.3, 0.35, 8350, 7850),
            ('688981', '2026-06-11', 52.8, 42.2, 38.5, 6.21, 6.5, 6.2, 0.5, 0.6, 1050, 950),
            # 价值股估值
            ('600036', '2026-06-11', 36.8, 9.56, 9.2, 1.13, 4.5, 4.3, 4.2, 4.5, 9250, 8750),
            ('601088', '2026-06-11', 34.5, 16.0, 15.8, 1.82, 1.8, 1.75, 6.2, 6.5, 6850, 5950),
            ('600030', '2026-06-11', 22.3, 14.1, 13.8, 1.47, 3.8, 3.6, 2.8, 3.0, 3250, 3050),
        ])

        self.conn.commit()
        logger.info("演示数据初始化完成")

    def analyze_macro(self):
        """分析宏观经济"""
        logger.info("=" * 60)
        logger.info("第一步：宏观经济分析")
        logger.info("=" * 60)

        cursor = self.conn.cursor()

        # 获取最新PMI
        cursor.execute("SELECT value, date FROM macro_indicators WHERE indicator_name='PMI' ORDER BY date DESC LIMIT 2")
        pmi_results = cursor.fetchall()

        if len(pmi_results) >= 2:
            current_pmi = pmi_results[0][0]
            prev_pmi = pmi_results[1][0]
            pmi_trend = current_pmi - prev_pmi

            logger.info(f"PMI: {current_pmi:.1f} (↑{pmi_trend:.1f}) - 位于荣枯线之上，制造业保持扩张" if current_pmi >= 50 else f"PMI: {current_pmi:.1f} (↓{abs(pmi_trend):.1f}) - 低于荣枯线，制造业收缩")
        else:
            current_pmi = 50.8
            pmi_trend = 0.5
            logger.info(f"PMI: {current_pmi:.1f} (↑{pmi_trend:.1f}) - 位于荣枯线之上，制造业保持扩张")

        # 获取最新CPI
        cursor.execute("SELECT value, date FROM macro_indicators WHERE indicator_name='CPI' ORDER BY date DESC LIMIT 1")
        cpi_result = cursor.fetchone()

        if cpi_result:
            cpi_value = cpi_result[0]
            if 2 <= cpi_value <= 3:
                logger.info(f"CPI: {cpi_value:.1f}% - 温和通胀")
            elif cpi_value > 3:
                logger.info(f"CPI: {cpi_value:.1f}% - 通胀压力")
            else:
                logger.info(f"CPI: {cpi_value:.1f}% - 通缩压力")
        else:
            cpi_value = 0.3
            logger.info(f"CPI: {cpi_value:.1f}% - 通缩压力")

        # 获取最新M2
        cursor.execute("SELECT value, date FROM macro_indicators WHERE indicator_name='M2_GROWTH' ORDER BY date DESC LIMIT 1")
        m2_result = cursor.fetchone()

        if m2_result:
            m2_value = m2_result[0]
            logger.info(f"M2增速: {m2_value:.1f}% - 流动性{'宽松' if m2_value > 7 else '中性' if m2_value > 5 else '偏紧'}")
        else:
            m2_value = 6.2
            logger.info(f"M2增速: {m2_value:.1f}% - 流动性中性")

        # 计算宏观评分
        macro_score = 0
        if current_pmi >= 50:
            macro_score += 30 + (current_pmi - 50) * 2
        else:
            macro_score += 30 - (50 - current_pmi)

        if 2 <= cpi_value <= 3:
            macro_score += 20
        elif 0 < cpi_value < 2:
            macro_score += 15

        if m2_value >= 7:
            macro_score += 15
        elif m2_value >= 5:
            macro_score += 10

        macro_score = max(0, min(100, macro_score))

        logger.info(f"宏观评分: {macro_score:.1f}/100")
        logger.info(f"景气水平: {'繁荣' if macro_score >= 75 else '景气' if macro_score >= 60 else '平稳' if macro_score >= 45 else '偏冷' if macro_score >= 30 else '萧条'}")
        logger.info(f"整体趋势: {'持续向好' if macro_score >= 60 else '基本稳定' if macro_score >= 45 else '缓慢下行'}")

        return macro_score

    def analyze_market(self):
        """分析大盘技术面"""
        logger.info("=" * 60)
        logger.info("第二步：大盘技术分析")
        logger.info("=" * 60)

        cursor = self.conn.cursor()

        # 获取上证指数数据
        cursor.execute("SELECT * FROM index_data WHERE index_code='000001' ORDER BY date DESC LIMIT 2")
        index_results = cursor.fetchall()

        if index_results:
            latest = index_results[0]
            current = latest[7]  # close
            change_pct = latest[10]  # change_pct
            ma20 = latest[12]
            ma60 = latest[13]

            logger.info(f"上证指数: {current:.0f}点，涨跌幅 {change_pct:.2f}%")

            # 判断均线趋势
            if ma20 and ma60:
                if ma20 > ma60:
                    logger.info(f"MA20({ma20:.0f}) > MA60({ma60:.0f}) - 多头排列")
                    trend_score = 70
                else:
                    logger.info(f"MA20({ma20:.0f}) < MA60({ma60:.0f}) - 空头排列")
                    trend_score = 40
            else:
                trend_score = 50

            # 综合技术评分
            tech_score = trend_score
            if change_pct > 0:
                tech_score += 10
            else:
                tech_score -= 10

            tech_score = max(0, min(100, tech_score))

            logger.info(f"技术评分: {tech_score:.1f}/100")
            logger.info(f"关键支撑位: {current * 0.95:.0f}点")
            logger.info(f"关键压力位: {current * 1.05:.0f}点")

            return tech_score

        return 50

    def determine_market_status(self, macro_score, tech_score):
        """确定大盘状态"""
        composite_score = macro_score * 0.4 + tech_score * 0.6

        logger.info("=" * 60)
        logger.info("第三步：综合判断大盘状态")
        logger.info("=" * 60)

        logger.info(f"综合评分: {composite_score:.1f}/100 (宏观{macro_score:.1f} + 技术{tech_score:.1f})")

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
        """选成长股"""
        logger.info("=" * 60)
        logger.info("第四步：成长股选股策略")
        logger.info("=" * 60)

        cursor = self.conn.cursor()

        # 查询符合成长股标准的股票
        query = """
            SELECT s.ts_code, s.name, f.roe, f.revenue_yoy, f.net_profit_yoy, f.gross_margin, v.close, v.pe, v.pb
            FROM stock_basic s
            JOIN financial_data f ON s.ts_code = f.ts_code
            JOIN valuation_data v ON s.ts_code = v.ts_code
            WHERE s.is_st = 0
            AND f.roe >= 15
            AND f.revenue_yoy >= 20
            AND f.net_profit_yoy >= 20
            AND f.gross_margin >= 40
        """

        cursor.execute(query)
        stocks = cursor.fetchall()

        logger.info(f"符合条件的成长股数量: {len(stocks)}")

        selected_stocks = []
        for stock in stocks:
            ts_code, name, roe, revenue_yoy, profit_yoy, gross_margin, close, pe, pb = stock

            # 计算评分
            score = 50
            reasons = []

            if roe >= 20:
                score += 10
                reasons.append(f"ROE优异({roe:.1f}%)")
            elif roe >= 15:
                score += 5
                reasons.append(f"ROE良好({roe:.1f}%)")

            if revenue_yoy >= 50:
                score += 15
                reasons.append(f"营收高增({revenue_yoy:.1f}%)")
            elif revenue_yoy >= 30:
                score += 10
                reasons.append(f"营收增长良好({revenue_yoy:.1f}%)")

            if profit_yoy >= 50:
                score += 15
                reasons.append(f"利润高增({profit_yoy:.1f}%)")
            elif profit_yoy >= 30:
                score += 10
                reasons.append(f"利润增长良好({profit_yoy:.1f}%)")

            score = max(0, min(100, score))

            selected_stocks.append({
                'ts_code': ts_code,
                'name': name,
                'score': score,
                'current_price': close,
                'reason': '、'.join(reasons),
                'roe': roe,
                'revenue_yoy': revenue_yoy,
                'profit_yoy': profit_yoy
            })

        # 排序并选择
        selected_stocks.sort(key=lambda x: x['score'], reverse=True)

        # 根据仓位分配
        max_single = 0.15
        num_stocks = min(len(selected_stocks), int(position_ratio / max_single))
        final_stocks = selected_stocks[:num_stocks]

        if final_stocks:
            each_ratio = position_ratio / len(final_stocks)
            for stock in final_stocks:
                stock['position_ratio'] = each_ratio
                stock['target_price'] = round(stock['current_price'] * 1.15, 2)
                stock['stop_loss_price'] = round(stock['current_price'] * 0.92, 2)

        logger.info(f"最终选中成长股: {len(final_stocks)}只")
        for i, stock in enumerate(final_stocks, 1):
            logger.info(f"  {i}. {stock['ts_code']} {stock['name']} 评分:{stock['score']:.1f} "
                       f"现价:{stock['current_price']:.2f} 目标:{stock['target_price']:.2f} 止损:{stock['stop_loss_price']:.2f} "
                       f"仓位:{stock['position_ratio']*100:.1f}%")

        return final_stocks

    def select_value_stocks(self, position_ratio):
        """选价值股"""
        logger.info("=" * 60)
        logger.info("第五步：价值股选股策略")
        logger.info("=" * 60)

        cursor = self.conn.cursor()

        # 查询符合价值股标准的股票
        query = """
            SELECT s.ts_code, s.name, f.roe, f.debt_ratio, v.close, v.pe, v.pb, v.dv_ttm
            FROM stock_basic s
            JOIN financial_data f ON s.ts_code = f.ts_code
            JOIN valuation_data v ON s.ts_code = v.ts_code
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

        selected_stocks = []
        for stock in stocks:
            ts_code, name, roe, debt_ratio, close, pe, pb, dividend_yield = stock

            # 计算评分
            score = 50
            reasons = []

            if pe <= 8:
                score += 15
                reasons.append(f"PE极低({pe:.1f})")
            elif pe <= 12:
                score += 10
                reasons.append(f"PE低估({pe:.1f})")

            if dividend_yield >= 6:
                score += 15
                reasons.append(f"股息率极高({dividend_yield:.1f}%)")
            elif dividend_yield >= 4:
                score += 10
                reasons.append(f"股息率高({dividend_yield:.1f}%)")

            if roe >= 15:
                score += 15
                reasons.append(f"ROE优异({roe:.1f}%)")

            if debt_ratio <= 50:
                score += 10
                reasons.append(f"负债率低({debt_ratio:.1f}%)")

            score = max(0, min(100, score))

            selected_stocks.append({
                'ts_code': ts_code,
                'name': name,
                'score': score,
                'current_price': close,
                'reason': '、'.join(reasons),
                'pe': pe,
                'pb': pb,
                'dividend_yield': dividend_yield,
                'roe': roe
            })

        # 排序并选择
        selected_stocks.sort(key=lambda x: x['score'], reverse=True)

        # 根据仓位分配
        max_single = 0.15
        num_stocks = min(len(selected_stocks), int(position_ratio / max_single))
        final_stocks = selected_stocks[:num_stocks]

        if final_stocks:
            each_ratio = position_ratio / len(final_stocks)
            for stock in final_stocks:
                stock['position_ratio'] = each_ratio
                stock['target_price'] = round(stock['current_price'] * 1.10, 2)
                stock['stop_loss_price'] = round(stock['current_price'] * 0.92, 2)

        logger.info(f"最终选中价值股: {len(final_stocks)}只")
        for i, stock in enumerate(final_stocks, 1):
            logger.info(f"  {i}. {stock['ts_code']} {stock['name']} 评分:{stock['score']:.1f} "
                       f"现价:{stock['current_price']:.2f} 目标:{stock['target_price']:.2f} 止损:{stock['stop_loss_price']:.2f} "
                       f"仓位:{stock['position_ratio']*100:.1f}%")

        return final_stocks

    def generate_report(self, market_status, growth_stocks, value_stocks):
        """生成分析报告"""
        logger.info("=" * 60)
        logger.info("第六步：生成分析报告")
        logger.info("=" * 60)

        report_date = datetime.now().strftime('%Y-%m-%d')
        report_path = REPORTS_DIR / f"demo_report_{report_date}.md"

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"# A股交易策略日报 - {report_date}\n\n")

            f.write("## 一、大盘综述\n\n")
            f.write("### 【宏观经济】\n\n")

            cursor = self.conn.cursor()

            # PMI
            cursor.execute("SELECT value FROM macro_indicators WHERE indicator_name='PMI' ORDER BY date DESC LIMIT 1")
            pmi = cursor.fetchone()
            if pmi:
                pmi_value = pmi[0]
                f.write(f"- PMI: {pmi_value:.1f}，位于荣枯线之上，制造业保持扩张\n")

            # CPI
            cursor.execute("SELECT value FROM macro_indicators WHERE indicator_name='CPI' ORDER BY date DESC LIMIT 1")
            cpi = cursor.fetchone()
            if cpi:
                cpi_value = cpi[0]
                if 0 < cpi_value < 2:
                    f.write(f"- CPI: {cpi_value:.1f}%，存在通缩压力\n")

            # M2
            cursor.execute("SELECT value FROM macro_indicators WHERE indicator_name='M2_GROWTH' ORDER BY date DESC LIMIT 1")
            m2 = cursor.fetchone()
            if m2:
                m2_value = m2[0]
                f.write(f"- M2增速: {m2_value:.1f}%，流动性中性\n\n")

            f.write(f"宏观评分: {market_status['composite_score'] * 0.4:.1f}/100\n")
            f.write(f"景气水平: 平稳\n")
            f.write(f"整体趋势: 基本稳定\n\n")

            f.write("### 【技术面】\n\n")
            cursor.execute("SELECT close, change_pct FROM index_data WHERE index_code='000001' ORDER BY date DESC LIMIT 1")
            index = cursor.fetchone()
            if index:
                f.write(f"- 上证指数: {index[0]:.0f}点，涨跌幅 {index[1]:.2f}%\n")
                f.write(f"- 技术评分: {market_status['composite_score'] * 0.6:.1f}/100\n")
                f.write(f"- 关键支撑位: {index[0] * 0.95:.0f}点\n")
                f.write(f"- 关键压力位: {index[0] * 1.05:.0f}点\n\n")

            f.write(f"整体趋势: 震荡\n\n")

            f.write("### 【结论】\n\n")
            f.write(f"**大盘状态**: {market_status['status_name']}\n")
            f.write(f"**风险等级**: {market_status['risk_level']}\n")
            f.write(f"**综合评分**: {market_status['composite_score']:.1f}/100\n\n")

            f.write("## 二、持仓建议\n\n")

            # 成长股
            if growth_stocks:
                f.write(f"### 成长股策略 (目标仓位: {market_status['growth_ratio']*100:.0f}%)\n\n")
                for stock in growth_stocks:
                    action = "持有" if stock['current_price'] < stock['target_price'] else "观察"
                    f.write(f"- **[{action}]** {stock['ts_code']} **{stock['name']}**\n")
                    f.write(f"  - 评分: {stock['score']:.1f}\n")
                    f.write(f"  - 现价: {stock['current_price']:.2f}元\n")
                    f.write(f"  - 目标: {stock['target_price']:.2f}元\n")
                    f.write(f"  - 止损: {stock['stop_loss_price']:.2f}元\n")
                    f.write(f"  - 建议仓位: {stock['position_ratio']*100:.1f}%\n")
                    f.write(f"  - 选股逻辑: {stock['reason']}\n\n")

            # 价值股
            if value_stocks:
                f.write(f"### 价值股策略 (目标仓位: {market_status['value_ratio']*100:.0f}%)\n\n")
                for stock in value_stocks:
                    action = "持有" if stock['current_price'] < stock['target_price'] else "观察"
                    f.write(f"- **[{action}]** {stock['ts_code']} **{stock['name']}**\n")
                    f.write(f"  - 评分: {stock['score']:.1f}\n")
                    f.write(f"  - 现价: {stock['current_price']:.2f}元\n")
                    f.write(f"  - 目标: {stock['target_price']:.2f}元\n")
                    f.write(f"  - 止损: {stock['stop_loss_price']:.2f}元\n")
                    f.write(f"  - 建议仓位: {stock['position_ratio']*100:.1f}%\n")
                    f.write(f"  - 选股逻辑: {stock['reason']}\n\n")

            f.write("## 三、风险提示\n\n")
            f.write("1. **市场风险**\n")
            f.write(f"   - 当前市场风险为{market_status['risk_level']}，建议控制仓位\n")
            f.write("   - 外围市场波动可能影响A股走势\n\n")

            f.write("2. **个股风险**\n")
            f.write("   - 财务数据可能存在滞后性\n")
            f.write("   - 重点关注公司业绩变化\n\n")

            f.write("3. **交易风险**\n")
            f.write("   - 严格执行止盈止损纪律\n")
            f.write("   - 单只股票最大仓位不超过15%\n")
            f.write("   - 总止损线: -8%\n\n")

            f.write("## 四、操作纪律\n\n")
            f.write("1. 仓位管理\n")
            f.write("   - 严格按照大盘状态调整成长股和价值股的仓位配比\n\n")

            f.write("2. 买入时机\n")
            f.write("   - 股价回调至支撑位附近企稳\n")
            f.write("   - 技术指标出现买入信号\n")
            f.write("   - 确认大盘环境稳定\n\n")

            f.write("3. 卖出时机\n")
            f.write("   - 达到目标价考虑减仓\n")
            f.write("   - 跌破止损价坚决止损\n")
            f.write("   - 大盘转弱时降低仓位\n\n")

            f.write("---\n\n")
            f.write("**免责声明**: 本报告仅供研究参考，不构成投资建议。股市有风险，投资需谨慎。\n")
            f.write("（演示版本，数据为模拟数据）\n")

        logger.info(f"分析报告已生成: {report_path}")
        return report_path

    def run(self):
        """运行完整演示流程"""
        logger.info("🚀 A股分析系统演示版启动")
        logger.info("=" * 60)

        try:
            # 1. 宏观分析
            macro_score = self.analyze_macro()

            # 2. 市场分析
            tech_score = self.analyze_market()

            # 3. 判断大盘状态
            market_status = self.determine_market_status(macro_score, tech_score)

            # 4. 成长股选股
            growth_stocks = self.select_growth_stocks(market_status['growth_ratio'])

            # 5. 价值股选股
            value_stocks = self.select_value_stocks(market_status['value_ratio'])

            # 6. 生成报告
            report_path = self.generate_report(market_status, growth_stocks, value_stocks)

            logger.info("=" * 60)
            logger.info("✅ 演示完成！")
            logger.info("=" * 60)
            logger.info(f"📄 报告路径: {report_path}")
            logger.info("")
            logger.info("📊 演示结果汇总:")
            logger.info(f"  - 大盘状态: {market_status['status_name']}")
            logger.info(f"  - 成长股: {len(growth_stocks)}只")
            logger.info(f"  - 价值股: {len(value_stocks)}只")
            logger.info("")
            logger.info("💡 提示: 这是演示版本，使用模拟数据。")
            logger.info("   要使用真实数据，请解决AkShare安装问题后运行 main.py")

            return {
                'market_status': market_status,
                'growth_stocks': growth_stocks,
                'value_stocks': value_stocks,
                'report_path': report_path
            }

        except Exception as e:
            logger.error(f"演示失败: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            self.conn.close()

def main():
    """主函数"""
    demo = DemoSystem()
    return demo.run()

if __name__ == "__main__":
    main()