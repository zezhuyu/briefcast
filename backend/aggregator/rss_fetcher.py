import schedule
from minio import Minio
import concurrent.futures
import os
import io
import asyncio
from PIL import Image
import time
import feedparser
import requests
import socket
import pymongo
import time
from dotenv import load_dotenv
from datetime import timedelta
import gc
import sys
from playwright.async_api import async_playwright
from urllib.parse import urlparse
import tldextract
from asyncio import Semaphore
from googlenewsdecoder import gnewsdecoder
import asyncio
from asyncio import Semaphore
from playwright.async_api import async_playwright

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aggregator.news_broker import send_crawler_task

load_dotenv()

MONGO_DB = os.getenv('MONGO_DB')
MONGO_HOST = os.getenv('MONGO_HOST')
MONGO_PORT = os.getenv('MONGO_PORT')
MONGO_USER = os.getenv('MONGO_USER')
MONGO_PASSWORD = os.getenv('MONGO_PASSWORD')
MONGO_AUTH_SOURCE = os.getenv('MONGO_AUTH_SOURCE')

connection_string = f"mongodb://"
if MONGO_USER and MONGO_PASSWORD:
    connection_string += f"{MONGO_USER}:{MONGO_PASSWORD}@"
connection_string += f"{MONGO_HOST}:{MONGO_PORT}"
if MONGO_USER and MONGO_PASSWORD:
    connection_string += f"?authSource={MONGO_AUTH_SOURCE}"
db = pymongo.MongoClient(connection_string)[MONGO_DB]['links']

MAX_NEWS_PER_FEED = 30

class TaskQueue:
    def __init__(self, max_concurrent_tasks=10):
        self.semaphore = Semaphore(max_concurrent_tasks)
        self.tasks = set()
        self.results = []

    async def add_task(self, coro):
        async with self.semaphore:
            task = asyncio.create_task(coro)
            self.tasks.add(task)
            try:
                result = await task
                if result is not None:
                    self.results.append(result)
            except Exception as e:
                print(f"Task failed: {str(e)}")
            finally:
                self.tasks.remove(task)

    async def wait_all(self):
        if self.tasks:
            await asyncio.gather(*self.tasks)
        return self.results

# Create a global task queue
task_queue = TaskQueue(max_concurrent_tasks=20)

# async def resolve_google_news_redirect(url):
#     async with async_playwright() as p:
#         browser = await p.chromium.launch(headless=True, timeout=5000)
#         page = await browser.new_page()
#         await page.goto(url, wait_until="load")
#         await page.wait_for_timeout(1000)
#         final_url = page.url
#         await browser.close()
#         return final_url



sem = Semaphore(5)

async def resolve_google_news_redirect(browser, url):
    async with sem:
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=10000)
            await page.wait_for_timeout(2000)  # Optional small wait
            final_url = page.url
        except Exception as e:
            print(f"Error resolving {url}: {e}")
            final_url = url  # fallback to original
        finally:
            await page.close()

        print(final_url)
        return final_url

def get_base_url(url):
    parsed = urlparse(url)
    ext = tldextract.extract(url)
    l1 = f"{ext.domain}.{ext.suffix}"

    return parsed.netloc, l1

async def process_feed(row):
    """
    Process a single RSS feed and return its entries.
    """
    rss_url = row['link']
    try:
        # Parse feed with etag and modified headers
        # TODO: remove this
        # if not rss_url.startswith("https://news.google.com"):
        #     return None
        

        feed = feedparser.parse(rss_url, etag=row['lastEtag'], modified=row['lastModified'])
        
        # Get feed metadata
        lastEtag = getattr(feed, 'etag', None)
        lastModified = getattr(feed, 'updated', None)
        updatedParsed = time.mktime(feed.updated_parsed) if hasattr(feed, 'updated_parsed') else None
        
        # Process all entries asynchronously in batches
        entry_list = await process_feed_entries(feed, row['country'], row['category'], -1)
        
        if entry_list:  # Only update if we got valid entries
            # Update database with new metadata
            db.find_one_and_update(
                {"_id": row['_id']}, 
                {"$set": {
                    "lastEtag": lastEtag,
                    "lastModified": lastModified,
                    "updatedParsed": updatedParsed,
                    "lastCheck": time.time(),
                    "available": True,
                }}
            )
            
            print(f"Processed {len(entry_list)} entries from {rss_url}")
            return entry_list
            
    except Exception as e:
        print(f"Error processing feed {rss_url}: {str(e)}")
        # Update database to mark feed as unavailable
        db.find_one_and_update(
            {"_id": row['_id']}, 
            {"$set": {
                "lastCheck": time.time(),
                "available": False,
            }}
        )
    return None

