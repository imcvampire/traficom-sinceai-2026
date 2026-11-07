import type { ReactNode } from 'react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

/** A term with a dotted underline that explains itself on hover or keyboard focus. */
export function TermHint({ children, hint, className }: { children: ReactNode; hint: ReactNode; className?: string }) {
  return (
    <Tooltip>
      <TooltipTrigger
        className={cn(
          'cursor-help rounded-sm text-left underline decoration-dotted underline-offset-4 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
          className,
        )}
      >
        {children}
      </TooltipTrigger>
      <TooltipContent>{hint}</TooltipContent>
    </Tooltip>
  )
}
