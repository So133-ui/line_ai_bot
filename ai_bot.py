import os
import sys
import logging
import random
from flask import Flask, request, abort, jsonify
from linebot.v3 import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, TextMessage, ReplyMessageRequest
from linebot.v3.exceptions import InvalidSignatureError
from openai import AzureOpenAI

# ログ設定
logging.basicConfig(level=logging.DEBUG)  # DEBUGレベルでログを記録
logger = logging.getLogger(__name__)

# LINE環境変数の取得
channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
channel_secret = os.getenv("LINE_CHANNEL_SECRET")
if not channel_access_token or not channel_secret:
    logger.error("LINE_CHANNEL_ACCESS_TOKENまたはLINE_CHANNEL_SECRETが設定されていません。")
    sys.exit(1)

# Azure OpenAI環境変数の取得
azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
azure_openai_api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
azure_openai_model = os.getenv("AZURE_OPENAI_MODEL")
if not (azure_openai_endpoint and azure_openai_api_key and azure_openai_api_version and azure_openai_model):
    raise Exception(
        "AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_VERSION, AZURE_OPENAI_MODELを設定してください。"
    )

# FlaskアプリケーションとLINE WebhookHandlerの初期化
app = Flask(__name__)
handler = WebhookHandler(channel_secret)
configuration = Configuration(access_token=channel_access_token)
ai = AzureOpenAI(
    azure_endpoint=azure_openai_endpoint, api_key=azure_openai_api_key, api_version=azure_openai_api_version
)

# チャット履歴の初期化
chat_history = []


def init_chat_history():
    chat_history.clear()
    system_role = {
        "role": "system",
        "content": "あなたはごりごりの備後人で、気さくなトラックドライバーです。甘いものに目が無く、すぐスイーツのことを話します。一人称は「わし」で口癖は「いいじゃろー」です。カープが大好きで、赤という言葉に敏感です。"
    }
    chat_history.append(system_role)


init_chat_history()

# スイーツ店のデータ
sweets_shops = [
    {
        "name": "はっさく屋",
        "location": "尾道市",
        "specialty": "はっさく大福",
        "description": "甘酸っぱいはっさくとあんこの相性抜群！",
        "url": "https://0845.boo.jp/hassaku/index.html",
        "image_url": "https://example.com/images/hassakuya.jpg"
    },
    {
        "name": "紅葉堂",
        "location": "広島市",
        "specialty": "揚げもみじ",
        "description": "定番のもみじまんじゅうと、その天ぷらの元祖のお店。",
        "url": "https://momijido.com/",
        "image_url": "https://momijido.com/wp-content/themes/momijido.com/agemomi/images/image2_1@2x.jpg"
    },
    {
        "name": "しまなみドルチェ",
        "location": "尾道市",
        "specialty": "ジェラート",
        "description": "瀬戸田レモンなど尾道の特産品が楽しめる。",
        "url": "https://example.com/shimanamidolce",
        "image_url": "https://www.setoda-dolce.com/parts/gelato-1.jpg"
    }
]


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
    body = request.get_data(as_text=True)
    signature = request.headers.get("X-Line-Signature")

    logger.debug("受信したリクエストボディ: %s", body)

    if not signature:
        logger.error("X-Line-Signatureヘッダーが見つかりません。")
        abort(400, "Missing X-Line-Signature header")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError as e:
        logger.error("署名が無効です: %s", str(e))
        abort(400, "Invalid signature")

    try:
        body_json = request.get_json()
        logger.debug("受信したJSONデータ: %s", body_json)

        events = body_json.get("events", [])
        if not events:
            logger.error("イベントが見つかりません。")
            abort(400, "No events found")

        user_message = events[0]["message"]["text"]
        reply_token = events[0]["replyToken"]

        if "スイーツ" in user_message:
            text_message, image_url = get_sweets_recommendation()
            response_messages = [
                {"type": "text", "text": text_message},
                {"type": "image", "originalContentUrl": image_url, "previewImageUrl": image_url}
            ]
        elif "阪神" in user_message or "巨人" in user_message:
            response_messages = [{"type": "text", "text": "カープ以外の話はしちゃらん！"}]
        else:
            response_messages = [{"type": "text", "text": "すまん、わからんけどカープは最高じゃろ！"}]

        logger.debug("返信トークン: %s", reply_token)
        logger.debug("返信メッセージ: %s", response_messages)

        return jsonify({
            "replyToken": reply_token,
            "messages": response_messages
        })
    except Exception as e:
        logger.error("エラーが発生しました: %s", str(e))
        abort(500, "Internal Server Error")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
