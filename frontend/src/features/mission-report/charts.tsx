/**
 * Inline-SVG chart primitives for the mission report.
 *
 * Deliberately hand-drawn rather than pulled from a chart library. There is no
 * charting dependency in package.json, and every library's defaults fight the
 * LunaPath canvas on exactly the three rules it enforces: rounded corners,
 * drop shadows under the plot, and a categorical palette that means nothing.
 * These primitives take their colours from the caller, so a risk colour on a
 * chart is the same risk colour the map and the rail use.
 *
 * Every chart renders into a fixed viewBox and is stretched by CSS. Font sizes
 * are therefore in viewBox units, which is why they look small in the source:
 * a 10-unit label in a 640-wide box lands near 12px at the width the modal
 * gives it.
 */
import React from 'react'
import { fmt } from './format'

export interface Point {
  x: number
  y: number
}

const PAD = { top: 10, right: 14, bottom: 22, left: 46 }
const W = 640
const H = 200

/** Grid lines and axis text share these, so a chart never invents its own. */
const AXIS_COLOR = '#1d2432'
const AXIS_TEXT = '#6d7789'

interface Scale {
  sx: (v: number) => number
  sy: (v: number) => number
}

function makeScale(
  xMin: number,
  xMax: number,
  yMin: number,
  yMax: number,
): Scale {
  // A flat series (every y identical) would divide by zero and put the line
  // at NaN, which SVG renders as nothing at all -- a blank chart that looks
  // like missing data rather than a constant value. Widen the range instead.
  const xSpan = xMax - xMin || 1
  const ySpan = yMax - yMin || 1
  return {
    sx: (v) => PAD.left + ((v - xMin) / xSpan) * (W - PAD.left - PAD.right),
    sy: (v) => H - PAD.bottom - ((v - yMin) / ySpan) * (H - PAD.top - PAD.bottom),
  }
}

/** Round tick values so an axis reads -140, -120, -100 and not -142.6173. */
function ticks(min: number, max: number, count = 4): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) return [min]
  const raw = (max - min) / count
  const mag = Math.pow(10, Math.floor(Math.log10(raw)))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? mag * 10
  const out: number[] = []
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) out.push(v)
  return out
}

interface FrameProps {
  scale: Scale
  yTicks: number[]
  xTicks: number[]
  formatY?: (v: number) => string
  formatX?: (v: number) => string
}

/** Horizontal gridlines, a baseline, and the two axis labellings. */
const Frame: React.FC<FrameProps> = ({ scale, yTicks, xTicks, formatY, formatX }) => (
  <g aria-hidden="true">
    {yTicks.map((t) => (
      <g key={`y${t}`}>
        <line
          x1={PAD.left}
          x2={W - PAD.right}
          y1={scale.sy(t)}
          y2={scale.sy(t)}
          stroke={AXIS_COLOR}
          strokeWidth={1}
        />
        <text
          x={PAD.left - 6}
          y={scale.sy(t) + 3}
          textAnchor="end"
          fontSize={9}
          fill={AXIS_TEXT}
          fontFamily="var(--font-data)"
        >
          {formatY ? formatY(t) : fmt(t, 0)}
        </text>
      </g>
    ))}
    {xTicks.map((t) => (
      <text
        key={`x${t}`}
        x={scale.sx(t)}
        y={H - PAD.bottom + 13}
        textAnchor="middle"
        fontSize={9}
        fill={AXIS_TEXT}
        fontFamily="var(--font-data)"
      >
        {formatX ? formatX(t) : fmt(t, 0)}
      </text>
    ))}
  </g>
)

export interface RefLine {
  y: number
  label: string
  color: string
}

export interface Marker {
  x: number
  label?: string
}

export interface LineAreaProps {
  points: Point[]
  color: string
  /** Draw the area under the curve. Off for readings that are not a quantity. */
  fill?: boolean
  yMin?: number
  yMax?: number
  refLines?: RefLine[]
  markers?: Marker[]
  formatY?: (v: number) => string
  formatX?: (v: number) => string
  title: string
}

/**
 * A single series against x, with optional threshold lines and event markers.
 *
 * `refLines` is what turns a line into a verdict: the battery profile without
 * the reserve line is a shape, and with it is a pass or a fail.
 */
