"""
backfill_industry_sensitivity.py

补齐缺失的申万一级行业宏观敏感度数据
数据源：本地 industry_returns.parquet + macro_factors.parquet
方法：statsmodels RollingOLS（252日窗口）
输出：data/industry_sensitivity_rolling_ols_backfill.parquet
"""

import os
import sys
import logging
from datetime import datetime
from typing import List

import pandas as pd
import numpy as np
import akshare as ak
import warnings
warnings.filterwarnings('ignore')

from statsmodels.regression.rolling import RollingOLS
from statsmodels.tools import add_constant

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Paths
DATA_DIR = r'C:\Users\Fengpeng\data'
INDUSTRY_RETURNS_PATH = os.path.join(DATA_DIR, 'industry_returns.parquet')
MACRO_FACTORS_PATH = os.path.join(DATA_DIR, 'macro_factors.parquet')
OUTPUT_PATH = os.path.join(DATA_DIR, 'industry_sensitivity_rolling_ols_backfill.parquet')

# Existing industries (already in the main file)
EXISTING_INDUSTRIES = [
    '801010', '801030', '801040', '801050', '801080',
    '801110', '801120', '801130', '801140', '801150',
    '801160', '801170', '801180', '801200', '801210',
    '801230', '801250', '801260'
]

# Missing industries to backfill
MISSING_INDUSTRIES = [
    '801710', '801720', '801730', '801740', '801750',
    '801760', '801770', '801780', '801790', '801880',
    '801890', '801950', '801960', '801970', '801980'
]

