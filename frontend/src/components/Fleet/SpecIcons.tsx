import React from 'react'

/**
 * The eight glyphs the hangar needs, as inline paths.
 *
 * These are Material Symbols (Outlined, 24px), copied as path data rather than
 * pulled from fonts.googleapis.com. index.html already states the rule this
 * follows: the three text faces are served from public/fonts "so a network the
 * demo cannot reach costs nothing", and an icon font linked to Google would put
 * that back -- on a jury laptop with no wifi the specs would render as stray
 * words where the icons should be. Eight glyphs are cheaper inline than a
 * variable font is self-hosted.
 *
 * Material Symbols draw on a `0 -960 960 960` box, so the viewBox looks wrong
 * and is not. Size comes from the font-size of the parent (1em) and colour from
 * `currentColor`, which is what lets one icon sit in a dim spec label and
 * another in a bright weight row without either being restyled.
 */

export type IconName =
  // Rover specifications.
  | 'battery'
  | 'speed'
  | 'climb'
  | 'mass'
  // Route priority weights.
  | 'slope'
  | 'energy'
  | 'shadow'
  | 'thermal'
  // Mission profile presets. `fast_recon` reuses 'speed' and `shadow_traverse`
  // reuses 'shadow' -- Material's `landscape` is byte-identical to `terrain`,
  // so a separate name for it would have been the same drawing twice.
  | 'balance'
  | 'eco'
  // Affordance.
  | 'info'
  | 'map'
  | 'tune'

