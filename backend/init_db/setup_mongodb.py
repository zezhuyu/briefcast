#!/usr/bin/env python3
"""
Script to set up MongoDB schema and indexes.
"""
import os
import pymongo
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_mongodb_connection(host, port, user, password, auth_source):
    """Create a MongoDB connection"""
    connection_string = f"mongodb://"
    
    # Add authentication if provided
    if user and password:
        connection_string += f"{user}:{password}@"
    
    connection_string += f"{host}:{port}"
    
    # Add authentication source if using auth
    if user and password:
        connection_string += f"?authSource={auth_source}"
    
    try:
        client = MongoClient(connection_string)
        # Verify connection
        client.admin.command('ping')
        print(f"Connected to MongoDB at {host}:{port}")
        return client
    except ConnectionFailure:
        print(f"Failed to connect to MongoDB at {host}:{port}")
        raise

def setup_podcast_collection(db, collection_name="podcasts"):
    """Set up podcast collection with schema validation and indexes"""
    # Create or get the podcasts collection
    podcasts = db.podcasts
    
    # Define schema validation
    podcast_schema = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["title", "category", "subcategory"],
            "properties": {
                "id": {
                    "bsonType": "string",
                    "description": "Unique identifier for the podcast"
                },
                "link": {
                    "bsonType": "string",
                    "description": "URL to the podcast"
                },
                "title": {
                    "bsonType": "string",
                    "description": "Title of the podcast"
                },
                "content": {
                    "bsonType": ["string", "array"],
                    "description": "Short content or summary of the podcast",
                    "items": {
                        "bsonType": "string"
                    }
                },
                "lang": {
                    "bsonType": "string",
                    "description": "Language of the podcast"
                },
                "transcript_text": {
                    "bsonType": "string",
                    "description": "Full script or transcript of the podcast"
                },
                "description": {
                    "bsonType": "string",
                    "description": "Detailed description of the podcast"
                },
                "category": {
                    "bsonType": "string",
                    "description": "Main category of the podcast"
                },
                "subcategory": {
                    "bsonType": "string",
                    "description": "Subcategory of the podcast"
                },
                "label": {
                    "bsonType": ["string", "null"],
                    "description": "Label for the podcast"
                },
                "keywords": {
                    "bsonType": "array",
                    "description": "Keywords or tags for the podcast",
                    "items": {
                        "bsonType": "string"
                    }
                },
                "lastUpdate": {
                    "bsonType": ["string", "double", "date", "null"],
                    "description": "Last update timestamp (Unix time)"
                },
                "updatedParsed": {
                    "bsonType": ["string", "double", "date", "null"],
                    "description": "Parsed update time"
                },
                "createAt": {
                    "bsonType": "double",
                    "description": "Creation timestamp"
                },
                "published_at": {
                    "bsonType": "double",
                    "description": "Publication timestamp"
                },
                "modifyAt": {
                    "bsonType": ["double", "null"],
                    "description": "Modification timestamp (Unix time)"
                },

                # "duration": {
                #     "bsonType": "int",
                #     "description": "Duration of the podcast in seconds"
                # },
                # "positive": {
                #     "bsonType": "int",
                #     "description": "Count of positive ratings"
                # },
                # "negative": {
                #     "bsonType": "int",
                #     "description": "Count of negative ratings"
                # },
                # "totalRating": {
                #     "bsonType": "int",
                #     "description": "Total number of ratings"
                # },
                # "rating": {
                #     "bsonType": "double",
                #     "description": "Average rating score"
                # },
                # "audio_url": {
                #     "bsonType": "string",
                #     "description": "URL to the podcast audio file"
                # },
                # "transcript_url": {
                #     "bsonType": "string",
                #     "description": "URL to the podcast transcript"
                # },
                # "cover_image_url": {
                #     "bsonType": "string",
                #     "description": "URL to the podcast cover image"
                # }

            }
        }
    }
    
    # Try to create collection with validation
    try:
        db.create_collection(collection_name, validator=podcast_schema)
        print(f"Created {collection_name} collection with schema validation")
    except OperationFailure:
        # Collection might already exist
        try:
            db.command({
                "collMod": collection_name,
                "validator": podcast_schema
            })
            print(f"Updated {collection_name} collection with schema validation")
        except OperationFailure as e:
            print(f"Failed to set up schema validation: {e}")
    
    # Create indexes
    podcasts.create_index([("title", pymongo.TEXT), ("description", pymongo.TEXT), 
                          ("script", pymongo.TEXT), ("content", pymongo.TEXT)], 
                         name="text_search_index")
    podcasts.create_index([("category", pymongo.ASCENDING), ("subcategory", pymongo.ASCENDING)], 
                         name="category_index")
    podcasts.create_index("createAt", name="created_at_index")
    podcasts.create_index("id", unique=True, name="id_index")
    podcasts.create_index("milvus_id", sparse=True, name="milvus_id_index")
    podcasts.create_index("keywords", name="keywords_index")
    podcasts.create_index([("positive", pymongo.DESCENDING), ("negative", pymongo.ASCENDING)], 
                         name="ratings_index")
    
    print("Created indexes on podcasts collection")

