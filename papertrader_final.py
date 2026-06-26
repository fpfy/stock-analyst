"""
papertrader_final.py — 实盘模拟交易正式版
支持批量运行、连续交易、详细统计分析
主要功能：
1. 批量运行多天交易
2. 完整的持仓管理
3. 优化止损机制
4. 详细绩效分析
5. 交易记录追踪
"""
import sqlite3, logging, datetime, json
from typing import Optional, List, Dict, Tuple
from pathlib import Path
import pandas as pd
from dataclasses import dataclass
from enum import Enum

DB_PATH = Path('database/stock_analysis.db')
INITIAL_CASH = 1_000_000
MAX_POSITION = 0.15  # 单只股票最大仓位15%
MIN_POSITION = 0.05  # 最小仓位5%
BUY_COOLDOWN_DAYS = 5  # 清仓后冷却期，避免反复买卖

logger = logging.getLogger(__name__)

class TradeAction(Enum):
    BUY = "买入"
    SELL = "卖出"
    HOLD = "持有"

class StrategyType(Enum):
    GROWTH = "成长"
    VALUE = "价值"

@dataclass
class TradeRecord:
    date: str
    ts_code: str
    action: TradeAction
    price: float
    shares: int
    amount: float
    reason: str
    profit_pct: Optional[float] = None
    strategy_type: Optional[StrategyType] = None

