import { keepPreviousData, queryOptions, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  ApiError,
  assessIssue,
  checkNow,
  getChatStatus,
  getHealth,
  getRiskModel,
  getRiskNotice,
  getStation,
  getWatcher,
  listFiles,
  listRiskIssues,
  listRiskNotices,
  listStations,
  setWatcherEnabled,
  type IssueOut,
  type NoticeView,
  type StationTimePct,
  type WatcherState,
} from '@/lib/api'

const POLL_MS = 15_000
const POLL_RUNNING_MS = 3_000

export const queryKeys = {
  health: ['health'] as const,
  watcher: ['watcher'] as const,
  files: ['watcher', 'files'] as const,
  riskIssues: ['risk', 'issues'] as const,
  riskModel: ['risk', 'model'] as const,
  riskChat: ['risk', 'chat'] as const,
  riskNotices: (ificNo: number) => ['risk', 'issues', ificNo, 'notices'] as const,
  stations: ['stations'] as const,
}

export const healthQuery = queryOptions({
  queryKey: queryKeys.health,
  queryFn: getHealth,
  refetchInterval: 60_000,
})

export const watcherQuery = queryOptions({
  queryKey: queryKeys.watcher,
  queryFn: getWatcher,
  refetchInterval: (query) => (query.state.data?.running ? POLL_RUNNING_MS : POLL_MS),
})

export const filesQuery = queryOptions({
  queryKey: queryKeys.files,
  queryFn: listFiles,
  refetchInterval: POLL_MS,
})

export const riskIssuesQuery = queryOptions({
  queryKey: queryKeys.riskIssues,
  queryFn: listRiskIssues,
  refetchInterval: (query) =>
    query.state.data?.some((issue) => issue.job.status === 'running') ? POLL_RUNNING_MS : POLL_MS,
})

export const riskModelQuery = queryOptions({
  queryKey: queryKeys.riskModel,
  queryFn: getRiskModel,
  staleTime: Infinity,
})

export const chatStatusQuery = queryOptions({
  queryKey: queryKeys.riskChat,
  queryFn: getChatStatus,
  staleTime: Infinity,
})

// `assessedAt` is part of the key so a finished re-assessment fetches fresh results without manual invalidation.
export const riskNoticesQuery = (ificNo: number, asOf: string, view: NoticeView, assessedAt: string | null) =>
  queryOptions({
    queryKey: [...queryKeys.riskNotices(ificNo), { asOf, view, assessedAt }] as const,
    queryFn: () => listRiskNotices(ificNo, asOf, view),
    placeholderData: keepPreviousData,
  })

export const riskNoticeQuery = (ificNo: number, ntcId: number, asOf: string, assessedAt: string | null) =>
  queryOptions({
    queryKey: [...queryKeys.riskNotices(ificNo), ntcId, { asOf, assessedAt }] as const,
    queryFn: () => getRiskNotice(ificNo, ntcId, asOf),
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 1,
  })

// Contours depend only on the station data and these two inputs, so results never go stale within a session.
export const stationsQuery = (timePct: StationTimePct, threshold: number) =>
  queryOptions({
    queryKey: [...queryKeys.stations, { timePct, threshold }] as const,
    queryFn: () => listStations(timePct, threshold),
    placeholderData: keepPreviousData,
    staleTime: Infinity,
  })

export const stationQuery = (sourceRow: number, timePct: StationTimePct, threshold: number) =>
  queryOptions({
    queryKey: [...queryKeys.stations, sourceRow, { timePct, threshold }] as const,
    queryFn: () => getStation(sourceRow, timePct, threshold),
    placeholderData: keepPreviousData,
    staleTime: Infinity,
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 1,
  })

export function useAssessIssue() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ ificNo, asOf }: { ificNo: number; asOf: string }) => assessIssue(ificNo, asOf),
    onSuccess: ({ job }, { ificNo }) => {
      client.setQueryData<IssueOut[]>(queryKeys.riskIssues, (issues) =>
        issues?.map((issue) => (issue.ific_no === ificNo ? { ...issue, job } : issue)),
      )
      toast.info(`Assessing IFIC ${ificNo}`, { description: 'Progress updates every few seconds.' })
    },
    onError: (err, { ificNo }) => {
      if (err instanceof ApiError && err.status === 409)
        toast.warning(`IFIC ${ificNo} is already being assessed`, { description: err.message })
      else toast.error(`Could not assess IFIC ${ificNo}`, { description: errorText(err) })
    },
    onSettled: () => client.invalidateQueries({ queryKey: queryKeys.riskIssues, exact: true }),
  })
}

export function useToggleWatcher() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: setWatcherEnabled,
    onMutate: async (enabled) => {
      await client.cancelQueries({ queryKey: queryKeys.watcher, exact: true })
      const previous = client.getQueryData<WatcherState>(queryKeys.watcher)
      if (previous) client.setQueryData(queryKeys.watcher, { ...previous, enabled, ui_enabled: enabled })
      return { previous }
    },
    onError: (err, enabled, context) => {
      if (context?.previous) client.setQueryData(queryKeys.watcher, context.previous)
      toast.error(`Could not ${enabled ? 'resume' : 'pause'} the watcher`, { description: errorText(err) })
    },
    onSuccess: (state) => {
      client.setQueryData(queryKeys.watcher, state)
      if (state.enabled) toast.success('Watcher resumed', { description: 'A check starts now, then runs on schedule.' })
      else toast('Watcher paused', { description: 'Scheduled checks stop until you resume. Check now still works.' })
    },
    onSettled: () => client.invalidateQueries({ queryKey: queryKeys.watcher }),
  })
}

export function useCheckNow() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: checkNow,
    onSuccess: () => {
      client.setQueryData<WatcherState>(queryKeys.watcher, (state) => state && { ...state, running: true })
      toast.info('Check started', { description: 'New issues download one at a time.' })
    },
    onError: (err) => {
      const busy = err instanceof ApiError && err.status === 409 && err.message === 'check already running'
      if (busy) toast.warning('A check is already running')
      else toast.error('Check failed to start', { description: errorText(err) })
    },
    onSettled: () => client.invalidateQueries({ queryKey: queryKeys.watcher }),
  })
}

export function errorText(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}
