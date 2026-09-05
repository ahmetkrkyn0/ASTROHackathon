"""C-GUIDE -- the deterministic product-help knowledge source.

Planning help is answered the same way route analysis is: K1 selects
deterministic evidence, K4 phrases it, K5 checks the numbers. What changes is
the *kind* of evidence. A route summary is numbers; product help is mostly
sentences, so this module publishes a closed registry of canonical statements
alongside the registered rover quantities.

Three properties hold it together:

* **The registry is closed.** ``GUIDE_FACTS`` is a literal table and
  ``_TOPIC_FACTS`` says which entries each topic selects. K4 receives only the
  selected entries, so a product claim that is not in this file never reaches
  the model as evidence.
* **Numbers stay in the NumericRegistry.** No fact carries a quantity. Rover
  specs are registered ``Metric``s with canonical displays, exactly like plan
  metrics, so K5 masks them and the zero-tolerance string match still applies.
* **Nothing here executes anything.** There is no handler, no tool and no
  writer. ``guide_evidence`` reads the rover catalogue and returns a dict. The
  read-only guarantee is structural, not a check that could be forgotten.

Honest about the boundary: K5 verifies registered numbers and the forbidden
claim rules. It does not prove that a sentence K4 wrote is semantically
equivalent to the fact it came from, and this module does not add a validator
that would claim to. The containment is that the closed registry is the only
source of product statements the model is given.

Contract: docs/ai/LunaPath_AI_Chatbot_Scope_v0.3.md sections 6 and 12.
"""

from __future__ import annotations

from typing import Any, Literal, Mapping, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field

from .ai_analysis import (
    COUNT_WORDS,
    DIMENSIONLESS,
    GuideFact,
    Metric,
    Provenance,
    make_metric,
)

# -- the closed parameter vocabulary (K3 validates against this) -------------

GuideTopic = Literal[
    "workflow",
    "priority",
    "layer",
    "view",
    "mission_controls",
    "rover",
]

# One enum across every topic rather than six. A wrong pairing selects the
# topic's default fact set, which is a less useful answer but never an invalid
# one -- and six schemas is how a router starts guessing.
GuideSubject = Literal[
    "all",
    # workflow
    "overview",
    "first_steps",
    # priority
    "slope_safety",
    "energy_use",
    "shadow_exposure",
    "thermal_risk",
    "not_percentages",
    # layer
    "surface",
    "thermal",
    "cost",
    "shadow",
    "traversability",
    "slope",
    "aspect",
    # view
    "two_d",
    "three_d",
    # mission controls
    "start",
    "goal",
    "clear",
    "generate_route",
    "rover_select",
]

# A comparison the operator named a criterion for. K1 resolves it; K4 never
# compares two registered values.
GuideCriterion = Literal[
    "battery",
    "speed",
    "slope_limit",
    "mass",
    "shadow_endurance",
]


class GuideParams(BaseModel):
    """What K2 may ask the guide for. Closed on every axis."""

    model_config = ConfigDict(extra="forbid")

    topic: GuideTopic
    subject: Optional[GuideSubject] = None
    # Empty means "every catalogued rover". Capped so a router cannot ask for a
    # registry-sized answer.
    rover_ids: list[str] = Field(default_factory=list, max_length=4)
    criterion: Optional[GuideCriterion] = None


# -- the canonical fact table -----------------------------------------------

