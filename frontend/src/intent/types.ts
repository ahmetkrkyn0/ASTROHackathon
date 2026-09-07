/**
 * One operator intent, addressed from one feature to another.
 *
 * This exists because the mission report has to be able to hand the assistant
 * a question, and the shell contract gives it no way to: features may not
 * import each other, `mission → features` is forbidden, and the assistant's
 * draft is state inside its own panel. The three obvious alternatives were all
 * worse -- a writer on MissionActions would make mission/ the owner of an
 * inter-feature message bus wearing the mission's name; a shell/ channel
 * reverses the shell's own dependency direction; a CustomEvent bus is
 * invisible to the type system and untestable with no jsdom.
 *
 * What keeps this from becoming the service locator `features/registry.ts`
 * refuses to be: it carries ONE kind of intent, its origin union is closed, and
 * the payload is text. A second channel is an amendment to
 * docs/frontend/FRONTEND_MODULAR_SHELL.md §14, not another file dropped in
 * this folder.
 */

/** Who may ask. Closed, so a new producer is a deliberate change here. */
export type AssistantAskOrigin = 'mission-report'

export interface AssistantAsk {
  /**
   * Monotonic, and the reason the channel needs an id at all: the operator may
   * ask the same question twice, and comparing text would swallow the second.
   */
  id: number
  /**
   * Placed in the composer. NEVER sent -- the operator still presses Gönder,
   * and the panel still refuses until an explanation level is chosen.
   */
  question: string
  origin: AssistantAskOrigin
}

/** The next ask in the sequence. Pure, so the ordering is testable. */
export function nextAsk(
  previous: AssistantAsk | null,
  question: string,
  origin: AssistantAskOrigin,
): AssistantAsk {
  return { id: (previous?.id ?? 0) + 1, question, origin }
}

/**
 * Whether this ask still needs applying.
 *
 * The consumer decides, and there is deliberately no `consume` or `clear` on
 * the producer side: a one-way channel is what makes "a feature cannot make the
 * assistant do anything but show text" structural rather than a rule someone
 * has to remember.
 */
export function isFreshAsk(ask: AssistantAsk | null, appliedId: number): boolean {
  return ask !== null && ask.id !== appliedId
}
