from typing import Dict, List, Type
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain.tools import BaseTool
import os

class ProductEntity(BaseModel):
    brand: str
    model: str
    specifications: Dict[str, str]
    categories: List[str]

class NERModule:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=os.environ["GEMINI_API_KEY"],
            temperature=0
        )
        self.parser = PydanticOutputParser(pydantic_object=ProductEntity)
        
        self.prompt = ChatPromptTemplate.from_template(
            """你是一個專業的商品資訊分析專家。
            請從提供的商品標題和描述中提取以下資訊：
            - 品牌名稱  
            - 產品型號
            - 規格資訊
            - 商品類別

            請以結構化 JSON 格式輸出，符合以下格式：
            {{
                "brand": "品牌名稱",
                "model": "型號",
                "specifications": {{
                    "規格名稱": "規格值"
                }},
                "categories": ["類別1", "類別2"]
            }}

            輸入資訊：
            {input}
            """
        )

    async def extract_entities(self, title: str, description: str = "") -> ProductEntity:
        input_text = f"商品標題：{title}\n商品描述：{description}"
        chain = self.prompt | self.llm | self.parser
        result = await chain.ainvoke({"input": input_text})
        return result

# 定義工具的輸入 schema
class NERInput(BaseModel):
    title: str = Field(description="商品的標題")
    description: str = Field(description="商品的描述 (可選)")

# 將 NERModule 包裝成 Langchain 工具
class NERTool(BaseTool):
    name: str = "ner_extractor"
    description: str = "使用 NERModule 從商品標題和描述中提取品牌、型號、規格和類別等資訊。"
    args_schema: Type[BaseModel] = NERInput

    async def _arun(self, title: str, description: str = "") -> str:
        """使用工具"""
        try:
            ner = NERModule()
            result = await ner.extract_entities(title=title, description=description)
            return result.model_dump_json(indent=2) # 返回 JSON 字串
        except Exception as e:
            return f"工具執行錯誤: {e}"

    def _run(self, title: str, description: str = "") -> str:
        """同步方法不使用，因為 extract_entities 是非同步的"""
        raise NotImplementedError("NERTool 不支持同步運行")

# 使用範例
if __name__ == "__main__":
    import asyncio
    
    async def test():
        ner = NERModule()
        result = await ner.extract_entities(
            title="Hitachi 日立- 冷暖變頻左吹式窗型冷氣 RA-22HR 含基本安裝+舊機回收 大型配送",
            # description="最新的 A17 Pro 晶片，48MP 主相機，USB-C 接口，鈦金屬邊框"
        )
        print(result.model_dump_json(indent=2))
    
    asyncio.run(test()) 