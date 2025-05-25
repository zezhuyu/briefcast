import pika
import redis
import json
import os
import asyncio
from services.image_service import _load_image
from services.audio_services import _create_news_script, _create_transition_audio, _load_content
from services.daily import _store_news
from dotenv import load_dotenv

load_dotenv()

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
IMAGE_TASK_QUEUE = "image_task_queue"
CONTENT_TASK_QUEUE = "content_task_queue"
TRANSITION_TASK_QUEUE = "transition_task_queue"
NEWS_TASK_QUEUE = "daily_news_task_queue"
NEWS_SCRIPT_TASK_QUEUE = "news_script_task_queue"

print("connecting to rabbitmq", RABBITMQ_HOST, RABBITMQ_PORT)

def image_worker(ch, method, props, body):
    podcast_id = None
    try:
        podcast = json.loads(body)
        podcast_id = podcast["id"]
        result = None
        try:
            # Call actual image processing
            print("loading image", podcast_id)
            result = _load_image(podcast)
            success = True
        except Exception as e:
            print("function error", e)
            success = False

        # Send reply
        try:
            ch.basic_publish(
                exchange='',
                routing_key=props.reply_to,
                properties=pika.BasicProperties(correlation_id=props.correlation_id),
                body=result.encode('utf-8') if isinstance(result, str) else None
            )
        except Exception as e:
            print("reply error", e)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print("created image", podcast_id)
    except Exception as e:
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        print("service error", e)

def content_worker(ch, method, props, body):
    try:
        podcast = json.loads(body)
        podcast_id = podcast["id"]
        add_seconds = podcast["add_seconds"]
        result = None
        try:
            # Call actual image processing
            print("loading content", podcast_id)
            result = _load_content(podcast, add_seconds)
            success = True
        except Exception as e:
            success = False
        try:
            ch.basic_publish(
                exchange='',
                routing_key=props.reply_to,
                properties=pika.BasicProperties(correlation_id=props.correlation_id),
                body=json.dumps(result).encode()
            )
        except Exception as e:
            print(e)
            print(e)

        ch.basic_ack(delivery_tag=method.delivery_tag)
        print("created content", podcast_id)
            
    except Exception as e:
        print(e)

def transition_worker(ch, method, props, body):
    try:
        podcast = json.loads(body)
        podcast_id = podcast["id"]
        script1 = podcast["script1"]
        script2 = podcast["script2"]
        add_seconds = podcast["add_seconds"]

        result = None
        try:
            # Call actual image processing
            print("creating transition audio", podcast_id)
            result = _create_transition_audio(script1, script2, add_seconds)
            success = True
        except Exception as e:
            print(e)
            success = False

        try:
            ch.basic_publish(
                exchange='',
                routing_key=props.reply_to,
                properties=pika.BasicProperties(correlation_id=props.correlation_id),
                body=json.dumps(result).encode()
            )
        except Exception as e:
            print(e)

        ch.basic_ack(delivery_tag=method.delivery_tag)
        print("created transition audio", podcast_id)
    except Exception as e:
        print(e)

def create_news_worker(ch, method, props, body):
    try:
        podcasts = json.loads(body)
        user_id = podcasts["user_id"]
        ids = podcasts["ids"]
        location = podcasts["location"]
        result = None
        try:
            # Call actual image processing
            print("creating news", user_id)
            result = asyncio.run(_store_news(user_id, ids, location))
            success = True
        except Exception as e:
            print("worker error", e)
            success = False

        try:
            ch.basic_publish(
                exchange='',
                routing_key=props.reply_to,
                properties=pika.BasicProperties(correlation_id=props.correlation_id),
                body=json.dumps(result).encode()
            )
        except Exception as e:
            print("reply error", e)
        
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print("created news", user_id)
    except Exception as e:
        print("service error", e)

def create_news_script_worker(ch, method, props, body):
    try:
        podcast = json.loads(body)
        podcast_id = podcast["id"]
        result = None
        try:
            print("creating news script", podcast_id)
            result = asyncio.run(_create_news_script(podcast))
            success = True
        except Exception as e:
            print(e)
            success = False
        try:
            ch.basic_publish(
                exchange='',
                routing_key=props.reply_to,
                properties=pika.BasicProperties(correlation_id=props.correlation_id),
                body=result.encode('utf-8') if isinstance(result, str) else None
            )
        except Exception as e:
            print(e)
        
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print("created news", podcast_id)
    except Exception as e:
        print(e)

connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT, heartbeat=60))
channel = connection.channel()
channel.queue_declare(queue=IMAGE_TASK_QUEUE)
channel.queue_declare(queue=CONTENT_TASK_QUEUE)
channel.queue_declare(queue=TRANSITION_TASK_QUEUE)
channel.queue_declare(queue=NEWS_TASK_QUEUE)
channel.queue_declare(queue=NEWS_SCRIPT_TASK_QUEUE)
channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue=IMAGE_TASK_QUEUE, on_message_callback=image_worker)
channel.basic_consume(queue=CONTENT_TASK_QUEUE, on_message_callback=content_worker)
channel.basic_consume(queue=TRANSITION_TASK_QUEUE, on_message_callback=transition_worker)
channel.basic_consume(queue=NEWS_TASK_QUEUE, on_message_callback=create_news_worker)
channel.basic_consume(queue=NEWS_SCRIPT_TASK_QUEUE, on_message_callback=create_news_script_worker)
print("Starting workers...")
channel.start_consuming()