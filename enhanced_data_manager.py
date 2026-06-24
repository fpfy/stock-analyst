"""
enhanced_data_manager.py - 增强版数据源管理器
整合Tushare和akshare数据源，提供稳定的股票、宏观经济、市场情绪数据
"""

import logging
import tushare as ts
import akshare as ak
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import os

logger = logging.getLogger(__name__)

class EnhancedDataManager:
    """增强版数据源管理器 - 整合多个数据源"""
    
    def __init__(self, db_path: str = "database/stock_analysis.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # 初始化数据源
        self.tushare_pro = None
        self.tushare_available = False
        self.akshare_available = False
        
        # 检查并初始化Tushare
        token = os.getenv('TUSHARE_TOKEN')
        if token:
            try:
                ts.set_token(token)
                self.tushare_pro = ts.pro_api()
                # 测试Tushare连接
                test_df = self.tushare_pro.stock_basic(exchange='', list_status='L')
                if not test_df.empty:
                    self.tushare_available = True
                    logger.info("Tushare API初始化成功")
                else:
                    logger.warning("Tushare API测试失败")
            except Exception as e:
                logger.warning(f"Tushare API初始化失败: {e}")
        else:
            logger.warning("未找到Tushare Token")
        
        # 测试akshare连接
        try:
            # 测试akshare连接
            pmi_data = ak.macro_china_pmi()
            if not pmi_data.empty:
                self.akshare_available = True
                logger.info("akshare API初始化成功")
            else:
                logger.warning("akshare API测试失败")
        except Exception as e:
            logger.warning(f"akshare API初始化失败: {e}")
        
        # 数据缓存
        self.data_cache = {}
        
    def get_macro_data(self) -> Dict[str, Any]:
        """获取宏观经济数据 - 优先使用Tushare，备用akshare"""
        try:
            cache_key = 'macro_data'
            if cache_key in self.data_cache:
                return self.data_cache[cache_key]
            
            macro_data = {}
            
            # 获取PMI数据
            try:
                if self.tushare_available:
                    # Tushare PMI数据
                    # 尝试获取最新的PMI数据
                    df = self.tushare_pro.trade_cal(exchange='SSE', 
                                                   start_date=datetime.now().strftime('%Y%m%d'), 
                                                   end_date=datetime.now().strftime('%Y%m%d'))
                    if not df.empty:
                        # 使用akshare PMI数据作为补充
                        pmi_data = ak.macro_china_pmi()
                        if not pmi_data.empty:
                            latest = pmi_data.iloc[-1]
                            macro_data['pmi'] = {
                                'value': latest['制造业-指数'],
                                'trend': 'expansion' if latest['制造业-指数'] > 50 else 'contraction',
                                'date': latest['月份']
                            }
                            logger.info(f"PMI数据获取成功: {latest['制造业-指数']}")
                elif self.akshare_available:
                    # akshare PMI数据
                    pmi_data = ak.macro_china_pmi()
                    if not pmi_data.empty:
                        latest = pmi_data.iloc[-1]
                        macro_data['pmi'] = {
                            'value': latest['制造业-指数'],
                            'trend': 'expansion' if latest['制造业-指数'] > 50 else 'contraction',
                            'date': latest['月份']
                        }
                        logger.info(f"PMI数据获取成功: {latest['制造业-指数']}")
            except Exception as e:
                logger.warning(f"PMI数据获取失败: {e}")
            
            # 获取CPI数据
            try:
                if self.akshare_available:
                    cpi_data = ak.macro_china_cpi()
                    if not cpi_data.empty:
                        latest = cpi_data.iloc[-1]
                        macro_data['cpi'] = {
                            'value': latest['cpi'],
                            'growth': latest['cpi同比增长'],
                            'date': latest['月份']
                        }
                        logger.info(f"CPI数据获取成功: {latest['cpi']}")
            except Exception as e:
                logger.warning(f"CPI数据获取失败: {e}")
            
            # 获取PPI数据
            try:
                if self.akshare_available:
                    ppi_data = ak.macro_china_ppi()
                    if not ppi_data.empty:
                        latest = ppi_data.iloc[-1]
                        macro_data['ppi'] = {
                            'value': latest['ppi'],
                            'growth': latest['ppi同比增长'],
                            'date': latest['月份']
                        }
                        logger.info(f"PPI数据获取成功: {latest['ppi']}")
            except Exception as e:
                logger.warning(f"PPI数据获取失败: {e}")
            
            # 获取GDP数据
            try:
                if self.akshare_available:
                    gdp_data = ak.macro_china_gdp()
                    if not gdp_data.empty:
                        latest = gdp_data.iloc[-1]
                        macro_data['gdp'] = {
                            'value': latest['gdp'],
                            'growth': latest['gdp同比增长'],
                            'date': f"{latest['年份']}年第{latest['季度']}季度"
                        }
                        logger.info(f"GDP数据获取成功: {latest['gdp']}")
            except Exception as e:
                logger.warning(f"GDP数据获取失败: {e}")
            
            # 如果没有宏观数据，使用默认值
            if not macro_data:
                macro_data = {
                    'pmi': {'value': 50.0, 'trend': 'stable', 'date': '2024-06'},
                    'cpi': {'value': 102.0, 'growth': 2.0, 'date': '2024-06'},
                    'ppi': {'value': 100.0, 'growth': 0.0, 'date': '2024-06'},
                    'gdp': {'value': 60000.0, 'growth': 6.0, 'date': '2024年第1季度'}
                }
                logger.warning("使用默认宏观数据")
            
            self.data_cache[cache_key] = macro_data
            return macro_data
            
        except Exception as e:
            logger.error(f"获取宏观数据失败: {e}")
            return {}
    
    def get_market_indices(self) -> Dict[str, Dict[str, Any]]:
        """获取主要指数数据 - 优先使用Tushare"""
        try:
            cache_key = 'market_indices'
            if cache_key in self.data_cache:
                return self.data_cache[cache_key]
            
            indices = {}
            
            # 主要指数代码
            index_codes = [
                ('000001.SH', '上证指数'),
                ('399001.SZ', '深证成指'),
                ('399006.SZ', '创业板指'),
                ('000300.SH', '沪深300'),
                ('000905.SH', '中证500')
            ]
            
            for code, name in index_codes:
                try:
                    if self.tushare_available:
                        # Tushare指数数据
                        df = self.tushare_pro.index_daily(ts_code=code, start_date='20240601', end_date='20240618')
                        if not df.empty:
                            latest = df.iloc[-1]
                            indices[code] = {
                                'name': name,
                                'close': latest['close'],
                                'change_pct': latest['pct_chg'],
                                'volume': latest['vol'],
                                'amount': latest['amount']
                            }
                    elif self.akshare_available:
                        # akshare指数数据
                        df = ak.stock_zh_index_daily(symbol=code)
                        if not df.empty:
                            latest = df.iloc[-1]
                            indices[code] = {
                                'name': name,
                                'close': latest['close'],
                                'change_pct': latest['pct_chg'],
                                'volume': latest['vol'],
                                'amount': latest['amount']
                            }
                except Exception as e:
                    logger.warning(f"获取指数{code}数据失败: {e}")
            
            # 如果没有指数数据，使用默认值
            if not indices:
                indices = {
                    '000001.SH': {'name': '上证指数', 'close': 3100.0, 'change_pct': 0.0, 'volume': 0, 'amount': 0},
                    '399001.SZ': {'name': '深证成指', 'close': 9500.0, 'change_pct': 0.0, 'volume': 0, 'amount': 0},
                    '399006.SZ': {'name': '创业板指', 'close': 1800.0, 'change_pct': 0.0, 'volume': 0, 'amount': 0}
                }
                logger.warning("使用默认指数数据")
            
            self.data_cache[cache_key] = indices
            return indices
            
        except Exception as e:
            logger.error(f"获取指数数据失败: {e}")
            return {}
    
    def get_market_state(self) -> str:
        """获取市场状态"""
        try:
            cache_key = 'market_state'
            if cache_key in self.data_cache:
                return self.data_cache[cache_key]
            
            indices = self.get_market_indices()
            
            # 计算指数涨跌情况
            up_count = 0
            down_count = 0
            neutral_count = 0
            
            for code, data in indices.items():
                pct = data['change_pct']
                if pct > 1:
                    up_count += 1
                elif pct < -1:
                    down_count += 1
                else:
                    neutral_count += 1
            
            # 判断市场状态
            if up_count >= 3:
                market_state = '强多'
            elif up_count >= 2:
                market_state = '偏多'
            elif down_count >= 3:
                market_state = '弱空'
            elif down_count >= 2:
                market_state = '偏空'
            else:
                market_state = '震荡'
            
            self.data_cache[cache_key] = market_state
            return market_state
            
        except Exception as e:
            logger.error(f"获取市场状态失败: {e}")
            return '震荡'
    
    def get_dynamic_position_allocation(self) -> Dict[str, float]:
        """获取动态仓位分配"""
        try:
            cache_key = 'position_allocation'
            if cache_key in self.data_cache:
                return self.data_cache[cache_key]
            
            market_state = self.get_market_state()
            
            # 基于市场状态的仓位分配
            if market_state == '强多':
                allocation = {'growth': 0.4, 'value': 0.3}
            elif market_state == '偏多':
                allocation = {'growth': 0.35, 'value': 0.25}
            elif market_state == '震荡':
                allocation = {'growth': 0.3, 'value': 0.25}
            elif market_state == '偏空':
                allocation = {'growth': 0.2, 'value': 0.3}
            elif market_state == '弱空':
                allocation = {'growth': 0.1, 'value': 0.2}
            else:
                allocation = {'growth': 0.3, 'value': 0.25}
            
            # 确保总和不超过1
            total = sum(allocation.values())
            if total > 1:
                for key in allocation:
                    allocation[key] = allocation[key] / total
            
            self.data_cache[cache_key] = allocation
            return allocation
            
        except Exception as e:
            logger.error(f"获取仓位分配失败: {e}")
            return {'growth': 0.3, 'value': 0.25}
    
    def get_stocks_list(self) -> pd.DataFrame:
        """获取股票列表"""
        try:
            cache_key = 'stocks_list'
            if cache_key in self.data_cache:
                return self.data_cache[cache_key]
            
            if self.tushare_available:
                df = self.tushare_pro.stock_basic(exchange='', list_status='L')
            else:
                df = ak.stock_info_a_code_name()
            
            if not df.empty:
                self.data_cache[cache_key] = df
                return df
            else:
                raise ValueError("股票列表为空")
                
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return pd.DataFrame()
    
    def get_margin_data(self) -> Dict[str, Any]:
        """获取融资融券数据"""
        try:
            cache_key = 'margin_data'
            if cache_key in self.data_cache:
                return self.data_cache[cache_key]
            
            margin_data = {}
            
            try:
                if self.tushare_available:
                    # Tushare融资融券数据
                    df = self.tushare_pro.margin_detail(trade_date=datetime.now().strftime('%Y%m%d'))
                    if not df.empty:
                        total_margin = df['rzye'].sum()
                        total_rz = df['rzrqye'].sum()
                        
                        # 简单的情绪分析
                        if total_margin > 10000000000:  # 1000亿以上
                            sentiment = 'bullish'
                        elif total_margin > 5000000000:  # 500亿以上
                            sentiment = 'neutral'
                        else:
                            sentiment = 'bearish'
                        
                        margin_data['market_sentiment'] = {
                            'sentiment': sentiment,
                            'total_margin': total_margin,
                            'total_rz': total_rz,
                            'up_ratio': 0.6,  # 简化处理
                            'down_ratio': 0.4,
                            'total_stocks': len(df)
                        }
                        
                        logger.info(f"融资融券数据获取成功: {total_margin}亿元")
                elif self.akshare_available:
                    # akshare融资融券数据
                    try:
                        df = ak.stock_margin_flow_sina()
                        if not df.empty:
                            margin_data['market_sentiment'] = {
                                'sentiment': 'neutral',
                                'up_ratio': 0.5,
                                'down_ratio': 0.5,
                                'total_stocks': len(df)
                            }
                            logger.info("融资融券数据获取成功")
                    except Exception:
                        logger.warning("akshare融资融券数据获取失败")
                        margin_data['market_sentiment'] = {
                            'sentiment': 'neutral',
                            'up_ratio': 0.5,
                            'down_ratio': 0.5,
                            'total_stocks': 0
                        }
            except Exception as e:
                logger.warning(f"融资融券数据获取失败: {e}")
                margin_data['market_sentiment'] = {
                    'sentiment': 'neutral',
                    'up_ratio': 0.5,
                    'down_ratio': 0.5,
                    'total_stocks': 0
                }
            
            self.data_cache[cache_key] = margin_data
            return margin_data
            
        except Exception as e:
            logger.error(f"获取融资融券数据失败: {e}")
            return {'market_sentiment': {'sentiment': 'neutral', 'up_ratio': 0.5, 'down_ratio': 0.5, 'total_stocks': 0}}
    
    def get_stock_data(self, ts_code: str) -> pd.DataFrame:
        """获取个股数据"""
        try:
            cache_key = f'stock_data_{ts_code}'
            if cache_key in self.data_cache:
                return self.data_cache[cache_key]
            
            # 获取日线数据
            if self.tushare_available:
                df = self.tushare_pro.daily(ts_code=ts_code, start_date='20240101', end_date=datetime.now().strftime('%Y%m%d'))
            else:
                # akshare数据获取
                symbol = ts_code.replace('.SZ', '').replace('.SH', '')
                df = ak.stock_zh_a_hist(symbol=symbol, period='daily', start_date='20240101', end_date=datetime.now().strftime('%Y%m%d'))
            
            if not df.empty:
                # 计算技术指标
                df = self._calculate_technical_indicators(df)
                self.data_cache[cache_key] = df
                return df
            else:
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"获取个股数据失败 {ts_code}: {e}")
            return pd.DataFrame()
    
    def _calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        try:
            if len(df) < 20:
                return df
            
            # 确保数据格式正确
            if 'close' not in df.columns:
                return df
            
            # 移动平均线
            df['ma5'] = df['close'].rolling(5).mean()
            df['ma10'] = df['close'].rolling(10).mean()
            df['ma20'] = df['close'].rolling(20).mean()
            df['ma60'] = df['close'].rolling(60).mean()
            
            # MACD
            df['ema12'] = df['close'].ewm(span=12).mean()
            df['ema26'] = df['close'].ewm(span=26).mean()
            df['macd'] = df['ema12'] - df['ema26']
            df['macd_signal'] = df['macd'].ewm(span=9).mean()
            df['macd_hist'] = df['macd'] - df['macd_signal']
            
            # RSI
            df['rsi'] = self._calculate_rsi(df['close'])
            
            return df
            
        except Exception as e:
            logger.warning(f"计算技术指标失败: {e}")
            return df
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI指标"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi
        except Exception as e:
            logger.warning(f"计算RSI失败: {e}")
            return pd.Series([50] * len(prices))
    
    def get_financial_data(self, ts_code: str) -> Optional[Dict[str, Any]]:
        """获取财务数据"""
        try:
            cache_key = f'financial_data_{ts_code}'
            if cache_key in self.data_cache:
                return self.data_cache[cache_key]
            
            if self.tushare_available:
                df = self.tushare_pro.fina_indicator(ts_code=ts_code)
            else:
                # akshare财务数据获取
                symbol = ts_code.replace('.SZ', '').replace('.SH', '')
                df = ak.stock_financial_analysis(symbol=symbol)
            
            if not df.empty:
                latest = df.iloc[-1].to_dict()
                self.data_cache[cache_key] = latest
                return latest
            else:
                return None
                
        except Exception as e:
            logger.warning(f"获取财务数据失败 {ts_code}: {e}")
            return None
    
    def get_valuation_data(self, ts_code: str) -> Optional[Dict[str, Any]]:
        """获取估值数据"""
        try:
            cache_key = f'valuation_data_{ts_code}'
            if cache_key in self.data_cache:
                return self.data_cache[cache_key]
            
            if self.tushare_available:
                df = self.tushare_pro.dailybasic(ts_code=ts_code, start_date='20240101', end_date=datetime.now().strftime('%Y%m%d'))
            else:
                # akshare估值数据获取
                symbol = ts_code.replace('.SZ', '').replace('.SH', '')
                df = ak.stock_zh_a_daily(symbol=symbol)
            
            if not df.empty:
                latest = df.iloc[-1].to_dict()
                self.data_cache[cache_key] = latest
                return latest
            else:
                return None
                
        except Exception as e:
            logger.warning(f"获取估值数据失败 {ts_code}: {e}")
            return None
    
    def clear_cache(self):
        """清除缓存"""
        self.data_cache.clear()
        logger.info("数据缓存已清除")
    
    def close(self):
        """关闭连接"""
        try:
            self.conn.close()
            logger.info("数据库连接已关闭")
        except Exception as e:
            logger.warning(f"关闭数据库连接失败: {e}")


if __name__ == "__main__":
    # 测试模块
    logging.basicConfig(level=logging.INFO)
    
    try:
        manager = EnhancedDataManager()
        
        print("=== 增强版数据源管理器测试 ===")
        
        # 测试数据源状态
        print(f"Tushare可用: {manager.tushare_available}")
        print(f"akshare可用: {manager.akshare_available}")
        
        # 测试宏观数据
        macro_data = manager.get_macro_data()
        print(f"宏观数据: {macro_data}")
        
        # 测试指数数据
        indices = manager.get_market_indices()
        print(f"指数数据: {indices}")
        
        # 测试市场状态
        market_state = manager.get_market_state()
        print(f"市场状态: {market_state}")
        
        # 测试仓位分配
        allocation = manager.get_dynamic_position_allocation()
        print(f"仓位分配: {allocation}")
        
        # 测试股票列表
        stocks = manager.get_stocks_list()
        print(f"股票列表: {len(stocks)}只")
        
        # 测试融资融券数据
        margin_data = manager.get_margin_data()
        print(f"融资融券数据: {margin_data}")
        
        print("=== 测试完成 ===")
        
    except Exception as e:
        print(f"测试失败: {e}")
    finally:
        manager.close()