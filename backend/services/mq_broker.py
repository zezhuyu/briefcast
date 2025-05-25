import redis
import uuid
import pika
import json
import os
import time
from dotenv import load_dotenv

load_dotenv()

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
# connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT))
# channel = connection.channel()

print("connected to rabbitmq", RABBITMQ_HOST, RABBITMQ_PORT)

def send_task(podcast, queue_name):
    try:
        if not podcast or not isinstance(podcast, dict):
            return None

        podcast.pop("_id", None)
        podcast.pop("embedding", None)
        podcast_id = podcast.get("id")
        if not podcast_id:
            return None

        if redis_client.sismember(queue_name, podcast_id):
            print(f"Task for {podcast_id} already in progress")
            return None

        # Generate unique correlation ID
        corr_id = str(uuid.uuid4())

        # Create new connection and channel per task
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT))
        channel = connection.channel()

        # Declare a unique reply queue
        result = channel.queue_declare(queue='', exclusive=True)
        reply_queue = result.method.queue

        redis_client.sadd(queue_name, podcast_id)

        # Send the task
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            properties=pika.BasicProperties(
                reply_to=reply_queue,
                correlation_id=corr_id
            ),
            body=json.dumps(podcast)
        )

        response = None

        def on_response(ch, method, props, body):
            nonlocal response
            if props.correlation_id == corr_id:
                response = body
                try:
                    ch.stop_consuming()
                except Exception as err:
                    print(f"Error stopping consume: {err}")

        channel.basic_consume(queue=reply_queue, on_message_callback=on_response, auto_ack=True)

        # Wait for response with timeout
        print(f"Waiting for {queue_name} to process podcast {podcast_id}...")
        # start_time = time.time()
        # timeout = 60  # seconds

        while response is None:
            # if time.time() - start_time > timeout:
            #     raise TimeoutError(f"Timeout waiting for response from {queue_name} for podcast {podcast_id}")
            connection.process_data_events(time_limit=1)

        return response

    except Exception as e:
        print(f"Error sending task for podcast {podcast.get('id') if podcast else 'unknown'}: {e}")
        return None

    finally:
        # Cleanup
        try:
            if 'podcast_id' in locals():
                redis_client.srem(queue_name, podcast_id)
            if 'channel' in locals() and channel.is_open:
                try:
                    channel.queue_delete(queue=reply_queue)
                except:
                    pass
                channel.close()
            if 'connection' in locals() and connection.is_open:
                connection.close()
        except Exception as cleanup_err:
            print(f"Cleanup error: {cleanup_err}")