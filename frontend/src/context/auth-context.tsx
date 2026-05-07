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

export type UserRole = "admin" | "operator" | "viewer";

export interface CurrentUser {
  id: number;
  username: string;
  role: UserRole;
  is_active: boolean;
  must_change_password: boolean;
  last_login_at: string | null;
}

interface AuthContextType {
  accessToken: string | null;
  isAuthenticated: boolean;
  user: CurrentUser | null;
  role: UserRole | null;
  hasRole: (roles: UserRole[]) => boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [accessToken, setAccessToken] = useState<string | null>(() =>
    localStorage.getItem(TOKEN_KEY),
  );
  const [user, setUser] = useState<CurrentUser | null>(null);

  const isAuthenticated = !!accessToken;
  const role = user?.role ?? null;

  const hasRole = useCallback(
    (roles: UserRole[]) => (role ? roles.includes(role) : false),
    [role],
  );

  const fetchMe = useCallback(async (token: string) => {
    try {
      const res = await axios.get<CurrentUser>("/api/v1/auth/me", {
        headers: { Authorization: `Bearer ${token}` },
      });
      setUser(res.data);
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    if (accessToken) {
      fetchMe(accessToken);
    } else {
      setUser(null);
    }
  }, [accessToken, fetchMe]);

  const login = useCallback(async (username: string, password: string) => {
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
    setUser(null);
  }, []);

  useEffect(() => {
    window.addEventListener(AUTH_LOGOUT_EVENT, logout);
    return () => window.removeEventListener(AUTH_LOGOUT_EVENT, logout);
  }, [logout]);

  return (
    <AuthContext.Provider
      value={{ accessToken, isAuthenticated, user, role, hasRole, login, logout }}
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
