#!/usr/bin/env python3
"""
回测性能评估与可视化模块
- 绩效指标：夏普/索提诺/最大回撤/卡尔马/季度胜率/盈亏比
- 参数敏感性：ROE 门槛、持仓天数、选股上限
- 可视化：净值曲线、基准对比、回撤图、滚动夏普
"""

import os
import sys
import math
import logging
from statistics import mean, median
from datetime import datetime

import sqlite3
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

# 项目路径
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

DB_PATH = os.path.join(PROJECT_ROOT, 'database', 'stock_analysis.db')
REPORT_DIR = os.path.join(PROJECT_ROOT, 'reports')
os.makedirs(REPORT_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


# ============================================================
# 数据库读取
# ============================================================
def _get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def load_backtest_results(conn=None):
    """从 backtest_v3 结果表或直接读取最新报告"""
    close_conn = False
    if conn is None:
        conn = _get_conn()
        close_conn = True
    try:
        # 优先从 backtest_v3 内存结构无法持久化，这里用 runner 报告文件回退
        # 实际应扩展 backtest_v3 支持结果落库；当前采用重新运行一次获取结果
        from backtest_v3 import BacktestEngine
        engine = BacktestEngine(DB_PATH, conn=conn)
        engine.run_quarterly_backtest()
        results = engine.results
        return results
    finally:
        if close_conn:
            conn.close()


# ============================================================
# 指标计算
# ============================================================
def calc_sharpe(returns, periods_per_year=4, risk_free_rate=0.02):
    """夏普比率（年化）"""
    if not returns or len(returns) < 2:
        return 0.0
    arr = np.array(returns, dtype=float)
    avg = arr.mean()
    std = arr.std(ddof=1)
    if std == 0:
        return 0.0
    return (avg * periods_per_year - risk_free_rate) / (std * math.sqrt(periods_per_year))


def calc_sortino(returns, periods_per_year=4, risk_free_rate=0.02, target=0.0):
    """索提诺比率（以下行风险替代总波动）"""
    if not returns or len(returns) < 2:
        return 0.0
    arr = np.array(returns, dtype=float)
    avg = arr.mean()
    downside = arr[arr < target]
    if len(downside) == 0:
        return float('inf') if avg > 0 else 0.0
    down_std = np.sqrt(np.mean((downside - target) ** 2))
    if down_std == 0:
        return 0.0
    return (avg * periods_per_year - risk_free_rate) / (down_std * math.sqrt(periods_per_year))


def calc_max_drawdown_from_series(nav_series):
    """从净值序列计算最大回撤"""
    if nav_series is None or len(nav_series) < 2:
        return 0.0
    arr = np.array(nav_series, dtype=float)
    peak = np.maximum.accumulate(arr)
    dd = (arr - peak) / peak
    return float(dd.min())


def calc_calmar(nav_series, periods_per_year=4, risk_free_rate=0.02):
    """卡尔马比率 = 年化收益 / 最大回撤"""
    if nav_series is None or len(nav_series) < 2:
        return 0.0
    arr = np.array(nav_series, dtype=float)
    total_return = arr[-1] / arr[0] - 1
    years = len(arr) / periods_per_year
    annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
    max_dd = abs(calc_max_drawdown_from_series(nav_series))
    if max_dd == 0:
        return 0.0
    return (annual_return - risk_free_rate) / max_dd


def performance_metrics(results, risk_free_rate=0.02):
    """汇总绩效指标"""
    if not results:
        return {}

    # 每期组合平均收益
    rets = [r.get('avg_return', 0) for r in results if r.get('selected', 0) > 0]
    bench_rets = [r.get('benchmark_ret', 0) for r in results if r.get('selected', 0) > 0]

    # 季度胜率（相对上一期自身）
    win_count = sum(1 for r in results if r.get('avg_return', 0) > 0)
    win_rate = win_count / len(results) * 100 if results else 0

    # 相对基准胜率
    outperf_count = sum(1 for r in results if r.get('selected', 0) > 0 and
                        r.get('avg_return', 0) > r.get('benchmark_ret', 0))
    benchmark_win_rate = outperf_count / len(results) * 100 if results else 0

    # 净值曲线
    nav = [1.0]
    bench_nav = [1.0]
    for r in results:
        if r.get('selected', 0) > 0:
            nav.append(nav[-1] * (1 + r.get('avg_return', 0)))
            bench_nav.append(bench_nav[-1] * (1 + r.get('benchmark_ret', 0)))

    metrics = {
        'periods': len(results),
        'avg_return_pct': mean(rets) * 100 if rets else 0,
        'total_return_pct': (nav[-1] / nav[0] - 1) * 100 if len(nav) > 1 else 0,
        'benchmark_total_return_pct': (bench_nav[-1] / bench_nav[0] - 1) * 100 if len(bench_nav) > 1 else 0,
        'win_rate_pct': win_rate,
        'benchmark_win_rate_pct': benchmark_win_rate,
        'sharpe': calc_sharpe(rets, risk_free_rate=risk_free_rate),
        'sortino': calc_sortino(rets, risk_free_rate=risk_free_rate),
        'max_drawdown_pct': calc_max_drawdown_from_series(nav) * 100,
        'calmar': calc_calmar(nav, risk_free_rate=risk_free_rate),
        'nav_series': nav,
        'bench_nav_series': bench_nav,
        'period_labels': [r['period'] for r in results],
    }
    return metrics


# ============================================================
# 参数敏感性
# ============================================================
def run_parameter_sensitivity():
    """测试不同 ROE 门槛和持仓天数对组合收益的影响"""
    import backtest_v3 as bt

    roe_thresholds = [6, 8, 10, 12, 15]
    hold_days_list = [10, 20, 30, 40, 60]
    limit_list = [20, 30, 50, 80]

    conn = _get_conn()
    results = []

    for roe in roe_thresholds:
        for hold in hold_days_list:
            for lim in limit_list:
                # 临时修改配置
                orig_config = bt.BACKTEST_CONFIG.copy()
                bt.BACKTEST_CONFIG['hold_days'] = hold

                engine = bt.BacktestEngine(DB_PATH, conn=conn)
                # 动态修改内置策略的 ROE 门槛（通过 monkey-patch）
                orig_strategy = engine._default_strategy
                def patched_strategy(cursor, ts_code):
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
                    roe_val, rev_yoy, profit_yoy, debt, close, pe, pb, dv = r
                    if roe_val and roe_val >= roe and pe and 5 <= pe <= 20 and pb <= 3 and debt < 50:
                        return True
                    if roe_val and roe_val >= roe + 5 and rev_yoy and rev_yoy >= 15 and profit_yoy and profit_yoy >= 15:
                        return True
                    return False

                engine._default_strategy = patched_strategy
                engine.strategy_fn = patched_strategy

                try:
                    engine.run_quarterly_backtest()
                    bt_results = engine.results
                    valid_rets = [r['avg_return'] for r in bt_results if r.get('selected', 0) > 0]
                    avg_ret = mean(valid_rets) * 100 if valid_rets else 0
                    total_sel = sum(r.get('selected', 0) for r in bt_results)
                    results.append({
                        'roe_threshold': roe,
                        'hold_days': hold,
                        'limit': lim,
                        'avg_return_pct': avg_ret,
                        'total_selected': total_sel,
                        'periods': len(bt_results),
                    })
                except Exception as e:
                    logger.warning(f'敏感性测试失败 roe={roe} hold={hold} limit={lim}: {e}')
                finally:
                    bt.BACKTEST_CONFIG.update(orig_config)

    conn.close()
    df = pd.DataFrame(results)
    return df


# ============================================================
# 可视化
# ============================================================
def plot_equity_curve(metrics, save_path=None):
    """净值曲线 + 基准对比"""
    nav = metrics.get('nav_series', [])
    bench = metrics.get('bench_nav_series', [])
    labels = metrics.get('period_labels', [])

    if not nav or len(nav) < 2:
        logger.warning('净值序列不足，跳过净值曲线图')
        return

    fig, ax = plt.subplots(figsize=(10, 5))
    x = list(range(len(nav)))
    ax.plot(x, nav, marker='o', label='策略净值', linewidth=2)
    if bench and len(bench) == len(nav):
        ax.plot(x, bench, marker='s', label='基准净值', linewidth=2, linestyle='--')
    ax.set_title('策略净值曲线 vs 基准')
    ax.set_xlabel('回测期')
    ax.set_ylabel('净值')
    ax.legend()
    ax.grid(True, alpha=0.3)
    if labels:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha='right')
    plt.tight_layout()
    if save_path is None:
        save_path = os.path.join(REPORT_DIR, f"equity_curve_{datetime.now():%Y%m%d_%H%M%S}.png")
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    logger.info(f"净值曲线已保存: {save_path}")
    return save_path


