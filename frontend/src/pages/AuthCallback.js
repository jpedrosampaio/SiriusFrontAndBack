import { useEffect, useState, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import axios from "axios";
import { setToken } from "@/lib/api";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function AuthCallback() {
  const navigate = useNavigate();
  const location = useLocation();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const processSession = async () => {
      try {
        const hash = location.hash;
        const sessionId = new URLSearchParams(hash.substring(1)).get('session_id');
        
        if (!sessionId) {
          navigate('/login');
          return;
        }

        const response = await axios.get(`${API}/auth/google-session?session_id=${sessionId}`, {
          withCredentials: true
        });

        // Store token in localStorage for cross-origin/incognito support
        if (response.data.session_token) {
          setToken(response.data.session_token);
        }

        navigate('/dashboard', { state: { user: response.data.user }, replace: true });
      } catch (error) {
        console.error('Auth callback error:', error);
        navigate('/login');
      }
    };

    processSession();
  }, [navigate, location]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#050505]">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#007AFF] mx-auto"></div>
        <p className="mt-4 text-[#A1A1AA]">Autenticando...</p>
      </div>
    </div>
  );
}
