"""
全量历史数据补全脚本 V3
- 财务：Tushare fina_indicator（按 ts_code 逐只拉，分批）
- 估值：Tushare daily_basic（按 trade_date 批量拉）
- 自动保存进度，支持断点续传
"""

import os, sys, time, logging, sqlite3, json, traceback
from datetime import datetime, timedelta
from tushare import pro_api

# 统一限流器
from rate_limiter import tushare_limiter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('logs/backfill_full.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 配置
DB_PATH = 'database/stock_analysis.db'
PROGRESS_FILE = 'logs/backfill_progress.json'
TOKEN = os.environ.get('TUSHARE_TOKEN')
if not TOKEN:
    # 从 key 目录或 config 读取
    token_files = ['config/tushare_token.txt', '../config/tushare_token.txt', 'key/tushare.key']
    for f in token_files:
        if os.path.exists(f):
            TOKEN = open(f).read().strip()
            break

pro = pro_api(TOKEN)

# 目标报告期（2023Q1-2026Q1）
TARGET_PERIODS = [
    '20231231', '20230331', '20230630', '20230930',
    '20240331', '20240630', '20240930', '20241231',
    '20250331', '20250930', '20251231', '20260331'
]

# 目标估值日期范围（2023-01-01 至 2026-06-15）
VALUATION_START = '20230101'
VALUATION_END = '20260615'


def get_all_stocks():
    """获取全市场股票列表"""
    # 从 stock_basic 获取
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT ts_code, name, industry FROM stock_basic WHERE is_st = 0")
    stocks = [{'ts_code': r[0], 'name': r[1], 'industry': r[2]} for r in c.fetchall()]
    conn.close()
    logger.info(f"全市场股票数: {len(stocks)}")
    return stocks


def load_progress():
    """加载断点续传进度"""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {'done_stocks': [], 'failed_stocks': [], 'valuation_dates': []}


def save_progress(progress):
    """保存进度"""
    os.makedirs('logs', exist_ok=True)
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def backfill_financial(stocks):
    """补全财务数据（fina_indicator）"""
    progress = load_progress()
    done_set = set(progress['done_stocks'])
    failed_set = set(progress['failed_stocks'])
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    batch_size = 50  # 每50只保存一次进度
    success_count = 0
    fail_count = 0
    skip_count = 0
    
    for i, stock in enumerate(stocks):
        ts_code = stock['ts_code']
        
        # 跳过已完成
        if ts_code in done_set:
            skip_count += 1
            continue
        
        try:
            # 拉取该股票的所有历史财务指标
            df = pro.fina_indicator(
                ts_code=ts_code,
                fields='ts_code,end_date,ann_date,roe,roe_yearly,netprofit_yoy,revenue_yoy,'
                       'grossprofit_margin,net_margin,debt_ratio,current_ratio,quick_ratio,'
                       'eps,bps,netprofit_dedt,operating_cf,rd_exp,assets_turn'
            )
            
            if df is None or df.empty:
                logger.warning(f"[{ts_code}] 无财务数据")
                failed_set.add(ts_code)
                fail_count += 1
                continue
            
            # 写入数据库（INSERT OR REPLACE）
            written = 0
            for _, row in df.iterrows():
                try:
                    c.execute("""
                        INSERT OR REPLACE INTO financial_data 
                        (ts_code, end_date, ann_date, roe, roe_yearly, net_profit_yoy,
                         revenue_yoy, grossprofit_margin, net_margin, debt_ratio,
                         current_ratio, quick_ratio, eps, bps, netprofit_dedt,
                         operating_cf, rd_exp, assets_turn)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row.get('ts_code'), row.get('end_date'), row.get('ann_date'),
                        row.get('roe'), row.get('roe_yearly'), row.get('netprofit_yoy'),
                        row.get('revenue_yoy'), row.get('grossprofit_margin'),
                        row.get('net_margin'), row.get('debt_ratio'),
                        row.get('current_ratio'), row.get('quick_ratio'),
                        row.get('eps'), row.get('bps'), row.get('netprofit_dedt'),
                        row.get('operating_cf'), row.get('rd_exp'), row.get('assets_turn')
                    ))
                    written += 1
                except Exception as e:
                    logger.debug(f"[{ts_code}] 写入失败: {e}")
                    continue
            
            conn.commit()
            done_set.add(ts_code)
            success_count += 1
            logger.info(f"[{i+1}/{len(stocks)}] {ts_code} 写入 {written} 条")

            # 限流：Tushare 约 200次/分钟 - 使用统一限流器 (1-3秒随机间隔)
            tushare_limiter.wait(min_interval=1.0, max_interval=3.0)
            
        except Exception as e:
            failed_set.add(ts_code)
            fail_count += 1
            logger.error(f"[{ts_code}] 拉取失败: {e}")
            time.sleep(1)
            continue
        
        # 批量保存进度
        if (i + 1) % batch_size == 0:
            progress['done_stocks'] = list(done_set)
            progress['failed_stocks'] = list(failed_set)
            save_progress(progress)
            logger.info(f"进度: 已完成 {len(done_set)}, 失败 {len(failed_set)}, 跳过 {skip_count}")
    
    # 最终保存
    progress['done_stocks'] = list(done_set)
    progress['failed_stocks'] = list(failed_set)
    save_progress(progress)
    
    conn.close()
    logger.info(f"财务补全完成: 成功 {success_count}, 失败 {fail_count}, 跳过 {skip_count}")
    return success_count, fail_count


def backfill_valuation(stocks):
    """补全估值历史数据（daily_basic）"""
    progress = load_progress()
    done_dates = set(progress.get('valuation_dates', []))
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 按日期批量拉取
    start = datetime.strptime(VALUATION_START, '%Y%m%d')
    end = datetime.strptime(VALUATION_END, '%Y%m%d')
    current = start
    date_count = 0
    
    while current <= end:
        date_str = current.strftime('%Y%m%d')
        
        # 跳过已完成日期
        if date_str in done_dates:
            current += timedelta(days=1)
            continue
        
        # 检查是否交易日（简单跳过周末）
        weekday = current.weekday()
        if weekday >= 5:
            current += timedelta(days=1)
            continue
        
        try:
            df = pro.daily_basic(
                trade_date=date_str,
                fields='ts_code,trade_date,close,pe,pb,dv_ttm,total_mv,circ_mv,turnover_rate'
            )
            
            if df is not None and not df.empty:
                written = 0
                for _, row in df.iterrows():
                    try:
                        c.execute("""
                            INSERT OR REPLACE INTO valuation_data
                            (ts_code, trade_date, close, pe, pb, dv_ttm, total_mv, circ_mv, turnover_rate)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row.get('ts_code'), row.get('trade_date'), row.get('close'),
                            row.get('pe'), row.get('pb'), row.get('dv_ttm'),
                            row.get('total_mv'), row.get('circ_mv'), row.get('turnover_rate')
                        ))
                        written += 1
                    except Exception:
                        continue
                
                conn.commit()
                done_dates.add(date_str)
                date_count += 1
                logger.info(f"[{date_str}] 估值数据写入 {written} 条")

            # 限流 - 使用统一限流器 (1-3秒随机间隔)
            tushare_limiter.wait(min_interval=1.0, max_interval=3.0)
            
        except Exception as e:
            logger.error(f"[{date_str}] 估值拉取失败: {e}")
            time.sleep(1)
        
        current += timedelta(days=1)
    
    conn.close()
    progress['valuation_dates'] = list(done_dates)
    save_progress(progress)
    logger.info(f"估值补全完成: {date_count} 个交易日")
    return date_count


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['financial', 'valuation', 'all'], default='all')
    parser.add_argument('--max-stocks', type=int, default=5000, help='最大处理股票数')
    args = parser.parse_args()
    
    os.makedirs('logs', exist_ok=True)
    stocks = get_all_stocks()[:args.max_stocks]
    
    if args.mode in ['financial', 'all']:
        logger.info("=" * 60)
        logger.info("开始补全财务数据")
        logger.info("=" * 60)
        backfill_financial(stocks)
    
    if args.mode in ['valuation', 'all']:
        logger.info("=" * 60)
        logger.info("开始补全估值历史")
        logger.info("=" * 60)
        backfill_valuation(stocks)
