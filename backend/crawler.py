import asyncio
import schedule
from aggregator.rss_fetcher import get_all_link
from aggregator.agency_fetcher import get_agency_urls
# from aggregator.news_crawler import news_crawler

async def run_news_task():
    links = await get_all_link()
    # await news_crawler(input_links=links)

async def run_agency_task():
    links = await get_agency_urls()
    # await news_crawler(input_links=links)

async def run_scheduler():
    schedule.every(60*60*6).seconds.do(lambda: asyncio.create_task(run_news_task()))
    # schedule.every(60*60*6).seconds.do(lambda: asyncio.create_task(run_agency_task()))
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

if __name__ == "__main__":
    # asyncio.run(news_crawler(input_links=asyncio.run(get_agency_urls())))
    links = asyncio.run(get_all_link())
    # asyncio.run(news_crawler(input_links=links))
    asyncio.run(run_scheduler())