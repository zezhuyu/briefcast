'use client';
import { useState, useEffect } from 'react';

export default function AuthenticatedAudio({ src, ...props }: { src: string, [key: string]: any }) {
  const [blobUrl, setBlobUrl] = useState('');
  
  useEffect(() => {
    const fetchAudio = async () => {
      const response = await fetch(src, {
        credentials: 'same-origin', // Changed from 'include' to 'same-origin'
      });
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      setBlobUrl(url);
    };
    
    fetchAudio();
    
    return () => {
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [src]);
  
  return blobUrl ? <audio src={blobUrl} {...props} /> : null;
} 