# Deliberately statements, not paragraphs: each entry is one checkable claim
# about how LunaPath behaves. Nothing here carries a quantity -- a number that
# belongs in an answer is a Metric, and a number written into a sentence here
# would be a number K5 could not trace. Product identifiers that contain a
# digit ("2D", "3D") are permitted and are authorised through ``guide_lexicon``.
GUIDE_FACTS: dict[str, str] = {
    # workflow ---------------------------------------------------------------
    "workflow.overview": (
        "LunaPath, Ay güney kutbunda görev yapacak bir rover için görev öncesi "
        "rota planlama ve karar destek aracıdır. Ekranın akışı şudur: rover "
        "seçilir, rota öncelikleri gözden geçirilir, haritada başlangıç ve "
        "hedef hücresi belirlenir, ardından Generate Route ile rota üretilir."
    ),
    "workflow.first_steps": (
        "Önce bir rover seçin. Sonra haritada başlangıç ve hedef hücresini "
        "belirleyin. Rota önceliklerini gözden geçirdikten sonra Generate Route "
        "ile rotayı üretin."
    ),
    "workflow.after_route": (
        "Rota üretildikten sonra asistan analiz moduna geçer; mesafe, enerji, "
        "batarya, eğim ve uyarılar deterministik analiz kayıtlarından "
        "açıklanabilir hale gelir."
    ),
    # route priorities -------------------------------------------------------
    "priority.overview": (
        "Rota öncelikleri planlayıcının maliyet fonksiyonundaki ağırlık "
        "katsayılarıdır: Slope Safety, Energy Use, Shadow Exposure ve Thermal "
        "Risk."
    ),
    "priority.not_percentages": (
        "Bu öncelikler yüzde değildir. Toplamlarının sabit bir değere eşit "
        "olması gerekmez ve birini değiştirmek diğerlerini kendiliğinden "
        "yeniden ölçeklemez; her biri kendi bileşeninin maliyete katkısını "
        "ölçekleyen bağımsız bir katsayıdır."
    ),
    "priority.slope_safety": (
        "Slope Safety, eğimli geçişlerin maliyetini ölçekler. Katsayı "
        "yükseldikçe planlayıcı dik geçişlerden daha çok kaçınır."
    ),
    "priority.energy_use": (
        "Energy Use, enerji tüketimi yüksek geçişlerin maliyetini ölçekler. "
        "Katsayı yükseldikçe planlayıcı enerji açısından daha ucuz güzergâhları "
        "tercih eder."
    ),
    "priority.shadow_exposure": (
        "Shadow Exposure, gölgede kalan hücrelerin maliyetini ölçekler. Katsayı "
        "yükseldikçe planlayıcı gölgeli bölgelerden daha çok kaçınır."
    ),
    "priority.thermal_risk": (
        "Thermal Risk, termal açıdan riskli hücrelerin maliyetini ölçekler. "
        "Katsayı yükseldikçe planlayıcı bu bölgelerden daha çok kaçınır."
    ),
    "priority.operator_only": (
        "Öncelik katsayılarını yalnızca operatör değiştirir; sol paneldeki "
        "kaydırıcılar kullanılır. Asistan bu değerleri değiştiremez."
    ),
    "priority.invalidates_route": (
        "Bir öncelik katsayısını değiştirmek ekrandaki rotayı geçersiz kılar; "
        "yeni rota için Generate Route yeniden çalıştırılmalıdır."
    ),
    # terrain layers ---------------------------------------------------------
    "layer.overview": (
        "Harita katmanları arazinin farklı bir ölçüsünü gösterir: Surface, "
        "Thermal, Cost, Shadow, Traversability, Slope ve Aspect."
    ),
    "layer.surface": "Surface katmanı arazi yükseklik verisini gösterir.",
    "layer.thermal": "Thermal katmanı modellenen yüzey sıcaklığını gösterir.",
    "layer.cost": (
        "Cost katmanı, seçili öncelik katsayılarıyla hesaplanan birleşik geçiş "
        "maliyetini gösterir. Tek bir fiziksel büyüklük değil, planlayıcının "
        "kullandığı bileşik maliyettir."
    ),
    "layer.shadow": (
        "Shadow katmanı, bir hücrenin gölgede kalma oranını gösterir."
    ),
    "layer.cost_vs_shadow": (
        "Cost ve Shadow aynı şey değildir. Shadow tek bir arazi ölçüsüdür; Cost "
        "ise gölge dahil birden çok bileşenin ağırlıklı bileşimidir."
    ),
    "layer.traversability": (
        "Traversability, bir hücrenin seçili rover için geçilebilir olup "
        "olmadığını gösterir; eğim limiti ve veri geçerliliği gibi kısıtlardan "
        "türetilir."
    ),
    "layer.slope": "Slope katmanı arazi eğiminin dikliğini gösterir.",
    "layer.aspect": "Aspect katmanı eğimin baktığı yönü gösterir.",
    "layer.slope_vs_aspect": (
        "Slope eğimin ne kadar dik olduğunu, Aspect ise o eğimin hangi yöne "
        "baktığını söyler."
    ),
    "layer.static_shadow": (
        "Gölge modeli bu sürümde statiktir; zamana göre değişen bir gölge "
        "gösterimi değildir."
    ),
    # view dimension ---------------------------------------------------------
    "view.overview": (
        "Arazi 2D ve 3D olarak görüntülenebilir. İkisi de aynı arazi verisini "
        "gösterir; aralarındaki fark sunumdur, veri değildir."
    ),
    "view.two_d": (
        "2D görünüm arazinin üstten bakışıdır; hücre seçimi ve katman okuması "
        "bu görünümde yapılır."
    ),
    "view.three_d": (
        "3D görünüm aynı arazinin yükseklikli bir yüzey olarak sunumudur."
    ),
    # mission controls -------------------------------------------------------
    "mission_controls.overview": (
        "Görev kontrolleri şunlardır: rover seçimi, başlangıç ve hedef seçimi, "
        "temizleme ve Generate Route."
    ),
    "mission_controls.start": (
        "Başlangıç noktası, başlangıç seçim modundayken haritada ilgili "
        "hücreye tıklanarak belirlenir."
    ),
    "mission_controls.goal": (
        "Hedef noktası, hedef seçim modundayken haritada ilgili hücreye "
        "tıklanarak belirlenir."
    ),
    "mission_controls.generate_route": (
        "Generate Route, seçili rover, öncelik katsayıları, başlangıç ve hedef "
        "ile planlayıcıyı çalıştırır ve rotayı üretir. Bu işlemi yalnızca "
        "operatör başlatır."
    ),
    "mission_controls.clear": (
        "Temizleme, seçili başlangıç ve hedefi ve ekrandaki rotayı kaldırır."
    ),
    "mission_controls.invalidation": (
        "Başlangıcı, hedefi, rover'ı ya da bir öncelik katsayısını değiştirmek "
        "ekrandaki rotayı geçersiz kılar; rota yeniden üretilene kadar rota "
        "analizi soruları cevaplanamaz."
    ),
    "mission_controls.rover_select": (
        "Rover seçimi, planlayıcının kullandığı kütle, azami hız, batarya "
        "kapasitesi, eğim limitleri ve gölge dayanımı gibi parametreleri "
        "değiştirir; geçilebilirlik maskesi ve maliyet ızgarası seçilen rover'a "
        "göre yeniden hesaplanır."
    ),
    # rover ------------------------------------------------------------------
    "rover.overview": (
        "Rover kataloğu planlayıcının okuduğu parametreleri taşır: kütle, "
        "azami hız, batarya kapasitesi, azami eğim, azami yanal eğim, minimum "
        "batarya rezervi ve azami gölge dayanımı."
    ),
    "rover.no_universal_best": (
        "Mevcut kanıtla evrensel olarak üstün bir rover belirlenemez; uygun "
        "rover göreve ve kısıtlara bağlıdır. Kayıtlı değerler karşılaştırma "
        "için verilmiştir."
    ),
    # read-only and product honesty -----------------------------------------
    "readonly.assistant": (
        "Asistan yalnızca okur. Rover'ı, öncelik katsayılarını, başlangıcı, "
        "hedefi, katmanı ya da görünümü değiştiremez ve rota üretemez; bunları "
        "operatör kendisi yapar."
    ),
    "honesty.focus_cell": (
        "Asistanın çözümlediği hücre imlecin üzerinde durduğu hücre değildir; "
        "hedef seçiliyse hedef, değilse başlangıç hücresidir."
    ),
    "honesty.unknown_stays_unknown": (
        "Veri geçerliliği bilinmiyorsa bilinmiyor olarak kalır; eksik veri "
        "tahmin edilmez."
    ),
}


