"use client";
import { usePlayer } from '@/context/PlayerContext';
import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

export default function MiniPlayer() {
  const { currentPodcast, isPlaying, currentTime, duration, togglePlayPause, formatTime } = usePlayer();
  const router = useRouter();
  
  if (!currentPodcast) return null;
  
  const progressPercentage = duration > 0 ? (currentTime / duration) * 100 : 0;
  
  return (
    <div className="fixed bottom-4 left-4 z-50 bg-white rounded-lg shadow-xl overflow-hidden w-72 transition-all hover:shadow-2xl">
      <div className="flex items-center p-2">
        {/* Cover image */}
        <div 
          className="relative w-12 h-12 rounded-md overflow-hidden cursor-pointer"
          onClick={() => router.push(`/?podcast=${currentPodcast.id}`)}
        >
          <Image
            src={currentPodcast.cover_image_url}
            alt={currentPodcast.title}
            fill
            className="object-cover"
          />
        </div>
        
        {/* Info and controls */}
        <div className="flex-1 ml-3 min-w-0">
          <Link href={`/?podcast=${currentPodcast.id}`} className="block">
            <h4 className="font-medium text-sm truncate text-gray-800">{currentPodcast.title}</h4>
            <p className="text-xs text-gray-500 truncate">{currentPodcast.subcategory}</p>
          </Link>
          
          {/* Progress bar */}
          <div className="w-full h-1 bg-gray-200 rounded-full mt-1 mb-1">
            <div 
              className="h-full bg-amber-500 rounded-full"
              style={{ width: `${progressPercentage}%` }}
            />
          </div>
          
          {/* Time and play button */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">{formatTime(currentTime)}</span>
            <button 
              className="text-amber-500 hover:text-amber-600 transition-colors"
              onClick={togglePlayPause}
            >
              {isPlaying ? (
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              ) : (
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
} 