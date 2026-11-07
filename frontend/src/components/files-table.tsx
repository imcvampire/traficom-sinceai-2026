import {
  type ColumnDef,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table'
import { ArrowDown, ArrowUp, ArrowUpDown, Check, ChevronLeft, ChevronRight, Copy, Search, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useNow } from '@/hooks/use-now'
import type { FileStatus, WatcherFile } from '@/lib/api'
import { formatBytes, formatDate, formatDateTime, formatRelative } from '@/lib/format'
import { cn } from '@/lib/utils'
import { countByStatus, STATUS_META, STATUS_ORDER } from '@/lib/status'
import { StatusBadge } from './status-badge'

export type FilesTableView = { status?: FileStatus; q?: string; sort?: string }

const PAGE_SIZE = 20

declare module '@tanstack/react-table' {
  interface ColumnMeta<TData, TValue> {
    className?: string
    align?: 'right'
    hint?: string
  }
}

function CopyPath({ path }: { path: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(path)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      toast.error('Could not copy to the clipboard')
    }
  }
  return (
    <div className="flex items-center gap-1">
      <code className="truncate font-mono text-xs text-muted-foreground">{path}</code>
      <Button variant="ghost" size="icon-xs" onClick={() => void copy()} aria-label={`Copy path ${path}`}>
        {copied ? <Check className="text-status-good-foreground" /> : <Copy />}
      </Button>
    </div>
  )
}

function useColumns(now: number): ColumnDef<WatcherFile>[] {
  return useMemo(
    () => [
      {
        accessorKey: 'ific_no',
        header: 'IFIC no.',
        cell: ({ row }) => (
          <a
            href={row.original.zip_url}
            className="font-mono font-medium text-primary underline-offset-4 hover:underline"
            title="Download the original zip from ITU"
          >
            {row.original.ific_no}
          </a>
        ),
      },
      {
        accessorKey: 'published_on',
        header: 'Published',
        sortUndefined: 'last',
        meta: { className: 'hidden sm:table-cell' },
        cell: ({ getValue }) => <span className="whitespace-nowrap">{formatDate(getValue<string | null>())}</span>,
      },
      {
        accessorKey: 'status',
        header: 'Status',
        filterFn: 'equals',
        sortingFn: (a, b) =>
          STATUS_ORDER.indexOf(a.original.status) - STATUS_ORDER.indexOf(b.original.status),
        cell: ({ row }) => {
          const { status, error, attempts } = row.original
          if (status !== 'failed' || !error) return <StatusBadge status={status} />
          return (
            <Tooltip>
              <TooltipTrigger asChild>
                <button type="button" className="rounded-md focus-visible:ring-2 focus-visible:ring-ring">
                  <StatusBadge status={status} />
                </button>
              </TooltipTrigger>
              <TooltipContent className="max-w-sm">
                {error} · attempt {attempts}, retried on the next check
              </TooltipContent>
            </Tooltip>
          )
        },
      },
      {
        accessorKey: 'size_bytes',
        header: 'Size',
        sortUndefined: 'last',
        meta: { align: 'right' },
        cell: ({ getValue }) => <span className="tabular-nums">{formatBytes(getValue<number | null>())}</span>,
      },
      {
        accessorKey: 'downloaded_at',
        header: 'Downloaded',
        sortUndefined: 'last',
        meta: { className: 'hidden lg:table-cell' },
        cell: ({ getValue }) => {
          const value = getValue<string | null>()
          return value ? (
            <span className="whitespace-nowrap text-muted-foreground" title={formatDateTime(value)}>
              {formatRelative(value, now)}
            </span>
          ) : (
            <span className="text-muted-foreground">—</span>
          )
        },
      },
      {
        accessorKey: 'local_path',
        header: 'Local file',
        enableSorting: false,
        meta: { className: 'hidden md:table-cell max-w-64' },
        cell: ({ getValue }) => {
          const path = getValue<string | null>()
          return path ? <CopyPath path={path} /> : <span className="text-muted-foreground">—</span>
        },
      },
    ],
    [now],
  )
}

function parseSort(sort: string | undefined): SortingState {
  const [id, dir] = (sort ?? 'ific_no.desc').split('.')
  return [{ id, desc: dir !== 'asc' }]
}

type FilesTableProps = {
  files: WatcherFile[] | undefined
  isPending: boolean
  view: FilesTableView
  onViewChange: (view: FilesTableView) => void
}

