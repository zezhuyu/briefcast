/**
 * This script helps handle and recover from chunk loading errors
 * It's included in the public folder to be served statically without any
 * build process, ensuring it's available even when chunk loading fails.
 */

// Listen for errors globally 
window.addEventListener('error', function(event) {
  // Check if this is a chunk loading error
  if (event.message && (
    event.message.includes('Failed to load chunk') || 
    event.message.includes('Loading chunk') ||
    event.message.includes('Loading CSS chunk') ||
    (event.filename && event.filename.includes('static/chunks'))
  )) {
    console.error('Chunk loading error detected:', event);
    
    // Prevent the default error handling
    event.preventDefault();
    
    // Clear browser caches if possible
    if ('caches' in window) {
      console.log('Clearing caches...');
      caches.keys().then(cacheNames => {
        const deletionPromises = cacheNames.map(cacheName => {
          console.log('Deleting cache:', cacheName);
          return caches.delete(cacheName);
        });
        
        Promise.all(deletionPromises).then(() => {
          console.log('All caches cleared. Reloading page...');
          // Reload the page after a short delay
          setTimeout(() => {
            window.location.reload();
          }, 500);
        });
      });
    } else {
      // If Cache API not available, just reload
      console.log('Cache API not available. Reloading page...');
      window.location.reload();
    }
    
    // Show a custom error message
    const errorMessage = document.createElement('div');
    errorMessage.style.position = 'fixed';
    errorMessage.style.top = '0';
    errorMessage.style.left = '0';
    errorMessage.style.right = '0';
    errorMessage.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
    errorMessage.style.color = 'white';
    errorMessage.style.padding = '20px';
    errorMessage.style.textAlign = 'center';
    errorMessage.style.zIndex = '9999';
    errorMessage.innerHTML = `
      <p>Loading error detected. Attempting to fix...</p>
      <p style="font-size: 12px; opacity: 0.7; margin-top: 10px;">
        If this persists, try visiting /clear-cache.html
      </p>
    `;
    document.body.appendChild(errorMessage);
    
    return true; // Prevent default error handling
  }
  
  // Let other errors be handled normally
  return false;
});

// Add special handling for unhandled promise rejections
window.addEventListener('unhandledrejection', function(event) {
  const error = event.reason;
  if (error && error.message && (
    error.message.includes('Failed to load chunk') ||
    error.message.includes('Loading chunk') ||
    error.message.includes('dynamic import') ||
    error.message.includes('loadable component')
  )) {
    console.error('Unhandled chunk loading rejection:', error);
    
    // Prevent the default rejection handling
    event.preventDefault();
    
    // Clear cache and reload
    if ('caches' in window) {
      caches.keys().then(cacheNames => {
        Promise.all(cacheNames.map(cacheName => caches.delete(cacheName)))
          .then(() => {
            console.log('Caches cleared after unhandled rejection');
            window.location.reload();
          });
      });
    } else {
      window.location.reload();
    }
    
    return true;
  }
  
  return false;
});

console.log('Chunk error recovery script loaded'); 