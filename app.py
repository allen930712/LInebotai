# 匯入必要的函式庫
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    PostbackEvent, MemberJoinedEvent
)

import tempfile, os
import datetime
import requests
import json
import traceback
from dotenv import load_dotenv

# 載入 .env 環境變數
load_dotenv()

# 建立 Flask 應用
app = Flask(__name__)
static_tmp_path = os.path.join(os.path.dirname(__file__), 'static', 'tmp')

# 設定 LINE Bot API 與 Handler
line_bot_api = LineBotApi(os.getenv('CHANNEL_ACCESS_TOKEN'))  # 從環境變數讀取 Channel Access Token
handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))         # 從環境變數讀取 Channel Secret

# 設定 Groq API Key（從環境變數讀取）
GROQ_API_KEY = os.getenv('GROQ_API_KEY')                      # 確保你在 .env 中設定 GROQ_API_KEY
GROQ_MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct"                   # 模型名稱（可根據需求更改）

# Groq API 回傳函式
def GPT_response(text):
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": "請用繁體中文回答問題。"},
                {"role": "user", "content": text}
            ],
            "temperature": 1.0,
            "max_tokens": 5000
        }
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        print("Groq API 回傳內容：", result)

        # 回傳模型生成的回應
        return result['choices'][0]['message']['content'].strip()

    except Exception as e:
        print("Groq API 錯誤：", e)
        return "抱歉，我暫時無法處理您的請求。"


# 監聽所有來自 /callback 的 POST 請求
@app.route("/callback", methods=['POST'])
def callback():
    # 取得 LINE 簽章
    signature = request.headers['X-Line-Signature']
    # 取得請求內容
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    # 處理 LINE webhook
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# 處理收到的文字訊息事件
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text
    try:
        GPT_answer = GPT_response(msg)
        print("AI 回覆：", GPT_answer)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(GPT_answer))
    except:
        print(traceback.format_exc())
        line_bot_api.reply_message(event.reply_token, TextSendMessage('發生錯誤，請稍後再試或檢查 Groq API 金鑰。'))

# 處理 Postback 事件
@handler.add(PostbackEvent)
def handle_postback(event):
    print("Postback 資料：", event.postback.data)

# 處理新成員加入群組事件
@handler.add(MemberJoinedEvent)
def welcome(event):
    uid = event.joined.members[0].user_id
    gid = event.source.group_id
    profile = line_bot_api.get_group_member_profile(gid, uid)
    name = profile.display_name
    message = TextSendMessage(text=f'{name}，歡迎加入群組！')
    line_bot_api.reply_message(event.reply_token, message)

# 啟動伺服器
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
