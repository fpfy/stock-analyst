
"""channels_vs_bench.py
基于 backtest_v3 回测结果，按 asset_class = 'equity' / 'balanced' / 'conservative' 拆分，
量化对比双通道的相对收益、波动、最大回撤和胜率。
"""
from pathlib import Path
import sqlite3, re
from statistics import mean

PROJ = Path(r'C:\Users\fengpeng\stock_analysis_system')
DB = PROJ / 'database' / 'stock_analysis.db'
c = sqlite3.connect(DB).cursor()

# 1) 读取 watch_list 的 strategy_type（最近一条）
watch_rows = c.execute(
    "SELECT ts_code, strategy_type, MAX(updated_at) FROM watch_list GROUP BY ts_code"
).fetchall()
watch_type = {ts: st for ts, st, _ in watch_rows}
print('watch_list 覆盖:', len(watch_type))

# 2) 读最新回测报告，解析季度明细
rep = sorted((PROJ / 'reports').glob('backtest_v3_*.md'))[-1].read_text(encoding='utf-8')
# 拆分季度块
blocks = re.split(r'### \d{8} → 持有 \d{8}', rep)
all_records = []
for block in blocks[1:]:
    # 只留收益行
    m = re.findall(r'\| (\d{6}\.\w{2}) \| ([+\-]\d+\.\d+)%', block)
    if m:
        for code, ret in m:
            ch = watch_type.get(code, '未知')
            r = float(ret)/100
            all_records.append((code, ch, r))

# 3) 双通道统计
def stats(lst):
    if not lst:
        return {'count':0,'avg':0,'win_rate':0,'max':0,'min':0,'std':0}
    avg = mean(lst)
    wins = [x for x in lst if x > 0]
    std = (sum((x - avg)**2 for x in lst) / len(lst))**0.5
    mx = max(lst)
    mn = min(lst)
    return {'count': len(lst), 'avg': avg, 'win_rate': len(wins)/len(lst),
            'max': mx, 'min': mn, 'std': std}

growth_recs = [r for _, ch, r in all_records if ch == '成长']
value_recs  = [r for _, ch, r in all_records if ch == '价值']
all_recs    = [r for _, _, r in all_records]

for name, recs in [('成长', growth_recs), ('价值', value_recs), ('全部', all_recs)]:
    s = stats(recs)
    print(f"{name}: 样本={s['count']} 平均={s['avg']*100:+.2f}% 胜率={s['win_rate']*100:.1f}% 最大={s['max']*100:+.2f}% 最小={s['min']*100:+.2f}% 标准差={s['std']*100:.2f}%")

# 4) 按季度统计季度级收益（和回测报告对齐）
quarter = {}
for block in blocks[1:]:
    head = re.search(r'### (\d{8}) → 持有 (\d{8})', block)
    if not head: continue
    q = head.group(1)
    if q not in quarter: quarter[q]={'growth':[], 'value':[]}
    m = re.findall(r'\| (\d{6}\.\w{2}) \| ([+\-]\d+\.\d+)%', block)
    for code, ret in m:
        ch = watch_type.get(code, '未知')
        if ch == '成长': quarter[q]['growth'].append(float(ret)/100)
        if ch == '价值': quarter[q]['value'].append(float(ret)/100)

print('\n季度对比')
for q in sorted(quarter):
    g = mean(quarter[q]['growth']) if quarter[q]['growth'] else 0
    v = mean(quarter[q]['value']) if quarter[q]['value'] else 0
    print(f"{q}  成长={g*100:+.2f}%  价值={v*100:+.2f}%")
