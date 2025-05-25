from datetime import datetime
import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import threading
from pymilvus import MilvusClient, Collection
from pymongo import MongoClient
import psycopg2
from dotenv import load_dotenv
import time
import os
import schedule
import re
from minio import Minio
from minio.deleteobjects import DeleteObject
from setup_milvus import setup_milvus
import redis, json
import os
from dotenv import load_dotenv
from init_db import *

load_dotenv()


# Database connection parameters
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', '5432'))
POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', '')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'briefcast')

MONGO_HOST = os.getenv('MONGO_HOST', 'localhost')
MONGO_PORT = int(os.getenv('MONGO_PORT', '27017'))
MONGO_USER = os.getenv('MONGO_USER', '')
MONGO_PASSWORD = os.getenv('MONGO_PASSWORD', '')
MONGO_DB = os.getenv('MONGO_DB', 'podcast_app')
MONGO_AUTH_SOURCE = os.getenv('MONGO_AUTH_SOURCE', 'admin')
MONGO_PODCAST_COLLECTION = os.getenv('MONGO_PODCAST_COLLECTION', 'podcasts')
MONGO_EPISODE_COLLECTION = os.getenv('MONGO_EPISODE_COLLECTION', 'episodes')

MINIO_URL = os.getenv('MINIO_URL', 'localhost:9000')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minio')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'minio')
MINIO_AUDIO_BUCKET = os.getenv('MINIO_AUDIO_BUCKET', 'briefcast')
MINIO_USER_BUCKET = os.getenv('MINIO_USER_BUCKET', 'briefcastuser')

MILVUS_COLLECTION_NAME = "briefcast_daily"

MILVUS_URL = os.getenv("MILVUS_HOST", "localhost:19530")
MILVUS_DIMENSION = int(os.getenv("MILVUS_DIMENSION", 768))

STORE_TIME = int(os.getenv('PODCAST_STORE_TIME', 60 * 60 * 24 * 60))
BUFFER_TIME = int(os.getenv('PODCAST_BUFFER_TIME', 60 * 60 * 24))

REDIS_HOST = os.environ.get('REDIS_HOST')
REDIS_PORT = os.environ.get('REDIS_PORT')
REDIS_DB = os.environ.get('REDIS_DB')

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
pubsub = r.pubsub()
pubsub.psubscribe(f'__keyevent@{REDIS_DB}__:expired')

def get_postgres_connection():

    """Get a connection to PostgreSQL"""
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        database=POSTGRES_DB
    )
    return conn

def get_mongo_connection():
    """Get a connection to MongoDB"""
    connection_string = f"mongodb://"
    
    # Add authentication if provided
    if MONGO_USER and MONGO_PASSWORD:
        connection_string += f"{MONGO_USER}:{MONGO_PASSWORD}@"
    
    connection_string += f"{MONGO_HOST}:{MONGO_PORT}"
    
    # Add authentication source if using auth
    if MONGO_USER and MONGO_PASSWORD:
        connection_string += f"?authSource={MONGO_AUTH_SOURCE}"
    
    client = MongoClient(connection_string)
    return client

def get_milvus_client():
    """Get a Milvus client"""
    return MilvusClient(MILVUS_URL)

def get_minio_client():
    """Get a Minio client"""
    return Minio(
        MINIO_URL,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )

mongo_client = get_mongo_connection()
psql_client = get_postgres_connection()
milvus_client = get_milvus_client()
minio_client = get_minio_client()

