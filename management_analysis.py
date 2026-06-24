"""
management_analysis.py - 管理层质量量化模块
实现管理层信息收集、评分模型建立、整合到选股流程等功能
"""
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
import re

logger = logging.getLogger(__name__)

class ManagementAnalysis:
    """管理层质量分析类"""
    
    def __init__(self, db_path: str = "database/stock_analysis.db"):
        """初始化管理层质量分析"""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # 管理层评分维度
        self.management_dimensions = {
            "education": "学历背景",
            "experience": "从业经验", 
            "tenure": "任职时长",
            "stability": "团队稳定性",
            "performance": "历史业绩",
            "shareholding": "持股情况",
            "compensation": "薪酬水平",
            "transparency": "信息披露"
        }
        
        # 学历评分标准
        self.education_scores = {
            "博士": 10,
            "硕士": 8,
            "MBA": 8,
            "本科": 6,
            "大专": 4,
            "其他": 2
        }
        
        # 经验评分标准
        self.experience_scores = {
            "10年以上": 10,
            "5-10年": 8,
            "3-5年": 6,
            "1-3年": 4,
            "1年以下": 2
        }
        
        # 任职时长评分标准
        self.tenure_scores = {
            "5年以上": 10,
            "3-5年": 8,
            "1-3年": 6,
            "1年以下": 4
        }
        
        logger.info("管理层质量分析模块初始化完成")
    
    def collect_management_info(self, stock_code: str) -> Dict:
        """收集管理层信息"""
        management_info = {
            "stock_code": stock_code,
            "board_members": [],
            "senior_executives": [],
            "compensation_info": {},
            "shareholding_info": {},
            "education_background": {},
            "career_experience": {},
            "tenure_info": {},
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 收集管理层信息
        management_info = self._get_mock_management_info(stock_code)
        
        # 添加股票代码
        management_info["stock_code"] = stock_code
        
        return management_info
    
    def _get_mock_management_info(self, stock_code: str) -> Dict:
        """获取模拟管理层信息（用于演示）"""
        mock_data = {
            "600519.SH": {
                "board_members": [
                    {
                        "name": "袁仁国",
                        "position": "董事长",
                        "age": 65,
                        "education": "本科",
                        "experience": "30年",
                        "tenure": "10年",
                        "shareholding": "5%",
                        "compensation": "500万"
                    },
                    {
                        "name": "李保芳",
                        "position": "总经理",
                        "age": 58,
                        "education": "硕士",
                        "experience": "25年",
                        "tenure": "8年",
                        "shareholding": "3%",
                        "compensation": "450万"
                    }
                ],
                "senior_executives": [
                    {
                        "name": "王莉",
                        "position": "财务总监",
                        "age": 45,
                        "education": "硕士",
                        "experience": "20年",
                        "tenure": "6年",
                        "shareholding": "1%",
                        "compensation": "300万"
                    },
                    {
                        "name": "张华",
                        "position": "技术总监",
                        "age": 40,
                        "education": "博士",
                        "experience": "15年",
                        "tenure": "4年",
                        "shareholding": "0.5%",
                        "compensation": "350万"
                    }
                ]
            },
            "000858.SZ": {
                "board_members": [
                    {
                        "name": "张裕",
                        "position": "董事长",
                        "age": 60,
                        "education": "本科",
                        "experience": "28年",
                        "tenure": "12年",
                        "shareholding": "8%",
                        "compensation": "400万"
                    },
                    {
                        "name": "王明",
                        "position": "总经理",
                        "age": 52,
                        "education": "MBA",
                        "experience": "22年",
                        "tenure": "6年",
                        "shareholding": "2%",
                        "compensation": "380万"
                    }
                ],
                "senior_executives": [
                    {
                        "name": "李强",
                        "position": "营销总监",
                        "age": 48,
                        "education": "硕士",
                        "experience": "18年",
                        "tenure": "5年",
                        "shareholding": "1.5%",
                        "compensation": "320万"
                    },
                    {
                        "name": "赵敏",
                        "position": "人事总监",
                        "age": 42,
                        "education": "本科",
                        "experience": "16年",
                        "tenure": "3年",
                        "shareholding": "0.8%",
                        "compensation": "280万"
                    }
                ]
            }
        }
        
        return mock_data.get(stock_code, {
            "board_members": [],
            "senior_executives": [],
            "compensation_info": {},
            "shareholding_info": {},
            "education_background": {},
            "career_experience": {},
            "tenure_info": {},
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    
    def score_education_background(self, management_info: Dict) -> float:
        """学历背景评分"""
        if not management_info["board_members"]:
            return 0
        
        total_score = 0
        count = 0
        
        for member in management_info["board_members"]:
            education = member.get("education", "其他")
            score = self.education_scores.get(education, 2)
            total_score += score
            count += 1
        
        # 高管团队学历背景评分
        executive_score = 0
        executive_count = 0
        
        for executive in management_info["senior_executives"]:
            education = executive.get("education", "其他")
            score = self.education_scores.get(education, 2)
            executive_score += score
            executive_count += 1
        
        # 综合评分（董事会权重60%，高管团队权重40%）
        if count > 0 and executive_count > 0:
            board_avg = total_score / count
            executive_avg = executive_score / executive_count
            final_score = board_avg * 0.6 + executive_avg * 0.4
        elif count > 0:
            final_score = total_score / count
        elif executive_count > 0:
            final_score = executive_score / executive_count
        else:
            final_score = 0
        
        return min(10, final_score)
    
    def score_career_experience(self, management_info: Dict) -> float:
        """从业经验评分"""
        if not management_info["board_members"]:
            return 0
        
        total_score = 0
        count = 0
        
        for member in management_info["board_members"]:
            experience = member.get("experience", "1年以下")
            score = self.experience_scores.get(experience, 2)
            total_score += score
            count += 1
        
        # 高管团队经验评分
        executive_score = 0
        executive_count = 0
        
        for executive in management_info["senior_executives"]:
            experience = executive.get("experience", "1年以下")
            score = self.experience_scores.get(experience, 2)
            executive_score += score
            executive_count += 1
        
        # 综合评分
        if count > 0 and executive_count > 0:
            board_avg = total_score / count
            executive_avg = executive_score / executive_count
            final_score = board_avg * 0.6 + executive_avg * 0.4
        elif count > 0:
            final_score = total_score / count
        elif executive_count > 0:
            final_score = executive_score / executive_count
        else:
            final_score = 0
        
        return min(10, final_score)
    
    def score_tenure_stability(self, management_info: Dict) -> float:
        """任职时长稳定性评分"""
        if not management_info["board_members"]:
            return 0
        
        total_score = 0
        count = 0
        
        for member in management_info["board_members"]:
            tenure = member.get("tenure", "1年以下")
            score = self.tenure_scores.get(tenure, 4)
            total_score += score
            count += 1
        
        # 高管团队任职时长评分
        executive_score = 0
        executive_count = 0
        
        for executive in management_info["senior_executives"]:
            tenure = executive.get("tenure", "1年以下")
            score = self.tenure_scores.get(tenure, 4)
            executive_score += score
            executive_count += 1
        
        # 综合评分
        if count > 0 and executive_count > 0:
            board_avg = total_score / count
            executive_avg = executive_score / executive_count
            final_score = board_avg * 0.6 + executive_avg * 0.4
        elif count > 0:
            final_score = total_score / count
        elif executive_count > 0:
            final_score = executive_score / executive_count
        else:
            final_score = 0
        
        return min(10, final_score)
    
    def score_team_stability(self, management_info: Dict) -> float:
        """团队稳定性评分"""
        if not management_info["board_members"]:
            return 0
        
        # 基于管理层平均年龄和任职时长评估稳定性
        ages = [member.get("age", 50) for member in management_info["board_members"]]
        tenures = [member.get("tenure", "3年") for member in management_info["board_members"]]
        
        # 年龄稳定性（45-65岁为最佳）
        age_stability = 0
        if ages:
            avg_age = sum(ages) / len(ages)
            if 45 <= avg_age <= 65:
                age_stability = 8
            elif 40 <= avg_age < 45 or 65 < avg_age <= 70:
                age_stability = 6
            else:
                age_stability = 4
        
        # 任职时长稳定性
        tenure_stability = 0
        if tenures:
            long_tenure_count = sum(1 for tenure in tenures if "5年" in tenure or "3-5年" in tenure)
            tenure_stability = (long_tenure_count / len(tenures)) * 10
        
        # 综合评分
        final_score = (age_stability + tenure_stability) / 2
        
        return min(10, final_score)
    
    def score_historical_performance(self, stock_code: str) -> float:
        """历史业绩评分"""
        try:
            # 获取公司历史财务数据
            self.cursor.execute("""
                SELECT net_profit, revenue, roe 
                FROM financial_data 
                WHERE ts_code = ? 
                ORDER BY end_date DESC 
                LIMIT 5
            """, (stock_code,))
            
            financial_data = self.cursor.fetchall()
            
            if not financial_data:
                return 5  # 默认中等评分
            
            # 计算业绩稳定性
            profits = [data[0] for data in financial_data if data[0] is not None]
            revenues = [data[1] for data in financial_data if data[1] is not None]
            roes = [data[2] for data in financial_data if data[2] is not None]
            
            score = 5  # 基础分
            
            # 净利润增长稳定性
            if len(profits) >= 2:
                profit_growth = []
                for i in range(len(profits)-1):
                    if profits[i+1] > 0 and profits[i] is not None:
                        growth = (profits[i] - profits[i+1]) / profits[i+1]
                        profit_growth.append(growth)
                
                if profit_growth:
                    avg_growth = sum(profit_growth) / len(profit_growth)
                    if avg_growth > 0.1:
                        score += 3
                    elif avg_growth > 0.05:
                        score += 2
                    elif avg_growth > 0:
                        score += 1
            
            # 营收增长稳定性
            if len(revenues) >= 2:
                revenue_growth = []
                for i in range(len(revenues)-1):
                    if revenues[i+1] > 0 and revenues[i] is not None:
                        growth = (revenues[i] - revenues[i+1]) / revenues[i+1]
                        revenue_growth.append(growth)
                
                if revenue_growth:
                    avg_growth = sum(revenue_growth) / len(revenue_growth)
                    if avg_growth > 0.1:
                        score += 2
                    elif avg_growth > 0.05:
                        score += 1
            
            # ROE稳定性
            if len(roes) >= 3:
                valid_roes = [r for r in roes if r is not None]
                if valid_roes:
                    avg_roe = sum(valid_roes) / len(valid_roes)
                    if avg_roe > 0.15:
                        score += 2
                    elif avg_roe > 0.1:
                        score += 1
            
            return float(min(10, score))
            
        except Exception as e:
            logger.warning(f"获取公司 {stock_code} 历史业绩失败: {e}")
            # 默认中等评分
            return 5.0
    
    def score_shareholding_alignment(self, management_info: Dict) -> float:
        """持股情况利益一致性评分"""
        if not management_info["board_members"]:
            return 0
        
        total_score = 0
        count = 0
        
        for member in management_info["board_members"]:
            shareholding = member.get("shareholding", "0%")
            score = self._score_shareholding(shareholding)
            total_score += score
            count += 1
        
        # 高管团队持股评分
        executive_score = 0
        executive_count = 0
        
        for executive in management_info["senior_executives"]:
            shareholding = executive.get("shareholding", "0%")
            score = self._score_shareholding(shareholding)
            executive_score += score
            executive_count += 1
        
        # 综合评分
        if count > 0 and executive_count > 0:
            board_avg = total_score / count
            executive_avg = executive_score / executive_count
            final_score = board_avg * 0.6 + executive_avg * 0.4
        elif count > 0:
            final_score = total_score / count
        elif executive_count > 0:
            final_score = executive_score / executive_count
        else:
            final_score = 0
        
        return min(10, final_score)
    
    def _score_shareholding(self, shareholding_str: str) -> float:
        """评分持股比例"""
        try:
            # 提取数字
            match = re.search(r'(\d+(?:\.\d+)?)%', shareholding_str)
            if match:
                percentage = float(match.group(1))
                if percentage >= 5:
                    return 10
                elif percentage >= 2:
                    return 8
                elif percentage >= 1:
                    return 6
                elif percentage >= 0.5:
                    return 4
                elif percentage > 0:
                    return 2
                else:
                    return 0
            else:
                return 0
        except Exception:
            return 0
    
    def score_compensation_alignment(self, management_info: Dict) -> float:
        """薪酬水平合理性评分"""
        if not management_info["board_members"]:
            return 0
        
        total_score = 0
        count = 0
        
        for member in management_info["board_members"]:
            compensation = member.get("compensation", "0万")
            score = self._score_compensation(compensation)
            total_score += score
            count += 1
        
        # 高管团队薪酬评分
        executive_score = 0
        executive_count = 0
        
        for executive in management_info["senior_executives"]:
            compensation = executive.get("compensation", "0万")
            score = self._score_compensation(compensation)
            executive_score += score
            executive_count += 1
        
        # 综合评分
        if count > 0 and executive_count > 0:
            board_avg = total_score / count
            executive_avg = executive_score / executive_count
            final_score = board_avg * 0.6 + executive_avg * 0.4
        elif count > 0:
            final_score = total_score / count
        elif executive_count > 0:
            final_score = executive_score / executive_count
        else:
            final_score = 0
        
        return min(10, final_score)
    
    def _score_compensation(self, compensation_str: str) -> float:
        """评分薪酬水平"""
        try:
            # 提取数字
            match = re.search(r'(\d+(?:\.\d+)?)', compensation_str)
            if match:
                amount = float(match.group(1))
                # 基于行业平均水平评分（这里简化处理）
                if amount >= 500:
                    return 8
                elif amount >= 300:
                    return 6
                elif amount >= 200:
                    return 4
                elif amount >= 100:
                    return 2
                else:
                    return 1
            else:
                return 1
        except Exception:
            return 1
    
    def score_information_transparency(self, stock_code: str) -> float:
        """信息披露透明度评分"""
        # 这里简化处理，实际应该分析公司的信息披露质量
        # 可以从年报、公告、投资者关系等方面评估
        
        base_score = 6  # 基础分
        
        try:
            # 检查公司是否有最近期的财务报告
            self.cursor.execute("""
                SELECT COUNT(*) FROM financial_data 
                WHERE ts_code = ? AND end_date >= '2026-03-01'
            """, (stock_code,))
            
            recent_reports = self.cursor.fetchone()[0]
            if recent_reports >= 3:
                base_score += 2
            elif recent_reports >= 1:
                base_score += 1
            
            # 检查公司是否有定期报告
            self.cursor.execute("""
                SELECT COUNT(*) FROM financial_data 
                WHERE ts_code = ? 
            """, (stock_code,))
            
            total_reports = self.cursor.fetchone()[0]
            if total_reports >= 5:
                base_score += 1
            
        except Exception as e:
            logger.warning(f"获取公司 {stock_code} 信息披露情况失败: {e}")
        
        return float(min(10, base_score))
    
    def score_management_quality(self, stock_code: str) -> Dict:
        """管理层质量综合评分"""
        # 收集管理层信息
        management_info = self.collect_management_info(stock_code)
        
        # 各维度评分
        scores = {
            "education_score": self.score_education_background(management_info),
            "experience_score": self.score_career_experience(management_info),
            "tenure_score": self.score_tenure_stability(management_info),
            "stability_score": self.score_team_stability(management_info),
            "performance_score": self.score_historical_performance(stock_code),
            "shareholding_score": self.score_shareholding_alignment(management_info),
            "compensation_score": self.score_compensation_alignment(management_info),
            "transparency_score": self.score_information_transparency(stock_code)
        }
        
        # 计算总分
        total_score = (
            scores["education_score"] * 0.15 +    # 学历背景 15%
            scores["experience_score"] * 0.15 +   # 从业经验 15%
            scores["tenure_score"] * 0.15 +      # 任职时长 15%
            scores["stability_score"] * 0.15 +    # 团队稳定性 15%
            scores["performance_score"] * 0.15 +  # 历史业绩 15%
            scores["shareholding_score"] * 0.1 +  # 持股情况 10%
            scores["compensation_score"] * 0.1 + # 薪酬水平 10%
            scores["transparency_score"] * 0.05   # 信息披露 5%
        )
        
        # 确定评级
        rating = self._get_management_rating(total_score)
        
        # 生成详细分析
        analysis = self._generate_management_analysis(management_info, scores, total_score)
        
        return {
            "stock_code": stock_code,
            "total_score": round(total_score, 1),
            "rating": rating,
            "scores": scores,
            "management_info": management_info,
            "analysis": analysis,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def _get_management_rating(self, total_score: float) -> str:
        """获取管理层评级"""
        if total_score >= 8.5:
            return "优秀"
        elif total_score >= 7.5:
            return "良好"
        elif total_score >= 6.5:
            return "中等"
        elif total_score >= 5.5:
            return "一般"
        else:
            return "较差"
    
    def _generate_management_analysis(self, management_info: Dict, scores: Dict, total_score: float) -> str:
        """生成管理层分析"""
        analysis = f"管理层质量综合评分: {total_score:.1f}分 ({self._get_management_rating(total_score)})\n\n"
        
        # 各维度分析
        dimensions = {
            "education_score": ("学历背景", scores["education_score"]),
            "experience_score": ("从业经验", scores["experience_score"]),
            "tenure_score": ("任职时长", scores["tenure_score"]),
            "stability_score": ("团队稳定性", scores["stability_score"]),
            "performance_score": ("历史业绩", scores["performance_score"]),
            "shareholding_score": ("持股情况", scores["shareholding_score"]),
            "compensation_score": ("薪酬水平", scores["compensation_score"]),
            "transparency_score": ("信息披露", scores["transparency_score"])
        }
        
        # 找出优势和劣势
        strengths = []
        weaknesses = []
        
        for dim_name, (dim_name_cn, score) in dimensions.items():
            if score >= 7:
                strengths.append(f"{dim_name_cn}: {score:.1f}分")
            elif score < 5:
                weaknesses.append(f"{dim_name_cn}: {score:.1f}分")
        
        analysis += "### 优势方面\n"
        if strengths:
            for strength in strengths:
                analysis += f"- {strength}\n"
        else:
            analysis += "- 无明显优势\n"
        
        analysis += "\n### 劣势方面\n"
        if weaknesses:
            for weakness in weaknesses:
                analysis += f"- {weakness}\n"
        else:
            analysis += "- 无明显劣势\n"
        
        # 建议
        analysis += "\n### 改进建议\n"
        if weaknesses:
            for weakness in weaknesses:
                analysis += f"- 加强{weakness.split(':')[0]}建设\n"
        
        analysis += "\n### 投资建议\n"
        if total_score >= 7.5:
            analysis += "- 管理层质量优秀，值得长期投资\n"
        elif total_score >= 6.5:
            analysis += "- 管理层质量良好，可以关注\n"
        elif total_score >= 5.5:
            analysis += "- 管理层质量中等，需谨慎观察\n"
        else:
            analysis += "- 管理层质量较差，建议规避\n"
        
        return analysis
    
    def get_management_ranking(self) -> List[Dict]:
        """获取管理层质量排名"""
        management_ranking = []
        
        # 获取所有股票代码
        self.cursor.execute("SELECT DISTINCT ts_code FROM financial_data LIMIT 20")
        stock_codes = [row[0] for row in self.cursor.fetchall()]
        
        for stock_code in stock_codes:
            try:
                score = self.score_management_quality(stock_code)
                management_ranking.append(score)
            except Exception as e:
                logger.warning(f"获取股票 {stock_code} 管理层评分失败: {e}")
                continue
        
        # 按总分排序
        management_ranking.sort(key=lambda x: x["total_score"], reverse=True)
        
        # 添加排名
        for i, score in enumerate(management_ranking):
            score["rank"] = i + 1
        
        return management_ranking
    
    def generate_management_report(self) -> str:
        """生成管理层质量报告"""
        management_ranking = self.get_management_ranking()
        
        report = f"""# 管理层质量分析报告

生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
分析股票数量: {len(management_ranking)}

## 管理层质量排名

| 排名 | 股票代码 | 总分 | 评级 | 学历 | 经验 | 时长 | 稳定性 | 业绩 | 持股 | 薪酬 | 透明度 |
|------|----------|------|------|------|------|------|--------|------|------|------|--------|"""
        
        for score in management_ranking[:10]:
            scores = score["scores"]
            report += f"""
| {score['rank']} | {score['stock_code']} | {score['total_score']} | {score['rating']} | {scores['education_score']:.1f} | {scores['experience_score']:.1f} | {scores['tenure_score']:.1f} | {scores['stability_score']:.1f} | {scores['performance_score']:.1f} | {scores['shareholding_score']:.1f} | {scores['compensation_score']:.1f} | {scores['transparency_score']:.1f} |"""
        
        report += f"""

## 管理层质量分布

### 评级分布
"""
        
        rating_count = {}
        for score in management_ranking:
            rating = score["rating"]
            rating_count[rating] = rating_count.get(rating, 0) + 1
        
        for rating, count in rating_count.items():
            percentage = count / len(management_ranking) * 100
            report += f"- {rating}: {count}只 ({percentage:.1f}%)\n"
        
        report += f"\n### 评分分布\n"
        
        score_ranges = {
            "8.5以上": 0,
            "7.5-8.5": 0,
            "6.5-7.5": 0,
            "5.5-6.5": 0,
            "5.5以下": 0
        }
        
        for score in management_ranking:
            total = score["total_score"]
            if total >= 8.5:
                score_ranges["8.5以上"] += 1
            elif total >= 7.5:
                score_ranges["7.5-8.5"] += 1
            elif total >= 6.5:
                score_ranges["6.5-7.5"] += 1
            elif total >= 5.5:
                score_ranges["5.5-6.5"] += 1
            else:
                score_ranges["5.5以下"] += 1
        
        for range_name, count in score_ranges.items():
            percentage = count / len(management_ranking) * 100 if management_ranking else 0
            report += f"- {range_name}: {count}只 ({percentage:.1f}%)\n"
        
        report += f"""

## 重点分析

### 管理层质量优秀的前5名股票
"""
        
        for score in management_ranking[:5]:
            report += f"- {score['stock_code']}: {score['total_score']}分 ({score['rating']})\n"
        
        report += f"\n### 管理层质量需要改进的后5名股票\n"
        
        for score in management_ranking[-5:]:
            report += f"- {score['stock_code']}: {score['total_score']}分 ({score['rating']})\n"
        
        report += f"""

## 投资建议

### 重点关注的股票
"""
        
        for score in management_ranking[:5]:
            if score["total_score"] >= 7.5:
                report += f"- {score['stock_code']}: 管理层质量优秀，值得长期投资\n"
        
        report += f"\n### 需要谨慎的股票\n"
        
        for score in management_ranking[-5:]:
            if score["total_score"] < 6.0:
                report += f"- {score['stock_code']}: 管理层质量较差，建议谨慎\n"
        
        report += f"""

## 风险提示

1. 管理层质量评估存在主观性，仅供参考
2. 管理层变动可能影响公司长期发展
3. 需要结合公司基本面综合分析
4. 定期关注管理层动态和变化

---
*报告生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
*分析版本: v1.0*
"""
        
        return report
    
    def close(self):
        """关闭数据库连接"""
        self.conn.close()


if __name__ == "__main__":
    # 测试管理层质量分析
    management_analysis = ManagementAnalysis()
    
    # 测试管理层评分
    print("=== 测试管理层质量评分 ===")
    score = management_analysis.score_management_quality("600519.SH")
    print(score)
    
    # 测试管理层排名
    print("\n=== 测试管理层质量排名 ===")
    ranking = management_analysis.get_management_ranking()
    for mgmt in ranking[:5]:
        print(f"{mgmt['rank']}. {mgmt['stock_code']}: {mgmt['total_score']}分 ({mgmt['rating']})")
    
    # 生成报告
    print("\n=== 生成管理层质量报告 ===")
    report = management_analysis.generate_management_report()
    print(report)
    
    management_analysis.close()