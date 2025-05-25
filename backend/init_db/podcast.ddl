-- Enable vector extension if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE clusters (
    cid TEXT PRIMARY KEY,
    trending BOOLEAN DEFAULT FALSE,
    trending_time TIMESTAMP,
    trending_score INTEGER DEFAULT 0,
    hot BOOLEAN DEFAULT FALSE,
    hot_time TIMESTAMP,
    hot_score INTEGER DEFAULT 0
);

-- Main podcasts table
CREATE TABLE podcasts (
    id TEXT PRIMARY KEY,
    link TEXT UNIQUE,
    cluster_id TEXT REFERENCES clusters(cid) ON DELETE SET NULL,
    title TEXT NOT NULL,
    lang TEXT NOT NULL,
    city TEXT,
    region TEXT,
    country TEXT,
    category TEXT NOT NULL,         -- Main category as a single value
    subcategory TEXT NOT NULL,      -- Subcategory as a single value
    published_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    modify_at TIMESTAMP DEFAULT NOW(), 
    audio_url TEXT,
    transcript_url TEXT,
    cover_image_url TEXT,
    duration_seconds INTEGER,
    positive_rating INTEGER DEFAULT 0,  -- Count of positive ratings
    negative_rating INTEGER DEFAULT 0,  -- Count of negative ratings
    total_rating INTEGER DEFAULT 0,     -- Total number of ratings
    play_count INTEGER DEFAULT 0,
    embedding vector(768)               -- Vector embedding for similarity search
);

-- Podcast episodes table (if needed)
CREATE TABLE podcast_episodes (
    episode_id TEXT PRIMARY KEY,
    podcast_id TEXT REFERENCES podcasts(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    episode_number INTEGER,
    published_at TIMESTAMP,
    audio_url TEXT NOT NULL,
    transcript_url TEXT,
    duration_seconds INTEGER,
    positive_rating INTEGER DEFAULT 0,  -- Count of positive ratings
    negative_rating INTEGER DEFAULT 0,  -- Count of negative ratings
    total_rating INTEGER DEFAULT 0,     -- Total number of ratings
    embedding vector(768)               -- Vector embedding for similarity search
);

-- Enhanced user podcast listening history with interactions
CREATE TABLE user_podcast_history (
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    podcast_id TEXT REFERENCES podcasts(id) ON DELETE CASCADE,
    listened_at TIMESTAMP DEFAULT NOW(),
    hidden BOOLEAN DEFAULT false,
    
    -- Listening data
    listen_duration_seconds INTEGER DEFAULT 0,
    stop_position_seconds INTEGER DEFAULT 0,
    completed BOOLEAN DEFAULT false,
    
    -- Interaction counts
    play_count INTEGER DEFAULT 0,
    reaction INTEGER DEFAULT 0,
    share_count INTEGER DEFAULT 0,
    download_count INTEGER DEFAULT 0,
    add_to_playlist INTEGER DEFAULT 0,
    rating INTEGER DEFAULT 0,
    
    -- Additional metadata
    device_type TEXT,
    app_version TEXT,
    
    PRIMARY KEY (user_id, podcast_id, listened_at)
);

-- User podcast playlists
CREATE TABLE user_podcast_playlists (
    playlist_id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_public BOOLEAN DEFAULT false
);

-- Podcast playlist items
CREATE TABLE podcast_playlist_items (
    playlist_id TEXT REFERENCES user_podcast_playlists(playlist_id) ON DELETE CASCADE,
    podcast_id TEXT REFERENCES podcasts(id) ON DELETE SET NULL,
    episode_id TEXT REFERENCES podcast_episodes(episode_id) ON DELETE SET NULL,
    added_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (playlist_id, podcast_id)
);

CREATE TABLE user_favorite_podcasts (
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    podcast_id TEXT REFERENCES podcasts(id) ON DELETE CASCADE,
    added_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, podcast_id)
);

-- User liked podcasts (for tracking positive reactions)
CREATE TABLE user_liked_podcasts (
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    podcast_id TEXT REFERENCES podcasts(id) ON DELETE CASCADE,
    liked_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, podcast_id)
);

CREATE TABLE user_disliked_podcasts (
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    podcast_id TEXT REFERENCES podcasts(id) ON DELETE CASCADE,
    liked_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, podcast_id)
);

-- Create indexes for better query performance
CREATE INDEX idx_podcasts_cluster_id ON podcasts(cluster_id);
CREATE INDEX idx_podcasts_trending_time ON clusters(trending_time);
CREATE INDEX idx_podcasts_hot_time ON clusters(hot_time);
CREATE INDEX idx_podcasts_published_at ON podcasts(published_at);
CREATE INDEX idx_podcasts_created_at ON podcasts(created_at);
CREATE INDEX idx_podcasts_category ON podcasts(category);
CREATE INDEX idx_podcasts_subcategory ON podcasts(subcategory);
CREATE INDEX idx_podcast_episodes_podcast_id ON podcast_episodes(podcast_id);
CREATE INDEX idx_user_podcast_history_user_id ON user_podcast_history(user_id);
CREATE INDEX idx_user_podcast_history_podcast_id ON user_podcast_history(podcast_id);
CREATE INDEX idx_user_podcast_history_listened_at ON user_podcast_history(listened_at);
CREATE INDEX idx_user_podcast_playlists_user_id ON user_podcast_playlists(user_id);
CREATE INDEX idx_podcast_playlist_items_playlist_id ON podcast_playlist_items(playlist_id);
CREATE INDEX idx_user_liked_podcasts_user_id ON user_liked_podcasts(user_id);
CREATE INDEX idx_podcasts_ratings ON podcasts(positive_rating, negative_rating, total_rating);
