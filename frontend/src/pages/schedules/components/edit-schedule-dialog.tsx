import { useState, useEffect } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import * as z from "zod"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { schedulesApi, databasesApi } from "@/services/api"
import type { ScheduleResponse, DatabaseResponse } from "@/types"
import { CronBuilder } from "@/components/cron-builder"

const formSchema = z.object({
  database_id: z.string().min(1, "Database is required"),
  cron_expression: z.string().min(1, "Schedule is required"),
})

type FormValues = z.infer<typeof formSchema>

interface EditScheduleDialogProps {
  schedule: ScheduleResponse
  open: boolean
  onOpenChange: (open: boolean) => void
  onScheduleUpdated: () => void
}

export function EditScheduleDialog({ schedule, open, onOpenChange, onScheduleUpdated }: EditScheduleDialogProps) {
  const [databases, setDatabases] = useState<DatabaseResponse[]>([])

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      database_id: String(schedule.database_id),
      cron_expression: schedule.cron_expression,
    },
  })

  useEffect(() => {
    if (open) {
      form.reset({
        database_id: String(schedule.database_id),
        cron_expression: schedule.cron_expression,
      })
      databasesApi.getAll().then(r => setDatabases(r.data)).catch(() => {})
    }
  }, [open, schedule])

  async function onSubmit(values: FormValues) {
    try {
      await schedulesApi.update(schedule.id, {
        database_id: parseInt(values.database_id, 10),
        cron_expression: values.cron_expression,
        enabled: schedule.enabled,
      })
      toast.success("Schedule updated")
      onScheduleUpdated()
      onOpenChange(false)
    } catch (error) {
      toast.error("Failed to update schedule")
      console.error(error)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[550px]">
        <DialogHeader>
          <DialogTitle>Edit Schedule</DialogTitle>
          <DialogDescription>Update the backup schedule.</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField control={form.control} name="database_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Database</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger><SelectValue placeholder="Select database" /></SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {databases.map((db) => (
                        <SelectItem key={db.id} value={String(db.id)}>
                          {db.name} ({db.provider})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField control={form.control} name="cron_expression"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Schedule</FormLabel>
                  <FormControl>
                    <CronBuilder 
                      value={field.value} 
                      onChange={field.onChange} 
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <DialogFooter>
              <Button type="submit">Save Changes</Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
