# A izi — frontend entegrasyonu ilerleme kaydı

`goktug/tuna-backend-A` dalı. `backend-enhance-entegrasyon-2-kisi.md` §4'teki **A kişisinin**
görevleri. B kişisinin izine (D3, C3, B2, B5, D2, `analysis-job/`, `.gitattributes`) dokunulmadı.

Bu belge ne yapıldığını ve **neden öyle yapıldığını** tutar. Diff'in göstermediği kararlar burada.

---

## Durum

| Kod | Feature | A'nın payı | Durum | Nerede |
|---|---|---|---|---|
| C4 | Roughness + PSR | tam | **bitti** | `analysis-layers/`, `psr-validation/`, `RoutePriorities` |
| A1 | Safe Haven | tam | **bitti** | `safe-haven/` + `time-axis` kısıtı |
| A4 | Earth Visibility | tam | **bitti** | `earth-visibility/`, `analysis-layers/` + `time-axis` kısıtı |
| B3 | DEM Uncertainty | katman yarısı | **bitti** | `analysis-layers/` (4 katman), `layer-provenance/` (pedigree + seri) |
| B1 | Survival | katman yarısı | **bitti** | `coarse-fields/` |
| C6 | Thermal Dwell | katman yarısı | **bitti** | `coarse-fields/`, `thermal-envelope/` |
| A2 | Illumination Corridor | tam | **bitti** | `illumination-corridor/` + `time-axis` kısıtı |
| — | Hücre telemetrisi | tam | **bitti** | `mission-context/` — C4, A1, B1, C6 blokları |

Kontroller: `typecheck` · `lint` · `vitest` · `build` — hepsi yeşil.
Test sayısı 14 dosya / 180 testten **29 dosya / 332 teste** çıktı.
A'ya ait 18 uç isteği canlı backend'de 200 döndü, kancaların gönderdiği parametrelerle.

---

## Faz 0 — ortak zemin

### Fixture'lar: alan adı tahmin edilmez

`frontend/src/net/__fixtures__/` altında **çalışan backend'den alınmış gerçek yanıtlar** var.
Elle yazılmadı, sözleşme belgesinden türetilmedi. Sebep: belge `time_to_safe_haven` alanının
varlığını söylüyor ama `time_to_haven_finite_fraction`'ın da geldiğini, ulaşılamayan hücrenin
`null` mı `NaN` mi olduğunu, `cost_breakdown.total`'ın null olabildiğini söylemiyor. Üçü de
belgeyi okuyarak tahmin edilenden farklı çıktı.

İki halde yakalandı: `roughness`/`psr` için cache üretilmeden **önce** (`.unavailable`) ve sekiz
adımlık `scripts/setup_caches.py` bittikten **sonra** (`.available`). Yokluk testleri o çifte
karşı yazıldı.

### Fixture'ların çözdüğü dört şey

**`uncertainty-series` boşken 404 değil 200 döner.** Gövdede
`{"model": "unavailable", "reason": ...}` taşır, yanında gerçek bir `slices` ve `start_utc` ile.
Sadece `response.ok`'a bakan bir çağıran "veri var" sonucuna varır. `capabilityFromModel` bunun
için var.

**422 üç ayrı durumu kapsıyor.** Eksik zorunlu parametre (`survival` `goal_row` ister),
gerçekten imkânsız istek (geçilemez hedef), ve eksik cache (`thermal-envelope`). Status tek
başına ayırt edemiyor — `net/errors.ts`'in tek dosyada olmasının gerekçesi bu.

**`cost_breakdown` değerleri null olabilir, ve null "veri yok" demek değil.** Rover'ın eğim
sınırı dışındaki bir hücrede `slope`, `energy` ve `total` null gelir; orada null **sonsuz**
katkı, yani hücre geçilemez demek. Sıfır olarak çizmek gerçeğin tam tersini söyler: backend'in
"geçilemez" dediği yere mümkün olan en ucuz hücreyi çizer.

**`time_to_safe_haven`'ın tek yanıtta üç farklı nodata gösterimi var.** Manifestteki
`fields.time_to_safe_haven.nodata` bir **sayaç** (250 000 hücrede 20 236). Değerin kendisi f32
yükünde **NaN** olarak gelir (`binary_format.nodata: "NaN"`). `cell-telemetry`'de aynı olgu
`time_to_safe_haven_h: null` olur. Üç kodlama, tek anlam: ulaşılabilir safe haven yok. Hiçbiri
sıfır saat değil.

