# Briefcast Implementation Details

This document provides detailed information about the implementation of Briefcast's core features, including database design, recommendation system, and AI model integration.

## Database Architecture

Briefcast uses a multi-database architecture to optimize different aspects of the application:

### PostgreSQL (Main Database)
Primary database for structured data and indexing, with vector search capabilities for initial filtering and user-based recommendations.

#### Key Tables:
1. **Users**
   - Core user information
   - Vector embeddings for preferences (768-dim)
   - Daily and batch preference tracking
   - Category preferences

2. **Podcasts**
   - Core podcast metadata
   - Categories and subcategories
   - Ratings and engagement metrics
   - Vector embeddings for similarity search
   - Trending flags and scores
   - Hot news indicators

3. **User History**
   - Detailed listening history
   - Interaction tracking
   - Playlist management
   - User preferences

#### Vector Search Implementation
PostgreSQL uses pgvector for initial filtering and user-based recommendations:

1. **Hot-Trending Detection**
   ```sql
   -- Initial filtering of trending content
   SELECT * FROM podcasts 
   WHERE trending = true 
   ORDER BY trending_score DESC 
   LIMIT 100;
   ```

2. **User-Based Recommendations**
   ```sql
   -- Filter trending content and apply cosine similarity
   SELECT p.*, 
          1 - (p.embedding <=> u.embedding) as similarity
   FROM podcasts p, users u
   WHERE p.trending = true 
   AND u.id = :user_id
   ORDER BY similarity DESC
   LIMIT 50;
   ```

#### Performance Optimization
- Two-stage recommendation process:
  1. PostgreSQL: Initial filtering and trending detection
  2. Milvus: Fine-grained semantic search

- Indexing Strategy:
  ```sql
  -- Vector similarity index
  CREATE INDEX ON podcasts USING ivfflat (embedding vector_cosine_ops);
  
  -- Trending and score index
  CREATE INDEX ON podcasts (trending, trending_score);
  
  -- Composite index for user recommendations
  CREATE INDEX ON podcasts (trending, category, subcategory);
  ```

#### Use Cases

1. **Hot-Trending Detection**
   ```
   Process:
   1. Filter trending content in PostgreSQL
   2. Apply cosine similarity for user relevance
   3. Pass filtered results to Milvus for semantic search
   ```

2. **User Recommendations**
   ```
   Process:
   1. Get user preferences and history from PostgreSQL
   2. Filter trending content based on user categories
   3. Apply initial vector similarity in PostgreSQL
   4. Use Milvus for final semantic ranking
   ```

3. **Category-Based Filtering**
   ```
   Process:
   1. Filter by category and trending status
   2. Apply vector similarity for relevance
   3. Combine with Milvus results for final ranking
   ```

#### Performance Considerations
- PostgreSQL handles initial filtering to reduce Milvus load
- Vector operations in PostgreSQL for quick filtering
- Composite indexes for efficient querying
- Regular index maintenance for optimal performance

### MongoDB (Document Store)
Used for storing long-form content and unstructured data.

#### Collections:
1. **Podcasts**
   - Full content and transcripts
   - Rich metadata
   - Text search capabilities
   - Flexible schema for evolving content

2. **Episodes**
   - Episode-specific content
   - Transcripts and descriptions
   - Keywords and metadata

### Milvus (Vector Database)
Specialized database for semantic search and recommendations.

#### Multi-Collection Design
The system uses multiple collections to optimize different use cases and improve performance:

1. **Main Collection**
   - Stores all news articles up to 60 days
   - Used for general search and long-term recommendations
   - 768-dimensional vectors for semantic search
   - BM25 text matching for keyword search
   - Primary source for user-initiated searches

2. **Time-based Collections**
   - **Hourly Collection (1-2 hours)**
     - Latest news articles
     - Primary source for real-time trending detection
     - Used for immediate user recommendations
     - Automatically merged into daily collection

   - **Daily Collection (1-2 days)**
     - Source for daily briefing podcast generation
     - Used for short-term trending analysis
     - Combines data from hourly collections
     - Automatically merged into weekly collection

   - **Weekly Collection (7-8 days)**
     - Used for weekly trend analysis
     - Source for personalized recommendations
     - Combines data from daily collections
     - Automatically merged into main collection

#### Collection Management
- Automatic data migration between collections
- Time-based data expiration
- Efficient query routing based on time ranges
- Optimized for different use cases:
  - Real-time trending: Hourly, Daily collection
  - Daily briefings: Hourly, Daily collection
  - Personalized recommendations: Hourly, Daily, Weekly collections
  - Search: All collections with time-based prioritization

#### Use Cases by Collection

1. **Hourly Collection**
   ```
   Use Cases:
   - Real-time trending detection
   - Immediate user recommendations
   - Breaking news alerts
   - Live content updates
   ```

2. **Daily Collection**
   ```
   Use Cases:
   - Daily briefing podcast generation
   - Short-term trend analysis
   - Daily user recommendations
   - Content freshness scoring
   ```

3. **Weekly Collection**
   ```
   Use Cases:
   - Weekly trend analysis
   - Personalized recommendations
   - Content popularity tracking
   - User preference learning
   ```

4. **Main Collection**
   ```
   Use Cases:
   - General search functionality
   - Long-term recommendations
   - Historical content access
   - Comprehensive trend analysis
   ```

