import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import type { StationModel } from '@/lib/api'
import { BANDS, EXAGGERATION_RANGE, modelStatement } from './station-meta'

type Props = {
  model: StationModel | undefined
  counts: number[]
  view3d: boolean
  exaggeration: number
  onExaggeration: (value: number) => void
}

function LineKey({ dashed, label }: { dashed?: boolean; label: string }) {
  return (
    <li className="flex items-center gap-2">
      <svg width="22" height="8" aria-hidden className="shrink-0 text-muted-foreground">
        <line x1="1" y1="4" x2="21" y2="4" stroke="currentColor" strokeWidth="1.5" strokeDasharray={dashed ? '3 2' : undefined} />
      </svg>
      {label}
    </li>
  )
}

export function StationLegend({ model, counts, view3d, exaggeration, onExaggeration }: Props) {
  return (
    <div className="space-y-3 text-xs">
      <div>
        <h3 className="mb-1.5 font-medium">TX frequency</h3>
        <ul className="grid grid-cols-2 gap-x-3 gap-y-1">
          {BANDS.map((b) => (
            <li key={b.bin} className="flex items-center gap-2">
              <span className="size-2.5 shrink-0 rounded-full" style={{ background: `var(--band-${b.bin})` }} aria-hidden />
              <span>{b.label}</span>
              <span className="ml-auto tabular-nums text-muted-foreground">{counts[b.bin] ?? 0}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="space-y-1">
        <h3 className="font-medium">Disc radius</h3>
        <p className="text-muted-foreground">
          Distance at which the predicted field strength falls to the threshold
          {model ? ` (${modelStatement(model)}). ` : '. '}
          The threshold is the {model?.tr2508_citation ?? 'T/R 25-08'} trigger for 29.7–470 MHz, with the bandwidth
          conversion, and the map threshold of {model ? `${model.user_threshold_dbuv} dBµV/m` : 'the slider'} elsewhere.
          Directional antennas are drawn as circles at their maximum e.r.p.
        </p>
        <ul className="space-y-0.5 text-muted-foreground">
          <LineKey label="Solid: radius solved within 1–1000 km" />
          <LineKey dashed label="Dashed: below 1 km (drawn at 1 km) or 1000 km and more" />
          <li className="flex items-center gap-2">
            <svg width="22" height="10" aria-hidden className="shrink-0">
              <path d="M1 5h18M14 1l5 4-5 4" fill="none" stroke="currentColor" strokeWidth="1.5" />
            </svg>
            Azimuth of a directional antenna
          </li>
        </ul>
      </div>
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="exaggeration" className="text-xs font-medium">
            Mast height ×{exaggeration}
          </Label>
          {!view3d && <span className="text-muted-foreground">3D view only</span>}
        </div>
        <Slider
          id="exaggeration"
          min={EXAGGERATION_RANGE[0]}
          max={EXAGGERATION_RANGE[1]}
          step={1}
          value={[exaggeration]}
          onValueChange={([v]) => onExaggeration(v)}
          disabled={!view3d}
          aria-label="Mast height exaggeration"
        />
        <p className="text-muted-foreground">Columns are exaggerated so they show at country scale; tooltips give real metres.</p>
      </div>
    </div>
  )
}
