
import json
import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.mq_broker import send_task
from services.llm_stuff import create_audio
from services.script import create_weather_forecast, rewrite_podcast, create_transition
from pydub import AudioSegment
import ffmpeg
import numpy as np
import io
from timezonefinder import TimezoneFinder 
import geocoder
from zoneinfo import ZoneInfo
from datetime import datetime
import requests
from db.podcast_middleware import PodcastMiddleware
import re
import wave
import io
from db.minio_middleware import MinioMiddleware
import redis
import os
from dotenv import load_dotenv

load_dotenv()

podcast_middleware = PodcastMiddleware()
minio_middleware = MinioMiddleware()
CONTENT_TASK_QUEUE = "content_task_queue"
TRANSITION_TASK_QUEUE = "transition_task_queue"
NEWS_SCRIPT_TASK_QUEUE = "news_script_task_queue"
r = redis.Redis(host=os.environ.get('REDIS_HOST'), port=os.environ.get('REDIS_PORT'), db=os.environ.get('REDIS_DB'))

def convert_time_to_seconds(time_str):
    """Convert a time in mm:ss.xx format to total seconds."""
    minutes, seconds = time_str.split(':')
    seconds, milliseconds = seconds.split('.')
    total_seconds = int(minutes) * 60 + int(seconds) + int(milliseconds) / 100
    return total_seconds

def convert_seconds_to_time(seconds):
    """Convert total seconds to mm:ss.xx format."""
    minutes = int(seconds) // 60
    seconds_remaining = seconds % 60
    seconds_int = int(seconds_remaining)
    milliseconds = int((seconds_remaining - seconds_int) * 100)
    return f"[{minutes:02d}:{seconds_int:02d}.{milliseconds:02d}]"

def modify_timestamp(line, add_seconds):
    """Modify the timestamp in the given line by adding a value in seconds."""
    # Find the timestamp in the format [mm:ss.xx]
    match = re.search(r'\[(\d{2}:\d{2}\.\d{2})\]', line)
    if match:
        time_str = match.group(1)
        # Convert time to seconds, add the value, and convert back to time
        total_seconds = convert_time_to_seconds(time_str)
        modified_seconds = total_seconds + add_seconds
        modified_time_str = convert_seconds_to_time(modified_seconds)
        # Replace the original timestamp with the modified one
        modified_line = line.replace(time_str, modified_time_str[1:-1])  # Strip the brackets from time_str
        return modified_line
    else:
        return line

def get_audio_duration(wav_bytes_io):
    """Get the duration of a WAV file in seconds from a BytesIO object."""
    audio_segment = AudioSegment.from_file(wav_bytes_io)
    duration = len(audio_segment) / 1000
    return duration
    
def get_ordinal_suffix(day):
    if 11 <= day <= 13:  # Special case for 11th, 12th, 13th
        return f"{day}th"
    last_digit = day % 10
    if last_digit == 1:
        return f"{day}st"
    elif last_digit == 2:
        return f"{day}nd"
    elif last_digit == 3:
        return f"{day}rd"
    else:
        return f"{day}th"
    
def get_greeting(time=None):
    if time is None:
        return "Good morning!"
    hour = time.hour
    if 5 <= hour < 12:
        return "Good morning!"
    elif 12 <= hour < 17:
        return "Good afternoon!"
    elif 17 <= hour < 21:
        return "Good evening!"
    else:
        return "Good night!"

def save_wav(byte_io_wav, output_filename):
    """Save a BytesIO WAV object to a file."""
    with open(output_filename, 'wb') as f:
        f.write(byte_io_wav.getbuffer())

def save_lyric(lyrics, output_filename):
    with open(output_filename, "w", encoding="utf-8") as lyric_file:
        for lyric in lyrics:
            lyric_file.write(lyric + "\n")

