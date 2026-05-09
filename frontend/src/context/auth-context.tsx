import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from "react";
import api, { authApi } from "@/services/api";
import { AUTH_LOGOUT_EVENT } from "@/lib/constants";

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
  isAuthenticated: boolean;
  isLoading: boolean;
  user: CurrentUser | null;
  role: UserRole | null;
  hasRole: (roles: UserRole[]) => boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  // Auth is unknown until the first /me probe completes — gate protected
  // routes on isLoading so we don't briefly flash the authenticated UI to a
  // logged-out user (or vice versa).
  const [isLoading, setIsLoading] = useState(true);

  const isAuthenticated = !!user;
  const role = user?.role ?? null;

  const hasRole = useCallback(
    (roles: UserRole[]) => (role ? roles.includes(role) : false),
    [role],
  );

  const fetchMe = useCallback(async () => {
    try {
      const res = await authApi.me();
      setUser(res.data as CurrentUser);
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMe();
  }, [fetchMe]);

  const login = useCallback(
    async (username: string, password: string) => {
      const params = new URLSearchParams();
      params.append("username", username);
      params.append("password", password);

      // Cookie is set by the backend on success; nothing to store client-side.
      await api.post("/auth/token", params, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
      await fetchMe();
    },
    [fetchMe],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // Ignore — even if the backend call fails we still clear local state.
    }
    setUser(null);
  }, []);

  useEffect(() => {
    const handler = () => {
      setUser(null);
    };
    window.addEventListener(AUTH_LOGOUT_EVENT, handler);
    return () => window.removeEventListener(AUTH_LOGOUT_EVENT, handler);
  }, []);

  return (
    <AuthContext.Provider
      value={{ isAuthenticated, isLoading, user, role, hasRole, login, logout }}
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
