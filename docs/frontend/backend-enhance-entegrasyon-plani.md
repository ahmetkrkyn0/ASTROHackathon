# LunaPath Backend Enhance → Frontend Integration Implementation Plan

## 0. Dokümanın amacı

Bu planın amacı, LunaPath backend’ine eklenmiş tüm yeni mühendislik yeteneklerini mevcut frontend’e **özellik kaybetmeden**, **mevcut çalışan davranışı bozmadan**, **mevcut LunaPath tasarım dilini değiştirmeden** ve mümkün olduğunca **2–3 geliştiricinin paralel çalışabileceği** şekilde entegre etmektir.

Bu doküman repo yapısı hakkında varsayım yapmaz.

Belirli bir dosyanın, klasörün, component’in veya state management çözümünün var olduğu kabul edilmemelidir.

Bu planı alan her Claude Code oturumu önce mevcut güncel frontend’i incelemeli, mevcut mimariyi anlamalı ve aşağıdaki gereksinimleri o mimariye adapte etmelidir.

Temel yaklaşım:

**inspect → understand → preserve → extend → verify**

Amaç refactor yapmak değildir.

Amaç mevcut ürünü yeniden tasarlamak değildir.

Amaç backend özelliklerini frontend’e kayıpsız şekilde taşımaktır.

---

# 1. Kesin kapsam

Backend genişletmesindeki aşağıdaki 12 feature’ın tamamı frontend açısından ele alınacaktır:

| Kod | Feature |
|---|---|
| A4 | Earth Visibility / Direct-to-Earth communication |
| A1 | Safe Haven + time-to-haven |
| B5 | SHERPA Monte Carlo stress test |
| B3 | DEM uncertainty / 100 NASA clone propagation |
| D3 | FRETISH + STL formal safety margins |
| A2 | Continuous Illumination Corridor |
| C3 | Calibrated slip model |
| B2 | CVaR risk-aware planning |
| C4 | LOLA roughness + PSR |
| D2 | MoonPlanBench external validation |
| B1 | Survival / reach-avoid recovery policy |
| C6 | Thermal operating envelope + thermal dwell / entrenchment |

Hiçbiri “later”, “optional UI polish” veya “stretch” gerekçesiyle atlanmamalıdır.

Ancak bütün feature’ların aynı türde olmadığı bilinmelidir.

Bazıları planner input’udur.

Bazıları raster/map layer’dır.

Bazıları time-dependent cube’dür.

Bazıları route result block’udur.

Bazıları post-route analysis endpoint’idir.

D2 ise runtime API feature değildir; offline validation artifact’ıdır.

Bu ayrımlar korunmalıdır.

---

# 2. Ana koruma ilkesi: mevcut LunaPath bozulmayacak

Yeni backend tamamen additive tasarlanmıştır.

Frontend de aynı stratejiyi izlemelidir.

## Zorunlu non-regression kuralı

Yeni feature’ların hiçbiri etkin değilken:

- mevcut PLAN davranışı değişmemeli,
- mevcut route request’leri semantik olarak değişmemeli,
- mevcut route generation akışı çalışmalı,
- mevcut ANALYZE davranışı çalışmalı,
- mevcut 2D görüntüleme çalışmalı,
- mevcut 3D görüntüleme çalışmalı,
- mevcut playback çalışmalı,
- mevcut AI assistant çalışmalı,
- mevcut rover selection çalışmalı,
- mevcut dört route priority kaybolmamalı,
- mevcut layer’lar kaybolmamalı,
- mevcut start/goal workflow değişmemeli,
- mevcut error handling gerilememeli.

Backend tarafında yeni constraint’lerin gönderilmemesi eski planner davranışını koruyor.

Frontend de “disabled” özelliği yanlışlıkla request’e default value olarak koymamalıdır.

Örneğin:

Risk-aware planning kapalıysa:

`risk_alpha: 0.5`

göndermek doğru değildir.

Alan tamamen omit edilmelidir.

Çünkü `α = 0.5` nominal davranış anlamına gelmez.

Aynı prensip diğer opsiyonel backend parametreleri için de uygulanmalıdır.

---

# 3. Claude Code için zorunlu başlangıç aşaması: mevcut frontend discovery

Her geliştirici kod yazmadan önce güncel frontend’i incelemelidir.

Bu inceleme değiştirme amaçlı değil, entegrasyon noktalarını anlamak içindir.

Aşağıdaki konular bulunmalı ve kısa bir internal integration map oluşturulmalıdır.

## 3.1 Mevcut application lifecycle

Anlaşılması gerekenler:

- landing → mission workspace geçişi
- PLAN state
- route solving state
- ANALYZE state
- Edit & Replan davranışı
- route reset/invalidation davranışı
- mission locked/unlocked davranışı

Yeni feature’lar bu lifecycle’a adapte edilmelidir.

Lifecycle yeniden yazılmamalıdır.

---

## 3.2 Mevcut API boundary

Bul:

- HTTP client nerede soyutlanıyor?
- response parsing nerede yapılıyor?
- backend DTO ile frontend domain model arasında adapter var mı?
- cancellation destekleniyor mu?
- request deduplication var mı?
- binary/f32 response desteği var mı?
- API error → UI error dönüşümü nasıl yapılıyor?

Yeni backend payload’ları mevcut pattern içine eklenmelidir.

İkinci paralel bir API architecture yaratılmamalıdır.

---

## 3.3 Mission state

Bul:

- selected rover
- start
- goal
- weights
- current route
- current layer
- selected cell
- playback position
- selected time
- 2D/3D state
- mission status

Yeni feature state’leri mümkün olduğunca mevcut mission state modeline bağlanmalıdır.

---

## 3.4 Map / terrain rendering

Hem 2D hem 3D için anlaşılmalıdır:

- raster layer nasıl render ediliyor?
- binary grid nasıl taşınıyor?
- colour ramp nerede uygulanıyor?
- masks nasıl çiziliyor?
- overlay compositing var mı?
- selected cell nasıl belirleniyor?
- route nasıl drape ediliyor?
- START/GOAL nasıl render ediliyor?
- 3D terrain coordinate mapping nasıl çalışıyor?

Mevcut coordinate transform kesinlikle değiştirilmemelidir.

Yeni 320 m coarse grid ürünleri için bunun üstüne açık bir transform uygulanmalıdır.

---

## 3.5 Time / playback

Bul:

- mission timestamp nasıl tutuluyor?
- playback index ile route state ilişkisi nasıl?
- Sun/Time kontrolü var mı?
- illumination time series kullanılıyor mu?

Yeni backend time-dependent ürünleri mümkünse **tek ortak mission-time state** kullanmalıdır.

Ayrı ayrı 5 bağımsız time slider oluşturulmamalıdır.

---

## 3.6 Tasarım sistemi

Bul:

