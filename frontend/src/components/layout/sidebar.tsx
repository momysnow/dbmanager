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
} from "lucide-react"

interface SidebarProps extends React.HTMLAttributes<HTMLDivElement> {}

export function Sidebar({ className }: SidebarProps) {
  const location = useLocation()
  const pathname = location.pathname

  const routes = [
    {
      href: "/",
      label: "Dashboard",
      icon: LayoutDashboard,
      active: pathname === "/",
    },
    {
      href: "/databases",
      label: "Databases",
      icon: Database,
      active: pathname === "/databases" || pathname.startsWith("/databases/"),
    },
    {
      href: "/query",
      label: "Query",
      icon: TerminalSquare,
      active: pathname.startsWith("/query"),
    },
    {
      href: "/backups",
      label: "Backups",
      icon: Archive,
      active: pathname.startsWith("/backups"),
    },
    {
      href: "/storage",
      label: "Storage",
      icon: HardDrive,
      active: pathname.startsWith("/storage"),
    },
    {
      href: "/schedules",
      label: "Schedules",
      icon: CalendarClock,
      active: pathname.startsWith("/schedules"),
    },
    {
      href: "/settings",
      label: "Settings",
      icon: Settings,
      active: pathname.startsWith("/settings"),
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
            {routes.map((route) => (
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
