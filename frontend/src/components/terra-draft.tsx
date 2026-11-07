import { useQuery } from '@tanstack/react-query'
import { ChevronDown, CircleAlert, Copy, Download, Loader2, Sparkles, TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { ApiError, type DraftPolishRejection } from '@/lib/api'
import { saveFile } from '@/lib/download'
import { chatStatusQuery, errorText, terraDraftQuery, usePolishTerraDraft } from '@/lib/queries'
import { OutcomeBadge } from './outcome-badge'
import { DRAFT_BANNER, formatDb } from './risk-meta'
import { LETTER_KIND_META, formatDbuv, formatDbw, formatKhz, formatM, formatMhz } from './terra-meta'
import { TermHint } from './term-hint'

type TerraDraftProps = { ificNo: number; adm: string; assessedAt: string | null }

/** Why a polish failed, with the protected tokens a rejected rewrite dropped or introduced. */
function polishFailure(err: unknown): { title: string; detail: string; missing: string[]; added: string[] } {
  if (err instanceof ApiError && err.status === 422) {
    const body = err.body as Partial<DraftPolishRejection> | undefined
    return { title: 'Polish rejected, the template text is kept', detail: err.message, missing: body?.missing ?? [], added: body?.added ?? [] }
  }
  if (err instanceof ApiError && err.status === 429)
    return { title: 'LLM busy', detail: 'Another LLM answer is being generated, try again shortly.', missing: [], added: [] }
  if (err instanceof ApiError && err.status === 503)
    return { title: 'Polish is disabled', detail: err.message, missing: [], added: [] }
  return { title: 'Polish failed, the template text is kept', detail: errorText(err), missing: [], added: [] }
}

/** Mounted per issue and administration (keyed by the page), so a polished letter never outlives its inputs. */
export function TerraDraft({ ificNo, adm, assessedAt }: TerraDraftProps) {
  const draft = useQuery(terraDraftQuery(ificNo, adm, assessedAt))
  const chat = useQuery(chatStatusQuery)
  const polish = usePolishTerraDraft()
  const [polished, setPolished] = useState<string | null>(null)
  const [view, setView] = useState<'template' | 'polished'>('template')

  if (draft.isPending)
    return (
      <div className="space-y-3">
        <Skeleton className="h-6 w-2/3" />
        <Skeleton className="h-64" />
      </div>
    )
  if (draft.isError) {
    if (draft.error instanceof ApiError && draft.error.status === 409)
      return (
        <p className="rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
          {draft.error.message.replace(/^no concern to describe: /, 'No concern to describe: ')}. No draft letter is
          produced for {adm}.
        </p>
      )
    return (
      <Alert variant="destructive">
        <CircleAlert aria-hidden />
        <AlertTitle>Could not build the draft to {adm}</AlertTitle>
        <AlertDescription>{errorText(draft.error)}</AlertDescription>
      </Alert>
    )
  }

  const d = draft.data
  const kind = LETTER_KIND_META[d.kind]
  const showPolished = view === 'polished' && polished != null
  const letter = showPolished ? polished : d.letter_md
  const fileName = `brific${d.ific_no}-${d.adm}-${d.kind}${showPolished ? '-polished' : ''}.md`
  const chatOff = chat.data?.enabled === false
  const polishReason = chatOff ? (chat.data?.reason ?? 'The LLM provider is not configured.') : null
  const failure = polish.isError ? polishFailure(polish.error) : null

  const copy = () =>
    navigator.clipboard.writeText(letter).then(
      () => toast.success('Letter copied'),
      (err) => toast.error('Could not copy the letter', { description: errorText(err) }),
    )

  const runPolish = () =>
    polish.mutate(
      { ificNo, adm },
      {
        onSuccess: (out) => {
          setPolished(out.letter_md)
          setView('polished')
          toast.success('Prose polished', { description: `${out.model ? `By ${out.model}. ` : ''}Every protected fact was kept.` })
        },
      },
    )

  const polishButton = (
    <Button variant="outline" size="sm" onClick={runPolish} disabled={chatOff || polish.isPending}>
      {polish.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <Sparkles aria-hidden />} Polish with LLM
    </Button>
  )

  return (
    <div className="space-y-3">
      <p className="rounded-md bg-status-warning/15 px-2 py-1 text-xs font-semibold tracking-wide uppercase">
        {DRAFT_BANNER}
      </p>
      <dl className="grid grid-cols-1 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
        <div className="min-w-0">
          <dt className="text-xs text-muted-foreground">Kind</dt>
          <dd className="font-medium">
            <TermHint hint={kind.description}>{kind.label}</TermHint>
          </dd>
        </div>
        <div className="min-w-0">
          <dt className="text-xs text-muted-foreground">To</dt>
          <dd className="font-medium break-words">
            {d.adm_name ? `${d.adm_name} (${d.adm})` : `${d.adm} (name not in the reference table)`}
          </dd>
        </div>
        <div className="min-w-0">
          <dt className="text-xs text-muted-foreground">Assignments in the annex</dt>
          <dd className="font-medium tabular-nums">{d.annex.length}</dd>
        </div>
      </dl>

      {d.warnings.length > 0 && (
        <Alert>
          <TriangleAlert aria-hidden />
          <AlertTitle>Check before use</AlertTitle>
          <AlertDescription>
            <ul className="list-disc space-y-0.5 pl-4">
              {d.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      {failure && (
        <Alert variant="destructive">
          <CircleAlert aria-hidden />
          <AlertTitle>{failure.title}</AlertTitle>
          <AlertDescription>
            <p>{failure.detail}</p>
            {failure.missing.length > 0 && (
              <p>
                Dropped: <span className="font-mono">{failure.missing.join(', ')}</span>
              </p>
            )}
            {failure.added.length > 0 && (
              <p>
                Added: <span className="font-mono">{failure.added.join(', ')}</span>
              </p>
            )}
          </AlertDescription>
        </Alert>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {polished && (
          <ToggleGroup
            type="single"
            size="sm"
            variant="outline"
            value={view}
            onValueChange={(v) => v && setView(v as 'template' | 'polished')}
            aria-label="Letter text"
          >
            <ToggleGroupItem value="template">Template</ToggleGroupItem>
            <ToggleGroupItem value="polished">Polished</ToggleGroupItem>
          </ToggleGroup>
        )}
        <div className="ml-auto flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={copy}>
            <Copy aria-hidden /> Copy
          </Button>
          <Button variant="outline" size="sm" onClick={() => saveFile(fileName, letter, 'text/markdown;charset=utf-8')}>
            <Download aria-hidden /> Download .md
          </Button>
          {polishReason ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <span tabIndex={0}>{polishButton}</span>
              </TooltipTrigger>
              <TooltipContent>Polish is disabled: {polishReason}</TooltipContent>
            </Tooltip>
          ) : (
            polishButton
          )}
        </div>
      </div>

      <pre
        className="max-h-[32rem] overflow-auto rounded-lg border bg-muted/30 p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap"
        aria-label={`Draft letter, ${showPolished ? 'polished' : 'template'} text`}
      >
        {letter}
      </pre>
      <p className="text-xs text-muted-foreground">
        The header, annex and basis always come from the template; a polish rewrites the body paragraphs only and is
        rejected if any protected token (number, date, provision, identifier or administration code) changes.
      </p>

      <section className="space-y-2">
        <h3 className="text-sm font-semibold">Annex</h3>
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Ref</TableHead>
                <TableHead>Outcome</TableHead>
                <TableHead className="text-right">f</TableHead>
                <TableHead className="text-right">Bandwidth</TableHead>
                <TableHead className="text-right">e.r.p.</TableHead>
                <TableHead className="text-right">h1</TableHead>
                <TableHead>Criterion</TableHead>
                <TableHead className="text-right">Trigger</TableHead>
                <TableHead className="text-right">E</TableHead>
                <TableHead className="text-right">Margin</TableHead>
                <TableHead>FIN coordination</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {d.annex.map((r, i) => (
                <TableRow key={`${r.adm_ref_id ?? ''}-${i}`}>
                  <TableCell className="font-mono text-xs">{r.adm_ref_id ?? '—'}</TableCell>
                  <TableCell>
                    <OutcomeBadge outcome={r.outcome} />
                  </TableCell>
                  <TableCell className="text-right whitespace-nowrap tabular-nums">{formatMhz(r.f_mhz)}</TableCell>
                  <TableCell className="text-right whitespace-nowrap tabular-nums">{formatKhz(r.bw_khz)}</TableCell>
                  <TableCell className="text-right whitespace-nowrap tabular-nums">{formatDbw(r.erp_dbw)}</TableCell>
                  <TableCell className="text-right whitespace-nowrap tabular-nums">{formatM(r.h1_m)}</TableCell>
                  <TableCell className="text-xs">
                    <span className="font-mono">{r.criterion_id ?? '—'}</span>
                    {r.applicability && <span className="text-muted-foreground"> ({r.applicability})</span>}
                  </TableCell>
                  <TableCell className="text-right whitespace-nowrap tabular-nums">{formatDbuv(r.trigger_dbuv)}</TableCell>
                  <TableCell className="text-right whitespace-nowrap tabular-nums">{formatDbuv(r.e_dbuv)}</TableCell>
                  <TableCell className="text-right whitespace-nowrap tabular-nums">{formatDb(r.margin_db)}</TableCell>
                  <TableCell className="text-xs">{r.fin_coord ?? '—'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </section>

      {d.basis.length > 0 && (
        <section className="space-y-1">
          <h3 className="text-sm font-semibold">Basis</h3>
          <ul className="list-disc space-y-0.5 pl-4 text-xs">
            {d.basis.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
        </section>
      )}

      <Collapsible className="rounded-lg border">
        <CollapsibleTrigger className="group flex w-full items-center justify-between px-3 py-2 text-sm font-medium">
          Reviewer notes · Internal – do not send
          <ChevronDown className="size-4 transition-transform group-data-[state=open]:rotate-180" aria-hidden />
        </CollapsibleTrigger>
        <CollapsibleContent>
          <ul className="list-disc space-y-1 border-t px-3 py-2 pl-7 text-xs">
            {d.reviewer_notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}
