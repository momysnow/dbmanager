import axios from "axios"
import type { DatabaseResponse, StorageResponse, ScheduleResponse } from "@/types"
import { AUTH_LOGOUT_EVENT } from "@/lib/constants"

// withCredentials: cookies (httpOnly session) are sent automatically.
// X-Requested-With: required by the backend on state-changing requests as a
// CSRF guard. Browsers refuse to set this header cross-origin without a
// CORS preflight, and our backend CORS allow-list is explicit.
const api = axios.create({
  baseURL: "/api/v1",
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
  },
})

// On 401: dispatch a custom event so AuthProvider can drop user state without
// a full page reload (preserves React context).
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      window.dispatchEvent(new Event(AUTH_LOGOUT_EVENT))
    }
    if (error.response?.status === 403) {
      window.dispatchEvent(new CustomEvent("auth:forbidden", {
        detail: error.response?.data?.detail ?? "Insufficient permissions",
      }))
    }
    return Promise.reject(error)
  }
)

export const databasesApi = {
  getAll: () => api.get<DatabaseResponse[]>("/databases"),
  create: (data: Record<string, unknown>) => api.post<DatabaseResponse>("/databases", data),
  update: (id: number, data: Record<string, unknown>) => api.put<DatabaseResponse>(`/databases/${id}`, data),
  delete: (id: number) => api.delete(`/databases/${id}`),
  backup: (id: number) => api.post(`/databases/${id}/backup`),
  restore: (id: number, backupFile: string, location: "local" | "s3" = "local", skipSafetySnapshot = false) =>
    api.post(`/databases/${id}/restore`, { backup_file: backupFile, location, skip_safety_snapshot: skipSafetySnapshot }),
  test: (id: number) => api.post(`/databases/${id}/test`),
  listBackups: (id: number, location?: "local" | "s3") =>
    api.get(`/databases/${id}/backups${location ? `?location=${location}` : ""}`),
  getUptime: (id: number, period: "day" | "week" | "month" | "year") =>
    api.get(`/databases/${id}/uptime?period=${period}`),
}

export const backupMetadataApi = {
  get: (filename: string) => api.get(`/backups/metadata/${encodeURIComponent(filename)}`),
  update: (data: { filename: string; notes?: string; starred?: boolean }) =>
    api.patch("/backups/metadata", data),
}

export const exportApi = {
  getConfig: () => api.get("/export/config"),
  getDockerCompose: () => api.get("/export/docker-compose", { responseType: "text" as const }),
  getEnv: () => api.get("/export/env", { responseType: "text" as const }),
}

export const storageApi = {
  getAll: () => api.get<StorageResponse[]>("/storage"),
  create: (data: Record<string, unknown>) => api.post<StorageResponse>("/storage", data),
  update: (id: number, data: Record<string, unknown>) => api.put<StorageResponse>(`/storage/${id}`, data),
  delete: (id: number) => api.delete(`/storage/${id}`),
  test: (id: number) => api.post(`/storage/${id}/test`),
}

export const schedulesApi = {
  getAll: () => api.get<ScheduleResponse[]>("/schedules"),
  create: (data: Record<string, unknown>) => api.post<ScheduleResponse>("/schedules", data),
  update: (id: number, data: Record<string, unknown>) => api.put<ScheduleResponse>(`/schedules/${id}`, data),
  delete: (id: number) => api.delete(`/schedules/${id}`),
  toggle: (id: number) => api.post<ScheduleResponse>(`/schedules/${id}/toggle`),
}

export const settingsApi = {
  getAll: () => api.get("/settings"),
  getCompression: () => api.get("/settings/compression"),
  updateCompression: (data: Record<string, unknown>) => api.put("/settings/compression", data),
  getEncryption: () => api.get("/settings/encryption"),
  updateEncryption: (data: Record<string, unknown>) => api.put("/settings/encryption", data),
  syncConfig: () => api.post("/settings/config-sync/sync"),
  getConfigSync: () => api.get("/settings/config-sync"),
  updateConfigSync: (data: Record<string, unknown>) => api.put("/settings/config-sync", data),
}

