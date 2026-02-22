import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { MoreHorizontal, Shield, Trash, Pencil, Plug, Loader2, ExternalLink, TerminalSquare } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { toast } from "sonner"
import { databasesApi } from "@/services/api"
import { AddDatabaseDialog } from "./components/add-database-dialog"
import { EditDatabaseDialog } from "./components/edit-database-dialog"
import type { DatabaseResponse } from "@/types"
import { Badge } from "@/components/ui/badge"

function DatabaseStatusBadge({ dbId, retestTrigger = 0 }: { dbId: number, retestTrigger?: number }) {
  const [status, setStatus] = useState<"checking" | "ok" | "error" | "idle">("idle")

  useEffect(() => {
    let mounted = true
    const checkStatus = async () => {
      setStatus("checking")
      try {
        const res = await databasesApi.test(dbId)
        if (!mounted) return
        if (res.data && res.data.success === false) {
          setStatus("error")
        } else {
          setStatus("ok")
        }
      } catch {
        if (!mounted) return
        setStatus("error")
      }
    }
    checkStatus()
    return () => { mounted = false }
  }, [dbId, retestTrigger])

  if (status === "idle" || status === "checking") {
    return (
      <Badge variant="outline" className="text-muted-foreground flex items-center gap-1 w-20 justify-center">
        <Loader2 className="h-3 w-3 animate-spin" />
        <span className="text-xs">Ping...</span>
      </Badge>
    )
  }

  if (status === "ok") {
    return (
      <Badge variant="outline" className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20 w-20 justify-center">
        Online
      </Badge>
    )
  }

  return (
    <Badge variant="outline" className="bg-destructive/10 text-destructive border-destructive/20 w-20 justify-center">
      Offline
    </Badge>
  )
}

export function DatabasesPage() {
  const navigate = useNavigate()
  const [databases, setDatabases] = useState<DatabaseResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [editTarget, setEditTarget] = useState<DatabaseResponse | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<DatabaseResponse | null>(null)
  const [testing, setTesting] = useState<number | null>(null)

  const fetchDatabases = async () => {
    try {
      setLoading(true)
      const response = await databasesApi.getAll()
      setDatabases(response.data)
    } catch (error) {
      console.error(error)
      setDatabases([])
    } finally {
      setLoading(false)
    }
  }

  const handleBackup = async (id: number) => {
    try {
      await databasesApi.backup(id)
      toast.success("Backup started successfully")
    } catch (error) {
      toast.error("Failed to start backup")
      console.error(error)
    }
  }

  const handleTestConnection = async (db: DatabaseResponse) => {
    try {
      setTesting(db.id)
      const res = await databasesApi.test(db.id)
      if (res.data && res.data.success === false) {
          toast.error(`❌ Connection to "${db.name}" failed: ${res.data.error || "Unknown error"}`)
      } else {
          toast.success(`✅ Connection to "${db.name}" successful`)
      }
    } catch {
      toast.error(`❌ Connection to "${db.name}" failed`)
    } finally {
      setTesting(null)
    }
  }

  const handleDeleteConfirmed = async () => {
    if (!deleteTarget) return
    try {
      await databasesApi.delete(deleteTarget.id)
      toast.success(`Database "${deleteTarget.name}" deleted`)
      fetchDatabases()
    } catch (error) {
      toast.error("Failed to delete database")
      console.error(error)
    } finally {
      setDeleteTarget(null)
    }
  }

  useEffect(() => {
    fetchDatabases()
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between space-y-2">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Databases</h2>
          <p className="text-muted-foreground">
            Manage your database connections and backups.
          </p>
        </div>
        <AddDatabaseDialog onDatabaseAdded={fetchDatabases} />
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Provider</TableHead>
              <TableHead>Host</TableHead>
              <TableHead>Database</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 6 }).map((_, j) => (
                    <TableCell key={j}>
                      <div className="h-4 w-full animate-pulse rounded bg-muted" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : databases.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="h-24 text-center">
                  No databases found.
                </TableCell>
              </TableRow>
            ) : (
              databases.map((db) => (
                <TableRow
                  key={db.id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => navigate(`/databases/${db.id}`)}
                >
                  <TableCell className="font-medium">
                    <span className="flex items-center gap-1.5 group">
                      {db.name}
                      <ExternalLink className="h-3 w-3 opacity-0 group-hover:opacity-50 transition-opacity" />
                    </span>
                  </TableCell>
                  <TableCell className="capitalize">{db.provider}</TableCell>
                  <TableCell>{db.params.host}:{db.params.port}</TableCell>
                  <TableCell>{db.params.database ?? "—"}</TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <DatabaseStatusBadge dbId={db.id} retestTrigger={testing === db.id ? Date.now() : 0} />
                  </TableCell>
                  <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" className="h-8 w-8 p-0">
                          <span className="sr-only">Open menu</span>
                          {testing === db.id
                            ? <Loader2 className="h-4 w-4 animate-spin" />
                            : <MoreHorizontal className="h-4 w-4" />}
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuLabel>Actions</DropdownMenuLabel>
                        <DropdownMenuItem onClick={() => setEditTarget(db)}>
                          <Pencil className="mr-2 h-4 w-4" /> Edit
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => handleTestConnection(db)}
                          disabled={testing === db.id}
                        >
                          <Plug className="mr-2 h-4 w-4" /> Test Connection
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleBackup(db.id)}>
                          <Shield className="mr-2 h-4 w-4" /> Backup Now
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => navigate(`/query?dbId=${db.id}`)}>
                          <TerminalSquare className="mr-2 h-4 w-4" /> Query
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          className="text-destructive focus:text-destructive"
                          onClick={() => setDeleteTarget(db)}
                        >
                          <Trash className="mr-2 h-4 w-4" /> Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Edit dialog */}
      {editTarget && (
        <EditDatabaseDialog
          database={editTarget}
          open={!!editTarget}
          onOpenChange={(open) => { if (!open) setEditTarget(null) }}
          onDatabaseUpdated={fetchDatabases}
        />
      )}

      {/* Delete confirm dialog */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(open: boolean) => { if (!open) setDeleteTarget(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete database?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete{" "}
              <span className="font-semibold text-foreground">"{deleteTarget?.name}"</span>?
              This will remove the database configuration. Existing backups will not be deleted.
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
