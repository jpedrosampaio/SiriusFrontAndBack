import React, { Suspense, useEffect, useState } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { Toaster, toast } from "@/components/ui/sonner";
import { AnimatePresence } from "framer-motion";
import PageTransition from "@/components/PageTransition";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import AuthCallback from "@/pages/AuthCallback";
import ProtectedRoute from "@/components/ProtectedRoute";
import ErrorBoundary from "@/components/ErrorBoundary";
import NotificationManager from "@/components/NotificationManager";
import { GeminiKeyModal } from "@/components/GeminiKeyModal";
import AiChatModal from "@/components/AiChatModal";
import { X } from "lucide-react";

function SiriusGoldIcon({ size = "w-4 h-4" }) {
  return (
    <svg viewBox="0 0 100 100" className={size}>
      <defs>
        <linearGradient id="goldSiriusGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#FFD700" />
          <stop offset="50%" stopColor="#FF8C00" />
          <stop offset="100%" stopColor="#FFD700" />
        </linearGradient>
        <filter id="goldSiriusGlow">
          <feGaussianBlur stdDeviation="1.5" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>
      <polygon points="31,20 39,41 23,43" fill="url(#goldSiriusGrad)" opacity="0.9"/>
      <polygon points="69,20 61,41 77,43" fill="url(#goldSiriusGrad)" opacity="0.9"/>
      <path d="M50,82 L35,66 L27,51 L28,41 L37,37 L43,43 L50,39 L57,43 L63,37 L72,41 L73,51 L65,66 Z"
            fill="url(#goldSiriusGrad)" filter="url(#goldSiriusGlow)"/>
      <path d="M50,41 L44,47 L39,51 L43,55 L50,53 L57,55 L61,51 L56,47 Z" fill="#050505" opacity="0.35"/>
      <ellipse cx="41" cy="53" rx="4.3" ry="2.8" fill="#050505"/>
      <ellipse cx="59" cy="53" rx="4.3" ry="2.8" fill="#050505"/>
      <ellipse cx="42" cy="53" rx="1.8" ry="1.4" fill="#FFD700" opacity="0.9"/>
      <ellipse cx="60" cy="53" rx="1.8" ry="1.4" fill="#FFD700" opacity="0.9"/>
      <path d="M50,63 L48,65 L50,67 L52,65 Z" fill="#050505"/>
      <line x1="50" y1="67" x2="50" y2="71" stroke="#050505" strokeWidth="0.6"/>
      <polygon points="50,8 51.5,13 56,13 52.5,16 54,21 50,18 46,21 47.5,16 44,13 48.5,13"
               fill="#FFD700" filter="url(#goldSiriusGlow)"/>
      <circle cx="50" cy="14.5" r="1.2" fill="white" opacity="0.7"/>
    </svg>
  );
}

// Lazy-loaded pages — keeps initial bundle small
const Dashboard = React.lazy(() => import("@/pages/Dashboard"));
const Tasks = React.lazy(() => import("@/pages/Tasks"));
const Habits = React.lazy(() => import("@/pages/Habits"));
const Finance = React.lazy(() => import("@/pages/Finance"));
const Goals = React.lazy(() => import("@/pages/Goals"));
const Chat = React.lazy(() => import("@/pages/Chat"));
const Reports = React.lazy(() => import("@/pages/Reports"));
const Profile = React.lazy(() => import("@/pages/Profile"));
const Workouts = React.lazy(() => import("@/pages/Workouts"));
const Notifications = React.lazy(() => import("@/pages/Notifications"));
const Nutrition = React.lazy(() => import("@/pages/Nutrition"));
const Studies = React.lazy(() => import("@/pages/Studies"));
const Achievements = React.lazy(() => import("@/pages/Achievements"));
const CalendarPage = React.lazy(() => import("@/pages/CalendarPage"));

// Loading fallback for lazy pages
function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-[#050505]">
      <div className="flex flex-col items-center gap-4">
        <div className="relative w-12 h-12">
          <div className="absolute inset-0 rounded-full border-2 border-[#27272A]" />
          <div className="absolute inset-0 rounded-full border-2 border-t-[#007AFF] animate-spin" />
        </div>
        <p className="text-sm text-[#52525B] uppercase tracking-widest font-medium">Carregando...</p>
      </div>
    </div>
  );
}

