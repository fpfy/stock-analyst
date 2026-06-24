"""
macro_analyzer.py
独立宏观判断模块：不依赖 macro_indicators 表
读取：AkShare / Tushare 在线数据，全内存计算
输出：多空判断 + 对仓位上限的影响
"""
import logging
import akshare as ak
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)


class MacroAnalyzer:
    """宏观经济大盘状态判断"""

    def __init__(self):
        self.pmi = None
        self.pmi_trend = None
        self.market_state = None  # '强多' / '震荡' / '弱空'

    def fetch_pmi(self, months=24):
        """拉取 PMI 制造业指数"""
        try:
            df = ak.macro_china_pmi()
            df = df.rename(columns={'月份': 'month', '制造业-指数': 'pmi_value'})
            df['month'] = df['month'].str.replace('年', '-').str.replace('月份', '')
            df['pmi_value'] = pd.to_numeric(df['pmi_value'], errors='coerce')
            df = df.dropna(subset=['pmi_value']).sort_values('month').tail(months)
            self.pmi = df.set_index('month')['pmi_value']
            self._calc_trend()
            self._judge_market()
            logger.info(f"PMI 已更新: {self.pmi.tail(3).to_dict()}")
        except Exception as e:
            logger.error(f"拉取 PMI 失败: {e}")

    def _calc_trend(self):
        if self.pmi is None or len(self.pmi) < 3:
            self.pmi_trend = '未知'
            return
        last3 = list(self.pmi.tail(3))
        if last3[-1] > last3[-2] > last3[0]:
            self.pmi_trend = '上行'
        elif last3[-1] < last3[-2] < last3[0]:
            self.pmi_trend = '下行'
        else:
            self.pmi_trend = '震荡'

    def _judge_market(self):
        if self.pmi is None or len(self.pmi) == 0:
            self.market_state = '数据未知'
            return
        latest = float(self.pmi.iloc[-1])
        # 用最近半年均值判断强弱
        avg = float(self.pmi.tail(6).mean())
        if latest > 51 and avg > 51:
            self.market_state = '强多'
        elif latest < 49 and avg < 49:
            self.market_state = '弱空'
        else:
            self.market_state = '震荡'

    def get_position_cap(self, strategy_type):
        """
        基于宏观状态给仓位上限建议
        """
        if self.market_state == '强多':
            return 0.20 if strategy_type == '成长' else 0.25
        elif self.market_state == '震荡':
            return 0.15 if strategy_type == '成长' else 0.20
        else:  # 弱空
            return 0.10 if strategy_type == '成长' else 0.15

    def to_markdown_chapter(self):
        lines = []
        lines += ["## 宏观经济与大盘状态", "",
                 f"> 分析时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
                 ""]
        if self.pmi is None:
            lines += ["⚠️ PMI 数据暂不可用，宏观判断无法完成。", ""]
            return "\n".join(lines)
        latest = self.pmi.iloc[-1]
        lines += [
            f"**制造业 PMI**：{latest}（{self.pmi_trend}）",
            f"- 近6个月均值：{self.pmi.tail(6).mean():.2f}",
            f"- 近3个月均值：{self.pmi.tail(3).mean():.2f}",
            "",
            "| 月份 | PMI |",
            "|:---|:---:|",
        ]
        for m, v in self.pmi.tail(6).items():
            flag = "✅" if v >= 50 else "❌"
            lines.append(f"| {m} | {v:.1f} {flag} |")
        lines += ["",
                 f"### 大盘状态判断：{self.market_state}",
                 ""]
        if self.market_state == '强多':
            lines += [
                "- PMI 持续扩张，制造业回升，成长股可适度加仓。",
                "- 建议仓位上限：成长 20%，价值 25%。",
                "",
            ]
        elif self.market_state == '震荡':
            lines += [
                "- PMI 在荣枯线附近波动，经济恢复基础不稳，大盘大概率区间震荡。",
                "- 建议仓位上限：成长 15%，价值 20%。",
                "- 避免追高，优先低估值 + 高股息价值股。",
                "",
            ]
        else:
            lines += [
                "- PMI 持续低于荣枯线，制造业收缩，防御为主。",
                "- 建议仓位上限：成长 10%，价值 15%。",
                "- 价值股需进一步压缩到高股息蓝筹，成长股仅保留信号强且负债率低标的。",
                "",
            ]
        return "\n".join(lines)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    analyzer = MacroAnalyzer()
    analyzer.fetch_pmi()
    print(analyzer.to_markdown_chapter())
    print("\n仓位建议:")
    for t in ['成长', '价值']:
        print(f"  {t}: {analyzer.get_position_cap(t)*100:.0f}%")
