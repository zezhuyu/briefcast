#!/usr/bin/env python3
"""
Middleware for handling podcast operations across multiple databases.
This module coordinates operations between MongoDB, PostgreSQL, and Milvus.
"""
import asyncio
from datetime import datetime
import os
import re
import time
import uuid
import psycopg2
from psycopg2.extras import Json
from psycopg2.extensions import register_adapter, AsIs
from pymongo import MongoClient, DESCENDING
from pymilvus import MilvusClient, AnnSearchRequest, RRFRanker
import sys

import schedule

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nanoid import generate as nanoid_generate
from dotenv import load_dotenv
from services.llm_stuff import create_embedding, create_summary
import numpy as np
import globals
import threading
from urllib.parse import urlparse
import tldextract

# Load environment variables
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

MILVUS_COLLECTION_NAME = "briefcast_hourly"
MILVUS_USER_COLLECTION_NAME = "briefcast_user"
MILVUS_DAILY_COLLECTION_NAME = "briefcast_daily"
MILVUS_WEEKLY_COLLECTION_NAME = "briefcast_weekly"
MILVUS_MAIN_COLLECTION_NAME = "briefcast"

MILVUS_URL = os.getenv("MILVUS_HOST", "localhost:19530")
MILVUS_DIMENSION = int(os.getenv("MILVUS_DIMENSION", 768))

def adapt_numpy_array(numpy_array):
    if numpy_array is None:
        return AsIs('NULL')
    return AsIs("'[" + ",".join(str(x) for x in numpy_array.flatten()) + "]'")

# Register the adapter
register_adapter(np.ndarray, adapt_numpy_array)

# Generate a unique ID for podcasts
def generate_podcast_id(size=21):
    """Generate a unique ID for podcasts using nanoid"""
    return nanoid_generate(size=size)

# Database connection functions
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

milvus = get_milvus_client()

def _flush_collection(collection_name):
    milvus.flush(collection_name=collection_name)
    print(f"Flushed collection: {collection_name}")

def flush_collections():
    """Flush collections on a schedule"""
    schedule.every(1).day.do(_flush_collection, collection_name=MILVUS_COLLECTION_NAME)
    schedule.every(30).seconds.do(_flush_collection, collection_name=MILVUS_USER_COLLECTION_NAME)
    schedule.every(30).seconds.do(_flush_collection, collection_name=MILVUS_DAILY_COLLECTION_NAME)
    schedule.every(30).seconds.do(_flush_collection, collection_name=MILVUS_WEEKLY_COLLECTION_NAME)
    schedule.every(1).day.do(_flush_collection, collection_name=MILVUS_MAIN_COLLECTION_NAME)
    print("Milvus flush collections setup")
    while True:
        schedule.run_pending()
        time.sleep(1)

# Start flush_collections in a background thread so it doesn't block
threading.Thread(target=flush_collections, daemon=True).start()

