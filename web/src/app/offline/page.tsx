"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

export default function OfflinePage() {
  const [savedPodcasts, setSavedPodcasts] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    // Check if IndexedDB is available
    if (typeof window !== 'undefined' && 'indexedDB' in window) {
      const loadSavedPodcasts = async () => {
        try {
          // Use the global function we defined in page.tsx
          if (window.getAllSavedPodcasts) {
            const podcasts = await window.getAllSavedPodcasts();
            setSavedPodcasts(podcasts);
          } else {
            // Fallback implementation if function not found
            const openRequest = indexedDB.open('podcastDB', 1);
            openRequest.onsuccess = (event) => {
              const db = openRequest.result;
              const transaction = db.transaction(['podcasts'], 'readonly');
              const store = transaction.objectStore('podcasts');
              const request = store.getAll();
              
              request.onsuccess = () => {
                const podcasts = request.result.filter(p => p.savedOffline);
                setSavedPodcasts(podcasts);
              };
            };
          }
        } catch (error) {
          console.error('Error loading offline podcasts:', error);
        } finally {
          setIsLoading(false);
        }
      };
      
      loadSavedPodcasts();
    } else {
      setIsLoading(false);
    }
  }, []);
  
  const handlePodcastClick = (podcastId: string) => {
    router.push(`/downloads?podcast=${podcastId}`);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-900/90 to-purple-900/90 text-white p-4">
      <div className="max-w-4xl mx-auto pt-12">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold mb-4">You're Offline</h1>
          <p className="text-xl text-white/80">
            But don't worry, your downloaded podcasts are still available!
          </p>
        </div>
        
        <div className="bg-white/10 rounded-xl p-6 backdrop-blur-md">
          <h2 className="text-2xl font-bold mb-6">Your Downloaded Podcasts</h2>
          
          {isLoading ? (
            <div className="animate-pulse">
              <div className="h-16 bg-white/5 rounded-lg mb-4"></div>
              <div className="h-16 bg-white/5 rounded-lg mb-4"></div>
              <div className="h-16 bg-white/5 rounded-lg"></div>
            </div>
          ) : savedPodcasts.length > 0 ? (
            <div className="space-y-4">
              {savedPodcasts.map((podcast) => (
                <div 
                  key={podcast.id}
                  className="p-4 bg-white/5 rounded-lg hover:bg-white/10 transition-colors cursor-pointer"
                  onClick={() => handlePodcastClick(podcast.id)}
                >
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-gray-500 rounded overflow-hidden flex-shrink-0">
                      {podcast.cover_image_url && podcast.cover_image_url.startsWith('blob:') ? (
                        <img 
                          src={podcast.cover_image_url} 
                          alt={podcast.title} 
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center bg-amber-500 text-white">
                          {podcast.title?.charAt(0) || 'P'}
                        </div>
                      )}
                    </div>
                    <div className="flex-grow">
                      <h3 className="font-medium">{podcast.title}</h3>
                      <p className="text-sm text-white/70">{podcast.show || podcast.subcategory}</p>
                    </div>
                    <svg className="w-5 h-5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                    </svg>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <svg className="w-16 h-16 mx-auto text-white/30 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              <h3 className="text-xl font-bold mb-2">No Downloads Found</h3>
              <p className="text-white/70">
                You don't have any podcasts saved for offline listening.
              </p>
            </div>
          )}
          
          <div className="mt-8 text-center">
            <Link 
              href="/downloads"
              className="inline-block bg-amber-500 hover:bg-amber-600 text-white py-3 px-6 rounded-lg font-medium transition-colors"
            >
              Go to Downloads
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
} 