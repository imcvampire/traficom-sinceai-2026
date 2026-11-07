import { useQuery } from '@tanstack/react-query'
import { getRouteApi } from '@tanstack/react-router'
import { CircleAlert } from 'lucide-react'
import { useState } from 'react'
import { FilesTable, type FilesTableView } from '@/components/files-table'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { WatcherControls } from '@/components/watcher-controls'
import { errorText, filesQuery, terrestrialFilesQuery, watcherQuery } from '@/lib/queries'

const route = getRouteApi('/sources')

export function SourcesPage() {
  const view = route.useSearch()
  const navigate = route.useNavigate()
  const files = useQuery(filesQuery)
  const terrestrial = useQuery(terrestrialFilesQuery)
  const { data: watcher } = useQuery(watcherQuery)
  // The URL params belong to the Space table; the terrestrial table keeps its filters locally.
  const [terrestrialView, setTerrestrialView] = useState<FilesTableView>({})

  const setView = (next: FilesTableView) => void navigate({ search: next, replace: true })

  return (
    <>
      <section className="space-y-1">
        <h2 className="text-2xl font-semibold tracking-tight">IFIC watcher</h2>
        <p className="text-sm text-muted-foreground">
          Watches two ITU publications: the Space IFIC and the terrestrial BR IFIC.
        </p>
      </section>

      <WatcherControls />

      <section className="space-y-1">
        <h2 className="text-xl font-semibold tracking-tight">Space IFIC databases</h2>
        <p className="text-sm text-muted-foreground">
          Each newly published Space IFIC database is downloaded and extracted for analysis. Filters and sorting are
          kept in the URL, so you can share a view.
        </p>
      </section>

      {files.isError && !files.data ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden />
          <AlertTitle>Could not load Space issues</AlertTitle>
          <AlertDescription>{errorText(files.error)}</AlertDescription>
        </Alert>
      ) : (
        <FilesTable files={files.data} isPending={files.isPending} view={view} onViewChange={setView} />
      )}

      <section className="space-y-1">
        <h2 className="text-xl font-semibold tracking-tight">Terrestrial BR IFIC databases</h2>
        <p className="text-sm text-muted-foreground">
          Each newly published terrestrial BR IFIC database is downloaded and extracted for analysis.
        </p>
      </section>

      {watcher && !watcher.terrestrial_enabled && (
        <Alert>
          <CircleAlert aria-hidden />
          <AlertTitle>Terrestrial downloads are off</AlertTitle>
          <AlertDescription>
            Set <code className="font-mono text-xs">IFIC_TERRA_WATCHER_ENABLED=true</code> in the repository env file
            and restart the API to fetch them.
          </AlertDescription>
        </Alert>
      )}

      {terrestrial.isError && !terrestrial.data ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden />
          <AlertTitle>Could not load terrestrial issues</AlertTitle>
          <AlertDescription>{errorText(terrestrial.error)}</AlertDescription>
        </Alert>
      ) : (
        <FilesTable
          files={terrestrial.data}
          isPending={terrestrial.isPending}
          view={terrestrialView}
          onViewChange={setTerrestrialView}
          emptyMessage="No terrestrial BR IFIC issues yet."
        />
      )}
    </>
  )
}
