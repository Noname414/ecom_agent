import requests
import json
import time
from typing import List, Dict
import uuid
from urllib.parse import quote  # 新增：用於URL編碼

def get_headers(keyword: str) -> Dict:
    """生成模擬的請求頭，動態設置referer並對關鍵字進行URL編碼"""
    encoded_keyword = quote(keyword)  # 將關鍵字進行URL編碼，例如「天使」變為「%E5%A4%A9%E4%BD%BF」
    return {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/x-www-form-urlencoded",
        "referer": f"https://www.ruten.com.tw/find/?q={encoded_keyword}",
        "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    }

def fetch_product_ids(keyword: str, max_products: int = 60) -> List[str]:
    """發送第一個fetch請求，獲取商品ID清單，處理分頁"""
    url = "https://rtapi.ruten.com.tw/api/search/v3/index.php/core/prod"
    headers = get_headers(keyword)
    all_ids = []
    offset = 1
    limit = 60
    
    while True:
        params = {
            "q": keyword,
            "type": "direct",
            "sort": "rnk/dc",
            "limit": limit,
            "offset": offset
        }
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # 提取商品ID
            ids = [item["Id"] for item in data.get("Rows", [])]
            all_ids.extend(ids)
            
            # 檢查是否達到最大商品數量
            if len(all_ids) >= max_products:
                # print(f"已獲取 {len(all_ids)} 個商品ID，停止請求")
                break 
            total_rows = data.get("TotalRows", 0)
            
            # 檢查是否還有更多數據
            if offset + limit > total_rows or not ids:
                break
                
            offset += len(ids)
            # time.sleep(1)  # 延遲1秒，防止反爬
        except requests.RequestException as e:
            print(f"第一個請求失敗: {e}")
            break
    
    return list(set(all_ids))  # 去重

def fetch_product_details(product_ids: List[str], keyword: str, batch_size: int = 50) -> List[Dict]:
    """發送第二個fetch請求，批量獲取商品詳情"""
    url = "https://rtapi.ruten.com.tw/api/prod/v2/index.php/prod"
    headers = get_headers(keyword)
    products = []
    
    for i in range(0, len(product_ids), batch_size):
        batch_ids = product_ids[i:i + batch_size]
        id_string = ",".join(batch_ids)
        params = {"id": id_string}
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # 解析商品詳情
            for item in data:
                product_info = {
                    "title": item.get("ProdName", ""),
                    "price": float(item.get("PriceRange", [0, 0])[0]),  # 使用價格範圍的最低價
                    "image_url": f"https://a.rimg.com.tw{item.get('Image', '')}",
                    "url": f"https://www.ruten.com.tw/item/show?{item.get('ProdId', '')}",
                    "platform": "露天拍賣"
                }
                products.append(product_info)
            
            # time.sleep(1)  # 延遲1秒
        except requests.RequestException as e:
            print(f"第二個請求失敗 (批次 {i//batch_size + 1}): {e}")
    
    return products

def fetch_products(keyword: str, max_products: int = 100) -> List[Dict]:
    """主函數：爬取露天商品資訊並保存為JSON"""
    print(f"開始爬取關鍵字: {keyword}")
    
    # 第一步：獲取商品ID
    product_ids = fetch_product_ids(keyword, max_products)
    # print(f"獲取到 {len(product_ids)} 個商品ID")

    # 第二步：獲取商品詳情
    products = fetch_product_details(product_ids, keyword)
    # print(f"獲取到 {len(products)} 個商品詳情")
    print(f"獲取到 {len(products)} 個露天商品")
    return products[:max_products]


def crawl_ruten_products(keyword: str, output_file: str = None, max_products: int = 100) -> None:
    """主函數：爬取露天商品資訊並保存為JSON"""
    print(f"開始爬取關鍵字: {keyword}")
    
    # 第一步：獲取商品ID
    product_ids = fetch_product_ids(keyword,max_products)
    print(f"獲取到 {len(product_ids)} 個商品ID")
    
    if not product_ids:
        print("未找到任何商品")
        return
    
    # 第二步：獲取商品詳情
    products = fetch_product_details(product_ids, keyword)
    print(f"獲取到 {len(products)} 個商品詳情")
    
    # 第三步：整理輸出數據
    output_data = {
        "keyword": keyword,
        "total_products": len(products),
        "products": products,
        "crawl_time": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # 保存為JSON文件
    if not output_file:
        output_file = f"ruten_{keyword}_{uuid.uuid4().hex}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"結果已保存至 {output_file}")

if __name__ == "__main__":
    # keyword = input("請輸入搜索關鍵字: ")
    crawl_ruten_products("球鞋", max_products=100)