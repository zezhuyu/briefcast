import json
import threading
import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.audio_services import generate_daily_news, apply_times, combine_audio, combine_lyrics, get_audio_duration
from services.mq_broker import send_task
from services.llm_stuff import create_image
import redis
from db.user_middleware import UserMiddleware
from db.podcast_middleware import PodcastMiddleware
from db.minio_middleware import MinioMiddleware
import numpy as np
import os
import time
from dotenv import load_dotenv
import asyncio
load_dotenv()

from datetime import datetime, timedelta

NEWS_TASK_QUEUE = "daily_news_task_queue"

prompts = [
    "Generate a vivid and breathtaking depiction of a morning sunrise. The sun should be just above the horizon, casting a golden glow that blends into soft pink, lavender, and pale blue hues across the sky. Include gentle rays of sunlight illuminating scattered, fluffy clouds. Below, depict a serene landscape with rolling green hills, a calm reflective lake, and dew-kissed grass glistening in the early light. Capture the peaceful ambiance, the warmth of the sun, and the soft, dreamy atmosphere of a new day beginning.",
    "Create a photorealistic morning sunrise where the sun rises gently above the horizon. The sky is painted with warm golden hues blending into soft pinks and purples. Light reflects off a calm lake surrounded by misty rolling hills. Include delicate sun rays breaking through scattered clouds, casting long, soft shadows over the dewy grass.",
    "Generate an abstract interpretation of a morning sun. Use bold, swirling patterns of orange, yellow, and red, with fluid brush strokes to represent the rising sun. Let the sky transition into soft pastels with dynamic, flowing shapes to convey the warmth and energy of a new day.",
    "Design a minimalist morning sun with clean lines and simple geometric shapes. Depict a perfect circle in warm orange and yellow gradients rising over a flat horizon. Use a limited color palette of soft blues and peach to create a calming, modern aesthetic.",
    "Illustrate a magical morning sun rising over an enchanted landscape. The sun glows with radiant gold and shimmering pinks, casting sparkles across the sky. Floating islands drift in the background while ethereal creatures soar through beams of light. The scene is dreamy and otherworldly with a mystical ambiance.",
    "Create a soft watercolor-style morning sun. Gentle washes of yellow, orange, and pink blend into a pale blue sky. Capture the texture of watercolor paper and the subtle bleeding of colors. Show a quiet meadow in the foreground, softly lit by the morning light.",
    "Render a retro-inspired morning sun reminiscent of 70s aesthetics. Use warm, muted tones like burnt orange, mustard yellow, and faded pink. Include stylized sun rays in a radial pattern with a grainy texture. The horizon features a simple, rolling landscape in a vintage color scheme."
]

user_middleware = UserMiddleware()
podcast_middleware = PodcastMiddleware()
minio_middleware = MinioMiddleware()

prefence_dim = int(os.getenv("MILVUS_DIMENSION", 100))


async def store_daily_news(user_id, location=None, limit=5, force=False):
    try:
        real_time_vector = user_middleware.get_user(user_id)["prev_day_vector"]
        real_time_vector = np.array(eval(real_time_vector))
        history = user_middleware.get_listening_history(user_id)
        ids = None
        if history:
            ids = [item["id"] for item in history]
        ids = podcast_middleware.search_podcasts_by_vector(real_time_vector, history=ids, limit=limit)
        if not ids:
            return None
        print("create podcast from ids: ", ids)
        data = {
            "id": user_id,
            "user_id": user_id,
            "ids": ids,
            "location": location
        }
        print("send task to create news")
        podcast = send_task(data, NEWS_TASK_QUEUE)
        if not podcast or podcast == b'null':
            return None
        podcast = json.loads(podcast)
        print("podcast: ", podcast)
        if not force:
            user_middleware.update_user_daily_update(user_id)
    except Exception as e:
        raise e
    return podcast

async def _store_news(user_id, ids, location=None):
    print("create daily news for user: ", user_id)
    podcasts = podcast_middleware.get_podcasts_by_ids(ids)
    print("find podcasts")
    audio, lyrics, times = await generate_daily_news(podcasts, location=location)
    lyrics = apply_times(lyrics, times)
    combined_audio = combine_audio(audio)
    combined_lyrics = combine_lyrics(lyrics)
    daily_image = create_image(prompts[np.random.randint(0, len(prompts))])
    podcast_url, transcript_url, image_url = minio_middleware.store_user_audio(user_id, combined_audio, combined_lyrics, daily_image)
    combined_audio.seek(0)
    duration = get_audio_duration(combined_audio)
    keywords = []
    for podcast in podcasts:
        keywords.extend(podcast["keywords"])
    podcast_preferences = np.zeros(prefence_dim)
    embeddings = podcast_middleware.get_podcast_embeddings(ids)
    for i in embeddings:
        podcast_preferences += np.array(i)
    
    podcast_preferences = podcast_preferences / len(embeddings)
    data = {
        "title": "Briefcast Daily News " + datetime.now().strftime("%m-%d"),
        "content": ids,
        "keywords": keywords,
        "duration_seconds": duration,
        "cover_image_url": image_url,
        "audio_url": podcast_url,
        "transcript_url": transcript_url,
        "embedding": podcast_preferences
    }
    podcast = podcast_middleware.create_user_podcast(user_id, data)
    for pc in podcasts:
        user_middleware.add_to_listening_history(user_id, pc["id"], {}, hidden=True)
    data["rating"] = 0
    data["favorite"] = False
    data["positive_rating"] = podcast["positive"]
    data["negative_rating"] = podcast["negative"]
    data["total_rating"] = podcast["totalRating"]
    data.pop("embedding")
    return data

def load_daily_news(user_id, force=False, location=None, limit=5):
    podcast = podcast_middleware.get_user_podcast(user_id)
    current_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    if podcast and podcast["createAt"] > current_time and not force:
        rating = user_middleware.get_user_podcast_rating(user_id, podcast["id"])
        favorite = user_middleware.get_user_podcast_favorite(user_id, podcast["id"])
        if rating:
            podcast["rating"] = rating
        else:
            podcast["rating"] = 0
        if favorite:
            podcast["favorite"] = favorite
        else:
            podcast["favorite"] = False
        return podcast
    def load_content_task():
        asyncio.run(store_daily_news(user_id, location, limit, force=force))
    threading.Thread(target=load_content_task).start()
    podcast = {
        "id": "",
        "title": "Briefcast Daily News " + datetime.now().strftime("%m-%d"),
        "description": "",
        "duration": 0,
        "audio_url": "",
        "transcript_url": "",
        "cover_image_url": "",
        "country": "",
        "category": "news",
        "subcategory": "daily",
        "keywords": [],
        "createAt": "",
        "published_at": "",
        "total_rating": 0,
        "rating": 0,
        "favorite": False,
        "positive_rating": 0,
        "negative_rating": 0
    }
    return podcast