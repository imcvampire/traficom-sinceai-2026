import {
  Map as MapLibre,
  NavigationControl,
  Popup,
  setWorkerUrl,
  type ExpressionSpecification,
  type GeoJSONSource,
  type StyleSpecification,
} from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import type { Feature, FeatureCollection } from 'geojson'
import { useEffect, useRef, useState } from 'react'
import type { StationFeature } from '@/lib/api'
import { arrowLine, circlePolygon, hexagon, type LonLat } from '@/lib/geo'
import { BANDS, formatDbuv, formatHz, formatM, formatPower, formatRadius, thresholdSourceLabel } from './station-meta'

// MapLibre looks for its worker next to its own module, which a bundle does not keep; point it at Vite's copy.
setWorkerUrl(workerUrl)

const TILE_URL = import.meta.env.VITE_MAP_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const ATTRIBUTION = '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors'
const FINLAND_BOUNDS: [LonLat, LonLat] = [
  [19.0, 59.5],
  [31.6, 70.1],
]
// Wide enough to see from zoom 6 upwards; the footprint carries no meaning, only the height does.
const MAST_RADIUS_M = 2000
const ARROW_MAX_KM = 20
const ARROW_NO_CONTOUR_KM = 5
const PITCH_3D = 55
const SOURCES = ['contours', 'azimuth', 'masts', 'sites'] as const
const BAND_PAINT = [
  ['contour-fill', 'fill-color'],
  ['contour-line', 'line-color'],
  ['contour-line-dashed', 'line-color'],
  ['azimuth', 'line-color'],
  ['mast', 'fill-extrusion-color'],
  ['site', 'circle-color'],
  ['contour-hover-fill', 'fill-color'],
] as const
const HOVER_LAYERS = ['contour-hover-fill', 'contour-hover-line'] as const
const hoverFilter = (row: number | undefined): ExpressionSpecification => ['==', ['get', 'source_row'], row ?? -1]
const FILTERED_LAYERS = ['contour-fill', 'contour-line', 'contour-line-dashed', 'azimuth', 'mast', 'site'] as const

export type StationFilter = { bands: readonly number[] | null; q?: string }

type Props = {
  features: StationFeature[]
  filter: StationFilter
  showContours: boolean
  view3d: boolean
  exaggeration: number
  selected?: number
  dark: boolean
  onPick: (rows: number[], point: { x: number; y: number }) => void
  onTileError: () => void
  onTileOk: () => void
  onMapError: (message: string) => void
}

type Colors = { bands: string[]; background: string; foreground: string }

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
  return { bands: BANDS.map((b) => rgb(`--band-${b.bin}`)), background: rgb('--background'), foreground: rgb('--foreground') }
}

const bandColor = ({ bands: b, foreground }: Colors): ExpressionSpecification =>
  ['match', ['get', 'band_bin'], 0, b[0], 1, b[1], 2, b[2], 3, b[3], 4, b[4], 5, b[5], foreground]

function stationFilter(f: StationFilter): ExpressionSpecification {
  const parts: ExpressionSpecification[] = []
  // Stations without a TX frequency (bin -1) have no band to filter on, so a band filter keeps them.
  if (f.bands) parts.push(['in', ['get', 'band_bin'], ['literal', [-1, ...f.bands]]])
  if (f.q) parts.push(['in', f.q, ['to-string', ['get', 'station_no']]])
  return ['all', ...parts] as ExpressionSpecification
}

const collection = (features: Feature[]): FeatureCollection => ({ type: 'FeatureCollection', features })

function buildSources(stations: StationFeature[]): Record<(typeof SOURCES)[number], FeatureCollection> {
  const contours: Feature[] = []
  const azimuth: Feature[] = []
  const masts: Feature[] = []
  const sites: Feature[] = []
  for (const s of stations) {
    const p = s.properties
    const center = s.geometry.coordinates
    const base = { source_row: p.source_row, station_no: p.station_no, band_bin: p.band_bin ?? -1 }
    sites.push({ type: 'Feature', id: p.source_row, geometry: s.geometry, properties: base })
    if (p.effective_agl_m != null)
      masts.push({
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: hexagon(center, MAST_RADIUS_M) },
        properties: { ...base, agl: p.effective_agl_m },
      })
    if (p.contour)
      contours.push({
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: circlePolygon(center, p.contour.radius_km) },
        properties: { ...base, dashed: p.contour.bound !== 'exact', radius: p.contour.radius_km },
      })
    if (p.directivity === 'D' && p.azimuth_deg != null)
      azimuth.push({
        type: 'Feature',
        geometry: {
          type: 'MultiLineString',
          coordinates: arrowLine(center, p.azimuth_deg, Math.min(p.contour?.radius_km ?? ARROW_NO_CONTOUR_KM, ARROW_MAX_KM)),
        },
        properties: base,
      })
  }
  // Largest discs first so smaller ones stay on top and clickable.
  contours.sort((a, b) => b.properties!.radius - a.properties!.radius)
  return { contours: collection(contours), azimuth: collection(azimuth), masts: collection(masts), sites: collection(sites) }
}

