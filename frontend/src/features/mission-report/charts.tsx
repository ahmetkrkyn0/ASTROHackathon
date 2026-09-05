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
 * Every chart draws in CSS PIXELS, not in a stretched viewBox. A viewBox that
 * fills its column scales the text with it, which put the same tick label at
 * 16px in the full-width cards and 7px in the two-up rows. Drawing in measured
 * pixels means a font-size of 11 is 11px in every card, and the charts sit on
 * the cockpit's type scale (--fs-micro upward) instead of inventing one per
 * column width. SVG text takes a number, not a CSS variable, so the two
 * constants below are the scale's floor written out.
 */
import React from 'react'
import { fmt } from './format'
import { useChartWidth } from './useChartSize'

export interface Point {
  x: number
  y: number
}

const PAD = { top: 14, right: 16, bottom: 26, left: 48 }

/** --fs-micro, the interface floor. No chart label is smaller than this. */
const TICK_SIZE = 12
/** Threshold annotations sit at the same rung; they are labels, not readings. */
const NOTE_SIZE = 12

/**
 * Axis furniture, through the tokens rather than copied out of them.
 *
 * These were written as literals -- '#161b27' and '#7b8497' -- on the belief
 * that SVG's fill and stroke take no CSS variable. They do: every other
 * colour in this file already arrives as var(--risk-high), var(--cyan) or
 * var(--text), and the browser resolves all of them the same way.
 *
 * The copies were not merely redundant, they were unreachable. The report's
 * print stylesheet re-colours the document by redefining these tokens, so a
 * literal is a value no medium can retone: on paper the grid printed as a
 * hard black rule and the tick labels came out at 3.76:1 on white. Through
 * the token both follow the page they are drawn on.
 */
const AXIS_LINE = 'var(--line)'
const AXIS_TEXT = 'var(--text-dim-2)'

/**
 * How much ink an area fill is allowed.
 *
 * Low on purpose. The stroke carries the reading; the fill only says which
 * side of the line is "under". At the 0.13 it started from, a battery curve
 * that stays near 100% painted two thirds of the report's largest card a
 * saturated mint, and the eye read the block instead of the line.
 */
const FILL_OPACITY = 0.07

interface Scale {
  sx: (v: number) => number
  sy: (v: number) => number
}

function makeScale(
  xMin: number,
  xMax: number,
  yMin: number,
  yMax: number,
  width: number,
  height: number,
): Scale {
  // A flat series (every y identical) would divide by zero and put the line at
  // NaN, which SVG renders as nothing at all -- a blank chart that looks like
  // missing data rather than a constant value. Widen the range instead.
  const xSpan = xMax - xMin || 1
  const ySpan = yMax - yMin || 1
  return {
    sx: (v) => PAD.left + ((v - xMin) / xSpan) * (width - PAD.left - PAD.right),
    sy: (v) => height - PAD.bottom - ((v - yMin) / ySpan) * (height - PAD.top - PAD.bottom),
  }
}

/** Round tick values so an axis reads -140, -120, -100 and not -142.6173. */
function ticks(min: number, max: number, count: number): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) return [min]
  const raw = (max - min) / count
  const mag = Math.pow(10, Math.floor(Math.log10(raw)))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? mag * 10
  const out: number[] = []
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) out.push(v)
  return out
}

/**
 * How many x labels fit without crowding.
 *
 * Derived from the measured width rather than fixed: the two-up cards are half
 * the width of the full ones, and four labels that read cleanly at 1100px
 * collide at 520px.
 */
function xTickCount(width: number): number {
  return width > 820 ? 5 : width > 520 ? 4 : 3
}

interface FrameProps {
  scale: Scale
  yTicks: number[]
  xTicks: number[]
  width: number
  height: number
  formatY?: (v: number) => string
  formatX?: (v: number) => string
}