#### Performance Benefits
1. **Query Optimization**
   - Smaller collections for faster retrieval
   - Targeted queries based on time ranges
   - Reduced search space for recent content
   - Efficient hot/trending detection

2. **Resource Management**
   - Distributed load across collections
   - Optimized memory usage
   - Better cache utilization
   - Reduced index maintenance overhead

3. **Scalability**
   - Horizontal scaling capability
   - Independent collection scaling
   - Load distribution
   - Resource isolation

### MinIO (Object Storage)
Handles binary data and media files.

#### Buckets:
1. **Audio Bucket**
   - Podcast audio files
   - Episode recordings
   - Generated content

2. **User Bucket**
   - User-specific content
   - Profile images
   - Custom audio files

## Data Flow

1. **Content Ingestion**
   ```
   RSS Feed → RSS Fetcher → MongoDB (raw content)
   ```

2. **Content Processing**
   ```
   MongoDB → GenAI Worker → 
   ├── PostgreSQL (metadata)
   ├── Milvus (embeddings)
   └── MinIO (media files)
   ```

3. **User Interaction**
   ```
   User Action → PostgreSQL (history)
   └── Milvus (preference vectors)
   ```

4. **Recommendation Generation**
   ```
   Milvus (semantic search)
   └── PostgreSQL (filtered results)
   ```

## Database Optimization

### PostgreSQL
- Vector indexes for similarity search
- Composite indexes for common queries
- Partitioning for large tables
- Full-text search capabilities

### MongoDB
- Text indexes for content search
- Compound indexes for common queries
- Schema validation
- Efficient document storage

### Milvus
- IVF_FLAT index for vector search
- BM25 for text matching
- Time-based data management
- Automatic data migration

### MinIO
- Content-addressable storage
- Efficient media streaming
- Access control policies
- Backup and replication

## Data Retention

1. **PostgreSQL**
   - User data: 60 days
   - History: 60 days

2. **MongoDB**
   - Content: 60 days

3. **Milvus**
   - Hourly data: 1-2 hours
   - Daily data: 1-2 days
   - Weekly data: 7-8 days
   - Main collection: 60 days

4. **MinIO**
   - Audio files: 60 days
   - User content: 60 days
   - Temporary files: 24 hours

## Recommendation System

The recommendation system consists of three key components:

### 1. News Crawler
- Analyzes and processes news content
- Extracts key information and generates embeddings
- Updates trending scores and hot news indicators
- Maintains content freshness and relevance

### 2. User Experience Collection
- Tracks user interactions with podcasts
- Records various user activities:
  ```python
  weight = {
      "80%": 1,          # Complete listening
      "50%": 0.5,        # Partial listening
      "30%": 0,          # Minimal listening
      "0%": -0.5,        # Skipped
      "like": 1,         # Positive feedback
      "dislike": -1,     # Negative feedback
      "share": 1.8,      # Content sharing
      "download": 1.3,   # Content download
      "add_to_playlist": 1.4,  # Playlist addition
      "search": 0.75,    # Search activity
  }
  ```
- Computes activity weights based on:
  - Listening completion percentage
  - User interactions (likes, shares, etc.)
  - Search history
  - Playlist additions

### 3. Core Recommendation Engine

#### User Preference Vectors
The system maintains multiple preference vectors for each user:

1. **Realtime Vector**
   - Updated after every 10 user activities (batch_size)
   - Computation formula:
   ```python
   realtime_vector = prev_vector * 0.9 + current_batch_mean * 0.1
   ```
   - Prevents bias from single activities
   - Provides immediate feedback for recommendations

2. **Daily Vector**
   - Updated once per day
   - Computation formula:
   ```python
   daily_vector = prev_day_vector * 0.8 + daily_mean * 0.2
   ```
   - More stable than realtime vector
   - Used for long-term preference tracking

#### Vector Computation Process

1. **Batch Processing**
   ```python
   def update_user_batch_embedding(user_id, embedding, weight):
       # Accumulate embeddings with weights
       total_weight = embedding * weight
       if batched_vector is not None:
           total_weight += batched_vector
       
       # Update batch count and total weight
       batch_count += 1
       batch_total_weight += weight
       
       # When batch size reached, update realtime vector
       if batch_count >= batch_size:
           realtime_vector = compute_batch_embedding(
               prev_vector,
               get_embedding_mean(batched_vector, batch_total_weight)
           )
   ```

2. **Daily Processing**
   ```python
   def update_user_daily_embedding(user_id, embedding, weight):
       # Accumulate daily embeddings
       total_weight = embedding * weight
       if daily_vector is not None:
           total_weight += daily_vector
       
       # Update daily counts
       daily_listen_count += 1
       daily_total_weight += weight
       
       # Daily update computes new preference vector
       if time_for_daily_update:
           daily_vector = compute_daily_embedding(
               prev_day_vector,
               get_embedding_mean(daily_vector, daily_total_weight)
           )
   ```

#### Weight Computation
- Activity weights are computed based on:
  ```python
  def listen_weight(percentage):
      if percentage < 0.05: return 0
      elif percentage < 0.3: return -0.5
      elif percentage < 0.5: return 0
      elif percentage < 0.8: return 0.5
      else: return 1
  ```
- Diminishing returns for repeated activities:
  ```python
  def dim_weight(weight, replay):
      return weight * (1 / math.e ** (replay - 1))
  ```