def delete_expired_podcasts():
    """Delete expired podcasts"""
    try:
        db = mongo_client[MONGO_DB]
        collection = db[MONGO_PODCAST_COLLECTION]
        threshold = time.time() - (STORE_TIME + BUFFER_TIME)
        milvus_threshold = int(time.time()) - STORE_TIME
        print(MILVUS_COLLECTION_NAME, milvus_threshold)
        milvus_client.delete(MILVUS_COLLECTION_NAME, "", expr=f"created_at < {milvus_threshold}")
        
        # Step 1: Find matching documents and extract IDs
        pg_threshold = datetime.fromtimestamp(threshold)
        cursor = psql_client.cursor()
        cursor.execute("SELECT id, audio_url, transcript_url, cover_image_url FROM podcasts WHERE created_at < %s", (pg_threshold,))
        docs_to_delete = cursor.fetchall()
        ids_to_delete = [doc[0] for doc in docs_to_delete]
        
        user_files = re.compile(r'^[^/]+/[^/]+/[^/]+$')
        files = re.compile(r'^[^/]+/[^/]+$')

        urls = [doc[1] for doc in docs_to_delete] + [doc[2] for doc in docs_to_delete] + [doc[3] for doc in docs_to_delete]
        
        user_urls = []
        podcast_urls = []

        for url in urls:
            if user_files.match(url):
                parts = url.split("/")
                user_urls.append(f"{parts[1]}/{parts[2]}")
            elif files.match(url):
                parts = url.split("/")
                podcast_urls.append(f"{parts[0]}/{parts[1]}")

        user_urls = [DeleteObject(url) for url in set(user_urls)]
        podcast_urls = [DeleteObject(url) for url in set(podcast_urls)]

        minio_client.remove_objects(MINIO_USER_BUCKET, user_urls)
        minio_client.remove_objects(MINIO_AUDIO_BUCKET, podcast_urls)


        cursor = psql_client.cursor()
        cursor.execute("DELETE FROM podcasts WHERE id=ANY(%s)", (ids_to_delete,))
        psql_client.commit()
        cursor.close()

        if ids_to_delete:
            result = collection.delete_many({"_id": {"$in": ids_to_delete}})
            print(f"Deleted {result.deleted_count} documents.")
        else:
            print("No documents to delete.")
        return
    except Exception as e:
        psql_client.rollback()
        print(f"Error deleting expired podcasts: {e}")
        return False

def clean_empty_podcasts():
    """Clean empty podcasts"""
    try:
        mongo_client = get_mongo_connection()
        psql_client = get_postgres_connection()
        milvus_client = get_milvus_client()
        collection = mongo_client[MONGO_DB][MONGO_PODCAST_COLLECTION]
        cursor = psql_client.cursor()
        for podcast in collection.find({"content": "", "createdAt": {"$lt": time.time() - 1000 * 60 * 60 * 24}}):
            milvus_client.delete(
                collection_name=MILVUS_COLLECTION_NAME,
                filter=f'pid in ["{podcast["id"]}"]'
            )
            cursor.execute("DELETE FROM podcasts WHERE id = %s", (podcast["id"],))
            psql_client.commit()
            collection.delete_one({"id": podcast["id"]})
    except Exception as e:
        psql_client.rollback()
        print(f"Error cleaning empty podcasts: {e}")
        return False

def register_cleanup():
    schedule.every(60*60*24).seconds.do(delete_expired_podcasts)
    schedule.every(60*60*24).seconds.do(clean_empty_podcasts)
    print("Cleanup registered")
    while True:
        schedule.run_pending()
        time.sleep(1)

def handle_expired(key):
    try:
        shadow_key = f"shadow:{key}"
        if r.exists(shadow_key):
            shadow_value = r.get(shadow_key)
        json_value = json.loads(shadow_value)
        object_to_delete = [DeleteObject(json_value["audio_url"]), DeleteObject(json_value["transcript_url"])]
        minio_client.remove_objects(MINIO_AUDIO_BUCKET, object_to_delete)
        r.delete(shadow_key)
        print(f"Key expired: {key} {json_value}")
    except Exception as e:
        print(e)

def listen_expired():
    print("Listening for expired keys...")
    for message in pubsub.listen():
        if message['type'] == 'pmessage':
            expired_key = message['data'].decode()
            handle_expired(expired_key)

if __name__ == "__main__":
    milvus = setup_milvus()
    threading.Thread(target=milvus.auto_trigger, daemon=True).start()
    threading.Thread(target=listen_expired, daemon=True).start()
    asyncio.run(register_cleanup())