export const LineArea: React.FC<LineAreaProps> = ({
  points,
  color,
  fill = true,
  yMin,
  yMax,
  refLines = [],
  markers = [],
  formatY,
  formatX,
  title,
}) => {
  if (points.length < 2) return <p className="lp-report-empty">Grafik için yeterli nokta yok.</p>

  const xs = points.map((p) => p.x)
  const ys = points.map((p) => p.y)
  const refYs = refLines.map((r) => r.y)
  const lo = yMin ?? Math.min(...ys, ...refYs)
  const hi = yMax ?? Math.max(...ys, ...refYs)
  // A hair of headroom so the peak of the curve is not clipped by the frame.
  const padY = (hi - lo) * 0.08 || 1
  const scale = makeScale(Math.min(...xs), Math.max(...xs), lo - padY, hi + padY)

  const line = points.map((p, i) => `${i ? 'L' : 'M'}${scale.sx(p.x)},${scale.sy(p.y)}`).join('')
  const area = `${line}L${scale.sx(xs[xs.length - 1])},${H - PAD.bottom}L${scale.sx(xs[0])},${H - PAD.bottom}Z`

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="lp-chart" role="img" aria-label={title}>
      <Frame
        scale={scale}
        yTicks={ticks(lo - padY, hi + padY)}
        xTicks={ticks(Math.min(...xs), Math.max(...xs))}
        formatY={formatY}
        formatX={formatX}
      />
      {fill && <path d={area} fill={color} fillOpacity={0.13} />}
      <path d={line} fill="none" stroke={color} strokeWidth={1.6} strokeLinejoin="round" />
      {refLines.map((r) => (
        <g key={r.label}>
          <line
            x1={PAD.left}
            x2={W - PAD.right}
            y1={scale.sy(r.y)}
            y2={scale.sy(r.y)}
            stroke={r.color}
            strokeWidth={1}
            strokeDasharray="4 3"
          />
          <text
            x={W - PAD.right}
            y={scale.sy(r.y) - 4}
            textAnchor="end"
            fontSize={9}
            fill={r.color}
            fontFamily="var(--font-data)"
          >
            {r.label}
          </text>
        </g>
      ))}
      {markers.map((m, i) => (
        <line
          key={`${m.x}-${i}`}
          x1={scale.sx(m.x)}
          x2={scale.sx(m.x)}
          y1={PAD.top}
          y2={H - PAD.bottom}
          stroke="var(--mint)"
          strokeWidth={1}
          strokeDasharray="2 2"
        />
      ))}
    </svg>
  )
}

export interface SegmentedProfileProps {
  points: Point[]
  /** One colour per point; the segment leaving point i takes colour i. */
  colors: string[]
  title: string
  formatY?: (v: number) => string
  formatX?: (v: number) => string
}

/**
 * The elevation cut, painted by the risk level at each step.
 *
 * Drawn as N-1 separate segments rather than one path with a gradient: the
 * risk ramp is four discrete readings, and a gradient would invent colours
 * between them that stand for nothing.
 */
export const SegmentedProfile: React.FC<SegmentedProfileProps> = ({
  points,
  colors,
  title,
  formatY,
  formatX,
}) => {
  if (points.length < 2) return <p className="lp-report-empty">Yükseklik verisi yok.</p>

  const xs = points.map((p) => p.x)
  const ys = points.map((p) => p.y)
  const lo = Math.min(...ys)
  const hi = Math.max(...ys)
  const padY = (hi - lo) * 0.1 || 1
  const scale = makeScale(Math.min(...xs), Math.max(...xs), lo - padY, hi + padY)

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="lp-chart" role="img" aria-label={title}>
      <Frame
        scale={scale}
        yTicks={ticks(lo - padY, hi + padY)}
        xTicks={ticks(Math.min(...xs), Math.max(...xs))}
        formatY={formatY}
        formatX={formatX}
      />
      {points.slice(0, -1).map((p, i) => (
        <line
          key={i}
          x1={scale.sx(p.x)}
          y1={scale.sy(p.y)}
          x2={scale.sx(points[i + 1].x)}
          y2={scale.sy(points[i + 1].y)}
          stroke={colors[i] ?? colors[colors.length - 1]}
          strokeWidth={2.2}
          strokeLinecap="round"
        />
      ))}
    </svg>
  )
}

export interface BarRow {
  label: string
  value: number
  pct: number
  color: string
}

/** Horizontal bars for a distribution whose categories are ordered. */
export const HBars: React.FC<{ rows: BarRow[]; unit?: string }> = ({ rows, unit = '%' }) => {
  const max = Math.max(...rows.map((r) => r.pct), 1)
  return (
    <div className="lp-hbars">
      {rows.map((r) => (
        <div className="lp-hbar-row" key={r.label}>
          <span className="lp-hbar-label">{r.label}</span>
          <div className="lp-hbar-track">
            <div
              className="lp-hbar-fill"
              style={{ width: `${(r.pct / max) * 100}%`, background: r.color }}
            />
          </div>
          <span className="lp-hbar-val">
            {fmt(r.pct)}
            {unit}
          </span>
          <span className="lp-hbar-count">{r.value}</span>
        </div>
      ))}
    </div>
  )
}

