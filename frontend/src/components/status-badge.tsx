import { Badge } from '@/components/ui/badge'
import type { FileStatus } from '@/lib/api'
import { STATUS_META } from '@/lib/status'
import { cn } from '@/lib/utils'

export function StatusBadge({ status, className }: { status: FileStatus; className?: string }) {
  const meta = STATUS_META[status]
  const Icon = meta.icon
  return (
    <Badge variant="secondary" className={cn('gap-1 border-transparent font-medium', meta.badge, className)}>
      <Icon className={cn('size-3', meta.spin && 'animate-spin')} aria-hidden />
      {meta.label}
    </Badge>
  )
}
