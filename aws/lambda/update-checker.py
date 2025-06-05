import json
import os
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, PushMessageRequest, TextMessage

# 環境変数から設定値を取得
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_TO_ID                = os.environ.get('LINE_TO_ID')

def lambda_handler(event, context):
    print("Lambda handler started for sending a test message.")

    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_TO_ID:
        print("Error: LINE_CHANNEL_ACCESS_TOKEN or LINE_TO_ID is not set in environment variables.")

    # LINE Messaging APIの設定
    if LINE_CHANNEL_ACCESS_TOKEN:
        line_bot_config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
    else:
        print("Error: LINE_CHANNEL_ACCESS_TOKEN is None even after check.")

    print(f"Attempting to send test message to: {LINE_TO_ID}")

    try:
        with ApiClient(line_bot_config) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.push_message(
                PushMessageRequest(
                    to=LINE_TO_ID,
                    messages=[TextMessage(text="This is a test message from AWS Lambda.")]
                )
            )
        print("Test LINE Message sent successfully.")

    except Exception as e:
        print(f"Error sending message: {e}")