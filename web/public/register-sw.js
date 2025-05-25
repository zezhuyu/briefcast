// This file will be loaded directly in the HTML to register the service worker as early as possible
if ('serviceWorker' in navigator) {
  // Keep track of registration to avoid duplicate registrations
  let swRegistration = null;
  
  const registerServiceWorker = async () => {
    try {
      console.log('Attempting to register service worker...');
      
      // Check if already registered to avoid duplicate registrations
      let existingReg;
      try {
        existingReg = await navigator.serviceWorker.getRegistration('/');
        if (existingReg) {
          console.log('Service worker already registered, using existing registration');
          return existingReg;
        }
      } catch (regError) {
        console.warn('Error checking existing service worker registration:', regError);
        // Continue with registration attempt anyway
      }
      
      // Not registered yet, register now
      try {
        const registration = await navigator.serviceWorker.register('/sw.js', {
          scope: '/',
          updateViaCache: 'none'
        });
        
        console.log('ServiceWorker registration successful with scope:', registration.scope);
        
        // Force service worker activation after successful registration
        if (registration.waiting) {
          // If there's a waiting service worker, activate it immediately
          registration.waiting.postMessage({ type: 'SKIP_WAITING' });
        }
        
        return registration;
      } catch (regError) {
        // Log specific registration errors
        console.error('ServiceWorker registration error details:', {
          message: regError.message,
          name: regError.name,
          fileName: regError.fileName,
          lineNumber: regError.lineNumber,
          stack: regError.stack
        });
        throw regError; // Re-throw for the outer catch
      }
    } catch (error) {
      console.error('ServiceWorker registration failed:', error);
      return null;
    }
  };
  
  const setupServiceWorker = async () => {
    try {
      // Get or register the service worker
      const registration = await registerServiceWorker();
      if (!registration) {
        console.warn('Failed to register service worker');
        return;
      }
      
      swRegistration = registration;
      
      // Add listeners to handle updates
      registration.addEventListener('updatefound', () => {
        // A new service worker is being installed
        const newWorker = registration.installing;
        console.log('New service worker installing:', newWorker?.state);
        
        if (newWorker) {
          newWorker.addEventListener('statechange', () => {
            console.log('Service worker state changed to:', newWorker.state);
            
            if (newWorker.state === 'activated') {
              // When activated, add to window.swActive flag
              window.swActive = true;
              console.log('Service worker activated and caching complete!');
              
              // Dispatch event for components to react to service worker activation
              window.dispatchEvent(new CustomEvent('swActivated'));
            }
          });
        }
      });
      
      // Check if there's already an active service worker
      if (registration.active) {
        window.swActive = true;
        console.log('Service worker already active');
        window.dispatchEvent(new CustomEvent('swActivated'));
        
        // Check for updates (but not too aggressively)
        setTimeout(() => {
          registration.update().catch(err => {
            console.warn('Error checking for service worker updates:', err);
          });
        }, 5000);
      }
      
      // Handle updates
      navigator.serviceWorker.addEventListener('controllerchange', function() {
        console.log('Service worker controller changed - reload may be needed');
        // You can add auto-reload logic here if desired
      });
      
      // Add message listener to handle messages from service worker
      navigator.serviceWorker.addEventListener('message', event => {
        console.log('Message from service worker:', event.data);
        
        if (event.data) {
          if (event.data.type === 'CACHING_COMPLETE') {
            console.log('Caching complete!');
            window.dispatchEvent(new CustomEvent('cachingComplete'));
          } else if (event.data.type === 'PODCAST_CACHED') {
            console.log('Podcast cached:', event.data.podcastId);
            window.dispatchEvent(new CustomEvent('podcastCached', {
              detail: { podcastId: event.data.podcastId }
            }));
          } else if (event.data.type === 'PODCAST_REMOVED') {
            console.log('Podcast removed from cache:', event.data.podcastId);
            window.dispatchEvent(new CustomEvent('podcastRemoved', {
              detail: { podcastId: event.data.podcastId }
            }));
          }
        }
      });
    } catch (error) {
      console.error('Error setting up service worker:', error);
    }
  };
  
  // Wait for load to register service worker
  window.addEventListener('load', () => {
    // Delay registration slightly to prioritize initial page render
    setTimeout(setupServiceWorker, 1000);
  });
}

// Add event listener for offline/online status
window.addEventListener('online', function() {
  document.body.classList.remove('offline');
  document.body.classList.add('online');
  console.log('App is online');
});

window.addEventListener('offline', function() {
  document.body.classList.remove('online');
  document.body.classList.add('offline');
  console.log('App is offline');
  
  // Notify user they're offline
  if (!document.getElementById('offline-notification')) {
    const notification = document.createElement('div');
    notification.id = 'offline-notification';
    notification.style.position = 'fixed';
    notification.style.top = '0';
    notification.style.left = '0';
    notification.style.right = '0';
    notification.style.padding = '8px';
    notification.style.background = '#f44336';
    notification.style.color = 'white';
    notification.style.textAlign = 'center';
    notification.style.zIndex = '9999';
    notification.textContent = 'You are offline. Some content may not be available.';
    document.body.appendChild(notification);
  }
}); 