### B kişisinin primitifleri — beşin üçü yazıldı

B yokken A'nın işi derlenmiyordu. Yazılanlar ve yazılmayanlar:

| B'nin maddesi | Karar |
|---|---|
| `mission/capability.ts` | **yazıldı** — A'nın bağımlılık omurgası |
| `net/errors.ts` | **yazıldı** — 404/422 vakaları A'nın |
| `mission/routeIdentity.ts` + App.tsx alanı | **yazıldı** — §6.3 App.tsx'i tek dokunuştan sonra kapatıyor, sadece `missionTime` eklemek B'yi kapalı bir dosyayı açmaya zorlardı |
| `features/analysis-job/` | **atlandı** — B'ye özel, A'nın rota sonrası işi yok |
| `.gitattributes` + renormalize | **bilerek atlandı** — depo geneli renormalize, berke dallarından gelecek bir sonraki merge'i okunmaz yapar (bkz. §"satır sonları") |

### `capability.ts` — `unavailable ≠ error` tip düzeyinde

Yedi durum: `idle | loading | ready | unavailable | unsupported | error | stale`.
Birlik tipi `unavailable`'a `reason` verip `error` vermiyor, `error`'a `error` verip `reason`
vermiyor, ve ikisine de `value` vermiyor. Sebep: eksik cache **çalışan bir sistem** hakkında
doğru bir ifade, hata değil; hatayı eksik cache gibi göstermek ise gerçek arızayı gizler.

Spec'in `available` durumu `idle` olarak adlandırıldı: "available" veri hakkında bir iddiadır
("bu var"), oysa sormadan önce o iddiaya hakkımız yok. Kastedilen "henüz bakmadık".

### `errors.ts` — 404 iki farklı şey demek

```
GET /api/layers/roughness   404  "run scripts/build_roughness_cache.py"
POST /api/plan-4d           404  "...edges would have driven the rover into a cell with
                                  no Earth visibility..."
```

Birincisi cache üretmemiş bir makine. İkincisi kusursuz çalışan planlayıcının "senin
kısıtlarınla rota yok" demesi — bir **misyon bulgusu**, muhtemelen kısıt feature'ının ürettiği
en değerli şey. İkisini "İstek başarısız" diye göstermek yanlış; aynı göstermek daha yanlış.

Sınıflandırma backend'in kendi `detail` metnine bakıyor. Metne bakmak çirkin; alternatifi daha
kötü: dürüst alternatif backend'in yaymadığı makine-okunur bir hata kodu, dürüst olmayanı her
404'ü aynı saymak. Eşleşen metinler fixture'lardan geldiği için backend'de bir ifade değişikliği
**testi kırar**, üretimde yanlış etiketlenmiş bir panel olarak değil.

---

## Faz 1 — C4 Roughness + PSR

### Karar: yeni rasterlar overlay `field` komutu, yeni `MapCanvas` prop'u değil

`App.tsx:359` yedi temel gridi string sabitle çekip `MapCanvas`'a yedi prop olarak veriyor.
Yeni katmanı öyle eklemek her katman için App.tsx'i düzenlemek demek — ve §6.3 App.tsx'i tek
dokunuştan sonra kapatıyor. Overlay sistemi zaten çözüyor:

- `FieldCommand` kendi `rows`/`cols`'unu taşıyor ve `drawField` (`overlay/draw2d.ts:245`)
  `imageSmoothingEnabled = false` ile alanın kendi çözünürlüğünde bastırıyor. **Bu zaten A'nın
  ikinci semantiği**: "320 m ≠ 5 m, kaba ürünler blok sınırlarını korur", ve kodu hazırdı.
- Overlay'ler toplanabilir, yani `psr` herhangi bir temel katmanın üstünde durabilir — A'nın
  dördüncü semantiği ("PSR yasak bölge değil, analiz verisi"). Radyo düğmesi bunun tersini
  söylerdi: bir görünüm modu diğerini kapatır.
- `MapCanvas.tsx` feature'a özel çizim almıyor; kabuk sözleşmesi bunu yasaklıyor.

Sonuç: `layer-picker` yedi yollu radyosuyla aynı kaldı, yanına **toplanabilir** overlay
listesi olan `features/analysis-layers/` geldi.

### `/api/profiles` her zaman `w_roughness` gönderiyor

