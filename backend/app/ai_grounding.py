"""K5 -- deterministic validation of the verbalizer's draft.

This module owns **no number parser**, and that is the design. Instead of
decoding numerals out of Turkish prose -- where every decode path becomes an
attack surface and `1.490` has no safe answer -- K5 works by subtraction:

    1. mask every whitelisted identifier out of the draft;
    2. mask every registered display string out of the draft;
    3. assert that no digit survives.

K5 therefore never learns what a numeral means. It only notices a digit that
nothing accounted for, which is a strictly weaker requirement and robust by
construction. K1's ``format_display`` guarantees a canonical rendering with no
thousands separator, so step 2 is an exact string match and the tolerance here
is **zero**. Do not add an epsilon: rounding already happened, once, in K1.

The digit scan alone is not sufficient -- a model can spell a number in words
-- so a bounded bigram check covers numeral words immediately before the nouns
K1 actually counts. That set is closed on purpose; this is not a Turkish NLP
parser and must not grow into one.

On violation K5 **blocks**. It never edits the draft: a silent correction is a
hallucination that became invisible.

Contract: docs/ai/LunaPath_AI_Chatbot_Scope_v0.3.md sections 12 and 15.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

from .ai_analysis import AnalysisEnvelope

# A private-use codepoint cannot occur in real prose, so it is safe as the
# marker left behind by masking.
_SENTINEL = ""


@dataclass(frozen=True)
class GroundingViolation:
    code: str
    excerpt: str


@dataclass(frozen=True)
class GroundingVerdict:
    ok: bool
    violations: tuple[GroundingViolation, ...] = ()
    masked_text: str = ""


# Claim rules are identified by their contract number; everything else is
# already a category. Named here so the diagnostic can tell the two apart
# without a second list to keep in step.
_CLAIM_CODES = frozenset({"N-6", "N-7", "N-8", "N-9", "N-10", "N-11"})


def diagnostic(verdict: GroundingVerdict) -> tuple[dict[str, str], ...]:
    """Why a draft was refused, in a form that is safe to record.

    A blocked draft is discarded, which is right -- but it left nothing behind
    saying what tripped, so a rejection could not be told apart from a false
    positive after the fact. This carries the reason and nothing else.

    Codes only. ``GroundingViolation.excerpt`` is a fragment of the rejected
    draft and is deliberately dropped here: it is what makes a verdict useful
    to a developer reading it in the moment, and exactly what must not be
    logged, persisted or returned. A category and, for a claim rule, its
    contract number are enough to reproduce the decision from the registry.
    """
    out: list[dict[str, str]] = []
    for violation in verdict.violations:
        if violation.code in _CLAIM_CODES:
            out.append({"code": "FORBIDDEN_CLAIM", "rule": violation.code})
        else:
            out.append({"code": violation.code})
    return tuple(out)


# ── normalisation ────────────────────────────────────────────────────────────

_SPACEY = dict.fromkeys(map(ord, "    "), " ")
_DASHY = dict.fromkeys(map(ord, "−‐‑‒–—―"), "-")


def normalize(text: str) -> str:
    """NFKC plus the space/dash folds, applied identically everywhere.

    Deliberately does NOT touch digits, separators or case: those are the
    things being validated.
    """
    out = unicodedata.normalize("NFKC", text)
    out = out.translate(_SPACEY).translate(_DASHY)
    return re.sub(r"[ \t]+", " ", out)


def tr_fold(text: str) -> str:
    """Case-fold the Turkish way.

    ``str.lower()`` maps ``I`` to ``i`` and ``İ`` to ``i`` + combining dot,
    so a shouted ``KESİNLİKLE`` would slip past every pattern below.
    """
    return text.replace("İ", "i").replace("I", "ı").lower()


# ── whitelist ────────────────────────────────────────────────────────────────

# Deliberately tiny and digit-free. Unrelated spec identifiers are NOT here:
# a first-cut answer does not need them, and every added token is a hole.
_STATIC_TOKENS: frozenset[str] = frozenset(
    {"C-SUMMARY", "C-POINT", "C-COMPARE", "LunaPath"}
)


def whitelist_tokens(
    envelope: AnalysisEnvelope,
    rover_names: Optional[Iterable[str]] = None,
    profile_names: Optional[Iterable[str]] = None,
) -> frozenset[str]:
    """Identifiers that may legitimately contain a digit.

    Bounded by construction: every member is either a string the backend
    produced for *this* request, or a member of the tiny static table above.
    No shape heuristic, no "digits inside words don't count" escape. Anything
    outside the set fails closed -- which is why a date the model invented is
    blocked while this envelope's own version string is not.
    """
    tokens: set[str] = set(_STATIC_TOKENS)
    tokens.update(name for name in (rover_names or ()) if name)
    tokens.update(name for name in (profile_names or ()) if name)

    if envelope.backend_version:
        tokens.add(envelope.backend_version)
    for provenance in envelope.provenance_summary:
        for value in (provenance.dataset, provenance.version, provenance.layer):
            if value:
                tokens.add(value)
    for metric in envelope.numeric_registry:
        for value in (
            metric.provenance.dataset,
            metric.provenance.version,
            metric.provenance.layer,
        ):
            if value:
                tokens.add(value)

    return frozenset(normalize(token) for token in tokens)


# ── masking ──────────────────────────────────────────────────────────────────

# Anchored to line start and requiring trailing space, so it cannot be abused
# mid-sentence. This is the entire handling of list numbering.
_LIST_MARKER = re.compile(r"(?m)^[ \t]*(?:[-–—*•]|\(?\d{1,3}[.)])[ \t]+")

# Letters only -- never digits -- so a Turkish suffix on a value or a name is
# consumed without widening the numeric surface.
_SUFFIX = r"(?:['’]?[a-zçğıöşü]{1,12})?"


def _mask_tokens(text: str, tokens: Sequence[str]) -> str:
    for token in sorted(tokens, key=len, reverse=True):
        if not token:
            continue
        pattern = re.compile(
            r"(?<![\w\-])" + re.escape(token) + _SUFFIX + r"(?![\w])"
        )
        text = pattern.sub(_SENTINEL, text)
    return text


def _mask_displays(text: str, displays: Sequence[str]) -> str:
    for display in sorted(displays, key=len, reverse=True):
        if not display:
            continue
        # The lookarounds are load-bearing. Without the trailing guard a
        # registered 1490,23 would mask the head of 1490,236; without the
        # leading one it would mask the tail of 31490,23. They must still let
        # a sentence-ending period through, so a bare "." only blocks the
        # match when a digit follows it.
        pattern = re.compile(
            r"(?<![\d,])(?<!\d\.)"
            + re.escape(display)
            + _SUFFIX
            + r"(?![\d,])(?!\.\d)"
        )
        text = pattern.sub(_SENTINEL, text)
    return text


def _mask_aliases(text: str, aliases: Sequence[str]) -> str:
    """Mask the lexical phrases K1 explicitly registered for a metric.

    Case-insensitive, unlike the canonical displays: an alias is words, and
    the verbalizer will capitalise it at the start of a sentence. Canonical
    displays stay case-sensitive so a unit cannot be loosened (``Wh`` is not
    ``wh``).
    """
    for alias in sorted(aliases, key=len, reverse=True):
        if not alias:
            continue
        pattern = re.compile(
            r"(?<![\w-])" + re.escape(alias) + _SUFFIX + r"(?![\w-])",
            re.IGNORECASE,
        )
        text = pattern.sub(_SENTINEL, text)
    return text


# ── leftover scans ───────────────────────────────────────────────────────────

_LEFTOVER_DIGIT = re.compile(r"\d")
_LEFTOVER_PERCENT = re.compile(r"%|\byüzde\b", re.IGNORECASE)
_LEFTOVER_UNCERTAINTY = re.compile(r"±")

# Excludes "bir": it is Turkish's indefinite article and would fire on
# ordinary prose ("bir rota planlandı"). The residual gap is a count of one --
# the lowest-stakes number in the system -- and the verbalizer prompt requires
# registered display strings regardless.
_NUMERAL_WORDS = (
    "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz", "on",
    "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan",
    # "yüz" is guarded against "yüzey" (surface), which is ordinary prose in
    # this domain and would otherwise read as the numeral "hundred".
    "yüz(?!ey)", "bin", "milyon", "yarım", "çeyrek", "buçuk",
    "birinci", "ikinci", "üçüncü", "dördüncü", "beşinci",
)

# Closed on purpose: exactly the nouns K1 emits count metrics for. Adding a
# count metric and adding its noun is one change, in one file.
_COUNTED_NOUNS = (
    "profil", "hücre", "katman", "kısıt", "adım", "uyarı", "ihlal",
    "kenar", "metrik", "rota", "waypoint",
)

# Units a spelled-out quantity would be followed by. Closed vocabulary: the
# canonical unit tokens K1 emits, plus the Turkish words a verbalizer would
# reach for. Nothing here decodes a value; this is not a unit parser.
_UNIT_WORDS = (
    "wh", "kwh", "km", "m", "h", "deg", "degc", "weighted_metres",
    "watt-saat", "kilovat-saat", "kilovat", "watt",
    "saat", "dakika", "metre", "kilometre", "derece", "santigrat",
)

# A numeral word next to a quantity noun OR a unit. The scan runs on the
# MASKED text, so a unit belonging to a registered display string has already
# been deleted -- only an unaccounted-for unit can pair with a numeral, which
# is what keeps the false-positive surface narrow.
_NUMERAL_BIGRAM = re.compile(
    r"\b(?:" + "|".join(_NUMERAL_WORDS) + r")\w*\s+(?:\w+\s+){0,1}(?:"
    + "|".join(_COUNTED_NOUNS + _UNIT_WORDS)
    + r")\w*",
)

# A compound numeral is a number even with nothing after it: "bin dort yuz
# doksan" needs no unit to be a quantity. Two high-confidence numeral tokens
# close together is the signal. One alone is not -- a single word is ordinary
# prose often enough that firing on it would block normal answers.
_NUMERAL_RUN = re.compile(
    r"\b(?:" + "|".join(_NUMERAL_WORDS) + r")\w*"
    r"(?:\s+\w+){0,1}\s+"
    r"(?:" + "|".join(_NUMERAL_WORDS) + r")\w*\b",
)


def _excerpt(text: str, start: int, end: int) -> str:
    return text[max(0, start - 40) : min(len(text), end + 40)].strip()


# ── forbidden claims ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ClaimRule:
    code: str
    trigger: re.Pattern
    exempt: Optional[re.Pattern] = None


def _p(pattern: str) -> re.Pattern:
    return re.compile(pattern)


# Patterns run over the folded, MASKED text, so a registered value or a
# whitelisted name can never trip one lexically.
FORBIDDEN_CLAIMS: tuple[ClaimRule, ...] = (
    ClaimRule(
        code="N-6",
        trigger=_p(
            r"\b(otonom|özerk)\s+(navigasyon|sürüş|seyrüsefer|sistem)"
            r"|\bkendi\s+başına\s+(sür|git|karar)"
            r"|\b(gerçek\s*zamanlı|anlık|yerel)\s+engel\s*kaçın"
            r"|\bautonomous\s+(navigation|driving)\b"
        ),
        exempt=_p(
            r"\b(değildir|değil|yapmaz|sunmaz|içermez|kapsam\s*dışı|tasarlanmamış)"
            r"|\bnot\s+an?\b"
        ),
    ),
    ClaimRule(
        code="N-7",
        trigger=_p(
            r"\bgerçek\s+nasa\s+veri"
            r"|\bnasa\s+ölçüm\w*\s+ile\s+doğrulan"
            r"|\breal\s+nasa\s+data\b"
        ),
        exempt=_p(
            r"\b(sentetik|türetil\w*|modellen\w*|demo)\b"
            r"|\b(measured|derived|model|synthetic)\b"
        ),
    ),
    ClaimRule(
        code="N-8",
        trigger=_p(
            # guvenli(?!k) is the whole trick: "güvenlik marjı" is a different
            # word and needs no enumeration to stay legal.
            r"\brota\w*\s+(?:\w+\s+){0,2}güvenli(?!k)"
            r"|\bgüvenli(?!k)\s+(?:bir\s+)?(rota|güzergah|yol)\b"
            r"|\brover['’]?\w*\s*(?:\w+\s+)?(korur|koruyor|koruyacak)"
            r"|\b(risksiz|tehlikesiz|zarar\s+görmez)\b"
            r"|\b(this\s+)?(route|path)\s+is\s+safe\b|\bprotects\s+the\s+rover\b"
        ),
        exempt=_p(
            r"\bgüvenlik\s+(marj|pay|faktör|katsayı|sınır)"
            r"|\bkısıt\w*\s+(ihlal|aşıl|karşıla)"
            r"|\btanımlı\s+kısıt"
            r"|\b(değil\w*|garanti\s+edilemez|anlamına\s+gelmez)"
        ),
    ),
    ClaimRule(
        code="N-9",
        trigger=_p(
            r"\b(ilk|tek|biricik|benzersiz|eşsiz)\s+(?:\w+\s+)?"
            r"(çözüm|sistem|araç|platform|yaklaşım)\b"
            r"|\bdünyada\s+(ilk|tek)\b"
            r"|\ben\s+iyi\s+(çözüm|sistem|araç|rota)\b"
            r"|\bworld'?s\s+first\b|\bstate[- ]of[- ]the[- ]art\b"
        ),
        exempt=_p(
            r"\bilk\s+(adım|kesit|sürüm|bakışta|olarak|etap)"
            r"|\btek\s+(değişken\w*|başına|yön\w*|kaynak)"
            r"|\bdeğil\w*"
        ),
    ),
    ClaimRule(
        code="N-10",
        trigger=_p(
            r"\b(uçuş|görev)\s+yazılım"
            r"|\bkart\s*üstü\b|\bgömülü\s+(yazılım|sistem)\b"
            r"|\bsertifikalı\b|\buçuşa\s+hazır\b"
            r"|\brover\s+üzerinde\s+çalış"
            r"|\bflight[- ]software\b|\bspace[- ]qualified\b"
        ),
        exempt=_p(r"\b(değildir|değil|tasarlanmamış\w*|hedeflemez)\b"),
    ),
    ClaimRule(
        code="N-11",
        trigger=_p(
            r"\bkesinlikle\b|\bkesin(?!lik\b)\w*\b"
            r"|\bmutlaka\b|\bşüphesiz\b"
            r"|\bgaranti(?!\s+edilemez)\w*\b"
            r"|\byüzde\s+yüz\b"
            r"|\b(guarantee[sd]?|certainly|definitely)\b"
        ),
        exempt=_p(
            r"\bgaranti\s+edil(emez|mez)\b|\bgaranti\s+değil"
            r"|\bkesin\s+değil|\bkesinlik\s+pay"
        ),
    ),
)

_CLAUSE_SPLIT = re.compile(r"[.!?;:\n]")


def _scan_claims(masked: str) -> list[GroundingViolation]:
    violations: list[GroundingViolation] = []
    for clause in _CLAUSE_SPLIT.split(masked):
        folded = tr_fold(clause)
        if not folded.strip():
            continue
        for rule in FORBIDDEN_CLAIMS:
            if not rule.trigger.search(folded):
                continue
            if rule.exempt is not None and rule.exempt.search(folded):
                continue
            violations.append(
                GroundingViolation(code=rule.code, excerpt=clause.strip()[:120])
            )
    return violations


# ── the validator ────────────────────────────────────────────────────────────

def validate_draft(
    draft: str,
    envelope: AnalysisEnvelope,
    whitelist: frozenset[str],
) -> GroundingVerdict:
    """Accept the draft only if every number in it was registered by K1."""
    text = normalize(draft)
    text = _LIST_MARKER.sub("", text)
    text = _mask_tokens(text, tuple(whitelist))
    text = _mask_displays(
        text, tuple(metric.display for metric in envelope.numeric_registry)
    )
    # Aliases are registered by K1 and masked here, so an approved phrase such
    # as "dort profil" survives while an unregistered spelling does not.
    aliases: list[str] = []
    for metric in envelope.numeric_registry:
        aliases.extend(getattr(metric, "display_alt", ()) or ())
    if aliases:
        text = _mask_aliases(text, tuple(aliases))

    violations: list[GroundingViolation] = []

    match = _LEFTOVER_DIGIT.search(text)
    if match:
        violations.append(
            GroundingViolation(
                "UNREGISTERED_NUMBER", _excerpt(text, match.start(), match.end())
            )
        )
    match = _LEFTOVER_PERCENT.search(text)
    if match:
        violations.append(
            GroundingViolation(
                "UNREGISTERED_PERCENT", _excerpt(text, match.start(), match.end())
            )
        )
    match = _LEFTOVER_UNCERTAINTY.search(text)
    if match:
        violations.append(
            GroundingViolation(
                "UNREGISTERED_UNCERTAINTY", _excerpt(text, match.start(), match.end())
            )
        )
    folded = tr_fold(text)
    match = _NUMERAL_BIGRAM.search(folded) or _NUMERAL_RUN.search(folded)
    if match:
        violations.append(
            GroundingViolation(
                "UNREGISTERED_NUMBER_WORD", _excerpt(text, match.start(), match.end())
            )
        )

    violations.extend(_scan_claims(text))

    return GroundingVerdict(
        ok=not violations, violations=tuple(violations), masked_text=text
    )


# ── fallback ─────────────────────────────────────────────────────────────────

_FALLBACK_HEAD = (
    "Yanıtı doğrulayamadım, bu yüzden yalnızca kayıtlı değerleri gösteriyorum:"
)
_FALLBACK_TAIL = (
    "Bu özet, doğrulanmış analiz kayıtlarından üretildi; ek bir hesap yapılmadı."
)


def deterministic_fallback(envelope: AnalysisEnvelope) -> str:
    """What the operator sees when K5 blocks the draft.

    Built only from registered display strings and mandatory warnings, so it
    passes this module's own check by construction -- there is a test asserting
    exactly that. Performs no arithmetic of any kind.
    """
    lines: list[str] = [_FALLBACK_HEAD]
    for metric in envelope.numeric_registry:
        lines.append(f"- {metric.label}: {metric.display} ({metric.provenance.source})")
    for warning in envelope.warnings:
        lines.append(f"- {warning.message}")
    lines.append(_FALLBACK_TAIL)
    return "\n".join(lines)