def plot_drawdown(metrics, save_path=None):
    """回撤图（基于净值序列）"""
    nav = metrics.get('nav_series', [])
    if not nav or len(nav) < 2:
        logger.warning('净值序列不足，跳过回撤图')
        return
    arr = np.array(nav, dtype=float)
    peak = np.maximum.accumulate(arr)
    dd = (arr - peak) / peak * 100

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.fill_between(range(len(dd)), dd, 0, color='red', alpha=0.3)
    ax.plot(range(len(dd)), dd, color='red', linewidth=1.5)
    ax.set_title('策略回撤区间')
    ax.set_xlabel('回测期')
    ax.set_ylabel('回撤 (%)')
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    if save_path is None:
        save_path = os.path.join(REPORT_DIR, f"drawdown_{datetime.now():%Y%m%d_%H%M%S}.png")
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    logger.info(f"回撤图已保存: {save_path}")
    return save_path


def plot_parameter_heatmap(df, param_x='hold_days', param_y='roe_threshold', value='avg_return_pct', save_path=None):
    """参数敏感性热力图"""
    if df.empty:
        logger.warning('无敏感性数据，跳过热力图')
        return
    pivot = df.pivot_table(index=param_y, columns=param_x, values=value, aggfunc='mean')
    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(pivot.values, cmap='RdYlGn', aspect='auto')
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_xlabel(param_x)
    ax.set_ylabel(param_y)
    ax.set_title(f'参数敏感性: {value}')
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            ax.text(j, i, f"{pivot.values[i, j]:.1f}", ha='center', va='center', fontsize=9)
    fig.colorbar(im, ax=ax, label=value)
    plt.tight_layout()
    if save_path is None:
        save_path = os.path.join(REPORT_DIR, f"sensitivity_{value}_{datetime.now():%Y%m%d_%H%M%S}.png")
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    logger.info(f"敏感性热力图已保存: {save_path}")
    return save_path


