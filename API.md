# Briefcast API Documentation

## Authentication

All authenticated endpoints require a Bearer token in the Authorization header. The token should be obtained from Clerk authentication service.

```http
Authorization: Bearer <your_clerk_token>
```

## Endpoints

### Authentication

#### Sign Up
```http
POST /sign-up
```

Creates a new user account with specified topic preferences.

**Request Body:**
```json
{
  "topics": {
    "subtopics": {
      "Technology": ["AI", "Programming"],
      "Science": ["Physics", "Biology"]
    }
  }
}
```

**Response:**
```json
{
  "message": "User signed up successfully"
}
```

### Podcasts

#### Get Podcast
```http
GET /podcast/{podcast_id}
```

Retrieves detailed information about a specific podcast.

**Response:**
```json
{
  "id": "string",
  "title": "string",
  "description": "string",
  "duration": "number",
  "audio_url": "string",
  "transcript_url": "string",
  "cover_image_url": "string",
  "country": "string",
  "category": "string",
  "subcategory": "string",
  "keywords": ["string"],
  "createAt": "timestamp",
  "totalRating": "number",
  "rating": "number",
  "favorite": "boolean",
  "positive": "number",
  "negative": "number"
}
```

#### Generate Daily News
```http
POST /generate
```

Generates a daily news podcast for the user.

**Request Body:**
```json
{
  "location": "string",
  "force": "boolean"
}
```

**Response:** Same as Get Podcast response

### History

#### Get Listening History
```http
GET /history
```

Retrieves the user's listening history.

**Response:**
```json
[
  {
    "id": "string",
    "listened_at": "timestamp",
    "stop_position_seconds": "number",
    "completed": "boolean",
    "hidden": "boolean",
    "title": "string",
    "category": "string",
    "subcategory": "string",
    "cover_image_url": "string",
    "duration_seconds": "number"
  }
]
```

### Recommendations

#### Get Recommendations
```http
GET /recommendations
```

Retrieves personalized podcast recommendations for the user.

**Response:**
```json
[
  {
    "id": "string",
    "title": "string",
    "description": "string",
    "duration": "number",
    "cover_image_url": "string",
    "country": "string",
    "category": "string",
    "subcategory": "string",
    "keywords": ["string"],
    "createAt": "timestamp",
    "totalRating": "number",
    "positive": "number",
    "negative": "number"
  }
]
```

#### Get Recommendations by Podcast
```http
GET /recommendations/{podcast_id}
```

Retrieves recommendations similar to a specific podcast.

**Response:** Same as Get Recommendations response

### Playlists

#### Get Playlists
```http
GET /playlists
```

Retrieves all playlists for the user.

**Response:**
```json
[
  {
    "id": "string",
    "name": "string",
    "description": "string",
    "created_at": "timestamp"
  }
]
```

#### Create Playlist
```http
POST /playlist
```

Creates a new playlist.

**Request Body:**
```json
{
  "name": "string",
  "description": "string"
}
```

**Response:**
```json
{
  "message": "Playlist created successfully",
  "id": "string"
}
```

#### Update Playlist
```http
PUT /playlist
```

Updates an existing playlist.

**Request Body:**
```json
{
  "id": "string",
  "name": "string",
  "description": "string"
}
```

**Response:**
```json
{
  "message": "Playlist updated successfully"
}
```

#### Delete Playlist
```http
DELETE /playlist
```

Deletes a playlist.

**Request Body:**
```json
{
  "id": "string"
}
```

**Response:**
```json
{
  "message": "Playlist deleted successfully"
}
```

#### Get Playlist Items
```http
GET /playlist/{playlist_id}
```

Retrieves all items in a playlist.

**Response:**
```json
[
  {
    "id": "string",
    "added_at": "timestamp",
    "title": "string",
    "category": "string",
    "subcategory": "string",
    "cover_image_url": "string"
  }
]
```

#### Add to Playlist
```http
POST /playlist/{playlist_id}
```

Adds a podcast to a playlist.

**Request Body:**
```json
{
  "podcast_id": "string"
}
```

**Response:**
```json
{
  "message": "Podcast added to playlist successfully"
}
```

#### Remove from Playlist
```http
DELETE /playlist/{playlist_id}
```

Removes a podcast from a playlist.

**Request Body:**
```json
{
  "podcast_id": "string"
}
```

**Response:**
```json
{
  "message": "Podcast removed from playlist successfully"
}
```

### User Interactions

#### Rate Podcast
```http
POST /rate
```

Rates a podcast (like/dislike).

**Request Body:**
```json
{
  "podcast_id": "string",
  "rating": "number" // 1 for like, -1 for dislike, 0 for neutral
}
```

**Response:**
```json
{
  "message": "Podcast rated successfully"
}
```

#### Update Playing Position
```http
POST /playing
```

Updates the current playing position of a podcast.

**Request Body:**
```json
{
  "podcast_id": "string",
  "position": "number"
}
```

**Response:**
```json
{
  "message": "Playing successfully"
}
```

#### Mark as Played
```http
POST /played
```

Marks a podcast as played and logs user activity.

**Request Body:**
```json
{
  "podcast_id": "string",
  "activity": {
    "listen_duration_seconds": "number",
    "stop_position_seconds": "number",
    "completed": "boolean",
    "share_count": "number",
    "download_count": "number",
    "add_to_playlist": "number",
    "rating": "number"
  }
}
```

**Response:**
```json
{
  "message": "Marked as played successfully"
}
```

### Search

#### Search Podcasts
```http
GET /search?q={query}
```

Searches for podcasts based on a query string.

**Response:**
```json
[
  {
    "id": "string",
    "title": "string",
    "description": "string",
    "duration": "number",
    "cover_image_url": "string",
    "country": "string",
    "category": "string",
    "subcategory": "string",
    "keywords": ["string"],
    "createAt": "timestamp",
    "totalRating": "number",
    "positive": "number",
    "negative": "number"
  }
]
```

### Trending

#### Get Trending
```http
GET /get_trending
```

Retrieves trending podcasts.

**Response:** Same as Search Podcasts response

#### Get Hot Trending
```http
GET /get_hot_trending
```

Retrieves hot trending podcasts based on user preferences.

**Response:** Same as Search Podcasts response

### Files

#### Get File
```http
GET /files/{file_type}/{file_name}
GET /files/{user_id}/{file_type}/{file_name}
```

Retrieves a file (audio, image, or transcript).

**Response:**
- Audio files: `audio/mpeg`
- Image files: `image/jpeg`
- Transcript files: `text/plain`

### Transitions

#### Create Transition
```http
POST /transition
```

Creates a transition audio between two podcasts.

**Request Body:**
```json
{
  "id1": "string",
  "id2": "string"
}
```

**Response:**
```json
{
  "cover_image_url": "string",
  "audio_url": "string",
  "transcript_url": "string",
  "secs": "number"
}
```

## Error Responses

All endpoints may return the following error responses:

### 401 Unauthorized
```json
{
  "error": "Token is missing"
}
```
or
```json
{
  "error": "Token has expired"
}
```
or
```json
{
  "error": "Invalid token"
}
```

### 404 Not Found
```json
{
  "error": "Podcast not found"
}
```

### 500 Internal Server Error
```json
{
  "error": "Error message"
}
``` 