"""K1 -- the analysis core's types, and the canonical rendering of a number.

Every number the assistant is allowed to say is a ``Metric`` in some
envelope's ``numeric_registry``. K4 copies the metric's ``display`` string
verbatim; K5 masks those strings out of the draft and asserts no digit
survives. That strategy only holds if ``display`` is a pure, total function of
``(value, unit, precision)`` -- so the format is locked here and nowhere else.

The single most load-bearing decision is that there is **no thousands
separator**. It removes ``1.490,23`` from the system at the source, which means
K5 never has to answer whether ``1.490`` is one thousand four hundred ninety or
one point four nine. K5 owns no number parser, by construction.

Rounding happens exactly once, here, per ``precision``. K5's tolerance is
therefore zero: it compares strings, not magnitudes. Do not add an epsilon
anywhere downstream.

Contract: docs/ai/LunaPath_AI_Chatbot_Scope_v0.3.md sections 12 and 13.
"""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Literal, Mapping, Optional

from pydantic import BaseModel, Field, field_validator

from .ai_evidence import Quantity

ValiditySource = Literal["MEASURED", "MODEL", "DERIVED", "SYNTHETIC"]
Severity = Literal["info", "caution", "critical"]

# A dimensionless quantity renders bare: "0,13215", not "0,13215 dimensionless".
DIMENSIONLESS = "dimensionless"

# Default decimal places per unit, so callers do not each invent one. A metric
# may override, but the default has to exist: two renderings of the same value
# would both be "registered", which weakens the mask.
_UNIT_PRECISION: dict[str, int] = {
    "Wh": 2,
    "km": 3,
    "m": 1,
    "h": 2,
    "%": 1,
    "deg": 2,
    "degC": 1,
    "weighted_metres": 1,
    "kg": 0,
    "m/s": 2,
    DIMENSIONLESS: 5,
}
_DEFAULT_PRECISION = 2


def format_display(value: float, unit: str, precision: Optional[int] = None) -> str:
    """The one canonical rendering of a quantity.

    Decimal comma, no grouping, ASCII hyphen for the sign, unit after exactly
    one space, and nothing at all after a dimensionless value.
    """
    if value is None or isinstance(value, bool) or not math.isfinite(float(value)):
        raise ValueError(f"cannot render a non-finite value: {value!r}")
    if precision is None:
        precision = _UNIT_PRECISION.get(unit, _DEFAULT_PRECISION)
    if precision < 0:
        raise ValueError("precision must be non-negative")

    # ROUND_HALF_UP rather than Python's banker's rounding: the operator reads
    # 13,25 -> 13,3, and a half-even surprise here would look like an error.
    quantum = Decimal(1).scaleb(-precision)
    rounded = Decimal(repr(float(value))).quantize(quantum, rounding=ROUND_HALF_UP)

    text = f"{rounded:f}".replace(".", ",")
    if text.startswith("-") and set(text) <= {"-", "0", ","}:
        text = text[1:]  # -0,00 reads as an error; it is zero
    if unit == DIMENSIONLESS:
        return text
    return f"{text} {unit}"


# Alternative renderings of the SAME digits, per unit. Turkish prose writes
# "%34,2" where the canonical display is "34,2 %", and "12,34 derece" where it
# is "12,34 deg" -- so a correct, faithful answer was being blocked for a
# convention, not for a fabricated number.
#
# Strictly digit-preserving: every entry embeds the canonical numeric text
# verbatim, so nothing here can spell a value the registry does not hold. This
# is NOT the general auto-derivation Metric.display_alt warns about -- a numeral
# WORD would let the verbalizer say any registered number, and none is produced
# here. A test pins both properties.
#
# Wh/kWh are deliberately absent: _mask_aliases is case-insensitive, and case is
# exactly what keeps "Wh" from being loosened into "wh".
_UNIT_ALIAS_FORMS: dict[str, tuple[str, ...]] = {
    # Both orders. Turkish writes "%67,9" and the canonical display is "67,9 %",
    # but a model also writes the suffix form with no space -- and "67,9%"
    # matched neither, so a correct answer was blocked over a space. The alias
    # embeds the canonical digits verbatim and swallows the percent sign with
    # them, so it authorises no bare digit and leaves no % for the leftover scan.
    "%": ("%{n}", "{n}%"),
    "deg": ("{n}°", "{n} derece"),
    "degC": ("{n} °C", "{n}°C", "{n} derece"),
    "h": ("{n} saat",),
    "km": ("{n} kilometre",),
    "m": ("{n} metre",),
    "m/s": ("{n} m/sn",),
}


