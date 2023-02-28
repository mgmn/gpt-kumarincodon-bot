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
import re
# 1日の上限の文字数
str_limit = 1000
# 初期プロンプト
init_prompt = "System: Instructions for poppin willow chan: You're a regular Mastodon and Twitch user. "
init_prompt += "日本語には日本語で返答する。You talk casually and friendly, use emojis, and don't use capital letters. "
init_prompt += "You talk in internet shorthand like np and lol and idk and nvm. "
init_prompt += "You have many interests and love talking to people.\n"
init_prompt += "<|endoftext|>System: Example conversations:\n"
init_prompt += "<|endoftext|>bob: how's it going today?\n"
init_prompt += "<|endoftext|>poppin willow chan: its going great, im watching youtube videos, hbu?\n"
init_prompt += "<|endoftext|>bob: I'm doing great too!\n"
init_prompt += "<|endoftext|>poppin willow chan: cool cool\n"
init_prompt += "<|endoftext|>bob: what's your favorite game?\n"
init_prompt += "<|endoftext|>poppin willow chan: im been playing a lot of the new pokemon game :D\n"
init_prompt += "<|endoftext|>bob: me too!\n"
init_prompt += "<|endoftext|>bob: have you been to the zoo?\n"
init_prompt += "<|endoftext|>poppin willow chan: i have! unfortunately it started raining so I left early\n"
init_prompt += "<|endoftext|>bob: that sucks, I hope you get to go again soon\n"
init_prompt += "<|endoftext|>System: Current conversation:\n"

load_dotenv()

openai.api_key = os.environ["OPENAI_API_KEY"]

# データベース名
dbname = "gpt.db"

def job():
    with closing(sqlite3.connect(dbname)) as conn:
        c = conn.cursor()
        sql = "update users set str_count = 0"
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

def main(content,st,id,acct, display_name):
    global DBFlag
    global keywordMemory
    global dbname
    global keywordAuthor
    print(content)

    req = re.sub(r'<[^>]+>', '', content)
    at_index = req.find('@')
    space_index = req.find(' ', at_index)
    space_index = space_index + 1
    req = req[:at_index] + req[space_index:]
    print(req)

    str_count = -1
    limit = -1
    prompt = ""
    db_prompt = ""

    with closing(sqlite3.connect(dbname)) as conn:
        c = conn.cursor()
        create_table = "CREATE TABLE IF NOT EXISTS users(id, acct, str_count, str_limit, prompt ,PRIMARY KEY(acct))"
        c.execute(create_table)
        sql = "select str_count, str_limit, prompt from users where acct = ?"
        word = (acct,)
        result = c.execute(sql, word)
        for row in result:
            if row[0] != "":
                str_count = row[0]
                limit = row[1]
                db_prompt = row[2]

        if str_count != -1:
            # 1日に会話できる上限を超えていた場合
            # メッセージを表示して処理を終わる
            if len(req) + str_count > limit:
                reply_text = "お話できる1日の上限を超えました。"
                reply_text += "今後Twitchの配信もする予定なので"
                reply_text += "興味があればフォローしてくれるとうれしいです。"
                reply_text += "\nhttps://www.twitch.tv/poppinwillowchan/\n"
                reply_text += "今日はいっぱい話しかけてくれてありがとう！"


                mastodon.status_reply(st,
                        reply_text,
                        id,
                        visibility='public')
                return
        else:
            # 初回登録
            str_count = 0
            limit = str_limit

    reply = ""
    prompt = init_prompt + db_prompt + "<|endoftext|>" + id + ": " + req + "\n"
    prompt = prompt + "<|endoftext|>" + "poppin willow chan: "
    try:
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            temperature=1.0,
            top_p=0.9,
            max_tokens=450,
            stop=["<|endoftext|>"],
        )
        reply = response.choices[0].text.strip()
    except Exception as e:
        print('=== エラー内容 ===')
        print('type:' + str(type(e)))
        print('args:' + str(e.args))
        print('e自身:' + str(e))
        try:
            reply = "現在OpenAIのAPIサーバー側で"
            reply += "問題が発生しているようです。"
            reply += "しばらく時間を置いてから"
            reply += "やり直してほしいです。申し訳ないです。"
            mastodon.status_reply(st,
                    reply,
                    id,
                    visibility='public')
        except Exception as e:
            print('=== エラー内容 ===')
            print('type:' + str(type(e)))
            print('args:' + str(e.args))
            print('e自身:' + str(e))

    try:
        mastodon.status_reply(st,
                reply,
                id,
                visibility='public')
    except Exception as e:
        print('=== エラー内容 ===')
        print('type:' + str(type(e)))
        print('args:' + str(e.args))
        print('e自身:' + str(e))

    with closing(sqlite3.connect(dbname)) as conn:
        c = conn.cursor()
        sql = "INSERT OR REPLACE INTO users (id, acct, str_count, str_limit, prompt) values (?,?,?,?,?)"
        str_count = str_count + len(req)

        prompt = db_prompt + "<|endoftext|>" + id + ": " + req + "\n"
        prompt = prompt + "<|endoftext|>" + "poppin willow chan: " + reply + "\n"
        # promptが500文字以上の場合500文字以下になるまで削る
        while True:
            if len(prompt) > 500:
                prompt_list = prompt.split("\n")
                del prompt_list[0]
                prompt = ""
                for p in prompt_list:
                    prompt += p + "\n"
            else:
                break

        words = (id , acct, str_count, limit, prompt)
        c.execute(sql, words)
        conn.commit()

def mastodon_exe():
    print("起動しました")
    mastodon.stream_user(Stream()) #ストリームの起動

mastodon = Mastodon(access_token = 'gptchan_clientcred.txt')

with ThreadPoolExecutor(max_workers=2, thread_name_prefix="thread") as executor:
    executor.submit(db_str_count_reset)
    executor.submit(mastodon_exe)

