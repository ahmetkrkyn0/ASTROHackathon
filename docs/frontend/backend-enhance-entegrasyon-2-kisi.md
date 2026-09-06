# LunaPath Backend Enhance → Frontend Entegrasyonu — 2 kişilik çalışma planı

> Bu doküman, 3 kişilik entegrasyon planının iki kişiye uyarlanmış halidir. Uyarlama
> "C track'ini ikiye bölelim" değildir: mevcut kod tabanı incelenmiş, bölme gerçek
> çakışma yüzeylerine göre yeniden çizilmiştir. Orijinal planın bilimsel dürüstlük
> kuralları aynen korunur; değişen şey iş dağılımı, sıra ve kapsam disiplinidir.

---

## 0. Orijinal plandan farklar — özet

| Konu | Orijinal plan | Bu plan |
|---|---|---|
| Kişi sayısı | 3 track (A/B/C) | 2 track (A/B), C dağıtıldı |
| Repo varsayımı | "hiçbir yapı varsayma" | Yapı incelendi, dosya sahipliği isimle verildi |
| Backend | Var kabul ediliyor | **Bizim branch'te yok** — merge Faz 0'ın işi |
| Shared foundation | 8 madde sıfırdan | 4'ü zaten kodda var, 4'ü yazılacak |
| Milestone | M0–M10 (11 faz) | F0–F4 (5 faz) |
| Kapsam | 12 feature × 20 DoD, hepsi zorunlu | Aynı 12 feature, **öncelik katmanlı** (§9) |
| Çakışma yönetimi | Genel öğütler | Somut dosya kilidi + `.gitattributes` (§6) |

---

## 1. Doğrulanmış zemin

Aşağıdakiler tahmin değil, bu repo üzerinde kontrol edildi. Plana başlamadan önce
herkesin bildiğini varsaydığı ama doğru olmayan şeyler bunlar.

### 1.1 O backend bizim branch'imizde yok

| | `ahmet/rover&frontend` (HEAD) | `origin/berke-3d-backendEnhance` |
|---|---|---|
| 13 yeni endpoint | **0** | **13** |
| `docs/frontend/3b-veri-sozlesmesi.md` | 326 satır | **1620 satır** |
| B2 / C4 / B1 / C6 sözleşmeleri | yok | var |

Planın §4'te "authoritative source" dediği sözleşme de, uygulanacak backend de o
branch'te. **Adım sıfır kod yazmak değil, merge.**

### 1.2 Merge'ün gerçek boyutu

```
merge-base : d401854  (3 Eylül 2026)
HEAD       : +125 commit
enhance    : +12 commit
enhance'in dokunduğu frontend dosyası : 0
```

Çakışma yüzeyi tamamen backend'de ve **dört dosya**:

```
backend/app/constants.py
backend/app/main.py          ← asıl iş
backend/app/scenarios.py
backend/requirements.txt
```

Göktuğ'un AI modülleri (`ai_*.py`, `report.py`, `profile_comparison.py`) o branch'te
yok — çünkü branch onlar eklenmeden önce ayrıldı, silinmediler. Üç yollu merge onları
korur. Dikkat gereken tek yer `main.py`: onların sürümünde AI router bağlantısı
olmayacak. Orijinal planın §23'ü ("mevcut AI assistant korunacak") tam olarak burada
kazanılır veya kaybedilir.

### 1.3 Tek boğaz: `App.tsx:650`

`frontend/src/App.tsx` (1164 satır, CRLF) `missionValue` nesnesini tek elden kuruyor.
Yeni mission state'i buraya eklemek, iki kişinin **her gün** aynı dosyada çakışması
demektir. Bu planın en önemli mimari kararı §6'da: **Faz 0'dan sonra kimse App.tsx'e
dokunmaz.**

### 1.4 Altyapının yarısı zaten yazılmış

Orijinal planın §5'te sıfırdan istediği primitiflerin bir kısmı kodda mevcut:

