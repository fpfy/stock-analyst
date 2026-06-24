"""
PaperTrader.py — 模拟账户
基于 trading_strategy + valuation_data + holdings 实现全流程纸面交易。
"""
import sqlite3, logging, datetime
from typing import Optional, List, Dict
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / 'database' / 'stock_analysis.db'
logger = logging.getLogger('papertrader')


class PaperTrader:
    """模拟账户：虚拟资金、虚拟下单、自动止盈止损、绩效统计"""

    def __init__(self, initial_cash: float = 1_000_000,
                 max_single_position: float = 0.30,
                 max_total_position: float = 0.80):
        self.cash = initial_cash
        self.initial_cash = initial_cash
        self.max_single = max_single_position
        self.max_total = max_total_position
        self._conn = sqlite3.connect(DB_PATH)
        self._conn.row_factory = sqlite3.Row
        self._today = datetime.date.today().isoformat()

    # -------------------------- 核心：检查当日交易建议并执行 --------------------------

    def run_day(self, trade_date: Optional[str] = None) -> Dict:
        """执行单日模拟交易"""
        if trade_date:
            self._today = trade_date
        actions = []
        # 1) 处理当日 BUY 建议
        suggestions = self._get_today_suggestions()
        for s in suggestions:
            if s['action'] == 'BUY' and s['ts_code'] not in self.get_holdings():
                r = self._try_buy(s)
                if r:
                    actions.append(r)
        # 2) 检查现有持仓止盈止损
        positions = self.get_holdings()
        for p in positions.values():
            r = self._check_position(p)
            if r:
                actions.append(r)
        # 3) 生成绩效快照
        nav = self._calc_nav()
        self._record_nav(self._today, nav)
        return {'date': self._today, 'actions': actions, 'nav': nav,
                'cash': self.cash, 'holdings': len(positions),
                'total_position_value': nav - self.cash}

    # -------------------------- 买入 --------------------------

    def _try_buy(self, suggestion: Dict) -> Optional[Dict]:
        ts_code = suggestion['ts_code']
        close = self._get_latest_close(ts_code)
        if close is None or close <= 0:
            logger.warning(f'无法获取 {ts_code} 收盘价，跳过')
            return None
        # 建议仓位
        pos_ratio = float(suggestion.get('position_ratio', 0.15) or 0.15)
        if suggestion['priority'] == 'HIGH':
            pass
        elif suggestion['priority'] == 'MEDIUM':
            pos_ratio = min(pos_ratio, 0.10)
        else:
            pos_ratio = min(pos_ratio, 0.05)

        # 现有限额
        max_single_amount = self.cash * self.max_single
        target_amount = self.cash * pos_ratio
        use_amount = min(target_amount, max_single_amount)

        # 总仓位上限
        current_total = sum(p.get('market_value') or 0 for p in self.get_holdings().values())
        total_limit = self.initial_cash * self.max_total
        if current_total + use_amount > total_limit:
            use_amount = max(0, total_limit - current_total)
        if use_amount < 500:  # 最低买入额
            return None

        shares = int(use_amount / close / 100) * 100  # 整手
        if shares < 100:
            return None
        cost = shares * close
        self.cash -= cost

        stop_loss = suggestion.get('stop_loss_price')
        take_profit = suggestion.get('target_price')
        # 读取策略类型（来自 watch_list，兜底“价值”）
        strategy_type = self._get_strategy_type(ts_code) or '价值'
        if strategy_type not in ('成长', '价值'):
            strategy_type = '价值'

        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cost_value = round(close * shares, 2)
        position_pct = round(cost_value / self.initial_cash, 4)
        self._conn.execute("""
            INSERT INTO holdings (ts_code, name, industry, strategy_type, buy_price, shares,
                                 position_pct, cost_value, stop_loss, take_profit_price,
                                 buy_date, status, last_update)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,'持有中',?)
            ON CONFLICT(ts_code) DO UPDATE SET
                buy_price=excluded.buy_price,
                shares=excluded.shares,
                position_pct=excluded.position_pct,
                cost_value=excluded.cost_value,
                stop_loss=excluded.stop_loss,
                take_profit_price=excluded.take_profit_price,
                buy_date=excluded.buy_date,
                last_update=excluded.last_update
        """, (ts_code, suggestion.get('name', ts_code), '', strategy_type,
              close, shares, position_pct, cost_value, stop_loss, take_profit, self._today, now))
        self.cash -= cost
        action = '建仓'
        return {'date': self._today, 'action': action, 'ts_code': ts_code,
                'price': close, 'shares': shares, 'amount': cost,
                'reason': f"自动建仓 | 建议优先级:{suggestion['priority']}"}

    def _get_strategy_type(self, ts_code: str) -> Optional[str]:
        row = self._conn.execute("""
            SELECT strategy_type FROM watch_list
            WHERE ts_code = ?
            ORDER BY updated_at DESC LIMIT 1
        """, (ts_code,)).fetchone()
        if row and row['strategy_type'] in ('成长', '价值'):
            return row['strategy_type']
        return None

    # -------------------------- 持仓检查（止盈止损） --------------------------

    def _check_position(self, position: Dict) -> Optional[Dict]:
        ts_code = position['ts_code']
        close = self._get_latest_close(ts_code)
        if close is None:
            return None
        buy_price = position['buy_price']
        take_profit = position.get('take_profit_price')
        stop_loss = position.get('stop_loss')
        shares = position['shares']
        market_value = shares * close
        pnl_pct = round((close - buy_price) / buy_price * 100, 2)

        action = None
        reason = ''
        if take_profit and close >= take_profit:
            action = 'SELL'
            reason = f'止盈触发 {take_profit:.2f}，盈利{pnl_pct:.1f}%'
        elif stop_loss and close <= stop_loss:
            action = 'SELL'
            reason = f'止损触发 {stop_loss:.2f}，亏损{pnl_pct:.1f}%'
        elif position['strategy_type'] == '成长' and pnl_pct <= -8:
            action = 'SELL'
            reason = f'成长股亏损 {pnl_pct:.1f}% 超过预警线'
        elif position['strategy_type'] == '价值' and pnl_pct <= -15:
            action = 'SELL'
            reason = f'价值股亏损 {pnl_pct:.1f}% 超过预警线'
        elif pnl_pct >= 30:
            action = 'SELL'
            reason = f'累计盈利 {pnl_pct:.1f}%，锁定利润'

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
        # 更新市值和最后价格
        self._conn.execute("""
            UPDATE holdings SET last_update=?, last_price=? WHERE ts_code=?
        """, (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), close, ts_code))
        self._conn.commit()
        return None

    # -------------------------- 数据获取 --------------------------

    def _get_today_suggestions(self) -> List[Dict]:
        # 取最近一个报告日的所有 BUY
        latest_report = self._conn.execute("""
            SELECT MAX(report_date) FROM trading_strategy WHERE report_date <= ?
        """, (self._today,)).fetchone()[0]
        if not latest_report:
            return []
        rows = self._conn.execute("""
            SELECT * FROM trading_strategy
            WHERE report_date = ? AND action = 'BUY'
        """, (latest_report,)).fetchall()
        return [dict(r) for r in rows]

    def _get_latest_close(self, ts_code: str) -> Optional[float]:
        c = self._conn.execute("""
            SELECT close, trade_date FROM valuation_data
            WHERE ts_code = ? ORDER BY trade_date DESC LIMIT 1
        """, (ts_code,)).fetchone()
        if c:
            return c['close']
        return None

    def get_holdings(self) -> Dict[str, Dict]:
        rows = self._conn.execute("""
            SELECT * FROM holdings WHERE status = '持有中'
        """).fetchall()
        return {r['ts_code']: dict(r) for r in rows}

    # -------------------------- 绩效统计 --------------------------

    def _calc_nav(self) -> float:
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
        self._conn.execute("""
            INSERT OR REPLACE INTO portfolio_nav (trade_date, nav, cash, position_value)
            VALUES (?,?,?,?)
        """, (date, nav, self.cash, nav - self.cash))
        self._conn.commit()

    def get_performance(self) -> Dict:
        total_return = (self._calc_nav() - self.initial_cash) / self.initial_cash * 100
        closed = self._conn.execute("""
            SELECT * FROM holdings WHERE status = '已清仓'
        """).fetchall()
        trades = [dict(r) for r in closed]
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
            last_update TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_nav (
            trade_date TEXT PRIMARY KEY,
            nav REAL,
            cash REAL,
            position_value REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_holdings_ts ON holdings (ts_code)")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    conn = sqlite3.connect(DB_PATH)
    init_portfolio_tables(conn)
    conn.close()

    trader = PaperTrader()
    print('--- 第1天 ----')
    r1 = trader.run_day('2026-06-17')
    print(r1)
    trader.close()