def mix_wav_with_delay(background_wav, greeting_wav, opening_wav, starting_wav, forecast_wav=None, bg_volume=0.1, delay_sec=31, fade_duration_sec=1, start_volume=0.6):
    """Mix background music with speech, applying a volume change for the beginning part and fade-in effect."""
    
    # Open both WAV files
    with wave.open(background_wav, 'rb') as bg, wave.open(greeting_wav, 'rb') as greeting, wave.open(opening_wav, 'rb') as opening:
        # Ensure both have the same parameters (channels, sample width, framerate)
        if (bg.getnchannels() != greeting.getnchannels() or 
            bg.getsampwidth() != greeting.getsampwidth() or 
            bg.getframerate() != greeting.getframerate()):
            raise ValueError("WAV files must have the same format")

        # Read frames as NumPy arrays
        bg_frames = np.frombuffer(bg.readframes(bg.getnframes()), dtype=np.int16)
        greeting_frames = np.frombuffer(greeting.readframes(greeting.getnframes()), dtype=np.int16)
        opening_frames = np.frombuffer(opening.readframes(opening.getnframes()), dtype=np.int16)

        # Convert delay to number of samples
        sample_rate = bg.getframerate()
        delay_samples = int(delay_sec * sample_rate * bg.getnchannels())

        # Pad speech with silence at the beginning
        silence = np.zeros(delay_samples, dtype=np.int16)
        one_second_silence = np.zeros(int(0.5 * sample_rate * bg.getnchannels()), dtype=np.int16)
        speech_frames = np.concatenate((silence, greeting_frames, one_second_silence, opening_frames))

        soft_delay = delay_samples
        if delay_sec > (fade_duration_sec + 0.1):
            soft_delay = int((delay_sec - (fade_duration_sec + 0.1)) * sample_rate * bg.getnchannels())

        # Split the background music frames:
        bg_before_delay = bg_frames[:soft_delay]  # No fade during the delay period
        bg_after_delay = bg_frames[soft_delay:].copy()  # Copy to ensure it's mutable

        # Apply the initial volume change for the first part of the background music
        bg_before_delay = bg_before_delay * start_volume  # Adjust the volume for the initial part

        # Apply fade-in effect for 1 second (fade_duration_sec)
        fade_samples = int(fade_duration_sec * sample_rate * bg.getnchannels())  # Number of samples for the fade

        # Apply a quadratic fade-in (soft start, faster towards the end)
        fade_in_curve = np.linspace(start_volume, bg_volume, fade_samples)

        # Ensure no mute by applying fade-in curve from the beginning of bg_after_delay
        if len(bg_after_delay) > fade_samples:
            bg_after_delay[:fade_samples] = (bg_after_delay[:fade_samples] * fade_in_curve).astype(np.int16)
        else:
            bg_after_delay = (bg_after_delay * fade_in_curve).astype(np.int16)

        # Once the fade-in completes, apply the bg_volume for the remainder of the audio
        bg_after_fade = bg_after_delay[fade_samples:]
        bg_after_fade = bg_after_fade * bg_volume  # Ensure background music stays at the desired volume

        # Concatenate the parts of the background music back together
        bg_frames = np.concatenate((bg_before_delay, bg_after_delay[:fade_samples], bg_after_fade))

        # Determine the final length (longest file should be kept)
        max_len = max(len(bg_frames), len(speech_frames))

        # Extend both arrays to match the longest one (fill with silence if needed)
        if len(bg_frames) < max_len:
            bg_frames = np.pad(bg_frames, (0, max_len - len(bg_frames)), 'constant', constant_values=0)
        if len(speech_frames) < max_len:
            speech_frames = np.pad(speech_frames, (0, max_len - len(speech_frames)), 'constant', constant_values=0)

        # Mix the audio: sum the background music with speech
        mixed_audio = (speech_frames + bg_frames).astype(np.int16)

        # Create a new BytesIO object to store the mixed audio
        mixed_wav = io.BytesIO()
        with wave.open(mixed_wav, 'wb') as output:
            output.setnchannels(bg.getnchannels())
            output.setsampwidth(bg.getsampwidth())
            output.setframerate(sample_rate)
            output.writeframes(mixed_audio.tobytes())
            if forecast_wav:
                with wave.open(forecast_wav, 'rb') as forecast:
                    output.writeframes(forecast.readframes(forecast.getnframes()))
            with wave.open(starting_wav, 'rb') as starting:
                output.writeframes(starting.readframes(starting.getnframes()))

    mixed_wav.seek(0)  # Reset pointer to the start
    return mixed_wav