- typography
- spacing
- surface
- border
- accent
- risk colors
- chart styles
- popover/drawer patterns
- button hierarchy
- loading state pattern
- empty state pattern
- tooltip pattern

Yeni backend feature’ları mevcut LunaPath design language kullanmalıdır.

Yeni feature = yeni tasarım sistemi değildir.

Özellikle:

- neon HUD,
- yeni rastgele gradient’ler,
- glow efektleri,
- yeni card estetiği,
- farklı font,
- sci-fi gösteriş

eklenmemelidir.

---

## 3.7 Mevcut test baseline

Kod değişmeden önce:

- typecheck
- lint
- unit tests
- integration tests
- build
- mevcut E2E varsa E2E

çalıştırılmalıdır.

Baseline failure varsa yeni değişikliklerden ayrıştırılmalıdır.

---

# 4. Backend contract authoritative source

Backend özet raporu feature semantiğini anlatır.

Ancak JSON wire format için authoritative kaynak:

`docs/frontend/3b-veri-sozlesmesi.md`

olmalıdır.

Her feature implement edilmeden önce ilgili contract section okunmalıdır.

Özet rapordan field name tahmin edilmemelidir.

Contract’tan doğrulanması gerekenler:

- HTTP method
- query params
- body fields
- nullable/optional fields
- exact enum values
- response headers
- binary f32 layout
- dimensions
- units
- timestamps
- coordinate convention
- error response body
- validity metadata
- claim
- provenance
- unavailable semantics

Backend payload’ını frontend’e uygun olsun diye frontend tarafında yeniden yorumlamayın.

Backend ne söylüyorsa onu doğru temsil edin.

---

# 5. Ortak frontend infrastructure — feature’lardan önce

Bu 12 feature ayrı ayrı implement edilmeden önce birkaç cross-cutting primitive hazır olmalıdır.

Bu primitive’ler mevcut architecture içinde, mevcut pattern’ler kullanılarak oluşturulmalıdır.

---

# 5.1 Capability / availability modeli

Yeni backend data’larının bir kısmı cache/preprocessing yoksa hiç gelmez.

Frontend şu varsayımı yapmamalı:

> “Backend yeni ise tüm layer’lar vardır.”

Capability mevcut response/manifest üzerinden keşfedilmelidir.

Her feature için en az şu state’ler ayrılmalıdır:

- available
- loading
- ready
- unavailable
- unsupported
- error
- stale

`unavailable` ile `error` aynı değildir.

Örnek:

thermal envelope cache yok.

Bu:

**data unavailable**

durumudur.

Sahte heatmap üretmek yasaktır.

---

# 5.2 Validity / provenance primitive

Backend dört temel validity seviyesi taşıyor:

- MEASURED
- DERIVED
- MODEL
- SYNTHETIC

Ayrıca bazı kaynaklarda:

- assumption:

provenance bulunuyor.

Frontend bunları görmezden gelmemelidir.

Reusable provenance presentation oluşturulmalıdır.

Her scientific result gerektiğinde şu bilgileri taşıyabilmeli:

**Validity**
MODEL

**Source**
...

**Claim**
...

**Assumptions**
...

**Limitations**
...

Özellikle risk, slip, survival ve thermal sonuçlarında bu kritik.

---

# 5.3 Semantic error taxonomy

HTTP status tek başına UI davranışını belirlememelidir.

En az şu kategoriler ayrılmalıdır:

### Transport failure

Backend erişilemiyor.

### Invalid request

422 vb.

### Data unavailable

Gerekli cache / kernel / epoch yok.

### Mission infeasible

Planner çalıştı ama constraint altında rota yok.

Örneğin:

- illumination corridor izin vermiyor,
- β constraint karşılanmıyor,
- thermal envelope altında feasible route yok.

Bu 404 olabilir fakat:

**“Request failed”**

olarak gösterilmemelidir.

Doğru semantik:

**No feasible route under selected mission constraints.**

### Analysis failure

Optional stress-test/uncertainty analizi çalışmadı fakat mevcut route hâlâ geçerli.

Optional analiz failure mevcut route’u silmemelidir.

---

# 5.4 Analysis invalidation

Bir route’a bağlı post-analysis sonuçları şu durumlarda stale olmalıdır:

- rover değişirse
- start değişirse
- goal değişirse
- planning weights değişirse
- relevant advanced constraint değişirse
- route yeniden hesaplanırsa
- route identifier/hash değişirse

Örneğin eski route’un Monte Carlo sonucu yeni route üzerinde gösterilmemelidir.

Ancak gereksiz invalidation da yapılmamalıdır.

Örneğin sadece visual layer değişmesi route analysis’i invalidate etmez.

---

# 5.5 Binary layer pipeline

f32 layer response’ları mümkünse:

- TypedArray olarak tutulmalı,
- gereksiz JSON dönüşümü yapılmamalı,
- aynı array gereksiz kopyalanmamalı,
- büyük array React/component state içinde tekrar tekrar clone edilmemeli,
- rendering pipeline’a minimum-copy ile aktarılmalı.

Mevcut worker/off-main-thread architecture varsa kullanılmalıdır.

Yeni alternatif worker architecture yaratılmamalıdır.

---

# 5.6 Resolution-aware layer model

Bu çok kritik.

Yeni layer’lar aynı resolution’da değildir.

Fine products yaklaşık:

**5 m / pixel**

4D-derived products:

**coarsen 4 → 320 m blocks**

örnekleri içerir.

Frontend layer metadata’da en az şunları bilmeli:

- native shape
- native resolution
- spatial extent
- transform
- units
- categorical/continuous
- nodata semantics

320 m veriyi 5 m raster’mış gibi stretch etmek yasaktır.

Drape/upscale sırasında blok sınırları korunmalıdır.

---

# 5.7 NaN semantiği

Özellikle Safe Haven:

`time_to_safe_haven = NaN`

şu anlama gelebilir:

**reachable haven does not exist**

Bu:

`0 h`

değildir.

Frontend hiçbir NaN’ı otomatik 0’a çevirmemelidir.

NaN:

- unavailable,
- unreachable,
- invalid cell

gibi context-dependent bir state ile render edilmelidir.

Contract hangi anlamı söylüyorsa o kullanılmalıdır.

---

# 5.8 Ortak mission-time controller

Aşağıdaki backend ürünleri aynı mission time ekseninde kullanılabilir:

- illumination series
- Earth visibility series
- illumination uncertainty
- illumination corridor
- thermal dwell slice
- survival slice

Bunlar mümkünse tek canonical:

`missionTime`

veya eşdeğer state kullanmalıdır.

Bir zaman değiştiğinde dependent layer’lar aynı zaman dilimine geçmelidir.

Categorical/binary veriyi frontend kendi başına interpolate etmemelidir.

---

# 6. Planner request composition

Yeni backend planner özellikleri mevcut request builder içine additive olarak bağlanmalıdır.

Yeni bir paralel “advanced planner API” oluşturmak gereksizdir.

