# LunaPath Backend Enhance — Full A+B Integration Audit

Denetim tarihi: 2026-09-07 · Dal: `main` @ `ab25ca9` · Denetçi: V&V oturumu (Claude Code + Claude-in-Chrome)

Bu dosya `docs/frontend/backend-enhance-entegrasyon-denetimi.md` yolunda duruyor, **git'e eklenmemiş
(untracked) ve commit edilmemiştir.** Denetim boyunca depoda hiçbir dosya değiştirilmedi, hiçbir
commit veya push yapılmadı — talimat "yalnız test et ve rapor çıkart" idi.

---

## 1. Executive Summary

Oniki özelliğin tamamı frontend'de temsil ediliyor ve büyük çoğunluğu tarayıcıda gerçek backend
verisiyle doğrulandı. Bilimsel bütünlük (provenance, iddia sınırı, kategorik/sürekli ayrımı, NaN,
"unavailable ≠ error", "mission infeasible ≠ network failure") **sistematik olarak korunmuş** — bu
denetimin en güçlü bulgusu. Açık kalan boşluklar planlayıcı kontrol yüzeyinde ve bir backend
kararlılık hatasında toplanıyor.

| Sonuç | Adet |
|---|---|
| PASS | 7 (A4, A1, B5, D3, C4, D2, C3) |
| PARTIAL | 4 (B3, A2, B2, C6) |
| FAIL | 0 |
| BACKEND-UNAVAILABLE | 0 |
| B1 | PARTIAL (katman/hücre var, planlayıcı kısıtı yok) |
| Düzeltilen kusur | **0** — kullanıcı talimatı gereği yalnız test + rapor; kod değiştirilmedi |
| Açık kusur | 10 (1 kritik backend; 5 planlayıcı yüzeyi: B2-1, B2-2, B1-1, C6-1, A2-1; 1 kullanılmayan uç: D3-1; 3 minör) |