export function FilesTable({ files, isPending, view, onViewChange }: FilesTableProps) {
  const now = useNow()
  const columns = useColumns(now)
  const data = useMemo(() => files ?? [], [files])
  const counts = useMemo(() => countByStatus(data), [data])
  // Controlled table state must keep a stable identity between renders: a fresh array re-runs the row
  // models, and their page-index auto-reset then re-renders forever.
  const sorting = useMemo(() => parseSort(view.sort), [view.sort])
  const columnFilters = useMemo(() => (view.status ? [{ id: 'status', value: view.status }] : []), [view.status])

  // oxlint-disable-next-line react/incompatible-library -- no React Compiler in this app
  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      globalFilter: view.q ?? '',
      columnFilters,
    },
    initialState: { pagination: { pageSize: PAGE_SIZE } },
    onSortingChange: (updater) => {
      const next = typeof updater === 'function' ? updater(sorting) : updater
      onViewChange({ ...view, sort: next[0] ? `${next[0].id}.${next[0].desc ? 'desc' : 'asc'}` : undefined })
    },
    globalFilterFn: (row, _columnId, query: string) => {
      const needle = query.trim().toLowerCase()
      return (
        String(row.original.ific_no).includes(needle) ||
        (row.original.local_path ?? '').toLowerCase().includes(needle) ||
        (row.original.error ?? '').toLowerCase().includes(needle)
      )
    },
    autoResetPageIndex: true,
    getRowId: (row) => String(row.ific_no),
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  })

  const rows = table.getRowModel().rows
  const filteredCount = table.getFilteredRowModel().rows.length
  const filtering = Boolean(view.status || view.q)

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <ToggleGroup
          type="single"
          variant="outline"
          size="sm"
          value={view.status ?? 'all'}
          onValueChange={(value) =>
            onViewChange({ ...view, status: !value || value === 'all' ? undefined : (value as FileStatus) })
          }
          aria-label="Filter by status"
          className="flex-wrap"
        >
          <ToggleGroupItem value="all" className="gap-1.5 px-3">
            All <span className="text-muted-foreground tabular-nums">{data.length}</span>
          </ToggleGroupItem>
          {STATUS_ORDER.map((status) => (
            <ToggleGroupItem key={status} value={status} className="gap-1.5 px-3">
              <span className={cn('size-2 rounded-full', STATUS_META[status].swatch)} aria-hidden />
              {STATUS_META[status].label}
              <span className="text-muted-foreground tabular-nums">{counts[status]}</span>
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <div className="relative w-full md:w-64">
          <Search
            className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            type="search"
            value={view.q ?? ''}
            onChange={(e) => onViewChange({ ...view, q: e.target.value || undefined })}
            placeholder="Search IFIC no. or error"
            aria-label="Search issues"
            className="pl-8"
          />
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border bg-card">
        <Table>
          <TableHeader className="bg-muted/40">
            {table.getHeaderGroups().map((group) => (
              <TableRow key={group.id} className="hover:bg-transparent">
                {group.headers.map((header) => {
                  const sorted = header.column.getIsSorted()
                  const meta = header.column.columnDef.meta
                  const SortIcon = sorted === 'asc' ? ArrowUp : sorted === 'desc' ? ArrowDown : ArrowUpDown
                  return (
                    <TableHead
                      key={header.id}
                      className={cn(meta?.className, meta?.align === 'right' && 'text-right')}
                      aria-sort={sorted === 'asc' ? 'ascending' : sorted === 'desc' ? 'descending' : undefined}
                    >
                      {header.column.getCanSort() ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          className={cn('-mx-2 h-8 gap-1 px-2', meta?.align === 'right' && 'ml-auto flex')}
                          onClick={header.column.getToggleSortingHandler()}
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          <SortIcon className={cn('size-3.5', !sorted && 'opacity-40')} aria-hidden />
                        </Button>
                      ) : (
                        flexRender(header.column.columnDef.header, header.getContext())
                      )}
                    </TableHead>
                  )
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {isPending ? (
              Array.from({ length: 6 }, (_, i) => (
                <TableRow key={i}>
                  {columns.map((column, j) => (
                    <TableCell key={j} className={column.meta?.className}>
                      <Skeleton className="h-5 w-full max-w-28" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : rows.length ? (
              rows.map((row) => (
                <TableRow key={row.id} data-state={row.original.status === 'failed' ? 'failed' : undefined}>
                  {row.getVisibleCells().map((cell) => {
                    const meta = cell.column.columnDef.meta
                    return (
                      <TableCell
                        key={cell.id}
                        className={cn(meta?.className, meta?.align === 'right' && 'text-right')}
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </TableCell>
                    )
                  })}
                </TableRow>
              ))
            ) : (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={columns.length} className="h-32 text-center text-muted-foreground">
                  {filtering ? (
                    <div className="flex flex-col items-center gap-2">
                      No issues match these filters.
                      <Button variant="outline" size="sm" onClick={() => onViewChange({ sort: view.sort })}>
                        <X aria-hidden /> Clear filters
                      </Button>
                    </div>
                  ) : (
                    'No IFIC issues discovered yet. Run a check to scan the ITU source.'
                  )}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span aria-live="polite">
          {filtering ? `${filteredCount} of ${data.length} issues` : `${data.length} issues`}
        </span>
        {table.getPageCount() > 1 && (
          <div className="flex items-center gap-2">
            <span className="tabular-nums">
              Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
            </span>
            <Button
              variant="outline"
              size="icon-sm"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
              aria-label="Previous page"
            >
              <ChevronLeft />
            </Button>
            <Button
              variant="outline"
              size="icon-sm"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
              aria-label="Next page"
            >
              <ChevronRight />
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
