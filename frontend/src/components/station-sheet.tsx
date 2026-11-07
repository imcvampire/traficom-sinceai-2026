import { useQuery } from '@tanstack/react-query'
import { CircleAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { StationDetail, StationTimePct } from '@/lib/api'
import { errorText, stationQuery } from '@/lib/queries'
import {
  ASSUMPTION_LABEL,
  NO_CONTOUR_LABEL,
  bandLabel,
  formatDbuv,
  formatHz,
  formatM,
  formatPower,
  formatRadius,
  modelStatement,
  thresholdSourceLabel,
} from './station-meta'

type Props = {
  sourceRow: number | undefined
  timePct: StationTimePct
  threshold: number
  onClose: () => void
}

const num = new Intl.NumberFormat(undefined, { maximumFractionDigits: 3 })

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-medium">{title}</h3>
      {children}
    </section>
  )
}

function Facts({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-muted-foreground">{k}</dt>
          <dd className="min-w-0 break-words">{v}</dd>
        </div>
      ))}
    </dl>
  )
}

function Body({ d }: { d: StationDetail }) {
  const p = d.properties
  const c = p.contour
  return (
    <div className="space-y-6 px-4 pb-6">
      <Section title="Parameters">
        <Facts
          rows={[
            ['TX frequency', formatHz(p.tx_hz)],
            ['RX frequency', formatHz(p.rx_hz)],
            ['Bandwidth', formatHz(p.bandwidth_hz)],
            ['Band', bandLabel(p)],
            ['e.r.p.', formatPower(p.radiated_power_dbw)],
            ['Antenna AGL', formatM(p.effective_agl_m)],
            ['Antenna ASL', formatM(p.effective_asl_m)],
            ['Ground height', formatM(p.ground_height_m)],
            ['Directivity', p.directivity ?? '—'],
            ['Azimuth', p.azimuth_deg == null ? '—' : `${p.azimuth_deg}°`],
            ['Antenna gain', p.ant_gain_db == null ? '—' : `${p.ant_gain_db} dB`],
            ['Polarisation', p.polarisation ?? '—'],
            ['Emission class', p.emission_class ?? '—'],
            ['Licence class', p.licence_class ?? '—'],
            ['Position', `${num.format(d.geometry.coordinates[1])}° N, ${num.format(d.geometry.coordinates[0])}° E`],
          ]}
        />
      </Section>

      <Section title="Contour">
        {c ? (
          <>
            <Facts
              rows={[
                ['Radius', formatRadius(c)],
                ['Threshold', `${formatDbuv(c.threshold_dbuv)} · ${thresholdSourceLabel(c)}`],
                ...(c.threshold_citation ? [['Citation', c.threshold_citation] as [string, string]] : []),
                ...(c.threshold_note ? [['Note', c.threshold_note] as [string, string]] : []),
                ['Model', modelStatement(d.model)],
                ['Frequency', `${num.format(c.f_mhz)} MHz`],
                ['h1 / h2', `${formatM(c.h1_m)} / ${formatM(c.h2_m)}`],
                ['e.r.p.', formatPower(c.erp_dbw)],
              ]}
            />
            <ul className="list-disc space-y-0.5 pl-5 text-sm text-muted-foreground">
              {c.assumptions.map((a) => (
                <li key={a}>
                  {ASSUMPTION_LABEL[a] ?? a} <code className="text-xs">{a}</code>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            No disc: {p.no_contour_reason ? NO_CONTOUR_LABEL[p.no_contour_reason] : 'unknown reason'}{' '}
            <code className="text-xs">{p.no_contour_reason}</code>
          </p>
        )}
      </Section>

      {d.p1546_steps && (
        <Section title="P.1546 intermediates at the radius">
          <Table>
            <TableBody>
              {Object.entries(d.p1546_steps).map(([k, v]) => (
                <TableRow key={k}>
                  <TableCell className="font-mono text-xs">{k}</TableCell>
                  <TableCell className="text-right tabular-nums">{num.format(v)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Section>
      )}

      <Section title="M4 overlaps">
        {d.m4_overlaps.length ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Side</TableHead>
                <TableHead>Overlap</TableHead>
                <TableHead>Services in Finland</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {d.m4_overlaps.map((o) => (
                <TableRow key={`${o.side}-${o.m4_id}`}>
                  <TableCell className="uppercase">{o.side}</TableCell>
                  <TableCell className="whitespace-nowrap tabular-nums">
                    {formatHz(o.overlap_lower_hz)}–{formatHz(o.overlap_upper_hz)}
                  </TableCell>
                  <TableCell className="whitespace-normal">{o.services_in_finland ?? '—'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="text-sm text-muted-foreground">No overlapping M4 allocation.</p>
        )}
      </Section>

      <Section title="Quality flags">
        {p.quality_flags.length ? (
          <div className="flex flex-wrap gap-1.5">
            {p.quality_flags.map((f) => (
              <Badge key={f} variant="outline" className="font-mono">
                {f}
              </Badge>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">None.</p>
        )}
      </Section>

      <Section title="Source">
        <Facts
          rows={[
            ['Spreadsheet row', String(p.source_row)],
            ...Object.entries(d.raw).map(([k, v]) => [k, v == null || v === '' ? '—' : String(v)] as [string, string]),
          ]}
        />
      </Section>
    </div>
  )
}

export function StationSheet({ sourceRow, timePct, threshold, onClose }: Props) {
  const detail = useQuery({ ...stationQuery(sourceRow ?? 0, timePct, threshold), enabled: sourceRow != null })
  const d = detail.data?.id === sourceRow ? detail.data : undefined
  return (
    <Sheet open={sourceRow != null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>{d ? `Station ${d.properties.station_no}` : 'Station'}</SheetTitle>
          <SheetDescription>
            {d ? `${formatHz(d.properties.tx_hz)} · spreadsheet row ${d.properties.source_row}` : 'Loading station detail'}
            {d && detail.isPlaceholderData && ' · updating for the new time or threshold…'}
          </SheetDescription>
        </SheetHeader>
        {detail.isError ? (
          <div className="px-4">
            <Alert variant="destructive">
              <CircleAlert aria-hidden />
              <AlertTitle>Could not load the station</AlertTitle>
              <AlertDescription>{errorText(detail.error)}</AlertDescription>
            </Alert>
          </div>
        ) : d ? (
          <Body d={d} />
        ) : (
          <div className="space-y-3 px-4">
            <Skeleton className="h-40 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