def mix_wav_with_fade_in_and_speech_control(bg_wav, speech_wav, bg_speech=0.6, bg_music=0.6, delay_sec=20, fade_duration_sec=1):
    """Play speech first, then fade in background music from 0 to bg_music over a specified duration, and adjust volume based on speech or music."""
    
    # Read the background music WAV from the BytesIO object
    with wave.open(bg_wav, 'rb') as bg:
        # Get background music parameters
        bg_channels = bg.getnchannels()
        bg_sampwidth = bg.getsampwidth()
        bg_framerate = bg.getframerate()
        bg_frames = np.frombuffer(bg.readframes(bg.getnframes()), dtype=np.int16)
        
    # Read the speech WAV from the BytesIO object
    with wave.open(speech_wav, 'rb') as speech:
        # Get speech parameters
        speech_channels = speech.getnchannels()
        speech_sampwidth = speech.getsampwidth()
        speech_framerate = speech.getframerate()
        speech_frames = np.frombuffer(speech.readframes(speech.getnframes()), dtype=np.int16)

    # Ensure both WAV files have the same parameters
    if (bg_channels != speech_channels or bg_sampwidth != speech_sampwidth or bg_framerate != speech_framerate):
        raise ValueError("WAV files must have the same format")

    # Convert delay to number of samples
    sample_rate = bg_framerate
    delay_samples = int(delay_sec * sample_rate * bg_channels)

    # Pad speech with silence at the beginning
    silence = np.zeros(delay_samples, dtype=np.int16)
    speech_frames_padded = np.concatenate((silence, speech_frames))

    # Fade-in the background music from volume 0 to bg_music at the start
    fade_samples = int(fade_duration_sec * sample_rate * bg_channels)  # Number of samples for the fade

    # Create a fade-in curve from 0 to bg_music
    fade_in_curve = np.linspace(0, bg_music, fade_samples)

    # Apply fade-in effect to the first part of the background music
    bg_fade_in = bg_frames[:fade_samples] * fade_in_curve
    bg_after_fade_in = bg_frames[fade_samples:] * bg_music  # Ensure remaining audio is at bg_music volume

    # Concatenate the faded background music
    bg_frames = np.concatenate((bg_fade_in, bg_after_fade_in))

    # Now adjust the volume for when the speech is playing (bg_speech)
    speech_end_sample = len(speech_frames_padded)
    bg_after_speech_start = bg_frames[speech_end_sample:]

    # Mix speech with background music at bg_speech volume during speech
    bg_during_speech = bg_frames[:speech_end_sample] * bg_speech

    # Make sure both arrays have the same length (pad if needed)
    max_len = max(len(speech_frames_padded), len(bg_during_speech))
    
    if len(speech_frames_padded) < max_len:
        speech_frames_padded = np.pad(speech_frames_padded, (0, max_len - len(speech_frames_padded)), 'constant', constant_values=0)
    
    if len(bg_during_speech) < max_len:
        bg_during_speech = np.pad(bg_during_speech, (0, max_len - len(bg_during_speech)), 'constant', constant_values=0)

    # Mix the audio: the speech part will be combined with the adjusted background music (at bg_speech volume)
    mixed_audio = (speech_frames_padded + bg_during_speech).astype(np.int16)

    # After speech, the background music should continue playing at bg_music volume
    mixed_audio = np.concatenate((mixed_audio, bg_after_speech_start * bg_music))

    # Prevent clipping by ensuring the mixed_audio doesn't exceed the int16 range
    mixed_audio = np.clip(mixed_audio, -32768, 32767).astype(np.int16)

    # Create a new BytesIO object to store the mixed audio
    mixed_wav = io.BytesIO()
    with wave.open(mixed_wav, 'wb') as output:
        output.setnchannels(bg_channels)
        output.setsampwidth(bg_sampwidth)
        output.setframerate(sample_rate)
        output.writeframes(mixed_audio.tobytes())

    mixed_wav.seek(0)  # Reset pointer to the start
    return mixed_wav



