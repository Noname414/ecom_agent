from typing import List, Dict, Optional, Any
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
import sys
import os
sys.path.append(os.path.dirname(__file__))

from pchome_crawler import fetch_products as fetch_pchome
from yahoo_crawler import fetch_products as fetch_yahoo
from routn_crawler import fetch_products as fetch_ruten

class SearchInput(BaseModel):
    """搜尋輸入參數"""
    keyword: str = Field(..., description="要搜尋的商品關鍵字")

class EcommerceTool(BaseTool):
    name: str = "ecommerce_search"
    description: str = """
    在台灣主要電商平台（PChome、Yahoo購物、露天拍賣）搜尋商品。
    只需要輸入關鍵字，就會自動搜尋並比較各平台商品。
    回傳的結果包含商品標題、價格、圖片網址、商品網址和平台名稱。
    """
    args_schema: Any = SearchInput

    def _fetch_all_platforms(self, keyword: str) -> List[Dict]:
        """從所有平台抓取商品資訊"""
        all_products = []
        max_products = 50  # 每個平台抓取的商品數量
        max_retries = 3   # 最大重試次數
        
        # 建立平台對應的函數字典
        platform_functions = {
            "pchome": fetch_pchome,
            "yahoo": fetch_yahoo,
            "ruten": fetch_ruten
        }
        
        def fetch_with_retry(func, platform_name, keyword, max_products):
            """帶有重試機制的爬蟲函數"""
            for attempt in range(max_retries):
                try:
                    return func(keyword, max_products)
                except Exception as e:
                    if attempt == max_retries - 1:  # 最後一次嘗試
                        print(f"警告：{platform_name} 平台搜尋失敗（重試 {attempt + 1}/{max_retries}）")
                        print(f"錯誤訊息：{str(e)}")
                        return []
                    print(f"警告：{platform_name} 平台搜尋失敗，正在重試（{attempt + 1}/{max_retries}）")
                    import time
                    time.sleep(1)  # 重試前等待 1 秒
            return []
        
        # 使用 ThreadPoolExecutor 平行處理各平台的請求
        with ThreadPoolExecutor(max_workers=len(platform_functions)) as executor:
            # 建立任務列表
            future_to_platform = {
                executor.submit(
                    fetch_with_retry,
                    platform_functions[platform],
                    platform,
                    keyword,
                    max_products
                ): platform 
                for platform in platform_functions
            }
            
            # 收集結果
            successful_platforms = []
            for future in future_to_platform:
                platform = future_to_platform[future]
                try:
                    products = future.result()
                    if products:
                        all_products.extend(products)
                        successful_platforms.append(platform)
                except Exception as e:
                    print(f"錯誤：{platform} 平台發生未預期的錯誤: {str(e)}")
        
        if not successful_platforms:
            print(f"警告：所有平台搜尋都失敗了")
        else:
            print(f"成功從以下平台獲取資料：{', '.join(successful_platforms)}")
        
        # 按價格排序
        all_products.sort(key=lambda x: x["price"])
        
        # 移除價格為 0 或異常的商品
        all_products = [p for p in all_products if p["price"] > 0]
        
        return all_products

    def _format_products(self, products: List[Dict], keyword: str) -> str:
        """格式化商品資訊"""
        if not products:
            return f"抱歉，沒有找到與「{keyword}」相關的商品。"
        
        # 計算價格統計資訊
        prices = [p["price"] for p in products]
        avg_price = sum(prices) / len(prices)
        min_price = min(prices)
        max_price = max(prices)
        
        # 按平台分組
        platform_products = {}
        for product in products:
            platform = product["platform"]
            if platform not in platform_products:
                platform_products[platform] = []
            platform_products[platform].append(product)
        
        result = f"🔍 「{keyword}」的搜尋結果：\n\n"
        result += f"📊 價格分析：\n"
        result += f"   • 最低價格：NT$ {min_price:,}\n"
        result += f"   • 最高價格：NT$ {max_price:,}\n"
        result += f"   • 平均價格：NT$ {int(avg_price):,}\n\n"
        
        result += "🏆 各平台商品列表：\n"
        result += "=" * 50 + "\n"
        
        for i, product in enumerate(products, 1):
            platform_icon = {
                "pchome": "🔵",
                "yahoo": "🟣",
                "ruten": "🟡"
            }.get(product["platform"], "📦")
            
            price_comparison = ""
            if product["price"] == min_price:
                price_comparison = "💰 最低價"
            elif product["price"] < avg_price:
                price_comparison = "👍 低於平均"
            
            result += f"{i}. {platform_icon} {product['title']}\n"
            result += f"   平台：{product['platform']}\n"
            result += f"   價格：NT$ {product['price']:,} {price_comparison}\n"
            result += f"   商品連結：{product['url']}\n"
            result += f"   圖片連結：{product['image_url']}\n"
            result += "-" * 50 + "\n"
        
        result += "\n💡 小提醒：價格可能會隨時變動，建議點擊商品連結查看最新價格。"
        return result

    def _run(self, keyword: str) -> str:
        """執行工具"""
        try:
            # 抓取所有平台的商品
            all_products = self._fetch_all_platforms(keyword)
            
            # 格式化輸出
            return all_products
            
        except Exception as e:
            return f"搜尋過程發生錯誤: {str(e)}"

    async def _arun(self, keyword: str) -> str:
        """異步執行工具"""
        return self._run(keyword)

def get_ecommerce_tool() -> EcommerceTool:
    """獲取電商搜尋工具實例"""
    return EcommerceTool()

if __name__ == "__main__":
    # 測試工具
    tool = get_ecommerce_tool()
    result = tool.run("羽毛球拍")
    print(result) 