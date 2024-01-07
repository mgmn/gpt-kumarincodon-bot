import openai
import os
import threading
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.environ["OPENAI_API_KEY"]

def chat_completion(prompt, retry_count, timeout):
    array_response = []
    worker = threading.Thread(target=chat_completion_worker, args=(prompt, array_response))
    for i in range(1 + retry_count):
        worker.start()
        worker.join(timeout)
        if len(array_response) == 1:
            return array_response[0]
        print(f'Retrying to OpenAI {1 + i}/{retry_count}')
    return None

def chat_completion_worker(prompt, array_response):
    try:
        response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=prompt
            )
        array_response.append(response)
    except Exception as e:
        print('=== エラー@chat_completion_worker ===')
        print('type:' + str(type(e)))
        print('args:' + str(e.args))
        print('e自身:' + str(e))
