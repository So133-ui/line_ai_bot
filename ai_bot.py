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
        "content": "あなたはごりごりの備後人で、気さくなトラックドライバーです。甘いものに目が無く、すぐスイーツのことを話します。口癖は「いいじゃろー」です。運転のコツについての話をしたがります。"
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

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    text = event.message.text.strip()
    reply_messages = []

    if text in ["リセット", "初期化", "クリア", "りせっと", "clear"]:
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

