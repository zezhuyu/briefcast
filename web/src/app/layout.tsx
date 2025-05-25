import { ClerkProvider } from '@clerk/nextjs';
import { PlayerProvider } from '@/context/PlayerContext';
import './globals.css';
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { Suspense } from 'react';
import Script from 'next/script';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'BriefCast',
  description: 'BriefCast is your personal commute companion on-the-go. Featuring AI generated news and updates delivered, daily, in audio format.',
  metadataBase: new URL('https://briefcast.net'),
  appleWebApp: {
    title: 'BriefCast',
    statusBarStyle: 'black-translucent',
  },
  other: {
    'apple-mobile-web-app-capable': 'yes',
    'mobile-web-app-capable': 'yes',
    'Cache-Control': 'no-cache, no-store, must-revalidate',
    'Pragma': 'no-cache',
    'Expires': '0'
  },
  manifest: '/manifest.json'
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ClerkProvider>
      <PlayerProvider>
        <html lang="en">
          <head>
            <meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no" />
            <meta name="apple-mobile-web-app-capable" content="yes" />
            <meta name="mobile-web-app-capable" content="yes" />
            <meta name="theme-color" content="#6422FE" />
            <meta httpEquiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
            <meta httpEquiv="Pragma" content="no-cache" />
            <meta httpEquiv="Expires" content="0" />
            <link rel="apple-touch-icon" href="/icons/icon-192x192.png" />

          </head>
          <body className={inter.className}>
            <Suspense fallback={<div>Loading...</div>}>
              {children}
            </Suspense>
            
          </body>
        </html>
      </PlayerProvider>
    </ClerkProvider>
  );
}