def create_opening(location=None):

    url = "https://wttr.in/"
    speech_delay = 31

    new_lyric = []
    # bg_wav = open("./resources/op.wav", "rb")
    # starting_audio = open("./resources/starting.wav", "rb")
    # starting_lyric = open("./resources/starting.lrc", "r", encoding="utf-8").readlines()
    # opening_lyric = open("./resources/opening.lrc", "r", encoding="utf-8").readlines()
    # opening_audio = open("./resources/opening.wav", "rb")

    bg_wav = minio_middleware.get_file("audio/op.wav")
    starting_audio = minio_middleware.get_file("audio/starting.wav")
    starting_lyric = minio_middleware.get_file("transcript/starting.lrc").readlines()
    starting_lyric = [line.decode("utf-8") for line in starting_lyric]
    opening_lyric = minio_middleware.get_file("transcript/opening.lrc").readlines()
    opening_lyric = [line.decode("utf-8") for line in opening_lyric]
    opening_audio = minio_middleware.get_file("audio/opening.wav")

    if location:
        Latitude, Longitude = location
        obj = TimezoneFinder()
        timezone = obj.certain_timezone_at(lng=Longitude, lat=Latitude)
        timezone = ZoneInfo(timezone)
        localized_time = datetime.now(timezone)
        try:
            response = requests.get(f"{url}{Latitude:.2f},{Longitude:.2f}?FT1")
        except Exception as e:
            print(e)
            response = None
    else:
        localized_time = datetime.now()

    today = localized_time.date()

    greeting = get_greeting(localized_time)
    weekday = today.strftime("%A")
    month = today.strftime("%B")
    day = today.day
    year = today.year

    day = get_ordinal_suffix(day)

    add_seconds = speech_delay

    welcome = f"{greeting} Today is {weekday} {month} {day} {year}."
    greeting_audio, greeting_lyric = create_audio(welcome, voice='af_heart', split_pattern=r'\.+')
    for line in greeting_lyric:
        new_lyric.append(modify_timestamp(line, add_seconds))
    add_seconds += get_audio_duration(greeting_audio)
    greeting_audio.seek(0)

    for line in opening_lyric:
        new_lyric.append(modify_timestamp(line, add_seconds))
    add_seconds = max(get_audio_duration(bg_wav), add_seconds)
    bg_wav.seek(0)
    forecast_audio = None
    if location and response:
        forecast = create_weather_forecast(response.text)
        split_pattern = r'[.:]\s+'
        sentences = re.split(split_pattern, forecast)
        audio_text = ""
        for text in sentences:
            if text:
                audio_text += text + ", "
        forecast_audio, forecast_lyric = create_audio(audio_text, voice='af_heart', split_pattern=r'\s*,\s*')
        for line in forecast_lyric:
            new_lyric.append(modify_timestamp(line, add_seconds))
        add_seconds += get_audio_duration(forecast_audio)
        forecast_audio.seek(0)

    for line in starting_lyric:
        new_lyric.append(modify_timestamp(line, add_seconds))
    add_seconds += get_audio_duration(starting_audio)
    starting_audio.seek(0)

    mixed_wav = mix_wav_with_delay(bg_wav, greeting_audio, opening_audio, starting_audio, forecast_wav=forecast_audio, delay_sec=speech_delay)
    mixed_wav.seek(0)

    return compress_audio(mixed_wav), new_lyric, add_seconds
    # return mixed_wav, new_lyric, add_seconds

