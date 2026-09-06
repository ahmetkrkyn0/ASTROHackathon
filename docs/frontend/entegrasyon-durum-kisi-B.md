# Entegrasyon durumu — Kişi B şeridi

`frontend/kisi-B` dalı. Bu belge, planın §45'te istediği kayıp denetiminin
Kişi B şeridi için doldurulmuş hâli ve §42'nin şart koştuğu "çağrılmayan
endpoint'in gerekçesi" listesidir.

Ölçümler bu makinedeki canlı backend'e karşı yapıldı, tahmin değil.

---

## 1. Nerede duruyoruz

| Faz | Durum |
|---|---|
| F0 — Zemin | **bitti** |
| F1 — Bedava gelen bloklar | **bitti** |
| F2 — Kısıtlar ve rota bandı (B tarafı) | **bitti** |
| F3 — Ağır analizler (B tarafı) | **bitti** |
| F4 — Sertleştirme | non-regression + hata fixture'ları bitti; §45 denetimi bu belge |

**278 test**, `tsc` temiz, `eslint` temiz, build başarılı.

Kişi A şeridi (katmanlar, çevresel kısıtlar, hücre telemetrisi, zaman ekseni
bağlama) **başlamadı**.

---

## 2. Feature denetimi — Kişi B payı

| Kod | Planner | Rota sonucu | Analiz | Provenance | Hata | Test |
|---|---|---|---|---|---|---|
| D3 Formal Safety | doğrulama | ✅ 12 gereksinim | — | ✅ claim verbatim | ✅ | ✅ |
| C3 Slip | backend fiziği | ✅ | — | ✅ MODEL | ✅ | ✅ |
| B2 CVaR | ✅ `risk_alpha` | ✅ | ✅ risk-sweep | ✅ MODEL + scope | ✅ | ✅ |
| C4 Roughness (rota yarısı) | A'da | ✅ | — | ✅ MEASURED + scale MODEL | ✅ | ✅ |
| B5 Monte Carlo | — | route-based | ✅ | ✅ | ✅ | ✅ |
| B3 DEM Uncertainty (rota yarısı) | dolaylı | ✅ özet + band | ✅ | ✅ | ✅ | ✅ |
| B1 Survival (rota yarısı) | **bloke** (§3) | ✅ okuyucu | — | ✅ assumption görünür | ✅ | ✅ |
| C6 Thermal (rota yarısı) | **bloke** (§3) | ✅ okuyucu | — | ✅ MODEL + UNCALIBRATED | ✅ | ✅ |
| D2 MoonPlanBench | — | — | ✅ offline | ✅ claim | — | ✅ |

B1 ve C6'nın okuyucuları bugünkü 2-B rotalarda **hiçbir şey çizmiyor**, çünkü
o bloklar `plan-4d` yanıtında geliyor. 4-B rota var olduğu an çalışırlar.

---

## 3. Neden altı kısıt sunulmuyor

Ölçüldü: `require_safe_haven`, `require_earth_visibility`,
`require_continuous_illumination`, `require_thermal_dwell`,
`max_failure_probability` — hepsi `POST /api/plan` tarafından **200 ile kabul
ediliyor ve sonra sessizce yok sayılıyor.** Rota, kısıtsız hâliyle bayt bayt
aynı dönüyor ve yanıtta kısıtın düşürüldüğünü söyleyen hiçbir alan yok.

Hiçbir şey yapmayan ve bunu söylemeyen bir anahtar, reddetmekten kötüdür:
operatör ekranda "Safe Haven required" okur ve bunu hiç kontrol etmemiş bir
rotayı uçurur. Planın §44/20 "no hidden assumptions" maddesi tam olarak budur.

Bu kısıtlar, kokpit 4-B plan üretene **veya** backend neyi yok saydığını
bildirene kadar sunulmayacak. Gerekçe `features/plan-request/contributors.ts`
içinde de yazılı.

`w_roughness` ayrı bir durum ve kısıt değil: beşinci bir ağırlık, `weights`
altına iç içe gidiyor, backend kabul edip geri yansıtıyor ve katman
önbelleklenmemişken `applied: false` + gerekçe döndürüyor. Dört ağırlık
nerede düzenleniyorsa oraya ait — yani Kişi A'ya.

---

## 4. Çağrılmayan endpoint'ler ve gerekçeleri (§42)

