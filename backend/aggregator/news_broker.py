import pika
import json
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))

NEWS_TASK_QUEUE = "news_crawler_task_queue"

print("connecting to rabbitmq", RABBITMQ_HOST, RABBITMQ_PORT)

def send_crawler_task(data_list):
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue=NEWS_TASK_QUEUE)

        # Convert the list of JSON (Python dicts) to a JSON string
        message = json.dumps(data_list)

        channel.basic_publish(exchange='',
                            routing_key=NEWS_TASK_QUEUE,
                            body=message)
        print("Sent JSON list to queue.")

        connection.close()
    except Exception as e:
        print(e)
    finally:
        try:
            connection.close()
        except:
            pass
