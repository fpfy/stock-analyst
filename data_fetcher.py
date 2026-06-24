"""
数据获取模块 - 使用AkShare获取A股数据
"""

import akshare as ak
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import database as db

logger = logging.getLogger(__name__)

class DataFetcher:
    """数据获取类"""

    def __init__(self):
        """初始化数据获取器"""
        self.db = db.db

    def fetch_macro_indicator(self, indicator_name: str, start_date: str = None) -> pd.DataFrame:
        """
        获取宏观经济指标数据

        Args:
            indicator_name: 指标名称 (PMI, CPI, PPI, M2, GDP等)
            start_date: 起始日期 (YYYY-MM-DD)

        Returns:
            指标数据DataFrame
        """
        try:
            if indicator_name == "PMI":
                data = ak.macro_china_pmi()
                data['indicator_name'] = 'PMI'
            elif indicator_name == "CPI":
                data = ak.macro_china_cpi()
                data['indicator_name'] = 'CPI'
            elif indicator_name == "PPI":
                data = ak.macro_china_ppi()
                data['indicator_name'] = 'PPI'
            elif indicator_name == "M2":
                data = ak.macro_china_m2()
                data['indicator_name'] = 'M2'
            elif indicator_name == "GDP":
                data = ak.macro_china_gdp()
                data['indicator_name'] = 'GDP'
            else:
                logger.warning(f"不支持的宏观指标: {indicator_name}")
                return pd.DataFrame()

            # 数据清洗
            if not data.empty:
                # 日期处理
                if '月份' in data.columns:
                    data['date'] = pd.to_datetime(data['月份'], errors='coerce')
                elif '时间' in data.columns:
                    data['date'] = pd.to_datetime(data['时间'], errors='coerce')
                else:
                    data['date'] = pd.to_datetime(data.iloc[:, 0], errors='coerce')

                # 提取年份和月份
                data['year'] = data['date'].dt.year.astype(str)
                data['month'] = data['date'].dt.month.astype(str)

                # 过滤日期
                if start_date:
                    data = data[data['date'] >= start_date]

                # 重命名列
                if '今值' in data.columns:
                    data['value'] = pd.to_numeric(data['今值'], errors='coerce')
                elif '数值' in data.columns:
                    data['value'] = pd.to_numeric(data['数值'], errors='coerce')

                # 保存到数据库
                self._save_macro_to_db(data, indicator_name)
                logger.info(f"成功获取宏观指标: {indicator_name}, 记录数: {len(data)}")

            return data

        except Exception as e:
            logger.error(f"获取宏观指标失败 {indicator_name}: {e}")
            return pd.DataFrame()

    def _save_macro_to_db(self, data: pd.DataFrame, indicator_name: str):
        """保存宏观经济数据到数据库"""
        for _, row in data.iterrows():
            try:
                record = {
                    'indicator_name': indicator_name,
                    'date': str(row['date'].date()) if pd.notna(row['date']) else '',
                    'value': float(row['value']) if 'value' in row and pd.notna(row['value']) else None,
                    'year': row.get('year', ''),
                    'month': row.get('month', ''),
                    'source': 'AkShare'
                }
                self.db.insert_data('macro_indicators', record)
            except Exception as e:
                logger.debug(f"保存宏观数据失败: {e}")

    def fetch_index_data(self, index_code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取指数数据

        Args:
            index_code: 指数代码 (000001为上证指数, 399001为深证成指)
            start_date: 起始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            指数数据DataFrame
        """
        try:
            # AkShare指数数据接口
            data = ak.index_zh_a_hist(symbol=index_code, period="daily",
                                       start_date=start_date, end_date=end_date)

            if not data.empty:
                # 数据清洗
                data.rename(columns={
                    '日期': 'date',
                    '开盘': 'open',
                    '收盘': 'close',
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'volume',
                    '成交额': 'amount',
                    '振幅': 'amplitude',
                    '涨跌幅': 'change_pct',
                    '涨跌额': 'change_amount',
                    '换手率': 'turnover'
                }, inplace=True)

                # 计算技术指标
                data = self._calculate_index_technical(data)

                # 获取指数名称
                index_names = {'000001': '上证指数', '399001': '深证成指',
                              '399006': '创业板指', '000300': '沪深300'}
                index_name = index_names.get(index_code, index_code)

                data['index_code'] = index_code
                data['index_name'] = index_name

                # 保存到数据库
                self._save_index_to_db(data)

                logger.info(f"成功获取指数数据: {index_name}, 记录数: {len(data)}")

            return data

        except Exception as e:
            logger.error(f"获取指数数据失败 {index_code}: {e}")
            return pd.DataFrame()

    def _calculate_index_technical(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算指数技术指标"""
        try:
            # 计算移动平均线
            for period in [5, 10, 20, 60]:
                if len(data) >= period:
                    data[f'ma{period}'] = data['close'].rolling(window=period).mean()

            return data
        except Exception as e:
            logger.error(f"计算指数技术指标失败: {e}")
            return data

    def _save_index_to_db(self, data: pd.DataFrame):
        """保存指数数据到数据库"""
        for _, row in data.iterrows():
            try:
                record = {
                    'index_code': str(row.get('index_code', '')),
                    'index_name': str(row.get('index_name', '')),
                    'date': str(row.get('date', '')),
                    'open': float(row['open']) if pd.notna(row.get('open')) else None,
                    'high': float(row['high']) if pd.notna(row.get('high')) else None,
                    'low': float(row['low']) if pd.notna(row.get('low')) else None,
                    'close': float(row['close']) if pd.notna(row.get('close')) else None,
                    'volume': float(row['volume']) if pd.notna(row.get('volume')) else None,
                    'amount': float(row['amount']) if pd.notna(row.get('amount')) else None,
                    'change_pct': float(row['change_pct']) if pd.notna(row.get('change_pct')) else None,
                    'ma5': float(row['ma5']) if 'ma5' in row and pd.notna(row.get('ma5')) else None,
                    'ma10': float(row['ma10']) if 'ma10' in row and pd.notna(row.get('ma10')) else None,
                    'ma20': float(row['ma20']) if 'ma20' in row and pd.notna(row.get('ma20')) else None,
                    'ma60': float(row['ma60']) if 'ma60' in row and pd.notna(row.get('ma60')) else None,
                }
                self.db.insert_data('index_data', record)
            except Exception as e:
                logger.debug(f"保存指数数据失败: {e}")

    def fetch_stock_basic(self) -> pd.DataFrame:
        """
        获取A股股票基本信息

        Returns:
            股票基本信息DataFrame
        """
        try:
            data = ak.stock_info_a_code_name()

            if not data.empty:
                # 数据清洗
                data.rename(columns={
                    'code': 'ts_code',
                    'name': 'name'
                }, inplace=True)

                # 过滤掉ST股票
                data['is_st'] = data['name'].apply(
                    lambda x: 1 if isinstance(x, str) and ('ST' in x or '退' in x) else 0
                )

                # 保存到数据库
                self._save_stock_basic_to_db(data)

                logger.info(f"成功获取股票基本信息, 记录数: {len(data)}")

            return data

        except Exception as e:
            logger.error(f"获取股票基本信息失败: {e}")
            return pd.DataFrame()

    def _save_stock_basic_to_db(self, data: pd.DataFrame):
        """保存股票基本信息到数据库"""
        for _, row in data.iterrows():
            try:
                record = {
                    'ts_code': str(row.get('ts_code', '')),
                    'symbol': str(row.get('ts_code', '')),
                    'name': str(row.get('name', '')),
                    'is_st': int(row.get('is_st', 0))
                }
                # 使用ON CONFLICT更新
                self.db.execute_query(
                    """
                    INSERT INTO stock_basic (ts_code, symbol, name, is_st)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(ts_code) DO UPDATE SET
                        symbol = excluded.symbol,
                        name = excluded.name,
                        is_st = excluded.is_st,
                        update_date = CURRENT_TIMESTAMP
                    """,
                    (record['ts_code'], record['symbol'], record['name'], record['is_st']),
                    commit=True
                )
            except Exception as e:
                logger.debug(f"保存股票基本信息失败: {e}")

    def fetch_stock_financial(self, ts_code: str, start_date: str = None) -> pd.DataFrame:
        """
        获取股票财务数据

        Args:
            ts_code: 股票代码
            start_date: 起始日期 (YYYY-MM-DD)

        Returns:
            财务数据DataFrame
        """
        try:
            # 获取财务指标
            data = ak.stock_financial_analysis_indicator(symbol=ts_code)

            if not data.empty:
                # 数据清洗和重命名
                data.rename(columns={
                    '日期': 'end_date',
                    '净资产收益率': 'roe',
                    '总资产净利润率': 'roa',
                    '毛利率': 'gross_margin',
                    '净利率': 'net_margin',
                    '营业总收入同比增长': 'revenue_yoy',
                    '归属母公司股东的净利润同比增长': 'net_profit_yoy',
                    '资产负债率': 'debt_ratio',
                    '每股收益': 'eps',
                    '每股净资产': 'bps'
                }, inplace=True)

                # 转换数据类型
                numeric_cols = ['roe', 'roa', 'gross_margin', 'net_margin',
                               'revenue_yoy', 'net_profit_yoy', 'debt_ratio', 'eps', 'bps']
                for col in numeric_cols:
                    if col in data.columns:
                        data[col] = pd.to_numeric(data[col], errors='coerce')

                # 保存到数据库
                self._save_financial_to_db(data, ts_code)

                logger.debug(f"成功获取股票财务数据: {ts_code}, 记录数: {len(data)}")

            return data

        except Exception as e:
            logger.error(f"获取股票财务数据失败 {ts_code}: {e}")
            return pd.DataFrame()

    def _save_financial_to_db(self, data: pd.DataFrame, ts_code: str):
        """保存财务数据到数据库"""
        for _, row in data.iterrows():
            try:
                record = {
                    'ts_code': ts_code,
                    'ann_date': str(row.get('end_date', '')),
                    'end_date': str(row.get('end_date', '')),
                    'roe': float(row['roe']) if 'roe' in row and pd.notna(row.get('roe')) else None,
                    'roa': float(row['roa']) if 'roa' in row and pd.notna(row.get('roa')) else None,
                    'gross_margin': float(row['gross_margin']) if 'gross_margin' in row and pd.notna(row.get('gross_margin')) else None,
                    'net_margin': float(row['net_margin']) if 'net_margin' in row and pd.notna(row.get('net_margin')) else None,
                    'revenue_yoy': float(row['revenue_yoy']) if 'revenue_yoy' in row and pd.notna(row.get('revenue_yoy')) else None,
                    'net_profit_yoy': float(row['net_profit_yoy']) if 'net_profit_yoy' in row and pd.notna(row.get('net_profit_yoy')) else None,
                    'debt_ratio': float(row['debt_ratio']) if 'debt_ratio' in row and pd.notna(row.get('debt_ratio')) else None,
                    'eps': float(row['eps']) if 'eps' in row and pd.notna(row.get('eps')) else None,
                    'bps': float(row['bps']) if 'bps' in row and pd.notna(row.get('bps')) else None,
                }
                self.db.insert_data('financial_data', record)
            except Exception as e:
                logger.debug(f"保存财务数据失败: {e}")

    def fetch_stock_valuation(self, ts_code: str, start_date: str = None) -> pd.DataFrame:
        """
        获取股票估值数据

        Args:
            ts_code: 股票代码
            start_date: 起始日期 (YYYY-MM-DD)

        Returns:
            估值数据DataFrame
        """
        try:
            # 获取历史行情数据
            data = ak.stock_zh_a_hist(symbol=ts_code, period="daily",
                                      start_date=start_date)

            if not data.empty:
                # 数据清洗
                data.rename(columns={
                    '日期': 'date',
                    '开盘': 'open',
                    '收盘': 'close',
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'volume',
                    '成交额': 'amount'
                }, inplace=True)

                # 保存到数据库
                self._save_valuation_to_db(data, ts_code)

                logger.debug(f"成功获取股票估值数据: {ts_code}, 记录数: {len(data)}")

            return data

        except Exception as e:
            logger.error(f"获取股票估值数据失败 {ts_code}: {e}")
            return pd.DataFrame()

    def _save_valuation_to_db(self, data: pd.DataFrame, ts_code: str):
        """保存估值数据到数据库"""
        # 注意：AkShare的历史行情数据中PE/PB需要另外计算或获取
        for _, row in data.iterrows():
            try:
                record = {
                    'ts_code': ts_code,
                    'trade_date': str(row.get('date', '')),
                    'close': float(row['close']) if pd.notna(row.get('close')) else None,
                    'open': float(row['open']) if pd.notna(row.get('open')) else None,
                    'high': float(row['high']) if pd.notna(row.get('high')) else None,
                    'low': float(row['low']) if pd.notna(row.get('low')) else None,
                    'volume': float(row['volume']) if pd.notna(row.get('volume')) else None,
                    'amount': float(row['amount']) if pd.notna(row.get('amount')) else None,
                }
                self.db.insert_data('valuation_data', record)
            except Exception as e:
                logger.debug(f"保存估值数据失败: {e}")

    def fetch_stock_realtime_pe_pb(self, ts_code: str) -> Dict[str, float]:
        """
        获取股票实时PE、PB数据

        Args:
            ts_code: 股票代码

        Returns:
            包含PE、PB等估值指标的字典
        """
        try:
            # 获取实时行情数据
            data = ak.stock_zh_a_spot_em()

            # 查找对应股票
            stock_data = data[data['代码'] == ts_code]

            if not stock_data.empty:
                row = stock_data.iloc[0]
                return {
                    'pe': float(row['市盈率-动态']) if '市盈率-动态' in row and pd.notna(row['市盈率-动态']) else None,
                    'pb': float(row['市净率']) if '市净率' in row and pd.notna(row['市净率']) else None,
                    'dividend_yield': float(row['股息率']) if '股息率' in row and pd.notna(row['股息率']) else None,
                    'total_mv': float(row['总市值']) if '总市值' in row and pd.notna(row['总市值']) else None,
                }

        except Exception as e:
            logger.error(f"获取股票实时PE/PB失败 {ts_code}: {e}")

        return {}

    def fetch_realtime_market(self, index_code: str = '000001') -> Dict[str, Any]:
        """
        获取实时市场数据

        Args:
            index_code: 指数代码

        Returns:
            实时市场数据字典
        """
        try:
            # 获取实时指数数据
            data = ak.index_zh_a_spot_em()
            index_data = data[data['代码'] == index_code]

            if not index_data.empty:
                row = index_data.iloc[0]
                return {
                    'code': str(row['代码']),
                    'name': str(row['名称']),
                    'current': float(row['最新价']),
                    'change': float(row['涨跌额']),
                    'change_pct': float(row['涨跌幅']),
                    'volume': float(row['成交量']),
                    'amount': float(row['成交额']),
                    'high': float(row['最高']),
                    'low': float(row['最低']),
                    'open': float(row['今开'])
                }

        except Exception as e:
            logger.error(f"获取实时市场数据失败: {e}")

        return {}

# 全局数据获取实例
data_fetcher = DataFetcher()