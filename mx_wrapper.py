"""
mx_wrapper.py - 妙想Skills统一调用接口
提供带配额管理的统一调用入口，防止超出每日50次限制
"""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Any

from mx_quota_manager import quota_manager

logger = logging.getLogger(__name__)

# 妙想Skills基础目录
MX_SKILLS_DIR = Path.home() / "AppData" / "Local" / "hermes" / "profiles" / "stock-analyst" / "skills"

# 各技能脚本路径
SKILL_SCRIPTS = {
    "mx-data": MX_SKILLS_DIR / "mx-data" / "mx_data.py",
    "mx-search": MX_SKILLS_DIR / "mx-search" / "mx_search.py",
    "mx-xuangu": MX_SKILLS_DIR / "mx-xuangu" / "mx_xuangu.py",
    "mx-zixuan": MX_SKILLS_DIR / "mx-zixuan" / "mx_zixuan.py",
    "mx-moni": MX_SKILLS_DIR / "mx-moni" / "mx_moni.py",
    "mx-poster": MX_SKILLS_DIR / "mx-poster" / "mx_poster.py",
}


def call_mx_skill(skill_name: str, query: str, output_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    统一调用妙想Skill（带配额检查）
    
    参数:
        skill_name: 技能名称，如 'mx-data', 'mx-search'
        query: 查询内容（自然语言）
        output_dir: 输出目录（可选）
    
    返回:
        {"success": bool, "data": any, "error": str, "quota_remaining": int}
    """
    # 1. 检查技能是否存在
    if skill_name not in SKILL_SCRIPTS:
        return {
            "success": False,
            "data": None,
            "error": f"未知技能: {skill_name}。可用技能: {list(SKILL_SCRIPTS.keys())}",
            "quota_remaining": quota_manager.get_remaining_quota()
        }
    
    script_path = SKILL_SCRIPTS[skill_name]
    if not script_path.exists():
        return {
            "success": False,
            "data": None,
            "error": f"技能脚本不存在: {script_path}",
            "quota_remaining": quota_manager.get_remaining_quota()
        }
    
    # 2. 检查配额
    if not quota_manager.use_quota(skill_name, query):
        return {
            "success": False,
            "data": None,
            "error": f"今日调用次数已达上限 (50次/天)。剩余: 0 次。",
            "quota_remaining": 0
        }
    
    # 3. 执行调用
    try:
        cmd = [sys.executable, str(script_path), query]
        if output_dir:
            cmd.append(output_dir)
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,  # 60秒超时
            encoding='utf-8',
            errors='replace'
        )
        
        if result.returncode == 0:
            logger.info(f"✅ [{skill_name}] 调用成功")
            return {
                "success": True,
                "data": result.stdout,
                "error": None,
                "quota_remaining": quota_manager.get_remaining_quota()
            }
        else:
            error_msg = result.stderr or result.stdout or "未知错误"
            # 检查是否是配额超限错误
            if "code=113" in error_msg or "今日调用次数已达上限" in error_msg:
                logger.error(f"❌ [{skill_name}] 配额超限（API返回）")
                # 回滚配额计数
                quota_manager.quota_data["used"] = max(0, quota_manager.quota_data["used"] - 1)
                quota_manager._save_quota()
                return {
                    "success": False,
                    "data": None,
                    "error": "配额超限（API返回code=113）。今日已用满50次调用。",
                    "quota_remaining": 0
                }
            
            logger.error(f"❌ [{skill_name}] 调用失败: {error_msg[:200]}")
            return {
                "success": False,
                "data": result.stdout,
                "error": error_msg[:500],
                "quota_remaining": quota_manager.get_remaining_quota()
            }
    
    except subprocess.TimeoutExpired:
        logger.error(f"❌ [{skill_name}] 调用超时")
        # 回滚配额
        quota_manager.quota_data["used"] = max(0, quota_manager.quota_data["used"] - 1)
        quota_manager._save_quota()
        return {
            "success": False,
            "data": None,
            "error": "调用超时（60秒）",
            "quota_remaining": quota_manager.get_remaining_quota()
        }
    except Exception as e:
        logger.error(f"❌ [{skill_name}] 调用异常: {e}")
        quota_manager.quota_data["used"] = max(0, quota_manager.quota_data["used"] - 1)
        quota_manager._save_quota()
        return {
            "success": False,
            "data": None,
            "error": str(e)[:500],
            "quota_remaining": quota_manager.get_remaining_quota()
        }


def get_mx_quota_status() -> Dict[str, Any]:
    """获取妙想Skills配额状态"""
    return quota_manager.get_status()


def reset_mx_quota():
    """重置当日配额（谨慎使用）"""
    quota_manager.reset_quota()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== 妙想Skills统一接口测试 ===\n")
    
    # 测试1：获取配额状态
    print("1. 配额状态:")
    status = get_mx_quota_status()
    print(f"   日期: {status['date']}")
    print(f"   已用/限制: {status['used']}/{status['limit']}")
    print(f"   剩余: {status['remaining']}")
    
    # 测试2：调用 mx-data
    print("\n2. 调用 mx-data (查询贵州茅台最新价)...")
    result = call_mx_skill("mx-data", "贵州茅台最新价")
    print(f"   成功: {result['success']}")
    print(f"   剩余配额: {result['quota_remaining']}")
    if result['success']:
        print(f"   数据预览: {result['data'][:200]}...")
    else:
        print(f"   错误: {result['error']}")
    
    # 测试3：查看最终状态
    print("\n3. 最终配额状态:")
    print(f"   {get_mx_quota_status()}")
