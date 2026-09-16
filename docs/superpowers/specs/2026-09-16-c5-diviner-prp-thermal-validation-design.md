# C5 — Termal doğrulama için doğru ürün kimlikleri (Diviner PRP + Williams 2019) — Tasarım Belgesi

**Tarih:** 16 Eylül 2026 · **Dal:** `tuna/backendEnhance` · **Kaynak madde:**
[12_faktor_backend_ozellik_arastirmasi_2026-09-03.md § C5](../../research/12_faktor_backend_ozellik_arastirmasi_2026-09-03.md)
· **Bağımlılık:** C4 (dışarıdan NASA ürünü indirip önbelleğe alma deseni), A4
(doğrulama betiği + rapor + saf modül üçlüsü), C1/C2 (`*_QUOTED` sözlüğü ve
"yayımlanmış bir sayıyı kendi aritmetiğinle yeniden üret" deseni), C6 (heat1d zarfı).

**Yol:** mevcut `backend/app/thermal_validation.py` genişletilir; PRP üçgen ağını
indirip önbelleğe alan bir betik; tek bir doğrulama/rapor betiği; iki `*_QUOTED` sözlüğü.

**Kapsam:** yalnızca `backend/app/`, `backend/test_*.py`, `scripts/`, `docs/`, `.gitignore`.
Frontend koduna dokunulmaz; `docs/frontend/3b-veri-sozlesmesi.md`'ye "C5 eki" yazılır
(yalnızca ekleme).

---

## C5 bir DOĞRULAMA özelliğidir

C1 ve C2 birer **model** özelliğiydi: yeni fizik ekliyor, bayrakla kapatılıyor, kapalıyken
bit-eşit oluyorlardı. C5 hiçbir fizik eklemez. Amacı **dürüst bir sayı** üretmektir.

- Uyum kötü çıkarsa kötü hâliyle yayımlanır.
- Modeli Diviner'a uydurmak (LUT, ofset, tau, eşik oynatmak) C5 **değildir**; o ayrı bir
  özelliktir (kalibrasyon) ve yapılırsa A1'den C2'ye kadar yayımlanmış her ölçümü
  geçersizleştirir.
- Bir parametrenin "daha iyi uysun diye" değiştirilmesi gerektiği ortaya çıkarsa, bu bir
  **bulgu** olarak yazılır ve parametreye dokunulmaz.

---

## İddia sınırı

1. **Diviner'ın ve Williams'ın sayıları ONLARIN.** PRP'nin `temp_avg`/`temp_max`'ı,
   Williams'ın 240 m/px mevsimsel haritaları, "1,3×10⁴ km² soğuk tuzak" — hepsi alıntı.
   `PRP_QUOTED` ve `WILLIAMS_QUOTED` sözlüklerinde, künyeleriyle, bizim ölçüm
   tablomuzdan ayrı durur.
2. **RMSE / Spearman / bias BİZİM.** Hangi alan, hangi çözünürlük, hangi n, hangi
   maskeleme ile hesaplandığı her tabloda yazılır.