class PaperTraderFinal:
    def __init__(self, initial_cash: float = INITIAL_CASH, db_path: str = None, conn=None):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.nav_history = []
        self.trade_records = []
        self.db_path = db_path or DB_PATH
        self._conn = None
        self._owns_conn = True

        if conn is not None:
            # 单连接共享模式：直接使用外部传入的连接
            self._conn = conn
            self._owns_conn = False
        else:
            self._connect_with_retry()

        # 创建绩效统计表
        self._create_performance_tables()

        print(f"模拟交易器初始化完成，初始资金: {initial_cash:,.0f}")
    
    def _connect_with_retry(self, max_retries=5, delay=1.0):
        """连接数据库，遇到锁定自动重试"""
        import time
        for attempt in range(max_retries):
            try:
                self._conn = sqlite3.connect(str(self.db_path), timeout=20)
                # 与全局 DatabaseManager 保持一致：WAL 模式 + busy_timeout
                self._conn.execute("PRAGMA journal_mode=WAL")
                self._conn.execute("PRAGMA foreign_keys=ON")
                self._conn.execute("PRAGMA busy_timeout=5000")
                return
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    print(f"[DB_LOCK] 连接数据库第{attempt+1}次重试: {e}")
                    time.sleep(delay)
                    delay *= 2
                else:
                    raise
    
    def _execute_with_retry(self, sql, params=(), max_retries=5, delay=0.5, fetch=None, label=""):
        """执行SQL，遇到锁定自动重试；可选直接fetchone/fetchall；label用于错误定位"""
        import time
        for attempt in range(max_retries):
            try:
                cursor = self._conn.execute(sql, params)
                try:
                    if fetch == 'one':
                        return cursor.fetchone()
                    if fetch == 'all':
                        return cursor.fetchall()
                    return cursor
                finally:
                    cursor.close()
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    print(f"[DB_LOCK] {label or sql[:40]}... 第{attempt+1}次重试")
                    time.sleep(delay)
                    delay *= 2
                else:
                    raise
            except Exception as e:
                raise
    
    def _commit_with_retry(self, max_retries=3, delay=0.5):
        """提交事务，遇到锁定自动重试"""
        import time
        for attempt in range(max_retries):
            try:
                self._conn.commit()
                return
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(delay)
                    delay *= 2
                else:
                    raise
    
    def _create_performance_tables(self):
        """创建绩效统计相关表"""
        self._execute_with_retry("""
            CREATE TABLE IF NOT EXISTS nav_history (
                date TEXT PRIMARY KEY,
                nav REAL,
                cash REAL,
                holdings_value REAL,
                positions_count INTEGER
            )
        """)

        self._execute_with_retry("""
            CREATE TABLE IF NOT EXISTS trade_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                ts_code TEXT,
                action TEXT,
                price REAL,
                shares INTEGER,
                amount REAL,
                reason TEXT,
                profit_pct REAL,
                strategy_type TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self._execute_with_retry("""
            CREATE TABLE IF NOT EXISTS performance_summary (
                date TEXT PRIMARY KEY,
                total_return REAL,
                win_rate REAL,
                total_trades INTEGER,
                avg_win REAL,
                avg_loss REAL,
                max_drawdown REAL,
                sharpe_ratio REAL,
                volatility REAL
            )
        """)
        
        self._commit_with_retry()
    
    def run_single_day(self, date: str) -> Dict:
        """运行一天的模拟交易（全程使用真实数据）"""
        print(f"\n=== 运行交易日: {date} ===")
        
        self._today = date
        actions = []
        
        # 1. 检查现有持仓止盈止损（使用真实收盘价）
        positions = self.get_holdings()
        print(f"当前持仓数: {len(positions)}")
        
        for p in positions.values():
            r = self._check_position_v2(p)
            if r:
                actions.append(r)
                print(f"{p['ts_code']} {r['action']} {r['shares']}股 @ {r['price']}")
        
        # 2. 刷新持仓市值（使用真实收盘价，确保 NAV 准确）
        self._update_holdings_market_value()
        
        # 3. 读取新的交易建议并建仓
        suggestions = self._get_today_suggestions()
        print(f"获取到 {len(suggestions)} 条建议")
        
        # 排除当日已清仓标的，避免当天卖出后立即买回
        closed_today = {a['ts_code'] for a in actions if a.get('action') == '清仓'}
        # 排除近期清仓标的，加入冷却期，避免反复快炒
        recent_closed = self._get_recently_closed_codes(date, BUY_COOLDOWN_DAYS)
        exclude_codes = closed_today | recent_closed
        
        if exclude_codes:
            print(f"冷却排除: {', '.join(sorted(exclude_codes))}")
        
        for suggestion in suggestions:
            ts_code = suggestion.get('ts_code')
            if ts_code in exclude_codes:
                continue
            # 计算最小买入金额
            min_amount = 100 * suggestion.get('current_price', 0)  # 最小1手
            if self.cash >= min_amount:
                r = self._execute_buy(suggestion)
                if r:
                    actions.append(r)
                    print(f"{r['ts_code']} 建仓 {r['shares']}股 @ {r['price']}")
        
        # 4. 记录当日净值（基于真实持仓市值）
        nav = self._calc_nav()
        self._record_nav(date, nav)
        
        # 5. 保存交易记录
        for action in actions:
            self._save_trade_record(action)
        
        result = {
            'date': date,
            'nav': nav,
            'cash': self.cash,
            'holdings_count': len(positions),
            'actions': actions,
            'trade_count': len(actions)
        }
        
        print(f"当日净值: {nav:,.0f}, 现金: {self.cash:,.0f}, 交易数: {len(actions)}")
        return result
    
    def run_batch_trading(self, start_date: str, end_date: str = None) -> List[Dict]:
        """批量运行多天交易"""
        if end_date is None:
            end_date = datetime.date.today().isoformat()
        
        print(f"\n=== 批量交易模拟 {start_date} 至 {end_date} ===")
        
        # 生成交易日期列表
        dates = self._generate_trading_dates(start_date, end_date)
        
        results = []
        for date in dates:
            try:
                result = self.run_single_day(date)
                results.append(result)
                
                # 每周输出一次进度
                if date.endswith('05') or date == end_date:  # 每月5号或最后一天
                    self._print_weekly_summary(results)
                    
            except Exception as e:
                print(f"日期 {date} 交易失败: {e}")
                continue
        
        # 最终统计
        self._generate_final_report(results)
        return results
    
    def _generate_trading_dates(self, start_date: str, end_date: str) -> List[str]:
        """生成交易日期列表"""
        start = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
        
        dates = []
        current = start
        
        # 跳过周末
        while current <= end:
            if current.weekday() < 5:  # 周一到周五
                dates.append(current.isoformat())
            current += datetime.timedelta(days=1)
        
        return dates
    
    def _print_weekly_summary(self, results: List[Dict]):
        """输出周度总结"""
        if not results:
            return
            
        latest = results[-1]
        total_return = (latest['nav'] - self.initial_cash) / self.initial_cash * 100
        
        print(f"\n--- 周度总结 ({latest['date']}) ---")
        print(f"当前净值: {latest['nav']:,.0f}")
        print(f"总收益率: {total_return:.2f}%")
        print(f"总交易数: {sum(r['trade_count'] for r in results)}")
        print(f"持仓数: {latest['holdings_count']}")
    
    def _get_today_suggestions(self) -> List[Dict]:
        """
        获取今日交易建议

        优先来源（按优先级）：
        1. selection_bridge.get_latest_selection() — 当日/最新选股结果
        2. trading_strategy 表 — 历史残留建议（降级方案）
        """
        suggestions = []

        # 1. 优先读取最新选股结果（与选股模块直接联动）
        try:
            from selection_bridge import get_latest_selection
            latest = get_latest_selection(limit=50)
            if latest:
                today = self._today
                # 只返回报告日期为今日或近3日内的建议（避免 stale 数据）
                from datetime import datetime, timedelta
                cutoff = (datetime.strptime(today, '%Y-%m-%d') - timedelta(days=3)).strftime('%Y-%m-%d')

                for s in latest:
                    report_date = s.get('report_date', '')
                    if report_date >= cutoff:
                        # 将 selection_bridge 格式转换为 papertrader 内部格式
                        suggestions.append({
                            'id': s.get('ts_code'),
                            'ts_code': s['ts_code'],
                            'action': 'BUY',
                            'current_price': s.get('current_price', 0),
                            'target_price': s.get('target_price', 0),
                            'stop_loss_price': s.get('stop_loss_price', 0),
                            'position_ratio': s.get('position_ratio', 0.15),
                            'priority': s.get('priority', 'MEDIUM'),
                            'reason': s.get('reason', ''),
                            'risk_grade': s.get('risk_grade', 'MEDIUM'),
                            'name': s.get('name', s['ts_code']),
                            'strategy_type': s.get('strategy_type', '成长'),
                        })

                if suggestions:
                    logger.info(f"[PAPER] 从 selection_bridge 读取 {len(suggestions)} 条选股建议 "
                                f"(报告日: {latest[0].get('report_date', 'N/A')})")
        except Exception as e:
            logger.debug(f"[PAPER] selection_bridge 读取失败，降级到 trading_strategy: {e}")

        # 2. 降级：读取 trading_strategy 表（兼容历史数据）
        if not suggestions:
            latest_report = self._execute_with_retry("""
                SELECT MAX(report_date) FROM trading_strategy WHERE report_date <= ?
            """, (self._today,), fetch='one')

            if latest_report and latest_report[0]:
                latest_date = latest_report[0]
                rows = self._execute_with_retry("""
                    SELECT id, ts_code, action, current_price, target_price, stop_loss_price,
                           position_ratio, priority, reason, risk_grade
                    FROM trading_strategy
                    WHERE report_date = ? AND action = 'BUY'
                    ORDER BY priority, id
                """, (latest_date,), fetch='all')

                for row in rows:
                    suggestions.append({
                        'id': row[0],
                        'ts_code': row[1],
                        'action': row[2],
                        'current_price': row[3],
                        'target_price': row[4],
                        'stop_loss_price': row[5],
                        'position_ratio': row[6],
                        'priority': row[7],
                        'reason': row[8],
                        'risk_grade': row[9],
                    })
                logger.info(f"[PAPER] 从 trading_strategy 读取 {len(suggestions)} 条建议 ({latest_date})")

        return suggestions
    
    def _execute_buy(self, suggestion: Dict) -> Optional[Dict]:
        """执行买入操作（使用统一风控参数）"""
        ts_code = suggestion['ts_code']
        # 优先使用 valuation_data 最新真实收盘价，而非建议表中的可能过期价格
        live_close = self._get_latest_close(ts_code)
        close = live_close if live_close and live_close > 0 else suggestion.get('current_price', 0)
        if not close:
            return None

        # 已持仓标的直接跳过，避免重复建仓
        if self._is_holding(ts_code):
            return None

        # 获取策略类型
        strategy_type = self._get_strategy_type(ts_code)
        if not strategy_type:
            return None

        # 使用统一风控配置（与 selection_bridge / backtest_v3 一致）
        from selection_bridge import RISK_CONFIG
        cfg = RISK_CONFIG.get(strategy_type.value, RISK_CONFIG['成长'])

        # 计算可买数量
        max_amount = self.initial_cash * cfg['max_position']
        risk_grade = suggestion.get('risk_grade', 'MEDIUM')
        if risk_grade == 'HIGH':
            max_amount *= 0.67  # 高风险股票仓位降至约10%
        elif risk_grade == 'LOW':
            max_amount *= 0.33  # 低风险股票仓位降至约5%

        # 计算实际买入金额和股数
        amount = min(self.cash, max_amount)
        shares = int(amount / close / 100) * 100  # 按手数买入

        if shares < 100:  # 至少1手
            return None

        cost = shares * close
        position_pct = cost / self.initial_cash

        # 使用统一风控参数计算止损价和止盈价
        stop_loss = close * (1 - cfg['stop_loss_pct'])
        take_profit = close * (1 + cfg['take_profit_pct'])

        # 记录持仓
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 初始化移动止盈参数
        peak_price = close  # 初始最高价为买入价
        trailing_activated = False  # 移动止盈是否已激活

        self._execute_with_retry("""
            INSERT OR REPLACE INTO holdings (ts_code, name, strategy_type, buy_price, shares,
                                 position_pct, cost_value, stop_loss, take_profit_price,
                                 buy_date, status, last_update, last_price, market_value,
                                 peak_price, trailing_stop, trailing_activated)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (ts_code, suggestion.get('name', ts_code), strategy_type.value,
              close, shares, position_pct, cost, stop_loss, take_profit,
              self._today, '持有中', now, close, shares * close,
              peak_price, stop_loss, int(trailing_activated)), label="insert_holdings")
        self._commit_with_retry()
        
        self.cash -= cost
        action = '建仓'
        return {'date': self._today, 'action': action, 'ts_code': ts_code,
                'price': close, 'shares': shares, 'amount': cost,
                'reason': f"自动建仓 | 建议优先级:{suggestion['priority']} | 风险等级:{suggestion['risk_grade']}"}
    
    def _check_position_v2(self, position: Dict) -> Optional[Dict]:
        """
        检查持仓止盈止损（动态止盈版）

        止盈优先级：
        1. 阶梯止盈：+30% 减仓50%，+50% 全清
        2. 移动止盈：盈利≥15%后激活，从最高点回撤8%触发
        3. 固定止盈：+15% 保底
        4. 固定止损：-7% 无条件执行

        全程使用 valuation_data 真实收盘价
        """
        ts_code = position['ts_code']
        strategy_type = position['strategy_type']
        buy_price = position['buy_price']
        current_price = self._get_latest_close(ts_code)

        if not current_price or current_price <= 0:
            return None

        # 计算当前盈亏
        profit_pct = (current_price - buy_price) / buy_price * 100

        # 获取统一风控参数（兼容 StrategyType 枚举和字符串）
        from selection_bridge import RISK_CONFIG
        strategy_key = strategy_type.value if hasattr(strategy_type, 'value') else strategy_type
        cfg = RISK_CONFIG.get(strategy_key, RISK_CONFIG['成长'])

        # 更新最高价和移动止盈状态
        peak_price = position.get('peak_price', buy_price) or buy_price
        trailing_activated = bool(position.get('trailing_activated', 0))

        if current_price > peak_price:
            peak_price = current_price
            # 检查是否达到移动止盈激活阈值
            activation_pct = cfg.get('trailing_activation_pct', 0.15) * 100
            if profit_pct >= activation_pct and not trailing_activated:
                trailing_activated = True
                # 激活时，将移动止盈线设为成本价+10%（锁定部分利润）
                new_trailing_stop = buy_price * 1.10
                self._execute_with_retry("""
                    UPDATE holdings SET peak_price=?, trailing_activated=1, trailing_stop=?
                    WHERE ts_code=? AND status='持有中'
                """, (peak_price, new_trailing_stop, ts_code), label="activate_trailing")
                self._commit_with_retry()
            else:
                # 更新最高价
                self._execute_with_retry("""
                    UPDATE holdings SET peak_price=?
                    WHERE ts_code=? AND status='持有中'
                """, (peak_price, ts_code), label="update_peak")
                self._commit_with_retry()

        # 止盈止损判断
        should_sell = False
        sell_reason = ""
        exit_price = current_price
        ladder_exit = False  # 是否阶梯止盈（部分减仓）

        # 优先级1：阶梯止盈
        ladder_1_pct = cfg.get('ladder_1_pct', 0.30) * 100
        ladder_2_pct = cfg.get('ladder_2_pct', 0.50) * 100

        if profit_pct >= ladder_2_pct:
            should_sell = True
            sell_reason = f"阶梯止盈2(+{ladder_2_pct:.0f}%)"
            exit_price = current_price
        elif profit_pct >= ladder_1_pct:
            # 阶梯止盈1：减仓50%，保留50%继续持有
            should_sell = True
            sell_reason = f"阶梯止盈1(+{ladder_1_pct:.0f}%)"
            ladder_exit = True
            exit_price = current_price

        # 优先级2：移动止盈（激活后从最高点回撤）
        elif trailing_activated:
            trailing_drop_pct = cfg.get('trailing_drop_pct', 0.08)
            drop_from_peak = (peak_price - current_price) / peak_price
            if drop_from_peak >= trailing_drop_pct:
                should_sell = True
                sell_reason = f"移动止盈(回撤{drop_from_peak*100:.1f}%)"
                exit_price = current_price

        # 优先级3：固定止盈（保底）
        take_profit_pct = cfg.get('take_profit_pct', 0.15) * 100
        if not should_sell and current_price >= position.get('take_profit_price', 0):
            should_sell = True
            sell_reason = f"固定止盈(+{take_profit_pct:.0f}%)"
            exit_price = current_price

        # 优先级4：固定止损（无条件执行）
        stop_loss_price = position.get('stop_loss', 0)
        if not should_sell and current_price <= stop_loss_price:
            should_sell = True
            sell_reason = "固定止损"
            exit_price = current_price

        # 优先级5：最大持仓时间（超期强制卖出）
        days_held = self._get_days_held(ts_code)
        max_hold_days = cfg.get('max_hold_days', 30)
        if not should_sell and days_held > max_hold_days:
            should_sell = True
            sell_reason = f"超期({days_held}天)"
            exit_price = current_price

        if should_sell:
            if ladder_exit:
                # 阶梯止盈1：减仓50%
                shares_to_sell = position['shares'] // 2
                if shares_to_sell < 100:
                    # 不足1手，全清
                    shares_to_sell = position['shares']
                    ladder_exit = False
            else:
                shares_to_sell = position['shares']

            amount = shares_to_sell * exit_price
            self.cash += amount

            if ladder_exit:
                # 减仓50%，更新持仓
                remaining_shares = position['shares'] - shares_to_sell
                new_market_value = remaining_shares * exit_price
                self._execute_with_retry("""
                    UPDATE holdings SET shares=?, market_value=?, last_price=?, last_update=?
                    WHERE ts_code=? AND status='持有中'
                """, (remaining_shares, new_market_value, exit_price,
                      self._today, ts_code), label="reduce_position")
                self._commit_with_retry()

                # 记录部分减仓交易
                return {
                    'date': self._today,
                    'action': '减仓',
                    'ts_code': ts_code,
                    'price': exit_price,
                    'shares': shares_to_sell,
                    'amount': amount,
                    'reason': sell_reason,
                    'profit_pct': profit_pct
                }
            else:
                # 全清仓
                self._execute_with_retry("""
                    UPDATE holdings SET status=?, profit_pct=?,
                                     last_update=?, last_price=?, market_value=?
                    WHERE ts_code=?
                """, ('已清仓', profit_pct,
                      self._today, exit_price, amount, ts_code), label="update_holdings")
                self._commit_with_retry()

                return {
                    'date': self._today,
                    'action': '清仓',
                    'ts_code': ts_code,
                    'price': exit_price,
                    'shares': shares_to_sell,
                    'amount': amount,
                    'reason': sell_reason,
                    'profit_pct': profit_pct
                }

        return None
    
    def _get_latest_close(self, ts_code: str) -> Optional[float]:
        """获取最新收盘价， valuation_data.trade_date 为 YYYYMMDD，需统一格式"""
        raw_today = self._today.replace('-', '') if isinstance(self._today, str) and '-' in self._today else self._today
        # 仅保留纯数字日期，防止格式污染导致比较错误
        today = ''.join(ch for ch in str(raw_today) if ch.isdigit())
        c = self._execute_with_retry("""
            SELECT close FROM valuation_data
            WHERE ts_code = ? AND trade_date <= ?
            ORDER BY trade_date DESC LIMIT 1
        """, (ts_code, today), fetch='one', label="latest_close")
        if c:
            return c[0]
        return None
    
    def _get_strategy_type(self, ts_code: str) -> Optional[StrategyType]:
        """获取股票策略类型"""
        row = self._execute_with_retry("""
            SELECT strategy_type FROM watch_list
            WHERE ts_code = ?
            ORDER BY updated_at DESC LIMIT 1
        """, (ts_code,), fetch='one', label="strategy_type")
        if row and row[0] in ('成长', '价值'):
            return StrategyType(row[0])
        return None
    
    def _get_days_held(self, ts_code: str) -> int:
        """获取持仓天数"""
        row = self._execute_with_retry("""
            SELECT buy_date FROM holdings WHERE ts_code = ? AND status = '持有中'
        """, (ts_code,), fetch='one', label="days_held")
        if row:
            buy_date_str = row[0]
            # 处理不同的日期格式
            if len(buy_date_str) == 10:  # YYYY-MM-DD
                buy_date = datetime.datetime.strptime(buy_date_str, '%Y-%m-%d').date()
            elif len(buy_date_str) == 8:  # YYYYMMDD
                buy_date = datetime.datetime.strptime(buy_date_str, '%Y%m%d').date()
            else:
                return 0
            
            current_date = datetime.datetime.strptime(self._today, '%Y-%m-%d').date()
            return (current_date - buy_date).days
        return 0
    
    def get_holdings(self) -> Dict[str, Dict]:
        """获取当前持仓"""
        rows = self._execute_with_retry("""
            SELECT * FROM holdings WHERE status = '持有中'
        """, fetch='all', label="get_holdings")
        
        columns = [desc[1] for desc in self._execute_with_retry("PRAGMA table_info(holdings)", fetch='all', label="holdings_info")]
        holdings_dict = {}
        for row in rows:
            row_dict = dict(zip(columns, row))
            if 'ts_code' in row_dict:
                holdings_dict[row_dict['ts_code']] = row_dict
        return holdings_dict
    
    def _is_holding(self, ts_code: str) -> bool:
        """判断当前是否已持仓"""
        return ts_code in self.get_holdings()
    
    def _get_recently_closed_codes(self, date: str, days: int) -> set:
        """获取最近 N 个交易日内已清仓的股票代码，用于建仓冷却"""
        rows = self._execute_with_retry("""
            SELECT ts_code, date FROM trade_records
            WHERE action = '清仓' AND date <= ?
            ORDER BY date DESC
        """, (date,), fetch='all', label="recent_closed")
        
        if not rows:
            return set()
        
        current = datetime.datetime.strptime(date, '%Y-%m-%d').date()
        closed = set()
        for ts_code, trade_date in rows:
            try:
                trade_dt = datetime.datetime.strptime(trade_date, '%Y-%m-%d').date()
            except ValueError:
                continue
            if (current - trade_dt).days <= days:
                closed.add(ts_code)
        return closed
    
    def _update_holdings_market_value(self):
        """
        使用 valuation_data 真实收盘价刷新所有持仓的 last_price 和 market_value
        
        这是模拟盘真实数据 core 逻辑：每日收盘后必须重新标定市值，
        避免使用买入日 stale 价格导致 NAV 失真。
        """
        positions = self.get_holdings()
        updated = 0
        for ts_code, p in positions.items():
            live_close = self._get_latest_close(ts_code)
            if live_close and live_close > 0:
                market_value = p['shares'] * live_close
                self._execute_with_retry("""
                    UPDATE holdings 
                    SET last_price = ?, market_value = ?, last_update = ?
                    WHERE ts_code = ? AND status = '持有中'
                """, (live_close, market_value, 
                      datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                      ts_code), label="update_market_value")
                updated += 1
            # 若 live_close 为 None，保留原有 market_value，不破坏数据
        
        if updated > 0:
            self._commit_with_retry()
            logger.debug(f"[PAPER] 刷新持仓市值: {updated}/{len(positions)} 只使用真实收盘价")
    
    def _calc_nav(self) -> float:
        """计算当前净值（基于真实持仓市值）"""
        holdings_value = sum(h['market_value'] for h in self.get_holdings().values())
        return self.cash + holdings_value
    
    def _record_nav(self, date: str, nav: float):
        """记录净值"""
        holdings_value = sum(h['market_value'] for h in self.get_holdings().values())
        positions_count = len(self.get_holdings())
        
        self._execute_with_retry("""
            INSERT OR REPLACE INTO nav_history (date, nav, cash, holdings_value, positions_count)
            VALUES (?,?,?,?,?)
        """, (date, nav, self.cash, holdings_value, positions_count))
        
        self.nav_history.append({'date': date, 'nav': nav})
    
    def _save_trade_record(self, action: Dict):
        """保存交易记录，带幂等保护，避免同一笔交易重复写入"""
        # 先检查是否已存在相同记录
        existing = self._execute_with_retry("""
            SELECT id FROM trade_records
            WHERE date = ? AND ts_code = ? AND action = ? AND price = ? AND shares = ?
        """, (action['date'], action['ts_code'], action['action'],
              action['price'], action['shares']), fetch='one', label="check_existing_trade")
        
        if existing:
            # 已存在相同记录，跳过写入
            return
        
        self._execute_with_retry("""
            INSERT INTO trade_records (date, ts_code, action, price, shares, amount, reason, profit_pct)
            VALUES (?,?,?,?,?,?,?,?)
        """, (action['date'], action['ts_code'], action['action'], 
              action['price'], action['shares'], action['amount'], 
              action['reason'], action.get('profit_pct')))
        
        self.trade_records.append(action)
    
    def get_performance_summary(self) -> Dict:
        """获取绩效统计"""
        if not self.nav_history:
            return {}
        
        # 计算总收益率
        total_return = (self._calc_nav() - self.initial_cash) / self.initial_cash * 100
        
        # 计算交易统计
        trades = self._execute_with_retry("""
            SELECT * FROM trade_records WHERE action IN ('买入', '清仓')
        """, fetch='all', label="perf_trades")
        
        if trades:
            # 将元组转换为字典
            columns = [desc[1] for desc in self._execute_with_retry("PRAGMA table_info(trade_records)", fetch='all', label="perf_info")]
            trade_dicts = [dict(zip(columns, trade)) for trade in trades]
            
            wins = [t for t in trade_dicts if t['profit_pct'] is not None and t['profit_pct'] > 0]
            win_rate = len(wins) / len(trade_dicts) * 100 if trade_dicts else 0
            
            avg_win = sum(abs(t['profit_pct']) for t in wins) / len(wins) if wins else 0
            loss_trades = [t for t in trade_dicts if t['profit_pct'] is not None and t['profit_pct'] <= 0]
            avg_loss = sum(abs(t['profit_pct']) for t in loss_trades) / len(loss_trades) if loss_trades else 0
        else:
            win_rate = 0
            avg_win = 0
            avg_loss = 0
        
        # 计算最大回撤
        max_drawdown = self._calculate_max_drawdown()
        
        # 计算夏普比率
        sharpe_ratio = self._calculate_sharpe_ratio()
        
        # 计算波动率
        volatility = self._calculate_volatility()
        
        return {
            'initial_cash': self.initial_cash,
            'current_nav': self._calc_nav(),
            'total_return_pct': round(total_return, 2),
            'win_rate_pct': round(win_rate, 1),
            'avg_win_pct': round(avg_win, 2),
            'avg_loss_pct': round(avg_loss, 2),
            'max_drawdown_pct': round(max_drawdown, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'volatility_pct': round(volatility, 2),
            'total_trades': len(trades),
            'active_positions': len(self.get_holdings())
        }
    
    def _calculate_max_drawdown(self) -> float:
        """计算最大回撤"""
        if not self.nav_history:
            return 0
        
        navs = [h['nav'] for h in self.nav_history]
        peak = navs[0]
        max_dd = 0
        
        for nav in navs:
            if nav > peak:
                peak = nav
            dd = (peak - nav) / peak * 100
            if dd > max_dd:
                max_dd = dd
        
        return max_dd
    
    def _calculate_sharpe_ratio(self) -> float:
        """计算夏普比率"""
        if len(self.nav_history) < 2:
            return 0
        
        # 计算日收益率
        returns = []
        for i in range(1, len(self.nav_history)):
            prev_nav = self.nav_history[i-1]['nav']
            curr_nav = self.nav_history[i]['nav']
            if prev_nav > 0:
                returns.append((curr_nav - prev_nav) / prev_nav)
        
        if not returns:
            return 0
        
        import statistics
        avg_return = statistics.mean(returns)
        std_return = statistics.stdev(returns) if len(returns) > 1 else 0
        
        if std_return == 0:
            return 0
        
        # 年化夏普比率
        return avg_return / std_return * 252 ** 0.5
    
    def _calculate_volatility(self) -> float:
        """计算波动率"""
        if len(self.nav_history) < 2:
            return 0
        
        # 计算日收益率
        returns = []
        for i in range(1, len(self.nav_history)):
            prev_nav = self.nav_history[i-1]['nav']
            curr_nav = self.nav_history[i]['nav']
            if prev_nav > 0:
                returns.append((curr_nav - prev_nav) / prev_nav)
        
        if not returns:
            return 0
        
        import statistics
        std_return = statistics.stdev(returns) if len(returns) > 1 else 0
        
        # 年化波动率
        return std_return * 252 ** 0.5 * 100
    
    def _generate_final_report(self, results: List[Dict]):
        """生成最终报告"""
        if not results:
            print("没有交易记录")
            return
        
        # 生成绩效报告
        perf = self.get_performance_summary()
        
        print("\n" + "="*60)
        print("              最终交易绩效报告")
        print("="*60)
        print(f"交易周期: {results[0]['date']} 至 {results[-1]['date']}")
        print(f"初始资金: {perf['initial_cash']:,.0f}")
        print(f"当前净值: {perf['current_nav']:,.0f}")
        print(f"总收益率: {perf['total_return_pct']}%")
        print(f"总交易数: {perf['total_trades']}")
        print(f"胜率: {perf['win_rate_pct']}%")
        print(f"平均盈利: {perf['avg_win_pct']}%")
        print(f"平均亏损: {perf['avg_loss_pct']}%")
        print(f"最大回撤: {perf['max_drawdown_pct']}%")
        print(f"夏普比率: {perf['sharpe_ratio']}")
        print(f"波动率: {perf['volatility_pct']}%")
        print(f"当前持仓: {perf['active_positions']}只")
        print("="*60)
        
        # 保存报告到文件
        self._save_performance_report(perf, results)
        
        # 生成图表
        self._generate_performance_charts()
    
    def _save_performance_report(self, perf: Dict, results: List[Dict]):
        """保存绩效报告"""
        report = {
            'summary': perf,
            'daily_results': results,
            'trade_records': self.trade_records,
            'generated_at': datetime.datetime.now().isoformat()
        }
        
        report_path = Path('reports') / f'papertrader_final_{datetime.date.today().isoformat()}.json'
        report_path.parent.mkdir(exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"详细报告已保存至: {report_path}")
    
    def _generate_performance_charts(self):
        """生成绩效图表（简化版，不依赖matplotlib）"""
        try:
            # 生成简单的文本图表
            if not self.nav_history:
                return
            
            print("\n" + "="*60)
            print("              净值走势图表")
            print("="*60)
            
            # 计算净值变化
            dates = [r['date'] for r in self.nav_history]
            navs = [r['nav'] for r in self.nav_history]
            
            # 找到最大最小值用于缩放
            min_nav = min(navs)
            max_nav = max(navs)
            nav_range = max_nav - min_nav
            
            if nav_range == 0:
                nav_range = 1
            
            # 生成文本图表
            chart_height = 20
            for i in range(chart_height):
                line = ""
                threshold = max_nav - (i / chart_height) * nav_range
                threshold_min = threshold - (nav_range / chart_height)
                
                for j, nav in enumerate(navs):
                    if threshold_min <= nav <= threshold:
                        line += "█"
                    else:
                        line += " "
                
                line += f" {dates[len(navs)-1-chart_height+i+1] if i < len(dates) else ''}"
                print(line)
            
            print(f"初始资金: {self.initial_cash:,.0f}")
            print(f"最高净值: {max_nav:,.0f}")
            print(f"最低净值: {min_nav:,.0f}")
            print("="*60)
            
        except Exception as e:
            print(f"生成图表时出错: {e}")
    
    def get_current_positions(self) -> List[Dict]:
        """获取当前持仓详情"""
        holdings = self.get_holdings()
        positions = []
        
        for ts_code, pos in holdings.items():
            current_price = self._get_latest_close(ts_code)
            if current_price:
                profit_pct = (current_price - pos['buy_price']) / pos['buy_price'] * 100
                positions.append({
                    'ts_code': ts_code,
                    'name': pos.get('name', ts_code),
                    'strategy_type': pos['strategy_type'],
                    'buy_price': pos['buy_price'],
                    'current_price': current_price,
                    'shares': pos['shares'],
                    'profit_pct': profit_pct,
                    'stop_loss': pos['stop_loss'],
                    'take_profit': pos['take_profit_price']
                })
        
        return positions
    
    def export_trade_history(self, filename: str = None):
        """导出交易历史"""
        if filename is None:
            filename = f'trade_history_{datetime.date.today().isoformat()}.csv'
        
        df = pd.DataFrame(self.trade_records)
        df.to_csv(filename, index=False, encoding='utf-8')
        print(f"交易历史已导出至: {filename}")
    
    def close(self):
        """关闭连接；若为外部共享连接，则只做 commit，不关闭"""
        try:
            if self._conn is not None:
                self._commit_with_retry()
                if getattr(self, '_owns_conn', True):
                    # 仅当连接由本实例创建时才做 checkpoint 并关闭
                    try:
                        self._execute_with_retry("PRAGMA wal_checkpoint(TRUNCATE)")
                    except Exception:
                        pass
                    self._conn.close()
        except Exception:
            pass
        self._conn = None
        print("模拟交易器已关闭")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='实盘模拟交易正式版')
    parser.add_argument('--start-date', type=str, default='2026-06-01', 
                       help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str,
                       help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--cash', type=float, default=INITIAL_CASH,
                       help='初始资金')
    parser.add_argument('--single-day', type=str,
                       help='单日交易 (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    # 创建模拟交易器
    trader = PaperTraderFinal(initial_cash=args.cash)
    
    try:
        if args.single_day:
            # 单日交易
            result = trader.run_single_day(args.single_day)
            print(f"单日交易完成: {result}")
        else:
            # 批量交易
            result = trader.run_batch_trading(args.start_date, args.end_date)
            print(f"批量交易完成，共 {len(result)} 个交易日")
        
        # 输出最终统计
        perf = trader.get_performance_summary()
        print("\n最终绩效:")
        for key, value in perf.items():
            print(f"{key}: {value}")
        
        return {
            'date': args.single_day or args.start_date,
            'result': result,
            'performance': perf
        }
        
    except Exception as e:
        print(f"交易过程中出错: {e}")
        return {
            'date': args.single_day or args.start_date,
            'error': str(e),
            'performance': None
        }
    finally:
        trader.close()

if __name__ == "__main__":
    main()