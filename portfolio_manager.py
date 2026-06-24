"""
portfolio_manager.py - 观察池/持仓管理/预警退出机制
修复database is locked问题：不再持有长期cursor
"""

import logging
import sqlite3
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class WatchListManager:
    """观察池管理"""

    def __init__(self, db_manager):
        self.db = db_manager
        # 不再持有长期cursor，避免database is locked

    def add_to_watch(self, ts_code, name, industry, strategy_type,
                     score, grade, dim_scores=None, reasons=None,
                     stop_loss=None, target_price=None, core_logic=None,
                     cursor=None, conn=None):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # 每只股票使用独立连接，避免单例连接的锁竞争
        db_path = self.db.db_path
        for attempt in range(5):
            conn = None
            cursor = None
            try:
                conn = sqlite3.connect(db_path, timeout=10)
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA busy_timeout=10000")
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO watch_list
                        (ts_code, name, industry, strategy_type, total_score,
                         grade, dim_scores, reasons, stop_loss, target_price,
                         core_logic, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '观察中', ?, ?)
                """, (
                    ts_code, name, industry, strategy_type, score, grade,
                    str(dim_scores) if dim_scores else None,
                    '; '.join(reasons[:8]) if reasons else None,
                    stop_loss, target_price, core_logic, now, now
                ))
                conn.commit()
                return  # 成功则直接返回
            except sqlite3.OperationalError as e:
                if 'locked' in str(e) and attempt < 4:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                logger.error(f"添加观察池失败 {ts_code}: {e}")
            except Exception as e:
                logger.error(f"添加观察池失败 {ts_code}: {e}")
            finally:
                if cursor:
                    try:
                        cursor.close()
                    except Exception:
                        pass
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

    def check_buy_signals(self, ts_code):
        """技术面买入信号检查（扩展至5条信号）"""
        signals = []
        count = 0
        cursor = None
        try:
            cursor = self.db.get_cursor()
            # 统一取最近20日估值
            cursor.execute("""
                SELECT trade_date, close, pe_ttm, pb, dv_ttm
                FROM valuation_data
                WHERE ts_code = ? AND close IS NOT NULL
                ORDER BY trade_date DESC LIMIT 25
            """, (ts_code,))
            rows = cursor.fetchall()
            if len(rows) < 10:
                return 0, ['数据不足']

            closes = [r[1] for r in reversed(rows)]
            latest_close = closes[-1]
            ma5 = sum(closes[-5:]) / 5
            ma10 = sum(closes[-10:]) / 10
            ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else sum(closes) / len(closes)

            # 信号1: MA多头
            if ma5 > ma10 > ma20:
                signals.append('MA多头排列')
                count += 1
            # 信号2: 价格在关键均线上
            if latest_close > ma20:
                signals.append('站上MA20')
                count += 1
            # 信号3: 短期动量 > 0（近5日涨幅为正）
            if len(closes) >= 6:
                mom5 = (closes[-1] - closes[-6]) / closes[-6] * 100
                if mom5 > 0:
                    signals.append(f'短期动量{mom5:.1f}%')
                    count += 1
            # 信号4: PE低位分位
            pe_cur = rows[0][2]
            if pe_cur and pe_cur > 0:
                cursor.execute("""
                    SELECT pe_ttm FROM valuation_data
                    WHERE ts_code = ? AND pe_ttm IS NOT NULL AND pe_ttm > 0 AND pe_ttm < 10000
                    ORDER BY trade_date ASC
                """, (ts_code,))
                pe_vals = [r[0] for r in cursor.fetchall()]
                if pe_vals and len(pe_vals) >= 10:
                    cur = pe_vals[-1]
                    below = sum(1 for p in pe_vals if p <= cur)
                    pct = below / len(pe_vals) * 100
                    if pct < 30:
                        signals.append(f'PE低位{pct:.0f}%')
                        count += 1
            # 信号5: PB低位分位
            pb_cur = rows[0][3]
            if pb_cur and pb_cur > 0:
                cursor.execute("""
                    SELECT pb FROM valuation_data
                    WHERE ts_code = ? AND pb IS NOT NULL AND pb > 0
                    ORDER BY trade_date ASC
                """, (ts_code,))
                pb_vals = [r[0] for r in cursor.fetchall()]
                if pb_vals and len(pb_vals) >= 10:
                    cur = pb_vals[-1]
                    below = sum(1 for p in pb_vals if p <= cur)
                    pct = below / len(pb_vals) * 100
                    if pct < 30:
                        signals.append(f'PB低位{pct:.0f}%')
                        count += 1
            # 信号6: 股息率高位（仅当有值且 > 2%）
            dv_cur = rows[0][4]
            if dv_cur and dv_cur >= 2.0:
                signals.append(f'股息率{dv_cur:.1f}%')
                count += 1
        except Exception as e:
            logger.debug(f"信号检查失败 {ts_code}: {e}")
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
        return min(count, 6), signals

    def update_watch_signals(self, ts_code):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        count, signals = self.check_buy_signals(ts_code)
        cursor = None
        try:
            cursor = self.db.get_cursor()
            cursor.execute("""
                UPDATE watch_list
                SET signals_met = ?, buy_signal_1 = ?, updated_at = ?
                WHERE ts_code = ? AND status = '观察中'
            """, (count, ' | '.join(signals) if signals else '', now, ts_code))
            self.db.get_connection().commit()
        except Exception:
            pass
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
        return count, signals

    def get_watch_list(self, strategy_type=None, status='观察中'):
        cursor = None
        try:
            cursor = self.db.get_cursor()
            if strategy_type:
                cursor.execute("""
                    SELECT ts_code, name, industry, total_score, grade, signals_met,
                           stop_loss, target_price, core_logic, created_at
                    FROM watch_list WHERE strategy_type=? AND status=?
                    ORDER BY total_score DESC
                """, (strategy_type, status))
            else:
                cursor.execute("""
                    SELECT ts_code, name, industry, strategy_type, total_score, grade,
                           signals_met, stop_loss, target_price, created_at
                    FROM watch_list WHERE status=?
                    ORDER BY strategy_type, total_score DESC
                """, (status,))
            return cursor.fetchall()
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass

    def trigger_buy(self, ts_code):
        """触发买入（技术信号满足2个以上）→ 移到观察池_已触发"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor = None
        try:
            cursor = self.db.get_cursor()
            cursor.execute("""
                UPDATE watch_list SET status='已触发', updated_at=?
                WHERE ts_code=? AND status='观察中'
            """, (now, ts_code))
            self.db.get_connection().commit()
        except Exception as e:
            logger.error(f"触发买入失败 {ts_code}: {e}")
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass


