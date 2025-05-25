from init_db.setup_postgresql import setup_postgresql
from init_db.setup_milvus import setup_milvus
from init_db.setup_mongodb import setup_mongodb
from init_db.setup_minio import setup_minio
from init_db.load_links import load_links_to_mongodb, load_agency_to_mongodb

setup_postgresql()
milvus = setup_milvus()
setup_mongodb()
setup_minio()
load_links_to_mongodb('./init_db/rss.csv')
load_agency_to_mongodb('./init_db/agency.csv')

