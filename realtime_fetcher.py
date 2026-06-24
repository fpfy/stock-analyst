"""
数据获取模块 - 支持Tushare和AkShare双数据源
从真实Tushare API获取全量A股数据
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import time
import requests
import database as db

# 统一限流器 + 安全包装
from rate_limiter import tushare_limiter
from safe_tushare import wrap_tushare_pro

logger = logging.getLogger(__name__)

class MultiDataFetcher:
    """多数据源获取器 - 使用Tushare Pro API"""

    def __init__(self):
        """初始化数据获取器"""
        self.db = db.db

        # 尝试导入Tushare
        self.tushare_available = False
        self.ts = None
        self.pro = None

        try:
            import tushare as ts
            token = __import__('os').environ.get('TUSHARE_TOKEN', '')
            if token:
                ts.set_token(token)
                raw_pro = ts.pro_api()
                # 包装为安全版本：自动限流 + 429 退避
                self.pro = wrap_tushare_pro(raw_pro)
                self.ts = ts
                self.tushare_available = True
                logger.info("Tushare数据源初始化成功")
            else:
                logger.warning("TUSHARE_TOKEN未设置，Tushare不可用")
        except Exception as e:
            logger.warning(f"Tushare导入失败: {e}")

        # 尝试导入AkShare作为备用
        self.akshare_available = False
        try:
            import akshare as ak
            self.ak = ak
            self.akshare_available = True
            logger.info("AkShare数据源就绪（备用）")
        except Exception:
            logger.info("AkShare不可用（备用数据源）")

    def fetch_macro_indicator(self, indicator_name: str, start_date: str = None) -> pd.DataFrame:
        """获取宏观经济指标数据"""
        if not self.tushare_available:
            logger.warning("Tushare不可用，无法获取宏观指标")
            return pd.DataFrame()

        try:
            today = datetime.now().strftime('%Y%m%d')
            start_date = start_date or (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')

            data = None
            if indicator_name == "PMI":
                # 请求前限流
                tushare_limiter.wait(min_interval=1.0, max_interval=2.0)
                data = self.pro.cn_pmi(start_m=start_date[:6], end_m=today[:6])
                if not data.empty:
                    data = data.rename(columns={'month': 'date', 'pmiYoy': 'value'})
                    data['date'] = data['date'].apply(lambda x: f"{x[:4]}-{x[4:]}-01")
                    data['indicator_name'] = 'PMI'
                    data['year'] = data['date'].str[:4]
                    data['month'] = data['date'].str[5:7]

            elif indicator_name == "CPI":
                # 请求前限流
                tushare_limiter.wait(min_interval=1.0, max_interval=2.0)
                data = self.pro.cn_cpi(start_m=start_date[:6], end_m=today[:6])
                if not data.empty:
                    data = data.rename(columns={'month': 'date', 'cpiYoy': 'value'})
                    data['date'] = data['date'].apply(lambda x: f"{x[:4]}-{x[4:]}-01")
                    data['indicator_name'] = 'CPI'
                    data['year'] = data['date'].str[:4]
                    data['month'] = data['date'].str[5:7]

            elif indicator_name == "PPI":
                # 请求前限流
                tushare_limiter.wait(min_interval=1.0, max_interval=2.0)
                data = self.pro.cn_ppi(start_m=start_date[:6], end_m=today[:6])
                if not data.empty:
                    data = data.rename(columns={'month': 'date', 'ppiYoy': 'value'})
                    data['date'] = data['date'].apply(lambda x: f"{x[:4]}-{x[4:]}-01")
                    data['indicator_name'] = 'PPI'
                    data['year'] = data['date'].str[:4]
                    data['month'] = data['date'].str[5:7]

            elif indicator_name == "M2_GROWTH":
                # 请求前限流
                tushare_limiter.wait(min_interval=1.0, max_interval=2.0)
                data = self.pro.cn_m(start_m=start_date[:6], end_m=today[:6])
                if not data.empty:
                    data = data.rename(columns={'month': 'date', 'm2Yoy': 'value'})
                    data['date'] = data['date'].apply(lambda x: f"{x[:4]}-{x[4:]}-01")
                    data['indicator_name'] = 'M2_GROWTH'
                    data['year'] = data['date'].str[:4]
                    data['month'] = data['date'].str[5:7]

            if data is not None and not data.empty:
                self._save_macro_to_db(data, indicator_name)
                logger.info(f"成功获取宏观指标: {indicator_name}, 记录数: {len(data)}")
                return data

        except Exception as e:
            logger.error(f"获取宏观指标失败 {indicator_name}: {e}")

        return pd.DataFrame()

    def _save_macro_to_db(self, data, indicator_name):
        """保存宏观经济数据到数据库"""
        for _, row in data.iterrows():
            try:
                record = {
                    'indicator_name': indicator_name,
                    'date': str(row.get('date', '')),
                    'value': float(row['value']) if pd.notna(row.get('value')) else None,
                    'year': str(row.get('year', '')),
                    'month': str(row.get('month', '')),
                    'source': 'Tushare'
                }
                self.db.insert_data('macro_indicators', record)
            except Exception:
                pass

    def fetch_index_data(self, index_code, start_date=None, end_date=None):
        """获取指数数据"""
        if not self.tushare_available:
            logger.warning("Tushare不可用")
            return pd.DataFrame()

        try:
            today = datetime.now().strftime('%Y%m%d')
            start_date = start_date or (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')
            end_date = end_date or today

            # Tushare格式: 000001.SH
            ts_index_code = index_code if '.' in index_code else f"{index_code}.SH"

            # 请求前限流
            tushare_limiter.wait(min_interval=1.0, max_interval=2.0)
            data = self.pro.index_daily(ts_code=ts_index_code, start_date=start_date, end_date=end_date)

            if data is not None and not data.empty:
                data = data.sort_values('trade_date')
                data = data.rename(columns={
                    'trade_date': 'date',
                    'pct_chg': 'change_pct',
                    'vol': 'volume'
                })

                # 计算技术指标
                for period in [5, 10, 20, 60]:
                    if len(data) >= period:
                        data[f'ma{period}'] = data['close'].rolling(window=period).mean()

                data['index_code'] = index_code
                index_names = {
                    '000001': '上证指数', '399001': '深证成指',
                    '399006': '创业板指', '000300': '沪深300',
                    '000001.SH': '上证指数', '399001.SZ': '深证成指'
                }
                data['index_name'] = index_names.get(index_code, index_code)

                self._save_index_to_db(data)
                logger.info(f"成功获取指数数据: {data.iloc[-1]['index_name']}, 记录数: {len(data)}")

                return data

        except Exception as e:
            logger.error(f"获取指数数据失败 {index_code}: {e}")

        return pd.DataFrame()

    def _save_index_to_db(self, data):
        """保存指数数据到数据库"""
        for _, row in data.iterrows():
            try:
                record = {
                    'index_code': str(row.get('index_code', '')),
                    'index_name': str(row.get('index_name', '')),
                    'date': str(row.get('date', '')),
                    'open': float(row.get('open', 0)) if pd.notna(row.get('open')) else None,
                    'high': float(row.get('high', 0)) if pd.notna(row.get('high')) else None,
                    'low': float(row.get('low', 0)) if pd.notna(row.get('low')) else None,
                    'close': float(row.get('close', 0)) if pd.notna(row.get('close')) else None,
                    'volume': float(row.get('volume', 0)) if pd.notna(row.get('volume')) else None,
                    'amount': float(row.get('amount', 0)) if pd.notna(row.get('amount')) else None,
                    'change_pct': float(row.get('change_pct', 0)) if pd.notna(row.get('change_pct')) else None,
                    'ma5': float(row.get('ma5')) if 'ma5' in row and pd.notna(row.get('ma5')) else None,
                    'ma10': float(row.get('ma10')) if 'ma10' in row and pd.notna(row.get('ma10')) else None,
                    'ma20': float(row.get('ma20')) if 'ma20' in row and pd.notna(row.get('ma20')) else None,
                    'ma60': float(row.get('ma60')) if 'ma60' in row and pd.notna(row.get('ma60')) else None,
                }
                self.db.insert_data('index_data', record)
            except Exception:
                pass

    def fetch_stock_basic(self):
        """获取A股股票基本信息（tushare 优先，iTick fallback）"""
        if self.tushare_available:
            try:
                # 请求前限流
                tushare_limiter.wait(min_interval=1.0, max_interval=2.0)
                data = self.pro.stock_basic(exchange='', list_status='L',
                                             fields='ts_code,symbol,name,area,industry,list_date')

                if data is not None and not data.empty:
                    data['is_st'] = data['name'].apply(lambda x: 1 if isinstance(x, str) and ('ST' in x or '退' in x) else 0)
                    self._save_stock_basic_to_db(data)
                    logger.info(f"成功获取股票基本信息, 记录数: {len(data)}")
                    return data

            except Exception as e:
                logger.error(f"Tushare 获取股票基本信息失败: {e}")

        # tushare 失败，尝试 iTick fallback
        logger.info("Tushare 不可用，回退 iTick stock/info ...")
        return self.fetch_stock_basic_itick()

    def _save_stock_basic_to_db(self, data):
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
                self.db.execute_query(
                    """INSERT INTO stock_basic (ts_code, symbol, name, industry, list_date, is_st)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(ts_code) DO UPDATE SET
                       name=excluded.name, industry=excluded.industry, is_st=excluded.is_st""",
                    (record['ts_code'], record['symbol'], record['name'],
                     record['industry'], record['list_date'], record['is_st']),
                    commit=True
                )
            except Exception:
                pass

    def fetch_stock_basic_itick(self, ts_codes: list = None) -> pd.DataFrame:
        """
        iTick fallback：获取A股股票基本信息
        - 免费限流：5 次/分钟
        - 若传入 ts_codes，只查询指定股票；否则拉全市场会极慢，不推荐
        """
        token = __import__('os').environ.get('ITICK_TOKEN', '') or 'e88f98fd87d842bcb0076ed3404ec82c5f50fcbbf6634766bd052fcd889f7b86'
        if not token:
            logger.warning("ITICK_TOKEN 未设置，iTick stock_basic fallback 不可用")
            return pd.DataFrame()

        url = 'https://api-free.itick.org/stock/info'
        headers = {'token': token, 'accept': 'application/json'}
        rows = []
        codes = ts_codes or []

        # 免费限流：5次/分钟 => 每次请求间隔 >= 12s
        interval = 12.0

        def _request(region: str, code: str):
            for attempt in range(3):
                try:
                    if attempt > 0:
                        time.sleep(interval)
                    params = {'type': 'stock', 'region': region, 'code': code}
                    r = requests.get(url, headers=headers, params=params, timeout=15)
                    if r.status_code == 200:
                        payload = r.json()
                        if payload.get('code') == 0 and payload.get('data'):
                            d = payload['data']
                            return {
                                'ts_code': f"{region}.{code}",
                                'symbol': code,
                                'name': d.get('n', ''),
                                'industry': d.get('s', ''),
                                'list_date': '',
                                'is_st': 1 if isinstance(d.get('n'), str) and ('ST' in d.get('n') or '退' in d.get('n')) else 0,
                            }
                        elif payload.get('code') == 1:
                            logger.warning(f"iTick stock/info 业务错误: {payload.get('msg')}")
                            return None
                except Exception as e:
                    logger.warning(f"iTick stock/info 请求失败 {region}{code}: {e}")
                    time.sleep(interval)
            return None

        if not codes:
            logger.warning("iTick stock_basic fallback 未传 ts_codes，为避免限流直接返回空")
            return pd.DataFrame()

        for code in codes:
            region = 'SH' if code.endswith('.SH') else 'SZ' if code.endswith('.SZ') else None
            if region is None:
                continue
            pure_code = code.split('.')[0]
            record = _request(region, pure_code)
            if record:
                rows.append(record)
            if len(rows) < len(codes):
                time.sleep(interval)

        if not rows:
            return pd.DataFrame()

        basic_df = pd.DataFrame(rows)
        self._save_stock_basic_to_db(basic_df)
        logger.info(f"iTick stock_basic fallback 成功: {len(basic_df)}/{len(codes)}")
        return basic_df

    def fetch_candidate_basic_and_financial(self, candidate_codes, chunk_size=200):
        """
        云端直连：为候选股票池批量获取 stock_basic + fina_indicator
        返回 DataFrame: ts_code, name, industry, list_date, is_st,
                        roe, revenue_yoy, net_profit_yoy, gross_margin, debt_ratio, eps, bps,
                        end_date, ann_date
        """
        if not self.tushare_available or not candidate_codes:
            return pd.DataFrame()

        try:
            # 1. 基础信息
            tushare_limiter.wait(min_interval=1.0, max_interval=2.0)
            basic_df = self.pro.stock_basic(exchange='', list_status='L',
                                            fields='ts_code,symbol,name,area,industry,list_date')
            if basic_df is None or basic_df.empty:
                return pd.DataFrame()
            basic_df['is_st'] = basic_df['name'].apply(
                lambda x: 1 if isinstance(x, str) and ('ST' in x or '退' in x) else 0
            )
            basic_df = basic_df[basic_df['ts_code'].isin(candidate_codes)].copy()

            # 2. fina_indicator：roe / revenue_yoy / net_profit_yoy / gross_margin / debt_ratio / eps / bps
            fina_fields = 'ts_code,ann_date,end_date,roe,or_yoy,netprofit_yoy,debt_to_assets,grossprofit_margin,basic_eps,bps'
            fina_chunks = []
            for i in range(0, len(candidate_codes), chunk_size):
                chunk = candidate_codes[i:i + chunk_size]
                try:
                    tushare_limiter.wait(min_interval=0.35, max_interval=0.5, jitter=True, max_per_minute=170)
                    df = self.pro.fina_indicator(ts_code=','.join(chunk), fields=fina_fields)
                    if df is not None and not df.empty:
                        fina_chunks.append(df)
                except Exception as e:
                    logger.warning(f'fina_indicator chunk {i} failed: {e}')
                    time.sleep(1)

            if not fina_chunks:
                return basic_df
            fina_df = pd.concat(fina_chunks, ignore_index=True)
            # 取每只股票最新一期
            fina_df['end_date_dt'] = pd.to_datetime(fina_df['end_date'], errors='coerce')
            fina_df = fina_df.sort_values('end_date_dt').drop_duplicates('ts_code', keep='last')
            fina_df = fina_df.rename(columns={
                'or_yoy': 'revenue_yoy',
                'netprofit_yoy': 'net_profit_yoy',
                'debt_to_assets': 'debt_ratio',
                'grossprofit_margin': 'gross_margin',
                'basic_eps': 'eps',
            })

            # 3. 合并
            merged = basic_df.merge(fina_df, on='ts_code', how='left')
            return merged

        except Exception as e:
            logger.error(f'fetch_candidate_basic_and_financial failed: {e}')
            return pd.DataFrame()

    def fetch_candidate_valuation(self, candidate_codes, trade_date=None, chunk_size=200):
        """
        云端直连：为候选股票池批量获取 daily_basic 估值数据
        返回 DataFrame: ts_code, close, pe, pb, dv_ttm, total_mv, trade_date
        """
        if not self.tushare_available or not candidate_codes:
            return pd.DataFrame()

        try:
            if trade_date is None:
                trade_date = datetime.now().strftime('%Y%m%d')

            val_chunks = []
            for i in range(0, len(candidate_codes), chunk_size):
                chunk = candidate_codes[i:i + chunk_size]
                try:
                    tushare_limiter.wait(min_interval=0.35, max_interval=0.5, jitter=True, max_per_minute=170)
                    df = self.pro.daily_basic(ts_code=','.join(chunk), trade_date=trade_date,
                                               fields='ts_code,close,pe,pb,dv_ttm,total_mv,trade_date')
                    if df is not None and not df.empty:
                        val_chunks.append(df)
                except Exception as e:
                    logger.warning(f'daily_basic chunk {i} failed: {e}')
                    time.sleep(1)

            if not val_chunks:
                return pd.DataFrame()
            return pd.concat(val_chunks, ignore_index=True)

        except Exception as e:
            logger.error(f'fetch_candidate_valuation failed: {e}')
            return pd.DataFrame()

    def fetch_stock_financial(self, ts_code, start_date=None):
        """获取股票财务数据"""
        if not self.tushare_available:
            return pd.DataFrame()

        try:
            today = datetime.now().strftime('%Y%m%d')
            start_date = start_date or (datetime.now() - timedelta(days=365*3)).strftime('%Y%m%d')

            # 请求前限流
            tushare_limiter.wait(min_interval=1.5, max_interval=3.0)
            data = self.pro.fina_indicator(ts_code=ts_code, start_date=start_date, end_date=today)

            if data is not None and not data.empty:
                data = data.rename(columns={
                    'end_date': 'end_date',
                    'ann_date': 'ann_date',
                    'roe_yearly': 'roe',  # 使用年度化ROE
                    'roa': 'roa',
                    'grossprofit_margin': 'gross_margin',
                    'netprofit_margin': 'net_margin',
                    'or_yoy': 'revenue_yoy',
                    'netprofit_yoy': 'net_profit_yoy',
                    'debt_to_assets': 'debt_ratio',
                    'eps': 'eps',
                    'bps': 'bps'
                })

                self._save_financial_to_db(data, ts_code)
                logger.debug(f"成功获取财务数据: {ts_code}, 记录数: {len(data)}")
                return data

        except Exception as e:
            logger.error(f"获取财务数据失败 {ts_code}: {e}")

        return pd.DataFrame()

    def _save_financial_to_db(self, data, ts_code):
        """保存财务数据到数据库"""
        for _, row in data.iterrows():
            try:
                record = {
                                            'ts_code': ts_code,
                                            'ann_date': str(row.get('ann_date', row.get('end_date', ''))),
                                            'end_date': str(row.get('end_date', '')),
                                            'roe': row.get('roe_yearly'),  # 使用年度化ROE
                                            'roa': row.get('roa'),
                                            'gross_margin': row.get('grossprofit_margin'),
                                            'net_margin': row.get('netprofit_margin'),
                                            'revenue_yoy': row.get('or_yoy'),
                                            'net_profit_yoy': row.get('netprofit_yoy'),
                                            'debt_ratio': row.get('debt_to_assets'),
                                            'eps': row.get('eps'),
                                            'bps': row.get('bps'),
                                        }
                self.db.insert_data('financial_data', record)
            except Exception:
                pass

    def fetch_stock_valuation(self, ts_code, start_date=None):
        """获取股票估值数据（含PE/PB等）"""
        if not self.tushare_available:
            return pd.DataFrame()

        try:
            today = datetime.now().strftime('%Y%m%d')
            start_date = start_date or (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')

            # 请求前限流
            tushare_limiter.wait(min_interval=1.0, max_interval=2.0)
            data = self.pro.daily_basic(ts_code=ts_code, start_date=start_date, end_date=today)

            if data is not None and not data.empty:
                data = data.rename(columns={
                    'trade_date': 'date',
                    'ts_code': 'ts_code',
                    'close': 'close',
                    'pe': 'pe',
                    'pe_ttm': 'pe_ttm',
                    'pb': 'pb',
                    'ps': 'ps',
                    'ps_ttm': 'ps_ttm',
                    'dv_ratio': 'dv_ratio',
                    'dv_ttm': 'dv_ttm',
                    'total_mv': 'total_mv',
                    'circ_mv': 'circ_mv'
                })

                self._save_valuation_to_db(data, ts_code)
                logger.debug(f"成功获取估值数据: {ts_code}, 记录数: {len(data)}")
                return data

        except Exception as e:
            logger.error(f"获取估值数据失败 {ts_code}: {e}")

        return pd.DataFrame()

    def _save_valuation_to_db(self, data, ts_code):
        """保存估值数据到数据库"""
        for _, row in data.iterrows():
            try:
                record = {
                    'ts_code': ts_code,
                    'trade_date': str(row.get('date', '')),
                    'close': float(row.get('close', 0)) if pd.notna(row.get('close')) else None,
                    'pe': float(row.get('pe')) if 'pe' in row and pd.notna(row.get('pe')) else None,
                    'pe_ttm': float(row.get('pe_ttm')) if 'pe_ttm' in row and pd.notna(row.get('pe_ttm')) else None,
                    'pb': float(row.get('pb')) if 'pb' in row and pd.notna(row.get('pb')) else None,
                    'ps': float(row.get('ps')) if 'ps' in row and pd.notna(row.get('ps')) else None,
                    'ps_ttm': float(row.get('ps_ttm')) if 'ps_ttm' in row and pd.notna(row.get('ps_ttm')) else None,
                    'dv_ratio': float(row.get('dv_ratio')) if 'dv_ratio' in row and pd.notna(row.get('dv_ratio')) else None,
                    'dv_ttm': float(row.get('dv_ttm')) if 'dv_ttm' in row and pd.notna(row.get('dv_ttm')) else None,
                    'total_mv': float(row.get('total_mv')) if 'total_mv' in row and pd.notna(row.get('total_mv')) else None,
                    'circ_mv': float(row.get('circ_mv')) if 'circ_mv' in row and pd.notna(row.get('circ_mv')) else None,
                }
                self.db.insert_data('valuation_data', record)
            except Exception:
                pass

    def fetch_realtime_market(self, index_code='000001.SH'):
        """获取实时市场数据"""
        if not self.tushare_available:
            return {}

        try:
            today = datetime.now().strftime('%Y%m%d')

            # 请求前限流
            tushare_limiter.wait(min_interval=1.0, max_interval=2.0)
            data = self.pro.index_daily(ts_code=index_code, start_date=today, end_date=today)

            if data is not None and not data.empty:
                row = data.iloc[-1]
                return {
                    'code': index_code,
                    'current': float(row['close']),
                    'change_pct': float(row['pct_chg']),
                    'volume': float(row['vol']),
                    'amount': float(row['amount']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'open': float(row['open'])
                }

        except Exception as e:
            logger.error(f"获取实时市场数据失败: {e}")

        return {}

    def fetch_bulk_financial(self, ts_codes, start_date=None, batch_size=20):
        """批量获取财务数据"""
        logger.info(f"开始批量获取 {len(ts_codes)} 只股票的财务数据...")
        count = 0
        for i, ts_code in enumerate(ts_codes):
            try:
                self.fetch_stock_financial(ts_code, start_date)
                count += 1
                if count % 10 == 0:
                    logger.info(f"  进度: {count}/{len(ts_codes)}")
                # 节流 - 使用统一限流器 (1-3秒随机间隔)
                tushare_limiter.wait(min_interval=1.0, max_interval=3.0)
            except Exception as e:
                logger.debug(f"批量获取 {ts_code} 失败: {e}")
        logger.info(f"批量获取财务数据完成: {count}/{len(ts_codes)}")

    def fetch_bulk_valuation(self, ts_codes, start_date=None, batch_size=20):
        """批量获取估值数据"""
        logger.info(f"开始批量获取 {len(ts_codes)} 只股票的估值数据...")
        count = 0
        for i, ts_code in enumerate(ts_codes):
            try:
                self.fetch_stock_valuation(ts_code, start_date)
                count += 1
                if count % 10 == 0:
                    logger.info(f"  进度: {count}/{len(ts_codes)}")
                # 节流 - 使用统一限流器 (1-3秒随机间隔)
                tushare_limiter.wait(min_interval=1.0, max_interval=3.0)
            except Exception as e:
                logger.debug(f"批量获取 {ts_code} 失败: {e}")
        logger.info(f"批量获取估值数据完成: {count}/{len(ts_codes)}")


# 全局数据获取实例
data_fetcher = MultiDataFetcher()