def setup_episodes_collection(db, collection_name="episodes"):
    """Set up podcast episodes collection with schema validation and indexes"""
    # Create or get the episodes collection
    episodes = db.episodes
    
    # Define schema validation
    episode_schema = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["podcast_id", "title", "audio_url"],
            "properties": {
                "podcast_id": {
                    "bsonType": "string",
                    "description": "Reference to the parent podcast"
                },
                "title": {
                    "bsonType": "string",
                    "description": "Title of the episode"
                },
                "description": {
                    "bsonType": "string",
                    "description": "Description of the episode"
                },
                "episode_number": {
                    "bsonType": "int",
                    "description": "Episode number"
                },
                "published_at": {
                    "bsonType": "date",
                    "description": "Publication timestamp"
                },
                
                "transcript_text": {
                    "bsonType": "string",
                    "description": "Full text transcript of the episode"
                },
                "keywords": {
                    "bsonType": "array",
                    "description": "Keywords or tags for the episode",
                    "items": {
                        "bsonType": "string"
                    }
                },
            }
        }
    }
    
    # Try to create collection with validation
    try:
        db.create_collection(collection_name, validator=episode_schema)
        print(f"Created {collection_name} collection with schema validation")
    except OperationFailure:
        # Collection might already exist
        try:
            db.command({
                "collMod": collection_name,
                "validator": episode_schema
            })
            print(f"Updated {collection_name} collection with schema validation")
        except OperationFailure as e:
            print(f"Failed to set up schema validation: {e}")
    
    # Create indexes
    episodes.create_index("podcast_id", name="podcast_id_index")
    episodes.create_index([("title", pymongo.TEXT), ("description", pymongo.TEXT), ("transcript_text", pymongo.TEXT)], 
                         name="text_search_index")
    episodes.create_index("published_at", name="published_at_index")
    episodes.create_index("milvus_id", sparse=True, name="milvus_id_index")
    
    print("Created indexes on episodes collection")

def setup_mongodb(host=None, port=None, user=None, password=None, database=None, auth_source=None, podcast_collection=None, episode_collection=None):
    """
    Function to be called from other modules to set up MongoDB
    
    Args:
        host (str): MongoDB host
        port (int): MongoDB port
        user (str): MongoDB user
        password (str): MongoDB password
        database (str): MongoDB database name
        auth_source (str): MongoDB authentication source
    """
    # Set arguments from parameters or environment variables
    host = host or os.getenv('MONGO_HOST', 'localhost')
    port = port or int(os.getenv('MONGO_PORT', '27017'))
    user = user or os.getenv('MONGO_USER', '')
    password = password or os.getenv('MONGO_PASSWORD', '')
    database = database or os.getenv('MONGO_DB', 'podcast_app')
    auth_source = auth_source or os.getenv('MONGO_AUTH_SOURCE', 'admin')
    podcast_collection = podcast_collection or os.getenv('MONGO_PODCAST_COLLECTION', 'podcasts')
    episode_collection = episode_collection or os.getenv('MONGO_EPISODE_COLLECTION', 'episodes')
    
    client = get_mongodb_connection(host, port, user, password, auth_source)
    db = client[database]
    
    if not db.command('ping'):
        raise Exception("Failed to connect to MongoDB")
    
    if not podcast_collection in db.list_collection_names():
        setup_podcast_collection(db, podcast_collection)
    if not episode_collection in db.list_collection_names():
        setup_episodes_collection(db, episode_collection)
    
    print(f"MongoDB setup completed for database '{database}'")
    client.close() 
