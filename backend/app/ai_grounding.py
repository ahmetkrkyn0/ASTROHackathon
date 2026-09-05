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
    # Product identifiers and phrasings K1 authorised for THIS answer. Empty
    # for every analysis capability, so their strictness is unchanged; the
    # entries are exact strings, never patterns, so authorising "2D" does not
    # authorise a bare digit anywhere else.
    tokens.update(token for token in getattr(envelope, "lexicon", ()) or () if token)

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
        #
        # The comma half of the trailing guard applies ONLY when the display
        # ends in a digit. A dimensionless "495" really can be the head of
        # "495,2", so it stays guarded -- but "1490,23 Wh" ends in a unit, and
        # no comma can continue that number. Guarding it anyway meant an
        # ordinary Turkish sentence ("... 3,100 km, ... 1490,23 Wh.") failed to
        # mask its own registered values and was blocked as an unregistered
        # number: a correct answer refused for a punctuation mark. This is a
        # narrower guard, not a looser check -- the digit lookahead, the
        # decimal-point lookahead and the leading guard are unchanged, and the
        # tolerance is still zero.
        #
        # For a digit-terminated display that guard is `(?!,\d)`, not `(?!,)`.
        # Blocking every following comma was the same punctuation bug one step
        # further in: a summary that enumerates counts writes "Kritik adım
        # sayısı 0, yüksek riskli adım sayısı 0", the first 0 is followed by a
        # comma, and it went unmasked while the second one -- ending the
        # sentence -- was masked. One registered value survived out of two
        # identical ones, and the answer was blocked. A comma only continues a
        # number when a digit follows it, so that is the only case still
        # guarded; "495,2" is protected exactly as before.
        trailing = r"(?!\d)(?!,\d)(?!\.\d)" if display[-1].isdigit() else r"(?!\d)(?!\.\d)"
        pattern = re.compile(
            r"(?<![\d,])(?<!\d\.)" + re.escape(display) + _SUFFIX + trailing
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
# "ağırlık" is deliberately absent: the verbalizer prompt itself contains
# "diğer üç ağırlık da değişir" as the CORRECT way to describe a profile, and
# adding the noun here would block the answer that instruction asks for.
_COUNTED_NOUNS = (
    "profil", "hücre", "katman", "kısıt", "adım", "uyarı", "ihlal",
    "kenar", "metrik", "rota", "waypoint",
    # Nouns the planning guide counts. Each has a registered count metric with
    # an explicit display_alt, so the legitimate phrasing survives and an
    # unregistered one does not.
    "rover", "öncelik", "görünüm",
    # Nouns the mission report's verdict counts. "şarj" and "mola" both appear
    # because the recharge count is read either way in Turkish, and "düğüm"
    # arrives with the truncated-execution reason.
    "düğüm", "şarj", "mola",
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


# What a whitelisted identifier looks like by the time a claim rule sees it.
# Rover names are in the K5 whitelist -- that is what makes "LPR-1" sayable at
# all -- so by the time _scan_claims runs, "LPR-1 guvenlidir" has already
# become "<masked> guvenlidir". A rule that matched the catalogue name would
# match nothing; the sentinel IS the known-identifier vocabulary here.
_MASKED = re.escape(_SENTINEL)

# Patterns run over the folded, MASKED text, so a registered value or a
# whitelisted name can never trip one lexically.
#
# A denial of a forbidden claim is what the honesty rules ASK for, so it must
# never be the thing that gets blocked. Turkish marks negation
# morphologically -- the -ma/-me suffix in front of the tense marker -- and
# enumerating verbs missed the commonest form of all: a yes/no question
# ("otonom navigasyon yapıyor mu?") is answered with the progressive negative
# ("yapmıyor"), while the exemptions listed only the aorist ("yapmaz"). That
# blocked 3 of 8 live calls to exactly that question.
#
# Matching the morpheme rather than a verb list is what makes it hold for the
# next denial nobody thought to enumerate. Every entry still requires a real
# negation, and "yok" is anchored so it cannot fire on "yokuş" (uphill),
# which appears in ordinary route prose.
_DENIAL = (
    r"\b\w*m[ıiuü]yor\w*\b"                  # yapmıyor, sunmuyor, desteklemiyor
    r"|\b\w*m[ae]z\b"                        # yapmaz, içermez, hedeflemez
    r"|\b\w*m[ae]d[ıi]\w*\b"                 # yapmadı, edilmedi
    r"|\b\w*m[ae]y[ae]cak\w*\b"              # yapmayacak, olmayacak
    r"|\bdeğil\w*"
    r"|\byok\b|\bhayır\b"
    r"|\bkapsam\s*dışı"
    r"|\btasarlanmamış\w*"
    r"|\b(?:does|do|is|are)\s+not\b|\bnot\s+an?\b"
)


FORBIDDEN_CLAIMS: tuple[ClaimRule, ...] = (
    ClaimRule(
        code="N-6",
        trigger=_p(
            r"\b(otonom|özerk)\s+(navigasyon|sürüş|seyrüsefer|sistem)"
            r"|\bkendi\s+başına\s+(sür|git|karar)"
            r"|\b(gerçek\s*zamanlı|anlık|yerel)\s+engel\s*kaçın"
            r"|\bautonomous\s+(navigation|driving)\b"
        ),
        # Every entry the old list held is subsumed by _DENIAL, which also
        # covers the progressive negative the old list missed.
        exempt=_p(_DENIAL),
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
            # The rover as the SUBJECT of a safety claim. Harmless until
            # C-GUIDE, which answers "which rover" and "LPR-1 vs NASA VIPER" --
            # so "Bu rover guvenlidir" became a sentence the assistant could
            # actually produce, and nothing stopped it.
            #
            # Two narrowings keep this from firing on honest prose:
            #
            # (?![kğ]) rather than (?!k). The existing lookahead excludes the
            # noun "güvenlik" but not its possessive "güvenliği", so without
            # the ğ this would fire on "rover güvenliğini sertifikalandırmaz"
            # -- a sentence that DENIES the claim.
            #
            # The predicate must carry a copula. The sentinel's subject is
            # unknown by construction, so only an assertion counts:
            # "<masked> güvenlidir" is a claim, "<masked> güvenli sınırın
            # altında" is a measurement. The same requirement is applied to
            # the rover branch, which would otherwise fire on "Rover için
            # güvenli sınır aşılmadı."
            r"|\brover\w*\s+(?:\w+\s+){0,2}güvenli(?![kğ])(?:dir|ydi|ymiş|dirler)\b"
            rf"|{_MASKED}\s+(?:\w+\s+){{0,2}}güvenli(?![kğ])(?:dir|ydi|ymiş|dirler)\b"
            r"|\bgüvenli(?![kğ])\s+(?:bir\s+)?rover\w*"
            # \w* rather than \b: "risksizdir" is the same claim as
            # "risksiz", and Turkish attaches the copula to the stem.
            r"|\b(risksiz|tehlikesiz|zarar\s+görmez)\w*\b"
            r"|\b(this\s+)?(route|path)\s+is\s+safe\b|\bprotects\s+the\s+rover\b"
        ),
        exempt=_p(
            r"\bgüvenlik\s+(marj|pay|faktör|katsayı|sınır)"
            r"|\bkısıt\w*\s+(ihlal|aşıl|karşıla)"
            r"|\btanımlı\s+kısıt"
            r"|\b(değil\w*|garanti\s+edilemez|anlamına\s+gelmez)"
            # A denial in the same clause. The copula requirement above already
            # lets the cautious phrasings through on its own; these cover a
            # hedge that shares a clause with the assertion, because a comma
            # does not split one -- _CLAUSE_SPLIT is [.!?;:\n].
            r"|\b(doğrulanmam\w*|kanıtlamaz|kanıtlanmam\w*|göstermez)"
            r"|\bsertifika\w*(maz|mam\w*)"
        ),
    ),
    ClaimRule(
        code="N-9",
        trigger=_p(
            r"\b(ilk|tek|biricik|benzersiz|eşsiz)\s+(?:\w+\s+)?"
            r"(çözüm|sistem|araç|platform|yaklaşım)\w*\b"
            r"|\bdünyada\s+(ilk|tek)\b"
            r"|\ben\s+iyi\s+(çözüm|sistem|araç|rota)\w*\b"
            r"|\bworld'?s\s+first\b|\bstate[- ]of[- ]the[- ]art\b"
        ),
        exempt=_p(
            # The noun exemptions are specific to this rule; the denial
            # vocabulary is shared.
            r"\bilk\s+(adım|kesit|sürüm|bakışta|olarak|etap)"
            r"|\btek\s+(değişken\w*|başına|yön\w*|kaynak)"
            r"|" + _DENIAL
        ),
    ),
    ClaimRule(
        code="N-10",
        trigger=_p(
            r"\b(uçuş|görev)\s+yazılım"
            r"|\bkart\s*üstü\w*\b|\bgömülü\s+(yazılım|sistem)\w*\b"
            r"|\bsertifikalı\w*\b|\buçuşa\s+hazır\w*\b"
            r"|\brover\s+üzerinde\s+çalış"
            r"|\bflight[- ]software\b|\bspace[- ]qualified\b"
        ),
        exempt=_p(_DENIAL),
    ),
    ClaimRule(
        code="N-11",
        trigger=_p(
            # "kesinti" and its family mean interruption, not certainty, and
            # "En uzun kesintisiz gölge" is one of K1's own metric labels -- so
            # this rule used to block the deterministic fallback it exists to
            # protect. Excluding that stem removes a false positive; every
            # actual certainty claim ("kesin", "kesindir", "kesinlikle") still
            # fires.
            r"\bkesinlikle\b|\bkesin(?!lik\b)(?!ti)\w*\b"
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
# A guide answer can be entirely prose, in which case "only the registered
# values" would describe an empty list and read as a lie in the one case it
# fires.
_FALLBACK_HEAD_FACTS = (
    "Yanıtı doğrulayamadım, bu yüzden yalnızca kayıtlı bilgileri gösteriyorum:"
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
    facts = list(getattr(envelope, "facts", ()) or ())
    head = _FALLBACK_HEAD if envelope.numeric_registry else _FALLBACK_HEAD_FACTS
    lines: list[str] = [head if (envelope.numeric_registry or facts) else _FALLBACK_HEAD]
    # The verdict leads, ahead of the head line's list. A blocked draft is
    # exactly when the operator most needs the disposition, and it is a
    # deterministic sentence with no quantity in it.
    verdict = getattr(envelope, "verdict", None)
    if verdict is not None:
        lines.insert(0, verdict.sentence)
    # K1's own canonical sentences. Safe by construction for the same reason
    # the displays are: the operator is shown exactly what the registry holds,
    # with nothing generated in between.
    for fact in facts:
        lines.append(f"- {fact.text}")
    for metric in envelope.numeric_registry:
        lines.append(f"- {metric.label}: {metric.display} ({metric.provenance.source})")
    for warning in envelope.warnings:
        lines.append(f"- {warning.message}")
    lines.append(_FALLBACK_TAIL)
    return "\n".join(lines)
