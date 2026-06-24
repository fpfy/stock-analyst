"""
Tushare数据源模块
"""

import tushare as ts
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import os
import database as db

# 统一限流器
from rate_limiter import tushare_limiter

logger = logging.getLogger(__name__)


class TushareDataFetcher:
    """Tushare数据获取器"""

    def __init__(self):
        """初始化Tushare数据获取器"""
        # 从环境变量获取token
        self.token = os.environ.get('TUSHARE_TOKEN', '')

        if not self.token:
            logger.warning("未找到TUSHARE_TOKEN环境变量，请设置环境变量")
        else:
            # 设置token
            ts.set_token(self.token)
            self.pro = ts.pro_api()
            logger.info("Tushare API初始化成功")

        self.db = db.db

    def _check_connection(self) -> bool:
        """检查连接是否正常"""
        try:
            if not hasattr(self, 'pro'):
                logger.error("Tushare API未初始化")
                return False

            # 测试获取交易日历 - 请求前限流
            tushare_limiter.wait(min_interval=1.0, max_interval=2.0)
            self.pro.trade_cal(exchange='SSE', start_date='20250101', end_date='20250110')
            return True

        except Exception as e:
            logger.error(f"Tushare连接检查失败: {e}")
            return False

    def fetch_macro_indicator(self, indicator_name: str, start_date: str = None) -> pd.DataFrame:
        """
        获取宏观经济指标数据

        Args:
            indicator_name: 指标名称
            start_date: 起始日期 (YYYYMMDD)

        Returns:
            指标数据DataFrame
        """
        try:
            if not self._check_connection():
                return pd.DataFrame()

            today = datetime.now().strftime('%Y%m%d')
            start_date = start_date or (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')

            # 根据指标类型调用不同的API
            if indicator_name == "PMI":
                # 获取PMI数据（制造业采购经理指数） - 请求前限流
                tushare_limiter.wait(min_interval=1.0, max_interval=2.0)
                data = self.pro.cn_pmi(start_date=start_date, end_date=today)
                if not data.empty:
                    data.rename(columns={
                        'month': 'date',
                        'pmi': 'value'
                    }, inplace=True)
                    data['indicator_name'] = 'PMI'
                    data['date'] = pd.to_datetime(data['date'], format='%Y%m').dt.strftime('%Y-%m-%d')
                    data['year'] = pd.to_datetime(data['date']).dt.year.astype(str)
                    data['month'] = pd.to_datetime(data['date']).dt.month.astype(str)

            elif indicator_name == "CPI":
                # 获取CPI数据（消费者物价指数） - 请求前限流
                tushare_limiter.wait(min_interval=1.0, max_interval=2.0)
                data = self.pro.cn_cpi(start_date=start_date, end_date=today)
                if not data.empty:
                    data.rename(columns={
                        'month': 'date',
                        'cpi': 'value'
                    }, inplace=True)
                    data['indicator_name'] = 'CPI'
                    data['date'] = pd.to_datetime(data['date'], format='%Y%m').dt.strftime('%Y-%m-%d')
                    data['year'] = pd.to_datetime(data['date']).dt.year.astype(str)
                    data['month'] = pd.to_datetime(data['date']).dt.month.astype(str)

            elif indicator_name == "PPI":
                # 获取PPI数据（生产者物价指数） - 请求前限流
                tushare_limiter.wait(min_interval=1.0, max_interval=2.0)
                data = self.pro.cn_ppi(start_date=start_date, end_date=today)
                if not data.empty:
                    data.rename(columns={
                        'month': 'date',
                        'ppi': 'value'
                    }, inplace=True)
                    data['indicator_name'] = 'PPI'
                    data['date'] = pd.to_datetime(data['date'], format='%Y%m').dt.strftime('%Y-%m-%d')

            elif indicator_name == "M2_GROWTH":
                # 获取M2增速数据 - 请求前限流
                tushare_limiter.wait(min_interval=1.0, max_interval=2.0)
                data = self.pro.m2(start_date=start_date, end_date=today)
                if not data.empty:
                    data.rename(columns={
                        'month': 'date',
                        'm2': 'value'
                    }, inplace=True)
                    data['indicator_name'] = 'M2_GROWTH'
                    data['date'] = pd.to_datetime(data['date'], format='%Y%m').dt.strftime('%Y-%m-%d')

            else:
                logger.warning(f"不支持的宏观指标: {indicator_name}")
                return pd.DataFrame()

            if not data.empty:
                # 保存到数据库
                self._save_macro_to_db(data, indicator_name)
                logger.info(f"成功获取Tushare宏观指标: {indicator_name}, 记录数: {len(data)}")

            return data

        except Exception as e:
            logger.error(f"获取Tushare宏观指标失败 {indicator_name}: {e}")
            return pd.DataFrame()

    def _save_macro_to_db(self, data: pd.DataFrame, indicator_name: str):
        """保存宏观经济数据到数据库"""
        for _, row in data.iterrows():
            try:
                record = {
                    'indicator_name': indicator_name,
                    'date': str(row['date']) if pd.notna(row['date']) else '',
                    'value': float(row['value']) if pd.notna(row['value']) else None,
                    'year': row.get('year', ''),
                    'month': row.get('month', ''),
                    'source': 'Tushare'
                }
                self.db.insert_data('macro_indicators', record)
            except Exception as e:
                logger.debug(f"保存宏观数据失败: {e}")

    def fetch_index_data(self, index_code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取指数数据

        Args:
            index_code: 指数代码 (000001.SH为上证指数, 399001.SZ为深证成指)
            start_date: 起始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            指数数据DataFrame
        """
        try:
            if not self._check_connection():
                return pd.DataFrame()

            today = datetime.now().strftime('%Y%m%d')
            start_date = start_date or (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')
            end_date = end_date or today

            # 获取指数数据 - 请求前限流
            tushare_limiter.wait(min_interval=1.0, max_interval=2.0)
            data = self.pro.index_daily(ts_code=index_code, start_date=start_date, end_date=end_date)

            if not data.empty:
                # 数据清洗
                data.rename(columns={
                    'trade_date': 'date',
                    'open': 'open',
                    'close': 'close',
                    'high': 'high',
                    'low': 'low',
                    'vol': 'volume',
                    'amount': 'amount',
                    'pct_chg': 'change_pct'
                }, inplace=True)

                # 计算技术指标
                data = self._calculate_index_technical(data)

                # 获取指数名称
                index_names = {
                    '000001.SH': '上证指数',
                    '399001.SZ': '深证成指',
                    '399006.SZ': '创业板指',
                    '000300.SH': '沪深300',
                    '000905.SH': '中证500'
                }
                index_name = index_names.get(index_code, index_code)

                data['index_code'] = index_code
                data['index_name'] = index_name

                # 保存到数据库
                self._save_index_to_db(data)

                logger.info(f"成功获取Tushare指数数据: {index_name}, 记录数: {len(data)}")

            return data

        except Exception as e:
            logger.error(f"获取Tushare指数数据失败 {index_code}: {e}")
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
            if not self._check_connection():
                return pd.DataFrame()

            # 获取股票列表 - 请求前限流
            tushare_limiter.wait(min_interval=1.0, max_interval=2.0)
            data = self.pro.stock_basic(exchange='', list_status='L')

            if not data.empty:
                # 数据清洗
                data.rename(columns={
                    'ts_code': 'ts_code',
                    'symbol': 'symbol',
                    'name': 'name',
                    'industry': 'industry',
                    'list_date': 'list_date'
                }, inplace=True)

                # 过滤掉ST股票
                data['is_st'] = data['name'].apply(
                    lambda x: 1 if isinstance(x, str) and ('ST' in x or '退' in x) else 0
                )

                # 保存到数据库
                self._save_stock_basic_to_db(data)

                logger.info(f"成功获取Tushare股票基本信息, 记录数: {len(data)}")

            return data

        except Exception as e:
            logger.error(f"获取Tushare股票基本信息失败: {e}")
            return pd.DataFrame()

    def _save_stock_basic_to_db(self, data: pd.DataFrame):
        """保存股票基本信息到数据库"""
        for _, row in data.iterrows():
            try:
                record = {
                    'ts_code': str(row.get('ts_code', '')),
                    'symbol': str(row.get('symbol', '')),
                    'name': str(row.get('name', '')),
                    'industry': str(row.get('industry', '')),
                    'list_date': str(row.get('list_date', '')),
                    'is_st': int(row.get('is_st', 0))
                }
                # 使用ON CONFLICT更新
                self.db.execute_query(
                    """
                    INSERT INTO stock_basic (ts_code, symbol, name, industry, list_date, is_st)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ts_code) DO UPDATE SET
                        symbol = excluded.symbol,
                        name = excluded.name,
                        industry = excluded.industry,
                        list_date = excluded.list_date,
                        is_st = excluded.is_st,
                        update_date = CURRENT_TIMESTAMP
                    """,
                    (record['ts_code'], record['symbol'], record['name'],
                     record['industry'], record['list_date'], record['is_st']),
                    commit=True
                )
            except Exception as e:
                logger.debug(f"保存股票基本信息失败: {e}")

    def fetch_stock_financial(self, ts_code: str, start_date: str = None) -> pd.DataFrame:
        """
        获取股票财务数据

        Args:
            ts_code: 股票代码
            start_date: 起始日期 (YYYYMMDD)

        Returns:
            财务数据DataFrame
        """
        try:
            if not self._check_connection():
                return pd.DataFrame()

            today = datetime.now().strftime('%Y%m%d')
            start_date = start_date or (datetime.now() - timedelta(days=365*3)).strftime('%Y%m%d')

            # 获取财务指标 - 请求前限流
            tushare_limiter.wait(min_interval=1.5, max_interval=3.0)
            data = self.pro.fina_indicator(ts_code=ts_code, start_date=start_date, end_date=today)

            if not data.empty:
                # 数据清洗和重命名
                data.rename(columns={
                    'end_date': 'end_date',
                    'roe': 'roe',
                    'roa': 'roa',
                    'gross_profit_margin': 'gross_margin',
                    'net_profit_margin': 'net_margin',
                    'or_yoy': 'revenue_yoy',
                    'profit_yoy': 'net_profit_yoy',
                    'debt_to_assets': 'debt_ratio',
                    'eps': 'eps',
                    'bps': 'bps'
                }, inplace=True)

                # 转换数据类型
                numeric_cols = ['roe', 'roa', 'gross_margin', 'net_margin',
                               'revenue_yoy', 'net_profit_yoy', 'debt_ratio', 'eps', 'bps']
                for col in numeric_cols:
                    if col in data.columns:
                        data[col] = pd.to_numeric(data[col], errors='coerce')

                # 保存到数据库
                self._save_financial_to_db(data, ts_code)

                logger.debug(f"成功获取Tushare股票财务数据: {ts_code}, 记录数: {len(data)}")

            return data

        except Exception as e:
            logger.error(f"获取Tushare股票财务数据失败 {ts_code}: {e}")
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
            start_date: 起始日期 (YYYYMMDD)

        Returns:
            估值数据DataFrame
        """
        try:
            if not self._check_connection():
                return pd.DataFrame()

            today = datetime.now().strftime('%Y%m%d')
            start_date = start_date or (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')

            # 获取每日行情数据 - 请求前限流
            tushare_limiter.wait(min_interval=1.0, max_interval=2.0)
            data = self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=today)

            if not data.empty:
                # 数据清洗
                data.rename(columns={
                    'trade_date': 'date',
                    'open': 'open',
                    'close': 'close',
                    'high': 'high',
                    'low': 'low',
                    'vol': 'volume',
                    'amount': 'amount',
                    'pct_chg': 'change_pct'
                }, inplace=True)

                # 内部限流：两个 API 调用之间
                tushare_limiter.wait(min_interval=0.5, max_interval=1.5, jitter=False)

                # 获取估值指标
                daily_basic = self.pro.daily_basic(ts_code=ts_code,
                                                   start_date=start_date,
                                                   end_date=today,
                                                   fields='trade_date,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,total_mv,circ_mv')

                if not daily_basic.empty:
                    # 合并估值数据
                    data = pd.merge(data, daily_basic, on='trade_date', how='left')
                    data.rename(columns={
                        'trade_date': 'date'
                    }, inplace=True)

                # 保存到数据库
                self._save_valuation_to_db(data, ts_code)

                logger.debug(f"成功获取Tushare股票估值数据: {ts_code}, 记录数: {len(data)}")

            return data

        except Exception as e:
            logger.error(f"获取Tushare股票估值数据失败 {ts_code}: {e}")
            return pd.DataFrame()

    def _save_valuation_to_db(self, data: pd.DataFrame, ts_code: str):
        """保存估值数据到数据库"""
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
                    'pe': float(row['pe']) if 'pe' in row and pd.notna(row.get('pe')) else None,
                    'pe_ttm': float(row['pe_ttm']) if 'pe_ttm' in row and pd.notna(row.get('pe_ttm')) else None,
                    'pb': float(row['pb']) if 'pb' in row and pd.notna(row.get('pb')) else None,
                    'ps': float(row['ps']) if 'ps' in row and pd.notna(row.get('ps')) else None,
                    'ps_ttm': float(row['ps_ttm']) if 'ps_ttm' in row and pd.notna(row.get('ps_ttm')) else None,
                    'dv_ratio': float(row['dv_ratio']) if 'dv_ratio' in row and pd.notna(row.get('dv_ratio')) else None,
                    'dv_ttm': float(row['dv_ttm']) if 'dv_ttm' in row and pd.notna(row.get('dv_ttm')) else None,
                    'total_mv': float(row['total_mv']) if 'total_mv' in row and pd.notna(row.get('total_mv')) else None,
                    'circ_mv': float(row['circ_mv']) if 'circ_mv' in row and pd.notna(row.get('circ_mv')) else None,
                }
                self.db.insert_data('valuation_data', record)
            except Exception as e:
                logger.debug(f"保存估值数据失败: {e}")

    def fetch_realtime_market(self, index_code: str = '000001.SH') -> Dict[str, Any]:
        """
        获取实时市场数据

        Args:
            index_code: 指数代码

        Returns:
            实时市场数据字典
        """
        try:
            if not self._check_connection():
                return {}

            # 获取最新指数数据 - 请求前限流
            tushare_limiter.wait(min_interval=1.0, max_interval=2.0)
            today = datetime.now().strftime('%Y%m%d')
            data = self.pro.index_daily(ts_code=index_code,
                                        start_date=today,
                                        end_date=today)

            if not data.empty:
                row = data.iloc[0]
                return {
                    'code': index_code,
                    'current': float(row['close']),
                    'change': float(row['close']) - float(row['pre_close']),
                    'change_pct': float(row['pct_chg']),
                    'volume': float(row['vol']),
                    'amount': float(row['amount']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'open': float(row['open'])
                }

        except Exception as e:
            logger.error(f"获取Tushare实时市场数据失败: {e}")

        return {}

# 全局Tushare数据获取实例
tushare_fetcher = TushareDataFetcher()