3. **PRP bir ÖLÇÜM DEĞİL, ölçüme oturtulmuş bir MODELDİR.** PDS kataloğu (`prpds.cat`,
   16 Eylül 2026'da okundu) birebir şöyle diyor: *"thermal model fits to first mapping
   year Diviner polar observations"*, işlem düzeyi **CODMAC Level 5 / NASA Level 4**.
   Araştırma belgesinin "PRP'nin annual maximum ürünü tam bu istatistiğin **ölçülmüş**
   karşılığıdır" cümlesi bu yüzden fazla güçlüdür ve C5 onu düzeltir: karşılaştırma
   **MODEL ↔ MODEL-ÖLÇÜME-OTURTULMUŞ**'tur, MODEL ↔ MEASURED değil. Bizim tarafımız
   `MODEL`, PRP tarafı `DERIVED` etiketi taşır.
4. **PRP'nin her sütunu aynı şey değil.** Etiket dosyası (`dlre_prp.fmt`) üç türetilmiş
   niceliği ayrı ayrı tanımlıyor ve ikisi bizim sandığımız yerde değil:
   - `temp_max` = yıllık maksimum sıcaklık, **yüzeyde** hesaplanmış → bizim yıllık
     tepemizin karşılığı **budur**.
   - `temp_avg` = yıllık ortalama sıcaklık, **yüzeyin 2 cm altında** hesaplanmış → bir
     yüzey alanı değildir, bizim hiçbir alanımızın doğrudan karşılığı değildir.
   - `ice_depth` = modellenmiş buz kararlılık derinliği, `INVALID_CONSTANT = -999`.
     Bir ölçüm değildir; C5 onu karşılaştırmaya **sokmaz**.
5. **Bizim termal modelimiz hâlâ MODEL / UNCALIBRATED.** İyi bir RMSE bunu değiştirmez;
   yalnızca ona **beyan edilmiş bir hata bandı** kazandırır. "Artık MEASURED" denmez;
   `layer_validity` ve `weakest_validity` değişmez (C4'ün kararı korunur).
6. **n küçükse söylenir.** Site11 penceresinde PRP ~49 üçgen eder (ölçüm: sonda 4). Bu bir
   **sınırdır**, dipnot değil, ve güven aralığıyla birlikte yazılır.

---

## Kaynak notu (16 Eylül 2026'da PDS arşivinden birinci elden okundu)

Araştırma belgesi ürünü `DLRE_PRP_SOUTH.TAB` / `LRO-L-DLRE-5-PRP-V2.0` olarak adlandırıyordu
ama bir indirme adresi vermiyordu; 07 ve 11 no'lu belgeler yalnızca "Diviner'ı indirin"
diyordu. C5'in adı zaten "**doğru ürün kimlikleri**". Bulunan ve gerçekten `curl` ile
doğrulanan adresler:

| Ne | Adres | Durum |
|---|---|---|
| PRP koleksiyonu | `https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_prp/` | 200 |
| Güney tablosu | `.../dlre_prp_south.tab` | 200, **604 800 210 B** |
| Etiket | `.../dlre_prp_south.lbl` | 200 |
| Sütun tanımı | `.../label/dlre_prp.fmt` | 200 |
| Veri seti kataloğu | `.../catalog/prpds.cat` | 200 |
| ODE yardım sayfası | `https://ode.rsl.wustl.edu/moon/pagehelp/Content/Missions_Instruments/LRO/DIVINER/PRP.htm` | 200 |

Araştırma belgesindeki `https://pds-geosciences.wustl.edu/lro/lro-l-dlre-5-prp-v2/...`
biçimindeki PDS3 yolu **404** veriyor; ürün PDS4 paketi `urn-nasa-pds-lro_diviner_derived1`
altına taşınmış. Mevcut `scripts/diviner_validation.py`'nin işaret ettiği MIT Imbrium
`BROWSE/EXTRAS/ILLUMINATION/` adresi ise **aydınlanma** ürünüdür, Diviner sıcaklığı değil.

**Biçim (etiketten, varsayımla değil):** `RECORD_TYPE = FIXED_LENGTH`, `RECORD_BYTES = 210`,
`FILE_RECORDS = 2 880 000`, 1 başlık satırı + 2 880 000 veri satırı, 15 ASCII sütun:
`tri1_x..tri3_z` (üçgen köşeleri, Ay merkezli kartezyen, **km**), `tri_clon`, `tri_clat`
(**planetosentrik** derece), `tri_calt` (1737,4 km küreye göre yükseklik, km), `temp_avg`,
`temp_max` (**kelvin**), `ice_depth` (m).

**Üç uyumsuzluk, kaynakta:**
1. Katalog metni ağı "**288000** triangles" diyor; etiket ve dosya boyutu **2 880 000**
   diyor (604 800 210 / 210 = 2 880 001 = 1 başlık + 2 880 000). Makine-okunur etikete
   uyulur, katalog düzyazısında bir sıfır eksik.
2. Katalog "covers a square region centered on the pole to 80 degrees latitude" diyor —
   **kare** bir bölge, dolayısıyla köşeleri 80°'nin ekvator tarafına taşıyor. Ölçüldü:
   dosyadaki en düşük |enlem| **−75,905°**. 80°'nin kutup tarafı tamamen kapsanıyor, ki
   soğuk-tuzak alanı hesabı bunu gerektiriyor.
3. Ağ **Kaguya** lazer altimetre DEM'inden (Araki vd. 2009) türetilmiş; bizim gridimiz
   Site11'in 5 m/px LOLA ürünü. İki farklı topografya üzerinde iki farklı termal model —
   ko-registrasyon farkı bir hata kaynağıdır ve rapora yazılır.

Model yaklaşımı: **Paige vd., Science 330, 497 (2010)** ve onun çevrimiçi ek materyali.

---

## Belgenin dayattığı üç soru (ve cevapları)

### (a) `scripts/diviner_validation.py` bugün ne yapıyor; C5 onu genişletiyor mu, yerine mi geçiyor?

**Bugün:** elle indirilmiş bir **raster** (GeoTIFF/IMG) bekliyor
(`lunapath/data/raw/diviner_temperature.tif`), `rasterio.warp.reproject` ile bizim gridimize
yeniden projelendiriyor ve `thermal_comparison`'ı çağırıyor. Dosya yoksa nasıl indirileceğini
anlatıp **0 ile çıkıyor**. Diskte öyle bir dosya hiç olmadı; betik gerçek veriyle **hiç
koşmadı**. İçindeki `destination_transform` ise gerçek bir doğruluk dersi taşıyor (Round 2
H-3: `origin.y` üst kenardır ve `pixel_to_map_xy` onu 0. satırın **merkezi** sayar, dolayısıyla
yarım hücre kaydırma gerekir) ve `backend/test_review2_fixes.py`'deki **iki test** onu pinliyor.

**Sorun:** gerçek ürün bir raster değil, 605 MB'lık bir **ASCII üçgen ağı**. `reproject`
yolu onu tüketemez. Yani betik, var olmayan biçimdeki bir ürün için yazılmış bir taslak.

**Karar — C5 onun YERİNE GEÇER, ama dersini kaybetmez:**
- `destination_transform` saf bir coğrafi referans fonksiyonudur ve zaten
  `thermal_validation.py`'nin modül docstring'inin "fetch/reproject betiğin işi" dediği için
  yanlış yere düşmüştü. **`backend/app/thermal_validation.py`'ye taşınır.**
- `backend/test_review2_fixes.py`'deki iki H-3 testi yeni adrese **yönlendirilir**;
  iddiaları harfiyen aynı kalır, ders zayıflamaz.
- `scripts/diviner_validation.py` **silinir**. Yerine tek giriş noktası
  `scripts/validate_thermal.py` gelir.
- `backend/app/slip_model.py`'deki iki atıf (docstring + `NotImplementedError` metni) yeni
  betiğe güncellenir.

Gerekçe: iki betiğin de "termal gridi Diviner'a karşı doğrula" demesi, araştırma belgesinin
C5'i açarken şikâyet ettiği belirsizliğin ta kendisidir. **Tek betik, tek iş.**

### (b) `thermal_validation.py` neyi doğruluyor; C5 ona ne ekliyor?

**Bugün:** tek bir saf fonksiyon, `thermal_comparison(model_c, reference_c,
traversable_threshold_c=-150.0)` → `rmse_c`, `mae_c`, `bias_c`, `n_compared`,
`misclassified_traversable_pct`. İki **eş-kayıtlı, aynı şekilli** Celsius gridi varsayar.
Ölçeği, projeksiyonu, istatistik eşleşmesini hiç konuşmaz.

**C5 ekler:** Spearman; üç adayın yan yana karşılaştırılması; üçgen ağını pencereye örnekleme
ve **alan ağırlıklı** toplulaştırma; enlem/eğim kutularında LUT karşılaştırması; üçgen
alanlarından soğuk-tuzak alanının yeniden türetilmesi; `PRP_QUOTED` / `WILLIAMS_QUOTED`;
ve `destination_transform` (yukarıda). `thermal_comparison`'ın imzası ve çıktısı
**değişmez** — yedi mevcut test aynen geçer.

### (c) Belgenin istediği `scripts/validate_thermal.py` adı mevcut betikle çakışıyor mu?

Evet, ve (a)'daki kararla çözülür: **tek bir betikte toplanır.** Belgenin verdiği ad kullanılır.

---

## İstatistik eşleşmesi — C5'in en kolay yanlış yapılacak yeri

Görev tanımı "diskteki `thermal_grid.npy` gölge serisiyle eşlenmiş bir alandır" diyordu ve
üçüncü aday olarak `sunlit_peak_from_annual_peak_c` ile gölge eşlemesinin **geri alınmasını**
öneriyordu. **Ölçüldü (sonda 1): bu doğru değil.** Disk alanı eşlenmemiştir; eşleme yükleme
anında bir kez yapılır. Dolayısıyla tersini almak çifte-ters olurdu.

`data_loader.py:64-75` bunu zaten açıkça yazıyor: `thermal_grid.npy` **düzeltilmemiş sunlit
peak** tutar, `thermal_field: "sunlit_peak"` yetkili anahtardır, `thermal_shadow_coupled: true`
ise yorumu kodda **"legacy alias; see thermal_field"** olarak işaretlenmiş eski bir addır.
Yalan söyleyen bir etiket değildir; ama görev tanımını yanlış yönlendirmiştir, o yüzden burada
yazılıdır.

**Doğru üç aday (hepsinin RMSE'si yayımlanır, sonra hangisinin doğru eşleşme olduğu
gerekçesiyle söylenir):**

| # | Aday | Nasıl elde edilir | Ne olduğu |
|---|---|---|---|
| A | `thermal_sunlit_peak` | `thermal_grid.npy`, olduğu gibi | yalnız geometri; (eğim × bakı) LUT'u, gölge görmez |
| B | `thermal` | `annual_peak_c(sunlit_peak, shadow_ratio)` | gölge eşlenmiş **yıllık tepe** — **planlayıcının gerçekten kullandığı alan** |
| C | `thermal_min` | `shadowed_equilibrium_c(sunlit_peak, shadow_ratio)` | soğuk uç **dengesi** (bir maksimum değil) |

Ön beklenti: PRP `temp_max` gerçek bir topografya üzerinde aydınlanma dâhil hesaplanmış
yıllık maksimum olduğu için **B** kavramsal karşılıktır. Ama üçü de ölçülür ve üçü de
yayımlanır; tek bir sayı yayımlayıp "RMSE budur" demek burada yanlış olma ihtimali en yüksek
cümledir.

**Gece minimumu için aynı titizlik.** Williams'ın "min"i **mevsimsel bir minimum**dur.
Bizdeki `thermal_min` bir minimum değil, **denge**dir (yukarıdaki C). heat1d transientinin
gece dibi ise C6'nın zarf önbelleğinde durur (yüzey −232,4 °C'ye iner). İkisi farklı
büyüklüktür; hangisiyle karşılaştırıldığı adlandırılmadan sayı verilmez.

---

## Ölçek ve projeksiyon

- PRP düzenli bir raster değil, **üçgen ağ**. Ölçüldü (sonda 4): medyan üçgen alanı
  **0,1268 km²**, eşdeğer kenar **541 m**.
- Bizim gridimiz 500×500, **5 m/px**, polar stereografik, pencere `(2400, 2500)`.
- **Karşılaştırma kabanın çözünürlüğünde yapılır.** PRP'yi 5 m'e interpolasyon yapıp
  "210 000 hücreye yaydım" demek sahte bir örneklem büyüklüğü üretir. Bunun yerine: her PRP
  üçgeninin merkezi bizim gridimize düşürülür, o üçgenin kapsadığı bizim hücrelerimiz
  **toplulaştırılır**, karşılaştırma üçgen başına bir çift sayıyla yapılır. **n = üçgen
  sayısı**, her tabloda yazılır.
- **Toplulaştırma seçimi bir karardır:** PRP'nin üçgen değeri o **faseti**n (tek eğim, tek
  bakı) modellenmiş yıllık maksimumudur — faset-altı topografyanın maksimumu değil.
  Dolayısıyla bizim hücrelerimizin **ortalaması** dürüst eşdeğerdir. Yine de hem ortalama
  hem maksimum toplulaştırması ölçülür ve ikisi de yayımlanır.