| Plan maddesi | Kodda karşılığı | Durum |
|---|---|---|
| §5.2 provenance sunumu | `features/layer-provenance/` | **var** — genişletilecek |
| §5.6 layer metadata | `mission/useTerrainManifest.ts` | **var** — çözünürlük alanı eklenecek |
| §5.8 ortak mission-time | `features/time-axis/useTimeAxis.ts` | **kısmen** — feature-local, paylaşıma çıkarılacak |
| katman seçimi | `features/layer-picker/` | **var** — yeni katmanlar kaydedilecek |
| §5.1 capability modeli | — | yazılacak |
| §5.3 semantic error | — | yazılacak |
| §5.4 route identity | — | yazılacak |
| §5.5 binary pipeline | `net/terrain.ts` içinde kısmi | genişletilecek |

### 1.5 İsim tuzağı

`frontend/src/features/corridor/` **rota koridoru**dur (yarı genişlik, eğim, enerji —
`/api/plan` yanıtındaki `corridor` bloğu). A2'nin *illumination corridor*'ı **değildir**.
A2 yeni bir feature klasörüne gider: `features/illumination-corridor/`. Aynı isme iki
anlam yüklemek bu planın yasakladığı şeyin ta kendisi.

### 1.6 En ucuz iş: zaten gelen bloklar

Sözleşmeye göre şu bloklar **her plan yanıtında, istek alanı gerekmeden** geliyor:

- `risk` bloğu (her zaman) — B2
- `roughness` bloğu (her zaman) — C4
- `survival` bloğu (her zaman, plan-4d) — B1
- `thermal_dwell` bloğu (her zaman, plan-4d) — C6
- `safety_margins` — D3, dört planner endpoint'inin hepsinde
- `slip_model` — C3

Yani merge biter bitmez **altı feature'ın veri tarafı bedava gelir**; iş sadece
parse etmek ve göstermektir. Yeni endpoint çağırmak, yeni istek alanı göndermek,
yeni katman indirmek gerekmez. Bu, planın tamamındaki en yüksek getirili iştir ve
sıralama buna göre yapılmıştır (§8).

---

## 2. Bölme mantığı

İki kişilik bölmede doğru soru "12 feature'ı 6+6 nasıl yaparız" değil, "**hangi
dikişte en az dosya paylaşırız**". Bu kod tabanında o dikiş nettir:

```
KİŞİ A                              KİŞİ B
Haritaya çizilen                    Rotadan çıkan
+ plan isteğine giren               + rotadan sonra gelen
─────────────────────               ─────────────────────
raster katmanlar                    route result blokları
zaman ekseni / cube'ler             post-route analiz job'ları
hücre telemetrisi                   rota profil dizileri + playback
çevresel kısıt anahtarları          kanıt / provenance sunumu
MapCanvas, layer-picker             route-analysis, mission-report
```

Kural: **bir feature'ın sonucunu kim gösteriyorsa, o feature'ın istek alanını da o
gönderir.** B1'in β kısıtı ve C6'nın termal alanları B'ye aittir, çünkü sonuç bloğu
B'de. A o feature'lardan yalnızca *katmanı* alır — bir `GET` katman isteği plan
`POST`'undan tamamen bağımsızdır, bu yüzden bölünebilir.

---

## 3. Faz 0 — Ortak zemin (paralel, ama feature yok)

Bu fazda iki kişi paralel çalışır ama **hiç aynı dosyaya dokunmaz**. Feature işi
başlamadan bitmesi gereken kapı budur.

### Kişi A — backend'i getir ve kanıtla

1. `origin/berke-3d-backendEnhance` merge'ü. Dört dosyayı çöz, `main.py`'da AI
   router bağlantısının hayatta kaldığını doğrula.
2. Backend'i ayağa kaldır, **13 endpoint'in her birine tek tek istek at**. Cevap
   vermeyen / cache isteyen hangisi, listele.
