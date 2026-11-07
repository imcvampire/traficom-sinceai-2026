import { useQuery } from '@tanstack/react-query'
import { getRouteApi } from '@tanstack/react-router'
import { CircleAlert } from 'lucide-react'
import { FilesTable, type FilesTableView } from '@/components/files-table'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { WatcherControls } from '@/components/watcher-controls'
import { errorText, filesQuery } from '@/lib/queries'

const route = getRouteApi('/sources')

export function SourcesPage() {
  const view = route.useSearch()
  const navigate = route.useNavigate()
  const files = useQuery(filesQuery)

  const setView = (next: FilesTableView) => void navigate({ search: next, replace: true })

  return (
    <>
      <section className="space-y-1">
        <h2 className="text-2xl font-semibold tracking-tight">Space IFIC sources</h2>
        <p className="text-sm text-muted-foreground">
          Each newly published IFIC database is downloaded and extracted for analysis. Filters and sorting are kept in
          the URL, so you can share a view.
        </p>
      </section>

      <WatcherControls />

      {files.isError && !files.data ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden />
          <AlertTitle>Could not load issues</AlertTitle>
          <AlertDescription>{errorText(files.error)}</AlertDescription>
        </Alert>
      ) : (
        <FilesTable files={files.data} isPending={files.isPending} view={view} onViewChange={setView} />
      )}
    </>
  )
}
