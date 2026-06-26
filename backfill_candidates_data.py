#!/usr/bin/env python3
"""
补全观察池候选股票的技术/筹码数据
目的：扩展三模型融合覆盖度
数据源：Tushare Pro
"""
import os
import sys
import time
import logging
import sqlite3
import pandas as pd
import numpy as np
import tushare as ts

sys.path.insert(0, r'C:\Users\Fengpeng\stock_analysis_system')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = r'C:\Users\Fengpeng\stock_analysis_system\database\stock_analysis.db'
TUSHARE_TOKEN = os.environ.get('TUSHARE_TOKEN')
if not TUSHARE_TOKEN:
    raise EnvironmentError('TUSHARE_TOKEN 未设置')

pro = ts.pro_api(TUSHARE_TOKEN)


def get_candidates():
    """获取观察池候选股票（最近一批）"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()
    cur.execute('''
        SELECT DISTINCT s.ts_code, s.name, s.industry_code
        FROM stock_basic s
        WHERE s.industry_code IN (
            SELECT DISTINCT industry_code FROM watch_pool 
            WHERE entry_date = (SELECT MAX(entry_date) FROM watch_pool)
        )
        AND s.ts_code NOT IN (SELECT ts_code FROM holdings WHERE status='持有中')
        ORDER BY s.industry_code, s.ts_code
    ''')
    rows = cur.fetchall()
    conn.close()
    return rows


def fetch_daily(ts_code, start_date='20260101', end_date=None):
    """获取日线行情"""
    if end_date is None:
        end_date = pd.Timestamp.now().strftime('%Y%m%d')
    try:
        df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.rename(columns={
            'trade_date': 'trade_date',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'vol': 'volume',
            'amount': 'amount',
        })
        df['pct_change'] = df['close'].pct_change() * 100
        df['ts_code'] = ts_code
        return df[['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'pct_change']]
    except Exception as e:
        logger.debug(f"获取日线失败 {ts_code}: {e}")
        return pd.DataFrame()


def calculate_technical(df: pd.DataFrame) -> pd.DataFrame:
    """计算技术指标"""
    if len(df) < 20:
        return pd.DataFrame()
    df = df.sort_values('trade_date').reset_index(drop=True)
    close = df['close']
    # 均线
    df['ma5'] = close.rolling(5).mean()
    df['ma10'] = close.rolling(10).mean()
    df['ma20'] = close.rolling(20).mean()
    df['ma60'] = close.rolling(60).mean() if len(df) >= 60 else np.nan
    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    # RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    # 布林带
    df['boll_mid'] = close.rolling(20).mean()
    std = close.rolling(20).std()
    df['boll_upper'] = df['boll_mid'] + 2 * std
    df['boll_lower'] = df['boll_mid'] - 2 * std
    # 量能均线
    df['volume_ma5'] = df['volume'].rolling(5).mean()
    df['volume_ma20'] = df['volume'].rolling(20).mean()
    # 趋势与信号
    latest = df.iloc[-1]
    if latest['close'] > latest['ma20'] and latest['macd_hist'] > 0:
        df['trend'] = 'bullish'
        df['signal'] = 'buy'
    elif latest['close'] < latest['ma20'] and latest['macd_hist'] < 0:
        df['trend'] = 'bearish'
        df['signal'] = 'sell'
    else:
        df['trend'] = 'neutral'
        df['signal'] = 'hold'
    return df


def insert_daily(conn, df: pd.DataFrame):
    if df.empty:
        return 0
    cur = conn.cursor()
    inserted = 0
    for _, row in df.iterrows():
        try:
            cur.execute('''
                INSERT OR IGNORE INTO daily_quotes (ts_code, trade_date, open, high, low, close, volume, amount, pct_change, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            ''', (
                row['ts_code'], row['trade_date'], row['open'], row['high'], row['low'],
                row['close'], row['volume'], row['amount'], row['pct_change'],
                pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            inserted += cur.rowcount
        except Exception as e:
            logger.debug(f"插入daily_quotes失败 {row['ts_code']} {row['trade_date']}: {e}")
    conn.commit()
    return inserted


def insert_technical(conn, df: pd.DataFrame):
    if df.empty:
        return 0
    cur = conn.cursor()
    tech_cols = ['ts_code', 'trade_date', 'ma5', 'ma10', 'ma20', 'ma60',
                 'macd', 'macd_signal', 'macd_hist', 'rsi',
                 'boll_upper', 'boll_mid', 'boll_lower',
                 'volume_ma5', 'volume_ma20', 'trend', 'signal']
    df = df[tech_cols].copy()
    inserted = 0
    for _, row in df.iterrows():
        if pd.isna(row['rsi']) and pd.isna(row['macd_hist']):
            continue
        try:
            cur.execute('''
                INSERT OR IGNORE INTO technical_indicators (ts_code, trade_date, ma5, ma10, ma20, ma60,
                    macd, macd_signal, macd_hist, rsi, boll_upper, boll_mid, boll_lower,
                    volume_ma5, volume_ma20, trend, signal, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (
                row['ts_code'], row['trade_date'], row['ma5'], row['ma10'], row['ma20'], row['ma60'],
                row['macd'], row['macd_signal'], row['macd_hist'], row['rsi'],
                row['boll_upper'], row['boll_mid'], row['boll_lower'],
                row['volume_ma5'], row['volume_ma20'], row['trend'], row['signal'],
                pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            inserted += cur.rowcount
        except Exception as e:
            logger.debug(f"插入technical_indicators失败 {row['ts_code']} {row['trade_date']}: {e}")
    conn.commit()
    return inserted


def main():
    candidates = get_candidates()
    if not candidates:
        print('无候选股票')
        return
    print(f'=== 候选股票: {len(candidates)} 只 ===')
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    total_quote_insert = 0
    total_tech_insert = 0
    success_count = 0
    fail_count = 0
    
    for idx, (ts_code, name, industry_code) in enumerate(candidates, 1):
        print(f'[{idx}/{len(candidates)}] {ts_code} {name} | {industry_code}')
        try:
            daily_df = fetch_daily(ts_code)
            if daily_df.empty:
                print(f'  无日线数据')
                fail_count += 1
                continue
            q_insert = insert_daily(conn, daily_df)
            print(f'  daily_quotes 插入: {q_insert}')
            total_quote_insert += q_insert
            
            tech_df = calculate_technical(daily_df)
            t_insert = insert_technical(conn, tech_df)
            print(f'  technical_indicators 插入: {t_insert}')
            total_tech_insert += t_insert
            success_count += 1
            time.sleep(2)  # Tushare QPS限制
        except Exception as e:
            print(f'  失败: {e}')
            fail_count += 1
            continue
    
    conn.close()
    print(f'\n=== 补全完成 ===')
    print(f'成功: {success_count} 只')
    print(f'失败: {fail_count} 只')
    print(f'daily_quotes 插入: {total_quote_insert} 条')
    print(f'technical_indicators 插入: {total_tech_insert} 条')


if __name__ == '__main__':
    main()
