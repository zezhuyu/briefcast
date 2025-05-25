#!/usr/bin/env python3
"""
Script to load RSS feed links from a CSV file into MongoDB.
"""
import os
import csv
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection parameters
MONGO_HOST = os.getenv('MONGO_HOST', 'localhost')
MONGO_PORT = int(os.getenv('MONGO_PORT', '27017'))
MONGO_USER = os.getenv('MONGO_USER', '')
MONGO_PASSWORD = os.getenv('MONGO_PASSWORD', '')
MONGO_DB = os.getenv('MONGO_DB', 'briefcast')
MONGO_AUTH_SOURCE = os.getenv('MONGO_AUTH_SOURCE', 'admin')
MONGO_LINKS_COLLECTION = os.getenv('MONGO_LINKS_COLLECTION', 'links')
MONGO_AGENCY_COLLECTION = os.getenv('MONGO_AGENCY_COLLECTION', 'agency')

def get_mongo_connection():
    """Get a connection to MongoDB"""
    connection_string = f"mongodb://"
    
    # Add authentication if provided
    if MONGO_USER and MONGO_PASSWORD:
        connection_string += f"{MONGO_USER}:{MONGO_PASSWORD}@"
    
    connection_string += f"{MONGO_HOST}:{MONGO_PORT}"
    
    # Add authentication source if using auth
    if MONGO_USER and MONGO_PASSWORD:
        connection_string += f"?authSource={MONGO_AUTH_SOURCE}"
    
    client = MongoClient(connection_string)
    return client

def load_links_to_mongodb(csv_file_path):
    """
    Load RSS feed links from a CSV file into MongoDB.
    
    Args:
        csv_file_path (str): Path to the CSV file containing links
        
    Returns:
        int: Number of links loaded
    """
    # Connect to MongoDB

    if not os.path.isfile(csv_file_path):
        print(f"Error: File '{csv_file_path}' not found.")
        return 0
    mongo_client = get_mongo_connection()
    db = mongo_client[MONGO_DB]
    links_collection = db[MONGO_LINKS_COLLECTION]
    
    # Initialize counter
    links_loaded = 0
    
    try:
        # Read CSV file
        with open(csv_file_path, 'r', encoding='utf-8') as csv_file:
            csv_reader = csv.reader(csv_file)
            
            # Process each row
            for row in csv_reader:
                if len(row) >= 3:
                    country, category, link = row[0], row[1], row[2]
                    
                    # Create document
                    link_doc = {
                        'country': country,
                        'category': category,
                        'link': link,
                        'lastEtag': None,
                        'lastModified': None,
                        'updatedParsed': None,
                        'lastCheck': None,
                        'available': False
                    }
                    
                    # Check if link already exists
                    existing_link = links_collection.find_one({'link': link})
                    if not existing_link:
                        # Insert document
                        links_collection.insert_one(link_doc)
                        links_loaded += 1
                        print(f"Loaded: {country}, {category}, {link}")
                    else:
                        print(f"Skipped (already exists): {link}")
                else:
                    print(f"Skipped invalid row: {row}")
        
        return links_loaded
    
    finally:
        # Close MongoDB connection
        mongo_client.close()

def load_agency_to_mongodb(csv_file_path):
    """
    Load RSS feed links from a CSV file into MongoDB.
    
    Args:
        csv_file_path (str): Path to the CSV file containing links
        
    Returns:
        int: Number of links loaded
    """
    # Connect to MongoDB

    if not os.path.isfile(csv_file_path):
        print(f"Error: File '{csv_file_path}' not found.")
        return 0
    mongo_client = get_mongo_connection()
    db = mongo_client[MONGO_DB]
    links_collection = db[MONGO_AGENCY_COLLECTION]
    
    # Initialize counter
    links_loaded = 0
    
    try:
        # Read CSV file
        with open(csv_file_path, 'r', encoding='utf-8') as csv_file:
            csv_reader = csv.reader(csv_file)
            
            # Process each row
            for row in csv_reader:
                if len(row) >= 3:
                    country, category, link = row[0], row[1], row[2]
                    
                    # Create document
                    link_doc = {
                        'country': country,
                        'category': category,
                        'link': link,
                        'lastCheck': None,
                        'available': False
                    }
                    
                    # Check if link already exists
                    existing_link = links_collection.find_one({'link': link})
                    if not existing_link:
                        # Insert document
                        links_collection.insert_one(link_doc)
                        links_loaded += 1
                        print(f"Loaded: {country}, {category}, {link}")
                    else:
                        print(f"Skipped (already exists): {link}")
                else:
                    print(f"Skipped invalid row: {row}")
        
        return links_loaded
    
    finally:
        # Close MongoDB connection
        mongo_client.close()