export interface Segment {
  label: string
  pct: number
  color: string
}

/** One bar carrying the whole route, split by category share. */
export const StackedBar: React.FC<{ segments: Segment[] }> = ({ segments }) => {
  const shown = segments.filter((s) => s.pct > 0)
  return (
    <div className="lp-stacked-block">
      <div className="lp-stacked-bar">
        {shown.map((s) => (
          <div
            key={s.label}
            className="lp-stacked-seg"
            style={{ width: `${s.pct}%`, background: s.color }}
            title={`${s.label}: ${fmt(s.pct)}%`}
          />
        ))}
      </div>
      <ul className="lp-stacked-legend">
        {shown.map((s) => (
          <li key={s.label}>
            <span className="lp-legend-swatch" style={{ background: s.color }} />
            {s.label}
            <strong>{fmt(s.pct)}%</strong>
          </li>
        ))}
      </ul>
    </div>
  )
}

export interface Slice {
  label: string
  value: number
  color: string
}

/**
 * The energy split.
 *
 * A donut and not a pie: the hole carries the total, which is the number
 * anyone reads first, and the ring then says where it went.
 */
export const Donut: React.FC<{ slices: Slice[]; centerValue: string; centerLabel: string }> = ({
  slices,
  centerValue,
  centerLabel,
}) => {
  const total = slices.reduce((sum, s) => sum + s.value, 0)
  const R = 54
  const C = 2 * Math.PI * R
  let offset = 0

  return (
    <div className="lp-donut-block">
      <svg viewBox="0 0 140 140" className="lp-donut" role="img" aria-label={centerLabel}>
        <g transform="translate(70,70) rotate(-90)">
          <circle r={R} fill="none" stroke="var(--line-card)" strokeWidth={14} />
          {total > 0 &&
            slices.map((s) => {
              const len = (s.value / total) * C
              const dash = `${len} ${C - len}`
              const el = (
                <circle
                  key={s.label}
                  r={R}
                  fill="none"
                  stroke={s.color}
                  strokeWidth={14}
                  strokeDasharray={dash}
                  strokeDashoffset={-offset}
                />
              )
              offset += len
              return el
            })}
        </g>
        <text x={70} y={68} textAnchor="middle" fontSize={16} fill="var(--text)" fontFamily="var(--font-data)">
          {centerValue}
        </text>
        <text x={70} y={82} textAnchor="middle" fontSize={8} fill="var(--text-dim)" letterSpacing="0.08em">
          {centerLabel}
        </text>
      </svg>
      <ul className="lp-stacked-legend lp-donut-legend">
        {slices.map((s) => (
          <li key={s.label}>
            <span className="lp-legend-swatch" style={{ background: s.color }} />
            {s.label}
            <strong>{fmt(s.value)} Wh</strong>
          </li>
        ))}
      </ul>
    </div>
  )
}

/**
 * A value against a hard limit.
 *
 * The limit is drawn as the full track rather than a mark on a longer scale,
 * so "how close did we come" is read as a proportion and not from two numbers.
 */
export const LimitGauge: React.FC<{
  value: number
  limit: number | null
  unit: string
  label: string
  exceeded: boolean | null
}> = ({ value, limit, unit, label, exceeded }) => {
  const pct = limit && limit > 0 ? Math.min(100, (value / limit) * 100) : 0
  const color = exceeded ? 'var(--risk-crit)' : pct > 75 ? 'var(--risk-med)' : 'var(--risk-low)'
  return (
    <div className="lp-gauge">
      <div className="lp-gauge-head">
        <span className="lp-kpi-label">{label}</span>
        <strong className="lp-mono-val" style={{ color }}>
          {fmt(value, 2)} / {limit === null ? '--' : fmt(limit, 1)} {unit}
        </strong>
      </div>
      <div className="lp-gauge-track">
        <div className="lp-gauge-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="lp-gauge-note">
        {limit === null
          ? 'Bu rover için gölge limiti tanımlı değil.'
          : exceeded
            ? 'Limit aşıldı — rota bu haliyle güvenli değil.'
            : `Limitin %${fmt(pct, 0)} kadarı kullanıldı.`}
      </span>
    </div>
  )
}
