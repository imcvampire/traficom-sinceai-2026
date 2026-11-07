import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

type StatCardProps = {
  label: string
  value: ReactNode
  hint?: ReactNode
  icon: LucideIcon
  loading?: boolean
  tone?: 'default' | 'critical'
}

export function StatCard({ label, value, hint, icon: Icon, loading, tone = 'default' }: StatCardProps) {
  return (
    <Card className="gap-0 py-4">
      <CardContent className="px-4">
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>{label}</span>
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
}
