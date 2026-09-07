/**
 * The mission report in two languages.
 *
 * Outside `src/features/` on purpose. `features/mission-report/index.tsx` may
 * not import from a sibling feature -- a contract test asserts the absence of
 * `from '../../features/` in that file -- and `src/intent/` is the precedent
 * for a seam that more than one feature may reach.
 *
 * Only the report is translated today. The cockpit around it is English and
 * the assistant is Turkish, and neither moves here: the assistant's language
 * is load-bearing (backend/app/ai_grounding.py matches Turkish morphology to
 * block fabricated numbers), so translating its surface alone would leave that
 * guard watching a language the model no longer speaks.
 *
 * Every string the report can draw is in this file. Nothing is assembled from
 * fragments across languages -- see `subtitle`, which exists as a function
 * because Turkish is SOV and cannot reuse the English node order.
 */
import type { VerdictReason, Verdict } from '../features/mission-report/report'

export type ReportLang = 'en' | 'tr'

export const REPORT_LANGS: readonly ReportLang[] = ['en', 'tr']

/** What the switch itself says. Each language names itself, never the other. */
export const LANG_LABEL: Record<ReportLang, string> = { en: 'EN', tr: 'TR' }

const LOCALE: Record<ReportLang, string> = { en: 'en-GB', tr: 'tr-TR' }

/**
 * A number, in the reader's convention.
 *
 * Turkish swaps both separators -- 2.665 thousands, 3,47 decimal -- so this
 * cannot be a `toFixed` with a string replace. Intl does it properly, and it
 * is also what stops the report printing two different thousands separators,
 * which it did while `format.ts` said en-GB and the planner-evidence row said
 * tr-TR.
 *
 * Non-finite reads as `--` rather than `NaN`: an absent measurement is a fact
 * about the mission, and it is spelled the same way in both languages.
 */
export function fmtNum(value: number, digits = 1, lang: ReportLang = 'en'): string {
  if (!Number.isFinite(value)) return '--'
  // Above a thousand the fraction stops carrying information and the digits
  // only make the column harder to scan.
  const places = Math.abs(value) >= 1000 ? 0 : digits
  // Intl prints negative zero as "-0", and a chart axis that starts at zero
  // produces exactly that: the tick generator lands on -0 whenever the range
  // opens below the origin, so the battery axis read "-0%". `toFixed` used to
  // hide it, which is why it only appeared once the formatting moved to Intl.
  const safe = Object.is(value, -0) ? 0 : value
  return new Intl.NumberFormat(LOCALE[lang], {
    minimumFractionDigits: places,
    maximumFractionDigits: places,
  }).format(safe)
}

/**
 * A percentage, with the sign where that language puts it.
 *
 * Turkish writes `%70,0`; English writes `70.0%`. Getting this backwards is
 * the tell that a report was translated word by word.
 */
export function fmtPct(value: number, digits = 1, lang: ReportLang = 'en'): string {
  if (!Number.isFinite(value)) return '--'
  const n = fmtNum(value, digits, lang)
  return lang === 'tr' ? `%${n}` : `${n}%`
}

/** A whole number: counts of steps, nodes and stops are never fractional. */
function count(value: number, lang: ReportLang): string {
  return fmtNum(value, 0, lang)
}

/**
 * The verdict findings, rendered.
 *
 * `decideVerdict` returns codes and measurements; the sentence is built here.
 * That split is what makes the reasons translatable, and it matches
 * `backend/app/report.py`, which has carried codes rather than sentences from
 * the start. The parity fixture compares codes only, so nothing in this
 * function can break it.
 *
 * The switch is exhaustive over the discriminated union, so adding a reason
 * code without a sentence in both languages is a type error rather than an
 * empty line in a printed report.
 */
