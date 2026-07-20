import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import axios from "axios";
import { getToken, clearToken } from "@/lib/api";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function ProtectedRoute({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(null);
  const [user, setUser] = useState(null);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (location.state?.user) {
      setIsAuthenticated(true);
      setUser(location.state.user);
      return;
    }

    const checkAuth = async () => {
      try {
        // Token is automatically added by axios interceptor from api.js
        const response = await axios.get(`${API}/auth/me`, {
          withCredentials: true
        });
        setIsAuthenticated(true);
        setUser(response.data);
      } catch (error) {
        clearToken();
        setIsAuthenticated(false);
        navigate('/login');
      }
    };

    // Check if we have a token (cookie or localStorage)
    const hasToken = getToken();
    if (!hasToken) {
      // No token in localStorage, still try with cookies
      checkAuth();
    } else {
      checkAuth();
    }
  }, [navigate, location]);

  if (isAuthenticated === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#050505]">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#007AFF]"></div>
      </div>
    );
  }

  return isAuthenticated ? children : null;
}
