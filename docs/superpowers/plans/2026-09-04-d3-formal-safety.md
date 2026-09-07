# D3 — Formal güvenlik gereksinimleri (FRETISH + STL robustness, RTAMT) — uygulama planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 11 güvenlik/görev gereksinimini FRETISH kalıbında yazıp STL'e elle
çevirmek; `/api/plan`, `/api/plan-4d`, `/api/compare` yanıtlarına ve yeni
`POST /api/safety-check` ucuna gereksinim başına robustness (ρ, birimli)
taşıyan `safety_margins` bloğunu eklemek; RTAMT ile yerleşik motoru her istekte
çapraz kontrol etmek; ROS 2 düğümüyle aynı kataloğu telemetri üzerinde koşturmak.

**Architecture:** `app/safety_monitor.py` (saf) üç şeyi taşır: küçük bir STL
AST'si + iki motor (yerleşik ayrık-zaman robustness ve RTAMT sarmalayıcı),
iz çeviricileri (2-B `RoverState`, 4-B plan yanıtı, telemetri örnekleri →
adlandırılmış sinyaller, türetilmiş saat sayaçları) ve rover'a bağlanan
gereksinim kataloğu (`evaluate_catalogue` → blok). `main.py` yalnızca ekleme
yapar. `docs/requirements/lunapath.fret.json` `fret_export()`'tan üretilir ve
testle birebirliği korunur.

**Spec:** [2026-09-04-d3-formal-safety-design.md](../specs/2026-09-04-d3-formal-safety-design.md)

**Tech Stack:** Python 3.11, NumPy, FastAPI/pydantic, `rtamt==0.3.5`
(isteğe bağlı; ANTLR runtime 4.9.3 ile doğrulandı), pytest; ROS 2 (rclpy,
`sensor_msgs`, `nav_msgs`, `std_msgs`, `lunapath_msgs`) yalnızca düğümde.

**Commit kuralı:** özellik bitince tek commit; push en sonda toplu; commit
mesajında eş-yazar satırı yok.

---

## Global Constraints

- Mevcut `/api/plan`, `/api/plan-4d`, `/api/compare`, `/api/plan-multi` alanları
  aynen; yalnızca ekleme (`safety_margins`, `comparison.safety_margin_ranking`,
  `comparison.largest_min_margin_profile`).
- Eşikler rover kataloğundan; tek katalog sabiti `RECHARGE_DEADLINE_H = 6.0`
  (`threshold_source: "catalogue"`). Sayı uydurma yok.
- RTAMT yoksa yerleşik motor; hiçbir uç 500 vermez; `inf`/`NaN` JSON'a sızmaz.
- Kapsam örnek maskesi; açık uçlu ρ → `null` + `open_ended`; ρ ≥ 0 sağlandı.
- Her yanıt "runtime monitoring ile denetlendi; model checking ile
  ispatlanmadı" iddiasını taşır (`monitor.claim`).
- TDD: her görevde önce başarısız test. Çekirdeksiz/verisiz klonda tüm yeni
  testler koşar; gerçek grid ve ROS testleri `skip`-korumalı.

---

## Dosya haritası

| Dosya | Sorumluluk |
|---|---|
| `backend/app/safety_monitor.py` | Yeni: STL AST, `to_rtamt`, `robustness_builtin`, `robustness_rtamt`, `robustness`; `Trace`, türetilmiş sinyaller, `trace_from_states` / `trace_from_plan4d` / `trace_from_samples`; `REQUIREMENTS`, `bind_catalogue`, `evaluate_catalogue`, `rank_by_margin`, `fret_export`; `SafetyMonitorSession` |
| `backend/app/main.py` | `SafetyCheckRequest`, `POST /api/safety-check`; `_safety_margins_2d`, `_safety_margins_4d` yardımcıları; `/api/plan`, `/api/plan-4d` blokları; `_attach_constraint_check` + `compare`/`plan_multi` sıralaması |
| `backend/requirements.txt` | `rtamt==0.3.5` (yorumla) |
| `lunapath_ros/lunapath_ros/safety_monitor_node.py`, `lunapath_ros/setup.py` | ROS düğümü ve giriş noktası |
| `scripts/export_fret_requirements.py` | `docs/requirements/lunapath.fret.json` üretimi |
| `scripts/safety_monitor_report.py` | Rapor → `docs/research/safety_monitor_report.md` |
| `docs/requirements/lunapath.fret.json`, `docs/requirements/README.md` | Gereksinim dosyası ve okunur özet |
| `backend/test_safety_monitor.py`, `test_safety_monitor_api.py`, `test_safety_monitor_real_grid.py`, `test_safety_monitor_ros.py` | Testler |
| `docs/frontend/3b-veri-sozlesmesi.md`, araştırma belgesi, spec, `README.md` | Belgeler |

