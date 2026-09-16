# C1 — Güneş paneli geliş açısı ve panel geometrisi (cos i) — uygulama planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Panel kazancı `g(t) = Σ_yüzey max(0, cos i) / raw_ref` yeni `app/panel.py`'de; kataloğa
beş panel geometrisi alanı (hepsi `"assumption:"` kaynaklı); `panel_model="cos_incidence"` ile
4-B hattının WAIT maliyeti, MOVE enerjisi ve batarya durumu aynı (T,) diziden beslenir;
varsayılan `"sun_pointed"` bit-eşit; `GET /api/panel-gain`; her yanıtta `panel` bloğu; Site11'de
ölçüm ve rapor.

**Architecture:** Yeni `app/panel.py` (geometri, çok yüzeyli kazanç, normalizasyon, katalog
okuma, NASA çapraz kontrolü, bloklar, karşı-olgular); paylaşılan enerji fonksiyonlarına tek
`solar_gain` parametresi (`cost_engine`, `cost_vec`, `costmap.PlanContext`, `cost_cube`);
`pathfinder_4d.astar_4d(solar_gain_series=…)`; `stress_test` kümülatif aydınlık-kazanç tablosu;
`survival._power_terms(solar_gain=…)` muhafazakâr, **ışık olan dilimlerin** en küçüğü
(`panel.conservative_gain`); `main.py` istek alanı, yanıt bloğu,
bir yeni uç; `scripts/panel_cos_i_report.py`.

**Spec:** [2026-09-15-c1-panel-cos-i-design.md](../specs/2026-09-15-c1-panel-cos-i-design.md)

**Tech Stack:** Python 3.11, NumPy, FastAPI/pydantic, pytest, spiceypy (yalnız gerçek grid).

**Commit kuralı:** özellik bitince **tek commit**; ara commit yok; push en sonda; commit
mesajında eş-yazar satırı yok.

---

## Global Constraints

- Sayı uydurma yok: her kazanç, oran, rota ve bekleme sayısı Site11'de koşturulup okunur.
  Araştırma belgesindeki "~30 kat" ölçülmeden yazılmaz.
- `p_solar_w × max(0, cos i)` YAPILMAZ (geometri iki kez sayılır). Kazanç dizinin kendi en iyi
  ham değerine normalize edilir.
- `panel_model="sun_pointed"` (varsayılan) ⇒ `g ≡ 1` ⇒ **bit-eşit**: standart 4-B rotalar
  41 / 116 hamle, aynı `nodes_expanded`, aynı `total_cost`; `COST_MODEL_ID = …_v5` değişmez ve
  maliyet gridi bayt-eşittir (LPR-1'in iki checked-in SHA-256 özeti eşleşmeye devam eder; NASA
  VIPER'ınkiler C1'den ÖNCE de eşleşmiyordu — 4af6989). VIPER kısa leg'i her iki modelde de aynı
  cevabı verir (bu katalogda 422).
- Panel geometrisi kataloğa yalnız `"assumption:"` ile başlayan kaynak dizesiyle girer.
- Model `MODEL`; verim/alan/toz/albedo yok ve yokluğu her blokta yazılır.
- Güneş ufkun altındayken `g = 0`.
- Frontend koduna dokunulmaz; sözleşmeye yalnız ek.

## Dosya haritası