function baseStyle(): StyleSpecification {
  return {
    version: 8,
    sources: { osm: { type: 'raster', tiles: [TILE_URL], tileSize: 256, maxzoom: 19, attribution: ATTRIBUTION } },
    layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
  }
}

function addLayers(map: MapLibre, c: Colors) {
  for (const id of SOURCES) map.addSource(id, { type: 'geojson', data: collection([]) })
  const color = bandColor(c)
  map.addLayer({ id: 'contour-fill', type: 'fill', source: 'contours', paint: { 'fill-color': color, 'fill-opacity': 0.04 } })
  map.addLayer({
    id: 'contour-line',
    type: 'line',
    source: 'contours',
    filter: ['==', ['get', 'dashed'], false],
    paint: { 'line-color': color, 'line-width': 1 },
  })
  map.addLayer({
    id: 'contour-line-dashed',
    type: 'line',
    source: 'contours',
    filter: ['==', ['get', 'dashed'], true],
    paint: { 'line-color': color, 'line-width': 1, 'line-dasharray': [3, 2] },
  })
  // The hovered station's disc, drawn even when the contour layer is switched off.
  map.addLayer({
    id: 'contour-hover-fill',
    type: 'fill',
    source: 'contours',
    filter: hoverFilter(undefined),
    paint: { 'fill-color': color, 'fill-opacity': 0.25 },
  })
  map.addLayer({
    id: 'contour-hover-line',
    type: 'line',
    source: 'contours',
    filter: hoverFilter(undefined),
    // Foreground ink, not the band colour, so it stands out from the other blue outlines.
    paint: { 'line-color': c.foreground, 'line-width': 2.5 },
  })
  map.addLayer({
    id: 'azimuth',
    type: 'line',
    source: 'azimuth',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': color, 'line-width': 1.5 },
  })
  map.addLayer({
    id: 'site',
    type: 'circle',
    source: 'sites',
    paint: {
      'circle-radius': 5,
      'circle-color': color,
      'circle-stroke-width': 1.5,
      'circle-stroke-color': c.background,
      'circle-pitch-alignment': 'map',
    },
  })
  map.addLayer({
    id: 'site-selected',
    type: 'circle',
    source: 'sites',
    filter: ['==', ['get', 'source_row'], -1],
    paint: { 'circle-radius': 9, 'circle-opacity': 0, 'circle-stroke-width': 2, 'circle-stroke-color': c.foreground },
  })
  // Columns go last so in 3D they stand in front of the flat site dots.
  map.addLayer({
    id: 'mast',
    type: 'fill-extrusion',
    source: 'masts',
    layout: { visibility: 'none' },
    paint: { 'fill-extrusion-color': color, 'fill-extrusion-opacity': 0.85, 'fill-extrusion-height': ['get', 'agl'] },
  })
}

