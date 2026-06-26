#!/usr/bin/env python3
"""
补全持仓股票的日线行情和技术指标
目的：为三模型融合提供数据基础
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


def get_holdings():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()
    cur.execute("SELECT ts_code, name FROM holdings WHERE status='持有中'")
    rows = cur.fetchall()
    conn.close()
    return rows


def fetch_daily(ts_code, start_date='20260101', end_date=None):
    """获取日线行情"""
    if end_date is None:
        end_date = pd.Timestamp.now().strftime('%Y%m%d')
    df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    if df is None or df.empty:
        return pd.DataFrame()
    # 标准化列名
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
    holdings = get_holdings()
    if not holdings:
        print('无持仓记录')
        return
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    total_quote_insert = 0
    total_tech_insert = 0
    for idx, (ts_code, name) in enumerate(holdings, 1):
        print(f'[{idx}/{len(holdings)}] {ts_code} {name}')
        try:
            daily_df = fetch_daily(ts_code)
            if daily_df.empty:
                print(f'  无日线数据')
                continue
            q_insert = insert_daily(conn, daily_df)
            print(f'  daily_quotes 插入: {q_insert}')
            total_quote_insert += q_insert
            tech_df = calculate_technical(daily_df)
            t_insert = insert_technical(conn, tech_df)
            print(f'  technical_indicators 插入: {t_insert}')
            total_tech_insert += t_insert
            time.sleep(2)  # Tushare QPS限制
        except Exception as e:
            print(f'  失败: {e}')
            continue
    conn.close()
    print(f'\\n总计: daily_quotes 插入 {total_quote_insert} 条, technical_indicators 插入 {total_tech_insert} 条')


if __name__ == '__main__':
    main()
