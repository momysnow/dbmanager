import { useEffect, useState } from "react"
import { Save, RefreshCw, Send, Eye, EyeOff } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { settingsApi, notificationsApi } from "@/services/api"

// ── Skeleton ─────────────────────────────────────────────────────────────────
function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-muted ${className ?? ""}`} />
}

// ── Types ─────────────────────────────────────────────────────────────────────
interface CompressionSettings {
  enabled: boolean
  algorithm: string
  level: number
}

interface EncryptionSettings {
  enabled: boolean
}

interface EmailSettings {
  enabled: boolean
  smtp_host: string
  smtp_port: number
  smtp_username: string
  from_email: string
  to_emails: string[]
  smtp_password_set: boolean
}

interface WebhookSettings {
  enabled: boolean
  webhook_url_set: boolean
}

// ── General Tab ───────────────────────────────────────────────────────────────
function GeneralTab() {
  const [syncing, setSyncing] = useState(false)

  const handleSync = async () => {
    try {
      setSyncing(true)
      await settingsApi.syncConfig()
      toast.success("Configuration synced successfully")
    } catch {
      toast.error("Failed to sync configuration")
    } finally {
      setSyncing(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Configuration Sync</CardTitle>
        <CardDescription>
          Force synchronization of your configuration to persistent storage.
          The application automatically saves changes, but you can force a sync here if needed.
        </CardDescription>
      </CardHeader>
      <CardFooter>
        <Button onClick={handleSync} disabled={syncing}>
          {syncing ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
          {syncing ? "Syncing..." : "Sync Configuration"}
        </Button>
      </CardFooter>
    </Card>
  )
}

// ── Compression Tab ───────────────────────────────────────────────────────────
function CompressionTab() {
  const [settings, setSettings] = useState<CompressionSettings>({ enabled: false, algorithm: "gzip", level: 6 })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    settingsApi.getCompression()
      .then(r => setSettings(r.data))
      .catch(() => toast.error("Failed to load compression settings"))
      .finally(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    try {
      setSaving(true)
      await settingsApi.updateCompression(settings as unknown as Record<string, unknown>)
      toast.success("Compression settings saved")
    } catch {
      toast.error("Failed to save compression settings")
    } finally {
      setSaving(false)
    }
  }

  if (loading) return (
    <Card>
      <CardHeader><Skeleton className="h-6 w-40" /><Skeleton className="h-4 w-64 mt-1" /></CardHeader>
      <CardContent className="space-y-4">
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
      </CardContent>
    </Card>
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>Compression</CardTitle>
        <CardDescription>Configure backup compression to reduce storage usage.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <Label className="text-base">Enable Compression</Label>
            <p className="text-sm text-muted-foreground">Compress backups before storing them</p>
          </div>
          <Switch
            checked={settings.enabled}
            onCheckedChange={(v) => setSettings(s => ({ ...s, enabled: v }))}
          />
        </div>

        {settings.enabled && (
          <>
            <div className="space-y-2">
              <Label>Algorithm</Label>
              <Select
                value={settings.algorithm}
                onValueChange={(v) => setSettings(s => ({ ...s, algorithm: v }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="gzip">gzip (fast, good compatibility)</SelectItem>
                  <SelectItem value="zstd">zstandard (faster, better ratio)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Compression Level: {settings.level}</Label>
              <input
                type="range"
                min={1}
                max={9}
                value={settings.level}
                onChange={(e) => setSettings(s => ({ ...s, level: Number(e.target.value) }))}
                className="w-full accent-primary"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>1 (fastest)</span>
                <span>9 (best ratio)</span>
              </div>
            </div>
          </>
        )}
      </CardContent>
      <CardFooter>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
          {saving ? "Saving..." : "Save"}
        </Button>
      </CardFooter>
    </Card>
  )
}

// ── Encryption Tab ────────────────────────────────────────────────────────────
function EncryptionTab() {
  const [settings, setSettings] = useState<EncryptionSettings>({ enabled: false })
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    settingsApi.getEncryption()
      .then(r => setSettings(r.data))
      .catch(() => toast.error("Failed to load encryption settings"))
      .finally(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    try {
      setSaving(true)
      await settingsApi.updateEncryption({
        enabled: settings.enabled,
        password: password || undefined,
      })
      toast.success("Encryption settings saved")
      setPassword("")
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(msg || "Failed to save encryption settings")
    } finally {
      setSaving(false)
    }
  }

  if (loading) return (
    <Card>
      <CardHeader><Skeleton className="h-6 w-40" /><Skeleton className="h-4 w-64 mt-1" /></CardHeader>
      <CardContent className="space-y-4">
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
      </CardContent>
    </Card>
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>Encryption</CardTitle>
        <CardDescription>Encrypt backups at rest using AES-256 or ChaCha20.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <Label className="text-base">Enable Encryption</Label>
            <p className="text-sm text-muted-foreground">Encrypt backup files before storing</p>
          </div>
          <Switch
            checked={settings.enabled}
            onCheckedChange={(v) => setSettings(s => ({ ...s, enabled: v }))}
          />
        </div>

        {settings.enabled && (
          <div className="space-y-2">
            <Label htmlFor="enc-password">Encryption Password</Label>
            <div className="relative">
              <Input
                id="enc-password"
                type={showPassword ? "text" : "password"}
                placeholder="Enter new password (leave blank to keep current)"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPassword(v => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              ⚠️ If you change the password, existing encrypted backups cannot be decrypted with the new password.
            </p>
          </div>
        )}
      </CardContent>
      <CardFooter>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
          {saving ? "Saving..." : "Save"}
        </Button>
      </CardFooter>
    </Card>
  )
}

// ── Notifications Tab ─────────────────────────────────────────────────────────
function NotificationsTab() {
  const [email, setEmail] = useState<EmailSettings>({
    enabled: false, smtp_host: "", smtp_port: 587,
    smtp_username: "", from_email: "", to_emails: [], smtp_password_set: false,
  })
  const [slack, setSlack] = useState<WebhookSettings>({ enabled: false, webhook_url_set: false })
  const [discord, setDiscord] = useState<WebhookSettings>({ enabled: false, webhook_url_set: false })
  const [teams, setTeams] = useState<WebhookSettings>({ enabled: false, webhook_url_set: false })

  const [emailPassword, setEmailPassword] = useState("")
  const [slackUrl, setSlackUrl] = useState("")
  const [discordUrl, setDiscordUrl] = useState("")
  const [teamsUrl, setTeamsUrl] = useState("")

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState<string | null>(null)
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    notificationsApi.getAll()
      .then(r => {
        const d = r.data
        setEmail(d.email)
        setSlack(d.slack)
        setDiscord(d.discord)
        setTeams(d.teams)
      })
      .catch(() => toast.error("Failed to load notification settings"))
      .finally(() => setLoading(false))
  }, [])

  const saveEmail = async () => {
    try {
      setSaving("email")
      await notificationsApi.updateEmail({
        enabled: email.enabled,
        smtp_host: email.smtp_host,
        smtp_port: email.smtp_port,
        smtp_username: email.smtp_username,
        from_email: email.from_email,
        to_emails: email.to_emails,
        smtp_password: emailPassword || undefined,
      })
      toast.success("Email settings saved")
      setEmailPassword("")
    } catch {
      toast.error("Failed to save email settings")
    } finally {
      setSaving(null)
    }
  }

  const saveWebhook = async (provider: "slack" | "discord" | "teams", url: string) => {
    const stateMap = { slack, discord, teams }
    const current = stateMap[provider]
    try {
      setSaving(provider)
      await notificationsApi.updateWebhook(provider, {
        enabled: current.enabled,
        webhook_url: url || undefined,
      })
      toast.success(`${provider.charAt(0).toUpperCase() + provider.slice(1)} settings saved`)
      if (provider === "slack") setSlackUrl("")
      if (provider === "discord") setDiscordUrl("")
      if (provider === "teams") setTeamsUrl("")
    } catch {
      toast.error(`Failed to save ${provider} settings`)
    } finally {
      setSaving(null)
    }
  }

  const handleTest = async () => {
    try {
      setTesting(true)
      const r = await notificationsApi.test()
      if (r.data.success) toast.success(r.data.message)
      else toast.error(r.data.message)
    } catch {
      toast.error("Failed to send test notification")
    } finally {
      setTesting(false)
    }
  }

  if (loading) return (
    <div className="space-y-4">
      {[1, 2, 3].map(i => (
        <Card key={i}>
          <CardHeader><Skeleton className="h-6 w-32" /></CardHeader>
          <CardContent><Skeleton className="h-20 w-full" /></CardContent>
        </Card>
      ))}
    </div>
  )

  return (
    <div className="space-y-4">
      {/* Test button */}
      <div className="flex justify-end">
        <Button variant="outline" onClick={handleTest} disabled={testing}>
          {testing ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
          Send Test Notification
        </Button>
      </div>

      {/* Email */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Email (SMTP)</CardTitle>
              <CardDescription>Send backup notifications via email</CardDescription>
            </div>
            <Switch checked={email.enabled} onCheckedChange={(v) => setEmail(s => ({ ...s, enabled: v }))} />
          </div>
        </CardHeader>
        {email.enabled && (
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>SMTP Host</Label>
                <Input value={email.smtp_host} onChange={e => setEmail(s => ({ ...s, smtp_host: e.target.value }))} placeholder="smtp.gmail.com" />
              </div>
              <div className="space-y-2">
                <Label>SMTP Port</Label>
                <Input type="number" value={email.smtp_port} onChange={e => setEmail(s => ({ ...s, smtp_port: Number(e.target.value) }))} placeholder="587" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Username</Label>
                <Input value={email.smtp_username} onChange={e => setEmail(s => ({ ...s, smtp_username: e.target.value }))} placeholder="user@example.com" />
              </div>
              <div className="space-y-2">
                <Label>Password {email.smtp_password_set && <span className="text-xs text-green-500">(set)</span>}</Label>
                <Input type="password" value={emailPassword} onChange={e => setEmailPassword(e.target.value)} placeholder="Leave blank to keep current" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>From Email</Label>
                <Input value={email.from_email} onChange={e => setEmail(s => ({ ...s, from_email: e.target.value }))} placeholder="noreply@example.com" />
              </div>
              <div className="space-y-2">
                <Label>To Emails (comma-separated)</Label>
                <Input
                  value={email.to_emails.join(", ")}
                  onChange={e => setEmail(s => ({ ...s, to_emails: e.target.value.split(",").map(x => x.trim()).filter(Boolean) }))}
                  placeholder="admin@example.com, ops@example.com"
                />
              </div>
            </div>
          </CardContent>
        )}
        <CardFooter>
          <Button onClick={saveEmail} disabled={saving === "email"}>
            {saving === "email" ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
            Save Email Settings
          </Button>
        </CardFooter>
      </Card>

      {/* Slack */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Slack</CardTitle>
              <CardDescription>Send notifications to a Slack channel via webhook</CardDescription>
            </div>
            <Switch checked={slack.enabled} onCheckedChange={(v) => setSlack(s => ({ ...s, enabled: v }))} />
          </div>
        </CardHeader>
        {slack.enabled && (
          <CardContent>
            <div className="space-y-2">
              <Label>Webhook URL {slack.webhook_url_set && <span className="text-xs text-green-500">(set)</span>}</Label>
              <Input value={slackUrl} onChange={e => setSlackUrl(e.target.value)} placeholder="https://hooks.slack.com/services/..." />
            </div>
          </CardContent>
        )}
        <CardFooter>
          <Button onClick={() => saveWebhook("slack", slackUrl)} disabled={saving === "slack"}>
            {saving === "slack" ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
            Save Slack Settings
          </Button>
        </CardFooter>
      </Card>

      {/* Discord */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Discord</CardTitle>
              <CardDescription>Send notifications to a Discord channel via webhook</CardDescription>
            </div>
            <Switch checked={discord.enabled} onCheckedChange={(v) => setDiscord(s => ({ ...s, enabled: v }))} />
          </div>
        </CardHeader>
        {discord.enabled && (
          <CardContent>
            <div className="space-y-2">
              <Label>Webhook URL {discord.webhook_url_set && <span className="text-xs text-green-500">(set)</span>}</Label>
              <Input value={discordUrl} onChange={e => setDiscordUrl(e.target.value)} placeholder="https://discord.com/api/webhooks/..." />
            </div>
          </CardContent>
        )}
        <CardFooter>
          <Button onClick={() => saveWebhook("discord", discordUrl)} disabled={saving === "discord"}>
            {saving === "discord" ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
            Save Discord Settings
          </Button>
        </CardFooter>
      </Card>

      {/* Teams */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Microsoft Teams</CardTitle>
              <CardDescription>Send notifications to a Teams channel via webhook</CardDescription>
            </div>
            <Switch checked={teams.enabled} onCheckedChange={(v) => setTeams(s => ({ ...s, enabled: v }))} />
          </div>
        </CardHeader>
        {teams.enabled && (
          <CardContent>
            <div className="space-y-2">
              <Label>Webhook URL {teams.webhook_url_set && <span className="text-xs text-green-500">(set)</span>}</Label>
              <Input value={teamsUrl} onChange={e => setTeamsUrl(e.target.value)} placeholder="https://outlook.office.com/webhook/..." />
            </div>
          </CardContent>
        )}
        <CardFooter>
          <Button onClick={() => saveWebhook("teams", teamsUrl)} disabled={saving === "teams"}>
            {saving === "teams" ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
            Save Teams Settings
          </Button>
        </CardFooter>
      </Card>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Settings</h2>
        <p className="text-muted-foreground">Manage application settings and configuration.</p>
      </div>

      <Tabs defaultValue="general">
        <TabsList className="mb-4">
          <TabsTrigger value="general">General</TabsTrigger>
          <TabsTrigger value="compression">Compression</TabsTrigger>
          <TabsTrigger value="encryption">Encryption</TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
        </TabsList>

        <TabsContent value="general"><GeneralTab /></TabsContent>
        <TabsContent value="compression"><CompressionTab /></TabsContent>
        <TabsContent value="encryption"><EncryptionTab /></TabsContent>
        <TabsContent value="notifications"><NotificationsTab /></TabsContent>
      </Tabs>
    </div>
  )
}