def create_ending(add_seconds=0):
    speech_delay = 3.5

    # bg_wav = open("./resources/ed.wav", "rb")
    # ending_audio = open("./resources/ending.wav", "rb")
    # ending_lyric = open("./resources/ending.lrc", "r", encoding="utf-8").readlines()

    bg_wav = minio_middleware.get_file("audio/ed.wav")
    ending_audio = minio_middleware.get_file("audio/ending.wav")
    ending_lyric = minio_middleware.get_file("transcript/ending.lrc").readlines()
    ending_lyric = [line.decode("utf-8") for line in ending_lyric]

    new_lyric = []
    add_seconds += speech_delay

    for line in ending_lyric:
        new_lyric.append(modify_timestamp(line, add_seconds))
    add_seconds += get_audio_duration(ending_audio)
    ending_audio.seek(0)

    mixed_wav = mix_wav_with_fade_in_and_speech_control(bg_wav, ending_audio, delay_sec=speech_delay)
    mixed_wav.seek(0)

    return compress_audio(mixed_wav), new_lyric, add_seconds

async def create_transition_audio(script1, script2, id, add_seconds=0, local=False, delete_tmp=True, return_file=True):
    podcast = {
        "id": id,
        "script1": script1,
        "script2": script2,
        "add_seconds": add_seconds
    }
    if local:
        return _create_transition_audio(script1, script2, add_seconds, local)
    else:
        data = send_task(podcast, TRANSITION_TASK_QUEUE)
    if not data:
        return None, None, None
    json_data = json.loads(data)
    if not json_data:
        return None, None, None
    if return_file:
        audio = minio_middleware.get_tmp_audio(json_data["audio_url"])
        audio.seek(0)
        transcript = minio_middleware.get_tmp_transcript(json_data["transcript_url"])
        lyrics = transcript.read().decode('utf-8').splitlines()
        lyric = []
        for line in lyrics:
            lyric.append(modify_timestamp(line, add_seconds))
    else:
        audio = json_data["audio_url"]
        lyric = json_data["transcript_url"]
    if delete_tmp:
        minio_middleware.delete_tmp_audio(json_data["audio_url"])
        minio_middleware.delete_tmp_transcript(json_data["transcript_url"])
    return audio, lyric, json_data["add_seconds"]

def _create_transition_audio(script1, script2, add_seconds=0, local=False):
    if not script1 or not script2:
        result = {
            "audio_url": "",
            "transcript_url": "",
            "add_seconds": add_seconds
        }
        if local:
            return None, None, add_seconds
        return result
    if script1 == "" or script2 == "":
        result = {
            "audio_url": "",
            "transcript_url": "",
            "add_seconds": add_seconds
        }
        if local:
            return None, None, add_seconds
        return result
    transition = create_transition(script1, script2)
    new_lyric = []
    split_pattern = r'[.:]\s+'
    sentences = re.split(split_pattern, transition)
    audio_text = ""
    for text in sentences:
        if text:
            audio_text += text + ", "
    audio, lyric = create_audio(audio_text, voice='af_heart')
    for line in lyric:
        new_lyric.append(modify_timestamp(line, add_seconds))
    add_seconds += get_audio_duration(audio)
    audio.seek(0)
    audio = compress_audio(audio)
    if local:
        return audio, new_lyric, add_seconds
    
    audio_url = minio_middleware.store_tmp_audio(audio)
    transcript_url = minio_middleware.store_tmp_transcript(new_lyric)

    result = {
        "audio_url": audio_url,
        "transcript_url": transcript_url,
        "add_seconds": add_seconds
    }

    return result

