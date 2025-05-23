import requests
import json
import time
from typing import List, Dict
import uuid
from urllib.parse import quote
from datetime import datetime

def get_headers() -> Dict:
    """生成模擬的請求頭"""
    return {
        "Accept": "application/json",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"'
    }

def fetch_products(keyword: str, max_products: int = 100) -> List[Dict]:
    """發送請求獲取商品清單，處理分頁"""
    encoded_keyword = quote(keyword)
    base_url = f"https://ecshweb.pchome.com.tw/search/v3.3/all/results"
    headers = get_headers()
    products = []
    page = 1
    
    while True:
        params = {
            'q': keyword,
            'page': page,
            'sort': 'sale/dc',  # 依銷售量排序
            'price': '0-999999'  # 價格範圍
        }
        
        try:
            response = requests.get(base_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if not data.get('prods'):
                print(f"第 {page} 頁無數據，停止爬取")
                break
            
            for item in data['prods']:
                product_info = {
                    "title": item.get("name", ""),
                    "price": float(item.get("price", 0)),
                    "image_url": f"https://cs-a.ecimg.tw{item.get('picB', '')}",
                    "url": f"https://24h.pchome.com.tw/prod/{item.get('Id', '')}",
                    "platform": "PChome"
                }
                products.append(product_info)
            
            # 檢查是否達到最大商品數量
            if len(products) >= max_products:
                # print(f"已獲取 {len(products)} 個商品，達到最大數量限制")
                break
            
            # 檢查是否還有下一頁
            if len(data['prods']) < 20:  # PChome每頁通常顯示20個商品
                print(f"第 {page} 頁僅有 {len(data['prods'])} 個商品，無更多數據")
                break
            
            page += 1
            time.sleep(1)  # 延遲1秒，防止反爬
            
        except requests.RequestException as e:
            print(f"請求第 {page} 頁失敗: {e}")
            break
        except json.JSONDecodeError as e:
            print(f"解析第 {page} 頁JSON失敗: {e}")
            break
    print(f"獲取到 {len(products)} 個PChome商品")
    return products[:max_products]

def crawl_pchome_products(keyword: str, output_file: str = None, max_products: int = 100) -> None:
    """主函數：爬取PChome商品資訊並保存為JSON"""
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
        output_file = f"pchome_{keyword}_{uuid.uuid4().hex}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"結果已保存至 {output_file}")

if __name__ == "__main__":
    # keyword = input("請輸入搜索關鍵字: ")
    crawl_pchome_products("球鞋", max_products=100) 