import requests
import json
import time
from typing import List, Dict
import uuid
from urllib.parse import quote
from datetime import datetime

def get_headers(keyword: str) -> Dict:
    """生成模擬的請求頭，動態設置referrer並對關鍵字進行URL編碼"""
    encoded_keyword = quote(keyword)
    return {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9,zh-TW;q=0.8,zh;q=0.7",
        "content-type": "application/json",
        "priority": "u=1, i",
        "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "referrer": f"https://tw.buy.yahoo.com/search/product?p={encoded_keyword}"
    }

def fetch_products(keyword: str, max_products: int = 100, page_size: int = 60) -> List[Dict]:
    """發送GraphQL請求，獲取商品清單，處理分頁"""
    url = "https://graphql.ec.yahoo.com/graphql"
    headers = get_headers(keyword)
    products = []
    page = 1
    
    while True:
        # 構建GraphQL請求體
        payload = {
            "variables": {
                "property": "sas",
                "p": keyword,
                "cid": "0",
                "pg": str(page),
                "psz": str(page_size),
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
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # 提取商品數據
            hits = data.get("data", {}).get("getUther", {}).get("hits", [])
            if not hits:
                print(f"第 {page} 頁無數據，停止爬取")
                break
                
            for item in hits:
                product_info = {
                    "title": item.get("ec_title", ""),
                    "price": float(item.get("ec_price", 0)),
                    "image_url": item.get("ec_image", ""),
                    "url": item.get("ec_item_url", ""),
                    "platform": "Yahoo購物"
                }
                products.append(product_info)
            
            # 檢查是否達到最大商品數量
            if len(products) >= max_products:
                # print(f"已獲取 {len(products)} 個商品，達到最大數量限制")
                break
                
            # 若當前頁商品數少於page_size，無更多數據
            if len(hits) < page_size:
                print(f"第 {page} 頁僅 {len(hits)} 個商品，無更多數據")
                break
                
            page += 1
            time.sleep(1)  # 延遲1秒，防止反爬
        except requests.RequestException as e:
            print(f"請求第 {page} 頁失敗: {e}")
            break
    print(f"獲取到 {len(products)} 個Yahoo商品")
    return products[:max_products]  # 確保不超過最大數量

def crawl_yahoo_products(keyword: str, output_file: str = None, max_products: int = 100) -> None:
    """主函數：爬取Yahoo商品資訊並保存為JSON"""
    print(f"開始爬取關鍵字: {keyword}")
    
    # 獲取商品詳情
    products = fetch_products(keyword, max_products)
    print(f"獲取到 {len(products)} 個商品")
    
    if not products:
        print("未找到任何商品")
        return
    
    # 整理輸出數據
    output_data = {
        "keyword": keyword,
        "total_products": len(products),
        "products": products,
        "crawl_time": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # 保存為JSON文件
    if not output_file:
        output_file = f"yahoo_{keyword}_{uuid.uuid4().hex}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"結果已保存至 {output_file}")

if __name__ == "__main__":
    # keyword = input("請輸入搜索關鍵字: ")
    crawl_yahoo_products("球鞋", max_products=100)