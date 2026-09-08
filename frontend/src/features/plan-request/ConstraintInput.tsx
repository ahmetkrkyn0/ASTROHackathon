import { setConstraint, useConstraint } from './store'
import type { PlanRequestContributor } from './contributors'

/**
 * The input for one advanced constraint, wherever it is rendered.
 *
 * Two panels now show constraints -- the mission constraints drawer, which
 * builds the 2-D request, and the time-axis strip, which builds the 4-D one.
 * They differ in layout and in which contributors they list, but the control
 * itself is the same question in both: a slider between two bounds, or one of
 * a fixed set of backend enum values. Writing it twice would be the "aynı
 * shared primitive'i iki kez yazma" the integration plan forbids (§31.7), and
 * the copy that got missed would be the one that stopped matching the
 * contributor registry.
 *
 * A toggle renders nothing here on purpose: it IS the row's on/off control,
 * and each panel draws that differently -- a switch in the drawer, a pressed
 * chip in the strip. Only the secondary value is shared.
 *
 * `classPrefix` rather than fixed class names: the drawer's rules are already
 * written against `lp-mc-*` and the strip needs its own. Passing the prefix
 * keeps this component free of layout opinions and left the existing panel
 * pixel-identical when it adopted this.
 */
export function ConstraintInput({
  contributor,
  classPrefix,
}: {
  contributor: PlanRequestContributor
  classPrefix: string
}) {
  const state = useConstraint(contributor.id)
  const { control } = contributor

  if (control.kind === 'toggle') return null

  if (control.kind === 'number') {
    const value = typeof state.value === 'number' ? state.value : control.initial
    return (
      <div className={`${classPrefix}-control`}>
        <input
          type="range"
          min={control.min}
          max={control.max}
          step={control.step}
          value={value}
          aria-label={contributor.label}
          onChange={(event) =>
            setConstraint(contributor.id, { enabled: true, value: Number(event.target.value) })
          }
        />
        <output className={`${classPrefix}-value`}>
          {formatNumber(value, control.step)}
          {control.unit ?? ''}
        </output>
      </div>
    )
  }

  return (
    <div className={`${classPrefix}-control`}>
      <select
        className={`${classPrefix}-select`}
        value={typeof state.value === 'string' ? state.value : control.initial}
        aria-label={contributor.label}
        onChange={(event) =>
          setConstraint(contributor.id, { enabled: true, value: event.target.value })
        }
      >
        {control.options.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    </div>
  )
}

/**
 * As many decimals as the step actually resolves, and no more.
 *
 * The drawer printed every number to three places, which reads as false
 * precision on a weight that moves in hundredths: `0.150` claims a resolution
 * the slider does not have. Risk alpha does step in thousandths, so the rule
 * is taken from the control rather than fixed.
 */
function formatNumber(value: number, step: number): string {
  const decimals = Math.max(0, Math.ceil(-Math.log10(step)))
  return value.toFixed(Math.min(decimals, 6))
}
