"""
backtest_engine.py - 回测引擎核心模块
实现多策略并行回测、交易执行、性能评估等功能
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class SignalType(Enum):
    """交易信号类型"""
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    WAIT = "wait"

class PositionStatus(Enum):
    """持仓状态"""
    EMPTY = "empty"
    LONG = "long"
    SHORT = "short"

@dataclass
class Trade:
    """交易记录"""
    trade_id: str
    ts_code: str
    trade_date: str
    signal_type: SignalType
    price: float
    quantity: int
    amount: float
    commission: float = 0.0
    strategy_type: str = ""
    
    def __post_init__(self):
        self.amount = self.price * self.quantity
        
@dataclass
class Position:
    """持仓信息"""
    ts_code: str
    quantity: int
    avg_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    position_status: PositionStatus
    
    def __post_init__(self):
        self.market_value = self.quantity * self.current_price
        self.unrealized_pnl = self.market_value - (self.quantity * self.avg_price)

@dataclass
class Portfolio:
    """投资组合"""
    portfolio_id: str
    total_capital: float
    available_cash: float
    positions: Dict[str, Position]
    trades: List[Trade]
    total_value: float
    
    def __post_init__(self):
        self.update_total_value()
    
    def update_total_value(self):
        """更新组合总价值"""
        position_value = sum(pos.market_value for pos in self.positions.values())
        self.total_value = self.available_cash + position_value

class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, db_path: str = "database/stock_analysis.db"):
        """初始化回测引擎"""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # 回测参数
        self.start_date = None
        self.end_date = None
        self.initial_capital = 1000000.0
        self.commission_rate = 0.0003  # 手续费率
        self.slippage_rate = 0.0001   # 滑点率
        
        # 策略参数
        self.strategies = {}
        self.portfolios = {}
        
        # 回测结果
        self.results = {}
        
    def add_strategy(self, strategy_name: str, strategy_func: callable, 
                    strategy_type: str = "custom", params: Dict = None):
        """添加策略"""
        self.strategies[strategy_name] = {
            'func': strategy_func,
            'type': strategy_type,
            'params': params or {}
        }
        
    def set_backtest_params(self, start_date: str, end_date: str, 
                           initial_capital: float = 1000000.0,
                           commission_rate: float = 0.0003,
                           slippage_rate: float = 0.0001):
        """设置回测参数"""
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        
    def get_trading_dates(self) -> List[str]:
        """获取交易日期列表"""
        query = """
            SELECT DISTINCT trade_date 
            FROM daily_quotes 
            WHERE trade_date BETWEEN ? AND ?
            ORDER BY trade_date
        """
        self.cursor.execute(query, (self.start_date, self.end_date))
        dates = [row[0] for row in self.cursor.fetchall()]
        return dates
    
    def get_daily_data(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取日线数据"""
        query = """
            SELECT trade_date, open, high, low, close, volume, amount
            FROM daily_quotes 
            WHERE ts_code = ? AND trade_date BETWEEN ? AND ?
            ORDER BY trade_date
        """
        self.cursor.execute(query, (ts_code, start_date, end_date))
        columns = ['trade_date', 'open', 'high', 'low', 'close', 'volume', 'amount']
        data = self.cursor.fetchall()
        
        if data:
            return pd.DataFrame(data, columns=columns)
        return pd.DataFrame()
    
    def get_technical_signals(self, ts_code: str, trade_date: str, 
                            strategy_type: str) -> Dict:
        """获取技术面信号"""
        try:
            # 导入技术面整合模块
            from technical_integration import TechnicalIntegration
            
            ti = TechnicalIntegration(self.cursor)
            
            # 获取交易日期前一个交易日
            prev_date_query = """
                SELECT MAX(trade_date) 
                FROM daily_quotes 
                WHERE ts_code = ? AND trade_date < ?
            """
            self.cursor.execute(prev_date_query, (ts_code, trade_date))
            prev_date = self.cursor.fetchone()[0]
            
            if not prev_date:
                return {'signal': 'wait', 'strength': 'unknown', 'score': 0}
            
            # 获取技术面信号
            signal = ti.get_integrated_signal(ts_code, prev_date, strategy_type)
            return signal
            
        except Exception as e:
            logger.error(f"获取技术面信号失败: {e}")
            return {'signal': 'wait', 'strength': 'unknown', 'score': 0}
    
    def execute_trade(self, portfolio: Portfolio, ts_code: str, signal: Dict, 
                    current_price: float, trade_date: str) -> bool:
        """执行交易"""
        try:
            signal_type = signal.get('signal', 'wait')
            strength = signal.get('strength', 'unknown')
            score = signal.get('score', 0)
            strategy_type = signal.get('strategy_type', 'unknown')
            
            # 计算交易数量
            if signal_type == 'buy' and portfolio.available_cash > 0:
                # 买入信号
                available_amount = portfolio.available_cash * 0.95  # 保留5%现金
                quantity = int(available_amount / current_price / 100) * 100  # 按手数
                
                if quantity > 0:
                    # 计算实际价格（含滑点）
                    actual_price = current_price * (1 + self.slippage_rate)
                    total_amount = quantity * actual_price
                    commission = total_amount * self.commission_rate
                    
                    if total_amount + commission <= portfolio.available_cash:
                        # 创建交易记录
                        trade_id = f"{trade_date}_{ts_code}_{len(portfolio.trades)}"
                        trade = Trade(
                            trade_id=trade_id,
                            ts_code=ts_code,
                            trade_date=trade_date,
                            signal_type=SignalType.BUY,
                            price=actual_price,
                            quantity=quantity,
                            amount=total_amount,
                            commission=commission,
                            strategy_type=strategy_type
                        )
                        
                        # 更新持仓
                        if ts_code in portfolio.positions:
                            # 持仓加仓
                            pos = portfolio.positions[ts_code]
                            total_cost = pos.avg_price * pos.quantity + total_amount
                            total_quantity = pos.quantity + quantity
                            pos.avg_price = total_cost / total_quantity
                            pos.quantity = total_quantity
                            pos.current_price = current_price
                            pos.market_value = pos.quantity * current_price
                            pos.unrealized_pnl = pos.market_value - total_cost
                        else:
                            # 新建持仓
                            position = Position(
                                ts_code=ts_code,
                                quantity=quantity,
                                avg_price=actual_price,
                                current_price=current_price,
                                market_value=total_amount,
                                unrealized_pnl=0,
                                position_status=PositionStatus.LONG
                            )
                            portfolio.positions[ts_code] = position
                        
                        # 更新现金
                        portfolio.available_cash -= (total_amount + commission)
                        portfolio.trades.append(trade)
                        
                        logger.info(f"买入 {ts_code} {quantity}股 @ {actual_price:.2f}")
                        return True
                        
            elif signal_type == 'sell' and ts_code in portfolio.positions:
                # 卖出信号
                position = portfolio.positions[ts_code]
                quantity = position.quantity
                
                if quantity > 0:
                    # 计算实际价格（含滑点）
                    actual_price = current_price * (1 - self.slippage_rate)
                    total_amount = quantity * actual_price
                    commission = total_amount * self.commission_rate
                    
                    # 创建交易记录
                    trade_id = f"{trade_date}_{ts_code}_{len(portfolio.trades)}"
                    trade = Trade(
                        trade_id=trade_id,
                        ts_code=ts_code,
                        trade_date=trade_date,
                        signal_type=SignalType.SELL,
                        price=actual_price,
                        quantity=quantity,
                        amount=total_amount,
                        commission=commission,
                        strategy_type=strategy_type
                    )
                    
                    # 更新现金
                    portfolio.available_cash += (total_amount - commission)
                    
                    # 移除持仓
                    del portfolio.positions[ts_code]
                    
                    logger.info(f"卖出 {ts_code} {quantity}股 @ {actual_price:.2f}")
                    return True
                    
            return False
            
        except Exception as e:
            logger.error(f"执行交易失败: {e}")
            return False
    
    def run_backtest(self, strategy_names: List[str] = None) -> Dict:
        """运行回测"""
        try:
            if not strategy_names:
                strategy_names = list(self.strategies.keys())
            
            # 初始化投资组合
            for strategy_name in strategy_names:
                portfolio = Portfolio(
                    portfolio_id=f"{strategy_name}_{self.start_date}_{self.end_date}",
                    total_capital=self.initial_capital,
                    available_cash=self.initial_capital,
                    positions={},
                    trades=[],
                    total_value=self.initial_capital
                )
                self.portfolios[strategy_name] = portfolio
            
            # 获取交易日期列表
            trading_dates = self.get_trading_dates()
            
            # 逐日回测
            for trade_date in trading_dates:
                logger.info(f"回测日期: {trade_date}")
                
                for strategy_name in strategy_names:
                    portfolio = self.portfolios[strategy_name]
                    
                    # 获取股票池（这里简化处理，实际应该根据策略获取）
                    stock_pool = self.get_stock_pool_for_strategy(strategy_name, trade_date)
                    
                    for ts_code in stock_pool:
                        # 获取当前价格
                        daily_data = self.get_daily_data(ts_code, trade_date, trade_date)
                        if daily_data.empty:
                            continue
                            
                        current_price = daily_data.iloc[0]['close']
                        
                        # 获取技术面信号
                        signal = self.get_technical_signals(ts_code, trade_date, strategy_name)
                        
                        # 执行交易
                        self.execute_trade(portfolio, ts_code, signal, current_price, trade_date)
                
                # 更新组合总价值
                for portfolio in self.portfolios.values():
                    portfolio.update_total_value()
            
            # 计算回测结果
            results = self.calculate_performance_metrics()
            
            return results
            
        except Exception as e:
            logger.error(f"回测运行失败: {e}")
            return {}
    
    def get_stock_pool_for_strategy(self, strategy_name: str, trade_date: str) -> List[str]:
        """获取策略股票池（简化版本）"""
        # 这里应该根据策略类型返回不同的股票池
        # 现在返回一个固定的股票池用于测试
        query = """
            SELECT DISTINCT ts_code 
            FROM daily_quotes 
            WHERE trade_date = ? 
            LIMIT 20
        """
        self.cursor.execute(query, (trade_date,))
        return [row[0] for row in self.cursor.fetchall()]
    
    def calculate_performance_metrics(self) -> Dict:
        """计算性能指标"""
        results = {}
        
        for strategy_name, portfolio in self.portfolios.items():
            # 计算收益率
            total_return = (portfolio.total_value - self.initial_capital) / self.initial_capital
            
            # 计算交易统计
            buy_trades = [t for t in portfolio.trades if t.signal_type == SignalType.BUY]
            sell_trades = [t for t in portfolio.trades if t.signal_type == SignalType.SELL]
            
            # 计算胜率
            win_trades = 0
            for buy_trade in buy_trades:
                # 找到对应的卖出交易
                sell_trade = None
                for sell in sell_trades:
                    if sell.ts_code == buy_trade.ts_code and sell.trade_date > buy_trade.trade_date:
                        sell_trade = sell
                        break
                
                if sell_trade:
                    pnl = sell_trade.amount - buy_trade.amount - sell_trade.commission - buy_trade.commission
                    if pnl > 0:
                        win_trades += 1
            
            total_trades = len(buy_trades)
            win_rate = win_trades / total_trades if total_trades > 0 else 0
            
            # 计算最大回撤
            values = [self.initial_capital]
            for trade in portfolio.trades:
                if trade.signal_type == SignalType.BUY:
                    values.append(values[-1] - trade.amount - trade.commission)
                elif trade.signal_type == SignalType.SELL:
                    values.append(values[-1] + trade.amount - trade.commission)
            
            max_drawdown = 0
            peak = values[0]
            for value in values[1:]:
                if value > peak:
                    peak = value
                drawdown = (peak - value) / peak
                max_drawdown = max(max_drawdown, drawdown)
            
            # 存储结果
            results[strategy_name] = {
                'total_return': total_return,
                'annual_return': total_return * 252 / len(self.get_trading_dates()),
                'win_rate': win_rate,
                'total_trades': total_trades,
                'max_drawdown': max_drawdown,
                'final_value': portfolio.total_value,
                'total_trades_count': len(portfolio.trades),
                'positions_count': len(portfolio.positions)
            }
        
        return results
    
    def generate_report(self, results: Dict) -> str:
        """生成回测报告"""
        report = f"""
# 回测报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
回测周期: {self.start_date} 至 {self.end_date}
初始资金: {self.initial_capital:,.2f}

## 策略表现对比
"""
        
        # 添加策略表现表格
        report += "| 策略名称 | 总收益率 | 年化收益率 | 胜率 | 总交易次数 | 最大回撤 | 最终价值 |\n"
        report += "|----------|----------|------------|------|------------|----------|----------|\n"
        
        for strategy_name, metrics in results.items():
            report += f"| {strategy_name} | {metrics['total_return']:.2%} | {metrics['annual_return']:.2%} | {metrics['win_rate']:.2%} | {metrics['total_trades']} | {metrics['max_drawdown']:.2%} | {metrics['final_value']:,.2f} |\n"
        
        # 添加详细分析
        report += "\n## 详细分析\n"
        
        for strategy_name, metrics in results.items():
            report += f"\n### {strategy_name}\n"
            report += f"- 总收益率: {metrics['total_return']:.2%}\n"
            report += f"- 年化收益率: {metrics['annual_return']:.2%}\n"
            report += f"- 胜率: {metrics['win_rate']:.2%}\n"
            report += f"- 总交易次数: {metrics['total_trades']}\n"
            report += f"- 最大回撤: {metrics['max_drawdown']:.2%}\n"
            report += f"- 最终价值: {metrics['final_value']:,.2f}\n"
        
        return report
    
    def save_results(self, results: Dict, filename: str = None):
        """保存回测结果"""
        if not filename:
            filename = f"backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        report = self.generate_report(results)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"回测结果已保存到: {filename}")
        return filename

if __name__ == "__main__":
    # 测试回测引擎
    engine = BacktestEngine()
    engine.set_backtest_params("2026-01-01", "2026-06-18", 1000000)
    
    # 添加策略（这里简化处理）
    def dummy_strategy(ts_code, trade_date):
        return {'signal': 'wait', 'strength': 'unknown', 'score': 0}
    
    engine.add_strategy("dummy_strategy", dummy_strategy)
    
    # 运行回测
    results = engine.run_backtest(["dummy_strategy"])
    print(results)