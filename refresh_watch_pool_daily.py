"""
refresh_watch_pool_daily.py

每日观察池刷新入口脚本
用途：Windows 计划任务 / cron 调用

输出：
- 将观察池写入 watch_pool 表
- 打印简短结果摘要
"""
import sys
import logging
from datetime import datetime

# 保证能导入 stock_analysis_system 包
sys.path.insert(0, r'C:\Users\Fengpeng\stock_analysis_system')

from observation_pool_builder import refresh_watch_pool

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)


def main():
    print(f"[REFRESH] 开始刷新观察池: {datetime.now()}")
    try:
        result = refresh_watch_pool(top_n_industries=8, min_score=55)
        print(f"[REFRESH] 报告日期: {result.get('report_date')}")
        print(f"[REFRESH] 候选行业: {result.get('industry_candidates')} 个")
        print(f"[REFRESH] 股票池: {result.get('stock_universe')} 只")
        print(f"[REFRESH] 成长: {result.get('growth_pool')} 只 | 价值: {result.get('value_pool')} 只")
        print(f"[REFRESH] 持久化: {result.get('persist')}")
        print(f"[REFRESH] Top 行业: {result.get('top_industries')}")
        print(f"[REFRESH] 宏观信号: {result.get('macro_signal')}")
        print("[REFRESH] 完成")
        return 0
    except Exception as e:
        logging.error(f"[REFRESH] 刷新失败: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
