import { useEffect, useState, useCallback, useRef, useId } from "react"
import { useParams, useNavigate } from "react-router-dom"
import {
  ArrowLeft, RefreshCw, Plug, Shield, RotateCcw, Trash2,
  ShieldCheck, Loader2, CheckCircle2, XCircle, Clock
} from "lucide-react"
import { format, parseISO } from "date-fns"
import { toast } from "sonner"
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from "recharts"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle
} from "@/components/ui/card"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow
} from "@/components/ui/table"
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { databasesApi, backupsApi } from "@/services/api"
import type { DatabaseResponse } from "@/types"

// ── Types ─────────────────────────────────────────────────────────────────────
interface BackupInfo {
  filename: string
  path: string
  size_mb: number
  date: string
  has_checksum: boolean
  location: "local" | "s3"
}

type ConnectionStatus = "unknown" | "checking" | "ok" | "error"

// ── Skeleton ──────────────────────────────────────────────────────────────────
function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-muted ${className ?? ""}`} />
}

// ── Status badge ──────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: ConnectionStatus }) {
  if (status === "checking") return (
    <Badge variant="secondary" className="gap-1">
      <Loader2 className="h-3 w-3 animate-spin" /> Checking…
    </Badge>
  )
  if (status === "ok") return (
    <Badge className="gap-1 bg-green-500/20 text-green-400 border-green-500/30">
      <CheckCircle2 className="h-3 w-3" /> Online
    </Badge>
  )
  if (status === "error") return (
    <Badge variant="destructive" className="gap-1">
      <XCircle className="h-3 w-3" /> Offline
    </Badge>
  )
  return (
    <Badge variant="outline" className="gap-1 text-muted-foreground">
      <Clock className="h-3 w-3" /> Unknown
    </Badge>
  )
}

// ── Chart tooltip ─────────────────────────────────────────────────────────────
function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number }[]; label?: string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-md border bg-background px-3 py-2 text-sm shadow-md">
      <p className="font-medium">{label}</p>
      <p className="text-muted-foreground">{payload[0].value.toFixed(2)} MB</p>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export function DatabaseDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const dbId = Number(id)

  const [db, setDb] = useState<DatabaseResponse | null>(null)
  const [backups, setBackups] = useState<BackupInfo[]>([])
  const [loadingDb, setLoadingDb] = useState(true)
  const [loadingBackups, setLoadingBackups] = useState(true)
  const [connStatus, setConnStatus] = useState<ConnectionStatus>("unknown")
  const [restoring, setRestoring] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [verifying, setVerifying] = useState<string | null>(null)
  const [restoreTarget, setRestoreTarget] = useState<BackupInfo | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<BackupInfo | null>(null)
  const [skipSafetySnapshot, setSkipSafetySnapshot] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const skipSnapshotId = useId()

  // ── Fetch DB info ────────────────────────────────────────────────────────────
  const fetchDb = useCallback(async () => {
    try {
      const res = await databasesApi.getAll()
      const found = res.data.find((d: DatabaseResponse) => d.id === dbId)
      if (!found) { navigate("/databases"); return }
      setDb(found)
    } catch {
      toast.error("Failed to load database info")
    } finally {
      setLoadingDb(false)
    }
  }, [dbId, navigate])

  // ── Fetch backups ────────────────────────────────────────────────────────────
  const fetchBackups = useCallback(async () => {
    setLoadingBackups(true)
    try {
      const res = await backupsApi.listForDatabase(dbId)
      const sorted = [...(res.data as BackupInfo[])].sort(
        (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
      )
      setBackups(sorted)
    } catch {
      setBackups([])
    } finally {
      setLoadingBackups(false)
    }
  }, [dbId])

  // ── Test connection ──────────────────────────────────────────────────────────
  const checkConnection = useCallback(async () => {
    setConnStatus("checking")
    try {
      const res = await databasesApi.test(dbId)
      if (res.data && res.data.success === false) {
          setConnStatus("error")
      } else {
          setConnStatus("ok")
      }
    } catch {
      setConnStatus("error")
    }
  }, [dbId])

  useEffect(() => {
    fetchDb()
    fetchBackups()
    checkConnection()
    // Poll connection every 30s
    pollRef.current = setInterval(checkConnection, 30_000)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [fetchDb, fetchBackups, checkConnection])

  // ── Backup now ───────────────────────────────────────────────────────────────
  const handleBackupNow = async () => {
    try {
      const res = await databasesApi.backup(dbId)
      const taskId = res.data?.task_id
      toast.info("⏳ Backup in corso...")
      if (taskId) {
        const success = await pollTask(taskId, "✅ Backup completato con successo", "Backup fallito")
        if (success) fetchBackups()
      } else {
        toast.success("Backup avviato!")
        setTimeout(fetchBackups, 3000)
      }
    } catch {
      toast.error("Failed to start backup")
    }
  }

  // ── Poll task until done ─────────────────────────────────────────────────────
  const pollTask = useCallback(async (taskId: string, successMsg: string, errorPrefix: string) => {
    const maxAttempts = 60 // 60 * 2s = 2 min timeout
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise(r => setTimeout(r, 2000))
      try {
        const res = await backupsApi.getTaskStatus(taskId)
        const task = res.data
        if (task.status === "completed") {
          toast.success(successMsg)
          return true
        }
        if (task.status === "failed") {
          toast.error(`❌ ${errorPrefix}: ${task.error ?? task.message ?? "Errore sconosciuto"}`)
          return false
        }
        // still running/pending — continue polling
      } catch {
        // ignore transient errors
      }
    }
    toast.error(`❌ ${errorPrefix}: timeout`)
    return false
  }, [])

  // ── Restore ──────────────────────────────────────────────────────────────────
  const handleRestoreConfirmed = async () => {
    if (!restoreTarget) return
    const backup = restoreTarget
    const skip = skipSafetySnapshot
    setRestoreTarget(null)
    setSkipSafetySnapshot(false)
    try {
      setRestoring(backup.path)
      toast.info(`⏳ Restore in corso da ${backup.filename}…`)
      const res = await databasesApi.restore(dbId, backup.path, backup.location, skip)
      const taskId = res.data?.task_id
      if (taskId) {
        await pollTask(taskId, `✅ Restore completato da ${backup.filename}`, "Restore fallito")
      } else {
        toast.success(`✅ Restore avviato da ${backup.filename}`)
      }
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(`❌ Restore fallito: ${detail ?? "Errore sconosciuto"}`)
    } finally {
      setRestoring(null)
    }
  }

  // ── Delete ───────────────────────────────────────────────────────────────────
  const handleDeleteConfirmed = async () => {
    if (!deleteTarget) return
    const backup = deleteTarget
    setDeleteTarget(null)
    try {
      setDeleting(backup.path)
      await backupsApi.delete(backup.path, backup.location, dbId)
      toast.success(`Deleted: ${backup.filename}`)
      setBackups(prev => prev.filter(b => b.path !== backup.path))
    } catch {
      toast.error("Delete failed")
    } finally {
      setDeleting(null)
    }
  }

  // ── Verify ───────────────────────────────────────────────────────────────────
  const handleVerify = async (backup: BackupInfo) => {
    try {
      setVerifying(backup.path)
      const r = await backupsApi.verify(backup.path, backup.location, dbId)
      if (r.data.valid) toast.success(`✅ Integrity OK: ${backup.filename}`)
      else toast.error(`❌ Integrity FAILED: ${backup.filename}`)
    } catch {
      toast.error("Verification failed")
    } finally {
      setVerifying(null)
    }
  }

  // ── Helpers ──────────────────────────────────────────────────────────────────
  const formatSize = (mb: number) => {
    if (mb < 1) return `${(mb * 1024).toFixed(0)} KB`
    if (mb < 1024) return `${mb.toFixed(1)} MB`
    return `${(mb / 1024).toFixed(2)} GB`
  }

  // Chart data: last 10 backups reversed (oldest → newest)
  const chartData = [...backups].reverse().slice(-10).map(b => ({
    name: format(parseISO(b.date), "MMM d HH:mm"),
    size: parseFloat(b.size_mb.toFixed(3)),
  }))

  const totalSize = backups.reduce((s, b) => s + b.size_mb, 0)

  // ── Render ───────────────────────────────────────────────────────────────────
  if (loadingDb) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => <Skeleton key={i} className="h-32" />)}
        </div>
      </div>
    )
  }

  if (!db) return null

  const providerColors: Record<string, string> = {
    postgres: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    mysql: "bg-orange-500/20 text-orange-400 border-orange-500/30",
    mariadb: "bg-teal-500/20 text-teal-400 border-teal-500/30",
    mongodb: "bg-green-500/20 text-green-400 border-green-500/30",
    sqlserver: "bg-red-500/20 text-red-400 border-red-500/30",
  }

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/databases")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-3xl font-bold tracking-tight">{db.name}</h2>
              <Badge className={`capitalize ${providerColors[db.provider] ?? ""}`}>
                {db.provider}
              </Badge>
              <StatusBadge status={connStatus} />
            </div>
            <p className="text-muted-foreground text-sm mt-0.5">
              {db.params.host}:{db.params.port}
              {db.params.database ? ` · ${db.params.database}` : ""}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={checkConnection} disabled={connStatus === "checking"}>
            <Plug className="mr-2 h-4 w-4" /> Test Connection
          </Button>
          <Button size="sm" onClick={handleBackupNow}>
            <Shield className="mr-2 h-4 w-4" /> Backup Now
          </Button>
          <Button variant="outline" size="sm" onClick={() => navigate(`/databases/${dbId}/query`)}>
            <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 3h6l3 3v12a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" />
              <path d="M9 3v4h6V3" />
              <path d="M9 11h6" />
              <path d="M9 15h6" />
            </svg>
            Query
          </Button>
        </div>
      </div>

      {/* ── Stats cards ── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Backups</CardDescription>
            <CardTitle className="text-3xl">{backups.length}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              {backups.filter(b => b.location === "local").length} local ·{" "}
              {backups.filter(b => b.location === "s3").length} S3
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Size</CardDescription>
            <CardTitle className="text-3xl">{formatSize(totalSize)}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              Retention: {db.retention} days local · {db.s3_retention} days S3
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Last Backup</CardDescription>
            <CardTitle className="text-xl">
              {backups.length > 0
                ? format(parseISO(backups[0].date), "MMM d, HH:mm")
                : "Never"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              {backups.length > 0 ? formatSize(backups[0].size_mb) : "—"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* ── Chart ── */}
      {chartData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Backup Size Over Time</CardTitle>
            <CardDescription>Last {chartData.length} backups</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 11 }}
                  className="fill-muted-foreground"
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11 }}
                  className="fill-muted-foreground"
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(v) => `${v}MB`}
                />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="size" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* ── Backups table ── */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Backups</CardTitle>
            <CardDescription>Chronological list — click Restore to recover</CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={fetchBackups} disabled={loadingBackups}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loadingBackups ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>#</TableHead>
                  <TableHead>Filename</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Size</TableHead>
                  <TableHead>Location</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loadingBackups ? (
                  Array.from({ length: 3 }).map((_, i) => (
                    <TableRow key={i}>
                      {Array.from({ length: 6 }).map((_, j) => (
                        <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                      ))}
                    </TableRow>
                  ))
                ) : backups.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                      No backups yet. Click "Backup Now" to create one.
                    </TableCell>
                  </TableRow>
                ) : (
                  backups.map((backup, idx) => {
                    const isRestoring = restoring === backup.path
                    const isDeleting = deleting === backup.path
                    const isVerifying = verifying === backup.path
                    const isBusy = isRestoring || isDeleting || isVerifying
                    const isLatest = idx === 0
                    return (
                      <TableRow key={backup.path} className={isLatest ? "bg-primary/5" : ""}>
                        <TableCell className="text-muted-foreground text-sm">
                          {isLatest ? (
                            <Badge variant="secondary" className="text-xs">Latest</Badge>
                          ) : (
                            `#${backups.length - idx}`
                          )}
                        </TableCell>
                        <TableCell
                          className="font-mono text-xs max-w-[180px] truncate"
                          title={backup.filename}
                        >
                          {backup.filename}
                        </TableCell>
                        <TableCell className="text-sm whitespace-nowrap text-muted-foreground">
                          {format(parseISO(backup.date), "MMM d, yyyy HH:mm")}
                        </TableCell>
                        <TableCell className="text-sm">{formatSize(backup.size_mb)}</TableCell>
                        <TableCell>
                          <div className="flex flex-col gap-0.5">
                            <Badge
                              variant={backup.location === "s3" ? "secondary" : "outline"}
                              className="w-fit text-xs"
                            >
                              {backup.location === "s3" ? "S3" : "Local"}
                            </Badge>
                            {backup.has_checksum && (
                              <span className="text-xs text-green-500 flex items-center gap-1">
                                <ShieldCheck className="h-3 w-3" /> SHA-256
                              </span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-1">
                            {backup.has_checksum && (
                              <Button
                                variant="ghost" size="icon"
                                className="h-7 w-7"
                                onClick={() => handleVerify(backup)}
                                disabled={isBusy}
                                title="Verify integrity"
                              >
                                {isVerifying
                                  ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                  : <ShieldCheck className="h-3.5 w-3.5" />}
                              </Button>
                            )}
                            <Button
                              variant="ghost" size="icon"
                              className="h-7 w-7 text-amber-500 hover:text-amber-600"
                              onClick={() => setRestoreTarget(backup)}
                              disabled={isBusy}
                              title="Restore from this backup"
                            >
                              {isRestoring
                                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                : <RotateCcw className="h-3.5 w-3.5" />}
                            </Button>
                            <Button
                              variant="ghost" size="icon"
                              className="h-7 w-7 text-destructive hover:text-destructive"
                              onClick={() => setDeleteTarget(backup)}
                              disabled={isBusy}
                              title="Delete backup"
                            >
                              {isDeleting
                                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                : <Trash2 className="h-3.5 w-3.5" />}
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* ── DB Info card ── */}
      <Card>
        <CardHeader>
          <CardTitle>Connection Details</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-3 text-sm">
            {[
              ["Host", db.params.host],
              ["Port", String(db.params.port)],
              ["Database", db.params.database ?? "—"],
              ["User", db.params.user ?? "—"],
              ["Provider", db.provider],
              ["S3 Enabled", db.s3_enabled ? "Yes" : "No"],
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="text-muted-foreground">{label}</dt>
                <dd className="font-medium capitalize">{value}</dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>

      {/* ── Restore confirm ── */}
      <AlertDialog open={!!restoreTarget} onOpenChange={(open: boolean) => { if (!open) { setRestoreTarget(null); setSkipSafetySnapshot(false) } }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Restore database?</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div>
                <p>
                  Ripristinerà <span className="font-semibold text-foreground">"{db.name}"</span> dal backup{" "}
                  <span className="font-semibold text-foreground break-all">"{restoreTarget?.filename}"</span>.
                </p>
                <p className="mt-2">
                  <span className="text-amber-500 font-medium">⚠️ Attenzione:</span> I dati correnti verranno sovrascritti.
                </p>
                <div className="mt-4 rounded-md border border-muted bg-muted/30 p-3">
                  <p className="text-xs text-muted-foreground mb-2">
                    Di default viene creato uno snapshot di sicurezza prima del restore (richiede che il DB sia raggiungibile).
                    Se il DB è offline o non raggiungibile, spunta l'opzione qui sotto.
                  </p>
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id={skipSnapshotId}
                      checked={skipSafetySnapshot}
                      onCheckedChange={(v) => setSkipSafetySnapshot(!!v)}
                    />
                    <Label htmlFor={skipSnapshotId} className="text-sm cursor-pointer">
                      Salta lo snapshot di sicurezza pre-restore
                      <span className="ml-1 text-xs text-muted-foreground">(più veloce, meno sicuro)</span>
                    </Label>
                  </div>
                </div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setSkipSafetySnapshot(false)}>Annulla</AlertDialogCancel>
            <AlertDialogAction
              className="bg-amber-500 text-white hover:bg-amber-600"
              onClick={handleRestoreConfirmed}
            >
              Ripristina
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* ── Delete confirm ── */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(open: boolean) => { if (!open) setDeleteTarget(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete backup?</AlertDialogTitle>
            <AlertDialogDescription>
              Permanently delete{" "}
              <span className="font-semibold text-foreground break-all">"{deleteTarget?.filename}"</span>?
              This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={handleDeleteConfirmed}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