export function reasonText(reason: VerdictReason, lang: ReportLang): string {
  const n = (v: number, d = 1) => fmtNum(v, d, lang)
  const c = (v: number) => count(v, lang)

  switch (reason.code) {
    case 'STRANDED': {
      const step = reason.step === null ? '?' : c(reason.step)
      return lang === 'tr'
        ? `Rover ${step}. adımda enerjisiz kaldı — rota tamamlanamıyor.`
        : `Rover ran out of energy at step ${step} — the route cannot be completed.`
    }
    case 'EXECUTION_TRUNCATED': {
      // The backend's own wording for why, passed through untranslated: it is
      // a server string, and inventing a Turkish equivalent for a value this
      // file has never seen would be a guess presented as a translation.
      const why = reason.reason ? ` (${reason.reason})` : ''
      const nodes = `${c(reason.executable)}/${c(reason.planned)}`
      return lang === 'tr'
        ? `Rota kısaldı: ${nodes} düğüm sürülebilir${why}.`
        : `Route truncated: ${nodes} nodes are drivable${why}.`
    }
    case 'SHADOW_LIMIT_EXCEEDED': {
      const limit = reason.limitH === null ? '--' : n(reason.limitH)
      return lang === 'tr'
        ? `Kesintisiz gölge ${n(reason.shadowH)} h; rover sınırı ${limit} h.`
        : `Continuous shadow ${n(reason.shadowH)} h against a rover limit of ${limit} h.`
    }
    case 'CRITICAL_STEPS':
      return lang === 'tr'
        ? `${c(reason.count)} adım KRİTİK risk seviyesinde.`
        : `${c(reason.count)} steps at CRITICAL risk.`
    case 'HIGH_RISK_STEPS':
      return lang === 'tr'
        ? `${c(reason.count)} adım YÜKSEK risk seviyesinde veya üzerinde.`
        : `${c(reason.count)} steps at HIGH risk or above.`
    case 'BATTERY_WATCH':
      return lang === 'tr'
        ? `Batarya en düşük noktada ${fmtPct(reason.pct, 1, lang)} seviyesine indi.`
        : `Battery fell to ${fmtPct(reason.pct, 1, lang)} at its lowest.`
    case 'PEAK_POWER_EXCEEDED':
      return lang === 'tr'
        ? `${c(reason.count)} adımda tepe güç bütçesi aşıldı.`
        : `Peak power budget exceeded on ${c(reason.count)} steps.`
    case 'RECHARGES_REQUIRED':
      return lang === 'tr'
        ? `Rota ${c(reason.count)} şarj molası gerektiriyor.`
        : `The route needs ${c(reason.count)} recharge stops.`
    case 'NO_VIOLATION':
      return lang === 'tr'
        ? 'Hiçbir sürüş kısıtı ihlal edilmedi.'
        : 'No driving constraint was violated.'
  }
}

/**
 * What the verdict means, in one sentence.
 *
 * The token itself (GO / GO-WITH-RISK / NO-GO) is a contract value shared with
 * the backend and is never translated. This is the line that says what it
 * means, which is what the UI review asked for: a three-letter token is not an
 * explanation.
 */
export const VERDICT_MEANING: Record<ReportLang, Record<Verdict, string>> = {
  en: {
    GO: 'Route is safe as planned.',
    'GO-WITH-RISK': 'Route is drivable, with findings to review.',
    'NO-GO': 'Route is not safe as planned.',
  },
  tr: {
    GO: 'Rota planlandığı hâliyle güvenli.',
    'GO-WITH-RISK': 'Rota sürülebilir, ancak incelenmesi gereken bulgular var.',
    'NO-GO': 'Rota planlandığı hâliyle güvenli değil.',
  },
}

