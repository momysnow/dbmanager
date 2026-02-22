import { useEffect, useState } from "react"
import { Activity, Database, HardDrive, ShieldCheck, CheckCircle2, XCircle, AlertCircle } from "lucide-react"
import { dashboardApi } from "@/services/api"
import { format } from "date-fns"

// ── Skeleton helper ──────────────────────────────────────────────────────────
function Skeleton({ className }: { className?: string }) {
  return (
    <div className={`animate-pulse rounded bg-muted ${className ?? ""}`} />
  )
}

// ── Stats card ───────────────────────────────────────────────────────────────
interface StatsCardProps {
  title: string
  value: string | number
  icon: React.ElementType
  description: string
  loading?: boolean
}

function StatsCard({ title, value, icon: Icon, description, loading }: StatsCardProps) {
  return (
    <div className="rounded-xl border bg-card text-card-foreground shadow-sm">
      <div className="p-6 flex flex-row items-center justify-between space-y-0 pb-2">
        <h3 className="tracking-tight text-sm font-medium">{title}</h3>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <div className="p-6 pt-0">
        {loading ? (
          <>
            <Skeleton className="h-8 w-16 mb-1" />
            <Skeleton className="h-3 w-24" />
          </>
        ) : (
          <>
            <div className="text-2xl font-bold">{value}</div>
            <p className="text-xs text-muted-foreground">{description}</p>
          </>
        )}
      </div>
    </div>
  )
}

// ── Types ────────────────────────────────────────────────────────────────────
interface OverviewStats {
  total_databases: number
  total_backups: number
  total_backup_size_mb: number
  total_s3_buckets: number
  total_schedules: number
  active_schedules: number
}

interface HealthData {
  status: "healthy" | "warning" | "critical"
  issues: string[]
  warnings: string[]
}

interface DatabaseHealth {
  id: number
  name: string
  provider: string
  backup_count: number
  last_backup?: string | null
  size_mb: number
}

interface RecentBackup {
  database: string
  date: string
  size_mb: number
}

// ── Health badge ─────────────────────────────────────────────────────────────
function HealthBadge({ status }: { status: "healthy" | "warning" | "critical" }) {
  if (status === "healthy")
    return <span className="flex items-center gap-1 text-xs text-green-500"><CheckCircle2 className="h-3.5 w-3.5" />Healthy</span>
  if (status === "warning")
    return <span className="flex items-center gap-1 text-xs text-yellow-500"><AlertCircle className="h-3.5 w-3.5" />Warning</span>
  return <span className="flex items-center gap-1 text-xs text-red-500"><XCircle className="h-3.5 w-3.5" />Critical</span>
}

