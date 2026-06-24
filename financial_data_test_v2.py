"""
financial_data_test_v2.py - 腾讯财经、东方财富、新浪财经数据源测试（修复版）
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import time
import logging
from typing import Dict, List, Optional, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FinancialDataTesterV2:
    """金融数据源测试器（修复版）"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.qq.com/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        })
        
    def test_tencent_finance(self) -> Dict[str, Any]:
        """测试腾讯财经接口"""
        print("=== 腾讯财经接口测试 ===")
        
        results = {}
        
        try:
            # 测试股票基本信息
            url = "https://qt.gtimg.cn/q=sh000001,sz399001,sz399006"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                # 解析腾讯财经数据
                data = response.text
                lines = data.split('~')
                
                logger.info(f"腾讯财经返回数据行数: {len(lines)}")
                
                # 上证指数
                if len(lines) > 1:
                    sh_data = lines[1].split(',')
                    if len(sh_data) >= 10:
                        results['sh_index'] = {
                            'name': sh_data[0],
                            'code': sh_data[1],
                            'price': float(sh_data[3]) if sh_data[3] else 0,
                            'change': float(sh_data[4]) if sh_data[4] else 0,
                            'change_pct': float(sh_data[5]) if sh_data[5] else 0,
                            'volume': float(sh_data[8]) if sh_data[8] else 0,
                            'amount': float(sh_data[9]) if sh_data[9] else 0,
                            'status': '✅ 成功'
                        }
                        logger.info(f"上证指数获取成功: {results['sh_index']['price']}")
                    else:
                        results['sh_index'] = {'error': '数据格式错误', 'status': '❌ 失败'}
                
                # 深证成指
                if len(lines) > 2:
                    sz_data = lines[2].split(',')
                    if len(sz_data) >= 10:
                        results['sz_index'] = {
                            'name': sz_data[0],
                            'code': sz_data[1],
                            'price': float(sz_data[3]) if sz_data[3] else 0,
                            'change': float(sz_data[4]) if sz_data[4] else 0,
                            'change_pct': float(sz_data[5]) if sz_data[5] else 0,
                            'volume': float(sz_data[8]) if sz_data[8] else 0,
                            'amount': float(sz_data[9]) if sz_data[9] else 0,
                            'status': '✅ 成功'
                        }
                        logger.info(f"深证成指获取成功: {results['sz_index']['price']}")
                    else:
                        results['sz_index'] = {'error': '数据格式错误', 'status': '❌ 失败'}
                
                # 创业板指
                if len(lines) > 3:
                    cy_data = lines[3].split(',')
                    if len(cy_data) >= 10:
                        results['cy_index'] = {
                            'name': cy_data[0],
                            'code': cy_data[1],
                            'price': float(cy_data[3]) if cy_data[3] else 0,
                            'change': float(cy_data[4]) if cy_data[4] else 0,
                            'change_pct': float(cy_data[5]) if cy_data[5] else 0,
                            'volume': float(cy_data[8]) if cy_data[8] else 0,
                            'amount': float(cy_data[9]) if cy_data[9] else 0,
                            'status': '✅ 成功'
                        }
                        logger.info(f"创业板指获取成功: {results['cy_index']['price']}")
                    else:
                        results['cy_index'] = {'error': '数据格式错误', 'status': '❌ 失败'}
            else:
                results['error'] = f'HTTP {response.status_code}'
                logger.error(f"腾讯财经HTTP错误: {response.status_code}")
                
        except Exception as e:
            results['error'] = str(e)
            logger.error(f"腾讯财经接口测试失败: {e}")
        
        # 测试股票列表
        try:
            url = "https://qt.gtimg.cn/q=sh600000,sz000001,sz000002"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.text
                lines = data.split('~')
                
                stock_count = 0
                valid_lines = 0
                for line in lines[1:]:  # 跳过第一行
                    if line and ',' in line:
                        stock_count += 1
                        valid_lines += 1
                
                results['stock_list'] = {
                    'count': stock_count,
                    'total_lines': valid_lines,
                    'status': '✅ 成功' if stock_count > 0 else '⚠️ 无数据'
                }
                
                logger.info(f"腾讯财经股票列表测试成功: {stock_count}只")
            else:
                results['stock_list'] = {
                    'error': f'HTTP {response.status_code}',
                    'status': '❌ 失败'
                }
                
        except Exception as e:
            results['stock_list'] = {
                'error': str(e),
                'status': '❌ 失败'
            }
            logger.error(f"腾讯财经股票列表测试失败: {e}")
        
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
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"东方财富响应数据: {json.dumps(data, ensure_ascii=False, indent=2)[:200]}...")
                
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
                        'response': str(data)[:200],
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
        
        # 测试股票数据
        try:
            url = "https://push2.eastmoney.com/api/qt/stock/kline/get"
            params = {
                'secid': '1.600000',  # 浦发银行
                'ut': 'fa5fd1943c7b386f172d689aabd9286f',
                'fields1': 'f1,f2,f3,f4,f5,f6',
                'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63',
                'klt': '101',  # 日线
                'fqt': '1',
                'end': '20500101',
                'lmt': '120'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('result') and data['result'].get('data') and data['result']['data'].get('klines'):
                    klines = data['result']['data']['klines']
                    results['stock_data'] = {
                        'name': '浦发银行',
                        'code': '1.600000',
                        'klines_count': len(klines),
                        'status': '✅ 成功'
                    }
                    logger.info(f"东方财富股票数据获取成功: {len(klines)}条")
                else:
                    results['stock_data'] = {
                        'error': '数据格式错误',
                        'response': str(data)[:200],
                        'status': '❌ 失败'
                    }
                    logger.error("东方财富股票数据格式错误")
            else:
                results['stock_data'] = {
                    'error': f'HTTP {response.status_code}',
                    'status': '❌ 失败'
                }
                
        except Exception as e:
            results['stock_data'] = {
                'error': str(e),
                'status': '❌ 失败'
            }
            logger.error(f"东方财富股票数据测试失败: {e}")
        
        return results
    
    def test_sina_finance(self) -> Dict[str, Any]:
        """测试新浪财经接口"""
        print("=== 新浪财经接口测试 ===")
        
        results = {}
        
        try:
            # 测试指数数据
            url = "https://hq.sinajs.cn/list=s_sh000001,s_sz399001,s_sz399006"
            response = self.session.get(url, timeout=10)
            
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
        
        # 测试股票数据
        try:
            url = "https://hq.sinajs.cn/list=s_sh600000,s_sz000001"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.text
                lines = data.split(';')
                
                stock_count = 0
                for line in lines[:-1]:  # 跳过最后一行空行
                    if line and '=' in line:
                        stock_count += 1
                
                results['stock_data'] = {
                    'count': stock_count,
                    'status': '✅ 成功'
                }
                
                logger.info(f"新浪财经股票数据获取成功: {stock_count}只")
            else:
                results['stock_data'] = {
                    'error': f'HTTP {response.status_code}',
                    'status': '❌ 失败'
                }
                
        except Exception as e:
            results['stock_data'] = {
                'error': str(e),
                'status': '❌ 失败'
            }
            logger.error(f"新浪财经股票数据测试失败: {e}")
        
        return results
    
    def test_macro_data_sources(self) -> Dict[str, Any]:
        """测试宏观数据源"""
        print("=== 宏观数据源测试 ===")
        
        results = {}
        
        try:
            # 测试国家统计局数据
            url = "http://data.stats.gov.cn/easyquery.htm?cn=C01"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                results['stats_gov'] = {
                    'status': '✅ 可访问',
                    'content_length': len(response.text)
                }
                logger.info("国家统计局数据源可访问")
            else:
                results['stats_gov'] = {
                    'error': f'HTTP {response.status_code}',
                    'status': '❌ 不可访问'
                }
                logger.error(f"国家统计局HTTP错误: {response.status_code}")
                
        except Exception as e:
            results['stats_gov'] = {
                'error': str(e),
                'status': '❌ 不可访问'
            }
            logger.error(f"国家统计局接口测试失败: {e}")
        
        # 测试中国人民银行数据
        try:
            url = "https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/5267372/index.html"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                results['pbc'] = {
                    'status': '✅ 可访问',
                    'content_length': len(response.text)
                }
                logger.info("中国人民银行数据源可访问")
            else:
                results['pbc'] = {
                    'error': f'HTTP {response.status_code}',
                    'status': '❌ 不可访问'
                }
                
        except Exception as e:
            results['pbc'] = {
                'error': str(e),
                'status': '❌ 不可访问'
            }
            logger.error(f"中国人民银行接口测试失败: {e}")
        
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
        
        # 测试宏观数据源
        print("4. 测试宏观数据源...")
        macro_results = self.test_macro_data_sources()
        all_results['macro'] = macro_results
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
            if 'sh_index' in results['tencent']:
                sh = results['tencent']['sh_index']
                report.append(f"上证指数: {sh.get('status', '未知')}")
                if 'price' in sh:
                    report.append(f"  价格: {sh['price']:.2f}")
                if 'change_pct' in sh:
                    report.append(f"  涨跌幅: {sh['change_pct']:.2f}%")
            if 'sz_index' in results['tencent']:
                sz = results['tencent']['sz_index']
                report.append(f"深证成指: {sz.get('status', '未知')}")
                if 'price' in sz:
                    report.append(f"  价格: {sz['price']:.2f}")
                if 'change_pct' in sz:
                    report.append(f"  涨跌幅: {sz['change_pct']:.2f}%")
            if 'cy_index' in results['tencent']:
                cy = results['tencent']['cy_index']
                report.append(f"创业板指: {cy.get('status', '未知')}")
                if 'price' in cy:
                    report.append(f"  价格: {cy['price']:.2f}")
                if 'change_pct' in cy:
                    report.append(f"  涨跌幅: {cy['change_pct']:.2f}%")
            if 'stock_list' in results['tencent']:
                sl = results['tencent']['stock_list']
                report.append(f"股票列表: {sl.get('status', '未知')}")
                if 'count' in sl:
                    report.append(f"  数量: {sl['count']}只")
        
        report.append()
        
        # 东方财富
        report.append("### 东方财富接口")
        if 'eastmoney' in results:
            if 'sh_index' in results['eastmoney']:
                sh = results['eastmoney']['sh_index']
                report.append(f"上证指数: {sh.get('status', '未知')}")
                if 'klines_count' in sh:
                    report.append(f"  K线数量: {sh['klines_count']}")
            if 'stock_data' in results['eastmoney']:
                sd = results['eastmoney']['stock_data']
                report.append(f"股票数据: {sd.get('status', '未知')}")
                if 'klines_count' in sd:
                    report.append(f"  K线数量: {sd['klines_count']}")
        
        report.append()
        
        # 新浪财经
        report.append("### 新浪财经接口")
        if 'sina' in results:
            if 'index_data' in results['sina']:
                idata = results['sina']['index_data']
                report.append(f"指数数据: {idata.get('status', '未知')}")
                if 'count' in idata:
                    report.append(f"  数量: {idata['count']}")
            if 'stock_data' in results['sina']:
                sdata = results['sina']['stock_data']
                report.append(f"股票数据: {sdata.get('status', '未知')}")
                if 'count' in sdata:
                    report.append(f"  数量: {sdata['count']}")
        
        report.append()
        
        # 宏观数据源
        report.append("### 宏观数据源")
        if 'macro' in results:
            if 'stats_gov' in results['macro']:
                sg = results['macro']['stats_gov']
                report.append(f"国家统计局: {sg.get('status', '未知')}")
            if 'pbc' in results['macro']:
                pbc = results['macro']['pbc']
                report.append(f"中国人民银行: {pbc.get('status', '未知')}")
        
        report.append()
        
        # 综合评价
        report.append("### 综合评价")
        report.append("#### 数据源特点分析:")
        report.append("1. **腾讯财经**: 实时性强，数据更新及时，适合实时行情")
        report.append("2. **东方财富**: 历史数据完整，K线数据丰富，适合技术分析")
        report.append("3. **新浪财经**: 接口稳定，数据格式简单，适合快速获取")
        report.append("4. **宏观数据**: 国家统计局数据权威，但获取难度较大")
        report.append()
        
        report.append("#### 推荐方案:")
        report.append("1. **主要数据源**: 腾讯财经 + 东方财富")
        report.append("2. **备用数据源**: 新浪财经")
        report.append("3. **宏观数据**: 国家统计局官方数据")
        report.append("4. **数据质量**: 腾讯财经 > 东方财富 > 新浪财经")
        report.append()
        
        return "\n".join(report)


if __name__ == "__main__":
    tester = FinancialDataTesterV2()
    results = tester.run_all_tests()
    report = tester.generate_report(results)
    print(report)
    
    # 保存报告到文件
    with open('financial_data_test_report_v2.txt', 'w', encoding='utf-8') as f:
        f.write(report)
    
    print("\n=== 测试完成，报告已保存到 financial_data_test_report_v2.txt ===")