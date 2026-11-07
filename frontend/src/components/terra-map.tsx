import {
  Map as MapLibre,
  Marker,
  NavigationControl,
  Popup,
  setWorkerUrl,
  type ExpressionSpecification,
  type GeoJSONSource,
  type StyleSpecification,
} from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import type { Feature, FeatureCollection } from 'geojson'
import { CircleAlert, MapPinOff } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { useTheme } from '@/hooks/use-theme'
import type { Outcome, TerraAssignment } from '@/lib/api'
import type { LonLat } from '@/lib/geo'
import { cn } from '@/lib/utils'
import { OutcomeBadge } from './outcome-badge'
import { OUTCOME_META, formatDb } from './risk-meta'
import { TERRA_OUTCOMES, formatDbuv, formatKm, formatMhz, worstPoint } from './terra-meta'

// Same basemap and worker setup as the stations map (station-map.tsx).
setWorkerUrl(workerUrl)

const TILE_URL = import.meta.env.VITE_MAP_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const ATTRIBUTION = '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors'
// Finland and the near side of its neighbours, where relevant sites sit.
const REGION_BOUNDS: [LonLat, LonLat] = [
  [14.0, 56.0],
  [40.0, 70.5],
]
const SOURCES = ['sites', 'border', 'selection'] as const
const STATUS_TOKEN: Record<Outcome, string> = {
  exceeds: '--status-critical',
  not_assessed: '--status-warning',
  meets: '--status-good',
  screened_out: '--status-neutral',
  not_applicable: '--status-neutral',
}

type Colors = Record<Outcome, string> & { background: string; foreground: string }

// MapLibre cannot read CSS variables, so resolve the theme tokens to rgb() through a canvas.
function resolveColors(): Colors {
  const style = getComputedStyle(document.documentElement)
  const ctx = document.createElement('canvas').getContext('2d', { willReadFrequently: true })
  const rgb = (name: string) => {
    const value = style.getPropertyValue(name).trim()
    if (!ctx || !value) return value || '#888'
    ctx.clearRect(0, 0, 1, 1)
    ctx.fillStyle = value
    ctx.fillRect(0, 0, 1, 1)
    const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data
    return `rgb(${r}, ${g}, ${b})`
  }
  const outcomes = Object.fromEntries(TERRA_OUTCOMES.map((o) => [o, rgb(STATUS_TOKEN[o])])) as Record<Outcome, string>
  return { ...outcomes, background: rgb('--background'), foreground: rgb('--foreground') }
}

const outcomeColor = (c: Colors): ExpressionSpecification => [
  'match',
  ['get', 'outcome'],
  ...TERRA_OUTCOMES.flatMap((o) => [o, c[o]]),
  c.foreground,
] as unknown as ExpressionSpecification

const collection = (features: Feature[]): FeatureCollection => ({ type: 'FeatureCollection', features })

function baseStyle(): StyleSpecification {
  return {
    version: 8,
    sources: { osm: { type: 'raster', tiles: [TILE_URL], tileSize: 256, maxzoom: 19, attribution: ATTRIBUTION } },
    layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
  }
}

function addLayers(map: MapLibre, c: Colors) {
  for (const id of SOURCES) map.addSource(id, { type: 'geojson', data: collection([]) })
  map.addLayer({
    id: 'selection-line',
    type: 'line',
    source: 'selection',
    filter: ['==', ['geometry-type'], 'LineString'],
    layout: { 'line-cap': 'round' },
    paint: { 'line-color': c.foreground, 'line-width': 2, 'line-dasharray': [2, 1.5] },
  })
  // Worst Finnish point of every exceeding site: a hollow ring in the outcome colour.
  map.addLayer({
    id: 'border',
    type: 'circle',
    source: 'border',
    paint: { 'circle-radius': 4, 'circle-opacity': 0, 'circle-stroke-width': 2, 'circle-stroke-color': c.exceeds },
  })
  map.addLayer({
    id: 'site',
    type: 'circle',
    source: 'sites',
    paint: {
      'circle-radius': 6,
      'circle-color': outcomeColor(c),
      'circle-stroke-width': 1.5,
      'circle-stroke-color': c.background,
    },
  })
  map.addLayer({
    id: 'site-selected',
    type: 'circle',
    source: 'sites',
    filter: ['==', ['get', 'terrakey'], -1],
    paint: { 'circle-radius': 10, 'circle-opacity': 0, 'circle-stroke-width': 2, 'circle-stroke-color': c.foreground },
  })
  map.addLayer({
    id: 'selection-point',
    type: 'circle',
    source: 'selection',
    filter: ['==', ['geometry-type'], 'Point'],
    paint: { 'circle-radius': 5, 'circle-color': c.foreground, 'circle-stroke-width': 1.5, 'circle-stroke-color': c.background },
  })
}

