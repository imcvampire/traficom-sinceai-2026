import {
  type ColumnDef,
  type ColumnFiltersState,
  type RowSelectionState,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table'
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, Flag, Search, X } from 'lucide-react'
import { useMemo, type ReactNode } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import type { NoticeSummary, OrbitType, Outcome } from '@/lib/api'
import { cn } from '@/lib/utils'
import { OutcomeBadge } from './outcome-badge'
import {
  OUTCOME_META,
  OUTCOME_ORDER,
  ORBIT_LABEL,
  STAGE_SHORT,
  compareOutcomes,
  daysLeftText,
  formatDb,
  formatShare,
} from './risk-meta'

export type RiskTableView = {
  outcome?: Outcome
  service?: string
  adm?: string
  prov?: string
  orbit?: OrbitType
  q?: string
  sort?: string
}

export const RISK_SORT_RE = /^(outcome|network|adm|prov|share|exceedance|days_left|fin)\.(asc|desc)$/

const PAGE_SIZE = 25
const ALL = '__all'

const FILTER_KEYS = ['outcome', 'service', 'adm', 'prov', 'orbit'] as const

function useColumns(serviceLabel: (id: string) => string, onOpen: (ntcId: number) => void): ColumnDef<NoticeSummary>[] {
  return useMemo(
    () => [
      {
        id: 'select',
        enableSorting: false,
        header: ({ table }) => (
          <Checkbox
            checked={table.getIsAllPageRowsSelected() || (table.getIsSomePageRowsSelected() && 'indeterminate')}
            onCheckedChange={(value) => table.toggleAllPageRowsSelected(Boolean(value))}
            aria-label="Select all on this page for comparison"
          />
        ),
        cell: ({ row }) => (
          <Checkbox
            checked={row.getIsSelected()}
            onCheckedChange={(value) => row.toggleSelected(Boolean(value))}
            aria-label={`Compare notice ${row.original.ntc_id}`}
          />
        ),
        meta: { className: 'w-8' },
      },
      {
        id: 'outcome',
        accessorKey: 'worst_outcome',
        header: 'Worst outcome',
        filterFn: 'equals',
        sortingFn: (a, b) => compareOutcomes(a.original.worst_outcome, b.original.worst_outcome),
        cell: ({ row }) => <OutcomeBadge outcome={row.original.worst_outcome} />,
      },
      {
        id: 'network',
        accessorFn: (n) => n.sat_name ?? undefined,
        header: 'Satellite network',
        sortUndefined: 'last',
        cell: ({ row }) => (
          <button
            type="button"
            onClick={() => onOpen(row.original.ntc_id)}
            className="block max-w-56 rounded-sm text-left focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <span className="block truncate font-medium text-primary underline-offset-4 hover:underline">
              {row.original.sat_name ?? 'Unnamed network'}
            </span>
            <span className="font-mono text-xs text-muted-foreground">{row.original.ntc_id}</span>
          </button>
        ),
      },
      { id: 'adm', accessorKey: 'adm', header: 'Adm.', filterFn: 'equals' },
      {
        id: 'prov',
        accessorKey: 'prov',
        header: 'Provision',
        filterFn: 'equals',
        cell: ({ row }) => (
          <span className="flex items-center gap-1.5 whitespace-nowrap">
            <Badge variant="outline" className="font-mono">
              {STAGE_SHORT[row.original.regulatory.stage]}
            </Badge>
            <span className="text-muted-foreground">{row.original.prov}</span>
          </span>
        ),
      },
      {
        id: 'orbit',
        accessorKey: 'orbit',
        header: 'Orbit',
        filterFn: 'equals',
        enableSorting: false,
        cell: ({ row }) => <span className="whitespace-nowrap">{ORBIT_LABEL[row.original.orbit]}</span>,
      },
      {
        id: 'service',
        accessorFn: (n) => n.services_assessed,
        header: 'Services affected',
        enableSorting: false,
        filterFn: (row, _id, value: string) =>
          row.original.services_assessed.includes(value) || row.original.services_exceeding.includes(value),
        meta: { className: 'min-w-40' },
        cell: ({ row }) => {
          const { services_exceeding: exceeding, services_assessed: assessed } = row.original
          const rest = assessed.filter((s) => !exceeding.includes(s))
          if (!exceeding.length && !rest.length) return <span className="text-muted-foreground">—</span>
          return (
            <div className="flex flex-wrap gap-1">
              {exceeding.map((s) => (
                <span key={s} className="text-status-critical-foreground" title="At least one hazard exceeds">
                  {serviceLabel(s)}
                </span>
              ))}
              {rest.map((s) => (
                <span key={s} className="text-muted-foreground">
                  {serviceLabel(s)}
                </span>
              ))}
            </div>
          )
        },
      },
      {
        id: 'share',
        accessorFn: (n) => n.max_share_violating ?? undefined,
        header: 'Share violating',
        sortUndefined: 'last',
        meta: { align: 'right' },
        cell: ({ row }) => <span className="tabular-nums">{formatShare(row.original.max_share_violating)}</span>,
      },
      {
        id: 'exceedance',
        accessorFn: (n) => n.max_median_exceedance_db ?? undefined,
        header: 'Worst exceedance',
        sortUndefined: 'last',
        meta: { align: 'right' },
        cell: ({ row }) => (
          <span className="whitespace-nowrap tabular-nums">{formatDb(row.original.max_median_exceedance_db)}</span>
        ),
      },
      {
        id: 'days_left',
        accessorFn: (n) =>
          n.regulatory.window_open && n.regulatory.days_left != null && n.regulatory.days_left >= 0
            ? n.regulatory.days_left
            : undefined,
        header: 'Days left',
        sortUndefined: 'last',
        sortDescFirst: false,
        meta: { align: 'right' },
        cell: ({ row }) => {
          const { text, closed } = daysLeftText(row.original.regulatory)
          return <span className={cn('whitespace-nowrap tabular-nums', closed && 'text-muted-foreground')}>{text}</span>
        },
      },
      {
        id: 'fin',
        accessorFn: (n) => (n.regulatory.fin_identified ? 1 : 0),
        header: 'BR',
        cell: ({ row }) =>
          row.original.regulatory.fin_identified ? (
            <Badge variant="outline" className="gap-1 whitespace-nowrap">
              <Flag className="size-3 text-primary" aria-hidden /> FIN identified
            </Badge>
          ) : (
            <span className="text-muted-foreground">—</span>
          ),
      },
    ],
    [serviceLabel, onOpen],
  )
}

