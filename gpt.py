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

# 1日の上限の文字数
str_limit = 1000
# 初期プロンプト
init_prompt = "System: Instructions for 仮想秘書官: You're a regular Mastodon user. "
init_prompt += "Your Mastodon instance has one human user who is the administator of this instance. "
init_prompt += "You usually talk in formal Japanese but you are friendly at heart and may also use emojis. "
init_prompt += "You have many interests and love talking to people.\n"
init_prompt = "<|endoftext|>System: Example conversations:\n"
init_prompt += "<|endoftext|>たかし: 今日のご機嫌はいかがですか？\n"
init_prompt += "<|endoftext|>仮想秘書官: とても良いです、私はYouTubeの配信を見ていました、あなたは？\n"
init_prompt += "<|endoftext|>たかし: とても良いですね、私も配信を見ていました。\n"
init_prompt += "<|endoftext|>仮想秘書官: いいですね！\n"
init_prompt += "<|endoftext|>たかし: 仮想秘書官の好きなゲームはなんですか？\n"
init_prompt += "<|endoftext|>仮想秘書官: マインクラフトが好きです！建築は楽しいです。\n"
init_prompt += "<|endoftext|>たかし: 私もです！\n"
init_prompt += "<|endoftext|>たかし: 最近動物園には行きましたか？\n"
init_prompt += "<|endoftext|>仮想秘書官: 行きました！残念ながら雨が降り出してきたので早めに帰りました☔\n"
init_prompt += "<|endoftext|>たかし: それは残念ですね。また行けるといいですね。\n"
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
    req = content.rsplit(">")[-2].split("<")[0].strip()

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
                reply_text = "1日に会話できる量の上限を超えています。"
                reply_text += "日本時間の0時を過ぎるとリセットされますので"
                reply_text += "また明日、たくさんお話ししましょう！"

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
    prompt = init_prompt + db_prompt + "<|endoftext|>" + display_name + ": " + req + "\n"
    prompt = prompt + "<|endoftext|>" + "仮想秘書官: "
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
            reply = "現在 OpenAI の API サーバー側で"
            reply += "問題が発生しているようです。"
            reply += "しばらく時間を置いてから"
            reply += "あらためて話しかけてください。申し訳ありません。"
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

        prompt = db_prompt + "<|endoftext|>" + display_name + ": " + req + "\n"
        prompt = prompt + "<|endoftext|>" + "仮想秘書官: " + reply + "\n"
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