3. Her endpoint'in **gerçek yanıtını** `frontend/src/net/__fixtures__/` altına kaydet.
   İki kişi de bu fixture'lara karşı test yazacak. Sözleşmeden alan adı tahmin
   etmek yasak (orijinal §4); fixture bunu imkânsız kılar.
4. Hangi endpoint'in preprocessing cache'i olmadığı için `unavailable` döndüğünü
   yaz. Bu liste §5.1 capability modelinin girdisidir.

**Çıktı:** çalışan backend + 13 fixture + unavailable listesi.

### Kişi B — paylaşılan primitifleri yaz

Backend gerekmez; sözleşme dokümanı (merge'den sonra 1620 satır) yeter.

1. `.gitattributes` + satır sonu normalizasyonu (§6.1). **Tek başına, ilk commit.**
2. `mission/capability.ts` — §5.1 durum makinesi
   (`available | loading | ready | unavailable | unsupported | error | stale`).
   `unavailable ≠ error` ayrımı tip seviyesinde zorunlu olsun.
3. `net/errors.ts` — §5.3 semantic error taksonomisi. HTTP status → anlam:
   transport / invalid request / data unavailable / **mission infeasible** /
   analysis failure. 404'ün "İstek başarısız" olarak görünmesi bu dosyada engellenir.
4. `mission/routeIdentity.ts` — §5.4. Rota kimliği = rover + start + goal + weights
   + aktif ileri kısıtların hash'i. Post-analiz sonuçları bu kimliğe bağlanır;
   kimlik değişince stale olur, görsel katman değişince olmaz.
5. `features/analysis-job/` — §26 job yaşam döngüsü:
   `idle → running → success | failure | stale`. Sahte yüzde üretmesi **imkânsız**
   olsun (tipte `percent` alanı olmasın).
6. `App.tsx`'e **tek ve son dokunuş**: `missionTime` ve `routeIdentity` mission
   state'e eklenir. Bundan sonra App.tsx kapalıdır.

**Çıktı:** dört primitif + normalize edilmiş satır sonları + App.tsx'in son hali.

### Faz 0 kapısı — şu üçü doğru değilse paralel başlamaz

- [ ] Merge'den sonra mevcut PLAN → Generate → ANALYZE akışı bozulmadan çalışıyor
- [ ] AI assistant çalışıyor (§23)
- [ ] `npm run typecheck && npm test && npm run build` yeşil, baseline'dan kötü değil

---

## 4. Kişi A — Arazi, Kısıt ve Zaman

### Sahip olduğu feature'lar

| Kod | Feature | A'nın payı |
|---|---|---|
| A4 | Earth Visibility | **tam** — katman, seri, comm-window, kısıt |
| A1 | Safe Haven | **tam** — 4 katman, kısıt, NaN semantiği |
| A2 | Illumination Corridor | **tam** — cube, zaman dilimi, kısıt |
| C4 | Roughness + PSR | **tam** — 2 katman, `w_roughness`, psr-validation |
| B3 | DEM Uncertainty | **katman yarısı** — `p_traversable`, `slope_sigma`, `elevation_sigma`, `slope_sigma_nasa`, uncertainty-series |
| B1 | Survival | **katman yarısı** — `GET /api/survival` (`p_safe`, `best_action`) |
| C6 | Thermal Dwell | **katman yarısı** — `GET /api/thermal-dwell`, `GET /api/thermal-envelope` |
| — | Hücre telemetrisi | **tam** — tek panel, tek sahip |

### Endpoint'ler

```
GET  /api/earth-series          GET  /api/safe-haven
GET  /api/comm-window           GET  /api/illumination-corridor
GET  /api/uncertainty-series    GET  /api/psr-validation
GET  /api/survival              GET  /api/thermal-dwell
GET  /api/thermal-envelope      GET  /api/terrain
GET  /api/layers/{ad}           GET  /api/cell-telemetry
```

### Dosya sahipliği (A dışında kimse dokunmaz)

```
frontend/src/MapCanvas.tsx
frontend/src/colormap.ts
frontend/src/features/layer-picker/
frontend/src/features/layer-provenance/
frontend/src/features/time-axis/
frontend/src/features/mission-context/          ← hücre telemetrisi
frontend/src/features/illumination-corridor/    ← YENİ
frontend/src/features/safe-haven/               ← YENİ
frontend/src/mission/useTerrainManifest.ts
frontend/src/net/terrain.ts, series.ts
```

### A'nın taşıması gereken dört semantik

1. **NaN ≠ 0.** `time_to_safe_haven = NaN` → "Ulaşılabilir Safe Haven yok".
   `0.0 h` yazmak yalandır. Hiçbir NaN otomatik 0'a çevrilmez.
2. **320 m ≠ 5 m.** Coarse ürünler blok sınırlarını koruyarak çizilir, fine
   raster gibi gerilmez. `useTerrainManifest`'e native çözünürlük alanı eklenir.
3. **`best_action` kategoriktir.** Yön/bekle semantiği renk rampasına ezilmez.
4. **PSR yasak bölge değildir.** Katman açık diye path seçimi kısıtlanmaz;
   PSR analiz/doğrulama verisidir.

---

## 5. Kişi B — Rota Analizi ve Kanıt

### Sahip olduğu feature'lar

| Kod | Feature | B'nin payı |
|---|---|---|
| D3 | Formal Safety | **tam** — 12 requirement, `safety_margins`, safety-check |
| C3 | Slip | **tam** — rover modeli, rota bloğu, eğim-slip eğrisi |
| B2 | CVaR | **tam** — `risk_alpha`, `risk` bloğu, risk-sweep |
| B5 | Monte Carlo | **tam** — stress-test, histogram, fan chart |
| B3 | DEM Uncertainty | **rota yarısı** — `POST /api/dem-uncertainty`, p5/p50/p95 bandı |
| B1 | Survival | **rota yarısı** — β kısıtı, `survival` bloğu, recovery_suggestion |
| C6 | Thermal Dwell | **rota yarısı** — `thermal_dwell` bloğu, entrenchment |
| D2 | MoonPlanBench | **tam** — offline artifact |
| — | Rota profil dizileri + playback bağlama | **tam** |

### Endpoint'ler

```
POST /api/stress-test      POST /api/dem-uncertainty
POST /api/safety-check     POST /api/risk-sweep
POST /api/plan             POST /api/plan-4d
POST /api/compare          POST /api/plan-multi
POST /api/replan
```

### Dosya sahipliği (B dışında kimse dokunmaz)

```
frontend/src/features/route-analysis/
frontend/src/features/mission-report/
frontend/src/features/profile-compare/
frontend/src/features/playback/
frontend/src/features/replan/
frontend/src/features/cost-explain/
frontend/src/features/mission-validation/
frontend/src/features/safety-margins/     ← YENİ (D3)
frontend/src/features/stress-test/        ← YENİ (B5)
frontend/src/features/risk/               ← YENİ (B2)
frontend/src/net/plan4d.ts, compare.ts, replan.ts
```

### B'nin taşıması gereken beş semantik

1. **404 ≠ hata.** Kısıt altında rota yoksa: "No feasible route under selected
   mission constraints." Ekranda "Request failed" görünmesi kabul edilmez.
2. **`monitored ≠ proven`.** D3 STL robustness'tir. "Formally proven" veya
   "model checked" kelimeleri hiçbir yerde geçmez. Backend'in `claim` alanı varsa
   o gösterilir. Rho işareti korunur: pozitif = marj, negatif = ihlal.
3. **CVaR fizik değildir.** `risk_alpha` rota *sıralamasını* değiştirir, playback
   değerlerini "CVaR fiziği" diye sunmak yanlıştır. Risk kapalıysa alan **hiç
   gönderilmez** — `0.5` nötr değildir.
4. **Completion ≠ safety.** B5'in tamamlanma oranı, planner'ın rota döndürmüş
   olmasını geçersiz kılmaz ve route status'ü ezmez.
5. **MODEL ≠ MEASURED.** C3 slip ve C6 termal MODEL/UNCALIBRATED'dır. "Thermally
   validated" veya "measured South Pole slip" yazılmaz.

---

## 6. Çakışma yönetimi — somut kurallar

Bu bölüm iki kişilik çalışmanın en kritik parçasıdır. Genel öğüt değil, kural.

### 6.1 Satır sonları — Faz 0'ın ilk commit'i

Repoda `.gitattributes` **yok** ve dağılım en kötü haliyle şöyle:

```
frontend/src altında:  LF-only 126   CRLF-only 9   MIXED 1
```

Ve o 9 CRLF dosyanın içinde **App.tsx ve features/registry.ts** var — yani en çok
dokunulan paylaşılan dosyalar. `mission/types.ts` ise tek MIXED dosya. İki kişi
paralel çalışırken bu, hayalet çakışma üretir: kimsenin değiştirmediği satırlar
conflict olarak gelir.

**Yapılacak, feature işinden önce, tek commit:**

```
# .gitattributes
* text=auto eol=lf
*.png binary
*.jpg binary
*.glb binary
*.tif binary
```

sonra `git add --renormalize .` ve tek başına commit. Bu commit'in içinde başka
hiçbir şey olmayacak.

### 6.2 Kapalı dosyalar

Faz 0 bittikten sonra aşağıdakiler **kilitlidir**. Değişiklik gerekiyorsa iki kişi
konuşur, tek kişi yapar, küçük ve izole commit olarak önce merge edilir.

| Dosya | Neden | Kural |
|---|---|---|
| `App.tsx` | Tek mission state boğazı (§1.3) | Faz 0'dan sonra dokunulmaz |
| `App.css` (6146 satır) | Kaskad sırası kırılgan | **Yeni kural yazılmaz** — her feature kendi `.css`'ini alır |
| `mission/types.ts` | İki taraf da state eklemek ister | Faz 0'da bir kez, sonra kapalı |
| `net/types.ts` (342 satır) | İki taraf da tip eklemek ister | **Bölünür**: her feature tipini kendi klasöründe tanımlar |

### 6.3 Yeni state App.tsx'e gitmez

Kod tabanında doğru desen **zaten var**: `useCorridor`, `useTimeAxis`,
`useLayerProvenance` — hepsi `useMission()`'dan okur, kendi verisini kendi çeker,
kendi state'ini kendi tutar. Yeni feature'lar bu deseni izler.

`MissionValue`'ya yalnızca **iki** yeni alan girer, o da Faz 0'da: `missionTime` ve
`routeIdentity`. Başka hiçbir feature state'i oraya eklenmez.

### 6.4 Plan isteği — append-only katkı listesi

İki kişi de plan isteğine alan ekleyecek (A: çevresel kısıtlar, B: risk/survival/termal).
Ortak bir request builder'ı ikisi de düzenlerse her gün çakışır. Çözüm, kod tabanının
kendi `FEATURES` desenidir:

```ts
// features/plan-request/contributors.ts
export const PLAN_REQUEST_CONTRIBUTORS: PlanRequestContributor[] = [
  earthVisibilityContributor,   // A
  safeHavenContributor,         // A
  illuminationCorridorContributor, // A
  roughnessWeightContributor,   // A
  riskContributor,              // B
  survivalContributor,          // B
  thermalDwellContributor,      // B
]
```

Her contributor `{ enabled: boolean, fields(): object | null }` döndürür. `enabled`
false ise `null` döner ve **alan isteğe hiç girmez** — orijinal planın §2 non-regression
kuralı böylece tipte garanti altına alınır. Dosya append-only olduğu için çakışması
önemsizdir.

### 6.5 `features/registry.ts`

Append-only. İki kişi de listenin sonuna satır ekler; çakışma olursa ikisini de tut.
CRLF olduğu için §6.1 normalizasyonundan sonra sorun kalmaz.

### 6.6 Günlük ritim

- Gün başında ikisi de `main`'den (veya ortak entegrasyon dalından) rebase
- Feature dalları küçük ve sık merge edilir; iki gün açık kalan dal yoktur
- Paylaşılan primitif değişikliği ayrı, tek amaçlı commit olarak **önce** gider
- Vite pull'dan sonra yeniden başlatılır (stale module graph)

---

## 7. Fazlar

Orijinal M0–M10 iki kişi için beşe indirildi. Her fazda iki track paralel ilerler.

### F0 — Zemin
§3. Merge, fixture'lar, dört primitif, `.gitattributes`, App.tsx'in son hali.
**Kapı:** mevcut akış + AI assistant bozulmadan çalışıyor, testler yeşil.

### F1 — Bedava gelen her şey
En yüksek getirili faz. Yeni endpoint çağrılmaz.

- **A:** yeni katmanların `layer-picker`'a kaydı, manifest'e çözünürlük/validity
  alanları, `roughness` + `psr` + `earth_visibility` katmanlarının çizimi
- **B:** `safety_margins` (D3), `slip_model` (C3), `risk` (B2), `roughness` (C4)
  bloklarının parse'ı ve gösterimi — bunlar zaten her yanıtta geliyor (§1.6)

**Kapı:** bir rota çözüldüğünde D3'ün 12 requirement'ı ve slip özeti ekranda.

### F2 — Kısıtlar ve katmanlar
- **A:** A4 + A1 tam (katman, kısıt, NaN semantiği, comm-window), C4 `w_roughness`
- **B:** B2 `risk_alpha` + risk-sweep, B3 rota bandı (`POST /api/dem-uncertainty`)

**Kapı:** kısıt kapalıyken istek gövdesi F0'daki ile **birebir aynı** (non-regression testi).

### F3 — Zaman ve ağır analizler
- **A:** ortak `missionTime`'a bağlı earth-series / uncertainty-series /
  illumination-corridor (A2), thermal-dwell + survival katmanları
- **B:** B5 stress-test, B1 survival bloğu + β, C6 thermal bloğu + entrenchment, D2

**Kapı:** tek zaman sürgüsü tüm zamana bağlı katmanları sürüyor; ağır analiz
UI'yı kilitlemiyor.

### F4 — Sertleştirme
Hücre telemetrisi tamamlama, 2D/3D parity, hata durumları, §10 audit, performans.

---

## 8. Sıralama gerekçesi

F1'in bu kadar erken olmasının sebebi §1.6: altı feature'ın verisi merge ile birlikte
zaten geliyor. Bir hackathon takviminde "yeni endpoint bağlamadan altı feature'ın
sonucunu ekrana koymak" en yüksek getirili iştir ve demo değerinin çoğunu buradan
alırsınız. Ağır olanlar (A2 cube, B1 survival alanı, B5 Monte Carlo) sona bırakıldı
çünkü hem hesap hem UI maliyetleri yüksek.

---

## 9. Öncelik katmanları — zaman biterse

Orijinal plan §44'te 20 maddelik DoD ve §45'te tamamen yeşil bir matris şart koşuyor.
12 feature × 20 madde iki kişilik bir takvimde gerçekçi değildir. Kapsamı sessizce
düşürmek yerine önceliği açıkça yazıyoruz.

**Katman 1 — bunlar olmadan entegrasyon anlamsız**
D3 Formal Safety · C3 Slip · C4 Roughness+PSR · A1 Safe Haven · A4 Earth Visibility

Gerekçe: dördü yanıtta hazır geliyor, A1/A4 ise görsel olarak en anlatılabilir
olanlar ve NASA verisine dayanıyor.

**Katman 2 — belirgin değer, orta maliyet**
B2 CVaR · B5 Monte Carlo · B3 DEM Uncertainty · D2 MoonPlanBench

D2 aslında en ucuzu: statik bir kanıt kartı. Maliyeti düşük, güvenilirlik getirisi
yüksek.

**Katman 3 — ağır**
B1 Survival · C6 Thermal Dwell · A2 Illumination Corridor

Bunlar zamana bağlı cube ve uzun hesap içerir. Yetişmezse **katman yarısı**
(salt okunur harita katmanı) bırakılır, planner kısıtı bırakılmaz — yarım bir kısıt
yanlış rota üretir, yarım bir katman sadece daha az bilgi gösterir.

**Kural:** bir katman tamamlanmadan bir sonrakine geçilmez. "Hepsinden biraz"
12 yarım feature üretir; orijinal planın §48'i buna açıkça karşıdır.

---

## 10. Tema koruması — dikkat

Orijinal §38 şunu soruyor: *"Yeni feature canvas'ı küçültüyor mu? Onlarca permanent
card yaratıyor mu?"*

Bu proje son dönemde dashboard'dan **panel silerek** ilerledi (Active raster layer,
Mission context, "No route analysed yet" kaldırıldı). 12 feature'lık panel yükü bu
yönün tersidir. Karar:

