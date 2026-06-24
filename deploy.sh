#!/bin/bash
# deploy.sh - 生产环境部署脚本

set -e

echo "🚀 开始部署股票分析系统..."

# 检查环境
echo "📋 检查部署环境..."
command -v docker >/dev/null 2>&1 || { echo "❌ Docker未安装，请先安装Docker"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "❌ Docker Compose未安装，请先安装Docker Compose"; exit 1; }

# 创建必要目录
echo "📁 创建目录结构..."
mkdir -p database logs reports data backups

# 检查环境变量
if [ ! -f .env ]; then
    echo "⚠️ .env文件不存在，从.env.example复制..."
    cp .env.example .env
    echo "⚠️ 请编辑.env文件，配置必要的环境变量（特别是TUSHARE_TOKEN）"
fi

# 构建Docker镜像
echo "🔨 构建Docker镜像..."
docker-compose build

# 停止旧容器
echo "🛑 停止旧容器..."
docker-compose down || true

# 启动服务
echo "▶️ 启动服务..."
docker-compose up -d

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 10

# 健康检查
echo "🏥 执行健康检查..."
if docker exec stock-analysis-system python -c "import sqlite3; sqlite3.connect('database/stock_analysis.db')"; then
    echo "✅ 健康检查通过"
else
    echo "❌ 健康检查失败"
    docker-compose logs
    exit 1
fi

# 显示服务状态
echo "📊 服务状态："
docker-compose ps

echo ""
echo "🎉 部署完成！"
echo ""
echo "访问方式："
echo "  - 查看日志: docker-compose logs -f"
echo "  - 停止服务: docker-compose down"
echo "  - 重启服务: docker-compose restart"
echo "  - 查看状态: docker-compose ps"
echo ""
echo "⚠️ 请确保已配置TUSHARE_TOKEN环境变量"