- Koordinat dönüşümü `metadata.json`'daki `crs` + `origin` ve `grid_frame` üzerinden,
  `pyproj` ile yapılır; kendi projeksiyonumuz yazılmaz. Küre yarıçapı iki tarafta da
  **1 737 400 m** (PRP `A_AXIS_RADIUS = 1737.4 km`; bizim WKT `SPHEROID[...,1737400,0]`) —
  datum farkı yok.
- Pencere merkezi `pyproj` ile **−88,920375° / −72,669205°** çıktı; A1/C1'de kayıtlı
  −88,9205 / −72,6721 ile uyuşuyor (sonda 2).

**İki ayrı bölüm sunulur:**
1. **Site11 penceresi** — n ~49, güven aralığı geniş, öyle yazılır.
2. **LUT'un kendisi** — 80°S'e kadar olan ürünün tamamı ↔ bizim LUT'umuzun aynı
   enlem/eğim kutularında ürettiği değerler. n milyonlarca.

---

## Bakı (aspect) referans çerçevesi — ölçülen bir bulgu, düzeltilmeyen bir kusur

PRP üçgeninin **normali**nden eğim ve bakı hesaplanabilir, dolayısıyla LUT'u doğrudan
faset geometrisine karşı sınamak mümkün. Ama bir referans-çerçeve sorunu var:

