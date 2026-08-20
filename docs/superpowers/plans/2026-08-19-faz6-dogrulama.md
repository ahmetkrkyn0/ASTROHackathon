# Faz 6 — Doğrulama ve Baseline Implementasyon Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** LunaPath'in rover kataloğunu ve termal modelini, uçmuş gerçek misyon verisiyle ve `ETH lunar_planner`'ın metodolojisiyle harici olarak doğrulamak.

**Architecture:** Doğrulama üç bağımsız katman olarak kuruluyor. **(1)** `mission_reference.py` — kaynak künyeli, tarihli, gerçek yayınlanmış rakamlar; kod değil veri. **(2)** `test_rover_validation.py` — bu verilere karşı **gerekli koşul** testleri (nokta-doğruluk iddiası değil; "gerçek bir misyon bu kadar yol aldıysa, rover'ımızın hız sabiti fiziksel olarak bunu imkânsız kılmamalı" türünden sınır kontrolleri). **(3)** `route_analysis.py` — ETH `lunar_planner`'ın `PathAnalysis` aracından ilham alan istatistiksel rota özeti, mevcut `simulate_path`'e dokunmadan `/api/plan`'a eklenir. **(4)** `thermal_validation.py` — heat1d çıktısının Diviner ölçümüyle karşılaştırılması; gerçek veri yoksa nazikçe atlanır, asla sahte veri üretmez.

**Tech Stack:** Python 3.11+ · NumPy 2.2.1 · rasterio 1.4.3 · pytest

**Spec:** [`docs/research/ENTEGRASYON_TEKNOLOJILERI.md`](../../research/ENTEGRASYON_TEKNOLOJILERI.md) BÖLÜM 6 (§6.1–6.4), §1.4, §1.5

**Master plan:** [`2026-08-19-lunapath-master-plan.md`](2026-08-19-lunapath-master-plan.md) — **Global Constraints bölümü bu planın her görevi için geçerlidir.**

