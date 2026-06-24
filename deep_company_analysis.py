"""
深度公司分析模块
补充四层分析框架：行业研究、商业模式、同行业对比、估值-成长匹配
"""
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class DeepCompanyAnalyzer:
    """深度公司分析器：基于财务数据推导行业地位、商业模式、竞争格局、估值匹配度"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        self.cursor = db_manager.get_cursor()
    
    def _safe_float(self, val):
        """安全转浮点"""
        try:
            if val is None or pd.isna(val):
                return None
            return float(val)
        except (ValueError, TypeError):
            return None
    
    def analyze_industry(self, ts_code: str) -> Dict:
        """
        行业研究层分析
        基于同行业对比，分析公司在行业内的相对地位
        """
        try:
            # 获取公司基本信息
            self.cursor.execute("""
                SELECT s.ts_code, s.name, s.industry, s.list_date, s.is_st,
                       f.roe, f.revenue_yoy, f.net_profit_yoy, f.gross_margin, f.net_margin,
                       f.debt_ratio, f.total_assets, f.operating_cf
                FROM stock_basic s
                LEFT JOIN financial_data f ON s.ts_code = f.ts_code
                WHERE s.ts_code = ? AND f.end_date = (SELECT MAX(end_date) FROM financial_data WHERE ts_code = ?)
            """, (ts_code, ts_code))
            company = self.cursor.fetchone()
            
            if not company:
                return {'status': '数据不足', 'score': 50}
            
            cols = [d[0] for d in self.cursor.description]
            company = dict(zip(cols, company))
            industry = company.get('industry', '')
            
            # 获取同行业公司数据
            self.cursor.execute("""
                SELECT s.ts_code, s.name, s.industry,
                       f.roe, f.revenue_yoy, f.net_profit_yoy, f.gross_margin, f.net_margin,
                       f.debt_ratio, f.total_assets, f.operating_cf,
                       v.pe, v.pb, v.dv_ttm, v.total_mv, v.close
                FROM stock_basic s
                LEFT JOIN financial_data f ON s.ts_code = f.ts_code AND f.end_date = (SELECT MAX(end_date) FROM financial_data WHERE ts_code = s.ts_code)
                LEFT JOIN valuation_data v ON s.ts_code = v.ts_code AND v.trade_date = (SELECT MAX(trade_date) FROM valuation_data WHERE ts_code = s.ts_code)
                WHERE s.industry = ? AND s.is_st = 0 AND s.list_date < DATE('now', '-3 years')
                AND f.roe IS NOT NULL AND f.revenue_yoy IS NOT NULL
            """, (industry,))
            
            peers = self.cursor.fetchall()
            if not peers or len(peers) < 3:
                return {'status': '同行业对比样本不足', 'score': 50, 'industry': industry}
            
            peer_cols = [d[0] for d in self.cursor.description]
            peers_df = pd.DataFrame(peers, columns=peer_cols)
            
            # 计算行业分位排名
            def percentile_rank(series, val):
                valid = series.dropna()
                if len(valid) == 0:
                    return 50
                return (valid <= val).mean() * 100
            
            roe_pct = percentile_rank(peers_df['roe'], company.get('roe'))
            rev_pct = percentile_rank(peers_df['revenue_yoy'], company.get('revenue_yoy'))
            profit_pct = percentile_rank(peers_df['net_profit_yoy'], company.get('net_profit_yoy'))
            margin_pct = percentile_rank(peers_df['gross_margin'], company.get('gross_margin'))
            
            # 规模排名（总资产）
            asset_rank = 0
            if company.get('total_assets'):
                valid_assets = peers_df['total_assets'].dropna()
                if len(valid_assets) > 0:
                    asset_rank = (valid_assets <= company['total_assets']).mean() * 100
            
            # 行业景气度判断
            avg_rev_yoy = peers_df['revenue_yoy'].mean()
            industry_status = "上行" if avg_rev_yoy > 10 else "稳定" if avg_rev_yoy > 0 else "下行"
            
            # 公司行业地位评分
            industry_score = np.mean([roe_pct, rev_pct, profit_pct, margin_pct, asset_rank])
            
            # 行业地位描述
            if industry_score >= 75:
                position = "龙头/领先"
            elif industry_score >= 60:
                position = "前列"
            elif industry_score >= 40:
                position = "中等"
            else:
                position = "落后"
            
            return {
                'status': '完成',
                'industry': industry,
                'industry_status': industry_status,
                'peer_count': len(peers),
                'company_position': position,
                'industry_score': round(industry_score, 1),
                'roe_percentile': round(roe_pct, 0),
                'revenue_percentile': round(rev_pct, 0),
                'profit_percentile': round(profit_pct, 0),
                'margin_percentile': round(margin_pct, 0),
                'asset_rank_percentile': round(asset_rank, 0),
                'industry_avg_revenue_yoy': round(avg_rev_yoy, 1)
            }
            
        except Exception as e:
            logger.error(f"行业分析失败 {ts_code}: {e}")
            return {'status': '分析失败', 'score': 50}
    
    def analyze_business_model(self, ts_code: str) -> Dict:
        """
        商业模式分析
        基于财务数据推导：收入结构趋势、盈利质量、上下游议价能力、经营现金流健康度
        """
        try:
            # 获取近4期财务数据（年度）
            self.cursor.execute("""
                SELECT end_date, revenue, revenue_yoy, net_profit, net_profit_yoy,
                       gross_margin, net_margin, roe, roa, debt_ratio,
                       operating_cf, total_assets, total_liab,
                       current_assets, current_liab, eps, bps
                FROM financial_data
                WHERE ts_code = ?
                ORDER BY end_date DESC
                LIMIT 4
            """, (ts_code,))
            
            rows = self.cursor.fetchall()
            if not rows:
                return {'status': '数据不足', 'score': 50}
            
            cols = [d[0] for d in self.cursor.description]
            df = pd.DataFrame(rows, columns=cols)
            
            # 收入结构稳定性（营收增速标准差）
            rev_yoy_std = df['revenue_yoy'].std() if len(df) > 1 else None
            
            # 盈利质量（净利润/经营现金流匹配度）
            latest = df.iloc[0]
            profit_cf_ratio = None
            if latest['net_profit'] and latest['operating_cf'] and latest['net_profit'] != 0:
                profit_cf_ratio = latest['operating_cf'] / latest['net_profit']
            
            # 上下游议价能力（应付/应收周转简化）
            # 用资产负债率 + 流动比率间接判断
            debt_ratio = latest.get('debt_ratio')
            current_ratio = None
            if latest.get('current_assets') and latest.get('current_liab'):
                current_ratio = latest['current_assets'] / latest['current_liab']
            
            # 经营现金流健康度
            cf_health = None
            if latest.get('operating_cf'):
                cf_health = 1 if latest['operating_cf'] > 0 else -1
            
            # 盈利趋势
            profit_trend = "向好" if len(df) >= 2 and df['net_profit_yoy'].iloc[0] > df['net_profit_yoy'].iloc[1] else "恶化" if len(df) >= 2 and df['net_profit_yoy'].iloc[0] < df['net_profit_yoy'].iloc[1] else "平稳"
            
            # 商业模式评分
            score_items = []
            if profit_cf_ratio is not None:
                score_items.append(100 if profit_cf_ratio > 0.8 else 60 if profit_cf_ratio > 0.3 else 30)
            if rev_yoy_std is not None:
                score_items.append(100 if rev_yoy_std < 5 else 60 if rev_yoy_std < 15 else 30)
            if cf_health is not None:
                score_items.append(80 if cf_health > 0 else 40)
            if debt_ratio is not None:
                score_items.append(100 if debt_ratio < 0.4 else 60 if debt_ratio < 0.6 else 40)
            
            biz_score = np.mean(score_items) if score_items else 50
            
            return {
                'status': '完成',
                'biz_score': round(biz_score, 1),
                'profit_cf_ratio': round(profit_cf_ratio, 2) if profit_cf_ratio else None,
                'revenue_stability_std': round(rev_yoy_std, 1) if rev_yoy_std else None,
                'cf_health': cf_health,
                'debt_ratio': round(debt_ratio, 2) if debt_ratio else None,
                'current_ratio': round(current_ratio, 2) if current_ratio else None,
                'profit_trend': profit_trend,
                'latest_revenue_yoy': round(latest['revenue_yoy'], 1) if latest['revenue_yoy'] else None,
                'latest_net_profit_yoy': round(latest['net_profit_yoy'], 1) if latest['net_profit_yoy'] else None,
                'latest_gross_margin': round(latest['gross_margin'], 1) if latest['gross_margin'] else None,
                'quarters_analyzed': len(df)
            }
            
        except Exception as e:
            logger.error(f"商业模式分析失败 {ts_code}: {e}")
            return {'status': '分析失败', 'score': 50}
    
    def analyze_peer_comparison(self, ts_code: str) -> Dict:
        """
        同行业对比分析
        PE/PB分位、ROE排名、营收增速排名、综合竞争力评分
        """
        try:
            # 获取公司行业
            self.cursor.execute("SELECT industry FROM stock_basic WHERE ts_code = ?", (ts_code,))
            row = self.cursor.fetchone()
            if not row:
                return {'status': '数据不足', 'score': 50}
            industry = row[0]
            
            # 获取同行业所有公司的估值+财务数据（最新）
            self.cursor.execute("""
                SELECT s.ts_code, s.name, s.industry,
                       f.roe, f.revenue_yoy, f.net_profit_yoy, f.gross_margin,
                       f.debt_ratio, f.eps, f.bps,
                       v.pe, v.pb, v.dv_ttm, v.total_mv, v.close
                FROM stock_basic s
                LEFT JOIN financial_data f ON s.ts_code = f.ts_code
                    AND f.end_date = (SELECT MAX(end_date) FROM financial_data WHERE ts_code = s.ts_code)
                LEFT JOIN valuation_data v ON s.ts_code = v.ts_code
                    AND v.trade_date = (SELECT MAX(trade_date) FROM valuation_data WHERE ts_code = s.ts_code)
                WHERE s.industry = ? AND s.is_st = 0 AND s.list_date < DATE('now', '-3 years')
            """, (industry,))
            
            rows = self.cursor.fetchall()
            if not rows or len(rows) < 3:
                return {'status': '同行业对比样本不足', 'score': 50, 'industry': industry}
            
            cols = [d[0] for d in self.cursor.description]
            df = pd.DataFrame(rows, columns=cols)
            
            # 目标公司数据
            company_row = df[df['ts_code'] == ts_code]
            if company_row.empty:
                return {'status': '公司不在行业中', 'score': 50}
            company = company_row.iloc[0]
            
            # 计算各指标行业内分位（越低越好：PE/PB/负债率；越高越好：ROE/营收/利润）
            def calc_percentile(col, val, ascending=True):
                valid = df[col].dropna()
                if len(valid) == 0 or val is None or pd.isna(val):
                    return 50
                if ascending:
                    return (valid <= val).mean() * 100
                else:
                    return (valid >= val).mean() * 100
            
            pe_pct = calc_percentile('pe', company.get('pe'), ascending=True)  # PE越低越好
            pb_pct = calc_percentile('pb', company.get('pb'), ascending=True)
            roe_pct = calc_percentile('roe', company.get('roe'), ascending=False)
            rev_pct = calc_percentile('revenue_yoy', company.get('revenue_yoy'), ascending=False)
            profit_pct = calc_percentile('net_profit_yoy', company.get('net_profit_yoy'), ascending=False)
            margin_pct = calc_percentile('gross_margin', company.get('gross_margin'), ascending=False)
            debt_pct = calc_percentile('debt_ratio', company.get('debt_ratio'), ascending=True)
            
            # 综合竞争力评分（估值分 + 成长分 + 质量分）
            valuation_score = 100 - (pe_pct + pb_pct) / 2  # 估值越低分越高
            growth_score = (rev_pct + profit_pct) / 2
            quality_score = (roe_pct + margin_pct + (100 - debt_pct)) / 3
            competitive_score = (valuation_score + growth_score + quality_score) / 3
            
            # 估值-成长匹配判断（PEG）
            peg = None
            pe = self._safe_float(company.get('pe'))
            net_profit_yoy = self._safe_float(company.get('net_profit_yoy'))
            if pe and net_profit_yoy and net_profit_yoy > 0:
                peg = pe / net_profit_yoy
            
            # 估值溢价/折价
            avg_pe = df['pe'].mean()
            valuation_premium = None
            if avg_pe and pe:
                valuation_premium = (pe / avg_pe - 1) * 100
            
            return {
                'status': '完成',
                'industry': industry,
                'peer_count': len(df),
                'pe_percentile': round(pe_pct, 0),
                'pb_percentile': round(pb_pct, 0),
                'roe_percentile': round(roe_pct, 0),
                'revenue_percentile': round(rev_pct, 0),
                'profit_percentile': round(profit_pct, 0),
                'margin_percentile': round(margin_pct, 0),
                'debt_percentile': round(debt_pct, 0),
                'competitive_score': round(competitive_score, 1),
                'peg': round(peg, 2) if peg else None,
                'industry_avg_pe': round(avg_pe, 1) if avg_pe else None,
                'valuation_premium_pct': round(valuation_premium, 1) if valuation_premium else None,
                'pe': pe,
                'pb': self._safe_float(company.get('pb')),
                'roe': self._safe_float(company.get('roe')),
                'revenue_yoy': self._safe_float(company.get('revenue_yoy')),
                'net_profit_yoy': self._safe_float(company.get('net_profit_yoy')),
                'gross_margin': self._safe_float(company.get('gross_margin')),
                'total_mv': self._safe_float(company.get('total_mv'))
            }
            
        except Exception as e:
            logger.error(f"同行业对比失败 {ts_code}: {e}")
            return {'status': '分析失败', 'score': 50}
    
    def analyze_growth_valuation_match(self, ts_code: str) -> Dict:
        """
        估值-成长匹配分析
        PEG、合理估值区间、成长性溢价/折价判断
        """
        try:
            # 获取最新估值数据
            self.cursor.execute("""
                SELECT pe, pb, dv_ttm, total_mv, close, trade_date
                FROM valuation_data
                WHERE ts_code = ?
                ORDER BY trade_date DESC LIMIT 1
            """, (ts_code,))
            val_row = self.cursor.fetchone()
            if not val_row:
                return {'status': '估值数据不足', 'score': 50}
            
            pe, pb, dv_ttm, total_mv, close, val_date = val_row
            
            # 获取近4期净利润增速
            self.cursor.execute("""
                SELECT end_date, net_profit_yoy, revenue_yoy, roe
                FROM financial_data
                WHERE ts_code = ?
                ORDER BY end_date DESC LIMIT 4
            """, (ts_code,))
            fin_rows = self.cursor.fetchall()
            if not fin_rows:
                return {'status': '财务数据不足', 'score': 50}
            
            fin_df = pd.DataFrame(fin_rows, columns=['end_date', 'net_profit_yoy', 'revenue_yoy', 'roe'])
            
            # PEG计算
            avg_profit_yoy = fin_df['net_profit_yoy'].mean()
            peg = None
            if pe and avg_profit_yoy and avg_profit_yoy > 0:
                peg = pe / avg_profit_yoy
            
            # 合理PE区间（基于成长速度）
            reasonable_pe_min = max(8, avg_profit_yoy * 0.5) if avg_profit_yoy and avg_profit_yoy > 0 else 8
            reasonable_pe_max = min(60, avg_profit_yoy * 1.5) if avg_profit_yoy and avg_profit_yoy > 0 else 30
            
            # 估值状态判断
            if pe is None or pd.isna(pe):
                valuation_status = "PE缺失（亏损或特殊估值）"
                valuation_score = 50
            elif peg and peg < 0.8:
                valuation_status = "低估（PEG<0.8）"
                valuation_score = 85
            elif peg and peg < 1.0:
                valuation_status = "合理偏低（PEG<1.0）"
                valuation_score = 75
            elif peg and peg < 1.5:
                valuation_status = "合理（PEG<1.5）"
                valuation_score = 60
            elif peg and peg < 2.0:
                valuation_status = "偏高（PEG<2.0）"
                valuation_score = 40
            else:
                valuation_status = "高估（PEG>=2.0）"
                valuation_score = 30
            
            # 修正：亏损股PE无效，改用PB+市销率
            latest_profit = fin_df.iloc[0]['net_profit_yoy']
            if latest_profit is None or latest_profit < 0:
                valuation_status = "亏损股，PE失效，改用PB+营收增速"
                if pb:
                    if pb < 3:
                        valuation_score = 70
                        valuation_status += "（PB<3，尚可接受）"
                    elif pb < 5:
                        valuation_score = 55
                        valuation_status += "（PB 3-5，中性）"
                    else:
                        valuation_score = 35
                        valuation_status += "（PB>5，偏高）"
                peg = None
            
            # 股息率加分
            if dv_ttm and dv_ttm > 3:
                valuation_score = min(100, valuation_score + 10)
            
            return {
                'status': '完成',
                'pe': pe,
                'pb': pb,
                'peg': round(peg, 2) if peg else None,
                'reasonable_pe_range': f"{reasonable_pe_min:.0f}-{reasonable_pe_max:.0f}",
                'avg_profit_yoy_4q': round(avg_profit_yoy, 1) if avg_profit_yoy else None,
                'valuation_status': valuation_status,
                'valuation_score': round(valuation_score, 1),
                'close': close,
                'total_mv': total_mv,
                'val_date': val_date,
                'is_loss_making': latest_profit is not None and latest_profit < 0
            }
            
        except Exception as e:
            logger.error(f"估值-成长匹配分析失败 {ts_code}: {e}")
            return {'status': '分析失败', 'score': 50}
    
    def full_analysis(self, ts_code: str) -> Dict:
        """完整四层分析"""
        industry = self.analyze_industry(ts_code)
        business = self.analyze_business_model(ts_code)
        peer = self.analyze_peer_comparison(ts_code)
        valuation = self.analyze_growth_valuation_match(ts_code)
        
        # 综合评分（四维等权平均，每个维度满分100）
        raw_scores = []
        if industry.get('industry_score'):
            raw_scores.append(industry['industry_score'])
        if business.get('biz_score'):
            raw_scores.append(business['biz_score'])
        if peer.get('competitive_score'):
            raw_scores.append(peer['competitive_score'])
        if valuation.get('valuation_score'):
            raw_scores.append(valuation['valuation_score'])
        
        overall = float(np.mean(raw_scores)) if raw_scores else 50.0
        
        return {
            'ts_code': ts_code,
            'analysis_date': datetime.now().strftime('%Y-%m-%d'),
            'status': '完成',
            'overall_score': round(overall, 1),
            'industry_analysis': industry,
            'business_model': business,
            'peer_comparison': peer,
            'valuation_match': valuation
        }
    
    def batch_analyze(self, ts_codes: List[str]) -> List[Dict]:
        """批量分析"""
        results = []
        for code in ts_codes:
            try:
                result = self.full_analysis(code)
                results.append(result)
            except Exception as e:
                logger.error(f"分析失败 {code}: {e}")
                results.append({'ts_code': code, 'status': '失败', 'error': str(e)})
        return results
