"use client";
import { JSXElementConstructor, Key, ReactElement, ReactNode, ReactPortal, useState } from "react";
import { UserButton } from "@clerk/nextjs";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import MiniPlayer from "@/components/MiniPlayer";
import { usePlayer } from "@/context/PlayerContext";
import { useAuth } from "@clerk/nextjs";
import { useEffect } from "react";
// Sample history data - in a real app, this would come from a database or API

// Group history by month

const toDate = (timestamp: number) => {
  var date = new Date(timestamp * 1000);
  if (isNaN(date.getTime())) {
    date = new Date(timestamp);
  }
  const now = new Date();
  const diffTime = Math.abs(now.getTime() - date.getTime());
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  if (diffTime < 60) {
    return `${diffTime} seconds ago`; 
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

const groupHistoryByMonth = (history: any[]) => {
  const grouped = {};
  
  history.forEach(item => {
    var date = new Date(item.listened_at * 1000);
    if (isNaN(date.getTime())) {
      date = new Date(item.listened_at);
    }
    const monthYear = date.toLocaleString('default', { month: 'long', year: 'numeric' });
    
    if (!grouped[monthYear]) {
      grouped[monthYear] = [];
    }
    
    grouped[monthYear].push(item);
  });
  
  return grouped;
};

export default function HistoryPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const router = useRouter();
  const { getToken } = useAuth();
  const [history, setHistory] = useState([]);
  const { setCurrentPodcast, togglePlayPause } = usePlayer();
  

  const fetchHistory = async () => {
    return new Promise(resolve => {
      setTimeout(async () => {
        const token = await getToken();
        const response = await fetch(process.env.NEXT_PUBLIC_BACKEND_URL + "history", {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`
          },
          // credentials: 'same-origin'
        })  
    const data = await response.json();
    resolve(data);
      }, 500);
    });
  }

  useEffect(() => {
    fetchHistory().then((data: any[]) => {
      setHistory(data);
    });
  }, []);

  // Filter history based on search term
  const filteredHistory = history.filter((item: {
    title: string;
    subcategory: string;
  }) => 
    item.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.subcategory.toLowerCase().includes(searchTerm.toLowerCase())
  );
  
  // Group filtered history by month
  const groupedHistory = groupHistoryByMonth(filteredHistory);
  
  const handlePodcastClick = (podcastId: Key | null | undefined) => {
    router.push(`/?podcast=${podcastId}`);
  };
  
  // Render a history item
  const renderHistoryItem = (item: { id: Key | null | undefined; cover_image_url: any; title: string | number | bigint | boolean | ReactElement<unknown, string | JSXElementConstructor<any>> | Iterable<ReactNode> | Promise<string | number | bigint | boolean | ReactPortal | ReactElement<unknown, string | JSXElementConstructor<any>> | Iterable<ReactNode> | null | undefined> | null | undefined; listen_duration_seconds: number; duration_seconds: number; subcategory: string | number | bigint | boolean | ReactElement<unknown, string | JSXElementConstructor<any>> | Iterable<ReactNode> | ReactPortal | Promise<string | number | bigint | boolean | ReactPortal | ReactElement<unknown, string | JSXElementConstructor<any>> | Iterable<ReactNode> | null | undefined> | null | undefined; listened_at: number; }) => (
    <div 
      key={item.id}
      className="bg-white/10 backdrop-blur-sm rounded-lg shadow-md overflow-hidden cursor-pointer hover:shadow-lg transition-all hover:bg-white/20"
      onClick={() => handlePodcastClick(item.id)}
    >
      <div className="relative aspect-square">
        <Image
          src={`${process.env.NEXT_PUBLIC_BACKEND_URL}files/${item.cover_image_url || ''}`}
          alt={item.title?.toString() || ''}
          fill
          className="object-cover"
        />
        <div className="absolute bottom-0 left-0 right-0 h-1 bg-white/20">
          <div 
            className="h-full bg-amber-500"
            style={{ width: `${item.stop_position_seconds / item.duration_seconds * 100}%` }}
          />
        </div>
      </div>
      <div className="p-4">
        <h3 className="font-medium text-white text-sm line-clamp-1">{item.title}</h3>
        <p className="text-white/70 text-xs mb-1">{item.subcategory}</p>
        <div className="flex justify-between items-center mt-2">
          <span className="text-white/50 text-xs">{toDate(item.listened_at)}</span>
          <span className="text-amber-400 text-xs">{(item.stop_position_seconds / item.duration_seconds * 100).toFixed(0)}% completed</span>
        </div>
      </div>
    </div>
  );
  
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
            <Link href="/library" className="text-white/80 hover:text-white">Library</Link>
            <Link href="/downloads" className="text-white/80 hover:text-white">Downloads</Link>
            <Link href="/history" className="text-white font-medium">History</Link>
            <UserButton afterSignOutUrl="/sign-in" />
          </div>
        </div>
      </header>
      
      <main className="container mx-auto px-4 py-8">
        {/* Search Bar */}
        <div className="mb-8">
          <div className="relative max-w-2xl mx-auto">
            <input
              type="text"
              placeholder="Search your history..."
              className="w-full p-4 pl-12 rounded-lg border border-white/20 bg-white/10 text-white focus:outline-none focus:ring-2 focus:ring-amber-500 placeholder-white/50"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
            <svg 
              className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-white/50" 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
        </div>
        
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-6">Your Listening History</h1>
          
          {Object.keys(groupedHistory).length > 0 ? (
            <div className="space-y-12">
              {Object.entries(groupedHistory).map(([monthYear, items]) => (
                <div key={monthYear}>
                  <h2 className="text-xl font-semibold mb-4 border-b border-white/20 pb-2">{monthYear}</h2>
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
                    {items!.map((item: { id: Key | null | undefined; cover_image_url: any; title: string | number | bigint | boolean | ReactElement<unknown, string | JSXElementConstructor<any>> | Iterable<ReactNode> | Promise<string | number | bigint | boolean | ReactPortal | ReactElement<unknown, string | JSXElementConstructor<any>> | Iterable<ReactNode> | null | undefined> | null | undefined; listen_duration_seconds: number; duration_seconds: number; subcategory: string | number | bigint | boolean | ReactElement<unknown, string | JSXElementConstructor<any>> | Iterable<ReactNode> | ReactPortal | Promise<string | number | bigint | boolean | ReactPortal | ReactElement<unknown, string | JSXElementConstructor<any>> | Iterable<ReactNode> | null | undefined> | null | undefined; listened_at: number; }) => renderHistoryItem(item))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 bg-white/5 backdrop-blur-sm rounded-xl">
              <svg className="w-16 h-16 text-white/40 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <h3 className="text-xl font-medium text-white mb-2">No history found</h3>
              <p className="text-white/60">Try searching for something else or start listening to podcasts</p>
            </div>
          )}
        </div>
      </main>
      
      <MiniPlayer />
    </div>
  );
} 