---

## Görevler

### Task 0 — Ortam: RTAMT ve sonda
- [x] `pip install rtamt` (0.3.5; antlr4-python3-runtime 4.7'ye düşürdü, omegaconf/hydra ile çakıştı) → 4.9.3'e geri alındı, RTAMT sürüm uyarısıyla doğru çalışıyor (spec'te belgelendi).
- [x] 5 satırlık sonda: `always[0,10] (soc >= 20)` → ρ; veri kümesi `{'time': [...], 'soc': [...]}` biçiminde; iz sonu semantiği ölçüldü (pencere kırpılır).
- [x] `backend/requirements.txt`: `rtamt==0.3.5` + antlr notu.

### Task 1 — STL AST ve iki motor
- [x] `test_safety_monitor.py`: `to_rtamt(Always(Atom("soc", ">=", 20)))` == `"always (soc >= 20)"`; pencereli `Eventually(…, 0, 6)` `dt_h=0.1` → `"eventually[0,60] (…)"`; `dt_h` yokken pencereli → `ValueError`; `signals_of`.
- [x] Test: yerleşik ρ elle: atom (`x=[3,1,2]`, `x>=0` → `[3,1,2]`), `Not`, `And`/`Or`, `Implies` (`max(−a, b)`), `Always` sınırsız → `[1,1,2]`, `Eventually` sınırsız `x<=0` `[5,3,1]` → `[-1,-1,-1]`, `Always(…,0,3)` `x=[1,2,3,4,5]` → `[1,2,3,4,5]` (kırpma), `Eventually(…,0,3)` `[-1..-5]` → `[-1,-2,-3,-4,-5]`, `Until` `[1,2,3,3]` örneği (spec'teki RTAMT ölçümleri), `Implies + Eventually[0,2]` örneği → `[-0.5,…]`.
- [x] Test (`importorskip("rtamt")`): rastgele izlerde (seed) altı formül ailesi `max|Δρ| < 1e-9`; `+inf` içeren sinyal; `robustness(engine="auto")` `("rtamt"|"builtin")` döner; `engine="rtamt"` kurulu değilse `ImportError` (monkeypatch ile).
- [x] `safety_monitor.py`: AST sınıfları, `to_rtamt`, `signals_of`, `robustness_builtin` (numpy, pencereler örnek cinsinden, iz sonunda kırpma), `robustness_rtamt` (stdout bastırma, `time` anahtarı), `rtamt_available/version`, `robustness`.

### Task 2 — Türetilmiş sinyaller ve iz çeviricileri
- [x] Test: `continuous_shadow_hours(t=[0,1,3,4,6], in_shadow=[0,1,1,0,1])` → `[0,1,3,0,2]`; `hours_below_reserve(t, soc, 20, charging)` → şarjla sıfırlanan sayaç (elle); `path_lateral_slopes` eğik düzlemde (z = k·col): satır yönünde giden kenar yanal = atan(k), sütun yönünde 0; `path_step_slopes` = atan(|dz|/d).
- [x] Test: `trace_from_states` elle kurulmuş 4 `RoverState` (biri şarjlı, biri gölgeli) → `t_h`, `soc_pct = battery_low_pct`, `charging`, `shadow_continuous_h`, `drive_slope_deg = max(slope, segment)`, `dist_to_goal_m` (planlanan uzunluk − `distance_m`), `at_goal` son örnekte 1; `stranded=True` son durum → bir uzatma örneği (`extended_h = 708.72 − son adım`), `charging=0`, sayaçlar büyümüş.
- [x] Test: `trace_from_plan4d` sentetik (`path_states=[[0,0,0],[0,1,1],[0,1,2],[1,2,3]]`, bataryalar, `path_dark_hours`, `earth_visible=[T,T,F,T]`, `hours_until_earthset=[10,9,None,None]`, `haven_margin=[5,4,None,3]`, kaba gridler) → `moving=[0,1,0,1]`, `earth_link_h=[10,9,-1*slice? ,inf]` (görünmeyen bekleme kapsam dışı; görünmeyen hamle −süre), `haven_margin_h` `None→inf`, `drive_slope_deg` = max(kaba eğim, adım eğimi), `inner_temp_c` = `surface_to_inner(kaba termal)`.
- [x] Test: `trace_from_samples` eksik sinyal → `signals` içinde yok; `t_h` artmayan → `ValueError`; `shadow_ratio` ↔ `in_shadow`; `surface_temp_c` → `inner_temp_c`.
- [x] `safety_monitor.py`: `Trace`, dört yardımcı, üç çevirici.

### Task 3 — Katalog ve `evaluate_catalogue`
- [x] Test: `bind_catalogue(get_rover("nasa_viper"))` eşikleri (R01 96, R02 20, R03 6, R04 (−20, 50), R05 (0, 35), R06 20, R07 15, R11 20); LUVMI-M R04 `None` (uygulanamaz), Yutu-2 R02 30; `recharge_deadline_h=3` → R03 3.
- [x] Test: elle kurulmuş `Trace` (telemetri türü, 5 örnek) → `evaluate_catalogue` her gereksinimde bilinen ρ: R01 `96 − max(shadow)`, R02 `min(soc) − 20`, R03 `6 − max(hours_below)`, R04 `min(T+20, 50−T)`, R06/R07, R08 `min(earth_link_h | moving)`, R09 `min(haven_margin)`, R10 `−min(dist)`, R11 `soc[at_goal] − 20`; `satisfied`, `boundary` (ρ = 0), `worst_at.index/hours`; açık uçlu (`inf`) → `rho None, open_ended True`; kapsam boş (hedef yok) → R11 uygulanamaz, R10 ihlal; `min_margin` doğru id ve `rho_normalized = ρ/ölçek`; `verdict`; `monitor.engine`, `cross_check` (rtamt varsa 0); `json.dumps(allow_nan=False)` geçer.
- [x] Test: `rank_by_margin([("a", blok_a), ("b", blok_b)])` en büyük min-marj önce, ihlalli sonda, uygulanamaz (`not_evaluated`) en sonda.
- [x] `safety_monitor.py`: `Requirement`, `REQUIREMENTS` (11), `bind_catalogue`, `evaluate_catalogue`, `rank_by_margin`, `_json_safe`.

### Task 4 — FRET dışa aktarımı ve gereksinim belgesi
- [x] Test: `fret_export()` 11 gereksinim, her birinde `reqid`, `fulltext`, `rationale`, `semantics.{scope,condition,component,timing,response,ftLTL,stl,monitored_stl}`, `monitor.{signal,unit,rover_parameter,threshold_source,thresholds_by_rover,trace_kinds,class}`; `provenance` "not exported from the FRET tool" içerir; depodaki `docs/requirements/lunapath.fret.json` `==` `fret_export()` (dosya yoksa test başarısız — önce üret).
- [x] `scripts/export_fret_requirements.py`; `docs/requirements/lunapath.fret.json`; `docs/requirements/README.md` (FRETISH grameri, tablo, iddia sınırı, komut).

### Task 5 — API: plan, plan-4d, compare, safety-check
- [x] `test_safety_monitor_api.py`: `/api/plan` (test_plan_endpoint gridleri) → `safety_margins.monitor.engine ∈ {rtamt, builtin}`, R01/R02/R06/R07/R10/R11 uygulanabilir, R08/R09 `applicable False` + reason, `verdict`; mevcut anahtarlar (`status`, `summary`, `corridor`, …) aynen.
- [x] Test: `/api/plan-4d` (test_plan_4d_endpoint gridleri) → blok `trace.kind == "4d"`, R01 ρ = 96/50 − max(`path_dark_hours`), R02 ρ = min(`path_battery_pct`) − 20; Dünya/haven sahteleriyle (`_fake_safe_haven_map`, `_earth_series_closing_at(3)`) R08/R09 uygulanabilir ve R09 ρ == `metrics.min_haven_margin_h`.
- [x] Test: `/api/compare` her sonuçta `safety_margins`, `comparison.safety_margin_ranking` uzunluğu = profil sayısı, `largest_min_margin_profile`, mevcut `shortest_profile` vb. aynen; `/api/plan-multi` aynı.
- [x] Test: `/api/safety-check` 200 (telemetri örnekleri, `signals_present`, `ignored_keys`), `engine="builtin"` → `monitor.engine == "builtin"`, 422: boş `samples`, azalan `t_h`, `NaN`, bilinmeyen `engine`; `complete=False` → R10 `pending`.
- [x] `main.py`: `SafetyCheckRequest`, uç, `_safety_margins_2d/4d`, ekler.

### Task 6 — ROS 2 düğümü ve çevrimiçi oturum
- [x] Test (`test_safety_monitor.py`): `SafetyMonitorSession(rover).push({...})` ardışık örneklerde: `verdict` `pending` → `violated` monoton; `newly_violated` yalnızca ilk kez; `complete=False` R10 `satisfied None`.
- [x] Test (`test_safety_monitor_ros.py`, `importorskip("rclpy")`, `importorskip("lunapath_msgs")`): düğüm modülü içe aktarılır; `sample_from_messages(battery, temperature, shadow, odom, t_h)` çevirisi (`percentage 0.55 → 55`, `CHARGING → charging True`, hız > 1 mm/s → moving).
- [x] `safety_monitor.py`: `SafetyMonitorSession`; `lunapath_ros/lunapath_ros/safety_monitor_node.py` (`sample_from_messages` saf yardımcı + düğüm); `setup.py` giriş noktası.

### Task 7 — Gerçek grid testleri ve rapor
- [x] `test_safety_monitor_real_grid.py` (skip-guarded: gridler + ufuk + çekirdek): VIPER haven→haven `plan-4d` bloğu tutarlılıkları (R01/R02/R09 formülleri, `cross_check.max_abs_diff == 0`), `/api/plan` VIPER R01 ρ == `h_max − summary.max_continuous_shadow_h`; toplam süre sınırı.
- [x] `scripts/safety_monitor_report.py` → `docs/research/safety_monitor_report.md` (motor; iki 4-B rota tabloları; compare profilleri + ikili karar kıyası + sıralama; SHERPA ρ dağılımları; safety-check süresi). Koştur, sayıları oku.

### Task 8 — Belgeler ve kapanış
- [x] `docs/frontend/3b-veri-sozlesmesi.md` D3 eki ("## Değişmeyenler" öncesi): blok tabloları, ölçülen örnek.
- [x] Araştırma belgesinde D3 başlığına ✅ + "Yapıldı" blok alıntısı (ölçümler, bağlantılar, sapmalar).
- [x] Spec'e "Uygulama sırasında bulunanlar ve ölçümler"; README'ye rtamt satırı.
- [x] Tam test paketi `cd backend && python -m pytest` (1 031 passed, 2 skipped, 8:40); tek commit (eş-yazar satırı yok); hafıza dosyası güncellemesi (D3 yapıldı + hash, sıradaki A2).