`scenarios.py` ve `constants.py`'de statik katalog sabiti — roughness katmanı yüklü olmasa da
dönüyor. `planRoute` ağırlık nesnesini olduğu gibi serileştirdiği için
`setWeights({ ...profile.weights })` bir profil seçildiği anda beşinci ağırlığı **her plan
isteğine** sokuyordu, kriterin hiçbir şeyi yönlendirmediği makinelerde bile.

Düzeltme: `applyProfile` dört ağırlığı **adıyla** kopyalıyor, spread etmiyor.
`PlanWeights.w_roughness` opsiyonel ve yalnızca operatör sürgüyü oynattığında set ediliyor;
sürgü de yalnızca `/api/terrain` katmanı listelediğinde beliriyor.

Bu §2'nin non-regression kuralı: kapalı bir feature isteği **bayt-bayt aynı** bırakır.
`net/planRequest.nonregression.test.ts` bunu sabitliyor ve bu izdeki en önemli test.

### `CoreWeightKey`

`w_roughness` opsiyonel olunca `keyof PlanWeights` kirlendi ve `weights[key]`
`number | undefined` oldu. Dört zorunlu ağırlığı ayrı adlandırmak (`CoreWeightKey`), "ağırlıklar"
üzerinde dönen bir tablonun hep var olan dördü kastetmesini sağlıyor.

---

## Faz 2 — A1 Safe Haven

### NaN ≠ 0, ölçülerek kanıtlandı

`time_to_safe_haven` alanı, downsample 2, 250×250:

```
X-Layer-Nodata: 20236        yükteki NaN sayısına tam eşit
NaN hücre     : 20236 (%32,4)  ulaşılabilir haven yok  -> boyanmıyor
tam sıfır     : 1023           bu hücre haven'in kendisi -> rampa minimumu
sonlu aralık  : 0.000 .. 39.314 h
```

NaN'i sıfıra çevirmek o 20 236 hücreyi 1 023 gerçek sıfırla birleştirir ve harita sahanın üçte
birini güvenli ilan eder. `fieldValues` NaN'i `null`'a çeviriyor, renderer null'ı boyamıyor, ve
`time_to_safe_haven` rampasında "ulaşılamaz" için **stop yok** — o hücre rampanın uzak ucunda
değil, tamamen dışında.

---

## Faz 3 — A4 Earth Visibility

### Mission saati: bir kararı düzelttim

Saati önce **boş** başlattım, gerekçesi "epoch uydurmayalım"dı. Tarayıcıda görüldü ki
`time-axis` yalnızca `analyze` modunda mount oluyor — dolayısıyla **plan** modunda epoch'u
kimse ayarlamıyor ve A1/A4 kalıcı olarak "epoch gerekiyor" gösteriyordu.

Gerekçe yanlıştı. Backend'in "epoch yok" `unavailable`'ı, ne sorduğumuz hakkında bir ifade;
bu dağıtımın neye sahip olduğu hakkında değil. Epoch seçmek bir **planlama kararı**; uydurma
olan, epoch'suz haven haritası çizmek olurdu.

Şimdi `SESSION_MISSION_TIME` saati oturum başlangıcıyla tohumluyor ve **her panel kullandığı
epoch'u yazıyor**. `useTimeAxis` kendi modül düzeyi `new Date()`'ini bıraktı ve paylaşılan saati
okuyor — §5.8'in tek kanonik ekseni. İki katmanın iki farklı ana ait olması, tek ana ait
olmalarıyla birebir aynı görünür; ayırt edilemeyen hata sınıfı budur.

### Uydu penceresi: bilinmeyen süre sayıya çevrilmez

`visible_now: true` + `minutes_remaining: null`, arama ufku bağlantı kesilmeden bitti demek.
"0 dakika kaldı" yazmak, verinin desteklemediği bir sinyal kaybını rapor eder.
`format.ts` üç durumu ayırıyor ve `search_limited`'ı ayrıca söylüyor: sınırlı bir cevap,
sınırsız bir cevaptan farklı bir iddiadır ve fark sayının içinde görünmez.

---

## Bu makinede iş gören notlar

**Satır sonları.** `App.tsx`, `mission/types.ts`, `features/registry.ts`, `api.ts`,
`colormap.ts`, `net/types.ts` **CRLF**. `Write` aracı ve `sed -i` LF'e çeviriyor; bu dosyalara
Python ile `open(..., "rb")` / `"wb"` yazın. Bir kez `colormap.ts` karışık kaldı ve
normalize edildi. `git diff --ignore-cr-at-eol` gerçek farkı gösterir.

