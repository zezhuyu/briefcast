#!/usr/bin/env python3
"""
Middleware for handling user operations across databases.
This module coordinates user-related operations with PostgreSQL.
"""
import os
import time
import psycopg2
from psycopg2.extras import Json
from nanoid import generate as nanoid_generate
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pymilvus import MilvusClient
import numpy as np
from constant.history_weight import get_embeding_mean, compute_daily_embedding, compute_batch_embedding
# Load environment variables
load_dotenv()

# Database connection parameters
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', '5432'))
POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', '')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'podcast_app')

MILVUS_URL = os.getenv("MILVUS_HOST", "localhost:19530")
MILVUS_DIMENSION = int(os.getenv("MILVUS_DIMENSION", 768))
MILVUS_USER_COLLECTION_NAME = os.getenv("MILVUS_USER_COLLECTION_NAME", "briefcast_user")

def get_milvus_client():
    """Get a Milvus client"""
    return MilvusClient(MILVUS_URL)

# Generate a unique ID for internal use
def generate_id(size=21):
    """Generate a unique ID using nanoid"""
    return nanoid_generate(size=size)

# Database connection function
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

class UserMiddleware:
    """Middleware for handling user operations with PostgreSQL"""
    
    def __init__(self):
        """Initialize connection to PostgreSQL"""
        self.pg_conn = get_postgres_connection()
        self.milvus_client = get_milvus_client()
    
    def close_connections(self):
        """Close database connection"""
        if self.pg_conn:
            self.pg_conn.close()
    
    def create_user(self, user_data, perference_vector, category_preferences):
        """
        Create a new user in the database with specified category preferences
        
        Args:
            user_data (dict): User data including id, first_name, last_name, email
            category_preferences (dict): Dictionary where keys are categories and values are
                                        lists of subcategories, e.g.:
                                        {"Technology": ["Programming", "AI"], 
                                         "Science": ["Physics"]}
            
        Returns:
            str: The ID of the created user
        """
        try:
            # Use the provided Clerk ID
            user_id = user_data.get("uid")
            if not user_id:
                raise ValueError("User ID (Clerk ID) is required")
            
            cursor = self.pg_conn.cursor()
            
            # Check if user already exists
            cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            if cursor.fetchone():
                print(f"User with ID {user_id} already exists")
                return user_id        
            
            print("user_id_check_done", user_id)
            # Insert new user
            insert_query = """
            INSERT INTO users (
                id, user_name, first_name, last_name, email, prev_day_vector, realtime_vector
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """
            cursor.execute(insert_query, (
                user_id,
                user_data.get("userName", ""),
                user_data.get("firstName", ""),
                user_data.get("lastName", ""),
                user_data.get("email", ""),
                perference_vector,
                perference_vector
            ))
            print("insert_query_done")
            
            # Create category preferences if provided
            if category_preferences:
                # First, create entries in user_preferences for each category
                for category in category_preferences.keys():
                    # Insert into user_preferences first
                    insert_pref_base_query = """
                    INSERT INTO user_preferences (
                        user_id, category, level
                    ) VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, category) DO NOTHING
                    """
                    
                    cursor.execute(insert_pref_base_query, (
                        user_id,
                        category,
                        1
                    ))
                print("insert_pref_base_query_done")
                
                # Then create the category preferences that reference the user_preferences
                for category, subcategories in category_preferences.items():
                    for subcategory in subcategories:
                        insert_cat_pref_query = """
                        INSERT INTO user_category_preferences (
                            user_id, category, subcategory, level
                        ) VALUES (%s, %s, %s, %s)
                        """
                        
                        cursor.execute(insert_cat_pref_query, (
                            user_id,
                            category,
                            subcategory,
                            1
                        ))
            print("insert_cat_pref_query_done")
            
            # Commit all changes
            self.pg_conn.commit()
            self.pg_conn.autocommit = True

            self.milvus_client.insert(
                collection_name=MILVUS_USER_COLLECTION_NAME,
                data=[
                    {
                        "uid": user_id,
                        "user_name": user_data.get("userName", ""),
                        "vector": perference_vector,
                        "created_at": int(time.time())
                    }
                ]
            )
            self.milvus_client.flush(collection_name=MILVUS_USER_COLLECTION_NAME)
            
            print(f"Created user with ID: {user_id}")
            
            return user_id
            
        except Exception as e:
            self.pg_conn.rollback()
            self.pg_conn.autocommit = True
            print(f"Error creating user: {e}")
            raise
    
    def get_user(self, user_id):
        """
        Get complete user details by ID including preferences
        
        Args:
            user_id (str): The ID of the user to retrieve
            
        Returns:
            dict: Complete user data or None if not found
        """
        try:
            cursor = self.pg_conn.cursor()
            
            # Get basic user info
            user_query = """
            SELECT id, user_name, first_name, last_name, email, created_at, last_login, prev_day_vector, realtime_vector, batched_vector, daily_vector, daily_listen_count, batch_count, daily_total_weight, batch_total_weight
            FROM users
            WHERE id = %s
            """
            
            cursor.execute(user_query, (user_id,))
            user = cursor.fetchone()
            
            if not user:
                return None
                
            # Convert to dictionary
            user_dict = {
                "id": user[0],
                "user_name": user[1],
                "first_name": user[2],
                "last_name": user[3],
                "email": user[4],
                "created_at": user[5],
                "last_login": user[6],
                "prev_day_vector": user[7],
                "realtime_vector": user[8],
                "batched_vector": user[9],
                "daily_vector": user[10],
                "daily_listen_count": user[11],
                "batch_count": user[12],
                "daily_total_weight": user[13],
                "batch_total_weight": user[14],
                "category_preferences": {},
                "preferences": {}
            }
            
            # Get category preferences
            cat_pref_query = """
            SELECT category, subcategory, level
            FROM user_category_preferences
            WHERE user_id = %s
            """
            
            cursor.execute(cat_pref_query, (user_id,))
            cat_prefs = cursor.fetchall()
            
            # Group subcategories by category
            for cat, subcat, value in cat_prefs:
                if cat not in user_dict["category_preferences"]:
                    user_dict["category_preferences"][cat] = []
                
                user_dict["category_preferences"][cat].append({
                    "subcategory": subcat,
                    "value": value
                })
            
            # Get other preferences
            pref_query = """
            SELECT category, level
            FROM user_preferences
            WHERE user_id = %s
            """
            
            cursor.execute(pref_query, (user_id,))
            prefs = cursor.fetchall()
            
            for category, level in prefs:
                user_dict["preferences"][category] = level
            
            return user_dict
            
        except Exception as e:
            print(f"Error retrieving user: {e}")

            self.pg_conn.rollback()
            return None
    
    def update_user_login(self, user_id):
        """
        Update the last login time for a user
        
        Args:
            user_id (str): The ID of the user
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            cursor = self.pg_conn.cursor()
            
            update_query = """
            UPDATE users
            SET last_login = %s
            WHERE id = %s
            """
            
            cursor.execute(update_query, (datetime.now(), user_id))
            self.pg_conn.commit()
            
            return True
            
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error updating user login: {e}")
            return False
        
    def update_user_daily_update(self, user_id):
        """
        Update the last daily update time for a user
        """
        try:
            cursor = self.pg_conn.cursor()
            
            update_query = """
            UPDATE users
            SET last_daily_update = %s
            WHERE id = %s
            """
            
            cursor.execute(update_query, (datetime.now(), user_id))
            self.pg_conn.commit()
            
            return True
            
        except Exception as e:  
            self.pg_conn.rollback()
            print(f"Error updating user daily update: {e}")
            return False
        
    def get_user_last_podcast_update(self, user_id):
        """
        Get the last podcast update time for a user
        """
        try:
            cursor = self.pg_conn.cursor()
            cursor.execute("SELECT last_daily_update FROM users WHERE id = %s", (user_id,))
            last_daily_update = cursor.fetchone()
            if last_daily_update:
                return last_daily_update[0]
            return None
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error getting user last daily update: {e}")
            return None
        
    def get_user_last_daily_update(self, user_id):
        """
        Get the last daily update time for a user
        """
        try:
            cursor = self.pg_conn.cursor()  
            cursor.execute("SELECT last_daily_vector_update FROM users WHERE id = %s", (user_id,))
            last_daily_update = cursor.fetchone()
            if last_daily_update:
                return last_daily_update[0]
            return None
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error getting user last daily update: {e}")
            return None

    def add_user_category_preference(self, user_id, category, subcategory, value=3):
        """
        Add or update a category preference for a user
        
        Args:
            user_id (str): The ID of the user
            category (str): The category name
            subcategory (str): The subcategory name
            value (int): Preference value from 1-5
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            cursor = self.pg_conn.cursor()
            
            # Ensure value is in valid range
            value = max(1, min(5, value))
            
            # Begin transaction
            self.pg_conn.autocommit = False
            
            # First, ensure the category exists in user_preferences
            cursor.execute(
                "SELECT user_id FROM user_preferences WHERE user_id = %s AND category = %s",
                (user_id, category)
            )
            
            if not cursor.fetchone():
                # Insert the category into user_preferences first
                insert_pref_query = """
                INSERT INTO user_preferences (
                    user_id, category, level
                ) VALUES (%s, %s, %s)
                """
                
                cursor.execute(insert_pref_query, (
                    user_id,
                    category,
                    1
                ))
            
            # Now check if the category preference already exists
            cursor.execute(
                "SELECT user_id FROM user_category_preferences WHERE user_id = %s AND category = %s AND subcategory = %s",
                (user_id, category, subcategory)
            )
            
            if cursor.fetchone():
                # Update existing preference
                update_query = """
                UPDATE user_category_preferences
                SET value = %s
                WHERE user_id = %s AND category = %s AND subcategory = %s
                """
                
                cursor.execute(update_query, (value, user_id, category, subcategory))
            else:
                # Insert new preference
                insert_query = """
                INSERT INTO user_category_preferences (
                    user_id, category, subcategory, level
                ) VALUES (%s, %s, %s, %s)
                """
                
                cursor.execute(insert_query, (
                    user_id,
                    category,
                    subcategory,
                    value
                ))
            
            self.pg_conn.commit()
            self.pg_conn.autocommit = True
            return True
            
        except Exception as e:
            self.pg_conn.rollback()
            self.pg_conn.autocommit = True
            print(f"Error adding user category preference: {e}")
            return False
    
    def get_user_category_preferences(self, user_id):
        """
        Get all category preferences for a user
        
        Args:
            user_id (str): The ID of the user
            
        Returns:
            list: List of category preference dictionaries
        """
        try:
            cursor = self.pg_conn.cursor()
            
            query = """
            SELECT category, subcategory, level
            FROM user_category_preferences
            WHERE user_id = %s
            """
            
            cursor.execute(query, (user_id,))
            results = cursor.fetchall()
            
            # Convert to list of dictionaries
            preferences = []
            for category, subcategory, value in results:
                preferences.append({
                    "category": category,
                    "subcategory": subcategory,
                    "value": value
                })
            
            return preferences
            
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error retrieving user category preferences: {e}")
            return []
        
    def add_user_search_history(self, user_id, search_query):
        """
        Add a search query to user's search history
        """
        try:
            cursor = self.pg_conn.cursor()
            insert_query = """
            INSERT INTO search_history (user_id, search_query) VALUES (%s, %s)
            """
            cursor.execute(insert_query, (user_id, search_query))
            self.pg_conn.commit()
            return True
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error adding user search history: {e}")
            return False
        
    def update_user_listen_position(self, user_id, podcast_id, position):
        """
        Update the listen position for a user
        """
        try:
            cursor = self.pg_conn.cursor() 
            query = """SELECT * FROM user_podcast_history WHERE user_id = %s AND podcast_id = %s AND hidden = FALSE ORDER BY listened_at DESC LIMIT 1"""
            cursor.execute(query, (user_id, podcast_id))
            history = cursor.fetchone()
            if history:
                update_query = """
                UPDATE user_podcast_history SET stop_position_seconds = %s, listened_at = now() WHERE user_id = %s AND podcast_id = %s AND hidden = FALSE
                """
                cursor.execute(update_query, (position, user_id, podcast_id))
            else:
                insert_query = """
                INSERT INTO user_podcast_history (user_id, podcast_id, stop_position_seconds, listened_at, hidden) VALUES (%s, %s, %s, now(), FALSE)
                """
                cursor.execute(insert_query, (user_id, podcast_id, position))
            self.pg_conn.commit()
            return True
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error updating user listen position: {e}")
            return False
    
    def add_to_listening_history(self, user_id, podcast_id, user_activity, completed=False, hidden=False):
        """
        Add a podcast to user's listening history
        
        Args:
            user_id (str): The ID of the user
            podcast_id (str): The ID of the podcast
            duration_seconds (int): Duration listened in seconds
            completed (bool): Whether the podcast was completed
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            cursor = self.pg_conn.cursor()

            # Check if the podcast is already in the history
            cursor.execute("SELECT user_id FROM user_podcast_history WHERE user_id = %s AND podcast_id = %s AND hidden = %s", (user_id, podcast_id, hidden))
            history = cursor.fetchone()
            if history and not hidden:
                # Update the history entry
                update_query = """
                UPDATE user_podcast_history
                SET
                listened_at = now(),
                hidden = %s,
                listen_duration_seconds = listen_duration_seconds + %s, 
                stop_position_seconds = %s, 
                completed = %s, 
                play_count = play_count + 1,
                share_count = share_count + %s,
                download_count = download_count + %s,
                add_to_playlist = add_to_playlist + %s,
                rating = %s
                WHERE user_id = %s AND podcast_id = %s AND hidden = FALSE
                """
                cursor.execute(update_query, (hidden, user_activity['listen_duration_seconds'], user_activity['stop_position_seconds'], completed, user_activity['share_count'], user_activity['download_count'], user_activity['add_to_playlist'], user_activity['rating'], user_id, podcast_id))
                self.pg_conn.commit()
                return True
            if not hidden:
                hidden = False
                listen_duration_seconds = user_activity['listen_duration_seconds']
                stop_position_seconds = user_activity['stop_position_seconds']
                completed = completed
                share_count = user_activity['share_count']
                download_count = user_activity['download_count']
                add_to_playlist = user_activity['add_to_playlist']
                rating = user_activity['rating']
            else:
                hidden = True
                listen_duration_seconds = 0
                stop_position_seconds = 0
                completed = False
                share_count = 0
                download_count = 0
                add_to_playlist = 0
                rating = 0
            # Insert new history entry
            insert_query = """
            INSERT INTO user_podcast_history (
                user_id, podcast_id, 
                listen_duration_seconds,
                stop_position_seconds,
                completed,
                hidden,
                play_count,
                share_count,
                download_count,
                add_to_playlist,
                rating
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            cursor.execute(insert_query, (
                user_id,
                podcast_id,
                listen_duration_seconds,
                stop_position_seconds,
                completed,
                hidden,
                1,
                share_count,
                download_count,
                add_to_playlist,
                rating
            ))
            
            self.pg_conn.commit()
            return True
            
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error adding to listening history: {e}")
            return False
        
    def get_complete_user_history(self, user_id, podcast_ids=[], include_hidden=False):
        """
        Get complete user history
        """
        try:
            cursor = self.pg_conn.cursor()
            if len(podcast_ids) > 0:
                if include_hidden:
                    query = """
                    SELECT * FROM user_podcast_history WHERE user_id = %s AND podcast_id IN %s
                    """
                    cursor.execute(query, (user_id, tuple(podcast_ids)))
                else:
                    query = """
                    SELECT * FROM user_podcast_history WHERE user_id = %s AND podcast_id IN %s AND hidden = FALSE
                    """
                    cursor.execute(query, (user_id, tuple(podcast_ids)))
            else:
                if include_hidden:
                    query = """
                    SELECT * FROM user_podcast_history WHERE user_id = %s
                    """
                    cursor.execute(query, (user_id,))
                else:
                    query = """
                    SELECT * FROM user_podcast_history WHERE user_id = %s AND hidden = FALSE
                    """
                    cursor.execute(query, (user_id,))
            history = cursor.fetchall()
            complete_history = []
            for item in history:
                complete_history.append({
                    "user_id": item[0],
                    "podcast_id": item[1],
                    "listened_at": item[2],
                    "hidden": item[3],
                    "listen_duration_seconds": item[4],
                    "stop_position_seconds": item[5],
                    "completed": item[6],
                    "play_count": item[7],
                    "reaction": item[8],
                    "share_count": item[9],
                    "download_count": item[10],
                    "add_to_playlist": item[11],
                    "rating": item[12],
                    "device_type": item[13],
                    "app_version": item[14]
                })
            return complete_history
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error getting complete user history: {e}")
            return []
            
    
    def get_listening_history(self, user_id, limit=50, time_limit=30):
        """
        Get user's listening history
        
        Args:
            user_id (str): The ID of the user
            limit (int): Maximum number of history items to return
            
        Returns:
            list: List of listening history items
        """
        try:
            time = datetime.now() - timedelta(days=time_limit)
            cursor = self.pg_conn.cursor()
            
            query = """
            SELECT h.podcast_id, h.listened_at, h.stop_position_seconds, h.completed, h.hidden,
                   p.title, p.category, p.subcategory, p.cover_image_url, p.duration_seconds
            FROM user_podcast_history h
            JOIN podcasts p ON h.podcast_id = p.id
            WHERE h.user_id = %s AND h.listened_at > %s
            ORDER BY h.listened_at DESC
            LIMIT %s
            """
            
            cursor.execute(query, (user_id, time, limit))
            history = cursor.fetchall()
            
            # Convert to list of dictionaries
            result = []
            for item in history:
                result.append({
                    "id": item[0],
                    "listened_at": item[1],
                    "stop_position_seconds": item[2],
                    "completed": item[3],
                    "hidden": item[4],
                    "title": item[5],
                    "category": item[6],
                    "subcategory": item[7],
                    "cover_image_url": item[8],
                    "duration_seconds": item[9]
                })
            
            return result
            
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error retrieving listening history: {e}")
            return []
    
    def create_playlist(self, user_id, name, description=""):
        """
        Create a new playlist for a user
        
        Args:
            user_id (str): The ID of the user
            name (str): The name of the playlist
            description (str): Optional description of the playlist
            
        Returns:
            str: The ID of the created playlist or None if failed
        """
        try:
            cursor = self.pg_conn.cursor()
            
            # Check if playlist already exists
            cursor.execute(
                "SELECT playlist_id FROM user_podcast_playlists WHERE user_id = %s AND name = %s",
                (user_id, name)
            )
            if cursor.fetchone():
                print(f"Playlist with name {name} already exists for user {user_id}")
                return None
            
            # Generate a unique ID for the playlist
            playlist_id = generate_id()
            
            # Insert new playlist
            insert_query = """
            INSERT INTO user_podcast_playlists (
                playlist_id, user_id, name, description
            ) VALUES (%s, %s, %s, %s)
            RETURNING playlist_id;
            """
            
            cursor.execute(insert_query, (
                playlist_id,
                user_id,
                name,
                description
            ))
            
            self.pg_conn.commit()
            
            return playlist_id
            
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error creating playlist: {e}")
            return None
        
    def rename_playlist(self, playlist_id, name, description=""):
        """
        Rename a playlist
        """
        try:
            cursor = self.pg_conn.cursor()  
            
            update_query = """
            UPDATE user_podcast_playlists
            SET name = %s, description = %s
            WHERE playlist_id = %s
            """
            cursor.execute(update_query, (name, description, playlist_id))
            self.pg_conn.commit()
            return True
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error renaming playlist: {e}")
            return False
        
    def delete_playlist(self, playlist_id):
        """
        Delete a playlist
        """
        try:
            cursor = self.pg_conn.cursor()
            
            # Delete playlist items
            delete_items_query = """
            DELETE FROM podcast_playlist_items WHERE playlist_id = %s
            """
            cursor.execute(delete_items_query, (playlist_id,))
            
            # Delete playlist
            delete_playlist_query = """
            DELETE FROM user_podcast_playlists WHERE playlist_id = %s
            """
            cursor.execute(delete_playlist_query, (playlist_id,))   
            
            self.pg_conn.commit()
            return True
        
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error deleting playlist: {e}")
            return False
        
    def add_to_playlist(self, playlist_id, podcast_id, user_id, position=None):
        """
        Add a podcast to a playlist
        
        Args:
            playlist_id (str): The ID of the playlist
            podcast_id (str): The ID of the podcast
            position (int): Optional position in the playlist
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            cursor = self.pg_conn.cursor()
            
            if playlist_id == "favorite":
                cursor.execute(
                    "SELECT user_id FROM user_favorite_podcasts WHERE user_id = %s AND podcast_id = %s",
                    (user_id, podcast_id)
                )
                if cursor.fetchone():
                    return True
                insert_query = """
                INSERT INTO user_favorite_podcasts (
                    user_id, podcast_id
                ) VALUES (%s, %s)
                """
                cursor.execute(insert_query, (user_id, podcast_id))
                self.pg_conn.commit()
                return True
            elif playlist_id == "like":
                cursor.execute(
                    "SELECT user_id FROM user_liked_podcasts WHERE user_id = %s AND podcast_id = %s",
                    (user_id, podcast_id)
                )
                if cursor.fetchone():
                    return True
                insert_query = """
                INSERT INTO user_liked_podcasts (
                    user_id, podcast_id
                ) VALUES (%s, %s)
                """
                cursor.execute(insert_query, (user_id, podcast_id)) 
                self.pg_conn.commit()
                return True
            else:
                # Check if podcast is already in the playlist
                cursor.execute(
                    "SELECT playlist_id FROM podcast_playlist_items WHERE playlist_id = %s AND podcast_id = %s",
                    (playlist_id, podcast_id)
                )
            
                if cursor.fetchone():
                    # Already in playlist
                    return True
                
                # Get the max position if not specified
                if position is None:
                    cursor.execute(
                        "SELECT COALESCE(MAX(position), 0) FROM podcast_playlist_items WHERE playlist_id = %s",
                        (playlist_id,)
                    )
                    position = cursor.fetchone()[0] + 1
                
                # Insert new playlist item
                insert_query = """
                INSERT INTO podcast_playlist_items (
                    playlist_id, podcast_id, position
                ) VALUES (%s, %s, %s)
                """
                
                cursor.execute(insert_query, (
                    playlist_id,
                    podcast_id,
                    position
                ))
                
                self.pg_conn.commit()
                return True
            
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error adding to playlist: {e}")
            return False
    
    def delete_from_playlist(self, playlist_id, podcast_id, user_id):
        """
        Delete a podcast from a playlist
        """
        try:
            cursor = self.pg_conn.cursor()
            if playlist_id == "favorite":
                delete_query = """  
                DELETE FROM user_favorite_podcasts WHERE user_id = %s AND podcast_id = %s
                """
                cursor.execute(delete_query, (user_id, podcast_id))
            elif playlist_id == "like":
                delete_query = """  
                DELETE FROM user_liked_podcasts WHERE user_id = %s AND podcast_id = %s
                """
                cursor.execute(delete_query, (user_id, podcast_id)) 
            else:
                delete_query = """  
                DELETE FROM podcast_playlist_items WHERE playlist_id = %s AND podcast_id = %s
                """
                cursor.execute(delete_query, (playlist_id, podcast_id))
            
            self.pg_conn.commit()
            return True

        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error deleting from playlist: {e}")
            return False

    def get_user_playlists(self, user_id):
        """
        Get all playlists for a user
        
        Args:
            user_id (str): The ID of the user
            
        Returns:
            list: List of playlist dictionaries
        """
        try:
            cursor = self.pg_conn.cursor()
            
            query = """
            SELECT playlist_id, name, description, created_at
            FROM user_podcast_playlists
            WHERE user_id = %s
            ORDER BY created_at DESC
            """
            
            cursor.execute(query, (user_id,))
            playlists = cursor.fetchall()
            
            # Convert to list of dictionaries
            result = []
            result.append({
                "id": "favorite",
                "name": "Favorite",
                "description": "Favorite podcasts",
                "created_at": None
            })
            result.append({
                "id": "like",
                "name": "Liked",
                "description": "Liked podcasts",
                "created_at": None
            })
            for playlist in playlists:
                result.append({
                    "id": playlist[0],
                    "name": playlist[1],
                    "description": playlist[2],
                    "created_at": playlist[3]
                })
            return result
            
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error retrieving user playlists: {e}")
            return []
    
    def get_playlist_items(self, playlist_id, user_id):
        """
        Get all items in a playlist
        
        Args:
            playlist_id (str): The ID of the playlist
            
        Returns:
            list: List of playlist item dictionaries
        """
        try:
            cursor = self.pg_conn.cursor()
            if playlist_id == "favorite":
                query = """
                SELECT i.podcast_id, i.added_at,
                       p.title, p.category, p.subcategory, p.cover_image_url
                FROM user_favorite_podcasts i
                JOIN podcasts p ON i.podcast_id = p.id
                WHERE i.user_id = %s
                ORDER BY i.added_at DESC
                """ 
                cursor.execute(query, (user_id,))
            elif playlist_id == "like":
                query = """
                SELECT i.podcast_id, i.liked_at,
                       p.title, p.category, p.subcategory, p.cover_image_url
                FROM user_liked_podcasts i
                JOIN podcasts p ON i.podcast_id = p.id
                WHERE i.user_id = %s
                ORDER BY i.liked_at DESC
                """
                cursor.execute(query, (user_id,))
            else:
                query = """
                SELECT i.podcast_id, i.added_at,
                        p.title, p.category, p.subcategory, p.cover_image_url
                FROM podcast_playlist_items i
                JOIN podcasts p ON i.podcast_id = p.id
                WHERE i.playlist_id = %s
                ORDER BY i.added_at DESC
                """
                cursor.execute(query, (playlist_id,))
            

            items = cursor.fetchall()
            # Convert to list of dictionaries
            result = []
            for item in items:
                result.append({
                    "id": item[0],
                    "added_at": item[1],
                    "title": item[2],
                    "category": item[3],
                    "subcategory": item[4],
                    "cover_image_url": item[5]
                })
            
            return result
            
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error retrieving playlist items: {e}")
            return []
    
    def like_podcast(self, user_id, podcast_id):
        """
        Add a podcast to user's liked podcasts
        
        Args:
            user_id (str): The ID of the user
            podcast_id (str): The ID of the podcast
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            cursor = self.pg_conn.cursor()
            
            # Check if already liked
            cursor.execute(
                "SELECT user_id FROM user_liked_podcasts WHERE user_id = %s AND podcast_id = %s",
                (user_id, podcast_id)
            )
            
            if cursor.fetchone():
                # Already liked
                return True
            
            # Check if already disliked
            cursor.execute(
                "SELECT user_id FROM user_disliked_podcasts WHERE user_id = %s AND podcast_id = %s",
                (user_id, podcast_id)
            )
            if cursor.fetchone():
                # Remove from disliked podcasts 
                cursor.execute(
                    "DELETE FROM user_disliked_podcasts WHERE user_id = %s AND podcast_id = %s",
                    (user_id, podcast_id)
                )
            
            # Insert new like
            insert_query = """
            INSERT INTO user_liked_podcasts (
                user_id, podcast_id
            ) VALUES (%s, %s)
            """
            
            cursor.execute(insert_query, (
                user_id,
                podcast_id
            ))
            
            self.pg_conn.commit()
            
            return True
            
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error liking podcast: {e}")
            return False
    
    def dislike_podcast(self, user_id, podcast_id):
        """
        Remove a podcast from user's liked podcasts
        """
        try:
            cursor = self.pg_conn.cursor()

            # Check if already disliked
            cursor.execute(
                "SELECT user_id FROM user_disliked_podcasts WHERE user_id = %s AND podcast_id = %s",
                (user_id, podcast_id)
            )
            if cursor.fetchone():
                # Already disliked
                return True

            cursor.execute(
                "SELECT user_id FROM user_liked_podcasts WHERE user_id = %s AND podcast_id = %s",
                (user_id, podcast_id)
            )
            if cursor.fetchone():
                # Remove from liked podcasts
                cursor.execute(
                    "DELETE FROM user_liked_podcasts WHERE user_id = %s AND podcast_id = %s",
                    (user_id, podcast_id)
                )
            
            # Insert new dislike
            insert_query = """
            INSERT INTO user_disliked_podcasts (
                user_id, podcast_id
            ) VALUES (%s, %s)
            """
            cursor.execute(insert_query, (user_id, podcast_id))
            self.pg_conn.commit()
            return True
                
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error disliking podcast: {e}")
            return False
        
    def neutralize_podcast(self, user_id, podcast_id):
        """
        Neutralize a podcast for a user
        """
        try:
            cursor = self.pg_conn.cursor()  
            cursor.execute("DELETE FROM user_liked_podcasts WHERE user_id = %s AND podcast_id = %s", (user_id, podcast_id))
            cursor.execute("DELETE FROM user_disliked_podcasts WHERE user_id = %s AND podcast_id = %s", (user_id, podcast_id))
            self.pg_conn.commit()
            return True
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error neutralizing podcast: {e}")
            return False
        
    def get_user_podcast_rating(self, user_id, podcast_id):
        """
        Get the rating of a podcast for a user
        """
        try:
            cursor = self.pg_conn.cursor()
            cursor.execute("SELECT user_id FROM user_liked_podcasts WHERE user_id = %s AND podcast_id = %s", (user_id, podcast_id))
            if cursor.fetchone():
                return 1
            cursor.execute("SELECT user_id FROM user_disliked_podcasts WHERE user_id = %s AND podcast_id = %s", (user_id, podcast_id))
            if cursor.fetchone():
                return -1
            return 0
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error getting user podcast rating: {e}")
            return 0
            
    def get_user_podcast_favorite(self, user_id, podcast_id):
        """
        Get the favorite status of a podcast for a user
        """
        try:
            cursor = self.pg_conn.cursor() 
            cursor.execute("SELECT user_id FROM user_favorite_podcasts WHERE user_id = %s AND podcast_id = %s", (user_id, podcast_id))
            if cursor.fetchone():
                return True
            return False
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error getting user podcast favorite: {e}")
            return False


    def get_liked_podcasts(self, user_id, limit=50):
        """
        Get all podcasts liked by a user
        
        Args:
            user_id (str): The ID of the user
            limit (int): Maximum number of podcasts to return
            
        Returns:
            list: List of podcast dictionaries
        """
        try:
            cursor = self.pg_conn.cursor()
            
            query = """
            SELECT l.podcast_id, l.liked_at,
                   p.title, p.category, p.subcategory, p.cover_image_url
            FROM user_liked_podcasts l
            JOIN podcasts p ON l.podcast_id = p.id
            WHERE l.user_id = %s
            ORDER BY l.liked_at DESC
            LIMIT %s
            """
            
            cursor.execute(query, (user_id, limit))
            podcasts = cursor.fetchall()
            
            # Convert to list of dictionaries
            result = []
            for podcast in podcasts:
                result.append({
                    "podcast_id": podcast[0],
                    "liked_at": podcast[1],
                    "title": podcast[2],
                    "category": podcast[3],
                    "subcategory": podcast[4],
                    "cover_image_url": podcast[5]
                })
            
            return result
            
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error retrieving liked podcasts: {e}")
            return []
        
    def update_user_daily_embedding(self, user_id, embedding, weight):
        """ 
        Update the daily embedding for a user
        """
        try:
            cursor = self.pg_conn.cursor()
            cursor.execute("SELECT daily_vector, last_daily_vector_update FROM users WHERE id = %s", (user_id,))
            user_info = cursor.fetchone()
            daily_vector = user_info[0]
            last_update_time = user_info[1]
            total_weight = embedding * weight
            if daily_vector is not None:
                total_weight += np.array(eval(daily_vector))
            cursor.execute("UPDATE users SET daily_vector = %s, daily_total_weight = daily_total_weight + %s, daily_listen_count = daily_listen_count + 1 WHERE id = %s", (total_weight, weight, user_id))
            self.pg_conn.commit()
            return last_update_time
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error updating user daily embedding: {e}")
            return None
        
    def update_user_batch_embedding(self, user_id, embedding, weight):
        """
        Update the batch embedding for a user
        """
        try:
            cursor = self.pg_conn.cursor()
            cursor.execute("SELECT batched_vector, batch_count FROM users WHERE id = %s", (user_id,))
            user_info = cursor.fetchone()
            batched_vector = user_info[0]
            batch_count = user_info[1]
            total_weight = embedding * weight
            if batched_vector is not None:  
                total_weight += np.array(eval(batched_vector))
            cursor.execute("UPDATE users SET batched_vector = %s, batch_total_weight = batch_total_weight + %s, batch_count = batch_count + 1 WHERE id = %s", (total_weight, weight, user_id))
            self.pg_conn.commit()
            return batch_count + 1
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error updating user batch embedding: {e}")
            return -1
        
    def update_realtime_embedding(self, user_id):
        """
        Update the realtime embedding for a user
        """
        try:
            cursor = self.pg_conn.cursor()
            cursor.execute("SELECT realtime_vector, batched_vector, batch_total_weight, batch_count FROM users WHERE id = %s", (user_id,))
            user_info = cursor.fetchone()
            prev_vector = user_info[0]
            prev_vector = np.array(eval(prev_vector))
            batched_vector = user_info[1]
            batched_vector = np.array(eval(batched_vector))
            batch_total_weight = user_info[2]
            batch_count = user_info[3]
            realtime_vector = np.zeros(768)
            zero_weight = np.zeros(768)
            if batch_total_weight is not None and batched_vector is not None:
                realtime_vector = get_embeding_mean(batched_vector, batch_total_weight)
            if prev_vector is not None:
                realtime_vector = compute_batch_embedding(prev_vector, realtime_vector)
            cursor.execute("UPDATE users SET realtime_vector = %s, batched_vector = %s, batch_total_weight = 0.0, batch_count = 0 WHERE id = %s", (realtime_vector, zero_weight, user_id))
            self.pg_conn.commit()
            return True
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error updating user realtime embedding: {e}")
            return False

    def update_prevday_embedding(self, user_id):
        """
        Update the previous day embedding for a user
        """
        try:
            cursor = self.pg_conn.cursor()
            cursor.execute("SELECT prev_day_vector, daily_vector, daily_total_weight, daily_listen_count, user_name FROM users WHERE id = %s", (user_id,))
            user_info = cursor.fetchone()
            prev_day_vector = user_info[0]
            prev_day_vector = np.array(eval(prev_day_vector))
            daily_vector = user_info[1]
            daily_vector = np.array(eval(daily_vector))
            daily_total_weight = user_info[2]
            daily_listen_count = user_info[3]
            user_name = user_info[4]
            zero_weight = np.zeros(768)
            daily_mean = np.zeros(768)
            if daily_total_weight is not None and daily_vector is not None:
                daily_mean = get_embeding_mean(daily_vector, daily_total_weight)
            if prev_day_vector is not None:
                daily_mean = compute_daily_embedding(prev_day_vector, daily_mean)
            cursor.execute("UPDATE users SET prev_day_vector = %s, daily_vector = %s, daily_total_weight = 0.0, daily_listen_count = 0, last_daily_vector_update = now() WHERE id = %s", (daily_mean, zero_weight, user_id))
            self.pg_conn.commit()
            self.milvus_client.upsert(
                collection_name=MILVUS_USER_COLLECTION_NAME,
                data=[{
                    "uid": user_id,
                    "user_name": user_name,
                    "vector": daily_mean,
                    "created_at": int(time.time())
                }]
            )
            return True
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error updating user previous day embedding: {e}")

    def check_user_exist(self, user_id):
        """
        Check if a user exists
        """
        try:
            cursor = self.pg_conn.cursor()
            cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            res = cursor.fetchone()
            return res is not None
        except Exception as e:
            self.pg_conn.rollback()
            print(f"Error checking user existence: {e}")
            return False

    def match_user_preference(self, podcast_embedding, threshold=0.85):
        """
        Match a user's preference to a podcast
        """
        try:
            search_params = {
                "output_fields": ["uid", "user_name"],
                "params": {
                    "radius": threshold
                }
            }
            res = self.milvus_client.search(
                collection_name=MILVUS_USER_COLLECTION_NAME,
                anns_field="vector",
                data=[podcast_embedding],
                search_params=search_params
            )
            filtered = [item for item in res[0] if item.get("distance", 0) > threshold]
            if len(filtered) > 0:
                return filtered
            else:
                return None
        except Exception as e:
            print(f"Error matching user preference: {e}")
            return None
# Example usage
# if __name__ == "__main__":
#     # This is just for testing
#     middleware = UserMiddleware()
    
#     try:
#         # Example user data
#         user = {
#             "id": "user_clerk_123",
#             "first_name": "John",
#             "last_name": "Doe",
#             "email": "john.doe@example.com"
#         }
        
#         # Create user
#         user_id = middleware.create_user(user)
#         print(f"Created user with ID: {user_id}")
        
#         # Add category preference
#         middleware.add_user_category_preference(user_id, "Technology", "Technology", 5)
#         print("Added category preference")
        
#         # Create playlist
#         playlist_id = middleware.create_playlist(user_id, "My Favorite Tech Podcasts")
#         print(f"Created playlist with ID: {playlist_id}")
        
#     finally:
#         middleware.close_connections() 