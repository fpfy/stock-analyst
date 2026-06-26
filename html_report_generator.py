#!/usr/bin/env python3
"""
html_report_generator.py — HTML 可视化日报生成器
输出：reports/daily_report_YYYYMMDD.html

包含：
1. 市场状态仪表盘
2. 三模型融合评分分布图
3. 选股结果表格
4. 模拟交易结果
"""
import os
import sys
import datetime
import base64
from io import BytesIO

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(PROJECT_ROOT, 'reports')


def _ensure_reports_dir() -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    return REPORTS_DIR


def _fig_to_base64(fig) -> str:
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('ascii')


def generate_market_gauge(status: str, risk_level: str, recent_5d: float, recent_10d: float, recent_20d: float) -> str:
    fig, ax = plt.subplots(figsize=(5, 3), subplot_kw={'projection': 'polar'})
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 1)
    ax.axis('off')

    colors = {
        'bull': '#22c55e',
        'bear': '#ef4444',
        'neutral': '#eab308',
    }
    status_key = status.lower() if isinstance(status, str) else 'neutral'
    for key in ['bull', 'bear', 'neutral']:
        if key in status_key:
            status_key = key
            break
    color = colors.get(status_key, '#94a3b8')

    theta = np.linspace(np.pi, 0, 200)
    ax.fill_between(theta, 0.85, 1, color=color, alpha=0.25)
    ax.plot(theta, 0.85 * np.ones_like(theta), color=color, linewidth=6)

    arrow_angle = np.deg2rad(135)
    ax.annotate(
        '',
        xy=(arrow_angle, 1.05),
        xytext=(arrow_angle, 0.75),
        arrowprops=dict(arrowstyle='->', color=color, lw=3),
    )
    ax.text(0, 1.15, status.upper(), ha='center', va='center', fontsize=14, weight='bold', color=color)
    ax.text(0, 1.0, f'risk: {risk_level}', ha='center', va='center', fontsize=9, color='#475569')
    ax.text(0, 0.55, f'5d {recent_5d:+.2f}%\n10d {recent_10d:+.2f}%\n20d {recent_20d:+.2f}%', ha='center', va='center', fontsize=9, color='#334155')

    return _fig_to_base64(fig)


def generate_fusion_distribution_chart(stocks, score_key='fusion_score', title='三模型融合评分分布') -> str:
    if not stocks:
        return ''

    scores = [s.get(score_key, 0) or 0 for s in stocks]
    if not scores:
        return ''

    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    ax.hist(scores, bins=range(0, 105, 5), color='#3b82f6', edgecolor='white', linewidth=0.6)
    ax.axvline(np.mean(scores), color='#ef4444', linestyle='--', linewidth=1.5, label=f"均值 {np.mean(scores):.1f}")
    ax.set_title(title, fontsize=12, weight='bold', color='#0f172a')
    ax.set_xlabel('融合评分')
    ax.set_ylabel('标的数')
    ax.set_xlim(0, 100)
    ax.legend(loc='upper left')
    ax.grid(axis='y', alpha=0.25)
    fig.tight_layout()

    return _fig_to_base64(fig)


def generate_fusion_component_chart(stocks) -> str:
    if not stocks:
        return ''

    tech = [s.get('technical_score', 0) or 0 for s in stocks]
    chip = [s.get('chip_score', 0) or 0 for s in stocks]
    macro = [s.get('macro_score', 0) or 0 for s in stocks]

    if not tech:
        return ''

    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    x = np.arange(len(stocks))
    width = 0.25
    ax.bar(x - width, tech, width, label='技术面', color='#3b82f6')
    ax.bar(x, chip, width, label='筹码面', color='#22c55e')
    ax.bar(x + width, macro, width, label='宏观面', color='#eab308')
    ax.set_title('三维度评分对比', fontsize=12, weight='bold', color='#0f172a')
    ax.set_xticks(x)
    ax.set_xticklabels([s.get('ts_code', '') for s in stocks], rotation=45, ha='right', fontsize=8)
    ax.set_ylabel('评分')
    ax.set_ylim(0, 100)
    ax.legend(loc='upper right')
    ax.grid(axis='y', alpha=0.25)
    fig.tight_layout()

    return _fig_to_base64(fig)


def _get_market_status_data() -> dict:
    try:
        from market_status_detector import get_market_status
        return get_market_status() or {}
    except Exception:
        return {}


def _get_selection_data() -> dict:
    try:
        from selection_bridge import get_latest_selection
        return {'stocks': get_latest_selection(limit=50) or []}
    except Exception:
        return {'stocks': []}


def _get_papertrade_data() -> dict:
    try:
        from papertrader_final import PaperTraderFinal
        trader = PaperTraderFinal(initial_cash=1_000_000)
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        result = trader.run_single_day(today)
        trader.close()
        return result or {}
    except Exception:
        return {}


def generate_html_report() -> dict:
    report_date = datetime.datetime.now().strftime('%Y-%m-%d')
    report_path = os.path.join(_ensure_reports_dir(), f'daily_report_{report_date.replace("-", "")}.html')

    market = _get_market_status_data()
    selection = _get_selection_data()
    papertrade = _get_papertrade_data()
    stocks = selection.get('stocks', [])

    market_gauge_b64 = generate_market_gauge(
        status=market.get('status', 'neutral'),
        risk_level=market.get('risk_level', 'low'),
        recent_5d=market.get('recent_5d', 0.0),
        recent_10d=market.get('recent_10d', 0.0),
        recent_20d=market.get('recent_20d', 0.0),
    )
    fusion_dist_b64 = generate_fusion_distribution_chart(stocks, score_key='fusion_score', title='三模型融合评分分布')
    fusion_comp_b64 = generate_fusion_component_chart(stocks)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>每日分析报告 {report_date}</title>