- Yeni feature **varsayılan olarak kalıcı kart açmaz**
- Katman verisi → `layer-picker` + seçili hücre telemetrisi
- Rota sonucu → mevcut `route-analysis` / `mission-report` panellerinin içine blok
- Kanıt / doğrulama panelleri → **Systems & Evidence çekmecesi** (`group: 'systems'`)
- Kokpitin varsayılan hali feature sayısı arttıkça büyümez

`registry.ts`'teki `group: 'systems'` alanı tam olarak bunun için var; yeni
kanıt panelleri oraya kaydedilir.

---

## 11. Test ve kabul

### Her feature için asgari
1. **Contract testi** — Faz 0'da yakalanan gerçek fixture'a karşı parse
2. **Yokluk testi** — blok gelmediğinde, `unavailable` geldiğinde, NaN geldiğinde
3. **Davranış testi** — kısıt kapalıyken alan **gönderilmiyor**
4. **Hata testi** — 404 mission-infeasible olarak, 422 configuration olarak görünüyor

### Non-regression paketi (ayrı tutulur)
Tüm ileri feature'lar kapalıyken: istek gövdesi F0'daki ile birebir aynı, PLAN →
Generate → ANALYZE → playback → replan çalışıyor, AI assistant çalışıyor. Bu paket
bu projedeki en önemli regresyon testidir.

