import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.minio_middleware import MinioMiddleware
from db.podcast_middleware import PodcastMiddleware
from services.llm_stuff import create_image
from services.mq_broker import send_task

IMAGE_TASK_QUEUE = "image_task_queue"

minio_middleware = MinioMiddleware()
podcast_middleware = PodcastMiddleware()

async def load_image(podcast, return_file=True):
    if podcast["cover_image_url"] == "":
        image_url = send_task(podcast, IMAGE_TASK_QUEUE)
        if not image_url:
            return None
        if isinstance(image_url, bytes):
            image_url = image_url.decode('utf-8')
        if return_file and image_url:
            image = minio_middleware.get_file(image_url)
            image.seek(0)
            return image
        else:
            return image_url
    else:
        if return_file:
            image = minio_middleware.get_file(podcast["cover_image_url"])
            image.seek(0)
            return image
        else:
            return podcast["cover_image_url"]
        
def _load_image(podcast):
    podcast = podcast_middleware.get_podcast_by_id(podcast["id"])
    if podcast and podcast["cover_image_url"] != "":
        return podcast["cover_image_url"]
    instruction = podcast["description"] if podcast["description"] != "" else podcast["title"]
    if instruction == "":
        return None
    try:
        image = create_image(instruction)
        if image:
            image_url = minio_middleware.store_image(image)
            if image_url:
                print("store image")
                podcast_middleware.update_podcast_cover_image_url(podcast["id"], image_url)
                print("update image url")
                return image_url
            else:
                return None
        else:
            return None
    except Exception as e:
        print(e)
        return None