const lonLat = (p: { lat: number; lon: number }): LonLat => [p.lon, p.lat]

function sitesData(rows: TerraAssignment[]) {
  const sites: Feature[] = []
  const border: Feature[] = []
  for (const a of rows) {
    if (!a.site) continue
    // Exceeding sites last so they draw on top of the others.
    sites.push({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: lonLat(a.site) },
      properties: { terrakey: a.terrakey, outcome: a.outcome, rank: a.outcome === 'exceeds' ? 1 : 0 },
    })
    const point = worstPoint(a)
    if (a.outcome === 'exceeds' && point)
      border.push({ type: 'Feature', geometry: { type: 'Point', coordinates: lonLat(point) }, properties: {} })
  }
  sites.sort((x, y) => x.properties!.rank - y.properties!.rank)
  return { sites: collection(sites), border: collection(border) }
}

function tooltip(a: TerraAssignment): HTMLElement {
  const root = document.createElement('div')
  root.className = 'space-y-0.5 text-xs'
  const title = document.createElement('div')
  title.className = 'font-medium'
  title.textContent = `${a.adm} ${a.adm_ref_id ?? `#${a.terrakey}`}`
  root.append(title)
  const rows: [string, string][] = [
    ['Outcome', OUTCOME_META[a.outcome].label],
    ['Site', a.site?.name ?? '—'],
    ['f', formatMhz(a.f_mhz)],
    ['E', formatDbuv(a.e_dbuv)],
    ['To Finland', formatKm(a.relevance.distance_km)],
  ]
  for (const [label, value] of rows) {
    const row = document.createElement('div')
    const name = document.createElement('span')
    name.className = 'text-muted-foreground'
    name.textContent = `${label}: `
    row.append(name, value)
    root.append(row)
  }
  return root
}

function labelElement(a: TerraAssignment): HTMLElement {
  const el = document.createElement('div')
  el.className = 'rounded-md border bg-background/95 px-1.5 py-0.5 text-xs font-medium whitespace-nowrap text-foreground shadow'
  el.textContent = `E ${formatDbuv(a.e_dbuv)}${a.margin_db != null ? ` (${formatDb(a.margin_db)})` : ''}`
  return el
}

type CanvasProps = {
  rows: TerraAssignment[]
  current: TerraAssignment | undefined
  dark: boolean
  onSelect: (terrakey: number | undefined) => void
  onTileError: (failed: boolean) => void
  onMapError: (message: string) => void
}