- heat1d'in `slope_az` parametresi, kurulu paketin docstring'inde birebir:
  *"Slope azimuth in **radians**, clockwise from north (0 = N, pi/2 = E)"* — yani **gerçek**
  yerel kuzey.
- Bizim `make_aspect_grid` (`lunapath/src/process_lunar_data.py:275`)
  `degrees(arctan2(-dx, dy))` hesaplıyor; bu **grid** koordinatlarında bir açıdır.
- Polar stereografik projeksiyonda (merkez meridyen 0) grid kuzeyi ile gerçek kuzey,
  boylam kadar ayrışır. Pencere boylamı **−72,67°**, yani ayrışma ~72,7° — 22,5°'lik
  bakı kutularında **~3,2 kutu**.

**Bunun büyüklüğü ölçüldü (sonda 3):** LUT'ta sabit eğimde bakıya bağlı yayılım **28,4 °C**'ye
kadar çıkıyor (2,5° eğimde), 30° eğimde 6,0 °C'ye iniyor. Sabit bakıda eğime bağlı yayılım
**189,9 °C**. Yani eğim baskın, ama bakı ihmal edilebilir değil ve bir çerçeve dönmesi
10–28 °C mertebesinde hata taşır — yayımlayacağımız RMSE ile **aynı mertebede**.

