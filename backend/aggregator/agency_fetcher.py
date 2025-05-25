import asyncio
from crawl4ai import *
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse, parse_qs, unquote
import tldextract
from playwright.async_api import async_playwright
import pymongo
import os
import sys
import gc
from dotenv import load_dotenv

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
db = pymongo.MongoClient(connection_string)[MONGO_DB]['agency']

async def resolve_google_news_redirect(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="load")
        await page.wait_for_timeout(1000)
        final_url = page.url
        await browser.close()
        return final_url

def get_base_url(url):
    parsed = urlparse(url)
    ext = tldextract.extract(url)
    l1 = f"{ext.domain}.{ext.suffix}"

    return parsed.netloc, l1


def extract_google_news_url(google_url):
    parsed = urlparse(google_url)
    qs = parse_qs(parsed.query)
    real_url = qs.get("url") or qs.get("u")
    
    if real_url:
        return unquote(real_url[0])
    else:
        # fallback: sometimes Google includes the full URL path-encoded
        if "/articles/" in google_url:
            article_path = google_url.split("/articles/")[-1].split("?")[0]
            parts = article_path.split("https")
            if len(parts) > 1:
                return "https" + parts[-1].replace("_", "/")
    return None

def is_url(text):
    pattern = re.compile(
        r'^(https?://)?'         # optional http or https
        r'([a-z0-9-]+\.)+[a-z]{2,}'  # domain
        r'(:\d+)?'               # optional port
        r'(/[^\s]*)?$',          # optional path
        re.IGNORECASE
    )
    return bool(pattern.match(text))

def get_all_urls(all_links, tag_mode=False):
    keywords = ["sign-up", "signup", "sign-in", "signin", "register", "login", "log-in"]
    boring_keywords = ["about", "contact", "cookie", "privacy", "terms", "faq", "sitemap", "usingthebbc"]
    media_paths = ["video", "videos", "audio", "audios", "media", "playlist", "vod", "stream", "livestream", "watch", "player", "api", "apis", "podcast", "podcasts"]
    non_text_extensions = (".mp4", ".mp3", ".avi", ".mov", ".wav", ".ogg", ".webm", ".flac", ".jpg", ".png", ".gif", ".pdf")

    pattern = re.compile(r'(sign[-_]?in|sign[-_]?up|log[-_]?in|register)', re.IGNORECASE)

    url_list = []
    for url in all_links:
        if not tag_mode and len(url['text'].split()) <= 4:
            continue
        elif tag_mode and len(url['text'].split()) > 4:
            continue
        if url['text'].startswith("!["):
            continue
        if any(keyword in url['href'].lower() for keyword in keywords):
            continue
        if url['href'].lower().endswith(non_text_extensions):
            continue
        if pattern.search(url['text'].lower()):
            continue
        if any(f"/{mp}/" in url['href'].lower() or url['href'].lower().endswith(f"/{mp}") for mp in boring_keywords):
            continue
        if any(f"/{mp}/" in url['href'].lower() or url['href'].lower().endswith(f"/{mp}") for mp in media_paths):
            continue

        url_list.append(url['href'])
    return url_list

def get_url_list(result):
    # all_links = result.links['internal']
    all_links = []
    if all_links == []:
        markdown_text = result.markdown
        matches = re.findall(r'\[([^\]]+)\]\((https?://[^\s)]+)\)', markdown_text)  
        for match in matches:
            if len(match[0].split()) <= 4:
                continue
            all_links.append({'text': match[0], 'href': match[1]})

    url_list = get_all_urls(all_links)
    
    if url_list == []:
        markdown_text = result.markdown
        matches = re.findall(r'\[([^\]]+)\]\((https?://[^\s)]+)\)', markdown_text)  
        for match in matches:
            if len(match[0].split()) < 4:
                continue
            all_links.append({'text': match[0], 'href': match[1]})

    url_list = get_all_urls(all_links)

    return url_list

def get_tag_urls(result):

    html = result.html
    soup = BeautifulSoup(html, "html.parser")

    nav_candidates = soup.find_all(
        lambda tag: tag.name in ["nav", "ul", "div"] and 
                    any(kw in (tag.get("id", "") + " " + " ".join(tag.get("class", []))).lower()
                        for kw in ["nav", "navbar", "menu", "navigation"])
    )
    
    navbar_links = set()

    for container in nav_candidates:
        for a in container.find_all("a", href=True):
            href = a["href"]
            if href == "" or href == result.url or not is_url(href):
                continue
            text = a.get_text(strip=True)
            if href and text:
                navbar_links.add(href)

    if len(navbar_links) == 0:
        markdown_text = result.markdown
        matches = re.findall(r'\[([^\]]+)\]\((https?://[^\s)]+)\)', markdown_text) 

        tag_list = []

        for match in matches:
            tag_list.append({"text": match[0], "href": match[1]})

        navbar_links = get_all_urls(tag_list, tag_mode=True)

    return navbar_links

async def agency_crawler(url):
    browser_conf = BrowserConfig(
        headless=True, 
        # verbose=False,
        # use_managed_browser=True,
        java_script_enabled=True,
    )
    crawl_config = CrawlerRunConfig(
        process_iframes=True
    )
    async with AsyncWebCrawler(config=browser_conf) as crawler:
        result = await crawler.arun(url=url, bypass_cache=True, config=crawl_config)
        return result


async def get_agency_urls():
    url_list = []
    for row in db.find():
        url = row['link']

        result = await agency_crawler(url)
        main_url_list = get_url_list(result)
        tag_urls = get_tag_urls(result)
        tmp_url_list = []
        for url in main_url_list:
            if get_base_url(url)[0] == "news.google.com":
                url = await extract_google_news_url(url)
            tmp_url_list.append({"link": url})
        # send_crawler_task([tmp_url_list])
        url_list.append(tmp_url_list)

        # for url in tag_urls:
        #     result = await agency_crawler(url)
        #     sub_url_list = get_url_list(result)
        #     tmp_url_list = []
        #     for url in sub_url_list:
        #         if get_base_url(url)[0] == "news.google.com":
        #             url = await extract_google_news_url(url)
        #         tmp_url_list.append({"link": url})
        #     url_list.append(tmp_url_list)
    gc.collect()
    return url_list



if __name__ == "__main__":
    asyncio.run(get_agency_urls())