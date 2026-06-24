"""
mx_quota_manager.py - 妙想Skills配额管理
管理每日50次调用限制，防止超限
"""

import logging
import json
import os
from datetime import datetime, date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class MXQuotaManager:
    """妙想Skills配额管理器"""
    
    def __init__(self, quota_file: str = "database/mx_quota.json", daily_limit: int = 50):
        self.quota_file = Path(quota_file)
        self.daily_limit = daily_limit
        self.quota_data = self._load_quota()
    
    def _load_quota(self) -> dict:
        """加载配额数据"""
        if self.quota_file.exists():
            try:
                with open(self.quota_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"date": str(date.today()), "used": 0, "history": []}
    
    def _save_quota(self):
        """保存配额数据"""
        try:
            self.quota_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.quota_file, 'w') as f:
                json.dump(self.quota_data, f, indent=2)
        except Exception as e:
            logger.error(f"保存配额数据失败: {e}")
    
    def _check_date(self):
        """检查日期，新的一天重置计数"""
        today = str(date.today())
        if self.quota_data.get("date") != today:
            self.quota_data = {
                "date": today,
                "used": 0,
                "history": []
            }
            self._save_quota()
    
    def get_remaining_quota(self) -> int:
        """获取剩余配额"""
        self._check_date()
        return max(0, self.daily_limit - self.quota_data["used"])
    
    def use_quota(self, skill_name: str, query: str) -> bool:
        """
        使用一个配额
        返回: True=成功使用, False=配额不足
        """
        self._check_date()
        
        if self.quota_data["used"] >= self.daily_limit:
            logger.warning(
                f"⚠️ 妙想Skills当日调用次数已达上限 ({self.daily_limit}次)。"
                f" 剩余: 0 次。请明天再试或前往 https://dl.dfcfs.com/m/itc4 获取更多次数。"
            )
            return False
        
        self.quota_data["used"] += 1
        self.quota_data["history"].append({
            "time": datetime.now().isoformat(),
            "skill": skill_name,
            "query": query[:50]  # 只保存前50字符
        })
        
        # 限制历史记录长度
        if len(self.quota_data["history"]) > 1000:
            self.quota_data["history"] = self.quota_data["history"][-500:]
        
        self._save_quota()
        
        remaining = self.get_remaining_quota()
        logger.info(f"✅ [{skill_name}] 调用成功。今日剩余: {remaining}/{self.daily_limit}")
        return True
    
    def get_status(self) -> dict:
        """获取配额状态"""
        self._check_date()
        return {
            "date": self.quota_data["date"],
            "used": self.quota_data["used"],
            "limit": self.daily_limit,
            "remaining": self.get_remaining_quota(),
            "recent_calls": self.quota_data["history"][-5:]  # 最近5次
        }
    
    def reset_quota(self):
        """手动重置配额（仅用于测试）"""
        self.quota_data = {
            "date": str(date.today()),
            "used": 0,
            "history": []
        }
        self._save_quota()
        logger.info("✅ 配额已重置")

# 全局单例
quota_manager = MXQuotaManager()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # 测试配额管理
    print("=== 妙想Skills配额管理器测试 ===")
    print(f"初始状态: {quota_manager.get_status()}")
    
    # 模拟调用
    for i in range(5):
        success = quota_manager.use_quota("mx-data", f"测试查询{i}")
        print(f"调用{i+1}: {'成功' if success else '失败'} - 剩余: {quota_manager.get_remaining_quota()}")
    
    print(f"\n最终状态: {quota_manager.get_status()}")
