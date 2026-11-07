import { useQuery } from '@tanstack/react-query'
import { Link, Outlet, useRouterState } from '@tanstack/react-router'
import { LayoutDashboard, MapPin, Radar, RadioTower, Satellite, ShieldAlert } from 'lucide-react'
import { Separator } from '@/components/ui/separator'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import { filesQuery, healthQuery } from '@/lib/queries'
import { cn } from '@/lib/utils'
import { ThemeToggle } from './theme-toggle'

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/sources', label: 'IFIC watcher', icon: Satellite },
  { to: '/risk', label: 'Interference risk', icon: ShieldAlert },
  { to: '/terrestrial', label: 'Terrestrial land mobile', icon: RadioTower },
  { to: '/stations', label: 'Stations map', icon: MapPin },
] as const

const PAGE_TITLES: Record<string, string> = {
  '/': 'Overview',
  '/sources': 'IFIC watcher',
  '/risk': 'Interference risk',
  '/terrestrial': 'Terrestrial land mobile',
  '/stations': 'Stations map',
}

function ApiStatus() {
  const { data, isError, isPending } = useQuery(healthQuery)
  const tone = isError ? 'bg-status-critical' : isPending ? 'bg-status-neutral' : 'bg-status-good'
  const text = isError ? 'API unreachable' : isPending ? 'Connecting…' : `API v${data?.version} · connected`
  return (
    <div className="flex items-center gap-2 rounded-md px-2 py-1.5 text-xs text-muted-foreground" role="status">
      <span className={cn('size-2 shrink-0 rounded-full', tone)} aria-hidden />
      {text}
    </div>
  )
}

export function AppShell() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const { data: files } = useQuery(filesQuery)
  const failed = files?.filter((f) => f.status === 'failed').length ?? 0

  return (
    <SidebarProvider>
      <Sidebar collapsible="icon">
        <SidebarHeader>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton size="lg" asChild>
                <Link to="/">
                  <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                    <Radar className="size-4" aria-hidden />
                  </div>
                  <div className="grid flex-1 text-left leading-tight">
                    <span className="truncate text-sm font-semibold">IFIC analyser</span>
                    <span className="truncate text-xs text-muted-foreground">Finnish spectrum use</span>
                  </div>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>Monitor</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {NAV.map((item) => (
                  <SidebarMenuItem key={item.to}>
                    <SidebarMenuButton asChild isActive={pathname === item.to} tooltip={item.label}>
                      <Link to={item.to}>
                        <item.icon aria-hidden />
                        <span>{item.label}</span>
                      </Link>
                    </SidebarMenuButton>
                    {item.to === '/sources' && failed > 0 && (
                      <SidebarMenuBadge className="text-status-critical-foreground" aria-label={`${failed} failed`}>
                        {failed}
                      </SidebarMenuBadge>
                    )}
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter className="group-data-[collapsible=icon]:hidden">
          <ApiStatus />
        </SidebarFooter>
      </Sidebar>
      <SidebarInset>
        <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background/80 px-4 backdrop-blur">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-1 data-[orientation=vertical]:h-4" />
          <h1 className="text-sm font-medium">{PAGE_TITLES[pathname] ?? 'Not found'}</h1>
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 space-y-6 p-4 md:p-6">
          <Outlet />
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
