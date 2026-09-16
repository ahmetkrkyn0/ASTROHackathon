# C2 — Batarya soğuk davranışı, hibernasyon ve karanlık dayanımı — uygulama planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Yeni `app/battery.py`'de (a) `usable_fraction(T)` teslim edilebilir kapasite eğrisi,
(b) JSC'nin Stefan-Boltzmann yasasından `heater_power_w(surface)`, (c) 4-B planlayıcıda atomik
`HIBERNATE` kenarı (karanlıkta başlar, aydınlıkta biter, dawn pre-heat'i güneşten öder),
(d) oransal dinamik `h_max_shadow_h`. Üç bayrak, üçü de kapalıyken **bit-eşit**.
`p_hibernate_w` ve `thermal_tau_s` ilk kez gerçekten okunur.

**Architecture:** `app/battery.py` (eğri, kalibrasyon, hibernasyon, dawn pre-heat, bloklar,
JSC çapraz kontrolü); paylaşılan enerji fonksiyonlarına tek isteğe bağlı `heater_w`;
`pathfinder_4d`'de `track_inner` + durum bağımlı dayanım eşiği + üçüncü kenar ailesi;
`main.py` üç bayrak + `battery` bloğu + bir uç; `scripts/battery_hibernation_report.py`.

**Spec:** [2026-09-16-c2-batarya-hibernasyon-design.md](../specs/2026-09-16-c2-batarya-hibernasyon-design.md)

**Tech Stack:** Python 3.11, NumPy, FastAPI/pydantic, pytest, spiceypy (yalnız gerçek grid).

**Commit kuralı:** özellik bitince **tek commit**; ara commit yok; push en sonda; commit
mesajında eş-yazar satırı yok.

---

## Global Constraints

- **Sayı uydurma yok.** Her eğri, katsayı, saat ve rota sayısı Site11'de koşturulup okunur.
  Belgedeki "%85 / %60" hiçbir yere yazılmaz.
- **Bit-eşitlik.** `battery_model="constant"` + `heater_power_model="constant"` +
  `allow_hibernate=false` ⇒ LPR-1'in iki checked-in SHA-256 maliyet-gridi özeti kıpırdamaz,
  `COST_MODEL_ID` v5 kalır, standart 4-B rotalar aynı hamle / `nodes_expanded` / `total_cost`.
- **Yeni katalog alanı YOK.** Her girdi ya `MODELLED_FIELDS`'ta, ya modül düzeyinde kaynaklı
  bir sabit, ya `"assumption:"` etiketli. `test_panel.py:315-322` bölüntü testi dokunulmadan
  yeşil kalır.
- **2-B maliyet gridi dokunulmaz** — sıcaklığa bağlı ısıtıcı `compute_cost_grid`'e girmez.
- **Alıntı ≠ ölçüm.** NASA Glenn / ISRO / Surveyor / JSC sayıları `*_QUOTED` sözlüklerinde
  ayrı durur.
- Frontend koduna dokunulmaz; sözleşmeye yalnız ek.

## Dosya haritası

| Dosya | Durum | Ne |
|---|---|---|
| `backend/app/battery.py` | yeni | eğri, kalibrasyon, hibernasyon, dawn pre-heat, bloklar, JSC çapraz kontrolü |
| `backend/app/constants.py` | ekleme+düzeltme | üç kaynak dizesi, `thermal_tau_s` sınıflaması, `:21` yorumu, C6 dizesi |
| `backend/app/cost_engine.py` | ekleme | `housekeeping_power_w(..., heater_w=None)` + üç çağıran |
| `backend/app/cost_vec.py` | ekleme | `_housekeeping_power_w_grid(..., heater_w=None)` aynı sırayla |
| `backend/app/cost_cube.py` | ekleme | `wait_cost`, `build_wait_cost_cube`, `build_cost_cube` |
| `backend/app/pathfinder_4d.py` | ekleme | `track_inner`, dinamik eşik, `HIBERNATE`, `path_actions` |
| `backend/app/survival.py` | ekleme | `_power_terms(..., heater_w)` |
| `backend/app/stress_test.py` | ekleme | ısıtıcı serisi, `path_actions` |
| ~~`backend/app/simulation.py`~~ | **yapılmadı** | 2-B simülatörün okuyabileceği tek termal alan uzun vadeli yıllık zirvedir, 4-B'nin dilim başına serisi değil |
| ~~`backend/app/safe_haven.py`~~ | **yapılmadı** | `route_margins` nominal şarj + sabit idame gücü kullanır; sınır yanıtta `margins_use_nameplate_charge` ile söylendi |
| `backend/app/main.py` | ekleme | üç bayrak, blok, `GET /api/battery-model`, önbellek anahtarı |
| `backend/test_battery.py` | yeni | birim + bit-eşitlik + ikiz süpürmesi |
| `backend/test_battery_api.py` | yeni | API + 422'ler |
| `backend/test_battery_real_grid.py` | yeni | skip-korumalı Site11 |
| `scripts/battery_hibernation_report.py` | yeni | ölçüm betiği |
| `docs/research/battery_hibernation_report.md` | yeni | rapor |
| `docs/frontend/3b-veri-sozlesmesi.md` | ekleme | "C2 eki", `## Değişmeyenler`'den ÖNCE |
| `README.md` | ekleme | bir satır (varsayılan KAPALI denir) |
| `docs/research/12_…_2026-09-03.md` | ekleme | `## C2.` başlığına ✅ + "Yapıldı" bloğu |

---

### Task 0 — `battery.py` kimlik, alıntılar, kullanılabilir kesir

**Files:** `backend/app/battery.py`, `backend/test_battery.py`
**Produces:** `BATTERY_*` kimlikleri, `NASA_GLENN_QUOTED`, `JSC_QUOTED`, `BATTERY_FREEZE_C`,
`usable_fraction`, `usable_fraction_unavailable_reason`, `deliverable_wh`

- [x] `BATTERY_FREEZE_K = 200.0` → `-73.15 °C`; kaynak dizesi `"assumption:"` ile başlar
- [x] Sıcak uç `bat_op_min_c`; LPR-1/VIPER'da 0 °C ⇒ NASA'nın rating sıcaklığıyla çakışır
- [x] `bat_op_min_c ≤ BATTERY_FREEZE_C` (LUVMI-M) ⇒ `None` + gerekçe, değer uydurmaz
- [x] Belgedeki "%85 / %60" hiçbir yere yazılmaz; gerekçesi docstring'de
- [x] `exponent` parametresi (şekil varsayımı), varsayılan 1,0

### Task 1 — ısıtıcı kalibrasyonu ve JSC çapraz kontrolü

**Files:** `backend/app/battery.py`, `backend/test_battery.py`
**Produces:** `heater_coefficients`, `heater_power_w`, `heater_power_w_grid`,
`jsc_survival_temperature_check`

- [x] Ortam = **YÜZEY**, iç hedef değil (K3'ün ölümcül işaret dönmesi)
- [x] `radiative` = JSC'nin `εσA(T⁴−T_env⁴)`'ü; `delta_t` = belgenin doğrusal biçimi
- [x] `[0, p_heater_w]`'ye kırpılır; `constant` eski terimi aynen döndürür
- [x] `jsc_survival_temperature_check()` 270 K→250 K'da **%26,50** verir, JSC'nin %26'sıyla
      karşılaştırılıp fark yazılır
- [x] Dört profilde de kalibrasyon var (LUVMI-M dahil — ofset haritası kullanılmıyor)

### Task 2 — hibernasyon, dawn pre-heat, dinamik dayanım

**Files:** `backend/app/battery.py`, `backend/test_battery.py`
**Produces:** `hibernation_available`, `hibernate_dark_rate`, `survival_envelope`,
`dawn_preheat`, `shadow_endurance_h`, `HIBERNATION_EVIDENCE_LIMIT`

- [x] `dawn_preheat` saat döndürür (`/3600` — `exit_time_h:298` ile aynı)
- [x] `T_eq ≤ zarf_alt` ⇒ NaN değil, **gerekçeli reddetme**
- [x] `shadow_endurance_h` oransal: tam şarj + rating'te **dört profilde de** yayımlanan sabit
- [x] LUVMI-M `p_hibernate_w=None` ⇒ `unavailable` + gerekçe
- [x] Kanıt sınırı: < 80 K ya da > 14 gün ⇒ `beyond_cited_evidence`

### Task 3 — paylaşılan enerji fonksiyonlarına `heater_w`

**Files:** `cost_engine.py`, `cost_vec.py`, `cost_cube.py`, `backend/test_battery.py`
**Produces:** `heater_w=None` × beş imza, ikizler aynı işlem sırasında

- [x] `heater_w=None` ⇒ `np.array_equal` eski çağrıyla; ifade karakter karakter eski
- [x] **Eksik kilit ekleniyor:** ikiz testi dört rover × dört gölge oranı × ısıtıcı
      verili/verilmemiş, `==` ile (bugünkü `test_review_fixes.py:340` yalnız eğimi süpürüyor)
- [x] `compute_cost_grid` DOKUNULMAZ; `COST_MODEL_ID` v5 kalır
- [x] `python test_cost_engine.py` doğrudan koşturulur (pytest toplamıyor)

### Task 4 — `pathfinder_4d`: izleme, dinamik eşik

**Files:** `pathfinder_4d.py`, `backend/test_battery.py`
**Produces:** `track_inner`, `battery_model`, durum bağımlı dayanım eşiği

- [x] `track_inner = enforce_dwell or derate`; sentinel `0.0` yalnız ikisi de kapalıyken
- [x] Binleme (`dark_quantum_h`, `dark_tol`, `endurance_finite`) **yayımlanan sabitte** kalır
- [x] Eşik `new_battery` üzerinde değerlendirilir, gelen `battery_wh` üzerinde değil
- [x] Derate kapalıyken çarpma hiç yapılmaz (C1'in "ifadeyi yeniden yazma" dersi)

### Task 5 — `pathfinder_4d`: atomik `HIBERNATE` kenarı

**Files:** `pathfinder_4d.py`, `backend/test_battery.py`
**Produces:** üçüncü kenar ailesi, `hibernate_unwakeable`, `path_actions`, metrikler

- [x] Atomik: tek kenar `(r,c,t) → (r,c,t+d)`; **altıncı etiket ekseni yok**
- [x] Giriş `exposure ≥ _DARK_RATIO_THRESHOLD`; çıkış dilimi **aydınlık** (NASA'nın kuralı)
- [x] Karanlık saati durmaz: `dark_h += saat × p_hibernate_w / p_shadow_w`
- [x] Zarf askıya alınmaz, `survival_envelope` ile **değiştirilir**, **her ara dilimde** kontrol
- [x] `hibernate_unwakeable` → `REJECTION_KEYS` + `no_path_reason_4d` + **`lead` demeti (:176)**
- [x] `path_actions` döner; `wait_steps` hibernasyonu bekleme saymaz
- [x] Sezgisel: kenar maliyeti ≥ 0, mesafe kapatmaz ⇒ kabul edilebilirlik korunur

### Task 6 — `survival`, `stress_test` (ve bilinçli olarak yapılmayan ikisi)

**Files:** `survival.py`, `stress_test.py`, `backend/test_battery.py`
**Produces:** `heater_w` geçişi, `path_actions` okuma

- [x] B1: `_power_terms(heater_w)` skaler girer, afin kapalı form **bozulmaz**; alan ısıtıcıyı
      yayımlanan azamisinde çeker (ufku plandan uzun, orada yüzey yok — muhafazakâr)
- [x] B5: `route_legs(actions=…)` + `RouteLegs.is_hibernate`; uyku `p_hibernate_w` çeker ve
      karanlık bütçesini dormant hızında harcar. `actions` verilmezse rota C2 öncesi gibi okunur
- [x] Survival önbellek anahtarına ısıtıcı bayrağı eklendi (iki istek yalnız modelde farklıysa
      `_CACHE_LIMIT = 2` yüzünden biri öbürünün alanını kullanıyordu)
- [x] `test_stress_test_runs.py` SHERPA↔planlayıcı yeniden üretim kilidi bozulmaz
- [ ] ~~`simulation.simulate_path(heater_w)`~~ — **yapılmadı, gerekçesi spec § Bulunanlar 11**:
      2-B yolda dilim başına yüzey yok, yarım bağlamak iki farklı istatistiği karıştırırdı
- [ ] ~~`safe_haven.route_margins` teslim edilebilir enerji~~ — **yapılmadı, aynı gerekçe**;
      sınır gizlenmedi, `battery.route.margins_use_nameplate_charge: true` ile yanıtta söylendi

### Task 7 — API

**Files:** `main.py`, `backend/test_battery_api.py`
**Produces:** üç bayrak, `battery` bloğu, `GET /api/battery-model`, önbellek anahtarı

- [x] `applied = bool(requested and artefact is not None)` (A1/A2/B1/C6/C1 kuralı)
- [x] Beş 422: iç sıcaklık yok / LUVMI-M donma çelişkisi / `heater_model` uyumsuz /
      `p_hibernate_w=None` / kernel-epoch yok
- [x] `/api/plan` bloğu `reason: "the 2-D cost grid has no epoch"`
- [x] **Survival önbellek anahtarına** üç bayrak eklenir (C1'in `solar_gain`'i gibi)
- [x] Varsayılan yanıtta blok `applied: false`, mevcut alanların hiçbiri değişmez

### Task 8 — katalog dürüstlük düzeltmeleri

**Files:** `constants.py`, `backend/test_battery.py`
**Produces:** `:21` yorumu, `thermal_tau_s` sınıflaması, C6 kaynak dizesi

- [x] `thermal_tau_s` → `MODELLED_FIELDS`, **ve** `rover_catalog()`'a üst düzey anahtar
      (API'den kaybolmasın — bu bir EKLEME)
- [x] `HEATER_THERMOSTAT_ASSUMPTION_SOURCE` W-to-K katsayısını anar (bugün "yok" diyor)
- [x] `test_review3_fixes.py:636` ve `test_panel.py:315-322` yeşil kalır

### Task 9 — gerçek grid testleri

**Files:** `backend/test_battery_real_grid.py`
**Produces:** skip-korumalı testler

- [x] Skip muhafızı altı dosyadaki metinle birebir aynı
- [x] Bit-eşitlik: üç bayrak kapalı ⇒ standart rotalar kıpırdamaz
- [x] **Bayrak-AÇIK kilidi:** yeni modelin eskisinden farkı yazılı bir iddia olarak pinlenir
- [x] Muhafızın gerçekten geçtiği (atlanmadığı) doğrulanır

### Task 10 — rapor betiği ve rapor

**Files:** `scripts/battery_hibernation_report.py`, `docs/research/battery_hibernation_report.md`
**Produces:** ölçüm betiği ve raporu

- [x] Bölümler: (1) kaynakların söyledikleri + JSC çapraz kontrolü, (2) katalog kalibrasyonu
      ve ima edilen alanlar, (3) "karanlık ≠ soğuk" ölçümü, (4) üç ısıtıcı modelinin işaretli
      farkı, (5) eğri şekli süpürmesi, (6) dayanım: katalog tutarsızlığı ve oransal model,
      (7) hibernasyon: dört profilin sıralaması + rota etkisi, (8) iddia sınırı
- [x] `--json` önce yazılır, `--from-json` ölçmeden yeniden render eder, veri yoksa yazmadan çıkar

### Task 11 — dokümanlar, tam paket, tek commit

**Files:** `docs/frontend/3b-veri-sozlesmesi.md`, `README.md`, araştırma belgesi, spec sonu
**Produces:** C2 eki, README satırı, ✅ + "Yapıldı" bloğu, "Uygulama sırasında bulunanlar"

- [x] Sözleşme eki `## Değişmeyenler`'den ÖNCE, `git diff --numstat` ile silme yok doğrulanır
- [x] `cd backend && python -m pytest -q` tam paket; FAILED listesi referansla `comm`'lanır
- [x] `ruff check backend/app backend/test_battery*.py scripts/battery_hibernation_report.py`
- [x] Tek commit, eş-yazar satırı yok, push yok