# Which entries each topic selects, and in what order. A subject narrows the
# selection; an unknown or absent subject falls back to the topic's own set.
_TOPIC_FACTS: dict[str, tuple[str, ...]] = {
    "workflow": (
        "workflow.overview",
        "workflow.first_steps",
        "workflow.after_route",
        "readonly.assistant",
    ),
    "priority": (
        "priority.overview",
        "priority.not_percentages",
        "priority.operator_only",
        "priority.invalidates_route",
    ),
    "layer": (
        "layer.overview",
        "layer.cost_vs_shadow",
        "layer.slope_vs_aspect",
        "layer.static_shadow",
    ),
    "view": ("view.overview", "view.two_d", "view.three_d"),
    "mission_controls": (
        "mission_controls.overview",
        "mission_controls.start",
        "mission_controls.goal",
        "mission_controls.generate_route",
        "mission_controls.invalidation",
        "readonly.assistant",
    ),
    "rover": ("rover.overview", "mission_controls.rover_select"),
}

# A subject that names one entry answers with that entry plus the topic's
# framing, rather than with the whole topic.
_SUBJECT_FACTS: dict[tuple[str, str], tuple[str, ...]] = {
    ("workflow", "overview"): ("workflow.overview", "workflow.first_steps"),
    ("workflow", "first_steps"): (
        "workflow.first_steps",
        "workflow.after_route",
    ),
    ("priority", "slope_safety"): (
        "priority.overview",
        "priority.slope_safety",
        "priority.not_percentages",
        "priority.operator_only",
    ),
    ("priority", "energy_use"): (
        "priority.overview",
        "priority.energy_use",
        "priority.not_percentages",
        "priority.operator_only",
    ),
    ("priority", "shadow_exposure"): (
        "priority.overview",
        "priority.shadow_exposure",
        "priority.not_percentages",
        "priority.operator_only",
    ),
    ("priority", "thermal_risk"): (
        "priority.overview",
        "priority.thermal_risk",
        "priority.not_percentages",
        "priority.operator_only",
    ),
    ("priority", "not_percentages"): (
        "priority.overview",
        "priority.not_percentages",
    ),
    ("layer", "surface"): ("layer.surface", "layer.overview"),
    ("layer", "thermal"): ("layer.thermal", "layer.overview"),
    ("layer", "cost"): ("layer.cost", "layer.cost_vs_shadow"),
    ("layer", "shadow"): (
        "layer.shadow",
        "layer.cost_vs_shadow",
        "layer.static_shadow",
    ),
    ("layer", "traversability"): ("layer.traversability", "layer.overview"),
    ("layer", "slope"): ("layer.slope", "layer.slope_vs_aspect"),
    ("layer", "aspect"): ("layer.aspect", "layer.slope_vs_aspect"),
    ("view", "two_d"): ("view.overview", "view.two_d"),
    ("view", "three_d"): ("view.overview", "view.three_d"),
    ("mission_controls", "start"): (
        "mission_controls.start",
        "mission_controls.invalidation",
        "readonly.assistant",
    ),
    ("mission_controls", "goal"): (
        "mission_controls.goal",
        "mission_controls.invalidation",
        "readonly.assistant",
    ),
    ("mission_controls", "clear"): (
        "mission_controls.clear",
        "mission_controls.invalidation",
    ),
    ("mission_controls", "generate_route"): (
        "mission_controls.generate_route",
        "readonly.assistant",
    ),
    ("mission_controls", "rover_select"): (
        "mission_controls.rover_select",
        "mission_controls.invalidation",
    ),
    ("rover", "rover_select"): (
        "mission_controls.rover_select",
        "rover.overview",
    ),
}