**C5 bunu DÜZELTMEZ.** Düzeltmek `aspect_grid`'i değiştirmek, dolayısıyla `thermal_grid`'i,
dolayısıyla maliyet gridini ve her rotayı değiştirmek demektir — bu bir kalibrasyon/hata
düzeltmesidir, ayrı bir özelliktir. C5 onu **ölçer, adlandırır ve rapora bulgu olarak yazar**.
LUT karşılaştırması bu yüzden iki biçimde sunulur: bakıyı marjinalleştirerek (yalnız eğim
kutuları — çerçeveden bağımsız) ve bakıyı dâhil ederek (çerçeve varsayımı açıkça yazılı).

---

## Yayımlanmış bir sayıyı kendi aritmetiğimizle yeniden üretmek

C1'in `viper_corner_check`'i (450 W ↔ 452,5 W) ve C2'nin `jsc_survival_temperature_check`'i
(%26 ↔ %26,50) deseni verir. C5'in muadili **`cold_trap_area_check`**:

Williams vd. (2019) 80°S'nin kutup tarafında tepe sıcaklığı 110 K'nin altındaki gerçek
soğuk tuzakların toplam alanını **1,3×10⁴ km²** olarak yayımlıyor. PRP dosyası her üçgenin
**üç köşesini** de taşıdığı için alanı `½|(v₂−v₁)×(v₃−v₁)|` ile doğrudan hesaplanabilir.
Yani: `tri_clat ≤ −80` ve `temp_max < 110 K` olan üçgenlerin alanları toplanır.

**Künye farkı açıkça yazılır:** Williams kendi 240 m/px mevsimsel ürününden hesapladı; biz
PRP v2'den (Paige 2010 modeli, ~541 m, Kaguya DEM) yeniden türetiyoruz. **Farklı ürünler.**
Uyuşsun ya da uyuşmasın sonuç bilgilendiricidir ve hangi ürünün hangi sayıyı verdiği
ayrı ayrı yazılır. Bu bizim tek başına PRP ile yapabildiğimiz bir kontroldür — Williams'ın
rasterleri indirilemese bile çalışır.

---

## Bileşenler

