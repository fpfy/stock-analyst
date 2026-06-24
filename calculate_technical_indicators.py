"""
calculate_technical_indicators.py - 计算并存储技术指标（候选池优先版）
"""
import sqlite3
import logging
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
from technical_indicators import TechnicalIndicators

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

ITICK_TOKEN = __import__('os').environ.get('ITICK_TOKEN', '') or 'e88f98fd87d842bcb0076ed3404ec82c5f50fcbbf6634766bd052fcd889f7b86'
ITICK_KLINES_URL = 'https://api-free.itick.org/stock/klines'
ITICK_INTERVAL = 12.0  # 免费限流 5次/分钟 => >=12s


class TechnicalIndicatorCalculator:
    """技术指标计算器（候选池优先：先处理有价格数据的股票）"""
    
    def __init__(self, db_path: str = "database/stock_analysis.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.cursor = self.conn.cursor()
        self.ti = TechnicalIndicators(self.cursor)
        
    def get_candidate_stocks(self) -> List[str]:
        """获取候选池股票：优先 daily_quotes 有数据的，否则回退 stock_basic 前 50"""
        self.cursor.execute("""
            SELECT DISTINCT ts_code FROM daily_quotes 
            ORDER BY ts_code
        """)
        quoted = [row[0] for row in self.cursor.fetchall()]
        if quoted:
            logger.info(f"从 daily_quotes 获取 {len(quoted)} 只有价格数据的股票")
            return quoted
        
        # daily_quotes 为空时，尝试 iTick 回退（限流严格，只取少量）
        logger.info("daily_quotes 为空，尝试 iTick klines 回退（限流 5次/分钟）")
        itick_codes = self._fetch_itick_daily_quotes()
        if itick_codes:
            return itick_codes
        
        self.cursor.execute("""
            SELECT ts_code FROM stock_basic 
            WHERE ts_code NOT LIKE 'BJ%' AND ts_code NOT LIKE 'SH%'
            LIMIT 50
        """)
        fallback = [row[0] for row in self.cursor.fetchall()]
        logger.info(f"iTick 回退失败，回退 stock_basic 前 {len(fallback)} 只")
        return fallback
    
    def _fetch_itick_daily_quotes(self, max_codes: int = 10) -> List[str]:
        """
        iTick 回退：为少量候选股票拉取日线数据，写入 daily_quotes
        免费限流 5次/分钟，单次最多 10 只
        """
        if not ITICK_TOKEN:
            logger.warning("ITICK_TOKEN 未设置，跳过 iTick 回退")
            return []
        
        # 先取 stock_basic 中前 max_codes 只作为候选
        self.cursor.execute("""
            SELECT ts_code FROM stock_basic 
            WHERE ts_code NOT LIKE 'BJ%'
            LIMIT ?
        """, (max_codes,))
        candidates = [row[0] for row in self.cursor.fetchall()]
        if not candidates:
            return []
        
        headers = {'token': ITICK_TOKEN, 'accept': 'application/json'}
        success_codes = []
        
        # 分批：每批最多 10 只，每次请求间隔 12s
        batch_size = 10
        for i in range(0, len(candidates), batch_size):
            batch = candidates[i:i + batch_size]
            codes_str = ','.join([c.split('.')[0] for c in batch])
            region = batch[0].split('.')[1] if batch else 'SH'
            
            for attempt in range(3):
                try:
                    if attempt > 0:
                        time.sleep(ITICK_INTERVAL)
                    params = {'region': region, 'codes': codes_str, 'kType': '8', 'limit': '100'}
                    r = requests.get(ITICK_KLINES_URL, headers=headers, params=params, timeout=20)
                    if r.status_code == 200:
                        payload = r.json()
                        if payload.get('code') == 0 and payload.get('data'):
                            data = payload['data']
                            for code, rows in data.items():
                                if not isinstance(rows, list) or not rows:
                                    continue
                                full_code = None
                                for c in batch:
                                    if c.split('.')[0] == code:
                                        full_code = c
                                        break
                                if not full_code:
                                    continue
                                for row in rows:
                                    trade_date = datetime.fromtimestamp(row['t'] / 1000).strftime('%Y-%m-%d')
                                    self.cursor.execute("""
                                        INSERT OR REPLACE INTO daily_quotes 
                                        (ts_code, trade_date, open, high, low, close, volume, amount)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                    """, (
                                        full_code,
                                        trade_date,
                                        row.get('o'),
                                        row.get('h'),
                                        row.get('l'),
                                        row.get('c'),
                                        row.get('v'),
                                        row.get('tu'),
                                    ))
                                success_codes.append(full_code)
                            self.conn.commit()
                            logger.info(f"iTick klines 回退成功: {len(success_codes)}/{len(candidates)}")
                            break
                        elif payload.get('code') == 1:
                            logger.warning(f"iTick klines 业务错误: {payload.get('msg')}")
                            break
                except Exception as e:
                    logger.warning(f"iTick klines 请求失败: {e}")
                    time.sleep(ITICK_INTERVAL)
            
            if i + batch_size < len(candidates):
                time.sleep(ITICK_INTERVAL)
        
        return success_codes
    
    def get_latest_trade_date(self, ts_code: str) -> Optional[str]:
        """获取股票的最新交易日"""
        self.cursor.execute("""
            SELECT MAX(trade_date) FROM daily_quotes 
            WHERE ts_code = ?
        """, (ts_code,))
        row = self.cursor.fetchone()
        return row[0] if row and row[0] else None
    
    def calculate_and_store_indicators(self, ts_code: str, trade_date: str):
        """计算并存储单只股票技术指标"""
        try:
            indicators = self.ti.get_latest_technical_indicators(ts_code)
            if not indicators:
                logger.warning(f"无法获取股票 {ts_code} 的技术指标")
                return False
            
            trend_analysis = self.ti.analyze_trend(ts_code)
            
            self.cursor.execute("""
                INSERT OR REPLACE INTO technical_indicators 
                (ts_code, trade_date, ma5, ma10, ma20, ma60, macd, macd_signal, macd_hist, 
                 rsi, boll_upper, boll_mid, boll_lower, trend, signal, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ts_code,
                trade_date,
                indicators.get('ma_5'),
                indicators.get('ma_10'),
                indicators.get('ma_20'),
                indicators.get('ma_60'),
                indicators.get('macd_macd'),
                indicators.get('macd_signal'),
                indicators.get('macd_histogram'),
                indicators.get('rsi'),
                indicators.get('bb_upper'),
                indicators.get('bb_middle'),
                indicators.get('bb_lower'),
                trend_analysis.get('trend'),
                trend_analysis.get('signal'),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            return True
        except Exception as e:
            logger.error(f"计算股票 {ts_code} 技术指标失败: {e}")
            return False
    
    def run(self):
        """批量计算候选池技术指标"""
        logger.info("=== 开始批量计算技术指标 ===")
        
        stock_list = self.get_candidate_stocks()
        if not stock_list:
            logger.warning("候选池为空，退出")
            return
        
        success = 0
        skipped = 0
        failed = 0
        
        for i, ts_code in enumerate(stock_list, 1):
            try:
                latest_date = self.get_latest_trade_date(ts_code)
                if not latest_date:
                    logger.warning(f"股票 {ts_code} 没有交易日数据，跳过")
                    skipped += 1
                    continue
                
                if self.calculate_and_store_indicators(ts_code, latest_date):
                    success += 1
                else:
                    failed += 1
                
                if i % 10 == 0:
                    self.conn.commit()
                    logger.info(f"进度: {i}/{len(stock_list)} (成功:{success} 跳过:{skipped} 失败:{failed})")
                    
            except Exception as e:
                logger.error(f"处理股票 {ts_code} 失败: {e}")
                failed += 1
                continue
        
        self.conn.commit()
        logger.info(f"=== 技术指标计算完成: 成功 {success} / 跳过 {skipped} / 失败 {failed} ===")
        
        cur = self.conn.cursor()
        cur.execute('SELECT COUNT(*) FROM technical_indicators')
        total = cur.fetchone()[0]
        cur.execute('SELECT COUNT(DISTINCT ts_code) FROM technical_indicators')
        distinct = cur.fetchone()[0]
        logger.info(f"technical_indicators 表现状: {total} 行, {distinct} 只股票")
    
    def close(self):
        self.conn.close()

if __name__ == "__main__":
    calc = TechnicalIndicatorCalculator()
    try:
        calc.run()
    finally:
        calc.close()
