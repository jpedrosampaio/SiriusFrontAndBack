import React, { Suspense, useEffect } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { Toaster, toast } from "@/components/ui/sonner";
import PageTransition from "@/components/PageTransition";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import AuthCallback from "@/pages/AuthCallback";
import ProtectedRoute from "@/components/ProtectedRoute";
import ErrorBoundary from "@/components/ErrorBoundary";
import NotificationManager from "@/components/NotificationManager";
import { GeminiKeyModal } from "@/components/GeminiKeyModal";
import AppShell from "@/components/AppShell";


// Lazy-loaded pages — keeps initial bundle small
const Dashboard = React.lazy(() => import("@/pages/Dashboard"));
const Tasks = React.lazy(() => import("@/pages/Tasks"));
const Habits = React.lazy(() => import("@/pages/Habits"));
const Finance = React.lazy(() => import("@/pages/Finance"));
const Goals = React.lazy(() => import("@/pages/Goals"));
const AgentSettings = React.lazy(() => import("@/pages/AgentSettings"));
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
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<PageTransition><Login /></PageTransition>} />
          <Route path="/register" element={<PageTransition><Register /></PageTransition>} />
          <Route element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
          <Route path="/dashboard" element={<ErrorBoundary><PageTransition><Dashboard /></PageTransition></ErrorBoundary>} />
          <Route path="/tasks" element={<ErrorBoundary><PageTransition><Tasks /></PageTransition></ErrorBoundary>} />
          <Route path="/habits" element={<ErrorBoundary><PageTransition><Habits /></PageTransition></ErrorBoundary>} />
          <Route path="/finance" element={<ErrorBoundary><PageTransition><Finance /></PageTransition></ErrorBoundary>} />
          <Route path="/goals" element={<ErrorBoundary><PageTransition><Goals /></PageTransition></ErrorBoundary>} />
          <Route path="/assistant/settings" element={<ErrorBoundary><PageTransition><AgentSettings /></PageTransition></ErrorBoundary>} />
          <Route path="/chat" element={<ErrorBoundary><PageTransition><Chat /></PageTransition></ErrorBoundary>} />
          <Route path="/reports" element={<ErrorBoundary><PageTransition><Reports /></PageTransition></ErrorBoundary>} />
          <Route path="/profile" element={<ErrorBoundary><PageTransition><Profile /></PageTransition></ErrorBoundary>} />
          <Route path="/workouts" element={<ErrorBoundary><PageTransition><Workouts /></PageTransition></ErrorBoundary>} />
          <Route path="/notifications" element={<ErrorBoundary><PageTransition><Notifications /></PageTransition></ErrorBoundary>} />
          <Route path="/nutrition" element={<ErrorBoundary><PageTransition><Nutrition /></PageTransition></ErrorBoundary>} />
          <Route path="/studies" element={<ErrorBoundary><PageTransition><Studies /></PageTransition></ErrorBoundary>} />
          <Route path="/achievements" element={<ErrorBoundary><PageTransition><Achievements /></PageTransition></ErrorBoundary>} />
          <Route path="/calendar" element={<ErrorBoundary><PageTransition><CalendarPage /></PageTransition></ErrorBoundary>} />
          </Route>
        </Routes>
      </Suspense>
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
      </BrowserRouter>
    </div>
  );
}

export default App;
