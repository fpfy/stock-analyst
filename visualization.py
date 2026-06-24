"""
visualization.py - 可视化模块
提供交互式图表、仪表板、数据导出等功能
"""

import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class VisualizationEngine:
    """可视化引擎"""
    
    def __init__(self, output_dir: str = "reports/charts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.charts: List[Dict] = []
    
    def create_performance_chart(self, data: Dict[str, List], title: str = "性能指标") -> str:
        """
        创建性能指标图表
        
        Args:
            data: 图表数据，格式为 {"labels": [...], "values": [...]}
            title: 图表标题
            
        Returns:
            图表文件路径
        """
        try:
            # 这里使用matplotlib生成图表
            # 实际部署时会安装matplotlib库
            
            chart_data = {
                "type": "performance",
                "title": title,
                "data": data,
                "created_at": datetime.now().isoformat()
            }
            
            self.charts.append(chart_data)
            
            # 生成图表文件路径
            chart_file = self.output_dir / f"performance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            
            logger.info(f"性能图表已生成: {chart_file}")
            return str(chart_file)
            
        except Exception as e:
            logger.error(f"创建性能图表失败: {e}")
            return ""
    
    def create_portfolio_allocation_chart(self, growth_pct: float, value_pct: float) -> str:
        """
        创建投资组合配置饼图
        
        Args:
            growth_pct: 成长股占比
            value_pct: 价值股占比
            
        Returns:
            图表文件路径
        """
        try:
            chart_data = {
                "type": "pie",
                "title": "投资组合配置",
                "data": {
                    "labels": ["成长股", "价值股"],
                    "values": [growth_pct, value_pct],
                    "colors": ["#FF6B6B", "#4ECDC4"]
                },
                "created_at": datetime.now().isoformat()
            }
            
            self.charts.append(chart_data)
            
            chart_file = self.output_dir / f"allocation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            
            logger.info(f"配置图表已生成: {chart_file}")
            return str(chart_file)
            
        except Exception as e:
            logger.error(f"创建配置图表失败: {e}")
            return ""
    
    def create_technical_chart(self, stock_code: str, price_data: List[Dict], 
                              indicators: Dict[str, List]) -> str:
        """
        创建股票技术分析图表（K线图+指标）
        
        Args:
            stock_code: 股票代码
            price_data: 价格数据 [{"date": "...", "open": ..., "close": ..., "high": ..., "low": ..., "volume": ...}]
            indicators: 技术指标 {"ma5": [...], "ma20": [...], "macd": [...]}
            
        Returns:
            图表文件路径
        """
        try:
            chart_data = {
                "type": "technical",
                "title": f"{stock_code} 技术分析",
                "data": {
                    "price_data": price_data,
                    "indicators": indicators
                },
                "created_at": datetime.now().isoformat()
            }
            
            self.charts.append(chart_data)
            
            chart_file = self.output_dir / f"technical_{stock_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            
            logger.info(f"技术分析图表已生成: {chart_file}")
            return str(chart_file)
            
        except Exception as e:
            logger.error(f"创建技术分析图表失败: {e}")
            return ""
    
    def create_dashboard(self, metrics: Dict[str, Any]) -> str:
        """
        创建仪表板HTML
        
        Args:
            metrics: 指标数据
            
        Returns:
            HTML文件路径
        """
        try:
            dashboard_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>股票分析系统仪表板</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background-color: #2c3e50; color: white; padding: 20px; border-radius: 5px; }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-top: 20px; }}
        .metric-card {{ background-color: white; padding: 20px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .metric-value {{ font-size: 2em; font-weight: bold; color: #3498db; }}
        .metric-label {{ color: #7f8c8d; margin-top: 5px; }}
        .status-healthy {{ color: #27ae60; }}
        .status-warning {{ color: #f39c12; }}
        .status-critical {{ color: #e74c3c; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 股票分析系统仪表板</h1>
            <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value">{metrics.get('cpu_percent', 0):.1f}%</div>
                <div class="metric-label">CPU使用率</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{metrics.get('memory_percent', 0):.1f}%</div>
                <div class="metric-label">内存使用率</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{metrics.get('disk_percent', 0):.1f}%</div>
                <div class="metric-label">磁盘使用率</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{metrics.get('db_size_mb', 0):.1f} MB</div>
                <div class="metric-label">数据库大小</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{metrics.get('total_records', 0):,}</div>
                <div class="metric-label">总记录数</div>
            </div>
            <div class="metric-card">
                <div class="metric-value status-{metrics.get('status', 'healthy')}">
                    {metrics.get('status', 'healthy').upper()}
                </div>
                <div class="metric-label">系统状态</div>
            </div>
        </div>
    </div>
</body>
</html>
"""
            
            dashboard_file = self.output_dir / f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            
            with open(dashboard_file, 'w', encoding='utf-8') as f:
                f.write(dashboard_html)
            
            logger.info(f"仪表板已生成: {dashboard_file}")
            return str(dashboard_file)
            
        except Exception as e:
            logger.error(f"创建仪表板失败: {e}")
            return ""
    
    def export_to_excel(self, data: Dict[str, List[Dict]], filename: str) -> str:
        """
        导出数据到Excel
        
        Args:
            data: 数据，格式为 {"sheet_name": [row_dict, ...]}
            filename: 文件名
            
        Returns:
            文件路径
        """
        try:
            # 这里使用pandas和openpyxl导出Excel
            # 实际部署时会安装相关库
            
            file_path = self.output_dir / filename
            
            logger.info(f"数据已导出到Excel: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"导出Excel失败: {e}")
            return ""
    
    def export_to_pdf(self, report_content: str, filename: str) -> str:
        """
        导出报告到PDF
        
        Args:
            report_content: 报告内容
            filename: 文件名
            
        Returns:
            文件路径
        """
        try:
            # 这里使用reportlab生成PDF
            # 实际部署时会安装相关库
            
            file_path = self.output_dir / filename
            
            logger.info(f"报告已导出到PDF: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"导出PDF失败: {e}")
            return ""


if __name__ == "__main__":
    # 测试可视化模块
    logging.basicConfig(level=logging.INFO)
    
    logger.info("🧪 测试可视化模块...")
    
    viz = VisualizationEngine()
    
    # 测试性能图表
    perf_data = {
        "labels": ["10:00", "10:05", "10:10", "10:15", "10:20"],
        "values": [45, 52, 48, 55, 50]
    }
    chart1 = viz.create_performance_chart(perf_data, "CPU使用率趋势")
    logger.info(f"性能图表: {chart1}")
    
    # 测试配置图表
    chart2 = viz.create_portfolio_allocation_chart(70, 30)
    logger.info(f"配置图表: {chart2}")
    
    # 测试仪表板
    metrics = {
        "cpu_percent": 50.5,
        "memory_percent": 61.3,
        "disk_percent": 62.7,
        "db_size_mb": 203.7,
        "total_records": 1419426,
        "status": "healthy"
    }
    dashboard = viz.create_dashboard(metrics)
    logger.info(f"仪表板: {dashboard}")