/** Horizontal gridlines and the two axis labellings. */
const Frame: React.FC<FrameProps> = ({
  scale,
  yTicks,
  xTicks,
  width,
  height,
  formatY,
  formatX,
}) => (
  <g aria-hidden="true">
    {yTicks.map((t) => (
      <g key={`y${t}`}>
        <line
          x1={PAD.left}
          x2={width - PAD.right}
          y1={scale.sy(t)}
          y2={scale.sy(t)}
          stroke={AXIS_LINE}
          strokeWidth={1}
        />
        <text
          x={PAD.left - 8}
          y={scale.sy(t) + 3}
          textAnchor="end"
          fontSize={TICK_SIZE}
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
        y={height - PAD.bottom + 15}
        textAnchor="middle"
        fontSize={TICK_SIZE}
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
  height?: number
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
  height = 180,
}) => {
  const [ref, width] = useChartWidth()

  if (points.length < 2) return <p className="lp-report-empty">Not enough points to plot.</p>

  const xs = points.map((p) => p.x)
  const ys = points.map((p) => p.y)
  const refYs = refLines.map((r) => r.y)
  const lo = yMin ?? Math.min(...ys, ...refYs)
  const hi = yMax ?? Math.max(...ys, ...refYs)
  // A hair of headroom so the peak of the curve is not clipped by the frame.
  const padY = (hi - lo) * 0.08 || 1
  const scale = makeScale(Math.min(...xs), Math.max(...xs), lo - padY, hi + padY, width, height)

  const line = points.map((p, i) => `${i ? 'L' : 'M'}${scale.sx(p.x)},${scale.sy(p.y)}`).join('')
  const area = `${line}L${scale.sx(xs[xs.length - 1])},${height - PAD.bottom}L${scale.sx(xs[0])},${height - PAD.bottom}Z`

  return (
    <div ref={ref} className="lp-chart-wrap">
      <svg width={width} height={height} className="lp-chart" role="img" aria-label={title}>
        <Frame
          scale={scale}
          yTicks={ticks(lo - padY, hi + padY, 3)}
          xTicks={ticks(Math.min(...xs), Math.max(...xs), xTickCount(width))}
          width={width}
          height={height}
          formatY={formatY}
          formatX={formatX}
        />
        {fill && <path d={area} fill={color} fillOpacity={FILL_OPACITY} />}
        <path d={line} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" />
        {refLines.map((r) => (
          <g key={r.label}>
            <line
              x1={PAD.left}
              x2={width - PAD.right}
              y1={scale.sy(r.y)}
              y2={scale.sy(r.y)}
              stroke={r.color}
              strokeWidth={1}
              strokeDasharray="3 4"
              // The threshold is context for the curve, never a second reading
              // competing with it.
              strokeOpacity={0.55}
            />
            <text
              x={width - PAD.right}
              y={scale.sy(r.y) - 5}
              textAnchor="end"
              fontSize={NOTE_SIZE}
              fill={r.color}
              fillOpacity={0.75}
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
            y2={height - PAD.bottom}
            stroke="var(--mint)"
            strokeWidth={1}
            strokeOpacity={0.4}
            strokeDasharray="2 3"
          />
        ))}
      </svg>
    </div>
  )
}

export interface SegmentedProfileProps {
  points: Point[]
  /** One colour per point; the segment leaving point i takes colour i. */
  colors: string[]
  title: string
  formatY?: (v: number) => string
  formatX?: (v: number) => string
  height?: number
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
  height = 180,
}) => {
  const [ref, width] = useChartWidth()

  if (points.length < 2) return <p className="lp-report-empty">No elevation data.</p>

  const xs = points.map((p) => p.x)
  const ys = points.map((p) => p.y)
  const lo = Math.min(...ys)
  const hi = Math.max(...ys)
  const padY = (hi - lo) * 0.1 || 1
  const scale = makeScale(Math.min(...xs), Math.max(...xs), lo - padY, hi + padY, width, height)

  return (
    <div ref={ref} className="lp-chart-wrap">
      <svg width={width} height={height} className="lp-chart" role="img" aria-label={title}>
        <Frame
          scale={scale}
          yTicks={ticks(lo - padY, hi + padY, 3)}
          xTicks={ticks(Math.min(...xs), Math.max(...xs), xTickCount(width))}
          width={width}
          height={height}
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
            strokeWidth={1.8}
            strokeLinecap="round"
          />
        ))}
      </svg>
    </div>
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
 * anyone reads first, and the ring then says where it went. The ring is thin
 * for the same reason the area fills are faint -- one dominant slice at a
 * heavy stroke turned the card into a large bright disc.
 */
export const Donut: React.FC<{ slices: Slice[]; centerValue: string; centerLabel: string }> = ({
  slices,
  centerValue,
  centerLabel,
}) => {
  const total = slices.reduce((sum, s) => sum + s.value, 0)
  const R = 48
  const C = 2 * Math.PI * R
  let offset = 0

  return (
    <div className="lp-donut-block">
      <svg viewBox="0 0 128 128" className="lp-donut" role="img" aria-label={centerLabel}>
        <g transform="translate(64,64) rotate(-90)">
          <circle r={R} fill="none" stroke="var(--line-card)" strokeWidth={9} />
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
                  strokeWidth={9}
                  strokeDasharray={dash}
                  strokeDashoffset={-offset}
                />
              )
              offset += len
              return el
            })}
        </g>
        <text
          x={64}
          y={61}
          textAnchor="middle"
          fontSize={16}
          fill="var(--text)"
          fontFamily="var(--font-data)"
        >
          {centerValue}
        </text>
        <text
          x={64}
          y={78}
          textAnchor="middle"
          fontSize={12}
          fill="var(--text-dim-2)"
          letterSpacing="0.08em"
          fontFamily="var(--font-data)"
        >
          {centerLabel}
        </text>
      </svg>
      {/* Tiles, not a legend list. A three-line legend beside a 128px donut
          left two thirds of a full-width card empty; the same tile grid the
          decision summary uses fills it and carries the share as well as the
          absolute figure. */}
      <ul className="lp-donut-legend">
        {slices.map((s) => (
          <li key={s.label} className="lp-donut-tile">
            <span className="lp-kpi-label">
              <span className="lp-legend-swatch" style={{ background: s.color }} />
              {s.label}
            </span>
            <strong className="lp-donut-tile-val">{fmt(s.value)} Wh</strong>
            <span className="lp-donut-tile-share">
              %{total > 0 ? fmt((s.value / total) * 100) : '--'}
            </span>
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
        <strong className="lp-gauge-val" style={{ color }}>
          {fmt(value, 2)} / {limit === null ? '--' : fmt(limit, 1)} {unit}
        </strong>
      </div>
      <div className="lp-gauge-track">
        <div className="lp-gauge-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="lp-gauge-note">
        {limit === null
          ? 'No shadow limit is defined for this rover.'
          : exceeded
            ? 'Limit exceeded — the route is not safe as planned.'
            : `${fmt(pct, 0)}% of the limit used.`}
      </span>
    </div>
  )
}
