/**
 * What the catalogue does not carry.
 *
 * /api/rovers answers with the physics -- mass, speed, slope limit, capacity --
 * and nothing about who flies the thing or what it looks like. The agency, the
 * photograph, the payload list and the one-word class are presentation, so they
 * live here rather than being invented by the backend.
 *
 * This was inside FleetSelectionView until the cockpit's left rail needed the
 * same photograph for its assigned-vehicle card. Two callers is the point at
 * which a private const becomes a module.
 */

interface RoverDetailMeta {
  agency: string
  agencyColor: string
  /** One word for what kind of vehicle this is, for the deploy block. */
  roverClass: string
  highlight: string
  payload: string
  image: string
  description: string
}

const ROVER_META: Record<string, RoverDetailMeta> = {
  lpr_1: {
    agency: 'ESA / LUNAPATH',
    agencyColor: '#4fd8f0',
    roverClass: 'Exploration',
    highlight: 'Flagship Autonomous Polar Explorer',
    payload: '360° LiDAR Turret, Panoramic Stereo NavCam, Deep Regolith Temperature Probes',
    image: '/rovers/lpr_1.jpg',
    description:
      'High-endurance heavy science explorer engineered for long-distance polar traverses. Features dual solar arrays and regenerative cryogenic battery packs.',
  },
  luvmi_m: {
    agency: 'LUNAPATH EXP',
    agencyColor: '#b3a5ff',
    roverClass: 'Scout',
    highlight: 'Agile Crater Descent Micro-Rover',
    payload: 'High-Torque Mesh Wheels, Micro-LiDAR, Stereo Camera Mast, Rock Abrasion Tool',
    image: '/rovers/luvmi_m.jpg',
    description:
      'Ultra-compact robotic scout specifically designed to descend steep crater slopes and explore narrow shadowed terrain inaccessible to larger vehicles.',
  },
  luvm_m: {
    agency: 'LUNAPATH EXP',
    agencyColor: '#b3a5ff',
    roverClass: 'Scout',
    highlight: 'Agile Crater Descent Micro-Rover',
    payload: 'High-Torque Mesh Wheels, Micro-LiDAR, Stereo Camera Mast, Rock Abrasion Tool',
    image: '/rovers/luvmi_m.jpg',
    description:
      'Ultra-compact robotic scout specifically designed to descend steep crater slopes and explore narrow shadowed terrain inaccessible to larger vehicles.',
  },
  nasa_viper: {
    agency: 'NASA',
    agencyColor: '#e8c85a',
    roverClass: 'Prospector',
    highlight: 'Subsurface Volatiles Prospector',
    payload: 'The TRIDENT 1-Meter Hammer Drill, Neutron Spectrometer System (NSS), NIRVSS',
    image: '/rovers/nasa_viper.jpg',
    description:
      'NASA premier volatile prospecting rover equipped with a heavy hammer drill and spectrometers to hunt for sub-surface water ice inside permanently shadowed regions.',
  },
  viper: {
    agency: 'NASA',
    agencyColor: '#e8c85a',
    roverClass: 'Prospector',
    highlight: 'Subsurface Volatiles Prospector',
    payload: 'The TRIDENT 1-Meter Hammer Drill, Neutron Spectrometer System (NSS), NIRVSS',
    image: '/rovers/nasa_viper.jpg',
    description:
      'NASA premier volatile prospecting rover equipped with a heavy hammer drill and spectrometers to hunt for sub-surface water ice inside permanently shadowed regions.',
  },
  cnsa_yutu_2: {
    agency: 'CNSA',
    agencyColor: '#ee5a52',
    roverClass: 'Endurance',
    highlight: 'Far-Side Lunar Endurance Rover',
    payload: 'Lunar Penetrating Radar (LPR), Visible & Near-Infrared Imaging Spectrometer (VNIS)',
    image: '/rovers/cnsa_yutu_2.jpg',
    description:
      'Lightweight solar-powered lunar rover holding world records for lunar surface operational longevity on the rugged terrain of the Moon.',
  },
  yutu_2: {
    agency: 'CNSA',
    agencyColor: '#ee5a52',
    roverClass: 'Endurance',
    highlight: 'Far-Side Lunar Endurance Rover',
    payload: 'Lunar Penetrating Radar (LPR), Visible & Near-Infrared Imaging Spectrometer (VNIS)',
    image: '/rovers/cnsa_yutu_2.jpg',
    description:
      'Lightweight solar-powered lunar rover holding world records for lunar surface operational longevity on the rugged terrain of the Moon.',
  },
}

function getRoverMeta(id: string): RoverDetailMeta {
  const norm = id.toLowerCase().trim()
  if (ROVER_META[norm]) return ROVER_META[norm]
  if (norm.includes('viper')) return ROVER_META.nasa_viper
  if (norm.includes('yutu')) return ROVER_META.cnsa_yutu_2
  if (norm.includes('luvm')) return ROVER_META.luvmi_m
  if (norm.includes('lpr')) return ROVER_META.lpr_1
  return ROVER_META.lpr_1
}

export { getRoverMeta }
export type { RoverDetailMeta }
