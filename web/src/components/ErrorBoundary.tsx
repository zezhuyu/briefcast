'use client';

import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { 
      hasError: false,
      error: null 
    };
  }

  static getDerivedStateFromError(error: Error): State {
    // Update state so the next render will show the fallback UI.
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Error caught by error boundary:", error, errorInfo);
    
    // Check if this is a chunk loading error
    if (error.message && (
      error.message.includes('Failed to load chunk') || 
      error.message.includes('Loading chunk') ||
      error.message.includes('Loading CSS chunk')
    )) {
      console.log('Chunk loading error detected. Clearing cache and reloading...');
      
      // Clear caches if possible
      if ('caches' in window) {
        caches.keys().then(cacheNames => {
          cacheNames.forEach(cacheName => {
            caches.delete(cacheName);
          });
        });
      }

      // Reload the page after a short delay to make sure cache clearing completes
      setTimeout(() => {
        window.location.reload();
      }, 1000);
    }
  }

  handleReload = () => {
    if ('caches' in window) {
      caches.keys().then(cacheNames => {
        cacheNames.forEach(cacheName => {
          caches.delete(cacheName);
        });
        // Reload after cache is cleared
        window.location.reload();
      });
    } else {
      // Just reload if cache API is not available
      window.location.reload();
    }
  };

  render() {
    if (this.state.hasError) {
      const isChunkError = this.state.error?.message?.includes('chunk');
      
      return (
        <div className="min-h-screen bg-gradient-to-br from-indigo-900 to-purple-900 text-white flex items-center justify-center">
          <div className="max-w-md mx-auto p-8 bg-white/10 backdrop-blur-sm rounded-xl border border-white/20">
            <h1 className="text-2xl font-bold mb-4">Something went wrong</h1>
            
            {isChunkError ? (
              <>
                <p className="mb-4">
                  There was a problem loading some resources. This is usually caused by caching issues or a recent update.
                </p>
                <p className="text-amber-300 mb-6">
                  Trying to automatically recover...
                </p>
                <div className="animate-pulse flex space-x-4 mb-6">
                  <div className="flex-1 space-y-4 py-1">
                    <div className="h-2 bg-amber-500/30 rounded w-3/4"></div>
                    <div className="h-2 bg-amber-500/30 rounded w-1/2"></div>
                  </div>
                </div>
              </>
            ) : (
              <>
                <p className="mb-6">
                  {this.state.error?.message || 'An unexpected error occurred'}
                </p>
                <button 
                  onClick={this.handleReload}
                  className="px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-lg transition-colors"
                >
                  Try reloading
                </button>
                <a 
                  href="/clear-cache.html" 
                  className="ml-4 px-4 py-2 bg-transparent border border-amber-500 text-amber-500 hover:bg-amber-500/10 rounded-lg transition-colors"
                >
                  Clear cache
                </a>
              </>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
} 