class PodcastMiddleware:
    """Middleware for handling podcast operations across multiple databases"""
    
    def __init__(self):
        """Initialize connections to all databases"""
        self.pg_conn = get_postgres_connection()
        self.mongo_client = get_mongo_connection()
        self.mongo_db = self.mongo_client[MONGO_DB]
        self.milvus_client = get_milvus_client()
    
    def close_connections(self):
        """Close all database connections"""
        if self.pg_conn:
            self.pg_conn.close()
        if self.mongo_client:
            self.mongo_client.close()

    def create_user_podcast(self, user_id, podcast_data):
        """
        Create a user podcast across all databases
        """
        try:
            # Generate a unique ID for the podcast
            podcast_id = generate_podcast_id()
            
            # Prepare timestamps
            current_time = time.time()
            ts = datetime.fromtimestamp(current_time)
            # 1. Store in MongoDB
            mongo_data = {
                "id": podcast_id,
                "link": "https://briefcast.net/?podcast=" + podcast_id,
                "title": podcast_data.get("title", ""),
                "content": podcast_data.get("content", []),
                "transcript_text": "",
                "description": user_id,
                "country": "US",
                "category": "daily",
                "subcategory": "news",
                "keywords": podcast_data.get("keywords", []),
                "lastUpdate": current_time,
                "updatedParsed": current_time,
                "published_at": current_time,
                "createAt": current_time,
                "modifyAt": current_time,
            }
            
            # 2. Store in PostgreSQL
            cursor = self.pg_conn.cursor()
            
            insert_query = """
            INSERT INTO podcasts (
                id, link, title, category, subcategory, 
                audio_url, transcript_url, cover_image_url, duration_seconds,
                positive_rating, negative_rating, total_rating, embedding, published_at, lang
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """
            
            cursor.execute(insert_query, (
                podcast_id,
                "https://briefcast.net/?podcast=" + podcast_id,
                podcast_data.get("title", ""),
                "daily",
                "news",
                podcast_data.get("audio_url", ""),
                podcast_data.get("transcript_url", ""),
                podcast_data.get("cover_image_url", ""),
                podcast_data.get("duration_seconds", 0),
                0,  # positive_rating
                0,  # negative_rating
                0,  # total_rating
                podcast_data.get("embedding", []),
                ts,
                ""
            ))
            
            
            print(f"Stored podcast in PostgreSQL with ID: {podcast_id}")
            self.mongo_db[MONGO_PODCAST_COLLECTION].insert_one(mongo_data)

            self.pg_conn.commit()

            mongo_data["duration_seconds"] = podcast_data.get("duration_seconds", 0)
            mongo_data["positive"] = 0
            mongo_data["negative"] = 0
            mongo_data["totalRating"] = 0
            mongo_data["rating"] = 0.0
            mongo_data["audio_url"] = podcast_data.get("audio_url", "")
            mongo_data["transcript_url"] = podcast_data.get("transcript_url", "")
            mongo_data["cover_image_url"] = podcast_data.get("cover_image_url", "")
            
            return mongo_data
            
        except Exception as e:
            # Rollback in case of error
            self.pg_conn.rollback()
            print(f"Error storing podcast: {e}")
            # Try to clean up any partial inserts
            try:
                self.mongo_db[MONGO_PODCAST_COLLECTION].delete_one({"id": podcast_id})
            except Exception as cleanup_error:
                print(f"Error during cleanup: {cleanup_error}")
            return None
        
    def get_user_podcast(self, user_id):
        """
        Get a user podcast from MongoDB
        """
        try:
            podcast = self.mongo_db[MONGO_PODCAST_COLLECTION].find_one({"description": user_id}, sort=[("createAt", DESCENDING)])
            if podcast:
                cursor = self.pg_conn.cursor()
                cursor.execute("SELECT id, positive_rating, negative_rating, total_rating, audio_url, transcript_url, cover_image_url, duration_seconds FROM podcasts WHERE id = %s", (podcast["id"],))
                podcast_id = cursor.fetchone()
                if podcast_id:
                    podcast_ratings = {
                        "positive_rating": podcast_id[1],
                        "negative_rating": podcast_id[2],
                        "total_rating": podcast_id[3],
                        "audio_url": podcast_id[4],
                        "transcript_url": podcast_id[5],
                        "cover_image_url": podcast_id[6],
                        "duration": podcast_id[7]
                        }
                else:
                    podcast_ratings = {
                        "positive_rating": 0,
                        "negative_rating": 0,
                        "total_rating": 0,
                        "audio_url": "",
                        "transcript_url": "",
                        "cover_image_url": "",
                        "duration": 0
                        }
                return {**podcast, **podcast_ratings}
            else:
                return None
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error getting user podcast: {e}")
            return None


    def get_podcast_metadata(self, podcast_id):
        """
        Get podcast metadata from MongoDB
        """
        try:
            query = """
            SELECT id, cluster_id, link, title, category, subcategory, audio_url, transcript_url, cover_image_url, duration_seconds, created_at, modify_at, published_at, lang, city, region, country, trending, trending_time, trending_score, hot, hot_time, hot_score, embedding
            FROM podcasts
            WHERE id = %s
            """
            cursor = self.pg_conn.cursor()
            cursor.execute(query, (podcast_id,))
            podcast = cursor.fetchone()
            if podcast:
                data = {
                    "id": podcast[0],
                    "cluster_id": podcast[1],
                    "link": podcast[2],
                    "title": podcast[3],
                    "category": podcast[4],
                    "subcategory": podcast[5],
                    "audio_url": podcast[6],
                    "transcript_url": podcast[7],
                    "cover_image_url": podcast[8],
                    "duration": podcast[9],
                    "created_at": podcast[10],
                    "modify_at": podcast[11],
                    "published_at": podcast[12],
                    "lang": podcast[13],
                    "city": podcast[14],
                    "region": podcast[15],
                    "country": podcast[16],
                    "trending": podcast[17],
                    "trending_time": podcast[18],
                    "trending_score": podcast[19],
                    "hot": podcast[20],
                    "hot_time": podcast[21],
                    "hot_score": podcast[22],
                    "embedding": podcast[23]
                }
                return data
            else:
                return None
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error getting podcast metadata: {e}")
            return None


    def create_podcast(self, podcast_data):
        """
        Create a podcast across all databases
        """
        try:
            # Generate a unique ID for the podcast
            
            
            # Prepare timestamps
            current_time = time.time()
            
            # 1. Store in MongoDB
            
            mongo_data = self.mongo_db[MONGO_PODCAST_COLLECTION].find_one({"link": podcast_data.get("link", "")})

            if not mongo_data:
                mongo_data = {
                    "id": nanoid_generate(),
                    "link": podcast_data.get("link", ""),
                    "title": podcast_data.get("title", ""),
                    "content": "",
                    "transcript_text": "",
                    "description": "",
                    "category": podcast_data.get("category", ""),
                    "subcategory": "",
                    "keywords": [],
                    "lastUpdate": podcast_data.get("updated", ""),
                    "updatedParsed": podcast_data.get("updated_parsed", ""),
                    "published_at": current_time,
                    "createAt": current_time,
                    "modifyAt": current_time,
                }
                
                self.mongo_db[MONGO_PODCAST_COLLECTION].insert_one(mongo_data)
                return mongo_data.get("link")

            return None
            
        except Exception as e:
            print(f"Error storing podcast: {e}")
            # Try to clean up any partial inserts
            try:
                self.mongo_db[MONGO_PODCAST_COLLECTION].delete_one({"link": podcast_data.get("link", "")})
            except Exception as cleanup_error:
                print(f"Error during cleanup: {cleanup_error}")
            return None
    
    def update_podcast(self, podcast_data):
        """
        Store a podcast across all databases
        
        Args:
            podcast_data (dict): Podcast data including title, description, etc.
            embedding (list): Vector embedding for the podcast content
            
        Returns:
            str: The ID of the stored podcast
        """
        try:
            podcast_id = nanoid_generate()
            current_time = time.time()
            label = podcast_data.get("category", "")
            sub_label = podcast_data.get("subcategory", "")
            keywords = podcast_data.get("keywords", "")
            summary = podcast_data.get("summary", "")
            embedding = podcast_data.get("embedding", [])
            transcript = podcast_data.get("script", "")
            text_vector = podcast_data.get("text_vector", np.zeros(MILVUS_DIMENSION))
            ts = datetime.fromtimestamp(podcast_data.get("published_at", 0.0))
            
            if podcast_data.get("content", "") == "":
                mongo_result = self.mongo_db[MONGO_PODCAST_COLLECTION].find_one_and_delete(
                    {"link": podcast_data.get("link", "")},
                    sort=[("published_at", -1)],
                    projection={"id": 1}
                )
                if mongo_result:
                    pid = mongo_result.get("id")
                    cursor = self.pg_conn.cursor()
                    cursor.execute("DELETE FROM podcasts WHERE id = %s", (pid,))
                    self.pg_conn.commit()
                    
                return None

            # 1. Update in MongoDB
            
            # 2. Update in PostgreSQL
            cursor = self.pg_conn.cursor()

            insert_query = """
                INSERT INTO podcasts (
                    id, link, title, category, subcategory, 
                    audio_url, transcript_url, cover_image_url, duration_seconds,
                    embedding, lang, published_at, city, region, country
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (link) DO UPDATE SET
                id = EXCLUDED.id, category = EXCLUDED.category, subcategory = EXCLUDED.subcategory, embedding = EXCLUDED.embedding, title = EXCLUDED.title, lang = EXCLUDED.lang, published_at = EXCLUDED.published_at, city = EXCLUDED.city, region = EXCLUDED.region, country = EXCLUDED.country
                RETURNING id;
                """
                
            cursor.execute(insert_query, (
                podcast_id,
                podcast_data.get("link", ""),
                podcast_data.get("title", ""),
                podcast_data.get("category", ""),
                podcast_data.get("subcategory", ""),
                "",
                "",
                "",
                0,
                embedding,
                podcast_data.get("lang", ""),
                ts,
                podcast_data.get("city", ""),
                podcast_data.get("region", ""),
                podcast_data.get("country", "")
            ))

            updated_doc = self.mongo_db[MONGO_PODCAST_COLLECTION].find_one_and_update(
                {"link": podcast_data.get("link", "")},
                {"$set": {
                    "id": podcast_id,
                    "title": podcast_data.get("title", ""),
                    "lang": podcast_data.get("lang", ""),
                    "script": transcript,
                    "category": label,
                    "subcategory": sub_label,   
                    "keywords": keywords,
                    "modifyAt": current_time,
                    "published_at": float(podcast_data.get("published_at", "")),
                    "content": podcast_data.get("content", ""),
                    "description": podcast_data.get("description", podcast_data.get("summary", "")),
                }},
                return_document=True
            )


            updated_id = updated_doc.get("id") if updated_doc else None

            print(f"updated_id in mongo: {updated_id}")
            
            # 3. Update in Milvus
            self.milvus_client.insert(
                collection_name=MILVUS_COLLECTION_NAME,
                data=[
                    {
                        "pid": podcast_id,
                        "lang": podcast_data.get("lang", ""),
                        "country": podcast_data.get("country", ""),
                        "city": podcast_data.get("city", ""),
                        "region": podcast_data.get("region", ""),
                        "category": label,
                        "subcategory": sub_label,
                        "keywords": keywords,
                        "title": podcast_data.get("title", ""),
                        "text_vector": text_vector,
                        "summary": summary,
                        "vector": embedding,
                        "created_at": int(current_time),
                        "published_at": int(podcast_data.get("published_at", ""))
                    }
                ]
            )
            self.milvus_client.flush(collection_name=MILVUS_COLLECTION_NAME)
            print(f"Updated podcast embedding in Milvus with ID: {podcast_id}")
            self.pg_conn.commit()
            
            return podcast_id
            
        except Exception as e:
            # Rollback in case of error
            self.pg_conn.rollback()
            print(f"Error updating podcast: {e}")
            # Try to clean up any partial inserts
            try:
                self.mongo_db[MONGO_PODCAST_COLLECTION].delete_one({"id": podcast_id})
                if podcast_id is not None and podcast_id != "None":
                    self.milvus_client.delete(
                        collection_name=MILVUS_COLLECTION_NAME,
                        filter=f'pid in ["{podcast_id}"]'  # Make sure to use the correct field name (pid, not id)
                    )
            except Exception as cleanup_error:
                print(f"Error during cleanup: {cleanup_error}")
            
            raise
    
    def update_podcast_rating(self, podcast_id, user_id, rating):
        """
        Update the rating of a podcast
        
        Args:
            podcast_id (str): The ID of the podcast to update
            is_positive (bool): Whether the rating is positive
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # get original rating from user_podcast_history table and update it
            # if rating is positive, add it to user_liked_podcasts if not exist and delete from user_disliked_podcasts if exist
            # if rating is negative, add it to user_disliked_podcasts if not exist and delete from user_liked_podcasts if exist
            # if rating is 0, delete from both user_liked_podcasts and user_disliked_podcasts
            # if rating is not same as original rating, update the rating in MONGO_PODCAST_COLLECTION
            
            cursor = self.pg_conn.cursor()
            cursor.execute("SELECT rating FROM user_podcast_history WHERE user_id = %s AND podcast_id = %s", (user_id, podcast_id))
            original_rating = cursor.fetchone()
            if original_rating:
                if original_rating[0] == rating:
                    return True
                elif rating == 1 and original_rating[0] == -1:
                    cursor.execute("UPDATE podcasts SET positive_rating = positive_rating + 1, negative_rating = negative_rating - 1 WHERE id = %s", (podcast_id,))
                    self.pg_conn.commit()
                    return True
                elif rating == -1 and original_rating[0] == 1:
                    cursor.execute("UPDATE podcasts SET positive_rating = positive_rating - 1, negative_rating = negative_rating + 1 WHERE id = %s", (podcast_id,))
                    self.pg_conn.commit()
                    return True
                elif rating == 1 and original_rating[0] == 0:
                    cursor.execute("UPDATE podcasts SET positive_rating = positive_rating + 1 WHERE id = %s", (podcast_id,))
                    self.pg_conn.commit()
                    return True
                elif rating == -1 and original_rating[0] == 0:
                    cursor.execute("UPDATE podcasts SET negative_rating = negative_rating + 1 WHERE id = %s", (podcast_id,))
                    self.pg_conn.commit()
                    return True
                elif rating == 0 and original_rating[0] == 1:
                    cursor.execute("UPDATE podcasts SET positive_rating = positive_rating - 1, total_rating = total_rating - 1 WHERE id = %s", (podcast_id,))
                    self.pg_conn.commit()
                    return True
                elif rating == 0 and original_rating[0] == -1:
                    cursor.execute("UPDATE podcasts SET negative_rating = negative_rating - 1, total_rating = total_rating - 1 WHERE id = %s", (podcast_id,))
                    self.pg_conn.commit()
                    return True
                return True
            else:
                if rating == 1:
                    cursor.execute("UPDATE podcasts SET positive_rating = positive_rating + 1, total_rating = total_rating + 1 WHERE id = %s", (podcast_id,))
                elif rating == -1:
                    cursor.execute("UPDATE podcasts SET negative_rating = negative_rating + 1, total_rating = total_rating + 1 WHERE id = %s", (podcast_id,))
                self.pg_conn.commit()
                return True
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error updating podcast rating: {e}")
            return False
                
    def search_podcasts_by_vector(self, query_embedding, history=None, limit=10, category=None, subcategory=None, hourly=True, daily=True, weekly=False, whole=False):
        """
        Search for podcasts by embedding similarity
        """
        search_params = {
            "output_fields": ["pid", "category", "subcategory", "keywords"]
        }

        filter = []

        if subcategory:
            search_params["filter"] = f'subcategory == "{subcategory}"'
        elif category:
            search_params["filter"] = f'category == "{category}"'

        if history:
            filter.append(f'pid not in {history}')

        if filter:
            search_params["filter"] = " AND ".join(filter)

        podcast_ids = set()
        podcasts = []

        if hourly:
            try:
                results = self.milvus_client.search(
                    anns_field="vector",
                    collection_name="briefcast_hourly",
                    data=[query_embedding],
                    limit=limit,
                    **search_params
                )
                if results and len(results) > 0:
                    podcasts.extend(results[0])
            except Exception as e:
                print(f"Error searching podcasts: {e}")

        if daily:
            try:
                results = self.milvus_client.search(
                    anns_field="vector",
                    collection_name="briefcast_daily",
                    data=[query_embedding],
                    limit=limit,
                    **search_params
                )
                if results and len(results) > 0:
                    podcasts.extend(results[0])
            except Exception as e:
                print(f"Error searching podcasts: {e}")

        if weekly:
            try:
                results = self.milvus_client.search(
                    anns_field="vector",
                    collection_name="briefcast_weekly",
                    data=[query_embedding],
                    limit=limit,
                    **search_params
                )
                if results and len(results) > 0:
                    podcasts.extend(results[0])
            except Exception as e:
                print(f"Error searching podcasts: {e}")

        if whole:
            try:
                results = self.milvus_client.search(
                    anns_field="vector",
                    collection_name="briefcast",
                    data=[query_embedding],
                    limit=limit,
                    **search_params
                )
                if results and len(results) > 0:
                    podcasts.extend(results[0])
            except Exception as e:
                print(f"Error searching podcasts: {e}")

        podcasts.sort(key=lambda x: x["distance"], reverse=True)
        podcast_ids = set([podcast["entity"]["pid"] for podcast in podcasts])

        return list(podcast_ids)[:limit]


    def search_podcasts_by_text(self, query, history=None, limit=10, category=None, subcategory=None, hourly=True, daily=True, weekly=False, whole=False):
        """
        Search for podcasts by text similarity
        """
        search_params = {
            "output_fields": ["pid", "category", "subcategory", "keywords"],
            "params": {"drop_ratio_search": 0.6}
        }

        filter = []

        if subcategory:
            filter.append(f'subcategory == "{subcategory}"')
        elif category:
            filter.append(f'category == "{category}"')

        if history:
            filter.append(f'pid not in {history}')

        if filter:
            search_params["filter"] = " AND ".join(filter)

        podcast_ids = set()
        podcasts = []

        if hourly:
            try:
                results = self.milvus_client.search(
                    anns_field="sparse",
                    collection_name="briefcast_hourly",
                    data=[query],
                    limit=limit,
                    **search_params
                )
                if results and len(results) > 0:
                    podcasts.extend(results[0])
            except Exception as e:
                print(f"Error searching podcasts: {e}")

        if daily:
            try:
                results = self.milvus_client.search(
                    anns_field="sparse",
                    collection_name="briefcast_daily",
                    data=[query],
                    limit=limit,
                    **search_params
                )
                if results and len(results) > 0:
                    podcasts.extend(results[0])
            except Exception as e:
                print(f"Error searching podcasts: {e}")

        if weekly:
            try:
                results = self.milvus_client.search(
                    anns_field="sparse",
                    collection_name="briefcast_weekly",
                    data=[query],
                    limit=limit,
                    **search_params
                )
                if results and len(results) > 0:
                    podcasts.extend(results[0])
            except Exception as e:
                print(f"Error searching podcasts: {e}")

        if whole:
            try:
                results = self.milvus_client.search(
                    anns_field="sparse",
                    collection_name="briefcast",
                    data=[query],
                    limit=limit,
                    **search_params
                )
                if results and len(results) > 0:
                    podcasts.extend(results[0])
            except Exception as e:
                print(f"Error searching podcasts: {e}")

        podcasts.sort(key=lambda x: x["distance"], reverse=True)
        podcast_ids = set([podcast["entity"]["pid"] for podcast in podcasts])

        return list(podcast_ids)[:limit]


    def search_podcasts(self, query, history=None, limit=10, category=None, subcategory=None, hourly=True, daily=True, weekly=False, whole=False):
        """
        Search for podcasts by embedding similarity
        
        Args:
            query_embedding (list): The query embedding vector
            limit (int): Maximum number of results to return
            category (str): Optional category filter
            
        Returns:
            list: List of podcast IDs sorted by similarity
        """
        query_embedding = create_embedding(query)
        search_params = {
            "output_fields": ["pid", "category", "subcategory", "keywords"]
        }

        filter = []

        if subcategory:
            filter.append(f'subcategory == "{subcategory}"')
        elif category:
            filter.append(f'category == "{category}"')

        if history:
            filter.append(f'pid not in {history}')

        if filter:
            search_params["filter"] = " AND ".join(filter)

        sparse_search_params = search_params.copy()
        sparse_search_params["params"] = {'drop_ratio_search': 0.6}

        full_text_search_params = {"metric_type": "BM25"}
        full_text_search_req = AnnSearchRequest(
            [query], "sparse", full_text_search_params, limit=limit
        )

        dense_search_params = {"metric_type": "COSINE"}
        dense_req = AnnSearchRequest(
            [query_embedding], "vector", dense_search_params, limit=limit
        )

        podcast_ids = set()
        podcasts = []

        if hourly:
            try:
                sparse_results = self.milvus_client.hybrid_search(
                    "briefcast_hourly",
                    [full_text_search_req, dense_req],
                    ranker=RRFRanker(),
                    limit=limit,
                    **sparse_search_params
                )
                if sparse_results and len(sparse_results) > 0:
                    podcasts.extend(sparse_results[0])
            except Exception as e:
                print(f"Error searching podcasts: {e}")

        if daily:
            try:
                sparse_results = self.milvus_client.hybrid_search(
                    "briefcast_daily",
                    [full_text_search_req, dense_req],
                    ranker=RRFRanker(),
                    limit=limit,
                    **sparse_search_params
                )
                if sparse_results and len(sparse_results) > 0:
                    podcasts.extend(sparse_results[0])
            except Exception as e:
                print(f"Error searching podcasts: {e}")

        if weekly:
            try:
                sparse_results = self.milvus_client.hybrid_search(
                    "briefcast_weekly",
                    [full_text_search_req, dense_req],
                    ranker=RRFRanker(),
                    limit=limit,
                    **sparse_search_params
                )
                if sparse_results and len(sparse_results) > 0:
                    podcasts.extend(sparse_results[0])
            except Exception as e:
                print(f"Error searching podcasts: {e}")

        if whole:
            try:
                sparse_results = self.milvus_client.hybrid_search(
                    "briefcast",
                    [full_text_search_req, dense_req],
                    ranker=RRFRanker(),
                    limit=limit,
                    **sparse_search_params
                )
                if sparse_results and len(sparse_results) > 0:
                    podcasts.extend(sparse_results[0])
            except Exception as e:
                print(f"Error searching podcasts: {e}")

        podcasts.sort(key=lambda x: x["distance"], reverse=True)
        podcast_ids = set([podcast["entity"]["pid"] for podcast in podcasts])

        return list(podcast_ids)[:limit]
    

    def get_podcast_embeddings(self, podcast_ids):
        """
        Get the embeddings of a list of podcasts
        """
        try:
            cursor = self.pg_conn.cursor()
            cursor.execute("SELECT embedding FROM podcasts WHERE id = ANY(%s)", (podcast_ids,))
            embeddings = cursor.fetchall()
            return [eval(embedding[0]) for embedding in embeddings]
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error getting podcast embeddings: {e}")
            return []

    def search_embeddings_in_milvus(self, podcast_id):
        """
        Search for podcasts by embedding similarity in Milvus
        """
        try:
            
            results = self.milvus_client.query(
                collection_name="briefcast_hourly",
                filter = f'pid like "{podcast_id}"',
                limit=1
            )
            if results and len(results) > 0:
                return results[0]["vector"]
            results = self.milvus_client.query(
                collection_name="briefcast_daily",
                filter = f'pid like "{podcast_id}"',
                limit=1
            )
            if results and len(results) > 0:
                return results[0]["vector"]
            results = self.milvus_client.query(
                collection_name="briefcast_weekly",
                filter = f'pid like "{podcast_id}"',
                limit=1
            )
            if results and len(results) > 0:
                return results[0]["vector"]
            results = self.milvus_client.query(
                collection_name="briefcast",
                filter = f'pid like "{podcast_id}"',
                limit=1
            )
            if results and len(results) > 0:
                return results[0]["vector"]
            return None
        except Exception as e:
            print(f"Error searching embeddings in Milvus: {e}")
            return None
        
    def get_podcast_by_id(self, podcast_id):
        """
        Get a podcast by ID
        """
        try:
            mongo_podcast = self.mongo_db[MONGO_PODCAST_COLLECTION].find_one({"id": podcast_id})
            rating_info = {
                "positive_rating": 0,
                "negative_rating": 0,
                "total_rating": 0,
                "audio_url": "",
                "transcript_url": "",
                "cover_image_url": "",
                "duration": 0
            }
            if mongo_podcast:
                cursor = self.pg_conn.cursor()
                cursor.execute("SELECT positive_rating, negative_rating, total_rating, audio_url, transcript_url, cover_image_url, duration_seconds, country FROM podcasts WHERE id = %s", (podcast_id,))
                podcast = cursor.fetchone()
                if podcast:
                    rating_info = {
                        "positive_rating": podcast[0],
                        "negative_rating": podcast[1],
                        "total_rating": podcast[2],
                        "audio_url": podcast[3],
                        "transcript_url": podcast[4],
                        "cover_image_url": podcast[5],
                        "duration": podcast[6],
                        "country": podcast[7]
                    }
                else:
                    embedding = self.search_embeddings_in_milvus(podcast_id)
                    if not embedding:
                        return None
                    embedding = np.array(embedding)
                    insert_query = """
                        INSERT INTO podcasts (
                            id, link, title, category, subcategory, embedding, lang, published_at, created_at, city, region, country
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (link)
                        DO UPDATE SET
                            id = EXCLUDED.id,
                            link = EXCLUDED.link,
                            title = EXCLUDED.title,
                            category = EXCLUDED.category,
                            subcategory = EXCLUDED.subcategory,
                            embedding = EXCLUDED.embedding,
                            lang = EXCLUDED.lang,
                            published_at = EXCLUDED.published_at,
                            created_at = EXCLUDED.created_at,
                            city = EXCLUDED.city,
                            region = EXCLUDED.region,
                            country = EXCLUDED.country
                        RETURNING id;
                        """
                    pubtime = datetime.fromtimestamp(podcast["published_at"])
                    create_time = datetime.fromtimestamp(podcast["createAt"])
                    cursor.execute(insert_query, (
                        podcast_id,
                        mongo_podcast.get("link", ""),
                        mongo_podcast.get("title", ""),
                        mongo_podcast.get("category", ""),
                        mongo_podcast.get("subcategory", ""),
                        embedding,
                        mongo_podcast.get("lang", ""),
                        pubtime,
                        create_time,
                        mongo_podcast.get("city", ""),
                        mongo_podcast.get("region", ""),
                        mongo_podcast.get("country", "")
                    ))

                    self.pg_conn.commit()
                    print(f"Inserted podcast {podcast_id} into PostgreSQL")
                return {**mongo_podcast, **rating_info}
            else:
                return None
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error getting podcast by ID: {e}")
            return None
    
    def get_podcasts_by_ids(self, podcast_ids):
        """
        Get podcast details for a list of IDs
        
        Args:
            podcast_ids (list): List of podcast IDs
            
        Returns:
            list: List of podcast data
        """
        try:
            podcasts = list(self.mongo_db[MONGO_PODCAST_COLLECTION].find({"id": {"$in": podcast_ids}}))
            cursor = self.pg_conn.cursor()
            cursor.execute("SELECT id, positive_rating, negative_rating, total_rating, audio_url, transcript_url, cover_image_url, duration_seconds, country FROM podcasts WHERE id = ANY(%s)", (podcast_ids,))
            podcast_ratings = cursor.fetchall()
            for podcast in podcasts:
                pos = False
                for podcast_rating in podcast_ratings:
                    if podcast_rating[0] == podcast["id"]:
                        podcast["positive_rating"] = podcast_rating[1]
                        podcast["negative_rating"] = podcast_rating[2]
                        podcast["total_rating"] = podcast_rating[3]
                        podcast["audio_url"] = podcast_rating[4]
                        podcast["transcript_url"] = podcast_rating[5]
                        podcast["cover_image_url"] = podcast_rating[6]
                        podcast["duration"] = podcast_rating[7]
                        podcast["country"] = podcast_rating[8]
                        pos = True
                        break
                if not pos:
                    podcast["positive_rating"] = 0
                    podcast["negative_rating"] = 0
                    podcast["total_rating"] = 0
                    podcast["audio_url"] = ""
                    podcast["transcript_url"] = ""
                    podcast["cover_image_url"] = ""
                    podcast["duration"] = 0
                    embedding = self.search_embeddings_in_milvus(podcast["id"])
                    if not embedding:
                        continue
                    embedding = np.array(embedding)
                    insert_query = """
                        INSERT INTO podcasts (
                            id, link, title, category, subcategory, embedding, lang, published_at, created_at, city, region, country
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (link)
                        DO UPDATE SET
                            id = EXCLUDED.id,
                            link = EXCLUDED.link,
                            title = EXCLUDED.title,
                            category = EXCLUDED.category,
                            subcategory = EXCLUDED.subcategory,
                            embedding = EXCLUDED.embedding,
                            lang = EXCLUDED.lang,
                            published_at = EXCLUDED.published_at,
                            created_at = EXCLUDED.created_at,
                            city = EXCLUDED.city,
                            region = EXCLUDED.region,
                            country = EXCLUDED.country
                        RETURNING id;
                        """
                    pubtime = datetime.fromtimestamp(podcast["published_at"])
                    create_time = datetime.fromtimestamp(podcast["createAt"])
                    cursor.execute(insert_query, (
                        podcast["id"],
                        podcast.get("title", ""),
                        podcast.get("category", ""),
                        podcast.get("subcategory", ""),
                        embedding,
                        podcast.get("lang", ""),
                        pubtime,
                        create_time,
                        podcast.get("city", ""),
                        podcast.get("region", ""),
                        podcast.get("country", "")
                    ))

                    self.pg_conn.commit()
                    print(f"Inserted podcast {podcast['id']} into PostgreSQL")
                
            return podcasts
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error getting podcasts by IDs: {e}")
            return []
        
    def get_user_trending_podcasts(self, play_count_threshold=100):
        """
        Get the trending podcasts for a user
        """
        try:
            cursor = self.pg_conn.cursor()
            query = """
            SELECT id, title, positive_rating, negative_rating, total_rating, cover_image_url, duration_seconds, published_at, category, subcategory
            FROM podcasts 
            WHERE play_count > %s
            ORDER BY play_count DESC, published_at DESC
            LIMIT 8
            """
            
            cursor.execute(query, (play_count_threshold,))
            all_podcasts = cursor.fetchall()
            podcasts = []
            for podcast in all_podcasts:
                ts = podcast[7].timestamp()
                podcasts.append({
                    "id": podcast[0],
                    "title": podcast[1],
                    "positive_rating": podcast[2],
                    "negative_rating": podcast[3],
                    "total_rating": podcast[4],
                    "cover_image_url": podcast[5],
                    "duration": podcast[6], 
                    "published_at": ts,
                    "category": podcast[8],
                    "subcategory": podcast[9]
                })
            return podcasts
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error getting user trending podcasts: {e}")
            return []
        
    def get_hot_trending_podcasts(self, preference=None, threshold=0.75):
        """
        Get the hot and trending podcasts
        """
        try:
            timestamp_cutoff = datetime.fromtimestamp(time.time() - 1000 * 60 * 60 * 36 / 1000.0)
            cursor = self.pg_conn.cursor()
            query = """
            SELECT DISTINCT ON (c.cid)
                p.id,
                p.title,
                p.positive_rating,
                p.negative_rating,
                p.total_rating,
                p.cover_image_url,
                p.duration_seconds,
                p.published_at,
                p.category,
                p.subcategory,
                c.cid
            FROM podcasts p
            JOIN clusters c ON p.cluster_id = c.cid
            WHERE c.hot = TRUE AND p.published_at > %s
            ORDER BY c.cid, c.hot_score DESC, c.hot_time DESC, p.published_at DESC
            LIMIT 5;
            """
            cursor.execute(query, (timestamp_cutoff,))
            all_podcasts = cursor.fetchall()
            pid = set()
            podcasts = []
            for podcast in all_podcasts:
                if podcast[0] not in pid:
                    ts = podcast[7].timestamp()
                    podcasts.append({
                        "id": podcast[0],
                        "title": podcast[1],
                        "positive_rating": podcast[2],
                        "negative_rating": podcast[3],
                        "total_rating": podcast[4],
                        "cover_image_url": podcast[5],
                        "duration": podcast[6],
                        "published_at": ts,
                        "category": podcast[8],
                        "subcategory": podcast[9]
                    })
                    pid.add(podcast[0])
            if preference:
                query = """
                SELECT DISTINCT ON (c.cid)
                    p.id,
                    p.title,
                    p.positive_rating,
                    p.negative_rating,
                    p.total_rating,
                    p.cover_image_url,
                    p.duration_seconds,
                    p.published_at,
                    p.category,
                    p.subcategory,
                    c.cid
                FROM podcasts p
                JOIN clusters c ON p.cluster_id = c.cid
                WHERE c.trending = TRUE AND p.published_at > %s AND p.embedding <=> %s > %s
                ORDER BY c.cid, p.embedding <=> %s, c.trending_score DESC, c.trending_time DESC, p.published_at DESC
                LIMIT 5;
                """
                cursor.execute(query, (timestamp_cutoff, preference, threshold, preference))
                all_podcasts = cursor.fetchall()
                for podcast in all_podcasts:
                    if podcast[0] not in pid:
                        ts = podcast[7].timestamp()
                        podcasts.append({
                            "id": podcast[0],
                            "title": podcast[1],
                            "positive_rating": podcast[2],
                            "negative_rating": podcast[3],
                            "total_rating": podcast[4],
                            "cover_image_url": podcast[5],
                            "duration": podcast[6],
                            "published_at": ts,
                            "category": podcast[8],
                            "subcategory": podcast[9]
                        })
                        pid.add(podcast[0])
            return podcasts
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error getting hot and trending podcasts: {e}")
            return []
        
    def get_base_url(self, url):
        parsed = urlparse(url)
        ext = tldextract.extract(url)
        l1 = f"{ext.domain}.{ext.suffix}"

        return parsed.netloc, l1
        
    def tag_hot_trending(self, podcast_embedding, threshold=0.7):
        """
        Tag a podcast as hot or trending
        """
        try:
            hot_links = ["reuters.com", "apnews.com", "cnn.com", "bbc.com", "nytimes.com", "wsj.com", "cnbc.com", "ft.com", "www.theguardian.com", "www.washingtonpost.com", "www.scmp.com", "english.news.cn", "www.cbc.ca", "www.forbes.com"]
            pids = set()
            search_params = {
                "output_fields": ["pid", "category", "subcategory", "keywords", "title"],
                "metric_type": "COSINE",
                "params": {
                    "radius": threshold
                }
            }
            results = self.milvus_client.search(
                collection_name="briefcast_hourly",
                data=[podcast_embedding],
                anns_field="text_vector",
                **search_params
            )
            if results and len(results) > 0:
                for result in results[0]:
                    if result.get("distance", 0) > threshold and result["entity"].get("pid"):
                        pids.add(result["entity"].get("pid"))

            results = self.milvus_client.search(
                collection_name="briefcast_daily",
                data=[podcast_embedding],
                anns_field="text_vector",
                **search_params
            )
            if results and len(results) > 0:
                for result in results[0]:
                    if result.get("distance", 0) > threshold and result["entity"].get("pid"):
                        pids.add(result["entity"].get("pid"))

            if len(pids) == 0:
                return []

            cursor = self.pg_conn.cursor()
            query = """
            SELECT cluster_id, link
            FROM podcasts
            WHERE id = ANY(%s) AND cluster_id IS NOT NULL;
            """
            cursor.execute(query, (list(pids),))
            results = cursor.fetchall()

            links = set()

            hot = False
            trending = False
            trending_time = None
            hot_time = None
            hot_score = 0
            trending_score = 0

            for link in results:
                base_url = self.get_base_url(link[1])
                if base_url not in links:
                    links.add(base_url)
                    if base_url in hot_links or any(link.endswith(base_url) for link in hot_links):
                        hot_score += 1
                    trending_score += 1

            if hot_score >= 2:
                hot = True
            if trending_score >= 4:
                trending = True


            if results:
                cid = results[0][0]
                cursor.execute("UPDATE clusters SET hot = %s, trending = %s, hot_score = %s, trending_score = %s, hot_time = %s, trending_time = %s WHERE cid = %s", (hot, trending, hot_score, trending_score, hot_time, trending_time, cid))
            else:
                cid = str(uuid.uuid4())
                cursor.execute("INSERT INTO clusters (cid, hot, trending, hot_score, trending_score, hot_time, trending_time) VALUES (%s, %s, %s, %s, %s, %s, %s)", (cid, hot, trending, hot_score, trending_score, hot_time, trending_time))

            for pid in pids:
                cursor.execute("UPDATE podcasts SET cluster_id = %s WHERE id = %s", (cid, pid))
            self.pg_conn.commit()

            return pids
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error tagging hot and trending podcasts: {e}")
            return []
            
    def update_podcast_generated_data(self, podcast_id, generated_data):
        """
        Update the generated data of a podcast in MongoDB
        
        Args:
            podcast_id (str): The ID of the podcast to update
        """
        try:
            transcript_text = generated_data.get("transcript_text", "")
            cursor = self.pg_conn.cursor()
            update_query = """
            UPDATE podcasts 
            SET audio_url = %s, transcript_url = %s, duration_seconds = %s
            WHERE id = %s
            """
            cursor.execute(update_query, (generated_data.get("audio_url", ""), generated_data.get("transcript_url", ""), generated_data.get("duration_seconds", 0), podcast_id))
            
            update_result = self.mongo_db[MONGO_PODCAST_COLLECTION].update_one(
                {"id": podcast_id},
                {
                    "$set": {
                        "transcript_text": transcript_text,
                        "modifyAt": time.time()
                    }
                }
            )

            self.pg_conn.commit()
            return True
        
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error updating podcast generated data: {e}")
            return False

    def update_podcast_transcript(self, podcast_id, transcript_text):
        """
        Update the transcript text of a podcast in MongoDB
        
        Args:
            podcast_id (str): The ID of the podcast to update
            transcript_text (str): The full transcript text
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Update in MongoDB
            update_result = self.mongo_db[MONGO_PODCAST_COLLECTION].update_one(
                {"id": podcast_id},
                {
                    "$set": {
                        "transcript_text": transcript_text,
                        "modifyAt": time.time()
                    }
                }
            )
            
            if update_result.modified_count > 0:
                print(f"Updated transcript for podcast {podcast_id}")
                return True
            else:
                print(f"No podcast found with ID {podcast_id}")
                return False
            
        except Exception as e:
            print(f"Error updating podcast transcript: {e}")
            return False

    def update_podcast_audio_url(self, podcast_id, audio_url, duration):
        """
        Update the audio URL of a podcast in MongoDB and PostgreSQL
        
        Args:
            podcast_id (str): The ID of the podcast to update
            audio_url (str): The URL to the podcast audio file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # 1. Update in MongoDB
            
            # 2. Update in PostgreSQL
            cursor = self.pg_conn.cursor()
            update_query = """
            UPDATE podcasts 
            SET audio_url = %s
            WHERE id = %s
            """
            cursor.execute(update_query, (audio_url, podcast_id))
            self.pg_conn.commit()

            return True
            
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error updating podcast audio URL: {e}")
            return False

    def update_podcast_transcript_url(self, podcast_id, transcript_url):
        """
        Update the transcript URL of a podcast in MongoDB and PostgreSQL
        
        Args:
            podcast_id (str): The ID of the podcast to update
            transcript_url (str): The URL to the podcast transcript file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # 1. Update in MongoDB
            
            # 2. Update in PostgreSQL
            cursor = self.pg_conn.cursor()
            update_query = """
            UPDATE podcasts 
            SET transcript_url = %s
            WHERE id = %s
            """
            cursor.execute(update_query, (transcript_url, podcast_id))
            self.pg_conn.commit()

            return True
            
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error updating podcast transcript URL: {e}")
            return False

    def update_podcast_cover_image_url(self, podcast_id, cover_image_url):
        """
        Update the cover image URL of a podcast in MongoDB and PostgreSQL
        
        Args:
            podcast_id (str): The ID of the podcast to update
            cover_image_url (str): The URL to the podcast cover image
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # 1. Update in MongoDB
            
            # 2. Update in PostgreSQL
            cursor = self.pg_conn.cursor()
            update_query = """
            UPDATE podcasts 
            SET cover_image_url = %s
            WHERE id = %s
            """
            cursor.execute(update_query, (cover_image_url, podcast_id))
            self.pg_conn.commit()
            
            return True
            
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error updating podcast cover image URL: {e}")
            return False
        
    def clean_empty_podcasts(self):
        """
        Clean empty podcasts from MongoDB and PostgreSQL
        """
        try:
            cursor = self.pg_conn.cursor()
            for podcast in self.mongo_db[MONGO_PODCAST_COLLECTION].find({"content": "", "createdAt": {"$lt": time.time() - 1000 * 60 * 60 * 24}}):
                cursor.execute("DELETE FROM podcasts WHERE id = %s", (podcast["id"],))
                self.mongo_db[MONGO_PODCAST_COLLECTION].delete_one({"id": podcast["id"]})
                self.milvus_client.delete(
                    collection_name=MILVUS_COLLECTION_NAME,
                    filter=f'pid in ["{podcast["id"]}"]'
                )
                self.pg_conn.commit()
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error cleaning empty podcasts: {e}")
            return False

    def check_podcast_content(self, url):
        """
        Check if the content of a podcast is empty
        """
        try:
            cursor = self.pg_conn.cursor()
            podcast = self.mongo_db[MONGO_PODCAST_COLLECTION].find_one({"link": url})
            if podcast and podcast["content"] != "":
                cursor.execute("SELECT id FROM podcasts WHERE id = %s", (podcast["id"],))
                if cursor.fetchone():
                    return True
            return False
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error checking podcast content: {e}")
            return False

    def update_play_count(self, podcast_id, play_count=1):
        """
        Update the play count of a podcast in PostgreSQL
        """
        try:
            cursor = self.pg_conn.cursor()
            cursor.execute("UPDATE podcasts SET play_count = play_count + %s WHERE id = %s", (play_count, podcast_id))
            self.pg_conn.commit()
            return True
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error updating play count: {e}")
            return False
        
        

# # Example usage
# if __name__ == "__main__":
#     # This is just for testing
#     middleware = PodcastMiddleware()
    
#     try:
#         # Example podcast data
#         podcast = {
#             "title": "Test Podcast",
#             "description": "This is a test podcast",
#             "category": "Technology",
#             "subcategory": "Programming",
#             "audio_url": "https://example.com/test.mp3",
#             "cover_image_url": "https://example.com/test.jpg"
#         }
        
#         # Example embedding (768 dimensions)
#         embedding = [0.1] * MILVUS_DIMENSION
        
#         # Store the podcast
#         podcast_id = middleware.store_podcast(podcast, embedding)
#         print(f"Stored podcast with ID: {podcast_id}")
        
#         # Retrieve the podcast
#         retrieved = middleware.get_podcast(podcast_id)
#         print(f"Retrieved podcast: {retrieved['title']}")
        
#         # Update rating
#         middleware.update_podcast_rating(podcast_id, True)
#         print("Updated podcast rating")
        
#     finally:
#         middleware.close_connections() 