async def process_batch(batch, country, category, browser):
    """
    Process a batch of entries concurrently and return results.
    All entries in the batch are processed at the same time.
    """

    tasks = [process_entry(entry, country, category, browser) for entry in batch]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]

async def process_feed_entries(feed, country, category, batch_size=10):
    """
    Process all entries in a feed in batches.
    Only one batch is processed at a time, but all entries within a batch are processed concurrently.
    """
    entries = feed.entries
    results = []

    total_entries = min(len(entries), MAX_NEWS_PER_FEED)

    if batch_size == -1 or batch_size > total_entries:
        batch_size = total_entries
    
    # Process entries in batches
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for i in range(0, total_entries, batch_size):
            batch = entries[i:i + batch_size]
            print(f"Processing batch of {len(batch)} entries")
            # Process entire batch concurrently

            batch_results = await process_batch(batch, country, category, browser)
            results.extend(batch_results)
            print(f"Completed batch with {len(batch_results)} valid results")
            await asyncio.sleep(1)
            gc.collect()
        await browser.close()
    return results

async def get_all_link(timeout=5, feed_batch_size=10):
    socket.setdefaulttimeout(timeout)
    all_link = []
    
    # Get all feeds from database
    feeds = list(db.find())
    total_feeds = len(feeds)
    processed_feeds = 0
    
    # Process feeds in batches
    for i in range(0, total_feeds, feed_batch_size):
        batch = feeds[i:i + feed_batch_size]
        print(f"\nProcessing feed batch {i//feed_batch_size + 1}")
        
        # Process each feed in the batch sequentially
        for feed in batch:
            try:
                result = await process_feed(feed)
                if result:
                    send_crawler_task([result])
                    all_link.append(result)
                    gc.collect()
            except Exception as e:
                print(f"Error processing feed {feed['link']}: {str(e)}")
        
        # Update progress
        processed_feeds += len(batch)
        print(f"Processed {processed_feeds}/{total_feeds} feeds")
        
        # Clean up memory after each batch
        gc.collect()
    
    return all_link

async def process_entry(entry, country, category, browser):
    """
    Process a single feed entry asynchronously, handling all fields and Google News redirects.
    """
    try:
        title = entry.title
    except:
        title = None
        
    try:
        item_id = entry.id
    except:
        item_id = None
        
    try:
        link = entry.link
    except:
        link = None
        
    try:
        updated = entry.updated
    except:
        updated = None
        
    try:
        updated_parsed = time.mktime(entry.updated_parsed)
    except:
        updated_parsed = None

    # Handle Google News redirect if needed
    if link and get_base_url(link)[0] == "news.google.com":
        try:
            decoded_url = gnewsdecoder(link)
            if decoded_url.get("status"):
                link = decoded_url["decoded_url"]
            if link is None or get_base_url(link)[0] == "news.google.com":
                try:
                    link = await resolve_google_news_redirect(browser, link)
                except Exception as e:
                    pass
            if link is None or get_base_url(link)[0] == "news.google.com":
                return None
            return {
                "country": country,
                "category": category,
                "title": title,
                "link": link,
                "updated": updated,
                "updated_parsed": updated_parsed,
                "item_id": item_id
            }
        except Exception as e:
            print(f"Error resolving Google News redirect for {link}")
            pass
    elif link and get_base_url(link)[0] != "news.google.com":
        return {
            "country": country,
            "category": category,
            "title": title,
            "link": link,
            "updated": updated,
            "updated_parsed": updated_parsed,
            "item_id": item_id
        }
    else:
        return None

if __name__ == "__main__":
    asyncio.run(get_all_link())
    gc.collect()