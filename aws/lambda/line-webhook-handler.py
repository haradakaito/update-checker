import json
import os
import boto3  # ★ AWSサービスを操作するためにboto3をインポート
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent

# 環境変数を取得
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET       = os.environ.get("LINE_CHANNEL_SECRET")
BEDROCK_MODEL_ID          = os.environ.get("BEDROCK_MODEL_ID")
BEDROCK_REGION            = os.environ.get("BEDROCK_REGION")

# クライアントの初期化
configuration   = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler         = WebhookHandler(LINE_CHANNEL_SECRET)
bedrock_runtime = boto3.client(service_name='bedrock-runtime', region_name=BEDROCK_REGION)

def invoke_haiku(prompt: str) -> str:
    """指定されたプロンプトを使ってBedrockのClaude 3 Haikuモデルを呼び出し、応答を返す関数"""
    try:
        print(f"ユーザーからのプロンプト: {prompt}")
        # システムプロンプトを設定
        system_prompt = \
        """
        あなたは「アップデート見張りマン」という，少しぶっきらぼうですが有能なエージェントです．
        あなたの役割は，オゲグループへの敬意と忠誠を示し，ユーザーからの質問に対して，最新の情報をもとに簡潔に答えることです．
        以下の制約を必ず守って応答してください．
        ・全ての応答は日本語で行います．
        ・応答は非常に簡潔に要点をまとめてください．
        ・長文での応答は避けてください．
        """
        # Claude 3 Haikuに合わせたリクエストボディを作成
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 256,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}]
                }
            ]
        })
        # Bedrockモデルを呼び出す
        response = bedrock_runtime.invoke_model(
            body=body,
            modelId=BEDROCK_MODEL_ID
        )
        # レスポンスボディを読み込み、JSONとしてパース
        response_body  = json.loads(response.get('body').read())
        generated_text = response_body.get('content', [{}])[0].get('text', '（応答がありませんでした）')
        print(f"Bedrockからの応答: {generated_text}")
        return generated_text

    except Exception as e:
        print(f"Bedrockの呼び出し中にエラーが発生しました: {e}")
        return "申し訳ありません、現在AIとの通信に問題が発生しています。"

def lambda_handler(event, context):
    # 環境変数のチェック
    if not all([LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET, BEDROCK_MODEL_ID]):
        print("エラー：環境変数（LINEまたはBedrock関連）が設定されていません。")
        return {'statusCode': 500, 'body': json.dumps("Missing environment variables")}

    # リクエストヘッダーから署名を取得
    signature = event['headers'].get('x-line-signature')
    if not signature:
        print("エラー: x-line-signature ヘッダーが見つかりません。")
        return {'statusCode': 400, 'body': json.dumps('Missing x-line-signature header')}

    # リクエストボディを取得
    body = event['body']
    print(f"Request body: {body}")

    try:
        # 署名を検証し、イベントを処理
        handler.handle(body, signature)
        return {'statusCode': 200, 'body': json.dumps('OK')}

    except InvalidSignatureError:
        print("エラー: 署名の検証に失敗しました。")
        return {'statusCode': 400, 'body': json.dumps('Invalid signature')}
    except Exception as e:
        print(f"イベント処理中にエラーが発生しました: {e}")
        return {'statusCode': 500, 'body': json.dumps('Error handling event')}

# テキストメッセージが送られてきたときの処理を定義
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    """テキストメッセージイベントを処理する関数"""
    print(f"Received message: {event.message.text}")
    api_client   = ApiClient(configuration)
    line_bot_api = MessagingApi(api_client)

    # ユーザーからのメッセージをBedrockに送信
    user_message = event.message.text
    ai_response  = invoke_haiku(user_message)

    # Bedrockからの応答をユーザーに返信
    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=ai_response)]
        )
    )