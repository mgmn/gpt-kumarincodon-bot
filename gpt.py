#!/usr/bin/env python3
from mastodon import Mastodon, StreamListener
import sqlite3
from contextlib import closing
import openai
import os
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
import schedule
import datetime
import time
import string_util
from context_splitter import split_context

# 返答の1ポストあたりの最大の文字数
max_chars = 450

# ポスティング間隔 (s)
wait_to_next_post = 5

# 1日の上限の文字数
str_limit = 100000

# 会話履歴の最大数
# gpt-3.5のコンテキスト上限は 4096 tokens
# 日本語は 1字 1 token 扱いなので、お互い500字で話し合った場合、4往復を超えたあたりで上限に達し InvalidRequestError になる
prompts_limit = 8

# 公開範囲
post_visibility = "unlisted"

# リモートユーザーとの会話を許可する
allow_remote = False

# 初期プロンプト
init_prompt = [
    {"role": "system", "content": "You are a helpful assistant and regular Mastodon user."},
    {"role": "system", "content": "You usually talk in formal Japanese but you are friendly at heart and may also use emojis."},
    {"role": "system", "content": "You have many interests and love talking to people."}
]

load_dotenv()

openai.api_key = os.environ["OPENAI_API_KEY"]

# データベース名
dbname = "gpt.db"

def job():
    with closing(sqlite3.connect(dbname)) as conn:
        c = conn.cursor()
        sql = "update counts set str_count = 0"
        c.execute(sql)
        print("str_countを0にリセットしました")
        print(datetime.datetime.now())

def db_str_count_reset():
    schedule.every().day.at("00:00").do(job)
    while True:
        schedule.run_pending()
        time.sleep(60)

class Stream(StreamListener):
    def __init__(self):
        super(Stream, self).__init__()

    def on_notification(self,notif): #通知が来た時に呼び出されます
        if notif['type'] == 'mention': #通知の内容がリプライかチェック
            content = notif['status']['content'] #リプライの本体です
            id = notif['status']['account']['username']
            acct = notif['status']['account']['acct']
            display_name = notif['status']['account']['display_name']
            st = notif['status']
            main(content, st, id, acct, display_name)

