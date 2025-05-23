from flask import Flask, render_template, request, jsonify
from agents.mainAgent import CustomerServiceAgent
import os
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

app = Flask(__name__)
agent = None  # 將 agent 設為全域變數

def create_agent():
    global agent
    agent = CustomerServiceAgent()

@app.route('/')
def home():
    create_agent()  # 每次訪問首頁時重置 agent
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    global agent
    if agent is None:  # 如果 agent 不存在，創建一個新的
        create_agent()
        
    user_input = request.json.get('message', '')
    if not user_input:
        return jsonify({'error': '請輸入訊息'}), 400
    
    try:
        result = agent.run(user_input)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    create_agent()  # 初始化 agent
    app.run(debug=True) 