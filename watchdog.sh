#!/bin/bash
# watchdog.sh - 系统监控守护进程

set -e

echo "🐕 启动系统监控守护进程..."

# 配置
CHECK_INTERVAL=300  # 检查间隔（秒）
BACKUP_INTERVAL=86400  # 备份间隔（秒）
MAX_RETRIES=3
RETRY_DELAY=10

last_backup=$(date +%s)
retry_count=0

while true; do
    current_time=$(date +%s)
    
    # 健康检查
    echo "[$(date)] 执行健康检查..."
    
    if docker exec stock-analysis-system python -c "
import sys
sys.path.append('.')
from system_monitor import SystemMonitor
monitor = SystemMonitor()
health = monitor.check_health()
if health['status'] == 'critical':
    print('CRITICAL')
    sys.exit(1)
elif health['status'] == 'warning':
    print('WARNING')
    sys.exit(0)
else:
    print('HEALTHY')
    sys.exit(0)
" 2>/dev/null; then
        health_status=$?
        retry_count=0
        
        case $health_status in
            0)
                echo "[$(date)] ✅ 系统健康"
                ;;
            1)
                echo "[$(date)] 🚨 系统状态异常，需要人工干预"
                # TODO: 发送告警通知
                ;;
        esac
    else
        retry_count=$((retry_count + 1))
        echo "[$(date)] ⚠️ 健康检查失败 (尝试 $retry_count/$MAX_RETRIES)"
        
        if [ $retry_count -ge $MAX_RETRIES ]; then
            echo "[$(date)] ❌ 达到最大重试次数，尝试重启服务..."
            docker-compose restart stock-analysis
            retry_count=0
            sleep 30
        fi
    fi
    
    # 定时备份
    if [ $((current_time - last_backup)) -ge $BACKUP_INTERVAL ]; then
        echo "[$(date)] 💾 执行定时备份..."
        ./backup.sh
        last_backup=$current_time
    fi
    
    # 等待下一次检查
    sleep $CHECK_INTERVAL
done
