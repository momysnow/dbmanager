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
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs"
import { storageApi } from "@/services/api"
import type { StorageResponse } from "@/types"

// ---------- S3 schema ----------
const s3Schema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters."),
  provider: z.enum(["aws", "minio", "cloudflare", "garage", "s3", "other"]),
  bucket: z.string().min(1, "Bucket name is required"),
  endpoint_url: z.string().optional(),
  access_key: z.string().optional(),
  secret_key: z.string().optional(),
  region: z.string().optional(),
})

type S3Values = z.infer<typeof s3Schema>

// ---------- SMB schema ----------
const smbSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters."),
  provider: z.literal("smb"),
  server: z.string().min(1, "Server is required"),
  share_name: z.string().min(1, "Share name is required"),
  smb_username: z.string().optional(),
  smb_password: z.string().optional(),
  domain: z.string().optional(),
  remote_path: z.string().optional(),
})

type SMBValues = z.infer<typeof smbSchema>

interface EditStorageDialogProps {
  storage: StorageResponse
  open: boolean
  onOpenChange: (open: boolean) => void
  onStorageUpdated: () => void
}

export function EditStorageDialog({ storage, open, onOpenChange, onStorageUpdated }: EditStorageDialogProps) {
  const isSMB = storage.provider === "smb"
  const [storageType] = useState<"s3" | "smb">(isSMB ? "smb" : "s3")

  const s3Form = useForm<S3Values>({
    resolver: zodResolver(s3Schema),
    defaultValues: {
      name: storage.name,
      provider: isSMB ? "minio" : (storage.provider as S3Values["provider"]),
      bucket: storage.bucket ?? "",
      endpoint_url: storage.endpoint_url ?? "",
      access_key: "",
      secret_key: "",
      region: storage.region ?? "",
    },
  })

  const smbForm = useForm<SMBValues>({
    resolver: zodResolver(smbSchema),
    defaultValues: {
      name: storage.name,
      provider: "smb",
      server: storage.server ?? "",
      share_name: storage.share_name ?? "",
      smb_username: "",
      smb_password: "",
      domain: storage.domain ?? "",
      remote_path: storage.remote_path ?? "",
    },
  })

  useEffect(() => {
    if (open) {
      if (isSMB) {
        smbForm.reset({
          name: storage.name,
          provider: "smb",
          server: storage.server ?? "",
          share_name: storage.share_name ?? "",
          smb_username: "",
          smb_password: "",
          domain: storage.domain ?? "",
          remote_path: storage.remote_path ?? "",
        })
      } else {
        s3Form.reset({
          name: storage.name,
          provider: storage.provider as S3Values["provider"],
          bucket: storage.bucket ?? "",
          endpoint_url: storage.endpoint_url ?? "",
          access_key: "",
          secret_key: "",
          region: storage.region ?? "",
        })
      }
    }
  }, [open, storage])

  async function onSubmitS3(values: S3Values) {
    try {
      const payload: Record<string, unknown> = { ...values }
      if (!values.access_key) delete payload.access_key
      if (!values.secret_key) delete payload.secret_key
      await storageApi.update(storage.id, payload)
      toast.success("Storage target updated")
      onStorageUpdated()
      onOpenChange(false)
    } catch (error) {
      toast.error("Failed to update storage target")
      console.error(error)
    }
  }

  async function onSubmitSMB(values: SMBValues) {
    try {
      const payload: Record<string, unknown> = { ...values }
      if (!values.smb_username) delete payload.smb_username
      if (!values.smb_password) delete payload.smb_password
      await storageApi.update(storage.id, payload)
      toast.success("Storage target updated")
      onStorageUpdated()
      onOpenChange(false)
    } catch (error) {
      toast.error("Failed to update storage target")
      console.error(error)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>Edit Storage Target</DialogTitle>
          <DialogDescription>Update storage configuration.</DialogDescription>
        </DialogHeader>

        <Tabs value={storageType}>
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="s3" disabled={isSMB}>S3 Compatible</TabsTrigger>
            <TabsTrigger value="smb" disabled={!isSMB}>SMB / CIFS</TabsTrigger>
          </TabsList>

          <TabsContent value="s3">
            <Form {...s3Form}>
              <form onSubmit={s3Form.handleSubmit(onSubmitS3)} className="space-y-4">
                <FormField control={s3Form.control} name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Name</FormLabel>
                      <FormControl><Input {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField control={s3Form.control} name="provider"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Provider</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl><SelectTrigger><SelectValue /></SelectTrigger></FormControl>
                        <SelectContent>
                          <SelectItem value="minio">MinIO</SelectItem>
                          <SelectItem value="aws">AWS S3</SelectItem>
                          <SelectItem value="cloudflare">Cloudflare R2</SelectItem>
                          <SelectItem value="garage">Garage</SelectItem>
                          <SelectItem value="s3">S3 Compatible</SelectItem>
                          <SelectItem value="other">Other</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField control={s3Form.control} name="bucket"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Bucket Name</FormLabel>
                      <FormControl><Input {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <div className="grid grid-cols-2 gap-4">
                  <FormField control={s3Form.control} name="region"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Region</FormLabel>
                        <FormControl><Input {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField control={s3Form.control} name="endpoint_url"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Endpoint URL</FormLabel>
                        <FormControl><Input {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <FormField control={s3Form.control} name="access_key"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Access Key</FormLabel>
                        <FormControl><Input type="password" placeholder="(unchanged)" {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField control={s3Form.control} name="secret_key"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Secret Key</FormLabel>
                        <FormControl><Input type="password" placeholder="(unchanged)" {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <DialogFooter>
                  <Button type="submit">Save Changes</Button>
                </DialogFooter>
              </form>
            </Form>
          </TabsContent>

          <TabsContent value="smb">
            <Form {...smbForm}>
              <form onSubmit={smbForm.handleSubmit(onSubmitSMB)} className="space-y-4">
                <FormField control={smbForm.control} name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Name</FormLabel>
                      <FormControl><Input {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <div className="grid grid-cols-2 gap-4">
                  <FormField control={smbForm.control} name="server"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Server</FormLabel>
                        <FormControl><Input {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField control={smbForm.control} name="share_name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Share Name</FormLabel>
                        <FormControl><Input {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <FormField control={smbForm.control} name="smb_username"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Username</FormLabel>
                        <FormControl><Input placeholder="(unchanged)" {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField control={smbForm.control} name="smb_password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Password</FormLabel>
                        <FormControl><Input type="password" placeholder="(unchanged)" {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <FormField control={smbForm.control} name="domain"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Domain</FormLabel>
                        <FormControl><Input {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField control={smbForm.control} name="remote_path"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Base Path</FormLabel>
                        <FormControl><Input {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <DialogFooter>
                  <Button type="submit">Save Changes</Button>
                </DialogFooter>
              </form>
            </Form>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}