/** The MapLibre map, created once and updated from props; the overlays and the selection live in `TerraMap`. */
function MapCanvas(props: CanvasProps) {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibre | null>(null)
  const latest = useRef(props)
  const byKey = useRef(new Map<number, TerraAssignment>())
  const [ready, setReady] = useState(false)

  useEffect(() => {
    latest.current = props
  })

  useEffect(() => {
    if (!container.current) return
    let map: MapLibre
    try {
      map = new MapLibre({
        container: container.current,
        style: baseStyle(),
        bounds: REGION_BOUNDS,
        fitBoundsOptions: { padding: 24 },
        attributionControl: { compact: true },
      })
    } catch (err) {
      latest.current.onMapError(err instanceof Error ? err.message : String(err))
      return
    }
    mapRef.current = map
    map.addControl(new NavigationControl({ showCompass: false }), 'top-right')
    const popup = new Popup({ closeButton: false, closeOnClick: false, offset: 10, maxWidth: '260px' })
    map.on('load', () => {
      addLayers(map, resolveColors())
      setReady(true)
    })
    map.on('error', (e) => {
      if ('sourceId' in e && e.sourceId === 'osm') latest.current.onTileError(true)
    })
    map.on('data', (e) => {
      if (e.dataType === 'source' && 'sourceId' in e && e.sourceId === 'osm' && 'tile' in e && e.tile)
        latest.current.onTileError(false)
    })
    map.on('mouseenter', 'site', () => (map.getCanvas().style.cursor = 'pointer'))
    map.on('mouseleave', 'site', () => {
      map.getCanvas().style.cursor = ''
      popup.remove()
    })
    map.on('mousemove', 'site', (e) => {
      const key = e.features?.[0]?.properties?.terrakey as number | undefined
      const a = key != null ? byKey.current.get(key) : undefined
      if (a?.site) popup.setLngLat(lonLat(a.site)).setDOMContent(tooltip(a)).addTo(map)
    })
    map.on('click', (e) => {
      const { x, y } = e.point
      const hits = map.queryRenderedFeatures(
        [
          [x - 6, y - 6],
          [x + 6, y + 6],
        ],
        { layers: ['site'] },
      )
      // The topmost hit comes first, and exceeding sites are drawn last, so they win a tie.
      latest.current.onSelect(hits.length ? (hits[0].properties.terrakey as number) : undefined)
    })
    return () => {
      popup.remove()
      map.remove()
      mapRef.current = null
      setReady(false)
    }
  }, [])

  const { rows, current, dark } = props

  useEffect(() => {
    byKey.current = new Map(rows.map((a) => [a.terrakey, a]))
    const map = mapRef.current
    if (!ready || !map) return
    const data = sitesData(rows)
    map.getSource<GeoJSONSource>('sites')?.setData(data.sites)
    map.getSource<GeoJSONSource>('border')?.setData(data.border)
  }, [ready, rows])

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    map.setFilter('site-selected', ['==', ['get', 'terrakey'], current?.terrakey ?? -1])
    const point = current && worstPoint(current)
    const features: Feature[] =
      current?.site && point
        ? [
            { type: 'Feature', geometry: { type: 'LineString', coordinates: [lonLat(current.site), lonLat(point)] }, properties: {} },
            { type: 'Feature', geometry: { type: 'Point', coordinates: lonLat(point) }, properties: {} },
          ]
        : []
    map.getSource<GeoJSONSource>('selection')?.setData(collection(features))
    if (!current || !point) return
    const marker = new Marker({ element: labelElement(current), anchor: 'left', offset: [10, 0] })
      .setLngLat(lonLat(point))
      .addTo(map)
    return () => void marker.remove()
  }, [ready, current])

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    // The theme class flips in the same commit; read the tokens on the next frame.
    const frame = requestAnimationFrame(() => {
      const c = resolveColors()
      map.setPaintProperty('osm', 'raster-brightness-max', dark ? 0.55 : 1)
      map.setPaintProperty('osm', 'raster-saturation', dark ? -0.6 : 0)
      map.setPaintProperty('site', 'circle-color', outcomeColor(c))
      map.setPaintProperty('site', 'circle-stroke-color', c.background)
      map.setPaintProperty('site-selected', 'circle-stroke-color', c.foreground)
      map.setPaintProperty('border', 'circle-stroke-color', c.exceeds)
      map.setPaintProperty('selection-line', 'line-color', c.foreground)
      map.setPaintProperty('selection-point', 'circle-color', c.foreground)
      map.setPaintProperty('selection-point', 'circle-stroke-color', c.background)
    })
    return () => cancelAnimationFrame(frame)
  }, [ready, dark])

  // MapLibre's own CSS makes its container position: relative, so the absolute box is a wrapper.
  return (
    <div className="absolute inset-0">
      <div ref={container} className="size-full" role="region" aria-label="Map of relevant transmitter sites" />
    </div>
  )
}

type TerraMapProps = {
  /** The rows the findings filters return; only relevant transmitters with a site are drawn. */
  assignments: TerraAssignment[]
  selected?: number
  onOpen: (terrakey: number) => void
}

