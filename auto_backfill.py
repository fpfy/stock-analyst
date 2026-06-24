"""
自动数据补全模块
当检测到 valuation_data / technical_indicators / daily_quotes 数据不足时，
自动从 tushare/akshare 下载所需数据，无需人工干预。
"""
import sqlite3
import time
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "database" / "stock_analysis.db"

# 最小数据要求
MIN_VALUATION_ROWS = 60      # 至少60个交易日估值数据
MIN_TECHNICAL_ROWS = 60       # 至少60个交易日技术指标
MIN_DAILY_ROWS = 60           # 至少60个交易日日线数据


def _get_token():
    return os.environ.get('TUSHARE_TOKEN', '')


def _init_tushare():
    try:
        import tushare as ts
        token = _get_token()
        if not token:
            return None
        ts.set_token(token)
        return ts.pro_api()
    except Exception as e:
        logger.warning(f"tushare 初始化失败: {e}")
        return None


def check_valuation_gaps(codes):
    """检查 valuation_data 数据缺口，返回需要补全的 (code, missing_reason)"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    gaps = []

    for code in codes:
        cur.execute("""
            SELECT COUNT(*) as cnt, MAX(trade_date) as max_dt, MIN(trade_date) as min_dt
            FROM valuation_data
            WHERE ts_code = ?
        """, (code,))
        row = cur.fetchone()
        cnt, max_dt, min_dt = row if row else (0, None, None)

        reasons = []
        if cnt < MIN_VALUATION_ROWS:
            reasons.append(f"行数不足({cnt}<{MIN_VALUATION_ROWS})")

        # 检查 PE/PB/dv_ttm 是否有有效值
        cur.execute("""
            SELECT COUNT(*) FROM valuation_data
            WHERE ts_code = ? AND (pe IS NOT NULL OR pb IS NOT NULL OR dv_ttm IS NOT NULL)
        """, (code,))
        valid_cnt = cur.fetchone()[0]
        if valid_cnt == 0:
            reasons.append("无有效PE/PB/股息率")

        if reasons:
            gaps.append((code, 'valuation', '; '.join(reasons)))

    conn.close()
    return gaps


def check_technical_gaps(codes):
    """检查 technical_indicators 数据缺口"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    gaps = []

    for code in codes:
        cur.execute("""
            SELECT COUNT(*) as cnt, MAX(trade_date) as max_dt
            FROM technical_indicators
            WHERE ts_code = ?
        """, (code,))
        row = cur.fetchone()
        cnt, max_dt = row if row else (0, None)

        if cnt < MIN_TECHNICAL_ROWS:
            gaps.append((code, 'technical', f"行数不足({cnt}<{MIN_TECHNICAL_ROWS})"))

    conn.close()
    return gaps


def check_daily_gaps(codes):
    """检查 daily_quotes 数据缺口"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    gaps = []

    for code in codes:
        cur.execute("""
            SELECT COUNT(*) as cnt FROM daily_quotes WHERE ts_code = ?
        """, (code,))
        cnt = cur.fetchone()[0]
        if cnt < MIN_DAILY_ROWS:
            gaps.append((code, 'daily', f"行数不足({cnt}<{MIN_DAILY_ROWS})"))

    conn.close()
    return gaps


def backfill_valuation_tushare(codes):
    """从 tushare 补全 valuation_data"""
    pro = _init_tushare()
    if not pro:
        logger.error("tushare 未初始化，无法补全 valuation_data")
        return 0

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    total_inserted = 0

    for code in codes:
        try:
            # 限流
            time.sleep(0.8)

            # 拉取最近250个交易日
            end_date = datetime.now().strftime('%Y%m%d')
            df = pro.daily_basic(ts_code=code, start_date='20240101', end_date=end_date)

            if df is None or df.empty:
                logger.warning(f"[{code}] tushare daily_basic 返回空")
                continue

            inserted = 0
            for _, row in df.iterrows():
                td = str(row.get('trade_date', ''))
                if not td:
                    continue
                try:
                    cur.execute("""
                        INSERT OR IGNORE INTO valuation_data
                        (ts_code, trade_date, close, pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm, total_mv, circ_mv)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        code, td,
                        float(row['close']) if row.get('close') is not None else None,
                        float(row['pe']) if row.get('pe') is not None else None,
                        float(row['pe_ttm']) if row.get('pe_ttm') is not None else None,
                        float(row['pb']) if row.get('pb') is not None else None,
                        float(row['ps']) if row.get('ps') is not None else None,
                        float(row['ps_ttm']) if row.get('ps_ttm') is not None else None,
                        float(row['dv_ratio']) if row.get('dv_ratio') is not None else None,
                        float(row['dv_ttm']) if row.get('dv_ttm') is not None else None,
                        float(row['total_mv']) if row.get('total_mv') is not None else None,
                        float(row['circ_mv']) if row.get('circ_mv') is not None else None,
                    ))
                    inserted += cur.rowcount
                except Exception:
                    pass

            conn.commit()
            if inserted > 0:
                logger.info(f"[{code}] valuation_data 补全 +{inserted} 行")
            total_inserted += inserted

        except Exception as e:
            logger.error(f"[{code}] valuation_data 补全失败: {e}")

    conn.close()
    return total_inserted


