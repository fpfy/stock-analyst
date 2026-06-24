"""
第一步：用 Tushare 下载历史财务 + 行情，保存为 CSV
按股票分批，避免限频
"""

import os, time, logging, sqlite3
from datetime import datetime

# 统一限流器
from rate_limiter import tushare_limiter

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = 'database/stock_analysis.db'
OUT_DIR = os.path.join(os.path.dirname(__file__), 'data_raw')
os.makedirs(OUT_DIR, exist_ok=True)

FIN_FIELDS = 'ts_code,end_date,ann_date,' \
    'roe_yearly,roa,grossprofit_margin,netprofit_margin,debt_ratio,' \
    'revenue_yoy,netprofit_yoy,op_yoy,' \
    'eps,bps,total_assets,total_liab,current_assets,current_liab,operating_cf'

def fetch_financial_csv(max_stocks=200):
    """
    下载历史财务数据到 CSV
    按股票逐只拉取近 3 年，存CSV便于后续分批入库
    """
    import tushare as ts
    ts.set_token(os.environ.get('TUSHARE_TOKEN', ''))
    pro = ts.pro_api()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT ts_code, name FROM stock_basic WHERE is_st=0 ORDER BY ts_code')
    stocks = c.fetchall()
    conn.close()

    out_path = os.path.join(OUT_DIR, f'financial_raw_{datetime.now().strftime("%Y%m%d")}.csv')
    total = 0
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('ts_code,end_date,ann_date,roe_yearly,roa,grossprofit_margin,netprofit_margin,debt_ratio,'
                'revenue_yoy,netprofit_yoy,op_yoy,eps,bps,total_assets,total_liab,'
                'current_assets,current_liab,operating_cf\n')
        for i, (ts_code, name) in enumerate(stocks[:max_stocks]):
            try:
                df = pro.fina_indicator(
                    ts_code=ts_code,
                    start_date='20230101',
                    end_date='20260101',
                    fields=FIN_FIELDS
                )
                if df is None or df.empty:
                    continue
                df = df[(df['end_date'] >= '20230101') & (df['end_date'] <= '20251231')]
                for _, row in df.iterrows():
                    line = ','.join(str(row.get(k, '')) for k in [
                        'ts_code','end_date','ann_date','roe_yearly','roa',
                        'grossprofit_margin','netprofit_margin','debt_ratio',
                        'revenue_yoy','netprofit_yoy','op_yoy',
                        'eps','bps','total_assets','total_liab',
                        'current_assets','current_liab','operating_cf'
                    ])
                    f.write(line + '\n')
                    total += 1
                if (i+1) % 50 == 0:
                    logger.info(f'  财务进度: {i+1}/{max_stocks} 已写{total}条')
                # 节流 - 使用统一限流器 (1-3秒随机间隔)
                tushare_limiter.wait(min_interval=1.0, max_interval=3.0)
            except Exception as e:
                if '每分钟' in str(e) or 'limit' in str(e).lower():
                    logger.warning(f'  限频，等待60s: {e}')
                    time.sleep(60)
                else:
                    logger.debug(f'  {ts_code} 失败: {e}')
    logger.info(f'财务 CSV 已生成: {out_path}，共 {total} 条')
    return out_path


def fetch_valuation_csv(max_stocks=200):
    """
    下载历史估值日线数据（daily_basic）到 CSV
    """
    import tushare as ts
    ts.set_token(os.environ.get('TUSHARE_TOKEN', ''))
    pro = ts.pro_api()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT ts_code FROM stock_basic WHERE is_st=0 ORDER BY ts_code')
    stocks = [r[0] for r in c.fetchall()]
    conn.close()

    out_path = os.path.join(OUT_DIR, f'valuation_raw_{datetime.now().strftime("%Y%m%d")}.csv')
    total = 0
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('ts_code,trade_date,close,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,total_mv,circ_mv\n')
        for i, ts_code in enumerate(stocks[:max_stocks]):
            try:
                df = pro.daily_basic(
                    ts_code=ts_code,
                    start_date='20220101',
                    end_date='20260612',
                    fields='ts_code,trade_date,close,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,total_mv,circ_mv'
                )
                if df is None or df.empty:
                    continue
                for _, row in df.iterrows():
                    line = ','.join(str(row.get(k, '')) for k in [
                        'ts_code','trade_date','close','pe','pe_ttm','pb',
                        'ps','ps_ttm','dv_ratio','dv_ttm','total_mv','circ_mv'
                    ])
                    f.write(line + '\n')
                    total += 1
                if (i+1) % 50 == 0:
                    logger.info(f'  估值进度: {i+1}/{max_stocks} 已写{total}条')
                # 节流 - 使用统一限流器 (1-3秒随机间隔)
                tushare_limiter.wait(min_interval=1.0, max_interval=3.0)
            except Exception as e:
                if '每分钟' in str(e) or 'limit' in str(e).lower():
                    logger.warning(f'  限频，等待60s: {e}')
                    time.sleep(60)
                else:
                    logger.debug(f'  {ts_code} 失败: {e}')
    logger.info(f'估值 CSV 已生成: {out_path}，共 {total} 条')
    return out_path


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--type', choices=['financial', 'valuation', 'both'], default='both')
    parser.add_argument('--max', type=int, default=200)
    args = parser.parse_args()

    if args.type in ('financial', 'both'):
        fetch_financial_csv(args.max)
    if args.type in ('valuation', 'both'):
        fetch_valuation_csv(args.max)
