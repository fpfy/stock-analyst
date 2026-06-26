#!/usr/bin/env python3
"""
市场状态判断模块
基于上证指数近5/10/20日涨跌判断市场状态
"""
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime

DB_PATH = r'C:\Users\Fengpeng\stock_analysis_system\database\stock_analysis.db'


def get_market_status():
    """获取当前市场状态"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    
    # 获取上证指数数据
    df = pd.read_sql('''
        SELECT date, close, change_pct 
        FROM index_data 
        WHERE index_code="000001.SH" 
        ORDER BY date DESC LIMIT 30
    ''', conn)
    
    if df.empty:
        conn.close()
        return None
    
    # 计算近期涨跌
    recent_5d = df.head(5)['change_pct'].mean()
    recent_10d = df.head(10)['change_pct'].mean()
    recent_20d = df.head(20)['change_pct'].mean()
    
    # 判断市场状态
    if recent_5d > 0.3 and recent_10d > 0.2:
        status = 'bull'
        risk_level = 'medium'
        description = '近期持续上涨，市场情绪偏多'
    elif recent_5d < -0.3 and recent_10d < -0.2:
        status = 'bear'
        risk_level = 'high'
        description = '近期持续下跌，市场情绪偏空'
    else:
        status = 'neutral'
        risk_level = 'low'
        description = '市场震荡，情绪中性'
    
    result = {
        'date': df.iloc[0]['date'],
        'status': status,
        'risk_level': risk_level,
        'recent_5d': round(recent_5d, 4),
        'recent_10d': round(recent_10d, 4),
        'recent_20d': round(recent_20d, 4),
        'description': description
    }
    
    # 更新数据库
    cur = conn.cursor()
    cur.execute('''
        INSERT OR REPLACE INTO market_status (date, status, risk_level, macro_score, technical_score, composite_score, description, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        result['date'], result['status'], result['risk_level'],
        recent_5d, recent_10d, recent_20d, result['description'],
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ))
    conn.commit()
    conn.close()
    
    return result


if __name__ == '__main__':
    status = get_market_status()
    if status:
        print(f'市场状态: {status["status"]}')
        print(f'风险等级: {status["risk_level"]}')
        print(f'近5日: {status["recent_5d"]:.2f}%')
        print(f'近10日: {status["recent_10d"]:.2f}%')
        print(f'近20日: {status["recent_20d"]:.2f}%')
        print(f'描述: {status["description"]}')
    else:
        print('无法获取市场状态')
