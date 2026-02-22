import { useState } from "react"
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

// ---------- S3 schema ----------
const s3Schema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters."),
  provider: z.enum(["aws", "minio", "cloudflare", "garage", "s3", "other"]),
  bucket: z.string().min(1, "Bucket name is required"),
  endpoint_url: z.string().optional(),
  access_key: z.string().min(1, "Access key is required"),
  secret_key: z.string().min(1, "Secret key is required"),
  region: z.string().optional(),
})

type S3Values = z.infer<typeof s3Schema>

// ---------- SMB schema ----------
const smbSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters."),
  provider: z.literal("smb"),
  server: z.string().min(1, "Server is required"),
  share_name: z.string().min(1, "Share name is required"),
  smb_username: z.string().min(1, "Username is required"),
  smb_password: z.string().min(1, "Password is required"),
  domain: z.string().optional(),
  remote_path: z.string().optional(),
})

type SMBValues = z.infer<typeof smbSchema>

export function AddStorageDialog({ onStorageAdded }: { onStorageAdded: () => void }) {
  const [open, setOpen] = useState(false)
  const [storageType, setStorageType] = useState<"s3" | "smb">("s3")

  const s3Form = useForm<S3Values>({
    resolver: zodResolver(s3Schema),
    defaultValues: {
      name: "",
      provider: "minio",
      bucket: "",
      endpoint_url: "",
      access_key: "",
      secret_key: "",
      region: "",
    },
  })

  const smbForm = useForm<SMBValues>({
    resolver: zodResolver(smbSchema),
    defaultValues: {
      name: "",
      provider: "smb",
      server: "",
      share_name: "",
      smb_username: "",
      smb_password: "",
      domain: "",
      remote_path: "",
    },
  })

  async function onSubmitS3(values: S3Values) {
    try {
      await storageApi.create(values)
      toast.success("S3 storage target added")
      onStorageAdded()
      setOpen(false)
      s3Form.reset()
    } catch (error) {
      toast.error("Failed to add storage target")
      console.error(error)
    }
  }

  async function onSubmitSMB(values: SMBValues) {
    try {
      await storageApi.create(values)
      toast.success("SMB storage target added")
      onStorageAdded()
      setOpen(false)
      smbForm.reset()
    } catch (error) {
      toast.error("Failed to add storage target")
      console.error(error)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 h-4 w-4" /> Add Storage
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>Add Storage Target</DialogTitle>
          <DialogDescription>
            Configure where backups are sent.
          </DialogDescription>
        </DialogHeader>

        <Tabs value={storageType} onValueChange={(v) => setStorageType(v as "s3" | "smb")}>
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="s3">S3 Compatible</TabsTrigger>
            <TabsTrigger value="smb">SMB / CIFS</TabsTrigger>
          </TabsList>

          {/* =========== S3 =========== */}
          <TabsContent value="s3">
            <Form {...s3Form}>
              <form onSubmit={s3Form.handleSubmit(onSubmitS3)} className="space-y-4">
                <FormField control={s3Form.control} name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Name</FormLabel>
                      <FormControl><Input placeholder="My S3 Bucket" {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField control={s3Form.control} name="provider"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Provider</FormLabel>
                      <Select onValueChange={field.onChange} defaultValue={field.value}>
                        <FormControl>
                          <SelectTrigger><SelectValue placeholder="Select provider" /></SelectTrigger>
                        </FormControl>
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
                      <FormControl><Input placeholder="my-backup-bucket" {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <div className="grid grid-cols-2 gap-4">
                  <FormField control={s3Form.control} name="region"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Region</FormLabel>
                        <FormControl><Input placeholder="us-east-1" {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField control={s3Form.control} name="endpoint_url"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Endpoint URL</FormLabel>
                        <FormControl><Input placeholder="http://minio:9000" {...field} /></FormControl>
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
                        <FormControl><Input type="password" {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField control={s3Form.control} name="secret_key"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Secret Key</FormLabel>
                        <FormControl><Input type="password" {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                <DialogFooter>
                  <Button type="submit">Save S3 Storage</Button>
                </DialogFooter>
              </form>
            </Form>
          </TabsContent>

          {/* =========== SMB =========== */}
          <TabsContent value="smb">
            <Form {...smbForm}>
              <form onSubmit={smbForm.handleSubmit(onSubmitSMB)} className="space-y-4">
                <FormField control={smbForm.control} name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Name</FormLabel>
                      <FormControl><Input placeholder="NAS Backups" {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <div className="grid grid-cols-2 gap-4">
                  <FormField control={smbForm.control} name="server"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Server</FormLabel>
                        <FormControl><Input placeholder="192.168.1.100" {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField control={smbForm.control} name="share_name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Share Name</FormLabel>
                        <FormControl><Input placeholder="backups" {...field} /></FormControl>
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
                        <FormControl><Input {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField control={smbForm.control} name="smb_password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Password</FormLabel>
                        <FormControl><Input type="password" {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <FormField control={smbForm.control} name="domain"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Domain (optional)</FormLabel>
                        <FormControl><Input placeholder="WORKGROUP" {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField control={smbForm.control} name="remote_path"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Base Path (optional)</FormLabel>
                        <FormControl><Input placeholder="dbmanager" {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                <DialogFooter>
                  <Button type="submit">Save SMB Storage</Button>
                </DialogFooter>
              </form>
            </Form>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}
