#!/usr/bin/env python3
"""
Script to load PostgreSQL schema from DDL files.
"""
import os
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_database_if_not_exists(args):
    """Create the database if it doesn't exist"""
    conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    # Check if database exists
    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (args.database,))
    exists = cursor.fetchone()
    
    if not exists:
        print(f"Creating database {args.database}...")
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(args.database)))
        print(f"Database {args.database} created successfully")
    else:
        print(f"Database {args.database} already exists")
    
    cursor.close()
    conn.close()

def load_schema(args):
    """Load schema from DDL files"""
    conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    for schema_file in args.schema_files:
        # Construct full path to schema file
        schema_path = os.path.join(args.schema_dir, schema_file)
        
        if not os.path.exists(schema_path):
            print(f"Error: Schema file {schema_path} not found")
            continue
        
        print(f"Loading schema from {schema_path}...")
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
            
        try:
            cursor.execute(schema_sql)
            print(f"Schema from {schema_path} loaded successfully")
        except psycopg2.Error as e:
            print(f"Error loading schema from {schema_path}: {e}")
    
    cursor.close()
    conn.close()

def setup_postgresql(host=None, port=None, user=None, password=None, database=None, 
                         create_db=False, schema_files=None, schema_dir=None):
    """
    Function to be called from other modules to load PostgreSQL schema
    
    Args:
        host (str): PostgreSQL host
        port (int): PostgreSQL port
        user (str): PostgreSQL user
        password (str): PostgreSQL password
        database (str): PostgreSQL database name
        create_db (bool): Create database if it doesn't exist
        schema_files (list): List of DDL files to load
        schema_dir (str): Directory containing schema files
    """
    # Create a namespace object to mimic argparse result
    class Args:
        pass
    
    args = Args()
    
    # Set arguments from parameters or environment variables
    args.host = host or os.getenv('POSTGRES_HOST', 'localhost')
    args.port = port or int(os.getenv('POSTGRES_PORT', '5432'))
    args.user = user or os.getenv('POSTGRES_USER', 'postgres')
    args.password = password or os.getenv('POSTGRES_PASSWORD', '')
    args.database = database or os.getenv('POSTGRES_DB', 'podcast_app')
    args.create_db = create_db
    args.schema_files = schema_files or os.getenv('POSTGRES_SCHEMA_FILES', 'user.ddl podcast.ddl').split()
    args.schema_dir = schema_dir or os.getenv('POSTGRES_SCHEMA_DIR', './init_db')

    if args.create_db:
        create_database_if_not_exists(args)
    
    load_schema(args)
    print("Schema loading completed")