WINDOW_YEARS = 5
WINDOW_DAYS = WINDOW_YEARS * 252
MIN_PERIODS = max(WINDOW_DAYS // 2, 20)

# Data-boundary industries (start from 2021-12-14, only 1089 days)
BOUNDARY_INDUSTRIES = {
    '801950': 3 * 252,  # 煤炭
    '801960': 3 * 252,  # 石油石化
    '801970': 3 * 252,  # 环保
    '801980': 3 * 252,  # 美容护理
}


def load_and_prepare_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """加载并准备行业收益和宏观因子数据"""
    logger.info("加载行业收益数据...")
    ret_wide = pd.read_parquet(INDUSTRY_RETURNS_PATH)
    ret_wide.index.name = 'date'
    ret_wide = ret_wide.reset_index()

    # 映射行业名称到申万代码
    logger.info("映射行业名称到申万代码...")
    sw = ak.sw_index_first_info()
    sw['code'] = sw['行业代码'].str.replace('.SI', '')
    name_to_code = dict(zip(sw['行业名称'], sw['code']))

    rename_map = {col: name_to_code[col] for col in ret_wide.columns if col in name_to_code}
    ret_wide = ret_wide.rename(columns=rename_map)

    # 转换为长格式
    ret_long = ret_wide.melt(id_vars=['date'], var_name='industry_code', value_name='return')
    ret_long = ret_long.rename(columns={'date': 'trade_date'})
    ret_long['trade_date'] = pd.to_datetime(ret_long['trade_date'])

    logger.info(f"行业收益数据: {ret_long.shape[0]} 行, {ret_long['industry_code'].nunique()} 个行业")

    # 加载宏观因子
    logger.info("加载宏观因子数据...")
    factors = pd.read_parquet(MACRO_FACTORS_PATH)
    factor_cols = ['growth', 'inflation', 'rate', 'fx', 'liquidity', 'pmi', 'ppi', 'm2_growth']
    factor_long = factors[['trade_date'] + factor_cols].melt(
        id_vars=['trade_date'], var_name='factor_name', value_name='factor_value'
    )
    factor_long['trade_date'] = pd.to_datetime(factor_long['trade_date'])

    logger.info(f"宏观因子数据: {factor_long.shape[0]} 行, {len(factor_cols)} 个因子")

    return ret_long, factor_long


def prepare_returns_and_factors(ret_long: pd.DataFrame, factor_long: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """准备行业收益和因子收益（20日变化率）"""
    # 透视行业收益
    industry_pivot = ret_long.pivot(index='trade_date', columns='industry_code', values='return')

    # 透视因子值
    factor_pivot = factor_long.pivot(index='trade_date', columns='factor_name', values='factor_value')

    # 计算因子收益率（20日变化率）
    factor_returns = factor_pivot.pct_change(20)

    # 日期对齐
    common_dates = industry_pivot.index.intersection(factor_returns.index)
    industry_pivot = industry_pivot.loc[common_dates]
    factor_returns = factor_returns.loc[common_dates]

    logger.info(f"对齐后交易日: {len(common_dates)} 天")
    return industry_pivot, factor_returns


def run_rolling_ols_for_industries(industry_pivot: pd.DataFrame, factor_returns: pd.DataFrame,
                                   industry_codes: List[str]) -> pd.DataFrame:
    """对指定行业列表运行 RollingOLS，对数据边界行业使用较短窗口"""
    results = []
    factors = list(factor_returns.columns)

    for industry in industry_codes:
        if industry not in industry_pivot.columns:
            logger.warning(f"行业 {industry} 不在收益矩阵中，跳过")
            continue

        y = industry_pivot[industry]
        X = factor_returns[factors].copy()

        # 清理 NaN
        valid = y.notna() & X.notna().all(axis=1)
        available = valid.sum()

        # 对数据边界行业使用较短窗口
        if industry in BOUNDARY_INDUSTRIES:
            window_days = BOUNDARY_INDUSTRIES[industry]
            min_periods = max(window_days // 2, 20)
            if available < window_days:
                logger.warning(f"行业 {industry} 边界数据不足窗口 ({available} < {window_days})，跳过")
                continue
            logger.info(f"行业 {industry} 使用边界窗口 {window_days} 天（可用 {available} 天）")
        else:
            window_days = WINDOW_DAYS
            min_periods = MIN_PERIODS
            if available < window_days:
                logger.warning(f"行业 {industry} 可用样本不足窗口长度 ({available} < {window_days})，跳过")
                continue

        y = y[valid]
        X = X[valid]

        # 索引对齐
        common_idx = y.index.intersection(X.index)
        if len(common_idx) < min_periods:
            logger.warning(f"行业 {industry} 对齐后样本不足 ({len(common_idx)} < {min_periods})，跳过")
            continue

        y = y.loc[common_idx]
        X = X.loc[common_idx]

        if not y.index.equals(X.index):
            y, X = y.align(X, join='inner')

        try:
            X_const = add_constant(X)
            mod = RollingOLS(y, X_const, window=window_days)
            rolling_res = mod.fit()

            params = rolling_res.params
            params.index.name = 'trade_date'

            if hasattr(rolling_res, 'rsquared'):
                r2 = rolling_res.rsquared
            else:
                r2 = pd.Series(np.nan, index=params.index)

            for date, row in params.iterrows():
                alpha = row.get('const', np.nan)
                for factor in factors:
                    results.append({
                        'trade_date': date,
                        'industry_code': industry,
                        'factor_name': factor,
                        'alpha': alpha,
                        'beta': row.get(factor, np.nan),
                        'r_squared': r2.loc[date] if isinstance(r2, pd.Series) else np.nan,
                        'method': 'rolling_ols',
                        'window': window_days,
                    })

            logger.info(f"行业 {industry}: 完成 {len(params)} 期回归")

        except Exception as e:
            logger.error(f"行业 {industry} 回归失败: {str(e)[:100]}")
            continue

    result_df = pd.DataFrame(results)
    logger.info(f"RollingOLS 完成: {len(result_df)} 行, {result_df['industry_code'].nunique() if len(result_df) > 0 else 0} 个行业")
    return result_df


def merge_with_existing(backfill_df: pd.DataFrame) -> pd.DataFrame:
    """将补全数据与现有敏感度数据合并"""
    existing_path = os.path.join(DATA_DIR, 'industry_sensitivity_rolling_ols.parquet')
    if os.path.exists(existing_path):
        existing = pd.read_parquet(existing_path)
        logger.info(f"现有数据: {len(existing)} 行, {existing['industry_code'].nunique()} 个行业")

        # 合并并去重（保留最新）
        combined = pd.concat([existing, backfill_df], ignore_index=True)
        combined = combined.sort_values('trade_date').drop_duplicates(
            subset=['trade_date', 'industry_code', 'factor_name'], keep='last'
        )
        logger.info(f"合并后: {len(combined)} 行, {combined['industry_code'].nunique()} 个行业")
        return combined
    else:
        logger.info("无现有数据，直接保存补全结果")
        return backfill_df


def main():
    logger.info("=" * 70)
    logger.info("开始补全缺失行业宏观敏感度数据")
    logger.info("=" * 70)

    # 1. 加载数据
    ret_long, factor_long = load_and_prepare_data()

    # 2. 准备收益和因子
    industry_pivot, factor_returns = prepare_returns_and_factors(ret_long, factor_long)

    # 3. 运行 RollingOLS
    logger.info(f"对 {len(MISSING_INDUSTRIES)} 个缺失行业运行 RollingOLS...")
    backfill_df = run_rolling_ols_for_industries(industry_pivot, factor_returns, MISSING_INDUSTRIES)

    if len(backfill_df) == 0:
        logger.error("补全结果为空，请检查数据")
        return 1

    # 4. 合并到主文件
    combined = merge_with_existing(backfill_df)

    # 5. 保存结果
    combined.to_parquet(OUTPUT_PATH, index=False)
    logger.info(f"补全数据已保存: {OUTPUT_PATH}")
    logger.info(f"最终覆盖行业数: {combined['industry_code'].nunique()}")
    logger.info(f"最终数据行数: {len(combined)}")

    # 6. 验证
    final_industries = set(combined['industry_code'].unique())
    all_31 = set(['801010', '801030', '801040', '801050', '801080', '801110', '801120',
                  '801130', '801140', '801150', '801160', '801170', '801180', '801200',
                  '801210', '801230', '801250', '801260', '801710', '801720', '801730',
                  '801740', '801750', '801760', '801770', '801780', '801790', '801880',
                  '801890', '801950', '801960', '801970', '801980'])
    missing_from_all = all_31 - final_industries
    if missing_from_all:
        logger.warning(f"仍有缺失行业: {sorted(missing_from_all)}")
    else:
        logger.info("✅ 全部 33 个申万一级行业已覆盖")

    return 0


if __name__ == '__main__':
    sys.exit(main())
