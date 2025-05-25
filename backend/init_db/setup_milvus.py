from pymilvus import MilvusClient, DataType, Function, FunctionType
from datetime import datetime, timezone
from dotenv import load_dotenv
import os
import time
import globals
import schedule
import asyncio

load_dotenv()

DIMENSION = int(os.getenv('MILVUS_DIMENSION', 768))

schema = MilvusClient.create_schema()

index_params = MilvusClient.prepare_index_params()

bm25_function = Function(
    name="title_bm25_emb", # Function name
    input_field_names=["title"], # Name of the VARCHAR field containing raw text data
    output_field_names=["sparse"], # Name of the SPARSE_FLOAT_VECTOR field reserved to store generated embeddings
    function_type=FunctionType.BM25, # Set to `BM25`
)

schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True, auto_id=True)
schema.add_field(field_name="pid", datatype=DataType.VARCHAR, max_length=1000, enable_analyzer=True, enable_match=True)
schema.add_field(field_name="lang", datatype=DataType.VARCHAR, max_length=100)
schema.add_field(field_name="country", datatype=DataType.VARCHAR, max_length=1000)
schema.add_field(field_name="region", datatype=DataType.VARCHAR, max_length=1000)
schema.add_field(field_name="city", datatype=DataType.VARCHAR, max_length=1000)
schema.add_field(field_name="category", datatype=DataType.VARCHAR, max_length=1000)
schema.add_field(field_name="subcategory", datatype=DataType.VARCHAR, max_length=1000)
schema.add_field(field_name="keywords", datatype=DataType.ARRAY, element_type=DataType.VARCHAR, max_length=1000, max_capacity=1000)
schema.add_field(field_name="summary", datatype=DataType.VARCHAR, max_length=20000)
schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=DIMENSION)
schema.add_field(field_name="text_vector", datatype=DataType.FLOAT_VECTOR, dim=DIMENSION)
schema.add_field(field_name="published_at", datatype=DataType.INT64)
schema.add_field(field_name="created_at", datatype=DataType.INT64)
schema.add_field(field_name="title", datatype=DataType.VARCHAR, max_length=1000, enable_analyzer=True)
schema.add_field(field_name="sparse", datatype=DataType.SPARSE_FLOAT_VECTOR)
schema.add_function(bm25_function)

index_params.add_index(
    field_name="sparse",
    index_type="SPARSE_INVERTED_INDEX",
    metric_type="BM25",
    params={
        "inverted_index_algo": "DAAT_MAXSCORE",
        "bm25_k1": 1.2,
        "bm25_b": 0.75
    }
)

index_params.add_index(
    field_name="vector",
    index_type="IVF_FLAT",
    metric_type="COSINE",
    params={
        "nlist": 128
    }
)

index_params.add_index(
    field_name="text_vector",
    index_type="IVF_FLAT",
    metric_type="COSINE",
    params={
        "nlist": 128
    }
)