class PortfolioManager:
    """持仓管理"""

    def __init__(self, db_manager):
        self.db = db_manager
        # 不再持有长期cursor，避免database is locked

    def buy_stock(self, ts_code, name, strategy_type, buy_price, shares,
                  stop_loss=None, take_profit=None):
        cursor = None
        try:
            cursor = self.db.get_cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cost = buy_price * shares
            cursor.execute("""
                INSERT OR REPLACE INTO holdings
                    (ts_code, name, strategy_type, score, quantity, avg_cost,
                     total_cost, buy_price, current_price, stop_loss, take_profit,
                     buy_date, updated_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '持有中')
            """, (
                ts_code, name, strategy_type, 0, shares, buy_price,
                cost, buy_price, buy_price, stop_loss, take_profit,
                now[:10], now
            ))
            self.db.get_connection().commit()
            logger.info(f"买入成功: {name} {shares}股 @ {buy_price}")
            return True
        except Exception as e:
            logger.error(f"买入失败 {ts_code}: {e}")
            return False
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass

    def sell_stock(self, ts_code, sell_price, shares=None):
        cursor = None
        try:
            cursor = self.db.get_cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            if shares is None:
                cursor.execute("DELETE FROM holdings WHERE ts_code=?", (ts_code,))
            else:
                cursor.execute("""
                    UPDATE holdings SET quantity=quantity-?, updated_at=?
                    WHERE ts_code=? AND quantity>=?
                """, (shares, now, ts_code, shares))
            self.db.get_connection().commit()
            logger.info(f"卖出成功: {ts_code} @ {sell_price}")
            return True
        except Exception as e:
            logger.error(f"卖出失败 {ts_code}: {e}")
            return False
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass

    def get_holdings(self):
        cursor = None
        try:
            cursor = self.db.get_cursor()
            cursor.execute("""
                SELECT ts_code, name, strategy_type, quantity, avg_cost, total_cost,
                       buy_price, stop_loss, take_profit, buy_date, status
                FROM holdings WHERE status='持有中'
            """)
            return cursor.fetchall()
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass

    def update_price(self, ts_code, current_price):
        cursor = None
        try:
            cursor = self.db.get_cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("""
                UPDATE holdings SET current_price=?, updated_at=?
                WHERE ts_code=? AND status='持有中'
            """, (current_price, now, ts_code))
            self.db.get_connection().commit()
        except Exception as e:
            logger.error(f"更新价格失败 {ts_code}: {e}")
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass


