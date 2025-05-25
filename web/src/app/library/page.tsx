"use client";
import { useState, useEffect, Key } from "react";
import { UserButton } from "@clerk/nextjs";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import MiniPlayer from "@/components/MiniPlayer";
import { usePlayer } from "@/context/PlayerContext";
import { useAuth } from "@clerk/nextjs";
import { ReactNode, ReactElement, JSXElementConstructor, ReactPortal } from 'react';

interface Podcast {
  id: string;
  title: string;
  category: string;
  subcategory: string;
  duration: number;
  duration_seconds: number;
  listen_duration_seconds: number;
  cover_image_url: string;
  positive_rating: number;
  negative_rating: number;
  total_rating: number;
  createAt: string;
  favorite: boolean;
  transcript_url: string;
  [key: string]: any;
}

const toDate = (timestamp: number) => {
  var date = new Date(timestamp * 1000);
  if (isNaN(date.getTime())) {
    date = new Date(timestamp);
  }
  const now = new Date();
  const diffTime = Math.abs(now.getTime() - date.getTime());
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  if (diffTime < 60) {
    return 'just now'; 
  }
  if (diffTime < 60 * 60) {
    return `${Math.ceil(diffTime / 60)} minutes ago`;
  }
  if (diffTime < 60 * 60 * 24) {
    return `${Math.ceil(diffTime / (60 * 60))} hours ago`;
  }
  if (diffDays < 30) {
    return `${diffDays} days ago`;
  }
  if (diffDays < 365) {
    return `${Math.ceil(diffDays / 30)} months ago`;
  }
  return `${Math.ceil(diffDays / 365)} years ago`;
}
// Mock recommendation API cal