class MilvusMiddleware:
    def __init__(self):
        self.host = os.getenv('MILVUS_HOST', 'localhost:19530')
        self.dimension = int(os.getenv('MILVUS_DIMENSION', 768))
        self.collection_name = os.getenv('MILVUS_COLLECTION_NAME', 'briefcast')
        self.user_collection_name = os.getenv('MILVUS_USER_COLLECTION_NAME', 'briefcast_user')
        self.store_time = int(os.getenv('PODCAST_STORE_TIME', 60*60*24*60))
        self.daily_collection = ""
        self.client = MilvusClient(self.host)
        self.hourly_collection = "briefcast_hourly"
        self.daily_collection = "briefcast_daily"
        self.weekly_collection = "briefcast_weekly"
        

    def get_daily_collection(self):
        return self.daily_collection

    def create_collection(self):
        if not self.client.has_collection(collection_name=self.collection_name):
            # self.client.create_collection(self.collection_name, enable_dynamic_field=True, auto_id=True, dimension=self.dimension)
            self.client.create_collection(collection_name=self.collection_name, schema=schema, index_params=index_params)
        if not self.client.has_collection(collection_name=self.user_collection_name):
            self.client.create_collection(self.user_collection_name, enable_dynamic_field=True, auto_id=True, dimension=self.dimension)

    def create_daily_collection(self):
        globals.MILVUS_DAILY_COLLECTION = self.daily_collection
        if not self.client.has_collection(collection_name=self.daily_collection):
            # self.client.create_collection(self.daily_collection, enable_dynamic_field=True, auto_id=True, dimension=self.dimension)
            self.client.create_collection(collection_name=self.daily_collection, schema=schema, index_params=index_params)
    def create_hourly_collection(self):
        globals.MILVUS_HOURLY_COLLECTION = self.hourly_collection
        if not self.client.has_collection(collection_name=self.hourly_collection):
            # self.client.create_collection(self.hourly_collection, enable_dynamic_field=True, auto_id=True, dimension=self.dimension)
            self.client.create_collection(collection_name=self.hourly_collection, schema=schema, index_params=index_params)

    def create_weekly_collection(self):
        globals.MILVUS_WEEKLY_COLLECTION = self.weekly_collection
        if not self.client.has_collection(collection_name=self.weekly_collection):
            # self.client.create_collection(self.weekly_collection, enable_dynamic_field=True, auto_id=True, dimension=self.dimension)
            self.client.create_collection(collection_name=self.weekly_collection, schema=schema, index_params=index_params)
            
    def merge_weekly_collection(self):
        if self.client.has_collection(self.collection_name):
            source_collection = self.weekly_collection
            target_collection = self.collection_name

            TTL_SECONDS = 60*60*24*7

            current_timestamp = int(time.time())
            expiry_time = current_timestamp - TTL_SECONDS

            res = self.client.query(
                collection_name=source_collection,
                filter=f"published_at < {expiry_time}",
            )

            if res:
                output_data = [{field: doc[field] for field in doc if field != 'id'} for doc in res]
                self.client.insert(
                    collection_name=target_collection,
                    data=output_data
                )
                print(f"Inserted {len(res)} expired vectors into '{self.collection_name}'.")
                self.client.delete(
                    collection_name=source_collection,
                    filter=f"published_at < {expiry_time}",
                )
                self.client.flush(collection_name=source_collection)
                self.client.flush(collection_name=target_collection)
                print(f"Deleted expired vectors from '{self.weekly_collection}'.")

    
    def merge_daily_collection(self):
        if self.client.has_collection(self.weekly_collection):
            source_collection = self.daily_collection
            target_collection = self.weekly_collection

            TTL_SECONDS = 60*60*24

            current_timestamp = int(time.time())
            expiry_time = current_timestamp - TTL_SECONDS

            res = self.client.query(
                collection_name=source_collection,
                filter=f"published_at < {expiry_time}"
            )

            if res:
                output_data = [{field: doc[field] for field in doc if field != 'id'} for doc in res]
                self.client.insert(
                    collection_name=target_collection,
                    data=output_data
                )
                print(f"Inserted {len(res)} expired vectors into '{target_collection}'.")
                self.client.delete(
                    collection_name=source_collection,
                    filter=f"published_at < {expiry_time}",
                )
                self.client.flush(collection_name=source_collection)
                self.client.flush(collection_name=target_collection)
                print(f"Deleted expired vectors from '{source_collection}'.")

    def merge_hourly_collection(self):
        if self.client.has_collection(self.daily_collection):
            source_collection = self.hourly_collection
            target_collection = self.daily_collection

            TTL_SECONDS = 60*60

            current_timestamp = int(time.time())
            expiry_time = current_timestamp - TTL_SECONDS

            res = self.client.query(
                collection_name=source_collection,
                filter=f"published_at < {expiry_time}"
            )

            if res:
                output_data = [{field: doc[field] for field in doc if field != 'id'} for doc in res]
                self.client.insert(
                    collection_name=target_collection,
                    data=output_data
                )
                print(f"Inserted {len(res)} expired vectors into '{target_collection}'.")
                self.client.delete(
                    collection_name=source_collection,
                    filter=f"published_at < {expiry_time}",
                )
                self.client.flush(collection_name=source_collection)
                self.client.flush(collection_name=target_collection)
                print(f"Deleted expired vectors from '{source_collection}'.")

    def delete_expired_entries(self):
        current_timestamp = int(time.time())
        expiry_time = current_timestamp - self.store_time
        if self.client.has_collection(self.collection_name):
            self.client.delete(
                collection_name=self.collection_name,
                filter=f"published_at < {expiry_time}"
            )

    def _flush_collection(self, collection_name):
        self.client.flush(collection_name=collection_name)
        print(f"Flushed collection: {collection_name}")

    def flush_collections(self):
        """Flush collections on a schedule"""
        schedule.every(1).day.do(self._flush_collection, collection_name=self.collection_name)
        schedule.every(30).seconds.do(self._flush_collection, collection_name=self.user_collection_name)
        schedule.every(30).seconds.do(self._flush_collection, collection_name=self.daily_collection)
        schedule.every(30).seconds.do(self._flush_collection, collection_name=self.hourly_collection)
        schedule.every(1).day.do(self._flush_collection, collection_name=self.weekly_collection)
        print("Milvus flush collections setup")
        while True:
            schedule.run_pending()
            time.sleep(1)

    def auto_trigger(self):
        schedule.every(1).day.do(self.merge_daily_collection)
        schedule.every(1).hour.do(self.merge_hourly_collection)
        schedule.every(1).day.do(self.merge_weekly_collection)
        schedule.every(1).day.do(self.delete_expired_entries)
        print("Milvus auto trigger setup")
        while True:
            schedule.run_pending()
            time.sleep(1)

def setup_milvus():
    milvus = MilvusMiddleware()
    milvus.create_collection()
    milvus.create_hourly_collection()
    milvus.create_daily_collection()
    milvus.create_weekly_collection()
    return milvus

if __name__ == "__main__":
    milvus = MilvusMiddleware()
    milvus.create_collection()
    milvus.create_hourly_collection()
    milvus.create_daily_collection()
    milvus.create_weekly_collection()
    asyncio.run(milvus.auto_trigger())