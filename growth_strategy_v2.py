"""
成长股策略改进版
新增：多期增长检查、行业排除、研发筛选、营收质量评分
"""

# ===== 成长股核心定义 =====

# 1. 排除的周期/传统行业
EXCLUDED_INDUSTRIES = [
    # 资源/周期
    '黄金', '铅锌', '铜', '铝', '钢铁', '煤炭', '石油', '石油开采',
    '小金属', '普钢', '特种钢', '焦炭加工', '铜', '铝',
    # 化工周期
    '农药化肥', '化工原料', '化纤', '聚氨酯', '纯碱', '氯碱', '有机硅',
    # 金融
    '证券', '银行', '保险', '多元金融', '房地产', '房产服务', '园区开发',
    # 传统制造
    '火力发电', '水力发电', '供气供热', '水务', '公路', '铁路',
    '水泥', '建材', '玻璃', '造纸',
    # 贸易
    '批发业', '商贸代理', '纺织', '纺织机械',
]

# 2. 优先行业（真正的成长赛道）
PREFERRED_INDUSTRIES = [
    '半导体', '芯片', '软件服务', '互联网', 'IT设备', '通信设备',
    '元器件', '电器仪表', '专用机械', '电气设备',
    '生物制药', '化学制药', '医疗保健', '医疗设备', '中成药',
    '食品', '白酒', '乳制品', '软饮料', '调味品',
    '汽车配件', '汽车整车', '汽车电子',
    '航空', '军工航天', '船舶',
    '新型电力', '光伏设备', '锂电池', '钠电池', '储能',
    '机器人', '人工智能', '大数据', '云计算',
    '家用电器', '家居用品', '日用化工',
]

# 3. 成长股评分标准更新
GROWTH_SCORING = {
    # ROE（年度化）
    'roe': {
        'thresholds': [
            (30, 20, 'ROE极其优异({:.1f}%)'),
            (20, 15, 'ROE非常优异({:.1f}%)'),
            (15, 10, 'ROE良好({:.1f}%)'),
        ]
    },
    # 营收增长 - 需要多期一致
    'revenue_growth': {
        'thresholds': [
            (100, 25, '营收爆发({:.1f}%)'),
            (50, 20, '营收高速增长({:.1f}%)'),
            (30, 15, '营收快速增长({:.1f}%)'),
            (20, 10, '营收稳定增长({:.1f}%)'),
        ]
    },
    # 利润增长 - 需要多期一致
    'profit_growth': {
        'thresholds': [
            (100, 25, '利润爆发({:.1f}%)'),
            (50, 20, '利润高速增长({:.1f}%)'),
            (30, 15, '利润快速增长({:.1f}%)'),
            (20, 10, '利润稳定增长({:.1f}%)'),
        ]
    },
    # 毛利率
    'gross_margin': {
        'thresholds': [
            (80, 15, '毛利率极高({:.1f}%)'),
            (60, 10, '毛利率高({:.1f}%)'),
            (40, 5, '毛利率良好({:.1f}%)'),
        ]
    },
    # 研发费用率（如果有数据）
    'rd_ratio': {
        'thresholds': [
            (15, 10, '研发投入极高({:.1f}%)'),
            (10, 5, '研发投入高({:.1f}%)'),
            (5, 0, '有研发投入({:.1f}%)'),
        ]
    },
    # 市值规模（偏好中小市值成长股）
    'market_cap': {
        'thresholds': [
            (0, 50, '小市值成长空间大'),
            (50, 200, '中等市值稳健成长'),
            (200, 500, '中大市值'),
            (500, float('inf'), '大市值，成长放缓'),
        ]
    }
}

# 4. 行业偏好分数
INDUSTRY_PREFERENCE = {
    # 高科技/高成长赛道（+15分）
    'high': ['半导体', '芯片', '软件服务', '人工智能', '机器人', '光伏设备', '锂电池', '储能', 
             '生物制药', '医疗设备', '军工航天', '汽车电子'],
    # 稳健成长赛道（+10分）
    'medium': ['元器件', '专用机械', '化学制药', '食品', '白酒', '家用电器',
               '汽车配件', '新型电力', '通信设备', 'IT设备'],
    # 一般成长（+5分）
    'low': ['中成药', '汽车整车', '家居用品', '日用化工', '软饮料', '电气设备'],
}