def create_news(news, add_seconds=0, by_script=False):
    if not by_script:
        script = rewrite_podcast(news)
    else:
        script = news
    new_lyric = []
    split_pattern = r'[.:]\s+'
    sentences = re.split(split_pattern, script)
    audio_text = ""
    for text in sentences:
        if text:
            audio_text += text + ", "
    audio, lyric = create_audio(audio_text, voice='bm_george')
    for line in lyric:
        new_lyric.append(modify_timestamp(line, add_seconds))
    add_seconds += get_audio_duration(audio)
    audio.seek(0)

    return compress_audio(audio), new_lyric, add_seconds, script

async def create_news_script(podcast):
    podcast = podcast_middleware.get_podcast_by_id(podcast["id"])
    if podcast["transcript_text"] == "":
        script = send_task(podcast, NEWS_SCRIPT_TASK_QUEUE)
        if not script:
            return None
        if isinstance(script, bytes):
            script = script.decode('utf-8')
    else:
        script = podcast["transcript_text"]
    return script

def _create_news_script(podcast):
    podcast = podcast_middleware.get_podcast_by_id(podcast["id"])
    if podcast["transcript_text"] == "":
        script = rewrite_podcast(podcast["content"])
        podcast_middleware.update_podcast_transcript(podcast["id"], script)
    else:
        script = podcast["transcript_text"]
    return script

async def load_content(podcast, add_seconds=0, return_file=True, local=False):
    audio, lyric, secs, script = None, None, None, None
    podcast = podcast_middleware.get_podcast_by_id(podcast["id"])
    if (podcast["audio_url"] == "" or podcast["transcript_text"] == ""):
        podcast["add_seconds"] = add_seconds
        if local:
            return _load_content(podcast, add_seconds, local)
        else:
            data = send_task(podcast, CONTENT_TASK_QUEUE)
        if not data:
            return audio, lyric, secs, script
        json_data = json.loads(data)
        if not json_data:
            return audio, lyric, secs, script
        audio = minio_middleware.get_file(json_data["audio_url"])
        transcript = minio_middleware.get_file(json_data["transcript_url"])
        script = json_data["transcript_text"]
        secs = json_data["secs"]
        audio.seek(0)
        lyrics = transcript.read().decode('utf-8').splitlines()
        lyric = []
        for line in lyrics:
            lyric.append(modify_timestamp(line, add_seconds))
        return audio, lyric, secs, script
    else:
        if return_file:
            audio = minio_middleware.get_file(podcast['audio_url'])
            if not audio:
                podcast["add_seconds"] = add_seconds
                if local:
                    return _load_content(podcast, add_seconds, local)
                else:
                    data = send_task(podcast, CONTENT_TASK_QUEUE)
                if not data:
                    return audio, lyric, secs, script
                json_data = json.loads(data)  
                if not json_data:
                    return audio, lyric, secs, script
                audio = minio_middleware.get_file(json_data["audio_url"])
                transcript = minio_middleware.get_file(json_data["transcript_url"])
            else:
                transcript = minio_middleware.get_file(podcast['transcript_url'])
            lyrics = transcript.read().decode('utf-8').splitlines()
            lyric = []
            for line in lyrics:
                lyric.append(modify_timestamp(line, add_seconds))
            duration = get_audio_duration(audio)
            audio.seek(0)
            secs = add_seconds + duration
            script = podcast["transcript_text"]
    return audio, lyric, secs, script