| Dosya | Durum | Ne |
|---|---|---|
| `backend/app/panel.py` | yeni | geometri, kazanç, normalizasyon, bloklar, çapraz kontrol |
| `backend/app/constants.py` | ekleme | beş alan × dört profil, iki kaynak dizesi, `MODELLED_FIELDS` |
| `backend/app/cost_engine.py` | ekleme | `solar_gain` × 4 fonksiyon + docstring |
| `backend/app/cost_vec.py` | ekleme | `solar_gain` × 2 (aynı işlem sırası) |
| `backend/app/costmap.py` | ekleme | `PlanContext.solar_gain` |
| `backend/app/cost_cube.py` | ekleme | `wait_cost`, `build_wait_cost_cube`, `build_cost_cube` |
| `backend/app/pathfinder_4d.py` | ekleme | `solar_gain_series` |
| `backend/app/simulation.py` | ekleme | `solar_gain` |
| `backend/app/stress_test.py` | ekleme | kümülatif aydınlık-kazanç |
| `backend/app/survival.py` | ekleme | `_power_terms(solar_gain)` |
| `backend/app/main.py` | ekleme | `panel_model`, `panel` bloğu, `GET /api/panel-gain` |
| `backend/test_panel.py` | yeni | birim + bit-eşitlik |
| `backend/test_panel_api.py` | yeni | API |
| `backend/test_panel_real_grid.py` | yeni | skip-korumalı gerçek grid |
| `scripts/panel_cos_i_report.py` | yeni | ölçüm betiği (`--json` / `--from-json` / `--out`) |
| `docs/research/panel_cos_i_report.md` | yeni | rapor |
| `docs/frontend/3b-veri-sozlesmesi.md` | ekleme | "C1 eki", `## Değişmeyenler`'den ÖNCE |
| `README.md` | ekleme | bir satır |
| `docs/research/12_…_2026-09-03.md` | ekleme | `## C1.` başlığına ✅ + "Yapıldı" bloğu |

---

### Task 0 — `panel.py` çekirdek geometri

**Files:** `backend/app/panel.py`, `backend/test_panel.py`
**Produces:** `cos_incidence`, `polar_tilt_deg`, `PanelFace`, `PanelArray`, `raw_gain`,
`best_reference_azimuth`, `reference_raw`, `panel_gain`

- [x] Adım 1: başarısız test → 2: kırmızı → 3: uygulama → 4: yeşil
- [x] Köşe durumları: dik geliş = 1, teğet = 0, arka yüz < 0 → kırpılır, β = 0 → `sin e`
- [x] Azimut yalnız farkla girer (çerçeve değişmezliği testle)
- [x] `e ≤ 0 → g = 0`

### Task 1 — çok yüzeyli dizi ve NASA çapraz kontrolü

**Files:** `backend/app/panel.py`, `backend/test_panel.py`
**Produces:** `PanelArray.reference_raw`, `viper_corner_check`, `VIPER_QUOTED`

- [x] Üç dik yüzey (90 / −90 / 180) → `raw_ref = √2`, en iyi ψ₀ = 135°
- [x] `viper_corner_check()`: 320 W → 452,5 W öngörü, yayımlanan 450 W, fark +%0,57
- [x] Tek levhada `panel_gain == max(0, cos i)` (normalizasyon özel hâli)

### Task 2 — katalog alanları

**Files:** `backend/app/constants.py`, `backend/test_panel.py`, `backend/test_rover_validation.py`
**Produces:** beş alan, iki `"assumption:"` kaynak dizesi, `MODELLED_FIELDS` güncel

- [x] Dört profil de aynı anahtar kümesine sahip kalır
- [x] Bölüntü **tamlığı** testi (bugün yalnız ayrıklık test ediliyor)
- [x] `array_for_rover` geometrisiz profilde `None` döner, uydurmaz
- [x] `json.dumps(rover_catalog(), allow_nan=False)` geçer

### Task 3 — paylaşılan enerji fonksiyonlarına `solar_gain`

**Files:** `cost_engine.py`, `cost_vec.py`, `costmap.py`, `backend/test_panel.py`
**Produces:** altı imza + `PlanContext.solar_gain`

- [x] Skaler ve vektörel ikizler **aynı işlem sırası**: `* (1.0 - ratio) * solar_gain`
- [x] `f_energy_cell` referans ölçeği `g = 1`'de sabit (yalnız `here_wh` okur)
- [x] `solar_gain=1.0` ⇒ `np.array_equal` eski çağrıyla
- [x] `python test_cost_engine.py` doğrudan koşturulur (pytest toplamıyor)

### Task 4 — `cost_cube` ve dilim başına tekilleştirme

**Files:** `cost_cube.py`, `backend/test_panel.py`, `backend/test_cost_cube.py`
**Produces:** `wait_cost(solar_gain)`, `build_wait_cost_cube(gain_series)`,
`build_cost_cube(gain_series)`

- [x] `gain_series=None` ⇒ eski tek-tablo yolu, küp bire bir aynı
- [x] `gain_series` verilince tekilleştirme **dilim başına**
- [x] Uzunluk uyuşmazlığı `ValueError`

