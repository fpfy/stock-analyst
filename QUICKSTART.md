# 快速使用指南

## 环境准备

### 1. 安装Python依赖

```bash
# 进入项目目录
cd C:\Users\fengpeng\stock_analysis_system

# 安装依赖包
pip install -r requirements.txt
```

**注意**: `talib` 可能需要额外安装步骤：

**Windows系统**:
1. 下载对应Python版本的whl文件: https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib
2. 安装: `pip install TA_Lib-0.4.XX-cp3XX-cp3XX-win_amd64.whl`

**macOS/Linux系统**:
```bash
brew install ta-lib
pip install ta-lib
```

### 2. 配置检查

系统首次运行会自动创建以下目录结构：
```
stock_analysis_system/
├── data/              # 数据缓存目录
├── database/          # SQLite数据库文件
├── reports/           # 分析报告输出目录
├── logs/              # 日志文件
└── config.py          # 配置文件（已包含默认参数）
```

## 使用方法

### 方式1: 手动运行（推荐首次使用）

```bash
# 执行完整分析流程
python main.py
```

系统将依次执行：
1. ✅ 宏观经济分析
2. ✅ 大盘技术分析
3. ✅ 综合判断大盘状态
4. ✅ 成长股选股
5. ✅ 价值股选股
6. ✅ 生成Markdown分析报告

### 方式2: 使用Hermes Cron自动化（可选）

```bash
# 创建定时任务，每个交易日收盘后15:30自动运行
hermes cron create \
  --schedule "30 15 * * 1-5" \
  --prompt "在C:/Users/fengpeng/stock_analysis_system目录下执行python main.py，并输出报告摘要" \
  --name "A股每日分析"
```

### 方式3: 模块化运行

如果您想单独测试某个模块：

```bash
# 测试宏观经济分析
python -c "from macro_market_analyzer import macro_analyzer; print(macro_analyzer.analyze_macro_economy())"

# 测试大盘技术分析
python -c "from macro_market_analyzer import market_analyzer; print(market_analyzer.analyze_market())"

# 测试成长股选股
python -c "from stock_selector import growth_selector; print(growth_selector.select_stocks('OSCILLATION', 0.5))"

# 测试价值股选股
python -c "from stock_selector import value_selector; print(value_selector.select_stocks('OSCILLATION', 0.5))"
```

## 输出说明

### 1. 控制台输出

运行时会在终端显示详细日志：
```
============================================================
A股分析及交易策略系统启动
============================================================
INFO:check_dependencies:✓ AkShare 已安装
INFO:check_dependencies:✓ Pandas 已安装
INFO:check_dependencies:✓ NumPy 已安装
INFO:init_system:数据库初始化完成
...
INFO:analyze_macro_and_market:大盘状态: 震荡市
INFO:generate_report:分析报告已生成: C:\Users\fengpeng\stock_analysis_system\reports\stock_analysis_report_2025-06-12.md
```

### 2. 分析报告

报告保存在 `reports/` 目录，命名格式：`stock_analysis_report_YYYY-MM-DD.md`

报告内容包括：
- 📊 大盘综述（宏观指标、技术面、综合判断）
- 📈 持仓建议（成长股、价值股候选及操作建议）
- ⚠️ 风险提示
- 📋 操作纪律

### 3. 数据库

所有历史数据存储在 `database/stock_analysis.db`，包括：
- 宏观经济指标
- 指数历史数据
- 股票财务数据
- 选股结果
- 交易策略记录

## 参数调整

### 修改选股条件

编辑 `config.py` 文件：

```python
# 成长股策略参数
GROWTH_STRATEGY = {
    "revenue_growth_min": 20,      # 营收增长率最小值(%)
    "profit_growth_min": 20,       # 净利润增长率最小值(%)
    "roe_min": 15,                 # ROE最小值(%)
    "gross_margin_min": 40,        # 毛利率最小值(%)
    "preferred_sectors": [
        "计算机", "电子", "通信",
        "电力设备", "医药生物",
        "食品饮料"
    ],
    "max_stocks": 10,
    "exclude_st": True
}

# 价值股策略参数
VALUE_STRATEGY = {
    "pe_max": 15,                  # PE最大值
    "pb_max": 2.0,                 # PB最大值
    "dividend_yield_min": 3.0,     # 股息率最小值(%)
    "roe_min": 10,                 # ROE最小值(%)
    "debt_ratio_max": 60,          # 负债率最大值(%)
    "preferred_sectors": [
        "银行", "房地产", "公用事业",
        "交通运输", "钢铁", "煤炭"
    ],
    "max_stocks": 10,
    "exclude_st": True
}
```

