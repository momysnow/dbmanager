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
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { databasesApi, storageApi } from "@/services/api"
import type { DatabaseResponse, StorageResponse } from "@/types"
import { Checkbox } from "@/components/ui/checkbox"

const formSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters."),
  provider: z.enum(["postgres", "mysql", "mariadb", "sqlserver", "mongodb"]),
  host: z.string().min(1, "Host is required"),
  port: z.number().min(1, "Port is required"),
  user: z.string().min(1, "User is required"),
  password: z.string().optional(),
  database: z.string().min(1, "Database name is required"),
  retention: z.number().min(0).optional(),
  s3_retention: z.number().min(0).optional(),
  storage_target_ids: z.array(z.number()).optional(),
})

type FormValues = z.infer<typeof formSchema>

interface EditDatabaseDialogProps {
  database: DatabaseResponse
  open: boolean
  onOpenChange: (open: boolean) => void
  onDatabaseUpdated: () => void
}

export function EditDatabaseDialog({ database, open, onOpenChange, onDatabaseUpdated }: EditDatabaseDialogProps) {
  const [storageTargets, setStorageTargets] = useState<StorageResponse[]>([])

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: database.name,
      provider: database.provider,
      host: database.params.host,
      port: database.params.port,
      user: database.params.user ?? "",
      password: "",
      database: database.params.database ?? "",
      retention: database.retention ?? 0,
      s3_retention: database.s3_retention ?? 0,
      storage_target_ids: database.storage_target_ids ?? [],
    },
  })

  useEffect(() => {
    if (open) {
      form.reset({
        name: database.name,
        provider: database.provider,
        host: database.params.host,
        port: database.params.port,
        user: database.params.user ?? "",
        password: "",
        database: database.params.database ?? "",
        retention: database.retention ?? 0,
        s3_retention: database.s3_retention ?? 0,
        storage_target_ids: database.storage_target_ids ?? [],
      })
      storageApi.getAll().then(r => setStorageTargets(r.data)).catch(() => {})
    }
  }, [open, database])

  async function onSubmit(values: FormValues) {
    try {
      const payload: Record<string, unknown> = {
        name: values.name,
        provider: values.provider,
        params: {
          host: values.host,
          port: values.port,
          database: values.database,
          user: values.user,
          ...(values.password ? { password: values.password } : {}),
        },
        retention: values.retention,
        s3_retention: values.s3_retention,
        storage_target_ids: values.storage_target_ids,
      }
      await databasesApi.update(database.id, payload)
      toast.success("Database updated")
      onDatabaseUpdated()
      onOpenChange(false)
    } catch (error) {
      toast.error("Failed to update database")
      console.error(error)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Edit Database</DialogTitle>
          <DialogDescription>Update the database connection settings.</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField control={form.control} name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl><Input {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid grid-cols-2 gap-4">
              <FormField control={form.control} name="provider"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Provider</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="postgres">PostgreSQL</SelectItem>
                        <SelectItem value="mysql">MySQL</SelectItem>
                        <SelectItem value="mariadb">MariaDB</SelectItem>
                        <SelectItem value="sqlserver">SQL Server</SelectItem>
                        <SelectItem value="mongodb">MongoDB</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField control={form.control} name="port"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Port</FormLabel>
                    <FormControl>
                      <Input type="number" {...field} onChange={(e) => field.onChange(e.target.valueAsNumber)} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField control={form.control} name="host"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Host</FormLabel>
                  <FormControl><Input {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid grid-cols-2 gap-4">
              <FormField control={form.control} name="user"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>User</FormLabel>
                    <FormControl><Input {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField control={form.control} name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Password</FormLabel>
                    <FormControl><Input type="password" placeholder="(unchanged)" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField control={form.control} name="database"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Database Name</FormLabel>
                  <FormControl><Input {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid grid-cols-2 gap-4">
              <FormField control={form.control} name="retention"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Local Retention (days)</FormLabel>
                    <FormControl>
                      <Input type="number" {...field} onChange={(e) => field.onChange(e.target.valueAsNumber)} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField control={form.control} name="s3_retention"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Remote Retention (days)</FormLabel>
                    <FormControl>
                      <Input type="number" {...field} onChange={(e) => field.onChange(e.target.valueAsNumber)} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            {storageTargets.length > 0 && (
              <FormField control={form.control} name="storage_target_ids"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Storage Targets</FormLabel>
                    <div className="space-y-2 rounded-md border p-3">
                      {storageTargets.map((t) => (
                        <label key={t.id} className="flex items-center gap-2 text-sm cursor-pointer">
                          <Checkbox
                            checked={(field.value || []).includes(t.id)}
                            onCheckedChange={(checked) => {
                              const currentValues = field.value || []
                              if (checked) {
                                field.onChange([...currentValues, t.id])
                              } else {
                                field.onChange(currentValues.filter((id: number) => id !== t.id))
                              }
                            }}
                          />
                          <span>{t.name}</span>
                          <span className="text-muted-foreground capitalize">({t.provider})</span>
                        </label>
                      ))}
                    </div>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}

            <DialogFooter>
              <Button type="submit">Save Changes</Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