# ============================================================
# 报告输出
# ============================================================
def generate_performance_report(metrics, sensitivity_df=None):
    """生成 Markdown 格式的性能评估报告"""
    lines = []
    lines.append("# 回测性能评估报告\n")
    lines.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    lines.append("## 一、核心绩效指标\n\n")
    lines.append("| 指标 | 数值 |")
    lines.append("|:---|:---:|")
    lines.append(f"| 回测期数 | {metrics.get('periods', 0)} |")
    lines.append(f"| 组合平均收益 | {metrics.get('avg_return_pct', 0):+.2f}% |")
    lines.append(f"| 累计收益 | {metrics.get('total_return_pct', 0):+.2f}% |")
    lines.append(f"| 基准累计收益 | {metrics.get('benchmark_total_return_pct', 0):+.2f}% |")
    lines.append(f"| 季度胜率 | {metrics.get('win_rate_pct', 0):.1f}% |")
    lines.append(f"| 相对基准胜率 | {metrics.get('benchmark_win_rate_pct', 0):.1f}% |")
    lines.append(f"| 夏普比率 | {metrics.get('sharpe', 0):.2f} |")
    lines.append(f"| 索提诺比率 | {metrics.get('sortino', 0):.2f} |")
    lines.append(f"| 最大回撤 | {metrics.get('max_drawdown_pct', 0):.2f}% |")
    lines.append(f"| 卡尔马比率 | {metrics.get('calmar', 0):.2f} |")

    if sensitivity_df is not None and not sensitivity_df.empty:
        lines.append("\n## 二、参数敏感性分析\n\n")
        lines.append("### ROE 门槛 vs 持仓天数（平均收益 %）\n")
        pivot = sensitivity_df.pivot_table(index='roe_threshold', columns='hold_days', values='avg_return_pct', aggfunc='mean')
        lines.append(pivot.to_markdown())
        lines.append("\n### 最优参数组合\n")
        best = sensitivity_df.loc[sensitivity_df['avg_return_pct'].idxmax()]
        lines.append(f"- ROE 门槛: {best['roe_threshold']}")
        lines.append(f"- 持仓天数: {best['hold_days']}")
        lines.append(f"- 选股上限: {best['limit']}")
        lines.append(f"- 平均收益: {best['avg_return_pct']:.2f}%")

    lines.append("\n## 三、可视化图表\n\n")
    lines.append(f"- 净值曲线: `reports/equity_curve_*.png`")
    lines.append(f"- 回撤图: `reports/drawdown_*.png`")
    lines.append(f"- 敏感性热力图: `reports/sensitivity_*.png`")

    report_path = os.path.join(REPORT_DIR, f"performance_report_{datetime.now():%Y%m%d_%H%M%S}.md")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    logger.info(f"性能评估报告已生成: {report_path}")
    return report_path


# ============================================================
# 主流程
# ============================================================
def main():
    logger.info('开始性能评估与可视化...')

    # 1. 加载回测结果
    conn = _get_conn()
    try:
        results = load_backtest_results(conn)
    finally:
        conn.close()

    if not results:
        logger.error('无回测结果，请先运行 backtest_v3_runner.py')
        return 1

    # 2. 计算绩效指标
    metrics = performance_metrics(results)
    logger.info(f"夏普: {metrics['sharpe']:.2f}, 索提诺: {metrics['sortino']:.2f}, 最大回撤: {metrics['max_drawdown_pct']:.2f}%")

    # 3. 参数敏感性（采样运行，耗时较长）
    logger.info('开始参数敏感性测试（可能需要几分钟）...')
    sensitivity_df = run_parameter_sensitivity()

    # 4. 可视化
    plot_equity_curve(metrics)
    plot_drawdown(metrics)
    if sensitivity_df is not None and not sensitivity_df.empty:
        plot_parameter_heatmap(sensitivity_df, param_x='hold_days', param_y='roe_threshold', value='avg_return_pct')

    # 5. 生成报告
    report_path = generate_performance_report(metrics, sensitivity_df)
    logger.info(f"全部完成，报告路径: {report_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
