"""
tushare_data_manager.py - 基于Tushare的数据源管理器
使用Tushare API提供高质量的股票、宏观经济、市场情绪数据
"""

import logging
import tushare as ts
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import os

logger = logging.getLogger(__name__)

class TushareDataManager:
    """基于Tushare的数据源管理器"""
    
    def __init__(self, db_path: str = "database/stock_analysis.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # 初始化Tushare
        token = os.getenv('TUSHARE_TOKEN')
        if token:
            ts.set_token(token)
            self.pro = ts.pro_api()
            logger.info("Tushare API初始化成功")
        else:
            logger.error("未找到Tushare Token")
            raise ValueError("请设置环境变量 TUSHARE_TOKEN")
        
        # 数据缓存
        self.data_cache = {}
        
    def get_macro_data(self) -> Dict[str, Any]:
        """获取宏观经济数据"""
        try:
            cache_key = 'macro_data'
            if cache_key in self.data_cache:
                return self.data_cache[cache_key]
            
            macro_data = {}
            
            # 获取PMI数据
            try:
                pmi_data = self.pmi()
                if not pmi_data.empty:
                    latest = pmi_data.iloc[-1]
                    macro_data['pmi'] = {
                        'value': latest['pmi'],
                        'trend': 'expansion' if latest['pmi'] > 50 else 'contraction',
                        'date': latest['month']
                    }
                    logger.info(f"PMI数据获取成功: {latest['pmi']}")
            except Exception as e:
                logger.warning(f"PMI数据获取失败: {e}")
            
            # 获取CPI数据
            try:
                cpi_data = self.cpi()
                if not cpi_data.empty:
                    latest = cpi_data.iloc[-1]
                    macro_data['cpi'] = {
                        'value': latest['cpi'],
                        'growth': latest['cpi_yoy'],
                        'date': latest['month']
                    }
                    logger.info(f"CPI数据获取成功: {latest['cpi']}")
            except Exception as e:
                logger.warning(f"CPI数据获取失败: {e}")
            
            # 获取PPI数据
            try:
                ppi_data = self.ppi()
                if not ppi_data.empty:
                    latest = ppi_data.iloc[-1]
                    macro_data['ppi'] = {
                        'value': latest['ppi'],
                        'growth': latest['ppi_yoy'],
                        'date': latest['month']
                    }
                    logger.info(f"PPI数据获取成功: {latest['ppi']}")
            except Exception as e:
                logger.warning(f"PPI数据获取失败: {e}")
            
            # 获取GDP数据
            try:
                gdp_data = self.gdp()
                if not gdp_data.empty:
                    latest = gdp_data.iloc[-1]
                    macro_data['gdp'] = {
                        'value': latest['gdp'],
                        'growth': latest['gdp_yoy'],
                        'date': f"{latest['year']}年第{latest['quarter']}季度"
                    }
                    logger.info(f"GDP数据获取成功: {latest['gdp']}")
            except Exception as e:
                logger.warning(f"GDP数据获取失败: {e}")
            
            self.data_cache[cache_key] = macro_data
            return macro_data
            
        except Exception as e:
            logger.error(f"获取宏观数据失败: {e}")
            return {}
    
    def get_market_indices(self) -> Dict[str, Dict[str, Any]]:
        """获取主要指数数据"""
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
                    df = self.pro.index_daily(ts_code=code, start_date='20240601', end_date='20240618')
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
            return 'unknown'
    
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
            
            df = self.pro.stock_basic(exchange='', list_status='L')
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
                # 获取融资融券详情
                df = self.pro.margin_detail(trade_date=datetime.now().strftime('%Y%m%d'))
                if not df.empty:
                    # 计算市场情绪
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
            df = self.pro.daily(ts_code=ts_code, start_date='20240101', end_date=datetime.now().strftime('%Y%m%d'))
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
            
            df = self.pro.fina_indicator(ts_code=ts_code)
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
            
            df = self.pro.dailybasic(ts_code=ts_code, start_date='20240101', end_date=datetime.now().strftime('%Y%m%d'))
            if not df.empty:
                latest = df.iloc[-1].to_dict()
                self.data_cache[cache_key] = latest
                return latest
            else:
                return None
                
        except Exception as e:
            logger.warning(f"获取估值数据失败 {ts_code}: {e}")
            return None
    
    def get_money_flow(self, trade_date: str = None) -> pd.DataFrame:
        """获取资金流向数据"""
        try:
            if trade_date is None:
                trade_date = datetime.now().strftime('%Y%m%d')
            
            df = self.pro.moneyflow(trade_date=trade_date)
            if not df.empty:
                return df
            else:
                return pd.DataFrame()
                
        except Exception as e:
            logger.warning(f"获取资金流向数据失败: {e}")
            return pd.DataFrame()
    
    def get_industry_data(self) -> pd.DataFrame:
        """获取行业数据"""
        try:
            cache_key = 'industry_data'
            if cache_key in self.data_cache:
                return self.data_cache[cache_key]
            
            df = self.pro.concept()
            if not df.empty:
                self.data_cache[cache_key] = df
                return df
            else:
                return pd.DataFrame()
                
        except Exception as e:
            logger.warning(f"获取行业数据失败: {e}")
            return pd.DataFrame()
    
    def pmi(self) -> pd.DataFrame:
        """获取PMI数据"""
        try:
            year = datetime.now().year
            df = self.pro.pmi(year=year)
            return df
        except Exception as e:
            logger.warning(f"获取PMI数据失败: {e}")
            return pd.DataFrame()
    
    def cpi(self) -> pd.DataFrame:
        """获取CPI数据"""
        try:
            year = datetime.now().year
            df = self.pro.cpi(year=year)
            return df
        except Exception as e:
            logger.warning(f"获取CPI数据失败: {e}")
            return pd.DataFrame()
    
    def ppi(self) -> pd.DataFrame:
        """获取PPI数据"""
        try:
            year = datetime.now().year
            df = self.pro.ppi(year=year)
            return df
        except Exception as e:
            logger.warning(f"获取PPI数据失败: {e}")
            return pd.DataFrame()
    
    def gdp(self) -> pd.DataFrame:
        """获取GDP数据"""
        try:
            year = datetime.now().year
            df = self.pro.gdp(year=year)
            return df
        except Exception as e:
            logger.warning(f"获取GDP数据失败: {e}")
            return pd.DataFrame()
    
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
        manager = TushareDataManager()
        
        print("=== Tushare数据源管理器测试 ===")
        
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