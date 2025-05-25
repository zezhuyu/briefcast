from minio import Minio
from dotenv import load_dotenv
import os
from nanoid import generate
from io import BytesIO
load_dotenv()

class MinioMiddleware:
    def __init__(self):
        self.minio_url = os.getenv('MINIO_URL', 'localhost:9000')
        self.access_key = os.getenv('MINIO_ACCESS_KEY', 'minio')
        self.secret_key = os.getenv('MINIO_SECRET_KEY', 'minio')
        self.briefcast_bucket = os.getenv('MINIO_AUDIO_BUCKET', 'briefcast')
        self.user_bucket = os.getenv('MINIO_USER_BUCKET', 'briefcastuser')
        self.client = Minio(
            self.minio_url,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=False,
        )

    def reconnect(self):
        if self.client is None or not self.client.bucket_exists(self.briefcast_bucket):
            self.client = Minio(
                self.minio_url,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=False,
            )

    def store_tmp_audio(self, audio_data):
        try:
            audio = "tmp/{}.wav".format(generate())
            audio_data.seek(0)
            self.client.put_object(self.briefcast_bucket, audio, audio_data, length=len(audio_data.getbuffer()))
            return f"{audio}"
        except Exception as e:  
            print(e)
            return None
    
    def get_tmp_audio(self, audio_url):
        try:
            response = self.client.get_object(bucket_name=self.briefcast_bucket, object_name=audio_url)
            file_buffer = BytesIO()
            file_buffer.write(response.data)
            file_buffer.seek(0)
            return file_buffer
        except Exception as e:
            print(e)
            return None
        
    def delete_tmp_audio(self, audio_url):
        try:
            self.client.remove_object(self.briefcast_bucket, audio_url)
        except Exception as e:
            print(e)
            return None
        
    def store_tmp_transcript(self, transcript_data):
        try:
            transcript = "tmp/{}.lrc".format(generate())
            transcript_buffer = BytesIO()
            transcript_text = '\n'.join(transcript_data)
            transcript_buffer.write(transcript_text.encode('utf-8'))
            transcript_buffer.seek(0)
            self.client.put_object(self.briefcast_bucket, transcript, transcript_buffer, length=len(transcript_buffer.getbuffer()))
            return f"{transcript}"
        except Exception as e:
            print(e)
            return None     
    
    def get_tmp_transcript(self, transcript_url):
        try:
            response = self.client.get_object(bucket_name=self.briefcast_bucket, object_name=transcript_url)
            file_buffer = BytesIO()
            file_buffer.write(response.data)
            file_buffer.seek(0)
            return file_buffer
        except Exception as e:
            print(e)
            return None
        
    def delete_tmp_transcript(self, transcript_url):
        try:
            self.client.remove_object(self.briefcast_bucket, transcript_url)
        except Exception as e:
            print(e)
            return None
            
    def store_tmp_image(self, image_data):
        try:
            image = "tmp/{}.png".format(generate())
            image_data.save(image_data, format='PNG')
            image_data.seek(0)
            self.client.put_object(self.briefcast_bucket, image, image_data, length=len(image_data.getbuffer()))
            return f"{image}"
        except Exception as e:
            print(e)
            return None
    
    def get_tmp_image(self, image_url):
        try:
            response = self.client.get_object(bucket_name=self.briefcast_bucket, object_name=image_url)
            file_buffer = BytesIO()
            file_buffer.write(response.data)
            file_buffer.seek(0)
            return file_buffer
        except Exception as e:
            print(e)
            return None
        
    def delete_tmp_image(self, image_url):
        try:
            self.client.remove_object(self.briefcast_bucket, image_url)
        except Exception as e:
            print(e)
            return None
        
    def store_audio(self, audio_data):
        try:
            podcast = "audio/{}.wav".format(generate())
            audio_data.seek(0)
            self.client.put_object(self.briefcast_bucket, podcast, audio_data, length=len(audio_data.getbuffer()))
            return f"{podcast}"
        except Exception as e:
            print(e)
            return None
    
    def store_image(self, image_data):
        try:
            image = "image/{}.png".format(generate())
            image_buffer = BytesIO()
            image_data.save(image_buffer, format='JPEG', quality=30, optimize=True)
            image_buffer.seek(0)
            self.client.put_object(self.briefcast_bucket, image, image_buffer, length=len(image_buffer.getbuffer()))
            return f"{image}"
        except Exception as e:
            print(e)
            return None
        
    def store_transcript(self, transcript_data):
        try:
            transcript = "transcript/{}.lrc".format(generate())
            transcript_buffer = BytesIO()
            transcript_text = '\n'.join(transcript_data)
            transcript_buffer.write(transcript_text.encode('utf-8'))
            transcript_buffer.seek(0)
            self.client.put_object(self.briefcast_bucket, transcript, transcript_buffer, length=len(transcript_buffer.getbuffer()))
            return f"{transcript}"
        except Exception as e:
            print(e)
            return None

    def store_user_audio(self, user_id, audio, transcript, image):
        image_buffer = BytesIO()
        image.save(image_buffer, format='JPEG', quality=30, optimize=True)
        image_buffer.seek(0)
        podcast_id = generate()
        podcast_name = "audio/{}.wav".format(podcast_id)
        transcript_name = "transcript/{}.lrc".format(podcast_id)
        image_name = "image/{}.png".format(podcast_id)
        try:
            self.client.put_object(self.user_bucket, f"{user_id}/{podcast_name}", audio, length=len(audio.getbuffer()))
            self.client.put_object(self.user_bucket, f"{user_id}/{transcript_name}", transcript, length=len(transcript.getbuffer()))
            self.client.put_object(self.user_bucket, f"{user_id}/{image_name}", image_buffer, length=len(image_buffer.getbuffer()))
            return f"{user_id}/{podcast_name}", f"{user_id}/{transcript_name}", f"{user_id}/{image_name}"
        except Exception as e:
            print(e)
            return None
        
    def get_audio(self, audio_url):
        try:
            response = self.client.get_object(bucket_name=self.briefcast_bucket, object_name=f"audio/{audio_url}")
            file_buffer = BytesIO()
            file_buffer.write(response.data)
            file_buffer.seek(0)
            return file_buffer
        except Exception as e:
            print(e)
            return None
    
    def get_transcript(self, transcript_url):
        try:
            response = self.client.get_object(bucket_name=self.briefcast_bucket, object_name=f"transcript/{transcript_url}")
            file_buffer = BytesIO()
            file_buffer.write(response.data)
            file_buffer.seek(0)
            return file_buffer
        except Exception as e:
            print(e)
            return None
        
    def get_image(self, image_url):
        try:
            response = self.client.get_object(bucket_name=self.briefcast_bucket, object_name=f"image/{image_url}")
            file_buffer = BytesIO()
            file_buffer.write(response.data)
            file_buffer.seek(0)
            return file_buffer
        except Exception as e:
            print(e)
            return None
    
    def get_file(self, file_path):
        try:
            response = self.client.get_object(bucket_name=self.briefcast_bucket, object_name=file_path)
            file_buffer = BytesIO()
            file_buffer.write(response.data)
            file_buffer.seek(0)
            return file_buffer
        except Exception as e:
            print(e)
            return None
        
    def delete_file(self, file_path):
        try:
            self.client.remove_object(self.briefcast_bucket, file_path)
        except Exception as e:
            print(e)
            return None
        
    def get_user_file(self, user_id, file_path):
        try:
            response = self.client.get_object(bucket_name=self.user_bucket, object_name=f"{user_id}/{file_path}")
            file_buffer = BytesIO()
            file_buffer.write(response.data)
            file_buffer.seek(0)
            return file_buffer
        except Exception as e:
            print(e)
            return None
