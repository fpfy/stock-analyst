"""
data_source_manager.py - 数据源管理器
集成多个实际可用的数据源，提供稳定的股票、宏观经济、市场情绪数据
"""

import logging
import akshare as ak
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class DataSourceManager:
    """数据源管理器"""
    
    def __init__(self, db_path: str = "database/stock_analysis.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # 数据源状态
        self.source_status = {
            'akshare': True,
            'requests': True,
            'local_db': True
        }
        
        # 测试连接
        self._test_connections()
        
        # 缓存数据
        self.data_cache = {}
        self.cache_timeout = 3600  # 1小时缓存
        
    def _test_connections(self):
        """测试各数据源连接"""
        try:
            # 测试akshare
            pmi_data = ak.macro_china_pmi()
            if not pmi_data.empty:
                self.source_status['akshare'] = True
                logger.info("akshare连接成功")
            else:
                self.source_status['akshare'] = False
        except Exception as e:
            self.source_status['akshare'] = False
            logger.warning(f"akshare连接失败: {e}")
        
        # 测试requests
        try:
            response = requests.get('http://www.sina.com.cn', timeout=5)
            self.source_status['requests'] = True
            logger.info("requests连接成功")
        except Exception as e:
            self.source_status['requests'] = False
            logger.warning(f"requests连接失败: {e}")
    
    def get_macro_data(self) -> Dict:
        """获取宏观经济数据"""
        cache_key = 'macro_data'
        current_time = datetime.now().timestamp()
        
        # 检查缓存
        if cache_key in self.data_cache:
            cached_data, cached_time = self.data_cache[cache_key]
            if current_time - cached_time < self.cache_timeout:
                return cached_data
        
        try:
            data = {}
            
            # PMI数据
            if self.source_status['akshare']:
                try:
                    pmi = ak.macro_china_pmi()
                    if not pmi.empty:
                        data['pmi'] = {
                            'value': pmi.iloc[-1]['制造业-指数'] if len(pmi) > 0 else None,
                            'trend': self._calculate_pmi_trend(pmi['制造业-指数']),
                            'date': pmi.iloc[-1]['月份'] if len(pmi) > 0 else None
                        }
                except Exception as e:
                    logger.warning(f"获取PMI数据失败: {e}")
            
            # CPI数据
            if self.source_status['akshare']:
                try:
                    cpi = ak.macro_china_cpi()
                    if not cpi.empty:
                        data['cpi'] = {
                            'value': cpi.iloc[-1]['全国-当月'] if len(cpi) > 0 else None,
                            'growth': cpi.iloc[-1]['全国-同比增长'] if len(cpi) > 0 else None,
                            'date': cpi.iloc[-1]['月份'] if len(cpi) > 0 else None
                        }
                except Exception as e:
                    logger.warning(f"获取CPI数据失败: {e}")
            
            # PPI数据
            if self.source_status['akshare']:
                try:
                    ppi = ak.macro_china_ppi()
                    if not ppi.empty:
                        data['ppi'] = {
                            'value': ppi.iloc[-1]['当月'] if len(ppi) > 0 else None,
                            'growth': ppi.iloc[-1]['当月同比增长'] if len(ppi) > 0 else None,
                            'date': ppi.iloc[-1]['月份'] if len(ppi) > 0 else None
                        }
                except Exception as e:
                    logger.warning(f"获取PPI数据失败: {e}")
            
            # GDP数据
            if self.source_status['akshare']:
                try:
                    gdp = ak.macro_china_gdp()
                    if not gdp.empty:
                        latest = gdp.iloc[-1]
                        data['gdp'] = {
                            'value': latest['国内生产总值-绝对值'] if not pd.isna(latest['国内生产总值-绝对值']) else None,
                            'growth': latest['国内生产总值-同比增长'] if not pd.isna(latest['国内生产总值-同比增长']) else None,
                            'date': latest['季度'] if len(gdp) > 0 else None
                        }
                except Exception as e:
                    logger.warning(f"获取GDP数据失败: {e}")
            
            # 缓存数据
            self.data_cache[cache_key] = (data, current_time)
            
            return data
            
        except Exception as e:
            logger.error(f"获取宏观数据失败: {e}")
            return {}
    
    def get_market_indices(self) -> Dict:
        """获取主要指数数据"""
        cache_key = 'market_indices'
        current_time = datetime.now().timestamp()
        
        # 检查缓存
        if cache_key in self.data_cache:
            cached_data, cached_time = self.data_cache[cache_key]
            if current_time - cached_time < self.cache_timeout:
                return cached_data
        
        try:
            indices = {}
            
            # 主要指数列表
            index_list = [
                ('sh000001', '上证指数'),
                ('sz399001', '深证成指'),
                ('sz399006', '创业板指'),
                ('sh000300', '沪深300'),
                ('sz399905', '中证500')
            ]
            
            if self.source_status['akshare']:
                for code, name in index_list:
                    try:
                        index_data = ak.stock_zh_index_daily(symbol=code)
                        if not index_data.empty:
                            latest = index_data.iloc[-1]
                            indices[code] = {
                                'name': name,
                                'close': latest['close'] if not pd.isna(latest['close']) else None,
                                'change': latest['close'] - latest['open'] if not pd.isna(latest['close']) and not pd.isna(latest['open']) else None,
                                'change_pct': ((latest['close'] - latest['open']) / latest['open'] * 100) if not pd.isna(latest['close']) and not pd.isna(latest['open']) else None,
                                'volume': latest['volume'] if not pd.isna(latest['volume']) else None,
                                'trend': self._calculate_price_trend(index_data['close']),
                                'date': latest['date'] if len(index_data) > 0 else None
                            }
                    except Exception as e:
                        logger.warning(f"获取{code}数据失败: {e}")
                        continue
            
            # 缓存数据
            self.data_cache[cache_key] = (indices, current_time)
            
            return indices
            
        except Exception as e:
            logger.error(f"获取指数数据失败: {e}")
            return {}
    
    def get_stocks_list(self) -> pd.DataFrame:
        """获取股票列表"""
        cache_key = 'stocks_list'
        current_time = datetime.now().timestamp()
        
        # 检查缓存
        if cache_key in self.data_cache:
            cached_data, cached_time = self.data_cache[cache_key]
            if current_time - cached_time < self.cache_timeout:
                return cached_data
        
        try:
            if self.source_status['akshare']:
                stocks = ak.stock_info_a_code_name()
                if not stocks.empty:
                    # 缓存数据
                    self.data_cache[cache_key] = (stocks, current_time)
                    return stocks
            
            # 从数据库获取
            try:
                query = "SELECT ts_code, name FROM stock_list"
                self.cursor.execute(query)
                rows = self.cursor.fetchall()
                if rows:
                    stocks = pd.DataFrame(rows, columns=['ts_code', 'name'])
                    self.data_cache[cache_key] = (stocks, current_time)
                    return stocks
            except Exception as e:
                logger.warning(f"从数据库获取股票列表失败: {e}")
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return pd.DataFrame()
    
    def get_stock_data(self, ts_code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """获取个股数据"""
        cache_key = f'stock_data_{ts_code}'
        current_time = datetime.now().timestamp()
        
        # 检查缓存
        if cache_key in self.data_cache:
            cached_data, cached_time = self.data_cache[cache_key]
            if current_time - cached_time < self.cache_timeout:
                return cached_data
        
        try:
            if self.source_status['akshare']:
                try:
                    # 获取个股历史数据
                    hist_data = ak.stock_zh_a_hist(symbol=ts_code, period="daily", 
                                                  start_date=start_date or "20240101", 
                                                  end_date=end_date or datetime.now().strftime('%Y%m%d'),
                                                  adjust="qfq")
                    if not hist_data.empty:
                        # 缓存数据
                        self.data_cache[cache_key] = (hist_data, current_time)
                        return hist_data
                except Exception as e:
                    logger.warning(f"获取{ts_code}历史数据失败: {e}")
            
            # 从数据库获取
            try:
                if start_date and end_date:
                    query = """
                        SELECT * FROM daily_quotes 
                        WHERE ts_code = ? AND trade_date BETWEEN ? AND ?
                        ORDER BY trade_date
                    """
                    self.cursor.execute(query, (ts_code, start_date, end_date))
                else:
                    query = """
                        SELECT * FROM daily_quotes 
                        WHERE ts_code = ?
                        ORDER BY trade_date DESC
                        LIMIT 100
                    """
                    self.cursor.execute(query, (ts_code,))
                
                rows = self.cursor.fetchall()
                if rows:
                    columns = [desc[0] for desc in self.cursor.description]
                    hist_data = pd.DataFrame(rows, columns=columns)
                    self.data_cache[cache_key] = (hist_data, current_time)
                    return hist_data
            except Exception as e:
                logger.warning(f"从数据库获取{ts_code}数据失败: {e}")
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"获取个股数据失败: {e}")
            return pd.DataFrame()
    
    def get_industry_data(self) -> pd.DataFrame:
        """获取行业板块数据"""
        cache_key = 'industry_data'
        current_time = datetime.now().timestamp()
        
        # 检查缓存
        if cache_key in self.data_cache:
            cached_data, cached_time = self.data_cache[cache_key]
            if current_time - cached_time < self.cache_timeout:
                return cached_data
        
        try:
            if self.source_status['akshare']:
                try:
                    # 获取行业板块数据
                    industry_data = ak.stock_board_industry_name_em()
                    if not industry_data.empty:
                        # 缓存数据
                        self.data_cache[cache_key] = (industry_data, current_time)
                        return industry_data
                except Exception as e:
                    logger.warning(f"获取行业板块数据失败: {e}")
            
            # 从数据库获取
            try:
                query = "SELECT * FROM industry_data ORDER BY industry_name"
                self.cursor.execute(query)
                rows = self.cursor.fetchall()
                if rows:
                    columns = [desc[0] for desc in self.cursor.description]
                    industry_data = pd.DataFrame(rows, columns=columns)
                    self.data_cache[cache_key] = (industry_data, current_time)
                    return industry_data
            except Exception as e:
                logger.warning(f"从数据库获取行业数据失败: {e}")
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"获取行业数据失败: {e}")
            return pd.DataFrame()
    
    def get_margin_data(self) -> Dict:
        """获取融资融券数据"""
        cache_key = 'margin_data'
        current_time = datetime.now().timestamp()
        
        # 检查缓存
        if cache_key in self.data_cache:
            cached_data, cached_time = self.data_cache[cache_key]
            if current_time - cached_time < self.cache_timeout:
                return cached_data
        
        try:
            margin_data = {}
            
            if self.source_status['requests']:
                try:
                    # 从新浪财经获取融资融券数据
                    url = 'http://vip.stock.finance.sina.com.cn/q/go.php/vInvestCenter/rank/data.phtml?type=margin'
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Referer': 'http://finance.sina.com.cn/'
                    }
                    
                    response = requests.get(url, headers=headers, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('data'):
                            margin_data['sina'] = data['data']
                            
                            # 计算市场情绪指标
                            total_stocks = len(data['data'])
                            up_stocks = sum(1 for item in data['data'] if float(item.get('change_pct', 0)) > 0)
                            down_stocks = sum(1 for item in data['data'] if float(item.get('change_pct', 0)) < 0)
                            
                            margin_data['market_sentiment'] = {
                                'up_ratio': up_stocks / total_stocks if total_stocks > 0 else 0,
                                'down_ratio': down_stocks / total_stocks if total_stocks > 0 else 0,
                                'total_stocks': total_stocks
                            }
                except Exception as e:
                    logger.warning(f"获取新浪融资融券数据失败: {e}")
            
            # 从数据库获取
            try:
                query = """
                    SELECT ts_code, margin_balance, margin_short, margin_net 
                    FROM margin_data 
                    ORDER BY trade_date DESC 
                    LIMIT 100
                """
                self.cursor.execute(query)
                rows = self.cursor.fetchall()
                if rows:
                    columns = [desc[0] for desc in self.cursor.description]
                    margin_db = pd.DataFrame(rows, columns=columns)
                    margin_data['database'] = margin_db.to_dict('records')
            except Exception as e:
                logger.warning(f"从数据库获取融资融券数据失败: {e}")
            
            # 缓存数据
            self.data_cache[cache_key] = (margin_data, current_time)
            
            return margin_data
            
        except Exception as e:
            logger.error(f"获取融资融券数据失败: {e}")
            return {}
    
    def _calculate_pmi_trend(self, pmi_data: pd.Series) -> str:
        """计算PMI趋势"""
        if len(pmi_data) < 3:
            return 'unknown'
        
        recent = pmi_data.tail(3)
        if recent.iloc[-1] > 50:
            return 'expansion'
        elif recent.iloc[-1] < 50:
            return 'contraction'
        else:
            return 'stable'
    
    def _calculate_price_trend(self, price_data: pd.Series) -> str:
        """计算价格趋势"""
        if len(price_data) < 5:
            return 'unknown'
        
        recent = price_data.tail(5)
        current = recent.iloc[-1]
        avg_price = recent.mean()
        
        if current > avg_price * 1.02:
            return 'high'
        elif current < avg_price * 0.98:
            return 'low'
        else:
            return 'average'
    
    def get_market_state(self) -> str:
        """根据最新数据判断市场状态"""
        try:
            # 获取主要指数数据
            indices = self.get_market_indices()
            
            if not indices:
                return 'unknown'
            
            # 计算涨跌家数
            up_count = 0
            down_count = 0
            
            for code, data in indices.items():
                if data.get('change_pct'):
                    if data['change_pct'] > 0:
                        up_count += 1
                    elif data['change_pct'] < 0:
                        down_count += 1
            
            # 判断市场状态
            total = up_count + down_count
            if total == 0:
                return 'unknown'
            
            up_ratio = up_count / total
            
            if up_ratio > 0.7:
                return '强多'
            elif up_ratio > 0.6:
                return '偏多'
            elif up_ratio > 0.4:
                return '震荡'
            elif up_ratio > 0.3:
                return '偏空'
            else:
                return '弱空'
                
        except Exception as e:
            logger.error(f"判断市场状态失败: {e}")
            return 'unknown'
    
    def get_dynamic_position_allocation(self) -> Dict:
        """根据市场状态动态分配仓位"""
        try:
            market_state = self.get_market_state()
            
            allocations = {
                '强多': {'growth': 0.30, 'value': 0.25},
                '偏多': {'growth': 0.25, 'value': 0.20},
                '震荡': {'growth': 0.15, 'value': 0.20},
                '偏空': {'growth': 0.10, 'value': 0.25},
                '弱空': {'growth': 0.05, 'value': 0.30},
                'unknown': {'growth': 0.15, 'value': 0.20}
            }
            
            return allocations.get(market_state, allocations['unknown'])
            
        except Exception as e:
            logger.error(f"获取动态仓位分配失败: {e}")
            return {'growth': 0.15, 'value': 0.20}
    
    def clear_cache(self):
        """清除缓存"""
        self.data_cache.clear()
        logger.info("数据缓存已清除")
    
    def close(self):
        """关闭连接"""
        if hasattr(self, 'conn'):
            self.conn.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # 测试数据源管理器
    manager = DataSourceManager()
    
    try:
        print("=== 测试数据源管理器 ===")
        
        # 测试宏观数据
        print("\n1. 宏观经济数据:")
        macro_data = manager.get_macro_data()
        for key, value in macro_data.items():
            print(f"  {key}: {value}")
        
        # 测试指数数据
        print("\n2. 主要指数数据:")
        indices = manager.get_market_indices()
        for code, data in indices.items():
            print(f"  {code}: {data['name']} - 收盘: {data['close']} - 涨跌: {data['change_pct']:.2f}%")
        
        # 测试市场状态
        print("\n3. 市场状态:")
        market_state = manager.get_market_state()
        print(f"  当前市场状态: {market_state}")
        
        # 测试仓位分配
        print("\n4. 动态仓位分配:")
        allocation = manager.get_dynamic_position_allocation()
        print(f"  成长股: {allocation['growth']*100:.0f}%")
        print(f"  价值股: {allocation['value']*100:.0f}%")
        
        # 测试融资融券数据
        print("\n5. 融资融券数据:")
        margin_data = manager.get_margin_data()
        if margin_data.get('market_sentiment'):
            sentiment = margin_data['market_sentiment']
            print(f"  上涨家数比例: {sentiment['up_ratio']:.2f}")
            print(f"  下跌家数比例: {sentiment['down_ratio']:.2f}")
        
    except Exception as e:
        print(f"测试失败: {e}")
    finally:
        manager.close()