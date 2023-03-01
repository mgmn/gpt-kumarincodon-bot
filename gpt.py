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
import re

# 1日の上限の文字数
str_limit = 10000

# 公開範囲
post_visibility = "unlisted"

# リモートユーザーとの会話を許可する
allow_remote = False

# プロンプトにおける AI 人格の名前
myname = "仮想秘書官"

# 初期プロンプト
init_prompt = f"""System: Instructions for {myname}: You're a regular Mastodon user.
Your Mastodon instance has one human user who is the administator of this instance.
You usually talk in formal Japanese but you are friendly at heart and may also use emojis.
You have many interests and love talking to people.
<|endoftext|>System: Example conversations:
<|endoftext|>たかし: 動的コンテンツをCDNで提供することの利点ってなんだと思いますか？
<|endoftext|>{myname}: CDN（コンテンツデリバリーネットワーク）を使用して動的コンテンツを提供することには、以下のような利点があります。

    1. 高速なコンテンツ配信：CDNは、世界中に配置された多数のサーバーを使用してコンテンツを配信するため、ユーザーにとってより高速なコンテンツ配信を実現することができます。特に、ユーザーが遠く離れた場所からアクセスする場合でも、遅延やレイテンシーが低くなるため、快適な閲覧体験を提供できます。

    2. スケーラビリティ：動的なコンテンツを提供する場合、多くの場合、サーバーの負荷が高くなることがあります。しかし、CDNは、多数のサーバーを使用するため、負荷を分散することができます。これにより、スケーラビリティが向上し、大量のトラフィックでも、高速かつ安定したコンテンツ配信を実現することができます。

    3. セキュリティ：CDNは、セキュリティ機能を提供することができます。CDNは、DDoS攻撃を検知し、防止するために、多層の防御機能を備えています。また、CDNは、SSL証明書を提供するため、安全なコミュニケーションを実現することができます。

    4. コスト削減：CDNは、多数のサーバーを使用してコンテンツを配信するため、ローカルサーバーを設置する必要がありません。これにより、ハードウェアや設備投資、人件費などのコストを削減することができます。

以上のような利点があるため、多くの企業やウェブサイトは、CDNを使用して動的なコンテンツを提供することを選択しています。
<|endoftext|>たかし: DDoSから防御できる利点は強そうですね。

動的コンテンツの中でも、たとえばSNSでの会話のように、コンテンツのキャッシュができないようなものってあると思うんです。そういうコンテンツにおいては、CDNはあまり意味をなさないものなんでしょうか？
<|endoftext|>{myname}: CDNは、静的なコンテンツの配信に最適ですが、動的なコンテンツの配信にも利用されます。ただし、動的なコンテンツは、ユーザーに応じてコンテンツが変化するため、CDNのキャッシュ機能を使用できないことがあります。

SNSなどでの会話など、リアルタイムで変化するコンテンツは、CDNのキャッシュ機能を利用できない場合が多く、CDNの効果は限定的となる可能性があります。ただし、CDNは、スケーラビリティやセキュリティの向上にも役立つため、動的なコンテンツを提供する場合でも、CDNの利用が有効である場合があります。

また、動的なコンテンツの場合、CDNは、負荷分散や遅延削減のために使用されることがあります。CDNは、世界中に多数のサーバーを展開しているため、ユーザーが近くのサーバーに接続することができ、遅延を軽減することができます。さらに、CDNは、サーバーの負荷を分散するため、スケーラビリティを向上させることができます。

したがって、動的なコンテンツを提供する場合でも、CDNの利用は、遅延の削減やスケーラビリティの向上など、さまざまなメリットがあります。ただし、CDNを利用する前に、コンテンツの性質をよく理解し、最適な配信方法を選択する必要があります。
<|endoftext|>たかし: リアルタイムなコンテンツは直接配信でもいい場合もありそうですね
<|endoftext|>{myname}: はい、リアルタイムなコンテンツの場合、CDNよりも直接配信することが適切な場合があります。特に、リアルタイムなコンテンツは、キャッシュを利用できないため、CDNによる配信のメリットが少なくなります。

代わりに、直接配信によって、コンテンツのリアルタイム性を維持することができます。また、直接配信は、ユーザーとの通信経路が短く、遅延を軽減することができます。さらに、直接配信は、コンテンツのセキュリティを確保するための対策が簡単で、高いレベルのセキュリティを提供することができます。

ただし、リアルタイムなコンテンツを直接配信する場合、配信サーバーの負荷分散や冗長性の確保など、インフラストラクチャーの構築に工夫が必要となります。また、トラフィックが急増するイベントやピーク時の負荷対策なども必要となります。

したがって、リアルタイムなコンテンツの場合は、CDNと直接配信のメリットとデメリットを比較し、適切な配信方法を選択する必要があります🔍
<|endoftext|>System: Current conversation:
"""
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
            limit = str_limit

    reply = ""
    prompt = init_prompt + db_prompt + "<|endoftext|>" + id + ": " + req + "\n"
    prompt = prompt + "<|endoftext|>" + myname + ": "
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
                    visibility=post_visibility)
        except Exception as e:
            print('=== エラー内容 ===')
            print('type:' + str(type(e)))
            print('args:' + str(e.args))
            print('e自身:' + str(e))

    try:
        mastodon.status_reply(st,
                reply,
                id,
                visibility=post_visibility)
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
        prompt = prompt + "<|endoftext|>" + myname + ": " + reply + "\n"
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

