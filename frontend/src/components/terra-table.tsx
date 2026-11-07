import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { TerraAssignment } from '@/lib/api'
import { cn } from '@/lib/utils'
import { OutcomeBadge } from './outcome-badge'
import { formatDb } from './risk-meta'
import {
  CHANGE_LABEL,
  PUB_STATUS_LABEL,
  TERMS,
  TERRA_OUTCOME_DESCRIPTION,
  finCoordText,
  formatDbw,
  formatKhz,
  formatKm,
  formatM,
  formatMhz,
} from './terra-meta'
import { TermHint } from './term-hint'

const PAGE_SIZE = 50

type TerraTableProps = {
  assignments: TerraAssignment[] | undefined
  isPending: boolean
  selected?: number
  onOpen: (terrakey: number) => void
  empty: string
}

/** Rows in the API's order (outcome, margin, …): the table never re-ranks them. */
export function TerraTable({ assignments, isPending, selected, onOpen, empty }: TerraTableProps) {
  const [page, setPage] = useState({ rows: assignments, index: 0 })
  // A new result set (filters, issue) starts again on the first page.
  const index = page.rows === assignments ? page.index : 0
  if (page.rows !== assignments) setPage({ rows: assignments, index: 0 })

  if (isPending && !assignments)
    return (
      <div className="space-y-2">
        {Array.from({ length: 8 }, (_, i) => (
          <Skeleton key={i} className="h-10" />
        ))}
      </div>
    )

  const rows = assignments ?? []
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))
  const shown = rows.slice(index * PAGE_SIZE, (index + 1) * PAGE_SIZE)

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>
                Outcome · <TermHint hint={TERMS.margin}>margin</TermHint>
              </TableHead>
              <TableHead>Administration · ref</TableHead>
              <TableHead>Class · notice · change · status</TableHead>
              <TableHead className="text-right">f</TableHead>
              <TableHead className="text-right">Bandwidth</TableHead>
              <TableHead className="text-right">
                <TermHint hint={TERMS.erp}>e.r.p.</TermHint>
              </TableHead>
              <TableHead className="text-right">
                <TermHint hint={TERMS.h1}>h1</TermHint>
              </TableHead>
              <TableHead>Criterion</TableHead>
              <TableHead>
                <TermHint hint={TERMS.finCoord}>FIN coordination</TermHint>
              </TableHead>
              <TableHead className="text-right">
                <TermHint hint={TERMS.distance}>To Finland</TermHint>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {shown.length === 0 ? (
              <TableRow>
                <TableCell colSpan={10} className="h-24 text-center text-muted-foreground">
                  {empty}
                </TableCell>
              </TableRow>
            ) : (
              shown.map((a) => (
                <TableRow
                  key={a.terrakey}
                  data-state={a.terrakey === selected ? 'selected' : undefined}
                  className={cn('cursor-pointer', isPending && 'opacity-60')}
                  onClick={() => onOpen(a.terrakey)}
                >
                  <TableCell>
                    <button
                      type="button"
                      className="flex items-center gap-2 rounded-sm text-left focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                      onClick={(e) => {
                        e.stopPropagation()
                        onOpen(a.terrakey)
                      }}
                      aria-label={`Open ${a.adm} ${a.adm_ref_id ?? a.terrakey}`}
                      title={a.reason ?? TERRA_OUTCOME_DESCRIPTION[a.outcome]}
                    >
                      <OutcomeBadge outcome={a.outcome} />
                      <span className="tabular-nums">{a.margin_db != null ? formatDb(a.margin_db) : ''}</span>
                    </button>
                  </TableCell>
                  <TableCell>
                    <div className="font-medium">{a.adm}</div>
                    <div className="font-mono text-xs text-muted-foreground">{a.adm_ref_id ?? `#${a.terrakey}`}</div>
                  </TableCell>
                  <TableCell className="text-xs">
                    <div>
                      <span className="font-medium" title={a.stn_cls_description ?? undefined}>
                        {a.stn_cls}
                      </span>
                      {a.notice_typ && (
                        <span className="text-muted-foreground" title={a.notice_typ_description ?? undefined}>
                          {' '}
                          · {a.notice_typ}
                        </span>
                      )}
                    </div>
                    <div className="text-muted-foreground">
                      {CHANGE_LABEL[a.change]} · {PUB_STATUS_LABEL[a.pub_status.status]}
                    </div>
                  </TableCell>
                  <TableCell className="text-right whitespace-nowrap tabular-nums">{formatMhz(a.f_mhz)}</TableCell>
                  <TableCell className="text-right whitespace-nowrap tabular-nums">
                    {a.bw_khz != null ? formatKhz(a.bw_khz) : (a.bw_code ?? '—')}
                  </TableCell>
                  <TableCell className="text-right whitespace-nowrap tabular-nums">
                    {formatDbw(a.antenna?.erp_dbw)}
                  </TableCell>
                  <TableCell className="text-right whitespace-nowrap tabular-nums">
                    {formatM(a.antenna?.hgt_agl_m)}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap items-center gap-1">
                      <span className="font-mono text-xs">{a.criterion?.id ?? '—'}</span>
                      {a.criterion?.applicability === 'indicative' && (
                        <Badge variant="outline" className="text-[10px]" title={a.regulatory.applicability_reason ?? TERMS.indicative}>
                          indicative
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="max-w-48 text-xs">
                    {a.relevance.fin_coordination.length ? (
                      <span className="line-clamp-2">{finCoordText(a)}</span>
                    ) : (
                      <span className="text-muted-foreground">none</span>
                    )}
                    {a.relevance.fin_coord_required && <div className="font-medium">required</div>}
                  </TableCell>
                  <TableCell className="text-right whitespace-nowrap tabular-nums">
                    {formatKm(a.relevance.distance_km)}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
      {rows.length > PAGE_SIZE && (
        <div className="flex items-center justify-end gap-2 text-xs text-muted-foreground">
          <span className="tabular-nums">
            {index * PAGE_SIZE + 1}–{Math.min(rows.length, (index + 1) * PAGE_SIZE)} of {rows.length}
          </span>
          <Button
            variant="outline"
            size="icon-sm"
            onClick={() => setPage({ rows: assignments, index: index - 1 })}
            disabled={index === 0}
            aria-label="Previous page"
          >
            <ChevronLeft aria-hidden />
          </Button>
          <Button
            variant="outline"
            size="icon-sm"
            onClick={() => setPage({ rows: assignments, index: index + 1 })}
            disabled={index >= pages - 1}
            aria-label="Next page"
          >
            <ChevronRight aria-hidden />
          </Button>
        </div>
      )}
    </div>
  )
}
