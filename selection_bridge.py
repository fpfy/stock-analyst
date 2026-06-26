"""
selection_bridge.py — 选股结果持久化与下游联动

解决的核心问题：
1. main_v3.py 选股后，结果只存在于内存，不回写 trading_strategy / watch_list
2. backtest_v3.py 独立选股，与当日选股池脱节
3. papertrader_final.py 依赖残留的 trading_strategy，无法关联最新选股

本模块提供：
  - persist_selection_results(): 将选股结果写入 trading_strategy + watch_list
  - get_backtest_strategy_fn(): 返回 strategy_fn，供 BacktestEngine 使用当日选股池
  - get_latest_selection(): 供 papertrader 读取最新选股结果
"""
import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Callable

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / 'database' / 'stock_analysis.db'

# 标准阶梯止盈模板（浮盈抬升→分批减仓→动态跟踪）
STANDARD_LADDER_TEMPLATE = {
    # 阶梯1：浮盈15%减仓30%，剩余仓位开启5%回撤跟踪
    'ladder_1_profit_pct': 0.15,      # +15% 触发
    'ladder_1_reduce_ratio': 0.30,    # 减仓30%
    'ladder_1_trailing_drop': 0.05,   # 剩余仓位5%回撤

    # 阶梯2：浮盈35%再减仓40%，剩余仓位收紧至3%回撤
    'ladder_2_profit_pct': 0.35,      # +35% 触发
    'ladder_2_reduce_ratio': 0.40,    # 再减仓40%
    'ladder_2_trailing_drop': 0.03,   # 剩余仓位3%回撤

    # 阶梯3：浮盈60%以上仅留底仓，1%回撤无条件清仓
    'ladder_3_profit_pct': 0.60,      # +60% 触发
    'ladder_3_remaining_ratio': 0.10, # 仅留10%底仓
    'ladder_3_trailing_drop': 0.01,   # 1%回撤清仓
}