class AlertManager:
    """预警管理"""

    def __init__(self, db_manager):
        self.db = db_manager
        # 不再持有长期cursor，避免database is locked

    def run_all_checks(self):
        """
        对现有持仓运行预警检查（止损/止盈/持仓集中度）
        """
        cursor = None
        try:
            cursor = self.db.get_cursor()
            cursor.execute("""
                SELECT ts_code, name, close_price, stop_loss, take_profit_price
                FROM holdings WHERE status = '持有中'
            """)
            rows = cursor.fetchall()
            alert_count = 0
            for row in rows:
                ts_code, name, current_price, stop_loss, take_profit = row
                if not current_price:
                    continue

                # 止损预警
                if stop_loss and current_price <= stop_loss:
                    self.trigger(
                        self.db, ts_code, name, '止损',
                        f'触发止损: 现价{current_price}≤止损价{stop_loss} ({(current_price/stop_loss-1)*100:.1f}%)',
                        'HIGH', '止损卖出'
                    )
                    alert_count += 1

                # 止盈预警
                elif take_profit and current_price >= take_profit:
                    self.trigger(
                        self.db, ts_code, name, '止盈',
                        f'触发止盈: 现价{current_price}≥止盈价{take_profit} ({(current_price/take_profit-1)*100:.1f}%)',
                        'MEDIUM', '止盈卖出'
                    )
                    alert_count += 1

            return alert_count
        except Exception as e:
            logger.error(f"预警检查失败: {e}")
            return 0
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass

    @classmethod
    def trigger(cls, db_manager, ts_code, name, alert_type, message, severity, action):
        cursor = None
        try:
            cursor = db_manager.get_cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("""
                INSERT INTO alert_log
                    (ts_code, name, alert_type, message, severity, action, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (ts_code, name, alert_type, message, severity, action, now))
            db_manager.get_connection().commit()
            logger.warning(f"🔔 预警: {name} [{alert_type}] {message}")
            return True
        except Exception as e:
            logger.error(f"触发预警日志失败 {ts_code}: {e}")
            return False
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass

    def get_recent_alerts(self, limit=10):
        cursor = None
        try:
            cursor = self.db.get_cursor()
            cursor.execute("""
                SELECT ts_code, name, alert_type, message, severity, action, created_at
                FROM alert_log ORDER BY created_at DESC LIMIT ?
            """, (limit,))
            return cursor.fetchall()
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass

    def get_alert_stats(self):
        cursor = None
        try:
            cursor = self.db.get_cursor()
            cursor.execute("""
                SELECT alert_type, COUNT(*) as cnt, MAX(created_at) as last_time
                FROM alert_log GROUP BY alert_type ORDER BY cnt DESC
            """)
            return cursor.fetchall()
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass


class TradeRecorder:
    """交易记录"""

    def __init__(self, db_manager):
        self.db = db_manager
        # 不再持有长期cursor，避免database is locked

    def record(self, ts_code, name, trade_type, price, quantity, reason=None):
        cursor = None
        try:
            cursor = self.db.get_cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("""
                INSERT INTO trade_records
                    (ts_code, name, trade_type, price, quantity, reason, trade_date, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ts_code, name, trade_type, price, quantity, reason,
                now[:10], now
            ))
            self.db.get_connection().commit()
            logger.info(f"交易记录: {trade_type} {name} {quantity}股 @ {price}")
            return True
        except Exception as e:
            logger.error(f"交易记录失败 {ts_code}: {e}")
            return False
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass

    def get_history(self, ts_code=None, limit=20):
        cursor = None
        try:
            cursor = self.db.get_cursor()
            if ts_code:
                cursor.execute("""
                    SELECT ts_code, name, trade_type, price, quantity, reason, trade_date
                    FROM trade_records WHERE ts_code=?
                    ORDER BY trade_date DESC LIMIT ?
                """, (ts_code, limit))
            else:
                cursor.execute("""
                    SELECT ts_code, name, trade_type, price, quantity, reason, trade_date
                    FROM trade_records ORDER BY trade_date DESC LIMIT ?
                """, (limit,))
            return cursor.fetchall()
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass


