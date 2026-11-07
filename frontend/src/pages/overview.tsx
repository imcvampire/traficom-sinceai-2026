import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { ArrowRight, BookOpen, CircleX, HardDrive, Layers, Satellite } from 'lucide-react'
import { StatCard } from '@/components/stat-card'
import { StatusBadge } from '@/components/status-badge'
import { StatusMeter } from '@/components/status-meter'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { WatcherControls } from '@/components/watcher-controls'
import { formatBytes, formatCompact, formatDate } from '@/lib/format'
import { filesQuery, healthQuery } from '@/lib/queries'
import { countByStatus } from '@/lib/status'

export function OverviewPage() {
  const files = useQuery(filesQuery)
  const health = useQuery(healthQuery)
  const list = files.data ?? []
  const counts = countByStatus(list)
  const latest = list.find((f) => f.status === 'downloaded')
  const storedBytes = list.reduce((sum, f) => sum + (f.status === 'downloaded' ? (f.size_bytes ?? 0) : 0), 0)

  return (
    <>
      <section className="space-y-1">
        <h2 className="text-2xl font-semibold tracking-tight">Spectrum monitoring</h2>
        <p className="text-sm text-muted-foreground">
          ITU Space IFIC publications tracked for analysis against the Finnish M4 frequency allocation.
        </p>
      </section>

      <section className="grid grid-cols-2 gap-4 lg:grid-cols-4" aria-label="Key figures">
        <StatCard
          label="Latest local IFIC"
          icon={Satellite}
          loading={files.isPending}
          value={latest ? <span className="font-mono">{latest.ific_no}</span> : '—'}
          hint={latest ? `Published ${formatDate(latest.published_on)}` : 'Nothing downloaded yet'}
        />
        <StatCard
          label="Issues tracked"
          icon={Layers}
          loading={files.isPending}
          value={formatCompact(list.length)}
          hint={`${counts.downloaded} downloaded · ${counts.new + counts.downloading} pending`}
        />
        <StatCard
          label="Local database size"
          icon={HardDrive}
          loading={files.isPending}
          value={formatBytes(storedBytes)}
          hint="Extracted .mdb files under data/ific"
        />
        <StatCard
          label="Failed downloads"
          icon={CircleX}
          loading={files.isPending}
          tone={counts.failed > 0 ? 'critical' : 'default'}
          value={counts.failed}
          hint={
            counts.failed > 0 ? (
              <Link to="/sources" search={{ status: 'failed' }} className="underline-offset-4 hover:underline">
                Review failures
              </Link>
            ) : (
              'Retried automatically on the next check'
            )
          }
        />
      </section>

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-6 lg:col-span-3">
          <WatcherControls compact />
          <Card>
            <CardHeader>
              <CardTitle>Download progress</CardTitle>
              <CardDescription>Status of every tracked issue. Select a segment to filter the table.</CardDescription>
            </CardHeader>
            <CardContent>
              {files.isPending ? (
                <Skeleton className="h-12 w-full" />
              ) : list.length ? (
                <StatusMeter files={list} />
              ) : (
                <p className="text-sm text-muted-foreground">No issues discovered yet.</p>
              )}
            </CardContent>
          </Card>
          <Card id="reference">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BookOpen className="size-4 text-primary" aria-hidden /> M4 reference data
              </CardTitle>
              <CardDescription>Finnish radio frequency regulation loaded into DuckDB</CardDescription>
            </CardHeader>
            <CardContent>
              {health.isPending ? (
                <Skeleton className="h-16" />
              ) : health.data ? (
                <dl className="grid grid-cols-3 gap-4">
                  <div>
                    <dt className="text-xs text-muted-foreground">Edition</dt>
                    <dd className="mt-0.5 font-medium">{health.data.db.m4_edition}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground">Allocations</dt>
                    <dd className="mt-0.5 font-medium">{formatCompact(health.data.db.tables.m4_allocation)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground">Text pages</dt>
                    <dd className="mt-0.5 font-medium">{formatCompact(health.data.db.tables.m4_page)}</dd>
                  </div>
                </dl>
              ) : (
                <p className="text-sm text-status-critical-foreground">Reference data unavailable: API unreachable.</p>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>Recent issues</CardTitle>
              <CardDescription>Newest publications first</CardDescription>
              <CardAction>
                <Button variant="ghost" size="sm" asChild>
                  <Link to="/sources">
                    View all <ArrowRight aria-hidden />
                  </Link>
                </Button>
              </CardAction>
            </CardHeader>
            <CardContent>
              {files.isPending ? (
                <div className="space-y-3">
                  {Array.from({ length: 5 }, (_, i) => (
                    <Skeleton key={i} className="h-8" />
                  ))}
                </div>
              ) : list.length ? (
                <ul className="divide-y">
                  {list.slice(0, 6).map((file) => (
                    <li key={file.ific_no} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
                      <div className="min-w-0">
                        <div className="font-mono text-sm font-medium">IFIC {file.ific_no}</div>
                        <div className="text-xs text-muted-foreground">
                          {formatDate(file.published_on)}
                          {file.size_bytes != null && ` · ${formatBytes(file.size_bytes)}`}
                        </div>
                      </div>
                      <StatusBadge status={file.status} />
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">Run a check to discover issues.</p>
              )}
            </CardContent>
          </Card>

        </div>
      </div>
    </>
  )
}
