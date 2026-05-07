import { Link, useLocation } from "react-router-dom"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  LayoutDashboard,
  Database,
  HardDrive,
  CalendarClock,
  Settings,
  Archive,
  TerminalSquare,
  Users,
  ClipboardList,
} from "lucide-react"
import { useAuth } from "@/context/auth-context"

interface SidebarProps extends React.HTMLAttributes<HTMLDivElement> {}

export function Sidebar({ className }: SidebarProps) {
  const location = useLocation()
  const pathname = location.pathname
  const { hasRole } = useAuth()

  const routes = [
    {
      href: "/",
      label: "Dashboard",
      icon: LayoutDashboard,
      active: pathname === "/",
      show: true,
    },
    {
      href: "/databases",
      label: "Databases",
      icon: Database,
      active: pathname === "/databases" || pathname.startsWith("/databases/"),
      show: true,
    },
    {
      href: "/query",
      label: "Query",
      icon: TerminalSquare,
      active: pathname.startsWith("/query"),
      show: true,
    },
    {
      href: "/backups",
      label: "Backups",
      icon: Archive,
      active: pathname.startsWith("/backups"),
      show: true,
    },
    {
      href: "/storage",
      label: "Storage",
      icon: HardDrive,
      active: pathname.startsWith("/storage"),
      show: true,
    },
    {
      href: "/schedules",
      label: "Schedules",
      icon: CalendarClock,
      active: pathname.startsWith("/schedules"),
      show: true,
    },
    {
      href: "/settings",
      label: "Settings",
      icon: Settings,
      active: pathname.startsWith("/settings"),
      show: hasRole(["admin"]),
    },
    {
      href: "/users",
      label: "Users",
      icon: Users,
      active: pathname.startsWith("/users"),
      show: hasRole(["admin"]),
    },
    {
      href: "/audit",
      label: "Audit Log",
      icon: ClipboardList,
      active: pathname.startsWith("/audit"),
      show: hasRole(["admin"]),
    },
  ]

  return (
    <div className={cn("pb-12 h-full border-r bg-card", className)}>
      <div className="space-y-4 py-4">
        <div className="px-3 py-2">
          <h2 className="mb-2 px-4 text-lg font-semibold tracking-tight">
            DB Manager
          </h2>
          <div className="space-y-1">
            {routes.filter((r) => r.show).map((route) => (
              <Button
                key={route.href}
                variant={route.active ? "secondary" : "ghost"}
                className="w-full justify-start"
                asChild
              >
                <Link to={route.href}>
                  <route.icon className="mr-2 h-4 w-4" />
                  {route.label}
                </Link>
              </Button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