export const notificationsApi = {
  getAll: () => api.get("/notifications"),
  getEmail: () => api.get("/notifications/email"),
  updateEmail: (data: Record<string, unknown>) => api.put("/notifications/email", data),
  getWebhook: (provider: "slack" | "teams" | "discord") => api.get(`/notifications/${provider}`),
  updateWebhook: (provider: "slack" | "teams" | "discord", data: Record<string, unknown>) =>
    api.put(`/notifications/${provider}`, data),
  test: () => api.post("/notifications/test"),
}

export const dashboardApi = {
  getOverview: () => api.get("/dashboard/overview"),
  getRecentActivity: (days = 7) => api.get(`/dashboard/recent?days=${days}`),
  getStorageBreakdown: () => api.get("/dashboard/storage"),
  getHealth: () => api.get("/dashboard/health"),
  getDatabases: () => api.get("/dashboard/databases"),
}

export const backupsApi = {
  listForDatabase: (dbId: number, location?: "local" | "s3") =>
    api.get(`/databases/${dbId}/backups${location ? `?location=${location}` : ""}`),
  delete: (backupFile: string, location: "local" | "s3" = "local", databaseId?: number) =>
    api.delete(`/backups?backup_file=${encodeURIComponent(backupFile)}&location=${location}${databaseId ? `&database_id=${databaseId}` : ""}`),
  verify: (backupFile: string, location: "local" | "s3" = "local", databaseId?: number) =>
    api.post("/backups/verify", { backup_file: backupFile, location, database_id: databaseId }),
  getTaskStatus: (taskId: string) => api.get(`/tasks/${taskId}`),
}

export const usersApi = {
  getAll: (skip = 0, limit = 100) => api.get(`/users?skip=${skip}&limit=${limit}`),
  create: (data: { username: string; password: string; role: string }) =>
    api.post("/users", data),
  update: (id: number, data: { role?: string; is_active?: boolean }) =>
    api.patch(`/users/${id}`, data),
  resetPassword: (id: number, newPassword: string) =>
    api.post(`/users/${id}/reset-password`, { new_password: newPassword }),
  delete: (id: number) => api.delete(`/users/${id}`),
}

export type ProxyConfig = {
  enabled: boolean
  mode: "disabled" | "http" | "https"
  domain: string
  acme: {
    method: "none" | "dns" | "http-01" | "manual" | "selfsigned"
    email: string
    dns_provider: "cloudflare" | "route53" | "digitalocean" | "gandi" | "duckdns" | null
    credentials_env: string | null
  }
  manual_cert: { cert_path: string; key_path: string }
  routes: { frontend_upstream: string; backend_upstream: string; backend_path_prefix: string }
  admin_url: string
  caddy_container: string
}

export const proxyApi = {
  getConfig: () => api.get<ProxyConfig>("/proxy/config"),
  putConfig: (data: ProxyConfig) => api.put("/proxy/config", data),
  getStatus: () => api.get("/proxy/status"),
  reload: () => api.post("/proxy/reload"),
  restart: () => api.post("/proxy/restart"),
}

// Settings export/import — full config + proxy round-trip in one zip.
export const configIoApi = {
  exportZip: () =>
    api.post("/settings/export", undefined, { params: { format: "zip", include_backups: false }, responseType: "blob" }),
  exportZipWithBackups: () =>
    api.post("/settings/export", undefined, { params: { format: "zip", include_backups: true }, responseType: "blob" }),
  exportJson: () =>
    api.post("/settings/export", undefined, { params: { format: "json" }, responseType: "blob" }),
  importFile: (file: File, merge = false, restoreBackups = false) => {
    const fd = new FormData()
    fd.append("file", file)
    return api.post("/settings/import", fd, {
      params: { merge, restore_backups: restoreBackups },
      headers: { "Content-Type": "multipart/form-data" },
    })
  },
}

export const auditApi = {
  getLogs: (params?: {
    user_id?: number
    action?: string
    resource_type?: string
    status?: string
    from?: string
    to?: string
    limit?: number
    offset?: number
  }) => api.get("/audit-logs", { params }),
  getActions: () => api.get<string[]>("/audit-logs/actions"),
}

export const authApi = {
  me: () => api.get("/auth/me"),
  logout: () => api.post("/auth/logout"),
}

export default api
