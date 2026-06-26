"""
observation_pool_builder.py — 观察池生成与宏观路由

目标：
1. 基于 Phase 1 宏观敏感度/IC 结果，选出当期景气行业
2. 在 stock_analysis_system 的 SQLite 中选出这些行业下的优质个股
3. 用现有六维评分做二次过滤，输出成长/价值双通道观察池
4. 结果可直接对接 selection_bridge.persist_selection_results()

设计原则：
- 不使用 dual_strategy_selector.py，避免 akshare 实时接口阻塞
- 全部基于本地数据：data/*.parquet + database/stock_analysis.db
- 宏观路由逻辑与六维评分分层，不混在一个循环里
"""

import os
import sys
import time
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional

import pandas as pd
import numpy as np
import sqlite3

logger = logging.getLogger(__name__)

# 路径处理
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(MODULE_DIR, '..', 'data')
DB_PATH = os.path.join(MODULE_DIR, 'database', 'stock_analysis.db')

# 宏观因子到行业敏感度的映射文件
BETA_SENSITIVITY_PATH = os.path.join(DATA_DIR, 'industry_sensitivity_rolling_ols.parquet')
PCA_SENSITIVITY_PATH = os.path.join(DATA_DIR, 'industry_sensitivity_pca.parquet')
IC_COMPARE_PATH = os.path.join(DATA_DIR, 'ic_analysis_compare.parquet')

# 六维评分权重（与现有系统保持一致）
SIX_DIM_WEIGHTS = {
    'growth': 0.20,      # 成长能力：ROE/营收/利润增速
    'profitability': 0.15, # 盈利能力：毛利率/净利率
    'quality': 0.15,     # 质量：负债率/现金流
    'valuation': 0.20,   # 估值：PE/PB分位
    'momentum': 0.15,    # 动量：ret20/Z-score
    'industry': 0.15,    # 行业景气：宏观敏感度得分
}

# 实时估值 fallback 配置
REALTIME_FALLBACK_ENABLED = os.environ.get('OBSERVATION_POOL_REALTIME', '1') == '1'
REALTIME_PRIMARY_SOURCE = os.environ.get('OBSERVATION_POOL_REALTIME_SOURCE', 'tushare')  # tushare / akshare
REALTIME_CHUNK_SIZE = int(os.environ.get('OBSERVATION_POOL_REALTIME_CHUNK', '200'))


