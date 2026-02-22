import { useEffect, useState } from "react"
import { MoreHorizontal, Trash, Power, Pencil } from "lucide-react"

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
import { Switch } from "@/components/ui/switch"
import { toast } from "sonner"
import { schedulesApi, databasesApi } from "@/services/api"
import { AddScheduleDialog } from "./components/add-schedule-dialog"
import { EditScheduleDialog } from "./components/edit-schedule-dialog"
import type { ScheduleResponse, DatabaseResponse } from "@/types"

export function SchedulesPage() {
  const [schedules, setSchedules] = useState<ScheduleResponse[]>([])
  const [databases, setDatabases] = useState<Record<number, DatabaseResponse>>({})
  const [loading, setLoading] = useState(true)
  const [editTarget, setEditTarget] = useState<ScheduleResponse | null>(null)

  const fetchData = async () => {
    try {
      setLoading(true)
      const [schedResponse, dbResponse] = await Promise.all([
        schedulesApi.getAll(),
        databasesApi.getAll(),
      ])
      
      setSchedules(schedResponse.data)
      
      const dbMap = dbResponse.data.reduce(
        (acc, db) => ({ ...acc, [db.id]: db }),
        {} as Record<number, DatabaseResponse>
      )
      setDatabases(dbMap)
    } catch (error) {
      console.error(error)
      setSchedules([])
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await schedulesApi.delete(id)
      toast.success("Schedule deleted successfully")
      fetchData()
    } catch (error) {
      toast.error("Failed to delete schedule")
      console.error(error)
    }
  }

  const handleToggle = async (id: number) => {
    try {
      const result = await schedulesApi.toggle(id)
      const updated = result.data
      setSchedules(schedules.map(s => s.id === id ? updated : s))
      toast.success(`Schedule ${updated.enabled ? "enabled" : "disabled"}`)
    } catch (error) {
      toast.error("Failed to update schedule")
      fetchData()
      console.error(error)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between space-y-2">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Backup Schedules</h2>
          <p className="text-muted-foreground">
            Automate your database backups.
          </p>
        </div>
        <AddScheduleDialog onScheduleAdded={fetchData} />
      </div>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Database</TableHead>
              <TableHead>Schedule (Cron)</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 4 }).map((_, j) => (
                    <TableCell key={j}>
                      <div className="h-4 w-full animate-pulse rounded bg-muted" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : schedules.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="h-24 text-center">
                  No schedules found.
                </TableCell>
              </TableRow>
            ) : (
              schedules.map((schedule) => (
                <TableRow key={schedule.id}>
                  <TableCell className="font-medium">
                    {databases[schedule.database_id]?.name || `DB #${schedule.database_id}`}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {schedule.cron_expression}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center space-x-2">
                       <Switch 
                        checked={schedule.enabled}
                        onCheckedChange={() => handleToggle(schedule.id)}
                       />
                       <span className="text-sm text-muted-foreground">
                         {schedule.enabled ? "Active" : "Paused"}
                       </span>
                    </div>
                  </TableCell>
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
                        <DropdownMenuItem onClick={() => setEditTarget(schedule)}>
                          <Pencil className="mr-2 h-4 w-4" /> Edit
                        </DropdownMenuItem>
                        <DropdownMenuItem 
                          onClick={() => handleToggle(schedule.id)}
                        >
                          <Power className="mr-2 h-4 w-4" /> 
                          {schedule.enabled ? "Disable" : "Enable"}
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem 
                          className="text-destructive"
                          onClick={() => handleDelete(schedule.id)}
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
        <EditScheduleDialog
          schedule={editTarget}
          open={!!editTarget}
          onOpenChange={(open) => { if (!open) setEditTarget(null) }}
          onScheduleUpdated={fetchData}
        />
      )}
    </div>
  )
}