export default function LibraryPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [showTrending, setShowTrending] = useState(false);
  const [trendingItems, setTrendingItems] = useState<Podcast[]>([]);
  const router = useRouter();
  const { setCurrentPodcast, togglePlayPause, playlists, addToPlaylist, createPlaylist, deletePlaylist } = usePlayer();
  const [showPlaylistModal, setShowPlaylistModal] = useState(false);
  const [selectedPodcast, setSelectedPodcast] = useState<Podcast | null>(null);
  const [filteredPodcasts, setFilteredPodcasts] = useState<Podcast[]>([]);
  const [recommendations, setRecommendations] = useState<Podcast[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingHotTrending, setIsLoadingHotTrending] = useState(true);
  const [history, setHistory] = useState<Podcast[]>([]);
  const [hotTrending, setHotTrending] = useState<Podcast[]>([]);
  const { getToken } = useAuth();
  const [newPlaylistName, setNewPlaylistName] = useState('');
  
  // Load recommendations on mount
  useEffect(() => {
    const loadRecommendations = async () => {
      
      try {
        fetchRecommendations();
        fetchHistory();
        fetchHotTrending();
      } catch (error) {
        console.error("Error fetching recommendations:", error);
      }
    };
    
    loadRecommendations();
  }, []);

  const fetchRecommendations = async () => {
    // In a real app, this would be an API call
    setIsLoading(true);
    return new Promise(resolve => {
      setTimeout(async () => {
        const token = await getToken();
        const response = await fetch(process.env.NEXT_PUBLIC_BACKEND_URL + "recommendations", {
          method: "GET",
          headers: {
            "Authorization": `Bearer ${token}`
          },
          // cache: 'no-store',
          // credentials: 'same-origin'
        })

        const data = await response.json();
        setRecommendations(data);
        setIsLoading(false);
        resolve(data);
      }, 500);
      
    });
  };
  

  const fetchHistory = async () => {
    return new Promise(resolve => {
      setTimeout(async () => {
        const token = await getToken();
        const response = await fetch(process.env.NEXT_PUBLIC_BACKEND_URL + "history", {
          method: "GET",
          headers: {
            "Authorization": `Bearer ${token}`
          },
          // cache: 'no-store',
          // credentials: 'same-origin'
        })

        const data = await response.json();
        setHistory(data);
        resolve(data);
      }, 500);
    });
  }

  const fetchHotTrending = async () => {
    setIsLoadingHotTrending(true);
    return new Promise(resolve => {
      setTimeout(async () => {
        const token = await getToken();
        const response = await fetch(process.env.NEXT_PUBLIC_BACKEND_URL + "get_hot_trending", {
          method: "GET",
          headers: {
            "Authorization": `Bearer ${token}`
          },
          // cache: 'no-store',
          // credentials: 'same-origin'
        })

        const data = await response.json();
        setHotTrending(data);
        setIsLoadingHotTrending(false);
        resolve(data);
      }, 500);
    });
  }

  const searchPodcasts = async () => {
    console.log(searchTerm)
    if (searchTerm.length <= 0) return;
    const token = await getToken();

    const response = await fetch(process.env.NEXT_PUBLIC_BACKEND_URL + "search?q=" + searchTerm , {
      method: "GET",
      headers: {
        "Authorization": `Bearer ${token}`
      },
      // cache: 'no-store',
      // credentials: 'same-origin'
    });
    const data = await response.json();
    setFilteredPodcasts(data);
  };
  
  
  
  const handlePodcastClick = (podcastId: Key | null | undefined) => {
    router.push(`/?podcast=${podcastId}`);
  };
  
  // Render a podcast card
  const renderPodcastCard = (podcast: {
    rating: ReactNode;
    subcategory: ReactNode;
    createAt(createAt: any): import("react").ReactNode; id: Key | null | undefined; cover_image_url: any; title: string | number | bigint | boolean | ReactElement<unknown, string | JSXElementConstructor<any>> | Iterable<ReactNode> | Promise<string | number | bigint | boolean | ReactPortal | ReactElement<unknown, string | JSXElementConstructor<any>> | Iterable<ReactNode> | null | undefined> | null | undefined; 
}) => (
    
    <div 
      key={podcast.id}
      className="bg-white rounded-xl shadow-lg overflow-hidden cursor-pointer transform transition-all hover:scale-105 hover:shadow-xl relative group"
      onClick={() => handlePodcastClick(podcast.id)}
    >
      <div className="relative aspect-square">
        <Image
          src={process.env.NEXT_PUBLIC_BACKEND_URL + `files/${podcast.cover_image_url}`}
          alt={podcast.title}
          fill
          className="object-cover"
        />
        
        <div 
          className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity"
          onClick={(e) => {
            e.stopPropagation();
            setSelectedPodcast(podcast);
            setShowPlaylistModal(true);
          }}
        >
          <button className="bg-white rounded-full p-2 shadow-md hover:bg-amber-100 transition-colors">
            <svg className="w-5 h-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
          </button>
        </div>
      </div>
      <div className="p-4">
        <h3 className="font-bold text-lg mb-1 line-clamp-1 text-gray-800">{podcast.title}</h3>
        <p className="text-gray-600 text-sm mb-1">{podcast.subcategory}</p>
        <div className="flex justify-between text-xs text-gray-500">
          <span>{toDate(Number(podcast.createAt))}</span>
          <span>Rating: {podcast.positive / podcast.totalRating || 0.0}</span>
        </div>
      </div>
    </div>
  );
  
  // Render a history item
  const renderHistoryItem = (item: never) => (
    <div 
      key={item.id}
      className="flex-shrink-0 w-48 bg-white rounded-lg shadow-md overflow-hidden cursor-pointer hover:shadow-lg transition-shadow"
      onClick={() => handlePodcastClick(item.id)}
    >
      <div className="relative h-32">
        <Image
          src={`${process.env.NEXT_PUBLIC_BACKEND_URL}files/${item.cover_image_url}`}
          alt={item.title}
          fill
          className="object-cover"
        />
        <div className="absolute bottom-0 left-0 right-0 h-1 bg-gray-200">
          <div 
            className="h-full bg-amber-500"
            style={{ width: `${item.stop_position_seconds / item.duration_seconds * 100}%` }}
          />
        </div>
      </div>
      <div className="p-3">
        <h3 className="font-medium text-sm line-clamp-1 text-gray-800">{item.title}</h3>
        <p className="text-gray-500 text-xs mb-1">{item.subcategory}</p>
        <p className="text-gray-400 text-xs">{toDate(item.listened_at)}</p>
      </div>
    </div>
  );
  
  // Add new function to fetch trending items
  const fetchTrending = async () => {
    try {
      const token = await getToken();
      const response = await fetch(process.env.NEXT_PUBLIC_BACKEND_URL + "get_trending", {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${token}`
        }
      });
      const data = await response.json();
      setTrendingItems(data);
    } catch (error) {
      console.error("Error fetching trending items:", error);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-900/90 to-purple-900/90 text-white">
      <header className="bg-white/10 backdrop-blur-md shadow-lg">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Link href="/" className="text-2xl font-bold text-white">BriefCast</Link>
            <span className="-ml-1 px-1.5 py-0.5 text-[10px] font-semibold text-white bg-gradient-to-r from-gray-500 to-gray-700 border border-gray-400/30 rounded-full -mt-3 whitespace-nowrap">Tech Preview</span>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/" className="text-white/80 hover:text-white">Player</Link>
            <Link href="/library" className="text-white font-medium">Library</Link>
            <Link href="/downloads" className="text-white/80 hover:text-white">Downloads</Link>
            <Link href="/history" className="text-white/80 hover:text-white">History</Link>
            <UserButton afterSignOutUrl="/sign-in" />
          </div>
        </div>
      </header>
      
      <main className="container mx-auto px-4 py-8">
        {/* Search Bar with Trending Dropdown */}
        <div className="mb-8">
          <div className="relative max-w-2xl mx-auto">
            <input
              type="text"
              placeholder="Search podcasts..."
              className="w-full p-4 pl-12 rounded-lg border border-white/20 bg-white/10 text-white focus:outline-none focus:ring-2 focus:ring-amber-500 placeholder-white/50"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  searchPodcasts();
                }
              }}
              onFocus={() => {
                setShowTrending(true);
                fetchTrending();
              }}
              onBlur={() => {
                // Delay hiding to allow clicking on trending items
                setTimeout(() => setShowTrending(false), 200);
              }}
            />
            <svg 
              className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-white/50" 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>

            {/* Trending Dropdown */}
            {showTrending && trendingItems.length > 0 && (
              <div className="absolute z-50 w-full mt-2 bg-white/10 backdrop-blur-md rounded-lg shadow-xl border border-white/20 max-h-96 overflow-y-auto">
                <div className="p-2">
                  <h3 className="text-sm font-semibold text-white/80 mb-2 px-2">Trending Now</h3>
                  {trendingItems.map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center gap-3 p-2 rounded-lg hover:bg-white/20 cursor-pointer"
                      onClick={() => {
                        setSearchTerm(item.title);
                        setShowTrending(false);
                        searchPodcasts();
                      }}
                    >
                      <div className="relative w-10 h-10 flex-shrink-0">
                        <Image
                          src={process.env.NEXT_PUBLIC_BACKEND_URL + `files/${item.cover_image_url}`}
                          alt={item.title}
                          fill
                          className="object-cover rounded-md"
                        />
                      </div>
                      <div className="flex-grow min-w-0">
                        <h4 className="text-white font-medium truncate">{item.title}</h4>
                        <p className="text-sm text-white/60 truncate">{item.category} | {item.subcategory}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
        
        {filteredPodcasts.length > 0 ? (
          // Search Results
          <div className="mb-8">
            <h2 className="text-2xl font-bold mb-6">Search Results</h2>
            
            {filteredPodcasts.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                {filteredPodcasts.map(podcast => renderPodcastCard(podcast))}
              </div>
            ) : (
              <div className="text-center py-12 bg-white/10 backdrop-blur-sm rounded-xl">
                <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <h3 className="text-xl font-medium text-gray-700 mb-2">No podcasts found</h3>
                <p className="text-gray-500">Try searching for something else</p>
              </div>
            )}
          </div>
        ) : (
          <>
            {/* History Section */}
            <section className="mb-4">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold">Recently Played</h2>
                <Link 
                  href="/history" 
                  className="text-amber-600 hover:text-amber-700 flex items-center gap-1"
                >
                  See all
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </Link>
              </div>
              
              <div className="flex overflow-x-auto gap-4 pb-4 -mx-4 px-4">
                {history.slice(0, 10).map(item => renderHistoryItem(item))}
              </div>
            </section>

            {/* Hot Trending Section */}
            <section className="mb-4">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold">Hot Trending</h2>
                <span className="text-amber-600 flex items-center gap-1">
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M12.395 2.553a1 1 0 00-1.45-.385c-.345.23-.614.558-.822.88-.214.33-.403.713-.57 1.116-.334.804-.614 1.768-.84 2.734a31.365 31.365 0 00-.613 3.58 2.64 2.64 0 01-.945-1.067c-.328-.68-.398-1.534-.398-2.654A1 1 0 005.05 6.05 6.981 6.981 0 003 11a7 7 0 1011.95-4.95c-.592-.591-.98-.985-1.348-1.467-.363-.476-.724-1.063-1.207-2.03zM12.12 15.12A3 3 0 017 13s.879.5 2.5.5c0-1 .5-4 1.25-4.5.5 1 .786 1.293 1.371 1.879A2.99 2.99 0 0113 13a2.99 2.99 0 01-.879 2.121z" clipRule="evenodd" />
                  </svg>
                  Trending Now
                </span>
              </div>
              
              {isLoadingHotTrending ? (
                <div className="flex overflow-x-auto gap-4 pb-4 -mx-4 px-4">
                  {[...Array(4)].map((_, i) => (
                    <div key={i} className="flex-shrink-0 w-48 bg-white/20 rounded-lg h-32 animate-pulse"></div>
                  ))}
                </div>
              ) : (
                <div className="flex overflow-x-auto gap-4 pb-4 -mx-4 px-4">
                  {hotTrending.map(podcast => (
                    <div 
                      key={podcast.id}
                      className="flex-shrink-0 w-48 bg-white rounded-lg shadow-md overflow-hidden cursor-pointer hover:shadow-lg transition-shadow"
                      onClick={() => handlePodcastClick(podcast.id)}
                    >
                      <div className="relative h-32">
                        <Image
                          src={process.env.NEXT_PUBLIC_BACKEND_URL + `files/${podcast.cover_image_url}`}
                          alt={podcast.title}
                          fill
                          className="object-cover"
                        />
                        <div 
                          className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedPodcast(podcast);
                            setShowPlaylistModal(true);
                          }}
                        >
                          <button className="bg-white rounded-full p-1.5 shadow-md hover:bg-amber-100 transition-colors">
                            <svg className="w-4 h-4 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                            </svg>
                          </button>
                        </div>
                      </div>
                      <div className="p-3">
                        <h3 className="font-medium text-sm line-clamp-1 text-gray-800">{podcast.title}</h3>
                        <p className="text-gray-500 text-xs mb-1">{podcast.subcategory}</p>
                        <div className="flex justify-between text-xs text-gray-500">
                          <span>{toDate(Number(podcast.createAt))}</span>
                          <span>Rating: {podcast.positive_rating / podcast.total_rating || 0.0}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
            
            {/* For You Section */}
            <section>
              <h2 className="text-2xl font-bold mb-6">For You</h2>
              
              {isLoading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {[...Array(6)].map((_, i) => (
                    <div key={i} className="bg-white/20 rounded-xl h-64 animate-pulse"></div>
                  ))}
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6">
                  {recommendations.map(podcast => renderPodcastCard(podcast))}
                </div>
              )}
            </section>
          </>
        )}
      </main>
      
      <MiniPlayer />
      
      {showPlaylistModal && selectedPodcast && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-indigo-900 border border-white/20 rounded-lg p-6 w-full max-w-md text-white">
            <h3 className="text-xl font-bold mb-4">Add to Playlist</h3>
            
            <div className="space-y-2 mb-4">
              {playlists?.map(playlist => (
                <button
                  key={playlist.id}
                  className="w-full text-left p-3 rounded-lg hover:bg-amber-600 flex justify-between items-center"
                  onClick={async () => {
                    await addToPlaylist(playlist.id, selectedPodcast);
                    setShowPlaylistModal(false);
                  }}
                >
                  <span>{playlist.name}</span>
                  {playlist.id !== 'favorite' && playlist.id !== 'like' && (<button 
                    className="text-gray-400 hover:text-red-500"
                    onClick={async (e) => {
                      e.stopPropagation();
                      await deletePlaylist(playlist.id);
                    }}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>)}
                </button>
              ))}
            </div>
            
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Create New Playlist
              </label>
              <input
                type="text"
                value={newPlaylistName}
                onChange={(e) => setNewPlaylistName(e.target.value)}
                placeholder="Enter playlist name"
                className="w-full px-3 py-2 rounded-md bg-white/10 text-white placeholder-gray-400 border border-white/20 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>
            
            <div className="flex justify-between">
              <button
                className="text-gray-500 hover:text-gray-300"
                onClick={() => setShowPlaylistModal(false)}
              >
                Cancel
              </button>
              
              <button
                className="bg-amber-500 text-white px-4 py-2 rounded-lg hover:bg-amber-600"
                onClick={async () => {
                  try {
                    const playlistName = newPlaylistName.trim() || `New Playlist ${playlists?.length + 1 || 1}`;
                    const newPlaylistId = await createPlaylist(playlistName);
                    await addToPlaylist(newPlaylistId, selectedPodcast);
                    setNewPlaylistName('');
                    setShowPlaylistModal(false);
                  } catch (error) {
                    console.error("Error creating playlist:", error);
                  }
                }}
              >
                Create Playlist
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
} 