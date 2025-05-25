import asyncio
import threading
import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.audio_services import create_transition_audio_by_ids, load_content
from services.image_service import load_image
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from functools import wraps
import jwt
from datetime import datetime, timedelta
import os, numpy as np
import requests
from db.podcast_middleware import PodcastMiddleware
from db.user_middleware import UserMiddleware
from db.minio_middleware import MinioMiddleware
from constant.preference import topic_embedding, preference_embedding
from services.daily import load_daily_news
from services.user_activity import like_or_dislike, search, user_activity_log
from dotenv import load_dotenv
import redis
import json
load_dotenv()

preference_dim = int(os.environ.get('MILVUS_DIMENSION', 768))

podcast_middleware = PodcastMiddleware()
user_middleware = UserMiddleware()
minio_middleware = MinioMiddleware()

r = redis.Redis(host=os.environ.get('REDIS_HOST'), port=os.environ.get('REDIS_PORT'), db=os.environ.get('REDIS_DB'))

app = Flask(__name__)
CORS(app)
CORS(app, origins=["http://localhost:3000", "https://briefcast.net", "https://briefcast.grandrecs.com"], supports_credentials=True)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')

CLERK_SECRET_KEY = os.environ.get('CLERK_SECRET_KEY')
CLERK_JWT_URL = os.environ.get('CLERK_JWT_URL')

response = requests.get(CLERK_JWT_URL)
response.raise_for_status()
jwks = response.json()

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].replace('Bearer ', '')
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401

        try:
            # Decode the token
            header = jwt.get_unverified_header(token)
            key = next((key for key in jwks["keys"] if key["kid"] == header["kid"]), None)
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
            data = jwt.decode(token, public_key, algorithms=["RS256"])

            if not user_middleware.check_user_exist(str(data.get('uid'))):
                return jsonify({'error': 'User not found'}), 401
            
            # Add user info to request headers
            request.headers = {
                **request.headers,
                'X-User-ID': str(data.get('uid')),
                'X-User-Name': str(data.get('userName'))
            }
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

        return f(*args, **kwargs)
    return decorated

