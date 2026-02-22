import { useEffect, useState } from "react"
import { MoreHorizontal, Trash, HardDrive, Pencil, Server, Cloud } from "lucide-react"

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
import { Badge } from "@/components/ui/badge"
import { toast } from "sonner"
import { storageApi } from "@/services/api"
import { AddStorageDialog } from "./components/add-storage-dialog"
import { EditStorageDialog } from "./components/edit-storage-dialog"
import type { StorageResponse } from "@/types"

const SMB_PROVIDERS = new Set(["smb"])

function getProviderIcon(provider: string) {
  return SMB_PROVIDERS.has(provider)
    ? <Server className="h-4 w-4 text-muted-foreground" />
    : <Cloud className="h-4 w-4 text-muted-foreground" />
}

function getProviderBadge(provider: string) {
  const variant = SMB_PROVIDERS.has(provider) ? "outline" : "secondary"
  return <Badge variant={variant} className="capitalize">{provider}</Badge>
}

function getTargetDetail(target: StorageResponse) {
  if (SMB_PROVIDERS.has(target.provider)) {
    return `\\\\${target.server}\\${target.share_name}`
  }
  return target.bucket ?? "—"
}

export function StoragePage() {
  const [targets, setTargets] = useState<StorageResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [editTarget, setEditTarget] = useState<StorageResponse | null>(null)

  const fetchTargets = async () => {
    try {
      setLoading(true)
      const response = await storageApi.getAll()
      setTargets(response.data)
    } catch (error) {
      console.error(error)
      setTargets([])
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await storageApi.delete(id)
      toast.success("Storage target deleted successfully")
      fetchTargets()
    } catch (error) {
      toast.error("Failed to delete storage target")
      console.error(error)
    }
  }

  const handleTest = async (id: number) => {
    try {
      const response = await storageApi.test(id)
      const result = response.data as { success: boolean; message: string }
      if (result.success) {
        toast.success("Connection successful")
      } else {
        toast.error(result.message || "Connection test failed")
      }
    } catch (error) {
      toast.error("Connection test failed")
      console.error(error)
    }
  }

  useEffect(() => {
    fetchTargets()
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between space-y-2">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Storage</h2>
          <p className="text-muted-foreground">
            Configure where backups are stored — S3, SMB, or both.
          </p>
        </div>
        <AddStorageDialog onStorageAdded={fetchTargets} />
      </div>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Target</TableHead>
              <TableHead>Region / Domain</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 5 }).map((_, j) => (
                    <TableCell key={j}>
                      <div className="h-4 w-full animate-pulse rounded bg-muted" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : targets.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="h-24 text-center">
                  No storage targets found.
                </TableCell>
              </TableRow>
            ) : (
              targets.map((target) => (
                <TableRow key={target.id}>
                  <TableCell className="font-medium flex items-center gap-2">
                    {getProviderIcon(target.provider)}
                    {target.name}
                  </TableCell>
                  <TableCell>{getProviderBadge(target.provider)}</TableCell>
                  <TableCell className="font-mono text-sm">{getTargetDetail(target)}</TableCell>
                  <TableCell>{target.region ?? target.domain ?? "—"}</TableCell>
                  <TableCell className="text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" className="h-8 w-8 p-0">
                          <span className="sr-only">Open menu</span>
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuLabel>Actions</DropdownMenuLabel>
                        <DropdownMenuItem onClick={() => setEditTarget(target)}>
                          <Pencil className="mr-2 h-4 w-4" /> Edit
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleTest(target.id)}>
                          <HardDrive className="mr-2 h-4 w-4" /> Test Connection
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem 
                          className="text-destructive"
                          onClick={() => handleDelete(target.id)}
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

      {editTarget && (
        <EditStorageDialog
          storage={editTarget}
          open={!!editTarget}
          onOpenChange={(open) => { if (!open) setEditTarget(null) }}
          onStorageUpdated={fetchTargets}
        />
      )}
    </div>
  )
}
