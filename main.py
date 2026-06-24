"""
A股分析及交易策略系统 - 主程序
"""

import logging
import logging.config
import sys
from datetime import datetime
from pathlib import Path

# 配置日志
import config
logging.config.dictConfig(config.LOGGING_CONFIG)
logger = logging.getLogger(__name__)

# 导入各个模块
import database
import data_fetcher
import macro_market_analyzer
import stock_selector

def init_system():
    """初始化系统"""
    logger.info("=" * 60)
    logger.info("A股分析及交易策略系统启动")
    logger.info("=" * 60)

    # 检查并安装必要的依赖
    check_dependencies()

    # 确保数据库已初始化
    db = database.DatabaseManager()
    logger.info("数据库初始化完成")

    return db

def check_dependencies():
    """检查依赖包"""
    logger.info("检查系统依赖...")

    required_packages = {
        'akshare': 'AkShare',
        'pandas': 'Pandas',
        'numpy': 'NumPy'
    }

    missing = []
    for package, name in required_packages.items():
        try:
            __import__(package)
            logger.info(f"✓ {name} 已安装")
        except ImportError:
            logger.warning(f"✗ {name} 未安装")
            missing.append(package)

    if missing:
        logger.error(f"缺少必要依赖包: {', '.join(missing)}")
        logger.info("请运行: pip install akshare pandas numpy")
        sys.exit(1)

def fetch_initial_data(db):
    """获取初始数据"""
    logger.info("开始获取初始数据...")

    fetcher = data_fetcher.data_fetcher

    # 1. 获取宏观经济指标
    logger.info("获取宏观经济指标...")
    indicators = ['PMI', 'CPI', 'PPI', 'M2']
    for indicator in indicators:
        fetcher.fetch_macro_indicator(indicator)

    # 2. 获取股票基本信息
    logger.info("获取股票基本信息...")
    fetcher.fetch_stock_basic()

    # 3. 获取指数数据（最近60天）
    logger.info("获取指数数据...")
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - datetime.timedelta(days=90)).strftime('%Y%m%d')
    for index_code in ['000001', '399001', '000300']:
        fetcher.fetch_index_data(index_code, start_date, end_date)

    logger.info("初始数据获取完成")

def analyze_macro_and_market():
    """分析宏观与大盘"""
    logger.info("=" * 60)
    logger.info("第一步：宏观与大盘分析")
    logger.info("=" * 60)

    # 1. 宏观经济分析
    logger.info("1.1 宏观经济分析...")
    macro_result = macro_market_analyzer.macro_analyzer.analyze_macro_economy()

    # 2. 大盘技术分析
    logger.info("1.2 大盘技术分析...")
    market_result = macro_market_analyzer.market_analyzer.analyze_market()

    # 3. 综合判断大盘状态
    logger.info("1.3 综合判断大盘状态...")
    if macro_result and market_result:
        market_status = macro_market_analyzer.determine_market_status(
            macro_result.get('score', 50),
            market_result.get('overall_score', 50)
        )

        logger.info(f"大盘状态: {market_status['status_name']}")
        logger.info(f"  - 综合评分: {market_status['composite_score']:.2f}")
        logger.info(f"  - 宏观评分: {market_status['macro_score']:.2f}")
        logger.info(f"  - 技术评分: {market_status['technical_score']:.2f}")
        logger.info(f"  - 风险等级: {market_status['risk_level']}")
        logger.info(f"  - 成长股仓位: {market_status['growth_ratio']*100:.0f}%")
        logger.info(f"  - 价值股仓位: {market_status['value_ratio']*100:.0f}%")

        return market_status, macro_result, market_result
    else:
        logger.error("宏观或大盘分析失败")
        return None, None, None

def select_stocks(market_status):
    """执行选股策略"""
    logger.info("=" * 60)
    logger.info("第二步：选股策略执行")
    logger.info("=" * 60)

    if not market_status:
        logger.error("大盘状态为空，跳过选股")
        return None

    try:
        selection_result = stock_selector.run_stock_selection(market_status)

        logger.info("选股结果:")
        logger.info(f"  - 成长股: {len(selection_result.get('growth_stocks', []))}只")
        logger.info(f"  - 价值股: {len(selection_result.get('value_stocks', []))}只")

        # 打印成长股列表
        growth_stocks = selection_result.get('growth_stocks', [])
        if growth_stocks:
            logger.info("\n  成长股候选:")
            for i, stock in enumerate(growth_stocks[:5], 1):  # 只显示前5只
                logger.info(f"    {i}. {stock['ts_code']} {stock.get('name', '')} "
                           f"评分:{stock.get('score', 0):.1f} "
                           f"目标价:{stock.get('target_price', 0):.2f} "
                           f"止损价:{stock.get('stop_loss_price', 0):.2f}")

        # 打印价值股列表
        value_stocks = selection_result.get('value_stocks', [])
        if value_stocks:
            logger.info("\n  价值股候选:")
            for i, stock in enumerate(value_stocks[:5], 1):  # 只显示前5只
                logger.info(f"    {i}. {stock['ts_code']} {stock.get('name', '')} "
                           f"评分:{stock.get('score', 0):.1f} "
                           f"目标价:{stock.get('target_price', 0):.2f} "
                           f"止损价:{stock.get('stop_loss_price', 0):.2f}")

        return selection_result

    except Exception as e:
        logger.error(f"选股失败: {e}")
        return None