def check_multi_period_growth(cursor, ts_code, threshold=20, periods=3):
    """
    检查多期增长持续性
    返回: (是否持续增长, 增长季数/总季数)
    """
    cursor.execute("""
        SELECT end_date, revenue_yoy, net_profit_yoy, roe
        FROM financial_data
        WHERE ts_code = ?
          AND revenue_yoy IS NOT NULL
          AND net_profit_yoy IS NOT NULL
        ORDER BY end_date DESC
        LIMIT ?
    """, (ts_code, periods))
    
    rows = cursor.fetchall()
    
    if len(rows) < periods:
        return False, (0, len(rows)), "数据不足"
    
    # 判断增长持续性
    rev_pass = sum(1 for r in rows if r[1] and r[1] >= threshold)
    profit_pass = sum(1 for r in rows if r[2] and r[2] >= threshold)
    
    # 至少2/3的期数满足增长
    required = max(2, periods - 1)
    rev_ok = rev_pass >= required
    profit_ok = profit_pass >= required
    
    reasons = []
    if rev_ok:
        reasons.append(f"营收连续{rev_pass}/{periods}期增长>={threshold}%")
    else:
        reasons.append(f"营收仅{rev_pass}/{periods}期达标")
    
    if profit_ok:
        reasons.append(f"利润连续{profit_pass}/{periods}期增长>={threshold}%")
    else:
        reasons.append(f"利润仅{profit_pass}/{periods}期达标")
    
    return (rev_ok and profit_ok), (rev_pass, profit_pass), '; '.join(reasons)


def is_growth_industry(industry):
    """
    判断行业是否为成长赛道
    返回: (是否成长行业, 偏好分数)
    """
    if not industry:
        return False, 0
    
    # 高优先级
    for ind in INDUSTRY_PREFERENCE['high']:
        if ind in industry:
            return True, 15
    
    # 中优先级
    for ind in INDUSTRY_PREFERENCE['medium']:
        if ind in industry:
            return True, 10
    
    # 低优先级
    for ind in INDUSTRY_PREFERENCE['low']:
        if ind in industry:
            return True, 5
    
    # 未分类但也不是排除行业
    for excl in EXCLUDED_INDUSTRIES:
        if excl in industry:
            return False, -20
    
    return False, 0  # 中性行业，不排除但也不加分


def calculate_growth_score(roe, revenue_yoy, profit_yoy, gross_margin, 
                            industry_pref_score, market_cap_billion=None):
    """
    计算综合成长股评分（满分100）
    """
    score = 0
    reasons = []
    
    # 1. ROE评分 (最高20分)
    for threshold, points, desc in GROWTH_SCORING['roe']['thresholds']:
        if roe and roe >= threshold:
            score += points
            reasons.append(desc.format(roe))
            break
    
    # 2. 营收增长评分 (最高25分)
    for threshold, points, desc in GROWTH_SCORING['revenue_growth']['thresholds']:
        if revenue_yoy and revenue_yoy >= threshold:
            score += points
            reasons.append(desc.format(revenue_yoy))
            break
    
    # 3. 利润增长评分 (最高25分)
    for threshold, points, desc in GROWTH_SCORING['profit_growth']['thresholds']:
        if profit_yoy and profit_yoy >= threshold:
            score += points
            reasons.append(desc.format(profit_yoy))
            break
    
    # 4. 毛利率评分 (最高15分)
    for threshold, points, desc in GROWTH_SCORING['gross_margin']['thresholds']:
        if gross_margin and gross_margin >= threshold:
            score += points
            reasons.append(desc.format(gross_margin))
            break
    
    # 5. 行业偏好 (最高15分)
    if industry_pref_score > 0:
        score += industry_pref_score
        reasons.append(f"行业加分(+{industry_pref_score})")
    elif industry_pref_score < 0:
        score = max(0, score + industry_pref_score)  # 行业减分不减为负
    
    # 6. 市值偏好（中小市值加分，大市值减分）
    if market_cap_billion:
        for lo, hi, desc in GROWTH_SCORING['market_cap']['thresholds']:
            if lo <= market_cap_billion < hi:
                if lo == 0:  # 小市值
                    score += 5
                    reasons.append(desc)
                elif hi == float('inf'):  # 超大市值
                    score -= 5
                break
    
    return min(score, 100), reasons