def _load_content(podcast, add_seconds=0, local=False):
    audio, lyric, secs, script = None, None, None, None
    by_script = False
    podcast = podcast_middleware.get_podcast_by_id(podcast["id"])
    if podcast and podcast.get("audio_url", "") != "" and podcast.get("transcript_text", "") != "":
        data = {
            "audio_url": podcast["audio_url"],
            "transcript_url": podcast["transcript_url"],
            "duration_seconds": podcast["duration_seconds"],
            "transcript_text": podcast["transcript_text"]
        }
        return data
    if podcast.get("transcript_text", "") != "":
        script = podcast["transcript_text"]
        by_script = True
    else:
        script = podcast["content"]
    audio, lyric, secs, script = create_news(script, add_seconds=add_seconds, by_script=by_script)
    
    duration = get_audio_duration(audio)
    audio.seek(0)
    audio = compress_audio(audio)
    audio_url = minio_middleware.store_audio(audio)
    transcript_url = minio_middleware.store_transcript(lyric)
    data = {
        "audio_url": audio_url,
        "transcript_url": transcript_url,
        "duration_seconds": duration,
        "transcript_text": str(script)
    }
    podcast_middleware.update_podcast_generated_data(podcast["id"], data)
    if local:
        return audio, lyric, secs, script
    data["secs"] = secs
    return data

def create_silence(secs, audio_sample=None):
    channels = 2
    width = 2
    frame_rate = 44100
    if audio_sample:
        with wave.open(audio_sample, 'rb') as audio:
            channels = audio.getnchannels()
            width = audio.getsampwidth()
            frame_rate = audio.getframerate()
    silence = io.BytesIO()
    with wave.open(silence, 'wb') as audio_file:
        audio_file.setnchannels(channels)
        audio_file.setsampwidth(width)
        audio_file.setframerate(frame_rate)
        audio_file.writeframes(np.zeros(int(secs * frame_rate * channels), dtype=np.int16).tobytes())
    silence.seek(0)
    return silence
    

async def generate_daily_news(podcasts, location=None, add_seconds=0, silence_secs=1):
    lyrics = []
    news = []
    times = []
    opening_audio, opening_lyric, add_seconds = create_opening(location)
    add_seconds += silence_secs
    news.append(opening_audio)
    news.append(create_silence(silence_secs))
    lyrics.append(opening_lyric)
    times.append(add_seconds)
    if len(podcasts) > 0:
        audio, lyric, add_seconds, script1 = await load_content(podcasts[0], local=True)
        # script1 = podcasts[0]["title"]
        id1 = podcasts[0]["id"]
        add_seconds += silence_secs
        news.append(audio)
        news.append(create_silence(silence_secs))
        lyrics.append(lyric)
        times.append(add_seconds)
    for podcast in podcasts[1:]:
        audio, lyric, add_seconds, script2 = await load_content(podcast, local=True)
        # script2 = podcast["title"]
        id2 = podcast["id"]
        add_seconds += silence_secs
        transition_audio, transition_lyric, transition_secs = await create_transition_audio(script1, script2, id1+id2, local=True)
        transition_secs += silence_secs
        times.append(transition_secs)
        news.append(transition_audio)
        lyrics.append(transition_lyric)
        news.append(create_silence(silence_secs))

        news.append(audio)
        lyrics.append(lyric)
        times.append(add_seconds)
        news.append(create_silence(silence_secs))
        script1 = script2
        id1 = id2
    ending_audio, ending_lyric, add_seconds = create_ending()
    news.append(ending_audio)
    lyrics.append(ending_lyric)
    times.append(add_seconds)
    return news, lyrics, times


def apply_times(lyrics, times):
    new_lyric = []
    add_seconds = 0
    for i in range(len(lyrics)):
        for line in lyrics[i]:
            new_lyric.append(modify_timestamp(line, add_seconds))
        add_seconds += times[i]
    return new_lyric

def safe_load_audio(audio_bytes_io: io.BytesIO):
    audio_bytes_io.seek(0)
    header = audio_bytes_io.read(10)
    audio_bytes_io.seek(0)

    if header.startswith(b'RIFF'):
        return AudioSegment.from_file(audio_bytes_io, format="wav")
    elif header.startswith(b'ID3') or header[0:1] == b'\xff':
        return AudioSegment.from_file(audio_bytes_io, format="mp3")
    else:
        raise ValueError("Unsupported or corrupt audio format.")
    