### 修改仓位配比

```python
# 大盘状态定义
MARKET_STATUS = {
    "BULL": {
        "name": "牛市",
        "growth_ratio": 0.70,  # 成长股占比70%
        "value_ratio": 0.30,   # 价值股占比30%
        "risk_level": "中高"
    },
    "OSCILLATION": {
        "name": "震荡市",
        "growth_ratio": 0.50,
        "value_ratio": 0.50,
        "risk_level": "中"
    },
    "BEAR": {
        "name": "熊市",
        "growth_ratio": 0.30,
        "value_ratio": 0.70,
        "risk_level": "中低"
    }
}
```

### 修改风险控制参数

```python
# 风险控制参数
RISK_CONTROL = {
    "max_single_position": 0.15,    # 单只股票最大仓位(15%)
    "stop_loss_ratio": -0.08,       # 止损线(-8%)
    "max_drawdown": -0.10,          # 最大回撤(-10%)
    "rebalance_frequency": "weekly"  # 再平衡频率
}
```

## 常见问题

### Q1: 首次运行报错 "无数据"

**解决方案**: 系统需要从AkShare获取数据，首次运行需要时间，请耐心等待。

如果仍然报错，手动获取数据：
```bash
python -c "
from data_fetcher import data_fetcher
data_fetcher.fetch_macro_indicator('PMI')
data_fetcher.fetch_stock_basic()
print('数据获取完成')
"
```

### Q2: AkShare数据获取失败

**可能原因**:
1. 网络连接问题
2. AkShare接口更新
3. 数据源临时不可用

**解决方案**:
- 检查网络连接
- 更新AkShare: `pip install --upgrade akshare`
- 查看AkShare文档: https://akshare.akfamily.xyz/

### Q3: 选股结果为空

**可能原因**:
1. 筛选条件过于严格
2. 当前市场环境下符合条件的股票较少
3. 数据不完整

**解决方案**:
- 放宽筛选条件（修改config.py）
- 检查日志文件 `logs/stock_analysis.log` 了解详细原因
- 确保财务数据已获取

### Q4: 如何查看历史选股记录

**方法1**: 查看数据库
```bash
python -c "
import database as db
results = db.db.execute_query('SELECT * FROM stock_selection ORDER BY selection_date DESC LIMIT 10')
for r in results:
    print(r)
"
```

**方法2**: 查看历史报告
```bash
ls reports/
```

## 进阶使用

### 1. 添加自定义指标

在 `config.py` 中添加新的权重配置：

```python
# 自定义指标权重
CUSTOM_INDICATORS_WEIGHT = {
    "INDICATOR1": 0.30,
    "INDICATOR2": 0.40,
    "INDICATOR3": 0.30
}
```

### 2. 集成其他数据源

修改 `data_fetcher.py`，添加新的数据源接口：

```python
def fetch_from_custom_source(self):
    # 实现自定义数据源
    pass
```

### 3. 添加邮件/微信通知

在 `main.py` 的 `generate_report()` 函数后添加通知逻辑：

```python
def send_notification(report_path):
    # 实现邮件或微信通知
    pass
```

## 技术支持

如遇到问题，请检查：
1. 日志文件: `logs/stock_analysis.log`
2. AkShare文档: https://akshare.akfamily.xyz/
3. Python版本: 建议3.8+

## 更新日志

### v1.0.0 (2025-06-12)
- ✅ 宏观经济分析模块
- ✅ 大盘技术分析模块
- ✅ 成长股选股策略
- ✅ 价值股选股策略
- ✅ 仓位自动配比
- ✅ Markdown报告生成
- ✅ SQLite数据库存储
- ✅ 完整的日志系统

---

**免责声明**: 本系统仅供研究参考，不构成投资建议。股市有风险，投资需谨慎。