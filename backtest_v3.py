"""
V3双体系策略回测引擎
基于现有财务数据4期 + 估值数据118交易日

回测逻辑：
  1. 在每个报告期发布日（按end_date顺序），只用当时已知的数据选股
  2. 持有30个交易日（约1.5个月）
  3. 计算收益、胜率、最大回撤、夏普比率

支持：季度回测 + 年度汇总
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from statistics import mean
from decimal import Decimal

logger = logging.getLogger(__name__)

# ============================================================
# 回测配置
# ============================================================
BACKTEST_CONFIG = {
    'hold_days': 30,            # 每批持有交易日数
    'initial_capital': 1_000_000,  # 初始资金 100万
    'commission_rate': 0.0015,     # 佣金 0.15%（买卖各一程）
    'stamp_tax': 0.001,            # 印花税 0.1%（仅卖出）
    'slippage': 0.001,             # 滑点估计 0.1%
    'max_position_pct': 0.40,      # 单股上限 40%（分散）
    'value_stop_loss': 0.15,      # 价值止损线（正数，回撤15%触发）
    'growth_stop_loss': 0.07,     # 成长止损线（正数，回撤7%触发）
    'benchmark': '000001.SH',      # 基准指数
}


class BacktestEngine:
    """V3双体系回测引擎"""

    def __init__(self, db_path, strategy_fn=None, conn=None):
        self.db_path = db_path
        if conn is not None:
            # 单连接共享模式：直接使用外部传入的连接，不关闭
            self.conn = conn
            self._owns_conn = False
        else:
            self.conn = sqlite3.connect(db_path)
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA busy_timeout=10000")
            self._owns_conn = True
        self.cursor = self.conn.cursor()
        # 外部选股函数（来自 selection_bridge），若提供则与选股模块联动
        self.strategy_fn = strategy_fn or self._default_strategy
        self.results = []

    def _default_strategy(self, cursor, ts_code):
        """
        简化版策略（模拟V3选股逻辑）：
        返回 True/False 表示通过筛选
        """
        cursor.execute("""
            SELECT f.roe, f.revenue_yoy, f.net_profit_yoy, f.debt_ratio,
                   v.close, v.pe, v.pb, v.dv_ttm
            FROM financial_data f
            JOIN valuation_data v ON f.ts_code = v.ts_code
            WHERE f.ts_code = ?
              AND v.trade_date = (SELECT MAX(trade_date) FROM valuation_data WHERE ts_code = ?)
              AND f.end_date = (SELECT MAX(end_date) FROM financial_data WHERE ts_code = ?)
            LIMIT 1
        """, (ts_code, ts_code, ts_code))
        r = cursor.fetchone()
        if not r:
            return False
        roe, rev_yoy, profit_yoy, debt, close, pe, pb, dv = r

        # 价值条件
        if roe >= 10 and pe and 5 <= pe <= 20 and pb <= 3 and debt < 50:
            return True
        # 成长条件
        if roe >= 15 and rev_yoy and rev_yoy >= 15 and profit_yoy and profit_yoy >= 15:
            return True
        return False

    def _guess_strategy_type(self, cursor, ts_code):
        """
        推断股票策略类型（用于回测中的止盈止损参数选择）
        优先从 watch_list 读取，其次从 trading_strategy 读取，最后根据 ROE/营收增速推断
        """
        # 1. 优先从 watch_list 读取
        cursor.execute("""
            SELECT strategy_type FROM watch_list
            WHERE ts_code = ?
            ORDER BY updated_at DESC LIMIT 1
        """, (ts_code,))
        row = cursor.fetchone()
        if row and row[0] in ('成长', '价值'):
            return row[0]

        # 2. 从 trading_strategy 读取
        cursor.execute("""
            SELECT ts_code FROM trading_strategy
            WHERE ts_code = ? AND action = 'BUY'
            LIMIT 1
        """, (ts_code,))
        if cursor.fetchone():
            # 如果有 trading_strategy 记录，尝试从 selection_bridge 获取
            try:
                from selection_bridge import get_latest_selection
                latest = get_latest_selection(limit=100)
                for s in latest:
                    if s['ts_code'] == ts_code:
                        return s.get('strategy_type', '成长')
            except Exception:
                pass

        # 3. 根据财务数据推断（成长股通常 ROE>=15% 且营收增速>=15%）
        cursor.execute("""
            SELECT f.roe, f.revenue_yoy
            FROM financial_data f
            WHERE f.ts_code = ?
              AND f.end_date = (SELECT MAX(end_date) FROM financial_data WHERE ts_code = ?)
            LIMIT 1
        """, (ts_code, ts_code))
        row = cursor.fetchone()
        if row:
            roe, rev_yoy = row
            if roe is not None and rev_yoy is not None and roe >= 15 and rev_yoy >= 15:
                return '成长'
            return '价值'

        return '成长'  # 默认成长

    def get_all_report_periods(self):
        """按时间顺序获取可用的财务报告期（只保留2023Q1及以后）"""
        self.cursor.execute("""
            SELECT DISTINCT end_date, COUNT(DISTINCT ts_code) as stock_count
            FROM financial_data
            WHERE end_date >= '20230101'
            GROUP BY end_date
            ORDER BY end_date
        """)
        return [r[0] for r in self.cursor.fetchall()]

    def get_valuation_dates(self):
        """获取所有估值交易日"""
        self.cursor.execute("""
            SELECT DISTINCT trade_date FROM valuation_data ORDER BY trade_date ASC
        """)
        return [r[0] for r in self.cursor.fetchall()]

    def run_quarterly_backtest(self):
        """
        按季度回测
        For each report period:
          1. 用该report期财务数据选股
          2. 选股当日价格作为买入价（用该报告期后第一个估值日）
          3. 持有30天后卖出
          4. 记录每只股票的收益
        """
        periods = self.get_all_report_periods()
        val_dates = self.get_valuation_dates()
        cfg = BACKTEST_CONFIG

        logger.info("=" * 70)
        logger.info("🚀 开始季度回测")
        logger.info("=" * 70)
        logger.info(f"报告期数量: {len(periods)}")
        logger.info(f"报告期: {periods}")
        logger.info(f"估值交易日数: {len(val_dates)}")

        quarterly_results = []

        for i, period in enumerate(periods):
            # 每个报告期的选股日：用该期后最近的估值日（假设季后T+1月有数据）
            # 这里简化：用该报告期之后第一个估值日模拟公布日
            eligible_stocks = self._select_stocks_at_period(period, val_dates, strategy_fn=self.strategy_fn)

            if not eligible_stocks:
                logger.info(f"[{period}] 选股0只，跳过")
                quarterly_results.append({
                    'period': period, 'date': '-', 'selected': 0, 'avg_return': 0,
                    'win_rate': 0, 'best': '-', 'best_ret': 0,
                    'worst': '-', 'worst_ret': 0,
                    'benchmark_ret': 0, 'stop_loss_count': 0
                })
                continue

            # 买入日：用该报告期后第一个估值日（或直接用日期本身）
            # valuation_data中没有end_date，用MAX(trade_date) < end_date+40天
            buy_date = self._find_buy_date(period, val_dates)
            if not buy_date:
                logger.warning(f"[{period}] 无估值数据，跳过")
                continue

            # 卖出日：买入后 hold_days 个交易日
            buy_idx = val_dates.index(buy_date)
            sell_idx = min(buy_idx + cfg['hold_days'], len(val_dates) - 1)
            sell_date = val_dates[sell_idx]

            logger.info(f"\n{'='*60}")
            logger.info(f"[{period}] 买入日: {buy_date} → 卖出日: {sell_date}")
            logger.info(f"[{period}] 候选股数: {len(eligible_stocks)}")

            # 计算每只股票的收益（支持真实触发价止损）
            stock_returns = []
            for ts_code in eligible_stocks:
                buy_price = self._get_price_at(ts_code, buy_date)
                sell_price = self._get_price_at(ts_code, sell_date)

                if not buy_price or not sell_price or buy_price <= 0 or sell_price <= 0:
                    continue

                # 先取持有期内价格序列，用于检测首次触发日
                price_series = self._get_price_series(ts_code, buy_date, val_dates[sell_idx])

                # 默认：持有到期
                exit_price = sell_price
                exit_date = sell_date
                exit_reason = None
                stopped = False

                if price_series:
                    # 确定该股票的风控参数（从 selection_bridge 统一读取）
                    from selection_bridge import RISK_CONFIG
                    stock_type = self._guess_strategy_type(self.cursor, ts_code)
                    stock_cfg = RISK_CONFIG.get(stock_type, RISK_CONFIG['价值'])

                    # 优先级1：移动止盈（最优先，让利润奔跑）
                    trailing_idx = self._find_trailing_stop_idx(price_series, stock_cfg)
                    if trailing_idx is not None:
                        exit_price = price_series[trailing_idx][1]
                        exit_date = price_series[trailing_idx][0]
                        exit_reason = '移动止盈'
                        stopped = True

                    # 优先级2：阶梯止盈（固定目标盈利触发）
                    elif (ladder_idx := self._find_profit_threshold_idx(price_series, stock_cfg.get('ladder_1_pct', 0.30))) is not None:
                        exit_price = price_series[ladder_idx][1]
                        exit_date = price_series[ladder_idx][0]
                        exit_reason = '阶梯止盈1(+30%)'
                        stopped = True
                    elif (ladder_idx := self._find_profit_threshold_idx(price_series, stock_cfg.get('ladder_2_pct', 0.50))) is not None:
                        exit_price = price_series[ladder_idx][1]
                        exit_date = price_series[ladder_idx][0]
                        exit_reason = '阶梯止盈2(+50%)'
                        stopped = True

                    # 优先级3：固定止损（保底）
                    else:
                        trigger_idx = None
                        stop_reason_label = ''
                        for label, threshold in [('成长止损', stock_cfg['stop_loss_pct']), ('价值止损', stock_cfg['stop_loss_pct'])]:
                            idx = self._find_first_threshold_idx(price_series, threshold)
                            if idx is not None:
                                if trigger_idx is None or idx < trigger_idx:
                                    trigger_idx = idx
                                    stop_reason_label = label

                        if trigger_idx is not None:
                            exit_price = price_series[trigger_idx][1]
                            exit_date = price_series[trigger_idx][0]
                            exit_reason = stop_reason_label
                            stopped = True

                # 含交易成本计算真实收益
                buy_cost = buy_price * (1 + cfg['commission_rate'] + cfg['slippage'])
                sell_revenue = exit_price * (1 - cfg['commission_rate'] - cfg['stamp_tax'] - cfg['slippage'])
                net_return = (sell_revenue - buy_cost) / buy_cost

                stock_returns.append({
                    'ts_code': ts_code,
                    'buy_price': buy_price,
                    'sell_price': exit_price,
                    'net_return': net_return,
                    'hold_days': sell_idx - buy_idx,
                    'stopped': stopped,
                    'stop_reason': exit_reason,
                    'max_dd': self._calc_max_drawdown(ts_code, buy_date, buy_idx, sell_idx, val_dates)
                })

            if not stock_returns:
                continue

            returns = [s['net_return'] for s in stock_returns]
            avg_ret = mean(returns)
            win_rate = sum(1 for r in returns if r > 0) / len(returns) * 100
            best = max(stock_returns, key=lambda x: x['net_return'])
            worst = min(stock_returns, key=lambda x: x['net_return'])

            # 基准收益（大盘）
            bench_buy = self._get_price_at(cfg['benchmark'], buy_date)
            bench_sell = self._get_price_at(cfg['benchmark'], sell_date)
            bench_ret = (bench_sell - bench_buy) / bench_buy if bench_buy else 0

            result = {
                'period': period,
                'date': buy_date,
                'selected': len(stock_returns),
                'avg_return': avg_ret,
                'win_rate': win_rate,
                'best': best['ts_code'],
                'best_ret': best['net_return'],
                'worst': worst['ts_code'],
                'worst_ret': worst['net_return'],
                'benchmark_ret': bench_ret,
                'stop_loss_count': sum(1 for s in stock_returns if s['stopped']),
                'stocks': stock_returns
            }
            quarterly_results.append(result)

            logger.info(f"  选中 {len(stock_returns)} 只")
            logger.info(f"  组合平均收益: {avg_ret*100:+.2f}% | 胜率: {win_rate:.1f}%")
            logger.info(f"  最佳: {best['ts_code']} ({best['net_return']*100:+.2f}%)")
            logger.info(f"  最差: {worst['ts_code']} ({worst['net_return']*100:+.2f}%)")
            logger.info(f"  基准: {bench_ret*100:+.2f}% | 止损: {result['stop_loss_count']}次")

        self.results = quarterly_results
        return quarterly_results

    def _select_stocks_at_period(self, period, val_dates=None, strategy_fn=None):
        """
        在给定报告期选择符合条件的股票

        Args:
            period: 报告期
            val_dates: 估值交易日列表
            strategy_fn: 外部选股函数（可选），若提供则优先使用，实现与选股模块联动
        """
        if val_dates is None:
            val_dates = self.get_valuation_dates()
        buy_date = self._find_buy_date(period, val_dates)
        if not buy_date:
            return []

        # 优先使用外部 strategy_fn（来自 selection_bridge 的当日选股池）
        if strategy_fn is not None:
            # 获取该报告期所有有财务数据的股票，然后用 strategy_fn 过滤
            self.cursor.execute("""
                SELECT DISTINCT f.ts_code
                FROM financial_data f
                WHERE f.end_date = ?
                  AND f.roe IS NOT NULL
            """, (period,))
            all_codes = [r[0] for r in self.cursor.fetchall()]
            eligible = [code for code in all_codes if strategy_fn(self.cursor, code)]
            logger.info(f"[Backtest] 使用外部选股权重 {period}: {len(eligible)}/{len(all_codes)} 只通过")
            return eligible

        # 降级：使用内置简化策略
        self.cursor.execute("""
            SELECT f.ts_code
            FROM financial_data f
            INNER JOIN (
                SELECT ts_code, pe, pb, dv_ttm, trade_date
                FROM valuation_data v2
                WHERE trade_date = (
                    SELECT MAX(trade_date) FROM valuation_data 
                    WHERE ts_code = v2.ts_code AND trade_date <= ?
                )
            ) v ON f.ts_code = v.ts_code
            WHERE f.end_date = ?
              AND f.roe IS NOT NULL AND f.roe >= 10
              AND f.revenue_yoy IS NOT NULL
              AND v.pe IS NOT NULL
            ORDER BY f.roe DESC
            LIMIT 30
        """, (buy_date, period))
        return [r[0] for r in self.cursor.fetchall()]

    def _get_price_series(self, ts_code, start_date, end_date):
        """获取持有期内价格序列 [(trade_date, close), ...]"""
        self.cursor.execute("""
            SELECT trade_date, close FROM valuation_data
            WHERE ts_code = ? AND trade_date >= ? AND trade_date <= ?
              AND close IS NOT NULL
            ORDER BY trade_date ASC
        """, (ts_code, start_date, end_date))
        return [(r[0], float(r[1])) for r in self.cursor.fetchall()]

    def _find_first_threshold_idx(self, price_series, threshold):
        """
        找到第一个回撤达到 threshold（比例）的索引（相对于序列起点）
        price_series: [(date, close), ...]
        threshold: float, e.g. 0.15 means 15%
        返回 int 或 None
        """
        if not price_series:
            return None
        peak = price_series[0][1]
        for idx, (_, px) in enumerate(price_series):
            if px > peak:
                peak = px
            dd = (peak - px) / peak
            if dd >= threshold:
                return idx
        return None

    def _find_profit_threshold_idx(self, price_series, target_profit_pct, partial=False):
        """
        找到第一个达到目标盈利的索引（用于阶梯止盈）

        Args:
            price_series: [(date, close), ...]
            target_profit_pct: float, e.g. 0.15 means +15%
            partial: True 表示部分止盈（减仓），False 表示全部止盈

        Returns:
            (idx, partial) 或 None
        """
        if not price_series:
            return None
        buy_price = price_series[0][1]
        target_price = buy_price * (1 + target_profit_pct)

        for idx, (date, px) in enumerate(price_series):
            if px >= target_price:
                return (idx, partial)
        return None

    def _get_ladder_trailing_drop(self, cfg, profit_pct):
        """
        根据当前浮盈和阶梯状态，返回当前应使用的回撤阈值

        标准阶梯模板：
        - 浮盈15%：减仓30%，剩余仓位开启5%回撤跟踪
        - 浮盈35%：再减仓40%，剩余仓位收紧至3%回撤
        - 浮盈60%以上：仅留底仓，1%回撤无条件清仓

        Returns:
            (trailing_drop, reduce_ratio, remaining_ratio, is_ladder_exit)
            is_ladder_exit=True 表示这是阶梯止盈（部分减仓）
        """
        ladder_3_pct = cfg.get('ladder_3_profit_pct', 0.60)
        ladder_3_remaining = cfg.get('ladder_3_remaining_ratio', 0.10)
        ladder_3_drop = cfg.get('ladder_3_trailing_drop', 0.01)

        ladder_2_pct = cfg.get('ladder_2_profit_pct', 0.35)
        ladder_2_reduce = cfg.get('ladder_2_reduce_ratio', 0.40)
        ladder_2_drop = cfg.get('ladder_2_trailing_drop', 0.03)

        ladder_1_pct = cfg.get('ladder_1_profit_pct', 0.15)
        ladder_1_reduce = cfg.get('ladder_1_reduce_ratio', 0.30)
        ladder_1_drop = cfg.get('ladder_1_trailing_drop', 0.05)

        if profit_pct >= ladder_3_pct:
            # 阶梯3：仅留底仓，1%回撤清仓
            return ladder_3_drop, 1.0 - ladder_3_remaining, ladder_3_remaining, True
        elif profit_pct >= ladder_2_pct:
            # 阶梯2：再减仓40%，剩余3%回撤
            return ladder_2_drop, ladder_2_reduce, 1.0 - ladder_2_reduce, True
        elif profit_pct >= ladder_1_pct:
            # 阶梯1：减仓30%，剩余5%回撤
            return ladder_1_drop, ladder_1_reduce, 1.0 - ladder_1_reduce, True
        else:
            # 未达到阶梯阈值，使用默认移动止盈回撤
            return cfg.get('trailing_drop_pct', 0.08), 0.0, 1.0, False

    def _find_trailing_stop_idx(self, price_series, cfg):
        """
        动态移动止盈：盈利达到激活阈值后，从最高点回撤 trailing_drop_pct 触发

        Args:
            price_series: [(date, close), ...]
            cfg: RISK_CONFIG 字典（包含 trailing_activation_pct, trailing_drop_pct）

        Returns:
            int 或 None
        """
        if not price_series or len(price_series) < 2:
            return None

        buy_price = price_series[0][1]
        activation_pct = cfg.get('trailing_activation_pct', 0.15)
        trailing_drop = cfg.get('trailing_drop_pct', 0.08)

        peak = buy_price
        activated = False

        for idx, (date, px) in enumerate(price_series):
            # 更新最高点
            if px > peak:
                peak = px
                profit_pct = (peak - buy_price) / buy_price
                # 检查是否达到激活阈值
                if profit_pct >= activation_pct:
                    activated = True

            # 激活后检查回撤
            if activated:
                drop_pct = (peak - px) / peak
                if drop_pct >= trailing_drop:
                    return idx

        return None

    def _find_buy_date(self, period, val_dates):
        """报告期后最近的估值日（模拟季报发布后选股）"""
        # period e.g. '20251231' → 20260101+
        try:
            period_date = datetime.strptime(period, '%Y%m%d')
        except Exception:
            period_date = datetime.strptime(period, '%Y%m')

        # 报告期后15-45天内选股
        search_start = (period_date + timedelta(days=15)).strftime('%Y%m%d')
        search_end = (period_date + timedelta(days=45)).strftime('%Y%m%d')

        for d in val_dates:
            if search_start <= d <= search_end:
                return d
        # fallback: report期后第一个估值日
        for d in val_dates:
            if d > period[:8].replace('-', '').replace('/', ''):
                return d
        return None

    def _get_price_at(self, ts_code, trade_date):
        """获取某只股票在某交易日的收盘价（严格精确匹配，不做fallback，避免引入失真）"""
        self.cursor.execute("""
            SELECT close FROM valuation_data
            WHERE ts_code = ? AND trade_date = ?
              AND close IS NOT NULL
            LIMIT 1
        """, (ts_code, trade_date))
        r = self.cursor.fetchone()
        return r[0] if r else None

    def debug_price(self, ts_code, buy_date, sell_date):
        """调试用：打印两端的实际查价路径"""
        for label, d in [('buy', buy_date), ('sell', sell_date)]:
            r = self.cursor.execute("""
                SELECT trade_date, close FROM valuation_data
                WHERE ts_code = ? AND trade_date = ? AND close IS NOT NULL
            """, (ts_code, d)).fetchone()
            if r:
                print(f"  {label} {d}: exact {r}")
            else:
                r = self.cursor.execute("""
                    SELECT trade_date, close FROM valuation_data
                    WHERE ts_code = ? AND trade_date <= ? AND close IS NOT NULL
                    ORDER BY trade_date DESC LIMIT 1
                """, (ts_code, d)).fetchone()
                print(f"  {label} {d}: fallback {r}")

    def _calc_max_drawdown(self, ts_code, start_date, start_idx, end_idx, val_dates):
        """持有期内的最大回撤"""
        self.cursor.execute("""
            SELECT close FROM valuation_data
            WHERE ts_code = ? AND trade_date >= ? AND trade_date <= ?
            AND close IS NOT NULL
            ORDER BY trade_date ASC
        """, (ts_code, start_date, val_dates[end_idx]))
        prices = [r[0] for r in self.cursor.fetchall()]
        if not prices:
            return 0
        peak = prices[0]
        max_dd = 0.0
        for px in prices:
            if px > peak:
                peak = px
            dd = (peak - px) / peak
            if dd > max_dd:
                max_dd = dd
        return max_dd

    def generate_report(self):
        """输出回测报告"""
        if not self.results:
            logger.warning("无回测结果")
            return ""

        lines = []
        lines.append("# V3双体系策略回测报告")
        lines.append(f"\n> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

        # 汇总绩效表
        lines.append("## 一、季度绩效汇总\n\n")
        lines.append("| 报告期 | 数量 | 平均收益 | 胜率 | 最佳 | 最差 | 基准 | 止损次数 |")
        lines.append("|:---|:---:|:---:|:---:|:---|:---|:---:|:---:|\n")
        total_ret = []
        total_win = 0
        total_stocks = 0
        total_stops = 0
        for r in self.results:
            total_ret.append(r['avg_return'])
            if r['avg_return'] > 0:
                total_win += 1
            total_stocks += r['selected']
            total_stops += r.get('stop_loss_count', 0)
            lines.append(f"| {r['period']} | {r['selected']} | "
                f"{r['avg_return']*100:+.2f}% | {r['win_rate']:.1f}% | "
                f"{r['best']} ({r.get('best_ret', 0)*100:+.1f}%) | "
                f"{r['worst']} ({r.get('worst_ret', 0)*100:+.1f}%) | "
                f"{r.get('benchmark_ret', 0)*100:+.2f}% | {r.get('stop_loss_count', 0)} |"
            )

        # 整体表现
        if total_ret:
            overall_avg = mean(total_ret) * 100
            overall_win_rate = total_win / len(total_ret) * 100
            sharpe = self._calc_sharpe(total_ret)
        else:
            overall_avg = 0
            overall_win_rate = 0
            sharpe = 0

        lines.append(f"\n**整体表现**")
        lines.append(f"- 报告期: {len(total_ret)}个")
        lines.append(f"- 组合平均收益: {overall_avg:+.2f}%")
        lines.append(f"- 策略季度胜率: {overall_win_rate:.1f}%")
        lines.append(f"- 简化夏普比率: {sharpe:.2f}")
        lines.append(f"- 总选股数: {total_stocks}只 | 总止损: {total_stops}次")

        # 止盈止损原因统计
        reason_counts = {}
        for r in self.results:
            for s in r.get('stocks', []):
                reason = s.get('stop_reason', '持有到期') or '持有到期'
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

        if reason_counts:
            lines.append("\n## 三、止盈止损原因统计\n\n")
            lines.append("| 原因 | 次数 | 占比 |")
            lines.append("|:---|:---:|:---:|\n")
            total_exits = sum(reason_counts.values())
            for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
                pct = count / total_exits * 100 if total_exits else 0
                lines.append(f"| {reason} | {count} | {pct:.1f}% |")

        # 逐股明细
        lines.append("\n## 二、逐股明细\n\n")
        for r in self.results:
            if r.get('selected', 0) == 0:
                continue
            lines.append(f"### {r['period']} → 持有 {r['date']}\n\n")
            lines.append("| 股票 | 收益 | 最大回撤 | 止损原因 |\n")
            lines.append("|:---|:---:|:---:|:---|\n")
            for s in r.get('stocks', []):
                stopped = s.get('stop_reason', '') or ''
                lines.append(
                    f"| {s['ts_code']} | "
                    f"{s['net_return']*100:+.2f}% | "
                    f"{s.get('max_dd', 0)*100:.1f}% | {stopped} |"
                )

        lines.append(f"\n---")
        lines.append("> ⚠️ 回测基于现有118个交易日的估值数据（约半年）")
        lines.append("> ⚠️ 收益未考虑滑点、分红、税费等，仅供方向参考")
        lines.append("> 数据来源: Tushare Pro 本地数据库\n")

        report_path = f"reports/backtest_v3_{datetime.now().strftime('%Y%m%d')}.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        logger.info(f"✅ 回测报告已生成: {report_path}")
        return '\n'.join(lines)

    def _calc_sharpe(self, returns, risk_free_rate=0.02):
        """简化夏普比率"""
        if not returns or len(returns) < 2:
            return 0
        avg = mean(returns)
        # 计算标准差
        variance = sum((r - avg) ** 2 for r in returns) / (len(returns) - 1)
        std = variance ** 0.5
        if std == 0:
            return 0
        annualized_return = avg * 4  # 假设 quarterly
        annualized_std = std * (4 ** 0.5)
        sharpe = (annualized_return - risk_free_rate) / annualized_std
        return sharpe

    def close(self):
        """关闭连接；若为外部共享连接，则只做 commit，不关闭"""
        try:
            if self.conn is not None:
                self.conn.commit()
                if getattr(self, '_owns_conn', True):
                    # 仅当连接由本实例创建时才做 checkpoint 并关闭
                    try:
                        self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    except Exception:
                        pass
                    self.conn.close()
        except Exception:
            pass
        self.conn = None
        self.cursor = None
        logger.info("回测引擎连接已关闭")


# ============================================================
# 简易调用接口
# ============================================================

def run_backtest(db_path=None):
    """一键回测"""
    from pathlib import Path
    if not db_path:
        db_path = Path(__file__).parent / 'database' / 'stock_analysis.db'
    
    # 根据大盘状态动态调整风控参数
    from selection_bridge import get_dynamic_risk_config
    get_dynamic_risk_config()
    
    engine = BacktestEngine(str(db_path))
    engine.run_quarterly_backtest()
    report = engine.generate_report()
    engine.close()
    return report


if __name__ == '__main__':
    import logging
    import sys
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    report = run_backtest()
    print("\n" + "=" * 70)
    print("回测完成，报告如下:")
    print("=" * 70)
    print(report)