| Endpoint | Durum | Gerekçe |
|---|---|---|
| `POST /api/safety-check` | çağrılmıyor | Harici bir telemetri izini doğrular. Kokpitte doğrulanacak bir iz yok — planlanan rotanın kendi izi zaten her yanıtta `safety_margins` olarak geliyor. Gerçek telemetri kaynağı bağlandığında değerlidir. |
| `GET /api/earth-series` | çağrılmıyor | Kişi A şeridi (A4). |
| `GET /api/comm-window` | çağrılmıyor | Kişi A şeridi (A4). |
| `GET /api/safe-haven` | çağrılmıyor | Kişi A şeridi (A1). |
| `GET /api/uncertainty-series` | çağrılmıyor | Kişi A şeridi (B3'ün katman yarısı). |
| `GET /api/illumination-corridor` | çağrılmıyor | Kişi A şeridi (A2). |
| `GET /api/psr-validation` | çağrılmıyor | Kişi A şeridi (C4). |
| `GET /api/survival` | çağrılmıyor | Kişi A şeridi (B1'in katman yarısı). |
| `GET /api/thermal-dwell` | çağrılmıyor | Kişi A şeridi (C6'nın katman yarısı). |
| `GET /api/thermal-envelope` | çağrılmıyor | Kişi A şeridi (C6). |

**Çağrılanlar:** `/api/plan` (genişletilmiş), `/api/dem-uncertainty`,
`/api/stress-test`, `/api/risk-sweep`.

---

## 5. Bu kurulumda eksik olan önbellekler

Backend bunları dürüstçe bildiriyor; UI de öyle gösteriyor (kırmızı hata
olarak değil, kesikli çerçeveli "bu kurulumda yok" olarak).

| Ne | Backend'in dediği |
|---|---|
| DEM klon topluluğu | `no dem_clones.npy …; run scripts/build_dem_clone_cache.py` |
| Pürüzlülük katmanı | `no roughness layer beside the processed grids …` |
| Klon önbelleği yok → | `/api/plan` yanıtında `uncertainty` bloğu **hiç yok** |

`scripts/setup_caches.py` bunların hepsini kurmak için var. Kurulunca C4 ve
B3 kendiliğinden dolacak — kodda değişiklik gerekmiyor.

---

## 6. Ölçülmüş bulgular

Uygulama sırasında çıkan, plana yazılı olmayan şeyler:

1. **`coarsen` varsayılanı 4.** Stres testi ve DEM belirsizliği varsayılan
   olarak 20 m blok bekliyor; bir blok ancak içindeki on altı 5 m hücrenin
   hepsi geçilebilirse geçilebilir. İnce hücreli 2-B rota gönderince
   "state 14 is not traversable" diyor — geçilebilir bir rota için.
   `coarsen: 1` doğru cevap ve iki çağrı yerinde de yorumla yazılı.

2. **α = 0.5 rotayı hiç değiştirmiyor** (örtüşme 1.0), α = 0.9 ve 0.99 ise
   %17'ye düşürüyor. "0.5 nötrdür" varsayımının ölçülmüş cevabı.

3. **LP-R10 tam sıfır marjla geliyor.** Hedefe varış tam sınırda; sınır
   durumu ayrı ele alınmasa yeşil tik görünürdü.

4. **İki ayrı `ApiError` sınıfı var** (`net/client.ts` ve `api/client.ts`),
   aynı isim, akrabalık yok. Bugün çakışmıyorlar ama `instanceof` kontrolü
   yapan ilk kişi sessizce `false` alacak. Sınıflandırıcım yapısal, ikisiyle
   de çalışıyor; birleştirmek refactor olurdu ve plan refactor'ü yasaklıyor.

5. **Üç ayrı görev-zamanı başlangıcı vardı** — düzeltildi, kanonik epok
   `mission/missionTime.ts`.

---

## 7. Sırada ne var

**Kişi A şeridi bütünüyle:** on katman endpoint'i, çevresel kısıtlar (A4, A1,
A2), C4'ün katman yarısı, hücre telemetrisi genişletmesi, `useTimeAxis` ve
`TerrainCanvas3D`'nin kanonik saate bağlanması.

**Kişi B'de kalan:** yok. Şeridin tamamı bu dalda.

**Ortak:** 4-B plan yolu açılırsa altı kısıt ve B1/C6'nın rota blokları
kendiliğinden canlanır.
