"""
stock-analysis 一键入口脚本
用法：
  python run_dual_selection.py
  python run_dual_selection.py --max-stocks 10
  python run_dual_selection.py --strategy growth
"""
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def main():
    os.chdir(PROJECT_ROOT)

    # 将技能脚本参数透传给 main_v3.py
    # main_v3.py 内部通过 sys.argv 解析（若有），这里直接传递
    sys.argv = ["main_v3.py"] + sys.argv[1:]

    import main_v3
    main_v3.main()


if __name__ == "__main__":
    main()
