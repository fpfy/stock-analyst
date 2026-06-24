"""
industry_rotation_strategy.py - 行业轮动策略模块
实现基于行业轮动策略的投资决策系统
"""
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from industry_analysis import IndustryAnalysis

logger = logging.getLogger(__name__)

class IndustryRotationStrategy:
    """行业轮动策略类"""
    
    def __init__(self, db_path: str = "database/stock_analysis.db"):
        """初始化行业轮动策略"""
        self.db_path = db_path
        self.industry_analysis = IndustryAnalysis(db_path)
        
        # 行业轮动参数
        self.lookback_period = 60  # 回看期（天）
        self.top_n_industries = 5   # 选择的行业数量
        self.rebalance_frequency = 30  # 调仓频率（天）
        
        # 权重分配策略
        self.weight_allocation = {
            "top_industry": 0.3,      # 最强势行业权重
            "second_industry": 0.25, # 第二强势行业权重
            "third_industry": 0.2,   # 第三强势行业权重
            "fourth_industry": 0.15, # 第四强势行业权重
            "fifth_industry": 0.1    # 第五强势行业权重
        }
        
        logger.info("行业轮动策略模块初始化完成")
    
    def calculate_industry_momentum(self, industry_name: str, period: str = "20d") -> Dict:
        """计算行业动量指标"""
        stocks = self.industry_analysis.get_industry_stocks(industry_name)
        if not stocks:
            return {"error": f"行业 {industry_name} 没有对应的股票"}
        
        momentum_scores = []
        
        for stock in stocks:
            try:
                # 获取股票价格数据
                self.industry_analysis.cursor.execute("""
                    SELECT close, trade_date FROM daily_quotes 
                    WHERE ts_code = ? AND trade_date >= '2026-06-01'
                    ORDER BY trade_date DESC
                """, (stock,))
                
                prices = self.industry_analysis.cursor.fetchall()
                if len(prices) >= 2:
                    # 计算动量得分
                    current_price = prices[0][0]
                    previous_price = prices[-1][0]
                    
                    if previous_price > 0:
                        return_rate = (current_price - previous_price) / previous_price
                        momentum_scores.append(return_rate)
                        
            except Exception as e:
                logger.warning(f"获取股票 {stock} 价格数据失败: {e}")
                continue
        
        if momentum_scores:
            avg_momentum = np.mean(momentum_scores)
            momentum_std = np.std(momentum_scores)
            
            return {
                "industry_name": industry_name,
                "avg_momentum": avg_momentum,
                "momentum_std": momentum_std,
                "momentum_score": self._calculate_momentum_score(avg_momentum, momentum_std),
                "stock_count": len(momentum_scores)
            }
        else:
            return {"error": f"行业 {industry_name} 无法计算动量"}
    
    def _calculate_momentum_score(self, avg_momentum: float, momentum_std: float) -> float:
        """计算动量得分"""
        # 动量得分 = 平均动量 * (1 - 动量标准差/2)
        # 这样既考虑了动量大小，又考虑了动量的稳定性
        momentum_score = avg_momentum * (1 - momentum_std / 2)
        return momentum_score
    
    def get_industry_momentum_ranking(self) -> List[Dict]:
        """获取行业动量排名"""
        momentum_ranking = []
        
        for industry_name in self.industry_analysis.industry_mapping.keys():
            momentum = self.calculate_industry_momentum(industry_name)
            if "error" not in momentum:
                momentum_ranking.append(momentum)
        
        # 按动量得分排序
        momentum_ranking.sort(key=lambda x: x["momentum_score"], reverse=True)
        
        # 添加排名
        for i, momentum in enumerate(momentum_ranking):
            momentum["rank"] = i + 1
        
        return momentum_ranking
    
    def generate_rotation_signals(self) -> Dict:
        """生成行业轮动信号"""
        # 获取行业动量排名
        momentum_ranking = self.get_industry_momentum_ranking()
        
        # 获取行业评分排名
        industry_ranking = self.industry_analysis.get_industry_ranking()
        
        # 生成轮动信号
        rotation_signals = {
            "momentum_ranking": momentum_ranking[:self.top_n_industries],
            "industry_ranking": industry_ranking[:self.top_n_industries],
            "combined_signals": self._combine_signals(momentum_ranking, industry_ranking),
            "rotation_timing": self._detect_rotation_timing(momentum_ranking),
            "market_regime": self._detect_market_regime(momentum_ranking)
        }
        
        return rotation_signals
    
    def _combine_signals(self, momentum_ranking: List[Dict], industry_ranking: List[Dict]) -> List[Dict]:
        """合并动量和行业评分信号"""
        combined_signals = []
        
        # 创建行业名称到评分的映射
        industry_score_map = {industry["industry_name"]: industry["total_score"] 
                           for industry in industry_ranking}
        
        # 创建行业名称到动量的映射
        industry_momentum_map = {industry["industry_name"]: industry["momentum_score"] 
                                for industry in momentum_ranking}
        
        # 合并信号
        for industry_name in set(industry_score_map.keys()) | set(industry_momentum_map.keys()):
            if industry_name in industry_score_map and industry_name in industry_momentum_map:
                combined_score = (
                    industry_score_map[industry_name] * 0.4 +  # 行业评分权重40%
                    industry_momentum_map[industry_name] * 100 * 0.6  # 动量得分权重60%
                )
                
                combined_signals.append({
                    "industry_name": industry_name,
                    "industry_score": industry_score_map[industry_name],
                    "momentum_score": industry_momentum_map[industry_name],
                    "combined_score": combined_score,
                    "score_rank": 0  # 将在后面计算
                })
        
        # 按合并得分排序
        combined_signals.sort(key=lambda x: x["combined_score"], reverse=True)
        
        # 添加排名
        for i, signal in enumerate(combined_signals):
            signal["score_rank"] = i + 1
        
        return combined_signals
    
    def _detect_rotation_timing(self, momentum_ranking: List[Dict]) -> str:
        """检测轮动时机"""
        if not momentum_ranking:
            return "unknown"
        
        # 计算前5名行业的平均动量
        top_momentum = np.mean([industry["momentum_score"] for industry in momentum_ranking[:5]])
        
        # 计算后5名行业的平均动量
        bottom_momentum = np.mean([industry["momentum_score"] for industry in momentum_ranking[-5:]])
        
        # 计算动量差
        momentum_diff = top_momentum - bottom_momentum
        
        # 判断轮动时机
        if momentum_diff > 0.1:
            return "strong_rotation"
        elif momentum_diff > 0.05:
            return "moderate_rotation"
        elif momentum_diff > -0.05:
            return "stable_rotation"
        else:
            return "weak_rotation"
    
    def _detect_market_regime(self, momentum_ranking: List[Dict]) -> str:
        """检测市场状态"""
        if not momentum_ranking:
            return "unknown"
        
        # 计算所有行业的平均动量
        avg_momentum = np.mean([industry["momentum_score"] for industry in momentum_ranking])
        
        # 判断市场状态
        if avg_momentum > 0.05:
            return "bull_market"
        elif avg_momentum < -0.05:
            return "bear_market"
        else:
            return "sideways_market"
    
    def generate_portfolio_allocation(self) -> Dict:
        """生成行业配置建议"""
        rotation_signals = self.generate_rotation_signals()
        combined_signals = rotation_signals["combined_signals"]
        
        # 选择前5个行业
        top_industries = combined_signals[:5]
        
        # 计算配置权重
        allocation = {}
        for i, industry in enumerate(top_industries):
            industry_name = industry["industry_name"]
            weight = self.weight_allocation[f"top_industry"]
            
            # 根据行业得分调整权重
            score_ratio = industry["combined_score"] / top_industries[0]["combined_score"]
            weight *= score_ratio
            
            allocation[industry_name] = weight
        
        # 归一化权重
        total_weight = sum(allocation.values())
        for industry in allocation:
            allocation[industry] /= total_weight
        
        portfolio_allocation = {
            "allocation": allocation,
            "top_industries": top_industries,
            "rotation_timing": rotation_signals["rotation_timing"],
            "market_regime": rotation_signals["market_regime"],
            "rebalance_date": datetime.now().strftime("%Y-%m-%d"),
            "expected_return": self._calculate_expected_return(top_industries),
            "risk_level": self._calculate_risk_level(top_industries)
        }
        
        return portfolio_allocation
    
    def _calculate_expected_return(self, top_industries: List[Dict]) -> float:
        """计算预期收益率"""
        if not top_industries:
            return 0.0
        
        # 基于行业得分和动量得分计算预期收益率
        weighted_return = 0.0
        total_weight = 0.0
        
        for industry in top_industries:
            industry_return = (industry["industry_score"] / 100) * 0.1 + industry["momentum_score"] * 0.2
            weight = 1.0 / len(top_industries)  # 等权重
            weighted_return += industry_return * weight
            total_weight += weight
        
        return weighted_return / total_weight if total_weight > 0 else 0.0
    
    def _calculate_risk_level(self, top_industries: List[Dict]) -> str:
        """计算风险水平"""
        if not top_industries:
            return "unknown"
        
        # 计算行业得分的标准差（归一化到0-1）
        scores = [industry["industry_score"] for industry in top_industries]
        score_std = np.std(scores) / 100  # 归一化
        
        # 计算动量得分的标准差
        momentums = [industry["momentum_score"] for industry in top_industries]
        momentum_std = np.std(momentums)
        
        # 综合风险水平
        risk_score = (score_std + momentum_std) / 2
        
        if risk_score > 0.1:
            return "high"
        elif risk_score > 0.03:
            return "medium"
        else:
            return "low"
    
    def generate_rotation_report(self) -> str:
        """生成行业轮动策略报告"""
        rotation_signals = self.generate_rotation_signals()
        portfolio_allocation = self.generate_portfolio_allocation()
        
        report = f"""# 行业轮动策略报告

生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
分析周期: {self.lookback_period}天
调仓频率: {self.rebalance_frequency}天

## 市场状态分析

### 市场周期: {rotation_signals['market_regime']}
### 轮动时机: {rotation_signals['rotation_timing']}

## 行业动量排名

| 排名 | 行业名称 | 动量得分 | 平均动量 | 动量标准差 |
|------|----------|----------|----------|------------|"""
        
        for industry in rotation_signals["momentum_ranking"]:
            report += f"""
| {industry['rank']} | {industry['industry_name']} | {industry['momentum_score']:.3f} | {industry['avg_momentum']:.3f} | {industry['momentum_std']:.3f} |"""
        
        report += f"""

## 行业评分排名

| 排名 | 行业名称 | 总分 | 基本面 | 技术面 | 估值 | 政策 | 推荐等级 |
|------|----------|------|--------|--------|------|------|----------|"""
        
        for industry in rotation_signals["industry_ranking"]:
            report += f"""
| {industry['rank']} | {industry['industry_name']} | {industry['total_score']:.1f} | {industry['fundamental_score']:.1f} | {industry['technical_score']:.1f} | {industry['valuation_score']:.1f} | {industry['policy_score']:.1f} | {industry['recommendation']} |"""
        
        report += f"""

## 综合信号排名

| 排名 | 行业名称 | 综合得分 | 行业评分 | 动量得分 |
|------|----------|----------|----------|----------|"""
        
        for industry in rotation_signals["combined_signals"][:10]:
            report += f"""
| {industry['score_rank']} | {industry['industry_name']} | {industry['combined_score']:.1f} | {industry['industry_score']:.1f} | {industry['momentum_score']:.3f} |"""
        
        report += f"""

## 行业配置建议

### 配置权重

| 行业名称 | 配置权重 | 行业评分 | 动量得分 |
|----------|----------|----------|----------|"""
        
        for industry_name, weight in portfolio_allocation["allocation"].items():
            industry = next((ind for ind in portfolio_allocation["top_industries"] 
                           if ind["industry_name"] == industry_name), None)
            if industry:
                report += f"""
| {industry_name} | {weight:.1%} | {industry['industry_score']:.1f} | {industry['momentum_score']:.3f} |"""
        
        report += f"""

### 预期表现
- **预期收益率**: {portfolio_allocation['expected_return']:.2%}
- **风险水平**: {portfolio_allocation['risk_level']}
- **调仓日期**: {portfolio_allocation['rebalance_date']}

## 投资建议

### 重点配置行业
"""
        
        for industry in portfolio_allocation["top_industries"]:
            report += f"- {industry['industry_name']}: 配置权重 {portfolio_allocation['allocation'][industry['industry_name']]:.1%}\n"
        
        report += f"""

### 风险提示
1. 关注市场周期变化，及时调整配置
2. 注意行业轮动节奏，避免追涨杀跌
3. 密切关注政策变化对行业的影响
4. 控制单一个行业配置比例，分散风险

### 操作建议
- **当前市场状态**: {portfolio_allocation['market_regime']}
- **轮动时机**: {portfolio_allocation['rotation_timing']}
- **建议操作**: {'积极配置' if portfolio_allocation['rotation_timing'] in ['strong_rotation', 'moderate_rotation'] else '谨慎配置'}

---
*报告生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
*策略版本: v1.0*
"""
        
        return report
    
    def close(self):
        """关闭数据库连接"""
        self.industry_analysis.close()


if __name__ == "__main__":
    # 测试行业轮动策略
    rotation_strategy = IndustryRotationStrategy()
    
    # 生成轮动信号
    print("=== 生成行业轮动信号 ===")
    signals = rotation_strategy.generate_rotation_signals()
    print(signals)
    
    # 生成配置建议
    print("\n=== 生成配置建议 ===")
    allocation = rotation_strategy.generate_portfolio_allocation()
    print(allocation)
    
    # 生成报告
    print("\n=== 生成行业轮动策略报告 ===")
    report = rotation_strategy.generate_rotation_report()
    print(report)
    
    rotation_strategy.close()