# 动态止盈参数预设（各市场状态可覆盖阶梯模板）
DYNAMIC_TRAILING_PRESETS = {
    # 牛市：波动率高，趋势强，让利润奔跑
    'bull': {
        '成长': {
            'stop_loss_pct': 0.07,
            'take_profit_pct': 0.15,
            'trailing_activation_pct': 0.20,  # +20%激活（延迟激活）
            'trailing_drop_pct': 0.12,        # 回撤12%触发（放宽，避免震出）
            'max_position': 0.15,
            'max_hold_days': 30,
            'risk_grade': 'MEDIUM',
            # 阶梯模板（牛市放宽阈值）
            'ladder_1_profit_pct': 0.20,      # +20%触发
            'ladder_1_reduce_ratio': 0.30,    # 减仓30%
            'ladder_1_trailing_drop': 0.08,   # 剩余8%回撤
            'ladder_2_profit_pct': 0.40,      # +40%触发
            'ladder_2_reduce_ratio': 0.40,    # 再减仓40%
            'ladder_2_trailing_drop': 0.05,   # 剩余5%回撤
            'ladder_3_profit_pct': 0.60,      # +60%触发
            'ladder_3_remaining_ratio': 0.10, # 仅留10%底仓
            'ladder_3_trailing_drop': 0.01,   # 1%回撤清仓
        },
        '价值': {
            'stop_loss_pct': 0.15,
            'take_profit_pct': 0.20,
            'trailing_activation_pct': 0.25,  # +25%激活
            'trailing_drop_pct': 0.15,        # 回撤15%触发
            'max_position': 0.15,
            'max_hold_days': 30,
            'risk_grade': 'LOW',
            # 阶梯模板（牛市放宽阈值）
            'ladder_1_profit_pct': 0.25,
            'ladder_1_reduce_ratio': 0.30,
            'ladder_1_trailing_drop': 0.10,
            'ladder_2_profit_pct': 0.45,
            'ladder_2_reduce_ratio': 0.40,
            'ladder_2_trailing_drop': 0.08,
            'ladder_3_profit_pct': 0.60,
            'ladder_3_remaining_ratio': 0.10,
            'ladder_3_trailing_drop': 0.01,
        },
    },
    # 熊市：波动率高，趋势弱，快速止盈
    'bear': {
        '成长': {
            'stop_loss_pct': 0.07,
            'take_profit_pct': 0.10,          # 降低止盈目标
            'trailing_activation_pct': 0.10,  # +10%激活（提前锁定）
            'trailing_drop_pct': 0.05,        # 回撤5%触发（快速止盈）
            'max_position': 0.10,             # 降低仓位
            'max_hold_days': 20,              # 缩短持仓
            'risk_grade': 'HIGH',
            # 阶梯模板（熊市收紧阈值）
            'ladder_1_profit_pct': 0.10,      # +10%触发
            'ladder_1_reduce_ratio': 0.50,    # 减仓50%
            'ladder_1_trailing_drop': 0.03,   # 剩余3%回撤
            'ladder_2_profit_pct': 0.20,      # +20%触发
            'ladder_2_reduce_ratio': 0.50,    # 再减仓50%
            'ladder_2_trailing_drop': 0.02,   # 剩余2%回撤
            'ladder_3_profit_pct': 0.35,      # +35%触发
            'ladder_3_remaining_ratio': 0.05, # 仅留5%底仓
            'ladder_3_trailing_drop': 0.01,   # 1%回撤清仓
        },
        '价值': {
            'stop_loss_pct': 0.12,            # 放宽止损
            'take_profit_pct': 0.15,
            'trailing_activation_pct': 0.12,
            'trailing_drop_pct': 0.06,
            'max_position': 0.12,
            'max_hold_days': 20,
            'risk_grade': 'MEDIUM',
            # 阶梯模板（熊市收紧阈值）
            'ladder_1_profit_pct': 0.12,
            'ladder_1_reduce_ratio': 0.50,
            'ladder_1_trailing_drop': 0.04,
            'ladder_2_profit_pct': 0.22,
            'ladder_2_reduce_ratio': 0.50,
            'ladder_2_trailing_drop': 0.03,
            'ladder_3_profit_pct': 0.40,
            'ladder_3_remaining_ratio': 0.05,
            'ladder_3_trailing_drop': 0.01,
        },
    },
    # 震荡市：标准参数（采用用户指定的标准阶梯模板）
    'sideways': {
        '成长': {
            'stop_loss_pct': 0.07,
            'take_profit_pct': 0.15,
            'trailing_activation_pct': 0.15,
            'trailing_drop_pct': 0.08,
            'max_position': 0.15,
            'max_hold_days': 30,
            'risk_grade': 'MEDIUM',
            # 标准阶梯模板
            'ladder_1_profit_pct': 0.15,      # +15%
            'ladder_1_reduce_ratio': 0.30,    # 减仓30%
            'ladder_1_trailing_drop': 0.05,   # 剩余5%回撤
            'ladder_2_profit_pct': 0.35,      # +35%
            'ladder_2_reduce_ratio': 0.40,    # 再减仓40%
            'ladder_2_trailing_drop': 0.03,   # 剩余3%回撤
            'ladder_3_profit_pct': 0.60,      # +60%
            'ladder_3_remaining_ratio': 0.10, # 仅留10%底仓
            'ladder_3_trailing_drop': 0.01,   # 1%回撤清仓
        },
        '价值': {
            'stop_loss_pct': 0.15,
            'take_profit_pct': 0.20,
            'trailing_activation_pct': 0.20,
            'trailing_drop_pct': 0.10,
            'max_position': 0.15,
            'max_hold_days': 30,
            'risk_grade': 'LOW',
            # 标准阶梯模板
            'ladder_1_profit_pct': 0.15,
            'ladder_1_reduce_ratio': 0.30,
            'ladder_1_trailing_drop': 0.05,
            'ladder_2_profit_pct': 0.35,
            'ladder_2_reduce_ratio': 0.40,
            'ladder_2_trailing_drop': 0.03,
            'ladder_3_profit_pct': 0.60,
            'ladder_3_remaining_ratio': 0.10,
            'ladder_3_trailing_drop': 0.01,
        },
    },
}

# 默认风控参数（震荡市）
RISK_CONFIG = DYNAMIC_TRAILING_PRESETS['sideways'].copy()


