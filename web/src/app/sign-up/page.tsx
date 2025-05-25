"use client";
import { useState, useEffect, useMemo } from "react";
import { SignIn, SignUp, useSignUp } from "@clerk/nextjs";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import axios from "axios";
import { SUBTOPICS } from "./subtopics";

// Define the list of available topics
const TOPICS = [
  "Politics", "Economy", "Sports", "Technology", "Health", 
  "Science", "Entertainment", "Business", "Education", 
  "Environment", "Culture", "Lifestyle", "Travel", 
  "Automotive", "Crime", "Law", "World News", "Local News"
];

export default function AuthPage() {
  const [view, setView] = useState<"signIn" | "signUp" | "topicSelection" | "subtopicSelection">("topicSelection");
  const [selectedTopics, setSelectedTopics] = useState<string[]>([]);
  const [selectedSubtopics, setSelectedSubtopics] = useState<Record<string, string[]>>({});
  const { isLoaded, signUp, setActive } = useSignUp();
  const router = useRouter();
  const [isSignUpComplete, setIsSignUpComplete] = useState(false);
  const { getToken } = useAuth();
  

  // Add this effect to listen for Clerk events
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const handleClerkEvent = (e: any) => {
        if (e.data && e.data.type === 'clerk:signUp:complete') {
          console.log('Clerk sign-up complete event detected');
          setIsSignUpComplete(true);
          setView("topicSelection");
        }
      };
      
      window.addEventListener('message', handleClerkEvent);
      
      return () => {
        window.removeEventListener('message', handleClerkEvent);
      };
    }
  }, []);

  // Also update your existing effect to check for sign-up completion
  useEffect(() => {
    if (isLoaded && signUp) {
      console.log("SignUp status:", signUp.status);
      
      if (signUp.status === "complete" || isSignUpComplete) {
        console.log("Sign-up complete, showing topic selection");
        setView("topicSelection");
      }
    }
  }, [isLoaded, signUp, isSignUpComplete]);

  // Handle topic selection
  const toggleTopic = (topic: string) => {
    setSelectedTopics(prev => 
      prev.includes(topic)
        ? prev.filter(t => t !== topic)
        : [...prev, topic]
    );
    
    // If we're removing a topic, also remove its subtopics
    if (selectedTopics.includes(topic)) {
      setSelectedSubtopics(prev => {
        const updated = { ...prev };
        delete updated[topic];
        return updated;
      });
    }
  };

  // Handle subtopic selection
  const toggleSubtopic = (topic: string, subtopic: string) => {
    setSelectedSubtopics(prev => {
      const currentTopicSubtopics = prev[topic] || [];
      const updatedTopicSubtopics = currentTopicSubtopics.includes(subtopic)
        ? currentTopicSubtopics.filter(st => st !== subtopic)
        : [...currentTopicSubtopics, subtopic];
      
      return {
        ...prev,
        [topic]: updatedTopicSubtopics
      };
    });
  };

  // Move to subtopic selection
  const handleContinueToSubtopics = () => {
    if (selectedTopics.length > 0) {
      setView("subtopicSelection");
    }
  };

  // Save topics and redirect to home page
  const handleTopicSubmit = async () => {
    try {
      // Format the data to include both topics and subtopics
      const topicsData = {
        mainTopics: selectedTopics,
        subtopics: selectedSubtopics
      };
      
      const token = await getToken();
      console.log(token);
      
      await axios.post(process.env.NEXT_PUBLIC_BACKEND_URL + "sign-up", 
        {
          topics: topicsData
        },
        {
          headers: {
            "Content-Type": "application/json", 
            "Authorization": `Bearer ${token}`
          },
        }
      );
      
      // Set the user as active in the session
      if (isLoaded && signUp && signUp.status === "complete") {
        await setActive({ session: signUp.createdSessionId });
      }
      
      // Redirect to home page
      router.push("/");
    } catch (error) {
      console.error("Error saving topics:", error);
    }
  };

  // First, let's randomize the order of topics
  const shuffledTopics = useMemo(() => {
    return [...TOPICS].sort(() => Math.random() - 0.5);
  }, []);

  // Create a shuffled array of all subtopics from selected topics
  const shuffledSubtopics = useMemo(() => {
    // Gather all subtopics from selected topics
    const allSubtopics = selectedTopics.flatMap(topic => 
      SUBTOPICS[topic].map(subtopic => ({ topic, subtopic }))
    );
    
    // Shuffle the array
    return [...allSubtopics].sort(() => Math.random() - 0.5);
  }, [selectedTopics]);

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
            
            {/* Add this to render the SignIn component when view is "signIn" */}
            {view === "signIn" && (
              <div className="bg-white/10 backdrop-blur-md p-6 rounded-xl shadow-2xl">
                <SignIn />
              </div>
            )}
            
            {/* Add this to render the SignUp component when view is "signUp" */}
            {view === "signUp" && (
              <div className="bg-white/10 backdrop-blur-md p-6 rounded-xl shadow-2xl">
                <SignUp />
              </div>
            )}
            
            {view === "topicSelection" && (
              <div className="bg-white/10 backdrop-blur-md p-6 rounded-xl shadow-2xl max-h-[80vh] overflow-y-auto mt-4">
                <h1 className="text-2xl font-bold text-white mb-4 text-center">Select Your Interests</h1>
                <p className="text-white/80 mb-4 text-center text-sm">
                  Choose topics you're interested in to personalize your experience.
                </p>
                
                <div className="flex flex-wrap justify-center gap-2 mb-6 max-h-[50vh] overflow-y-auto p-2">
                  {shuffledTopics.map(topic => (
                    <button
                      key={topic}
                      onClick={() => toggleTopic(topic)}
                      className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all transform hover:scale-105 ${
                        selectedTopics.includes(topic)
                          ? 'bg-amber-500 text-white shadow-lg'
                          : 'bg-white/20 text-white hover:bg-white/30'
                      }`}
                      style={{
                        fontSize: `${Math.random() * 0.1 + 0.8}rem`,
                        transform: Math.random() > 0.7 ? `rotate(${Math.random() * 3 - 1.5}deg)` : 'none'
                      }}
                    >
                      {topic}
                    </button>
                  ))}
                </div>

                <div className="flex justify-between items-center">
                  <span className="text-white/70 text-xs">
                    {selectedTopics.length} topics selected
                  </span>
                  <button
                    onClick={handleContinueToSubtopics}
                    disabled={selectedTopics.length === 0}
                    className={`px-4 py-1.5 rounded-lg text-sm font-medium ${
                      selectedTopics.length > 0
                        ? 'bg-amber-500 hover:bg-amber-600 text-white'
                        : 'bg-white/20 text-white/50 cursor-not-allowed'
                    }`}
                  >
                    Continue
                  </button>
                </div>
              </div>
            )}

            {view === "subtopicSelection" && (
              <div className="bg-white/10 backdrop-blur-md p-6 rounded-xl shadow-2xl max-h-[80vh] overflow-y-auto mt-4">
                <h1 className="text-2xl font-bold text-white mb-4 text-center">Refine Your Interests</h1>
                <p className="text-white/80 mb-4 text-center text-sm">
                  Select specific subtopics that interest you.
                </p>
                
                <div className="flex flex-wrap justify-center gap-2 mb-6 max-h-[50vh] overflow-y-auto p-2">
                  {shuffledSubtopics.map(({ topic, subtopic }) => (
                    <button
                      key={`${topic}-${subtopic}`}
                      onClick={() => toggleSubtopic(topic, subtopic)}
                      className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all transform hover:scale-105 ${
                        (selectedSubtopics[topic] || []).includes(subtopic)
                          ? 'bg-amber-500 text-white shadow-lg'
                          : 'bg-white/20 text-white hover:bg-white/30'
                      }`}
                      style={{
                        fontSize: `${Math.random() * 0.1 + 0.8}rem`,
                        transform: Math.random() > 0.7 ? `rotate(${Math.random() * 3 - 1.5}deg)` : 'none'
                      }}
                    >
                      {subtopic}
                    </button>
                  ))}
                </div>

                <div className="flex justify-between items-center">
                  <button
                    onClick={() => setView("topicSelection")}
                    className="px-4 py-1.5 rounded-lg text-sm font-medium bg-white/10 text-white hover:bg-white/20"
                  >
                    Back
                  </button>
                  <button
                    onClick={handleTopicSubmit}
                    className="px-4 py-1.5 rounded-lg text-sm font-medium bg-amber-500 hover:bg-amber-600 text-white"
                  >
                    Complete
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}