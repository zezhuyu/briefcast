import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  // Only accept GET requests
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // Get the token from Authorization header
    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return res.status(401).json({ error: 'Missing or invalid token' });
    }

    const token = authHeader.substring(7); // Remove "Bearer " part

    // Call the backend to refresh the token
    const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      credentials: 'include',
    });

    // If backend responds with an error, forward it
    if (!response.ok) {
      const errorText = await response.text();
      console.error(`[Token Refresh API] Backend responded with ${response.status}: ${errorText}`);
      return res.status(response.status).json({ 
        error: 'Failed to refresh token',
        details: errorText
      });
    }

    // Parse the response and extract the new token
    const data = await response.json();
    
    // Return the new token to the client
    return res.status(200).json({
      token: data.token || data.access_token,
      message: 'Token refreshed successfully'
    });
  } catch (error) {
    console.error('[Token Refresh API] Error:', error);
    return res.status(500).json({ 
      error: 'Internal server error',
      details: error instanceof Error ? error.message : String(error)
    });
  }
} 