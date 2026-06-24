"""
observation_pool_tracker.py - 观察池跟踪系统
对选出的股票进行持续跟踪，监控基本面、技术面、舆情等信息
"""

import logging
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import numpy as np

from technical_integration import TechnicalIntegration
from macro_market_analyzer import MacroMarketAnalyzer

logger = logging.getLogger(__name__)

class ObservationPoolTracker:
    """观察池跟踪系统"""
    
    def __init__(self, db_path: str = "database/stock_analysis.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # 初始化技术分析器
        self.tech_analyzer = TechnicalIntegration(self.cursor)
        
        # 初始化宏观分析器
        self.macro_analyzer = MacroMarketAnalyzer(db_path)
        
        # 观察池数据
        self.observation_stocks = {}  # 观察池股票
        self.track_records = {}  # 跟踪记录
        self.alerts = []  # 警报信息
        
        # 跟踪参数
        self.update_frequency = 1  # 更新频率（天）
        self.alert_thresholds = {
            'price_change': 0.10,  # 价格变化10%触发警报
            'volume_spike': 2.0,   # 成交量放大2倍触发警报
            'signal_change': 'strong'  # 信号强度变化触发警报
        }
        
    def add_stocks_to_observation(self, stocks: List[Dict], strategy_type: str = 'dual'):
        """添加股票到观察池"""
        try:
            for stock in stocks:
                ts_code = stock.get('ts_code')
                if ts_code:
                    self.observation_stocks[ts_code] = {
                        'basic_info': stock,
                        'strategy_type': strategy_type,
                        'add_date': datetime.now().strftime('%Y-%m-%d'),
                        'last_update': None,
                        'track_count': 0,
                        'signals_history': [],
                        'performance_history': []
                    }
                    
            logger.info(f"已添加{len(stocks)}只股票到观察池")
            
        except Exception as e:
            logger.error(f"添加股票到观察池失败: {e}")
            
    def update_observation_pool(self, trade_date: str = None):
        """更新观察池数据"""
        try:
            if not trade_date:
                trade_date = datetime.now().strftime('%Y-%m-%d')
                
            logger.info(f"开始更新观察池数据，日期: {trade_date}")
            
            updated_count = 0
            for ts_code, stock_info in self.observation_stocks.items():
                try:
                    # 更新技术面信号
                    tech_signal = self.tech_analyzer.get_integrated_signal(ts_code, trade_date)
                    
                    # 更新基本面数据
                    fundamental_data = self._get_fundamental_data(ts_code, trade_date)
                    
                    # 更新价格表现
                    performance_data = self._get_performance_data(ts_code, trade_date)
                    
                    # 更新跟踪记录
                    track_record = {
                        'date': trade_date,
                        'technical_signal': tech_signal,
                        'fundamental_data': fundamental_data,
                        'performance_data': performance_data,
                        'composite_score': self._calculate_composite_score(tech_signal, fundamental_data, performance_data),
                        'alert_flags': self._check_alerts(tech_signal, performance_data)
                    }
                    
                    # 更新股票信息
                    stock_info['last_update'] = trade_date
                    stock_info['track_count'] += 1
                    stock_info['signals_history'].append(tech_signal)
                    stock_info['performance_history'].append(performance_data)
                    
                    # 保存到数据库
                    self._save_track_record(ts_code, track_record)
                    
                    # 检查警报
                    if track_record['alert_flags']:
                        self.alerts.append({
                            'date': trade_date,
                            'ts_code': ts_code,
                            'flags': track_record['alert_flags'],
                            'details': track_record
                        })
                        
                    updated_count += 1
                    
                except Exception as e:
                    logger.error(f"更新股票{ts_code}数据失败: {e}")
                    
            logger.info(f"观察池更新完成，更新{updated_count}只股票")
            
        except Exception as e:
            logger.error(f"更新观察池失败: {e}")
            
    def _get_fundamental_data(self, ts_code: str, trade_date: str) -> Dict:
        """获取基本面数据"""
        try:
            # 查询最新财务数据
            query = """
                SELECT f.ts_code, f.trade_date, f.roe_yearly, f.netprofit_yoy, f.revenue_yoy,
                       f.pe_ttm, f.pb, f.dividend_yield, f.debt_ratio
                FROM financial_data f
                WHERE f.ts_code = ? AND f.trade_date <= ?
                ORDER BY f.trade_date DESC
                LIMIT 1
            """
            
            self.cursor.execute(query, (ts_code, trade_date))
            row = self.cursor.fetchone()
            
            if row:
                return {
                    'ts_code': row[0],
                    'trade_date': row[1],
                    'roe_yearly': row[2],
                    'netprofit_yoy': row[3],
                    'revenue_yoy': row[4],
                    'pe_ttm': row[5],
                    'pb': row[6],
                    'dividend_yield': row[7],
                    'debt_ratio': row[8]
                }
            else:
                return {}
                
        except Exception as e:
            logger.error(f"获取基本面数据失败: {e}")
            return {}
            
    def _get_performance_data(self, ts_code: str, trade_date: str) -> Dict:
        """获取价格表现数据"""
        try:
            # 查询最近20个交易日的数据
            query = """
                SELECT d.trade_date, d.close, d.volume, d.change_pct, d.ma5, d.ma10, d.ma20
                FROM daily_quotes d
                WHERE d.ts_code = ? AND d.trade_date <= ?
                ORDER BY d.trade_date DESC
                LIMIT 20
            """
            
            self.cursor.execute(query, (ts_code, trade_date))
            rows = self.cursor.fetchall()
            
            if rows:
                # 计算技术指标
                prices = [row[1] for row in rows]
                volumes = [row[2] for row in rows]
                
                # 计算价格变化
                price_change_5d = (prices[0] - prices[4]) / prices[4] if len(prices) > 4 else 0
                price_change_10d = (prices[0] - prices[9]) / prices[9] if len(prices) > 9 else 0
                price_change_20d = (prices[0] - prices[19]) / prices[19] if len(prices) > 19 else 0
                
                # 计算成交量变化
                volume_avg_5d = np.mean(volumes[:5])
                volume_avg_20d = np.mean(volumes[:20])
                volume_ratio = volume_avg_5d / volume_avg_20d if volume_avg_20d > 0 else 1
                
                return {
                    'ts_code': ts_code,
                    'trade_date': trade_date,
                    'current_price': prices[0],
                    'price_change_5d': price_change_5d,
                    'price_change_10d': price_change_10d,
                    'price_change_20d': price_change_20d,
                    'volume_ratio': volume_ratio,
                    'ma5': rows[0][5],
                    'ma10': rows[0][6],
                    'ma20': rows[0][7],
                    'above_ma5': prices[0] > rows[0][5],
                    'above_ma10': prices[0] > rows[0][6],
                    'above_ma20': prices[0] > rows[0][7]
                }
            else:
                return {}
                
        except Exception as e:
            logger.error(f"获取价格表现数据失败: {e}")
            return {}
            
    def _calculate_composite_score(self, tech_signal: Dict, fundamental_data: Dict, performance_data: Dict) -> float:
        """计算综合评分"""
        try:
            score = 0
            
            # 技术面评分 (40%)
            if tech_signal.get('score'):
                score += tech_signal['score'] * 0.4
                
            # 基本面评分 (35%)
            fundamental_score = 0
            if fundamental_data.get('roe_yearly'):
                fundamental_score += min(fundamental_data['roe_yearly'] * 100, 20)  # ROE 20分
            if fundamental_data.get('netprofit_yoy'):
                fundamental_score += min(fundamental_data['netprofit_yoy'] * 50, 15)  # 净利润增长 15分
            if fundamental_data.get('revenue_yoy'):
                fundamental_score += min(fundamental_data['revenue_yoy'] * 30, 10)  # 营收增长 10分
            if fundamental_data.get('pe_ttm') and fundamental_data['pe_ttm'] > 0:
                fundamental_score += min(30 / fundamental_data['pe_ttm'], 5)  # PE估值 5分
                
            score += fundamental_score * 0.35
            
            # 价格表现评分 (25%)
            performance_score = 0
            if performance_data.get('price_change_5d'):
                performance_score += min(abs(performance_data['price_change_5d']) * 50, 10)  # 短期表现 10分
            if performance_data.get('above_ma20'):
                performance_score += 10  # 站上MA20 10分
            if performance_data.get('volume_ratio') and performance_data['volume_ratio'] > 1.5:
                performance_score += 5  # 成交量放大 5分
                
            score += performance_score * 0.25
            
            return round(score, 2)
            
        except Exception as e:
            logger.error(f"计算综合评分失败: {e}")
            return 0
            
    def _check_alerts(self, tech_signal: Dict, performance_data: Dict) -> List[str]:
        """检查警报条件"""
        alerts = []
        
        try:
            # 价格变化警报
            if performance_data.get('price_change_5d', 0) > self.alert_thresholds['price_change']:
                alerts.append('price_up')
            elif performance_data.get('price_change_5d', 0) < -self.alert_thresholds['price_change']:
                alerts.append('price_down')
                
            # 成交量警报
            if performance_data.get('volume_ratio', 0) > self.alert_thresholds['volume_spike']:
                alerts.append('volume_spike')
                
            # 信号强度警报
            if tech_signal.get('strength') == 'strong':
                alerts.append('strong_signal')
            elif tech_signal.get('strength') == 'weak':
                alerts.append('weak_signal')
                
        except Exception as e:
            logger.error(f"检查警报失败: {e}")
            
        return alerts
        
    def _save_track_record(self, ts_code: str, track_record: Dict):
        """保存跟踪记录"""
        try:
            # 创建跟踪记录表
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS observation_track_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_code TEXT NOT NULL,
                    track_date TEXT NOT NULL,
                    technical_signal TEXT,
                    fundamental_data TEXT,
                    performance_data TEXT,
                    composite_score REAL,
                    alert_flags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 保存记录
            self.cursor.execute("""
                INSERT INTO observation_track_records (
                    ts_code, track_date, technical_signal, fundamental_data,
                    performance_data, composite_score, alert_flags
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                ts_code,
                track_record['date'],
                str(track_record['technical_signal']),
                str(track_record['fundamental_data']),
                str(track_record['performance_data']),
                track_record['composite_score'],
                str(track_record['alert_flags'])
            ))
            
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"保存跟踪记录失败: {e}")
            
    def generate_observation_report(self) -> str:
        """生成观察池报告"""
        report = []
        report.append("# 观察池跟踪报告")
        report.append(f"**报告时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"**观察股票数量**: {len(self.observation_stocks)}")
        report.append("")
        
        # 观察池摘要
        report.append("## 观察池摘要")
        growth_count = sum(1 for s in self.observation_stocks.values() if s['strategy_type'] == 'growth')
        value_count = sum(1 for s in self.observation_stocks.values() if s['strategy_type'] == 'value')
        report.append(f"- **成长股数量**: {growth_count}")
        report.append(f"- **价值股数量**: {value_count}")
        report.append("")
        
        # 股票详情
        report.append("## 股票跟踪详情")
        report.append("| 股票代码 | 股票名称 | 策略类型 | 综合评分 | 最新信号 | 警报状态 |")
        report.append("|----------|----------|----------|----------|----------|----------|")
        
        for ts_code, stock_info in self.observation_stocks.items():
            basic_info = stock_info['basic_info']
            strategy_type = stock_info['strategy_type']
            track_count = stock_info['track_count']
            
            # 获取最新评分和信号
            latest_score = 0
            latest_signal = 'N/A'
            alert_status = '正常'
            
            if stock_info['performance_history']:
                latest_performance = stock_info['performance_history'][0]
                latest_score = latest_performance.get('composite_score', 0)
                
            if stock_info['signals_history']:
                latest_signal = stock_info['signals_history'][0].get('signal', 'N/A')
                
            # 检查警报
            if stock_info['signals_history'] and stock_info['signals_history'][0].get('alert_flags'):
                alert_status = '有警报'
                
            name = basic_info.get('name', 'N/A')
            report.append(f"| {ts_code} | {name} | {strategy_type} | {latest_score:.1f} | {latest_signal} | {alert_status} |")
            
        report.append("")
        
        # 警报信息
        if self.alerts:
            report.append("## 警报信息")
            for alert in self.alerts[-10:]:  # 显示最近10条警报
                ts_code = alert['ts_code']
                flags = alert['flags']
                date = alert['date']
                report.append(f"- **{ts_code}** ({date}): {', '.join(flags)}")
            report.append("")
            
        # 推荐操作
        report.append("## 推荐操作")
        report.append("### 重点关注")
        high_score_stocks = []
        for ts_code, stock_info in self.observation_stocks.items():
            if stock_info['performance_history'] and stock_info['performance_history'][0].get('composite_score', 0) >= 80:
                high_score_stocks.append(ts_code)
                
        if high_score_stocks:
            report.append(f"综合评分较高的股票: {', '.join(high_score_stocks[:5])}")
        else:
            report.append("暂无特别突出的股票")
            
        report.append("")
        report.append("### 风险提示")
        if self.alerts:
            report.append(f"当前有{len(self.alerts)}条警报，请密切关注相关股票")
        else:
            report.append("当前无重大警报，可正常跟踪")
            
        return "\n".join(report)
        
    def get_portfolio_recommendations(self) -> Dict:
        """获取投资组合建议"""
        try:
            recommendations = {
                'high_priority': [],
                'medium_priority': [],
                'low_priority': [],
                'avoid': []
            }
            
            for ts_code, stock_info in self.observation_stocks.items():
                if stock_info['performance_history']:
                    score = stock_info['performance_history'][0].get('composite_score', 0)
                    signal = stock_info['signals_history'][0].get('signal', 'wait') if stock_info['signals_history'] else 'wait'
                    
                    recommendation = {
                        'ts_code': ts_code,
                        'score': score,
                        'signal': signal,
                        'strategy_type': stock_info['strategy_type']
                    }
                    
                    if score >= 80 and signal in ['buy', 'strong_buy']:
                        recommendations['high_priority'].append(recommendation)
                    elif score >= 60 and signal in ['buy', 'hold']:
                        recommendations['medium_priority'].append(recommendation)
                    elif score < 40 or signal == 'sell':
                        recommendations['avoid'].append(recommendation)
                    else:
                        recommendations['low_priority'].append(recommendation)
                        
            # 按评分排序
            for category in recommendations:
                recommendations[category].sort(key=lambda x: x['score'], reverse=True)
                
            return recommendations
            
        except Exception as e:
            logger.error(f"获取投资组合建议失败: {e}")
            return {}
            
    def close(self):
        """关闭连接"""
        if hasattr(self, 'conn'):
            self.conn.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # 测试观察池跟踪
    tracker = ObservationPoolTracker()
    
    try:
        # 添加测试股票到观察池
        test_stocks = [
            {'ts_code': '000001.SZ', 'name': '平安银行', 'strategy_type': 'value'},
            {'ts_code': '000002.SZ', 'name': '万科A', 'strategy_type': 'value'},
            {'ts_code': '300750.SZ', 'name': '宁德时代', 'strategy_type': 'growth'}
        ]
        
        tracker.add_stocks_to_observation(test_stocks)
        
        # 更新观察池
        tracker.update_observation_pool()
        
        # 生成报告
        report = tracker.generate_observation_report()
        print(report)
        
        # 获取投资组合建议
        recommendations = tracker.get_portfolio_recommendations()
        print("\n投资组合建议:")
        for category, stocks in recommendations.items():
            if stocks:
                print(f"{category}: {len(stocks)}只股票")
                
    except Exception as e:
        logger.error(f"测试失败: {e}")
    finally:
        tracker.close()