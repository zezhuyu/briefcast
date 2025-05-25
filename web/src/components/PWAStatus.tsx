"use client";
import { useState, useEffect } from 'react';
import { checkServiceWorkerStatus, isInStandaloneMode, registerServiceWorker, testOfflineCapability } from '@/utils/pwaUtils';

export default function PWAStatus() {
  const [status, setStatus] = useState<{
    active: boolean;
    scope?: string;
    state?: string;
    isStandalone: boolean;
    lastChecked: number;
    cacheStatus?: {
      tested: boolean;
      homeCached: boolean;
      offlineCached: boolean;
      podcastsCached: number;
    };
  }>({
    active: false,
    isStandalone: false,
    lastChecked: Date.now(),
    cacheStatus: {
      tested: false,
      homeCached: false,
      offlineCached: false,
      podcastsCached: 0
    }
  });

  const [showDetails, setShowDetails] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [isOnline, setIsOnline] = useState(true);

  // Check if device is online
  useEffect(() => {
    const updateOnlineStatus = () => {
      setIsOnline(navigator.onLine);
    };
    
    window.addEventListener('online', updateOnlineStatus);
    window.addEventListener('offline', updateOnlineStatus);
    
    updateOnlineStatus();
    
    return () => {
      window.removeEventListener('online', updateOnlineStatus);
      window.removeEventListener('offline', updateOnlineStatus);
    };
  }, []);

  // Check for service worker registration and cached podcasts
  useEffect(() => {
    const checkStatus = async () => {
      try {
        // Check service worker status
        const swStatus = await checkServiceWorkerStatus();
        
        // Check cache status
        const cacheStatus = {
          tested: true,
          homeCached: false,
          offlineCached: false,
          podcastsCached: 0
        };
        
        // Test if home page is cached
        if (swStatus.active) {
          try {
            const homeTest = await testOfflineCapability('/');
            cacheStatus.homeCached = homeTest.cacheAvailable;
            
            const offlineTest = await testOfflineCapability('/offline');
            cacheStatus.offlineCached = offlineTest.cacheAvailable;
            
            // Check for cached podcasts in IndexedDB
            if (window.indexedDB) {
              const db = await new Promise<IDBDatabase>((resolve, reject) => {
                const request = window.indexedDB.open('podcastDB', 1);
                request.onerror = () => reject(request.error);
                request.onsuccess = () => resolve(request.result);
              });
              
              const podcasts = await new Promise<any[]>((resolve) => {
                const transaction = db.transaction(['podcasts'], 'readonly');
                const store = transaction.objectStore('podcasts');
                const request = store.getAll();
                
                request.onsuccess = () => {
                  resolve(request.result?.filter(p => p.savedOffline) || []);
                };
                
                request.onerror = () => {
                  resolve([]);
                };
              });
              
              cacheStatus.podcastsCached = podcasts.length;
            }
          } catch (error) {
            console.warn('Error testing cache status:', error);
          }
        }
        
        // Update status
        setStatus({
          ...swStatus,
          isStandalone: isInStandaloneMode(),
          lastChecked: Date.now(),
          cacheStatus
        });
        
      } catch (error) {
        console.error('Error checking service worker status:', error);
      }
    };

    // Check immediately 
    checkStatus();
    
    // Then check periodically
    const interval = setInterval(checkStatus, 30000); // Check every 30 seconds
    
    // Also listen for podcast saved event
    const handlePodcastSaved = () => {
      checkStatus();
    };
    
    window.addEventListener('podcastSavedOffline', handlePodcastSaved);
    
    return () => {
      clearInterval(interval);
      window.removeEventListener('podcastSavedOffline', handlePodcastSaved);
    };
  }, []);

  // Try to manually register service worker
  const handleRegister = () => {
    registerServiceWorker();
    setTimeout(async () => {
      const swStatus = await checkServiceWorkerStatus();
      setStatus(prev => ({
        ...prev,
        ...swStatus,
        isStandalone: isInStandaloneMode(),
        lastChecked: Date.now()
      }));
    }, 1000);
  };

  // Reset service worker and caches
  const handleReset = async (e: React.MouseEvent) => {
    e.stopPropagation();
    
    if (isResetting) return;
    
    setIsResetting(true);
    
    try {
      // Unregister service worker
      if ('serviceWorker' in navigator) {
        const registrations = await navigator.serviceWorker.getRegistrations();
        for (let registration of registrations) {
          await registration.unregister();
          console.log('Service worker unregistered');
        }
      }
      
      // Clear caches
      if ('caches' in window) {
        const cacheKeys = await window.caches.keys();
        await Promise.all(
          cacheKeys.map(key => window.caches.delete(key))
        );
        console.log('Caches cleared');
      }
      
      // Clear IndexedDB (podcasts)
      if (window.indexedDB) {
        // Delete the database
        window.indexedDB.deleteDatabase('podcastDB');
      }
      
      // Force reload page
      window.location.reload();
    } catch (error) {
      console.error('Error resetting service worker:', error);
      setIsResetting(false);
    }
  };

  // Display message based on status
  const getBgColor = () => {
    if (!isOnline) return 'bg-red-500';
    if (status.active) return 'bg-green-500';
    return 'bg-yellow-500';
  };

  const getStatusText = () => {
    if (!isOnline) return 'You are offline';
    if (status.active) return 'Service Worker active';
    return `Service Worker ${status.state || 'inactive'}`;
  };

  return (
    <div 
      className={`fixed bottom-4 right-4 ${getBgColor()} text-white p-3 rounded-lg shadow-lg z-50 text-sm max-w-sm`}
      onClick={() => setShowDetails(!showDetails)}
    >
      <div className="flex items-center justify-between cursor-pointer">
        <div>
          <p className="font-medium">{getStatusText()} {status.isStandalone && '(PWA)'}</p>
        </div>
        <div className="ml-2">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
              d={showDetails ? "M19 9l-7 7-7-7" : "M9 5l7 7-7 7"} />
          </svg>
        </div>
      </div>
      
      {showDetails && (
        <div className="mt-2 border-t border-white/20 pt-2">
          <p className="text-xs mb-1">
            {!isOnline 
              ? "You're currently offline. Content may be limited."
              : status.active 
                ? "Content will be available offline" 
                : "Content won't be available offline"}
          </p>
          
          {status.cacheStatus?.tested && (
            <div className="mt-1 mb-1 bg-white/10 p-2 rounded text-xs">
              <p className="font-medium mb-1">Cache Status:</p>
              <p>Home page cached: {status.cacheStatus.homeCached ? '✅' : '❌'}</p>
              <p>Offline page cached: {status.cacheStatus.offlineCached ? '✅' : '❌'}</p>
              <p>Saved podcasts: {status.cacheStatus.podcastsCached}</p>
            </div>
          )}
          
          {status.scope && (
            <p className="text-xs mb-1">Scope: {status.scope}</p>
          )}
          {status.state && (
            <p className="text-xs mb-1">State: {status.state}</p>
          )}
          <p className="text-xs mb-1">
            Last checked: {new Date(status.lastChecked).toLocaleTimeString()}
          </p>
          
          <div className="flex space-x-2 mt-2">
            {!status.active && (
              <button 
                onClick={(e) => {
                  e.stopPropagation();
                  handleRegister();
                }}
                className="bg-white text-yellow-700 px-2 py-1 rounded text-xs font-medium"
                disabled={isResetting}
              >
                Register SW
              </button>
            )}
            
            <button 
              onClick={handleReset}
              className="bg-red-600 text-white px-2 py-1 rounded text-xs font-medium"
              disabled={isResetting}
            >
              {isResetting ? 'Resetting...' : 'Reset SW & Cache'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
} 