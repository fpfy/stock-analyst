"""
dual_strategy_selector.py - 双策略选股系统集成模块
整合成长股策略和低估值价值股策略，基于宏观分析动态分配仓位
"""

import logging
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import numpy as np

from macro_market_analyzer import MacroMarketAnalyzer
from data_source_manager import DataSourceManager
from stock_selector import GrowthStockSelector, ValueStockSelector

logger = logging.getLogger(__name__)

class DualStrategySelector:
    """双策略选股系统"""
    
    def __init__(self, db_path: str = "database/stock_analysis.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # 初始化数据源管理器
        self.data_manager = DataSourceManager(db_path)
        
        # 初始化宏观分析器
        self.macro_analyzer = MacroMarketAnalyzer(db_path)
        
        # 初始化策略
        self.growth_strategy = GrowthStockSelector()
        self.value_strategy = ValueStockSelector()
        
        # 选股结果
        self.growth_stocks = []
        self.value_stocks = []
        self.final_allocation = {}
        
        # 系统参数
        self.min_score_threshold = 70  # 最低入选分数
        self.max_stocks_per_strategy = 20  # 每个策略最多选股数量
        
    def run_dual_strategy_selection(self) -> Dict:
        """运行双策略选股"""
        try:
            logger.info("开始双策略选股...")
            
            # 1. 宏观分析
            self.macro_analyzer.fetch_all_macro_data()
            
            # 2. 获取动态仓位分配
            position_allocation = self.data_manager.get_dynamic_position_allocation()
            
            # 3. 执行成长股策略
            self.growth_stocks = self._execute_growth_strategy(position_allocation['growth'])
            
            # 4. 执行价值股策略
            self.value_stocks = self._execute_value_strategy(position_allocation['value'])
            
            # 5. 生成最终选股结果
            final_results = self._generate_final_results(position_allocation)
            
            # 6. 保存分析结果
            self._save_selection_results(final_results)
            
            logger.info("双策略选股完成")
            return final_results
            
        except Exception as e:
            logger.error(f"双策略选股失败: {e}")
            return {}
    
    def _execute_growth_strategy(self, allocation_ratio: float) -> List[Dict]:
        """执行成长股策略"""
        try:
            logger.info(f"执行成长股策略，仓位比例: {allocation_ratio:.2f}")
            
            # 获取市场状态
            market_state = self.data_manager.get_market_state()
            
            # 获取候选股票池
            candidate_stocks = self.growth_strategy.select_stocks(market_state, allocation_ratio)
            
            # 过滤和评分
            filtered_stocks = []
            for stock in candidate_stocks:
                if len(filtered_stocks) >= self.max_stocks_per_strategy:
                    break
                
                # 计算成长股评分
                score, reasons = self._calculate_growth_score(stock)
                if score >= self.min_score_threshold:
                    stock['growth_score'] = score
                    stock['reason'] = '、'.join(reasons) if reasons else '符合成长股标准'
                    stock['allocation_weight'] = allocation_ratio
                    filtered_stocks.append(stock)
            
            logger.info(f"成长股策略选出 {len(filtered_stocks)} 只股票")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"执行成长股策略失败: {e}")
            return []
    
    def _execute_value_strategy(self, allocation_ratio: float) -> List[Dict]:
        """执行价值股策略"""
        try:
            logger.info(f"执行价值股策略，仓位比例: {allocation_ratio:.2f}")
            
            # 获取市场状态
            market_state = self.data_manager.get_market_state()
            
            # 获取候选股票池
            candidate_stocks = self.value_strategy.select_stocks(market_state, allocation_ratio)
            
            # 过滤和评分
            filtered_stocks = []
            for stock in candidate_stocks:
                if len(filtered_stocks) >= self.max_stocks_per_strategy:
                    break
                
                # 计算价值股评分
                score = self._calculate_value_score(stock)
                if score >= self.min_score_threshold:
                    stock['value_score'] = score
                    stock['reason'] = '、'.join(reasons) if reasons else '符合价值股标准'
                    stock['allocation_weight'] = allocation_ratio
                    filtered_stocks.append(stock)
            
            logger.info(f"价值股策略选出 {len(filtered_stocks)} 只股票")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"执行价值股策略失败: {e}")
            return []
    
    def _calculate_growth_score(self, stock: Dict) -> Tuple[float, List[str]]:
        """计算成长股评分"""
        try:
            score = 0.0
            reasons = []
            
            # 获取个股数据
            stock_data = self.data_manager.get_stock_data(stock['ts_code'])
            if stock_data.empty:
                return 0.0, []
            
            # 基本面评分 (40%)
            if stock.get('roe_yearly'):
                roe_score = min(stock['roe_yearly'] * 10, 40)  # ROE评分，最高40分
                score += roe_score
                if roe_score > 0:
                    reasons.append(f"ROE={stock['roe_yearly']:.2f}%")
            
            if stock.get('netprofit_yoy'):
                profit_score = min(stock['netprofit_yoy'] * 2, 20)  # 净利润增长评分，最高20分
                score += profit_score
                if profit_score > 0:
                    reasons.append(f"净利增长={stock['netprofit_yoy']:.2f}%")
            
            if stock.get('revenue_yoy'):
                revenue_score = min(stock['revenue_yoy'] * 1.5, 20)  # 营收增长评分，最高20分
                score += revenue_score
                if revenue_score > 0:
                    reasons.append(f"营收增长={stock['revenue_yoy']:.2f}%")
            
            # 技术面评分 (30%)
            if not stock_data.empty:
                # 计算技术指标
                latest = stock_data.iloc[-1]
                
                # 相对强度
                if len(stock_data) >= 20:
                    ma20 = stock_data['close'].tail(20).mean()
                    if latest['close'] > ma20:
                        score += 15  # 站上20日均线
                        reasons.append("站上20日均线")
                
                # 成交量放大
                if len(stock_data) >= 5:
                    vol_ratio = latest['volume'] / stock_data['volume'].tail(5).mean()
                    if vol_ratio > 1.2:
                        score += 15  # 成交量放大
                        reasons.append("成交量放大")
            
            # 行业前景评分 (20%)
            if stock.get('industry_growth'):
                industry_score = min(stock['industry_growth'] * 5, 20)
                score += industry_score
                if industry_score > 0:
                    reasons.append(f"行业前景={stock['industry_growth']:.2f}")
            
            # 市场情绪评分 (10%)
            if stock.get('market_sentiment'):
                sentiment_score = stock['market_sentiment'] * 0.1
                score += sentiment_score
                if sentiment_score > 0:
                    reasons.append(f"市场情绪={stock['market_sentiment']:.2f}")
            
            return min(score, 100), reasons
            
        except Exception as e:
            logger.error(f"计算成长股评分失败: {e}")
            return 0.0, []
    
    def _calculate_value_score(self, stock: Dict) -> float:
        """计算价值股评分"""
        try:
            score = 0.0
            
            # 获取个股数据
            stock_data = self.data_manager.get_stock_data(stock['ts_code'])
            if stock_data.empty:
                return 0.0
            
            # 估值评分 (50%)
            if stock.get('pe_ttm'):
                pe = stock['pe_ttm']
                if pe < 15:
                    score += 25  # 低PE评分
                elif pe < 25:
                    score += 15  # 中等PE评分
                elif pe < 40:
                    score += 5   # 高PE评分
            
            if stock.get('pb_lf'):
                pb = stock['pb_lf']
                if pb < 1.5:
                    score += 25  # 低PB评分
                elif pb < 3:
                    score += 15  # 中等PB评分
                elif pb < 5:
                    score += 5   # 高PB评分
            
            # 基本面评分 (30%)
            if stock.get('roe_yearly'):
                score += min(stock['roe_yearly'] * 5, 30)  # ROE评分
            
            if stock.get('debt_to_assets'):
                debt_ratio = stock['debt_to_assets']
                if debt_ratio < 0.3:
                    score += 10  # 低负债评分
                elif debt_ratio < 0.6:
                    score += 5   # 中等负债评分
            
            # 股息率评分 (10%)
            if stock.get('dividend_yield'):
                dividend_yield = stock['dividend_yield']
                if dividend_yield > 0.04:
                    score += 10  # 高股息率评分
                elif dividend_yield > 0.02:
                    score += 5   # 中等股息率评分
            
            # 技术面评分 (10%)
            if not stock_data.empty:
                latest = stock_data.iloc[-1]
                
                # 相对位置
                if len(stock_data) >= 60:
                    ma60 = stock_data['close'].tail(60).mean()
                    if latest['close'] < ma60 * 0.9:
                        score += 10  # 低位
            
            return min(score, 100)
            
        except Exception as e:
            logger.error(f"计算价值股评分失败: {e}")
            return 0.0
    
    def _generate_final_results(self, position_allocation: Dict) -> Dict:
        """生成最终选股结果"""
        try:
            results = {
                'selection_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'position_allocation': position_allocation,
                'growth_stocks': self.growth_stocks,
                'value_stocks': self.value_stocks,
                'summary': self._generate_summary(),
                'recommendations': self._generate_strategy_recommendations()
            }
            
            self.final_allocation = results
            return results
            
        except Exception as e:
            logger.error(f"生成最终结果失败: {e}")
            return {}
    
    def _generate_summary(self) -> Dict:
        """生成选股摘要"""
        try:
            summary = {
                'total_growth_stocks': len(self.growth_stocks),
                'total_value_stocks': len(self.value_stocks),
                'total_stocks': len(self.growth_stocks) + len(self.value_stocks),
                'avg_growth_score': np.mean([s['growth_score'] for s in self.growth_stocks]) if self.growth_stocks else 0,
                'avg_value_score': np.mean([s['value_score'] for s in self.value_stocks]) if self.value_stocks else 0,
                'growth_industries': self._get_industry_distribution(self.growth_stocks),
                'value_industries': self._get_industry_distribution(self.value_stocks)
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"生成摘要失败: {e}")
            return {}
    
    def _get_industry_distribution(self, stocks: List[Dict]) -> Dict:
        """获取行业分布"""
        try:
            industry_count = {}
            for stock in stocks:
                industry = stock.get('industry_name', '未知')
                industry_count[industry] = industry_count.get(industry, 0) + 1
            
            return industry_count
            
        except Exception as e:
            logger.error(f"获取行业分布失败: {e}")
            return {}
    
    def _generate_strategy_recommendations(self) -> List[str]:
        """生成策略建议"""
        try:
            recommendations = []
            
            # 基于市场状态的建议
            market_state = self.data_manager.get_market_state()
            if market_state == '强多':
                recommendations.append("市场强势，成长股策略可适当提高仓位")
            elif market_state == '偏多':
                recommendations.append("市场偏多，成长股策略可维持正常仓位")
            elif market_state == '震荡':
                recommendations.append("市场震荡，价值股策略相对稳健")
            elif market_state == '偏空':
                recommendations.append("市场偏空，价值股策略相对抗跌")
            elif market_state == '弱空':
                recommendations.append("市场弱势，建议降低整体仓位")
            
            # 基于经济周期的建议
            economic_cycle = self.macro_analyzer.analyze_market_cycle()
            if economic_cycle == 'expansion':
                recommendations.append("经济扩张期，成长股策略占优")
            elif economic_cycle == 'contraction':
                recommendations.append("经济收缩期，价值股策略占优")
            
            # 基于选股结果的建议
            if self.growth_stocks and self.value_stocks:
                if len(self.growth_stocks) > len(self.value_stocks):
                    recommendations.append("成长股选股数量较多，建议关注成长机会")
                elif len(self.value_stocks) > len(self.growth_stocks):
                    recommendations.append("价值股选股数量较多，建议关注价值机会")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"生成策略建议失败: {e}")
            return []
    
    def _save_selection_results(self, results: Dict):
        """保存选股结果"""
        try:
            # 保存到数据库
            self.cursor.execute("""
                INSERT OR REPLACE INTO dual_strategy_selection 
                (selection_date, position_allocation_json, growth_stocks_json, 
                 value_stocks_json, summary_json, recommendations_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                results['selection_date'],
                str(results['position_allocation']),
                str(results['growth_stocks']),
                str(results['value_stocks']),
                str(results['summary']),
                str(results['recommendations'])
            ))
            
            self.conn.commit()
            logger.info("选股结果保存成功")
            
        except Exception as e:
            logger.error(f"保存选股结果失败: {e}")
    
    def get_selection_results(self) -> Dict:
        """获取选股结果"""
        return self.final_allocation
    
    def close(self):
        """关闭连接"""
        self.data_manager.close()
        self.macro_analyzer.close()


if __name__ == "__main__":
    # 测试模块
    logging.basicConfig(level=logging.INFO)
    
    selector = DualStrategySelector()
    
    try:
        print("=== 双策略选股系统测试 ===")
        
        # 运行双策略选股
        results = selector.run_dual_strategy_selection()
        
        if results:
            print("\n=== 选股结果 ===")
            print(f"选股时间: {results['selection_date']}")
            print(f"仓位分配: {results['position_allocation']}")
            
            print("\n=== 成长股选股结果 ===")
            for i, stock in enumerate(results['growth_stocks'], 1):
                print(f"{i}. {stock['ts_code']} - {stock['name']} (评分: {stock['growth_score']:.1f})")
            
            print("\n=== 价值股选股结果 ===")
            for i, stock in enumerate(results['value_stocks'], 1):
                print(f"{i}. {stock['ts_code']} - {stock['name']} (评分: {stock['value_score']:.1f})")
            
            print("\n=== 选股摘要 ===")
            summary = results['summary']
            print(f"成长股数量: {summary['total_growth_stocks']}")
            print(f"价值股数量: {summary['total_value_stocks']}")
            print(f"平均成长股评分: {summary['avg_growth_score']:.1f}")
            print(f"平均价值股评分: {summary['avg_value_score']:.1f}")
            
            print("\n=== 行业分布 ===")
            print("成长股行业分布:", summary['growth_industries'])
            print("价值股行业分布:", summary['value_industries'])
            
            print("\n=== 策略建议 ===")
            for i, rec in enumerate(results['recommendations'], 1):
                print(f"{i}. {rec}")
        
    except Exception as e:
        print(f"测试失败: {e}")
    finally:
        selector.close()