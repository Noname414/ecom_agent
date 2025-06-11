from playwright.async_api import async_playwright, Browser, BrowserContext
from bs4 import BeautifulSoup
import asyncio
import json
from langchain.tools import Tool
from abc import ABC, abstractmethod
import urllib
import requests
import sqlite3
from datetime import datetime
import re
from typing import Optional, Dict, Any
import logging

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def clean_price(price_str: str) -> str:
    """清理價格字串，移除非數字字符"""
    return re.sub(r'[^\d]', '', price_str)

def clean_title(title: str) -> str:
    """清理商品標題，移除多餘空格和特殊字符"""
    return re.sub(r'\s+', ' ', title).strip()

def retry_async(max_retries: int = 3, delay: float = 1.0):
    """非同步重試裝飾器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            for i in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if i == max_retries - 1:
                        raise
                    logger.warning(f"重試 {i+1}/{max_retries} 失敗: {str(e)}")
                    await asyncio.sleep(delay)
            return None
        return wrapper
    return decorator

def init_db():
    """初始化 SQLite 資料庫"""
    conn = sqlite3.connect('products.db')
    cursor = conn.cursor()
    
    # 建立商品表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT NOT NULL,
        title TEXT NOT NULL,
        price TEXT NOT NULL,
        link TEXT NOT NULL,
        query TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

def save_to_db(products: list, query: str):
    """將商品資料儲存到資料庫"""
    conn = sqlite3.connect('products.db')
    cursor = conn.cursor()
    
    for product in products:
        cursor.execute('''
        INSERT INTO products (platform, title, price, link, query)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            product['platform'],
            product['title'],
            product['price'],
            product['link'],
            query
        ))
    
    conn.commit()
    conn.close()

# 初始化資料庫
init_db()

class BaseScraper(ABC):
    """抽象基類，定義電子商務平台爬蟲的通用介面和行為。"""
    def __init__(self, browser: Browser, context: BrowserContext):
        self.browser = browser
        self.context = context
        self.platform_name = self.__class__.__name__.replace("Scraper", "")

    @retry_async(max_retries=3)
    async def _get_page_content(self, url: str, selector: str, timeout: int = 30000) -> BeautifulSoup:
        """通用的頁面內容獲取方法，帶重試機制"""
        page = await self.context.new_page()
        try:
            await page.goto(url, wait_until=selector, timeout=timeout)
            # await page.wait_for_selector(selector, timeout=10000)
            content = await page.content()
            return BeautifulSoup(content, "html.parser")
        finally:
            await page.close()
            
    @abstractmethod
    async def scrape(self, query: str, max_results: int = 5) -> list:
        """抽象方法，子類必須實現具體的爬蟲邏輯。"""
        pass

    def _clean_product_data(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """清理商品資料"""
        return {
            "platform": self.platform_name,
            "title": clean_title(product.get("title", "")),
            "price": clean_price(product.get("price", "")),
            "link": product.get("link", "")
        }

# Momo 平台爬蟲
class MomoScraper(BaseScraper):
    @retry_async(max_retries=3)
    async def scrape(self, query: str, max_results: int = 5) -> list:
        results = []
        page_num = 1
        base_url = f"https://www.momoshop.com.tw/search/searchShop.jsp?keyword={query}"
        
        while len(results) < max_results:
            page_url = f"{base_url}&curPage={page_num}"
            # print(f"正在爬取 {self.platform_name} 第 {page_num} 頁")
            try:
                soup = await self._get_page_content(page_url, "networkidle")
                # 判斷是否有搜尋結果或頁面不存在
                noSearch = soup.select(".noSearchResultWrapper")
                noPage = soup.select(".adjustmentTextArea")
                if noSearch: 
                    logger.info("沒有搜尋結果。請檢查關鍵字是否正確")
                    break
                if noPage:
                    logger.info("商品不足。可能已經到達最後一頁")
                    break
                items = soup.select(".listAreaLi")
                for item in items:
                    product = {
                        "title": item.select_one(".prdName").text.strip(),
                        "price": item.select_one(".price b").text.strip(),
                        "link": f"https://www.momoshop.com.tw/goods/GoodsDetail.jsp?i_code={item.select_one('a.goods-img-url')['href'].split('i_code=')[1].split('&')[0]}"
                    }
                    results.append(self._clean_product_data(product))
                page_num += 1 # 換頁
            except Exception as e:
                logger.error(f"爬取 {self.platform_name} 時發生錯誤: {e}")
                return []
            
        # with open("momo.json", "w", encoding="utf-8") as f:
        #     json.dump(results[:max_results], f, ensure_ascii=False, indent=2)
        # print(f"{self.platform_name}資料已儲存到{self.platform_name}.json")
        return results[:max_results]

# PChome 平台爬蟲
class PChomeScraper(BaseScraper):
    @retry_async(max_retries=3)
    async def scrape(self, query: str, max_results: int = 5) -> list:
        keyword_encoded = urllib.parse.quote(query)
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://shopping.pchome.com.tw/'
        }

        results = []
        page = 1

        while len(results) < max_results:
            url = f'https://ecshweb.pchome.com.tw/search/v3.3/all/results?q={keyword_encoded}&page={page}&sort=rnk/dc'
            try:
                response = requests.get(url, headers=headers)
                data = response.json()
                items = data.get('prods', [])

                if not items:
                    break

                for item in items:
                    product = {
                        "title": item.get("name", ""),
                        "price": str(item.get("price", "")),
                        "link": f"https://24h.pchome.com.tw/prod/{item.get('Id')}"
                    }
                    results.append(self._clean_product_data(product))

                # print(f"已抓取第 {page} 頁，累計 {len(results)} 筆")
                page += 1
            except Exception as e:
                logger.error(f"爬取 {self.platform_name} 時發生錯誤: {e}")
                break

        # # 儲存 JSON
        # with open("pchome.json", 'w', encoding='utf-8') as f:
        #     json.dump(results[:max_results], f, ensure_ascii=False, indent=2)
        # print(f"{self.platform_name}資料已儲存到{self.platform_name}.json")
        return results[:max_results]
        
# Yahoo 平台爬蟲
class YahooScraper(BaseScraper):
    # 使用 requests 來處理 Yahoo 的 GraphQL API
    @retry_async(max_retries=3)
    async def scrape(self, query: str, max_results: int = 5) -> list:
        results = []
        page_num = 1
        encoded_keyword = urllib.parse.quote(query)
        url = "https://graphql.ec.yahoo.com/graphql"

        headers = {
            "accept": "*/*",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "referer": f"https://tw.buy.yahoo.com/search/product?p={encoded_keyword}",
            "origin": "https://tw.buy.yahoo.com",
        }
        
        payload = {
            "variables": {
            "property": "sas",
            "p": f"{query}",
            "cid": "0",
            "pg": "1",
            "psz": f"{max_results}",
            "qt": "product",
            "sort": "rel",
            "isTestStoreIncluded": "0",
            "spaceId": 152989812,
            "source": "pc",
            "showMoreCluster": "0",
            "searchTarget": "ecItem",
            "isStoreSearch": 0,
            "isShoppingStoreSearch": 0
        },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "9e8c95a7bd216439855a6dcb580387b180713a20260a89c26096fbe4dd30133f"
                }
            }
        }
        
        try:
            session = requests.Session()
            res = session.post(url, headers=headers, json=payload)
            data = res.json()
            for item in data["data"]["getUther"]["hits"]:
                product = {
                    "title": item.get("ec_title", "N/A"),
                    "price": item.get("ec_price", "N/A"),
                    "link": item.get("ec_item_url", "N/A")
                }
                results.append(self._clean_product_data(product))
        except Exception as e:
            logger.error(f"爬取 {self.platform_name} 時發生錯誤: {e}")
            
        # with open("yahoo.json", 'w', encoding='utf-8') as f:
        #     json.dump(results, f, ensure_ascii=False, indent=2)
        # print(f"{self.platform_name}資料已儲存到{self.platform_name}.json")
        return results[:max_results]

async def create_scraper(platform: str, browser: Browser, context: BrowserContext) -> BaseScraper:
    """工廠方法，根據平台名稱創建對應的爬蟲實例。"""
    scrapers = {
        "momo": MomoScraper,
        "pchome": PChomeScraper,
        "yahoo": YahooScraper
    }
    scraper_class = scrapers.get(platform.lower())
    if not scraper_class:
        raise ValueError(f"不支援的平台: {platform}")
    return scraper_class(browser, context)

async def scrape_ecommerce(query: str, platforms: list = None, max_results: int = 30) -> str:
    """爬取多個電子商務平台的產品資料，並返回合併的 JSON 結果。"""
    logger.info(f"開始爬取關鍵字：{query}")
    if platforms is None:
        platforms = ["momo", "pchome", "yahoo"]
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=user_agent)
        try:
            # 並行執行所有平台的爬蟲
            scrapers = [await create_scraper(platform, browser, context) for platform in platforms]
            tasks = [scraper.scrape(query, max_results) for scraper in scrapers]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 合併結果
            combined_results = []
            for platform, result in zip(platforms, results):
                if isinstance(result, Exception):
                    logger.error(f"爬取 {platform} 時發生錯誤: {result}")
                    continue
                combined_results.extend(result)
            
            # 儲存到資料庫
            save_to_db(combined_results, query)
            logger.info(f"已將 {len(combined_results)} 筆商品資料儲存到資料庫")
            
            # 轉換為 JSON
            return json.dumps({"query": query, "results": combined_results}, ensure_ascii=False, indent=2)
        finally:
            await browser.close()

# LangChain Tool
ecommerce_tool = Tool(
    name="EcommerceScraper",
    func=lambda query: asyncio.run(scrape_ecommerce(query)),
    description="從台灣電商平台（Momo、PChome、Yahoo）爬取產品資料。輸入：產品查詢字串（例如「無線滑鼠」）。輸出：包含產品名稱、價格、連結和平台的 JSON 字串。"
)

if __name__ == "__main__":
    query = "洗衣機"
    result = asyncio.run(scrape_ecommerce(query))
    with open("ecommerce_results.json", "w", encoding="utf-8") as f:
        f.write(result)
    print("測試已完成。")
    print(result)
