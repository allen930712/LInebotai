import os, json, re, traceback, requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv('CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct"

# ========= 工具區 =========
def _norm(s):
    return re.sub(r"\s+", "", str(s)).lower()

def _join(val):
    if isinstance(val, list):
        return "\n".join(map(str, val))
    return str(val)

def load_all_json():
    kb = {}
    data_path = "data"
    for file in os.listdir(data_path):
        if file.endswith(".json"):
            try:
                with open(os.path.join(data_path, file), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    kb.update(data)
            except Exception as e:
                print(f"⚠️ 讀取 {file} 失敗：{e}")
    return kb

# ========= 查詢本地 JSON =========
def find_local_answer(user_text: str):
    kb = load_all_json()
    norm_text = _norm(user_text)

    for topic, info in kb.items():
        kws = info.get("關鍵字", [])
        matched = False

        # 關鍵字比對
        if isinstance(kws, list):
            if any(_norm(kw) in norm_text for kw in kws):
                matched = True
        elif isinstance(kws, dict):
            for arr in kws.values():
                if any(_norm(kw) in norm_text for kw in arr):
                    matched = True
                    break

        # 若主題名稱命中
        if not matched and _norm(topic) in norm_text:
            matched = True

        if not matched:
            continue

        # 命中主題 → 回傳對應欄位
        for key, val in info.items():
            if key == "關鍵字":
                continue
            if _norm(key) in norm_text:
                return f"📘 {topic}｜{key}\n{_join(val)}"

    return None


# ========= Groq =========
memory = {}

def GPT_response(user_id, user_text):
    local = find_local_answer(user_text)
    if local:
        return local

    if user_id not in memory:
        memory[user_id] = []
    memory[user_id].append({"role": "user", "content": user_text})

    context = [{"role": "system", "content": "你是一個親切的 AI 助理，請用繁體中文回覆。"}] + memory[user_id][-10:]

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": GROQ_MODEL, "messages": context, "temperature": 0.8, "max_tokens": 800}
        )
        data = resp.json()
        reply = data["choices"][0]["message"]["content"].strip()
        memory[user_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        print("Groq API 錯誤：", e)
        return "抱歉，我暫時無法處理您的請求。"

# ========= LINE Webhook =========
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    try:
        reply = GPT_response(user_id, user_text)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
    except:
        print(traceback.format_exc())
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='發生錯誤，請稍後再試。'))

if __name__ == "__main__":
    app.run(port=5000)
