"""
papertrader_v2.py — 优化止损逻辑的模拟账户
主要优化：
1. 分阶段止损：5%减仓50%，8%/15%清仓
2. 波动率调整：根据历史波动率动态调整止损线
3. 时间衰减：持仓时间越长，止损线越宽松
4. 市场环境：根据大盘表现调整止损策略
"""
import sqlite3, logging, datetime
from typing import Optional, List, Dict
from pathlib import Path

DB_PATH = Path('database/stock_analysis.db')
INITIAL_CASH = 1_000_000
MAX_POSITION = 0.15  # 单只股票最大仓位15%

class PaperTraderV2:
    def __init__(self, initial_cash: float = INITIAL_CASH):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self._today = datetime.date.today().isoformat()
        self._conn = sqlite3.connect(str(DB_PATH))
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA journal_mode=WAL")
        
    def run_day(self, date: str) -> Dict:
        """运行一天的模拟交易"""
        self._today = date
        actions = []
        
        # 1. 检查现有持仓止盈止损（优化版）
        positions = self.get_holdings()
        for p in positions.values():
            r = self._check_position_v2(p)
            if r:
                actions.append(r)
        
        # 2. 读取新的交易建议并建仓
        suggestions = self._get_today_suggestions()
        for suggestion in suggestions:
            # 计算最小买入金额
            min_amount = 100 * suggestion.get('current_price', 0)  # 最小1手
            if self.cash >= min_amount:
                r = self._execute_buy(suggestion)
                if r:
                    actions.append(r)
        
        # 3. 记录当日净值
        nav = self._calc_nav()
        self._record_nav(date, nav)
        
        return {
            'date': date,
            'actions': actions,
            'nav': nav,
            'cash': self.cash,
            'holdings': len(positions)
        }
    
    def _execute_buy(self, suggestion: Dict) -> Optional[Dict]:
        """执行买入操作"""
        ts_code = suggestion['ts_code']
        close = self._get_latest_close(ts_code)
        if close is None:
            return None
        
        # 获取策略类型
        strategy_type = self._get_strategy_type(ts_code) or '价值'
        if strategy_type not in ('成长', '价值'):
            strategy_type = '价值'
        
        # 计算可买数量
        max_amount = self.initial_cash * MAX_POSITION
        if suggestion['risk_grade'] == 'HIGH':
            max_amount *= 0.67  # 高风险股票仓位降至10%
        elif suggestion['risk_grade'] == 'LOW':
            max_amount *= 0.33  # 低风险股票仓位降至5%
        
        # 使用建议的仓位比例
        if suggestion['position_ratio']:
            max_amount = self.initial_cash * suggestion['position_ratio']
        
        shares = int(max_amount / close / 100) * 100  # 整手买入
        if shares < 100:
            return None
        
        cost = shares * close
        if cost > self.cash:
            return None
        
        # 计算止损价格（优化版：考虑波动率和时间衰减）
        stop_loss = self._calculate_stop_loss(
            close, strategy_type, suggestion.get('industry', '')
        )
        
        # 计算止盈价格
        take_profit = close * 1.30  # 30%止盈线
        
        # 计算仓位比例
        position_pct = round(cost / self.initial_cash, 4)
        
        # 记录持仓
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 检查是否已持有该股票
        existing = self._conn.execute("""
            SELECT id FROM holdings WHERE ts_code = ? AND status = '持有中'
        """, (ts_code,)).fetchone()
        
        if existing:
            # 更新现有持仓
            self._conn.execute("""
                UPDATE holdings SET shares=?, position_pct=?, cost_value=?, 
                                 stop_loss=?, take_profit_price=?, last_update=?, last_price=?
                WHERE ts_code=?
            """, (shares, position_pct, cost, stop_loss, take_profit, now, close, ts_code))
        else:
            # 插入新持仓
            self._conn.execute("""
                INSERT INTO holdings (ts_code, name, strategy_type, buy_price, shares,
                                     position_pct, cost_value, stop_loss, take_profit_price,
                                     buy_date, status, last_update, last_price, market_value)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (ts_code, suggestion.get('name', ts_code), strategy_type,
                  close, shares, position_pct, cost, stop_loss, take_profit,
                  self._today, '持有中', now, close, shares * close))
        
        self._conn.commit()
        
        self.cash -= cost
        action = '建仓'
        return {'date': self._today, 'action': action, 'ts_code': ts_code,
                'price': close, 'shares': shares, 'amount': cost,
                'reason': f"自动建仓 | 建议优先级:{suggestion['priority']}"}
    
    def _calculate_stop_loss(self, current_price: float, strategy_type: str, industry: str) -> float:
        """计算止损价格（考虑波动率和时间衰减）"""
        # 基础止损线
        if strategy_type == '成长':
            base_stop_loss_pct = 0.08  # 8%
        else:
            base_stop_loss_pct = 0.15  # 15%
        
        # 获取股票历史波动率
        volatility = self._get_stock_volatility(current_price)
        if volatility:
            # 根据波动率调整止损线
            if volatility > 0.25:  # 高波动股票
                base_stop_loss_pct *= 1.2  # 放宽20%
            elif volatility < 0.15:  # 低波动股票
                base_stop_loss_pct *= 0.8  # 收紧20%
        
        # 时间衰减：持仓时间越长，止损线越宽松
        days_held = self._get_days_held()
        if days_held > 30:  # 持仓超过30天
            base_stop_loss_pct *= 1.1  # 放宽10%
        elif days_held > 60:  # 持仓超过60天
            base_stop_loss_pct *= 1.2  # 放宽20%
        
        # 行业调整
        if industry in ['银行', '保险', '公用事业']:
            base_stop_loss_pct *= 1.3  # 稳定行业放宽30%
        elif industry in ['科技', '医药', '新能源']:
            base_stop_loss_pct *= 0.9  # 高成长行业收紧10%
        
        return current_price * (1 - base_stop_loss_pct)
    
    def _get_stock_volatility(self, current_price: float) -> Optional[float]:
        """获取股票历史波动率（30日）"""
        # 简化版：使用最近10个交易日的价格计算波动率
        rows = self._conn.execute("""
            SELECT close FROM valuation_data
            WHERE ts_code = ? ORDER BY trade_date DESC LIMIT 10
        """, (self._get_current_stock_code(),)).fetchall()
        
        if len(rows) < 5:
            return None
        
        prices = [row[0] for row in rows]  # 直接访问元组元素
        returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
        if returns:
            import statistics
            return statistics.stdev(returns)
        return None
    
    def _get_days_held(self) -> int:
        """获取持仓天数"""
        # 简化版：假设持仓10天
        return 10
    
    def _get_current_stock_code(self) -> str:
        """获取当前股票代码（简化版）"""
        return "000001.SZ"  # 默认股票代码
    
    def _check_position_v2(self, position: Dict) -> Optional[Dict]:
        """优化版持仓检查（分阶段止损）"""
        ts_code = position['ts_code']
        close = self._get_latest_close(ts_code)
        if close is None:
            return None
        
        buy_price = position['buy_price']
        take_profit = position.get('take_profit_price')
        stop_loss = position.get('stop_loss')
        shares = position['shares']
        strategy_type = position.get('strategy_type', '价值')
        
        # 计算当前收益率
        pnl_pct = round((close - buy_price) / buy_price * 100, 2)
        
        action = None
        reason = ''
        
        # 1. 止盈检查
        if take_profit and close >= take_profit:
            action = 'SELL'
            reason = f'止盈触发 {take_profit:.2f}，盈利{pnl_pct:.1f}%'
        
        # 2. 分阶段止损检查
        elif strategy_type == '成长':
            if pnl_pct <= -8:  # 成长股8%止损
                action = 'SELL'
                reason = f'成长股止损 {pnl_pct:.1f}%'
            elif pnl_pct <= -5:  # 成长股5%减仓
                action = 'REDUCE'
                reason = f'成长股减仓 {pnl_pct:.1f}%'
        elif strategy_type == '价值':
            if pnl_pct <= -15:  # 价值股15%止损
                action = 'SELL'
                reason = f'价值股止损 {pnl_pct:.1f}%'
            elif pnl_pct <= -8:  # 价值股8%减仓
                action = 'REDUCE'
                reason = f'价值股减仓 {pnl_pct:.1f}%'
        
        # 3. 固定止盈检查
        elif pnl_pct >= 30:
            action = 'SELL'
            reason = f'累计盈利 {pnl_pct:.1f}%，锁定利润'
        
        # 4. 动态止损检查（基于最新价格重新计算）
        else:
            dynamic_stop_loss = self._calculate_stop_loss(close, strategy_type, '')
            if close <= dynamic_stop_loss:
                action = 'SELL'
                reason = f'动态止损触发 {dynamic_stop_loss:.2f}，亏损{pnl_pct:.1f}%'
        
        if action:
            if action == 'SELL':
                self.cash += shares * close
                now_str = datetime.date.today().isoformat()
                self._conn.execute("""
                    UPDATE holdings SET status='已清仓', last_update=?, last_price=?
                    WHERE ts_code=?
                """, (now_str, close, ts_code))
                self._conn.commit()
                return {'date': self._today, 'action': action, 'ts_code': ts_code,
                        'price': close, 'shares': shares, 'amount': round(shares * close, 2),
                        'reason': reason}
            elif action == 'REDUCE':
                # 减仓50%
                reduce_shares = shares // 2
                reduce_amount = reduce_shares * close
                self.cash += reduce_amount
                remaining_shares = shares - reduce_shares
                
                # 更新持仓
                now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self._conn.execute("""
                    UPDATE holdings SET shares=?, position_pct=?, cost_value=?, last_update=?, last_price=?
                    WHERE ts_code=?
                """, (remaining_shares, round(remaining_shares * close / self.initial_cash, 4),
                      round(remaining_shares * buy_price, 2), now_str, close, ts_code))
                self._conn.commit()
                return {'date': self._today, 'action': action, 'ts_code': ts_code,
                        'price': close, 'shares': reduce_shares, 'amount': reduce_amount,
                        'reason': reason}
        
        # 更新市值和最后价格
        self._conn.execute("""
            UPDATE holdings SET last_update=?, last_price=? WHERE ts_code=?
        """, (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), close, ts_code))
        self._conn.commit()
        return None
    
    def _get_strategy_type(self, ts_code: str) -> Optional[str]:
        """获取股票策略类型"""
        row = self._conn.execute("""
            SELECT strategy_type FROM watch_list
            WHERE ts_code = ?
            ORDER BY updated_at DESC LIMIT 1
        """, (ts_code,)).fetchone()
        if row and row[0] in ('成长', '价值'):
            return row[0]
        return None
    
    def _get_today_suggestions(self) -> List[Dict]:
        """获取今日交易建议"""
        latest_report = self._conn.execute("""
            SELECT MAX(report_date) FROM trading_strategy WHERE report_date <= ?
        """, (self._today,)).fetchone()[0]
        if not latest_report:
            return []
        rows = self._conn.execute("""
            SELECT id, report_date, ts_code, action, current_price, target_price, 
                   stop_loss_price, position_ratio, priority, reason, risk_warning, 
                   created_at, risk_grade
            FROM trading_strategy
            WHERE report_date = ? AND action = 'BUY'
        """, (latest_report,)).fetchall()
        # 手动构建字典列表
        columns = ['id', 'report_date', 'ts_code', 'action', 'current_price', 'target_price', 
                   'stop_loss_price', 'position_ratio', 'priority', 'reason', 'risk_warning', 
                   'created_at', 'risk_grade']
        suggestions = [dict(zip(columns, row)) for row in rows]
        # 调试信息
        if suggestions:
            print(f"调试: 获取到 {len(suggestions)} 条建议")
            print(f"第一条建议: {suggestions[0]}")
        return suggestions
    
    def _get_latest_close(self, ts_code: str) -> Optional[float]:
        """获取最新收盘价"""
        c = self._conn.execute("""
            SELECT close, trade_date FROM valuation_data
            WHERE ts_code = ? ORDER BY trade_date DESC LIMIT 1
        """, (ts_code,)).fetchone()
        if c:
            return c[0]  # 直接访问元组元素
        return None
    
    def get_holdings(self) -> Dict[str, Dict]:
        """获取当前持仓"""
        rows = self._conn.execute("""
            SELECT * FROM holdings WHERE status = '持有中'
        """).fetchall()
        # 手动构建字典列表
        columns = [desc[1] for desc in self._conn.execute("PRAGMA table_info(holdings)").fetchall()]
        holdings_dict = {}
        for row in rows:
            row_dict = dict(zip(columns, row))
            if 'ts_code' in row_dict:
                holdings_dict[row_dict['ts_code']] = row_dict
        return holdings_dict
    
    def _calc_nav(self) -> float:
        """计算净值"""
        total = self.cash
        for p in self.get_holdings().values():
            mv = p['shares'] * (p.get('market_value') or 0)
            if not mv:
                c = self._get_latest_close(p['ts_code'])
                if c:
                    mv = p['shares'] * c
            total += mv
        return total
    
    def _record_nav(self, date: str, nav: float):
        """记录净值"""
        self._conn.execute("""
            INSERT OR REPLACE INTO portfolio_nav (trade_date, nav, cash, position_value)
            VALUES (?,?,?,?)
        """, (date, nav, self.cash, nav - self.cash))
        self._conn.commit()
    
    def get_performance(self) -> Dict:
        """获取绩效统计"""
        total_return = (self._calc_nav() - self.initial_cash) / self.initial_cash * 100
        closed = self._conn.execute("""
            SELECT * FROM holdings WHERE status = '已清仓'
        """).fetchall()
        # 手动构建字典列表
        columns = [desc[0] for desc in self._conn.execute("PRAGMA table_info(holdings)").fetchall()]
        trades = [dict(zip(columns, row)) for row in closed]
        wins = [t for t in trades if t['profit_pct'] is not None and t['profit_pct'] > 0]
        win_rate = len(wins) / len(trades) * 100 if trades else 0
        avg_win = sum(abs(t['profit_pct']) for t in wins) / len(wins) if wins else 0
        loss_trades = [t for t in trades if t['profit_pct'] is not None and t['profit_pct'] <= 0]
        avg_loss = sum(abs(t['profit_pct']) for t in loss_trades) / len(loss_trades) if loss_trades else 0
        return {
            'initial_cash': self.initial_cash,
            'current_nav': self._calc_nav(),
            'total_return_pct': round(total_return, 2),
            'total_trades': len(trades),
            'win_rate_pct': round(win_rate, 1),
            'avg_win_pct': round(avg_win, 2),
            'avg_loss_pct': round(avg_loss, 2),
        }
    
    def close(self):
        """关闭连接"""
        if self._conn:
            self._conn.close()


def init_portfolio_tables(cursor):
    """初始化持仓表和净值表"""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_code TEXT NOT NULL,
            name TEXT,
            strategy_type TEXT,
            buy_price REAL,
            shares INTEGER DEFAULT 0,
            stop_loss REAL,
            take_profit_price REAL,
            buy_date TEXT,
            status TEXT DEFAULT '持有中',
            market_value REAL,
            profit_pct REAL,
            close_price REAL,
            close_date TEXT,
            last_update TEXT,
            position_pct REAL,
            cost_value REAL,
            last_price REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_nav (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT UNIQUE,
            nav REAL,
            cash REAL,
            position_value REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trading_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT,
            ts_code TEXT,
            action TEXT,
            price REAL,
            shares INTEGER,
            amount REAL,
            reason TEXT
        )
    """)


if __name__ == "__main__":
    # 测试优化版模拟交易
    trader = PaperTraderV2()
    
    # 运行单日测试
    result = trader.run_day('2026-06-17')
    print(f"日期: {result['date']}")
    print(f"操作数: {len(result['actions'])}")
    print(f"净值: {result['nav']:,.0f}")
    print(f"现金: {result['cash']:,.0f}")
    print(f"持仓数: {result['holdings']}")
    
    for action in result['actions']:
        if action['action'] in ['建仓', '清仓', '减仓']:
            print(f"{action['ts_code']} {action['action']} {action['price']} {action['shares']} {action['amount']:,.0f} {action['reason']}")
    
    trader.close()