def main(content, st, id, acct, display_name):

    if not allow_remote and id != acct:
        reply_text = "私はリモートユーザーとの会話は許可されていないのです。申し訳ありません。"

        mastodon.status_reply(st,
                reply_text,
                id,
                visibility=post_visibility)
        return

    global DBFlag
    global keywordMemory
    global dbname
    global keywordAuthor
    print(content)

    req = string_util.remove_first_accts_id(string_util.remove_tags(content))
    print(req)

    str_count = -1
    prompt = init_prompt.copy()
    db_prompt = []

    with closing(sqlite3.connect(dbname)) as conn:
        c = conn.cursor()

        try:
            create_count_table = "CREATE TABLE IF NOT EXISTS counts (acct, str_count, PRIMARY KEY(acct))"
            create_prompt_table = "CREATE TABLE IF NOT EXISTS prompts (seq INTEGER PRIMARY KEY AUTOINCREMENT, acct, role, prompt)"
            create_prompt_index = "CREATE INDEX IF NOT EXISTS ix_acct ON prompts (acct)"
            c.execute(create_count_table)
            c.execute(create_prompt_table)
            c.execute(create_prompt_index)
        except Exception as e:
            print('=== エラー@create_*_table ===')
            print('type:' + str(type(e)))
            print('args:' + str(e.args))
            print('e自身:' + str(e))
            return

        try:
            sql_count = "SELECT str_count FROM counts WHERE acct = ?"
            words_count = (acct,)
            result_count = c.execute(sql_count, words_count)
            for row in result_count:
                if row[0] != "":
                    str_count = row[0]
            print(str_count)
        except Exception as e:
            print('=== エラー@sql_count ===')
            print('type:' + str(type(e)))
            print('args:' + str(e.args))
            print('e自身:' + str(e))
            return

        if str_count != -1:
            # 1日に会話できる上限を超えていた場合
            # メッセージを表示して処理を終わる
            if len(req) + str_count > str_limit:
                reply_text = "1日に会話できる量の上限を超えています。"
                reply_text += "日本時間の0時を過ぎるとリセットされますので"
                reply_text += "また明日、たくさんお話ししましょう！"

                mastodon.status_reply(st,
                        reply_text,
                        id,
                        visibility=post_visibility)
                return
        else:
            # 初回登録
            str_count = 0

        sql_prompt = "SELECT role, prompt FROM prompts WHERE acct = ?"
        words_prompt = (acct,)
        result_prompt = c.execute(sql_prompt, words_prompt)
        for row in result_prompt:
            if row[0] != "":
                db_prompt.append({"role": row[0], "content": row[1]})

    request_message = {"role": "user", "content": req}
    response_message = {}

    prompt.extend(db_prompt)
    prompt.append(request_message)

    print(prompt)
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=prompt
        )
        response_message = response.choices[0].message
        print(f"{response_message['role']}: {response_message['content']}")

    except Exception as e:
        print('=== エラー内容 ===')
        print('type:' + str(type(e)))
        print('args:' + str(e.args))
        print('e自身:' + str(e))
        try:
            reply = "現在 OpenAI の API サーバー側で"
            reply += "問題が発生しているようです。"
            reply += "しばらく時間を置いてから"
            reply += "あらためて話しかけてください。申し訳ありません。"
            mastodon.status_reply(st,
                    reply,
                    id,
                    visibility=post_visibility)
            return
        except Exception as e:
            print('=== エラー内容 ===')
            print('type:' + str(type(e)))
            print('args:' + str(e.args))
            print('e自身:' + str(e))
            return

    responses = split_context(string_util.escape_acct_at(response_message.content), max_chars)

    try:
        chain_reply(responses, st)
    except Exception as e:
        print('=== エラー内容 ===')
        print('type:' + str(type(e)))
        print('args:' + str(e.args))
        print('e自身:' + str(e))
        return

    with closing(sqlite3.connect(dbname)) as conn:
        c = conn.cursor()

        try:
            sql_insert_count = "INSERT OR REPLACE INTO counts (acct, str_count) values (?,?)"
            str_count = str_count + len(req)
            words_insert_count = (acct, str_count)
            c.execute(sql_insert_count, words_insert_count)
            print(f"str_count: {str_count}")

            sql_insert_prompt = "INSERT INTO prompts (acct, role, prompt) values (?,?,?)"
            words_insert_request_prompt = (acct, request_message["role"], request_message["content"])
            c.execute(sql_insert_prompt, words_insert_request_prompt)
            words_insert_response_prompt = (acct, response_message["role"], response_message["content"])
            c.execute(sql_insert_prompt, words_insert_response_prompt)

            conn.commit()
            print("prompts commit done")

        except Exception as e:
            print('=== エラー@prompts commit ===')
            print('type:' + str(type(e)))
            print('args:' + str(e.args))
            print('e自身:' + str(e))

        try:
            # 会話履歴の上限を超えてたら古いものから削除する
            sql_rowcount_prompt = "SELECT COUNT(seq) FROM prompts WHERE acct = ?"
            words_rowcount_prompt = (acct,)
            c.execute(sql_rowcount_prompt, words_rowcount_prompt)
            prompts_count = c.fetchone()[0]
            print(f"prompts_count: {prompts_count}")

            if prompts_count > prompts_limit:
                print(f"prompts reduce {prompts_count - prompts_limit} rows")
                sql_reduce_prompt = """DELETE FROM prompts WHERE seq IN (
                    SELECT seq FROM prompts WHERE acct = ? ORDER BY seq LIMIT ?)"""
                words_reduce_prompt = (acct, prompts_count - prompts_limit)
                c.execute(sql_reduce_prompt, words_reduce_prompt)
                conn.commit()
                print("prompts reduce done")

        except Exception as e:
            print('=== エラー@reduce promppts ===')
            print('type:' + str(type(e)))
            print('args:' + str(e.args))
            print('e自身:' + str(e))

def chain_reply(responses, reply_to):
    recent_status = reply_to
    for response in responses:
        recent_status = mastodon.status_reply(
                    recent_status,
                    response,
                    id,
                    visibility=post_visibility)
        time.sleep(wait_to_next_post)

def mastodon_exe():
    print("起動しました")
    mastodon.stream_user(Stream()) #ストリームの起動

mastodon = Mastodon(access_token = 'gptchan_clientcred.txt')

with ThreadPoolExecutor(max_workers=2, thread_name_prefix="thread") as executor:
    executor.submit(db_str_count_reset)
    executor.submit(mastodon_exe)

