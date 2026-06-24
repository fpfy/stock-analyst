"""
backtest_v3_runner.py —— backtest_v3 的轻量运行入口
不写引擎，只调用已有回测脚本导入并执行
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    import backtest_v3 as bt
    report = bt.run_backtest()
    print(report)