def generate_report(market_status, macro_result, market_result, selection_result):
    """生成分析报告"""
    logger.info("=" * 60)
    logger.info("第三步：生成分析报告")
    logger.info("=" * 60)

    try:
        report_date = datetime.now().strftime('%Y-%m-%d')
        report_path = config.REPORTS_DIR / f"stock_analysis_report_{report_date}.md"

        with open(report_path, 'w', encoding='utf-8') as f:
            # 1. 报告标题
            f.write(f"# A股交易策略日报 - {report_date}\n\n")

            # 2. 大盘综述
            f.write("## 一、大盘综述\n\n")
            f.write("### 【宏观经济】\n\n")

            if macro_result:
                f.write(f"- PMI: {macro_result.get('indicators', {}).get('PMI', {}).get('value', 'N/A')} ")
                pmi_trend = macro_result.get('indicators', {}).get('PMI', {}).get('trend', 0)
                if pmi_trend > 0:
                    f.write("(↑)\n")
                elif pmi_trend < 0:
                    f.write("(↓)\n")
                else:
                    f.write("\n")

                f.write(f"- CPI: {macro_result.get('indicators', {}).get('CPI', {}).get('value', 'N/A')}% - ")
                cpi_value = macro_result.get('indicators', {}).get('CPI', {}).get('value', 0)
                if 2 <= cpi_value <= 3:
                    f.write("温和通胀\n")
                elif cpi_value > 3:
                    f.write("通胀压力\n")
                else:
                    f.write("通缩压力\n")

                f.write(f"- M2增速: {macro_result.get('indicators', {}).get('M2_GROWTH', {}).get('value', 'N/A')}% ")
                m2_trend = macro_result.get('indicators', {}).get('M2_GROWTH', {}).get('trend', 0)
                if m2_trend > 0:
                    f.write("(↑)\n")
                elif m2_trend < 0:
                    f.write("(↓)\n")
                else:
                    f.write("\n")

                f.write(f"\n宏观评分: {macro_result.get('score', 50):.1f}/100\n")
                f.write(f"景气水平: {macro_result.get('level', '未知')}\n")
                f.write(f"整体趋势: {macro_result.get('trend', '未知')}\n\n")

            f.write("### 【技术面】\n\n")

            if market_result:
                shanghai = market_result.get('indices', {}).get('000001', {})
                if shanghai:
                    f.write(f"- 上证指数: {shanghai['current']:.0f}点，")
                    f.write(f"涨跌幅 {shanghai['change_pct']:.2f}%\n")

                f.write(f"- 技术评分: {market_result.get('overall_score', 50):.1f}/100\n")

                # 支撑位
                support_levels = market_result.get('support_levels', [])
                if support_levels:
                    f.write("- 关键支撑位: ")
                    f.write(", ".join([f"{level['name']} {level['level']:.0f}" for level in support_levels[:2]]))
                    f.write("\n")

                # 压力位
                resistance_levels = market_result.get('resistance_levels', [])
                if resistance_levels:
                    f.write("- 关键压力位: ")
                    f.write(", ".join([f"{level['name']} {level['level']:.0f}" for level in resistance_levels[:2]]))
                    f.write("\n")

                f.write(f"\n整体趋势: {market_result.get('trend', '未知')}\n\n")

            f.write("### 【结论】\n\n")
            if market_status:
                f.write(f"**大盘状态**: {market_status['status_name']}\n")
                f.write(f"**风险等级**: {market_status['risk_level']}\n")
                f.write(f"**综合评分**: {market_status['composite_score']:.1f}/100\n\n")

            # 3. 持仓建议
            f.write("## 二、持仓建议\n\n")

            if selection_result:
                growth_stocks = selection_result.get('growth_stocks', [])
                value_stocks = selection_result.get('value_stocks', [])

                # 成长股建议
                if growth_stocks:
                    f.write(f"### 成长股策略 (目标仓位: {market_status['growth_ratio']*100:.0f}%)\n\n")
                    for stock in growth_stocks:
                        action = "持有" if stock.get('current_price', 0) < stock.get('target_price', 0) else "观察"
                        f.write(f"- **[{action}]** {stock['ts_code']} **{stock.get('name', 'N/A')}**\n")
                        f.write(f"  - 评分: {stock.get('score', 0):.1f}\n")
                        f.write(f"  - 现价: {stock.get('current_price', 0):.2f}元\n")
                        f.write(f"  - 目标: {stock.get('target_price', 0):.2f}元\n")
                        f.write(f"  - 止损: {stock.get('stop_loss_price', 0):.2f}元\n")
                        f.write(f"  - 建议仓位: {stock.get('position_ratio', 0)*100:.1f}%\n")
                        f.write(f"  - 选股逻辑: {stock.get('reason', '')}\n\n")

                # 价值股建议
                if value_stocks:
                    f.write(f"### 价值股策略 (目标仓位: {market_status['value_ratio']*100:.0f}%)\n\n")
                    for stock in value_stocks:
                        action = "持有" if stock.get('current_price', 0) < stock.get('target_price', 0) else "观察"
                        f.write(f"- **[{action}]** {stock['ts_code']} **{stock.get('name', 'N/A')}**\n")
                        f.write(f"  - 评分: {stock.get('score', 0):.1f}\n")
                        f.write(f"  - 现价: {stock.get('current_price', 0):.2f}元\n")
                        f.write(f"  - 目标: {stock.get('target_price', 0):.2f}元\n")
                        f.write(f"  - 止损: {stock.get('stop_loss_price', 0):.2f}元\n")
                        f.write(f"  - 建议仓位: {stock.get('position_ratio', 0)*100:.1f}%\n")
                        f.write(f"  - 选股逻辑: {stock.get('reason', '')}\n\n")

            else:
                f.write("今日无选股建议\n\n")

            # 4. 风险提示
            f.write("## 三、风险提示\n\n")
            f.write("1. **市场风险**\n")
            if market_status and market_status['risk_level'] == '中高':
                f.write("   - 当前市场风险较高，建议控制仓位\n")
            f.write("   - 外围市场波动可能影响A股走势\n\n")

            f.write("2. **个股风险**\n")
            f.write("   - 财务数据可能存在滞后性\n")
            f.write("   - 重点关注公司业绩变化\n\n")

            f.write("3. **交易风险**\n")
            f.write("   - 严格执行止盈止损纪律\n")
            f.write(f"   - 单只股票最大仓位不超过{config.RISK_CONTROL['max_single_position']*100:.0f}%\n")
            f.write(f"   - 总止损线: {config.RISK_CONTROL['stop_loss_ratio']*100:.1f}%\n\n")

            # 5. 操作纪律
            f.write("## 四、操作纪律\n\n")
            f.write("1. 仓位管理\n")
            f.write("   - 严格按照大盘状态调整成长股和价值股的仓位配比\n")
            f.write(f"   - 牛市: 成长股{config.MARKET_STATUS['BULL']['growth_ratio']*100:.0f}% + "
                   f"价值股{config.MARKET_STATUS['BULL']['value_ratio']*100:.0f}%\n")
            f.write(f"   - 震荡市: 成长股{config.MARKET_STATUS['OSCILLATION']['growth_ratio']*100:.0f}% + "
                   f"价值股{config.MARKET_STATUS['OSCILLATION']['value_ratio']*100:.0f}%\n")
            f.write(f"   - 熊市: 成长股{config.MARKET_STATUS['BEAR']['growth_ratio']*100:.0f}% + "
                   f"价值股{config.MARKET_STATUS['BEAR']['value_ratio']*100:.0f}%\n\n")

            f.write("2. 买入时机\n")
            f.write("   - 股价回调至支撑位附近企稳\n")
            f.write("   - 技术指标出现买入信号\n")
            f.write("   - 确认大盘环境稳定\n\n")

            f.write("3. 卖出时机\n")
            f.write("   - 达到目标价考虑减仓\n")
            f.write("   - 跌破止损价坚决止损\n")
            f.write("   - 大盘转弱时降低仓位\n\n")

            f.write("4. 止盈止损\n")
            f.write("   - 单股止损线: 8%\n")
            f.write("   - 单股目标收益: 10%-25%\n")
            f.write("   - 严格执行，不主观调整\n\n")

            # 6. 免责声明
            f.write("---\n\n")
            f.write("**免责声明**: 本报告仅供研究参考，不构成投资建议。股市有风险，投资需谨慎。")
            f.write("请结合自身风险承受能力，理性决策。本系统基于公开数据和历史规律进行分析，")
            f.write("不保证结果的准确性和盈利性。\n")

        logger.info(f"分析报告已生成: {report_path}")
        return report_path

    except Exception as e:
        logger.error(f"生成报告失败: {e}")
        return None

def main():
    """主函数"""
    try:
        # 初始化系统
        db = init_system()

        # 获取初始数据（首次运行）
        # fetch_initial_data(db)

        # 1. 宏观与大盘分析
        market_status, macro_result, market_result = analyze_macro_and_market()

        # 2. 选股策略
        selection_result = select_stocks(market_status)

        # 3. 生成报告
        report_path = generate_report(market_status, macro_result, market_result, selection_result)

        logger.info("=" * 60)
        logger.info("分析完成！")
        logger.info("=" * 60)
        if report_path:
            logger.info(f"报告路径: {report_path}")

        return {
            'market_status': market_status,
            'macro_result': macro_result,
            'market_result': market_result,
            'selection_result': selection_result,
            'report_path': report_path
        }

    except Exception as e:
        logger.error(f"系统运行失败: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        # 关闭数据库连接
        if 'db' in locals():
            db.close()

if __name__ == "__main__":
    main()