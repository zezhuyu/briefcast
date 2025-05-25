import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const { path } = req.query;
  const resourcePath = Array.isArray(path) ? path.join('/') : path;
  
  // Forward the request to your backend with cookies
  const response = await fetch(`${process.env.BACKEND_URL}/${resourcePath}`, {
    headers: {
      Cookie: req.headers.cookie || '',
    },
  });
  
  // Get the content type from the response
  const contentType = response.headers.get('content-type');
  res.setHeader('Content-Type', contentType || 'application/octet-stream');
  
  // Stream the response back to the client
  const arrayBuffer = await response.arrayBuffer();
  res.send(Buffer.from(arrayBuffer));
} 