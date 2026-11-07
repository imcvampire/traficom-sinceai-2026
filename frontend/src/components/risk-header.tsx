import { CircleAlert, LoaderCircle, Play, RotateCw, Users } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { IssueOut } from '@/lib/api'
import { formatDate, formatDateTime } from '@/lib/format'
import { useAssessIssue } from '@/lib/queries'
import { RECEIVER_SOURCE_LABEL } from './risk-meta'
import { MethodSheet } from './risk-method'

function issueState(issue: IssueOut): string {
  const { job } = issue
  if (job.status === 'running') return job.total ? `Assessing ${job.done}/${job.total}` : 'Assessing…'
  if (job.status === 'failed') return 'Assessment failed'
  if (issue.assessed) return `Assessed${issue.notice_count != null ? ` · ${issue.notice_count} notices` : ''}`
  return issue.ingested ? 'Not assessed' : 'Not ingested'
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
            <MethodSheet />
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