**`backend/.venv` boş.** İçinde `pip` ve `setuptools` var, `uvicorn` yok. Sistem Python 3.11
kullanın:
`C:\Users\goktugtabak\AppData\Local\Programs\Python\Python311\python.exe -m uvicorn ...`

**Konsol cp1254.** `export PYTHONIOENCODING=utf-8` olmadan Türkçe karakterli çıktı
`UnicodeEncodeError` veriyor.

**Chrome'da planner sahnesinde ekran görüntüsü alınamıyor.** CDP `captureScreenshot` sürekli
zaman aşımına uğruyor (splash ve hangar sorunsuz). Erişilebilirlik ağacı ve backend logu
çalışıyor; doğrulamayı onlarla yapın. GPU/compositor, kod değil.

**Veri paketi zip'i eski pencereye ait.** Kökteki `LunaPath-veri-paketi-*.zip`,
`window_offset {2400, 2500}` için üretilmiş; yerel veri `{1500, 1000}`. Kendi `KURULUM.md` §8'i
karıştırmayın diyor. Yalnızca pencereden bağımsız olan `moonplanbench` alındı.

---

## Faz 4 — B3, B1, C6, A2 ve telemetrinin tamamı

### B3: dört katman, iki farklı iddia

`p_traversable` ve `slope_sigma` **DERIVED** — klonlar üzerinde bizim hesapladığımız yayılım.
`elevation_sigma` ve `slope_sigma_nasa` **MODEL** — NASA'nın kendi yayımladığı hata modeli.
Aynı etiket altında toplanmadılar çünkü aynı tür iddia değiller, ve rozet her satırda
**yanıtın kendi `X-Layer-Validity` başlığından** okunuyor, tablodan değil.

Ölçülen: `slope_sigma` maks 5,79°, `slope_sigma_nasa` maks 15,51° — yaklaşık üç kat. Ortak bir
sayısal alan bizimkini sıfıra ezerdi ve ikisinin doğrudan kıyaslanabilir olduğunu ima ederdi.

`p_traversable`'ın **%30,3'ü** 0,05–0,95 belirsiz bandında. Iraksayan rampa tam o bandı en
yüksek sesle boyuyor: 0 ve 1 ikisi de *kesin*, ilginç olan aradaki.

`dem_uncertainty` pedigree'sinin üç `*_held_fixed` bayrağı ekranda: termal alan, uzak alan ve
Dünya görünürlüğü klonlanmadı. Yani bu katmanlardan okunan bant **arazi** belirsizliğidir,
misyon belirsizliği değil — ve bu sınır katmanların kendisinde görünmez.

`/api/uncertainty-series` aynı topluluğun zaman yarısı, `layer-provenance` altında. Grid
anahtarları diğer kaba ürünlerden **farklı**: `stride` / `row_offset` / `col_offset`, ve ilk
örneklenen hücre ince koordinatta (2, 2) — `coarsen` şeklini yeniden kullanmak alanı iki hücre
kaydırırdı. Şeritte iki bar var çünkü ilginç sayı `mean` değil `uncertain_fraction`: %6 belirsizle
0,90 ortalama emin bir cevap, %40 belirsizle aynı ortalama değil, ve yalnız ortalama gösterilirse
ikisi ayırt edilemez.

### B1 + C6: kategorik alanlar ayrı maskeler

`best_action` ve `side` `units: "code"`. Overlay'in `FieldRamp`'ı min/max arası enterpolasyon
yapar; iki kod arasında ara renk üretmek "yarı bekle yarı kuzeye sür" gibi olmayan bir eylem
uydurmaktır. Her kategori **kendi tek renkli maskesi** olarak yayımlanıyor — enterpolasyon
yapısal olarak imkânsız, çünkü iki ayrı maske arasında interpole edilecek bir şey yok.

`best_action` 11 kod taşıyor (0–7 yön, 8 bekle, 254 zaten güvenli, 255 yok) ama dört kategori
çiziliyor. 125×125'te sekiz yön rengi okunmaz gürültü olurdu, ve tek bir bloğun yönü zaten hücre
kartında (`best_action_name`). Haritanın söyleyebileceği şey kararın **türü**.

Ölçülen: `open_ended == 1` ⟺ `side == 0` ⟺ `max_dwell_h == 24.0`. 1139 blok lookahead'e
**kırpılmış**. "En az 24 s" ile "24 s" farkı budur ve panel bunu taban olarak yazıyor.

