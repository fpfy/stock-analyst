# PaperTrader database is locked 错误代码分析
> 日期：2026-06-23  
> 错误位置：`papertrader_final.py` `_check_position_v2()` → `update_holdings`  
> 错误信息：`sqlite3.OperationalError: database is locked`

---

## 1. 错误触发代码段

### 1.1 持仓检查与卖出逻辑（`_check_position_v2`）
```python
# papertrader_final.py:354-415
def _check_position_v2(self, position: Dict) -> Optional[Dict]:
    """检查持仓止盈止损（优化版）"""
    ts_code = position['ts_code']
    strategy_type = position['strategy_type']
    buy_price = position['buy_price']
    current_price = self._get_latest_close(ts_code)

    if not current_price or current_price <= 0:
        return None

    # 计算当前盈亏
    profit_pct = (current_price - buy_price) / buy_price * 100

    # 优化止损逻辑
    should_sell = False
    sell_reason = ""

    # 1. 检查是否达到止损线
    stop_loss_price = position['stop_loss']
    if current_price <= stop_loss_price:
        should_sell = True
        sell_reason = "止损"

    # 2. 检查是否达到止盈线
    elif current_price >= position['take_profit_price']:
        should_sell = True
        sell_reason = "止盈"

    # 3. 检查是否达到最大持仓时间
    days_held = self._get_days_held(ts_code)
    if days_held > 90:  # 超过90天强制卖出
        should_sell = True
        sell_reason = "超期"

    if should_sell:
        # 执行卖出
        shares = position['shares']
        amount = shares * current_price
        self.cash += amount

        # 更新持仓状态 —— 错误发生点
        self._execute_with_retry("""
            UPDATE holdings SET status=?, profit_pct=?, 
                             last_update=?, last_price=?, market_value=?
            WHERE ts_code=?
        """, ('已清仓', profit_pct,
              self._today, current_price, amount, ts_code), label="update_holdings")
        self._commit_with_retry()

        # 记录交易
        return {
            'date': self._today,
            'action': '清仓',
            'ts_code': ts_code,
            'price': current_price,
            'shares': shares,
            'amount': amount,
            'reason': sell_reason,
            'profit_pct': profit_pct
        }

    return None
```

### 1.2 数据库连接与重试执行
```python
# papertrader_final.py:59-113
def _connect_with_retry(self, max_retries=3, delay=1.0):
    """连接数据库，遇到锁定自动重试"""
    import time
    for attempt in range(max_retries):
        try:
            self._conn = sqlite3.connect(str(self.db_path), timeout=15)
            # 已调整 journal_mode 为 DELETE，原为 WAL
            self._execute_with_retry("PRAGMA journal_mode=DELETE")
            self._execute_with_retry("PRAGMA foreign_keys=ON")
            return
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
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
```

### 1.3 回测引擎关闭代码（竞争来源之一）
```python
# backtest_v3.py:458-490
def close(self):
    """关闭连接"""
    try:
        if self.conn is not None:
            self.conn.commit()
            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:
        pass
    try:
        if self.conn is not None:
            self.conn.close()
    except Exception:
        pass
    self.conn = None
    self.cursor = None
    logger.info("回测引擎连接已关闭")

def run_backtest(db_path=None):
    """一键回测"""
    from pathlib import Path
    if not db_path:
        db_path = Path(__file__).parent / 'database' / 'stock_analysis.db'

    engine = BacktestEngine(str(db_path))
    engine.run_quarterly_backtest()
    report = engine.generate_report()
    engine.close()
    return report
```

---

## 2. 错误上下文（全流程输出片段）
```
=== Stock-Analysis 组合入口 ===
执行步骤: macro → selection → backtest → paper

--- 步骤: macro ---
[宏观] 市场状态: 震荡, PMI趋势: 下行

--- 步骤: selection ---

--- 步骤: backtest ---

--- 步骤: paper ---
模拟交易器初始化完成，初始资金: 1,000,000

=== 运行交易日: 2026-06-23 ===
当前持仓数: 2
[DB_LOCK] update_holdings... 第1次重试
[DB_LOCK] update_holdings... 第2次重试
[DB_LOCK] update_holdings... 第3次重试
[DB_LOCK] update_holdings... 第4次重试
交易过程中出错: database is locked
模拟交易器已关闭
```

---

## 3. 问题本质分析

### 3.1 锁竞争时序
1. `run_full_analysis.py --all` 顺序执行：macro → selection → backtest → paper  
2. `backtest_v3.py` 的 `BacktestEngine.close()` 执行 `wal_checkpoint(TRUNCATE)` 后关闭连接。  
3. WAL checkpoint 在 Windows 下可能遗留短暂的文件锁（`-wal`/`-shm` 文件未完全释放）。  
4. `PaperTraderFinal` 立即以同一 `stock_analysis.db` 路径新建连接，执行 `UPDATE holdings` 时遭遇 `database is locked`。

### 3.2 连接策略缺陷
- 回测与 paper 交易**各自独立连接**，虽然分阶段执行，但缺乏连接间同步机制。
- `_execute_with_retry` 仅对单条 SQL 重试，未考虑“连接建立后首次写操作”因文件锁未释放而连续失败的场景。

### 3.3 已尝试修复的路径
| 修改项 | 文件 | 状态 |
|-------|------|------|
| SQLite 写操作统一走 `_execute_with_retry` + `_commit_with_retry` | `papertrader_final.py` | ✅ 已应用 |
| `_connect_with_retry` / `_execute_with_retry` 重试次数提升 | `papertrader_final.py` | ✅ 已应用 |
| `run_full_analysis.py` 增加 paper 前 WAL checkpoint + 等待 | `run_full_analysis.py` | ✅ 已应用 |
| `backtest_v3.py` `BacktestEngine.__init__` 增加 WAL + busy timeout | `backtest_v3.py` | ✅ 已应用 |
| `run_backtest` 数据库路径改为绝对路径 | `backtest_v3.py` | ✅ 已应用 |
| `papertrader_final.py` `journal_mode` 从 `WAL` 改为 `DELETE` | `papertrader_final.py` | ✅ 最新修改 |

---

## 4. 明日验证命令
```bash
cd C:/Users/fengpeng/stock_analysis_system
python skills/stock-analysis/scripts/run_full_analysis.py --all
```

## 5. 若仍失败的排查方向
1. 检查是否有其他 Python 进程（如实时数据获取、监控脚本）在 paper 阶段并发写 `stock_analysis.db`。  
2. 在 `run_full_analysis.py` 的回测与 paper 阶段之间增加更长强制等待（如 10 秒）。  
3. 考虑回测与 paper 共享同一 `sqlite3.Connection`，彻底避免跨连接锁。  
4. 若项目可接受，可临时将 paper 阶段数据库切换为独立副本路径（如 `database/paper_trade.db`），完全隔离回测写操作。