**Planlayıcı kontrol yüzeyindeki boşlukların ortak kökü.** Beş eksikten ikisi (B2 `risk_alpha`,
C4'ün 4-B yolundaki `w_roughness`) kontrol yokluğu değil, **tek bir tip hatası**: 4-B kısıt sözlüğü
`PlanConstraints` yalnız `boolean` taşıyor (`useTimeAxis.ts:33`), oysa katkı mekanizması sayısal
kısıtlar için `Number.isFinite` arıyor. Contributor'lar doğru yazılmış ve 4-B builder onları
gerçekten yokluyor; sözlük tipi zinciri kesiyor. A2 `lit_rule`'da kanal kurulu ama çağıranı yok
(§10). Yalnız ikisi (B1 β, C6 termal zarf) gerçekten hiç yazılmamış kontroller — kısıt anahtarları
`frontend/src` genelinde sıfır referans. Bu ayrım düzeltme maliyetini değiştirdiği için her biri
kendi bölümünde kanıtla gösteriliyor; "eksik mi, yoksa bu oturumun kapasite koşullarında sessiz mi"
sorusu snake_case tel adıyla değil camelCase kısıt anahtarıyla ayrıldı.

Yüzde vermiyorum: aşağıdaki 12 özellik × 10 boyutluk matris tek meşru sayım ve tablo hâlinde §4'te.

**Tek kritik bulgu:** backend, eşzamanlı SPICE isteklerinde önce sessizce bozuluyor sonra çöküyor
(`SPICE(BADSUBSCRIPT) ... procedure "trcpkg"`). Bu, zaman bağımlı altı özelliği "unavailable"
gösterebiliyor ve `/api/comm-window`'u 500'e düşürüyor. Kusur backend'de; frontend'de maskelenmemeli.

---

## 2. Baseline & Environment

| | |
|---|---|
| Dal / commit | `main` @ `ab25ca9` (Merge `goktug/tuna-backend-A`), çalışma ağacı temiz, **hiç commit/push yapılmadı** |
| Backend | `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --env-file ../.env`, sistem Python 3.11 |
| Frontend | `npm run dev` — Vite 5.4.21, port 3000, `/api → 127.0.0.1:8000` |
| Tarayıcı | Chrome + Claude eklentisi, 1568×750 görünüm |
| Veri/önbellek | SPICE çekirdekleri ✅, `horizon_map.npy` (69 MiB) ✅, DEM klonları **20** ✅, roughness+PSR ✅, termal zarf (288 kutu) ✅ |

### Baseline test sonuçları (main, bu oturumda ölçüldü)

| Komut | Sonuç |
|---|---|
| `npm run typecheck` | exit 0, temiz |
| `npm run lint` | exit 0, temiz |
| `npx vitest run` | **38 dosya / 427 test**, hepsi geçti, ~8.8 s |
| `npm run build` | exit 0, 241 modül, ~15.5 s |
| `python -m pytest -q` (backend) | **tamamlanmadı** — ~%94'te bellek baskısı nedeniyle süreç sonlandırıldı; sonuç bu raporda yok |

**Backend süiti hakkında (önceden var olan koşul).** Koşu ~%94'e kadar ilerledi ve bellek baskısı
nedeniyle sonlandırıldı; bu bir test hatası değil, ortam sınırı — süit `~2,133` test için ~2.6 GB RSS
istiyor ve bu makinede aynı anda backend sunucusu, Vite ve tarayıcı da ayaktaydı. Sayılar alınamadığı
için bu rapor hiçbir backend test sonucunu denetime atfetmiyor; zaten kod değiştirilmediği için
atfedilebilecek bir şey de yok. Tekrar ölçmek gerekirse süit tek başına, sunucular kapalıyken
koşturulmalı.
Bilinen yerel koşul kayda geçirilir: `backend/test_plan_4d_real_grid.py` bu makinede
`start/goal falls in coarse block (r, c) at coarsen=4, which is not traversable` biçiminde düşüyor.
Sebep 5 m/px çözünürlükte `coarsen=4` bloğunun 20 m'ye yayılması ve içinde eğim sınırını aşan ince
hücre bulunması — modül `metadata.json` yoksa tümüyle atlandığı için CI yeşil. Log'un ulaştığı son
noktada, %94 işaretinde, `FF.F` deseni (üç başarısız) görüldü; bu koşulla sayıca uyumlu, ancak koşu
sonlandırıldığı için **nihai toplam değildir** ve rapor hiçbir yerde kesin sayı iddia etmiyor.

**Bu, §15 ve §16'daki kırmızı hata metinlerini okumanın anahtarıdır.** `/api/survival` ve
`/api/plan-4d`'nin bu oturumda döndürdüğü 422'ler
("goal (150, 290) falls in coarse block (37, 72) at coarsen=4, which is not traversable")
**aynı kök nedene** sahiptir: yerel veri koşulu, entegrasyon kusuru değil. Frontend'in yaptığı iş
(gerekçeyi olduğu gibi göstermek, sıfır uydurmamak) doğrudur; kısıtın kendisi bu rota/çözünürlük
çiftinde sağlanamamıştır. B1'in planlayıcı kontrolü eksikliği (§15) bundan **bağımsız** bir bulgudur
— aşağıda tip düzeyinde kanıtlanıyor.

**Baseline uyarısı (mevcut, denetimden önce de vardı):** `three-vendor` chunk'ı **621.41 kB**,
`chunkSizeWarningLimit: 550` — her build "Some chunks are larger than 550 kB" uyarısı basıyor
(exit 0). CI'da frontend job'ı yok; bu dört kontrol yalnız elde koşuyor.

### Tarayıcı baseline (§3.3)

LANDING → Launch → hangar (4 rover) → PLAN → START/GOAL → Generate Route → ANALYZE → playback →
2D/3D → Systems → AI asistanı: **tamamı çalışıyor**. Konsol temiz (yalnız Vite + React DevTools
bilgi mesajı; hiç error/warning yok).

---

## 3. API Coverage

### 3.1 On üç yeni uç

| Uç | Çağrılıyor? | Sonuç | UI tüketicisi | Durum | Not |
|---|---|---|---|---|---|
| `GET /api/earth-series` | Evet | 200, `model: spice_horizon`, `time_varying: true` | `features/earth-visibility`, `mission/capability`, `net/analysis` | ✅ | Katman + site link oranı sparkline'ı |
| `GET /api/comm-window` | Evet | 200 (`visible_now`, `minutes_remaining`, `next_change_utc`) | `useEarthVisibility`, `mission/missionTime` | ✅ | Hücre seçiminde otomatik; bozuk SPICE durumunda **500** (§23-B1) |
| `GET /api/safe-haven` | Evet | 200 — 22 837 haven hücresi, `safe_haven_fraction 0.115` | 25 referans; `useCellDetail`, `plan-request/contributors`, registry | ✅ | Dört ikili katman |
| `POST /api/stress-test` | Evet | 200, 1000 koşum 33–54 s | `features/stress-test` | ✅ | Wilson GA + histogramlar |
| `GET /api/uncertainty-series` | Evet | 200, `clone_horizon`, 20 klon | `net/analysis` | ✅ | Systems → Illumination uncertainty |
| `POST /api/dem-uncertainty` | Evet (kod) | Tarayıcıda **çalıştırılmadı** | `net/uncertainty` — "Price on the clone ensemble" düğmesi | ⚠️ | Düğme var, bu oturumda tetiklenmedi |
| `POST /api/safety-check` | **Hayır** | — | **0 referans** | ⚠️ | Kasıtlı görünüyor: `safety_margins` zaten `/api/plan` ve `/api/plan-4d` yanıtında geliyor; bu uç serbest telemetri izi denetimi için ve cockpit'in böyle bir izi yok. Yine de §13'ün istediği 422 senaryoları (zaman geri gitmesi, NaN, bilinmeyen motor) hiçbir yerden tetiklenemiyor. |
| `GET /api/illumination-corridor` | Evet | 200, `spice_horizon`, koridor bloğu | `features/illumination-corridor` (13 referans) | ✅ | `lit_rule` yalnız bu uçta parametre |
| `POST /api/risk-sweep` | Evet (kod) | Tarayıcıda **çalıştırılmadı** | `features/risk-sweep`, `net/riskSweep` | ⚠️ | "Plan at α 0.5, 0.9, 0.99" düğmesi mevcut |
| `GET /api/psr-validation` | Evet | 200 — Jaccard 0.8295, recall 0.9827, precision 0.8418 | `features/psr-validation` | ✅ | Systems'te birebir aynı sayılar |
| `GET /api/survival` | Evet | Bu rota için **422** ("leg safe set needs goal_row/goal_col" / hedef bloğu geçilemez) | 94 referans; `coarse-fields` | ✅ | 422 gerekçesiyle kart içinde gösteriliyor |
| `GET /api/thermal-dwell` | Evet | 200 — medyan dwell 0.55 h, %73 cold-limited | `coarse-fields`, `useBinaryField` | ✅ | `max_dwell_h` / `side` / `open_ended` |
| `GET /api/thermal-envelope` | Evet | 200 — 288 kutu (19 unlimited / 173 cold / 13 hot) | `features/thermal-envelope` | ✅ | Isı haritası |

### 3.2 Mevcut uçların eklentileri

| Uç | Doğrulanan | Durum |
|---|---|---|
| `POST /api/plan` | Yanıtta `safety_margins`, `slip_model`, `risk`, `roughness`, `uncertainty` — beşi de geliyor ve **beşi de UI'da render ediliyor**. İstekte `weights.w_roughness: 0.15` ve (açıkken) `risk_alpha` | ✅ |
| `POST /api/plan-4d` | Yanıt: `uncertainty`, `safety_margins`, `illumination_corridor`, `slip_model`, `risk`, `roughness`, `survival`, `thermal_dwell` + **13 durum dizisi, hepsi eşit uzunlukta (9/9)** | ✅ blok / ⚠️ istek (aşağı bkz.) |
| `POST /api/compare` | Her profilde `safety_margins` ("No violations"), `safety_margin_ranking` ("Lowest weighted cost") ve **`largest_min_margin_profile`** ("RECOMMENDED · Safest envelope") | ✅ |
| `POST /api/plan-multi` | Compare ile aynı yol; ayrı UI girişi yok | ✅ (dolaylı) |
| `GET /api/cell-telemetry` | `cost_breakdown` **beş kriter** (Slope/Energy/Shadow/Thermal/**Roughness w 0.150**), `roughness_m`, `f_roughness`, `in_psr`, `layer_validity`, haven/survival/dwell alanları istek üzerine | ✅ |
| `POST /api/replan` | Systems'te "Replan Triggers" paneli: Actual/Planned SoC, Actual/Predicted inner °C, Drift, Lateral offset, Corridor half-width, **Earth visibility left (min)**, Position 1σ, Map progress, Odometer claim | ⚠️ panel var, bu oturumda çalıştırılmadı |
| `POST /api/pose` | Cockpit'te tetikleyici bulunamadı | ⚠️ |
| `GET /api/rovers` | `slip_model` ve `declared_only` API'de mevcut; UI slip'i rota sonucundan gösteriyor | ✅ / ⚠️ (0–25° eğri grafiği yok) |
| `GET /api/terrain`, `/api/layers` | 7 yeni katmanın **hepsi** "Analysis overlays" menüsünde, her biri kendi provenance uyarısıyla | ✅ |

---

## 4. Feature Matrix

| Feature | Planner | Layer | Time | Route Result | Cell | Analysis | Provenance | Error | Tests | Final |
|---|---|---|---|---|---|---|---|---|---|---|
| **A4** Earth visibility | ✅ chip | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **PASS** |
| **A1** Safe Haven | ✅ chip | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 404→infeasible | ✅ | **PASS** |
| **B5** Monte Carlo | n/a | n/a | n/a | ✅ | n/a | ✅ | ✅ | ✅ | ✅ | **PASS** |
| **B3** DEM uncertainty | n/a | ✅ 4 katman | ✅ | ✅ | — | ⚠️ çalıştırılmadı | ✅ | ✅ | ✅ | **PARTIAL** |
| **D3** Formal safety | n/a | n/a | n/a | ✅ 12 gereksinim | n/a | ✅ | ✅ | ⚠️ 422 yolu yok | ✅ | **PASS** |
| **A2** Illumination corridor | ✅ chip / ❌ `lit_rule` | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | ✅ | ✅ | **PARTIAL** |
| **C3** Slip | n/a | n/a | n/a | ✅ | n/a | ✅ | ✅ MODEL | ✅ | ✅ | **PASS** |
| **B2** CVaR | ⚠️ 2-B ✅ / 4-B ❌ | n/a | n/a | ✅ | n/a | ⚠️ sweep çalıştırılmadı | ✅ | ✅ | ✅ | **PARTIAL** |
| **C4** Roughness + PSR | ✅ w_roughness | ✅ 2 katman | n/a | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **PASS** |
| **D2** MoonPlanBench | n/a | n/a | n/a | n/a | n/a | ✅ | ✅ | n/a | ✅ | **PASS** |
| **B1** Survival | ❌ | ✅ | ✅ | — | ✅ | ✅ | ✅ | ✅ | ✅ | **PARTIAL** |
| **C6** Thermal | ❌ | ✅ | ✅ | ✅ (blok) | ✅ | ✅ | ✅ | ✅ | ✅ | **PARTIAL** |

---

## 5. A4 — Earth Visibility

**Status: PASS**

**Ne çalışıyor.** `earth_visibility` katmanı "Analysis overlays"da; Systems'te Earth visibility kartı
("Earth below the horizon", EARTH ELEVATION 4.63°, TERRAIN HORIZON 10.45°, AZIMUTH 73.9°, CELL 362,89,
LINK FRACTION sparkline, "%56.6 of the site has a link on 2026-09-07"); hücre seçiminde otomatik
`/api/comm-window`; planlayıcıda **"Earth link"** chip'i.

**Browser evidence.** Chip açıkken `POST /api/plan-4d` gövdesinde `require_earth_visibility: true`.
Chip kapalıyken alan **hiç yok**.

**Network evidence.** `GET /api/comm-window?row&col&utc` → 200, `visible_now: true`,
`minutes_remaining: 13800.0`, `next_change_utc: 2027-06-08T14:00:00Z`, `search_limited: false`.

**Semantic verification.** `minutes_until_visible: null` durumu **"No rise inside the searched
14 days"** olarak gösteriliyor — sıfıra çevrilmiyor. Arama sınırı açıkça yazılı: "Bounded by a 14-day
search at 30-minute steps. A change beyond that horizon is not reported — it is not ruled out."
İddia sınırı: "Line-of-sight geometry only. Says nothing about link budget or antenna pointing."
Üst bardaki "Data link ACTIVE" **backend bağlantısı**; DTE durumu ayrı yerde ve ayrı dille anlatılıyor.

**Problems found.** Uzun süre çalışan sunucuda SPICE bozulunca `/api/comm-window` **500** dönüyor
(bkz. §23-B1). Bu bir backend kusuru; frontend onu transport hatası olarak gösteriyor ki doğru.

---

## 6. A1 — Safe Haven

**Status: PASS**

**Ne çalışıyor.** `/api/safe-haven` dört ikili katmanı tek çağrıda veriyor; planlayıcıda **"Haven
deadline"** chip'i; Monte Carlo karar metni haven kuralını rapor ediyor.

**Browser evidence.** Chip açıkken `require_safe_haven: true` gönderiliyor. Sonuç **404** ve UI şunu
gösteriyor:

> Start (89, 123) cannot reach a safe haven before the Earth sets: **inf h** to the nearest haven
> against 84.15 h of link left (the shortest gated coarse route needs…)

**Semantic verification.** Bu §7.5'in tam karşılığı: kısıt altında rota yok → **mission infeasible**,
"request failed" değil. Ulaşılamaz haven **`inf`** olarak yazılıyor — 0 saat değil (§7.1 PASS).
Mevcut 2-B rotası ekranda kaldı (§5.3 "optional analysis failure route'u silmez").

**Network evidence.** `/api/safe-haven?start_utc=2027-05-30&rover_id=nasa_viper` → `safe_haven_cells:
22837`, `safe_haven_fraction: 0.115`, `time_to_haven_finite_fraction: 0.9917` — OZET §4-A1'in
ölçümüyle birebir.

**Remaining gaps.** `time_to_safe_haven` katmanının haritada NaN renklendirmesi bu oturumda ayrıca
görsel olarak doğrulanmadı (kart üzerinden `inf` semantiği doğrulandı).

---

## 7. B5 — SHERPA Monte Carlo

**Status: PASS**

**Lifecycle.** idle → **"Executing…"** (belirsiz spinner) + **Cancel** bağlantısı → sonuç.
**Sahte yüzde yok.** Rota süresince ekranda kaldı. İki farklı rotada iki farklı sonuç alındı
(rota A: süre 3.2–10.3 h / min batarya 29.1–92.9 %; rota B: 0.8–6.7 h / 32.0 %).

**Sonuç kapsamı.** "REACHED THE GOAL 100.0 %" · "1000 runs · **95% CI 99.6–100.0%**" (Wilson) ·
"Full success 0.0%" · **DURATION histogramı** · **LOWEST BATTERY histogramı** (ikisi de backend'in
kendi bin'leri) · backend karar metni birebir:

> 1000/1000 runs reached the goal (95% CI 99.6-100.0%), 1000/1000 without touching the reserve;
> 0/1000 with every margin intact (95% CI 0.0-0.4%). No safe haven is reachable from any state of
> this route on this lunar day, so the haven rule fails every run.

**Kritik semantik.** Panelin altında sabit uyarı:

> **A completion rate is not a safety verdict.** The planner returned this route; this is how often a
> perturbed execution of it finishes.

**Network evidence.** `POST /api/stress-test` gövdesi: `path_states` (297 / 33), `coarsen: 1`,
`slice_hours` rotadan türetilmiş, `n_runs: 1000`, `seed: 0`. 2-B rotasından `path_states` üretimi
frontend'de yapılıyor — makul bir uyarlama.

**Remaining gaps.** Kesinti istatistikleri, arıza nedenleri, time-to-sun-shadow / time-to-DSN-shadow /
time-to-0-SOC dağılımları panelde görünmüyor (backend bunları döndürüyor). Bilgi kaybı, sessiz değil —
ama §11'in listesi tam karşılanmıyor.

---

## 8. B3 — DEM Uncertainty

**Status: PARTIAL**

**Statik katmanlar.** Dördü de "Analysis overlays"da, **her biri doğru rozetle**:

| Katman | UI açıklaması |
|---|---|
| P(traversable) | "Share of NASA's DEM clones that call this cell passable for this rover." + "0 and 1 are both certain; only 0.05–0.95 is disagreement." |
| Slope σ (ours) | "…computed with np.gradient. **DERIVED, not measured.**" |
| Elevation σ (NASA) | "**NASA's error MODEL (toterr), not a measurement** and not our ensemble." |
| Slope σ (NASA) | "**NASA's error MODEL (slperr).** Ranges about three times wider than our ensemble — **not the same quantity.**" |

Bu, §12'nin "NASA kaynağı otomatik olarak MEASURED demek değildir" şartının tam karşılığı.

**Zaman serisi.** Systems → "Illumination uncertainty [20 CLONES]": sparkline, Mean P(lit) 0.928/0.931,
Uncertain now %5.3/%2.3, Worst slice. Açıklama: "'Uncertain' is a cell where the clones disagree —
0.05 < P < 0.95. The mean alone cannot distinguish a confident…"

**Limitation.** Systems → DEM uncertainty kartı: Clones 20, Site11, near-field 1.000 m, slope limit 25°
ve kritik cümle: "**Held fixed across every clone: thermal field, far-field horizon, Earth visibility.
A band read off these layers is uncertainty in the terrain, not in the mission.**" — §12'nin "her
çevresel büyüklüğün oynatıldığı ima edilmemeli" şartı karşılanıyor.

**Rota analizi.** Analysis sekmesinde "DEM Uncertainty · P traversable 1.00 / min 1.00 (rota A),
min 0.95 (rota B) · Clones 20" + **"Price on the clone ensemble"** düğmesi.

**Problems found.** `POST /api/dem-uncertainty` bu oturumda tetiklenmedi; p5/p50/p95 bandının
grafik olarak gösterildiği doğrulanamadı. → **PARTIAL** sebebi budur, kod eksikliği değil.

---

## 9. D3 — Formal Safety

**Status: PASS**

**Browser evidence.** Safety sekmesi: "Formal Safety Margins", "REQUIREMENTS VIOLATED **7/9 met**",
"Tightest **LP-R05** -61.90 degC", ve **on iki gereksinimin tamamı** ID + ad + ρ + birim ile:

| ID | Ad | ρ |
|---|---|---|
| LP-R01 | shadow endurance | +46.82 h |
| LP-R02 | soc reserve | +68.15 pct |
| LP-R03 | soc recovery | +6.00 h |
| **LP-R04** | electronics thermal | **−51.90 degC** (ihlal, kırmızı) |
| **LP-R05** | battery thermal | **−61.90 degC** (ihlal, kırmızı) |
| LP-R06 | step slope | +6.16 deg |
| LP-R07 | cross slope | +6.16 deg |
| LP-R08 | dte while moving | **Not checked** |
| LP-R09 | safe haven leg | **Not checked** |
| LP-R10 | goal reached | 0.00 m |
| LP-R11 | soc at goal | +68.15 pct |
| LP-R12 | thermal dwell | **Not checked** |

Negatif ρ ihlal (kırmızı bar sola), pozitif ρ marj (yeşil bara sağa) — eksen "violation | 0 | margin".

**Semantic verification.** Panel altında: **"3 untested — which is not passed."** ✅ §13'ün "blok
yoksa PASS gösterme" şartı. "Requirement text and claim in the mission report." — iddia sınırı
raporda taşınıyor. UI hiçbir yerde "proven / verified / model checked" demiyor.

**Problems found.** `POST /api/safety-check` frontend'de hiç çağrılmıyor (0 referans). §13'ün
istediği geçersiz girdi senaryoları (zaman geri gidiyor, NaN, bilinmeyen motor, RTAMT yok → 422)
UI'dan tetiklenemiyor. Rota içi `safety_margins` yolu tam çalıştığı için bunu FAIL saymadım.

---

## 10. A2 — Illumination Corridor

**Status: PARTIAL**

**Ne çalışıyor.** `GET /api/illumination-corridor` 200 ve `shadow_model: spice_horizon,
time_varying: true`; koridor bloğu voksel/budama/bileşen/rota alanlarıyla geliyor. Planlayıcıda
**"Stay lit"** chip'i `require_continuous_illumination: true` gönderiyor (doğrulandı). Feature
`lit_rule` ve `lit_rule_definition`'ı ekranda gösteriyor.

**Problems found.**
1. **`lit_rule` operatöre açık değil.** Diğer eksiklerden farklı olarak burada **kanal zaten kurulu**:
   `CorridorParams.litRule` alanı ve onu tele koyan satır mevcut
   (`net/analysis.ts:522` ve `:534` → `query.set('lit_rule', params.litRule)`). Eksik olan tek şey
   çağıran:

   ```
   $ grep -rn "litRule" frontend/src --include=*.ts --include=*.tsx | grep -v net/analysis.ts
   (çıktı yok)
   ```

   Hiçbir yer `litRule` geçirmediği için backend varsayılanı (`all`) her zaman yürürlükte.
   Planlayıcı isteğine de eklenmiyor. §14'ün "iki semantiği UI'da açıkla ve seçtir" şartı yarım:
   **açıklama var, seçim yok** — feature yürürlükteki kuralı `lit_rule` /
   `lit_rule_definition` olarak dürüstçe gösteriyor (`illumination-corridor/index.tsx:163`), yani
   operatör hangi kuralın geçerli olduğunu görüyor, sadece değiştiremiyor. Taşıma katmanı hazır
   olduğu için kalan iş bir seçici ve bir parametre geçişi.
2. Zaman kaydırıcısıyla koridor küpünün dilim dilim güncellendiği bu oturumda görsel olarak
   doğrulanamadı (koridor overlay'i bu rota için açılmadı).

**Doğru olan.** 422 (statik aydınlanma) ve 404 (koridor altında rota yok) ayrımı backend'de var ve
frontend'in hata sınıflandırıcısı (`net/errors.ts`) `infeasible` / `invalid-request` /
`data-unavailable` / `transport` / `analysis-failure` olarak ayırıyor.

---

## 11. C3 — Slip

**Status: PASS**

**Browser evidence.** Safety sekmesi → "Route Cost Model" → **MOBILITY · SLIP [MODEL]**:
Mean slip **0.14**, Max slip **0.73 at 18.8°**, Wheel dist. **1.18×**, ve
**"0.49 h ⚡ 185 Wh added by slip"** — üçü de backend'in `slip_model.route` bloğundan.
Açıklama: "Slip is the share of wheel rotation that does not become forward motion. At 0.14 mean,
the wheels turn 1.18× the ground distance."

**Semantic verification.** Rozet **MODEL**; hiçbir yerde "measured" geçmiyor. Enerji/süre etkisi
backend delta'sından alınıyor, istemci tarafında yeniden hesaplanmıyor (kodda ayrı bir slip formülü
yok).

**Remaining gaps.** `/api/rovers`'taki 0–25° slip tablosu **eğri grafiği** olarak çizilmiyor;
`declared_only.regolith` UI'da hiç görünmüyor. İkisi de "gösterilmiyor" durumu — yanlış gösterim yok,
dolayısıyla PASS'i düşürmedim.

---

## 12. B2 — CVaR

**Status: PARTIAL**

**Ne çalışıyor.** Systems (PLAN modu) → **Advanced Constraints** → **Risk appetite** toggle'ı.
Kapalıyken: **"None enabled — the plan request is unchanged."** Açıkken: α sürgüsü **0.900** ve
**"1 field added to the plan request."**

**Network evidence.**

```
POST /api/plan     → { …, "risk_alpha": 0.9 }          ✅
POST /api/plan-4d  → risk_alpha ABSENT                  ❌
```

**Problem found — B2-1.** Risk appetite açıkken bile `risk_alpha` **4-B planlayıcıya gönderilmiyor**.
Backend `Plan4DRequest.risk_alpha`'yı destekliyor.

Bu bir "kapasite kapalı olduğu için katkı vermedi" durumu **değil**; tip düzeyinde imkânsızlık.
`riskContributor` `PLAN_REQUEST_CONTRIBUTORS` içinde ve 4-B builder `applyPlanRequestContributors`
(`useTimeAxis.ts:264`) onu gerçekten yoklıyor. Zincir tek yerde kopuyor:

```ts
// features/time-axis/useTimeAxis.ts:28-34 — 4-B kısıt sözlüğünün tipi
export interface PlanConstraints {
  requireEarthVisibility: boolean
  requireSafeHaven: boolean
  requireIlluminationCorridor: boolean
  [key: string]: boolean          // <-- yalnız boolean
}

// features/plan-request/contributors.ts:289-291 — sayısal contributor'ın açılma koşulu
const raw = context.constraints[contributor.constraintKey]
if (contributor.control.kind === 'number') {
  return { enabled: typeof raw === 'number' && Number.isFinite(raw), value: raw }
}
```

`constraints` yalnız boolean taşıyabildiği için `typeof raw === 'number'` bu yolda **asla** doğru
olamaz. Kısıt anahtarı (`riskAlpha`) sözlüğe yazılmıyor değil — sözlüğün tipi onu **taşıyamıyor**.
Ayrıca panelin çizdiği `CONSTRAINT_CONTROLS` (`TimeAxisPanel.tsx:13-18`) yalnız üç boolean anahtar
içeriyor, yani operatör tarafında da giriş noktası yok.

**Aynı kusurun ikinci kurbanı — B2-2 (yeni).** `roughnessWeightContributor` da
`control.kind: 'number'` ve `constraintKey: 'wRoughness'`. Yorumu açıkça "**4-D builder only**" diyor,
ama tam olarak aynı sebeple 4-B yolunda hiçbir zaman etkinleşemez: `w_roughness` `POST /api/plan-4d`
gövdesine giremez. C4'ün beşinci maliyet kriteri 2-B'de RoutePriorities üzerinden çalışıyor (§13'te
doğrulandı), 4-B'de ise kod niyetini beyan ettiği halde ulaşılamaz durumda.

Düzeltmenin şekli tek satırlık: `PlanConstraints`'in indeks imzasını `boolean | number` yapmak (ya da
sayısal kısıtlar için ayrı bir alan açmak) ve panele karşılık gelen kontrolü koymak. Bu denetimde
**değişiklik yapılmadı.**

**Semantic verification (doğru olan).** Safety sekmesinde **RISK APPETITE [MODEL]** kartı:
"**Nominal.** The cost grid is the ordinary one, bit for bit. Switch on Risk appetite under Advanced
Constraints (Systems, in plan mode) to rank routes on the adverse tail instead." — α'nın **sıralamayı**
değiştirdiği, fiziği değiştirmediği açıkça yazılı. α = 0.5'in "nominal" olduğu ima edilmiyor;
kapalıyken alan gönderilmiyor.

**Remaining gaps.** `POST /api/risk-sweep` düğmesi ("Plan at α 0.5, 0.9, 0.99") mevcut ama bu
oturumda çalıştırılmadı; risk matrisi ısı haritası doğrulanmadı.

---

## 13. C4 — Roughness + PSR

**Status: PASS**

**Roughness.**
- Katman: "Analysis overlays → Roughness" · rozet **MEASURED** · uyarı "**A 100 m block statistic
  shown on 5 m cells, not each cell's own roughness.**"
- Haritada blok blok görünüyor (50 m/px istatistiğinin 5 m'ye postalanmış hâli) — beklenen davranış.
- Rota sonucu: **ROUGHNESS [MEASURED] [scale MODEL]** — Mean 0.84 m, Max 1.52 m, In PSR 0,
  "100 m baseline · weight 0.15". İki ayrı rozet, OZET'in "katman ölçülmüş, [0,1] ölçeği MODEL"
  ayrımını birebir taşıyor.
- Planlayıcı ağırlığı: hangar'daki "Route priorities" beşinci sürgü **Surface Roughness 0,150**;
  `POST /api/plan` gövdesinde `weights.w_roughness: 0.15` doğrulandı.
- Hücre kartı: Cost Breakdown **beş kriter** — Slope w 0.409 → 0.103, Energy w 0.259 → 0.125,
  Shadow w 0.142 → 0.035, Thermal w 0.190 → 0.188, **Roughness w 0.150 → 0.138**, toplam 0.589.

**PSR.**
- Katman: "PSR mask · NASA PGDA permanently shadowed regions, 20 m product." + **"Measured evidence
  and a check on our shadow model. Not a forbidden region."**
- **Zorunlu negatif test (§17): PASS.** PSR görselini açmak istemci tarafında yasak bölge üretmiyor;
  UI bunu ayrıca yazıyor: "It is NOT a planning input -- VIPER's science targets are inside PSRs and
  the thermal gate already blocks them."
- Doğrulama paneli (Systems): JACCARD **0.830**, PSR RECALL **98.3%**, DARK PRECISION **84.2%**,
  PSR CELLS **14 016 / 250 000**, MEDIAN COLDEST INSIDE **−183.1 °C** / OUTSIDE **−98.6 °C**,
  rozetler "psr MEASURED · shadow_ratio DERIVED".
- **Backend ile karşılaştırma:** `GET /api/psr-validation` → jaccard 0.8295091…, psr_recall 0.98273…,
  dark_precision 0.84177…, n_psr 14016. **UI birebir aynı**, istemci tarafında hesap yok.

**Minör gözlem.** Cockpit'teki (ANALYZE/PLAN sol ray) "Route priorities" **dört** sürgü gösteriyor;
beşinci (roughness) yalnız hangar'da düzenlenebiliyor. Değer yine de isteğe giriyor, dolayısıyla veri
kaybı yok — ama iki ekran arasında asimetri var.

---

## 14. D2 — MoonPlanBench

**Status: PASS**

Canlı uç yok, uydurulmadı. Compare sekmesinde salt-okunur kanıt görünümü:

- 10° → **33.3% vs 100%** · "8 of 12 maps are connected only by cutting a corner between two blocked cells."
- 15° → **91.7% vs 100%** · "1 of 12 maps…"
- 20° → **100.0% vs 100%** · "No map depends on cutting a corner; the two models agree."
- "Under the benchmark's own motion model, LunaPath reproduces the paper's shortest-path lengths
  exactly (**651.81 · 636.16 · 620.24**)."

**CLAIM BOUNDARY** kutusu (tam metin ekranda): occupancy-only, 320 m–7 680 m hücre, "Success here
measures connectivity under a motion model, **not rover route planning**", "The benchmark's reference
planners allow diagonal moves between two occupied cells; LunaPath refuses them", "**Every paper
figure is a quotation from arXiv 2512.21438v1, not our measurement.**"

Atıf: `docs/research/moonplanbench_report.md · arXiv 2512.21438v1 (quoted)`.
Koşulsuz "%100 başarı" iddiası **hiçbir yerde yok**.

---

## 15. B1 — Survival / Recovery

**Status: PARTIAL**

**Ne çalışıyor.**
- `GET /api/survival` katmanı Systems → **"Survival & dwell"** kartından haritaya bağlanıyor
  (rozetler **MODEL** + **LAG UNCALIBRATED**, "Show on map" onay kutusu).
- Alan seçici: **P(safe) · Best action · Max dwell · Envelope side**.
- **P(safe)**: "Chance the rover reaches the safe set from this block." + "A computed policy (MODEL),
  not an observation. **Needs an epoch, a state of charge and a goal.**"
- **Best action**: "What the recovery policy would do from each block." + **"Categorical, not a scale.
  Drawn as four discrete kinds, never as a gradient."** → §7.3 PASS.
- Mission clock bağlantısı: "At **T+0.0 h** on the mission clock."
- Bu rota için survival hesaplanamadı ve **gerekçesi kart içinde kırmızı olarak** yazıldı:
  "goal (150, 290) falls in coarse block (37, 72) at coarsen=4, which is not traversable."
  → §7.4 PASS (unavailable ≠ error), sıfır uydurulmadı.

**Problem found — B1-1 (eksik planlayıcı entegrasyonu).** Şans kısıtı hiçbir yerden açılamıyor.
`frontend/src/` genelinde referans sayıları:

```
max_failure_probability   1  (yalnız contributors.ts yorum satırında)
report_survival           0
failure_rate_per_km       0
recovery_hours            0
survival_soc_bins         0
survival_safe_set         0
survival_horizon_hours    0
```

`PLAN_REQUEST_CONTRIBUTORS` beş girdi taşıyor (A4, A1, A2, C4, B2) — B1 yok. Yani §19'un istediği
"β infeasible → 404 → mission infeasible" senaryosu UI'dan üretilemiyor ve `survival` bloğu rota
sonucunda hiç doldurulmuyor.

**"Yok" mu, "kapasite kapalı olduğu için sessiz" mi?** Bu ayrım önemli, çünkü `contributors.ts`
bilinçli olarak bir kapı taşıyor: bir kontrol var olabilir ve kapasitesi yokken doğru biçimde hiçbir
şey katmayabilir — ikisi de aynı istek gövdesini üretir. Ayırt edici kontrol, tel üzerindeki
snake_case alan adı değil **camelCase `constraintKey`**'dir:

```
$ grep -rn "requireSurvival\|survivalBeta\|maxFailureProbability\|requireThermalDwell" frontend/src
(çıktı yok)
```

Hiçbiri mevcut değil. Kısıt anahtarı hiç tanımlanmamış, dolayısıyla kapatılabilecek bir kapasite
kapısı da yok: bulgu **"eksik"**tir, "bu oturumun koşullarında kapalı" değil. §2'de anlatılan yerel
veri koşulundan (422) bağımsızdır.

**Kaynak varsayımları.** Arıza oranı ve kurtarma süresinin varsayım olduğu kart metninde
("A computed policy (MODEL), not an observation") genel olarak taşınıyor; `assumption:` kaynak
dizeleri ayrıca gösterilmiyor.

---

## 16. C6 — Thermal Envelope + Dwell

**Status: PARTIAL**

**Ne çalışıyor.**
- `GET /api/thermal-dwell` → Survival & dwell kartında **MEDIAN DWELL 0.79 h (p5 0.44 · p95 3.00)**,
  **COLD-LIMITED 90.2%**, **HOT-LIMITED 0.0%**, **OPEN-ENDED 9.8% "clipped to 24 h"**.
- **`open_ended` semantiği doğru:** "Open-ended blocks never leave the envelope inside the 24 h
  lookahead, so their dwell reads **24 h as a floor — 'at least', not 'exactly'**." Sonsuza
  çevrilmiyor. → §20 PASS.
- **Envelope side kategorik:** "Which limit the inner temperature reaches first." +
  "**Categorical.** 'Stays inside' is why a dwell reads 24 h — it is a floor, not a value."
  Lejant sayılarla: Stays inside 1 757 (%15.4), Cold limit 7 910 (%69.4), Hot limit 1 735 (%15.2).
- `GET /api/thermal-envelope` → thermal-envelope feature'ı (288 kutu; 19 unlimited / 173 cold-limited /
  13 hot-limited). Systems metni JSC eksen farkını **açıkça** anlatıyor: "JSC's envelope axes …
  need a rover body model LunaPath does not have; ours are Sun elevation × Sun-parallel slope from
  heat1d's transient — the same method on our model, **not a comparison**. JSC's numbers are quoted,
  never mixed with a measurement."
- Isıtıcı semantiği: "The heater has no sourced W-to-K link; `heater_model='thermostat_assumed'` is an
  explicit **assumption** and the default is `'none'`."
- Rota sonucu: `thermal_dwell` bloğu ve `path_inner_c` / `path_max_dwell_h` / `path_dwell_margin_h` /
  `path_stay_hours` dizileri `/api/plan-4d` yanıtında mevcut ve uzunlukları hizalı.
- D3'teki LP-R04/LP-R05 ihlalleri gizlenmiyor (−51.90 / −61.90 °C).

**Problem found — C6-1 (eksik planlayıcı entegrasyonu).** `require_thermal_dwell`, `initial_inner_c`
ve `heater_model` **planlayıcı isteğine hiç eklenmiyor**; `initial_inner_c` / `heater_model` yalnız
`/api/thermal-dwell` ve `/api/thermal-envelope` sorgu parametresi olarak kullanılıyor
(`net/analysis.ts:432-434`). Yani operatör termal zarfı kısıt olarak açamıyor ve "ısıtıcı varsayımı"
seçimi planlamayı etkilemiyor.

**"Yok" mu, "kapalı" mı — B1'deki ayrımın aynısı.** `requireThermalDwell` kısıt anahtarı
`frontend/src/` genelinde hiç yok. Var olan tek `thermalDwell` tanımlayıcısı planlayıcı kısıtı değil,
hücre telemetrisinin sorgu seçeneği:

```
frontend/src/api.ts:487              thermalDwell?: boolean
frontend/src/api.ts:505              if (options.thermalDwell) query.set('thermal_dwell', 'true')
features/mission-context/useCellDetail.ts:66     thermalDwell: startUtc !== null,
```

`GET /api/cell-telemetry?...&thermal_dwell=true` ile `POST /api/plan-4d` gövdesindeki
`require_thermal_dwell` **farklı şeylerdir**; birincisi bir hücre hakkında bilgi ister, ikincisi
rotayı kısıtlar. Kapasite kapısı değil, kontrol yokluğu.

**Entrenchment / replan.** Systems'te "Replan Triggers" paneli `entrenched_hours` dâhil alanları
taşıyor ve "Leave a field blank to report that value as unavailable — the check that needs it comes
back **'Not checked', not 'Clear'**" diyor; `POST /api/replan` bu oturumda çalıştırılmadı.

---

## 17. Route Profile / Playback Audit

`POST /api/plan-4d` (baseline, doğrudan API) yanıtında **on üç durum dizisi** ve **hepsi 9 elemanlı**:

```
path_pixels 9 · path_pixels_coarse 9 · path_states 9 · path_battery_pct 9 · path_dark_hours 9
path_earth_visible 9 · path_time_to_haven_h 9 · path_hours_until_earthset 9 · path_haven_margin_h 9
path_stay_hours 9 · path_max_dwell_h 9 · path_dwell_margin_h 9 · path_inner_c 9
```

`path_survival_prob` ve `path_recovery_prob` yanıtta **null** — survival istenmediği için; dizi
uzunluğu uyuşmazlığı değil, doğru "yok" davranışı.

**Playback.** Waypoint sayacı (001/297, 001/033, 001/025) rota ile birlikte değişiyor; MISSION TIME,
SPEED, COVERED, BATTERY, SLOPE alt bantta canlı. Playback başlığı ile rota segmenti aynı rotayı
gösteriyor. **Index drift gözlenmedi.**

**Mission time.** Kaydırıcı +138.0 h'e çekildiğinde Güneş satırı
`Sun: 0.01° elevation · 165.3° grid azimuth · **2026-09-12T18:00:00Z**` oldu — başlangıç
`2026-09-07T00:00:00Z` + 138 h ile **tam uyumlu**. `illumination-series` tek çağrıda 24 dilim ×
6 saat çekiliyor ve kaydırma istemci tarafında dilim indeksliyor (gereksiz istek yok). Coarse alanlar
"At T+X h on the mission clock" ile aynı saate bağlanıyor.

---

## 18. Cell Telemetry Audit

| Backend alanı | Frontend'de |
|---|---|
| row/col, lon/lat, altitude_m | ✅ "Surface picker telemetry" |
| thermal_c | ✅ Surface temp |
| `cost_breakdown` (5 kriter + total) | ✅ "Cost Breakdown" paneli, ağırlıklarla birlikte |
| `roughness_m`, `f_roughness` | ✅ (Safety → ROUGHNESS kartı: Mean/Max) |
| `in_psr` | ✅ ("In PSR 0") |
| `layer_validity` | ✅ Systems → Layer Provenance |
| `safe_haven` + `safe_haven_model.reason` | ✅ (epok verilmezse "unavailable" gerekçesi) |
| `survival` / `best_action` | ✅ istek üzerine; bu rota için gerekçeli 422 |
| `thermal_dwell` | ✅ istek üzerine |

**İstek davranışı.** Hücre değiştikçe `cell-telemetry` + `comm-window` çiftleri gidiyor ve **eski
istekler `AbortController` ile iptal ediliyor** (audit log'da "THROW signal is aborted without
reason" kayıtları) — stale yanıt bağlanmıyor, her piksel hareketinde pahalı survival/dwell isteği
atılmıyor.

---

## 19. Semantic Integrity Matrix

| Kural | Durum | Kanıt |
|---|---|---|
| NaN ≠ 0 | **PASS** | Haven ulaşılamazlığı "**inf h**"; `minutes_until_visible: null` → "No rise inside the searched 14 days" |
| 320 m ≠ 5 m | **PASS** | Coarse alanlar blok blok çiziliyor, ince katmanlar 5 m; kart "coarsen=4" ve blok koordinatını (37,72) adıyla söylüyor |
| best_action kategorik | **PASS** | "Categorical, not a scale. Drawn as four discrete kinds, never as a gradient." |
| PSR otomatik kısıt değil | **PASS** | "Not a forbidden region." + "It is NOT a planning input"; overlay açmak rotayı değiştirmedi |
| MODEL ≠ MEASURED | **PASS** | slope σ (ours) DERIVED vs (NASA) MODEL vs roughness MEASURED + scale MODEL |
| monitored ≠ proven | **PASS** | Hiçbir yerde "proven/verified/model checked" yok; "3 untested — which is not passed." |
| completion ≠ safety | **PASS** | "A completion rate is not a safety verdict." |
| CVaR ≠ physics | **PASS** | "Changes which route is chosen, not what it costs to drive." |
| unavailable ≠ error | **PASS** | `capability.ts` tip düzeyinde ayırıyor; survival 422 kart içinde gerekçeyle |
| mission infeasible ≠ network failure | **PASS** | 404 → "Start (89,123) cannot reach a safe haven before the Earth sets: inf h …" |
| kapalı seçenek özelliği açmıyor | **PASS** | Baseline `/api/plan` ve `/api/plan-4d` gövdeleri yalnız eski alanları taşıyor; "None enabled — the plan request is unchanged." |
| ortak mission time | **PASS** | +138 h → `2026-09-12T18:00:00Z`; coarse alanlar "At T+X h on the mission clock" |
| stale sonuç koruması | **PASS** | Hedef değişip yeniden planlanınca Monte Carlo paneli düğmeye döndü, DEM belirsizliği yeniden hesaplandı |
| sahte ilerleme yok | **PASS** | "Executing…" + Cancel; yüzde yok |

---

## 20. Scientific Claim Audit

Sorunlu ifade **bulunamadı**. Aksine, iddia sınırları UI'nin kendisinde taşınıyor. Örnekler:

- A4: "Line-of-sight geometry only. Says nothing about link budget or antenna pointing."
- B3: "NASA's error MODEL (slperr). Ranges about three times wider than our ensemble — not the same quantity."
- C4: "A 100 m block statistic shown on 5 m cells, not each cell's own roughness."
- C6: "JSC's numbers are quoted, never mixed with a measurement."
- D2: "Every paper figure is a quotation from arXiv 2512.21438v1, not our measurement."
- D3: "3 untested — which is not passed."
- B5: "A completion rate is not a safety verdict."
- ROS: "Not a live connection. These run in a ROS 2 Jazzy environment beside the backend; the browser
  has no bridge to them."
- Reality Check: "This route's rate is its simulated traverse clock only — it excludes the lunar
  nights the published rates are averaged over, so the two columns are not the same measurement."

Düzeltme gerektiren metin yok.

---

## 21. Non-Regression Results

| Alan | Sonuç |
|---|---|
| PLAN | ✅ START/GOAL seçimi (haritadan ve ROW/COL girişinden), Undo/Clear, Generate Route |
| SOLVING → ANALYZE | ✅ otomatik geçiş, Mission LOCKED |
| ANALYZE | ✅ dört sekme (Route/Safety/Analysis/Compare), risk dağılımı, milestone listesi |
| Playback | ✅ Play/Pause, 1×/10×/60×/300×, waypoint sayacı, canlı telemetri |
| 2D | ✅ 7 eski katman + 7 yeni analiz overlay'i, ölçek çubuğu 5 m/px, risk lejantı |
| 3D | ✅ First person / Orbit, LIDAR PERCEPTION paneli, LROC NAC fotoğraf overlay'i; **görev durumu, zaman ve rota korunuyor**; analiz overlay menüsü 3-B'de de açık |
| Replan | ✅ panel mevcut (çalıştırılmadı) |
| AI | ✅ açılıyor, **otomatik göndermiyor** — anlatım seviyesi (Basit/Mühendislik/Teknik) seçilene dek Gönder kapalı |
| Rover | ✅ dört profil, seçim, `slope_max_deg` katalogdan |
| Mevcut katmanlar | ✅ Surface/Slope/Aspect/Thermal/Shadow/Cost/Traverse |

**Not:** AI asistanına mesaj gönderilmedi — dış API çağrısı için ayrı onay gerekiyor.

---

## 22. Performance / Browser Console

- **Konsol: 0 error, 0 warning.** Yalnız `[vite] connected` ve React DevTools bilgi mesajı.
- WebGL/decode sorunu gözlenmedi; 3-B sahne 10 s içinde ayağa kalktı.
- Stress test 1000 koşum: 33.5 s (33 durum) – 53.8 s (297 durum). UI donmadı, Cancel aktif kaldı.
- `plan-4d` (kısıtlı, 256 dilim): 45.5 s. Belirsiz yükleme, rota ekranda kaldı.
- **Yinelenen istek (minör):** backend erişim log'unda birbirinin aynısı iki
  `GET /api/illumination-series?...n_slices=24&slice_hours=6&downsample=2` ardışık olarak görüldü.
  Bu **yalnız sunucu tarafı gözlemidir**; tarayıcı içi ölçüm aynı uçtan parametreleri farklı üç çağrı
  saydı, yani ikisi aynı istek değil de log'un farklı bir pencereyi göstermesi de mümkün. Tarayıcı
  tarafında doğrulanmadı; ağırlığı buna göre verilmeli.
- Stale istekler `AbortController` ile düzgün iptal ediliyor.
- **Layout (minör):** `div.app-shell` bazı durumlarda yatay kaydırma durumuna giriyor (1658 px
  görünümde sol ray ekran dışına kayabiliyor). Yeniden üretilebilir ama tetikleyicisi net değil.

---

## 23. Changes Made During Audit

**Hiçbir kod değişikliği yapılmadı.** Kullanıcı talimatı: "asla commit push yapma, sadece test yap ve
rapor çıkart". Çalışma ağacı denetim boyunca temiz kaldı (`git status --short` boş), HEAD `ab25ca9`.

Yapılan tek "değişiklik" bu rapor dosyasıdır ve **commit edilmemiştir**.

### Bulunan kusurlar (düzeltilmedi)

**B1 — kritik, backend.** CSPICE iş parçacığı güvenli değil; FastAPI senkron uçları thread pool'da
koştuğu için eşzamanlı SPICE çağrıları önce kernel havuzunu bozuyor, sonra süreci öldürüyor.

- Aşama 1 (sessiz bozulma): `SPICE(BADFRAMESPEC) — The frame to which frame 31001 is relatively
  defined is not recognized … 'MOON_ME_DE440_ME421'`. Sonuç: `earth-series` → `model: static,
  reason: "Earth visibility unavailable…"`, `safe-haven` → `model: unavailable`,
  `uncertainty-series` → `"Sun track unavailable"`, `illumination-corridor` → statik gölge,
  `comm-window` → **HTTP 500**.
- Aşama 2 (çökme): `SPICE(BADSUBSCRIPT): Subscript out of range on file line 1189, procedure
  "trcpkg". Attempt to access element 0 of variable "stack".` → uvicorn süreci öldü.
- **Kanıt:** aynı kod taze bir süreçte sorunsuz çalışıyor
  (`app.ephemeris.sun_vector_body` + `spkpos` başarılı, 5 çekirdek yüklü); yalnız uzun süre çalışan
  ve eşzamanlı istek alan sunucuda bozuluyor. İki kez yeniden üretildi; her restart sonrası tüm
  uçlar gerçek veriye döndü.
- **Not:** Bu, denetimin başında altı özelliği yanlışlıkla "BACKEND-UNAVAILABLE" gösterdi. Rapordaki
  tüm sonuçlar restart sonrası sağlıklı backend ile alınmıştır.

**B2-1 — `risk_alpha` 4-B planlayıcıya gitmiyor.** Yukarıda §12. Kök neden `PlanConstraints`'in
boolean-only indeks imzası; contributor tarafı doğru.

**B2-2 — `w_roughness` de aynı sebeple 4-B'ye giremiyor.** Yukarıda §12. Kod yorumu "4-D builder
only" diyor, davranış tam tersi.

**B1-1 — şans kısıtı (β) planlayıcı kontrolü yok.** Yukarıda §15. Kısıt anahtarı hiç tanımlanmamış —
kapasite kapısı değil.

**C6-1 — termal zarf planlayıcı kontrolü yok.** Yukarıda §16.

**A2-1 — `lit_rule` operatöre kapalı.** Yukarıda §10.

**D3-1 — `POST /api/safety-check` hiç kullanılmıyor.** Yukarıda §9.

**Minör-1 — cockpit'te dört sürgü, hangar'da beş.** Yukarıda §13.

**Minör-2 — yinelenen `illumination-series` isteği** ve **Minör-3 — app-shell yatay kayması.**
Yukarıda §22.

---

## 24. Remaining Gaps

### Frontend missing
1. B1 şans kısıtı: `max_failure_probability`, `report_survival` ve beş yardımcı alan için kontrol yok.
2. C6 planlayıcı kısıtı: `require_thermal_dwell`, `initial_inner_c`, `heater_model` plan isteğine girmiyor.
3. B2: `risk_alpha` 4-B isteğine eklenemiyor — ve aynı tip hatası yüzünden `w_roughness` de.
   Tek satırlık düzeltme: `PlanConstraints`'in indeks imzası `boolean | number` (§12).
4. A2: `lit_rule` (all/majority) seçilemiyor.
5. C3: `/api/rovers` slip tablosu eğri grafiği olarak çizilmiyor; `declared_only.regolith` gösterilmiyor.
6. B5: kesinti istatistikleri, arıza nedenleri ve time-to-* dağılımları panelde yok.
7. D3: `POST /api/safety-check` için giriş yolu yok (422 senaryoları test edilemiyor).

### Backend defect (frontend'de maskelenmemeli)
8. CSPICE eşzamanlılık hatası — sessiz "unavailable" ve süreç çökmesi (§23-B1).

### Known backend limitation (dokunulmadı, doğru şekilde taşınıyor)
9. Planlayıcı saat/batarya uyumsuzluğu, termal zarf ihlalinin sürmesi, ısıtıcı varsayımı,
   LPR-1'in Site11'de haven'ı olmaması, ay gecesi rotasının β altında uygulanamazlığı, termal CVaR
   yokluğu — hepsi UI metinlerinde ya da backend yanıtlarında dürüstçe görünüyor.

### Doğrulanamayan (bu oturumda çalıştırılmadı)
10. `POST /api/dem-uncertainty`, `POST /api/risk-sweep`, `POST /api/replan`, `POST /api/pose`,
    AI asistanına gerçek soru (sonuncusu kasıtlı: harici API çağrısı onay gerektiriyor).
11. **Backend `python -m pytest -q` taban ölçümü** — ~%94'te bellek baskısıyla sonlandı (§2).
    Süit tek başına, backend sunucusu ve Vite kapalıyken tekrar koşturulmalı.

### Low-priority visual
12. Cockpit/hangar sürgü asimetrisi; app-shell yatay kayması; yinelenen illumination-series isteği.

---

## 25. Final Sign-Off

**Are all 12 backend features represented in the frontend appropriately?** — **PARTIAL.**
Oniki özelliğin tamamı görünür ve doğru anlatılıyor; dördünün planlayıcı yüzeyi eksik (B1, C6 tamamen;
B2 4-B'de; A2 `lit_rule`).

**Are all 13 new API endpoints accounted for?** — **YES.** On ikisi kullanılıyor,
`POST /api/safety-check` kasıtlı olarak kullanılmıyor ve gerekçesi bu raporda.

**Are existing endpoint extensions accounted for?** — **YES** (`/api/plan`, `/api/plan-4d`,
`/api/compare`, `/api/cell-telemetry`, `/api/terrain`, `/api/layers` doğrulandı;
`/api/replan` ve `/api/pose` yalnız kod düzeyinde).

**Does disabling advanced features preserve old behavior?** — **YES.** Hem `/api/plan` hem
`/api/plan-4d` baseline gövdeleri yalnız eski alanları taşıyor; UI bunu ayrıca beyan ediyor
("None enabled — the plan request is unchanged").

**Is scientific validity/provenance preserved?** — **YES.** §19 ve §20'deki tüm kurallar PASS.

**Are error/unavailable semantics correct?** — **YES.** 404 → mission infeasible, 422 → gerekçeli
kart, eksik veri → "unavailable" + neden, transport → ayrı sınıf.

**Is route/time/playback state coherent?** — **YES.** Diziler hizalı, mission time tek eksende,
stale analiz korunuyor.

**Has the existing LunaPath theme/workflow been preserved?** — **YES.** Koyu havacılık teması,
tipografi, canvas hâkimiyeti, risk renkleri ve kademeli açılım korunmuş; kalıcı kart patlaması yok.

**Is this integration ready to be called complete?** — **NO.** Bloklayan liste:

1. **CSPICE eşzamanlılık hatası** (backend) — sunucuyu düşürüyor ve özellikleri sahte biçimde
   "unavailable" gösteriyor. Diğer her şeyin üstünde.
2. **B1 şans kısıtı planlayıcı kontrolü** — özelliğin planlayıcı yarısı erişilemez.
3. **C6 termal zarf planlayıcı kontrolü** — aynı.
4. **4-B kısıt sözlüğünün boolean-only tipi** — `risk_alpha` ve `w_roughness` bu yüzden
   `POST /api/plan-4d` gövdesine giremiyor. Operatör açtığını sanıyor, 4-B rotası nominal.
   Beş bloklayan madde içinde en ucuzu: `PlanConstraints`'in indeks imzası.
5. **A2 `lit_rule` seçimi.**

Bunlar kapandığında entegrasyon "tamamlandı" denebilir; geri kalan boşluklar (D3 safety-check girişi,
slip eğrisi, B5 ek dağılımlar) tamamlayıcı iyileştirmelerdir.
