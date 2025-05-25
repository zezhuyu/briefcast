// Service worker for BriefCast
// This will cache the app shell and downloaded podcasts for offline use

const CACHE_NAME = 'briefcast-cache-v1';
const PODCAST_ASSETS_CACHE = 'briefcast-podcast-assets-v1';
const PODCAST_METADATA_CACHE = 'briefcast-podcast-metadata-v1';

// App Shell - critical files that make up the app's UI
const APP_SHELL = [
  '/',
  '/register-sw.js'
];

// Don't specify exact paths for Next.js chunks as they change with each build
// Instead, we'll dynamically cache chunks as they're requested

// Files that should never be cached
const NEVER_CACHE = [
  /\.map$/,
  /api\//,
  /clerk\.com/
];

// Files that should use network-first strategy
const NETWORK_FIRST = [
  /\/_next\/static\/chunks\//,
  /\/_next\/static\/[^\/]+\/pages\//,
  /\/_next\/static\/[^\/]+\/app\//
];

// Utility functions
const matchesPatterns = (url, patterns) => {
  return patterns.some(pattern => {
    if (pattern instanceof RegExp) {
      return pattern.test(url);
    }
    return url.includes(pattern);
  });
};

// Utility to safely cache a request/response pair
const safeCache = async (cache, request, response) => {
  try {
    // Skip if request or response is invalid
    if (!request || !response) {
      return false;
    }
    
    // Skip non-HTTP URLs
    const url = request.url || request;
    if (typeof url === 'string' && 
        (url.startsWith('chrome-extension:') || 
        url.startsWith('data:') || 
        url.startsWith('blob:') ||
        !url.startsWith('http'))) {
      console.log('[Service Worker] Skipping caching for unsupported URL:', url);
      return false;
    }
    
    // Check if this is a proper Request object, create one if not
    const req = request instanceof Request ? request : new Request(request);
    
    // Skip if not GET
    if (req.method !== 'GET') {
      return false;
    }
    
    await cache.put(req, response);
    return true;
  } catch (error) {
    console.error('[Service Worker] Safe cache error:', error, request.url || request);
    return false;
  }
};

// Install event - cache app shell
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[Service Worker] Caching app shell');
        
        // Use individual fetch operations instead of addAll to be more resilient
        return Promise.allSettled(
          APP_SHELL.map(url => 
            fetch(url, { cache: 'no-cache' })
              .then(response => {
                if (response.ok) {
                  console.log(`[Service Worker] Successfully cached: ${url}`);
                  return cache.put(url, response);
                }
                console.log(`[Service Worker] Failed to cache: ${url} - ${response.status}`);
              })
              .catch(err => {
                console.log(`[Service Worker] Failed to fetch: ${url}`, err);
                // Continue with installation even if individual resources fail
                return Promise.resolve();
              })
          )
        );
      })
      .then(results => {
        const successes = results.filter(r => r.status === 'fulfilled').length;
        console.log(`[Service Worker] App shell caching complete: ${successes}/${APP_SHELL.length} files cached`);
        return self.skipWaiting();
      })
      .catch(error => {
        console.error('[Service Worker] Installation failed:', error);
        // Still skip waiting even if caching fails to avoid stuck service workers
        return self.skipWaiting();
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          // Only delete cache if it's a briefcast cache but not one of our current caches
          if (cacheName.startsWith('briefcast-') && 
              cacheName !== CACHE_NAME && 
              cacheName !== PODCAST_ASSETS_CACHE &&
              cacheName !== PODCAST_METADATA_CACHE) {
            console.log('[Service Worker] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
          return Promise.resolve();
        })
      );
    })
    .then(() => {
      console.log('[Service Worker] Claiming clients');
      return self.clients.claim();
    })
    .catch(error => {
      console.error('[Service Worker] Activation error:', error);
      return self.clients.claim(); // Still claim clients even if there's an error
    })
  );
});

