"""
Phase 3 独立脚本：观察池同步 + 预警检查 + 策略生成
目的：把选股结果直接喂进 observation pool + trading strategy，绕过主流程锁竞争
用法：
  python phase3_runner.py --growth "688266.SH:泽璟制药,001309.SZ:德明利"
"""
import os, sys, argparse, logging
from pathlib import Path
from datetime import datetime

# 项目根
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from database import DatabaseManager
from portfolio_manager import WatchListManager, HoldingsManager, AlertManager, StrategyGenerator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('phase3')

def parse_pair(s):
    """解析 "code:name" """
    if not s:
        return None
    parts = str(s).split(':', 1)
    return {'ts_code': parts[0].strip(), 'name': parts[1].strip() if len(parts)>1 else ''}

def main():
    parser = argparse.ArgumentParser(description='Phase 3 观察池/策略生成')
    parser.add_argument('--growth', type=str, default='', help='成长股列表, 逗号分隔 "code:name"')
    parser.add_argument('--value', type=str, default='', help='价值股列表, 逗号分隔 "code:name"')
    args = parser.parse_args()

    db = DatabaseManager()
    db_path = db.db_path
    logger.info(f'DB: {db_path}')

    growth_stocks = [x for x in map(parse_pair, args.growth.split(',')) if x]
    value_stocks  = [x for x in map(parse_pair, args.value.split(',')) if x]

    if not growth_stocks and not value_stocks:
        logger.error('请通过 --growth 或 --value 传入至少一只股票')
        db.close()
        sys.exit(1)

    logger.info(f'输入: 成长 {len(growth_stocks)} 只 / 价值 {len(value_stocks)} 只')

    # ---------- 1. 同步到观察池 ----------
    wm = WatchListManager(db)
    for s in growth_stocks:
        rd = {
            'ts_code': s['ts_code'],
            'name': s.get('name', ''),
            'industry': '',
            'strategy_type': '成长',
            'score': 0,
            'grade': 'N/A',
            'dim_scores': None,
            'reasons': ['期3初筛'],
            'stop_loss': 0,
            'target_price': 0,
            'core_logic': 'phase3 runner',
        }
        wm.add_to_watch(**rd)
        logger.info(f'已入观察池(成长): {s["ts_code"]}')

    for s in value_stocks:
        rd = {
            'ts_code': s['ts_code'],
            'name': s.get('name', ''),
            'industry': '',
            'strategy_type': '价值',
            'score': 0,
            'grade': 'N/A',
            'dim_scores': None,
            'reasons': ['phase3初筛'],
            'stop_loss': 0,
            'target_price': 0,
            'core_logic': 'phase3 runner',
        }
        wm.add_to_watch(**rd)
        logger.info(f'已入观察池(价值): {s["ts_code"]}')

    # ---------- 2. 预警检查 ----------
    am = AlertManager(db)
    alert_cnt = am.run_all_checks()
    logger.info(f'预警检查完成: 触发 {alert_cnt} 条')

    # ---------- 2b. 观察池信号更新（核心桥接） ----------
    wm = WatchListManager(db)
    watch_all = wm.get_watch_list(status='观察中')
    logger.info(f'观察池信号更新: 共 {len(watch_all)} 只')
    for w in watch_all:
        try:
            changed = wm.update_watch_signals(w[0])
            if changed:
                logger.info(f'  信号更新 {w[0]}: {changed}')
        except Exception as e:
            logger.warning(f'信号更新异常 {w[0]}: {e}')

    # ---------- 2c. 触发买入标记 ----------
    for w in watch_all:
        try:
            cnt, _ = wm.update_watch_signals(w[0])
            if cnt >= 2:
                wm.trigger_buy(w[0])
                logger.info(f'  触发买入: {w[0]} (signals={cnt})')
        except Exception as e:
            logger.warning(f'触发买入异常 {w[0]}: {e}')

    # ---------- 3. 策略生成 ----------
    sg = StrategyGenerator(db)
    try:
        strategies = sg.generate_strategies()
        logger.info(f'策略生成完成: 共 {len(strategies)} 条')
        for stg in strategies:
            report_date, ts_code, action, current_price, target_price, stop_loss_price, priority, reason = stg
            logger.info(
                f'  {report_date} {ts_code} action={action} priority={priority} '
                f'price={current_price} target={target_price} stop={stop_loss_price}'
            )
    except Exception as e:
        logger.error(f'策略生成失败: {e}')
        import traceback
        traceback.print_exc()

    db.close()

if __name__ == '__main__':
    main()