def unit_aliases(display: str, unit: str) -> list[str]:
    """Digit-preserving alternative renderings of one canonical display."""
    forms = _UNIT_ALIAS_FORMS.get(unit)
    if not forms:
        return []
    numeric = display[: -len(unit)].strip() if display.endswith(unit) else display
    if not numeric:
        return []
    return [form.format(n=numeric) for form in forms]


class Provenance(BaseModel):
    """Where a number came from. The AI layer never invents this."""

    source: ValiditySource
    layer: Optional[str] = None
    dataset: Optional[str] = None
    version: Optional[str] = None
    note: Optional[str] = None


class Metric(BaseModel):
    """One number the verbalizer is permitted to state, and how to write it."""

    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    quantity: Quantity
    provenance: Provenance
    display: str = Field(min_length=1)
    # Exact phrases K1 explicitly permits as alternative renderings of THIS
    # metric, e.g. "dort profil" for a registered count. Never generated
    # automatically: an auto-derived numeral word would let the verbalizer
    # spell any registered value, which is what the grounding check exists
    # to prevent.
    display_alt: list[str] = Field(default_factory=list)


class EnvelopeWarning(BaseModel):
    """Mandatory, structured, and never hidden.

    Named ``EnvelopeWarning`` rather than ``Warning`` so it does not shadow the
    builtin; it travels on the wire as ``warnings``. ``suppressible`` is pinned
    to False by the type system because N-14 forbids any level -- or any
    caller -- from dropping one.
    """

    code: str = Field(min_length=1)
    severity: Severity
    message: str = Field(min_length=1)
    suppressible: Literal[False] = False


class GuideFact(BaseModel):
    """One canonical product statement K4 may paraphrase.

    ``key`` is drawn from a closed deterministic registry, so a fact is always
    traceable to the entry K1 selected. K4 receives only the SELECTED facts and
    is instructed to add no product claim outside them.

    Honest about the boundary: K5 verifies registered numbers and the forbidden
    claim rules. It does not -- and this pass does not build anything that does
    -- prove semantic equivalence between a fact and the sentence K4 wrote from
    it. The containment is that the deterministic registry is the only source
    of product statements reaching the model at all.
    """

    key: str = Field(min_length=1)
    text: str = Field(min_length=1)


class ErrorInfo(BaseModel):
    code: str
    message: str


