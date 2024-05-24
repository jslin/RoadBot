from flask import Flask, request, abort
from linebot import LineBotApi
from linebot.webhook import WebhookHandler
#from linebot.v3 import WebhookHandler
from linebot.v3.messaging import ShowLoadingAnimationRequest
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (ApiClient, Configuration, MessagingApi,
                                  ReplyMessageRequest, TextMessage)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.models import *
import os
import requests
import json

app = Flask(__name__)

configuration = Configuration(access_token=os.environ['CHANNEL_ACCESS_TOKEN'])
line_bot_api = LineBotApi(os.environ['CHANNEL_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['CHANNEL_SECRET'])
llm_server_url = os.environ['REMOTE_LLM_SERVER']

def llm_responser(url=llm_server_url, prompt_text=""):
    headers = {
    "Content-Type": "application/json"
    }
    data = {
        "model": "yi:v1.5",
        "prompt": prompt_text,
    #    "format": "json",
        "options": {
            "seed": 42,
            "top_k": 10,
            "top_p": 0.7,
            "temperature": 0.9
        },
        "stream": False
    }
    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code == 200:
        response_text = response.text
        data = json.loads(response_text)
    #    print(data)
        actual_response = data["response"]
#       print(actual_response)
        return_message = actual_response
    else:
#        print(f"Error:{response.status_code} {response.text}")
        retern_message = f"Error:{response.status_code} {response.text}"
    return return_message

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    with ApiClient(configuration) as api_client:
        api_instance = MessagingApi(api_client)
        api_instance.show_loading_animation_with_http_info(
            ShowLoadingAnimationRequest(chatId=event.source.user_id, 
                                        loadingSeconds=5)) # ShowLoadingAnimationRequest
        prompt = event.message.text
        llm_text = llm_responser(llm_server_url, prompt)
        message = TextSendMessage(text=llm_text)
#        line_bot_api.reply_message(event.reply_token, message)
        api_instance.reply_message(ReplyMessageRequest(replyToken=event.reply_token, messages=message))

# 以下程式碼是要給 Render.com 用來自動觸發測試 Webhook，以便持續動作不停機。
@app.route("/healthz", methods=['GET'])
def healthz():
    app.logger.info("Health trigger")
    return 'OK'


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)