class ObservationPoolBuilder:
    """观察池构建器"""

    def __init__(self, db_path: str = None, weights: Dict[str, float] = None):
        self.db_path = db_path or DB_PATH
        self.weights = weights or SIX_DIM_WEIGHTS.copy()
        self.conn = None
        self.cursor = None

    def _connect(self):
        """连接数据库，并确保 stock_basic 有 industry_code 字段"""
        self.conn = sqlite3.connect(self.db_path, timeout=30)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=10000")
        self.cursor = self.conn.cursor()
        self._ensure_industry_code_column()

    def _ensure_industry_code_column(self):
        """确保 stock_basic 表有 industry_code 字段，没有则从 akshare 补充"""
        # 检查列是否存在
        cols = [r[1] for r in self.cursor.execute("PRAGMA table_info(stock_basic)").fetchall()]
        if 'industry_code' in cols:
            return

        logger.info("stock_basic 缺少 industry_code 字段，正在从 akshare 补充...")
        try:
            import akshare as ak
            sw = ak.sw_index_first_info()
            # 映射: 行业名称 -> 行业代码（去掉 .SI 后缀）
            name_to_code = {}
            for _, row in sw.iterrows():
                name = row['行业名称']
                code = row['行业代码'].replace('.SI', '')
                name_to_code[name] = code

            # 添加列
            self.cursor.execute("ALTER TABLE stock_basic ADD COLUMN industry_code TEXT")
            updated = 0
            for ts_code, industry in self.cursor.execute("SELECT ts_code, industry FROM stock_basic").fetchall():
                code = name_to_code.get(industry)
                if code:
                    self.cursor.execute("UPDATE stock_basic SET industry_code = ? WHERE ts_code = ?", (code, ts_code))
                    updated += 1
            self.conn.commit()
            logger.info(f"industry_code 补充完成: {updated}/{self.cursor.execute('SELECT COUNT(*) FROM stock_basic').fetchone()[0]} 条")
        except Exception as e:
            logger.error(f"补充 industry_code 失败: {e}")
            logger.warning("将回退到按行业名称模糊匹配，准确率可能下降")

    def _close(self):
        """关闭连接"""
        try:
            if self.conn:
                self.conn.commit()
                self.conn.close()
        except Exception:
            pass
        self.conn = None
        self.cursor = None

    def load_macro_sensitivity(self, use_pca: bool = False) -> pd.DataFrame:
        """
        加载宏观敏感度，返回最新一期的宽矩阵
        返回: DataFrame [industry_code, factor_name, beta]
        use_pca=True 时读取 PCA 降维后的敏感度，factor_name 为 PC1~PC5
        """
        path = PCA_SENSITIVITY_PATH if use_pca else BETA_SENSITIVITY_PATH
        if not os.path.exists(path):
            raise FileNotFoundError(f"未找到宏观敏感度文件: {path}")

        sens_long = pd.read_parquet(path)
        latest_date = sens_long['trade_date'].max()
        sens_latest = sens_long[sens_long['trade_date'] == latest_date].copy()
        logger.info(f"宏观敏感度最新日期: {latest_date.date()}, 记录数: {len(sens_latest)}, 模式={'PCA' if use_pca else 'RollingOLS'}")
        return sens_latest[['industry_code', 'factor_name', 'beta']]

    def load_recent_factor_performance(self, recent_months: int = 3) -> pd.DataFrame:
        """
        加载因子近期表现（近N个月的ICIR）
        返回: DataFrame [factor, icir, ic_mean, ic_std, n_months]
        """
        ic_beta_path = os.path.join(DATA_DIR, 'ic_analysis_rolling_ols_v2.parquet')
        if not os.path.exists(ic_beta_path):
            logger.warning(f"未找到IC数据: {ic_beta_path}")
            return pd.DataFrame()

        ic_df = pd.read_parquet(ic_beta_path)
        ic_df = ic_df[ic_df['method'] == 'beta']

        latest_date = ic_df['trade_date'].max()
        cutoff = latest_date - pd.DateOffset(months=recent_months)
        recent = ic_df[ic_df['trade_date'] > cutoff].copy()

        if len(recent) == 0:
            return pd.DataFrame()

        stats_list = []
        for factor in recent['factor'].unique():
            factor_ic = recent[recent['factor'] == factor]['ic']
            if len(factor_ic) < 2:
                continue
            ic_mean = factor_ic.mean()
            ic_std = factor_ic.std()
            icir = ic_mean / ic_std if ic_std > 0 else 0
            stats_list.append({
                'factor': factor,
                'icir': icir,
                'ic_mean': ic_mean,
                'ic_std': ic_std,
                'n_months': len(factor_ic)
            })

        result = pd.DataFrame(stats_list)
        result = result.sort_values('icir', ascending=False)
        logger.info(f"近期({recent_months}个月)因子表现: {len(result)}个因子")
        return result

    def build_macro_scores(self, sens_long: pd.DataFrame, ic_ranking: pd.DataFrame = None, factor_names: List[str] = None) -> pd.DataFrame:
        """
        计算行业宏观得分
        factor_names: 若为None则自动从sens_long读取，用于兼容PCA模式
        """
        # 自动检测因子名称（兼容PCA模式）
        if factor_names is None:
            factor_names = sorted(sens_long['factor_name'].unique().tolist())
        
        # 加载因子信号
        macro_factors_path = os.path.join(DATA_DIR, 'macro_factors.parquet')
        if not os.path.exists(macro_factors_path):
            raise FileNotFoundError(f"未找到宏观因子文件: {macro_factors_path}")

        factors = pd.read_parquet(macro_factors_path)
        signal_cols = [f'{f}_signal' for f in factor_names]
        
        # 取最新信号
        available_signal_cols = [c for c in signal_cols if c in factors.columns]
        if not available_signal_cols:
            logger.warning(f"宏观因子文件中未找到信号列: {signal_cols}，所有信号设为0")
            latest_signals = pd.Series(0, index=factor_names)
        else:
            latest_signals = factors[['trade_date'] + available_signal_cols].dropna().sort_values('trade_date').iloc[-1]
        
        signal_map = {}
        for col, name in zip(available_signal_cols, factor_names):
            if col in latest_signals.index:
                val = latest_signals[col]
                signal_map[name] = 0 if pd.isna(val) else int(val)
            else:
                signal_map[name] = 0

        logger.info(f"最新宏观信号: {signal_map}")

        # 构建权重映射（近期IC表现动态加权）
        weight_map = {}
        base_weight = 1.0 / len(factor_names)
        recent_perf = self.load_recent_factor_performance(recent_months=3)

        if len(recent_perf) > 0:
            perf_map = dict(zip(recent_perf['factor'], recent_perf['icir']))
            positive_sum = sum(max(perf_map.get(f, 0), 0) for f in factor_names)

            for factor in factor_names:
                icir = perf_map.get(factor, 0)
                if icir > 0:
                    # 近期表现好，权重加成
                    weight_map[factor] = base_weight * 1.5 + (icir / positive_sum if positive_sum > 0 else 0)
                else:
                    # 近期表现差，权重减半
                    weight_map[factor] = base_weight * 0.5
        else:
            weight_map = {name: base_weight for name in factor_names}

        # PMI特殊规则：若PMI近期ICIR<=0，强制降权为0
        pmi_icir = 0.0
        if len(recent_perf) > 0 and 'pmi' in recent_perf['factor'].values:
            pmi_icir = recent_perf[recent_perf['factor'] == 'pmi']['icir'].iloc[0]
        if pmi_icir <= 0 and 'pmi' in weight_map:
            weight_map['pmi'] = 0.0
            logger.info("PMI近期ICIR<=0，纳入观察池路由但权重为0")

        # 归一化
        total = sum(weight_map.values())
        if total > 0:
            weight_map = {k: v / total for k, v in weight_map.items()}
        logger.info(f"因子权重: { {k: f'{v:.3f}' for k, v in weight_map.items()} }")

        # 计算行业得分
        sens_pivot = sens_long.pivot(index='industry_code', columns='factor_name', values='beta').fillna(0)
        industry_scores = []
        for industry_code in sens_pivot.index:
            score = 0.0
            details = {}
            for factor in factor_names:
                beta = sens_pivot.loc[industry_code, factor] if factor in sens_pivot.columns else 0
                signal = signal_map.get(factor, 0)
                weight = weight_map.get(factor, 0)
                contribution = weight * beta * signal
                score += contribution
                details[f'{factor}_beta'] = beta
                details[f'{factor}_signal'] = signal
                details[f'{factor}_weight'] = weight
                details[f'{factor}_contrib'] = contribution

            industry_scores.append({
                'industry_code': industry_code,
                'macro_score': score,
                **details
            })

        score_df = pd.DataFrame(industry_scores)
        score_df = score_df.sort_values('macro_score', ascending=False).reset_index(drop=True)
        score_df['macro_rank'] = score_df.index + 1
        logger.info(f"行业宏观得分计算完成: {len(score_df)} 个行业")
        logger.info(f"Top 3: {score_df.head(3)[['industry_code', 'macro_score']].to_dict('records')}")
        return score_df

    def get_industry_candidates(self, macro_scores: pd.DataFrame, top_n: int = 10) -> List[str]:
        """
        根据宏观得分选出行业观察池
        返回: industry_code 列表
        """
        candidates = macro_scores.head(top_n)['industry_code'].tolist()
        logger.info(f"宏观路由选出 {len(candidates)} 个景气行业: {candidates}")
        return candidates

    def query_local_stock_universe(self, industry_codes: List[str]) -> pd.DataFrame:
        """
        从本地 SQLite 查询候选股票池
        注意：valuation_data 数据稀疏，取最近一个有足够覆盖度的估值日
        若本地无数据或覆盖度不足，则触发实时估值 fallback
        """
        # 1. 优先读取本地 valuation_data
        self.cursor.execute("""
            SELECT trade_date, COUNT(*) as cnt 
            FROM valuation_data 
            GROUP BY trade_date 
            HAVING cnt >= 1000
            ORDER BY trade_date DESC 
            LIMIT 1
        """)
        row = self.cursor.fetchone()
        if not row:
            logger.warning("valuation_data 无足够覆盖度的日期，尝试实时 fallback")
            return self._try_realtime_valuation_fallback(industry_codes)

        latest_val_date, cnt = row
        logger.info(f"本地估值日期: {latest_val_date} ({cnt} 只)")

        # 2. 本地查询候选股票
        query = """
            SELECT 
                v.ts_code,
                v.trade_date,
                v.close,
                v.pe,
                v.pb,
                v.dv_ttm,
                b.industry,
                b.name,
                f.roe,
                f.revenue_yoy,
                f.net_profit_yoy,
                f.debt_ratio,
                f.gross_margin
            FROM valuation_data v
            JOIN stock_basic b ON v.ts_code = b.ts_code
            LEFT JOIN financial_data f ON v.ts_code = f.ts_code 
                AND f.end_date = (
                    SELECT MAX(end_date) FROM financial_data WHERE ts_code = v.ts_code
                )
            WHERE v.trade_date = ?
              AND v.close IS NOT NULL
              AND v.close > 0
            ORDER BY v.ts_code
        """
        self.cursor.execute(query, [latest_val_date])
        rows = self.cursor.fetchall()

        if not rows:
            logger.warning("本地 valuation_data 无记录，尝试实时 fallback")
            return self._try_realtime_valuation_fallback(industry_codes)

        cols = ['ts_code', 'trade_date', 'close', 'pe', 'pb', 'dv_ttm',
                'industry', 'name', 'roe', 'revenue_yoy', 'net_profit_yoy',
                'debt_ratio', 'gross_margin']
        df = pd.DataFrame(rows, columns=cols)
        logger.info(f"本地全量股票池: {len(df)} 只")

        # 3. 行业过滤
        mapped = self._filter_by_industry_code(df, industry_codes)
        if len(mapped) > 0:
            logger.info(f"通过 industry_code 过滤: {len(mapped)} 只")
            return mapped

        matched = self._filter_by_industry_name(df, industry_codes)
        if len(matched) > 0:
            logger.info(f"通过行业名称近似匹配: {len(matched)} 只")
            return matched

        logger.warning("本地行业匹配未命中，返回全量股票池")
        return self._map_industry_name_to_code(df)

    def _try_realtime_valuation_fallback(self, industry_codes: List[str]) -> pd.DataFrame:
        """
        实时估值 fallback：当本地 valuation_data 不足时，从云端拉取候选股票估值
        
        优先级：
        1. Tushare daily_basic（批量）
        2. akshare 实时估值接口（单股/批量）
        
        拉取后写回本地 SQLite，避免重复调用
        """
        if not REALTIME_FALLBACK_ENABLED:
            logger.warning("实时估值 fallback 已禁用，返回空 DataFrame")
            return pd.DataFrame()

        # 先确定候选股票代码：从 stock_basic 中按行业过滤
        candidate_codes = self._get_candidate_codes_by_industry(industry_codes)
        if not candidate_codes:
            logger.warning("无候选股票代码，跳过实时 fallback")
            return pd.DataFrame()

        logger.info(f"实时 fallback 候选股票: {len(candidate_codes)} 只")

        # 尝试 Tushare
        if REALTIME_PRIMARY_SOURCE == 'tushare':
            df = self._fetch_realtime_tushare(candidate_codes)
            if df is not None and not df.empty:
                return self._finalize_realtime_fallback(df, industry_codes)

        # 回退 akshare
        df = self._fetch_realtime_akshare(candidate_codes)
        if df is not None and not df.empty:
            return self._finalize_realtime_fallback(df, industry_codes)

        logger.error("所有实时估值源均失败，返回空 DataFrame")
        return pd.DataFrame()

    def _get_candidate_codes_by_industry(self, industry_codes: List[str]) -> List[str]:
        """从 stock_basic 获取候选股票代码"""
        if not industry_codes:
            return []

        placeholders = ','.join(['?'] * len(industry_codes))
        rows = self.cursor.execute(
            f"SELECT ts_code FROM stock_basic WHERE industry_code IN ({placeholders})",
            industry_codes
        ).fetchall()
        return [r[0] for r in rows if r and r[0]]

    def _fetch_realtime_tushare(self, candidate_codes: List[str]) -> Optional[pd.DataFrame]:
        """Tushare daily_basic 批量获取实时估值"""
        try:
            import tushare as ts
            token = os.environ.get('TUSHARE_TOKEN', '')
            if not token:
                logger.warning("TUSHARE_TOKEN 未设置，跳过 Tushare fallback")
                return None

            ts.set_token(token)
            pro = ts.pro_api()
            today = datetime.now().strftime('%Y%m%d')

            chunks = []
            for i in range(0, len(candidate_codes), REALTIME_CHUNK_SIZE):
                chunk = candidate_codes[i:i + REALTIME_CHUNK_SIZE]
                try:
                    time.sleep(0.4)  # 限流
                    df = pro.daily_basic(
                        ts_code=','.join(chunk),
                        trade_date=today,
                        fields='ts_code,close,pe,pb,dv_ttm,total_mv,trade_date'
                    )
                    if df is not None and not df.empty:
                        chunks.append(df)
                except Exception as e:
                    logger.warning(f"Tushare daily_basic chunk {i} failed: {e}")
                    time.sleep(1)

            if not chunks:
                return None

            result = pd.concat(chunks, ignore_index=True)
            logger.info(f"Tushare fallback 成功: {len(result)} 只")
            return result

        except Exception as e:
            logger.error(f"Tushare fallback 失败: {e}")
            return None

    def _fetch_realtime_akshare(self, candidate_codes: List[str]) -> Optional[pd.DataFrame]:
        """akshare 实时估值接口（单股循环，稳定性较低，仅作最后回退）"""
        try:
            import akshare as ak
            rows = []
            for code in candidate_codes:
                try:
                    time.sleep(0.3)  # 降低被封风险
                    df = ak.stock_individual_info_em(symbol=code)
                    if df is not None and not df.empty:
                        # 提取关键字段
                        info = {}
                        for _, row in df.iterrows():
                            info[row['item']] = row['value']
                        rows.append({
                            'ts_code': code,
                            'close': info.get('最新价') or info.get('最新价') or 0,
                            'pe': info.get('市盈率') or 0,
                            'pb': info.get('市净率') or 0,
                            'dv_ttm': info.get('股息率') or 0,
                            'trade_date': datetime.now().strftime('%Y%m%d'),
                        })
                except Exception as e:
                    logger.debug(f"akshare fallback {code} failed: {e}")

            if not rows:
                return None

            result = pd.DataFrame(rows)
            logger.info(f"akshare fallback 成功: {len(result)} 只")
            return result

        except Exception as e:
            logger.error(f"akshare fallback 失败: {e}")
            return None

    def _finalize_realtime_fallback(self, valuation_df: pd.DataFrame, industry_codes: List[str]) -> pd.DataFrame:
        """
        将实时估值结果与 stock_basic/financial_data 合并，写回本地 SQLite
        """
        # 标准化列名
        valuation_df = valuation_df.rename(columns={
            'trade_date': 'trade_date',
            'ts_code': 'ts_code',
            'close': 'close',
            'pe': 'pe',
            'pb': 'pb',
            'dv_ttm': 'dv_ttm',
        })

        # 写回本地 valuation_data
        try:
            self._connect()
            for _, row in valuation_df.iterrows():
                self.cursor.execute(
                    """
                    INSERT OR REPLACE INTO valuation_data 
                        (ts_code, trade_date, close, pe, pb, dv_ttm, total_mv, circ_mv, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        row.get('ts_code'),
                        str(row.get('trade_date', '')),
                        row.get('close'),
                        row.get('pe'),
                        row.get('pb'),
                        row.get('dv_ttm'),
                        row.get('total_mv'),
                        row.get('circ_mv'),
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    )
                )
            self.conn.commit()
            logger.info(f"实时估值写回本地: {len(valuation_df)} 条")
        except Exception as e:
            logger.warning(f"实时估值写回失败: {e}")

        # 与 stock_basic/financial_data 合并
        query = """
            SELECT 
                v.ts_code,
                v.trade_date,
                v.close,
                v.pe,
                v.pb,
                v.dv_ttm,
                b.industry,
                b.name,
                f.roe,
                f.revenue_yoy,
                f.net_profit_yoy,
                f.debt_ratio,
                f.gross_margin
            FROM valuation_data v
            JOIN stock_basic b ON v.ts_code = b.ts_code
            LEFT JOIN financial_data f ON v.ts_code = f.ts_code 
                AND f.end_date = (
                    SELECT MAX(end_date) FROM financial_data WHERE ts_code = v.ts_code
                )
            WHERE v.trade_date = ?
              AND v.close IS NOT NULL
              AND v.close > 0
            ORDER BY v.ts_code
        """
        self.cursor.execute(query, [str(valuation_df['trade_date'].iloc[0])])
        rows = self.cursor.fetchall()
        cols = ['ts_code', 'trade_date', 'close', 'pe', 'pb', 'dv_ttm',
                'industry', 'name', 'roe', 'revenue_yoy', 'net_profit_yoy',
                'debt_ratio', 'gross_margin']
        df = pd.DataFrame(rows, columns=cols)

        # 行业过滤
        mapped = self._filter_by_industry_code(df, industry_codes)
        if len(mapped) > 0:
            return mapped

        matched = self._filter_by_industry_name(df, industry_codes)
        if len(matched) > 0:
            return matched

        return self._map_industry_name_to_code(df)


    def _map_industry_name_to_code(self, df: pd.DataFrame) -> pd.DataFrame:
        """将 industry 中文名称映射为申万行业代码"""
        if 'industry_code' in df.columns:
            return df

        # 优先从 stock_basic 读取已有映射
        if self.cursor:
            code_map = {}
            for ts_code, code in self.cursor.execute("SELECT ts_code, industry_code FROM stock_basic WHERE industry_code IS NOT NULL").fetchall():
                code_map[ts_code] = code
            if code_map:
                df['industry_code'] = df['ts_code'].map(code_map)
                mapped = df['industry_code'].notna().sum()
                if mapped > 0:
                    logger.info(f"从 stock_basic 映射 industry_code: {mapped}/{len(df)} 条")
                    return df

        # 回退：用 akshare 申万行业列表做名称→代码映射
        try:
            import akshare as ak
            sw = ak.sw_index_first_info()
            name_to_code = {row['行业名称']: row['行业代码'].replace('.SI', '') for _, row in sw.iterrows()}
            df['industry_code'] = df['industry'].map(name_to_code)
            mapped = df['industry_code'].notna().sum()
            logger.info(f"通过 akshare 名称映射 industry_code: {mapped}/{len(df)} 条")
        except Exception as e:
            logger.warning(f"industry_code 名称映射失败: {e}")
            df['industry_code'] = None

        return df

    def _filter_by_industry_code(self, df: pd.DataFrame, industry_codes: List[str]) -> pd.DataFrame:
        """通过 industry_code 精确过滤，并保留 industry_code 字段"""
        placeholders = ','.join(['?'] * len(industry_codes))
        rows = self.cursor.execute(
            f"SELECT ts_code, industry_code FROM stock_basic WHERE industry_code IN ({placeholders})",
            industry_codes
        ).fetchall()
        if not rows:
            return pd.DataFrame()
        code_map = {ts_code: icode for ts_code, icode in rows}
        filtered = df[df['ts_code'].isin(code_map.keys())].copy()
        filtered['industry_code'] = filtered['ts_code'].map(code_map)
        return filtered

    def _filter_by_industry_name(self, df: pd.DataFrame, industry_codes: List[str]) -> pd.DataFrame:
        """通过行业名称关键词近似匹配"""
        keyword_to_sw = {
            '801010': ['农林牧渔', '农业', '农用机械', '农业综合'],
            '801030': ['化工', '化工原料', '农药化肥', '染料涂料'],
            '801040': ['钢铁', '钢加工', '矿物制品'],
            '801050': ['有色', '小金属', '铅锌', '铜', '铝'],
            '801080': ['电子', '半导体', '元器件'],
            '801110': ['家电', '家用电器'],
            '801120': ['食品', '食品饮料', '乳制品'],
            '801130': ['纺织', '服饰', '纺织服装'],
            '801140': ['轻工', '家居用品', '文教休闲', '广告包装'],
            '801150': ['医药', '制药', '生物制药', '中成药', '医疗保健', '医药商业'],
            '801160': ['公用', '供气供热', '环境保护'],
            '801170': ['综合', '其他商业', '其他建材'],
            '801180': ['地产', '房地产', '区域地产', '全国地产'],
            '801200': ['商贸', '零售'],
            '801210': ['社会服务', '休闲', '旅游'],
            '801230': ['传媒', '互联网'],
            '801250': ['银行', '证券', '保险', '非银'],
            '801260': ['国防', '军工', '航空'],
            '801710': ['建材', '建筑材料', '建筑工程'],
            '801720': ['建筑', '装饰', '装修'],
            '801730': ['电力', '电气', '电器', '机械'],
            '801740': ['军工', '国防'],
            '801750': ['计算机', '软件', 'IT设备', '互联网'],
            '801760': ['传媒', '文化', '广告'],
            '801770': ['通信', '通信设备'],
            '801780': ['计算机', '软件服务'],
            '801790': ['金融', '银行', '证券', '保险'],
            '801880': ['汽车', '汽车配件', '汽车整车'],
            '801890': ['机械', '专用机械', '工程机械', '运输设备', '机械基件'],
        }

        matched_codes = set()
        for sw_code, keywords in keyword_to_sw.items():
            if sw_code in industry_codes:
                for kw in keywords:
                    matched = df[df['industry'].str.contains(kw, na=False, case=False)]
                    matched_codes.update(matched['ts_code'].tolist())

        if not matched_codes:
            return pd.DataFrame()

        result = df[df['ts_code'].isin(matched_codes)].copy()
        result = self._map_industry_name_to_code(result)
        return result

    def calculate_six_dim_score(self, stock_df: pd.DataFrame) -> pd.DataFrame:
        """
        六维评分（简化版，基于已有财务/估值数据）
        不调用外部接口，全部基于本地 SQLite 字段
        """
        if len(stock_df) == 0:
            return stock_df

        df = stock_df.copy()

        # 1. 成长能力 (20%)
        growth_score = 0.0
        if 'roe' in df.columns:
            growth_score += np.clip(df['roe'] * 2, 0, 20)  # ROE 每1%得2分，上限20
        if 'revenue_yoy' in df.columns:
            growth_score += np.clip(df['revenue_yoy'] * 0.5, 0, 20)  # 营收增速每1%得0.5分
        if 'net_profit_yoy' in df.columns:
            growth_score += np.clip(df['net_profit_yoy'] * 0.3, 0, 20)  # 净利增速每1%得0.3分
        df['score_growth'] = np.clip(growth_score, 0, 20)

        # 2. 盈利能力 (15%)
        profit_score = 0.0
        if 'grossprofit_margin' in df.columns:
            profit_score += np.clip(df['grossprofit_margin'] * 0.5, 0, 15)
        df['score_profitability'] = np.clip(profit_score, 0, 15)

        # 3. 质量 (15%)
        quality_score = 0.0
        if 'debt_ratio' in df.columns:
            # 负债率越低越好，50%以下得满分
            quality_score += np.clip((1 - df['debt_ratio'] / 100) * 15, 0, 15)
        df['score_quality'] = np.clip(quality_score, 0, 15)

        # 4. 估值 (20%)
        val_score = 0.0
        if 'pe' in df.columns:
            val_score += np.clip(np.where(df['pe'] < 15, 25, np.where(df['pe'] < 25, 15, 5)), 0, 25)
        if 'pb' in df.columns:
            val_score += np.clip(np.where(df['pb'] < 1.5, 25, np.where(df['pb'] < 3, 15, 5)), 0, 25)
        df['score_valuation'] = np.clip(val_score, 0, 20)

        # 5. 动量 (15%) — 用本地估值数据的 20 日涨跌幅代理（若存在）
        # 这里先用宏观得分代理，避免再查行情表
        df['score_momentum'] = 0.0

        # 6. 行业景气 (15%) — 后续会在外层叠加宏观得分
        df['score_industry'] = 0.0

        # 六维总分
        df['six_dim_score'] = (
            df['score_growth'] * (self.weights['growth'] / 0.20) * 0.20 +
            df['score_profitability'] * (self.weights['profitability'] / 0.15) * 0.15 +
            df['score_quality'] * (self.weights['quality'] / 0.15) * 0.15 +
            df['score_valuation'] * (self.weights['valuation'] / 0.20) * 0.20 +
            df['score_momentum'] * (self.weights['momentum'] / 0.15) * 0.15 +
            df['score_industry'] * (self.weights['industry'] / 0.15) * 0.15
        )

        # 归一化到 0-100
        max_score = df['six_dim_score'].max()
        if max_score and max_score > 0:
            df['six_dim_score'] = df['six_dim_score'] / max_score * 100

        return df

    def attach_macro_scores(self, stock_df: pd.DataFrame, macro_scores: pd.DataFrame) -> pd.DataFrame:
        """
        将宏观得分映射到个股
        """
        if len(stock_df) == 0 or len(macro_scores) == 0:
            return stock_df

        macro_map = dict(zip(macro_scores['industry_code'], macro_scores['macro_score']))
        stock_df = stock_df.copy()
        stock_df['macro_industry_score'] = stock_df['industry_code'].map(macro_map).fillna(0)

        # 行业景气得分（15% 权重）替换
        max_macro = stock_df['macro_industry_score'].max()
        if max_macro and max_macro > 0:
            stock_df['score_industry'] = stock_df['macro_industry_score'] / max_macro * 15

        # 重新计算总分
        stock_df['six_dim_score'] = (
            stock_df['score_growth'] * (self.weights['growth'] / 0.20) * 0.20 +
            stock_df['score_profitability'] * (self.weights['profitability'] / 0.15) * 0.15 +
            stock_df['score_quality'] * (self.weights['quality'] / 0.15) * 0.15 +
            stock_df['score_valuation'] * (self.weights['valuation'] / 0.20) * 0.20 +
            stock_df['score_momentum'] * (self.weights['momentum'] / 0.15) * 0.15 +
            stock_df['score_industry'] * (self.weights['industry'] / 0.15) * 0.15
        )

        # 归一化
        max_score = stock_df['six_dim_score'].max()
        if max_score and max_score > 0:
            stock_df['six_dim_score'] = stock_df['six_dim_score'] / max_score * 100

        return stock_df

    def split_growth_value(self, stock_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        按成长/价值双通道拆分
        成长通道：ROE>=15 且 营收增速>=15
        价值通道：PE<20 且 PB<3 且 股息率>0
        """
        if len(stock_df) == 0:
            return pd.DataFrame(), pd.DataFrame()

        # 成长通道
        growth_mask = (
            (stock_df['roe'].notna()) & (stock_df['roe'] >= 15) &
            (stock_df['revenue_yoy'].notna()) & (stock_df['revenue_yoy'] >= 15)
        )
        growth_df = stock_df[growth_mask].copy()

        # 价值通道
        value_mask = (
            (stock_df['pe'].notna()) & (stock_df['pe'] < 20) &
            (stock_df['pb'].notna()) & (stock_df['pb'] < 3) &
            (stock_df['dv_ttm'].notna()) & (stock_df['dv_ttm'] > 0)
        )
        value_df = stock_df[value_mask].copy()

        # 标记策略类型
        growth_df['strategy_type'] = '成长'
        value_df['strategy_type'] = '价值'

        logger.info(f"成长通道: {len(growth_df)} 只 | 价值通道: {len(value_df)} 只")
        return growth_df, value_df

    def build_observation_pool(self, top_n_industries: int = 10, min_score: float = 55, use_pca: bool = False) -> Dict:
        """
        一键生成观察池
        use_pca: 是否使用 PCA 降维后的行业敏感度（PC1~PC5），否则使用原始 RollingOLS 8因子敏感度
        """
        self._connect()
        try:
            # 1. 加载宏观数据
            sens_long = self.load_macro_sensitivity(use_pca=use_pca)
            ic_ranking = self.load_recent_factor_performance(recent_months=3)

            # 2. 计算行业宏观得分
            macro_scores = self.build_macro_scores(sens_long, ic_ranking)
            industry_candidates = self.get_industry_candidates(macro_scores, top_n=top_n_industries)

            # 3. 查询候选行业下的股票池
            stock_universe = self.query_local_stock_universe(industry_candidates)

            # 4. 六维评分
            scored_stocks = self.calculate_six_dim_score(stock_universe)

            # 5. 叠加宏观得分
            scored_stocks = self.attach_macro_scores(scored_stocks, macro_scores)

            # 5.1 三模型融合（技术+筹码/资金流+宏观）
            try:
                from three_model_fusion import ThreeModelFusion
                from market_status_detector import get_market_status
                fusion = ThreeModelFusion(self.db_path)
                market_status = get_market_status()
                current_market = market_status['status'] if market_status else 'neutral'
                fusion_scores = []
                for _, row in scored_stocks.iterrows():
                    fr = fusion.fuse(row['ts_code'], market_status=current_market)
                    if fr:
                        fusion_scores.append({
                            'ts_code': row['ts_code'],
                            'technical_score': fr['technical_score'],
                            'chip_score': fr['chip_score'],
                            'macro_score': fr['macro_score'],
                            'fusion_score': fr['total_score'],
                        })
                    else:
                        fusion_scores.append({
                            'ts_code': row['ts_code'],
                            'technical_score': np.nan,
                            'chip_score': np.nan,
                            'macro_score': np.nan,
                            'fusion_score': np.nan,
                        })
                fusion_df = pd.DataFrame(fusion_scores)
                scored_stocks = scored_stocks.merge(fusion_df, on='ts_code', how='left')
                # 融合得分缺失时保持中性50分
                scored_stocks['fusion_score'] = scored_stocks['fusion_score'].fillna(50.0)
                fusion.close()
            except Exception as e:
                logger.warning(f"三模型融合失败，跳过: {e}")

            # 6. 过滤低分股
            scored_stocks = scored_stocks[scored_stocks['six_dim_score'] >= min_score].copy()

            # 7. 成长/价值拆分
            growth_df, value_df = self.split_growth_value(scored_stocks)

            # 8. 排序
            if len(growth_df) > 0:
                growth_df = growth_df.sort_values('six_dim_score', ascending=False).reset_index(drop=True)
            if len(value_df) > 0:
                value_df = value_df.sort_values('six_dim_score', ascending=False).reset_index(drop=True)

            # 9. 汇总
            summary = {
                'report_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'industry_candidates': len(industry_candidates),
                'stock_universe': len(stock_universe),
                'growth_pool': len(growth_df),
                'value_pool': len(value_df),
                'top_industries': industry_candidates[:5],
                'macro_signal': self._get_latest_macro_signal(),
            }

            return {
                'report_date': summary['report_date'],
                'macro_ranking': macro_scores,
                'growth_stocks': growth_df,
                'value_stocks': value_df,
                'summary': summary,
            }

        finally:
            self._close()

    def _get_latest_macro_signal(self) -> Dict:
        """获取最新宏观信号摘要"""
        macro_factors_path = os.path.join(DATA_DIR, 'macro_factors.parquet')
        if not os.path.exists(macro_factors_path):
            return {}

        factors = pd.read_parquet(macro_factors_path)
        signal_cols = ['growth_signal', 'inflation_signal', 'rate_signal', 'fx_signal', 'liquidity_signal']
        latest = factors[['trade_date'] + signal_cols].dropna().sort_values('trade_date').iloc[-1]

        signal_map = {}
        for col in signal_cols:
            val = latest[col]
            signal_map[col.replace('_signal', '')] = 0 if pd.isna(val) else int(val)
        return signal_map

    def to_selection_bridge_format(self, pool: Dict) -> Tuple[List[Dict], List[Dict]]:
        """
        转换为 selection_bridge.persist_selection_results 需要的格式
        """
        growth_stocks = []
        for _, row in pool['growth_stocks'].iterrows():
            growth_stocks.append({
                'ts_code': row['ts_code'],
                'name': row.get('name', ''),
                'strategy_type': '成长',
                'industry_code': row.get('industry_code', ''),
                'industry_name': row.get('industry_name', ''),
                'six_dim_score': round(row.get('six_dim_score', 0), 1),
                'fusion_score': round(row.get('fusion_score', 0), 1),
                'macro_score': round(row.get('macro_industry_score', 0), 3),
                'roe': row.get('roe'),
                'revenue_yoy': row.get('revenue_yoy'),
                'net_profit_yoy': row.get('net_profit_yoy'),
                'pe': row.get('pe'),
                'pb': row.get('pb'),
                'dv_ttm': row.get('dv_ttm'),
            })

        value_stocks = []
        for _, row in pool['value_stocks'].iterrows():
            value_stocks.append({
                'ts_code': row['ts_code'],
                'name': row.get('name', ''),
                'strategy_type': '价值',
                'industry_code': row.get('industry_code', ''),
                'industry_name': row.get('industry_name', ''),
                'six_dim_score': round(row.get('six_dim_score', 0), 1),
                'fusion_score': round(row.get('fusion_score', 0), 1),
                'macro_score': round(row.get('macro_industry_score', 0), 3),
                'roe': row.get('roe'),
                'revenue_yoy': row.get('revenue_yoy'),
                'net_profit_yoy': row.get('net_profit_yoy'),
                'pe': row.get('pe'),
                'pb': row.get('pb'),
                'dv_ttm': row.get('dv_ttm'),
            })

        return growth_stocks, value_stocks

    def persist_observation_pool(self, pool: Dict, replace: bool = True) -> Dict:
        """
        将观察池结果持久化到 watch_pool 表

        Args:
            pool: build_observation_pool() 返回的完整结果
            replace: True=全量替换今日记录；False=仅追加新标的

        Returns:
            {'growth_inserted': int, 'value_inserted': int, 'total_updated': int}
        """
        if not pool or not pool.get('growth_stocks') is not None and not pool.get('value_stocks') is not None:
            return {'growth_inserted': 0, 'value_inserted': 0, 'total_updated': 0}

        report_date = pool.get('report_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        today = report_date[:10] if len(report_date) >= 10 else report_date

        if replace:
            self._connect()
            try:
                self.cursor.execute(
                    "DELETE FROM watch_pool WHERE entry_date = ?",
                    (today,)
                )
                self.conn.commit()
            except Exception as e:
                logger.warning(f"[WATCH_POOL] 清空今日记录失败: {e}")

        growth_stocks, value_stocks = self.to_selection_bridge_format(pool)
        growth_inserted = 0
        value_inserted = 0

        for s in growth_stocks:
            try:
                self._connect()
                self.cursor.execute(
                    """
                    INSERT OR REPLACE INTO watch_pool
                        (ts_code, name, pool_type, entry_date, current_status,
                         entry_price, current_price, position_ratio, last_update, notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        s['ts_code'],
                        s.get('name', ''),
                        'GROWTH',
                        today,
                        'OBSERVING',
                        s.get('pe') or 0,
                        s.get('pe') or 0,
                        0.0,
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        f"six_dim={s.get('six_dim_score', 0)}, macro={s.get('macro_score', 0)}"
                    )
                )
                self.conn.commit()
                growth_inserted += 1
            except Exception as e:
                logger.error(f"[WATCH_POOL] 写入成长 {s['ts_code']} 失败: {e}")

        for s in value_stocks:
            try:
                self._connect()
                self.cursor.execute(
                    """
                    INSERT OR REPLACE INTO watch_pool
                        (ts_code, name, pool_type, entry_date, current_status,
                         entry_price, current_price, position_ratio, last_update, notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        s['ts_code'],
                        s.get('name', ''),
                        'VALUE',
                        today,
                        'OBSERVING',
                        s.get('pe') or 0,
                        s.get('pe') or 0,
                        0.0,
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        f"six_dim={s.get('six_dim_score', 0)}, macro={s.get('macro_score', 0)}"
                    )
                )
                self.conn.commit()
                value_inserted += 1
            except Exception as e:
                logger.error(f"[WATCH_POOL] 写入价值 {s['ts_code']} 失败: {e}")

        logger.info(f"[WATCH_POOL] 持久化完成: 成长 {growth_inserted} 只, 价值 {value_inserted} 只, 日期 {today}")
        return {
            'growth_inserted': growth_inserted,
            'value_inserted': value_inserted,
            'total_updated': growth_inserted + value_inserted
        }

    def sync_watch_pool_to_selection_bridge(self, report_date: str = None) -> Dict:
        """
        将 watch_pool 同步到 selection_bridge（trading_strategy + watch_list）
        实现观察池 → 选股桥 → PaperTrader 的自动建仓链路

        Args:
            report_date: 同步日期，默认今天

        Returns:
            selection_bridge.persist_selection_results() 的返回结果
        """
        if report_date is None:
            report_date = datetime.now().strftime('%Y-%m-%d')

        try:
            from selection_bridge import persist_selection_results

            self._connect()
            self.cursor.execute(
                """
                SELECT ts_code, name, pool_type, notes
                FROM watch_pool
                WHERE entry_date = ?
                ORDER BY pool_type, ts_code
                """,
                (report_date,)
            )
            rows = self.cursor.fetchall()

            growth_stocks = []
            value_stocks = []
            for row in rows:
                ts_code, name, pool_type, notes = row
                six_dim = 0
                macro = 0
                if notes:
                    import re
                    m1 = re.search(r'six_dim=([0-9.]+)', notes)
                    m2 = re.search(r'macro=([0-9.]+)', notes)
                    if m1:
                        six_dim = float(m1.group(1))
                    if m2:
                        macro = float(m2.group(1))

                stock = {
                    'ts_code': ts_code,
                    'name': name,
                    'six_dim_score': six_dim,
                    'macro_score': macro,
                }

                if pool_type == 'GROWTH':
                    stock['growth_score'] = six_dim
                    growth_stocks.append(stock)
                elif pool_type == 'VALUE':
                    stock['score'] = six_dim
                    value_stocks.append(stock)

            logger.info(f"[SYNC] 读取 watch_pool: 成长{len(growth_stocks)}只 + 价值{len(value_stocks)}只 @ {report_date}")

            result = persist_selection_results(growth_stocks, value_stocks, report_date=report_date)
            logger.info(f"[SYNC] selection_bridge 持久化完成: {result}")
            return result

        except Exception as e:
            logger.error(f"[SYNC] watch_pool → selection_bridge 同步失败: {e}")
            return {'error': str(e), 'growth_count': 0, 'value_count': 0}


def refresh_watch_pool(top_n_industries: int = 10, min_score: float = 55) -> Dict:
    """
    每日刷新观察池：构建 + 持久化 + 输出摘要

    可作为 cron / scheduled task 的入口函数
    """
    builder = ObservationPoolBuilder()
    pool = builder.build_observation_pool(top_n_industries=top_n_industries, min_score=min_score)
    result = builder.persist_observation_pool(pool, replace=True)
    builder._close()
    return {
        'report_date': pool.get('report_date'),
        'industry_candidates': pool['summary']['industry_candidates'],
        'stock_universe': pool['summary']['stock_universe'],
        'growth_pool': pool['summary']['growth_pool'],
        'value_pool': pool['summary']['value_pool'],
        'persist': result,
        'top_industries': pool['summary']['top_industries'],
        'macro_signal': pool['summary']['macro_signal'],
    }


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    builder = ObservationPoolBuilder()
    pool = builder.build_observation_pool(top_n_industries=8, min_score=55)

    print("\n" + "=" * 70)
    print("观察池生成结果")
    print("=" * 70)
    print(f"\n报告日期: {pool['report_date']}")
    print(f"候选行业: {pool['summary']['industry_candidates']} 个")
    print(f"股票池: {pool['summary']['stock_universe']} 只")
    print(f"成长通道: {pool['summary']['growth_pool']} 只")
    print(f"价值通道: {pool['summary']['value_pool']} 只")

    print("\n【行业宏观排名 Top 5】")
    print(pool['macro_ranking'].head(5)[['industry_code', 'macro_score', 'macro_rank']].to_string(index=False))

    print("\n【成长通道 Top 10】")
    cols = ['ts_code', 'name', 'six_dim_score', 'macro_industry_score', 'roe', 'revenue_yoy', 'pe', 'pb']
    if len(pool['growth_stocks']) > 0:
        print(pool['growth_stocks'][cols].head(10).to_string(index=False))
    else:
        print("  （无）")

    print("\n【价值通道 Top 10】")
    if len(pool['value_stocks']) > 0:
        print(pool['value_stocks'][cols].head(10).to_string(index=False))
    else:
        print("  （无）")

    print("\n" + "=" * 70)
    print("观察池生成完成")
    print("=" * 70)
