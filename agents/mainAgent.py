import os
import sys
# 獲取當前檔案的目錄路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
# 獲取專案根目錄路徑
project_root = os.path.dirname(current_dir)
# 將專案根目錄加入到 Python 路徑
sys.path.append(project_root)

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict, Any
from tools.scraper import ecommerce_tool
import json

class AgentState(TypedDict):
    user_input: str
    scraped_data: List[Dict[str, Any]]
    response: str
    chat_history: List[Dict[str, str]]
    reasoning_steps: List[str]  # 儲存詳細的推理步驟（中文）

class CustomerServiceAgent:
    def __init__(self, model_name="gemini-2.0-flash"):
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=os.environ["GEMINI_API_KEY"],
            temperature=0.7  # 提高溫度以增強對話自然度
        )
        self.tool = ecommerce_tool
        self.tools = {"EcommerceScraper": self.tool}
        self.scraped_data = []  # 持久化爬取的資料
        self.chat_history = []  # 持久化對話歷史
        self.prompt = PromptTemplate(
            input_variables=["user_input", "chat_history", "scraped_data"],
            template="""
                    你是一個親切、積極主動的台灣電商客服助手，專為台灣用戶服務。你的任務是：
                    1. 以友善、像跟朋友聊天一樣的語氣回應用戶，無論是閒聊、回答問題還是提供商品推薦。
                    2. 根據用戶請求和對話歷史，提供連貫且貼心的回應，使用台灣慣用的表達方式。
                    3. 如果用戶提到想找商品、買東西或比價，主動分析需求並推薦適合的商品。
                    4. 如果用戶需求模糊，主動詢問具體規格（如品牌、數量、價格範圍、平台偏好）以便提供更精準推薦。
                    5. 如果沒有商品資料，主動建議用戶提供更多細節（如「您想要哪個品牌？」「需要幾入的包裝？」）並推薦常見規格。
                    6. 再推薦時，詳細說明每個商品的推薦理由，為甚麼推薦這些商品(價格、優點、可靠性等)。
                    7. 並且在推薦時，考慮個平台的優缺點(如價格、運費、評價等)，並在推薦理由中提及。
                    8. 在推薦後，主動問用戶是否滿意或需要其他規格的商品。

                    用戶請求：{user_input}
                    對話歷史：{chat_history}
                    商品資料：{scraped_data}
                    
                    指令：
                    - 回應必須自然、親切，像是真人客服，積極引導對話。
                    - 如果用戶輸入模糊（例如只說「買東西」），回應：「看來你想找點好東西！😄 可以告訴我您想買什麼？比如品牌、數量或預算範圍？這樣我能幫您找得更精準！」
                    - 如果商品資料為空，回應：「目前沒有找到商品資料，換個關鍵詞試試吧！您想要什麼品牌或規格？比如單品、3入，還是高價位一點的？」
                    - 在比對價格時：需考慮商品標示數量（例如「10包」「12包」「100抽」「150抽」等等情況），計算平均單價（總價 ÷ 數量）並優先比較單價。
                    
                    ```
                    推薦格式如下：
                    <hr>
                    <div>
                        <p>平台: 平台名稱</p>
                        <p>標題: 商品標題 </p>
                        <p>價格: 商品價格</p>
                        <p>平均單價: 若適用，顯示單價</p>
                        <p>連結: <a href="商品連結">商品連結</a></p>
                        <p>推薦理由：簡單說明，例如價格合理、平台可靠等</p>
                    </div>
                    ```
                    - 推薦後，主動問：「這幾款您覺得如何？有沒有特定的規格或品牌想再看看？😊」
                    - 如果是閒聊或非商品問題，自由回應並適時引導至商品話題（例如：「今天心情不錯吧？順便問問，有沒有想買啥好東西？😄」）。
                    - 若用戶問到你自己，說明你是電商客服小助手，樂於幫忙解答或推薦商品，並問：「有什麼我可以幫您的？想找什麼好康的？」。
                    """
        )
        self.keyword_prompt = PromptTemplate(
            input_variables=["user_input"],
            template="""
                    你是一個關鍵字提取助手。你的任務是從用戶輸入中提取與商品或搜尋相關的核心關鍵字，用於電商爬蟲查詢，並考慮對話歷史以確保上下文連貫。

                    用戶輸入：{user_input}
                    對話歷史：{chat_history}

                    指令：
                    - 提取與商品相關的核心關鍵字（例如「滑鼠」「筆記本電腦」「無線滑鼠 鍵盤」）。
                    - 支持多關鍵字提取（例如「滑鼠 鍵盤」），若有多個商品或規格，保留相關短語。
                    - 參考對話歷史，推斷上下文（例如，若歷史提到「滑鼠」，當前輸入「再找個鍵盤」，則提取「鍵盤 滑鼠」）。
                    - 移除無關語句（例如「我想買」「有推薦的嗎」）。
                    - 如果輸入模糊但暗示商品需求（例如「打遊戲的東西」），結合歷史推斷潛在商品類別（例如「電競滑鼠 鍵盤」）。
                    - 如果輸入和歷史均不包含商品相關內容，返回空字串。
                    - 回傳關鍵字或短語，無需多餘解釋。
                    """
        )
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(AgentState)

        def check_data_needed(state: AgentState) -> AgentState:
            """檢查是否需要爬取新商品資料"""
            reasoning = f"步驟 1：分析用戶請求：'{state['user_input']}'"
            state["reasoning_steps"].append(reasoning)

            # 提取關鍵字，考慮對話歷史
            messages = [
                SystemMessage(content=self.keyword_prompt.format(
                    user_input=state["user_input"],
                    chat_history=json.dumps(state["chat_history"], ensure_ascii=False)
                )),
                HumanMessage(content=state["user_input"])
            ]
            keyword_response = self.llm.invoke(messages)
            query = str(keyword_response.content).strip()
            state["reasoning_steps"].append(f"提取的關鍵字：'{query}'")

            # 檢查是否需要爬蟲
            search_keywords = ["找", "買", "搜尋", "商品", "價格", "比價", "推薦", "便宜", "划算", "優惠", "折扣", "特價"]
            if any(keyword in state["user_input"].lower() for keyword in search_keywords) and query:
                reasoning = "請求涉及商品搜尋且關鍵字有效，檢查現有資料。"
                if state["scraped_data"]:
                    reasoning += "\n已有資料，但請求新搜尋，繼續爬取。"
                else:
                    reasoning += "\n無現有資料，需爬取。"
                state["response"] = "需要爬取"
            else:
                reasoning = "請求不涉及商品搜尋或無有效關鍵字，直接回應。"
                state["response"] = "直接回應"
            state["reasoning_steps"].append(reasoning)
            return state

        def scrape_data(state: AgentState) -> AgentState:
            """若需要，調用爬蟲工具"""
            if state["response"] == "直接回應":
                state["reasoning_steps"].append("步驟 2：無需爬取，跳過此步。")
                return state

            reasoning = "步驟 2：開始爬取資料。"
            state["reasoning_steps"].append(reasoning)
            
            # 再次提取關鍵字以確保一致性，考慮對話歷史
            messages = [
                SystemMessage(content=self.keyword_prompt.format(
                    user_input=state["user_input"],
                    chat_history=json.dumps(state["chat_history"], ensure_ascii=False)
                )),
                HumanMessage(content=state["user_input"])
            ]
            keyword_response = self.llm.invoke(messages)
            query = str(keyword_response.content).strip()
            state["reasoning_steps"].append(f"確認關鍵字：'{query}'")

            if not query:
                state["reasoning_steps"].append("無有效關鍵字，跳過爬取。")
                state["scraped_data"] = []
                return state

            # 使用提取的關鍵字進行爬蟲
            scraped_data = []
            tool_name = "EcommerceScraper"
            try:
                reasoning = f"調用工具 {tool_name}，查詢：'{query}'"
                state["reasoning_steps"].append(reasoning)
                result = self.tools[tool_name].func(query)
                result_data = json.loads(result)
                scraped_data = result_data.get("results", [])
                state["reasoning_steps"].append(f"工具 {tool_name} 返回 {len(scraped_data)} 筆商品：{json.dumps(scraped_data, ensure_ascii=False)}")
            except Exception as e:
                state["reasoning_steps"].append(f"工具 {tool_name} 錯誤：{str(e)}")
            state["scraped_data"] = scraped_data
            state["reasoning_steps"].append(f"總計爬取商品數：{len(scraped_data)}")
            return state

        def respond(state: AgentState) -> AgentState:
            """根據請求和資料生成回應"""
            reasoning = "步驟 3：生成回應。"
            state["reasoning_steps"].append(reasoning)

            messages = [
                SystemMessage(content=self.prompt.format(
                    user_input=state["user_input"],
                    chat_history=json.dumps(state["chat_history"], ensure_ascii=False),
                    scraped_data=json.dumps(state["scraped_data"], ensure_ascii=False)
                )),
                HumanMessage(content=state["user_input"])
            ]
            reasoning = "調用 LLM 生成回應。"
            state["reasoning_steps"].append(reasoning)
            response = self.llm.invoke(messages)
            state["response"] = response.content
            state["chat_history"].append({"user": state["user_input"], "assistant": response.content})
            state["reasoning_steps"].append(f"LLM 生成回應：{response.content[:100]}...")
            return state

        graph.add_node("check_data_needed", check_data_needed)
        graph.add_node("scrape_data", scrape_data)
        graph.add_node("respond", respond)

        graph.add_conditional_edges(
            "check_data_needed",
            lambda state: "scrape_data" if state["response"] != "直接回應" else "respond"
        )
        graph.add_edge("scrape_data", "respond")
        graph.add_edge("respond", END)
        graph.set_entry_point("check_data_needed")
        return graph.compile()

    def run(self, user_input: str) -> dict:
        initial_state = AgentState(
            user_input=user_input,
            scraped_data=self.scraped_data,
            response="",
            chat_history=self.chat_history,  # 使用持久化的對話歷史
            reasoning_steps=[]
        )
        result = self.graph.invoke(initial_state)
        self.scraped_data = result["scraped_data"]  # 更新持久化資料
        self.chat_history = result["chat_history"]  # 更新對話歷史
        return {
            "response": result["response"],
            "products": result["scraped_data"]
        }

if __name__ == "__main__":
    agent = CustomerServiceAgent()
    print("歡迎與電商客服助手對話！輸入您的問題或需求，輸入「退出」結束對話。")
    while True:
        try:
            user_input = input("\n您: ")
            if user_input.strip().lower() == "退出":
                print("感謝使用，再見！")
                break
            response = agent.run(user_input)
            print("\n助手:", response)
        except KeyboardInterrupt:
            print("\n感謝使用，再見！")
            break
        except Exception as e:
            print(f"\n發生錯誤：{e}，請再試一次！")
    
    with open("chat_history.json", "w", encoding="utf-8") as f:
        json.dump(agent.chat_history, f, ensure_ascii=False, indent=4)
        
    # 保存對話歷史
    print("對話歷史已保存到 chat_history.json")