---

# 6.1 A4 Earth visibility

Constraint:

`require_earth_visibility`

Yalnız operator gerçekten açtıysa gönder.

Kapalıysa omit veya backend contract’ın eski davranışı sağlayan biçimini kullan.

---

# 6.2 A1 Safe Haven

Constraint:

`require_safe_haven`

Açıldığında planner her state için Safe Haven reachability koşulunu uygular.

---

# 6.3 A2 Continuous illumination

Fields:

`require_continuous_illumination`

`lit_rule`

`lit_rule` backend enum’una birebir uymalı.

`all` ve `majority` semantiği UI’da açık açıklanmalıdır.

---

# 6.4 B2 CVaR

Field:

`risk_alpha`

Kritik:

Risk kapalıysa field gönderme.

`0.5 = nominal` varsayımı yapma.

Alpha’nın fizik modelini değil **route ranking** davranışını değiştirdiğini açıkça koru.

---

# 6.5 B1 Survival

Planner alanları contract’tan doğrulanarak desteklenmeli:

- `max_failure_probability`
- `report_survival`
- `failure_rate_per_km`
- `recovery_hours`
- `survival_soc_bins`
- `survival_safe_set`
- `survival_horizon_hours`

Default assumption değerleri UI tarafından gizlice hard-code edilmemelidir.

Backend provenance kullanılmalıdır.

---

# 6.6 C6 Thermal dwell

Fields:

- `require_thermal_dwell`
- `initial_inner_c`
- `heater_model`

Default:

`heater_model = none`

Assumption-based:

`thermostat_assumed`

Thermostat assumed seçildiğinde açıkça:

**ASSUMPTION**

olarak belirtilmelidir.

---

# 6.7 C4 Roughness weight

Roughness yeni cost criterion’dur.

Backend contract’ın izin verdiği planner endpoint’lerinde:

`w_roughness`

desteklenmelidir.

Mevcut dört priority’nin normalization mantığı varsa frontend bunu kafasına göre değiştirmemelidir.

Backend’in beklediği weight semantiği contract’tan doğrulanmalıdır.

Roughness data yoksa weight silently başka kritere dağıtılmamalıdır.

---

# 7. A4 — Earth Visibility implementation

## İşlev

Rover’ın belirli zaman ve hücrede doğrudan Dünya görüşü olup olmadığını ve iletişim penceresini gösterir.

---

## Data integrations

Desteklenecekler:

`GET /api/earth-series`

`GET /api/comm-window`

terrain/layer manifest içindeki:

`earth_visibility`

planner result:

`path_earth_visible`

`metrics.moves_out_of_earth_view`

pose/replan içindeki calculated communication fields.

---

## Görsel davranış

Earth visibility continuous ratio layer olarak render edilebilmeli.

Range:

0–1.

Route boyunca Earth visibility binary profile desteklenmeli.

Playback sırasında mevcut waypoint Earth visibility state’i gösterilebilmeli.

Communication status backend değerinden türetilmeli.

Static decorative:

`Data Link ACTIVE`

yerine backend data mevcutsa gerçek communication status kullanılmalıdır.

---

## Constraint behavior

Require Earth Visibility açılırsa:

planner field doğru gönderilmeli.

Result route’da Earth-view violation varsa count gösterilmeli.

---

## Edge cases

Link yok:

`comm_minutes_remaining = 0`

bunu missing data sayma.

Earth series unavailable ise current route silinmemeli.

---

## Validity

Model/validation metadata backend’den alınmalı.

Frontend:

“NASA measured direct Earth link”

gibi yanlış bir ifade üretmemeli.

---

## Acceptance

Feature complete sayılmak için:

- layer render
- time series
- current communication window
- planner constraint
- route profile
- playback status
- unavailable
- provenance
- tests

hepsi çalışmalı.

---

# 8. A1 — Safe Haven implementation

## İşlev

Rover’ın Earth link kaybından önce hayatta kalabileceği Safe Haven bölgelerini ve onlara ulaşım marjını hesaplar.

---

## Integrations

`GET /api/safe-haven`

Dört product:

- safe_haven
- max_dark_hours_without_dte
- earth_below_hours
- time_to_safe_haven

Cell telemetry:

`start_utc`

Planner:

`require_safe_haven`

Route arrays:

- path_time_to_haven_h
- path_hours_until_earthset
- path_haven_margin_h

Metrics:

`min_haven_margin_h`

`ends_at_safe_haven`

---

## Semantics

Safe Haven generic “safe terrain” değildir.

Communication-loss survival mantığıdır.

Bu ayrım korunmalıdır.

---

## Map rendering

Safe Haven:

binary mask.

Time to Safe Haven:

continuous hours surface.

Earth-below duration:

hours.

---

## Critical edge case

`time_to_safe_haven = NaN`

=> reachable Safe Haven does not exist.

UI:

`No reachable Safe Haven`

demelidir.

`0.0 h`

göstermemelidir.

---

## Route analysis

`path_haven_margin_h`

önemli engineering profile’dır.

Margin sıfıra yaklaştıkça visual severity artmalıdır.

Negatif değer violation’dır.

---

## Planner failure

Require Safe Haven altında 404:

generic API error değil:

**No route satisfies Safe Haven reachability requirement.**

---

# 9. B5 — SHERPA Monte Carlo stress-test implementation

## İşlev

Deterministic planın perturbed mission conditions altında ne kadar robust olduğunu ölçer.

Route var olmadan çalıştırılmamalıdır.

---

## Endpoint

`POST /api/stress-test`

Default backend run count:

1000.

Override destekleniyorsa contract’a göre gönderilmelidir.

---

## Request lifecycle

Stress test post-route analysis job olarak ele alınmalı.

State:

idle → running → success / failure / stale

Running sırasında fake percentage gösterilmemeli.

Indeterminate engineering state kullanılmalı.

---

## Result visualization

Desteklenmesi gereken tüm output sınıfları:

- completion rate
- Wilson 95% interval
- p5 / p50 / p95
- prepared histograms
- arrival fan chart
- battery fan chart
- outage statistics
- failure causes
- backend decision text

Backend histogram bin’leri hazır gönderiyorsa frontend yeniden binning yapmamalıdır.

---

## Semantics

Deterministic route success ile Monte Carlo success aynı kavram değildir.

Örneğin planner route döndürmüş olabilir fakat stress-test completion düşük olabilir.

Bu nedenle stress-test sonucu route status’u overwrite etmemelidir.

---

## Known backend limitation

Backend dokümanında planner time/battery accounting mismatch açık issue’dur.

Frontend bunu “fix” etmeye çalışmamalıdır.

Gerekli yerde limitation/provenance gösterilmelidir.

---

# 10. B3 — DEM uncertainty implementation

## İşlev

NASA’nın 100 statistical DEM clone’u üzerinden terrain ve route uncertainty gösterir.

---

## Integrations