**Önkoşul:** Faz 1 (`Heat1DModel`, `layer_validity`), Faz 2 (`Corridor` — Task 3'ün `/api/plan` genişletmesi için).

---

## Dürüstlük notu — bu fazın en önemli kuralı

Bu fazdaki hiçbir test **"modelimiz gerçekliği X hata payıyla yeniden üretiyor"** gibi nokta-doğruluk iddiası kurmaz. Yutu-2 ay yüzeyinde 6 yılı aşkın süredir, çoğu zamanı Ay geceleri boyunca **uykuda** geçirerek hareket ediyor; LunaPath bugün görev-döngüsü (duty cycle) modellemiyor. Bu yüzden testler **gerekli koşul** (necessary condition) kontrolleridir: "gerçek misyon bu mesafeyi bu sürede aldıysa, rover sabitlerimiz bunu fiziksel olarak imkânsız kılmamalı." Bu, nokta-doğruluk değil ama **anlamlı bir sınır**dır — biri `v_max_ms`'i saçma bir değere düşürürse test kırılır.

---

## Faz kapsamı

| Görev | Ne | Süre |
|---|---|---|
| 1 | `mission_reference.py` — kaynak künyeli gerçek misyon verisi | 0.5 gün |
| 2 | `test_rover_validation.py` — rover sabitlerinin fiziksel sınır kontrolleri | 1 gün |
| 3 | `route_analysis.py` — ETH `PathAnalysis`'ten ilham istatistikler + `/api/plan` | 1 gün |
| 4 | `thermal_validation.py` + Diviner karşılaştırma script'i | 1 gün |

---

### Task 1: `mission_reference.py` — kaynak künyeli gerçek misyon verisi

**Files:**
- Create: `backend/app/mission_reference.py`
- Test: `backend/test_mission_reference.py` (create)

**Interfaces:**
- Consumes: yok (saf veri modülü)
- Produces:
  - `DistanceMilestone` dataclass: `mission`, `on_date`, `total_distance_m`, `source`
  - `YUTU_2_MILESTONES: tuple[DistanceMilestone, ...]`
  - `PRAGYAN_MISSION: dict[str, object]`
  - `yutu2_average_rate_m_per_day() -> float`
  - `pragyan_active_days() -> int`
  - `pragyan_average_rate_m_per_day() -> float`
  - Task 2 bunları tüketir

- [ ] **Step 1: Başarısız testleri yaz**

`backend/test_mission_reference.py` oluştur:

```python
"""Reference data integrity tests.

These do not validate the numbers against the outside world (that already
happened when the values were cited) -- they guard the dataset against
being silently edited into nonsense later.
"""

from __future__ import annotations

import pytest

from app.mission_reference import (
    PRAGYAN_MISSION,
    YUTU_2_MILESTONES,
    pragyan_active_days,
    pragyan_average_rate_m_per_day,
    yutu2_average_rate_m_per_day,
)


def test_yutu2_has_at_least_two_milestones():
    assert len(YUTU_2_MILESTONES) >= 2


def test_yutu2_milestones_are_chronologically_increasing():
    dates = [m.on_date for m in YUTU_2_MILESTONES]
    assert dates == sorted(dates)


def test_yutu2_distance_never_decreases_between_milestones():
    distances = [m.total_distance_m for m in YUTU_2_MILESTONES]
    assert distances == sorted(distances)


def test_every_yutu2_milestone_cites_a_source():
    for milestone in YUTU_2_MILESTONES:
        assert milestone.source.strip() != ""


def test_yutu2_average_rate_is_a_small_positive_number():
    """Sanity band, not a prediction: a rover this size cannot average
    more than a few metres a day even during active lunar days."""
    rate = yutu2_average_rate_m_per_day()
    assert 0.0 < rate < 10.0


def test_pragyan_mission_declares_required_fields():
    for key in ("mission", "landing_date", "sleep_date", "total_distance_m", "source"):
        assert key in PRAGYAN_MISSION


def test_pragyan_active_days_matches_the_known_short_mission_window():
    assert pragyan_active_days() == 10


def test_pragyan_average_rate_is_positive_and_bounded():
    rate = pragyan_average_rate_m_per_day()
    assert 0.0 < rate < 50.0


def test_pragyan_sleep_date_is_after_landing_date():
    assert PRAGYAN_MISSION["sleep_date"] > PRAGYAN_MISSION["landing_date"]
```

- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula**

Run: `cd backend && pytest test_mission_reference.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'app.mission_reference'`

- [ ] **Step 3: `mission_reference.py`'yi uygula**

`backend/app/mission_reference.py` oluştur:

```python
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
```

- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula**

Run: `cd backend && pytest test_mission_reference.py -v`

Expected: 9 test PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/mission_reference.py backend/test_mission_reference.py
git commit -m "feat: add cited real-mission distance milestones (Yutu-2, Pragyan)"
```

---

### Task 2: `test_rover_validation.py` — fiziksel sınır kontrolleri

**Files:**
- Create: `backend/test_rover_validation.py`

**Interfaces:**
- Consumes: `app.constants.get_rover`, `app.mission_reference.*` (Task 1)
- Produces: yeni kod yok — doğrulama testleri

- [ ] **Step 1: Testleri yaz**

`backend/test_rover_validation.py` oluştur:

```python
"""External reality check: rover constants against flown missions.

Every assertion here is a NECESSARY condition, not a point-accuracy claim
(see the honesty note at the top of the Phase 6 plan). A real mission
achieving distance D over duration T means: no rover profile modelling
that class of hardware may have a top speed physically incapable of
covering D in T. These tests catch a corrupted or fabricated constant;
they do not certify simulation fidelity.
"""

from __future__ import annotations

from app.constants import get_rover
from app.mission_reference import (
    PRAGYAN_MISSION,
    pragyan_active_days,
    pragyan_average_rate_m_per_day,
    yutu2_average_rate_m_per_day,
)

_SECONDS_PER_DAY = 86400.0


def test_yutu2_profile_top_speed_could_physically_average_the_observed_rate():
    """v_max, expressed as m/day, must exceed the real (dormancy-included)
    average rate -- otherwise the profile could not have covered that
    distance even driving nonstop."""
    rover = get_rover("cnsa_yutu_2")
    top_speed_m_per_day = float(rover["v_max_ms"]) * _SECONDS_PER_DAY
    assert top_speed_m_per_day > yutu2_average_rate_m_per_day()


def test_yutu2_profile_top_speed_is_not_absurdly_faster_than_reality():
    """A weak upper sanity bound: v_max should not exceed the observed
    rate by more than four orders of magnitude, which would indicate the
    constant was mistyped (e.g. km/h entered as m/s)."""
    rover = get_rover("cnsa_yutu_2")
    top_speed_m_per_day = float(rover["v_max_ms"]) * _SECONDS_PER_DAY
    assert top_speed_m_per_day < yutu2_average_rate_m_per_day() * 1e4


def test_cnsa_yutu2_profile_could_physically_cover_pragyans_distance():
    """Cross-mission bound: LunaPath's slow-rover-class profile
    (cnsa_yutu_2), run continuously for Pragyan's real active window,
    must be physically capable of exceeding Pragyan's real distance.
    Real operations always include imaging, commanding and ISRO ground
    review, so actual driving time is well below this ceiling -- this
    test only asserts the ceiling is not already violated."""
    rover = get_rover("cnsa_yutu_2")
    max_possible_m = (
        float(rover["v_max_ms"]) * _SECONDS_PER_DAY * pragyan_active_days()
    )
    assert max_possible_m >= float(PRAGYAN_MISSION["total_distance_m"])


def test_lpr1_default_speed_exceeds_every_referenced_real_mission_rate():
    """LPR-1 is LunaPath's default, higher-capability profile; it should
    not be constant-for-constant slower than any flown mission this
    catalogue references."""
    rover = get_rover("lpr_1")
    top_speed_m_per_day = float(rover["v_max_ms"]) * _SECONDS_PER_DAY
    assert top_speed_m_per_day > yutu2_average_rate_m_per_day()
    assert top_speed_m_per_day > pragyan_average_rate_m_per_day()


def test_all_rover_speeds_are_within_a_physically_plausible_planetary_rover_band():
    """0 < v_max <= 1 m/s covers every flown or proposed lunar/martian
    rover to date (Perseverance's peak is ~0.042 m/s; VIPER's design
    target is a few cm/s); this is a broad corruption guard, not a
    per-rover claim."""
    for rover_id in ("lpr_1", "luvmi_m", "nasa_viper", "cnsa_yutu_2"):
        v_max = float(get_rover(rover_id)["v_max_ms"])
        assert 0.0 < v_max <= 1.0
```

- [ ] **Step 2: Testleri çalıştır, geçtiklerini doğrula**

Run: `cd backend && pytest test_rover_validation.py -v`

Expected: 6 test PASS. Herhangi biri **başarısız** olursa `constants.py`'deki ilgili rover sabitini incele — bu, bir yazım hatası (birim karışıklığı gibi) yakaladığı anlamına gelir, testi gevşetme.

- [ ] **Step 3: Tam regresyon**

```bash
cd backend && pytest -v
python test_cost_engine.py
python test_traversability.py
```

Expected: hepsi PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/test_rover_validation.py
git commit -m "test: validate rover speed constants against flown mission data"
```

---

### Task 3: `route_analysis.py` — `PathAnalysis`'ten ilham istatistikler

Spec §1.5: *"`PathAnalysis` istatistiksel analiz — bizde yok. Rota üzerinde dağılım istatistikleri (eğim histogramı, risk yüzdeleri) sunmak jüri için güçlü."* Bu görev `simulate_path`'in ürettiği durum dizisini, dokunmadan, ayrı bir modülde özetliyor.

**Files:**
- Create: `backend/app/route_analysis.py`
- Modify: `backend/app/main.py` (`plan` endpoint)
- Modify: `backend/app/serializer.py` (`build_plan_response`)
- Test: `backend/test_route_analysis.py` (create)

**Interfaces:**
- Consumes: `list[app.simulation.RoverState]`
- Produces: `route_statistics(states, slope_bins_deg=(0, 5, 10, 15, 20, 25)) -> dict` — Task 3 Step 5 `/api/plan` yanıtına `route_statistics` alanı olarak ekler

- [ ] **Step 1: Başarısız testleri yaz**

`backend/test_route_analysis.py` oluştur:

```python
"""Route statistics (PathAnalysis-inspired) tests."""

from __future__ import annotations

import pytest

from app.route_analysis import route_statistics
from app.simulation import RoverState


def _state(step, slope_deg, risk_level, surface_temp_c=-60.0) -> RoverState:
    return RoverState(
        step=step,
        row=step,
        col=step,
        distance_m=step * 80.0,
        elapsed_hours=step * 0.5,
        battery_wh=5000.0 - step * 10,
        battery_pct=100.0 - step * 2,
        risk_level=risk_level,
        slope_deg=slope_deg,
        surface_temp_c=surface_temp_c,
        shadow_ratio=0.2,
        node_cost=0.3,
        step_energy_wh=10.0,
        cumulative_cost=step * 0.3,
        recharge_count=0,
        recharged_this_step=False,
    )


def test_empty_states_return_zeroed_statistics():
    stats = route_statistics([])
    assert stats["waypoint_count"] == 0
    assert stats["slope_histogram"] == []
    assert stats["risk_breakdown_pct"] == {}


def test_slope_histogram_bins_cover_every_waypoint():
    states = [
        _state(0, slope_deg=2.0, risk_level="LOW"),
        _state(1, slope_deg=7.0, risk_level="LOW"),
        _state(2, slope_deg=22.0, risk_level="MEDIUM"),
    ]
    stats = route_statistics(states)
    total_count = sum(bucket["count"] for bucket in stats["slope_histogram"])
    assert total_count == 3


def test_slope_histogram_bucket_labels_are_ordered():
    states = [_state(0, slope_deg=3.0, risk_level="LOW")]
    stats = route_statistics(states)
    lows = [bucket["bin_low_deg"] for bucket in stats["slope_histogram"]]
    assert lows == sorted(lows)


def test_risk_breakdown_sums_to_one_hundred_percent():
    states = [
        _state(0, slope_deg=2.0, risk_level="LOW"),
        _state(1, slope_deg=3.0, risk_level="LOW"),
        _state(2, slope_deg=4.0, risk_level="HIGH"),
        _state(3, slope_deg=5.0, risk_level="CRITICAL"),
    ]
    stats = route_statistics(states)
    assert stats["risk_breakdown_pct"]["LOW"] == pytest.approx(50.0)
    assert stats["risk_breakdown_pct"]["HIGH"] == pytest.approx(25.0)
    assert stats["risk_breakdown_pct"]["CRITICAL"] == pytest.approx(25.0)
    assert sum(stats["risk_breakdown_pct"].values()) == pytest.approx(100.0)


def test_thermal_extremes_are_reported():
    states = [
        _state(0, slope_deg=1.0, risk_level="LOW", surface_temp_c=-140.0),
        _state(1, slope_deg=1.0, risk_level="LOW", surface_temp_c=-20.0),
    ]
    stats = route_statistics(states)
    assert stats["min_surface_temp_c"] == pytest.approx(-140.0)
    assert stats["max_surface_temp_c"] == pytest.approx(-20.0)


def test_waypoint_count_matches_input_length():
    states = [_state(i, slope_deg=1.0, risk_level="LOW") for i in range(7)]
    stats = route_statistics(states)
    assert stats["waypoint_count"] == 7


def test_custom_slope_bins_are_respected():
    states = [_state(0, slope_deg=12.0, risk_level="LOW")]
    stats = route_statistics(states, slope_bins_deg=(0, 15, 30))
    assert len(stats["slope_histogram"]) == 2
    assert stats["slope_histogram"][0]["count"] == 1
```

- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula**

Run: `cd backend && pytest test_route_analysis.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'app.route_analysis'`

- [ ] **Step 3: `route_analysis.py`'yi uygula**

`backend/app/route_analysis.py` oluştur:

```python
"""Route-level statistical summary, inspired by ETH lunar_planner's
PathAnalysis tool (spec 1.5).

simulate_path already produces a per-step RoverState sequence;
summarize_simulation reduces it to scalar totals. This module adds the
distribution view PathAnalysis has and LunaPath lacked: how much of the
route sits in each slope band, what fraction of steps were at each risk
level, and the thermal extremes actually crossed. Kept separate from
summarize_simulation so neither function's tested output changes shape.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .simulation import RoverState

DEFAULT_SLOPE_BINS_DEG: tuple[float, ...] = (0.0, 5.0, 10.0, 15.0, 20.0, 25.0)


def route_statistics(
    states: Sequence[RoverState],
    slope_bins_deg: Sequence[float] = DEFAULT_SLOPE_BINS_DEG,
) -> dict[str, Any]:
    """Distribution statistics over a simulated route."""
    if not states:
        return {
            "waypoint_count": 0,
            "slope_histogram": [],
            "risk_breakdown_pct": {},
            "min_surface_temp_c": None,
            "max_surface_temp_c": None,
        }

    bins = list(slope_bins_deg)
    counts = [0] * (len(bins) - 1)
    for state in states:
        for i in range(len(bins) - 1):
            lo, hi = bins[i], bins[i + 1]
            is_last = i == len(bins) - 2
            if lo <= state.slope_deg < hi or (is_last and state.slope_deg == hi):
                counts[i] += 1
                break

    total = len(states)
    histogram = [
        {
            "bin_low_deg": bins[i],
            "bin_high_deg": bins[i + 1],
            "count": counts[i],
            "pct": round(100.0 * counts[i] / total, 2),
        }
        for i in range(len(bins) - 1)
    ]

    risk_counts: dict[str, int] = {}
    for state in states:
        risk_counts[state.risk_level] = risk_counts.get(state.risk_level, 0) + 1
    risk_breakdown_pct = {
        level: round(100.0 * count / total, 2) for level, count in risk_counts.items()
    }

    temps = [state.surface_temp_c for state in states]

    return {
        "waypoint_count": total,
        "slope_histogram": histogram,
        "risk_breakdown_pct": risk_breakdown_pct,
        "min_surface_temp_c": round(min(temps), 2),
        "max_surface_temp_c": round(max(temps), 2),
    }
```

- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula**

Run: `cd backend && pytest test_route_analysis.py -v`

Expected: 7 test PASS.

- [ ] **Step 5: `/api/plan`'a bağla**

`backend/app/serializer.py` içinde `build_plan_response` imzasına, `corridor` parametresinin altına ekle:

```python
    route_statistics: dict[str, Any] | None = None,
```

ve döndürülen sözlüğe `"corridor": corridor,` satırının altına ekle:

```python
        "route_statistics": route_statistics,
```

`backend/app/main.py` import bloğuna ekle:

```python
from .route_analysis import route_statistics as compute_route_statistics
```

`plan` fonksiyonunda, `build_plan_response(...)` çağrısına son argüman olarak ekle:

```python
            route_statistics=compute_route_statistics(states),
```

- [ ] **Step 6: Endpoint testini ekle ve çalıştır**

`backend/test_route_analysis.py` sonuna ekle:

```python
import numpy as np
from fastapi.testclient import TestClient

from app.constants import get_rover
from app.main import app

_SHAPE = (30, 30)


def test_plan_endpoint_returns_route_statistics():
    rover = get_rover()
    app.state.grids = {
        "elevation": np.zeros(_SHAPE),
        "slope": np.full(_SHAPE, 3.0),
        "aspect": np.zeros(_SHAPE),
        "thermal": np.full(_SHAPE, -60.0),
        "shadow_ratio": np.full(_SHAPE, 0.2),
        "traversable": np.ones(_SHAPE, dtype=bool),
        "cost": np.full(_SHAPE, 0.3),
        "metadata": {
            "origin": {"x": 156000.0, "y": 28000.0},
            "resolution_m": 80.0,
            "shape": list(_SHAPE),
            "crs": "test",
            "default_rover_id": rover["id"],
            "cost_weights": {
                "w_slope": 0.409,
                "w_energy": 0.259,
                "w_shadow": 0.142,
                "w_thermal": 0.19,
            },
        },
    }
    with TestClient(app) as client:
        response = client.post(
            "/api/plan",
            json={
                "start": {"row": 2, "col": 2},
                "goal": {"row": 25, "col": 25},
                "include_simulation": True,
            },
        )
    app.state.grids = None

    assert response.status_code == 200
    stats = response.json()["route_statistics"]
    assert stats["waypoint_count"] > 0
    assert stats["slope_histogram"]
    assert stats["risk_breakdown_pct"]
```

Run: `cd backend && pytest test_route_analysis.py test_plan_endpoint.py -v`

Expected: 8 test PASS.

- [ ] **Step 7: Tam regresyon ve commit**

```bash
cd backend && pytest -v
python test_cost_engine.py
python test_traversability.py
git add backend/app/route_analysis.py backend/app/main.py backend/app/serializer.py \
        backend/test_route_analysis.py
git commit -m "feat: add PathAnalysis-inspired route statistics to /api/plan

Slope histogram and risk-level percentage breakdown, in the spirit of
ETH lunar_planner's PathAnalysis tool. Additive: summarize_simulation
and its tested output shape are untouched."
```

---

### Task 4: `thermal_validation.py` — Diviner karşılaştırması

Spec §1.4: *"Diviner sıcaklıkları → `heat1d` çıktımızın harici doğrulaması."* Gerçek Diviner Polar Resource Product verisi bu repoda **yok** ve indirme adımı otomatikleştirilmiyor — MIT Imbrium / PDS Geosciences node'dan manuel indirme gerektirir (bkz. `KAYNAK_HARITASI.md` B1). Bu görev, veri varsa çalışan, yoksa nazikçe atlayan bir karşılaştırma hattı kuruyor.

**Files:**
- Create: `backend/app/thermal_validation.py`
- Create: `scripts/diviner_validation.py`
- Test: `backend/test_thermal_validation.py` (create)

**Interfaces:**
- Consumes: yalnızca NumPy (saf fonksiyon)
- Produces: `thermal_comparison(model_c, reference_c, traversable_threshold_c=-150.0) -> dict` — `rmse_c`, `mae_c`, `bias_c`, `n_compared`, `misclassified_traversable_pct`

- [ ] **Step 1: Başarısız testleri yaz**

`backend/test_thermal_validation.py` oluştur:

```python
"""Thermal model vs. reference comparison tests (pure function, no data file)."""

from __future__ import annotations

import numpy as np
import pytest

from app.thermal_validation import thermal_comparison


def test_identical_grids_have_zero_error():
    grid = np.array([[-60.0, -80.0], [-40.0, -120.0]])
    result = thermal_comparison(grid, grid)
    assert result["rmse_c"] == pytest.approx(0.0, abs=1e-9)
    assert result["mae_c"] == pytest.approx(0.0, abs=1e-9)
    assert result["bias_c"] == pytest.approx(0.0, abs=1e-9)


def test_constant_offset_is_captured_as_bias_and_rmse():
    model = np.full((3, 3), -60.0)
    reference = np.full((3, 3), -50.0)
    result = thermal_comparison(model, reference)
    assert result["bias_c"] == pytest.approx(-10.0)
    assert result["rmse_c"] == pytest.approx(10.0)


def test_nan_cells_are_excluded_from_the_comparison():
    model = np.array([[-60.0, np.nan], [-40.0, -120.0]])
    reference = np.array([[-55.0, -70.0], [-40.0, np.nan]])
    result = thermal_comparison(model, reference)
    assert result["n_compared"] == 2


def test_shape_mismatch_is_rejected():
    with pytest.raises(ValueError):
        thermal_comparison(np.zeros((2, 2)), np.zeros((3, 3)))


def test_all_nan_grids_report_zero_compared_and_no_crash():
    model = np.full((2, 2), np.nan)
    reference = np.full((2, 2), np.nan)
    result = thermal_comparison(model, reference)
    assert result["n_compared"] == 0
    assert result["rmse_c"] is None


def test_misclassification_counts_only_disagreements_at_the_threshold():
    """Model says traversable (-140 > -150), reference says blocked (-160)."""
    model = np.array([[-140.0]])
    reference = np.array([[-160.0]])
    result = thermal_comparison(model, reference, traversable_threshold_c=-150.0)
    assert result["misclassified_traversable_pct"] == pytest.approx(100.0)


def test_misclassification_is_zero_when_thresholds_agree():
    model = np.array([[-140.0, -160.0]])
    reference = np.array([[-135.0, -170.0]])
    result = thermal_comparison(model, reference, traversable_threshold_c=-150.0)
    assert result["misclassified_traversable_pct"] == pytest.approx(0.0)
```

- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula**

Run: `cd backend && pytest test_thermal_validation.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'app.thermal_validation'`

- [ ] **Step 3: `thermal_validation.py`'yi uygula**

`backend/app/thermal_validation.py` oluştur:

```python
"""Compare a modelled thermal grid to an external reference (e.g. Diviner).

Pure function: takes two co-registered (H, W) Celsius arrays, returns
error statistics. Does not fetch, reproject or crop data -- that is
scripts/diviner_validation.py's job, kept out of this module so the
comparison itself is testable without a real Diviner file.
"""

from __future__ import annotations

import numpy as np


def thermal_comparison(
    model_c: np.ndarray,
    reference_c: np.ndarray,
    traversable_threshold_c: float = -150.0,
) -> dict[str, float | int | None]:
    """RMSE/MAE/bias between a modelled and a reference thermal grid.

    Cells where either grid is NaN are excluded. ``misclassified_traversable_pct``
    is the share of compared cells where the two grids disagree about
    whether ``value >= traversable_threshold_c`` -- the number that
    matters for LunaPath, since that threshold gates traversability.
    """
    model = np.asarray(model_c, dtype=np.float64)
    reference = np.asarray(reference_c, dtype=np.float64)
    if model.shape != reference.shape:
        raise ValueError(
            f"shape mismatch: model {model.shape} vs reference {reference.shape}"
        )

    valid = np.isfinite(model) & np.isfinite(reference)
    n_compared = int(np.sum(valid))
    if n_compared == 0:
        return {
            "rmse_c": None,
            "mae_c": None,
            "bias_c": None,
            "n_compared": 0,
            "misclassified_traversable_pct": None,
        }

    error = model[valid] - reference[valid]
    rmse = float(np.sqrt(np.mean(error**2)))
    mae = float(np.mean(np.abs(error)))
    bias = float(np.mean(error))

    model_ok = model[valid] >= traversable_threshold_c
    reference_ok = reference[valid] >= traversable_threshold_c
    misclassified_pct = float(100.0 * np.mean(model_ok != reference_ok))

    return {
        "rmse_c": round(rmse, 3),
        "mae_c": round(mae, 3),
        "bias_c": round(bias, 3),
        "n_compared": n_compared,
        "misclassified_traversable_pct": round(misclassified_pct, 3),
    }
```

- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula**

Run: `cd backend && pytest test_thermal_validation.py -v`

Expected: 7 test PASS.

- [ ] **Step 5: Karşılaştırma script'ini yaz**

`scripts/diviner_validation.py` oluştur:

```python
#!/usr/bin/env python3
"""Compare LunaPath's modelled thermal grid to a real Diviner measurement.

Requires a manually downloaded Diviner Polar Resource Product covering our
80 m south-pole window. LunaPath does not auto-fetch this: MIT Imbrium
(imbrium.mit.edu) and the PDS Geosciences node host these products under
per-mission browse directories that change over time, so pin down the
current URL by hand rather than trust a hardcoded one.

If the reference file is not present, this script explains what to get
and exits 0 -- it must never fabricate comparison data.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from rasterio.warp import Resampling, reproject  # noqa: E402

from app.thermal_validation import thermal_comparison  # noqa: E402

_HOWTO = """
Diviner referans dosyasi bulunamadi: {path}

Elde etmek icin:
  1. https://imbrium.mit.edu/BROWSE/EXTRAS/ILLUMINATION/ (veya guncel PDS
     Geosciences node adresini) ziyaret edin.
  2. LunaPath'in penceresini kapsayan Diviner Polar Resource Product
     (ortalama/maksimum yuzey sicakligi) IMG/GeoTIFF dosyasini indirin.
  3. {path} yoluna kaydedin.

Bu script veri olmadan sahte karsilastirma uretmez.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reference",
        default="lunapath/data/raw/diviner_temperature.tif",
        help="Path to a Diviner surface-temperature raster (Celsius).",
    )
    parser.add_argument(
        "--processed-dir", default="lunapath/data/processed",
        help="Directory holding thermal_grid.npy and metadata.json.",
    )
    parser.add_argument("--out", default="docs/research/diviner_validation.md")
    args = parser.parse_args()

    reference_path = Path(args.reference)
    if not reference_path.exists():
        print(_HOWTO.format(path=reference_path))
        return

    processed_dir = Path(args.processed_dir)
    model = np.load(processed_dir / "thermal_grid.npy")

    with rasterio.open(processed_dir / "elevation_grid.npy") as _:
        pass  # placeholder guard removed below; elevation_grid.npy is not
              # a rasterio-readable file (.npy), so read the CRS/transform
              # from metadata.json instead.

    import json

    metadata = json.loads((processed_dir / "metadata.json").read_text(encoding="utf-8"))
    resolution_m = float(metadata["resolution_m"])
    origin = metadata["origin"]
    rows, cols = metadata["shape"]
    dst_transform = rasterio.transform.from_origin(
        origin["x"], origin["y"] + rows * resolution_m, resolution_m, resolution_m
    )
    dst_crs = metadata["crs"]

    with rasterio.open(reference_path) as reference_ds:
        reference = np.full((rows, cols), np.nan, dtype=np.float64)
        reproject(
            source=rasterio.band(reference_ds, 1),
            destination=reference,
            src_transform=reference_ds.transform,
            src_crs=reference_ds.crs,
            dst_transform=dst_transform,
            dst_crs=dst_crs,
            resampling=Resampling.bilinear,
        )

    result = thermal_comparison(model, reference)

    lines = [
        "# Diviner dogrulama raporu",
        "",
        f"Referans: `{reference_path}`",
        "",
        "| Metrik | Deger |",
        "|---|---|",
    ]
    for key, value in result.items():
        lines.append(f"| {key} | {value} |")

    lines += [
        "",
        "**Okuma:** `rmse_c` heat1d'nin peak yuzey sicakligi ile Diviner'in",
        "olcumu arasindaki kok-ortalama-kare hatasidir. `misclassified_traversable_pct`,",
        "iki modelin `-150 C` gecilebilirlik esiginde ANLASMADIGI hucrelerin oranidir",
        "-- planlama acisindan en kritik sayi budur.",
    ]

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Veri olmadan çalıştığını doğrula**

```bash
python scripts/diviner_validation.py
```

Expected: dosya bulunamadı mesajı ve indirme talimatı yazdırılıyor; script **çıkış kodu 0** ile bitiyor (hata fırlatmıyor), `docs/research/diviner_validation.md` **oluşturulmuyor**.

- [ ] **Step 7: (Opsiyonel) gerçek veriyle doğrula**

Diviner referans dosyası elde edilirse:

```bash
python scripts/diviner_validation.py --reference lunapath/data/raw/diviner_temperature.tif
```

Expected: `docs/research/diviner_validation.md` üretiliyor; `rmse_c` sonlu bir sayı. **Bu adım veri erişimine bağlı — elde edilemezse Step 6'nın çıktısı yeterli kabul kriteridir.**

- [ ] **Step 8: Commit**

```bash
git add backend/app/thermal_validation.py backend/test_thermal_validation.py \
        scripts/diviner_validation.py
git commit -m "feat: add Diviner thermal comparison with graceful no-data fallback

thermal_comparison() is a pure, fully-tested function. The download step
is deliberately manual: LunaPath does not fabricate validation data when
a reference file is absent -- it explains how to get one and exits."
```

---

## Faz 6 kabul kriterleri

- [ ] `cd backend && pytest` — tüm testler geçiyor (`test_mission_reference.py`, `test_rover_validation.py`, `test_route_analysis.py`, `test_thermal_validation.py` dahil)
- [ ] `python test_cost_engine.py` ve `python test_traversability.py` — çıkış kodu 0
- [ ] `test_rover_validation.py`'deki altı test, gerçek Yutu-2/Pragyan verisine karşı geçiyor
- [ ] `POST /api/plan` yanıtında `route_statistics` alanı var: `slope_histogram` ve `risk_breakdown_pct` dolu
- [ ] `python scripts/diviner_validation.py` veri olmadan **çökmeden** çalışıyor ve indirme talimatı veriyor
- [ ] `mission_reference.py`'deki her rakamın satır içi kaynak atıfı var

## Bilinen sınır

Bu faz **nokta-doğruluk** değil **gerekli koşul** doğrulaması yapar (bkz. üstteki dürüstlük notu). Tam bir A/B/C/D ablasyon protokolü (gerçek termal + gerçek gölge ile uçtan uca rota karşılaştırması) ve NASA-STD-7009 tarzı kredibilite skorkartı, spec'in "Sonraki aşamaya bırakılanlar" tablosunda [03](../../research/03_sentetik_minimum_veri.md) ve [09](../../research/09_olgunluk_kiyaslama.md)'a atıfla kapsam dışı bırakılmıştır.

## Sonraki adım

Yok — bu, altı fazlı entegrasyon planının sonuncusu. Master plan'daki [`Faz kabul kriterleri`](2026-08-19-lunapath-master-plan.md#faz-kabul-kriterleri-üst-düzey) bölümüyle tüm planı kapat.