| Dosya | Durum | İş |
|---|---|---|
| `backend/app/thermal_validation.py` | **genişletilir** | saf fonksiyonlar: mevcut `thermal_comparison` (değişmez), `destination_transform` (taşındı), `spearman_rho`, `triangle_areas_km2`, `facet_slope_aspect_deg`, `aggregate_to_facets`, `compare_candidates`, `cold_trap_area_check`, `PRP_QUOTED`, `WILLIAMS_QUOTED` |
| `scripts/build_diviner_prp_cache.py` | **yeni** | PRP'yi indir (varsa atla), 605 MB'ı tek geçişte akıtarak ayrıştır, pencere altkümesi + tam ağ türevlerini `.npz`'e, künyeyi (URL, SHA-256, bayt, satır) `_meta.json`'a yaz |
| `scripts/validate_thermal.py` | **yeni** | ölçümü koş, `--json` ham çıktı, `--from-json` ölçmeden yeniden render, `docs/research/thermal_validation_report.md` üret |
| `scripts/diviner_validation.py` | **silinir** | (a)'daki karar |
| `backend/app/slip_model.py` | iki atıf güncellenir | yeni betik adı |
| `backend/test_review2_fixes.py` | iki test yönlendirilir | H-3 dersi korunur |
| `backend/test_thermal_validation.py` | genişletilir | yeni saf fonksiyonların birim testleri |
| `backend/test_thermal_validation_real_grid.py` | **yeni** | skip-korumalı gerçek grid + gerçek PRP önbelleği |
| `.gitignore` | dört satır | ham `.tab`/`.lbl`, `.npz` önbelleği, `_meta.json` |

---

## Hata davranışı

- PRP indirilemezse (PDS 403/404 verirse — B3'ün PGDA'da gördüğü durum) betik **hiçbir şey
  yazmadan** çıkar ve nedenini söyler. Sentetik veri, "temsili" örnek, uydurma sayı **yok**.
- Önbellek yoksa rapor "ölçülemedi" der; testler skip-guard'la kendini atlar.
- **Bir test atlanıyorsa "geçti" sayılmaz.**
- Williams'ın rasterleri indirilemezse gece-minimumu bölümü `unavailable` + gerekçe döner
  (C2'de LUVMI-M'in üç modelde de gerekçeli reddedilmesi gibi); `cold_trap_area_check`
  yine de koşar, çünkü yalnız PRP'ye dayanır.

---

## Bit-eşitlik

C5 planlayıcıya dokunmaz. İddia: **hiçbir rota sayısı değişmedi ve bu testle gösterildi.**
Kanıt C2'dekiyle aynı: LPR-1'in iki checked-in SHA-256 maliyet-gridi özeti kıpırdamaz
(v5 `55e1bb3c…`, v4 `0e74607d…`, `test_roughness_real_grid.py`) ve `COST_MODEL_ID` `…_v5`'te
kalır. `layer_validity` ve `weakest_validity` **değişmez** — C4'ün kararı korunur: NASA'nın
ölçülmüş/türetilmiş ürünleri maliyet etiketini yükseltmez, en zayıf girdi yönetmeye devam eder.

---

## Kapsam dışı (ve nedeni)

- **Modeli PRP'ye kalibre etmek.** Ayrı özellik; yapılırsa yayımlanmış her ölçüm geçersizleşir.
- **`aspect_grid`'in referans çerçevesini düzeltmek.** Gerçek bir bulgu, ama düzeltmesi her
  rotayı değiştirir; C5 ölçer ve yazar.
- **Pencereyi değiştirmek.** `(2400, 2500)` proje düzeyinde ayrı bir karar.
- **`ice_depth` sütunu.** Modellenmiş bir ürün, ölçüm değil.
- **Kuzey kutbu tablosu.** Site11 güneyde.

---

## Sondalar (16 Eylül 2026, gerçek Site11 gridi + gerçek PRP dosyası)

**Sonda 1 — diskteki alan gölge eşlenmiş mi?** Görev tanımı "evet" diyordu. Ölçüm "hayır" dedi:
`shadow_ratio == 1.0` olan **16 253** hücre **+43,4 °C**'ye kadar okuyor; PSR tabanında
(−183,15 °C) **sıfır** hücre var; 250 000 hücrede yalnız **190 farklı değer**
(bir 13×16 = 208 kutuluk LUT imzası); `annual_peak_c(t, s)` uygulandığında tam o 16 253
hücre, en fazla **226,55 °C** değişiyor. Yani disk **düzeltilmemiş sunlit peak** tutuyor.
`data_loader.py:64-75` bunu zaten yazıyor ve `thermal_shadow_coupled`'ı açıkça
**"legacy alias"** olarak işaretliyor. Yalan söyleyen bir etiket **değil** — ama görev
tanımını yanlış yönlendirdi, o yüzden burada.
→ Üçüncü aday `sunlit_peak_from_annual_peak_c` **reddedildi** (çifte-ters olurdu);
yerine `shadowed_equilibrium_c` kondu.