Terrain layers:

- p_traversable
- slope_sigma
- elevation_sigma
- slope_sigma_nasa

Series:

`GET /api/uncertainty-series`

Route analysis:

`POST /api/dem-uncertainty`

Plan responses:

`uncertainty`

---

## Layer semantics

### p_traversable

0–1 probability.

0.5 çevresi uncertainty band olarak vurgulanabilir.

Bu nominal traversability değildir.

### slope_sigma

DERIVED.

### slope_sigma_nasa

MODEL.

NASA kaynaklı olması onu MEASURED yapmaz.

### elevation_sigma

Elevation uncertainty.

---

## Route results

p5/p50/p95 band desteklenmelidir.

Nominal/best-estimate DEM result band üzerinde ayrıca gösterilmelidir.

Band tek scalar gibi gösterilmemelidir.

---

## Important limitation

Clone propagation sırasında bazı environmental quantities sabit tutulmuştur.

Frontend result limitation içinde bunu korumalıdır.

---

## Cache absence

Uncertainty cache yoksa bu layer’lar manifestte bulunmayabilir.

Frontend placeholder 0 layer üretmemelidir.

---

# 11. D3 — Formal Safety implementation

## İşlev

Her planned/simulated route’u 12 mission/safety requirement’a karşı quantitative robustness margin ile değerlendirir.

---

## Automatic integration

`safety_margins`

geldiği her route result’ta parse edilmelidir:

- plan
- plan-4d
- compare
- plan-multi

Bu analysis optional button’a bağlı olmamalıdır.

Result mevcutsa görünür olmalıdır.

---

## Requirements

Frontend şu requirement kimliklerini korumalı:

LP-R01 Continuous shadow endurance

LP-R02 Minimum SOC

LP-R03 Charge recovery after low SOC

LP-R04 Electronics operating temperature

LP-R05 Battery operating temperature

LP-R06 Drive slope

LP-R07 Lateral slope

LP-R08 Earth visibility during movement

LP-R09 Safe Haven reachability margin

LP-R10 Goal reached

LP-R11 Goal SOC

LP-R12 Thermal dwell

---

## Display semantics

Her requirement:

- ID
- human-readable meaning
- rho / robustness
- unit
- minimum-margin state/location
- pass/violation

gösterebilmelidir.

Rho sign korunmalıdır.

Positive = margin.

Negative = violation.

---

## Safety-check

`POST /api/safety-check`

ayrı telemetry trace validation için desteklenmelidir.

422 cases:

- time reversal
- NaN
- unknown engine
- unavailable RTAMT engine

semantic olarak gösterilmelidir.

Silent fallback yapılmamalıdır.

---

## Critical claim boundary

Frontend hiçbir yerde:

**formally proven**

veya

**model checked**

dememelidir.

Doğru kavram:

**runtime monitored / checked with STL robustness**

Backend `claim` field’i varsa gösterilmelidir.

---

# 12. A2 — Continuous Illumination Corridor implementation

## İşlev

Time × terrain volume içinde rover’ın sürekli aydınlık ve traversable kalabileceği corridor’u gösterir ve gerektiğinde planner constraint olarak uygular.

---

## Integrations

Planner:

`require_continuous_illumination`

`lit_rule`

Endpoint:

`GET /api/illumination-corridor`

Outputs:

- corridor
- lit_safe
- dwell_hours
- voxel count
- pruned fraction
- connected components
- start/goal inclusion
- path-in-corridor
- dwell opportunities

---

## Rendering

Bu feature özellikle time-dependent terrain visualization’dır.

Single mission-time controller ile sürülmelidir.

2D’de:

time slice mask/overlay.

3D’de:

terrain üzerine restrained animated volume/surface overlay.

Fantasy volumetric glow yapılmamalıdır.

---

## Data handling

Cube büyük olabilir.

Tam cube mümkün olduğunda typed array olarak tutulmalıdır.

Her frame React state’e kopyalanmamalıdır.

---

## Error behavior

Static shadow series kullanılırken constraint mümkün değilse backend 422 dönebilir.

Corridor nedeniyle no-route:

404 mission infeasible olarak işlenmelidir.

Backend’in detayındaki corridor statistics korunmalıdır.

---

# 13. C3 — Slip model implementation

## İşlev

Slope-dependent slip artık travel time ve energy physics’e bağlıdır.

Frontend slip’i tekrar hesaplamamalıdır.

Backend source of truth olmalıdır.

---

## Integrations

Rovers:

`slip_model`

- validity
- source anchors
- 0–25° table
- references

Route:

`slip_model` result block.

Beklenen route metrics:

- average slip
- max slip
- distance multiplier
- added travel hours
- added Wh

---

## Presentation

Slope-to-slip curve gösterilebilir.

Curve backend table üzerinden çizilmelidir.

Client-side formula tahmin edilmemelidir.

---

## Provenance

Slip:

MODEL.

Uçmuş veriye bağlı olması:

MEASURED South Pole slip

anlamına gelmez.

Source anchors ve assumption kaynakları görünür olmalıdır.

---

## Existing energy UI integration

Energy summary route slip effect’i ayırt edebilmelidir:

Base/nominal result ile:

`Slip added +X Wh`

gibi.

Ancak backend’in verdiği değer kullanılmalıdır.

---

# 14. B2 — CVaR risk-aware planning implementation

## İşlev

Planner’ın mean estimate yerine adverse distribution tail’ini route ranking sırasında dikkate almasını sağlar.

---

## Critical semantic

CVaR:

route-selection preference’dır.

Nominal physics değildir.

Risk alpha değiştiğinde:

- ranking cost değişebilir,
- rota değişebilir,

fakat physical playback değerleri “CVaR physics” gibi sunulmamalıdır.

---

## Planner

`risk_alpha`

yalnız enabled olduğunda gönder.

Allowed interval contract’tan validate edilmeli.

Backend summary range:

0.5–0.999.

---

## Result block

`risk`

içinden desteklenmeli:

- alpha
- applied
- validity
- multiplier
- scope
- criterion impact
- sigma sources
- route CVaR slip
- risk-adjusted hour/Wh fields
- claim

---

## Risk sweep

`POST /api/risk-sweep`

tam desteklenecek.

Visualization:

- nominal route
- alpha routes
- route overlap
- comparative results
- risk matrix heatmap

Risk matrix yeniden frontend’de hesaplanmamalı.

Backend matrix kullanılmalı.

---

## Unsupported thermal risk

Thermal CVaR backend tarafından uygulanmıyor.

Frontend bunu hesaplamamalıdır.

---

# 15. C4 — Roughness + PSR implementation

## Roughness

NASA LOLA roughness:

MEASURED data product.

Layer:

`roughness`

Units:

meters.

Ancak bu per-cell rock count değildir.

50 m pixel / 100 m baseline block statistic semantiği korunmalıdır.

---

## Roughness cost

