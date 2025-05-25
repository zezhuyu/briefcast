-- Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Users table with core user information and category preferences
CREATE TABLE users (
    id TEXT PRIMARY KEY,  -- Clerk ID
    user_name TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP DEFAULT NOW(),
    last_daily_update TIMESTAMP DEFAULT NOW(),
    last_daily_vector_update TIMESTAMP DEFAULT NOW(),
    daily_listen_count INTEGER DEFAULT 0,
    batch_count INTEGER DEFAULT 0,
    daily_total_weight REAL DEFAULT 0.0,
    batch_total_weight REAL DEFAULT 0.0,
    prev_day_vector vector(768),  -- For daily recommendations
    realtime_vector vector(768),  -- For real-time updates
    batched_vector vector(768),   -- For batch preference updates
    daily_vector vector(768)      -- Stabilized user preference vector
);

-- User preferences (other types like moods, tempo, etc.)
CREATE TABLE user_preferences (
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    category TEXT NOT NULL,  -- e.g., 'mood', 'tempo'
    level INTEGER CHECK (level BETWEEN 1 AND 5) DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, category)
);

-- User category preferences
CREATE TABLE user_category_preferences (
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    category TEXT NOT NULL,  -- Must match category in `user_preferences`
    subcategory TEXT NOT NULL,  -- e.g., 'AI', 'Blockchain', 'Football'
    level INTEGER CHECK (level BETWEEN 1 AND 5) DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, category, subcategory),
    FOREIGN KEY (user_id, category) REFERENCES user_preferences(user_id, category) ON DELETE CASCADE
);

-- Search history
CREATE TABLE search_history (
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    search_query TEXT NOT NULL,
    searched_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, searched_at)
);

-- Create indexes for better query performance
CREATE INDEX idx_search_history_user_id ON search_history(user_id);
CREATE INDEX idx_user_preferences_user_id ON user_preferences(user_id);
CREATE INDEX idx_user_category_preferences_user_id ON user_category_preferences(user_id);
CREATE INDEX idx_user_category_preferences_category ON user_category_preferences(category);

-- Create vector indexes for similarity search
CREATE INDEX idx_prev_day_vector ON users USING ivfflat (prev_day_vector vector_cosine_ops);
CREATE INDEX idx_realtime_vector ON users USING ivfflat (realtime_vector vector_cosine_ops);
CREATE INDEX idx_batched_vector ON users USING ivfflat (batched_vector vector_cosine_ops);
CREATE INDEX idx_daily_vector ON users USING ivfflat (daily_vector vector_cosine_ops);