// Fetch event - handle all network requests
self.addEventListener('fetch', (event) => {
  try {
    const url = event.request.url;
    
    // Skip URLs with unsupported schemes (chrome-extension, etc.)
    if (url.startsWith('chrome-extension:') || 
        url.startsWith('data:') || 
        url.startsWith('blob:') ||
        !url.startsWith('http')) {
      return;
    }
    
    // Skip non-GET requests as they can't be stored in the cache
    if (event.request.method !== 'GET') {
      return;
    }

    // Skip authentication-related requests entirely
    if (url.includes('/auth') || 
        url.includes('clerk.com') || 
        url.includes('/api/') || 
        url.includes('/generate') ||
        url.includes('/sign-')) {
      return; // Let the browser handle auth requests directly
    }

    // Skip never-cache items
    if (matchesPatterns(url, NEVER_CACHE)) {
      return;
    }

    // Special handling for podcast assets (audio, images, transcripts)
    if ((url.includes('/files/') || url.includes('.mp3') || url.includes('.wav')) && 
         event.request.method === 'GET') {
      event.respondWith(
        caches.match(event.request)
          .then(cachedResponse => {
            if (cachedResponse) {
              return cachedResponse;
            }
            
            // Clone the request to ensure credentials are preserved
            const fetchRequest = event.request.clone();
            
            return fetch(fetchRequest, {
              // credentials: 'include', // Important for auth cookies
              mode: 'cors'
            })
              .then(response => {
                if (!response || response.status !== 200) {
                  return response;
                }
                
                const responseToCache = response.clone();
                caches.open(PODCAST_ASSETS_CACHE)
                  .then(cache => {
                    // Only cache if it's not an authenticated response
                    if (!responseToCache.headers.get('set-cookie')) {
                      safeCache(cache, event.request, responseToCache);
                    }
                  })
                  .catch(error => {
                    console.error('[Service Worker] Error caching podcast asset:', error);
                  });
                  
                return response;
              })
              .catch(error => {
                console.error('[Service Worker] Fetch error:', error);
                return new Response('Network error', { status: 408, headers: { 'Content-Type': 'text/plain' } });
              });
          })
      );
      return;
    }

    // Special handling for JavaScript chunks - use network first strategy
    if ((url.includes('/_next/static/') || 
        matchesPatterns(url, NETWORK_FIRST)) && 
        event.request.method === 'GET') {
      
      event.respondWith(
        fetch(event.request.clone(), {
          credentials: 'include' // Include credentials on all requests
        })
          .then(response => {
            // Only cache successful responses
            if (!response || !response.ok) {
              return response;
            }
            
            // Clone the response to cache it and return it
            const responseToCache = response.clone();
            
            // Don't cache responses with cookies or auth headers
            if (!responseToCache.headers.get('set-cookie')) {
              caches.open(CACHE_NAME)
                .then((cache) => {
                  safeCache(cache, event.request, responseToCache);
                });
            }
              
            return response;
          })
          .catch(() => {
            // If network fails, try the cache as a fallback
            return caches.match(event.request)
              .then(cachedResponse => {
                if (cachedResponse) {
                  return cachedResponse;
                }
                
                // If no cached response, provide a minimal error response
                if (url.includes('.js')) {
                  // For JS files, return empty JS to prevent complete UI failure
                  return new Response('console.log("Failed to load script");', 
                    { status: 200, headers: { 'Content-Type': 'application/javascript' } });
                }
                
                if (url.includes('.css')) {
                  // For CSS files, return empty CSS
                  return new Response('/* Failed to load stylesheet */', 
                    { status: 200, headers: { 'Content-Type': 'text/css' } });
                }
                
                // For other resources, return a network error response
                return new Response('Network error', 
                  { status: 408, headers: { 'Content-Type': 'text/plain' } });
              });
          })
      );
      return;
    }

    // For navigation requests, try network first, then cache
    if (event.request.mode === 'navigate' && event.request.method === 'GET') {
      event.respondWith(
        fetch(event.request)
          .then(response => {
            // Cache the latest version of the page
            if (response.ok) {
              const responseToCache = response.clone();
              caches.open(CACHE_NAME)
                .then(cache => {
                  safeCache(cache, event.request, responseToCache);
                })
                .catch(error => {
                  console.error('[Service Worker] Error caching page:', error);
                });
            }
            return response;
          })
          .catch(() => {
            return caches.match(event.request)
              .then((response) => {
                if (response) {
                  return response;
                }
                
                // If no match in cache, generate a simple offline page
                console.log('[Service Worker] No cached version of', event.request.url, '- serving offline page');
                
                const offlineHtml = `
                  <!DOCTYPE html>
                  <html lang="en">
                  <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>BriefCast - Offline</title>
                    <style>
                      body {
                        font-family: system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
                        background: linear-gradient(145deg, #4F46E5, #6422FE);
                        color: white;
                        height: 100vh;
                        margin: 0;
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        justify-content: center;
                        text-align: center;
                        padding: 1rem;
                      }
                      .container {
                        background-color: rgba(255, 255, 255, 0.1);
                        padding: 2rem;
                        border-radius: 0.5rem;
                        backdrop-filter: blur(10px);
                        max-width: 500px;
                      }
                      h1 {
                        margin-top: 0;
                      }
                      .button {
                        background-color: #F59E0B;
                        color: white;
                        padding: 0.5rem 1rem;
                        border-radius: 0.25rem;
                        text-decoration: none;
                        display: inline-block;
                        margin-top: 1rem;
                      }
                    </style>
                  </head>
                  <body>
                    <div class="container">
                      <h1>You're Offline</h1>
                      <p>BriefCast is currently offline. You can still access your downloaded podcasts.</p>
                      <a href="/" class="button">Try Again</a>
                    </div>
                    <script>
                      // Check for online status changes
                      window.addEventListener('online', function() {
                        window.location.reload();
                      });
                    </script>
                  </body>
                  </html>
                `;
                
                return new Response(offlineHtml, {
                  status: 200,
                  headers: { 'Content-Type': 'text/html' }
                });
              });
          })
      );
      return;
    }

    // Default cache strategy (Cache first, network as fallback)
    event.respondWith(
      caches.match(event.request)
        .then((response) => {
          if (response) {
            return response;
          }
          
          // Only fetch for GET requests
          if (event.request.method !== 'GET') {
            return fetch(event.request);
          }
          
          return fetch(event.request)
            .then(response => {
              // Don't cache non-successful responses
              if (!response || response.status !== 200) {
                return response;
              }
              
              // Cache successful responses
              const responseToCache = response.clone();
              caches.open(CACHE_NAME)
                .then(cache => {
                  safeCache(cache, event.request, responseToCache);
                })
                .catch(error => {
                  console.error('[Service Worker] Error in default caching:', error);
                });
                
              return response;
            })
            .catch(error => {
              console.error('[Service Worker] Fetch error in default handler:', error);
              return new Response('Network error', { status: 408, headers: { 'Content-Type': 'text/plain' } });
            });
        })
    );
  } catch (error) {
    console.error('[Service Worker] Uncaught error in fetch handler:', error);
    // If an error occurs in our handling code, try to continue without breaking
    return;
  }
});

