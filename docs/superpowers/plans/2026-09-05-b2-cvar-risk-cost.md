# B2 — CVaR tabanlı risk-farkında maliyet — uygulama planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Operatörün risk iştahı `α`'yı (`risk_alpha ∈ [0,5, 0,999]`, varsayılan `None` =
bugünkü grid bit-eşit) sıralama maliyetine bağlamak: enerji kriterinin slip'i `CVaR_α(slip)`
(C3 σ ⊕ B3 eğim σ, delta yöntemi), eğim kriterinin eğimi `min(slope_max, θ + σ_θ·m_α)`;
fizik (süre, batarya, D3, B5) μ'da kalır. `/api/plan` ve `/api/plan-4d`'ye `risk_alpha`,
yanıtlara `risk` bloğu, `POST /api/risk-sweep` ile α taraması; Site11'de ölçüm raporu.

**Architecture:** Yeni `app/risk.py` (kapalı form CVaR, slip/eğim CVaR skaler + vektörize
bit-eşit, rota risk özeti, termal kanca); `cost_engine`/`cost_vec` α ve `slope_sigma`
parametreleri (None yolu aynı işlemler); `costmap` katmanları α; `cost_cube` σ_θ kabalaştırma;
`rover_grids` önbellek anahtarı; `main` alanlar + bloklar + tarama ucu; rapor betiği.

**Spec:** [2026-09-05-b2-cvar-risk-cost-design.md](../specs/2026-09-05-b2-cvar-risk-cost-design.md)

**Tech Stack:** Python 3.11, NumPy 2.2, SciPy 1.15 (`special.ndtri`), FastAPI/pydantic, pytest.

**Commit kuralı:** özellik bitince tek commit; push en sonda toplu; commit mesajında
eş-yazar satırı yok.

---

## Global Constraints

- `risk_alpha=None` yolu **bit-eşit**: `compute_cost_grid`, `f_*_grid`, `edge_travel_time_s`,
  `build_cost_cube`, `grids_for_rover` çıktıları argümansız çağrıyla `np.array_equal`;
  Site11 v4 gridi SHA-256 kilidi (LPR-1 `0e74607d…`, VIPER `8788936c…`). `COST_MODEL_ID` v4 kalır.
- α yalnızca sıralama maliyetine girer; hiçbir süre/batarya/marj/Monte Carlo sayısı α'ya bağlı olmaz.
- `inf` kapısı (`θ > slope_max`) nominal θ'da; geçilebilirlik α'dan bağımsız.
- Etiket `MODEL`; "ölçülmüş risk" hiçbir yerde yazılmaz; `CVaR_0,5 ≠ ortalama` belgede açık.
- Termal CVaR uygulanmaz (kanca + not, ölçülen doygunlukla).
- Mevcut API alanları aynen; yalnızca ekleme. Frontend koduna dokunulmaz.
- Sayı uydurma yok; rapor Site11'de koşar; gerçek grid testleri skip-korumalı; TDD.

---

## Dosya haritası

| Dosya | Sorumluluk |
|---|---|
| `backend/app/risk.py` (yeni) | `cvar_multiplier`, `cvar_normal`, `slip_sensitivity(_array)`, `slip_stats_array`, `slip_cvar(_array)`, `slope_cvar(_array)`, `route_risk_summary`, `risk_block`, `sigma_sources`, `thermal_cvar_cold_c`, sabitler |
| `backend/app/cost_engine.py` | `edge_travel_time_s(_array)` `slip=`; `net_energy_per_metre_wh` `slip=`; `f_slope` / `f_energy_cell` α + σ_θ; `compute_cost_grid` α + `slope_sigma_grid` |
| `backend/app/cost_vec.py` | `f_slope_grid`, `f_energy_cell_grid`, `_energy_per_metre_wh_grid` α / `slip=` |
| `backend/app/costmap.py` | `PlanContext.slope_sigma`; `SlopeLayer`/`EnergyLayer` `risk_alpha`; `default_cost_map(risk_alpha)` |
| `backend/app/cost_cube.py` | `build_cost_cube(risk_alpha, slope_sigma)` |
| `backend/app/rover_grids.py` | `grids_for_rover(risk_alpha)`, önbellek anahtarı, `slope_sigma` ekleme |
| `backend/app/main.py` | `risk_alpha` alanları, `_risk_block_2d/_4d`, `RiskSweepRequest`, `POST /api/risk-sweep` |
| `backend/test_risk.py`, `backend/test_risk_cost.py`, `backend/test_risk_api.py`, `backend/test_risk_sweep_real_grid.py` | Testler |
| `scripts/risk_sweep_report.py` → `docs/research/risk_sweep_report.md` | Rapor |
| `docs/frontend/3b-veri-sozlesmesi.md`, araştırma belgesi, spec, `README.md` | Belgeler |

---

## Görevler

### Task 0 — Sondalar (yapıldı, spec'te)
- [x] Grid düzeyi CVaR slip / maliyet Spearman / termal doygunluk (sonda 1–2), 4-B + B5 rotaları (sonda 3/3b), 2-B ince grid (sonda 3c); v4 SHA-256 parmak izleri.

