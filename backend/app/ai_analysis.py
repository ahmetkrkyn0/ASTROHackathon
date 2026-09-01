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
from typing import Any, Literal, Optional

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
) -> Metric:
    """Register one number, with its unit and its canonical rendering."""
    quantity = Quantity(value=float(value), unit=unit, precision=precision)
    return Metric(
        key=key,
        label=label,
        quantity=quantity,
        provenance=provenance,
        display=format_display(float(value), unit, precision),
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