def combine_audio(news):
    combined = None

    for audio_io in news:
        segment = safe_load_audio(audio_io)
        if combined is None:
            combined = segment
        else:
            combined += segment

    if combined is None:
        raise ValueError("No audio data provided.")

    output = io.BytesIO()
    combined.export(output, format="wav")
    output.seek(0)
    return compress_audio(output)

# def combine_audio(news):
#     output = io.BytesIO()
#     with wave.open(output, 'wb') as audio_file:
#         info = True
#         for a in news:
#             a.seek(0)
#             with wave.open(a, 'rb') as a_file:
#                 if info:
#                     audio_file.setnchannels(a_file.getnchannels())
#                     audio_file.setsampwidth(a_file.getsampwidth())
#                     audio_file.setframerate(a_file.getframerate())
#                     info = False
#             audio_file.writeframes(a_file.readframes(a_file.getnframes()))
#     output.seek(0)
#     return output

def combine_lyrics(lyrics):
    lyric_path = io.BytesIO()
    lyric_text = '\n'.join(lyrics)
    lyric_path.write(lyric_text.encode('utf-8'))
    lyric_path.seek(0)
    return lyric_path


def compress_audio(audio):
    audio.seek(0)
    compressed_audio = io.BytesIO()
    # process=(ffmpeg.input('pipe:0').output('pipe:1', format='wav', acodec='pcm_s16le', audio_bitrate='64k').run(input=audio.read(), capture_stdout=True, capture_stderr=True))
    # process=(ffmpeg.input('pipe:0').output('pipe:1', format='wav', acodec='pcm_s16le', ar=12000).run(input=audio.read(), capture_stdout=True, capture_stderr=True))
    process=(ffmpeg.input('pipe:0').output('pipe:1', format='mp3', audio_bitrate='32k', ac=1, ar=16000).run(input=audio.read(), capture_stdout=True, capture_stderr=True))
    compressed_audio.write(process[0])
    compressed_audio.seek(0)
    return compressed_audio

async def create_transition_audio_by_ids(id1, id2):
    if r.exists(f"transition:{id1}{id2}"):
        try:
            value = r.get(f"transition:{id1}{id2}")
            if value:
                json_value = json.loads(value)
                if json_value["audio_url"] and json_value["transcript_url"] and json_value["add_seconds"]:
                    return json_value["audio_url"], json_value["transcript_url"], json_value["add_seconds"]
        except Exception as e:
            print(e)
            # r.delete(f"transition:{id1}{id2}")
    if r.sismember(TRANSITION_TASK_QUEUE, id1+id2):
        return None, None, None
    podcast1 = podcast_middleware.get_podcast_by_id(id1)
    podcast2 = podcast_middleware.get_podcast_by_id(id2)
    if not podcast1 or not podcast2:
        return None, None, None
    
    if podcast1.get("transcript_text", "") == "" and not podcast1["title"].startswith("Briefcast Daily News"):
        audio, lyric, secs, script1 = await load_content(podcast1)
    elif podcast1["title"].startswith("Briefcast Daily News"):
        script1 = "Briefcast Daily News"
    else:
        script1 = podcast1["transcript_text"]

    if podcast2.get("transcript_text", "") == "" and not podcast2["title"].startswith("Briefcast Daily News"):
        audio, lyric, secs, script2 = await load_content(podcast2)
    elif podcast2["title"].startswith("Briefcast Daily News"):
        script2 = "Briefcast Daily News"
    else:
        script2 = podcast2["transcript_text"]

    audio, lyric, secs = await create_transition_audio(script1, script2, id1+id2, delete_tmp=False, return_file=False)
    if audio and lyric and secs:
        r.set(f"transition:{id1}{id2}", json.dumps({"audio_url": audio, "transcript_url": lyric, "secs": secs}), ex=60*60*24)
        r.set(f"shadow:transition:{id1}{id2}", json.dumps({"audio_url": audio, "transcript_url": lyric, "secs": secs}), ex=60*60*28)
        return audio, lyric, secs
    else:
        return None, None, None

