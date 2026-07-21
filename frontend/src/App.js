import React, { Suspense } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
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

function App() {
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
