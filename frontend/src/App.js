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
import { Brain, X } from "lucide-react";

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
        className={`fixed bottom-20 right-4 z-50 w-12 h-12 rounded-2xl flex items-center justify-center shadow-lg transition-all duration-300 ${
          open
            ? 'bg-[#FFD700] text-black rotate-45 scale-110'
            : 'bg-gradient-to-br from-[#FFD700] to-[#FF8C00] text-black hover:scale-105'
        }`}
      >
        {open ? <X className="w-5 h-5" /> : <Brain className="w-5 h-5" />}
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
