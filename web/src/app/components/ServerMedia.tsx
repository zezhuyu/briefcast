import { cookies } from 'next/headers';
import Image from 'next/image';

export default async function ServerMedia({ imageId, audioId }) {
  const cookieStore = cookies();
  const allCookies = cookieStore.getAll().map(c => `${c.name}=${c.value}`).join('; ');
  
  // Fetch image metadata with cookies
  const imageRes = await fetch(`https://your-backend.com/images/${imageId}/metadata`, {
    headers: { Cookie: allCookies },
  });
  const imageData = await imageRes.json();
  
  return (
    <div>
      <Image 
        src={`/api/media/images/${imageId}`} 
        width={imageData.width} 
        height={imageData.height} 
        alt={imageData.alt} 
      />
      <audio src={`/api/media/audio/${audioId}`} controls />
    </div>
  );
} 