def sync_portfolio(db, growth_stocks, value_stocks):
    """
    将选股结果同步到观察池（无数据源切换，专注修复database is locked）
    growth_stocks/value_stocks: list of dict with keys: ts_code, name, industry, score, ...
    """
    watch_mgr = WatchListManager(db)
    all_stocks = [
        {**s, 'strategy_type': '成长'} for s in (growth_stocks or [])
    ] + [
        {**s, 'strategy_type': '价值'} for s in (value_stocks or [])
    ]

    success_count = 0
    for stock in all_stocks:
        ts_code = stock.get('ts_code')
        if not ts_code:
            continue
        try:
            # 每只股票独立连接，避免长事务锁竞争
            watch_mgr.add_to_watch(
                ts_code=ts_code,
                name=stock.get('name', ''),
                industry=stock.get('industry', ''),
                strategy_type=stock['strategy_type'],
                score=stock.get('growth_score', stock.get('score', 0)),
                grade=stock.get('growth_grade', stock.get('grade', 'B')),
                reasons=stock.get('growth_reasons', stock.get('reasons', [])),
                stop_loss=stock.get('stop_loss'),
                target_price=stock.get('target_price'),
                core_logic=stock.get('core_logic')
            )
            success_count += 1
        except Exception as e:
            logger.debug(f"sync_portfolio跳过 {ts_code}: {e}")

    logger.info(f"📥 观察池同步完成: {success_count}/{len(all_stocks)}只")


# ===== 兼容别名 =====
HoldingsManager = PortfolioManager  # 兼容旧导入名


class StrategyGenerator:
    """交易策略生成器"""

    def __init__(self, db_manager):
        self.db = db_manager

    def generate_strategies(self, market_cycle=None, macro_score=None, tech_score=None):
        """
        生成当日交易策略
        返回: [(report_date, ts_code, action, current_price, target_price, stop_loss, priority, reason), ...]
        """
        strategies = []
        cursor = None
        try:
            cursor = self.db.get_cursor()
            now = datetime.now().strftime('%Y-%m-%d')

            # 从观察池获取待买入标的
            cursor.execute("""
                SELECT ts_code, name, strategy_type, stop_loss, target_price, core_logic
                FROM watch_list
                WHERE status = '已触发'
                ORDER BY total_score DESC
            """)
            buy_candidates = cursor.fetchall()

            for row in buy_candidates:
                ts_code, name, strategy_type, stop_loss, target_price, core_logic = row
                action = 'BUY'
                priority = 'HIGH' if strategy_type == '成长' else 'MEDIUM'
                reason = f"观察池触发|{core_logic or ''}"

                # 获取最新价格
                cursor.execute("""
                    SELECT close FROM valuation_data
                    WHERE ts_code = ? ORDER BY trade_date DESC LIMIT 1
                """, (ts_code,))
                price_row = cursor.fetchone()
                current_price = price_row[0] if price_row else 0

                strategies.append((
                    now, ts_code, action, current_price,
                    target_price or 0, stop_loss or 0,
                    priority, reason
                ))

            # 从持仓获取待卖出标的（止损/止盈检查）
            cursor.execute("""
                SELECT ts_code, name, close_price, stop_loss, take_profit_price
                FROM holdings WHERE status = '持有中'
            """)
            holdings = cursor.fetchall()

            for row in holdings:
                ts_code, name, current_price, stop_loss, take_profit = row
                if not current_price:
                    continue

                # 止损检查
                if stop_loss and current_price <= stop_loss:
                    strategies.append((
                        now, ts_code, 'SELL', current_price, 0, stop_loss,
                        'HIGH', f'触发止损价{stop_loss}'
                    ))
                # 止盈检查
                elif take_profit and current_price >= take_profit:
                    strategies.append((
                        now, ts_code, 'SELL', current_price, take_profit, 0,
                        'HIGH', f'触发止盈价{take_profit}'
                    ))

            return strategies

        except Exception as e:
            logger.error(f"生成策略失败: {e}")
            return []
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
