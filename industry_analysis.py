"""
industry_analysis.py - 行业分析模块
实现行业分析、行业轮动策略、行业评分体系等功能
"""
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class IndustryAnalysis:
    """行业分析类"""
    
    def __init__(self, db_path: str = "database/stock_analysis.db"):
        """初始化行业分析"""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # 行业分类映射
        self.industry_mapping = {
            # 金融行业
            "银行": ["601398.SH", "601939.SH", "600036.SH", "601318.SH"],
            "保险": ["601318.SH", "601601.SH", "601336.SH", "601328.SH"],
            "证券": ["600030.SH", "600837.SH", "600999.SH", "601688.SH"],
            
            # 科技行业
            "半导体": ["002415.SZ", "600536.SH", "002371.SZ", "600460.SH"],
            "软件服务": ["300059.SZ", "300124.SZ", "002230.SZ", "600588.SH"],
            "消费电子": ["002475.SZ", "300454.SZ", "002413.SZ", "600883.SH"],
            
            # 消费行业
            "白酒": ["600519.SH", "000858.SZ", "000568.SZ", "000596.SZ"],
            "家电": ["000651.SZ", "600887.SH", "000333.SZ", "600690.SH"],
            "食品饮料": ["600300.SH", "002415.SZ", "600519.SH", "000858.SZ"],
            
            # 医药行业
            "医药生物": ["600276.SH", "000661.SZ", "002007.SZ", "300003.SZ"],
            "医疗器械": ["300760.SZ", "002432.SZ", "300458.SZ", "300676.SZ"],
            "医疗服务": ["300142.SZ", "300663.SZ", "300253.SZ", "300296.SZ"],
            
            # 新能源行业
            "光伏": ["300274.SZ", "002459.SZ", "300393.SZ", "600438.SH"],
            "风电": ["300816.SZ", "002202.SZ", "300346.SZ", "300496.SZ"],
            "新能源汽车": ["002415.SZ", "300750.SZ", "002594.SZ", "300724.SZ"],
            
            # 制造业
            "汽车": ["600104.SH", "000625.SZ", "002594.SZ", "600166.SH"],
            "机械": ["000157.SZ", "002410.SZ", "300296.SZ", "600519.SH"],
            "化工": ["600309.SH", "000830.SZ", "002422.SZ", "600612.SH"],
            
            # 周期性行业
            "钢铁": ["600019.SH", "000898.SZ", "002460.SZ", "600585.SH"],
            "有色": ["600547.SH", "000063.SZ", "002460.SZ", "600362.SH"],
            "煤炭": ["601898.SH", "000983.SZ", "002128.SZ", "600348.SH"],
            
            # 公用事业
            "电力": ["600886.SH", "000958.SZ", "600795.SH", "002039.SZ"],
            "水务": ["600008.SH", "000826.SZ", "600388.SH", "300388.SZ"],
            "燃气": ["600333.SH", "000096.SZ", "600732.SH", "300338.SZ"],
            
            # 地产行业
            "房地产": ["000002.SZ", "600048.SH", "600383.SH", "002244.SZ"],
            "物业管理": ["600048.SH", "002911.SZ", "002916.SZ", "300248.SZ"],
            "家居装饰": ["603833.SH", "002415.SZ", "600612.SH", "300338.SZ"],
            
            # 交通运输
            "航空": ["600029.SH", "000858.SZ", "600115.SH", "600221.SH"],
            "港口": ["600017.SH", "600190.SH", "000088.SZ", "600317.SH"],
            "高速公路": ["600038.SH", "600548.SH", "000429.SZ", "600350.SH"],
            
            # 通信行业
            "5G": ["300052.SZ", "002415.SZ", "300496.SZ", "600522.SH"],
            "通信设备": ["000063.SZ", "002415.SZ", "600487.SH", "300408.SZ"],
            "通信服务": ["600050.SH", "002415.SZ", "600522.SH", "300338.SZ"],
            
            # 其他行业
            "农业": ["000876.SZ", "002299.SZ", "002041.SZ", "600336.SH"],
            "零售": ["600859.SH", "000858.SZ", "002415.SZ", "600631.SH"],
            "旅游": ["600138.SH", "000063.SZ", "002415.SZ", "600631.SH"]
        }
        
        # 行业轮动指标
        self.rotation_indicators = {
            "relative_strength": "相对强度",
            "momentum": "动量指标",
            "valuation": "估值水平",
            "volume": "成交量",
            "sentiment": "市场情绪",
            "policy": "政策影响"
        }
        
        logger.info("行业分析模块初始化完成")
    
    def get_industry_stocks(self, industry_name: str) -> List[str]:
        """获取行业股票列表"""
        return self.industry_mapping.get(industry_name, [])
    
    def calculate_industry_strength(self, industry_name: str, period: str = "20d") -> Dict:
        """计算行业强度"""
        stocks = self.get_industry_stocks(industry_name)
        if not stocks:
            return {"error": f"行业 {industry_name} 没有对应的股票"}
        
        # 获取行业股票的平均表现
        total_return = 0
        valid_stocks = 0
        
        for stock in stocks:
            try:
                # 获取股票价格数据
                self.cursor.execute("""
                    SELECT close FROM daily_quotes 
                    WHERE ts_code = ? AND trade_date >= '2026-06-01'
                    ORDER BY trade_date DESC
                    LIMIT 2
                """, (stock,))
                
                prices = self.cursor.fetchall()
                if len(prices) >= 2:
                    current_price = prices[0][0]
                    previous_price = prices[1][0]
                    if previous_price > 0:
                        return_rate = (current_price - previous_price) / previous_price
                        total_return += return_rate
                        valid_stocks += 1
                        
            except Exception as e:
                logger.warning(f"获取股票 {stock} 价格数据失败: {e}")
                continue
        
        if valid_stocks > 0:
            avg_return = total_return / valid_stocks
            industry_strength = {
                "industry_name": industry_name,
                "avg_return": avg_return,
                "stock_count": valid_stocks,
                "total_stocks": len(stocks),
                "strength_level": self._get_strength_level(avg_return)
            }
            return industry_strength
        else:
            return {"error": f"行业 {industry_name} 无法计算强度"}
    
    def _get_strength_level(self, return_rate: float) -> str:
        """获取强度等级"""
        if return_rate > 0.05:
            return "强势"
        elif return_rate > 0.02:
            return "偏强"
        elif return_rate > -0.02:
            return "平稳"
        elif return_rate > -0.05:
            return "偏弱"
        else:
            return "弱势"
    
    def calculate_industry_rotation(self, period: str = "60d") -> Dict:
        """计算行业轮动信号"""
        rotation_signals = {}
        
        for industry_name in self.industry_mapping.keys():
            strength = self.calculate_industry_strength(industry_name, period)
            if "error" not in strength:
                rotation_signals[industry_name] = strength
        
        # 按收益率排序
        sorted_industries = sorted(
            rotation_signals.items(), 
            key=lambda x: x[1]["avg_return"], 
            reverse=True
        )
        
        return {
            "rotation_signals": sorted_industries,
            "top_industries": sorted_industries[:5],
            "bottom_industries": sorted_industries[-5:],
            "market_cycle": self._detect_market_cycle(rotation_signals)
        }
    
    def _detect_market_cycle(self, rotation_signals: Dict) -> str:
        """检测市场周期"""
        if not rotation_signals:
            return "unknown"
        
        # 计算平均收益率
        avg_return = np.mean([signal["avg_return"] for signal in rotation_signals.values()])
        
        # 判断市场周期
        if avg_return > 0.03:
            return "bull_market"  # 牛市
        elif avg_return < -0.03:
            return "bear_market"  # 熊市
        else:
            return "sideways_market"  # 震荡市
    
    def score_industry(self, industry_name: str) -> Dict:
        """对行业进行评分"""
        stocks = self.get_industry_stocks(industry_name)
        if not stocks:
            return {"error": f"行业 {industry_name} 没有对应的股票"}
        
        # 获取行业基本面数据
        industry_score = {
            "industry_name": industry_name,
            "fundamental_score": 0,
            "technical_score": 0,
            "valuation_score": 0,
            "policy_score": 0,
            "total_score": 0,
            "rank": 0,
            "recommendation": "观望"
        }
        
        # 基本面评分 (30%)
        fundamental_score = self._score_industry_fundamental(industry_name, stocks)
        industry_score["fundamental_score"] = fundamental_score
        
        # 技术面评分 (25%)
        technical_score = self._score_industry_technical(industry_name, stocks)
        industry_score["technical_score"] = technical_score
        
        # 估值评分 (25%)
        valuation_score = self._score_industry_valuation(industry_name, stocks)
        industry_score["valuation_score"] = valuation_score
        
        # 政策评分 (20%)
        policy_score = self._score_industry_policy(industry_name)
        industry_score["policy_score"] = policy_score
        
        # 计算总分
        industry_score["total_score"] = (
            fundamental_score * 0.3 +
            technical_score * 0.25 +
            valuation_score * 0.25 +
            policy_score * 0.2
        )
        
        # 确定推荐等级
        industry_score["recommendation"] = self._get_industry_recommendation(industry_score["total_score"])
        
        return industry_score
    
    def _score_industry_fundamental(self, industry_name: str, stocks: List[str]) -> float:
        """行业基本面评分"""
        # 这里简化处理，实际应该获取行业财务数据
        base_score = 60  # 基础分
        
        # 根据行业类型调整
        if industry_name in ["白酒", "医药生物", "半导体"]:
            base_score += 10  # 高成长性行业
        elif industry_name in ["银行", "保险", "公用事业"]:
            base_score += 5   # 稳定性行业
        elif industry_name in ["钢铁", "煤炭", "有色"]:
            base_score -= 10  # 周期性行业
        
        return min(100, max(0, base_score))
    
    def _score_industry_technical(self, industry_name: str, stocks: List[str]) -> float:
        """行业技术面评分"""
        # 这里简化处理，实际应该计算行业技术指标
        base_score = 60  # 基础分
        
        # 获取行业平均表现
        strength = self.calculate_industry_strength(industry_name)
        if "error" not in strength:
            if strength["avg_return"] > 0.05:
                base_score += 20
            elif strength["avg_return"] > 0.02:
                base_score += 10
            elif strength["avg_return"] < -0.05:
                base_score -= 20
        
        return min(100, max(0, base_score))
    
    def _score_industry_valuation(self, industry_name: str, stocks: List[str]) -> float:
        """行业估值评分"""
        # 这里简化处理，实际应该获取行业估值数据
        base_score = 60  # 基础分
        
        # 根据行业类型调整
        if industry_name in ["银行", "保险", "公用事业"]:
            base_score += 10  # 低估值行业
        elif industry_name in ["半导体", "新能源", "医药生物"]:
            base_score -= 10  # 高估值行业
        
        return min(100, max(0, base_score))
    
    def _score_industry_policy(self, industry_name: str) -> float:
        """行业政策评分"""
        # 这里简化处理，实际应该分析政策影响
        base_score = 60  # 基础分
        
        # 根据政策敏感度调整
        if industry_name in ["新能源", "半导体", "5G"]:
            base_score += 15  # 政策支持行业
        elif industry_name in ["房地产", "钢铁", "煤炭"]:
            base_score -= 10  # 政策调控行业
        
        return min(100, max(0, base_score))
    
    def _get_industry_recommendation(self, total_score: float) -> str:
        """获取行业推荐等级"""
        if total_score >= 80:
            return "强烈推荐"
        elif total_score >= 70:
            return "推荐"
        elif total_score >= 60:
            return "中性"
        elif total_score >= 50:
            return "谨慎"
        else:
            return "回避"
    
    def get_industry_ranking(self) -> List[Dict]:
        """获取行业排名"""
        industry_scores = []
        
        for industry_name in self.industry_mapping.keys():
            score = self.score_industry(industry_name)
            if "error" not in score:
                industry_scores.append(score)
        
        # 按总分排序
        industry_scores.sort(key=lambda x: x["total_score"], reverse=True)
        
        # 添加排名
        for i, score in enumerate(industry_scores):
            score["rank"] = i + 1
        
        return industry_scores
    
    def generate_industry_report(self) -> str:
        """生成行业分析报告"""
        industry_ranking = self.get_industry_ranking()
        rotation_signals = self.calculate_industry_rotation()
        
        report = f"""# 行业分析报告

生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
分析行业数量: {len(industry_ranking)}

## 行业排名

| 排名 | 行业名称 | 总分 | 基本面 | 技术面 | 估值 | 政策 | 推荐等级 |
|------|----------|------|--------|--------|------|------|----------|"""
        
        for industry in industry_ranking[:10]:
            report += f"""
| {industry['rank']} | {industry['industry_name']} | {industry['total_score']:.1f} | {industry['fundamental_score']:.1f} | {industry['technical_score']:.1f} | {industry['valuation_score']:.1f} | {industry['policy_score']:.1f} | {industry['recommendation']} |"""
        
        report += f"""

## 行业轮动信号

### 市场周期: {rotation_signals['market_cycle']}

### 强势行业
"""
        
        for industry in rotation_signals['top_industries']:
            report += f"- {industry[0]}: {industry[1]['avg_return']:.2%} ({industry[1]['strength_level']})\n"
        
        report += "\n### 弱势行业\n"
        
        for industry in rotation_signals['bottom_industries']:
            report += f"- {industry[0]}: {industry[1]['avg_return']:.2%} ({industry[1]['strength_level']})\n"
        
        report += f"""

## 投资建议

### 重点关注的行业
"""
        
        for industry in industry_ranking[:5]:
            report += f"- {industry['industry_name']} ({industry['recommendation']})\n"
        
        report += "\n### 需要谨慎的行业\n"
        
        for industry in industry_ranking[-5:]:
            report += f"- {industry['industry_name']} ({industry['recommendation']})\n"
        
        return report
    
    def close(self):
        """关闭数据库连接"""
        self.conn.close()


if __name__ == "__main__":
    # 测试行业分析模块
    industry_analysis = IndustryAnalysis()
    
    # 测试行业强度计算
    print("测试行业强度计算:")
    strength = industry_analysis.calculate_industry_strength("白酒")
    print(strength)
    
    # 测试行业评分
    print("\n测试行业评分:")
    score = industry_analysis.score_industry("白酒")
    print(score)
    
    # 测试行业排名
    print("\n测试行业排名:")
    ranking = industry_analysis.get_industry_ranking()
    for industry in ranking[:5]:
        print(f"{industry['rank']}. {industry['industry_name']}: {industry['total_score']:.1f}分")
    
    # 生成报告
    print("\n生成行业分析报告:")
    report = industry_analysis.generate_industry_report()
    print(report)
    
    industry_analysis.close()