# -- the lexicon: exact strings a guide answer may legitimately contain ------

# Product identifiers that carry a digit. Enumerated, never pattern-matched:
# authorising "2D" must not authorise a bare "2" anywhere else, and the
# exact-token masking in ai_grounding is what keeps that true.
_VIEW_IDENTIFIERS: tuple[str, ...] = ("2D", "3D", "2d", "3d")

# The word "yüzde" is what the honest answer to "are these percentages?" has to
# contain, and the leftover scan fires on it by design. These exact phrasings
# are authorised for that one fact; an unauthorised percentage elsewhere in the
# same draft still blocks.
_PERCENT_PHRASES: tuple[str, ...] = (
    "yüzde değildir",
    "yüzde değil",
    "yüzde olarak yorumlanmamalıdır",
    "yüzde olarak",
    "yüzde cinsinden",
    "yüzde değeri",
    "yüzde mi",
)


# -- rover evidence ---------------------------------------------------------

# (catalogue field, Turkish label, unit, precision, scale). Restricted to what
# rover_catalog() actually publishes -- the power and thermal internals stay
# behind get_rover(), and reaching past the published surface here would widen
# the assistant's view of the backend for no product reason.
_ROVER_SPECS: tuple[tuple[str, str, str, int, float], ...] = (
    ("mass_kg", "kütle", "kg", 0, 1.0),
    ("v_max_ms", "azami hız", "m/s", 2, 1.0),
    ("e_cap_wh", "batarya kapasitesi", "Wh", 0, 1.0),
    ("slope_max_deg", "azami eğim", "deg", 0, 1.0),
    ("slope_lateral_max_deg", "azami yanal eğim", "deg", 0, 1.0),
    ("h_max_shadow_h", "azami gölge dayanımı", "h", 0, 1.0),
    # The catalogue field is named _pct but holds a FRACTION (0.20). K1 does the
    # scaling so the operator is not shown 0,20 under a percent label, and the
    # result is marked DERIVED so its lineage survives.
    ("soc_min_pct", "minimum batarya rezervi", "%", 0, 100.0),
)

