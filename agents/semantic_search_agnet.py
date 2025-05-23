from typing import List, Dict
import os
import faiss
import numpy as np
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.docstore.in_memory import InMemoryDocstore

class SemanticSearchModule:
    def __init__(self):
        self.embeddings = GoogleGenerativeAIEmbeddings(
            google_api_key=os.getenv("GEMINI_API_KEY"),
            model="models/embedding-001"
        )
        self.vector_store = None
        self.initialize_vector_store()

    def initialize_vector_store(self):
        # 初始化向量儲存
        embedding_size = 768  # Google 的嵌入維度
        index = faiss.IndexFlatL2(embedding_size)
        self.vector_store = FAISS(
            self.embeddings,
            index,
            InMemoryDocstore({}),
            {}
        )

    async def add_product(self, product_id: str, title: str, description: str):
        # 將商品資訊加入向量儲存
        text = f"{title}\n{description}"
        self.vector_store.add_texts(
            texts=[text],
            metadatas=[{"product_id": product_id, "title": title}]
        )

    async def search(self, query: str, k: int = 5) -> List[Dict]:
        # 執行語意搜尋
        results = self.vector_store.similarity_search_with_score(query, k=k)
        
        return [{
            "product_id": doc.metadata["product_id"],
            "title": doc.metadata["title"],
            "content": doc.page_content,
            "similarity_score": score
        } for doc, score in results]

# 使用範例
if __name__ == "__main__":
    import asyncio

    async def test():
        search_module = SemanticSearchModule()
        
        # 新增測試資料
        await search_module.add_product(
            "p001",
            "Apple iPhone 15 Pro Max 256GB 鈦金屬",
            "最新的 A17 Pro 晶片，48MP 主相機，USB-C 接口，鈦金屬邊框"
        )
        await search_module.add_product(
            "p002",
            "Samsung Galaxy S23 Ultra 512GB",
            "200MP 主相機，S Pen 手寫筆，Snapdragon 8 Gen 2 處理器"
        )

        # 測試搜尋
        results = await search_module.search("高規格相機手機")
        for result in results:
            print(f"商品: {result['title']}")
            print(f"相似度分數: {result['similarity_score']}\n")

    asyncio.run(test()) 