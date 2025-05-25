"use client";
import React, { createContext, useContext, useState, useEffect, useRef, ReactNode } from 'react';
import { useAuth } from '@clerk/nextjs';

// Define user activity types
type UserAction = 'share' | 'download' | 'add_to_playlist' | 'like' | 'dislike' | 'remove_from_playlist' | 'seek';

type ActivityLog = {
  timestamp: number;
  action: UserAction;
  podcastId: string;
  details?: any;
};

type ListeningProgress = {
  podcastId: string;
  totalDuration: number;
  listenedSeconds: number[];
  lastPosition: number;
  positionLog: Array<{time: number, position: number}>;
  startTime: number;
};

type UserActivityState = {
  actions: ActivityLog[];
  listeningProgress: ListeningProgress | null;
};

type Podcast = {
  favorite: boolean | undefined;
  transcript_url: any;
  positive: any;
  category: ReactNode;
  totalRating: any;
  cover_image_url: string;
  subcategory: ReactNode;
  id: string;
  podcast_id?: string;
  title: string;
  show: string;
  episode: string;
  duration: string;
  audio_url: string;
};

type Playlist = {
  id: string;
  name: string;
  podcasts: Podcast[];
};

type PlayerContextType = {
  currentPodcast: Podcast | null;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  playlists: Playlist[] | undefined;
  currentPlaylist: Playlist | null;
  tmpPlaylist: Podcast[];
  setCurrentPodcast: (podcast: Podcast) => void;
  togglePlayPause: () => void;
  seekTo: (time: number) => void;
  formatTime: (time: number) => string;
  addToPlaylist: (playlistId: string, podcast: Podcast) => void;
  deletePlaylist: (playlistId: string) => void;
  createPlaylist: (name: string) => Promise<string>;
  setCurrentPlaylist: (playlist: Playlist | null) => void;
  removeFromPlaylist: (playlistId: string, podcastId: string) => void;
  playNext: () => void;
  playPrevious: () => void;
  // New user activity tracking functions
  logUserAction: (action: UserAction, details?: any) => void;
  setLiked: (liked: boolean | null) => void;
  sharePodcast: () => void;
  downloadPodcast: () => void;
  setPodcastId: (podcastId: string) => void;
  setTmpPlaylist: (playlist: Podcast[]) => void;
};

const PlayerContext = createContext<PlayerContextType | undefined>(undefined);

