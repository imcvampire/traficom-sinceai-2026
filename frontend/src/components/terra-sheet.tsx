import { useQuery } from '@tanstack/react-query'
import { ChevronDown, CircleAlert, FileText } from 'lucide-react'
import type { ReactNode } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { TerraAssignment, TerraPoint, TerraSegment } from '@/lib/api'
import { errorText, terraAssignmentQuery, terraModelQuery } from '@/lib/queries'
import { cn } from '@/lib/utils'
import { OutcomeBadge } from './outcome-badge'
import { formatDb } from './risk-meta'
import {
  CHANGE_LABEL,
  PUB_STATUS_LABEL,
  SEGMENT_META,
  SIGNAL_META,
  TERMS,
  TERRA_OUTCOME_DESCRIPTION,
  fixed,
  formatDbuv,
  formatDbw,
  formatKhz,
  formatKm,
  formatLatLon,
  formatM,
  formatMhz,
} from './terra-meta'
import { TermHint } from './term-hint'

type TerraSheetProps = {
  ificNo: number
  terrakey: number | undefined
  assessedAt: string | null
  draftAdms: ReadonlySet<string>
  onOpenDraft: (adm: string) => void
  onClose: () => void
}

function Field({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{hint ? <TermHint hint={hint}>{label}</TermHint> : label}</dt>
      <dd className="mt-0.5 text-sm font-medium break-words">{children ?? '—'}</dd>
    </div>
  )
}

function Section({ title, hint, description, children }: { title: string; hint?: string; description?: ReactNode; children: ReactNode }) {
  return (
    <section className="min-w-0 space-y-3">
      <div>
        <h3 className="text-sm font-semibold">{hint ? <TermHint hint={hint}>{title}</TermHint> : title}</h3>
        {description && <p className="text-xs text-muted-foreground">{description}</p>}
      </div>
      {children}
    </section>
  )
}

/** The source tags whose table is one of `tables` (tags look like `issue:table:key`). */
function SourceTags({ sources, tables }: { sources: string[]; tables: string[] }) {
  const tags = sources.filter((s) => tables.some((t) => s.split(':')[1]?.startsWith(t)))
  if (!tags.length) return null
  return (
    <div className="flex flex-wrap gap-1" aria-label="Source tags">
      {tags.map((tag) => (
        <Badge key={tag} variant="outline" className="font-mono text-[10px] font-normal">
          {tag}
        </Badge>
      ))}
    </div>
  )
}