_DERIVED_FIELDS: frozenset[str] = frozenset({"soc_min_pct"})

# (field, direction, Turkish phrase) for each criterion the operator may name.
# K1 resolves the extremum; K4 is never asked to compare two registered values.
_CRITERIA: dict[str, tuple[str, str, str]] = {
    "battery": ("e_cap_wh", "max", "En yüksek batarya kapasitesi"),
    "speed": ("v_max_ms", "max", "En yüksek azami hız"),
    "slope_limit": ("slope_max_deg", "max", "En yüksek azami eğim limiti"),
    "mass": ("mass_kg", "min", "En düşük kütle"),
    "shadow_endurance": ("h_max_shadow_h", "max", "En yüksek gölge dayanımı"),
}

# Closed table, used only to register an alternative rendering of a COUNT
# metric K1 itself produced. Never applied to a measured quantity.
def short_name(name: str) -> str:
    """The catalogue name without its parenthetical qualifier.

    "LPR-1 (Default)" is what the catalogue publishes; "LPR-1" is what a
    sentence contains. Both have to be whitelisted, or the bare form's digit
    survives the mask and blocks an otherwise correct answer.
    """
    head = name.split("(")[0].strip()
    return head or name


def _pick_rovers(
    catalog: Sequence[Mapping[str, Any]], rover_ids: Sequence[str]
) -> list[dict[str, Any]]:
    """The requested rovers in catalogue order, or all of them."""
    if not rover_ids:
        return [dict(entry) for entry in catalog]
    wanted = {str(rid).strip().lower() for rid in rover_ids}
    picked = [
        dict(entry)
        for entry in catalog
        if str(entry.get("id", "")).lower() in wanted
        or short_name(str(entry.get("name", ""))).lower() in wanted
    ]
    # An id the router invented resolves to nothing. Answering about every
    # rover is more useful than answering about none, and each registered value
    # is labelled with the rover it belongs to either way.
    return picked or [dict(entry) for entry in catalog]


def _spec_value(
    entry: Mapping[str, Any], field: str, scale: float
) -> Optional[float]:
    value = entry.get(field)
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value) * scale
    except (TypeError, ValueError):
        return None


def _criterion_fact(
    criterion: str, rovers: Sequence[Mapping[str, Any]]
) -> Optional[GuideFact]:
    """Resolve a named comparison deterministically, here and not in K4."""
    spec = _CRITERIA.get(criterion)
    if spec is None:
        return None
    field, direction, phrase = spec

    scored: list[tuple[float, str]] = []
    for entry in rovers:
        value = _spec_value(entry, field, 1.0)
        if value is None:
            continue
        scored.append((value, short_name(str(entry.get("name") or entry.get("id")))))
    if not scored:
        return None

    best = max(v for v, _ in scored) if direction == "max" else min(v for v, _ in scored)
    winners = [name for value, name in scored if value == best]
    joined = " ve ".join(winners)
    if len(winners) > 1:
        text = (
            f"{phrase} kayıtlı roverlar arasında eşit olarak {joined} için "
            "geçerlidir."
        )
    else:
        text = f"{phrase} kayıtlı roverlar arasında {joined} için geçerlidir."
    return GuideFact(key=f"rover.criterion.{criterion}", text=text)


# -- evidence assembly (K1) -------------------------------------------------