export function PlayerProvider({ children }: { children: React.ReactNode }) {
  // Get the initial podcast ID from URL if available
  const [podcastId, setPodcastId] = useState<string | null>(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      return params.get('podcast') || null;
    }
    return null;
  });
  const [currentPodcast, setCurrentPodcast] = useState<Podcast | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playlists, setPlaylists] = useState<Playlist[]>();
  const [currentPlaylist, setCurrentPlaylist] = useState<Playlist | null>(null);
  const [tmpPlaylist, setTmpPlaylist] = useState<Podcast[]>([]);
  const [isPlayingTransition, setIsPlayingTransition] = useState(false);
  const [nextPodcastId, setNextPodcastId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const { getToken } = useAuth();
  
  // User activity tracking state
  const [userActivity, setUserActivity] = useState<UserActivityState>({
    actions: [],
    listeningProgress: null,
  });
  
  // Track if first render to avoid reporting on initial mount
  const isInitialMount = useRef(true);
  
  // Helper function to log user actions
  const logUserAction = (action: UserAction, details?: any) => {
    if (!currentPodcast) return;
    
    setUserActivity(prev => ({
      ...prev,
      actions: [
        ...prev.actions,
        {
          timestamp: Date.now(),
          action,
          podcastId: currentPodcast.id,
          details
        }
      ]
    }));
  };
  
  // Convenience functions for common actions
  const setLiked = (liked: boolean | null) => {
    if (liked === true) {
      logUserAction('like');
    } else if (liked === false) {
      logUserAction('dislike');
    }
  };
  
  const sharePodcast = () => {
    logUserAction('share');
  };
  
  const downloadPodcast = () => {
    logUserAction('download');
  };
  
  // Function to report activity to backend
  const reportUserActivity = async () => {
    if (!userActivity.listeningProgress || !currentPodcast) return;
    
    try {
      // Calculate total listened time and coverage
      const uniqueSeconds = new Set(userActivity.listeningProgress.listenedSeconds);
      const listenedDuration = uniqueSeconds.size;
      const totalDuration = userActivity.listeningProgress.totalDuration;
      const coverage = totalDuration > 0 ? (listenedDuration / totalDuration) * 100 : 0;
      
      // Prepare data for backend
      const activityData = {
        podcast_id: userActivity.listeningProgress.podcastId,
        actions: userActivity.actions,
        listened_seconds: Array.from(uniqueSeconds),
        listen_duration_seconds: listenedDuration,
        total_duration_seconds: totalDuration,
        coverage_percentage: coverage,
        last_position: userActivity.listeningProgress.lastPosition,
        position_log: userActivity.listeningProgress.positionLog,
        listening_time: Date.now() - userActivity.listeningProgress.startTime,
      };

      if (activityData.podcast_id === "") {
        return;
      }
      
      // Send to backend
      const token = await getToken({ skipCache: true });
      if (!token) return;
      const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}played`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(activityData),
        cache: 'no-cache',
        credentials: 'same-origin'
      });
      
      if (!response.ok) {
        console.error('Failed to report user activity:', await response.text());
      }
    } catch (error) {
      console.error('Error reporting user activity:', error);
    }
    
    // Reset activity tracking for the next podcast
    setUserActivity({
      actions: [],
      listeningProgress: null,
    });
  };
  
  // Track listened seconds
  useEffect(() => {
    if (!currentPodcast || currentTime <= 0) return;
    
    const second = Math.floor(currentTime);
    
    setUserActivity(prev => {
      // If this is a new podcast, initialize listening progress
      if (!prev.listeningProgress || prev.listeningProgress.podcastId !== currentPodcast.id) {
        return {
          ...prev,
          listeningProgress: {
            podcastId: currentPodcast.id,
            totalDuration: duration,
            listenedSeconds: isPlaying ? [second] : [],
            lastPosition: second,
            positionLog: [{ time: Date.now(), position: second }],
            startTime: Date.now(),
          }
        };
      }
      
      // Otherwise, update the existing listening progress
      return {
        ...prev,
        listeningProgress: {
          ...prev.listeningProgress,
          listenedSeconds: isPlaying 
            ? [...prev.listeningProgress.listenedSeconds, second]
            : prev.listeningProgress.listenedSeconds,
          lastPosition: second,
          totalDuration: duration,
        }
      };
    });
  }, [currentTime, currentPodcast, duration]);

  // Add this function to log position to backend
  const logPositionToBackend = async (position: number) => {
    if (!currentPodcast) return;
    
    try {
      const token = await getToken({ skipCache: true });
      if (!token) return;
      if (currentPodcast.id === "") {
        return;
      }

      const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}playing`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          podcast_id: currentPodcast.id,
          position: position,
          timestamp: Date.now()
        }),
        cache: 'no-cache',
        credentials: 'same-origin'
      });

      if (!response.ok) {
        console.error('Failed to log position:', await response.text());
      }
    } catch (error) {
      console.error('Error logging position:', error);
    }
  };

  // Modify the useEffect for position logging
  useEffect(() => {
    if (!currentPodcast) return;
    
    const intervalId = setInterval(() => {
      if (isPlaying) {  // Only log when playing
        logPositionToBackend(currentTime);
      }
    }, 5000); // Log every 5 seconds
    
    return () => clearInterval(intervalId);
  }, [currentPodcast, isPlaying, currentTime]);

  // Report activity when podcast changes, component unmounts or window is closed
  useEffect(() => {
    // Skip initial mount
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }
    
    // Report activity when podcast changes
    reportUserActivity();
    
    // Also report on unmount
    return () => {
      reportUserActivity();
    };
  }, [currentPodcast?.id]);
  
  // Report activity when window closes or user navigates away
  useEffect(() => {
    const handleBeforeUnload = () => {
      reportUserActivity();
    };
    
    window.addEventListener('beforeunload', handleBeforeUnload);
    
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, []);
  
  useEffect(() => {
    

    function getLocation(): Promise<GeolocationPosition> {
      return new Promise((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject);
      });
    }

    const loadPodcast = async () => {
      // Skip loading if we already have the current podcast
      if (currentPodcast && 
        currentPodcast.id === podcastId && 
        currentPodcast.hasOwnProperty("cover_image_url") && 
        currentPodcast.hasOwnProperty("audio_url") && 
        currentPodcast.hasOwnProperty("transcript_url") && 
        currentPodcast.cover_image_url !== "" && 
        currentPodcast.audio_url !== "" && 
        currentPodcast.transcript_url !== "") {
        return;
      }

      const token = await getToken({ skipCache: true });
      let response;
      let data;
      if (podcastId && podcastId !== "") {
        try {
          response = await fetch(process.env.NEXT_PUBLIC_BACKEND_URL + "podcast/" + podcastId, {
            method: "GET",
            cache: 'no-cache',
            credentials: 'same-origin',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`
            }
          });
          
        } catch (error) {
          console.error("Error loading podcast:", error);
        }
      }else{
        let locationData;
        try {
          const location = await getLocation();
          locationData = [location.coords.latitude, location.coords.longitude];
        } catch (locError) {
          console.error("Failed to get location:", locError);
          // Fallback to default location
          locationData = [0, 0];
        }
        try {
          response = await fetch(process.env.NEXT_PUBLIC_BACKEND_URL + "generate", {
            method: "POST",
            cache: 'no-cache',
            credentials: 'same-origin',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
              location: locationData
            })
          });
        } catch (error) {
          console.error("Error generating new podcast:", error);
        }
      }

      // First check if we can load from offline storage
      // if (window.isPodcastAvailableOffline && window.loadPodcastFromStorage) {
      //   try {
      //     const isAvailable = await window.isPodcastAvailableOffline(podcastId);
      //     if (isAvailable) {
      //       const offlinePodcast = await window.loadPodcastFromStorage(podcastId);
      //       if (offlinePodcast) {
      //         setCurrentPodcast(offlinePodcast);
      //         return;
      //       }
      //     }
      //   } catch (error) {
      //     console.error("Error checking offline availability:", error);
      //   }
      // }
      
      // Load from network as fallback
      
        
        // Check if URLs are empty
        if (!response) {
          console.error("No response received");
          await new Promise(resolve => setTimeout(resolve, 3000));
          return loadPodcast();
        }

        if (response.status === 401) {
          await new Promise(resolve => setTimeout(resolve, 1000));
          return loadPodcast();
        }
        
        data = await response.json();
        if (data.cover_image_url === "") {
          await new Promise(resolve => setTimeout(resolve, 3000));
          return loadPodcast();
        }else{
          if (!data.cover_image_url.startsWith(process.env.NEXT_PUBLIC_BACKEND_URL) && !data.cover_image_url.startsWith('blob:')) data.cover_image_url = process.env.NEXT_PUBLIC_BACKEND_URL + 'files/' + data.cover_image_url;
        }

        if (data.transcript_url === "" || data.transcript_url === null) {
          await new Promise(resolve => setTimeout(resolve, 3000));
          return loadPodcast();
        }else{
          if (!data.transcript_url.startsWith(process.env.NEXT_PUBLIC_BACKEND_URL) && 
            !data.transcript_url.startsWith('blob:') && 
            !data.transcript_url.startsWith('data:text/plain')) {
            data.transcript_url = process.env.NEXT_PUBLIC_BACKEND_URL + 'files/' + data.transcript_url;
          }
        }
        setCurrentPodcast(data);
    };
    loadPodcast();

  }, [podcastId]); // Only depend on podcastId changes

  let localTMPList: Podcast[] = [];



  const checkPlaylistAndFetchRecommendations = async (podcast: Podcast) => {
    try {
      const token = await getToken({ skipCache: true });
      if (!token) return;
      if (podcast.id === undefined || podcast.id === "") return;
      const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}recommendations/${podcast.id}`, { 
        method: "GET",
        headers: {
          "Authorization": `Bearer ${token}`
        },
        cache: 'no-cache',
        credentials: 'same-origin'
      }); 
      const recommendations = await response.json();
      const deduplicatedRecommendations = deduplicatePodcasts(tmpPlaylist, recommendations);
      setTmpPlaylist(deduplicatedRecommendations);
      localTMPList = deduplicatedRecommendations;
    } catch (error) {
      console.error("Error fetching recommendations:", error);
    }
  };

  const deduplicatePodcasts = (pList1: Podcast[], pList2: Podcast[]): Podcast[] => {
    pList2.forEach(p => {
      if (!pList1.some(p2 => p2.id === p.id)) {
        pList1.push(p);
      }
    });
    return pList1;
  };

  // Initialize audio element
  useEffect(() => {
    audioRef.current = new Audio();
    
    const audio = audioRef.current;
    
    const updateTime = () => setCurrentTime(audio.currentTime);
    const updateDuration = () => {
      if (audio.duration && !isNaN(audio.duration)) {
        setDuration(audio.duration);
      }
    };
    const handleEnded = () => setIsPlaying(false);
    const handleError = (e: any) => {
      console.error("Audio error:", e);
      setDuration(0);
    };
    
    audio.addEventListener('timeupdate', updateTime);
    audio.addEventListener('loadedmetadata', updateDuration);
    audio.addEventListener('durationchange', updateDuration);
    audio.addEventListener('ended', handleEnded);
    audio.addEventListener('error', handleError);
    
    return () => {
      audio.pause();
      audio.removeEventListener('timeupdate', updateTime);
      audio.removeEventListener('loadedmetadata', updateDuration);
      audio.removeEventListener('durationchange', updateDuration);
      audio.removeEventListener('ended', handleEnded);
      audio.removeEventListener('error', handleError);
    };
  }, []);

  useEffect(() => {
    const loadPodcast = async () => {
      const token = await getToken();
      const response = await fetch(process.env.NEXT_PUBLIC_BACKEND_URL + "playlists", {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${token}`
        },
        cache: 'no-cache',
        credentials: 'same-origin'
      });
      const data = await response.json();
      setPlaylists(data)
    }
    loadPodcast();
  }, [])

  // Update audio source when podcast changes
  useEffect(() => {
    if (!audioRef.current || !currentPodcast) return;
    
    const loadAudioSource = async () => {
      try {
        // Check if we have offline storage functions from page.tsx
        if (window.isPodcastAvailableOffline && window.loadAsset) {
          try {
            // Check if this podcast is available offline
            const isAvailable = await window.isPodcastAvailableOffline(currentPodcast.id);
            
            if (isAvailable && audioRef.current) {
              // Load audio from offline storage
              const audioUrl = await window.loadAsset(currentPodcast.audio_url, 'audio');
              if (audioUrl && audioRef.current) {
                audioRef.current.src = audioUrl;
                await audioRef.current.load();
                
                // Wait for audio to be loaded before playing
                if (audioRef.current.readyState >= 2) {
                  await audioRef.current.play();
                  setIsPlaying(true);
                } else {
                  // If not loaded yet, wait for canplay event
                  audioRef.current.addEventListener('canplay', async () => {
                    try {
                      await audioRef.current?.play();
                      setIsPlaying(true);
                    } catch (err) {
                      console.error("Error playing audio after load:", err);
                      setIsPlaying(false);
                    }
                  }, { once: true });
                }
                return;
              }
            }
          } catch (error) {
            console.error("Error accessing offline content:", error);
          }
        }
        
        // Fallback to network URL
        if (audioRef.current) {
          audioRef.current.src = currentPodcast.audio_url;
          await audioRef.current.load();
          
          // Wait for audio to be loaded before playing
          if (audioRef.current.readyState >= 2) {
            await audioRef.current.play();
            setIsPlaying(true);
          } else {
            // If not loaded yet, wait for canplay event
            audioRef.current.addEventListener('canplay', async () => {
              try {
                await audioRef.current?.play();
                setIsPlaying(true);
              } catch (err) {
                console.error("Error playing audio after load:", err);
                setIsPlaying(false);
              }
            }, { once: true });
          }
        }
      } catch (error) {
        console.error("Error loading audio source:", error);
        setIsPlaying(false);
      }
    };
    
    loadAudioSource();
  }, [currentPodcast]);

  // Format time in MM:SS
  const formatTime = (timeInSeconds: number) => {
    const minutes = Math.floor(timeInSeconds / 60) || 0;
    const seconds = Math.floor(timeInSeconds % 60) || 0;
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  };

  // Modify the togglePlayPause function to handle loading states
  const togglePlayPause = async () => {
    if (!audioRef.current || !currentPodcast) return;
    
    try {
      if (isPlaying) {
        audioRef.current.pause();
        // Log position when pausing
        logPositionToBackend(currentTime);
        setIsPlaying(false);
      } else {
        // If audio is not loaded yet, wait for it
        if (audioRef.current.readyState < 2) {
          await new Promise((resolve) => {
            audioRef.current?.addEventListener('canplay', resolve, { once: true });
          });
        }
        await audioRef.current.play();
        // Log position when starting to play
        logPositionToBackend(currentTime);
        setIsPlaying(true);
      }
    } catch (err) {
      console.error("Error toggling play/pause:", err);
      setIsPlaying(false);
    }
  };

  // Seek to specific time
  const seekTo = (time: number) => {
    if (!audioRef.current) return;
    
    // Log the seek action
    if (currentPodcast) {
      logUserAction('seek', { from: currentTime, to: time });
      
      // Also update the listening progress with this seek action
      setUserActivity(prev => {
        if (!prev.listeningProgress) return prev;
        
        return {
          ...prev,
          listeningProgress: {
            ...prev.listeningProgress,
            lastPosition: time,
            positionLog: [
              ...prev.listeningProgress.positionLog, 
              { time: Date.now(), position: time }
            ]
          }
        };
      });
    }
    
    audioRef.current.currentTime = time;
    setCurrentTime(time);
  };

  // Create a new playlist
  const createPlaylist = async (name: string): Promise<string> => {
    const token = await getToken();
    const response = await fetch(process.env.NEXT_PUBLIC_BACKEND_URL + "playlist", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify({
        name
      }),
      cache: 'no-cache',
      credentials: 'same-origin'
    });
    if (response.ok) {
      const data = await response.json();
      if (data.hasOwnProperty('id') && data.id !== null) {
        const newPlaylist: Playlist = {
          id: data.id,
          name,
          podcasts: []
        };
        setPlaylists(prev => prev ? [...prev, newPlaylist] : [newPlaylist]);
        return newPlaylist.id;
      }

    }
    throw new Error("Failed to create playlist");
  };

  const deletePlaylist = async (playlistId: string) => {
    const token = await getToken();
    const response = await fetch(process.env.NEXT_PUBLIC_BACKEND_URL + "playlist", {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify({
        id: playlistId,
      }),
      cache: 'no-cache',
      credentials: 'same-origin'
    });
    if (response.ok) {
      setPlaylists(prev => prev?.filter(playlist => playlist.id !== playlistId));
      return;
    }
    throw new Error("Failed to delete playlist");
  };

  const addToPlaylist = async (playlistId: string, podcast: Podcast) => {
    // Log the action
    logUserAction('add_to_playlist', { playlistId });
    
    const token = await getToken();
    const response = await fetch(process.env.NEXT_PUBLIC_BACKEND_URL + "playlist/" + playlistId, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify({
        podcast_id: podcast.id,
      }),
      cache: 'no-cache',
      credentials: 'same-origin'
    });
    if (response.ok) {
      if (playlistId === currentPlaylist?.id) {
        if (currentPlaylist && currentPlaylist.podcasts && !currentPlaylist.podcasts.some(p => p.id === podcast.id)) {
          setCurrentPlaylist(prev => {
            if (!prev) return null;
            return {
              id: prev.id,
              name: prev.name,
              podcasts: [...(prev.podcasts || []), podcast]
            };
          });
        }
      }
      setPlaylists(prev => 
        prev?.map(playlist => {
          if (playlist.id === playlistId) {
            const exists = playlist.podcasts?.some(p => p.id === podcast.id);
            if (!exists) {
              return {
                ...playlist,
                podcasts: [...(playlist.podcasts || []), podcast]
              };
            }
          }
          return playlist;
        })
      );
    }
  };

  const removeFromPlaylist = async (playlistId: string, podcastId: string) => {
    // Log the action
    logUserAction('remove_from_playlist', { playlistId });
    
    const token = await getToken();
    const response = await fetch(process.env.NEXT_PUBLIC_BACKEND_URL + "playlist/" + playlistId, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify({
        podcast_id: podcastId,
      }),
      cache: 'no-cache',
      credentials: 'same-origin'
    });
    if (response.ok) {
      if (playlistId === currentPlaylist?.id) {
        setCurrentPlaylist(prev => {
          if (!prev) return null;
          return {
            id: prev.id,
            name: prev.name,
            podcasts: prev.podcasts?.filter(p => p.id !== podcastId && p.podcast_id !== podcastId)
          };
        });
      }
      
      setPlaylists(prev => 
        prev?.map(playlist => {
          if (playlist.id === playlistId) {
            return {
              ...playlist,
              podcasts: playlist.podcasts?.filter(p => 
                p.id !== podcastId && p.podcast_id !== podcastId
              )
            };
          }
          return playlist;
        })
      );
    }
  };


  useEffect(() => {
    const fetchPodcast = async () => {
      if (!currentPodcast) return;
      let list = tmpPlaylist;
      if (currentPlaylist && currentPlaylist.podcasts.findIndex(p => p.id === currentPodcast.id) >= 0) {
        list = currentPlaylist.podcasts;
      }
      if(list.length == 0 || list.findIndex(p => p.id === currentPodcast.id) === -1 || list.findIndex(p => p.id === currentPodcast.id) >= list.length - 1){
        await checkPlaylistAndFetchRecommendations(currentPodcast); 
        list = tmpPlaylist;
      }
      if (list.length > 0 && currentPodcast && list.findIndex(p => p.id === currentPodcast.id) < list.length - 1) {
        const token = await getToken({ skipCache: true });
        const podcastId = list[list.findIndex(p => p.id === currentPodcast.id) + 1].id;
        fetch(process.env.NEXT_PUBLIC_BACKEND_URL + "podcast/" + podcastId, {
          method: "GET",
          cache: 'no-cache',
          credentials: 'same-origin',
          headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`
            }
          });
        if (currentPodcast.id === "") {
          return;
        }
        const response = await fetch(process.env.NEXT_PUBLIC_BACKEND_URL + "transition", {
          method: "POST",
          cache: 'no-cache',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({
            id1: currentPodcast.id,
            id2: podcastId
          })
        })
        const data = await response.json();
      }
    }
    fetchPodcast();
  }, [currentPodcast])
  // Play next podcast in playlist
  const playNext = () => {
    if (!currentPodcast) return;

    let nextPodcastId: string | null = null;

    if (currentPlaylist) {
      // If we have a current playlist, use its logic
      const currentIndex = currentPlaylist.podcasts.findIndex(p => p.id === currentPodcast.id);
      if (currentIndex === -1 || currentIndex === currentPlaylist.podcasts.length - 1) return;
      nextPodcastId = currentPlaylist.podcasts[currentIndex + 1].id;
    } else if (tmpPlaylist.length > 0) {
      // If we have a tmp playlist, play from it
      const currentIndex = tmpPlaylist.findIndex(p => p.id === currentPodcast.id);
      if (currentIndex === -1) {
        // If current podcast is not in tmp playlist, play the first one
        nextPodcastId = tmpPlaylist[0].id;
      } else if (currentIndex < tmpPlaylist.length - 1) {
        // Play the next one in tmp playlist
        nextPodcastId = tmpPlaylist[currentIndex + 1].id;
      } else if (tmpPlaylist.length === 0 || currentIndex >= tmpPlaylist.length - 1) {
        // Only call checkPlaylistAndFetchRecommendations if currentPodcast is not null
        if (currentPodcast) {
          checkPlaylistAndFetchRecommendations(currentPodcast);
        }
        return;
      }
    }

    if (nextPodcastId) {
      // Load and play transition before playing next podcast
      loadAndPlayTransition(currentPodcast.id, nextPodcastId);
    }
  };

  // Play previous podcast in playlist
  const playPrevious = () => {
    if (!currentPlaylist || !currentPodcast) return;
    
    const currentIndex = currentPlaylist.podcasts.findIndex(p => p.id === currentPodcast.id);
    if (currentIndex <= 0) return;
    
    setCurrentPodcast(currentPlaylist.podcasts[currentIndex - 1]);
  };

  // Add new function to load and play transition
  const loadAndPlayTransition = async (currentId: string, nextId: string) => {
    try {
      const token = await getToken({ skipCache: true });
      if (!token) return;

      const response = await fetch(process.env.NEXT_PUBLIC_BACKEND_URL + "transition", {
        method: "POST",
        cache: 'no-cache',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          id1: currentId,
          id2: nextId
        })
      });

      const transitionData = await response.json();

      if (transitionData.audio_url === "") {
        await new Promise(resolve => setTimeout(resolve, 3000));
        return loadAndPlayTransition(currentId, nextId); 
      }
      
      if (transitionData.audio_url && transitionData.audio_url !== "") {
        // Store the next podcast ID to play after transition
        setNextPodcastId(nextId);
        setIsPlayingTransition(true);
        
        // Create a temporary podcast object for the transition
        const transitionPodcast: Podcast = {
          id: '',
          title: 'Sofia Lane',
          show: 'Transition',
          episode: 'Transition',
          duration: transitionData.secs,
          audio_url: transitionData.audio_url,
          cover_image_url: transitionData.cover_image_url || '',
          transcript_url: transitionData.transcript_url || '',
          favorite: false,
          positive: false,
          category: 'Host',
          subcategory: 'BriefCast',
          totalRating: 0
        };

        // Set the transition as current podcast
        if (transitionPodcast.audio_url !== "" && !transitionPodcast.audio_url.startsWith(process.env.NEXT_PUBLIC_BACKEND_URL) && !transitionPodcast.audio_url.startsWith("blob")) {
          transitionPodcast.audio_url = process.env.NEXT_PUBLIC_BACKEND_URL + "files/" + transitionPodcast.audio_url;
        }
        if (transitionPodcast.transcript_url !== "" && !transitionPodcast.transcript_url.startsWith(process.env.NEXT_PUBLIC_BACKEND_URL) && !transitionPodcast.transcript_url.startsWith("blob")) {
          transitionPodcast.transcript_url = process.env.NEXT_PUBLIC_BACKEND_URL + "files/" + transitionPodcast.transcript_url;
        }
        if (transitionPodcast.cover_image_url !== "" && !transitionPodcast.cover_image_url.startsWith(process.env.NEXT_PUBLIC_BACKEND_URL) && !transitionPodcast.cover_image_url.startsWith("blob")) {
          transitionPodcast.cover_image_url = process.env.NEXT_PUBLIC_BACKEND_URL + "files/" + transitionPodcast.cover_image_url;
        }
        setCurrentPodcast(transitionPodcast);
      }
    } catch (error) {
      console.error("Error loading transition:", error);
      // If transition fails, just play the next podcast directly
      setPodcastId(nextId);
    }
  };

  // Modify the useEffect for audio ended to handle transitions
  useEffect(() => {
    if (!audioRef.current) return;

    const handleEnded = () => {
      setIsPlaying(false);
      
      if (isPlayingTransition && nextPodcastId) {
        // If we just finished playing a transition, play the next podcast
        setIsPlayingTransition(false);
        setPodcastId(nextPodcastId);
        setNextPodcastId(null);
      } else {
        // Normal case - play next podcast
        playNext();
      }
    };

    audioRef.current.addEventListener('ended', handleEnded);
    return () => {
      if (audioRef.current) {
        audioRef.current.removeEventListener('ended', handleEnded);
      }
    };
  }, [currentPodcast, tmpPlaylist, currentPlaylist, isPlayingTransition, nextPodcastId]);

  return (
    <PlayerContext.Provider
      value={{
        currentPodcast,
        isPlaying,
        currentTime,
        duration,
        playlists,
        currentPlaylist,
        tmpPlaylist,
        setCurrentPodcast,
        togglePlayPause,
        seekTo,
        formatTime,
        addToPlaylist,
        deletePlaylist,
        createPlaylist,
        setCurrentPlaylist,
        removeFromPlaylist,
        playNext,
        playPrevious,
        // New user activity tracking functions
        logUserAction,
        setLiked,
        sharePodcast,
        downloadPodcast,
        setPodcastId,
        setTmpPlaylist
      }}
    >
      {children}
    </PlayerContext.Provider>
  );
}

export function usePlayer() {
  const context = useContext(PlayerContext);
  if (context === undefined) {
    throw new Error('usePlayer must be used within a PlayerProvider');
  }
  return context;
} 