Survival'in `fraction_zero`'su **%28,5** — geçilebilir blokların neredeyse üçte biri güvenli
kümeye hiçbir eylemle ulaşamıyor. Dört özet sayıdan biri gibi değil, bulgu olarak gösteriliyor.

Efsanede her kategorinin hücre sayısı var: `wait` bu pencerede 15 625 blokta **üç** blok, ve
sayısız bir renk kutusu onu bir bölge gibi okutur.

### C6 zarf: dördüncü karar rengi yok

288 kutuluk matris, 12 Güneş yüksekliği × 24 Güneş-paralel eğim. `unsampled` (84 kutu, **%29**)
boş bırakılıyor — dolgusuz. "heat1d izi bu geometriye hiç düşmedi" bir sonuç değil, veri
yokluğudur; dördüncü bir ton onu "soğuk" ile aynı eksene koyardı. Yanıtta hiç geçmeyen bir kutu
ise **taranmış** çiziliyor: o, backend'in cevap vermemesi, "burada bir şey yok" demesi değil.

`unlimited` ve `unsampled` ikisi de boş `dwell_h` taşıyor. Biri matristeki en iyi sonuç, diğeri
hiç sonuç değil; tooltip metinleri karıştırılamayacak şekilde ayrı yazıldı.

Satırlar ters çevrildi: yanıt kutu 0'ı en düşük yükseklikte indeksliyor, bu bir dizi için doğru
bir grafik için yanlış — operatör "Güneş yüksek"i üstte okur.

### A2 koridor: `enforced: false` panelin ilk satırı

Küp `[T, 125, 125]` slice-major, dilim **paylaşılan mission saatinden** geliyor. Kendi sürgüsü
yok — o ikinci bir saat olurdu.

`corridor.enforced` false: planlayıcı bu koridora göre kısıtlanmamış. Panel bunu kutulu ve amber
yazıyor, çünkü bir rotanın yanına çizilen koridor "rota içinde kaldı" okumasını davet eder.
`lit_rule_definition`, `pruning` ve `edge_rule` metinleri **alıntılanıyor** — bir koridor onu
üreten kural kadar anlamlıdır ve kuralı yeniden ifade etmek onu değiştirir.

`dwell_hours`'ta sıfır **null'a çevrilmiyor**: koridorda olup önünde saat kalmamış bir blok,
koridor dışındaki bir bloktan farklı bir ifadedir ve birincisini yalnızca rampanın alt ucu söyler.

### Kısıtlar: contributor hattı 4-B plan düğmesine bağlandı

A4, A1 ve A2'nin "tam" payındaki **kısıt** kısmı. Üç anahtar `time-axis` panelinde, "Plan through
time" düğmesinin yanında — kısıt onu kullanan düğmenin yanında durmalı; başka bir paneldeki bir
anahtarın sessizce buradaki düğmeyi değiştirmesi daha kötü olurdu.

Backend alan adı `require_continuous_illumination`, `require_illumination_corridor` **değil**:
koridor kuralın kurulduğu hacim, kural ise sürekli aydınlıkta kalmak. `Plan4DRequest`'ten
okundu, uç adından tahmin edilmedi.

Üçü de kapalı başlıyor ve kapalı bir kısıt isteğe **hiçbir alan eklemiyor** — `false` bile değil,
çünkü `false` belgelenmiş bir backend varsayılanını ezerdi.
`net/planRequest.nonregression.test.ts` bunu sabitliyor.

Verisi olmayan bir kısıt listede kalıp devre dışı görünüyor: hiç var olmamış bir kontrol ile
bu dağıtımda çalışmayan bir kontrol farklı şeylerdir.

### Zaman ekseni: beş ürün tek saatte

`survival` ve `thermal-dwell` `t_hours` alıyor. Mission saatinin `offsetHours`'ı ikisine de
geçiyor, iki ondalığa yuvarlanarak (saniyelik hareket saatlerce geniş dilimleri yeniden
çekmesin). Böylece aydınlanma serisi, Dünya serisi, belirsizlik serisi, koridor küpü ve iki kaba
alan aynı anı gösteriyor. Farklı anlar tek haritada, tek an gibi görünür.

---

## Doğrulama

| Kontrol | Sonuç |
|---|---|
| `npm run typecheck` | temiz |
| `npm run lint` | temiz (`--max-warnings 0`) |
| `npx vitest run` | 29 dosya / 332 test |
| `npm run build` | temiz |
| A'nın 18 canlı uç isteği | 18/18 → 200 |
| Vite modül dönüşümü (12 modül) | hepsi temiz |