Planner cost’a yeni criterion:

`f_roughness`

ve weight:

`w_roughness`

eklenmiştir.

Backend request contract desteklediği yerde weight gönderilmelidir.

Frontend f_roughness’ı roughness metre değerinden kendi formülüyle üretmemelidir.

---

## Route result

`roughness`

result block:

- route roughness summary
- cost contribution

gösterilebilmelidir.

---

## PSR

`psr`

MEASURED mask.

PSR:

planner forbidden region değildir.

Bu çok kritik.

Frontend PSR layer açık diye path selection’ı kendi başına yasaklamamalıdır.

PSR analysis/validation data’dır.

---

## PSR validation

`GET /api/psr-validation`

Destek:

- NASA PSR
- LunaPath shadow result
- overlay comparison
- Jaccard
- recall
- precision

Bu scientific validation’dır.

---

# 16. D2 — MoonPlanBench implementation

## İşlev

Runtime mission feature değildir.

External benchmark evidence’dır.

Backend API endpoint’i yoktur.

Frontend nonexistent endpoint invent etmemelidir.

---

## Implementasyon şekli

MoonPlanBench sonucu:

**offline validation artifact**

olarak ele alınmalıdır.

Eğer current product build/report artifact erişimi destekliyorsa:

- benchmark summary
- movement-model caveat
- LunaPath result
- paper result

read-only engineering evidence olarak gösterilebilir.

Artifact yoksa:

`Benchmark artifact unavailable in this build`

gibi explicit state kullanılmalıdır.

Sahte live result üretilmemelidir.

---

## Critical caveat

Benchmark’ın corner-cutting motion model’i ile LunaPath motion model’i aynı değildir.

Koşulsuz:

`100% success`

ifadesi kullanılmamalıdır.

---

# 17. B1 — Survival / recovery implementation

## İşlev

Mobility failure altında safe execution probability ve optimal recovery action üretir.

---

## Planner integration

Desteklenecek request family:

- max_failure_probability β
- report_survival
- failure_rate_per_km
- recovery_hours
- survival_soc_bins
- survival_safe_set
- survival_horizon_hours

Exact wire format contract’tan okunmalıdır.

---

## Layer

`GET /api/survival`

Outputs:

`p_safe`

`best_action`

p_safe:

continuous probability.

best_action:

categorical action.

Frontend `best_action`ı scalar colour ramp’a çevirmemelidir.

Direction/wait semantics korunmalıdır.

---

## Cell telemetry

`survival=true`

ile:

- P_safe
- best recovery action

gösterilebilmelidir.

---

## Replan

`recovery_policy: true`

ile:

`recovery_suggestion`

support edilmelidir.

---

## Planner result

Survival block:

- P_safe
- β
- rejected transition counts
- route/path survival arrays

desteklenmelidir.

---

## Long-running behavior

Survival field computation uzun sürebilir.

UI:

- fake progress percentage göstermemeli,
- duplicate request göndermemeli,
- mission değişirse stale result’ı apply etmemeli,
- mümkünse stale request cancel etmeli,
- mevcut route’u loading sırasında gizlememeli.

---

## Assumptions

Failure rate ve recovery duration assumptions olabilir.

Bunlar provenance olarak görünmelidir.

---

## 404

Chance constraint nedeniyle no route:

network error değildir.

Doğru state:

**No feasible route satisfies the selected execution-failure limit.**

---

# 18. C6 — Thermal operating envelope + dwell implementation

## İşlev

Rover internal temperature evolution ve operating-envelope exit time hesaplar.

---

## Planner integration

- require_thermal_dwell
- initial_inner_c
- heater_model

---

## Route outputs

- thermal_dwell block
- path_inner_c
- path_max_dwell_h
- path_dwell_margin_h
- path_stay_hours
- min_dwell_margin_h

hepsi desteklenmelidir.

---

## Thermal dwell layer

`GET /api/thermal-dwell`

Outputs:

- max_dwell_h
- side
- open_ended

Semantics:

`open_ended`

ile büyük finite value aynı değildir.

UI:

**Open-ended within evaluated horizon**

gibi temsil etmelidir.

Infinity uydurulmamalıdır.

---

## Thermal envelope

`GET /api/thermal-envelope`

Heatmap axis doğru tutulmalıdır:

**Sun elevation × Sun-parallel slope**

Yanlış eski tanım:

azimuth × elevation × slope

kullanılmamalıdır.

Categories:

- unlimited
- cold-limited
- hot-limited

---

## Cell telemetry

`thermal_dwell=true`

ile:

- current thermal dwell
- tolerated entrenchment duration
- Safe Haven window interaction

gösterilmelidir.

---

## Entrenchment

Replan state:

`entrenched_hours`

Result:

`entrenchment`

Severity:

- ok
- warning at ~50%
- critical at ~80%
- fail

Backend threshold semantics kullanılmalıdır.

Frontend kendisi farklı threshold üretmemelidir.

Thermal budget ve Haven window birlikte korunmalıdır.

---

## Heater

`none`:

default physical behavior.

`thermostat_assumed`:

assumption.

Assumed heater mode result:

validated heater model gibi gösterilmemelidir.

---

## Critical provenance

Thermal model:

**MODEL / UNCALIBRATED**

Frontend hiçbir yerde:

“thermally validated”

veya:

“thermal prediction accurate”

dememelidir.

---

# 19. Harita/layer integration completeness

Mevcut layer’lar korunacaktır.

Yeni backend’den gelen minimum layer coverage:

## Terrain manifest family

- earth_visibility
- p_traversable
- slope_sigma
- slope_sigma_nasa
- elevation_sigma
- roughness
- psr

## Safe Haven family

- safe_haven
- max_dark_hours_without_dte
- earth_below_hours
- time_to_safe_haven

## Survival family

- p_safe
- best_action

## Thermal family

- max_dwell_h
- side
- open_ended

## Time-varying

- earth visibility
- p_illuminated
- illumination corridor
- lit_safe
- dwell_hours

Her layer descriptor şu metadata’yı korumalı:

- name
- human label
- feature
- units
- validity
- shape
- resolution
- continuous/categorical
- nodata
- colour semantics
- provenance

---

# 20. Route profile integration completeness

`plan-4d` route state arrays tek canonical route index/time eksenine bağlanmalıdır.

Desteklenecek yeni arrays minimum:

- path_earth_visible
- path_time_to_haven_h
- path_hours_until_earthset
- path_haven_margin_h
- path_survival_prob
- path_recovery_prob
- path_inner_c
- path_max_dwell_h
- path_dwell_margin_h
- path_stay_hours

Bunlar:

- playback cursor,
- map route segment,
- engineering profile

ile aynı current route index’i kullanmalıdır.

Index drift kabul edilemez.

---

# 21. Cell telemetry expansion

Cell selection mevcutsa onu genişlet.

Yeni ikinci inspector sistemi yaratma.

