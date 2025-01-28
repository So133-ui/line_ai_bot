import os
import sys
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent, UserSource
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, TextMessage, ReplyMessageRequest
from linebot.v3.exceptions import InvalidSignatureError
from openai import AzureOpenAI
import random

# Get LINE credentials from environment variables
channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
channel_secret = os.getenv("LINE_CHANNEL_SECRET")
if not channel_access_token or not channel_secret:
    print("Specify LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET as environment variables.")
    sys.exit(1)

# Get Azure OpenAI credentials from environment variables
azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
azure_openai_api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
azure_openai_model = os.getenv("AZURE_OPENAI_MODEL")
if not (azure_openai_endpoint and azure_openai_api_key and azure_openai_api_version and azure_openai_model):
    raise Exception(
        "Please set the environment variables AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_VERSION, and AZURE_OPENAI_MODEL."
    )

# Initialize Flask app and LINE WebhookHandler
app = Flask(__name__)
handler = WebhookHandler(channel_secret)
configuration = Configuration(access_token=channel_access_token)
ai = AzureOpenAI(
    azure_endpoint=azure_openai_endpoint, api_key=azure_openai_api_key, api_version=azure_openai_api_version
)

# Initialize chat history
chat_history = []


def init_chat_history():
    chat_history.clear()
    system_role = {
        "role": "system",
        "content": "あなたはごりごりの備後人で、気さくなトラックドライバーです。甘いものに目が無く、すぐスイーツのことを話します。一人称は「わし」で口癖は「いいじゃろー」です。カープが大好きで、赤という言葉に敏感です。"
    }
    chat_history.append(system_role)

init_chat_history()

# Function to get AI response
def get_ai_response(text):
    user_msg = {"role": "user", "content": text}
    chat_history.append(user_msg)

    parameters = {
        "model": azure_openai_model,
        "max_tokens": 100,
        "temperature": 0.5,
        "frequency_penalty": 0,
        "presence_penalty": 0,
        "stop": ["\n"],
        "stream": False,
    }

    ai_response = ai.chat.completions.create(messages=chat_history, **parameters)
    res_text = ai_response.choices[0].message["content"]

    ai_msg = {"role": "assistant", "content": res_text}
    chat_history.append(ai_msg)
    return res_text

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    if not signature:
        abort(400, "Missing X-Line-Signature header")

    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400, "Invalid signature")

    return "OK"

#「広島のスイーツ」に応答
sweets_shops = [
    {
        "name": "はっさく屋",
        "location": "尾道市",
        "specialty": "はっさく大福",
        "description": "甘酸っぱいはっさくとあんこの相性抜群！",
        "url": "https://0845.boo.jp/hassaku/index.html",
        "image_url": "https://example.com/images/hassakuya.jpg"  # 画像URLを追加
    },
    {
        "name": "紅葉堂",
        "location": "広島市",
        "specialty": "揚げもみじ",
        "description": "定番のもみじまんじゅうと、その天ぷらの元祖のお店。",
        "url": "https://momijido.com/",
        "image_url": "https://momijido.com/wp-content/themes/momijido.com/agemomi/images/image2_1@2x.jpg"
    },
    {   "name": "しまなみドルチェ",
        "location": "尾道市",
        "specialty": "ジェラート",
        "description": "瀬戸田レモンなど尾道の特産品が楽しめる。",
        "url": "https://example.com/shimanamidolce",
        "image_url": "https://www.setoda-dolce.com/parts/gelato-1.jpg"
        }
    ]

import random
from flask import Flask, request, jsonify

app = Flask(__name__)

def get_sweets_recommendation():
    shop = random.choice(sweets_shops)
    text_message = (
        f"ほいじゃ、広島でおすすめのスイーツ屋さんを教えちゃるわ！\n\n"
        f"🏠 {shop['name']}（{shop['location']}）\n"
        f"🍰 名物: {shop['specialty']}\n"
        f"✨ {shop['description']}\n"
        f"もっと見たいんなら: {shop['url']}"
    )
    return text_message, shop["image_url"]

@app.route("/callback", methods=["POST"])
def callback():
    user_message = request.json.get("events")[0]["message"]["text"]

    if "スイーツ" in user_message:
        text_message, image_url = get_sweets_recommendation()
        response_messages = [
            {"type": "text", "text": text_message},  # テキストメッセージ
            {"type": "image", "originalContentUrl": image_url, "previewImageUrl": image_url}  # 画像メッセージ
        ]
    if "阪神" or "巨人" in user_message:
        response_messages = "カープ以外の話はしちゃらん"


    return jsonify({
        "replyToken": request.json.get("events")[0]["replyToken"],
        "messages": response_messages })


if __name__ == "__main__":
    app.run(debug=True)



@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    text = event.message.text.strip()
    reply_messages = []

    if text in ["リセット", "初期化", "クリア", "reset", "clear"]:
        init_chat_history()
        reply_messages.append(TextMessage(text="チャットをリセットしました。"))
    else:
        ai_response = get_ai_response(text)
        reply_messages.append(TextMessage(text=ai_response))

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(reply_token=event.reply_token, messages=reply_messages)
        )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)


