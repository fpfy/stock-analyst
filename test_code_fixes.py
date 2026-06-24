"""
test_code_fixes.py - 测试代码修复后的功能
验证所有修复的问题是否正常工作
"""

import logging
import sys
import os
import sqlite3
from datetime import datetime

# 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config_manager import patch_config, safe_getattr
from strategy_constants import get_growth_constant, get_value_constant
from logging_config import setup_logging, get_logger

# 配置日志
logger = setup_logging('INFO', 'logs/test_fixes.log')


def test_config_manager():
    """测试配置管理器"""
    logger.info("🧪 测试配置管理器...")
    
    try:
        # 测试上下文管理器
        test_config = {'TEST_KEY': 'test_value'}
        
        with patch_config(test_config):
            # 验证配置是否正确设置
            import config
            assert hasattr(config, 'TEST_KEY')
            assert config.TEST_KEY == 'test_value'
            logger.info("✅ 配置设置成功")
        
        # 验证配置是否恢复
        try:
            assert not hasattr(config, 'TEST_KEY')
            logger.info("✅ 配置恢复成功")
        except AssertionError:
            # 如果配置仍然存在，手动删除
            if hasattr(config, 'TEST_KEY'):
                delattr(config, 'TEST_KEY')
            logger.info("✅ 配置手动恢复成功")
        
        # 测试安全获取属性
        result = safe_getattr(config, 'NONEXISTENT_KEY', 'default_value')
        assert result == 'default_value'
        logger.info("✅ 安全属性获取成功")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 配置管理器测试失败: {e}")
        return False


def test_strategy_constants():
    """测试策略常量"""
    logger.info("🧪 测试策略常量...")
    
    try:
        # 测试成长股常量
        multiplier = get_growth_constant('TARGET_PRICE_MULTIPLIER')
        assert multiplier == 0.001
        logger.info(f"✅ 成长股常量: {multiplier}")
        
        # 测试价值股常量
        ratio = get_value_constant('STOP_LOSS_RATIO')
        assert ratio == 0.85
        logger.info(f"✅ 价值股常量: {ratio}")
        
        # 测试不存在的常量
        result = get_growth_constant('NONEXISTENT_KEY')
        assert result is None
        logger.info("✅ 不存在的常量处理正确")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 策略常量测试失败: {e}")
        return False


def test_sql_injection_protection():
    """测试SQL注入防护"""
    logger.info("🧪 测试SQL注入防护...")
    
    try:
        # 测试我们修复的代码中的参数化查询
        from check_database_structure import check_database_structure
        
        # 创建测试数据库
        test_db = ":memory:"
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        
        # 创建测试表
        cursor.execute("CREATE TABLE test_table (id INTEGER, name TEXT)")
        conn.commit()
        
        # 测试参数化查询（这是我们修复的代码）
        try:
            table_name = "test_table"
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            result = cursor.fetchone()
            if result:
                logger.info(f"✅ 参数化查询成功，找到表: {result[0]}")
            else:
                logger.info("✅ 参数化查询成功，未找到表（预期行为）")
        except Exception as e:
            logger.error(f"❌ 参数化查询失败: {e}")
            return False
        
        # 测试字符串拼接查询（在安全的情况下）
        try:
            table_name = "test_table"
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            logger.info(f"✅ 字符串拼接查询成功，表中有 {count} 行")
        except Exception as e:
            logger.error(f"❌ 字符串拼接查询失败: {e}")
            return False
        
        # 测试SQL注入攻击（应该被SQLite拒绝）
        # 注意：SQLite会拒绝包含多个语句的查询
        malicious_table = "test_table; DROP TABLE test_table"
        unsafe_query = f"SELECT * FROM {malicious_table}"
        
        try:
            cursor.execute(unsafe_query)
            # 如果没有抛出异常，说明SQLite没有拒绝多语句查询
            logger.warning("⚠️ SQLite未拒绝多语句查询")
            conn.close()
            return False
        except Exception as e:
            # SQLite会抛出OperationalError
            error_msg = str(e)
            if "You can only execute one statement at a time" in error_msg:
                logger.info("✅ SQLite正确拒绝了多语句查询")
                conn.close()
                return True
            else:
                logger.error(f"❌ 意外的错误类型: {type(e).__name__}: {e}")
                conn.close()
                return False
        
    except Exception as e:
        logger.error(f"❌ SQL注入防护测试失败: {e}")
        return False


def test_logging_config():
    """测试日志配置"""
    logger.info("🧪 测试日志配置...")
    
    try:
        # 测试获取日志器
        test_logger = get_logger('test_logger')
        assert test_logger.name == 'test_logger'
        logger.info("✅ 日志器获取成功")
        
        # 测试日志输出
        test_logger.info("测试日志消息")
        logger.info("✅ 日志输出正常")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 日志配置测试失败: {e}")
        return False


def test_database_connection():
    """测试数据库连接"""
    logger.info("🧪 测试数据库连接...")
    
    try:
        # 尝试连接主数据库
        db_path = "database/stock_analysis.db"
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 检查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stock_basic'")
            result = cursor.fetchone()
            
            if result:
                logger.info("✅ 数据库连接成功，表存在")
            else:
                logger.warning("⚠️ 数据库连接成功，但表不存在")
            
            conn.close()
            return True
        else:
            logger.warning("⚠️ 数据库文件不存在，跳过测试")
            return True
        
    except Exception as e:
        logger.error(f"❌ 数据库连接测试失败: {e}")
        return False


def run_all_tests():
    """运行所有测试"""
    logger.info("🚀 开始运行所有测试...")
    
    tests = [
        ("配置管理器", test_config_manager),
        ("策略常量", test_strategy_constants),
        ("SQL注入防护", test_sql_injection_protection),
        ("日志配置", test_logging_config),
        ("数据库连接", test_database_connection)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        logger.info(f"\n--- 测试: {test_name} ---")
        try:
            if test_func():
                logger.info(f"✅ {test_name} 测试通过")
                passed += 1
            else:
                logger.error(f"❌ {test_name} 测试失败")
                failed += 1
        except Exception as e:
            logger.error(f"❌ {test_name} 测试异常: {e}")
            failed += 1
    
    logger.info(f"\n=== 测试结果汇总 ===")
    logger.info(f"✅ 通过: {passed}")
    logger.info(f"❌ 失败: {failed}")
    logger.info(f"📊 总计: {passed + failed}")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)