Bir selected cell için backend desteklediği ölçüde:

- existing telemetry
- five-criterion cost breakdown
- roughness_m
- f_roughness
- in_psr
- Safe Haven status
- time to nearest Haven
- P_safe
- best recovery action
- thermal dwell
- tolerated entrenchment time

getirilebilmelidir.

Expensive fields query flags gerektiriyorsa:

sadece ihtiyaç olduğunda request edilmelidir.

Cell hover sırasında her piksel hareketinde survival hesaplatmak gibi pahalı davranış oluşturulmamalıdır.

---

# 22. Analysis results model

Route result tek dev anonymous JSON olarak component’lere taşınmamalıdır.

Mevcut frontend pattern’ine uygun typed/domain representation oluşturulmalıdır.

Logical sections:

- summary
- energy
- terrain
- environment
- communication
- Safe Haven
- uncertainty
- formal safety
- mobility/slip
- roughness
- risk
- survival
- thermal dwell
- robustness/stress test
- provenance

Bu logical separation UI location dayatması değildir.

Ama feature boundaries’in kaybolmasını önler.

---

# 23. AI Assistant compatibility

Mevcut Mission Guide / Analysis Assistant korunmalıdır.

Backend feature entegrasyonu assistant’ı bozmayacak.

Assistant context üretimi mevcut route result’tan geliyorsa yeni structured blocks eklenebilir.

Assistant şu bilgileri kullanabilir:

- Earth link
- Haven margin
- safety margins
- uncertainty
- stress-test
- slip
- risk
- survival
- thermal dwell

Ancak:

- unavailable data hakkında cevap uydurmamalı,
- backend claim’i aşmamalı,
- assumptions’ı gizlememeli,
- warnings assistant prose içine gömmemeli,
- limitations ayrı kalmalı,
- evidence/provenance ayrı kalmalı.

Assistant panelinin açılması otomatik model request üretmemeye devam etmelidir.

---

# 24. Request scheduling / performance

Her feature route generation’ın blocking dependency’si değildir.

Sistem iki sınıfa ayrılmalıdır.

## Route-critical

Planner request içinde gerekli olan enabled constraints.

Route çözülmeden analysis başlamaz.

## Post-route

- Monte Carlo
- DEM uncertainty
- risk sweep
- PSR validation
- optional safety-check
- heavy survival visualization

bunlar route-ready UI’yı bloklamamalıdır.

Route önce gösterilmelidir.

Heavy analyses independently load olmalıdır.

---

# 25. Cancellation ve stale response safety

Örnek:

Operator stress-test başlattı.

Ardından route’u değiştirdi.

Eski stress-test response’u daha sonra gelirse yeni route’a attach edilmemelidir.

Her analysis result canonical mission/route identity ile eşleştirilmelidir.

Benzer kural:

- survival
- risk sweep
- uncertainty
- corridor
- thermal calculations

için geçerlidir.

---

# 26. Loading davranışı

Engineering operations loading states:

- indeterminate
- non-blocking where possible
- cancel-aware
- duplicate-submit protected

olmalıdır.

Backend gerçek progress yüzdesi vermiyorsa:

`63%`

gibi sayı üretmek yasaktır.

---

# 27. Error presentation rules

### 404 planner constraint failure

Mission infeasible.

### 422 contract validation

Input/configuration problem.

### Missing cache

Data unavailable.

### Optional analysis failure

Analysis unavailable; route retained.

### Network error

Connectivity/API problem.

### Missing field due capability

Feature unavailable on current dataset.

Bu durumlar birbirine karıştırılmamalıdır.

---

# 28. Parallel çalışma planı — 3 kişi

Üç kişi için önerilen domain ownership aşağıdadır.

Bu ownership dosya ownership’i değildir.

Aynı repo structure içinde uygulanacaktır.

---

## TRACK A — Mission Constraints + Environment Data

Ana sorumluluk:

- A4 Earth Visibility
- A1 Safe Haven
- A2 Illumination Corridor
- C4 Roughness + PSR
- planner request integration for these capabilities
- map layer registration
- common time-axis environment data
- related cell telemetry
- related mission infeasible states

Ek sorumluluk:

Shared capability / availability modeline katkı.

---

## TRACK B — Route Analysis + Risk + Uncertainty

Ana sorumluluk:

- B3 DEM Uncertainty
- B5 Monte Carlo
- D3 Formal Safety
- C3 Slip
- B2 CVaR
- route profile integration
- safety margin model
- uncertainty bands
- risk sweep
- robustness results

Ek sorumluluk:

Common provenance presentation.

---

## TRACK C — Survival + Thermal + System Integration

Ana sorumluluk:

- B1 Survival / Recovery
- C6 Thermal Dwell
- D2 MoonPlanBench artifact
- advanced replan state
- long-running request behavior
- 3D/time-dependent parity review
- AI context compatibility
- final integration audit

Ek sorumluluk:

Semantic error model ve final feature completeness audit.

---

# 29. İlk paralel aşama

Kod başlamadan üç kişi de farklı açıdan güncel frontend discovery yapmalıdır.

### Track A

Map/layer/time architecture’ı inceler.

### Track B

Route/result/analysis architecture’ı inceler.

### Track C

Mission state/request/error/assistant architecture’ı inceler.

Sonuçlar kısa bir ortak integration note’ta birleştirilir.

Hiç kimse kendi başına yeni architecture icat etmez.

---

# 30. Shared foundation merge gate

Feature branch’leri tam hız paralel gitmeden önce aşağıdaki contract’lar stabil hale gelmelidir:

- capability state
- validity/provenance representation
- semantic errors
- layer metadata
- route identity/invalidation
- mission-time identity
- analysis job lifecycle

Bu foundation mümkün olduğunca küçük olmalıdır.

Ama bütün feature branch’lerin aynı temel kavramları farklı şekillerde implement etmesini engellemelidir.

---

# 31. Conflict avoidance

Paralel çalışan kişiler:

- aynı shared primitive’i iki kez yazmamalı,
- aynı API response için farklı type oluşturmamalı,
- aynı backend field’a farklı human meaning vermemeli,
- ayrı time controller oluşturmamalı,
- ayrı provenance badge sistemi oluşturmamalı,
- ayrı analysis job state machine oluşturmamalı.

Shared contract değişikliği gerekiyorsa küçük, izole commit olarak önce merge edilmelidir.

---

# 32. Önerilen milestone sırası

## M0 — Baseline

Current frontend understood.

Tests green/baselined.

Screens visually recorded.

---

## M1 — Integration foundation

Capability.

Validity.

Errors.

Layer metadata.

Route invalidation.

Time identity.

---

## M2 — Planner request extensions

All advanced optional fields supported.

Disabled state confirms old request semantics.

---

## M3 — Static scientific layers

Earth visibility.

DEM uncertainty.

Roughness.

PSR.

Safe Haven.

Survival.

Thermal dwell.