const PATHS: Record<IconName, string> = {
  battery:
    'M660-80v-120H560l140-200v120h100L660-80Zm-300-80Zm-40 80q-17 0-28.5-11.5T280-120v-640q0-17 11.5-28.5T320-800h80v-80h160v80h80q17 0 28.5 11.5T680-760v280q-21 0-41 3.5T600-466v-254H360v560h94q8 23 19.5 43T501-80H320Z',
  speed:
    'M480-316.5q38-.5 56-27.5l224-336-336 224q-27 18-28.5 55t22.5 61q24 24 62 23.5Zm0-483.5q59 0 113.5 16.5T696-734l-76 48q-33-17-68.5-25.5T480-720q-133 0-226.5 93.5T160-400q0 42 11.5 83t32.5 77h552q23-38 33.5-79t10.5-85q0-36-8.5-70T766-540l48-76q30 47 47.5 100T880-406q1 57-13 109t-41 99q-11 18-30 28t-40 10H204q-21 0-40-10t-30-28q-26-45-40-95.5T80-400q0-83 31.5-155.5t86-127Q252-737 325-768.5T480-800Zm7 313Z',
  climb: 'm136-240-56-56 296-298 160 160 208-206H640v-80h240v240h-80v-104L536-320 376-480 136-240Z',
  mass: 'M80-80q0-111 29.5-189.5T185-400q46-52 103-80.5T400-520v-120q-137-17-228.5-84.5T80-880h800q0 88-91.5 155.5T560-640v120q55 11 112 39.5T775-400q46 52 75.5 130.5T880-80H640v-80h155q-18-152-113.5-220T480-448q-106 0-201.5 68T165-160h155v80H80Zm562-659.5Q713-764 755-800H205q42 36 113 60.5T480-715q91 0 162-24.5ZM480-80q-33 0-56.5-23.5T400-160q0-17 6.5-31t17.5-25q24-24 81-50.5T640-320q-28 78-54 135t-50 81q-11 11-25 17.5T480-80Zm0-635Z',
  slope: 'm40-240 240-320 180 240h300L560-586 460-454l-50-66 150-200 360 480H40Zm521-80Zm-361 0h160l-80-107-80 107Zm0 0h160-160Z',
  energy: 'm422-232 207-248H469l29-227-185 267h139l-30 208ZM320-80l40-280H160l360-520h80l-40 320h240L400-80h-80Zm151-390Z',
  shadow:
    'M480-120q-150 0-255-105T120-480q0-150 105-255t255-105q14 0 27.5 1t26.5 3q-41 29-65.5 75.5T444-660q0 90 63 153t153 63q55 0 101-24.5t75-65.5q2 13 3 26.5t1 27.5q0 150-105 255T480-120Zm0-80q88 0 158-48.5T740-375q-20 5-40 8t-40 3q-123 0-209.5-86.5T364-660q0-20 3-40t8-40q-78 32-126.5 102T200-480q0 116 82 198t198 82Zm-10-270Z',
  thermal:
    'M520-520v-80h200v80H520Zm0-160v-80h320v80H520ZM178.5-178.5Q120-237 120-320q0-48 21-89.5t59-70.5v-240q0-50 35-85t85-35q50 0 85 35t35 85v240q38 29 59 70.5t21 89.5q0 83-58.5 141.5T320-120q-83 0-141.5-58.5ZM200-320h240q0-29-12.5-54T392-416l-32-24v-280q0-17-11.5-28.5T320-760q-17 0-28.5 11.5T280-720v280l-32 24q-23 17-35.5 42T200-320Z',
  balance:
    'M80-120v-80h360v-447q-26-9-45-28t-28-45H240l120 280q0 50-41 85t-99 35q-58 0-99-35t-41-85l120-280h-80v-80h247q12-35 43-57.5t70-22.5q39 0 70 22.5t43 57.5h247v80h-80l120 280q0 50-41 85t-99 35q-58 0-99-35t-41-85l120-280H593q-9 26-28 45t-45 28v447h360v80H80Zm585-320h150l-75-174-75 174Zm-520 0h150l-75-174-75 174Zm335-280q17 0 28.5-11.5T520-760q0-17-11.5-28.5T480-800q-17 0-28.5 11.5T440-760q0 17 11.5 28.5T480-720Z',
  eco: 'M216-176q-45-45-70.5-104T120-402q0-63 24-124.5T222-642q35-35 86.5-60t122-39.5Q501-756 591.5-759t202.5 7q8 106 5 195t-16.5 160.5q-13.5 71.5-38 125T684-182q-53 53-112.5 77.5T450-80q-65 0-127-25.5T216-176Zm112-16q29 17 59.5 24.5T450-160q46 0 91-18.5t86-59.5q18-18 36.5-50.5t32-85Q709-426 716-500.5t2-177.5q-49-2-110.5-1.5T485-670q-61 9-116 29t-90 55q-45 45-62 89t-17 85q0 59 22.5 103.5T262-246q42-80 111-153.5T534-520q-72 63-125.5 142.5T328-192Zm0 0Zm0 0Z',
  map: 'm600-120-240-84-186 72q-20 8-37-4.5T120-170v-560q0-13 7.5-23t20.5-15l212-72 240 84 186-72q20-8 37 4.5t17 33.5v560q0 13-7.5 23T812-192l-212 72Zm-40-98v-468l-160-56v468l160 56Zm80 0 120-40v-474l-120 46v468Zm-440-10 120-46v-468l-120 40v474Zm440-458v468-468Zm-320-56v468-468Z',
  tune: 'M440-120v-240h80v80h320v80H520v80h-80Zm-320-80v-80h240v80H120Zm160-160v-80H120v-80h160v-80h80v240h-80Zm160-80v-80h400v80H440Zm160-160v-240h80v80h160v80H680v80h-80Zm-480-80v-80h400v80H120Z',
  info: 'M440-280h80v-240h-80v240Zm68.5-331.5Q520-623 520-640t-11.5-28.5Q497-680 480-680t-28.5 11.5Q440-657 440-640t11.5 28.5Q463-600 480-600t28.5-11.5ZM480-80q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5 156T763-197q-54 54-127 85.5T480-80Zm0-80q134 0 227-93t93-227q0-134-93-227t-227-93q-134 0-227 93t-93 227q0 134 93 227t227 93Zm0-320Z',
}

interface IconProps {
  name: IconName
  className?: string
}

/**
 * Decorative by default: every place these are used already prints the label in
 * text beside the glyph, so announcing the icon too would make a screen reader
 * say everything twice.
 */
export const Icon: React.FC<IconProps> = ({ name, className }) => (
  <svg
    className={`lp-icon ${className ?? ''}`}
    viewBox="0 -960 960 960"
    fill="currentColor"
    aria-hidden="true"
    focusable="false"
  >
    <path d={PATHS[name]} />
  </svg>
)

export default Icon
