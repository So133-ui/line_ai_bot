import os
import sys

from flask import Flask, request, abort

from linebot.v3 import WebhookHandler

from linebot.v3.webhooks import MessageEvent, TextMessageContent, UserSource
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, TextMessage, ReplyMessageRequest
from linebot.v3.exceptions import InvalidSignatureError

from openai import AzureOpenAI

import random

# get LINE credentials from environment variables
channel_access_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
channel_secret = os.environ["LINE_CHANNEL_SECRET"]

if channel_access_token is None or channel_secret is None:
    print("Specify LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET as environment variable.")
    sys.exit(1)

# get Azure OpenAI credentials from environment variables
azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
azure_openai_api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
azure_openai_model = os.getenv("AZURE_OPENAI_MODEL")

if azure_openai_endpoint is None or azure_openai_api_key is None or azure_openai_api_version is None:
    raise Exception(
        "Please set the environment variables AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and AZURE_OPENAI_API_VERSION."
    )


handler = WebhookHandler(channel_secret)
configuration = Configuration(access_token=channel_access_token)

app = Flask(__name__)
ai = AzureOpenAI(
    azure_endpoint=azure_openai_endpoint, api_key=azure_openai_api_key, api_version=azure_openai_api_version
)


# LINEボットからのリクエストを受け取るエンドポイント
@app.route("/callback", methods=["POST"])
def callback():
   # get X-Line-Signature header value
   signature = request.headers["X-Line-Signature"]
   if signature is None:
       abort(400, "Missing X-Line-Signature header")

   # get request body as text
   body = request.get_data(as_text=True)
   app.logger.info("Request body: " + body)

   #handle webhook body
   try:
       handler.handle(body, signature)
   except InvalidSignatureError as e:
    abort(400, e)

    # デバッグ: 署名を手動で計算
    import hmac
    import hashlib
    import base64


    # デバッグ: 署名を手動で計算
    computed_signature = base64.b64encode(hmac.new(
        channel_secret.encode('utf-8'),
        body.encode('utf-8'),
        hashlib.sha256
    ).digest()).decode('utf-8')

    app.logger.info(f"Computed Signature: {computed_signature}")
    app.logger.info(f"Received Signature: {signature}")

    # 比較
    if not hmac.compare_digest(computed_signature, signature):
         app.logger.error("Signature mismatch")
         abort(400, "Invalid signature")



    app.logger.info(f"Computed Signature: {computed_signature}")
    app.logger.info(f"Received Signature: {signature}")

    # 比較
    if not hmac.compare_digest(computed_signature, signature):
        app.logger.error("Signature mismatch")
        abort(400, "Invalid signature")


   return "OK"



chat_history = []


# 　AIへのメッセージを初期化する関数
def init_chat_history():
    chat_history.clear()
    system_role = {
        "role": "system",
        "content": "あなたはごりごりの備後人の50歳のおじさんで、備後弁を話します。トラックドライバーで、甘いものが大好きです。"
    }
    chat_history.append(system_role)


# 　返信メッセージをAIから取得する関数
def get_ai_response(from_user, text):
    # ユーザのメッセージを記録
    user_msg = {
        "role": "user",
        "content": text,  # ユーザーのメッセージ
    }
    chat_history.append(user_msg)

    # AIのパラメータ
    parameters = {
        "model": azure_openai_model,  # AIモデル
        "max_tokens": 100,  # 返信メッセージの最大トークン数
        "temperature": 0.5,  # 生成の多様性（0: 最も確実な回答、1: 最も多様な回答）
        "frequency_penalty": 0,  # 同じ単語を繰り返す頻度（0: 小さい）
        "presence_penalty": 0,  # すでに生成した単語を再度生成する頻度（0: 小さい）
        "stop": ["\n"],
        "stream": False,
    }

    # AIから返信を取得
    ai_response = ai.chat.completions.create(messages=chat_history, **parameters)
    res_text = ai_response.choices[0].message.content

    # AIの返信を記録
    ai_msg = {
        "role": "assistant",
        "content": [
            {"type": "text", "text": res_text},
        ],
    }
    chat_history.append(ai_msg)
    return res_text


# 　返信メッセージを生成する関数
def generate_response(from_user, text):
    res = []
    if text in ["リセット", "初期化", "クリア", "reset", "clear"]:
        # チャット履歴を初期化
        init_chat_history()
        res = [TextMessage(text="チャットをリセットしました。")]
    else:
        # AIを使って返信を生成
        res = [TextMessage(text=get_ai_response(from_user, text))]
    return res


# メッセージを受け取った時の処理
@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    # 送られてきたメッセージを取得
    text = event.message.text

    # 返信メッセージの送信
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        res = []
        if isinstance(event.source, UserSource):
            # ユーザー情報が取得できた場合
            profile = line_bot_api.get_profile(event.source.user_id)
            # 返信メッセージを生成
            res = generate_response(profile.display_name, text)
        else:
            # ユーザー情報が取得できなかった場合
            # fmt: off
            # 定型文の返信メッセージ
            res = [
                TextMessage(text="ユーザー情報を取得できませんでした。"),
                TextMessage(text=f"メッセージ：{text}")
            ]
            # fmt: on

        # メッセージを送信
        line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=event.reply_token, messages=res))
# 応答テンプレート
responses = {
    "greeting": [
        "おお、元気しとるんかい！今日はトラックの運転で疲れたけえ、甘いもん食べたくてたまらんわ！",
        "おお、来たんか！トラックで運びよったらええ甘いもん見つけたんじゃが、お前も食べるか？"
    ],
    "farewell": [
        "ほいじゃの、わしもトラックで次の現場行かにゃあけんけえ！また来いや！",
        "おお、また話に来いよ！今度は新しいケーキの話でもしようや！"
    ],
    "default": [
        "なんじゃそれ、わしのトラックとどっちがデカいか言うてみい！",
        "はあ？甘いもんの話ならなんぼでも聞くで！それ以外は適当に言うときんさい！",
        "ほうほう、それでお前も甘いもん好きなんか？"
    ]
}

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text.lower()
    reply_message = ""

    # 応答ロジック
    if "こんにちは" in user_message or "やっほー" in user_message:
        reply_message = random.choice(responses["greeting"])
    elif "さようなら" in user_message or "バイバイ" in user_message:
        reply_message = random.choice(responses["farewell"])
    elif "甘いもの" in user_message or "スイーツ" in user_message:
        reply_message = "おお！甘いもんの話なら任せとけ！最近はクリームたっぷりのケーキにハマっとるんじゃ！"
    else:
        reply_message = random.choice(responses["default"])




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