**Sonda 2 — pencere gerçekten nerede?** `pyproj` ile `metadata.json`'ın `crs` + `origin`
değerlerinden: merkez **−88,920375° / −72,669205°** (A1/C1'de kayıtlı −88,9205 / −72,6721
ile uyuşuyor), köşeler −88,8685…−88,9715° enlem, −75,335…−69,867° boylam. Küre yarıçapı
iki tarafta da 1 737 400 m → **datum kaydırması yok**. Pencere `(2400, 2500)` doğrulandı.

**Sonda 3 — bakı ne kadar önemli?** LUT gönderilen gridden geri kazanıldı. Sabit eğimde
bakıya bağlı yayılım **28,41 °C**'ye kadar (2,5° eğimde), 30°'de 6,02 °C'ye iniyor; sabit
bakıda eğime bağlı yayılım **189,92 °C**. Eğim ~7× baskın **ama bakı ihmal edilebilir
değil** — ve pencere boylamındaki 72,67°'lik çerçeve dönmesi 10–28 °C mertebesinde hata
taşır, yani yayımlayacağımız RMSE ile **aynı mertebede**. Düz hücre tepesi **−146,37 °C**,
C6'nın bağımsız heat1d ölçümü −146,4 °C ile uyuşuyor.

**Sonda 4 — pencerede kaç PRP üçgeni var?** Medyan üçgen alanı **0,1279 km²**, eşdeğer
kenar **544 m**. 2,5 km × 2,5 km = 6,25 km² → merkezi pencerede olan **50** üçgen,
hücrelerimizi örten **71**. Beklenen n ≈ 49 ile uyuşuyor. **Küçük n bir sınırdır**, ve
raporda güven aralığıyla birlikte duruyor.

**Sonda 5 — PDS erişilebilir mi?** Evet. Koleksiyon, tablo, etiket, `.fmt` ve katalog
hepsi **200**. B3'ün PGDA'da gördüğü 403 burada çıkmadı. Ham dosya **604 800 210 B**,
SHA-256 `393deaa5…`, etiketin `210 × (2 880 000 + 1)` hesabıyla **birebir**.

---

## Uygulama sırasında bulunanlar ve ölçümler

### Ne ölçüldü

| Bölüm | n | Sonuç |
|---|---|---|
| Site11 penceresi, ortalama toplulaştırma, örtme ≥ %50 | 49 faset | A 37,44 / **B 39,43** / C 72,11 °C RMSE |
| Site11 penceresi, maksimum toplulaştırma | 49 faset | A/B bias **+62…63 °C** (yanlış eşdeğer, gösterilerek) |
| LUT, enlem eşlenmiş, bakı çözümlenmiş | 5 009 faset | RMSE 55,30 °C, bias −4,35, ρ **0,811** |
| LUT, bakı marjinalleştirilmiş | 13 eğim kutusu | Spearman **1,000** |
| Soğuk tuzak alanı | 112 757 üçgen | **14 749,1 km²** ↔ Williams'ın 1,3×10⁴ (**+%13,4**) |
| Gece minimumu | — | **`unavailable`** + gerekçe |

### Beklenmedik 1: kenardan kırpılan fasetler sonucu yanıltıyordu

İlk uygulama, hücrelerimizi örten **71** fasetin hepsini karşılaştırdı. Ama bir Diviner
fasetinin `temp_max`'ı **bütün** üçgenini (~0,128 km²) anlatır; pencere kenarında kırpılan
bir faset bize yalnız kendi diliminden görünür. Ölçüldü: **22 faset yarıdan az örtülüyor**,
13'ü dörtte birden az, en küçüğü **%2**. Ve bunları dâhil etmek uyumu **olduğundan iyi**
gösteriyor:

| Örtme eşiği | n | B RMSE | B bias | B ρ |
|---|---|---|---|---|
| ≥ %0 (süzgeçsiz) | 71 | 35,52 | −19,23 | 0,629 |
| **≥ %50 (ana sayı)** | **49** | **39,43** | **−23,19** | **0,457** |
| ≥ %90 | 38 | 40,14 | −23,42 | 0,423 |