---

## M4 — Cell telemetry

All new cell outputs.

---

## M5 — Route result blocks

Safety.

Slip.

Risk.

Roughness.

Uncertainty.

Survival.

Thermal.

Haven.

Earth visibility.

---

## M6 — Time-dependent visualization

Earth series.

Uncertainty series.

Illumination corridor.

Thermal/survival slices.

Single time controller.

---

## M7 — Robustness analyses

Stress-test.

DEM route uncertainty.

Risk sweep.

Thermal envelope.

PSR validation.

---

## M8 — Recovery / replan

Recovery suggestion.

Entrenchment.

Communication window.

---

## M9 — Offline validation

MoonPlanBench evidence.

---

## M10 — Hardening

Cross-feature testing.

Visual regression.

Performance.

Error states.

3D parity.

AI compatibility.

Full feature-loss audit.

---

# 33. Test strategy

Her feature en az dört seviyede test edilmelidir.

---

## 33.1 Contract tests

Frontend parser exact backend fixture ile çalışmalı.

Cases:

- complete response
- optional blocks absent
- unavailable
- NaN
- zero
- negative margin
- binary f32
- coarse grid
- provenance

---

## 33.2 Behavior tests

Örnek:

Risk disabled:

`risk_alpha` gönderilmez.

Risk enabled:

explicit alpha gönderilir.

Earth visibility disabled:

old plan request semantics.

Thermal assumed heater:

assumption visible.

---

## 33.3 Rendering tests

- continuous raster
- categorical raster
- binary mask
- NaN
- coarse grid
- route profile
- negative safety margin
- fan chart
- uncertainty band
- heatmap
- vector action field

---

## 33.4 Workflow tests

PLAN → Generate → ANALYZE.

Advanced constraint → solve.

Constraint infeasible.

Edit/Replan.

Route invalidation.

Post-analysis stale cancellation.

2D→3D.

Playback.

Selected cell.

AI existing workflow.

---

# 34. Non-regression suite

Bütün yeni features disabled iken:

old behavior expected.

Bu test ayrı tutulmalıdır.

Bu proje için frontend tarafındaki en önemli regression testlerinden biridir.

---

# 35. Feature-specific error fixture zorunluluğu

Aşağıdakiler mutlaka fixture/test edilmelidir:

- Earth link unavailable
- Safe Haven NaN/unreachable
- stress-test failure
- uncertainty cache absent
- safety-check 422
- illumination corridor 404
- illumination unsupported/static series 422
- risk alpha invalid
- survival β infeasible 404
- thermal dwell unavailable
- thermal envelope cache missing 422
- thermostat assumption
- PSR validation unavailable
- MoonPlanBench artifact absent

---

# 36. Scientific integrity acceptance gate

Feature teknik olarak görünse bile aşağıdakiler yanlışsa tamamlanmış sayılmaz.

### A4

MODEL vs validation doğru mu?

### A1

Safe Haven generic safety olarak yanlış anlatılıyor mu?

### B5

Completion = safety gibi gösteriliyor mu?

### B3

Probability ve nominal terrain ayrılıyor mu?

### D3

Monitoring ile proof ayrılıyor mu?

### A2

Model corridor gerçek guaranteed sunlight diye anlatılıyor mu?

### C3

MODEL slip measured diye gösteriliyor mu?

### B2

CVaR physical uncertainty ile karıştırılıyor mu?

### C4

Roughness per-cell rock count diye gösteriliyor mu?

### D2

Benchmark condition kayboluyor mu?

### B1

Assumed failure rate saklanıyor mu?

### C6

UNCALIBRATED thermal result validated gibi sunuluyor mu?

Bu sorulardan herhangi biri “evet” ise feature done değildir.

---

# 37. Bilinen backend açıkları frontend tarafından gizlenmeyecek

Aşağıdaki backend limitations UI veya provenance seviyesinde gerektiğinde korunmalıdır:

## B5 planner battery/time mismatch

Frontend kendi battery correction’ını üretmez.

## Thermal violations

C6 violation’a süre ekledi; thermal physics’i validate etmedi.

## Heater

Thermostat model assumption.

## LPR-1 Safe Haven

Bazı Site11 koşullarında usable Haven yok.

## B1 night infeasibility

β constraint gerçek no-route üretebilir.

## Recovery policy discretization limitation

Result kesin recovery guarantee gibi gösterilmez.

## Thermal CVaR

Yok.

Frontend implement etmez.

---

# 38. Theme-preservation gate

Her yeni UI addition mevcut LunaPath system’ine benzemelidir.

Review sırasında şu sorular sorulmalıdır:

- Existing typography mi kullanılıyor?
- Existing spacing mi?
- Existing panel surfaces mi?
- Lavender yalnız interaction accent olarak mı kullanılıyor?
- Risk colours yalnız safety semantics için mi?
- Yeni feature canvas’ı küçültüyor mu?
- Yeni feature onlarca permanent card yaratıyor mu?
- 3D viewport eskiye göre daha az mı kullanışlı?
- Engineering hierarchy korunuyor mu?

Yeni backend complexity görsel clutter’a dönüşmemelidir.

---

# 39. 2D / 3D parity

Bütün feature’ların her iki renderer’da birebir aynı representation’a sahip olması zorunlu değildir.

Ancak hiçbir backend feature sadece renderer limitation yüzünden kaybolmamalıdır.

Minimum:

- raster data 2D’de inspect edilebilir,
- meaningful terrain overlay’ler 3D’de mümkün olduğunda drape edilebilir,
- route profile data her iki mode’da playback ile accessible,
- time-dependent layers same mission time kullanır,
- selected cell semantics renderer’dan bağımsızdır.

---

# 40. Datalink ve mission status semantics

Backend artık gerçek communication/window result ürettiği için mevcut static status göstergeleri backend data varsa onu yansıtabilir.

Ancak:

system/API connectivity

ile

Earth communication visibility

aynı şey değildir.

İkisi farklı semantic kavram olarak korunmalıdır.

---

# 41. Performance acceptance

Yeni feature’lar eklenince:

- normal PLAN interaction yavaşlamamalı,
- map pan/zoom her layer request’inde full reparse yapmamalı,
- 3D orbit büyük f32 array decode yüzünden bloklanmamalı,
- stress/survival job route viewport’u dondurmamalı,
- time scrub mümkün olduğunca interactive kalmalı,
- redundant fetch engellenmeli.

Expensive analysis lazy/on-demand olabilir.

Feature’ın lazy olması feature kaybı değildir.

Feature’ın hiç erişilememesi feature kaybıdır.

---

# 42. API coverage checklist

Aşağıdaki 13 yeni endpoint integration audit’inde tek tek işaretlenmelidir:

