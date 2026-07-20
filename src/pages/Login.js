import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Shield, Mail, Lock, Chrome, Wifi, WifiOff } from "lucide-react";
import { SiriusLogo } from "@/components/Sidebar";
import axios from "axios";
import { toast } from "sonner";
import { setToken, getOfflineUser, getOfflineData, isOfflineMode, OFFLINE_MODE } from "@/lib/api";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleOfflineLogin = () => {
    localStorage.setItem('sirius_offline_user', JSON.stringify(getOfflineUser()));
    localStorage.setItem('sirius_offline_data', JSON.stringify(getOfflineData()));
    setToken('offline_token');
    toast.success("Modo offline ativado!");
    navigate('/dashboard', { state: { user: getOfflineUser() } });
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const response = await axios.post(`${API}/auth/login`, { email, password }, {
        withCredentials: true
      });
      // Store token in localStorage for cross-origin/incognito support
      if (response.data.session_token) {
        setToken(response.data.session_token);
      }
      toast.success("Login realizado com sucesso!");
      navigate('/dashboard', { state: { user: response.data.user } });
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erro ao fazer login");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + '/dashboard';
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen bg-[#050505] flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <SiriusLogo size="w-16 h-16 mx-auto mb-4" />
          <h1 className="font-heading text-4xl mb-2">SIRIUS</h1>
          <p className="text-[#A1A1AA]">Entre no sistema de comando</p>
        </div>

        <div className="bg-[#0A0A0A] border border-[#27272A] p-8 rounded-sm">
          <form onSubmit={handleLogin} className="space-y-6">
            <div>
              <Label htmlFor="email" className="text-[#FFFFFF] uppercase text-xs tracking-wider mb-2 block">
                E-mail
              </Label>
              <div className="relative">
                <Mail className="absolute left-3 top-3 w-5 h-5 text-[#52525B]" />
                <Input
                  id="email"
                  data-testid="login-email-input"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="pl-10 bg-[#121212] border-[#27272A] text-white font-mono"
                  required
                />
              </div>
            </div>

            <div>
              <Label htmlFor="password" className="text-[#FFFFFF] uppercase text-xs tracking-wider mb-2 block">
                Senha
              </Label>
              <div className="relative">
                <Lock className="absolute left-3 top-3 w-5 h-5 text-[#52525B]" />
                <Input
                  id="password"
                  data-testid="login-password-input"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-10 bg-[#121212] border-[#27272A] text-white font-mono"
                  required
                />
              </div>
            </div>

            <Button
              data-testid="login-submit-btn"
              type="submit"
              disabled={loading}
              className="w-full bg-[#007AFF] hover:bg-[#0062CC] uppercase text-xs tracking-widest shadow-[0_0_10px_rgba(0,122,255,0.3)]"
            >
              {loading ? "AUTENTICANDO..." : "ENTRAR"}
            </Button>

            {OFFLINE_MODE && (
              <Button
                type="button"
                onClick={handleOfflineLogin}
                variant="outline"
                className="w-full mt-3 border-[#27272A] hover:bg-[#121212] uppercase text-xs tracking-widest"
              >
                <Wifi className="w-4 h-4 mr-2" />
                Modo Offline (Teste)
              </Button>
            )}
          </form>

          <div className="mt-6">
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-[#27272A]"></div>
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-[#0A0A0A] px-2 text-[#A1A1AA]">Ou</span>
              </div>
            </div>

            <Button
              data-testid="login-google-btn"
              type="button"
              onClick={handleGoogleLogin}
              variant="outline"
              className="w-full mt-6 border-[#27272A] hover:bg-[#121212] uppercase text-xs tracking-widest"
            >
              <Chrome className="w-5 h-5 mr-2" />
              Entrar com Google
            </Button>
          </div>

          <p className="mt-6 text-center text-sm text-[#A1A1AA]">
            Não tem conta?{" "}
            <Link to="/register" className="text-[#007AFF] hover:underline">
              Registrar-se
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
