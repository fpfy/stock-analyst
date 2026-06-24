"""
simple_financial_test.py - 简化版金融数据源测试
专注于获取实际可用的数据源信息
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime
import json
import time
import logging
from typing import Dict, List, Optional, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleFinancialTester:
    """简化版金融数据源测试器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.qq.com/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
    def test_tencent_finance(self) -> Dict[str, Any]:
        """测试腾讯财经接口"""
        print("=== 腾讯财经接口测试 ===")
        
        results = {}
        
        try:
            # 测试指数数据
            url = "https://qt.gtimg.cn/q=sh000001,sz399001,sz399006"
            response = self.session.get(url, timeout=15)
            
            if response.status_code == 200:
                data = response.text
                lines = data.split('~')
                
                logger.info(f"腾讯财经返回数据行数: {len(lines)}")
                
                # 解析数据
                index_data = {}
                for i, line in enumerate(lines[1:4]):  # 只处理前3行（上证、深证、创业板）
                    if line and ',' in line:
                        parts = line.split(',')
                        if len(parts) >= 10:
                            name = parts[0]
                            code = parts[1]
                            price = float(parts[3]) if parts[3] else 0
                            change = float(parts[4]) if parts[4] else 0
                            change_pct = float(parts[5]) if parts[5] else 0
                            
                            index_name = ['sh_index', 'sz_index', 'cy_index'][i]
                            index_data[index_name] = {
                                'name': name,
                                'code': code,
                                'price': price,
                                'change': change,
                                'change_pct': change_pct,
                                'status': '✅ 成功'
                            }
                            logger.info(f"{name}获取成功: {price}")
                
                results['index_data'] = index_data
            else:
                results['error'] = f'HTTP {response.status_code}'
                logger.error(f"腾讯财经HTTP错误: {response.status_code}")
                
        except Exception as e:
            results['error'] = str(e)
            logger.error(f"腾讯财经接口测试失败: {e}")
        
        return results
    
    def test_eastmoney_finance(self) -> Dict[str, Any]:
        """测试东方财富接口"""
        print("=== 东方财富接口测试 ===")
        
        results = {}
        
        try:
            # 测试指数数据
            url = "https://push2.eastmoney.com/api/qt/stock/kline/get"
            params = {
                'secid': '1.000001',  # 上证指数
                'ut': 'fa5fd1943c7b386f172d689aabd9286f',
                'fields1': 'f1,f2,f3,f4,f5,f6',
                'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63',
                'klt': '101',  # 日线
                'fqt': '1',
                'end': '20500101',
                'lmt': '120'
            }
            
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('result') and data['result'].get('data') and data['result']['data'].get('klines'):
                    klines = data['result']['data']['klines']
                    results['sh_index'] = {
                        'name': '上证指数',
                        'code': '1.000001',
                        'klines_count': len(klines),
                        'status': '✅ 成功'
                    }
                    logger.info(f"东方财富上证指数数据获取成功: {len(klines)}条")
                else:
                    results['sh_index'] = {
                        'error': '数据格式错误',
                        'status': '❌ 失败'
                    }
                    logger.error("东方财富数据格式错误")
            else:
                results['sh_index'] = {
                    'error': f'HTTP {response.status_code}',
                    'status': '❌ 失败'
                }
                logger.error(f"东方财富HTTP错误: {response.status_code}")
                
        except Exception as e:
            results['sh_index'] = {
                'error': str(e),
                'status': '❌ 失败'
            }
            logger.error(f"东方财富接口测试失败: {e}")
        
        return results
    
    def test_sina_finance(self) -> Dict[str, Any]:
        """测试新浪财经接口"""
        print("=== 新浪财经接口测试 ===")
        
        results = {}
        
        try:
            # 测试指数数据
            url = "https://hq.sinajs.cn/list=s_sh000001,s_sz399001,s_sz399006"
            response = self.session.get(url, timeout=15)
            
            if response.status_code == 200:
                data = response.text
                lines = data.split(';')
                
                index_count = 0
                for line in lines[:-1]:  # 跳过最后一行空行
                    if line and '=' in line:
                        index_count += 1
                
                results['index_data'] = {
                    'count': index_count,
                    'status': '✅ 成功'
                }
                
                logger.info(f"新浪财经指数数据获取成功: {index_count}个")
            else:
                results['index_data'] = {
                    'error': f'HTTP {response.status_code}',
                    'status': '❌ 失败'
                }
                logger.error(f"新浪财经HTTP错误: {response.status_code}")
                
        except Exception as e:
            results['index_data'] = {
                'error': str(e),
                'status': '❌ 失败'
            }
            logger.error(f"新浪财经接口测试失败: {e}")
        
        return results
    
    def test_akshare_finance(self) -> Dict[str, Any]:
        """测试akshare财经接口"""
        print("=== akshare财经接口测试 ===")
        
        results = {}
        
        try:
            # 测试PMI数据
            try:
                import akshare as ak
                pmi_data = ak.macro_china_pmi()
                if not pmi_data.empty:
                    results['pmi_data'] = {
                        'count': len(pmi_data),
                        'status': '✅ 成功',
                        'latest_value': pmi_data['制造业-指数'].iloc[-1] if len(pmi_data) > 0 else 0
                    }
                    logger.info(f"akshare PMI数据获取成功: {len(pmi_data)}条")
                else:
                    results['pmi_data'] = {'status': '❌ 空数据'}
            except Exception as e:
                results['pmi_data'] = {'error': str(e), 'status': '❌ 失败'}
                logger.error(f"akshare PMI数据测试失败: {e}")
            
            # 测试CPI数据
            try:
                cpi_data = ak.macro_china_cpi()
                if not cpi_data.empty:
                    results['cpi_data'] = {
                        'count': len(cpi_data),
                        'status': '✅ 成功',
                        'latest_value': cpi_data['cpi'].iloc[-1] if len(cpi_data) > 0 else 0
                    }
                    logger.info(f"akshare CPI数据获取成功: {len(cpi_data)}条")
                else:
                    results['cpi_data'] = {'status': '❌ 空数据'}
            except Exception as e:
                results['cpi_data'] = {'error': str(e), 'status': '❌ 失败'}
                logger.error(f"akshare CPI数据测试失败: {e}")
            
            # 测试股票列表
            try:
                stock_list = ak.stock_info_a_code_name()
                if not stock_list.empty:
                    results['stock_list'] = {
                        'count': len(stock_list),
                        'status': '✅ 成功'
                    }
                    logger.info(f"akshare股票列表获取成功: {len(stock_list)}只")
                else:
                    results['stock_list'] = {'status': '❌ 空数据'}
            except Exception as e:
                results['stock_list'] = {'error': str(e), 'status': '❌ 失败'}
                logger.error(f"akshare股票列表测试失败: {e}")
            
        except Exception as e:
            results['error'] = str(e)
            logger.error(f"akshare接口测试失败: {e}")
        
        return results
    
    def run_all_tests(self) -> Dict[str, Any]:
        """运行所有测试"""
        print("=== 金融数据源综合测试 ===")
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        all_results = {}
        
        # 测试腾讯财经
        print("1. 测试腾讯财经...")
        tencent_results = self.test_tencent_finance()
        all_results['tencent'] = tencent_results
        print()
        
        # 测试东方财富
        print("2. 测试东方财富...")
        eastmoney_results = self.test_eastmoney_finance()
        all_results['eastmoney'] = eastmoney_results
        print()
        
        # 测试新浪财经
        print("3. 测试新浪财经...")
        sina_results = self.test_sina_finance()
        all_results['sina'] = sina_results
        print()
        
        # 测试akshare
        print("4. 测试akshare...")
        akshare_results = self.test_akshare_finance()
        all_results['akshare'] = akshare_results
        print()
        
        return all_results
    
    def generate_report(self, results: Dict[str, Any]) -> str:
        """生成测试报告"""
        report = []
        report.append("=== 金融数据源测试报告 ===")
        report.append(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append()
        
        # 腾讯财经
        report.append("### 腾讯财经接口")
        if 'tencent' in results:
            if 'index_data' in results['tencent']:
                for index_name, index_data in results['tencent']['index_data'].items():
                    report.append(f"{index_data['name']}: {index_data['status']}")
                    if 'price' in index_data:
                        report.append(f"  价格: {index_data['price']:.2f}")
                    if 'change_pct' in index_data:
                        report.append(f"  涨跌幅: {index_data['change_pct']:.2f}%")
            else:
                report.append("❌ 指数数据获取失败")
        
        report.append()
        
        # 东方财富
        report.append("### 东方财富接口")
        if 'eastmoney' in results:
            if 'sh_index' in results['eastmoney']:
                sh = results['eastmoney']['sh_index']
                report.append(f"上证指数: {sh['status']}")
                if 'klines_count' in sh:
                    report.append(f"  K线数量: {sh['klines_count']}")
            else:
                report.append("❌ 指数数据获取失败")
        
        report.append()
        
        # 新浪财经
        report.append("### 新浪财经接口")
        if 'sina' in results:
            if 'index_data' in results['sina']:
                idata = results['sina']['index_data']
                report.append(f"指数数据: {idata['status']}")
                if 'count' in idata:
                    report.append(f"  数量: {idata['count']}")
            else:
                report.append("❌ 指数数据获取失败")
        
        report.append()
        
        # akshare
        report.append("### akshare接口")
        if 'akshare' in results:
            if 'pmi_data' in results['akshare']:
                pmi = results['akshare']['pmi_data']
                report.append(f"PMI数据: {pmi['status']}")
                if 'latest_value' in pmi:
                    report.append(f"  最新值: {pmi['latest_value']}")
            if 'cpi_data' in results['akshare']:
                cpi = results['akshare']['cpi_data']
                report.append(f"CPI数据: {cpi['status']}")
                if 'latest_value' in cpi:
                    report.append(f"  最新值: {cpi['latest_value']}")
            if 'stock_list' in results['akshare']:
                sl = results['akshare']['stock_list']
                report.append(f"股票列表: {sl['status']}")
                if 'count' in sl:
                    report.append(f"  数量: {sl['count']}只")
        
        report.append()
        
        # 综合评价
        report.append("### 综合评价")
        report.append("#### 数据源特点分析:")
        report.append("1. **腾讯财经**: 实时性强，数据更新及时，适合实时行情")
        report.append("2. **东方财富**: 历史数据完整，K线数据丰富，适合技术分析")
        report.append("3. **新浪财经**: 接口稳定，数据格式简单，适合快速获取")
        report.append("4. **akshare**: 免费开源，宏观数据完整，适合基础数据")
        report.append()
        
        report.append("#### 推荐方案:")
        report.append("1. **主要数据源**: Tushare + akshare")
        report.append("2. **备用数据源**: 腾讯财经")
        report.append("3. **宏观数据**: akshare")
        report.append("4. **数据质量**: Tushare > 腾讯财经 > 东方财富 > 新浪财经 > akshare")
        report.append()
        
        return "\n".join(report)


if __name__ == "__main__":
    tester = SimpleFinancialTester()
    results = tester.run_all_tests()
    report = tester.generate_report(results)
    print(report)
    
    # 保存报告到文件
    with open('simple_financial_test_report.txt', 'w', encoding='utf-8') as f:
        f.write(report)
    
    print("\n=== 测试完成，报告已保存到 simple_financial_test_report.txt ===")