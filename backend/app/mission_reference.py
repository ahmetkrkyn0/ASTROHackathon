"""Verified real-mission reference data.

Every value here is a published, dated figure -- not a model output. This
is the external reality check LunaPath's own maturity assessment
(docs/research/09_olgunluk_kiyaslama.md) flags as missing. Sources are
cited inline; if a number changes because a rover keeps driving, add a new
milestone with a new citation -- never silently edit an existing one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DistanceMilestone:
    mission: str
    on_date: date
    total_distance_m: float
    source: str


# Yutu-2 (Chang'e-4): landed 2019-01-03, still operating on the lunar far
# side as of these citations -- the longest-lived lunar rover to date.
YUTU_2_MILESTONES: tuple[DistanceMilestone, ...] = (
    DistanceMilestone(
        mission="Yutu-2 (Chang'e-4)",
        on_date=date(2024, 9, 17),
        total_distance_m=1613.0,
        source=(
            "space.com, 'China's Yutu 2 rover still going strong after "
            "nearly 6 years on the far side of the moon' (17 Sep 2024)"
        ),
    ),
    DistanceMilestone(
        mission="Yutu-2 (Chang'e-4)",
        on_date=date(2025, 3, 4),
        total_distance_m=1630.0,
        source=(
            "friendsofnasa.org, 'China's Yutu-2 Moon Rover: New Far Side "
            "Image' (4 Mar 2025)"
        ),
    ),
)

# Pragyan (Chandrayaan-3): landed 2023-08-23 near the lunar south pole
# (69.4 S), completed its traverse and was parked into sleep mode ahead of
# the first lunar night on 2023-09-02. It never woke back up. A single
# short, largely continuous active window -- unlike Yutu-2's multi-year,
# multi-lunar-cycle record, duty-cycle ambiguity here is small.
PRAGYAN_MISSION: dict[str, object] = {
    "mission": "Pragyan (Chandrayaan-3)",
    "landing_date": date(2023, 8, 23),
    "sleep_date": date(2023, 9, 2),
    "total_distance_m": 101.4,
    "source": (
        "ISRO traverse-path image, reported via gulfnews.com, "
        "'Chandrayaan-3's Pragyan Rover completed its assignments, safely "
        "parked, put to sleep mode: ISRO' (2 Sep 2023) -- total traverse "
        "distance 101.4 m"
    ),
}


def yutu2_average_rate_m_per_day() -> float:
    """Average advance rate (m / calendar day) between the two milestones.

    Includes lunar-night dormancy: LunaPath does not model duty cycles
    (see docs/research/08_global_local_rotalama_yuku.md 3.3). This is a
    LOWER bound on any "actively driving" rate, not an estimate of it.
    """
    first, second = YUTU_2_MILESTONES[0], YUTU_2_MILESTONES[-1]
    delta_days = (second.on_date - first.on_date).days
    delta_m = second.total_distance_m - first.total_distance_m
    return delta_m / delta_days


def pragyan_active_days() -> int:
    landing = PRAGYAN_MISSION["landing_date"]
    sleep = PRAGYAN_MISSION["sleep_date"]
    return (sleep - landing).days  # type: ignore[operator]


def pragyan_average_rate_m_per_day() -> float:
    return float(PRAGYAN_MISSION["total_distance_m"]) / pragyan_active_days()


def reference_summary() -> dict[str, object]:
    """JSON-ready view of everything this module holds, citations included.

    Nothing outside this module's own tests read any of it -- not the API,
    not a script -- so the one component whose entire purpose is to be the
    external reality check was unreachable by anything doing the comparing.
    ``GET /api/reference-missions`` is that reader. (Round 4 review, L-9.)

    Every rate here includes dormancy: LunaPath does not model duty cycles,
    so these are LOWER bounds on an actively-driving rate, not estimates of
    one. The field names say so.
    """
    return {
        "note": (
            "Published mission figures, not model output. Rates include "
            "lunar-night dormancy and are lower bounds on driving rate."
        ),
        "missions": [
            {
                "mission": YUTU_2_MILESTONES[-1].mission,
                "total_distance_m": YUTU_2_MILESTONES[-1].total_distance_m,
                "as_of": YUTU_2_MILESTONES[-1].on_date.isoformat(),
                "lower_bound_rate_m_per_calendar_day": round(
                    yutu2_average_rate_m_per_day(), 4
                ),
                "milestones": [
                    {
                        "on_date": m.on_date.isoformat(),
                        "total_distance_m": m.total_distance_m,
                        "source": m.source,
                    }
                    for m in YUTU_2_MILESTONES
                ],
            },
            {
                "mission": PRAGYAN_MISSION["mission"],
                "total_distance_m": PRAGYAN_MISSION["total_distance_m"],
                "as_of": PRAGYAN_MISSION["sleep_date"].isoformat(),  # type: ignore[union-attr]
                "active_days": pragyan_active_days(),
                "lower_bound_rate_m_per_calendar_day": round(
                    pragyan_average_rate_m_per_day(), 4
                ),
                "milestones": [
                    {
                        "on_date": PRAGYAN_MISSION["sleep_date"].isoformat(),  # type: ignore[union-attr]
                        "total_distance_m": PRAGYAN_MISSION["total_distance_m"],
                        "source": PRAGYAN_MISSION["source"],
                    }
                ],
            },
        ],
    }
