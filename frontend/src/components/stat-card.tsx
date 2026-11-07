import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { TermHint } from './term-hint'

type StatCardProps = {
  label: string
  labelHint?: ReactNode
  value: ReactNode
  hint?: ReactNode
  icon: LucideIcon
  loading?: boolean
  tone?: 'default' | 'critical'
  onClick?: () => void
  pressed?: boolean
}

export function StatCard({
  label,
  labelHint,
  value,
  hint,
  icon: Icon,
  loading,
  tone = 'default',
  onClick,
  pressed,
}: StatCardProps) {
  const title = onClick ? (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={pressed}
      className="text-left after:absolute after:inset-0 after:rounded-[inherit] focus-visible:outline-none"
    >
      {label}
    </button>
  ) : labelHint ? (
    <TermHint hint={labelHint}>{label}</TermHint>
  ) : (
    <span>{label}</span>
  )
  const card = (
    <Card
      className={cn(
        'gap-0 py-4',
        onClick &&
          'relative cursor-pointer transition-colors hover:bg-muted/40 has-[button:focus-visible]:ring-2 has-[button:focus-visible]:ring-ring has-[button[aria-pressed=true]]:ring-2 has-[button[aria-pressed=true]]:ring-ring/60',
      )}
    >
      <CardContent className="px-4">
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          {title}
          <Icon
            className={cn('size-4', tone === 'critical' ? 'text-status-critical-foreground' : 'text-primary')}
            aria-hidden
          />
        </div>
        {loading ? (
          <Skeleton className="mt-2 h-8 w-24" />
        ) : (
          <div
            className={cn(
              'mt-1 text-2xl font-semibold tracking-tight',
              tone === 'critical' && 'text-status-critical-foreground',
            )}
          >
            {value}
          </div>
        )}
        {hint && <div className="mt-1 truncate text-xs text-muted-foreground">{hint}</div>}
      </CardContent>
    </Card>
  )
  if (!onClick || !labelHint) return card
  return (
    <Tooltip>
      <TooltipTrigger asChild>{card}</TooltipTrigger>
      <TooltipContent>{labelHint}</TooltipContent>
    </Tooltip>
  )
}
