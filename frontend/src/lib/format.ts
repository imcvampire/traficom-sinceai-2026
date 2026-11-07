const dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })
const dateOnly = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' })
const compact = new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 })
const integer = new Intl.NumberFormat()

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit++
  }
  return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`
}

export const formatDateTime = (iso: string) => dateTime.format(new Date(iso))

export function formatDate(isoDate: string | null): string {
  if (!isoDate) return '—'
  const [y, m, d] = isoDate.split('-').map(Number)
  return dateOnly.format(new Date(y, m - 1, d))
}

export const formatCompact = (n: number) => (n < 10_000 ? integer.format(n) : compact.format(n))

export function formatRelative(iso: string, now: number): string {
  const minutes = Math.round((new Date(iso).getTime() - now) / 60_000)
  const abs = Math.abs(minutes)
  const span = abs < 1 ? 'less than a minute' : abs < 60 ? `${abs} min` : `${Math.floor(abs / 60)} h ${abs % 60} min`
  if (abs < 1) return minutes >= 0 ? 'in under a minute' : 'just now'
  return minutes > 0 ? `in ${span}` : `${span} ago`
}

export function formatInterval(seconds: number): string {
  if (seconds % 3600 === 0) return `every ${seconds / 3600} h`
  if (seconds % 60 === 0) return `every ${seconds / 60} min`
  return `every ${seconds} s`
}