### Task 1 — `risk.py`: kapalı form, slip/eğim CVaR, parite, rota özeti, kanca
- [x] `test_risk.py` yaz (spec "Birim"): çarpan tablosu, sınır dışı, Monte Carlo doğrulaması, `CVaR_0,5 ≠ μ`, monotonluk, α = 0,999 sonlu, `slip_sensitivity` ↔ sayısal türev / kapıda 0 / eğrisiz 0, `slip_cvar` özellikleri, `slope_cvar` özellikleri, dört `_array` parite testi (100 000 θ × 4 rover), `route_risk_summary` elle, `thermal_cvar_cold_c`, sabitler.
- [x] Koştur → içe aktarma hatası.
- [x] `risk.py` yaz (spec "Bileşenler"); modül docstring'i: ne yapıldı, iddia sınırı, termal kanca.
- [x] Koştur → geçer.

### Task 2 — `cost_engine` / `cost_vec`: α ve `slip=` parametreleri
- [x] `test_risk_cost.py` yaz (spec "Maliyet yolu", ilk yarı): `edge_travel_time_s` `slip=None` bit-eşit ve `slip=s` formülü (dizi eşi de); `f_slope`/`f_energy_cell` ↔ grid α'lı `abs=1e-12`; None yolu `np.array_equal`; `compute_cost_grid` None ↔ argümansız, α monotonluğu, `inf` deseni, şekil hatası.
- [x] Koştur → başarısız.
- [x] `cost_engine.py`, `cost_vec.py` değişiklikleri; docstring'ler (α'nın nereye girdiği, None yolunun aynı işlemler olduğu).
- [x] Koştur → geçer; `test_review3_fixes.py`, `test_review_fixes.py`, `test_cost_vec.py`, `test_cost_engine_slip.py`, `test_legacy_harness.py` geçer.

### Task 3 — `costmap` / `cost_cube` / `rover_grids`
- [x] `test_risk_cost.py` ekle (ikinci yarı): `default_cost_map(risk_alpha)` explain; `build_cost_cube` α ≥ nominal ve None `np.array_equal`; `grids_for_rover` anahtar/`slope_sigma`/`risk` metadata/None temizliği.
- [x] Koştur → başarısız.
- [x] `costmap.py` (`PlanContext.slope_sigma`, katmanlar, `default_cost_map`), `cost_cube.py`, `rover_grids.py`.
- [x] Koştur → geçer; `test_costmap.py`, `test_cost_cube.py`, `test_rover_grids.py`, `test_pathfinder_4d.py`, `test_plan_4d_endpoint.py` geçer.

### Task 4 — API: alanlar, `risk` blokları, `/api/risk-sweep`
- [x] `test_risk_api.py` yaz (spec "API").
- [x] Koştur → başarısız.
- [x] `main.py`: `PlanRequest.risk_alpha`, `Plan4DRequest.risk_alpha`, `_risk_legs_2d`/`_risk_block_2d`, `_risk_legs_4d`/`_risk_block_4d`, `RiskSweepRequest`, `risk_sweep` ucu; `plan` ve `plan_4d` bağlama.
- [x] Koştur → geçer; `test_slip_api.py`, `test_plan_endpoint.py`, `test_plan_4d_endpoint.py`, `test_stress_test_api.py`, `test_uncertainty_api.py` geçer.

### Task 5 — Gerçek grid testi ve rapor
- [x] `test_risk_sweep_real_grid.py` (skip: `metadata.json` + `horizon_map.npy` + çekirdek; v4 SHA kilidi klon önbelleğinden bağımsız): spec "Gerçek grid".
- [x] Koştur → geçer (sayıları oku).
- [x] `scripts/risk_sweep_report.py` → `docs/research/risk_sweep_report.md`: (1) CVaR çarpanı tablosu ve eğrinin α'daki değerleri (0/5/10/15/20°, C3 σ ⊕ B3 medyan σ_θ); (2) Site11 grid düzeyi: σ_θ istatistikleri, CVaR slip medyan/kap oranı, eğim kapısı oranı, maliyet Spearman, enerji doygunluğu, termal doygunluk; (3) `/api/risk-sweep` 2-B: dört standart çift × α ∈ {None, 0,5, 0,9, 0,99}: mesafe/süre/Wh/min SOC/ort.-maks slip/örtüşme + risk matrisi; (4) 4-B `/api/plan-4d` + B5 (1 000 koşum): LPR-1 28 Eyl, LPR-1 Ay gecesi, VIPER kısa leg × α: hamle, varış, min SOC, ort./maks slip, CVaR slip, risk-ayarlı saat, B5 tamamlanma/rezerv içinde/tam başarı, örtüşme, planlama süresi; (5) okuma + sunum cümlesi + iddia sınırı + Endo alıntısı. `--json` önce, `--from-json`. Koştur, sayıları oku.

### Task 6 — Belgeler ve kapanış
- [x] `docs/frontend/3b-veri-sozlesmesi.md` B2 eki ("## Değişmeyenler" öncesi): `risk_alpha` istek alanı, `risk` bloğu tablosu, `/api/risk-sweep`, ölçülen örnek, iddia sınırı, `CVaR_0,5 ≠ ortalama` uyarısı.
- [x] Araştırma belgesinde B2 başlığına ✅ + "Yapıldı" blok alıntısı; README satırı.
- [x] Spec'e "Uygulama sırasında bulunanlar ve ölçümler" (tablolar, sapmalar, test sayıları).
- [x] Tam paket `cd backend && python -m pytest` (arka planda, tek başına); ruff yeni dosyalarda; tek commit (eş-yazar satırı yok); hafıza dosyası (B2 yapıldı + hash, sıradaki C4).
