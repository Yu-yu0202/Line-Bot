import os
import requests
import openai
from dotenv import load_dotenv
from flask import Flask, abort, request
from linebot.v3.webhook import (
	WebhookHandler
)
from linebot.v3.exceptions import (
	InvalidSignatureError
)
from linebot.v3.messaging import (
	Configuration,
	ApiClient,
	MessagingApi,
	ReplyMessageRequest,
	TextMessage
)
from linebot.v3.webhooks import (
	MessageEvent,
	TextMessageContent
)
load_dotenv()

app = Flask(__name__)
client = openai.OpenAI()

handler = WebhookHandler(os.environ['Channel_seclet'])
configuration = Configuration(access_token=os.environ['Channel_access_token'])


@app.route("/callback", methods=['POST'])
def callback():
	# get X-Line-Signature header value
	signature = request.headers['X-Line-Signature']

	# get request body as text
	body = request.get_data(as_text=True)
	app.logger.info("Request body: " + body)

	# handle webhook body
	try:
		handler.handle(body, signature)
	except InvalidSignatureError:
		app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
		abort(400)

	return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
	with ApiClient(configuration) as api_client:
		#event.message.text,msg
		# OpenAIのAPIキーを環境変数から設定します
		openai.api_key = os.environ['OPENAI_API_KEY']

		try:
			client = openai.OpenAI(api_key=os.environ['OPENAI_API_KEY'])

			response = client.chat.completions.create(
				model="gpt-4o-mini",
				messages=[
					{
						"role": "system",
						"content": "あなたは、LineBotに組み込まれています。的確な情報を提供して、わからないことはわからないと言ってください。口調は、送られてくる文に合わせてください。"
					},
					{
						"role": "user",
						"content": event.message.text
					}
				],
				temperature=1,
				max_tokens=150,
				top_p=1,
				frequency_penalty=0,
				presence_penalty=0
			)

			# 応答メッセージの取得
			msg = response['choices'][0]['message']['content'].strip()
		except Exception as e:
			print(f"エラーが発生しました: {e}")
			msg = "エラーが発生しました。後でもう一度お試しください。"
		
		line_bot_api = MessagingApi(api_client)
		line_bot_api.reply_message_with_http_info(
			ReplyMessageRequest(
				reply_token=event.reply_token,
				messages=[TextMessage(text=msg)]
			)
		)



if __name__ == "__main__":
	port = int(os.getenv("PORT", 5000))
	app.run(host="0.0.0.0", port=port, debug=False)
