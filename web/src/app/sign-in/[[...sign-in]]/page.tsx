"use client";
import { useEffect, useState } from "react";
import { useSearchParams } from 'next/navigation'
import { SignIn, SignUp } from "@clerk/nextjs";
import Image from "next/image";



export default function AuthPage() {
  const [activeTab, setActiveTab] = useState<"signIn" | "signUp">("signIn");
  const searchParams = useSearchParams()

  useEffect(() => {
    if (searchParams) {
      if (searchParams.has('__clerk_status')) {
        if (searchParams.get('__clerk_status') === 'sign_up') {
          setActiveTab("signUp");
        }
      }
    }
  }, [searchParams]);


  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-indigo-900/90 to-purple-900/90">
      <div className="flex w-full max-w-5xl">
        {/* Left Side - Welcome and Icon */}
        <div className="hidden md:flex md:w-1/2 flex-col justify-center items-center p-8 text-white">
          {/* Premium Headphones Icon */}
          <div className="mb-8 rounded-full bg-gradient-to-br from-zinc-800 to-zinc-900 shadow-lg shadow-amber-600/20 border border-amber-400/20 flex items-center justify-center relative overflow-hidden w-80 h-80">
            {/* Glow effect */}
            <div className="absolute inset-0 bg-gradient-to-r from-amber-500 to-amber-700 rounded-full blur-md"></div>
            
            {/* Premium rim */}
            <div className="absolute inset-2 rounded-full border-2 border-amber-400/20"></div>
            
            {/* Headphones Image */}
            <div className="relative z-10 w-full h-full flex items-center justify-center">
              <Image 
                src="/headphone.png" 
                alt="Premium Headphones"
                width={440}
                height={440}
                className="object-contain scale-110"
                priority
              />
              
              {/* Animated Sound Waves */}
              <div className="absolute left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2 -z-10">
                <div className="w-48 h-48 rounded-full border-2 border-amber-400/20 animate-ping opacity-30"></div>
                <div className="w-64 h-64 rounded-full border-2 border-amber-400/10 animate-ping opacity-20 animation-delay-300"></div>
              </div>
            </div>
          </div>
          
          <h1 className="text-4xl font-bold mb-4 text-center">Welcome to BriefCast</h1>
          <p className="text-xl text-white/70 text-center mb-6">
            Your personal daily presidential briefing on the web
          </p>
          <div className="space-y-4 text-white/80">
            <div className="flex items-center">
              <svg className="w-5 h-5 mr-2 text-amber-400" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span>Daily executive summaries</span>
            </div>
            <div className="flex items-center">
              <svg className="w-5 h-5 mr-2 text-amber-400" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span>Concise policy updates</span>
            </div>
            <div className="flex items-center">
              <svg className="w-5 h-5 mr-2 text-amber-400" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span>Listen on any device</span>
            </div>
          </div>
        </div>

        {/* Right Side - Auth Forms */}
        <div className="w-full md:w-1/2 flex items-center justify-center">
          {/* Auth Component */}
          <div className="w-full max-w-md p-6">
            {activeTab === "signIn" ? (
              <SignIn
                appearance={{
                  elements: {
                    rootBox: "mx-auto",
                    card: "bg-transparent border-none shadow-none",
                    headerTitle: "text-white text-2xl font-bold",
                    headerSubtitle: "text-white/70",
                    formButtonPrimary: "bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-white",
                    formFieldLabel: "text-white",
                    formFieldInput: "bg-white/10 border-white/20 text-white rounded-lg focus:ring-amber-500",
                    footerActionLink: "text-amber-400 hover:text-amber-300",
                    footer: {
                      display: 'none',
                    }
                  }
                }}
                routing="path"
                path="/sign-in"
              />
            ) : (
              <SignUp 
                appearance={{
                  elements: {
                    rootBox: "mx-auto",
                    card: "bg-transparent border-none shadow-none",
                    headerTitle: "text-white text-2xl font-bold",
                    headerSubtitle: "text-white/70",
                    formButtonPrimary: "bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-white",
                    formFieldLabel: "text-white",
                    formFieldInput: "bg-white/10 border-white/20 text-white rounded-lg focus:ring-amber-500",
                    footerActionLink: "text-amber-400 hover:text-amber-300",
                    footer: {
                      display: 'none',
                    }
                  }
                }}
                routing="path"
                path="/sign-in"
              />
            )}

            {/* Tab Buttons Below Auth Component */}
            <div className="flex justify-center mt-6 space-x-4">
              <button
                className={`px-4 py-2 text-sm font-medium rounded-lg transition-all ${
                  activeTab === "signIn"
                    ? "bg-gradient-to-r from-amber-500 to-amber-600 text-white shadow-sm"
                    : "bg-white/10 text-white/70 hover:text-white hover:bg-white/20"
                }`}
                onClick={() => setActiveTab("signIn")}
              >
                Sign In
              </button>
              <button
                className={`px-4 py-2 text-sm font-medium rounded-lg transition-all ${
                  activeTab === "signUp"
                    ? "bg-gradient-to-r from-amber-500 to-amber-600 text-white shadow-sm"
                    : "bg-white/10 text-white/70 hover:text-white hover:bg-white/20"
                }`}
                onClick={() => setActiveTab("signUp")}
              >
                Sign Up
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}