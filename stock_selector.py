"""
选股策略模块 - 成长股和价值股策略
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import config
import data_fetcher as df

logger = logging.getLogger(__name__)


class StockSelector:
    """选股基类"""

    def __init__(self, strategy_name: str):
        """
        初始化选股器

        Args:
            strategy_name: 策略名称
        """
        self.strategy_name = strategy_name
        self.db = df.data_fetcher.db

    def select_stocks(self, market_status: str, position_ratio: float) -> List[Dict[str, Any]]:
        """
        选股主方法

        Args:
            market_status: 大盘状态
            position_ratio: 该策略的目标仓位比例

        Returns:
            选中的股票列表
        """
        logger.info(f"开始执行{self.strategy_name}选股策略...")

        try:
            # 1. 获取股票池
            stock_pool = self._get_stock_pool()
            logger.info(f"初始股票池数量: {len(stock_pool)}")

            # 2. 应用策略筛选条件
            filtered_stocks = self._apply_filters(stock_pool)
            logger.info(f"筛选后股票数量: {len(filtered_stocks)}")

            # 3. 计算评分
            scored_stocks = self._calculate_scores(filtered_stocks)
            logger.info(f"评分完成股票数量: {len(scored_stocks)}")

            # 4. 排序并选择最优股票
            selected_stocks = self._select_top_stocks(scored_stocks, position_ratio)
            logger.info(f"最终选中股票数量: {len(selected_stocks)}")

            # 5. 计算目标价和止损价
            selected_stocks = self._calculate_price_targets(selected_stocks)

            # 6. 保存到数据库
            self._save_selection_results(selected_stocks)

            return selected_stocks

        except Exception as e:
            logger.error(f"{self.strategy_name}选股失败: {e}")
            return []

    def _get_stock_pool(self) -> pd.DataFrame:
        """获取股票池"""
        query = """
            SELECT ts_code, symbol, name, industry, is_st
            FROM stock_basic
            WHERE ts_code IS NOT NULL
            AND name IS NOT NULL
        """
        results = self.db.execute_query(query)
        return pd.DataFrame(results)

    def _apply_filters(self, stocks: pd.DataFrame) -> pd.DataFrame:
        """应用筛选条件（由子类实现）"""
        raise NotImplementedError("子类必须实现此方法")

    def _calculate_scores(self, stocks: pd.DataFrame) -> pd.DataFrame:
        """计算评分（由子类实现）"""
        raise NotImplementedError("子类必须实现此方法")

    def _select_top_stocks(self, stocks: pd.DataFrame, position_ratio: float) -> List[Dict[str, Any]]:
        """选择最优股票"""
        # 根据目标仓位比例确定股票数量
        # 假设单只股票最大仓位为15%
        max_single_position = config.RISK_CONTROL['max_single_position']
        num_stocks = int(position_ratio / max_single_position)

        # 按评分降序排序
        sorted_stocks = stocks.sort_values('score', ascending=False)

        # 取前N只股票
        top_stocks = sorted_stocks.head(num_stocks)

        # 重新分配仓位
        if len(top_stocks) > 0:
            equal_ratio = position_ratio / len(top_stocks)
            top_stocks['position_ratio'] = equal_ratio

        return top_stocks.to_dict('records')

    def _calculate_price_targets(self, stocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """计算目标价和止损价"""
        for stock in stocks:
            current_price = stock.get('current_price', 0)

            if current_price > 0:
                # 目标价：根据评分和当前价计算
                score = stock.get('score', 50)
                target_up_pct = 0.10 + (score - 50) / 100 * 0.15  # 10%-25%
                stock['target_price'] = round(current_price * (1 + target_up_pct), 2)

                # 止损价：根据大盘风险等级调整
                stop_loss_pct = 0.08  # 默认8%
                stock['stop_loss_price'] = round(current_price * (1 - stop_loss_pct), 2)

        return stocks

    def _save_selection_results(self, stocks: List[Dict[str, Any]]):
        """保存选股结果到数据库"""
        for stock in stocks:
            try:
                record = {
                    'selection_date': datetime.now().strftime('%Y-%m-%d'),
                    'ts_code': stock.get('ts_code', ''),
                    'strategy_type': self.strategy_name.upper(),
                    'score': stock.get('score', 0),
                    'rank': stock.get('rank', 0),
                    'position_ratio': stock.get('position_ratio', 0),
                    'target_price': stock.get('target_price', 0),
                    'stop_loss_price': stock.get('stop_loss_price', 0),
                    'reason': stock.get('reason', '')
                }
                self.db.insert_data('stock_selection', record)
            except Exception as e:
                logger.debug(f"保存选股结果失败: {e}")


class GrowthStockSelector(StockSelector):
    """成长股选股策略"""

    def __init__(self):
        """初始化成长股选股器"""
        super().__init__("GROWTH")
        self.params = config.GROWTH_STRATEGY

    def _apply_filters(self, stocks: pd.DataFrame) -> pd.DataFrame:
        """应用成长股筛选条件"""
        logger.info("应用成长股筛选条件...")

        # 1. 排除ST股票
        if self.params['exclude_st']:
            stocks = stocks[stocks['is_st'] == 0]

        # 2. 筛选行业
        preferred_sectors = self.params['preferred_sectors']
        if preferred_sectors:
            stocks = stocks[stocks['industry'].isin(preferred_sectors)]

        # 3. 获取财务数据
        filtered_stocks = []
        for _, stock in stocks.iterrows():
            ts_code = stock['ts_code']
            financial_data = self._get_financial_data(ts_code)

            if not financial_data:
                continue

            # 应用财务指标筛选
            if self._check_growth_criteria(financial_data):
                stock['financial_data'] = financial_data
                filtered_stocks.append(stock.to_dict())

        return pd.DataFrame(filtered_stocks)

    def _get_financial_data(self, ts_code: str) -> Optional[Dict[str, Any]]:
        """获取最新财务数据"""
        try:
            query = """
                SELECT * FROM financial_data
                WHERE ts_code = ?
                ORDER BY end_date DESC
                LIMIT 1
            """
            result = self.db.execute_query(query, (ts_code,))

            if result:
                return result[0]

            # 如果数据库没有数据，尝试从AkShare获取
            logger.debug(f"数据库无财务数据 {ts_code}，尝试从AkShare获取")
            df_financial = df.data_fetcher.fetch_stock_financial(ts_code)

            if not df_financial.empty:
                latest = df_financial.iloc[-1]
                return latest.to_dict()

        except Exception as e:
            logger.debug(f"获取财务数据失败 {ts_code}: {e}")

        return None

    def _check_growth_criteria(self, financial_data: Dict[str, Any]) -> bool:
        """检查是否满足成长股标准"""
        try:
            roe = financial_data.get('roe')
            revenue_yoy = financial_data.get('revenue_yoy')
            net_profit_yoy = financial_data.get('net_profit_yoy')
            gross_margin = financial_data.get('gross_margin')

            # ROE检查
            if roe is None or roe < self.params['roe_min']:
                return False

            # 营收增长率检查
            if revenue_yoy is None or revenue_yoy < self.params['revenue_growth_min']:
                return False

            # 净利润增长率检查
            if net_profit_yoy is None or net_profit_yoy < self.params['profit_growth_min']:
                return False

            # 毛利率检查
            if gross_margin is None or gross_margin < self.params['gross_margin_min']:
                return False

            return True

        except Exception as e:
            logger.debug(f"检查成长股标准失败: {e}")
            return False

    def _calculate_scores(self, stocks: pd.DataFrame) -> pd.DataFrame:
        """计算成长股评分"""
        logger.info("计算成长股评分...")

        for idx, stock in stocks.iterrows():
            score = 50  # 基础分
            reasons = []

            financial_data = stock.get('financial_data', {})

            # ROE评分 (权重: 20%)
            roe = financial_data.get('roe', 0)
            if roe >= 20:
                score += 10
                reasons.append("ROE优异(≥20%)")
            elif roe >= 15:
                score += 5
                reasons.append("ROE良好(15-20%)")

            # 营收增长率评分 (权重: 25%)
            revenue_yoy = financial_data.get('revenue_yoy', 0)
            if revenue_yoy >= 50:
                score += 15
                reasons.append(f"营收高增长({revenue_yoy:.1f}%)")
            elif revenue_yoy >= 30:
                score += 10
                reasons.append(f"营收增长良好({revenue_yoy:.1f}%)")
            elif revenue_yoy >= 20:
                score += 5
                reasons.append(f"营收稳健增长({revenue_yoy:.1f}%)")

            # 净利润增长率评分 (权重: 25%)
            profit_yoy = financial_data.get('net_profit_yoy', 0)
            if profit_yoy >= 50:
                score += 15
                reasons.append(f"利润高增长({profit_yoy:.1f}%)")
            elif profit_yoy >= 30:
                score += 10
                reasons.append(f"利润增长良好({profit_yoy:.1f}%)")
            elif profit_yoy >= 20:
                score += 5
                reasons.append(f"利润稳健增长({profit_yoy:.1f}%)")

            # 毛利率评分 (权重: 15%)
            gross_margin = financial_data.get('gross_margin', 0)
            if gross_margin >= 50:
                score += 10
                reasons.append("毛利率优异(≥50%)")
            elif gross_margin >= 40:
                score += 5
                reasons.append("毛利率良好(40-50%)")

            # 行业稀缺性加分 (权重: 5%)
            industry = stock.get('industry', '')
            if industry in ['计算机', '半导体', '生物医药']:
                score += 5
                reasons.append("行业稀缺性强")

            # 限制分数范围
            score = max(0, min(100, score))

            stocks.at[idx, 'score'] = score
            stocks.at[idx, 'reason'] = '、'.join(reasons)

            # 获取当前价格
            current_price = self._get_current_price(stock['ts_code'])
            stocks.at[idx, 'current_price'] = current_price

        return stocks

    def _get_current_price(self, ts_code: str) -> float:
        """获取当前股价"""
        try:
            # 获取估值数据
            query = """
                SELECT close FROM valuation_data
                WHERE ts_code = ?
                ORDER BY trade_date DESC
                LIMIT 1
            """
            result = self.db.execute_query(query, (ts_code,))

            if result and result[0]['close']:
                return result[0]['close']

            # 尝试从AkShare获取
            realtime_data = df.data_fetcher.fetch_stock_realtime_pe_pb(ts_code)
            if 'close' in realtime_data:
                return realtime_data['close']

        except Exception as e:
            logger.debug(f"获取当前价失败 {ts_code}: {e}")

        return 0


class ValueStockSelector(StockSelector):
    """价值股选股策略"""

    def __init__(self):
        """初始化价值股选股器"""
        super().__init__("VALUE")
        self.params = config.VALUE_STRATEGY

    def _apply_filters(self, stocks: pd.DataFrame) -> pd.DataFrame:
        """应用价值股筛选条件"""
        logger.info("应用价值股筛选条件...")

        # 1. 排除ST股票
        if self.params['exclude_st']:
            stocks = stocks[stocks['is_st'] == 0]

        # 2. 筛选行业
        preferred_sectors = self.params['preferred_sectors']
        if preferred_sectors:
            stocks = stocks[stocks['industry'].isin(preferred_sectors)]

        # 3. 获取估值和财务数据
        filtered_stocks = []
        for _, stock in stocks.iterrows():
            ts_code = stock['ts_code']

            financial_data = self._get_financial_data(ts_code)
            valuation_data = self._get_valuation_data(ts_code)

            if not financial_data or not valuation_data:
                continue

            # 应用价值股标准
            if self._check_value_criteria(financial_data, valuation_data):
                stock['financial_data'] = financial_data
                stock['valuation_data'] = valuation_data
                filtered_stocks.append(stock.to_dict())

        return pd.DataFrame(filtered_stocks)

    def _get_financial_data(self, ts_code: str) -> Optional[Dict[str, Any]]:
        """获取最新财务数据"""
        try:
            query = """
                SELECT * FROM financial_data
                WHERE ts_code = ?
                ORDER BY end_date DESC
                LIMIT 1
            """
            result = self.db.execute_query(query, (ts_code,))

            if result:
                return result[0]

        except Exception as e:
            logger.debug(f"获取财务数据失败 {ts_code}: {e}")

        return None

    def _get_valuation_data(self, ts_code: str) -> Optional[Dict[str, Any]]:
        """获取最新估值数据"""
        try:
            # 获取实时估值数据
            valuation_data = df.data_fetcher.fetch_stock_realtime_pe_pb(ts_code)

            if valuation_data:
                return valuation_data

        except Exception as e:
            logger.debug(f"获取估值数据失败 {ts_code}: {e}")

        return None

    def _check_value_criteria(self, financial_data: Dict, valuation_data: Dict) -> bool:
        """检查是否满足价值股标准"""
        try:
            pe = valuation_data.get('pe')
            pb = valuation_data.get('pb')
            dividend_yield = valuation_data.get('dividend_yield', 0)
            roe = financial_data.get('roe')
            debt_ratio = financial_data.get('debt_ratio')

            # PE检查
            if pe is None or pe > self.params['pe_max']:
                return False

            # PB检查
            if pb is None or pb > self.params['pb_max']:
                return False

            # 股息率检查
            if dividend_yield is None or dividend_yield < self.params['dividend_yield_min']:
                return False

            # ROE检查
            if roe is None or roe < self.params['roe_min']:
                return False

            # 负债率检查
            if debt_ratio is None or debt_ratio > self.params['debt_ratio_max']:
                return False

            return True

        except Exception as e:
            logger.debug(f"检查价值股标准失败: {e}")
            return False

    def _calculate_scores(self, stocks: pd.DataFrame) -> pd.DataFrame:
        """计算价值股评分"""
        logger.info("计算价值股评分...")

        for idx, stock in stocks.iterrows():
            score = 50  # 基础分
            reasons = []

            financial_data = stock.get('financial_data', {})
            valuation_data = stock.get('valuation_data', {})

            # PE评分 (权重: 25%)
            pe = valuation_data.get('pe', 0)
            if pe <= 8:
                score += 15
                reasons.append(f"PE极低(≤8)")
            elif pe <= 12:
                score += 10
                reasons.append(f"PE低估(8-12)")
            elif pe <= 15:
                score += 5
                reasons.append(f"PE合理(12-15)")

            # PB评分 (权重: 20%)
            pb = valuation_data.get('pb', 0)
            if pb <= 0.8:
                score += 15
                reasons.append(f"PB极低(≤0.8)")
            elif pb <= 1.2:
                score += 10
                reasons.append(f"PB低估(0.8-1.2)")
            elif pb <= 2:
                score += 5
                reasons.append(f"PB合理(1.2-2)")

            # 股息率评分 (权重: 20%)
            dividend_yield = valuation_data.get('dividend_yield', 0)
            if dividend_yield >= 6:
                score += 15
                reasons.append(f"股息率极高(≥6%)")
            elif dividend_yield >= 4:
                score += 10
                reasons.append(f"股息率高(4-6%)")
            elif dividend_yield >= 3:
                score += 5
                reasons.append(f"股息率良好(3-4%)")

            # ROE评分 (权重: 20%)
            roe = financial_data.get('roe', 0)
            if roe >= 15:
                score += 15
                reasons.append("ROE优异(≥15%)")
            elif roe >= 12:
                score += 10
                reasons.append("ROE良好(12-15%)")
            elif roe >= 10:
                score += 5
                reasons.append("ROE尚可(10-12%)")

            # 财务稳健性加分 (权重: 10%)
            debt_ratio = financial_data.get('debt_ratio', 0)
            if debt_ratio <= 30:
                score += 10
                reasons.append("负债率极低(≤30%)")
            elif debt_ratio <= 50:
                score += 5
                reasons.append("负债率低(30-50%)")

            # 限制分数范围
            score = max(0, min(100, score))

            stocks.at[idx, 'score'] = score
            stocks.at[idx, 'reason'] = '、'.join(reasons)

            # 获取当前价格
            current_price = self._get_current_price(stock['ts_code'])
            stocks.at[idx, 'current_price'] = current_price

        return stocks

    def _get_current_price(self, ts_code: str) -> float:
        """获取当前股价"""
        try:
            # 尝试从AkShare获取实时数据
            realtime_data = df.data_fetcher.fetch_stock_realtime_pe_pb(ts_code)
            if realtime_data:
                # 使用实时市值估算
                total_mv = realtime_data.get('total_mv', 0)
                if total_mv > 0:
                    return total_mv  # 这里简化处理，实际需要除以股本

        except Exception as e:
            logger.debug(f"获取当前价失败 {ts_code}: {e}")

        return 0


def run_stock_selection(market_status: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行完整的选股流程

    Args:
        market_status: 大盘状态分析结果

    Returns:
        选股结果
    """
    logger.info("开始执行选股流程...")

    result = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'market_status': market_status['status_name'],
        'growth_ratio': market_status['growth_ratio'],
        'value_ratio': market_status['value_ratio'],
        'growth_stocks': [],
        'value_stocks': []
    }

    try:
        # 1. 成长股选股
        if market_status['growth_ratio'] > 0:
            growth_selector = GrowthStockSelector()
            growth_stocks = growth_selector.select_stocks(
                market_status['status'],
                market_status['growth_ratio']
            )
            result['growth_stocks'] = growth_stocks
            logger.info(f"成长股选股完成: {len(growth_stocks)}只")

        # 2. 价值股选股
        if market_status['value_ratio'] > 0:
            value_selector = ValueStockSelector()
            value_stocks = value_selector.select_stocks(
                market_status['status'],
                market_status['value_ratio']
            )
            result['value_stocks'] = value_stocks
            logger.info(f"价值股选股完成: {len(value_stocks)}只")

    except Exception as e:
        logger.error(f"选股流程失败: {e}")
        result['error'] = str(e)

    return result


# 全局选股器实例
growth_selector = GrowthStockSelector()
value_selector = ValueStockSelector()