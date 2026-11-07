import { useQuery } from '@tanstack/react-query'
import { getRouteApi } from '@tanstack/react-router'
import { CircleAlert, MapPinOff, RotateCw, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { StationLegend } from '@/components/station-legend'
import { StationMap, type StationFilter } from '@/components/station-map'
import {
  BANDS,
  DEFAULT_EXAGGERATION, DEFAULT_THRESHOLD, THRESHOLD_RANGE,
  formatHz,
  type StationsSearch,
} from '@/components/station-meta'
import { StationSheet } from '@/components/station-sheet'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { Toggle } from '@/components/ui/toggle'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { useTheme } from '@/hooks/use-theme'
import type { StationTimePct } from '@/lib/api'
import { errorText, stationsQuery } from '@/lib/queries'

const DEBOUNCE_MS = 300

const route = getRouteApi('/stations')

type Picker = { rows: number[]; x: number; y: number }

function PageIntro() {
  return (
    <section className="space-y-1">
      <h2 className="text-2xl font-semibold tracking-tight">Stations map</h2>
      <p className="max-w-3xl text-sm text-muted-foreground">
        Every special-interest station, coloured by TX frequency. A disc is the distance at which the station's ITU-R
        P.1546 field strength falls to the T/R 25-08 coordination trigger, or to the map threshold where T/R 25-08 does
        not apply. Hover a station for its values; click it for the full inputs. The view is kept in the URL.
      </p>
    </section>
  )
}

export function StationsPage() {
  const search = route.useSearch()
  const navigate = route.useNavigate()
  const { resolvedTheme } = useTheme()
  const timePct: StationTimePct = search.t ?? 10
  const threshold = search.thr ?? DEFAULT_THRESHOLD
  const view3d = search.view === '3d'
  const showContours = search.contours !== 'off'
  const exaggeration = search.ex ?? DEFAULT_EXAGGERATION

  const stations = useQuery(stationsQuery(timePct, threshold))
  const features = useMemo(() => stations.data?.features ?? [], [stations.data])

  const patch = useCallback(
    (next: Partial<StationsSearch>) => void navigate({ search: (prev) => ({ ...prev, ...next }), replace: true }),
    [navigate],
  )

  const [draftThreshold, setDraftThreshold] = useState<number | null>(null)
  useEffect(() => {
    if (draftThreshold == null) return
    const timer = setTimeout(() => {
      patch({ thr: draftThreshold === DEFAULT_THRESHOLD ? undefined : draftThreshold })
      setDraftThreshold(null)
    }, DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [draftThreshold, patch])

  const bands = useMemo(
    () => (search.band === 'none' ? [] : search.band ? search.band.split(',').map(Number) : null),
    [search.band],
  )
  const filter = useMemo<StationFilter>(() => ({ bands, q: search.q }), [bands, search.q])
  const counts = useMemo(() => {
    const c = BANDS.map(() => 0)
    for (const f of features) if (f.properties.band_bin != null) c[f.properties.band_bin]++
    return c
  }, [features])

  const toggleBand = (bin: number) => {
    const current = bands ?? BANDS.map((b) => b.bin)
    const next = current.includes(bin) ? current.filter((b) => b !== bin) : [...current, bin].sort()
    patch({ band: next.length === BANDS.length ? undefined : next.length ? next.join(',') : 'none' })
  }

  const [picker, setPicker] = useState<Picker | null>(null)
  const [tileError, setTileError] = useState(false)
  const [mapError, setMapError] = useState<string | null>(null)
  const byRow = useMemo(() => new Map(features.map((f) => [f.id, f])), [features])

  const onPick = useCallback(
    (rows: number[], point: { x: number; y: number }) => {
      if (rows.length === 1) {
        setPicker(null)
        patch({ station: rows[0] })
      } else setPicker(rows.length ? { rows, ...point } : null)
    },
    [patch],
  )
  const onTileError = useCallback(() => setTileError(true), [])
  const onTileOk = useCallback(() => setTileError(false), [])

  return (
    <>
      <PageIntro />
      <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
        <div className="space-y-1.5">
          <span className="text-xs font-medium text-muted-foreground">TX frequency</span>
          <div className="flex flex-wrap gap-1" role="group" aria-label="Frequency bands">
            {BANDS.map((b) => (
              <Toggle
                key={b.bin}
                size="sm"
                variant="outline"
                pressed={bands ? bands.includes(b.bin) : true}
                onPressedChange={() => toggleBand(b.bin)}
                aria-label={`${b.label}, ${counts[b.bin]} stations`}
              >
                <span className="size-2 rounded-full" style={{ background: `var(--band-${b.bin})` }} aria-hidden />
                {b.label}
                <span className="tabular-nums text-muted-foreground">{counts[b.bin]}</span>
              </Toggle>
            ))}
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="station-q" className="text-xs text-muted-foreground">
            Station number
          </Label>
          <Input
            id="station-q"
            inputMode="numeric"
            className="h-8 w-36"
            placeholder="e.g. 5931"
            value={search.q ?? ''}
            onChange={(e) => {
              const q = e.target.value.replace(/\D/g, '')
              patch({ q: q || undefined })
            }}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="time-pct" className="text-xs text-muted-foreground">
            Time
          </Label>
          <Select value={String(timePct)} onValueChange={(v) => patch({ t: v === '10' ? undefined : (Number(v) as StationTimePct) })}>
            <SelectTrigger id="time-pct" size="sm" className="w-28">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">1% time</SelectItem>
              <SelectItem value="10">10% time</SelectItem>
              <SelectItem value="50">50% time</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="w-60 space-y-2">
          <Label htmlFor="threshold" className="text-xs text-muted-foreground">
            Threshold {draftThreshold ?? threshold} dBµV/m, used where T/R 25-08 doesn't apply
          </Label>
          <Slider
            id="threshold"
            min={THRESHOLD_RANGE[0]}
            max={THRESHOLD_RANGE[1]}
            step={1}
            value={[draftThreshold ?? threshold]}
            onValueChange={([v]) => setDraftThreshold(v)}
            aria-label="Threshold in dBµV/m, used where T/R 25-08 doesn't apply"
          />
        </div>
        <div className="flex items-center gap-2 pb-1.5">
          <Switch
            id="contours"
            checked={showContours}
            onCheckedChange={(on) => patch({ contours: on ? undefined : 'off' })}
          />
          <Label htmlFor="contours" className="text-xs">
            Contours
          </Label>
        </div>
        <ToggleGroup
          type="single"
          size="sm"
          variant="outline"
          value={view3d ? '3d' : '2d'}
          onValueChange={(v) => v && patch({ view: v === '3d' ? '3d' : undefined })}
          aria-label="Map view"
        >
          <ToggleGroupItem value="2d">2D</ToggleGroupItem>
          <ToggleGroupItem value="3d">3D</ToggleGroupItem>
        </ToggleGroup>
      </div>

      {stations.isError && !stations.data ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden />
          <AlertTitle>Could not load stations</AlertTitle>
          <AlertDescription className="flex flex-wrap items-center gap-3">
            {errorText(stations.error)}
            <Button size="sm" variant="outline" onClick={() => void stations.refetch()}>
              <RotateCw aria-hidden />
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[1fr_18rem]">
        <Card className="relative h-[65svh] min-h-[420px] overflow-hidden p-0">
          {mapError ? (
            <div className="p-4">
              <Alert variant="destructive">
                <MapPinOff aria-hidden />
                <AlertTitle>The map cannot start</AlertTitle>
                <AlertDescription>WebGL is unavailable in this browser. {mapError}</AlertDescription>
              </Alert>
            </div>
          ) : (
            <StationMap
              features={features}
              filter={filter}
              showContours={showContours}
              view3d={view3d}
              exaggeration={exaggeration}
              selected={search.station}
              dark={resolvedTheme === 'dark'}
              onPick={onPick}
              onTileError={onTileError}
              onTileOk={onTileOk}
              onMapError={setMapError}
            />
          )}
          {stations.isPending && <Skeleton className="absolute inset-0 rounded-none" />}
          {stations.isFetching && !stations.isPending && (
            <div className="absolute top-2 left-2 rounded-md bg-background/90 px-2 py-1 text-xs shadow" role="status">
              Updating contours…
            </div>
          )}
          {tileError && (
            <div
              className="absolute bottom-8 left-2 flex items-center gap-1.5 rounded-md bg-background/90 px-2 py-1 text-xs shadow"
              role="status"
            >
              <CircleAlert className="size-3.5" aria-hidden />
              Basemap tiles failed to load; stations still show.
            </div>
          )}
          {picker && (
            <div
              className="absolute z-10 w-64 rounded-md border bg-popover p-2 text-popover-foreground shadow-md"
              style={{ left: `min(${picker.x + 8}px, calc(100% - 16.5rem))`, top: `min(${picker.y + 8}px, calc(100% - 16rem))` }}
            >
              <div className="mb-1 flex items-center justify-between px-1 text-xs font-medium">
                {picker.rows.length} stations here
                <Button size="icon-xs" variant="ghost" onClick={() => setPicker(null)} aria-label="Close">
                  <X aria-hidden />
                </Button>
              </div>
              <ul className="max-h-56 overflow-y-auto">
                {picker.rows.map((row) => {
                  const p = byRow.get(row)?.properties
                  return (
                    <li key={row}>
                      <button
                        type="button"
                        className="flex w-full items-center gap-2 rounded px-1 py-1 text-left text-xs hover:bg-accent"
                        onClick={() => {
                          setPicker(null)
                          patch({ station: row })
                        }}
                      >
                        <span
                          className="size-2 shrink-0 rounded-full"
                          style={{ background: p?.band_bin != null ? `var(--band-${p.band_bin})` : 'var(--foreground)' }}
                          aria-hidden
                        />
                        <span className="font-medium">{p?.station_no ?? row}</span>
                        <span className="ml-auto text-muted-foreground">{formatHz(p?.tx_hz)}</span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            </div>
          )}
        </Card>
        <Card>
          <CardContent>
            <StationLegend
              model={stations.data?.model}
              counts={counts}
              view3d={view3d}
              exaggeration={exaggeration}
              onExaggeration={(ex) => patch({ ex: ex === DEFAULT_EXAGGERATION ? undefined : ex })}
            />
          </CardContent>
        </Card>
      </div>

      <StationSheet
        sourceRow={search.station}
        timePct={timePct}
        threshold={threshold}
        onClose={() => patch({ station: undefined })}
      />
    </>
  )
}
