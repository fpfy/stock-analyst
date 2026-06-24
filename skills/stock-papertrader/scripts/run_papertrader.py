"""
stock-papertrader 入口脚本
用法：
  python run_papertrader.py --single-day 2026-06-17
  python run_papertrader.py --start 2026-06-10 --end 2026-06-17
  python run_papertrader.py --single-day 2026-06-17 --cash 500000
"""
import sys
import os
import argparse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def main():
    parser = argparse.ArgumentParser(description="stock-papertrader Skill 入口")
    parser.add_argument("--single-day")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--cash", type=float, default=1_000_000)
    args = parser.parse_args()

    os.chdir(PROJECT_ROOT)

    if args.single_day:
        sys.argv = [
            "papertrader_final.py",
            "--single-day", args.single_day,
            "--cash", str(args.cash),
        ]
    elif args.start and args.end:
        sys.argv = [
            "papertrader_final.py",
            "--start-date", args.start,
            "--end-date", args.end,
            "--cash", str(args.cash),
        ]
    else:
        # 默认：运行当日
        sys.argv = [
            "papertrader_final.py",
            "--single-day", "today",
            "--cash", str(args.cash),
        ]

    import papertrader_final
    papertrader_final.main()


if __name__ == "__main__":
    main()
