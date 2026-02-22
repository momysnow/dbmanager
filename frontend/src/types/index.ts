export type DatabaseProvider = "postgres" | "mysql" | "mariadb" | "sqlserver" | "mongodb"

export interface ConnectionParams {
  host: string
  port: number
  database?: string
  user?: string
  password?: string
  trust_certificate?: boolean
  driver?: string
  [key: string]: unknown
}

export interface DatabaseResponse {
  id: number
  name: string
  provider: DatabaseProvider
  params: {
    host: string
    port: number
    database?: string
    user?: string
    trust_certificate?: boolean
    driver?: string
    [key: string]: unknown
  }
  s3_enabled: boolean
  s3_bucket_id?: number | null
  storage_target_ids: number[]
  retention: number
  s3_retention: number
}

export type StorageProviderType = "aws" | "minio" | "cloudflare" | "garage" | "s3" | "other" | "smb"

export interface StorageResponse {
  id: number
  name: string
  provider: StorageProviderType
  // S3 fields
  endpoint_url?: string | null
  bucket?: string | null
  region?: string | null
  // SMB fields
  server?: string | null
  share_name?: string | null
  domain?: string | null
  remote_path?: string | null
}

export interface ScheduleResponse {
  id: number
  database_id: number
  cron_expression: string
  enabled: boolean
  next_run?: string | null
  last_run?: string | null
}

export interface BackupJob {
  id: string
  database_id: number
  status: "pending" | "running" | "success" | "failed"
  file_path?: string
  size_bytes?: number
  created_at: string
  completed_at?: string
  error?: string
}
