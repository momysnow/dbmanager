import { useState, useEffect } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import * as z from "zod"
import { Plus } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
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
import { databasesApi, schedulesApi } from "@/services/api"
import type { DatabaseResponse } from "@/types"
import { CronBuilder } from "@/components/cron-builder"

const formSchema = z.object({
  database_id: z.string().min(1, "Database is required"),
  cron_expression: z.string().min(1, "Schedule is required"),
})

type FormValues = z.infer<typeof formSchema>

export function AddScheduleDialog({ onScheduleAdded }: { onScheduleAdded: () => void }) {
  const [open, setOpen] = useState(false)
  const [databases, setDatabases] = useState<DatabaseResponse[]>([])

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      database_id: "",
      cron_expression: "0 0 * * *", // Default to daily at midnight
    },
  })

  useEffect(() => {
    if (open) {
      const fetchData = async () => {
        try {
          const dbs = await databasesApi.getAll()
          setDatabases(dbs.data)
        } catch (error) {
          console.error("Failed to fetch databases", error)
          toast.error("Failed to load databases")
        }
      }
      fetchData()
    }
  }, [open])

  async function onSubmit(values: FormValues) {
    try {
      await schedulesApi.create({
        database_id: parseInt(values.database_id, 10),
        cron_expression: values.cron_expression,
        enabled: true,
      })
      toast.success("Schedule created successfully")
      onScheduleAdded()
      setOpen(false)
      form.reset()
    } catch (error) {
      toast.error("Failed to create schedule")
      console.error(error)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 h-4 w-4" /> Create Schedule
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[550px]">
        <DialogHeader>
          <DialogTitle>Create Backup Schedule</DialogTitle>
          <DialogDescription>
            Automate backups for your database.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="database_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Database</FormLabel>
                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select database" />
                      </SelectTrigger>
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

            <FormField
              control={form.control}
              name="cron_expression"
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
              <Button type="submit">Create Schedule</Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
