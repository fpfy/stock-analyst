# API 安全调用规范

> 为避免 429 限流错误，所有 API 调用必须通过限流/重试包装层。
> 违反本规范的调用会被 CI/Lint 检查拦截。

---

## 1. 主流程（`realtime_fetcher.py`）

已自动修复：`self.pro` 在初始化时被 `wrap_tushare_pro()` 包装。
- 所有 `self.pro.xxx()` 调用**自动限流 + 429 退避**，无需逐行修改。
- 批量接口 `fetch_bulk_financial()` / `fetch_bulk_valuation()` 内部使用 `tushare_limiter.wait()`，已满足限流。

## 2. 新增脚本必须遵循的写法

### 方式 A：通过 `safe_api_call` 包装单次调用

```python
from safe_api_call import safe_api_call

# 推荐
df = safe_api_call(pro.daily_basic, source="tushare",
                   ts_code="000651.SZ", start_date="20240101", end_date="20241231")
```

### 方式 B：通过 `wrap_tushare_pro` 包装整个 pro 实例

```python
from safe_tushare import wrap_tushare_pro
pro = wrap_tushare_pro(raw_pro)

# 之后所有 pro.xxx() 自动安全
df = pro.daily_basic(ts_code="000651.SZ", start_date="20240101", end_date="20241231")
```

## 3. 禁止裸调用

以下写法**禁止**出现在会被定期执行的代码路径中：

```python
# ❌ 错误：裸调用，无 429 保护
df = pro.daily_basic(ts_code=code, start_date=start, end_date=end)
data = pro.fina_indicator(ts_code=code, start_date=start, end_date=end)
```

## 4. 限流阈值参考

| 数据源 | 最小间隔 | 最大间隔 | 每分钟上限 |
|---|---|---|---|
| tushare | 2.0s | 4.0s | 30 |
| akshare | 1.0s | 2.0s | 40 |
| http/requests | 1.0s | 2.0s | 60 |

## 5. 批量任务约束

- 禁止 `ThreadPoolExecutor` / `multiprocessing.Pool` 无限制并发调用 tushare/akshare。
- 批量任务必须串行 + 固定间隔（如 `tushare_limiter.wait(min_interval=1.5, max_interval=3.0)`）。
- 单批次股票数 ≤ 50，超过 50 必须分多批次且批次间等待 ≥ 60s。

## 6. 历史一次性脚本

`backfill_*.py`、`fetch_historical_valuation.py`、`backfill_full_v3.py` 等为一次性历史脚本，当前不在主流程调用路径中。如需重新执行，必须先通过 `wrap_tushare_pro()` 或 `safe_api_call()` 包装所有 `pro.xxx()` 调用。
