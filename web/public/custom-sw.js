// This is a custom service worker that augments the auto-generated Workbox service worker
// Place specific caching strategies and custom offline behaviors here

// This will be injected into the generated sw.js file

// Custom cache names for different types of assets
const CACHE_NAMES = {
  static: 'static-cache-v1',
  pages: 'pages-cache-v1',
  images: 'images-cache-v1',
  audio: 'audio-cache-v1',
  podcast: 'podcast-metadata-v1'
};

// List of critical resources that must be cached for offline functionality
// These will be precached during service worker installation
const CRITICAL_RESOURCES = [
  '/',
  '/offline',
  '/library',
  '/downloads',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png',
  '/manifest.json'
];

// Event listener for the install event
self.addEventListener('install', (event) => {
  console.log('[Service Worker] Installing...');
  
  // Cache critical resources during installation
  event.waitUntil(
    caches.open(CACHE_NAMES.static)
      .then(cache => {
        console.log('[Service Worker] Caching critical resources');
        return cache.addAll(CRITICAL_RESOURCES);
      })
      .then(() => {
        console.log('[Service Worker] Critical resources cached');
        // Skip waiting to activate the service worker immediately
        return self.skipWaiting();
      })
  );
});

// Event listener for the activate event
self.addEventListener('activate', (event) => {
  console.log('[Service Worker] Activating...');
  
  // Clean up old caches
  event.waitUntil(
    caches.keys()
      .then(cacheNames => {
        return Promise.all(
          cacheNames.map(cacheName => {
            // If the cache name doesn't match any of our current cache names, delete it
            if (!Object.values(CACHE_NAMES).includes(cacheName)) {
              console.log('[Service Worker] Deleting old cache:', cacheName);
              return caches.delete(cacheName);
            }
            return Promise.resolve();
          })
        );
      })
      .then(() => {
        console.log('[Service Worker] Claiming clients');
        // Claim clients to ensure the service worker takes control immediately
        return self.clients.claim();
      })
  );
});

// Helper function to cache a response for a request
const cacheResponse = async (request, response, cacheName) => {
  const cache = await caches.open(cacheName);
  console.log(`[Service Worker] Caching new resource: ${request.url}`);
  cache.put(request, response.clone());
  return response;
};

// Handle a special message to cache podcast data
self.addEventListener('message', async (event) => {
  console.log('[Service Worker] Message received:', event.data);
  
  if (event.data && event.data.type === 'CACHE_PODCAST') {
    const podcastData = event.data.podcast;
    
    if (!podcastData || !podcastData.id) {
      console.error('[Service Worker] Invalid podcast data received');
      return;
    }
    
    try {
      // Open podcast metadata cache
      const metadataCache = await caches.open(CACHE_NAMES.podcast);
      
      // Store podcast metadata
      const metadataRequest = new Request(`podcast-metadata-${podcastData.id}`);
      const metadataResponse = new Response(JSON.stringify(podcastData));
      await metadataCache.put(metadataRequest, metadataResponse);
      
      // Cache each asset URL if provided
      const urls = [
        podcastData.audio_url,
        podcastData.cover_image_url,
        podcastData.transcript_url
      ].filter(url => url);
      
      // Cache each asset
      const cachePromises = urls.map(async (url) => {
        try {
          const response = await fetch(url);
          if (!response.ok) {
            throw new Error(`Failed to fetch: ${url}`);
          }
          
          const cache = await caches.open(
            url.includes('.mp3') || url.includes('audio') ? 
              CACHE_NAMES.audio : CACHE_NAMES.images
          );
          
          await cache.put(url, response);
          console.log(`[Service Worker] Cached asset: ${url}`);
        } catch (error) {
          console.error(`[Service Worker] Failed to cache: ${url}`, error);
        }
      });
      
      await Promise.all(cachePromises);
      
      // Notify clients that caching is complete
      const clients = await self.clients.matchAll();
      clients.forEach(client => {
        client.postMessage({
          type: 'CACHING_COMPLETE',
          podcastId: podcastData.id
        });
      });
      
    } catch (error) {
      console.error('[Service Worker] Error caching podcast:', error);
    }
  }
}); 