class AnalysisEnvelope(BaseModel):
    """K1's whole output. K4 sees this and nothing else."""

    capability: str
    request_echo: dict[str, Any] = Field(default_factory=dict)
    ok: bool
    payload: Optional[dict[str, Any]] = None
    error: Optional[ErrorInfo] = None
    numeric_registry: list[Metric] = Field(default_factory=list)
    # Canonical non-numeric product statements. Empty for every analysis
    # capability, so their briefing is byte-for-byte what it was.
    facts: list[GuideFact] = Field(default_factory=list)
    # Exact strings K1 authorises the draft to contain: product identifiers
    # ("2D", "LPR-1") and phrases whose wording would otherwise trip a leftover
    # scan. Bounded by construction and empty unless K1 filled it.
    lexicon: list[str] = Field(default_factory=list)
    warnings: list[EnvelopeWarning] = Field(default_factory=list)
    provenance_summary: list[Provenance] = Field(default_factory=list)
    compute_ms: float = 0.0
    backend_version: str = ""

    @field_validator("compute_ms")
    @classmethod
    def _finite_ms(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("compute_ms must be finite")
        return v


def make_metric(
    *,
    key: str,
    label: str,
    value: float,
    unit: str,
    provenance: Provenance,
    precision: Optional[int] = None,
    display_alt: Optional[list[str]] = None,
) -> Metric:
    """Register one number, with its unit and its canonical rendering."""
    quantity = Quantity(value=float(value), unit=unit, precision=precision)
    display = format_display(float(value), unit, precision)
    aliases = list(display_alt or [])
    for alias in unit_aliases(display, unit):
        if alias not in aliases:
            aliases.append(alias)
    return Metric(
        key=key,
        label=label,
        quantity=quantity,
        provenance=provenance,
        display=display,
        display_alt=aliases,
    )


def percent_of_ratio(ratio: Metric, *, key: str, label: str) -> Metric:
    """Turn a registered ratio into a registered percentage.

    K1 does this multiplication so the verbalizer does not have to -- N-1 bans
    the model from converting ``0,13215`` into ``13,2 %`` itself, which without
    this helper would make ratios effectively unspeakable.

    Deliberately NOT applied to every ratio: a percentage is registered only
    where the product actually needs one, and it carries DERIVED provenance
    naming the metric it came from, so its lineage survives.
    """
    return make_metric(
        key=key,
        label=f"{label} (yüzde)",
        value=ratio.quantity.value * 100.0,
        unit="%",
        provenance=Provenance(
            source="DERIVED",
            layer=ratio.provenance.layer,
            note=f"{ratio.key} oranından türetildi",
        ),
    )


# ── envelope builders (K1) ───────────────────────────────────────────────────

# Label and unit for each field a sanitizer may emit. A field absent from
# here is never registered, which is what keeps the verbalizer's vocabulary
# narrow: registering every raw number would defeat the point of a registry.
# Ordered by what a route summary leads with: route, then energy, then
# terrain/risk. K4 used to be handed the registry in registration order and had
# no way to tell a core fact from a secondary one, so it opened on whichever
# metric happened to come first.
_PLAN_QUANTITIES: tuple[tuple[str, str, str], ...] = (
    ("distance", "Toplam mesafe", "km"),
    ("elapsed", "Geçen süre", "h"),
    ("energy", "Toplam enerji tüketimi", "Wh"),
    ("min_battery", "Minimum batarya", "%"),
    ("final_battery", "Varıştaki batarya", "%"),
    ("max_slope", "En dik eğim", "deg"),
    ("max_continuous_shadow", "En uzun kesintisiz gölge", "h"),
)

_PLAN_COUNTS: tuple[tuple[str, str], ...] = (
    ("waypoint_count", "Rota düğüm sayısı"),
    ("total_recharges", "Şarj sayısı"),
    ("critical_steps_count", "Kritik adım sayısı"),
    ("high_or_above_steps_count", "Yüksek riskli adım sayısı"),
)

# The grouping K4 is told about, so ordering survives a metric it does not
# recognise. A key absent from here carries no section and is secondary by
# omission rather than by K4 guessing.
_SUMMARY_SECTIONS: dict[str, str] = {
    "distance": "route",
    "elapsed": "route",
    "waypoint_count": "route",
    "energy": "energy",
    "min_battery": "energy",
    "final_battery": "energy",
    "total_recharges": "energy",
    "max_slope": "terrain",
    "max_continuous_shadow": "terrain",
    "critical_steps_count": "terrain",
    "high_or_above_steps_count": "terrain",
}


def summary_section(key: str) -> Optional[str]:
    """Which part of a route summary a registered metric belongs to."""
    return _SUMMARY_SECTIONS.get(key)

_CELL_QUANTITIES: tuple[tuple[str, str, str], ...] = (
    ("altitude", "Yükseklik", "m"),
    ("thermal", "Yüzey sıcaklığı (tepe)", "degC"),
    ("thermal_min", "Yüzey sıcaklığı (soğuk uç)", "degC"),
    ("resolution", "Çözünürlük", "m"),
    ("span", "Bölge genişliği", "km"),
)

_SIMULATION_QUANTITIES: tuple[tuple[str, str, str], ...] = (
    ("total_distance_km", "mesafe", "km"),
    ("total_energy_consumed_wh", "enerji", "Wh"),
    ("max_continuous_shadow_h", "en uzun kesintisiz gölge", "h"),
    ("min_battery_pct", "minimum batarya", "%"),
    ("total_elapsed_hours", "geçen süre", "h"),
)


def _quantity_metric(
    payload: Mapping[str, Any],
    field: str,
    key: str,
    label: str,
    unit: str,
    provenance: "Provenance",
) -> Optional[Metric]:
    entry = payload.get(field)
    if not isinstance(entry, Mapping):
        return None
    value = entry.get("value")
    if value is None:
        return None
    try:
        return make_metric(
            key=key, label=label, value=float(value), unit=unit, provenance=provenance
        )
    except (TypeError, ValueError):
        return None


def plan_registry(
    plan: Mapping[str, Any], provenance: "Provenance"
) -> list[Metric]:
    """Register the plan facts a summary may state."""
    metrics: list[Metric] = []
    for field, label, unit in _PLAN_QUANTITIES:
        metric = _quantity_metric(plan, field, field, label, unit, provenance)
        if metric is not None:
            metrics.append(metric)
    for field, label in _PLAN_COUNTS:
        value = plan.get(field)
        if isinstance(value, int) and not isinstance(value, bool):
            metrics.append(
                make_metric(
                    key=field,
                    label=label,
                    value=value,
                    unit=DIMENSIONLESS,
                    provenance=provenance,
                    precision=0,
                )
            )
    return metrics


def cell_registry(
    cell: Mapping[str, Any], provenance: "Provenance"
) -> list[Metric]:
    """Register one cell's telemetry, and its decomposition when it is valid."""
    metrics: list[Metric] = []
    for field, label, unit in _CELL_QUANTITIES:
        metric = _quantity_metric(cell, field, field, label, unit, provenance)
        if metric is not None:
            metrics.append(metric)
    for field, label in (("row", "Satır"), ("col", "Sütun")):
        value = cell.get(field)
        if isinstance(value, int) and not isinstance(value, bool):
            metrics.append(
                make_metric(
                    key=field, label=label, value=value, unit=DIMENSIONLESS,
                    provenance=provenance, precision=0,
                )
            )
    breakdown = cell.get("cost_breakdown")
    if isinstance(breakdown, Mapping):
        for component, value in breakdown.items():
            if value is None:
                continue
            try:
                metrics.append(
                    make_metric(
                        key=f"cost_{component}",
                        label=f"Maliyet bileşeni: {component}",
                        value=float(value),
                        unit=DIMENSIONLESS,
                        provenance=provenance,
                    )
                )
            except (TypeError, ValueError):
                continue
    return metrics


def compare_registry(
    compare: Mapping[str, Any], provenance: "Provenance"
) -> list[Metric]:
    """Register the per-profile figures a comparison may state."""
    profiles = compare.get("profiles") or []
    metrics: list[Metric] = [
        make_metric(
            key="profile_count",
            label="Karşılaştırılan profil sayısı",
            value=len(profiles),
            unit=DIMENSIONLESS,
            provenance=provenance,
            precision=0,
        )
    ]
    for profile in profiles:
        profile_id = profile.get("profile_id") or "?"
        name = profile.get("profile_name") or profile_id
        simulation = profile.get("simulation_summary") or {}
        for field, label, unit in _SIMULATION_QUANTITIES:
            value = simulation.get(field)
            if value is None:
                continue
            try:
                metrics.append(
                    make_metric(
                        key=f"{profile_id}.{field}",
                        label=f"{name} — {label}",
                        value=float(value),
                        unit=unit,
                        provenance=provenance,
                    )
                )
            except (TypeError, ValueError):
                continue
    return metrics


def constraint_warnings(compare: Mapping[str, Any]) -> list[EnvelopeWarning]:
    """Warn only where a deterministic backend field says a limit was missed.

    There is no AI-defined "near constraint" threshold: a proximity number we
    invented would be an interpretation dressed as a measurement. Only an
    explicit ``satisfied is False`` produces a warning.
    """
    warnings: list[EnvelopeWarning] = []
    for profile in compare.get("profiles") or []:
        name = profile.get("profile_name") or profile.get("profile_id") or "?"
        for key, verdict in (profile.get("constraint_check") or {}).items():
            if not isinstance(verdict, Mapping):
                continue
            if verdict.get("satisfied") is False:
                warnings.append(
                    EnvelopeWarning(
                        code="CONSTRAINT_VIOLATED",
                        severity="critical",
                        message=(
                            f"{name} profilinde {key} kısıtı sağlanmıyor."
                        ),
                    )
                )
    return warnings
