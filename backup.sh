#!/bin/bash
# backup.sh - 数据库备份脚本

set -e

BACKUP_DIR="backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_PATH="database/stock_analysis.db"
BACKUP_FILE="$BACKUP_DIR/stock_analysis_$TIMESTAMP.db"

echo "💾 开始备份数据库..."

# 创建备份目录
mkdir -p $BACKUP_DIR

# 检查数据库文件
if [ ! -f "$DB_PATH" ]; then
    echo "❌ 数据库文件不存在: $DB_PATH"
    exit 1
fi

# 执行备份
echo "📦 备份到: $BACKUP_FILE"
cp "$DB_PATH" "$BACKUP_FILE"

# 压缩备份文件
echo "🗜️ 压缩备份文件..."
gzip -c "$BACKUP_FILE" > "$BACKUP_FILE.gz"
rm "$BACKUP_FILE"

# 显示备份信息
BACKUP_SIZE=$(du -h "$BACKUP_FILE.gz" | cut -f1)
echo "✅ 备份完成: $BACKUP_FILE.gz ($BACKUP_SIZE)"

# 清理旧备份（保留最近30天）
echo "🧹 清理旧备份..."
find $BACKUP_DIR -name "*.gz" -type f -mtime +30 -delete || true

echo "📊 备份统计:"
ls -lh $BACKUP_DIR/*.gz 2>/dev/null | wc -l
echo "个备份文件"