def backfill_daily_tushare(codes):
    """从 tushare 补全 daily_quotes（用于后续计算技术指标）"""
    pro = _init_tushare()
    if not pro:
        return 0

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    total_inserted = 0

    for code in codes:
        try:
            time.sleep(0.8)
            end_date = datetime.now().strftime('%Y%m%d')
            df = pro.daily(ts_code=code, start_date='20240101', end_date=end_date)

            if df is None or df.empty:
                continue

            inserted = 0
            for _, row in df.iterrows():
                td = str(row.get('trade_date', ''))
                if not td:
                    continue
                try:
                    cur.execute("""
                        INSERT OR IGNORE INTO daily_quotes
                        (ts_code, trade_date, open, high, low, close, volume, amount, turn_rate)
                        VALUES (?,?,?,?,?,?,?,?,?)
                    """, (
                        code, td,
                        float(row['open']) if row.get('open') is not None else None,
                        float(row['high']) if row.get('high') is not None else None,
                        float(row['low']) if row.get('low') is not None else None,
                        float(row['close']) if row.get('close') is not None else None,
                        int(row['vol']) if row.get('vol') is not None else None,
                        float(row['amount']) if row.get('amount') is not None else None,
                        float(row['turnover_rate']) if row.get('turnover_rate') is not None else None,
                    ))
                    inserted += cur.rowcount
                except Exception:
                    pass

            conn.commit()
            if inserted > 0:
                logger.info(f"[{code}] daily_quotes 补全 +{inserted} 行")
            total_inserted += inserted

        except Exception as e:
            logger.error(f"[{code}] daily_quotes 补全失败: {e}")

    conn.close()
    return total_inserted


def auto_backfill(codes):
    """
    自动检测并补全数据缺口
    返回: (fixed_codes, still_missing)
    """
    logger.info("=== 自动数据补全检查 ===")

    # 1. 检查 valuation 缺口
    val_gaps = check_valuation_gaps(codes)
    tech_gaps = check_technical_gaps(codes)
    daily_gaps = check_daily_gaps(codes)

    if not val_gaps and not tech_gaps and not daily_gaps:
        logger.info("所有数据完整，无需补全")
        return codes, []

    # 2. 补全 valuation
    if val_gaps:
        val_codes = [c for c, _, _ in val_gaps]
        logger.info(f"valuation_data 缺口: {val_codes}")
        backfill_valuation_tushare(val_codes)

    # 3. 补全 daily（用于计算技术指标）
    if daily_gaps:
        daily_codes = list(set([c for c, _, _ in daily_gaps] + [c for c, _, _ in tech_gaps]))
        logger.info(f"daily_quotes 缺口: {daily_codes}")
        backfill_daily_tushare(daily_codes)

    # 4. 重新检查
    still_missing = []
    for code in codes:
        val_ok = not check_valuation_gaps([code])
        tech_ok = not check_technical_gaps([code])
        if not val_ok or not tech_ok:
            still_missing.append(code)

    if still_missing:
        logger.warning(f"补全后仍缺失: {still_missing}")
    else:
        logger.info("数据补全完成")

    fixed = [c for c in codes if c not in still_missing]
    return fixed, still_missing