function AnimatedRoutes() {
  const location = useLocation();

  if (location.hash?.includes('session_id=')) {
    return <AuthCallback />;
  }

  return (
    <AnimatePresence mode="wait">
      <Suspense fallback={<PageLoader />}>
        <Routes location={location} key={location.pathname}>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<PageTransition><Login /></PageTransition>} />
          <Route path="/register" element={<PageTransition><Register /></PageTransition>} />
          <Route path="/dashboard" element={<ProtectedRoute><ErrorBoundary><PageTransition><Dashboard /></PageTransition></ErrorBoundary></ProtectedRoute>} />
          <Route path="/tasks" element={<ProtectedRoute><ErrorBoundary><PageTransition><Tasks /></PageTransition></ErrorBoundary></ProtectedRoute>} />
          <Route path="/habits" element={<ProtectedRoute><ErrorBoundary><PageTransition><Habits /></PageTransition></ErrorBoundary></ProtectedRoute>} />
          <Route path="/finance" element={<ProtectedRoute><ErrorBoundary><PageTransition><Finance /></PageTransition></ErrorBoundary></ProtectedRoute>} />
          <Route path="/goals" element={<ProtectedRoute><ErrorBoundary><PageTransition><Goals /></PageTransition></ErrorBoundary></ProtectedRoute>} />
          <Route path="/chat" element={<ProtectedRoute><ErrorBoundary><PageTransition><Chat /></PageTransition></ErrorBoundary></ProtectedRoute>} />
          <Route path="/reports" element={<ProtectedRoute><ErrorBoundary><PageTransition><Reports /></PageTransition></ErrorBoundary></ProtectedRoute>} />
          <Route path="/profile" element={<ProtectedRoute><ErrorBoundary><PageTransition><Profile /></PageTransition></ErrorBoundary></ProtectedRoute>} />
          <Route path="/workouts" element={<ProtectedRoute><ErrorBoundary><PageTransition><Workouts /></PageTransition></ErrorBoundary></ProtectedRoute>} />
          <Route path="/notifications" element={<ProtectedRoute><ErrorBoundary><PageTransition><Notifications /></PageTransition></ErrorBoundary></ProtectedRoute>} />
          <Route path="/nutrition" element={<ProtectedRoute><ErrorBoundary><PageTransition><Nutrition /></PageTransition></ErrorBoundary></ProtectedRoute>} />
          <Route path="/studies" element={<ProtectedRoute><ErrorBoundary><PageTransition><Studies /></PageTransition></ErrorBoundary></ProtectedRoute>} />
          <Route path="/achievements" element={<ProtectedRoute><ErrorBoundary><PageTransition><Achievements /></PageTransition></ErrorBoundary></ProtectedRoute>} />
          <Route path="/calendar" element={<ProtectedRoute><ErrorBoundary><PageTransition><CalendarPage /></PageTransition></ErrorBoundary></ProtectedRoute>} />
        </Routes>
      </Suspense>
    </AnimatePresence>
  );
}

function AiFloatingButton() {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const isPublicPage = ['/', '/login', '/register'].includes(location.pathname);
  if (isPublicPage) return null;
  return (
    <>
      <button
        onClick={() => setOpen(!open)}
        className={`fixed bottom-6 right-6 z-50 flex items-center justify-center w-12 h-12 rounded-2xl border shadow-xl backdrop-blur-xl transition-all duration-300 ${
          open
            ? 'bg-[#0A0A0A] border-[#27272A] text-white scale-95'
            : 'bg-[#0A0A0A]/90 border-[#FFD700]/30 text-white hover:border-[#FFD700]/60 hover:shadow-[#FFD700]/10'
        }`}
        style={{ boxShadow: open ? 'none' : '0 4px 24px rgba(255,215,0,0.12)' }}
      >
        <div className="w-7 h-7 rounded-lg bg-[#050505] flex items-center justify-center">
          {open ? <X className="w-4 h-4 text-[#FFD700]" /> : <SiriusGoldIcon size="w-5 h-5" />}
        </div>
      </button>
      <AiChatModal open={open} onClose={() => setOpen(false)} />
    </>
  );
}

function App() {
  useEffect(() => {
    const handler = (e) => {
      toast.error(e.detail, { duration: 8000 });
    };
    window.addEventListener("gemini-api-error", handler);
    return () => window.removeEventListener("gemini-api-error", handler);
  }, []);

  return (
    <div className="App">
      <BrowserRouter>
        <AnimatedRoutes />
        <NotificationManager />
        <Toaster position="top-right" richColors />
        <GeminiKeyModal />
        <AiFloatingButton />
      </BrowserRouter>
    </div>
  );
}

export default App;
