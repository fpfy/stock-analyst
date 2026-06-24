"""
stock-macro 入口脚本
用法：
  python run_macro.py
  python run_macro.py --months 12
"""
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def main():
    parser = __import__('argparse').ArgumentParser(description="stock-macro Skill 入口")
    parser.add_argument("--months", type=int, default=24, help="PMI 回溯月份数")
    args = parser.parse_args()

    os.chdir(PROJECT_ROOT)

    from macro_analyzer import MacroAnalyzer
    analyzer = MacroAnalyzer()
    analyzer.fetch_pmi(months=args.months)

    print(f"市场状态: {analyzer.market_state}")
    print(f"PMI 趋势: {analyzer.pmi_trend}")
    print(f"成长仓位上限: {analyzer.get_position_cap('growth'):.0%}")
    print(f"价值仓位上限: {analyzer.get_position_cap('value'):.0%}")


if __name__ == "__main__":
    main()