export interface ReportCopy {
  kicker: string
  title: string
  /** Turkish is SOV, so the whole sentence is built rather than interleaved. */
  subtitle: (rover: string, km: string, waypoints: string) => string
  metaRover: string
  metaRegion: string
  metaGenerated: string
  /**
   * The region row: extent and resolution, both measured.
   *
   * Takes the numbers rather than a built string, so the separators follow the
   * reader -- it printed "2.5 x 2.5 km" in a Turkish report while every other
   * figure beside it used a comma.
   */
  regionValue: (widthKm: number, heightKm: number, resolutionM: number) => string
  langSwitchLabel: string
  savePdf: string
  downloadData: string
  backToMap: string
  backToMapAria: string
  askAssistant: string
  /** Only shown in English: the assistant replies in Turkish either way. */
  askAssistantTurkishHint: string
  sections: {
    decision: string
    battery: string
    slope: string
    risk: string
    thermal: string
    shadow: string
    energy: string
    terrain: string
    planner: string
    milestones: string
    safety: string
    costModel: string
  }
  /**
   * Labels for the evidence the rail panels deliberately do not carry.
   * The claim sentences themselves come from the backend and are printed in
   * its own words, so only the scaffolding around them is translated.
   */
  evidence: {
    requirement: string
    margin: string
    worstAt: string
    untested: string
    claimBoundary: string
    monitor: string
    scope: string
    notApplied: string
    sources: string
  }
  notes: {
    recharges: (n: string) => string
    noRecharges: string
    steepest: (deg: string) => string
    riskPerStep: string
    thermalRange: (min: string, max: string) => string
    shadowLimit: string
    energySource: string
    terrainPainted: string
    plannerEvidence: string
  }
  kpi: {
    distance: string
    duration: string
    endBattery: string
    lowestBattery: string
    energyUsed: string
    maxSlope: string
    recharges: string
    routeNodes: string
  }
  charts: {
    batteryTitle: string
    batteryReserve: (pct: string) => string
    batteryMin: (pct: string) => string
    thermalTitle: string
    thermalMin: (t: string) => string
    thermalMax: (t: string) => string
    shadowGaugeLabel: string
    shadowTitle: string
    elevationTitle: string
    donutTotal: string
    drive: string
    payload: string
    heater: string
    /** Chart-local empty and limit states, passed in as labels. */
    notEnoughPoints: string
    noElevation: string
    noShadowLimit: string
    limitExceeded: string
    limitUsed: (pct: string) => string
  }
  details: {
    show: string
    hide: string
  }
  planner: {
    nodesExpanded: string
    solveTime: string
    totalCost: string
    barrierShare: string
    edgesRejected: (reason: string) => string
  }
  table: {
    point: string
    step: string
    km: string
    battery: string
    slope: string
    temp: string
    risk: string
  }
  /** Milestone row titles. The data carries a key; this names it. */
  milestone: {
    START: string
    GOAL: string
    STEEPEST: string
    'LOWEST BATTERY': string
  }
  launcher: string
  launcherTitle: string
}

