import axios from "axios"
import type { DatabaseResponse, StorageResponse, ScheduleResponse } from "@/types"
import { TOKEN_KEY, AUTH_LOGOUT_EVENT } from "@/lib/constants"

const api = axios.create({
  baseURL: "/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
})

// Attach bearer token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// On 401: remove token and dispatch a custom event so AuthProvider can react
// without a full page reload (preserves React state/context)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      window.dispatchEvent(new Event(AUTH_LOGOUT_EVENT))
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

export default api