### Task 5 — `pathfinder_4d` batarya entegrasyonu

**Files:** `pathfinder_4d.py`, `backend/test_panel.py`, `backend/test_pathfinder_4d.py`
**Produces:** `astar_4d(solar_gain_series=None)`

- [x] `None` ⇒ aynı yol, aynı `nodes_expanded`, aynı `total_cost`
- [x] Çok dilimli hamle **dilim gelirlerinin yamuğunu** yükler (ortalamaların çarpımını değil —
      terim kazançla çift-doğrusal); maliyet küpü ve B5 ile aynı sayı
- [x] Satıriçi aritmetik `cost_engine` referanslarıyla eşit kalır (mevcut test)

### Task 6 — `simulation`, `stress_test`, `survival`

**Files:** `simulation.py`, `stress_test.py`, `survival.py`, `backend/test_panel.py`
**Produces:** `simulate_path(solar_gain)`, kümülatif aydınlık-kazanç, `_power_terms(solar_gain)`

- [x] B5: `cumulative_lit_gain` yalnız kazanç verilince kurulur; verilmeyince eski yol bit-eşit
- [x] B1: skaler muhafazakâr ve **alanın kendi ufkundan**; `np.min` DEĞİL — ışık olan dilimlerin
      en küçüğü (tek karanlık dilim skaleri 0'a çökertip diziyi tümden kapatıyordu)
- [x] `test_stress_test_runs.py` dict karşılaştırması bozulmaz

### Task 7 — API

**Files:** `main.py`, `backend/test_panel_api.py`
**Produces:** `panel_model` alanı, `panel` bloğu (her zaman), `GET /api/panel-gain`,
`/api/illumination-series` içinde `panel`

- [x] `applied = bool(requested and artefact is not None)`
- [x] Epoksuz / kernelsiz / geometrisiz → gerekçeli 422
- [x] Varsayılan yanıtta blok `applied: false`, mevcut alanların hiçbiri değişmez
- [x] `/api/plan` bloğu `reason: "the 2-D cost grid has no epoch"`

### Task 8 — gerçek grid testleri

**Files:** `backend/test_panel_real_grid.py`
**Produces:** skip-korumalı dokuz test

- [x] Skip muhafızı altı dosyadaki metinle birebir aynı
- [x] Üç standart rota varsayılanda 41 / 116 (VIPER kısa leg C1'den önce de 422 — 4af6989'un
      `slope_max_deg` 20°→15° düzeltmesi; C1 yalnız "iki panel modeli aynı cevabı veriyor"u kilitler)
- [x] `cos_incidence` ile rota, bekleme sayısı ve SOC **ölçülüp** pinlenir
- [x] Muhafızın gerçekten geçtiği (atlanmadığı) doğrulanır

### Task 9 — rapor betiği ve rapor

**Files:** `scripts/panel_cos_i_report.py`, `docs/research/panel_cos_i_report.md`
**Produces:** ölçüm betiği ve raporu

- [x] Bölümler: (1) kaynakların söyledikleri + NASA çapraz kontrolü, (2) Site11 geometrisi,
      (3) karşı-olgu oranları (pencere tanımlarıyla), (4) üç standart rotada kısıtlı/kısıtsız
      fark: hamle, bekleme (A2 dwell etkisi), SOC, süre, (5) başlık kilitli karşı-olgu,
      (6) B1/B5 etkisi, (7) iddia sınırı ve sunum cümlesi
- [x] `--json` önce yazılır, `--from-json` ölçmeden yeniden render eder, veri yoksa yazmadan çıkar

### Task 10 — dokümanlar, tam paket, tek commit

**Files:** `docs/frontend/3b-veri-sozlesmesi.md`, `README.md`, araştırma belgesi, spec sonu
**Produces:** C1 eki, README satırı, ✅ + "Yapıldı" bloğu, "Uygulama sırasında bulunanlar"

- [x] `cd backend && python -m pytest -q` tam paket; sayılar spec'e yazılır
- [x] `ruff check backend/app backend/test_panel*.py scripts/panel_cos_i_report.py`
- [x] Tek commit, eş-yazar satırı yok, push yok
