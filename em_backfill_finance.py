"""
东方财富数据回填脚本
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.absolute()
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
DB_DIR = BASE_DIR / "database"
PROGRESS_FILE = LOG_DIR / "em_backfill_progress.json"

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)


def load_progress():
    """加载回填进度"""
    try:
        if os.path.exists(PROGRESS_FILE):
            return json.load(open(PROGRESS_FILE, 'r'))
    except Exception:
        pass
    return {'done_codes': [], 'error_codes': []}


def save_progress(p):
    """保存回填进度"""
    os.makedirs(LOG_DIR, exist_ok=True)
    try:
        json.dump(p, open(PROGRESS_FILE, 'w'))
    except Exception:
        pass


def get_missing_dates(ts_code: str) -> list:
    """获取缺失的日期"""
    try:
        import akshare as ak
        import pandas as pd
        
        stock_daily = ak.stock_zh_a_hist(symbol=ts_code[:6], period="daily",
                                         start_date="20100101", end_date="20260620",
                                         adjust="qfq")
        if stock_daily.empty:
            return []
        
        stock_daily['日期'] = pd.to_datetime(stock_daily['日期'])
        all_dates = set(stock_daily['日期'].apply(lambda x: x.strftime('%Y%m%d')))
        
        # 检查本地数据库
        import sqlite3
        conn = sqlite3.connect(str(DB_DIR / "stock_analysis.db"))
        local_dates = set()
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT trade_date FROM stock_daily WHERE ts_code='{ts_code}'")
            for row in cursor.fetchall():
                local_dates.add(str(row[0]))
        except Exception:
            pass
        conn.close()
        
        missing = sorted(all_dates - local_dates)
        logger.info(f"{ts_code}: 总共{len(all_dates)}天，缺失{len(missing)}天")
        return missing
    except Exception as e:
        logger.error(f"获取缺失日期失败 {ts_code}: {e}")
        return []
