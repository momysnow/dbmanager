import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom"
import { ThemeProvider } from "@/components/theme-provider"
import { AuthProvider, useAuth } from "@/context/auth-context"
import { Layout } from "@/components/layout/layout"
import { Toaster } from "@/components/ui/sonner"

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

function ProtectedRoutes() {
  const { isAuthenticated } = useAuth()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
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
        <Route path="/settings" element={<SettingsPage />} />
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
          <AppRoutes />
          <Toaster />
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  )
}

export default App
