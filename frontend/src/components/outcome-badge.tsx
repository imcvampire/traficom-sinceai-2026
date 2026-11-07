import { Badge } from '@/components/ui/badge'
import type { Outcome } from '@/lib/api'
import { cn } from '@/lib/utils'
import { OUTCOME_META } from './risk-meta'

export function OutcomeBadge({ outcome, className }: { outcome: Outcome; className?: string }) {
  const meta = OUTCOME_META[outcome]
  const Icon = meta.icon
  return (
    <Badge variant="secondary" className={cn('gap-1 border-transparent font-medium', meta.badge, className)}>
      <Icon className="size-3" aria-hidden />
      {meta.label}
    </Badge>
  )
}