### Bitiş kapısı
- [ ] Katman 1 feature'larının hepsi tam (§9)
- [ ] Non-regression paketi yeşil
- [ ] `typecheck` + `test` + `lint` + `build` baseline'dan kötü değil
- [ ] Hiçbir ekranda uydurma değer yok: NaN → 0 yok, sahte yüzde yok,
      MODEL → MEASURED terfisi yok, "proven" kelimesi yok
- [ ] Çağrılmayan endpoint varsa **nedeni yazılı** (orijinal §42)

---

## 12. Değişmeyenler

Orijinal planın şu kuralları aynen geçerlidir ve bu dokümanda kısaltılmaları
yumuşatıldıkları anlamına gelmez:

- Backend output source of truth'tur; frontend backend mantığını yeniden hesaplamaz
- Eksik veri yerine mock değer konmaz
- Kapalı feature eski davranışı korur; alan omit edilir
- Semantic 404 network hatası yapılmaz
- Uzun hesapta sahte yüzde gösterilmez
- Validity / claim / assumption / limitation kaybedilmez
- Bilinen backend açıkları frontend patch'iyle gizlenmez
- Mevcut LunaPath tasarım dili değişmez: glass yok, glow yok, 2px, veri için mono,
  lavender yalnız etkileşim aksanı, risk renkleri yalnız güvenlik semantiği

**Başarı ölçütü** orijinal §48'deki ile aynıdır: yeni yeteneklerin "bir yerlerde
görünmesi" değil, LunaPath aynı ürün olarak kalırken hepsinin doğru semantik, doğru
provenance ve doğru yaşam döngüsüyle taşınması.