function tooltip(s: StationFeature): HTMLElement {
  const p = s.properties
  const root = document.createElement('div')
  root.className = 'space-y-0.5 text-xs'
  const rows: [string, string][] = [
    ['TX', formatHz(p.tx_hz)],
    ['Bandwidth', formatHz(p.bandwidth_hz)],
    ['e.r.p.', formatPower(p.radiated_power_dbw)],
    ['Antenna AGL', formatM(p.effective_agl_m)],
    [
      'Radius',
      p.contour
        ? `${formatRadius(p.contour)} to ${formatDbuv(p.contour.threshold_dbuv)} (${thresholdSourceLabel(p.contour)})`
        : 'none',
    ],
  ]
  const title = document.createElement('div')
  title.className = 'font-medium'
  title.textContent = `Station ${p.station_no}${p.licence_class ? ` · ${p.licence_class}` : ''}`
  root.append(title)
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

export function StationMap(props: Props) {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibre | null>(null)
  const latest = useRef(props)
  const byRow = useRef(new Map<number, StationFeature>())
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
        bounds: FINLAND_BOUNDS,
        fitBoundsOptions: { padding: 24 },
        maxPitch: 70,
        attributionControl: { compact: true },
      })
    } catch (err) {
      latest.current.onMapError(err instanceof Error ? err.message : String(err))
      return
    }
    mapRef.current = map
    map.addControl(new NavigationControl({ visualizePitch: true }), 'top-right')
    const popup = new Popup({ closeButton: false, closeOnClick: false, offset: 10, maxWidth: '280px' })

    map.on('load', () => {
      addLayers(map, resolveColors())
      setReady(true)
    })
    map.on('error', (e) => {
      if ('sourceId' in e && e.sourceId === 'osm') latest.current.onTileError()
    })
    map.on('mouseenter', 'site', () => (map.getCanvas().style.cursor = 'pointer'))
    let hovered: number | undefined
    const highlight = (row: number | undefined) => {
      hovered = row
      for (const id of HOVER_LAYERS) map.setFilter(id, hoverFilter(row))
    }
    map.on('mouseleave', 'site', () => {
      map.getCanvas().style.cursor = ''
      highlight(undefined)
      popup.remove()
    })
    map.on('mousemove', 'site', (e) => {
      const row = e.features?.[0]?.properties?.source_row as number | undefined
      if (row === hovered) return
      const station = row != null ? byRow.current.get(row) : undefined
      if (!station) return
      highlight(row)
      popup.setLngLat(station.geometry.coordinates).setDOMContent(tooltip(station)).addTo(map)
    })
    map.on('data', (e) => {
      if (e.dataType === 'source' && 'sourceId' in e && e.sourceId === 'osm' && 'tile' in e && e.tile)
        latest.current.onTileOk()
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
      const rows = [...new Set(hits.map((f) => f.properties.source_row as number))]
      latest.current.onPick(rows, { x, y })
    })
    return () => {
      popup.remove()
      map.remove()
      mapRef.current = null
      setReady(false)
    }
  }, [])

  const { features, filter, showContours, view3d, exaggeration, selected, dark } = props

  useEffect(() => {
    byRow.current = new Map(features.map((f) => [f.id, f]))
    const map = mapRef.current
    if (!ready || !map) return
    const data = buildSources(features)
    for (const id of SOURCES) map.getSource<GeoJSONSource>(id)?.setData(data[id])
  }, [ready, features])

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    const expr = stationFilter(filter)
    for (const id of FILTERED_LAYERS) {
      const own = id === 'contour-line' ? false : id === 'contour-line-dashed' ? true : null
      map.setFilter(id, own == null ? expr : ['all', expr, ['==', ['get', 'dashed'], own]])
    }
    map.setFilter('site-selected', ['all', expr, ['==', ['get', 'source_row'], selected ?? -1]])
  }, [ready, filter, selected])

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    for (const id of ['contour-fill', 'contour-line', 'contour-line-dashed'])
      map.setLayoutProperty(id, 'visibility', showContours ? 'visible' : 'none')
  }, [ready, showContours])

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    map.setLayoutProperty('mast', 'visibility', view3d ? 'visible' : 'none')
    map.easeTo({ pitch: view3d ? PITCH_3D : 0, bearing: view3d ? map.getBearing() : 0, duration: 600 })
  }, [ready, view3d])

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    map.setPaintProperty('mast', 'fill-extrusion-height', ['*', ['get', 'agl'], exaggeration])
  }, [ready, exaggeration])

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    // The theme class flips in the same commit; read the tokens on the next frame.
    const frame = requestAnimationFrame(() => {
      const c = resolveColors()
      const color = bandColor(c)
      map.setPaintProperty('osm', 'raster-brightness-max', dark ? 0.55 : 1)
      map.setPaintProperty('osm', 'raster-saturation', dark ? -0.6 : 0)
      for (const [id, prop] of BAND_PAINT) map.setPaintProperty(id, prop, color)
      map.setPaintProperty('site', 'circle-stroke-color', c.background)
      map.setPaintProperty('site-selected', 'circle-stroke-color', c.foreground)
      map.setPaintProperty('contour-hover-line', 'line-color', c.foreground)
    })
    return () => cancelAnimationFrame(frame)
  }, [ready, dark])

  // MapLibre's own CSS makes its container position: relative, so the absolute box is a wrapper.
  return (
    <div className="absolute inset-0">
      <div ref={container} className="size-full" role="region" aria-label="Map of special-interest stations" />
    </div>
  )
}