`net/planRequest.nonregression.test.ts` her fazda ayrıca koşuldu: tüm ileri kısıtlar kapalıyken
`/api/plan` ve `/api/plan-4d` gövdeleri bayt-bayt aynı.

**Tarayıcı doğrulaması yarım kaldı.** Claude in Chrome eklentisi oturumun ortasında bağlantısını
kaybetti; makinede Chrome kurulu değil (Brave var) ve Brave'i başlatmak da eklentiyi geri
getirmedi. Oturumun başında çalışıyordu: splash ve hangar ekran görüntüleri alındı,
erişilebilirlik ağacından `analysis-layers` panelinin üç satırı, PSR doğrulamasının gerçek
sayıları (Jaccard 0,612 / recall %84,7 / precision %68,8), `Surface Roughness 0,150` sürgüsü ve
roughness'in `format=f32&downsample=2&rover_id=lpr_1` isteği doğrulandı. Planner sahnesinde
`captureScreenshot` zaten zaman aşımına uğruyordu (GPU/compositor). Sonraki fazlar ağ ve modül
düzeyinde doğrulandı; görsel kontrol operatöre kaldı.

---

## Bir kez görülen, tekrarlanamayan backend çökmesi

7 Eylül 2026, kokpit Brave'de yüklenirken backend düştü:

```
SPICE(BADSUBSCRIPT): Subscript out of range on file line 949, procedure "tkfram".
Attempt to access element 4 of variable "angles".
str2et_c->spkpos_c->str2et_c->spkpos_c->spkpos_c->...->SPKGPS->REFCHG
```

Çökmeden hemen önceki istekler frontend'in normal açılışı: yedi temel katman, `/api/earth-series`
ve `/api/uncertainty-series` (epoch `2026-09-07T07:40:38.572Z`), tekrarlanan `cost`/`traversable`.

**Tekrarlanamadı.** Denenenler, hepsi temiz:

- Aynı epoch'ta altı SPICE ucu seri — 6/6 200
- Dört SPICE ucu eş zamanlı — 4/4 200
- Cache'i atlatmak için üç farklı epoch × altı uç = 18 eş zamanlı istek, 20,8 s — biri hariç
  hepsi 200 (o biri `comm-window`'un o hücre/epoch için verdiği meşru 4xx), SPICE hatası yok

İlk bakışta traceback'teki iç içe geçmiş `str2et_c`/`spkpos_c` zinciri thread-safety gibi
duruyor — bir çağrı yığını normalde böyle görünmez ve CSPICE thread-safe değil, FastAPI de senkron
uçları threadpool'da koşturur. **Ama bu bir hipotez, tanı değil**: yukarıdaki eş zamanlı yük onu
doğrulamadı. `tkfram` / `angles[4]` bir **frame kernel** okuması, yani sebep kernel tarafında da
olabilir.

Kayda geçiriliyor çünkü A'nın entegrasyonu SPICE çağıran uç sayısını belirgin şekilde artırdı:
önce yalnız `illumination-series` çağırıyordu, şimdi earth-series, uncertainty-series,
comm-window, safe-haven, corridor, thermal-dwell ve survival da çağırıyor. Yük profili değişti.

Tekrarlarsa bakılacak yer backend: `spiceypy` çağrılarının çevresinde bir kilit, ya da
`kernels/*.tf` frame tanımı. Frontend tarafında yapılacak bir şey yok — istekler meşru, ve
sunucuyu çökertmemek için isteklerini seri hale getiren bir istemci sorunu gizler.

---

## Elle bakılacaklar (tarayıcı geri geldiğinde)

1. Her yeni katman **kapalı** başlıyor; kokpitin varsayılan hali büyümedi (§10).
2. Cache yoksa satır listede kalıyor, sebebi ve komutu yazıyor — kaybolmuyor.
3. `best_action` ve `side` ayrık renk, gradyan değil; efsanede sayılar var.
4. `time_to_safe_haven`'ın NaN hücreleri **boş**; sıfır hücreleri rampa minimumunda.
5. Termal zarfta `unsampled` kutular dolgusuz.
6. Koridor panelinde "Not enforced" satırı görünüyor.
7. Mission saati kaydıkça koridor dilimi, Dünya şeridi ve kaba alanların `T+` okuması
   **birlikte** hareket ediyor.
8. Kısıtlar kapalıyken 4-B istek gövdesi ağ sekmesinde eski haliyle birebir aynı.