- GET `/api/earth-series`
- GET `/api/comm-window`
- GET `/api/safe-haven`
- POST `/api/stress-test`
- GET `/api/uncertainty-series`
- POST `/api/dem-uncertainty`
- POST `/api/safety-check`
- GET `/api/illumination-corridor`
- POST `/api/risk-sweep`
- GET `/api/psr-validation`
- GET `/api/survival`
- GET `/api/thermal-dwell`
- GET `/api/thermal-envelope`

Bir endpoint bilerek UI’dan çağrılmıyorsa nedeninin dokümante edilmesi gerekir.

---

# 43. Existing endpoint extension checklist

Aşağıdakiler de unutulmamalıdır.

## `/api/plan-4d`

Yeni request options.

Yeni route result blocks.

Yeni route arrays.

## `/api/plan`

Risk.

Roughness weight.

Safety.

Slip.

Roughness.

Uncertainty.

## `/api/compare`

Roughness.

Safety margin ranking.

## `/api/plan-multi`

Roughness.

Safety margin ranking.

## `/api/cell-telemetry`

Safe Haven.

Survival.

Thermal.

Roughness.

PSR.

## `/api/replan`

Communication.

Recovery.

Entrenchment.

## `/api/pose`

Calculated communication time.

## `/api/rovers`

Slip model.

Regolith declared-only evidence.

## `/api/terrain` / `/api/layers`

New scientific layers and DEM provenance.

---

# 44. Feature Definition of Done

Bir feature ancak aşağıdaki koşulların tamamı sağlanıyorsa DONE kabul edilir:

1. Backend contract okundu.
2. Exact request type destekleniyor.
3. Exact response type destekleniyor.
4. Optional absence destekleniyor.
5. Availability destekleniyor.
6. Loading destekleniyor.
7. Semantic error destekleniyor.
8. Provenance/validity destekleniyor.
9. Relevant visualization çalışıyor.
10. Relevant planner behavior çalışıyor.
11. Route invalidation doğru.
12. Time synchronization gerekiyorsa doğru.
13. Cell telemetry gerekiyorsa doğru.
14. 2D/3D access kaybolmamış.
15. Existing behavior regression yok.
16. Unit/contract test var.
17. Workflow test var.
18. Scientific claim boundary doğru.
19. No fake values.
20. No hidden assumptions.

Bu 20 maddenin herhangi biri eksikse feature %100 entegre edilmiş sayılmaz.

---

# 45. Final feature-loss audit

Release öncesi aşağıdaki matrix tamamen yeşil olmalıdır.

| Feature | Planner | Layer | Time | Route result | Cell | Analysis | Provenance | Error | Tests |
|---|---|---|---|---|---|---|---|---|---|
| A4 Earth Visibility | ✓ | ✓ | ✓ | ✓ | as applicable | ✓ | ✓ | ✓ | ✓ |
| A1 Safe Haven | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| B5 Monte Carlo | — | — | route-based | ✓ | — | ✓ | ✓ | ✓ | ✓ |
| B3 DEM Uncertainty | indirect | ✓ | ✓ | ✓ | as contract | ✓ | ✓ | ✓ | ✓ |
| D3 Formal Safety | validation | — | route | ✓ | — | ✓ | ✓ | ✓ | ✓ |
| A2 Illumination Corridor | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ |
| C3 Slip | physics already backend | rover/model | — | ✓ | — | ✓ | ✓ | ✓ | ✓ |
| B2 CVaR | ✓ | indirect | — | ✓ | — | ✓ | ✓ | ✓ | ✓ |
| C4 Roughness + PSR | ✓ roughness | ✓ | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| D2 MoonPlanBench | — | — | — | — | — | offline evidence | ✓ | artifact state | ✓ |
| B1 Survival | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| C6 Thermal Dwell | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

---

# 46. Final release gate

Entegrasyon tamamlandı denmeden önce:

### Functional

Tüm 12 feature audit edildi.

### API

13 yeni endpoint ve existing extensions audit edildi.

### Backward compatibility

All advanced features OFF → old behavior preserved.

### UI

Existing LunaPath visual system preserved.

### Mission workflow

PLAN → SOLVING → ANALYZE → PLAYBACK → REPLAN çalışıyor.

### 2D

New layers inspect edilebiliyor.

### 3D

Existing flagship simulation bozulmamış; suitable new time/environment overlays integrated.

### Data integrity

5 m / 320 m resolution mix doğru.

### Nodata

NaN ≠ 0.

### Scientific integrity

Validity + claim + assumptions visible.

### Performance

Heavy analysis UI’yı kilitlemiyor.

### Error semantics

404/422/unavailable/network ayrımı doğru.

### AI

Existing assistant behavior korunuyor; unavailable data fabricate edilmiyor.

### Testing

Typecheck/lint/unit/integration/build/E2E baseline’dan kötü değil.

---

# 47. Claude Code'a verilecek çalışma talimatı

Bu planı uygularken:

1. Mevcut güncel repo’yu önce incele.
2. Bu dokümandaki hiçbir dosya/klasör/component yapısını varsayma.
3. Mevcut architecture ve design system’i koru.
4. Önce backend frontend contract dokümanını oku.
5. Backend logic’i frontend’de tekrar implement etme.
6. Backend output’u source of truth kabul et.
7. Additive integration yap.
8. Existing feature silme veya davranışını değiştirme.
9. New capability unavailable ise graceful degradation yap.
10. Missing backend data yerine mock değer koyma.
11. Feature disabled olduğunda old behavior’ı koru.
12. Semantic 404’leri network error yapma.
13. Long-running computationlarda fake percentage gösterme.
14. Scientific validity ve assumptions’ı kaybetme.
15. Her feature için Definition of Done checklist’ini kapat.
16. Her anlamlı değişikliği küçük, reviewable commit’lere böl.
17. Parallel çalışan diğer workstream’lerin shared contracts’ını duplicate etme.
18. Bir contract belirsizse tahmin etme; backend contract’a dön.
19. Bilinen backend limitation’ı frontend patch’iyle gizleme.
20. Son aşamada 12-feature loss audit yapmadan işi tamamlandı ilan etme.

---

# 48. Başarı kriteri

Bu entegrasyonun başarısı:

“Yeni backend özelliklerinin ekranda bir yerlerde görünmesi”

değildir.

Başarı:

**Mevcut LunaPath aynı ürün olarak kalırken backend’in yeni scientific, mission-safety, uncertainty, robustness ve recovery yeteneklerinin tamamının doğru semantik, doğru provenance ve doğru interaction lifecycle ile frontend’e taşınmasıdır.**

Final ürün:

- eski kullanıcı akışını korumalı,
- advanced operator’a yeni capability’leri vermeli,
- backend olmayan data’yı uydurmamalı,
- mission infeasibility’yi dürüst göstermeli,
- model/measurement ayrımını korumalı,
- 2D/3D mission environment’i bozmamalı,
- route analysis’i belirgin şekilde zenginleştirmeli,
- ve hiçbir backend feature’ını sessizce kaybetmemelidir.