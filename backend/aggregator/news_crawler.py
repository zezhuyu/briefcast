import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from readability import Document
from bs4 import BeautifulSoup
from datetime import datetime
import time
import asyncio
import threading
import tldextract
from dateutil.parser import parse
from datetime import datetime
import spacy
from collections import Counter
from geopy.geocoders import Nominatim
from langdetect import detect  
from services.llm_stuff import create_label, create_keywords, create_embedding
from db.podcast_middleware import PodcastMiddleware
from googlenewsdecoder import gnewsdecoder
from playwright.async_api import async_playwright

from services.audio_services import create_news_script, load_content
from db.user_middleware import UserMiddleware
from services.image_service import load_image

import pika
import json
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))

NEWS_TASK_QUEUE = "news_crawler_task_queue"

print("connecting to rabbitmq", RABBITMQ_HOST, RABBITMQ_PORT)

user_middleware = UserMiddleware()
podcast_middleware = PodcastMiddleware()
nlp = spacy.load("en_core_web_sm")
geolocator = Nominatim(user_agent="Mac OS X 10_15_7")

def process_part1(content, title):
    general_label, sub_label = create_label(title)
    keywords = create_keywords(title)
    summary = ""
    # summary = create_summary(content)
    embedding = create_embedding(title)
    text_vector = create_embedding(content)
    return general_label, sub_label, keywords, summary, embedding, text_vector

def is_media_heavy(soup):
    media_tags = soup.find_all(["video", "audio", "iframe", "code"])
    visible_text = soup.get_text(separator="\n", strip=True)
    return len(media_tags) > 2 or len(visible_text.split()) < 100

def get_base_url(url):
    parsed = urlparse(url)
    ext = tldextract.extract(url)
    l1 = f"{ext.domain}.{ext.suffix}"

    return parsed.netloc, l1

def extract_visible_publish_date(soup):
    meta_tags = [
        {"property": "article:published_time"},
        {"name": "pubdate"},
        {"name": "date"}, 
    ]

    for tag in meta_tags:
        meta = soup.find("meta", attrs=tag)
        if meta and meta.get("content"):
            return meta["content"]

    for time_tag in soup.find_all("time"):
        if time_tag.get("datetime"):
            return time_tag["datetime"]
        
    text = soup.get_text(separator="\n", strip=True)
    lines = text.splitlines()
    keywords = ["published", "posted", "updated", "date"]

    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in keywords):
            # Try the next 1-2 lines for a date
            for offset in range(1, 3):
                if i + offset < len(lines):
                    try:
                        dt = parse(lines[i + offset], fuzzy=True)
                        return dt
                    except:
                        continue
    return None

def normalize_to_timestamp(time_value):
    # If it's already a float or int
    if time_value is None:
        return time.time()
    
    if isinstance(time_value, (int, float)):
        return float(time_value)

    # If it's a datetime object
    if isinstance(time_value, datetime):
        return time_value.timestamp()

    # If it's a string
    if isinstance(time_value, str):
        try:
            # Handle ISO 8601 'Z' (UTC)
            if time_value.endswith("Z"):
                time_value = time_value.replace("Z", "+00:00")
            dt = parse(time_value)
            return dt.timestamp()
        except Exception as e:
            raise ValueError(f"Invalid time string: {time_value!r}") from e

    raise TypeError(f"Unsupported time type: {type(time_value).__name__}")

def detect_news_url(url):
    keywords = ["sign-up", "signup", "sign-in", "signin", "register", "login", "log-in"]
    boring_keywords = ["about", "contact", "cookie", "privacy", "terms", "faq", "sitemap", "usingthebbc"]
    media_paths = ["video", "videos", "audio", "audios", "media", "playlist", "vod", "stream", "livestream", "watch", "player", "api", "apis", "podcast", "podcasts"]
    non_text_extensions = (".mp4", ".mp3", ".avi", ".mov", ".wav", ".ogg", ".webm", ".flac", ".jpg", ".png", ".gif", ".pdf")

    if any(keyword in url.lower() for keyword in keywords):
        return False
    if url.lower().endswith(non_text_extensions):
        return False
    if any(f"/{mp}/" in url.lower() or url.lower().endswith(f"/{mp}") for mp in boring_keywords):
        return False
    if any(f"/{mp}/" in url.lower() or url.lower().endswith(f"/{mp}") for mp in media_paths):
        return False
    return True


async def news_crawler(input_links, batch_size=2) -> None:
    crawler = BeautifulSoupCrawler(
        # max_request_retries=5,
        # request_handler_timeout=timedelta(seconds=5),
        # max_requests_per_crawl=2,
    )

    @crawler.router.default_handler
    async def request_handler(context: BeautifulSoupCrawlingContext) -> None:
        if not detect_news_url(context.request.url):
            return
        soup = context.soup
        html = soup.prettify()
        doc = Document(html)
        article_html = doc.summary()
        title = doc.title()
        bs4_soup = BeautifulSoup(article_html, "html.parser")
        content = bs4_soup.get_text(separator="\n", strip=True)

        pubtime = extract_visible_publish_date(soup)
        timestamp = normalize_to_timestamp(pubtime)
        heavy_media = is_media_heavy(soup)

        if title == "" or title is None or len(title.split()) <= 4:
            return
        
        if len(content.split()) <= 100:
            return

        # filter out non news content

        if timestamp is None or timestamp < time.time() - 1000 * 60 * 60 * 36:
            return
        
        if heavy_media:
            return
        
        if content != "":
            general_label, sub_label, keywords, summary, embedding, text_vector = process_part1(content, title)
            lang = detect(content)

            if not lang.startswith("en"):
                return

            data = {
                "link": context.request.url,
                "title": title,
                "content": content,
                "lang": lang,
                "country": "",
                "city": "",
                "region": "",
                "category": general_label,
                "subcategory": sub_label,
                "keywords": keywords,
                "title": title,
                "text_vector": text_vector,
                "summary": summary,
                "embedding": embedding,
                "created_at": int(time.time()),
                "published_at": int(timestamp)
            }

            
            pid = podcast_middleware.update_podcast(data)
            podcast_middleware.tag_hot_trending(text_vector)
            if pid:
                if user_middleware.match_user_preference(embedding):
                    podcast = podcast_middleware.get_podcast_by_id(pid)
                    def load_image_task():
                        asyncio.run(load_image(podcast, return_file=False))
                    threading.Thread(target=load_image_task).start()
                    def load_content_task():
                        asyncio.run(load_content(podcast))
                    threading.Thread(target=load_content_task).start()
                elif user_middleware.match_user_preference(embedding, threshold=0.75):
                    podcast = podcast_middleware.get_podcast_by_id(pid)
                    def load_script_task():
                        asyncio.run(create_news_script(podcast))
                    threading.Thread(target=load_script_task).start()
                
        return
    
    link_list = []
    for links in input_links:
        for link in links:
            if not link or not link['link']:
                continue
            if podcast_middleware.check_podcast_content(link['link']):
                continue
            podcast_id = podcast_middleware.create_podcast(link)
            if podcast_id:
                link_list.append(link['link'])
    await crawler.run(link_list)


def news_crawler_worker(ch, method, props, body):
    try:
        url_list = json.loads(body)
        try:
            asyncio.run(news_crawler(url_list))
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            print("news crawler function error", e)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    except Exception as e:
        print("news crawler worker error", e)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT, heartbeat=60))
channel = connection.channel()
channel.queue_declare(queue=NEWS_TASK_QUEUE)
channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue=NEWS_TASK_QUEUE, on_message_callback=news_crawler_worker)
print("Starting news crawler worker...")
channel.start_consuming()