"""
stock-backtest 入口脚本
用法：
  python run_backtest.py --strategy growth --start 2024-01-01 --end 2024-12-31
  python run_backtest.py --strategy all --hold-days 30
  python run_backtest.py --quick   # 快速验证（max-stocks 10）
"""
import sys
import os
import argparse

# 确保能找到项目根目录的模块
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def main():
    parser = argparse.ArgumentParser(description="stock-backtest Skill 入口")
    parser.add_argument("--strategy", default="all", choices=["growth", "value", "all"])
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--hold-days", type=int, default=30)
    parser.add_argument("--quick", action="store_true", help="快速验证：max-stocks 10")
    args = parser.parse_args()

    os.chdir(PROJECT_ROOT)

    if args.quick:
        sys.argv = [
            "backtest_v3.py",
            "--max-stocks", "10",
        ]
    else:
        sys.argv = [
            "backtest_v3.py",
            "--strategy", args.strategy,
            "--start", args.start,
            "--end", args.end,
            "--hold-days", str(args.hold_days),
        ]

    # 延迟导入，确保 sys.path 已设置
    import backtest_v3
    backtest_v3.main()


if __name__ == "__main__":
    main()
