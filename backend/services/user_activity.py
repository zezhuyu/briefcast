import numpy as np
import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.user_middleware import UserMiddleware
from db.podcast_middleware import PodcastMiddleware
from services.llm_stuff import create_embedding
from datetime import datetime, timedelta
from constant.history_weight import get_weight, batch_size, dim_weight, listen_weight, compute_completeness

user_middleware = UserMiddleware()
podcast_middleware = PodcastMiddleware()

def like_or_dislike(podcast_id, user_id, like):
    if podcast_middleware.update_podcast_rating(podcast_id, user_id, like):
        if like == 1:
            user_middleware.like_podcast(user_id, podcast_id)
        elif like == -1:
            user_middleware.dislike_podcast(user_id, podcast_id)
        else:
            user_middleware.neutralize_podcast(user_id, podcast_id)
        return True
    return False
    

def search(user_id, query):
    embedding = create_embedding(query)
    weight = get_weight(["search"])
    user_middleware.add_user_search_history(user_id, query)
    update_user_batch_embedding(user_id, embedding, weight)
    update_user_daily_embedding(user_id, embedding, weight)
    return True

def user_activity_log(user_id, actions):
    podcast_id = actions['podcast_id']
    embedding = podcast_middleware.get_podcast_embeddings([podcast_id])
    if embedding:
        embedding = np.array(embedding[0])
        percentage = compute_completeness(actions['last_position'], actions['total_duration_seconds'])
        
        action_set = set()
        for action in actions['actions']:
            action_set.add(action['action'])

        weight = min(get_weight(action_set) + listen_weight(percentage), 3)
        complete_history = user_middleware.get_complete_user_history(user_id, podcast_ids=[podcast_id])
        replay = 0
        for history in complete_history:
            if not history['hidden']:
                replay = history['play_count']
                break

        weight = dim_weight(weight, replay) 

        user_activity = {
            "listen_duration_seconds": actions['listen_duration_seconds'],
            "stop_position_seconds": actions['last_position'],
            "share_count": 1 if 'share' in action_set else 0,
            "download_count": 1 if 'download' in action_set else 0,
            "add_to_playlist": 1 if 'add_to_playlist' in action_set else 0,
            "rating": actions['rating'] if 'rating' in action_set else 0
        }

        update_user_batch_embedding(user_id, embedding, weight)
        update_user_daily_embedding(user_id, embedding, weight)
        user_middleware.add_to_listening_history(user_id, podcast_id, user_activity, completed=percentage >= 0.9)
        return True
    return False



def update_user_batch_embedding(user_id, embedding, weight):
    batch_count = user_middleware.update_user_batch_embedding(user_id, embedding, weight)
    if batch_count >= 0 and batch_count >= batch_size:
        return user_middleware.update_realtime_embedding(user_id)
    if batch_count >= 0 and batch_count < batch_size:
        return True
    return False

def update_user_daily_embedding(user_id, embedding, weight):
    time = user_middleware.update_user_daily_embedding(user_id, embedding, weight)
    if time is None:
        return False
    return recompute_user_daily_embedding(user_id)

def recompute_user_daily_embedding(user_id):
    time = user_middleware.get_user_last_daily_update(user_id)
    if time is not None and datetime.now() - time > timedelta(days=1):
        return user_middleware.update_prevday_embedding(user_id)
    return True