import { useEffect, useState, useCallback } from "react"
import { auditApi } from "@/services/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { toast } from "sonner"
import { ChevronLeft, ChevronRight, Eye } from "lucide-react"

interface AuditLog {
  id: number
  timestamp: string
  user_id: number | null
  username_snapshot: string | null
  action: string
  resource_type: string | null
  resource_id: string | null
  status: "success" | "failure" | "denied"
  ip: string | null
  user_agent: string | null
  details: Record<string, unknown> | null
}

const PAGE_SIZE = 50

const STATUS_VARIANT: Record<string, "default" | "destructive" | "secondary" | "outline"> = {
  success: "outline",
  failure: "destructive",
  denied: "secondary",
}

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const [actions, setActions] = useState<string[]>([])
  const [selected, setSelected] = useState<AuditLog | null>(null)

  // Filters
  const [filterAction, setFilterAction] = useState("all")
  const [filterStatus, setFilterStatus] = useState("all")
  const [filterResourceType, setFilterResourceType] = useState("")
  const [filterFrom, setFilterFrom] = useState("")
  const [filterTo, setFilterTo] = useState("")

  const loadLogs = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, unknown> = {
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }
      if (filterAction && filterAction !== "all") params.action = filterAction
      if (filterStatus && filterStatus !== "all") params.status = filterStatus
      if (filterResourceType) params.resource_type = filterResourceType
      if (filterFrom) params.from = filterFrom
      if (filterTo) params.to = filterTo

      const res = await auditApi.getLogs(params as Parameters<typeof auditApi.getLogs>[0])
      setLogs(res.data.logs)
      setTotal(res.data.total)
    } catch {
      toast.error("Failed to load audit logs")
    } finally {
      setLoading(false)
    }
  }, [page, filterAction, filterStatus, filterResourceType, filterFrom, filterTo])

  useEffect(() => {
    auditApi
      .getActions()
      .then((res) => setActions(res.data))
      .catch((err) => {
        console.error("Failed to load audit actions:", err)
      })
  }, [])

  useEffect(() => { loadLogs() }, [loadLogs])

  const totalPages = Math.ceil(total / PAGE_SIZE)

  // setPage(0) on page!=0 retriggers loadLogs via the memo above; when already
  // on page 0 the memo identity changes (filter deps) and reloads as well.
  function applyFilters() {
    setPage(0)
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Audit Log</h1>
          <p className="text-muted-foreground text-sm">{total} entries</p>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex flex-wrap gap-3">
            <Select value={filterAction} onValueChange={setFilterAction}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="All actions" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All actions</SelectItem>
                {actions.map((a) => (
                  <SelectItem key={a} value={a}>{a}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="w-36">
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="success">Success</SelectItem>
                <SelectItem value="failure">Failure</SelectItem>
                <SelectItem value="denied">Denied</SelectItem>
              </SelectContent>
            </Select>

            <Input
              className="w-40"
              placeholder="Resource type"
              value={filterResourceType}
              onChange={(e) => setFilterResourceType(e.target.value)}
            />

            <Input
              className="w-44"
              type="datetime-local"
              value={filterFrom}
              onChange={(e) => setFilterFrom(e.target.value)}
            />
            <Input
              className="w-44"
              type="datetime-local"
              value={filterTo}
              onChange={(e) => setFilterTo(e.target.value)}
            />

            <Button onClick={applyFilters}>Filter</Button>
            <Button variant="outline" onClick={() => {
              setFilterAction("all")
              setFilterStatus("all")
              setFilterResourceType("")
              setFilterFrom("")
              setFilterTo("")
              setPage(0)
            }}>Clear</Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Timestamp</TableHead>
                <TableHead>User</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Resource</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>IP</TableHead>
                <TableHead className="text-right">Details</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                    Loading…
                  </TableCell>
                </TableRow>
              ) : logs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                    No entries found
                  </TableCell>
                </TableRow>
              ) : logs.map((log) => (
                <TableRow key={log.id}>
                  <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                    {new Date(log.timestamp).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-sm">
                    {log.username_snapshot ?? <span className="text-muted-foreground">—</span>}
                  </TableCell>
                  <TableCell className="text-sm font-mono">{log.action}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {log.resource_type ?? "—"}
                    {log.resource_id ? ` #${log.resource_id}` : ""}
                  </TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[log.status] ?? "outline"}>{log.status}</Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">{log.ip ?? "—"}</TableCell>
                  <TableCell className="text-right">
                    {log.details && (
                      <Button size="sm" variant="ghost" onClick={() => setSelected(log)}>
                        <Eye className="h-4 w-4" />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Pagination */}
      <div className="flex items-center justify-between gap-2 text-sm text-muted-foreground">
        <span>
          {total === 0
            ? "No entries"
            : `Showing ${page * PAGE_SIZE + 1}–${Math.min((page + 1) * PAGE_SIZE, total)} of ${total}`}
        </span>
        {totalPages > 1 && (
          <div className="flex items-center gap-2">
            <span>Page {page + 1} of {totalPages}</span>
            <Button
              size="sm" variant="outline"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              size="sm" variant="outline"
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>

      {/* Details drawer */}
      <Dialog open={!!selected} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Log #{selected?.id} — {selected?.action}</DialogTitle>
          </DialogHeader>
          <pre className="bg-muted rounded p-4 text-xs overflow-auto max-h-96">
            {JSON.stringify(selected?.details, null, 2)}
          </pre>
        </DialogContent>
      </Dialog>
    </div>
  )
}