function parseSort(sort: string | undefined): SortingState {
  if (!sort) return []
  const [id, dir] = sort.split('.')
  return [{ id, desc: dir === 'desc' }]
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string | undefined
  options: { value: string; label: string }[]
  onChange: (value: string | undefined) => void
}) {
  return (
    <Select value={value ?? ALL} onValueChange={(next) => onChange(next === ALL ? undefined : next)}>
      <SelectTrigger size="sm" className="w-full min-w-0 sm:w-auto sm:min-w-32" aria-label={`Filter by ${label}`}>
        <SelectValue placeholder={label} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>All {label.toLowerCase()}</SelectItem>
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

const distinct = (values: string[]) => [...new Set(values)].sort((a, b) => a.localeCompare(b))

type RiskTableProps = {
  notices: NoticeSummary[] | undefined
  isPending: boolean
  view: RiskTableView
  onViewChange: (view: RiskTableView) => void
  selected: number[]
  onSelectedChange: (ids: number[]) => void
  onOpen: (ntcId: number) => void
  serviceLabel: (id: string) => string
  empty: ReactNode
}

export function RiskTable({
  notices,
  isPending,
  view,
  onViewChange,
  selected,
  onSelectedChange,
  onOpen,
  serviceLabel,
  empty,
}: RiskTableProps) {
  const columns = useColumns(serviceLabel, onOpen)
  const data = useMemo(() => notices ?? [], [notices])
  // Controlled table state must keep a stable identity between renders: a fresh array re-runs the row
  // models, and their page-index auto-reset then re-renders forever.
  const sorting = useMemo(() => parseSort(view.sort), [view.sort])
  const columnFilters = useMemo<ColumnFiltersState>(
    () => FILTER_KEYS.flatMap((id) => (view[id] ? [{ id, value: view[id] }] : [])),
    [view],
  )
  const rowSelection = useMemo<RowSelectionState>(
    () => Object.fromEntries(selected.map((id) => [String(id), true])),
    [selected],
  )

  const options = useMemo(
    () => ({
      service: distinct(data.flatMap((n) => [...n.services_assessed, ...n.services_exceeding])).map((s) => ({
        value: s,
        label: serviceLabel(s),
      })),
      adm: distinct(data.map((n) => n.adm)).map((s) => ({ value: s, label: s })),
      prov: distinct(data.map((n) => n.prov)).map((s) => ({ value: s, label: s })),
      orbit: (Object.keys(ORBIT_LABEL) as OrbitType[])
        .filter((o) => data.some((n) => n.orbit === o))
        .map((o) => ({ value: o, label: ORBIT_LABEL[o] })),
    }),
    [data, serviceLabel],
  )
  const counts = useMemo(() => {
    const result = Object.fromEntries(OUTCOME_ORDER.map((o) => [o, 0])) as Record<Outcome, number>
    for (const n of data) result[n.worst_outcome]++
    return result
  }, [data])

  // oxlint-disable-next-line react/incompatible-library -- no React Compiler in this app
  const table = useReactTable({
    data,
    columns,
    state: { sorting, columnFilters, globalFilter: view.q ?? '', rowSelection },
    initialState: { pagination: { pageSize: PAGE_SIZE } },
    onSortingChange: (updater) => {
      const next = typeof updater === 'function' ? updater(sorting) : updater
      onViewChange({ ...view, sort: next[0] ? `${next[0].id}.${next[0].desc ? 'desc' : 'asc'}` : undefined })
    },
    onRowSelectionChange: (updater) => {
      const next = typeof updater === 'function' ? updater(rowSelection) : updater
      onSelectedChange(
        Object.entries(next)
          .filter(([, on]) => on)
          .map(([id]) => Number(id)),
      )
    },
    globalFilterFn: (row, _columnId, query: string) => {
      const needle = query.trim().toLowerCase()
      const n = row.original
      return (
        String(n.ntc_id).includes(needle) ||
        (n.sat_name ?? '').toLowerCase().includes(needle) ||
        n.adm.toLowerCase().includes(needle)
      )
    },
    enableRowSelection: true,
    enableMultiSort: false,
    autoResetPageIndex: true,
    getRowId: (row) => String(row.ntc_id),
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  })

  const rows = table.getRowModel().rows
  const filteredCount = table.getFilteredRowModel().rows.length
  const filtering = Boolean(view.q || FILTER_KEYS.some((k) => view[k]))
  const set = (patch: Partial<RiskTableView>) => onViewChange({ ...view, ...patch })

  return (
    <div className="min-w-0 space-y-3">
      <ToggleGroup
        type="single"
        variant="outline"
        size="sm"
        value={view.outcome ?? 'all'}
        onValueChange={(value) => set({ outcome: !value || value === 'all' ? undefined : (value as Outcome) })}
        aria-label="Filter by worst outcome"
        className="flex-wrap"
      >
        <ToggleGroupItem value="all" className="gap-1.5 px-3">
          All <span className="text-muted-foreground tabular-nums">{data.length}</span>
        </ToggleGroupItem>
        {OUTCOME_ORDER.map((outcome) => (
          <ToggleGroupItem key={outcome} value={outcome} className="gap-1.5 px-3">
            <span className={cn('size-2 rounded-full', OUTCOME_META[outcome].swatch)} aria-hidden />
            {OUTCOME_META[outcome].label}
            <span className="text-muted-foreground tabular-nums">{counts[outcome]}</span>
          </ToggleGroupItem>
        ))}
      </ToggleGroup>

      <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-center">
        <FilterSelect label="Services" value={view.service} options={options.service} onChange={(service) => set({ service })} />
        <FilterSelect label="Administrations" value={view.adm} options={options.adm} onChange={(adm) => set({ adm })} />
        <FilterSelect label="Provisions" value={view.prov} options={options.prov} onChange={(prov) => set({ prov })} />
        <FilterSelect
          label="Orbits"
          value={view.orbit}
          options={options.orbit}
          onChange={(orbit) => set({ orbit: orbit as OrbitType | undefined })}
        />
        <div className="relative col-span-2 sm:ml-auto sm:w-64">
          <Search
            className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            type="search"
            value={view.q ?? ''}
            onChange={(e) => set({ q: e.target.value || undefined })}
            placeholder="Search network, notice or adm."
            aria-label="Search notices"
            className="h-8 pl-8"
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
                      className={cn('whitespace-nowrap', meta?.className, meta?.align === 'right' && 'text-right')}
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
                  {columns.map((_, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-5 w-full max-w-24" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : rows.length ? (
              rows.map((row) => (
                <TableRow key={row.id} data-state={row.getIsSelected() ? 'selected' : undefined}>
                  {row.getVisibleCells().map((cell) => {
                    const meta = cell.column.columnDef.meta
                    return (
                      <TableCell key={cell.id} className={cn(meta?.className, meta?.align === 'right' && 'text-right')}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </TableCell>
                    )
                  })}
                </TableRow>
              ))
            ) : (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={columns.length} className="h-32 text-center whitespace-normal text-muted-foreground">
                  {filtering && data.length ? (
                    <div className="flex flex-col items-center gap-2">
                      No notices match these filters.
                      <Button variant="outline" size="sm" onClick={() => onViewChange({ sort: view.sort })}>
                        <X aria-hidden /> Clear filters
                      </Button>
                    </div>
                  ) : (
                    empty
                  )}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between gap-2 text-sm text-muted-foreground">
        <span aria-live="polite">
          {filtering ? `${filteredCount} of ${data.length} notices` : `${data.length} notices`}
          {selected.length > 0 && ` · ${selected.length} selected`}
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
