import React, { useState, useEffect } from 'react';

const OfflineIndicator = () => {
  const [isOffline, setIsOffline] = useState(false);
  const [showBanner, setShowBanner] = useState(false);

  useEffect(() => {
    // Check initial state
    setIsOffline(!navigator.onLine);
    setShowBanner(!navigator.onLine);

    // Add event listeners
    const handleOffline = () => {
      setIsOffline(true);
      setShowBanner(true);
    };

    const handleOnline = () => {
      setIsOffline(false);
      // Don't immediately hide to allow user to see the change
      setTimeout(() => setShowBanner(false), 3000);
    };

    window.addEventListener('offline', handleOffline);
    window.addEventListener('online', handleOnline);

    return () => {
      window.removeEventListener('offline', handleOffline);
      window.removeEventListener('online', handleOnline);
    };
  }, []);

  // Don't render anything if online and banner is dismissed
  if (!showBanner) return null;

  return (
    <div 
      className={`fixed bottom-20 left-0 right-0 mx-auto max-w-md px-4 z-50 transition-transform duration-300 ${showBanner ? 'transform-none' : 'translate-y-full'}`}
    >
      <div className={`rounded-lg shadow-lg p-4 flex items-center gap-3 ${isOffline ? 'bg-amber-500' : 'bg-green-500'}`}>
        <div className="flex-shrink-0">
          {isOffline ? (
            <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          ) : (
            <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          )}
        </div>
        <div className="flex-1">
          <p className="text-white font-medium">
            {isOffline 
              ? "You're offline. Using cached content." 
              : "You're back online!"
            }
          </p>
        </div>
        <button 
          onClick={() => setShowBanner(false)} 
          className="flex-shrink-0 text-white/80 hover:text-white"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
};

export default OfflineIndicator; 