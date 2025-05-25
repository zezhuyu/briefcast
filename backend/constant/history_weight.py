import math
import numpy as np

weight = {
    "80%": 1,
    "50%": 0.5,
    "30%": 0,
    "0%": -0.5,
    "like": 1,
    "dislike": -1,
    "share": 1.8,
    "download": 1.3,
    "add_to_playlist": 1.4,
    # "click": 0.25,
    # "comment": 0.25,
    "search": 0.75,
}

batch_size = 10

def dim_weight(weight, replay):
    return weight * (1 / math.e ** (replay - 1))

def get_weight(actions):
    total_weight = 0
    for action in actions:
        if action in weight:
            total_weight += weight[action]
    return total_weight


def get_embeding_mean(embedding, number):
    return embedding / number

def normalize_embedding(embedding):
    return embedding / np.linalg.norm(embedding)

def compute_daily_embedding(privous, current):
    return privous * 0.8 + current * 0.2

def compute_batch_embedding(privous, current):
    return privous * 0.9 + current * 0.1

def listen_weight(percentage):
    if percentage < 0.05:
        return 0
    elif percentage < 0.3:
        return weight["0%"]
    elif percentage < 0.5:
        return weight["30%"]
    elif percentage < 0.8:
        return weight["50%"]
    elif percentage >= 0.8:
        return weight["80%"]
    else:
        return weight["0%"]


def compute_completeness(stop_position, duration):
    return stop_position / duration

def real_listen_time(listen_duration, stop_position):
    return listen_duration / stop_position


