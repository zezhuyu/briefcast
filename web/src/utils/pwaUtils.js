// This file contains utilities for PWA features and service worker registration

export function registerServiceWorker() {
  if (typeof window !== 'undefined' && 'serviceWorker' in navigator) {
    // Return the registration promise so it can be awaited
    return navigator.serviceWorker.register('/sw.js', { 
      scope: '/',
      updateViaCache: 'none' // Don't use cache for service worker updates
    })
      .then(function(registration) {
        console.log('Service Worker registered with scope:', registration.scope);
        
        // Add listeners to installation
        if (registration.installing) {
          const serviceWorker = registration.installing;
          serviceWorker.addEventListener('statechange', function() {
            console.log('Service Worker state changed:', serviceWorker.state);
          });
        }
        
        // Force update if needed
        if (registration.active) {
          registration.update();
        }
        
        return registration;
      })
      .catch(function(error) {
        console.error('Service Worker registration failed:', error);
        throw error;
      });
  }
  return Promise.resolve(null);
}

// Function to check if the app is being used in standalone mode (installed PWA)
export function isInStandaloneMode() {
  if (typeof window !== 'undefined') {
    return window.matchMedia('(display-mode: standalone)').matches || 
           (window.navigator && window.navigator.standalone);
  }
  return false;
}

// Improved function to check if service worker is active
export function checkServiceWorkerStatus() {
  if (typeof window !== 'undefined' && 'serviceWorker' in navigator) {
    return new Promise((resolve) => {
      // First try to get the registration
      navigator.serviceWorker.getRegistration('/')
        .then(registration => {
          if (registration && (registration.active || registration.installing || registration.waiting)) {
            resolve({
              active: true,
              scope: registration.scope,
              state: registration.active ? 'active' : 
                     registration.installing ? 'installing' : 'waiting'
            });
          } else {
            // No registration found, try one more time to register
            registerServiceWorker()
              .then(() => {
                resolve({
                  active: true, 
                  state: 'just-registered',
                  scope: '/'
                });
              })
              .catch(() => {
                resolve({ active: false });
              });
          }
        })
        .catch(() => {
          resolve({ active: false });
        });
    });
  }
  return Promise.resolve({ active: false });
}

/**
 * Tests if a URL is available when offline
 * @param {string} url - The URL to test
 * @returns {Promise<{cacheAvailable: boolean, response?: Response}>}
 */
export const testOfflineCapability = async (url) => {
  if (!('caches' in window)) {
    return { cacheAvailable: false };
  }

  try {
    // Try to find the resource in any cache
    const cacheResponse = await caches.match(url);
    if (cacheResponse) {
      return { cacheAvailable: true, response: cacheResponse };
    }

    // If not found in cache, check if specific cache
    const cacheNames = await caches.keys();
    for (const cacheName of cacheNames) {
      const cache = await caches.open(cacheName);
      const cachedResponse = await cache.match(url);
      if (cachedResponse) {
        return { cacheAvailable: true, response: cachedResponse };
      }
    }

    return { cacheAvailable: false };
  } catch (error) {
    console.error('Error testing offline capability:', error);
    return { cacheAvailable: false, error };
  }
};

/**
 * Cache a podcast via the service worker
 * @param {Object} podcast - The podcast to cache
 * @returns {Promise<boolean>}
 */
export const cachePodcastViaServiceWorker = async (podcast) => {
  if (!('serviceWorker' in navigator) || !navigator.serviceWorker.controller) {
    throw new Error('Service worker not available or not controlling the page');
  }

  // Create a message to send to the service worker
  const message = {
    type: 'CACHE_PODCAST',
    podcast: {
      id: podcast.id,
      title: podcast.title,
      audioUrl: podcast.audio_url,
      imageUrl: podcast.cover_image_url,
      transcriptUrl: podcast.transcript_url,
      slug: podcast.slug
    }
  };

  // Create a message channel for the response
  const messageChannel = new MessageChannel();
  
  // Return a promise that resolves when the SW responds
  return new Promise((resolve, reject) => {
    messageChannel.port1.onmessage = (event) => {
      if (event.data && event.data.error) {
        reject(new Error(event.data.error));
      } else {
        resolve(true);
      }
    };

    // Send the message to the service worker
    navigator.serviceWorker.controller.postMessage(message, [messageChannel.port2]);
    
    // Timeout after 10 seconds
    setTimeout(() => {
      reject(new Error('Timeout waiting for service worker response'));
    }, 10000);
  });
}; 