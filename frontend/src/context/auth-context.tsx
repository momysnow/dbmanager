import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from "react";
import axios from "axios";
import { TOKEN_KEY, AUTH_LOGOUT_EVENT } from "@/lib/constants";

interface AuthContextType {
  accessToken: string | null;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [accessToken, setAccessToken] = useState<string | null>(() =>
    localStorage.getItem(TOKEN_KEY),
  );

  const isAuthenticated = !!accessToken;

  const login = useCallback(async (username: string, password: string) => {
    // OAuth2 password grant expects form-encoded body
    const params = new URLSearchParams();
    params.append("username", username);
    params.append("password", password);

    const response = await axios.post("/api/v1/auth/token", params, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });

    const token = response.data.access_token;
    localStorage.setItem(TOKEN_KEY, token);
    setAccessToken(token);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setAccessToken(null);
  }, []);

  // Listen for the custom 401 event dispatched by the axios interceptor in api.ts
  // This avoids a full page reload and properly clears React state
  useEffect(() => {
    window.addEventListener(AUTH_LOGOUT_EVENT, logout);
    return () => window.removeEventListener(AUTH_LOGOUT_EVENT, logout);
  }, [logout]);

  return (
    <AuthContext.Provider
      value={{ accessToken, isAuthenticated, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
