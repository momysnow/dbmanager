import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth, type UserRole } from "@/context/auth-context";

interface RoleGuardProps {
  roles: UserRole[];
  children: ReactNode;
  fallback?: ReactNode;
  redirect?: string;
}

export function RoleGuard({ roles, children, fallback, redirect }: RoleGuardProps) {
  const { hasRole } = useAuth();

  if (!hasRole(roles)) {
    if (redirect) return <Navigate to={redirect} replace />;
    if (fallback) return <>{fallback}</>;
    return null;
  }

  return <>{children}</>;
}