# File endpoints
@app.route('/files/<file_type>/<file_name>', methods=['GET'])
@app.route('/files/<user_id>/<file_type>/<file_name>', methods=['GET'])
def get_file(file_type, file_name, user_id=None):
    try:
        if user_id:
            file = minio_middleware.get_user_file(user_id, f"{file_type}/{file_name}")
        else:
            file = minio_middleware.get_file(f"{file_type}/{file_name}")
        
        if file:
            file_type = file_type.lower()   
            name, ext = os.path.splitext(file_name)
            if file_type == "audio" or ext == ".wav":
                return send_file(file, mimetype='audio/mpeg')
            elif file_type == "image" or ext == ".jpg" or ext == ".jpeg" or ext == ".png":
                return send_file(file, mimetype='image/jpeg')
            elif file_type == "transcript" or ext == ".txt" or ext == ".lrc":
                return send_file(file, mimetype='text/plain')
        else:
            return jsonify({"error": "File not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Podcast endpoints
@app.route('/podcast/<podcast_id>', methods=['GET'])
def get_podcast(podcast_id):
    try:
        token = None
        if 'Authorization' in request.headers and request.headers['Authorization'] != "":
            token = request.headers['Authorization'].replace('Bearer ', '')
        if token:
            header = jwt.get_unverified_header(token)
            key = next((key for key in jwks["keys"] if key["kid"] == header["kid"]), None)
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
            user_info = jwt.decode(token, public_key, algorithms=["RS256"])
            user_id = str(user_info.get('uid'))
        else:
            user_id = None
        podcast = podcast_middleware.get_podcast_by_id(podcast_id)

        if not podcast:
            return jsonify({"error": "Podcast not found"}), 404
        if podcast["cover_image_url"] == "":
            def load_image_task():
                asyncio.run(load_image(podcast, return_file=False))
            threading.Thread(target=load_image_task).start()
            podcast["cover_image_url"] = ""
        if podcast["audio_url"] == "": 
            def load_content_task():
                asyncio.run(load_content(podcast))
            threading.Thread(target=load_content_task).start()
        podcast = podcast_middleware.get_podcast_by_id(podcast_id)
        
        rating = 0
        favorite = False
        if user_id:
            rating = user_middleware.get_user_podcast_rating(user_id, podcast_id)
            favorite = user_middleware.get_user_podcast_favorite(user_id, podcast_id)
        data = {
            "id": podcast["id"],
            "title": podcast["title"],
            "description": podcast["description"],
            "duration": podcast["duration"],
            "audio_url": podcast["audio_url"],
            "transcript_url": podcast["transcript_url"],
            "cover_image_url": podcast["cover_image_url"],
            "country": podcast["country"],
            "category": podcast["category"],
            "subcategory": podcast["subcategory"],
            "keywords": podcast["keywords"],
            "createAt": podcast["published_at"],
            "totalRating": podcast["total_rating"],
            "rating": rating,
            "favorite": favorite,
            "positive": podcast["positive_rating"],
            "negative": podcast["negative_rating"],
        }
        if podcast["audio_url"] != "":
            podcast_middleware.update_play_count(podcast_id)
        return jsonify(data)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Authentication endpoints
@app.route('/sign-up', methods=['POST'])
# @token_required
def sign_up():
    try:
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].replace('Bearer ', '')
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        header = jwt.get_unverified_header(token)
        key = next((key for key in jwks["keys"] if key["kid"] == header["kid"]), None)
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
        user_info = jwt.decode(token, public_key, algorithms=["RS256"])
        data = request.json

        user_perference = np.zeros(preference_dim)
        count = 0

        for topic in data["topics"]["subtopics"]:
            if len(data["topics"]["subtopics"][topic]) == 0:
                user_perference += topic_embedding[topic]
                count += 1
            else:
                for subtopic in data["topics"]["subtopics"][topic]:
                    user_perference += preference_embedding[topic][subtopic]
                    count += 1
        user_perference = user_perference / count

        user_middleware.create_user(user_info, user_perference, data["topics"])

        return jsonify({"message": "User signed up successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Generation endpoint
@app.route('/generate', methods=['POST'])
@token_required
def generate():
    try:
        user_id = request.headers.get('X-User-ID')
        user_name = request.headers.get('X-User-Name')
        location = request.json.get("location", None)
        force = request.json.get("force", False)
        print(user_id, location)
        daily_news = load_daily_news(user_id, force, location)
        if daily_news:
            data = {
                "id": daily_news["id"],
                "title": daily_news["title"],
                "description": daily_news["description"],
                "duration": daily_news["duration"],
                "audio_url": daily_news["audio_url"],
                "transcript_url": daily_news["transcript_url"],
                "cover_image_url": daily_news["cover_image_url"],
                "country": daily_news["country"],
                "category": daily_news["category"],
                "subcategory": daily_news["subcategory"],
                "keywords": daily_news["keywords"],
                "createAt": daily_news["published_at"],
                "totalRating": daily_news["total_rating"],
                "rating": daily_news["rating"],
                "favorite": daily_news["favorite"],
                "positive": daily_news["positive_rating"],
                "negative": daily_news["negative_rating"],
            }
            return jsonify(data)
        else:
            return jsonify({"error": "No daily news found"}), 404

        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# History endpoint
@app.route('/history', methods=['GET'])
@token_required
def get_history():
    try:
        user_id = request.headers.get('X-User-ID')
        history = user_middleware.get_listening_history(user_id)
        podcasts = []
        for item in history:
            if not item["hidden"]:
                podcasts.append(item)
        return jsonify(podcasts)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Recommendations endpoint
@app.route('/recommendations', methods=['GET'])
@token_required
def get_recommendations():
    try:
        user_id = request.headers.get('X-User-ID')
        real_time_vector = user_middleware.get_user(user_id)["realtime_vector"]
        real_time_vector = np.array(eval(real_time_vector))
        history = user_middleware.get_listening_history(user_id)
        ids = None
        if history:
            ids = [item["id"] for item in history]
        pids = podcast_middleware.search_podcasts_by_vector(real_time_vector, history=ids, limit=10, hourly=True, daily=True, weekly=True)
        podcasts = podcast_middleware.get_podcasts_by_ids(pids)
        podcasts_with_image = []
        for podcast in podcasts:
            if podcast["cover_image_url"] == "":
                image_url = asyncio.run(load_image(podcast, return_file=False))
                podcast["cover_image_url"] = image_url
            podcasts_with_image.append(
                {
                    "id": podcast["id"],
                    "title": podcast["title"],
                    "description": podcast["description"],
                    "duration": podcast["duration"],
                    "cover_image_url": podcast["cover_image_url"],
                    "country": podcast["country"],
                    "category": podcast["category"],
                    "subcategory": podcast["subcategory"],
                    "keywords": podcast["keywords"],
                    "createAt": podcast["published_at"],
                    "totalRating": podcast["total_rating"],
                    "positive": podcast["positive_rating"],
                    "negative": podcast["negative_rating"],
                }
            )
        return jsonify(podcasts_with_image)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/recommendations/<podcast_id>', methods=['GET'])
@token_required
def get_recommendations_by_podcast(podcast_id):
    try:
        user_id = request.headers.get('X-User-ID')
        # real_time_vector = user_middleware.get_user(user_id)["realtime_vector"]
        # real_time_vector = np.array(eval(real_time_vector))
        podcast_vector = podcast_middleware.get_podcast_embeddings([podcast_id])[0]
        if not podcast_vector:
            return jsonify({"error": "Podcast not found"}), 404
        history = user_middleware.get_listening_history(user_id)
        ids = None
        if history:
            ids = [item["id"] for item in history]
        pids = podcast_middleware.search_podcasts_by_vector(podcast_vector, history=ids, limit=10, hourly=True, daily=True, weekly=True)
        podcasts = podcast_middleware.get_podcasts_by_ids(pids)
        podcasts_with_image = []
        for podcast in podcasts:
            if podcast["cover_image_url"] == "":
                image_url = asyncio.run(load_image(podcast, return_file=False))
                podcast["cover_image_url"] = image_url
            podcasts_with_image.append(
                {
                    "id": podcast["id"],
                    "title": podcast["title"],
                    "description": podcast["description"],
                    "duration": podcast["duration"],
                    "cover_image_url": podcast["cover_image_url"],
                    "country": podcast["country"],
                    "category": podcast["category"],
                    "subcategory": podcast["subcategory"],
                    "keywords": podcast["keywords"],
                    "createAt": podcast["published_at"],
                    "totalRating": podcast["total_rating"],
                    "positive": podcast["positive_rating"],
                    "negative": podcast["negative_rating"],
                }
            )
        return jsonify(podcasts_with_image)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Playlist endpoints
@app.route('/playlists', methods=['GET'])
@token_required
def get_playlists():
    try:
        user_id = request.headers.get('X-User-ID')
        playlists = user_middleware.get_user_playlists(user_id)
        return jsonify(playlists)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/playlist', methods=['POST'])
@token_required
def create_playlist():
    try:
        user_id = request.headers.get('X-User-ID')
        name = request.json.get("name")
        description = request.json.get("description", "")
        playlist_id = user_middleware.create_playlist(user_id, name, description)
        return jsonify({"message": "Playlist created successfully", "id": playlist_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/playlist', methods=['PUT'])
@token_required
def update_playlist():
    try:
        data = request.json
        name = data.get("name")
        description = data.get("description", "")
        playlist_id = data.get("id")
        user_middleware.rename_playlist(playlist_id, name, description)
        return jsonify({"message": "Playlist updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/playlist', methods=['DELETE'])
@token_required
def delete_playlist():
    try:
        data = request.json
        playlist_id = data.get("id")
        if not playlist_id:
            return jsonify({"message": "no playlist id provided"}), 400 
        user_middleware.delete_playlist(playlist_id)
        return jsonify({"message": "Playlist deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/playlist/<playlist_id>', methods=['GET'])
@token_required
def get_playlist(playlist_id):
    try:
        user_id = request.headers.get('X-User-ID')
        playlist = user_middleware.get_playlist_items(playlist_id, user_id)
        return jsonify(playlist)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/playlist/<playlist_id>', methods=['POST'])
@token_required
def add_to_playlist(playlist_id):
    try:
        user_id = request.headers.get('X-User-ID')
        data = request.json
        podcast_id = data.get("podcast_id")
        if not podcast_id:
            return jsonify({"message": "no podcast id provided"}), 400
        user_middleware.add_to_playlist(playlist_id, podcast_id, user_id)
        return jsonify({"message": "Podcast added to playlist successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/playlist/<playlist_id>', methods=['DELETE'])
@token_required
def remove_from_playlist(playlist_id):
    try:
        user_id = request.headers.get('X-User-ID')
        data = request.json
        podcast_id = data.get("podcast_id")
        if not podcast_id:
            return jsonify({"message": "no podcast id provided"}), 400
        user_middleware.delete_from_playlist(playlist_id, podcast_id, user_id)
        return jsonify({"message": "Podcast removed from playlist successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/rate', methods=['POST'])
@token_required
def rate():
    try:
        user_id = request.headers.get('X-User-ID')
        data = request.json
        podcast_id = data.get("podcast_id")
        rating = int(data.get("rating", 0))
        if not podcast_id:
            return jsonify({"message": "no podcast id or rating provided"}), 400
        if like_or_dislike(podcast_id, user_id, rating):
            return jsonify({"message": "Podcast rated successfully"})
        else:
            return jsonify({"message": "Podcast rating failed"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/playing', methods=['POST'])
@token_required
def get_playing():
    try:
        user_id = request.headers.get('X-User-ID')
        data = request.json
        position = data.get("position", 0)
        podcast_id = data.get("podcast_id", None)
        if not podcast_id:
            return jsonify({"message": "no podcast id provided"}), 400
        user_middleware.update_user_listen_position(user_id, podcast_id, position)
        return jsonify({"message": "Playing successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Played endpoint
@app.route('/played', methods=['POST'])
@token_required
def mark_as_played():
    try:
        user_id = request.headers.get('X-User-ID')
        data = request.json
        user_activity_log(user_id, data)
        return jsonify({"message": "Marked as played successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/transition', methods=['POST'])
@token_required
def transition():
    try:
        user_id = request.headers.get('X-User-ID')
        data = request.json
        id1 = data.get("id1")
        id2 = data.get("id2")
        if not id1 or not id2:
            return jsonify({"error": "No id1 or id2 provided"}), 400
        if id1 == id2:
            return jsonify({"error": "id1 and id2 are the same"}), 400
        if r.exists(f"transition:{id1}{id2}"):
            transition_files = r.get(f"transition:{id1}{id2}")
            transition_files = json.loads(transition_files)
            transition_files["cover_image_url"] = "image/host.png"
            return jsonify(transition_files)
        def load_transition_task():
            asyncio.run(create_transition_audio_by_ids(id1, id2))
        threading.Thread(target=load_transition_task).start()
        transition = {
                "cover_image_url": "image/host.png",
                "audio_url": "",
                "transcript_url": "",
                "secs": 0
            }
        return jsonify(transition)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Search endpoint
@app.route('/search', methods=['GET'])
@token_required
def user_search():
    try:
        user_id = request.headers.get('X-User-ID')
        query = request.args.get('q', '')
        pids = podcast_middleware.search_podcasts(query, limit=20, hourly=True, daily=True, weekly=True, whole=True)
        podcasts = podcast_middleware.get_podcasts_by_ids(pids)
        search(user_id, query)
        podcasts_with_image = []
        for podcast in podcasts:
            if podcast["cover_image_url"] == "":
                image_url = asyncio.run(load_image(podcast, return_file=False))
                podcast["cover_image_url"] = image_url
            podcasts_with_image.append(
                {
                    "id": podcast["id"],
                    "title": podcast["title"],
                    "description": podcast["description"],
                    "duration": podcast["duration"],
                    "cover_image_url": podcast["cover_image_url"],
                    "country": podcast["country"],
                    "category": podcast["category"],
                    "subcategory": podcast["subcategory"],
                    "keywords": podcast["keywords"],
                    "createAt": podcast["published_at"],
                    "totalRating": podcast["total_rating"],
                    "positive": podcast["positive_rating"],
                    "negative": podcast["negative_rating"],
                }
            )
        return jsonify(podcasts_with_image)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/get_trending', methods=['GET'])
def get_trending():
    try:
        trending = podcast_middleware.get_user_trending_podcasts()
        podcasts_with_image = []
        for podcast in trending:
            podcast["createAt"] = podcast["published_at"]
            if podcast["cover_image_url"] == "":
                image_url = asyncio.run(load_image(podcast, return_file=False))
                podcast["cover_image_url"] = image_url
            podcasts_with_image.append(podcast)
        return jsonify(podcasts_with_image)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route('/get_hot_trending', methods=['GET'])
@token_required
def get_hot_trending():
    try:
        user_id = request.headers.get('X-User-ID')
        preference = user_middleware.get_user(user_id)["realtime_vector"]
        trending = podcast_middleware.get_hot_trending_podcasts(preference=preference)
        podcasts_with_image = []
        for podcast in trending:
            podcast["createAt"] = podcast["published_at"]
            if podcast["cover_image_url"] == "":
                image_url = asyncio.run(load_image(podcast, return_file=False))
                podcast["cover_image_url"] = image_url
            podcasts_with_image.append(podcast)
        return jsonify(podcasts_with_image)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5001)
