import { useQuery } from '@tanstack/react-query'
import { CircleAlert, ExternalLink, Lock, Pause, Radio, RefreshCw } from 'lucide-react'
import type { ReactNode } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useNow } from '@/hooks/use-now'
import type { WatcherState } from '@/lib/api'
import { formatDateTime, formatInterval, formatRelative } from '@/lib/format'
import { errorText, useCheckNow, useToggleWatcher, watcherQuery } from '@/lib/queries'
import { cn } from '@/lib/utils'

export function WatcherStateBadge({ state }: { state: WatcherState }) {
  if (state.locked)
    return (
      <Badge variant="outline" className="gap-1 text-muted-foreground">
        <Lock className="size-3" aria-hidden /> Disabled by environment
      </Badge>
    )
  if (!state.enabled)
    return (
      <Badge variant="secondary" className="gap-1 bg-status-warning/15 text-foreground">
        <Pause className="size-3" aria-hidden /> Paused
      </Badge>
    )
  return (
    <Badge variant="secondary" className="gap-1.5 bg-status-good/12 text-status-good-foreground">
      <span className="relative flex size-2" aria-hidden>
        <span className="absolute inline-flex size-full animate-ping rounded-full bg-status-good opacity-60" />
        <span className="relative inline-flex size-2 rounded-full bg-status-good" />
      </span>
      Active
    </Badge>
  )
}

function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium break-words">{children}</dd>
    </div>
  )
}

export function WatcherControls({ compact = false }: { compact?: boolean }) {
  const { data: state, error, isPending } = useQuery(watcherQuery)
  const toggle = useToggleWatcher()
  const check = useCheckNow()
  const now = useNow()

  if (isPending)
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-4 w-72" />
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-10" />
          ))}
        </CardContent>
      </Card>
    )

  if (!state)
    return (
      <Alert variant="destructive">
        <CircleAlert aria-hidden />
        <AlertTitle>Watcher API unreachable</AlertTitle>
        <AlertDescription>{errorText(error)}. Is the backend running on port 8000?</AlertDescription>
      </Alert>
    )

  const lastRun = state.last_run
  const nextCheck = state.running
    ? 'Checking now…'
    : state.next_run_at
      ? formatRelative(state.next_run_at, now)
      : state.locked || !state.enabled
        ? 'Not scheduled'
        : 'Starting…'

  return (
    <Card>
      <CardHeader className="max-sm:grid-cols-1!">
        <CardTitle className="flex flex-wrap items-center gap-2">
          <Radio className="size-4 text-primary" aria-hidden />
          Space IFIC watcher
          <WatcherStateBadge state={state} />
        </CardTitle>
        <CardDescription className="flex min-w-0 items-center gap-1">
          Watches
          <a
            href={state.source_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex min-w-0 items-center gap-1 font-medium text-foreground underline-offset-4 hover:underline"
          >
            ITU Space IFIC databases <ExternalLink className="size-3" aria-hidden />
          </a>
        </CardDescription>
        <CardAction className="flex items-center gap-4 max-sm:col-start-1 max-sm:row-span-1 max-sm:row-start-3 max-sm:mt-2 max-sm:justify-self-start">
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="flex items-center gap-2">
                <Switch
                  id={compact ? 'watcher-enabled-compact' : 'watcher-enabled'}
                  checked={state.enabled}
                  disabled={state.locked || toggle.isPending}
                  onCheckedChange={(enabled) => toggle.mutate(enabled)}
                  aria-label="Scheduled checks"
                />
                <Label
                  htmlFor={compact ? 'watcher-enabled-compact' : 'watcher-enabled'}
                  className={cn(state.locked && 'opacity-60')}
                >
                  Scheduled
                </Label>
              </div>
            </TooltipTrigger>
            <TooltipContent>
              {state.locked
                ? 'Locked: IFIC_WATCHER_ENABLED=false in the environment'
                : state.enabled
                  ? 'Pause scheduled checks'
                  : 'Resume scheduled checks (runs a check now)'}
            </TooltipContent>
          </Tooltip>
          <Button size="sm" onClick={() => check.mutate()} disabled={state.locked || state.running || check.isPending}>
            <RefreshCw className={cn(state.running && 'animate-spin')} aria-hidden />
            {state.running ? 'Checking' : 'Check now'}
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-4">
        <dl className={cn('grid gap-4', compact ? 'grid-cols-2' : 'grid-cols-2 md:grid-cols-4')}>
          <Detail label="Schedule">{formatInterval(state.interval_seconds)}</Detail>
          <Detail label="Next check">{nextCheck}</Detail>
          <Detail label="Last check">
            {lastRun ? (
              <span title={formatDateTime(lastRun.finished_at)}>{formatRelative(lastRun.finished_at, now)}</span>
            ) : (
              'Never'
            )}
          </Detail>
          <Detail label="Last result">
            {lastRun ? (
              <span
                className={cn(
                  lastRun.outcome === 'error' && 'text-status-critical-foreground',
                  lastRun.outcome === 'ok' && 'text-status-good-foreground',
                )}
              >
                {lastRun.outcome === 'ok' ? 'OK' : lastRun.outcome === 'error' ? 'Error' : 'Skipped'} ·{' '}
                {lastRun.new_count} new, {lastRun.downloaded_count} downloaded
              </span>
            ) : (
              '—'
            )}
          </Detail>
        </dl>
        {state.locked && !compact && (
          <Alert>
            <Lock aria-hidden />
            <AlertTitle>Disabled by environment</AlertTitle>
            <AlertDescription>
              Set <code className="font-mono text-xs">IFIC_WATCHER_ENABLED=true</code> in the repository env file and
              restart the API to enable the watcher.
            </AlertDescription>
          </Alert>
        )}
        {lastRun?.error && (
          <Alert variant={lastRun.outcome === 'error' ? 'destructive' : 'default'}>
            <CircleAlert aria-hidden />
            <AlertTitle>
              {lastRun.outcome === 'error' ? 'Last check failed' : 'Last check finished with issues'}
            </AlertTitle>
            <AlertDescription className="break-words">{lastRun.error}</AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  )
}
