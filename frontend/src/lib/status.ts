import { CircleCheck, CircleDashed, CircleX, LoaderCircle, type LucideIcon } from 'lucide-react'
import type { FileStatus, WatcherFile } from '@/lib/api'

export const STATUS_META: Record<
  FileStatus,
  { label: string; icon: LucideIcon; swatch: string; badge: string; spin?: boolean }
> = {
  downloaded: {
    label: 'Downloaded',
    icon: CircleCheck,
    swatch: 'bg-status-good',
    badge: 'bg-status-good/12 text-status-good-foreground',
  },
  downloading: {
    label: 'Downloading',
    icon: LoaderCircle,
    swatch: 'bg-primary',
    badge: 'bg-primary/12 text-primary',
    spin: true,
  },
  new: {
    label: 'New',
    icon: CircleDashed,
    swatch: 'bg-status-neutral',
    badge: 'bg-muted text-muted-foreground',
  },
  failed: {
    label: 'Failed',
    icon: CircleX,
    swatch: 'bg-status-critical',
    badge: 'bg-status-critical/12 text-status-critical-foreground',
  },
}

export const STATUS_ORDER: FileStatus[] = ['downloaded', 'downloading', 'new', 'failed']

export function countByStatus(files: WatcherFile[]): Record<FileStatus, number> {
  const counts: Record<FileStatus, number> = { downloaded: 0, downloading: 0, new: 0, failed: 0 }
  for (const file of files) counts[file.status]++
  return counts
}
