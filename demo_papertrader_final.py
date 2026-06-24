"""
demo_papertrader_final.py - 演示实盘模拟交易正式版功能
"""
from papertrader_final import PaperTraderFinal
import datetime

def demo_single_day():
    """演示单日交易"""
    print("=== 单日交易演示 ===")
    
    # 创建模拟交易器
    trader = PaperTraderFinal(initial_cash=1_000_000)
    
    try:
        # 运行单日交易
        result = trader.run_single_day('2026-06-17')
        
        print(f"\n单日交易结果:")
        print(f"日期: {result['date']}")
        print(f"净值: {result['nav']:,.0f}")
        print(f"现金: {result['cash']:,.0f}")
        print(f"持仓数: {result['holdings_count']}")
        print(f"交易数: {result['trade_count']}")
        
        # 获取当前持仓
        positions = trader.get_current_positions()
        print(f"\n当前持仓:")
        for pos in positions:
            print(f"  {pos['ts_code']} - {pos['name']}: {pos['shares']}股 @ {pos['current_price']}")
            print(f"    盈亏: {pos['profit_pct']:.2f}%")
        
        # 获取绩效统计
        perf = trader.get_performance_summary()
        print(f"\n绩效统计:")
        for key, value in perf.items():
            print(f"  {key}: {value}")
        
    finally:
        trader.close()

def demo_batch_trading():
    """演示批量交易"""
    print("\n=== 批量交易演示 ===")
    
    # 创建模拟交易器
    trader = PaperTraderFinal(initial_cash=1_000_000)
    
    try:
        # 运行批量交易
        results = trader.run_batch_trading('2026-06-10', '2026-06-17')
        
        print(f"\n批量交易完成，共 {len(results)} 个交易日")
        
        # 获取最终绩效
        perf = trader.get_performance_summary()
        print(f"\n最终绩效:")
        for key, value in perf.items():
            print(f"  {key}: {value}")
        
        # 导出交易历史
        trader.export_trade_history('demo_trade_history.csv')
        print(f"\n交易历史已导出至: demo_trade_history.csv")
        
    finally:
        trader.close()

def demo_custom_initial_cash():
    """演示自定义初始资金"""
    print("\n=== 自定义初始资金演示 ===")
    
    # 使用不同初始资金
    initial_cash = 500_000
    trader = PaperTraderFinal(initial_cash=initial_cash)
    
    try:
        result = trader.run_single_day('2026-06-17')
        print(f"初始资金: {initial_cash:,}")
        print(f"最终净值: {result['nav']:,.0f}")
        print(f"收益率: {(result['nav'] - initial_cash) / initial_cash * 100:.2f}%")
        
    finally:
        trader.close()

def demo_weekly_summary():
    """演示周度总结功能"""
    print("\n=== 周度总结演示 ===")
    
    trader = PaperTraderFinal(initial_cash=1_000_000)
    
    try:
        # 运行一周交易
        results = trader.run_batch_trading('2026-06-10', '2026-06-17')
        
        # 输出每日结果
        print("\n每日交易结果:")
        for i, result in enumerate(results):
            print(f"  {result['date']}: 净值 {result['nav']:,.0f}, 交易数 {result['trade_count']}")
        
        # 获取最终统计
        perf = trader.get_performance_summary()
        print(f"\n周度统计:")
        print(f"  总收益率: {perf['total_return_pct']:.2f}%")
        print(f"  胜率: {perf['win_rate_pct']:.1f}%")
        print(f"  最大回撤: {perf['max_drawdown_pct']:.2f}%")
        print(f"  夏普比率: {perf['sharpe_ratio']}")
        print(f"  波动率: {perf['volatility_pct']:.2f}%")
        
    finally:
        trader.close()

if __name__ == "__main__":
    print("实盘模拟交易正式版演示")
    print("="*50)
    
    # 运行所有演示
    demo_single_day()
    demo_batch_trading()
    demo_custom_initial_cash()
    demo_weekly_summary()
    
    print("\n" + "="*50)
    print("演示完成！")
    print("\n主要功能:")
    print("1. 单日交易模拟")
    print("2. 批量交易模拟")
    print("3. 自定义初始资金")
    print("4. 周度总结和绩效分析")
    print("5. 交易历史导出")
    print("6. 优化止损机制")
    print("7. 详细的绩效统计")