// Listen for messages from the client
self.addEventListener('message', (event) => {
  try {
    // Log the message for debugging
    console.log('[Service Worker] Message received:', event.data);
    
    if (event.data && event.data.type === 'SKIP_WAITING') {
      self.skipWaiting();
    }
    
    // Handle message to cache podcast data
    if (event.data && event.data.type === 'CACHE_PODCAST' && event.data.podcast) {
      const podcast = event.data.podcast;
      
      // Cache all podcast assets
      const cachePodcastAssets = async () => {
        try {
          const assets = [
            podcast.audio_url,
            podcast.cover_image_url,
            podcast.transcript_url
          ].filter(url => url);
          
          console.log('[Service Worker] Caching podcast assets:', assets);
          
          const cache = await caches.open(PODCAST_ASSETS_CACHE);
          
          // Cache each asset
          const cachePromises = assets.map(async (url) => {
            try {
              if (!url) return;
              
              // Skip URLs with unsupported schemes
              if (url.startsWith('chrome-extension:') || 
                  url.startsWith('data:') || 
                  !url.startsWith('http')) {
                console.log('[Service Worker] Skipping unsupported URL scheme:', url);
                return;
              }
              
              // Create a GET request for caching
              const request = new Request(url, {
                method: 'GET',
                credentials: 'same-origin',
                mode: 'no-cors' // Try with no-cors to avoid CORS issues
              });
              
              const response = await fetch(request);
              
              if (response) {
                await safeCache(cache, request, response);
                console.log('[Service Worker] Cached asset successfully:', url);
              }
            } catch (err) {
              console.error('[Service Worker] Failed to cache asset:', url, err);
            }
          });
          
          await Promise.allSettled(cachePromises);
          
          // Cache podcast metadata
          try {
            const metadataCache = await caches.open(PODCAST_METADATA_CACHE);
            const metadataResponse = new Response(JSON.stringify(podcast));
            const metadataKey = `podcast-${podcast.id}`;
            
            // Create a special request for the metadata
            const metadataRequest = new Request(`https://briefcast.app/podcast-metadata/${podcast.id}`, {
              method: 'GET'
            });
            
            await safeCache(metadataCache, metadataRequest, metadataResponse);
            console.log('[Service Worker] Podcast metadata cached successfully:', podcast.id);
          } catch (err) {
            console.error('[Service Worker] Failed to cache podcast metadata:', err);
          }
          
          // Notify all clients that caching is complete
          try {
            const clients = await self.clients.matchAll();
            for (const client of clients) {
              client.postMessage({
                type: 'PODCAST_CACHED',
                podcastId: podcast.id
              });
            }
            console.log('[Service Worker] Notified clients about cached podcast');
          } catch (err) {
            console.error('[Service Worker] Error notifying clients:', err);
          }
        } catch (err) {
          console.error('[Service Worker] Failed to cache podcast:', err);
        }
      };
      
      // Start the caching process
      cachePodcastAssets();
    }
    
    // Handle message to remove cached podcast
    if (event.data && event.data.type === 'REMOVE_CACHED_PODCAST') {
      const { podcastId, assetUrls = [] } = event.data;
      
      const removeCachedPodcast = async () => {
        try {
          // Remove podcast metadata from cache
          const metadataCache = await caches.open(PODCAST_METADATA_CACHE);
          await metadataCache.delete(`podcast-${podcastId}`);
          console.log('[Service Worker] Removed podcast metadata from cache:', podcastId);
          
          // Remove all associated assets
          if (assetUrls.length > 0) {
            const assetsCache = await caches.open(PODCAST_ASSETS_CACHE);
            
            const deletePromises = assetUrls.map(async (url) => {
              if (url) {
                // Skip URLs with unsupported schemes
                if (url.startsWith('chrome-extension:') || 
                    url.startsWith('data:') || 
                    !url.startsWith('http')) {
                  console.log('[Service Worker] Skipping unsupported URL scheme for deletion:', url);
                  return;
                }
                
                try {
                  const deleted = await assetsCache.delete(url);
                  console.log('[Service Worker] Removed asset from cache:', url, deleted ? 'success' : 'not found');
                } catch (err) {
                  console.error('[Service Worker] Error removing asset from cache:', url, err);
                }
              }
            });
            
            await Promise.allSettled(deletePromises);
          }
          
          // Notify clients that removal is complete
          const clients = await self.clients.matchAll();
          for (const client of clients) {
            client.postMessage({
              type: 'PODCAST_REMOVED',
              podcastId
            });
          }
          console.log('[Service Worker] Successfully removed podcast from cache:', podcastId);
        } catch (err) {
          console.error('[Service Worker] Failed to remove podcast from cache:', err);
        }
      };
      
      removeCachedPodcast();
    }
  } catch (error) {
    console.error('[Service Worker] Error handling message:', error);
  }
});
