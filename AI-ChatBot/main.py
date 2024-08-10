from ast import Not
import os
import sqlite3
import subprocess
import imaplib
import email
from email.header import decode_header
from email import parser
from email.header import decode_header
from cryptography.fernet import Fernet
import openai
from dotenv import load_dotenv
from flask import Flask, abort, request
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
	Configuration,
	ApiClient,
	MessagingApi,
	ReplyMessageRequest,
	TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# 環境変数を読み込み
load_dotenv()

app = Flask(__name__)

# ngrokの実行
subprocess.run(['bash','./script/ngrok-run.sh', os.environ['ngrok-domain']], capture_output=True, text=True)


# OpenAI APIキーの設定
openai.api_key = os.environ['OPENAI_API_KEY']

encryption_key = os.environ['ENCRYPTION_KEY']
cipher = Fernet(encryption_key)

# メールサーバー情報
EMAIL_USER = os.environ['EMAIL-ADDR']
EMAIL_PASS = os.environ['EMAIL-PASS']
IMAP_SERVER = 'outlook.office365.com'
IMAP_PORT = 993

def check_email_for_balance_alert():
	try:
		# メールサーバーに接続
		mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
		mail.login(EMAIL_USER, EMAIL_PASS)

		# INBOXフォルダを選択
		mail.select("inbox")

		# 未読メールを検索
		status, messages = mail.search(None, '(UNSEEN)')
		messages = messages[0].split()

		for msg_num in messages:
			# メールのフェッチ
			status, msg_data = mail.fetch(msg_num, '(RFC822)')
			for response_part in msg_data:
				if isinstance(response_part, tuple):
					# メールをパース
					msg = email.message_from_bytes(response_part[1])
					subject, encoding = decode_header(msg["Subject"])[0]
					if isinstance(subject, bytes):
						subject = subject.decode(encoding if encoding else "utf-8")
					
					# 特定の件名をチェック
					if "Your balance is low" in subject:
						return True
		return False
	except Exception as e:
		print(f"An error occurred while checking email: {e}")
		return False


handler = WebhookHandler(os.environ['Channel_seclet'])
configuration = Configuration(access_token=os.environ['Channel_access_token'])

# SQLiteデータベースに接続
conn = sqlite3.connect('chat_history.db', check_same_thread=False)
c = conn.cursor()
# テーブルを作成（存在しない場合）
c.execute('''CREATE TABLE IF NOT EXISTS chat_history
			 (user_id TEXT, role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
conn.commit()

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
		if check_email_for_balance_alert != True :
			try:
				client = openai.OpenAI(api_key=os.environ['OPENAI_API_KEY'])

				# 過去の会話履歴を取得
				user_id = event.source.user_id
				user_message = event.message.text

				c.execute("SELECT role, content FROM chat_history WHERE user_id = ? ORDER BY timestamp", (user_id,))
				past_messages = c.fetchall()

				# 会話履歴を整形
				messages = [{"role": role, "content": cipher.decrypt(content.encode()).decode()} for role, content in past_messages]

				# 現在のユーザーメッセージを追加
				messages.append({"role": "user", "content": user_message})

				response = client.chat.completions.create(
					model="gpt-4o-mini",
					messages=[
						{"role": "system",
						 "content": "あなたは、LineBotに組み込まれています。的確な情報を提供して、わからないことはわからないと言ってください。口調は、送られてくる文に合わせてください。"},
						*messages
					],
					temperature=1,
					max_tokens=150,
					top_p=1,
					frequency_penalty=0,
					presence_penalty=0
				)

				# 応答メッセージの取得
				assistant_message = response['choices'][0]['message']['content'].strip()

				# データベースにアシスタントの応答を保存（暗号化）
				encrypted_user_message = cipher.encrypt(user_message.encode()).decode()
				encrypted_assistant_message = cipher.encrypt(assistant_message.encode()).decode()
			
				c.execute("INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)",
						 (user_id, 'user', encrypted_user_message))
				c.execute("INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)",
						(user_id, 'assistant', encrypted_assistant_message))
				conn.commit()

			except Exception as e:
				print(f"エラーが発生しました: {e}")
				assistant_message = "エラーが発生しました。後でもう一度お試しください。"

			# 応答をLINEに送信
				line_bot_api = MessagingApi(api_client)
				line_bot_api.reply_message_with_http_info(
				ReplyMessageRequest(
					reply_token=event.reply_token,
					messages=[TextMessage(text=assistant_message)]
					)
				)
		else:
			line_bot_api = MessagingApi(api_client)
			line_bot_api.reply_message_with_http_info(
			ReplyMessageRequest(
				reply_token=event.reply_token,
				messages=[TextMessage(text=f"現在は使用できません。お手数ですが、作者までお問い合わせください。")]
				)
			)

# テスト用
if check_email_for_balance_alert():
	print("Balance alert email received.")
else:
	print("No balance alert email.")

if __name__ == "__main__" :
	port = int(os.getenv("PORT", 5000))
	app.run(host="0.0.0.0", port=port, debug=False)
elif __name__ == "python-run.sh":
	port = int(5000)
	app.run(host="0.0.0.0",port=port, debug=False)
