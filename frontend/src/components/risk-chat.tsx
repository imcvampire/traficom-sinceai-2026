import { useQuery } from '@tanstack/react-query'
import { CircleAlert, MessageSquare, RotateCcw, SendHorizontal, Square } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { ApiError, streamRiskChat, type ChatMessage } from '@/lib/api'
import { chatStatusQuery, errorText } from '@/lib/queries'
import { cn } from '@/lib/utils'

export type ChatScope =
  | { kind: 'view'; ids: number[]; filters: Record<string, string> }
  | { kind: 'notice'; ntcId: number }

export type MessagesUpdate = (update: (prev: ChatMessage[]) => ChatMessage[]) => void

export const CHAT_LABEL = 'Explanation, not assessment'

const SUGGESTIONS: Record<ChatScope['kind'], string[]> = {
  view: [
    'Which Finnish services are most affected?',
    'Which of these have an open comment window?',
    'What drives the largest exceedances?',
  ],
  notice: [
    'Why does this notice exceed?',
    'Which assumptions could change the outcome?',
    'What is the regulatory situation?',
  ],
}

function scopeText(scope: ChatScope): string {
  if (scope.kind === 'notice') return `Notice ${scope.ntcId}`
  const n = scope.ids.length
  const filters = Object.entries(scope.filters).map(([k, v]) => `${k} ${v}`)
  return [`${n} ${n === 1 ? 'notice' : 'notices'}`, ...filters].join(' · ')
}

function failureText(err: unknown): string {
  if (err instanceof ApiError && err.status === 429) return 'Another answer is being generated, try again shortly.'
  return errorText(err)
}

type RiskChatProps = {
  ificNo: number
  asOf: string
  scope: ChatScope
  messages: ChatMessage[]
  onMessagesChange: MessagesUpdate
  className?: string
}

export function RiskChat({ ificNo, asOf, scope, messages, onMessagesChange, className }: RiskChatProps) {
  const status = useQuery(chatStatusQuery)
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const enabled = status.data?.enabled === true
  const busy = pending != null

  useEffect(() => () => abortRef.current?.abort(), [])

  useEffect(() => {
    const list = listRef.current
    if (list) list.scrollTop = list.scrollHeight
  }, [messages, pending, error])

  const run = useCallback(
    async (history: ChatMessage[]) => {
      const controller = new AbortController()
      abortRef.current = controller
      setError(null)
      setPending('')
      let answer = ''
      try {
        await streamRiskChat(
          ificNo,
          asOf,
          {
            messages: history,
            ...(scope.kind === 'view' ? { ntc_ids: scope.ids, filters: scope.filters } : { ntc_id: scope.ntcId }),
          },
          {
            signal: controller.signal,
            onDelta: (text) => {
              answer += text
              setPending(answer)
            },
          },
        )
        if (answer) onMessagesChange((prev) => [...prev, { role: 'assistant', content: answer }])
        else setError('The model returned an empty answer.')
      } catch (err) {
        if (!controller.signal.aborted) setError(failureText(err))
      } finally {
        if (abortRef.current === controller) abortRef.current = null
        setPending(null)
      }
    },
    [ificNo, asOf, scope, onMessagesChange],
  )

  const send = (text: string) => {
    const content = text.trim()
    if (!content || busy || !enabled) return
    // An unanswered user turn (failed or stopped) is replaced, so the history keeps alternating.
    const base = messages.at(-1)?.role === 'user' ? messages.slice(0, -1) : messages
    const history: ChatMessage[] = [...base, { role: 'user', content }]
    onMessagesChange(() => history)
    setDraft('')
    void run(history)
  }

  const retry = () => {
    if (messages.at(-1)?.role === 'user' && !busy) void run(messages)
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      send(draft)
    }
  }

  return (
    <div className={cn('flex min-h-0 flex-col', className)}>
      <div className="space-y-0.5 border-b px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-medium">
          <MessageSquare className="size-4 text-primary" aria-hidden />
          <span className="min-w-0 truncate" title={scopeText(scope)}>
            {scopeText(scope)}
          </span>
        </div>
        <p className="text-xs text-muted-foreground">
          {CHAT_LABEL}
          {status.data?.model && <> · {status.data.model}</>}
        </p>
      </div>

      <div ref={listRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-3" aria-live="polite">
        {status.isError && (
          <Alert variant="destructive">
            <CircleAlert aria-hidden />
            <AlertTitle>Could not check the chat service</AlertTitle>
            <AlertDescription>{errorText(status.error)}</AlertDescription>
          </Alert>
        )}
        {status.data && !status.data.enabled && (
          <Alert>
            <CircleAlert aria-hidden />
            <AlertTitle>Chat is disabled</AlertTitle>
            <AlertDescription>{status.data.reason ?? 'The LLM provider is not configured.'}</AlertDescription>
          </Alert>
        )}
        {enabled && messages.length === 0 && !busy && (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">
              Answers are drawn from the stored results {scope.kind === 'view' ? 'of these notices' : 'of this notice'}{' '}
              and the method. They explain; they do not assess.
            </p>
            <ul className="space-y-1.5">
              {SUGGESTIONS[scope.kind].map((q) => (
                <li key={q}>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-auto w-full justify-start py-1.5 text-left whitespace-normal"
                    onClick={() => send(q)}
                  >
                    {q}
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {messages.map((m, i) => (
          <Bubble key={i} role={m.role}>
            {m.content}
          </Bubble>
        ))}
        {pending != null && (
          <Bubble role="assistant">
            {pending || <span className="text-muted-foreground">Thinking…</span>}
          </Bubble>
        )}
        {error && (
          <Alert variant="destructive">
            <CircleAlert aria-hidden />
            <AlertTitle>No answer</AlertTitle>
            <AlertDescription className="space-y-2">
              <p>{error}</p>
              {messages.at(-1)?.role === 'user' && (
                <Button variant="outline" size="sm" onClick={retry}>
                  <RotateCcw aria-hidden /> Retry
                </Button>
              )}
            </AlertDescription>
          </Alert>
        )}
      </div>

      <form
        className="flex items-end gap-2 border-t px-4 py-3"
        onSubmit={(e) => {
          e.preventDefault()
          send(draft)
        }}
      >
        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={enabled ? 'Ask about these results…' : 'Chat is disabled'}
          aria-label="Question"
          maxLength={8000}
          disabled={!enabled}
          className="max-h-40 min-h-10 resize-none"
        />
        {busy ? (
          <Button type="button" variant="outline" size="icon" onClick={() => abortRef.current?.abort()} aria-label="Stop">
            <Square aria-hidden />
          </Button>
        ) : (
          <Button type="submit" size="icon" disabled={!enabled || !draft.trim()} aria-label="Send">
            <SendHorizontal aria-hidden />
          </Button>
        )}
      </form>
    </div>
  )
}

function Bubble({ role, children }: { role: ChatMessage['role']; children: ReactNode }) {
  return (
    <div className={cn('flex', role === 'user' ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[90%] rounded-lg px-3 py-2 text-sm break-words whitespace-pre-wrap',
          role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted',
        )}
      >
        {children}
      </div>
    </div>
  )
}