export function TerraMap({ assignments, selected: initial, onOpen }: TerraMapProps) {
  const { resolvedTheme } = useTheme()
  const [mapError, setMapError] = useState<string | null>(null)
  const [tileError, setTileError] = useState(false)
  const [selected, setSelected] = useState<number | undefined>(initial)

  const rows = useMemo(
    () => assignments.filter((a) => a.relevance.relevant && a.role !== 'rx' && a.site != null),
    [assignments],
  )
  const current = useMemo(() => (selected != null ? rows.find((a) => a.terrakey === selected) : undefined), [rows, selected])

  const counts = useMemo(() => {
    const c = Object.fromEntries(TERRA_OUTCOMES.map((o) => [o, 0])) as Record<Outcome, number>
    for (const a of rows) c[a.outcome]++
    return c
  }, [rows])

  if (mapError)
    return (
      <Alert variant="destructive">
        <MapPinOff aria-hidden />
        <AlertTitle>The map cannot start</AlertTitle>
        <AlertDescription>WebGL is unavailable in this browser. {mapError}</AlertDescription>
      </Alert>
    )

  const point = current && worstPoint(current)
  return (
    <div className="relative h-[65svh] min-h-[420px] overflow-hidden rounded-xl border">
      <MapCanvas
        rows={rows}
        current={current}
        dark={resolvedTheme === 'dark'}
        onSelect={setSelected}
        onTileError={setTileError}
        onMapError={setMapError}
      />

      <ul className="absolute top-2 left-2 space-y-1 rounded-md bg-background/90 p-2 text-xs shadow" aria-label="Legend">
        {TERRA_OUTCOMES.filter((o) => counts[o] > 0).map((o) => {
          const Icon = OUTCOME_META[o].icon
          return (
            <li key={o} className="flex items-center gap-1.5">
              <span className={cn('size-2.5 rounded-full', OUTCOME_META[o].swatch)} aria-hidden />
              <Icon className="size-3" aria-hidden />
              {OUTCOME_META[o].label}
              <span className="ml-auto pl-2 tabular-nums text-muted-foreground">{counts[o]}</span>
            </li>
          )
        })}
        {counts.exceeds > 0 && (
          <li className="flex items-center gap-1.5 border-t pt-1 text-muted-foreground">
            <span className="size-2.5 rounded-full border-2 border-status-critical" aria-hidden />
            Worst Finnish point of an exceeding site
          </li>
        )}
        {rows.length === 0 && <li className="text-muted-foreground">No relevant transmitter matches the filters.</li>}
      </ul>

      {tileError && (
        <div className="absolute bottom-8 left-2 flex items-center gap-1.5 rounded-md bg-background/90 px-2 py-1 text-xs shadow" role="status">
          <CircleAlert className="size-3.5" aria-hidden />
          Basemap tiles failed to load; sites still show.
        </div>
      )}

      {current && (
        <div className="absolute right-2 bottom-8 w-72 space-y-2 rounded-md border bg-popover p-3 text-sm text-popover-foreground shadow-md">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{current.adm}</span>
            <span className="font-mono text-xs">{current.adm_ref_id ?? `#${current.terrakey}`}</span>
            <OutcomeBadge outcome={current.outcome} />
          </div>
          <dl className="grid grid-cols-2 gap-1 text-xs">
            <dt className="text-muted-foreground">Site</dt>
            <dd>{current.site?.name ?? '—'}</dd>
            <dt className="text-muted-foreground">E at worst point</dt>
            <dd className="tabular-nums">{formatDbuv(current.e_dbuv)}</dd>
            <dt className="text-muted-foreground">Trigger</dt>
            <dd className="tabular-nums">{formatDbuv(current.trigger_dbuv)}</dd>
            <dt className="text-muted-foreground">Path length</dt>
            <dd className="tabular-nums">{point ? formatKm(point.distance_km) : '—'}</dd>
          </dl>
          <div className="flex gap-2">
            <Button size="sm" onClick={() => onOpen(current.terrakey)}>
              Open evidence
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setSelected(undefined)}>
              Clear
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
