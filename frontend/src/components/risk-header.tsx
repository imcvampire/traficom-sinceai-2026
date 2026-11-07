import { useQuery } from '@tanstack/react-query'
import { BookOpen, CircleAlert, ExternalLink, LoaderCircle, Play, RotateCw, Users } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Progress } from '@/components/ui/progress'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import type { IssueOut } from '@/lib/api'
import { formatDate, formatDateTime } from '@/lib/format'
import { errorText, riskModelQuery, useAssessIssue } from '@/lib/queries'
import { RECEIVER_SOURCE_LABEL } from './risk-meta'

function issueState(issue: IssueOut): string {
  const { job } = issue
  if (job.status === 'running') return job.total ? `Assessing ${job.done}/${job.total}` : 'Assessing…'
  if (job.status === 'failed') return 'Assessment failed'
  if (issue.assessed) return `Assessed${issue.notice_count != null ? ` · ${issue.notice_count} notices` : ''}`
  return issue.ingested ? 'Not assessed' : 'Not ingested'
}

function MethodPopover() {
  const model = useQuery(riskModelQuery)
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm">
          <BookOpen aria-hidden /> Method
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="max-h-[70vh] w-[min(36rem,calc(100vw-2rem))] gap-4 overflow-y-auto p-4">
        {model.isPending ? (
          <div className="space-y-2">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
          </div>
        ) : model.isError ? (
          <p className="text-sm text-status-critical-foreground">Could not load the method: {errorText(model.error)}</p>
        ) : (
          <>
            <div>
              <h3 className="font-semibold">Risk-informed assessment, {model.data.model_version}</h3>
              <p className="text-xs text-muted-foreground">
                Four steps, each grounded in its source. No step combines results into a score.
              </p>
            </div>
            <ol className="space-y-3">
              {model.data.method_steps.map((step) => (
                <li key={step.step} className="space-y-1">
                  <div className="text-sm font-medium">
                    Step {step.step}: {step.what}
                  </div>
                  <blockquote className="border-l-2 pl-2 text-xs text-muted-foreground italic">
                    “{step.source_wording}”
                  </blockquote>
                  <div className="text-xs text-muted-foreground">{step.cite}</div>
                </li>
              ))}
            </ol>
            <div className="space-y-1.5">
              <h4 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">References</h4>
              <ul className="space-y-1.5 text-xs">
                {model.data.references.map((ref) => (
                  <li key={ref.url}>
                    <a
                      href={ref.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 font-medium text-primary underline-offset-4 hover:underline"
                    >
                      {ref.title} <ExternalLink className="size-3" aria-hidden />
                    </a>
                    <div className="text-muted-foreground">{ref.supports}</div>
                  </li>
                ))}
              </ul>
            </div>
            <p className="border-t pt-3 text-xs text-muted-foreground">
              Full method, inputs and known weaknesses: <code className="font-mono text-foreground">{model.data.doc_path}</code>
            </p>
          </>
        )}
      </PopoverContent>
    </Popover>
  )
}

type RiskHeaderProps = {
  issues: IssueOut[]
  issue: IssueOut
  asOf: string
  asOfIsToday: boolean
  modelVersion: string | null
  onIssueChange: (ificNo: number) => void
  onAsOfChange: (asOf: string | undefined) => void
}

export function RiskHeader({ issues, issue, asOf, asOfIsToday, modelVersion, onIssueChange, onAsOfChange }: RiskHeaderProps) {
  const assess = useAssessIssue()
  const running = issue.job.status === 'running'
  const busy = running || assess.isPending
  const progress = issue.job.total ? (issue.job.done / issue.job.total) * 100 : 0

  return (
    <Card>
      <CardContent className="space-y-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
          <div className="grid min-w-0 gap-1.5">
            <Label htmlFor="risk-issue">IFIC issue</Label>
            <Select value={String(issue.ific_no)} onValueChange={(value) => onIssueChange(Number(value))}>
              <SelectTrigger id="risk-issue" className="w-full sm:w-72">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {issues.map((i) => (
                  <SelectItem key={i.ific_no} value={String(i.ific_no)}>
                    <span className="font-mono">IFIC {i.ific_no}</span>
                    <span className="text-muted-foreground">{issueState(i)}</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="risk-as-of">As of</Label>
            <div className="flex items-center gap-2">
              <Input
                id="risk-as-of"
                type="date"
                value={asOf}
                onChange={(e) => onAsOfChange(e.target.value || undefined)}
                className="w-40"
              />
              {!asOfIsToday && (
                <Button variant="ghost" size="sm" onClick={() => onAsOfChange(undefined)}>
                  Today
                </Button>
              )}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 lg:ml-auto">
            <Button
              onClick={() => assess.mutate({ ificNo: issue.ific_no, asOf })}
              disabled={busy}
              aria-describedby={running ? 'risk-job-progress' : undefined}
            >
              {busy ? (
                <LoaderCircle className="animate-spin" aria-hidden />
              ) : issue.assessed ? (
                <RotateCw aria-hidden />
              ) : (
                <Play aria-hidden />
              )}
              {running ? 'Assessing…' : issue.assessed ? 'Re-assess' : 'Assess'}
            </Button>
            <MethodPopover />
          </div>
        </div>

        {running && (
          <div id="risk-job-progress" className="space-y-1.5" role="status" aria-live="polite">
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Assessing IFIC {issue.ific_no}</span>
              <span className="tabular-nums">
                {issue.job.done} of {issue.job.total || '…'} notices
              </span>
            </div>
            <Progress value={progress} aria-label="Assessment progress" />
          </div>
        )}
        {issue.job.status === 'failed' && (
          <Alert variant="destructive">
            <CircleAlert aria-hidden />
            <AlertTitle>The last assessment of IFIC {issue.ific_no} failed</AlertTitle>
            <AlertDescription>{issue.job.error ?? 'No error detail was recorded.'}</AlertDescription>
          </Alert>
        )}

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
          <Badge variant="secondary" className="gap-1">
            <Users className="size-3" aria-hidden /> {RECEIVER_SOURCE_LABEL}
          </Badge>
          <span>
            Model <span className="font-mono text-foreground">{modelVersion ?? '—'}</span>
          </span>
          <span>
            As of <span className="text-foreground">{formatDate(asOf)}</span>
          </span>
          {issue.assessed_at && <span>Assessed {formatDateTime(issue.assessed_at)}</span>}
          <span className="font-mono break-all">{issue.path}</span>
        </div>
      </CardContent>
    </Card>
  )
}