def _fact_keys(topic: str, subject: Optional[str]) -> tuple[str, ...]:
    if subject and subject != "all":
        keys = _SUBJECT_FACTS.get((topic, subject))
        if keys:
            return keys
    return _TOPIC_FACTS.get(topic, ("workflow.overview",))


def guide_evidence(
    params: Mapping[str, Any], catalog: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """The deterministic payload behind one C-GUIDE answer.

    Reads the rover catalogue and the fact table. Executes nothing, plans
    nothing, and touches no mission state.
    """
    validated = GuideParams.model_validate(dict(params))
    topic = validated.topic

    fact_keys = list(_fact_keys(topic, validated.subject))
    rovers: list[dict[str, Any]] = []
    criterion_key: Optional[str] = None

    if topic == "rover":
        rovers = _pick_rovers(catalog, validated.rover_ids)
        if validated.criterion is None:
            # No criterion means no winner. Said outright rather than left for
            # K4 to fill in with a ranking nothing computed.
            fact_keys.append("rover.no_universal_best")
        else:
            criterion_key = validated.criterion

    return {
        "topic": topic,
        "subject": validated.subject,
        "fact_keys": fact_keys,
        "rovers": rovers,
        "criterion": criterion_key,
    }


def guide_facts(payload: Mapping[str, Any]) -> list[GuideFact]:
    """The selected canonical statements, plus any resolved comparison.

    A key that is not in ``GUIDE_FACTS`` yields nothing: the table is the only
    source of product prose, so an unknown key cannot invent one.
    """
    facts = [
        GuideFact(key=key, text=GUIDE_FACTS[key])
        for key in payload.get("fact_keys") or ()
        if key in GUIDE_FACTS
    ]
    criterion = payload.get("criterion")
    if criterion:
        resolved = _criterion_fact(str(criterion), payload.get("rovers") or ())
        if resolved is not None:
            facts.append(resolved)
    return facts


def guide_registry(
    payload: Mapping[str, Any], provenance: Provenance
) -> list[Metric]:
    """Register every rover number the answer is allowed to state."""
    rovers = payload.get("rovers") or []
    if not rovers:
        return []

    metrics: list[Metric] = []
    count = len(rovers)
    word = COUNT_WORDS.get(count)
    metrics.append(
        make_metric(
            key="rover_count",
            label="Kapsanan rover sayısı",
            value=count,
            unit=DIMENSIONLESS,
            provenance=provenance,
            precision=0,
            # An explicit alternative rendering of THIS count, registered by K1
            # for one value -- not a rule that lets any number be spelled out.
            display_alt=[f"{word} rover"] if word else [],
        )
    )

    derived = Provenance(
        source="DERIVED",
        layer=provenance.layer,
        dataset=provenance.dataset,
        note="rover kataloğundaki orandan türetildi",
    )
    for entry in rovers:
        rover_id = str(entry.get("id") or "?")
        name = short_name(str(entry.get("name") or rover_id))
        for field, label, unit, precision, scale in _ROVER_SPECS:
            value = _spec_value(entry, field, scale)
            if value is None:
                continue
            metrics.append(
                make_metric(
                    key=f"{rover_id}.{field}",
                    label=f"{name} — {label}",
                    value=value,
                    unit=unit,
                    provenance=derived if field in _DERIVED_FIELDS else provenance,
                    precision=precision,
                )
            )
    return metrics


def guide_lexicon(payload: Mapping[str, Any]) -> list[str]:
    """Exact strings this answer is authorised to contain.

    Every entry is either a product identifier or a phrase K1 selected a fact
    for. Nothing is added by shape, so authorising "2D" does not authorise a
    stray digit anywhere else in the draft.
    """
    tokens: list[str] = []
    fact_keys = set(payload.get("fact_keys") or ())

    if any(key.startswith("view.") for key in fact_keys):
        tokens.extend(_VIEW_IDENTIFIERS)
    if "priority.not_percentages" in fact_keys:
        tokens.extend(_PERCENT_PHRASES)
    for entry in payload.get("rovers") or ():
        name = str(entry.get("name") or "")
        if name:
            tokens.append(name)
            tokens.append(short_name(name))
        rover_id = str(entry.get("id") or "")
        if rover_id:
            tokens.append(rover_id)

    ordered: list[str] = []
    for token in tokens:
        if token and token not in ordered:
            ordered.append(token)
    return ordered