function PathSegments({ path }: { path: TerraSegment[] }) {
  const total = path.reduce((sum, s) => sum + s.length_km, 0)
  return (
    <div className="space-y-1.5">
      <div className="flex h-3 overflow-hidden rounded-sm border" role="img" aria-label="Path segments">
        {path.map((s, i) => (
          <div
            key={i}
            style={{ width: `${total ? (s.length_km / total) * 100 : 0}%`, background: SEGMENT_META[s.kind].color }}
            title={`${SEGMENT_META[s.kind].label} ${formatKm(s.length_km)}`}
          />
        ))}
      </div>
      <ul className="flex flex-wrap gap-x-3 text-xs">
        {path.map((s, i) => (
          <li key={i} className="flex items-center gap-1">
            <span className="size-2 rounded-full" style={{ background: SEGMENT_META[s.kind].color }} aria-hidden />
            {SEGMENT_META[s.kind].label} <span className="tabular-nums">{formatKm(s.length_km)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

const pointText = (p: TerraPoint) =>
  `${formatLatLon(p.lat, p.lon)} · ${formatKm(p.distance_km)} at ${fixed(p.bearing_deg, 1)}°`

function KeyValues({ values }: { values: Record<string, number | string> }) {
  return (
    <Table>
      <TableBody>
        {Object.entries(values).map(([key, value]) => (
          <TableRow key={key}>
            <TableCell className="py-1 font-mono text-xs">{key}</TableCell>
            <TableCell className="py-1 text-right font-mono text-xs tabular-nums">
              {typeof value === 'number' ? Number(value.toFixed(4)) : value}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function Notice({ a }: { a: TerraAssignment }) {
  const ant = a.antenna
  const site = a.site
  const pub = a.pub_status
  return (
    <Section title="Notice" hint={TERMS.sources} description="As notified in the BR IFIC, with the source rows each block was read from.">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Field label="Station class">
          {a.stn_cls}
          {a.stn_cls_description && <span className="block text-xs font-normal text-muted-foreground">{a.stn_cls_description}</span>}
        </Field>
        <Field label="Notice type">
          {a.notice_typ ?? '—'}
          {a.notice_typ_description && (
            <span className="block text-xs font-normal text-muted-foreground">{a.notice_typ_description}</span>
          )}
        </Field>
        <Field label="Role · intent">
          {a.role.toUpperCase()} · {a.intent}
        </Field>
        <Field label="Provision">{a.prov ?? '—'}</Field>
        <Field label="Frequency">
          {formatMhz(a.f_mhz)}
          {a.freq_min_mhz != null && a.freq_max_mhz != null && (
            <span className="block text-xs font-normal text-muted-foreground">
              {formatMhz(a.freq_min_mhz)} – {formatMhz(a.freq_max_mhz)}
            </span>
          )}
        </Field>
        <Field label="Bandwidth">
          {formatKhz(a.bw_khz)} {a.bw_code && <span className="font-mono text-xs font-normal">({a.bw_code})</span>}
        </Field>
        <Field label="Emission class">{a.emi_cls ?? '—'}</Field>
        <Field label="Received (d_rcv)">{a.d_rcv?.slice(0, 10) ?? '—'}</Field>
        <Field label="terrakey">
          <span className="font-mono">{a.terrakey}</span>
        </Field>
      </dl>
      <SourceTags sources={a.sources} tables={['fxm_terra', 'ref_stn_cls']} />

      <h4 className="pt-1 text-xs font-semibold text-muted-foreground uppercase">Site</h4>
      {site ? (
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Field label="Name">{site.name ?? '—'}</Field>
          <Field label="Country">{site.ctry ?? '—'}</Field>
          <Field label="Position">{formatLatLon(site.lat, site.lon)}</Field>
          <Field label="Altitude">{formatM(site.alt_m)}</Field>
          <Field label="Geometry">{site.geo_type ?? '—'}</Field>
        </dl>
      ) : (
        <p className="text-sm text-muted-foreground">No site in the notice.</p>
      )}
      <SourceTags sources={a.sources} tables={['fxm_geo']} />

      <h4 className="pt-1 text-xs font-semibold text-muted-foreground uppercase">Antenna</h4>
      {ant ? (
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Field label="e.r.p." hint={TERMS.erp}>
            {formatDbw(ant.erp_dbw)}
          </Field>
          <Field label="Power">
            {formatDbw(ant.pwr_dbw)}{' '}
            <span className="font-mono text-xs font-normal">{[ant.pwr_eiv, ant.pwr_xyz].filter(Boolean).join('/')}</span>
          </Field>
          <Field label="Height above ground" hint={TERMS.h1}>
            {formatM(ant.hgt_agl_m)}
          </Field>
          <Field label="Directivity">{ant.ant_dir ?? '—'}</Field>
          <Field label="Azimuth of max e.r.p.">{fixed(ant.azm_max_e, 1, '°')}</Field>
          <Field label="Max gain">{fixed(ant.gain_max, 1, 'dB')}</Field>
          <Field label="Diagram">{ant.diagram.length ? `${ant.diagram.length} points` : 'none'}</Field>
          <Field label="Antenna rows">
            {ant.rows} {ant.rows > 1 && <span className="text-xs font-normal">(row {ant.ant_key} assessed)</span>}
          </Field>
        </dl>
      ) : (
        <p className="text-sm text-muted-foreground">No antenna in the notice.</p>
      )}
      <SourceTags sources={a.sources} tables={['fxm_ant']} />

      <h4 className="pt-1 text-xs font-semibold text-muted-foreground uppercase">Publication</h4>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Field label="Status">
          {PUB_STATUS_LABEL[pub.status]}
          {pub.part && <span className="text-xs font-normal"> · part {pub.part}</span>}
        </Field>
        <Field label="First published in">{pub.first_published_in ?? '—'}</Field>
        <Field label="History">
          {pub.history.length ? pub.history.map((h) => `${h.pub_no ?? '?'}/${h.part}`).join(', ') : '—'}
        </Field>
        <Field label="Findings">
          {pub.findings.length
            ? pub.findings
                .map((f) => [f.fdg_type, f.fdg_status, f.is_favorbl ? 'favourable' : 'unfavourable'].filter(Boolean).join(' '))
                .join('; ')
            : 'none'}
        </Field>
        <Field label="Coordination">
          {a.coordination.length
            ? a.coordination.map((c) => [c.adm, c.coord_prov, c.coord_st].filter(Boolean).join(' ')).join('; ')
            : 'none'}
        </Field>
      </dl>
      <SourceTags sources={a.sources} tables={['fxm_pub', 'fxm_fdg', 'fxm_coord']} />
    </Section>
  )
}

function ChangeDiff({ a }: { a: TerraAssignment }) {
  if (a.change !== 'modified' && !a.target) return null
  return (
    <Section title="Change" description={`${CHANGE_LABEL[a.change]} notice${a.target ? `, against terrakey ${a.target.terrakey}` : ''}.`}>
      {a.target && (
        <p className="text-xs text-muted-foreground">
          Target action {a.target.action ?? '—'} · intent {a.target.intent ?? '—'}
        </p>
      )}
      {a.diff?.length ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Field</TableHead>
              <TableHead className="text-right">Before</TableHead>
              <TableHead className="text-right">After</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {a.diff.map((d) => (
              <TableRow key={`${d.table}.${d.field}.${d.ant_key ?? ''}`}>
                <TableCell className="font-mono text-xs">
                  {d.table}.{d.field}
                  {d.ant_key != null && ` (antenna ${d.ant_key})`}
                </TableCell>
                <TableCell className="text-right font-mono text-xs">{d.before ?? '—'}</TableCell>
                <TableCell className="text-right font-mono text-xs font-medium">{d.after ?? '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <p className="text-sm text-muted-foreground">
          {a.diff_reason ? `No field diff: ${a.diff_reason}.` : 'No field changed.'}
        </p>
      )}
    </Section>
  )
}

function Relevance({ a }: { a: TerraAssignment }) {
  const r = a.relevance
  return (
    <Section title="Relevance to Finland" hint={TERMS.relevant}>
      <p className="text-sm">
        <span className="font-medium">{r.relevant ? 'Relevant' : 'Not relevant'}</span>
        {r.distance_km != null && <span className="text-muted-foreground"> · {formatKm(r.distance_km)} to Finland</span>}
        {r.fin_coord_required && <span className="font-medium"> · FIN coordination required</span>}
      </p>
      <ul className="space-y-2">
        {r.signals.map((s) => (
          <li key={s.id} className="rounded-md border p-2 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <TermHint hint={SIGNAL_META[s.id].description} className="font-medium">
                {SIGNAL_META[s.id].label}
              </TermHint>
              <Badge variant={s.sufficient ? 'secondary' : 'outline'} className="text-[10px]">
                {s.sufficient ? 'sufficient' : 'context only'}
              </Badge>
              <span className="ml-auto font-mono text-[10px] text-muted-foreground">{s.source}</span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">{s.detail}</p>
          </li>
        ))}
        {!r.signals.length && <li className="text-sm text-muted-foreground">No relevance signal.</li>}
      </ul>
    </Section>
  )
}

function Regulatory({ a }: { a: TerraAssignment }) {
  const reg = a.regulatory
  return (
    <Section title="Regulatory context" description="Shown next to the technical result, never combined with it.">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Field label="RR provision">
          {reg.rr_provision.code ?? '—'}
          {reg.rr_provision.label && <span className="block text-xs font-normal text-muted-foreground">{reg.rr_provision.label}</span>}
        </Field>
        <Field label="GE06">
          {reg.ge06.applies ? 'Applies' : 'Does not apply'}
          {reg.ge06.cite && <span className="block text-xs font-normal text-muted-foreground">{reg.ge06.cite}</span>}
        </Field>
        <Field label="Criterion">
          <span className="font-mono">{reg.criterion_id ?? '—'}</span>
          {reg.criterion_applicability && (
            <span className="block text-xs font-normal">
              {reg.criterion_applicability === 'indicative' ? (
                <TermHint hint={TERMS.indicative}>indicative</TermHint>
              ) : (
                reg.criterion_applicability
              )}
              {reg.applicability_reason && <span className="text-muted-foreground">: {reg.applicability_reason}</span>}
            </span>
          )}
        </Field>
        <Field label="Governing basis">{reg.governing ?? '—'}</Field>
        <Field label="M4 rows">
          {reg.m4_rows.length ? reg.m4_rows.map((r) => `${r.id}${r.services ? ` (${r.services})` : ''}`).join(', ') : 'none'}
          <span className="block text-xs font-normal text-muted-foreground">{reg.m4_cite}</span>
        </Field>
      </dl>
      {a.criterion && (
        <p className="text-xs text-muted-foreground">
          {a.criterion.title} · {a.criterion.citation}
        </p>
      )}
      <div>
        <h4 className="text-xs font-semibold text-muted-foreground uppercase">Citations</h4>
        <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs">
          {reg.citations.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      </div>
    </Section>
  )
}

function FieldStrength({ a }: { a: TerraAssignment }) {
  const h = a.hazard
  const t1 = h.tier1
  const t2 = h.tier2
  const p = h.parameters
  return (
    <Section
      title="Field strength at the Finnish border"
      description={
        <>
          Hazard <span className="font-mono">{h.hazard_id}</span>, decided at Tier {h.tier}
          {h.reason && <> · reason <span className="font-mono">{h.reason}</span></>}.
        </>
      }
    >
      {h.trigger && (
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Field label="Trigger" hint={TERMS.trigger}>
            {formatDbuv(h.trigger.e_dbuv_m)}
          </Field>
          <Field label="Base trigger">{formatDbuv(h.trigger.base_dbuv_m)}</Field>
          <Field label="Bandwidth correction">{fixed(h.trigger.bandwidth_correction_db, 1, 'dB')}</Field>
          <Field label="Evaluated at">{h.trigger.evaluation_km ? formatKm(h.trigger.evaluation_km) : 'the border'}</Field>
          <div className="col-span-full text-xs text-muted-foreground">{h.trigger.note}</div>
        </dl>
      )}

      {t1 && (
        <div className="space-y-2 rounded-md border p-3">
          <h4 className="text-sm font-medium">
            <TermHint hint={TERMS.tier1}>Tier 1 upper bound</TermHint>
          </h4>
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Field label="E upper">{formatDbuv(t1.e_upper_dbuv)}</Field>
            <Field label="Margin upper" hint={TERMS.margin}>
              {formatDb(t1.margin_upper_db)}
            </Field>
            <Field label="Nearest point">{pointText(t1.point)}</Field>
          </dl>
          <PathSegments path={t1.path} />
        </div>
      )}

      {t2 && (
        <div className="space-y-2 rounded-md border p-3">
          <h4 className="text-sm font-medium">
            <TermHint hint={TERMS.tier2}>Tier 2 worst point</TermHint>
          </h4>
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Field label="E">{formatDbuv(t2.e_dbuv)}</Field>
            <Field label="Margin" hint={TERMS.margin}>
              {formatDb(t2.margin_db)}
            </Field>
            <Field label="Worst point">{pointText(t2.worst_point)}</Field>
            <Field label="E (P.1546)">{formatDbuv(t2.e_p1546_dbuv)}</Field>
            <Field label="Antenna attenuation">{fixed(t2.antenna_attenuation_db, 1, 'dB')}</Field>
            <Field label="Points evaluated">{t2.points_evaluated}</Field>
            <Field label="E if all land">{formatDbuv(t2.e_all_land_dbuv)}</Field>
            <Field label="E if all sea">{formatDbuv(t2.e_all_sea_dbuv)}</Field>
          </dl>
          <PathSegments path={t2.path} />
          {t2.other_levels.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Other trigger level</TableHead>
                  <TableHead>Case</TableHead>
                  <TableHead className="text-right">Margin</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {t2.other_levels.map((o) => (
                  <TableRow key={`${o.case}-${o.trigger_dbuv_m}`}>
                    <TableCell className="tabular-nums">{formatDbuv(o.trigger_dbuv_m)}</TableCell>
                    <TableCell>{o.case}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatDb(o.margin_db)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      )}

      {p && (
        <div>
          <h4 className="text-xs font-semibold text-muted-foreground uppercase">Parameters</h4>
          <KeyValues
            values={{
              'f (MHz)': p.f_mhz,
              'bandwidth (kHz)': p.bw_khz ?? '—',
              'h1 (m)': p.h1_m,
              'h2 (m)': p.h2_m,
              'time (%)': p.time_pct,
              'locations (%)': p.loc_pct,
              'e.r.p. (dBW)': p.erp_dbw,
              'receiver environment': p.rx_env,
              'bandwidth correction (dB)': p.bw_correction_db,
            }}
          />
        </div>
      )}

      {t2?.p1546 && (
        <Collapsible className="rounded-md border">
          <CollapsibleTrigger className="group flex w-full items-center justify-between px-3 py-2 text-sm font-medium">
            <span title={TERMS.p1546}>
              P.1546 intermediates{' '}
              <span className="text-xs font-normal text-muted-foreground">{t2.p1546.version}</span>
            </span>
            <ChevronDown className="size-4 transition-transform group-data-[state=open]:rotate-180" aria-hidden />
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-3 border-t px-3 py-2">
            <div>
              <h5 className="text-xs font-semibold text-muted-foreground">Inputs</h5>
              <KeyValues values={t2.p1546.inputs} />
            </div>
            <div>
              <h5 className="text-xs font-semibold text-muted-foreground">Steps</h5>
              <KeyValues values={t2.p1546.steps} />
            </div>
            {t2.p1546.assumptions.length > 0 && (
              <p className="text-xs text-muted-foreground">
                Method notes: <span className="font-mono">{t2.p1546.assumptions.join(', ')}</span>
              </p>
            )}
          </CollapsibleContent>
        </Collapsible>
      )}
    </Section>
  )
}

function Assumptions({ ids }: { ids: string[] }) {
  const model = useQuery(terraModelQuery)
  const text = new Map(model.data?.assumptions.map((a) => [a.id, a.text]) ?? [])
  return (
    <Section title="Assumptions" description="Every assumption the result depends on, by id.">
      <ul className="space-y-1.5 text-sm">
        {ids.map((id) => (
          <li key={id}>
            <span className="font-mono text-xs font-medium">{id}</span>{' '}
            <span className="text-muted-foreground">{text.get(id) ?? (model.isPending ? '…' : 'No text in the model.')}</span>
          </li>
        ))}
        {!ids.length && <li className="text-muted-foreground">None.</li>}
      </ul>
    </Section>
  )
}

export function TerraSheet({ ificNo, terrakey, assessedAt, draftAdms, onOpenDraft, onClose }: TerraSheetProps) {
  const detail = useQuery({ ...terraAssignmentQuery(ificNo, terrakey ?? 0, assessedAt), enabled: terrakey != null })
  const a = detail.data

  return (
    <Sheet open={terrakey != null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full gap-0 data-[side=right]:sm:max-w-2xl">
        <SheetHeader className="border-b pr-12">
          <SheetTitle className="flex flex-wrap items-center gap-2">
            {a ? (
              <>
                {a.adm} <span className="font-mono">{a.adm_ref_id ?? `#${a.terrakey}`}</span>
                <OutcomeBadge outcome={a.outcome} />
                {a.margin_db != null && <span className="text-sm font-normal tabular-nums">{formatDb(a.margin_db)}</span>}
              </>
            ) : (
              `Assignment ${terrakey ?? ''}`
            )}
          </SheetTitle>
          <SheetDescription>
            {a ? (a.reason ? `Reason: ${a.reason}. ` : '') + TERRA_OUTCOME_DESCRIPTION[a.outcome] : `BR IFIC ${ificNo}`}
          </SheetDescription>
          {a && draftAdms.has(a.adm) && (
            <div>
              <Button variant="outline" size="sm" onClick={() => onOpenDraft(a.adm)}>
                <FileText aria-hidden /> Draft letter to {a.adm}
              </Button>
            </div>
          )}
        </SheetHeader>
        <div className={cn('flex-1 space-y-6 overflow-y-auto p-4', detail.isFetching && !detail.isPending && 'opacity-80')}>
          {detail.isPending ? (
            <div className="space-y-3">
              <Skeleton className="h-6 w-1/2" />
              <Skeleton className="h-40" />
              <Skeleton className="h-40" />
            </div>
          ) : detail.isError ? (
            <Alert variant="destructive">
              <CircleAlert aria-hidden />
              <AlertTitle>Could not load assignment {terrakey}</AlertTitle>
              <AlertDescription>{errorText(detail.error)}</AlertDescription>
            </Alert>
          ) : (
            a && (
              <>
                <FieldStrength a={a} />
                <Relevance a={a} />
                <Regulatory a={a} />
                <ChangeDiff a={a} />
                <Notice a={a} />
                <Assumptions ids={a.assumptions} />
              </>
            )
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
