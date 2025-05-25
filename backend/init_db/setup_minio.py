from minio import Minio
from dotenv import load_dotenv
import os
load_dotenv()

def setup_minio(host=None, access_key=None, secret_key=None, audio_bucket=None, user_bucket=None):
    """
    Function to be called from other modules to set up MinIO
    
    Args:
        host (str): MinIO host
        port (int): MinIO port
        access_key (str): MinIO access key
        secret_key (str): MinIO secret key
        bucket_name (str): MinIO bucket name
    """
    minio_url = host or os.getenv('MINIO_URL', 'localhost:9000')
    access_key = access_key or os.getenv('MINIO_ACCESS_KEY', 'minio')
    secret_key = secret_key or os.getenv('MINIO_SECRET_KEY', 'minio')
    audio_bucket = audio_bucket or os.getenv('MINIO_AUDIO_BUCKET', 'briefcast')
    user_bucket = user_bucket or os.getenv('MINIO_USER_BUCKET', 'briefcastuser')

    client = Minio(
        minio_url,
        access_key=access_key,
        secret_key=secret_key,
        secure=False,
    )

    if not client.bucket_exists(audio_bucket):
        client.make_bucket(audio_bucket)

    if not client.bucket_exists(user_bucket):
        client.make_bucket(user_bucket)

if __name__ == "__main__":
    setup_minio()