<style>
  :root {{
    --bg: #f8fafc;
    --card: #ffffff;
    --text: #0f172a;
    --muted: #475569;
    --border: #e2e8f0;
    --accent: #3b82f6;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; background: var(--bg); color: var(--text); }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 24px; }}
  header {{ margin-bottom: 24px; }}
  h1 {{ font-size: 22px; margin: 0 0 6px; }}
  .meta {{ color: var(--muted); font-size: 13px; }}
  .grid {{ display: grid; grid-template-columns: repeat(12, 1fr); gap: 16px; }}
  .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 16px; box-shadow: 0 1px 2px rgba(15,23,42,0.04); }}
  .card h2 {{ font-size: 14px; margin: 0 0 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; }}
  .col-12 {{ grid-column: span 12; }}
  .col-6 {{ grid-column: span 6; }}
  .col-4 {{ grid-column: span 4; }}
  img {{ max-width: 100%; height: auto; border-radius: 8px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--muted); font-weight: 600; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; }}
  .badge-success {{ background: #dcfce7; color: #166534; }}
  .badge-warning {{ background: #fef9c3; color: #92400e; }}
  .badge-danger {{ background: #fee2e2; color: #991b1b; }}
  .metric {{ font-size: 22px; font-weight: 700; }}
  .metric-sub {{ color: var(--muted); font-size: 12px; }}
  .footer {{ margin-top: 24px; color: var(--muted); font-size: 12px; }}
  @media (max-width: 860px) {{
    .col-6, .col-4 {{ grid-column: span 12; }}
  }}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>每日分析报告</h1>
    <div class="meta">生成时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp; 报告日期：{report_date}</div>
  </header>

  <div class="grid">
    <!-- 市场状态 -->
    <div class="card col-4">
      <h2>市场状态</h2>
      <img src="data:image/png;base64,{market_gauge_b64}" alt="market gauge">
      <div style="margin-top:8px;">
        <div class="metric">{market.get('status', 'neutral').upper()}</div>
        <div class="metric-sub">风险等级：{market.get('risk_level', '-')}</div>
      </div>
    </div>

    <!-- 三模型融合评分分布 -->
    <div class="card col-4">
      <h2>三模型融合评分分布</h2>
      {'<img src="data:image/png;base64,' + fusion_dist_b64 + '" alt="fusion distribution">' if fusion_dist_b64 else '<div class="metric-sub">暂无数据</div>'}
    </div>

    <!-- 三维度评分对比 -->
    <div class="card col-4">
      <h2>三维度评分对比</h2>
      {'<img src="data:image/png;base64,' + fusion_comp_b64 + '" alt="fusion components">' if fusion_comp_b64 else '<div class="metric-sub">暂无数据</div>'}
    </div>

    <!-- 选股结果 -->
    <div class="card col-12">
      <h2>选股结果</h2>
      <table>
        <thead>
          <tr>
            <th>股票</th>
            <th>通道</th>
            <th>六维评分</th>
            <th>融合评分</th>
            <th>技术</th>
            <th>筹码</th>
            <th>宏观</th>
          </tr>
        </thead>
        <tbody>
"""

    for s in stocks[:20]:
        tech = s.get('technical_score')
        chip = s.get('chip_score')
        macro = s.get('macro_score')
        fusion = s.get('fusion_score')
        tech_str = f"{tech:.1f}" if isinstance(tech, (int, float)) else '-'
        chip_str = f"{chip:.1f}" if isinstance(chip, (int, float)) else '-'
        macro_str = f"{macro:.1f}" if isinstance(macro, (int, float)) else '-'
        fusion_str = f"{fusion:.1f}" if isinstance(fusion, (int, float)) else '-'
        strategy = s.get('strategy_type', '-')
        badge_class = 'badge-success' if strategy == '成长' else 'badge-warning' if strategy == '价值' else 'badge-danger'
        html += f"""
          <tr>
            <td>{s.get('name', '')} {s.get('ts_code', '')}</td>
            <td><span class="badge {badge_class}">{strategy}</span></td>
            <td>{s.get('six_dim_score', '-'):.1f}</td>
            <td>{fusion_str}</td>
            <td>{tech_str}</td>
            <td>{chip_str}</td>
            <td>{macro_str}</td>
          </tr>
"""

    html += """
        </tbody>
      </table>
    </div>

    <!-- 模拟交易 -->
    <div class="card col-12">
      <h2>模拟交易</h2>
      <div class="grid" style="grid-template-columns: repeat(4, 1fr); gap: 12px;">
        <div>
          <div class="metric-sub">净值</div>
          <div class="metric">""" + f"{papertrade.get('nav', 0):,.0f}" + """</div>
        </div>
        <div>
          <div class="metric-sub">现金</div>
          <div class="metric">""" + f"{papertrade.get('cash', 0):,.0f}" + """</div>
        </div>
        <div>
          <div class="metric-sub">持仓数</div>
          <div class="metric">""" + f"{papertrade.get('holdings_count', 0)}" + """</div>
        </div>
        <div>
          <div class="metric-sub">交易数</div>
          <div class="metric">""" + f"{papertrade.get('trade_count', 0)}" + """</div>
        </div>
      </div>
    </div>
  </div>

  <div class="footer">
    本报告由 stock_analysis_system/html_report_generator.py 自动生成 &nbsp;|&nbsp; 三模型融合：技术40% + 筹码30% + 宏观30%
  </div>
</div>
</body>
</html>
"""

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return {'report_path': report_path, 'format': 'html'}


if __name__ == '__main__':
    result = generate_html_report()
    print(result)
