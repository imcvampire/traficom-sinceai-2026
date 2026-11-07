import { useQuery } from '@tanstack/react-query'
import { ChevronDown, CircleAlert, Copy, Download, Loader2, Sparkles, TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Skeleton } from '@/components/ui/skeleton'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { ApiError, type Draft, type DraftPolishRejection } from '@/lib/api'
import { chatStatusQuery, draftQuery, errorText, usePolishDraft } from '@/lib/queries'
import { DRAFT_BANNER, DRAFT_KIND_META } from './risk-meta'
import { TermHint } from './term-hint'

type NoticeDraftProps = { ificNo: number; ntcId: number; asOf: string; assessedAt: string | null }

function polishFailure(err: unknown): string {
  if (err instanceof ApiError && err.status === 422) {
    const body = err.body as Partial<DraftPolishRejection> | undefined
    const tokens = [
      body?.missing?.length ? `dropped ${body.missing.join(', ')}` : '',
      body?.added?.length ? `added ${body.added.join(', ')}` : '',
    ].filter(Boolean)
    return tokens.length ? `${err.message} (${tokens.join('; ')})` : err.message
  }
  if (err instanceof ApiError && err.status === 429) return 'Another LLM answer is being generated, try again shortly.'
  return errorText(err)
}

function windowText(d: Draft): string {
  if (d.window_end == null) return `no comment window at ${d.stage}`
  if (d.days_left != null && d.days_left >= 0) return `${d.days_left} days left (window ends ${d.window_end})`
  return `window closed on ${d.window_end}`
}

function saveFile(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown;charset=utf-8' }))
  const a = Object.assign(document.createElement('a'), { href: url, download: name })
  a.click()
  URL.revokeObjectURL(url)
}

/** Mounted per notice and `as_of` (keyed by the sheet), so a polished letter never outlives its inputs. */
export function NoticeDraft({ ificNo, ntcId, asOf, assessedAt }: NoticeDraftProps) {
  const draft = useQuery(draftQuery(ificNo, ntcId, asOf, assessedAt))
  const chat = useQuery(chatStatusQuery)
  const polish = usePolishDraft()
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
          produced for this notice.
        </p>
      )
    return (
      <Alert variant="destructive">
        <CircleAlert aria-hidden />
        <AlertTitle>Could not build the draft</AlertTitle>
        <AlertDescription>{errorText(draft.error)}</AlertDescription>
      </Alert>
    )
  }

  const d = draft.data
  const kind = DRAFT_KIND_META[d.kind]
  const letter = view === 'polished' && polished ? polished : d.letter_md
  const fileName = `ific${d.ific_no}-${d.ntc_id}-${d.kind}${view === 'polished' && polished ? '-polished' : ''}.md`
  const chatOff = chat.data?.enabled === false
  const polishReason = chatOff ? (chat.data?.reason ?? 'The LLM provider is not configured.') : null

  const copy = () =>
    navigator.clipboard.writeText(letter).then(
      () => toast.success('Letter copied'),
      (err) => toast.error('Could not copy the letter', { description: errorText(err) }),
    )

  const runPolish = () =>
    polish.mutate(
      { ificNo, ntcId, asOf },
      {
        onSuccess: (out) => {
          setPolished(out.letter_md)
          setView('polished')
          toast.success('Prose polished', { description: `By ${out.model}. Every protected fact was kept.` })
        },
        onError: (err) => toast.error('Polish rejected, the template text is kept', { description: polishFailure(err) }),
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
          <dt className="text-xs text-muted-foreground">Deadline</dt>
          <dd className="font-medium">{windowText(d)}</dd>
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
          <Button variant="outline" size="sm" onClick={() => saveFile(fileName, letter)}>
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
        aria-label={`Draft letter, ${view === 'polished' && polished ? 'polished' : 'template'} text`}
      >
        {letter}
      </pre>
      <p className="text-xs text-muted-foreground">
        The header, annex and Basis line always come from the template; a polish rewrites the body paragraphs only and
        is rejected if any number, date, provision, hazard id or administration code changes.
      </p>

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
