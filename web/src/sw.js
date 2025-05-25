// Service worker for BriefCast
// This will cache the app shell and downloaded podcasts for offline use

const CACHE_NAME = 'briefcast-cache-v1';

// App Shell - critical files that make up the app's UI
const APP_SHELL = [
  '/',
  '/downloads',
  '/library',
  '/offline',
  '/manifest.json',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png',
];

// Files that should never be cached
const NEVER_CACHE = [
  /\.map$/,
  /api\//
];

// Files that should use network-first strategy
const NETWORK_FIRST = [
  /\/_next\/static\/chunks\//,
  /\/_next\/static\/[^\/]+\/pages\//,
  /\/_next\/static\/[^\/]+\/app\//
];

// Install event - cache app shell
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Caching app shell');
        return cache.addAll(APP_SHELL);
      })
      .then(() => self.skipWaiting())
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Check if a request matches any pattern in the array
function matchesPatterns(url, patterns) {
  return patterns.some(pattern => 
    pattern instanceof RegExp 
      ? pattern.test(url) 
      : url.includes(pattern)
  );
}

// Fetch event - serve from cache or network
self.addEventListener('fetch', (event) => {
  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  const url = event.request.url;

  // Skip never-cache items
  if (matchesPatterns(url, NEVER_CACHE)) {
    return;
  }

  // Special handling for JavaScript chunks - use network first strategy
  // This prevents "Failed to load chunk" errors when chunks are updated
  if (url.includes('/_next/static/chunks/') || 
      url.includes('/_next/static/webpack/') ||
      matchesPatterns(url, NETWORK_FIRST)) {
    
    event.respondWith(
      fetch(event.request)
        .then(response => {
          // Clone the response to cache it and return it
          const responseToCache = response.clone();
          caches.open(CACHE_NAME)
            .then((cache) => {
              cache.put(event.request, responseToCache);
            });
            
          return response;
        })
        .catch(() => {
          // If network fails, try the cache as a fallback
          return caches.match(event.request);
        })
    );
    return;
  }

  // For navigation requests, try network first, then cache
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .catch(() => {
          return caches.match(event.request)
            .then((response) => {
              if (response) {
                return response;
              }
              
              // If no match in cache, try serving the offline page
              if (event.request.url.includes('/downloads')) {
                // For downloads page, always try serving from cache
                return caches.match('/downloads');
              }
              
              return caches.match('/offline');
            });
        })
    );
    return;
  }

  // For podcast assets (app/files/ URLs or blob URLs), use cache-first strategy
  if (
    event.request.url.includes('files/') || 
    event.request.url.includes('audio') ||
    event.request.url.startsWith('blob:')
  ) {
    event.respondWith(
      caches.match(event.request)
        .then((cachedResponse) => {
          if (cachedResponse) {
            return cachedResponse;
          }
          
          return fetch(event.request)
            .then((response) => {
              // Don't cache non-successful responses
              if (!response || response.status !== 200) {
                return response;
              }
              
              // Clone the response to cache it and return it
              const responseToCache = response.clone();
              caches.open(CACHE_NAME)
                .then((cache) => {
                  cache.put(event.request, responseToCache);
                });
                
              return response;
            })
            .catch(() => {
              // If fetch fails, return nothing (will be handled by IndexedDB)
            });
        })
    );
    return;
  }

  // For all other requests, use cache-first strategy 
  // as it's more reliable for offline support
  event.respondWith(
    caches.match(event.request)
      .then((cachedResponse) => {
        if (cachedResponse) {
          return cachedResponse;
        }

        // Not in cache, try network
        return fetch(event.request)
          .then(response => {
            // Don't cache non-successful responses
            if (!response || response.status !== 200) {
              return response;
            }
            
            // Clone the response to cache it and return it
            const responseToCache = response.clone();
            caches.open(CACHE_NAME)
              .then((cache) => {
                cache.put(event.request, responseToCache);
              });
              
            return response;
          })
          .catch(error => {
            console.error('Fetch failed:', error);
            // Network request failed, return nothing
          });
      })
  );
});

// Listen for messages from clients
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'CACHE_PODCAST') {
    const { podcast } = event.data;
    
    if (!podcast || !podcast.id) return;
    
    // Create a list of URLs to cache for this podcast
    const podcastAssets = [
      podcast.cover_image_url,
      podcast.audio_url,
      podcast.transcript_url
    ].filter(Boolean); // Remove any undefined URLs
    
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Caching podcast assets for offline use');
        return cache.addAll(podcastAssets);
      })
      .catch(err => {
        console.error('Error caching podcast assets:', err);
      });
  }
}); 