import json
import os
import requests
import boto3
from datetime import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, PushMessageRequest, TextMessage

# 環境変数を取得
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN") # チャネルアクセストークン
LINE_TO_ID                = os.environ.get("LINE_TO_ID")                # 送信先のLINE ID
TARGET_SCRAPING_URL       = os.environ.get("TARGET_SCRAPING_URL")       # スクレイピング対象のURL
DYNAMODB_TABLE_NAME       = os.environ.get("DYNAMODB_TABLE_NAME")       # DynamoDBのテーブル名

def send_line_message(access_token:str, to:str, text:str):
    """LINEメッセージを送信する関数"""
    # Configurationの設定
    line_bot_config = Configuration(access_token=access_token)
    # LINE Messaging APIのクライアントを作成
    with ApiClient(line_bot_config) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.push_message(
            PushMessageRequest(
                to=to,
                messages=[TextMessage(text=text)]
            )
        )

def scrape_latest_update_info(url:str):
    """指定されたURLから最新のアップデート情報をスクレイピングする関数"""
    # URLからHTMLを取得
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    # BeautifulSoupを使ってHTMLを解析
    soup = BeautifulSoup(response.content, "html.parser")
    # 最新のパッチノートを取得
    latest_patch_container = soup.find("div", class_="PatchNotes-live")
    if not latest_patch_container:
        latest_patch_container = soup.find("div", class_="PatchNotes-patch")
    # 最新のパッチノートが見つからない場合は、エラーメッセージを表示
    if latest_patch_container:
        # 日付、タイトル、アンカーIDを取得
        date_element  = latest_patch_container.find("div", class_="PatchNotes-date")
        title_element = latest_patch_container.find("h3", class_="PatchNotes-patchTitle")
        anchor_div    = latest_patch_container.find("div", class_="anchor")
        # 取得した情報を表示
        patch_date      = date_element.text.strip() if date_element else "日付不明"
        patch_title     = title_element.text.strip() if title_element else "タイトル不明"
        patch_anchor_id = anchor_div.get("id") if anchor_div and anchor_div.get("id") else "アンカーID不明"
        # URLを組み立てる
        patch_url = url
        if patch_anchor_id != "アンカーID不明":
            patch_url = f"{url}#{patch_anchor_id}"
        return {
            "date"     : patch_date,
            "title"    : patch_title,
            "anchor_id": patch_anchor_id,
            "url"      : patch_url
        }

def get_previous_patch_info(table_name:str, item_key:str):
    """DynamoDBから前回のパッチ情報を取得する関数"""
    # DynamoDBのテーブルに接続
    table = boto3.resource("dynamodb").Table(table_name)
    # アイテムを取得
    response = table.get_item(Key={"page_identifier": item_key})
    # アイテムが存在しない場合はNoneを返す
    if "Item" not in response:
        return None
    return response["Item"]

def save_patch_info(table_name:str, item_key:str, patch_info:dict):
    """パッチ情報を保存する関数"""
    # DynamoDBのテーブルに接続
    table = boto3.resource("dynamodb").Table(table_name)
    # パッチ情報を保存するためのアイテムを作成
    item_to_save = {"page_identifier": item_key}
    item_to_save.update(patch_info)
    item_to_save["last_checked_timestamp"] = datetime.now(tz=ZoneInfo("Asia/Tokyo")).isoformat()
    print(f"保存するパッチ情報: {item_to_save}")
    # パッチ情報をDynamoDBに保存
    table.put_item(Item=item_to_save)

def lambda_handler(event, context):
    # 環境変数のチェック
    if  not LINE_CHANNEL_ACCESS_TOKEN or\
        not LINE_TO_ID or\
        not TARGET_SCRAPING_URL or\
        not DYNAMODB_TABLE_NAME:
        print("エラー：環境変数が設定されていません．")

    # スクレイピング対象のURLから最新のアップデート情報を取得
    try:
        patch_info = scrape_latest_update_info(url=TARGET_SCRAPING_URL)

    except Exception as e:
        print(f"スクレイピング中にエラーが発生しました: {e}")
        return {"statusCode": 500, "body": json.dumps("スクレイピングに失敗しました．")}

    # 前回のパッチ情報の取得
    try:
        previous_patch_info = get_previous_patch_info(
            table_name=DYNAMODB_TABLE_NAME,
            item_key="latest_patch_info"
        )

    except Exception as e:
        print(f"前回のパッチ情報の取得中にエラーが発生しました: {e}")
        return {"statusCode": 500, "body": json.dumps("前回のパッチ情報の取得に失敗しました．")}

    # 前回のパッチ情報と最新のパッチ情報を比較
    has_changed = False
    if previous_patch_info is None:
        # 初回実行時は前回のパッチ情報が存在しないため、has_changedをTrueに設定
        has_changed = True
    elif  previous_patch_info["date"] != patch_info["date"] or\
        previous_patch_info["anchor_id"] != patch_info["anchor_id"]:
        # 日付またはアンカーIDが異なる場合、has_changedをTrueに設定
        has_changed = True

    if has_changed:
        # パッチ情報の保存
        try:
            save_patch_info(
                table_name=DYNAMODB_TABLE_NAME,
                item_key="latest_patch_info",
                patch_info=patch_info
            )

        except Exception as e:
            print(f"パッチ情報の保存中にエラーが発生しました: {e}")
            return {"statusCode": 500, "body": json.dumps("パッチ情報の保存に失敗しました．")}

        # LINEメッセージの送信
        try:
            send_line_message(
                access_token=LINE_CHANNEL_ACCESS_TOKEN,
                to=LINE_TO_ID,
                text=f"オーバーウォッチに新しいアップデートがあります！"
            )

        except Exception as e:
            print(f"メッセージ送信中にエラーが発生しました: {e}")
            return {"statusCode": 500, "body": json.dumps("メッセージ送信に失敗しました。")}
