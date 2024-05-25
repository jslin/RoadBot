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
model_name = "gemma:7b"

def llm_responser(url=llm_server_url, model_name="gemma:7b", prompt_text=""):
    headers = {
    "Content-Type": "application/json"
    }
    data = {
        "model": model_name,
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
    user_message = event.message.text
    global model_name
    if user_message[:5] == "/help":
        help_message = f'切換模型的指令：\n\n/model 模型名稱\n\n支援的模型名稱\n\nGemma 7B: gemma:7b\n零一萬物: yi:v1.5\nMistral 7B: mistral:7b\n\n目前的模型:{model_name}'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_message)) # 送出回應訊息
    else:
        if user_message[:6] == "/model":
            model_name = user_message.split(" ")[1]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"切換至{model_name}")) # 送出回應訊息
        else:
            with ApiClient(configuration) as api_client:
                api_instance = MessagingApi(api_client)
                api_instance.show_loading_animation_with_http_info(
                    ShowLoadingAnimationRequest(chatId=event.source.user_id, 
                                                loadingSeconds=5)) # ShowLoadingAnimationRequest
                prompt = event.message.text
                llm_text = llm_responser(llm_server_url, model_name=model_name, prompt_text=prompt) # 呼叫大模型
                message = TextSendMessage(text=llm_text) # 將大模型的回應轉成 LINE 訊息格式
                line_bot_api.reply_message(event.reply_token, message) # 送出回應訊息
        #        api_instance.reply_message(ReplyMessageRequest(replyToken=event.reply_token, messages=message))

# 以下程式碼是要給 Render.com 用來自動觸發測試程式是否活著用的，
# 另要需要搭配 uptime.com 的監控服務，以便 webhook 持續動作不停機。
@app.route("/healthz", methods=['GET'])
def healthz():
    app.logger.info("Health trigger")
    return 'OK'


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)