// ── Main page ─────────────────────────────────────────────────────────────────
export function DashboardPage() {
  const [stats, setStats] = useState<OverviewStats>({
    total_databases: 0,
    total_backups: 0,
    total_backup_size_mb: 0,
    total_s3_buckets: 0,
    total_schedules: 0,
    active_schedules: 0,
  })
  const [health, setHealth] = useState<HealthData | null>(null)
  const [dbHealth, setDbHealth] = useState<DatabaseHealth[]>([])
  const [recentActivity, setRecentActivity] = useState<RecentBackup[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [overviewRes, recentRes, healthRes, dbRes] = await Promise.all([
          dashboardApi.getOverview(),
          dashboardApi.getRecentActivity(),
          dashboardApi.getHealth(),
          dashboardApi.getDatabases(),
        ])
        setStats(overviewRes.data)
        setRecentActivity(recentRes.data.recent_backups || [])
        setHealth(healthRes.data)
        setDbHealth(dbRes.data || [])
      } catch (error) {
        console.error("Failed to fetch dashboard data", error)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  const formatSize = (mb: number) => {
    if (mb < 1024) return `${mb.toFixed(1)} MB`
    return `${(mb / 1024).toFixed(2)} GB`
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between space-y-2">
        <h2 className="text-3xl font-bold tracking-tight">Dashboard</h2>
      </div>

      {/* ── Stats cards ── */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatsCard
          title="Total Databases"
          value={stats.total_databases}
          icon={Database}
          description="Active databases"
          loading={loading}
        />
        <StatsCard
          title="Total Backups"
          value={stats.total_backups}
          icon={ShieldCheck}
          description="Stored backups"
          loading={loading}
        />
        <StatsCard
          title="Storage Usage"
          value={formatSize(stats.total_backup_size_mb)}
          icon={HardDrive}
          description="Total space used"
          loading={loading}
        />
        <StatsCard
          title="S3 Buckets"
          value={stats.total_s3_buckets}
          icon={Activity}
          description={`${stats.active_schedules} active schedules`}
          loading={loading}
        />
      </div>

      {/* ── Bottom row ── */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">

        {/* System Health Overview */}
        <div className="col-span-4 rounded-xl border bg-card text-card-foreground shadow-sm">
          <div className="flex flex-col space-y-1.5 p-6 pb-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold leading-none tracking-tight">System Health</h3>
              {health && !loading && <HealthBadge status={health.status} />}
            </div>
            <p className="text-sm text-muted-foreground">Database status overview</p>
          </div>
          <div className="p-6 pt-0">
            {loading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="flex items-center justify-between">
                    <Skeleton className="h-4 w-32" />
                    <Skeleton className="h-4 w-16" />
                  </div>
                ))}
              </div>
            ) : dbHealth.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">No databases configured</p>
            ) : (
              <div className="space-y-3">
                {/* Issues & warnings */}
                {health && health.issues.length > 0 && (
                  <div className="rounded-md bg-destructive/10 border border-destructive/20 p-3 mb-3">
                    <p className="text-xs font-medium text-destructive mb-1">Issues</p>
                    {health.issues.map((issue, i) => (
                      <p key={i} className="text-xs text-destructive/80">• {issue}</p>
                    ))}
                  </div>
                )}
                {health && health.warnings.length > 0 && (
                  <div className="rounded-md bg-yellow-500/10 border border-yellow-500/20 p-3 mb-3">
                    <p className="text-xs font-medium text-yellow-600 dark:text-yellow-400 mb-1">Warnings</p>
                    {health.warnings.map((w, i) => (
                      <p key={i} className="text-xs text-yellow-600/80 dark:text-yellow-400/80">• {w}</p>
                    ))}
                  </div>
                )}
                {/* Per-database table */}
                <div className="divide-y divide-border">
                  {dbHealth.map((db) => (
                    <div key={db.id} className="flex items-center justify-between py-2">
                      <div>
                        <p className="text-sm font-medium">{db.name}</p>
                        <p className="text-xs text-muted-foreground capitalize">{db.provider}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-xs text-muted-foreground">
                          {db.backup_count} backup{db.backup_count !== 1 ? "s" : ""}
                          {db.size_mb > 0 ? ` · ${formatSize(db.size_mb)}` : ""}
                        </p>
                        {db.last_backup ? (
                          <p className="text-xs text-muted-foreground">
                            Last: {format(new Date(db.last_backup), "MMM d, HH:mm")}
                          </p>
                        ) : (
                          <p className="text-xs text-destructive/70">No backups</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Recent Backups */}
        <div className="col-span-3 rounded-xl border bg-card text-card-foreground shadow-sm">
          <div className="flex flex-col space-y-1.5 p-6 pb-3">
            <h3 className="font-semibold leading-none tracking-tight">Recent Backups</h3>
            <p className="text-sm text-muted-foreground">Latest backup activity</p>
          </div>
          <div className="p-6 pt-0">
            {loading ? (
              <div className="space-y-4">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="flex items-center justify-between">
                    <div className="space-y-1">
                      <Skeleton className="h-4 w-24" />
                      <Skeleton className="h-3 w-32" />
                    </div>
                    <Skeleton className="h-4 w-12" />
                  </div>
                ))}
              </div>
            ) : recentActivity.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">No recent backups</p>
            ) : (
              <div className="space-y-4">
                {recentActivity.map((activity, i) => (
                  <div key={i} className="flex items-center">
                    <div className="space-y-1">
                      <p className="text-sm font-medium leading-none">{activity.database}</p>
                      <p className="text-xs text-muted-foreground">
                        {format(new Date(activity.date), "PPP p")}
                      </p>
                    </div>
                    <div className="ml-auto text-sm font-medium">
                      +{activity.size_mb.toFixed(1)} MB
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
