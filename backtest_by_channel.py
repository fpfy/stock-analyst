"""backtest_by_channel.py — 双通道收益拆分"""
from pathlib import Path
from statistics import mean

raw = {
'000048.SZ':'000048.SZ','000014.SZ':'000014.SZ','000625.SZ':'000625.SZ','000568.SZ':'000568.SZ',
'000333.SZ':'000333.SZ','000526.SZ':'000526.SZ','000408.SZ':'000408.SZ','000596.SZ':'000596.SZ',
'000651.SZ':'000651.SZ','000663.SZ':'000663.SZ','000661.SZ':'000661.SZ','000567.SZ':'000567.SZ',
'000429.SZ':'000429.SZ','000012.SZ':'000012.SZ','000034.SZ':'000034.SZ','000550.SZ':'000550.SZ',
'000538.SZ':'000538.SZ','000411.SZ':'000411.SZ','603688.SH':'603688.SH','600132.SH':'600132.SH',
'688717.SH':'688717.SH','688556.SH':'688556.SH','001269.SZ':'001269.SZ','603519.SH':'603519.SH',
'301004.SZ':'301004.SZ','600809.SH':'600809.SH','688516.SH':'688516.SH','300274.SZ':'300274.SZ',
'600961.SH':'600961.SH','002847.SZ':'002847.SZ','605117.SH':'605117.SH','000007.SZ':'000007.SZ',
'000523.SZ':'000523.SZ','000933.SZ':'000933.SZ','688390.SH':'688390.SH','600779.SH':'600779.SH',
'300856.SZ':'300856.SZ','001309.SZ':'001309.SZ','300492.SZ':'300492.SZ','688525.SH':'688525.SH',
'301308.SZ':'301308.SZ','300972.SZ':'300972.SZ','300475.SZ':'300475.SZ','600549.SH':'600549.SH',
'000506.SZ':'000506.SZ','002842.SZ':'002842.SZ','300308.SZ':'300308.SZ','002215.SZ':'002215.SZ',
'688111.SH':'688111.SH','300857.SZ':'300857.SZ','603045.SH':'603045.SH','002378.SZ':'002378.SZ',
'300502.SZ':'300502.SZ','002893.SZ':'002893.SZ','300444.SZ':'300444.SZ','600610.SH':'600610.SH',
'002379.SZ':'002379.SZ','001337.SZ':'001337.SZ','600506.SH':'600506.SH','600726.SH':'600726.SH',
'000426.SZ':'000426.SZ','300773.SZ':'300773.SZ','603629.SH':'603629.SH','000688.SZ':'000688.SZ',
}

# 回测已落库trading_strategy里 date=2026-06-17 的找到 strategy_type
import sqlite3
from pathlib import Path
db = Path(__file__).parent / 'database' / 'stock_analysis.db'
c = sqlite3.connect(db).cursor()
rows = c.execute("SELECT ts_code, action FROM trading_strategy WHERE report_date='2026-06-17'").fetchall()
buys = [r[0] for r in rows]

# 手动关键词补通道
def channel_of(code):
    if code in {'000568.SZ','000526.SZ','000523.SZ','000651.SZ','000933.SZ','000007.SZ','000688.SZ','600132.SH','600961.SH','600809.SH','600549.SH','600610.SH','600726.SH','600506.SH','000426.SZ','300773.SZ'}:
        return '价值'
    return '成长'

for code in buys:
    if code not in channel_of.__closure__[0].cell_contents:
        pass

# 更严格读取最新 watch_list
watch_rows = c.execute("SELECT ts_code, strategy_type, updated_at FROM watch_list").fetchall()
watch_map = {}
for ts, st, u in watch_rows:
    if ts not in watch_map or (watch_map[ts][1] or '') < (u or ''):
        watch_map[ts] = (st, u or '')

g, v = [], []
for ts in buys:
    if ts in watch_map and watch_map[ts][0] in ('成长','价值'):
        if watch_map[ts][0]=='成长': g.append(ts)
        else: v.append(ts)
    else:
        g.append(ts)

# 从最新回测报告里解析起来各股收益（用已经生成 latest report）
from pathlib import Path
rep = sorted(Path('reports').glob('backtest_v3_*.md'))[-1].read_text(encoding='utf-8')
# 简易解析
import re

blocks = re.split(r'### \d{8} → 持有 \d{8}', rep)
section_rets = {}
for block in blocks[1:]:
    m = re.search(r'\| (\d{6}\.\w{2}) \| ([+\-]\d+\.\d+)%', block)
    codes = re.findall(r'\| (\d{6}\.\w{2}) \|', block)
    rets = re.findall(r'\| \d{6}\.\w{2} \| ([+\-]\d+\.\d+)%', block)
    if codes:
        section_rets[block[:8]] = dict(zip(codes, [float(x)/100 for x in rets]))

# 合并季度收益
all_returns = []
for section in section_rets.values():
    for code,ret in section.items():
        ch = channel_of(code)
        all_returns.append((code, ch, ret))

g_returns = [r for _,c,r in all_returns if c=='成长']
v_returns = [r for _,c,r in all_returns if c=='价值']

print('通道拆分')  
print('成长', len(g_returns), '只, avg=', mean(g_returns)*100 if g_returns else 0)
print('价值', len(v_returns), '只, avg=', mean(v_returns)*100 if v_returns else 0)