def get_market_regime(db_path: str = None) -> str:
    """
    基于大盘数据判断市场状态
    
    返回: 'bull' | 'bear' | 'sideways'
    
    判断逻辑:
    - 牛市：波动率>20% 且 近20日涨幅>5% 且 250日位置>70%
    - 熊市：波动率>20% 且 近20日跌幅>5% 或 250日位置<30%
    - 震荡市：其他情况
    """
    if db_path is None:
        db_path = str(DB_PATH)
    
    try:
        import sqlite3
        import numpy as np
        
        conn = sqlite3.connect(db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        
        # 获取上证指数近250日数据
        cursor.execute("""
            SELECT trade_date, close 
            FROM valuation_data 
            WHERE ts_code = '000001.SH' 
            AND trade_date >= DATE('now', '-300 days')
            ORDER BY trade_date ASC
        """)
        rows = cursor.fetchall()
        conn.close()
        
        if len(rows) < 60:
            return 'sideways'  # 数据不足，默认震荡市
        
        closes = [r[1] for r in rows]
        
        # 从 close 计算日涨跌幅
        pct_chgs = []
        for i in range(1, len(closes)):
            if closes[i-1] and closes[i-1] != 0:
                pct_chg = (closes[i] - closes[i-1]) / closes[i-1] * 100
                pct_chgs.append(pct_chg)
        
        # 计算年化波动率
        if len(pct_chgs) > 1:
            import numpy as np
            returns = np.array(pct_chgs) / 100
            volatility = returns.std() * np.sqrt(252)
        else:
            volatility = 0.15
        
        # 计算近20日涨跌幅
        recent_20d_return = sum(pct_chgs[-20:]) if len(pct_chgs) >= 20 else 0
        
        # 计算250日区间位置
        if len(closes) >= 100:
            recent_250 = closes[-250:] if len(closes) >= 250 else closes
            high_250 = max(recent_250)
            low_250 = min(recent_250)
            current = closes[-1]
            if high_250 > low_250:
                position_pct = (current - low_250) / (high_250 - low_250) * 100
            else:
                position_pct = 50
        else:
            position_pct = 50
        
        logger.info(f"[Market] 波动率: {volatility*100:.1f}%, "
                   f"近20日: {recent_20d_return:+.1f}%, "
                   f"250日位置: {position_pct:.1f}%")
        
        # 判断市场状态（基于波动率、趋势、位置的三维判断）
        # 当前市场特征：高位(83%) + 低波动(13%) + 小幅上涨(+5%)
        # 调整逻辑：优先看位置和趋势，波动率作为辅助
        
        high_position = position_pct > 70
        low_position = position_pct < 30
        strong_up = recent_20d_return > 3      # 降低阈值：>3%即视为上涨趋势
        strong_down = recent_20d_return < -3   # 降低阈值：<-3%即视为下跌趋势
        
        # 牛市：高位或中位 + 上涨趋势（无论波动率）
        # 熊市：低位或中位 + 下跌趋势（无论波动率）
        # 震荡市：其他情况
        
        if high_position and strong_up:
            return 'bull'  # 高位上涨，趋势强
        elif low_position and strong_down:
            return 'bear'  # 低位下跌，趋势弱
        elif strong_up and not strong_down:
            return 'bull'  # 上涨趋势
        elif strong_down and not strong_up:
            return 'bear'  # 下跌趋势
        else:
            return 'sideways'  # 震荡或无明显趋势
            
    except Exception as e:
        logger.warning(f"[Market] 判断市场状态失败: {e}")
        return 'sideways'


def get_dynamic_risk_config(market_regime: str = None) -> Dict:
    """
    根据市场状态返回动态风控参数
    
    Args:
        market_regime: 'bull' | 'bear' | 'sideways'，None则自动判断
    
    Returns:
        RISK_CONFIG 字典（含成长/价值两个通道的参数）
    """
    if market_regime is None:
        market_regime = get_market_regime()
    
    config = DYNAMIC_TRAILING_PRESETS.get(market_regime, DYNAMIC_TRAILING_PRESETS['sideways']).copy()
    
    # 更新全局 RISK_CONFIG
    global RISK_CONFIG
    RISK_CONFIG.update(config)
    
    logger.info(f"[Market] 市场状态: {market_regime}，已应用动态风控参数")
    return config


def _get_conn():
    """获取数据库连接（短生命周期，调用方负责关闭）"""
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def persist_selection_results(growth_stocks: List[Dict], value_stocks: List[Dict],
                              report_date: str = None) -> Dict:
    """
    将选股结果持久化到 trading_strategy 和 watch_list

    Args:
        growth_stocks: 成长通道选股结果列表
        value_stocks: 价值通道选股结果列表
        report_date: 报告日期，默认今天

    Returns:
        {'growth_count': int, 'value_count': int, 'total_count': int, 'error': str|None}
    """
    if report_date is None:
        report_date = datetime.now().strftime('%Y-%m-%d')

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        growth_count = 0
        value_count = 0

        # 清除当日旧数据（避免重复）
        cursor.execute("DELETE FROM trading_strategy WHERE report_date = ?", (report_date,))
        cursor.execute("DELETE FROM watch_list WHERE updated_at >= ?", (report_date,))

        # 写入成长通道
        for stock in growth_stocks:
            ts_code = stock.get('ts_code', '')
            name = stock.get('name', ts_code)
            score = stock.get('six_dim_score', stock.get('score', 0))
            current_price = stock.get('current_price', 0)
            cfg = RISK_CONFIG['成长']

            stop_loss_price = current_price * (1 - cfg['stop_loss_pct']) if current_price > 0 else 0
            target_price = current_price * (1 + cfg['take_profit_pct']) if current_price > 0 else 0

            cursor.execute("""
                INSERT OR REPLACE INTO trading_strategy
                    (report_date, ts_code, action, current_price, target_price,
                     stop_loss_price, position_ratio, priority, reason, risk_grade,
                     six_dim_score, fusion_score)
                VALUES (?, ?, 'BUY', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report_date, ts_code, current_price, target_price,
                stop_loss_price, cfg['max_position'],
                'HIGH' if score >= 75 else 'MEDIUM' if score >= 55 else 'LOW',
                f"成长通道 评分:{score:.0f} grade:{stock.get('growth_grade','')}",
                cfg['risk_grade'],
                score,
                stock.get('fusion_score', 0)
            ))

            # 同步到观察池
            dims = stock.get('growth_dims', stock.get('dim_scores', {}))
            dim_json = json.dumps(dims, ensure_ascii=False) if isinstance(dims, dict) else ''
            reasons = '; '.join(stock.get('growth_reasons', stock.get('reasons', []))[:3])

            cursor.execute("""
                INSERT OR REPLACE INTO watch_list
                    (ts_code, name, industry, strategy_type, total_score, grade,
                     dim_scores, reasons, stop_loss, target_price,
                     buy_signal_1, buy_signal_2, buy_signal_3, signals_met,
                     status, updated_at)
                VALUES (?, ?, ?, '成长', ?, ?, ?, ?, ?, ?, '', '', '', 0, '观察中', ?)
            """, (
                ts_code, name, stock.get('industry', ''),
                score, stock.get('growth_grade', ''),
                dim_json, reasons[:200] if reasons else '',
                stop_loss_price, target_price, report_date
            ))
            growth_count += 1

        # 写入价值通道
        for stock in value_stocks:
            ts_code = stock.get('ts_code', '')
            name = stock.get('name', ts_code)
            score = stock.get('score', 0)
            current_price = stock.get('current_price', 0)
            cfg = RISK_CONFIG['价值']

            stop_loss_price = current_price * (1 - cfg['stop_loss_pct']) if current_price > 0 else 0
            target_price = current_price * (1 + cfg['take_profit_pct']) if current_price > 0 else 0

            cursor.execute("""
                INSERT OR REPLACE INTO trading_strategy
                    (report_date, ts_code, action, current_price, target_price,
                     stop_loss_price, position_ratio, priority, reason, risk_grade,
                     six_dim_score, fusion_score)
                VALUES (?, ?, 'BUY', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report_date, ts_code, current_price, target_price,
                stop_loss_price, cfg['max_position'],
                'HIGH' if score >= 75 else 'MEDIUM' if score >= 55 else 'LOW',
                f"价值通道 总分:{score:.0f} grade:{stock.get('grade','')}",
                cfg['risk_grade'],
                score,
                stock.get('fusion_score', 0)
            ))

            # 同步到观察池
            dims = stock.get('dim_scores', {})
            dim_json = json.dumps(dims, ensure_ascii=False) if isinstance(dims, dict) else ''
            reasons = '; '.join(stock.get('reasons', []))[:3] if stock.get('reasons') else ''

            cursor.execute("""
                INSERT OR REPLACE INTO watch_list
                    (ts_code, name, industry, strategy_type, total_score, grade,
                     dim_scores, reasons, stop_loss, target_price,
                     buy_signal_1, buy_signal_2, buy_signal_3, signals_met,
                     status, updated_at)
                VALUES (?, ?, ?, '价值', ?, ?, ?, ?, ?, ?, '', '', '', 0, '观察中', ?)
            """, (
                ts_code, name, stock.get('industry', ''),
                score, stock.get('grade', ''),
                dim_json, reasons,
                stop_loss_price, target_price, report_date
            ))
            value_count += 1

        conn.commit()
        logger.info(f"[Bridge] 选股持久化完成: 成长{growth_count}只 + 价值{value_count}只 @ {report_date}")

        return {
            'growth_count': growth_count,
            'value_count': value_count,
            'total_count': growth_count + value_count,
            'report_date': report_date,
            'error': None
        }

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"[Bridge] 选股持久化失败: {e}")
        return {
            'growth_count': 0,
            'value_count': 0,
            'total_count': 0,
            'report_date': report_date,
            'error': str(e)
        }
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def get_backtest_strategy_fn() -> Callable:
    """
    返回一个 strategy_fn，供 BacktestEngine 使用。

    该函数会读取最近一次选股日期的 trading_strategy 表中的 BUY 标的，
    回测只回测这些股票，实现选股与回测的联动。

    Returns:
        strategy_fn(cursor, ts_code) -> bool
    """
    # 预加载最近选股日的标的集合（避免每次调用都查库）
    _cache: Dict[str, set] = {}

    def _load_latest_selection() -> set:
        """加载最近一期的选股权重"""
        if '_selected_set' in _cache:
            return _cache['_selected_set']

        conn = None
        try:
            conn = _get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MAX(report_date) FROM trading_strategy WHERE action = 'BUY'
            """)
            row = cursor.fetchone()
            if not row or not row[0]:
                return set()

            latest_date = row[0]
            cursor.execute("""
                SELECT ts_code FROM trading_strategy
                WHERE report_date = ? AND action = 'BUY'
            """, (latest_date,))
            selected = {r[0] for r in cursor.fetchall()}
            _cache['_selected_set'] = selected
            _cache['_latest_date'] = latest_date
            logger.info(f"[Bridge] 回测选股权重加载: {latest_date} {len(selected)}只")
            return selected

        except Exception as e:
            logger.warning(f"[Bridge] 加载选股权重失败: {e}")
            return set()
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def strategy_fn(cursor, ts_code) -> bool:
        """
        策略过滤函数：只允许当日选股池中的股票通过
        同时保留基本的财务阈值过滤（避免回测过于宽松）
        """
        selected_set = _load_latest_selection()
        if not selected_set:
            # 无选股数据时，退化为原始简化策略
            return _default_strategy(cursor, ts_code)

        if ts_code not in selected_set:
            return False

        # 在选股权重内，再做基本财务过滤
        return _basic_financial_filter(cursor, ts_code)

    return strategy_fn


def _default_strategy(cursor, ts_code):
    """无选股数据时的回退策略"""
    cursor.execute("""
        SELECT f.roe, f.revenue_yoy, f.net_profit_yoy, f.debt_ratio,
               v.close, v.pe, v.pb, v.dv_ttm
        FROM financial_data f
        JOIN valuation_data v ON f.ts_code = v.ts_code
        WHERE f.ts_code = ?
          AND v.trade_date = (SELECT MAX(trade_date) FROM valuation_data WHERE ts_code = ?)
          AND f.end_date = (SELECT MAX(end_date) FROM financial_data WHERE ts_code = ?)
        LIMIT 1
    """, (ts_code, ts_code, ts_code))
    r = cursor.fetchone()
    if not r:
        return False
    roe, rev_yoy, profit_yoy, debt, close, pe, pb, dv = r
    if roe >= 10 and pe and 5 <= pe <= 20 and pb <= 3 and debt < 50:
        return True
    if roe >= 15 and rev_yoy and rev_yoy >= 15 and profit_yoy and profit_yoy >= 15:
        return True
    return False


def _basic_financial_filter(cursor, ts_code):
    """选股权重内的基础财务过滤（比 default_strategy 更宽松，因为选股阶段已过滤）"""
    cursor.execute("""
        SELECT f.roe, f.debt_ratio
        FROM financial_data f
        WHERE f.ts_code = ?
          AND f.end_date = (SELECT MAX(end_date) FROM financial_data WHERE ts_code = ?)
        LIMIT 1
    """, (ts_code, ts_code))
    r = cursor.fetchone()
    if not r:
        return False
    roe, debt = r
    if roe is None or debt is None:
        return False
    # 选股权重内只保留 ROE>=10 且负债<70% 的（比原始宽松，避免过度过滤）
    return roe >= 10 and debt < 70


def get_latest_selection(limit: int = 50) -> List[Dict]:
    """
    获取最近一期选股结果，供 papertrader 等下游模块使用

    Args:
        limit: 最大返回数量

    Returns:
        [{'ts_code', 'name', 'strategy_type', 'current_price',
          'stop_loss_price', 'target_price', 'position_ratio',
          'priority', 'risk_grade', 'reason'}, ...]
    """
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        # 取最近一期 trading_strategy
        cursor.execute("""
            SELECT MAX(report_date) FROM trading_strategy WHERE action = 'BUY'
        """)
        row = cursor.fetchone()
        if not row or not row[0]:
            return []

        latest_date = row[0]
        cursor.execute("""
            SELECT ts_code, current_price, stop_loss_price, target_price,
                   position_ratio, priority, risk_grade, reason,
                   six_dim_score, fusion_score
            FROM trading_strategy
            WHERE report_date = ? AND action = 'BUY'
            ORDER BY priority DESC, id ASC
            LIMIT ?
        """, (latest_date, limit))

        results = []
        for r in cursor.fetchall():
            ts_code = r[0]
            # 从 watch_list 补充名称和策略类型
            cursor.execute("""
                SELECT name, strategy_type FROM watch_list
                WHERE ts_code = ?
                ORDER BY updated_at DESC LIMIT 1
            """, (ts_code,))
            w = cursor.fetchone()
            name = w[0] if w else ts_code
            strategy_type = w[1] if w else '成长'

            results.append({
                'ts_code': ts_code,
                'name': name,
                'strategy_type': strategy_type,
                'current_price': r[1] or 0,
                'stop_loss_price': r[2] or 0,
                'target_price': r[3] or 0,
                'position_ratio': r[4] or 0.15,
                'priority': r[5] or 'MEDIUM',
                'risk_grade': r[6] or 'MEDIUM',
                'reason': r[7] or '',
                'six_dim_score': r[8] or 0,
                'fusion_score': r[9] or 0,
                'report_date': latest_date
            })

        logger.info(f"[Bridge] 读取最新选股: {latest_date} {len(results)}只")
        return results

    except Exception as e:
        logger.warning(f"[Bridge] 读取最新选股失败: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def get_backtest_stocks_for_period(period: str, cursor) -> List[str]:
    """
    获取指定报告期对应的选股标的（供回测引擎按报告期取股池）

    Args:
        period: 报告期，如 '20251231'
        cursor: 数据库游标

    Returns:
        [ts_code, ...]
    """
    try:
        # 找该报告期后最近的 trading_strategy 日期作为选股日
        cursor.execute("""
            SELECT report_date FROM trading_strategy
            WHERE action = 'BUY'
              AND report_date >= DATE(?, '+15 days')
            ORDER BY report_date ASC LIMIT 1
        """, (period,))
        row = cursor.fetchone()
        if not row:
            return []

        buy_date = row[0]
        cursor.execute("""
            SELECT ts_code FROM trading_strategy
            WHERE report_date = ? AND action = 'BUY'
        """, (buy_date,))
        return [r[0] for r in cursor.fetchall()]

    except Exception as e:
        logger.warning(f"[Bridge] 获取报告期选股失败 {period}: {e}")
        return []
