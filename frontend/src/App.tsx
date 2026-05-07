import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom"
import { useEffect } from "react"
import { ThemeProvider } from "@/components/theme-provider"
import { AuthProvider, useAuth } from "@/context/auth-context"
import { Layout } from "@/components/layout/layout"
import { Toaster } from "@/components/ui/sonner"
import { toast } from "sonner"

import { RoleGuard } from "@/components/RoleGuard"
import UsersPage from "@/pages/users/page"
import AuditPage from "@/pages/audit/page"
import ChangePasswordPage from "@/pages/change-password/page"

// Pages
import { LoginPage } from "@/pages/login/page"
import { DashboardPage } from "@/pages/dashboard/page"
import { DatabasesPage } from "@/pages/databases/page"
import { StoragePage } from "@/pages/storage/page"
import { SchedulesPage } from "@/pages/schedules/page"
import { SettingsPage } from "@/pages/settings/page"
import { BackupsPage } from "@/pages/backups/page"
import { DatabaseDetailPage } from "@/pages/databases/detail"
import QueryPage from "@/pages/query/page"

function ForbiddenToastListener() {
  useEffect(() => {
    const handler = (e: Event) => {
      const msg = (e as CustomEvent).detail ?? "Insufficient permissions"
      toast.error(msg)
    }
    window.addEventListener("auth:forbidden", handler)
    return () => window.removeEventListener("auth:forbidden", handler)
  }, [])
  return null
}

function ProtectedRoutes() {
  const { isAuthenticated, user } = useAuth()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (user?.must_change_password) {
    return (
      <Routes>
        <Route path="*" element={<ChangePasswordPage />} />
      </Routes>
    )
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/databases" element={<DatabasesPage />} />
        <Route path="/databases/:id" element={<DatabaseDetailPage />} />
        <Route path="/query" element={<QueryPage />} />
        <Route path="/storage" element={<StoragePage />} />
        <Route path="/backups" element={<BackupsPage />} />
        <Route path="/schedules" element={<SchedulesPage />} />
        <Route path="/settings" element={
          <RoleGuard roles={["admin"]} redirect="/">
            <SettingsPage />
          </RoleGuard>
        } />
        <Route path="/users" element={
          <RoleGuard roles={["admin"]} redirect="/">
            <UsersPage />
          </RoleGuard>
        } />
        <Route path="/audit" element={
          <RoleGuard roles={["admin"]} redirect="/">
            <AuditPage />
          </RoleGuard>
        } />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function AppRoutes() {
  const { isAuthenticated } = useAuth()

  return (
    <Routes>
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route path="/*" element={<ProtectedRoutes />} />
    </Routes>
  )
}

function App() {
  return (
    <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
      <BrowserRouter>
        <AuthProvider>
          <ForbiddenToastListener />
          <AppRoutes />
          <Toaster />
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  )
}

export default App