Ana sayı **≥ %50**'ye çekildi ve üç eşik de yayımlandı. Süzgeçsiz 35,52'yi tek başına
yayımlamak, C5'in tam olarak kaçınmak için var olduğu türden bir iyimserlik olurdu.

### Hangi aday doğru eşleşme

**B** (`annual_peak_c`) — planlayıcının okuduğu alan ve istatistik eşleşmesi odur. A'nın
daha küçük RMSE'si (37,44 ↔ 39,43) gölge eşlemesinin **yönünü** değil PSR tabanının
**değerini** suçluyor: B'nin sıra korelasyonu belirgin biçimde daha iyi (0,457 ↔ 0,290),
yani eşleme hücreleri doğru **sıraya** sokuyor, ama soğuk kuyruğu yanlış **yere** koyuyor.

### İki yeni bulgu (ikisi de düzeltilmedi)

1. **Bakı referans çerçevesi.** heat1d `slope_az`'ı gerçek kuzeyden, biz grid kuzeyinden
   sayıyoruz; ayrışma 72,67°. 5°'lik tarama minimumu **295°** — yakınsamanın −dalına
   **7,7°**, öteki dala 137,7°. Büyüklük geometriden, **işaret ölçümden** doğrulandı.
   Kazanç küçük: 55,30 → 53,87 °C (%2,6); tarama 53,9–58,7 °C arasında. Çerçeve, toplam
   uyuşmazlığın çoğunu **açıklamıyor**.
2. **PSR tabanı iki yönlü yanlış.** 90 K; Site11 penceresinde PRP'nin en soğuğu 161,5 K
   (**71 K fazla soğuğuz**, 16 253 hücre oraya çakılıyor), ama 88°S kutup tarafında
   fasetlerin **%16,30**'u 90 K'nin **altında** (en soğuğu 28,4 K). Tek sabit, PRP'nin
   26,8–348,7 K yayılımını temsil edemiyor.

### Beklenmedik 2: LUT bit-eşit yeniden üretilemiyor

Geri kazanılan tablo eğim/bakı gridlerine yeniden uygulandığında hücrelerin **%22,96**'sı
tutmuyor, en büyük fark **5,89 °C**, farklar hep **komşu kutu** değerleri. Yani gönderilen
`thermal_grid.npy`, diskteki `slope_grid.npy`/`aspect_grid.npy`'den belgelenmiş
en-yakın-kutu kuralıyla üretilemiyor. **Nedeni saptanmadı.** Gridlerin termal gridden
sonra yeniden üretilmiş olması bu büyüklükle tutarlı olurdu, ama bu bir **hipotez**,
ölçüm değil — ve C5'in işi değil. RMSE'lerin yanında ≤6 °C'lik kutu-kenarı gürültüsü
küçük olduğu için sonuçları geçersizleştirmiyor; yazıldı.

### Kaynakta bulunan üç uyumsuzluk

1. Katalog düzyazısı "288000 triangles" diyor, etiket ve dosya boyutu **2 880 000** diyor.
2. Kapsama "kutup merkezli **kare**" — köşeler 80°'nin ekvator tarafına taşıyor (−75,905°).
3. Ağ **Kaguya** DEM'inden, bizim gridimiz LOLA'dan — ko-registrasyon farkı.

### Sapmalar (plandan)

Altı sapma `plans/2026-09-16-c5-diviner-prp-thermal-validation.md` § Sapmalar'da.
Özeti: LUT heat1d yeniden koşulmadan geri kazanıldı (sadakati ölçüldü ve yayımlandı);
enlem şeridi pencerenin kendi aralığına kilitlendi; tarama 5° adıma indirildi;
yakınsamanın işareti ölçüme bırakıldı; API ucu eklenmedi; `test_review2_fixes.py`'nin
iki testi silinmek yerine yönlendirildi.

### Doğrulama

- Tam paket, C5 ile: **25 failed / 2 314 passed / 5 skipped (33 dk 09 s)** — temiz HEAD (e7f6cbe) referansı **25 failed /
  2 280 passed / 5 skipped** ile karşılaştırıldı.
- `ruff check backend/app` → **12** (değişmedi); yeni dosyalar → **0**.
- Rapor `--from-json` ile **birebir** yeniden üretiliyor.
- `git diff --numstat docs/frontend/3b-veri-sozlesmesi.md` → **62 / 0** (yalnızca ekleme).