export const COPY: Record<ReportLang, ReportCopy> = {
  en: {
    kicker: 'Mission report',
    title: 'Route complete',
    subtitle: (rover, km, waypoints) =>
      `${rover} drove ${km} km over ${waypoints} waypoints.`,
    metaRover: 'Rover',
    metaRegion: 'Region',
    metaGenerated: 'Report',
    regionValue: (w, h, res) =>
      `${fmtNum(w, 1, 'en')} × ${fmtNum(h, 1, 'en')} km · ${fmtNum(res, 0, 'en')} m/px`,
    langSwitchLabel: 'Report language',
    savePdf: 'Save as PDF',
    downloadData: 'Download data',
    backToMap: 'Back to map',
    backToMapAria: 'Close the report and return to the map',
    askAssistant: 'Ask the assistant',
    askAssistantTurkishHint: 'The assistant answers in Turkish',
    sections: {
      decision: 'Decision summary',
      battery: 'Battery profile',
      slope: 'Slope distribution',
      risk: 'Risk distribution',
      thermal: 'Thermal envelope',
      shadow: 'Shadow exposure',
      energy: 'Energy breakdown',
      terrain: 'Terrain cut',
      planner: 'Planner evidence',
      milestones: 'Milestones',
      safety: 'Formal safety requirements',
      costModel: 'Cost model evidence',
    },
    evidence: {
      requirement: 'Requirement',
      margin: 'Margin',
      worstAt: 'Tightest at',
      untested: 'Could not be tested on this trace. Untested is not passed.',
      claimBoundary: 'Claim boundary',
      monitor: 'Monitor',
      scope: 'Where it applies',
      notApplied: 'Not applied',
      sources: 'Sources',
    },
    notes: {
      recharges: (n) => `${n} recharge stops (dashed green)`,
      noRecharges: 'No recharge stops',
      steepest: (deg) => `Steepest step ${deg}°`,
      riskPerStep: 'Risk level per step',
      thermalRange: (min, max) => `${min}°C … ${max}°C`,
      shadowLimit: 'Continuous shadow against the rover limit',
      energySource:
        'Drive energy from the simulation; payload and heater from the operator setting',
      terrainPainted: 'Elevation, painted by step risk',
      plannerEvidence: 'A* really did apply constraints',
    },
    kpi: {
      distance: 'Distance',
      duration: 'Duration',
      endBattery: 'End battery',
      lowestBattery: 'Lowest battery',
      energyUsed: 'Energy used',
      maxSlope: 'Max slope',
      recharges: 'Recharges',
      routeNodes: 'Route nodes',
    },
    charts: {
      batteryTitle: 'Battery percentage against distance',
      batteryReserve: (pct) => `RESERVE ${pct}`,
      batteryMin: (pct) => `MIN ${pct}`,
      thermalTitle: 'Surface temperature against distance',
      thermalMin: (t) => `MIN ${t}°C`,
      thermalMax: (t) => `MAX ${t}°C`,
      shadowGaugeLabel: 'Continuous shadow',
      shadowTitle: 'Shadow ratio against distance',
      elevationTitle: 'Elevation against distance',
      donutTotal: 'Total Wh',
      drive: 'Drive',
      payload: 'Payload',
      heater: 'Heater',
      notEnoughPoints: 'Not enough points to plot.',
      noElevation: 'No elevation data.',
      noShadowLimit: 'No shadow limit is defined for this rover.',
      limitExceeded: 'Limit exceeded — the route is not safe as planned.',
      limitUsed: (pct) => `${pct} of the limit used.`,
    },
    details: {
      show: 'Technical detail (terrain cut, planner evidence, milestones)',
      hide: 'Hide technical detail',
    },
    planner: {
      nodesExpanded: 'Nodes expanded',
      solveTime: 'Solve time',
      totalCost: 'Total weighted cost',
      barrierShare: 'Barrier share',
      edgesRejected: (reason) => `Edges rejected · ${reason}`,
    },
    table: {
      point: 'Point',
      step: 'Step',
      km: 'KM',
      battery: 'Battery',
      slope: 'Slope',
      temp: 'Temp',
      risk: 'Risk',
    },
    milestone: {
      START: 'START',
      GOAL: 'GOAL',
      STEEPEST: 'STEEPEST',
      'LOWEST BATTERY': 'LOWEST BATTERY',
    },
    launcher: 'Mission Report',
    launcherTitle: 'Open the post-drive mission report',
  },
  tr: {
    kicker: 'Görev raporu',
    title: 'Rota tamamlandı',
    subtitle: (rover, km, waypoints) =>
      `${rover}, ${waypoints} ara noktada ${km} km sürdü.`,
    metaRover: 'Rover',
    metaRegion: 'Bölge',
    metaGenerated: 'Rapor',
    regionValue: (w, h, res) =>
      `${fmtNum(w, 1, 'tr')} × ${fmtNum(h, 1, 'tr')} km · ${fmtNum(res, 0, 'tr')} m/px`,
    langSwitchLabel: 'Rapor dili',
    savePdf: 'PDF olarak kaydet',
    downloadData: 'Veriyi indir',
    backToMap: 'Haritaya dön',
    backToMapAria: 'Raporu kapat ve haritaya dön',
    askAssistant: 'Asistana sor',
    askAssistantTurkishHint: 'Asistan Türkçe yanıtlar',
    sections: {
      decision: 'Karar özeti',
      battery: 'Batarya profili',
      slope: 'Eğim dağılımı',
      risk: 'Risk dağılımı',
      thermal: 'Termal zarf',
      shadow: 'Gölge maruziyeti',
      energy: 'Enerji dağılımı',
      terrain: 'Arazi kesiti',
      planner: 'Planlayıcı kanıtları',
      milestones: 'Kilometre taşları',
      safety: 'Formal güvenlik gereksinimleri',
      costModel: 'Maliyet modeli kanıtı',
    },
    evidence: {
      requirement: 'Gereksinim',
      margin: 'Marj',
      worstAt: 'En dar nokta',
      untested: 'Bu izde test edilemedi. Test edilmemiş, geçmiş değildir.',
      claimBoundary: 'İddia sınırı',
      monitor: 'İzleyici',
      scope: 'Nereye giriyor',
      notApplied: 'Uygulanmadı',
      sources: 'Kaynaklar',
    },
    notes: {
      recharges: (n) => `${n} şarj molası (kesikli yeşil)`,
      noRecharges: 'Şarj molası yok',
      steepest: (deg) => `En dik adım ${deg}°`,
      riskPerStep: 'Adım başına risk seviyesi',
      thermalRange: (min, max) => `${min}°C … ${max}°C`,
      shadowLimit: 'Kesintisiz gölge, rover sınırına karşı',
      energySource:
        'Sürüş enerjisi simülasyondan; faydalı yük ve ısıtıcı operatör ayarından',
      terrainPainted: 'Yükseklik, adım riskine göre renklendirilmiş',
      plannerEvidence: 'A* kısıtları gerçekten uyguladı',
    },
    kpi: {
      distance: 'Mesafe',
      duration: 'Süre',
      endBattery: 'Varış bataryası',
      lowestBattery: 'En düşük batarya',
      energyUsed: 'Tüketilen enerji',
      maxSlope: 'En yüksek eğim',
      recharges: 'Şarj molası',
      routeNodes: 'Rota düğümü',
    },
    charts: {
      batteryTitle: 'Mesafeye göre batarya yüzdesi',
      batteryReserve: (pct) => `REZERV ${pct}`,
      batteryMin: (pct) => `EN DÜŞÜK ${pct}`,
      thermalTitle: 'Mesafeye göre yüzey sıcaklığı',
      thermalMin: (t) => `EN DÜŞÜK ${t}°C`,
      thermalMax: (t) => `EN YÜKSEK ${t}°C`,
      shadowGaugeLabel: 'Kesintisiz gölge',
      shadowTitle: 'Mesafeye göre gölge oranı',
      elevationTitle: 'Mesafeye göre yükseklik',
      donutTotal: 'Toplam Wh',
      drive: 'Sürüş',
      payload: 'Faydalı yük',
      heater: 'Isıtıcı',
      notEnoughPoints: 'Çizim için yeterli nokta yok.',
      noElevation: 'Yükseklik verisi yok.',
      noShadowLimit: 'Bu rover için tanımlı gölge sınırı yok.',
      limitExceeded: 'Sınır aşıldı — rota planlandığı hâliyle güvenli değil.',
      limitUsed: (pct) => `Sınırın ${pct} kadarı kullanıldı.`,
    },
    details: {
      show: 'Teknik ayrıntı (arazi kesiti, planlayıcı kanıtları, kilometre taşları)',
      hide: 'Teknik ayrıntıyı gizle',
    },
    planner: {
      nodesExpanded: 'Genişletilen düğüm',
      solveTime: 'Çözüm süresi',
      totalCost: 'Toplam ağırlıklı maliyet',
      barrierShare: 'Bariyer payı',
      edgesRejected: (reason) => `Reddedilen kenar · ${reason}`,
    },
    table: {
      point: 'Nokta',
      step: 'Adım',
      km: 'KM',
      battery: 'Batarya',
      slope: 'Eğim',
      temp: 'Sıcaklık',
      risk: 'Risk',
    },
    milestone: {
      START: 'BAŞLANGIÇ',
      GOAL: 'HEDEF',
      STEEPEST: 'EN DİK',
      'LOWEST BATTERY': 'EN DÜŞÜK BATARYA',
    },
    launcher: 'Görev Raporu',
    launcherTitle: 'Sürüş sonrası görev raporunu aç',
  },
}

/**
 * Where the choice is kept.
 *
 * The first persisted preference in this application -- nothing else in the
 * frontend touches localStorage. Both accessors swallow their errors on
 * purpose: a private window, a browser set to block site data, and a
 * thumbnail-capture context all throw on access rather than returning null,
 * and a report that refuses to open because it could not read a preference is
 * a worse failure than one that opens in English.
 */
const STORAGE_KEY = 'lunapath.report.lang'

export const DEFAULT_LANG: ReportLang = 'en'

function isLang(value: unknown): value is ReportLang {
  return value === 'en' || value === 'tr'
}

export function readLang(): ReportLang {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    return isLang(stored) ? stored : DEFAULT_LANG
  } catch {
    return DEFAULT_LANG
  }
}

export function writeLang(lang: ReportLang): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, lang)
  } catch {
    // The report still works; only the memory of the choice is lost.
  }
}
