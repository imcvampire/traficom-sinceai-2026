import { Link } from '@tanstack/react-router'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type { WatcherFile } from '@/lib/api'
import { countByStatus, STATUS_META, STATUS_ORDER } from '@/lib/status'
import { cn } from '@/lib/utils'

/** Stacked share of tracked issues per download status; each segment links to the filtered table. */
export function StatusMeter({ files }: { files: WatcherFile[] }) {
  const counts = countByStatus(files)
  const total = files.length
  const segments = STATUS_ORDER.filter((status) => counts[status] > 0)

  return (
    <div className="space-y-3">
      <div
        className="flex h-3 w-full gap-0.5 overflow-hidden rounded-full bg-muted"
        role="img"
        aria-label={STATUS_ORDER.map((s) => `${counts[s]} ${STATUS_META[s].label.toLowerCase()}`).join(', ')}
      >
        {segments.map((status) => (
          <Tooltip key={status}>
            <TooltipTrigger asChild>
              <Link
                to="/sources"
                search={{ status }}
                aria-label={`${counts[status]} ${STATUS_META[status].label}: show in table`}
                className={cn(
                  'h-full min-w-1.5 transition-opacity first:rounded-l-full last:rounded-r-full hover:opacity-80',
                  STATUS_META[status].swatch,
                )}
                style={{ flexGrow: counts[status], flexBasis: 0 }}
              />
            </TooltipTrigger>
            <TooltipContent>
              {STATUS_META[status].label}: {counts[status]} of {total} ({Math.round((counts[status] / total) * 100)}%)
            </TooltipContent>
          </Tooltip>
        ))}
      </div>
      <ul className="flex flex-wrap gap-x-5 gap-y-1.5 text-sm">
        {STATUS_ORDER.map((status) => {
          const Icon = STATUS_META[status].icon
          return (
            <li key={status} className="flex items-center gap-1.5 text-muted-foreground">
              <span className={cn('size-2.5 rounded-sm', STATUS_META[status].swatch)} aria-hidden />
              <Icon className="size-3.5" aria-hidden />
              {STATUS_META[status].label}
              <span className="font-medium text-foreground tabular-nums">{counts[status]}</span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
