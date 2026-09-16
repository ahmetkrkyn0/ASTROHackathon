# C1 — Güneş paneli geliş açısı ve panel geometrisi (cos i modeli) — Tasarım Belgesi

**Tarih:** 15 Eylül 2026 · **Dal:** `tuna/backendEnhance` · **Kaynak madde:**
[12_faktor_backend_ozellik_arastirmasi_2026-09-03.md § C1](../../research/12_faktor_backend_ozellik_arastirmasi_2026-09-03.md)
· **Bağımlılık:** B5 (tek enerji modeli: `cost_engine`/`cost_vec` ikizleri), A2/A1
(`illumination_series.sun_track_for_series` dilim başına Güneş az/el), B1 (`survival`), C6
(`thermal_dwell`), B2 (`risk_alpha` kalıbı) — hepsi tamamlandı.

**Yol:** mimari (yeni çekirdek modül `panel.py`, paylaşılan enerji fonksiyonlarına tek bir
`solar_gain` parametresi, 4-B hattına dilim başına kazanç dizisi, bir yeni uç, bir istek bayrağı,
her yanıtta rapor bloğu, rapor betiği). Kullanıcı onay kapısını kaldırdı; tasarım otonom
kesinleştirildi, sayılar aşağıdaki sondalardan okunur.

**Kapsam:** yalnızca `backend/app/`, `backend/test_*.py`, `scripts/`, `docs/`. Frontend koduna
dokunulmaz; `docs/frontend/3b-veri-sozlesmesi.md`'ye "C1 eki" yazılır (yalnızca ekleme).

---

## Amaç

LunaPath'in güneş geliri bugün tek bir çarpımdır: `p_solar_w × (1 − gölge_oranı)`. Bu, panelin
Güneş'e **her zaman dik** olduğunu varsayar. Varsayım gizli değil — literatürde açıkça yazılmış:
Otten 2015 (CMU) aydınlık eşiğini sıfıra koyarken gerekçesini kendi cümlesiyle verir:

> "This assumes that any positive amount of solar illumination is adequate to fully power the
> rover, which is true for rover configurations with two-degree-of-freedom articulated solar
> arrays that can always point directly at the sun (provided the array is appropriately sized)."

Aynı varsayımı B1'in kaynağı Lamarre vd. (2024) de yapar: *"we assume that the rover maintains a
constant area of solar panels perfectly oriented towards the Sun at all times, mimicking panels
mounted on a pan-tilt platform … We keep the incorporation of more complex power generation
models as future work."*

**Ama LunaPath'in kendi varsayılan rover'ının böyle bir dizisi yok.** Kataloğun `lpr_1` profili
(410 W, 5 420 Wh) doğrudan NASA VIPER'ın Proposal Information Package'ından gelir ve o belge
diziyi şöyle tanımlar: *"three approximate 1 m2 solar arrays (one each on the port, starboard,
and aft surfaces)"*. VIPER'ın gimbal'leri yüksek kazançlı anten ve navigasyon kameralarındadır;
**dizide gimbal yoktur**. Yani kod, sahip olmadığı bir donanımı varsayıyor.

Tek cümlelik iddia: **Panel kazancı `g(t) = Σ_yüzey max(0, cos i_yüzey) / raw_ref` olarak, RoverDevKit'in
`cos i = sin e·cos β + cos e·sin β·cos(α_☉ − ψ)` bağıntısıyla ve kataloğun panel geometrisiyle
hesaplanır; `raw_ref` dizinin kendi en iyi geometrisidir, böylece `p_solar_w` bir tepe-geometri
gücü olarak okunur ve geometri iki kez sayılmaz; `g(t)` dilim başına, site genelinde bir skalerdir
ve 4-B hattının hem WAIT maliyetine hem MOVE enerjisine hem de batarya durumuna aynı diziden
girer; `panel_model="sun_pointed"` (varsayılan) `g ≡ 1` demektir ve her şey bugünkü hâliyle
bit-eşittir.**

## İddia sınırı (her blokta, raporun her bölümünde)

- **Model etiketi `MODEL`.** Hiçbir rover kutup regolitinde panel ölçümü yayımlamıyor. `panel.py`
  geometrik bir çarpandır; verim (η), alan (A), toz kaybı, sıcaklık katsayısı, albedo ve arazi
  kaynaklı yansıma **yok** ve yokluğu yazılır.
- **`p_solar_w` bir düz-levha anma gücü DEĞİL.** VIPER PIP'te 410 W "total power" üç yüzeyin
  toplamı; Bluethmann (LSIC 2024) slayt 2'de "320W per panel (450W on corner)". İkisi de **en iyi
  geometrideki sistem çıkışı**. Bu yüzden C1 `p_solar_w × max(0, cos i)` YAPMAZ — bu geometriyi
  iki kez sayar ve gücü ciddi biçimde eksik tahmin eder. Bunun yerine kazanç, dizinin kendi
  en iyi ham değerine **normalize edilir** (`raw_ref`), böylece `g ≤ 1` ve `g = 1` tam olarak
  `p_solar_w`'nin yayımlandığı geometridir.
- **`g ≡ 1` varsayılanı RoverDevKit'in varsayılanı değildir.** Makale açıkça *"The default array
  is horizontal"* der (β = 0 → cos i = sin e). `g ≡ 1`, Otten/Lamarre'ın 2-serbestlik dereceli
  Güneş'e dönük dizi varsayımıdır. Varsayılan "bugünkü LunaPath davranışını bit-eşit korur" diye
  gerekçelendirilir; "makalenin varsayılanı" diye ASLA.
- **Panel geometrisi kataloğa VARSAYIM olarak girer.** Beş alanın hepsi `panel_geometry_source`
  ile gelir ve dize `"assumption:"` ile başlar (C3/B1/C6 deseni). VIPER için eğimin 90° (dik)
  olduğu NASA'nın "port, starboard, and aft **surfaces**" + "Radiators (on top)" + AftCam'in
  "blind spot caused by the solar arrays" ifadelerinden **çıkarımdır**; NASA "vertical" kelimesini
  VIPER dizisi için kullanmaz (NASA'nın VSAT'ı ayrı bir programdır, karıştırılmaz).
- **RoverDevKit'in Pragyan doğrulaması ONLARIN sonucudur.** Alıntı olarak verilir, bizim ölçüm
  tablomuza konmaz, "biz doğruladık" denmez. Makalenin kendi kelimeleri kullanılır: tepe güç
  *"predicted at 52 W against a published 50 W band of 40–70 W—a +5% error"* (makale +5% yazıyor;
  aritmetik +4% — makale alıntılanır, yeniden hesaplanmaz) ve kütle modeli *"median absolute error
  of 13.3 % (mean 14.8 %)"* (araştırma belgesindeki "MAE %13,3" **ortanca**dır, ortalama değil).
- **Bizim çapraz kontrolümüz ayrı bir şeydir ve ayrı yazılır.** NASA'nın iki sayısı ("320W per
  panel", "450W on corner") aynı donanımın iki geometrisidir; çok yüzeyli cos i modelimiz bu
  oranı öngörür. Bu bizim hesabımızdır, NASA'nın doğrulaması değil; "modelin geometri terimi
  NASA'nın yayımladığı iki sayıyla tutarlı" denir, "enerji modelimiz doğrulandı" denmez.
- **Site genelinde tek `g(t)`** kabul edilir: pencere 2,5 km, Güneş az/el'i bu ölçekte değişmez.
  Bu, `_spice_shadow_series`'in zaten yaptığı kabuldür (pencere merkezinden tek az/el).
- **Gövdeye monte dizide ψ rover BAŞLIĞIDIR.** Planlayıcı `free_heading` kullanır — rover'ın
  gücü en çoklayacak yöne dönebildiği varsayımı, ki NASA'nın kendi sürüş kipidir ("Omni-directional
  driving with sun on corner / Maximizing power generation"). Başlığı rotanın gidiş yönüne
  kilitleyen karşı-olgu **ölçülür ve raporlanır**, planlayıcıya girmez (maliyet küpü hücre başına,
  yön başına değil).
- **Güneş ufkun altındayken `g = 0`.** cos i bağıntısı eğik bir panel için `e < 0`'da bile pozitif
  çıkar; bu fiziksel değildir. Aydınlanma serisi zaten `illum_frac = 0` verir, ama statik/bozulmuş
  yolda vermez, bu yüzden kazanç `e ≤ 0`'da açıkça sıfırlanır.
- **Sayı uydurma yok:** her kazanç, oran, rota etkisi ve bekleme sayısı Site11'de koşturulup
  okunur. Araştırma belgesindeki **"~30 kat" ölçülene kadar hiçbir yere yazılmaz**; ölçülen değer
  ne çıkarsa o yazılır (sonda 2: pencereye göre 32–275 kat, tanımı ile birlikte).

## Kaynak notu (15 Eylül 2026'da okundu)

| Kaynak | Ne dedi (birebir) | Nasıl kullanılıyor |
|---|---|---|
| RoverDevKit, arXiv 2606.21755 § 3.4 (Jon Reifschneider, **Duke University**; GitHub org adı "Autonomous Mission Systems Lab" — makalenin bağlantısı değil) | Eq (16) `cos i = sin e cos β + cos e sin β cos(α⊙ − ψ)`; Eq (17) `P_solar = S₀ A_s η_s d_s max(0, cos i)`, `S₀ = 1361 W m⁻²` [Kopp & Lean 2011]; *"The default array is horizontal; high-latitude runs can pass a fixed tilt, typically min(80°, \|λ\|)"*; *"does not account for terrain horizon masking or site shadowing"* | Bağıntı birebir alınır. `S₀·A·η·d` çarpanı kurulmaz (A ve η katalogda yok) — yerine `p_solar_w` tepe-geometri gücü kabul edilir ve `d_s` rolünü `illum_frac` oynar. Eğim kuralı `polar_tilt_deg(λ)` olarak kodlanır; **kural, yasa değil** |
| VIPER PIP, NTRS 20210015009 s. 8 | *"The rover is a solar powered vehicle, consisting of a battery and three approximate 1 m2 solar arrays (one each on the port, starboard, and aft surfaces), generating 410 (TBR) W of total power."* | Üç yüzeyli dizi geometrisi; `lpr_1`'in 410 W'ı ve 5 420 Wh'ı buradan geliyor (kataloğun VIPER türevi olduğu kanıtı) |
| Bluethmann, LSIC 14 Kas 2024, NTRS 20240013903 slayt 2 | *"Solar arrays: 320W per panel (450W on corner)"*; slayt 3 *"Power / Solar Array (3-sides)"*, *"Thermal Management / Radiators (on top)"*; slayt 5 *"Driving Modes • Omni-directional driving with sun on corner • Maximizing power generation"*; slayt 7 gimbal'ler yalnız HGA ve nav kameralarda | Çapraz kontrolün iki sayısı; `free_heading` kipinin gerekçesi; dizinin **eklemsiz** olduğunun kanıtı |
| Otten, Jones, Wettergreen, Whittaker — *Planning Routes of Continuous Illumination and Traversable Slope using Connected Component Analysis*, ICRA 2015, s. 3 | *"…which is true for rover configurations with two-degree-of-freedom articulated solar arrays that can always point directly at the sun"* | Bugünkü modelin ne varsaydığının kaynaklı ifadesi (A2'nin de kaynağı) |
| Lamarre, Malhotra, Kelly — AERO 2024 (B1'in kaynağı) | *"we assume that the rover maintains a constant area of solar panels perfectly oriented towards the Sun at all times… We keep the incorporation of more complex power generation models as future work."* | Aynı boşluğun literatürde de açık olduğunun kanıtı; B1 ile tutarlılık tartışmasının dayanağı |
| IAU 2015 Res. B3 (Prša vd. 2016) | `S_☉^N = 1361 W m⁻²` (nominal, tam değer) | Yalnız kaynak notu; kodda güneş sabiti kullanılmaz |

**Araştırma belgesine düzeltmeler** (Yapıldı bloğuna da yazılır):

1. **Formüldeki sembol `|λ|` (enlem), `|φ|` değil**; ve kural makalede "typically" — zorunlu
   değil, geçirilebilir bir seçenek. Makalenin **varsayılanı yatay dizidir**.
2. **"Kütle modeli MAE %13,3" ortancadır**, ortalama %14,8'dir; ayrıca Pragyan'ın kendi kütle
   hatası tesadüfen −%13,3'tür — aynı rakam iki farklı büyüklük.
3. **Yazar Duke University'den Jon Reifschneider**; "Autonomous Mission Systems Lab" yalnızca
   GitHub organizasyon adı, makalenin bağlantısı değil.
4. **"~30 kat" tahmini eksiktir ve tanımsızdır**: ölçüm penceresine göre 32,3 kat (28 Eyl 2026
   günlük 48 saat) ile 275 kat (23 Haz 2027 sinodik ayı) arasında değişir; yıl boyu aydınlık
   saatlerde 51,1 kat. Tek sayı yazılamaz; pencere ile birlikte yazılır.
5. **En önemlisi: belge `p_solar_w × max(0, cos i)` öneriyor, bu geometriyi iki kez sayar.**
   Kataloğun 410/450 W'ı zaten üç yüzeyli bir dizinin en iyi geometrideki çıkışıdır.

## Mevcut durumdan kullanılanlar

| Ne | Nerede | C1'de rolü |
|---|---|---|
| Dilim başına Güneş az/el (gerçek, grid merkezinden) | `illumination_series.sun_track_for_series:326` → `body_track_for_series:279` | `g(t)`'nin tek kaynağı; gölge serisiyle aynı epok aritmetiği, dolayısıyla dilim hizası garanti |
| Gölge serisi ve sağlayıcılığı | `illumination_series.build_shadow_series:48` | `illum_frac`; `d_s` rolünü oynar |
| Tek enerji modeli (B5) | `cost_engine.py:242/271/290`, `cost_vec.py:135`, `cost_cube.py:378` | Hepsine **tek** `solar_gain` parametresi; skaler ve vektörel ikizler aynı işlem sırasıyla |
| 4-B batarya entegrasyonu | `pathfinder_4d.py:1128, 1272` | Dilim indeksli kazanç dizisi |
| Rover kataloğu ve `"assumption:"` deseni | `constants.py` (C3 `slip_curve`, C6 `HEATER_THERMOSTAT_ASSUMPTION_SOURCE`) | Beş yeni alan + kaynak dizesi |
| Bayrak deseni | `main.py:788 heater_model`, `:708 risk_alpha` | `panel_model` Literal, varsayılan = eski davranış |
| Rapor betiği deseni | `scripts/thermal_dwell_report.py` (`--json`/`--from-json`/`--out`) | `scripts/panel_cos_i_report.py` |

## Sondalar (15 Eylül 2026, gerçek kernel + gerçek grid)

**Sonda 1 — Site11 geometrisi.** `metadata.json` pencere merkezi **−88,9205°, −72,6721°**;
RoverDevKit kuralı `min(80°, |λ|)` → **80°**. SPICE ile 1 Eyl 2026'dan bir yıl, 2 saat adım:
Güneş yüksekliği **−2,5903° … +2,5543°**, yüksekliği pozitif olan saat oranı %50,8, pozitif
yüksekliklerin ortalaması **1,107°**.

**Sonda 2 — çıplak geometri oranı (dik-izleyen 80° panel ÷ yatay panel), aydınlık saatlerde.**

| Pencere | Oran | Not |
|---|---|---|
| 28 Eyl 2026 + 48 h (standart gündüz rotasının epoğu) | **32,3 kat** | yükseklik 1,576…1,915° |
| Bir yıl (aydınlık saatler) | **51,1 kat** | — |
| Sinodik ay bazında | **37,3 … 275,3 kat** | 3 ayda Güneş hiç doğmuyor (Mar–May 2027), oran tanımsız |

Yani belgenin "~30 kat"ı yalnızca kısa bir gündüz penceresi için doğru.

**Sonda 3 — gerçek grid, 28 Eyl 2026, 48 dilim × 0,5 h, tüm hücreler.** Toplam `Σ illum × g`
(bugünkü model = 1,0927e5 birim):

| Geometri | Toplam | Bugünkünün yüzdesi |
|---|---|---|
| `g ≡ 1` (bugün, Otten 2-DOF) | 1,0927e5 | %100 |
| VIPER 3 yüzey, serbest başlık | (sonda 5) | — |
| tek yüzey 80°, Güneş izleyen | 1,0810e5 | **%98,9** |
| tek yüzey 80°, sabit ψ = 0° | 6,8034e4 | %62,3 |
| tek yüzey 0° (yatay) | 3,0337e3 | **%2,8** |
| tek yüzey 80°, sabit ψ = 180° | 0 | %0 (bu pencerede Güneş azimutu 27,8…52,0°) |

**Sonda 4 — NASA çapraz kontrolü (bizim hesabımız).** Üç dik yüzey (port/starboard/aft, 90° / −90° /
180° başlığa göre), Güneş ufukta (e = 0):

- bir yüzey dik geliş: ham kazanç **1,000000**
- üç yüzey, en iyi başlık (ψ₀ = 135°, Güneş iki yüzey normali arasında): ham kazanç **1,414214**
- NASA'nın "320W per panel"inden modelin öngördüğü köşe gücü: **452,5 W**
- NASA'nın yayımladığı köşe gücü: **450 W** → fark **+2,5 W (+%0,57)**; oranlar 1,41421 (model) ↔
  1,40625 (yayımlanan)

**Sonda 5 — normalize kazanç (her dizi kendi en iyisine bölünmüş), bir yıl, aydınlık saatler.**

| Dizi | ortalama | en küçük | en büyük |
|---|---|---|---|
| VIPER 3 yüzey, serbest başlık | **0,999724** | 0,999002 | 1,000000 |
| tek yüzey 80°, Güneş izleyen | **0,987903** | 0,984810 | 0,991568 |
| tek yüzey 80°, sabit ψ = 0° | 0,446938 | 0,000000 | 0,991563 |
| tek yüzey 0° (yatay) | **0,019320** | 0,000012 | 0,044567 |

**Bu tablonun okunması budur ve rapor bunu bu kelimelerle yazar:** kataloğun varsayacağı
geometrilerde (VIPER sınıfı 3 yüzey serbest başlık, küçük rover'larda 80° Güneş izleyen) kazanç
0,985–1,000 arasındadır, yani **C1 varsayılan katalogla rotayı neredeyse hiç değiştirmez**. Çarpıcı
sayılar karşı-olgulardadır (yatay dizi, sabit azimut, kilitli başlık) ve bunlar model riskinin
büyüklüğünü sınırlar — hiçbir rover hakkında iddia değildir.

## Tasarım kararları

1. **Kazanç normalize edilir, ham cos i değil.** `g = raw(t) / raw_ref`, `raw_ref` = dizinin
   (ψ₀, e) üzerinde en büyük ham değeri. Tek düz levhada `raw_ref = 1` ve `g = max(0, cos i)`
   — belgenin istediği bağıntı bunun özel hâli. Üç yüzeyli gövde dizisinde `raw_ref = √2`.
   Gerekçe: `p_solar_w` bir tepe-geometri gücü; aksi hâlde geometri iki kez sayılır.
2. **`g(t)` dilim başına skaler, (T,) dizi.** (T, H, W) küp **kurulmaz** (C6'nın bellek dersi).
3. **Bayrak: `panel_model: Literal["sun_pointed", "cos_incidence"] = "sun_pointed"`.** Varsayılan
   `g ≡ 1`. Blok **her zaman** raporlanır (geometri, kazanç istatistikleri, karşı-olgular), kısıt
   yalnız istenince uygulanır — A1/A2/C6 deseni.
4. **Paylaşılan enerji fonksiyonlarına tek parametre `solar_gain: float = 1.0`**, skaler ve
   vektörel ikizlerde **aynı işlem sırasında**: `* (1.0 - ratio) * solar_gain`. `1.0` ile çarpma
   IEEE 754'te birebir; ayrıca standart rotalar ve 2-B SHA-256 kilitleriyle testte sabitlenir.
5. **`f_energy_cell`'in referans ölçeği `g = 1`'de sabitlenir** (C3'ün `slip_free_view` deseni):
   yalnız `here_wh` kazancı okur, `best_wh`/`worst_wh` okumaz. Aksi hâlde [0, 1] ölçeği tümden
   kayar ve "en iyi hücre" kazançla birlikte oynar.
6. **`build_wait_cost_cube`'un tekilleştirmesi dilim başına yapılır.** Bugün `np.unique` tüm küp
   üzerinde; dilim başına farklı `g` ile aynı `illum` değeri iki farklı maliyet demektir ve
   bugünkü tekilleştirme bunları çökertir. `g` verilmediğinde eski tek-tablo yolu aynen korunur
   (bit-eşitlik).
7. **2-B `/api/plan` kapsam dışı ve bunu söyler.** Epok yok → Güneş yüksekliği yok → `g`
   yapısal olarak 1. Yanıtın `panel` bloğu `applied: false`, `reason: "the 2-D cost grid has no
   epoch"` der. Böylece `COST_MODEL_ID` **v5'te kalır** ve dört SHA-256 kilidi kıpırdamaz.
8. **B1 (survival) muhafazakâr skalerle girer:** alan ufku boyunca `g_min`. Bir güvenlik sınırı
   asla iyimser olmamalı; `_power_terms`'ün DP'yi kapalı formda tutan çarpanlaması bozulmaz.
   `g_min` ile `g_ort` farkı ölçülür ve rapora yazılır (izleyen geometride ~%0,8).
9. **B5 (stres testi) sürekli saate uygun biçimde girer:** gölgenin kümülatifi gibi bir
   `cumulative_lit_gain` tablosu (∫(1−gölge)·g dt) kurulur ve güneş terimi indeks yerine bu
   integralden okunur. Kazanç verilmediğinde tablo kurulmaz, eski yol aynen çalışır.
10. **Başlık kilitli karşı-olgu yalnız raporda.** Rota adımlarının yönünden başlık çıkarılır ve
    aynı rota `heading_locked` kipinde yeniden fiyatlanır; planlayıcı değişmez.

## Bileşenler

### `backend/app/panel.py` (yeni)

```python
PANEL_MODELS: tuple[str, ...] = ("sun_pointed", "cos_incidence")
AZIMUTH_MODES: tuple[str, ...] = ("sun_tracking", "free_heading", "fixed", "heading_locked")
PANEL_MODEL_ID: str = "multi_face_cos_incidence_v1"
PANEL_VALIDITY: str = "MODEL"
PANEL_SCOPE: str        # ne modelleniyor, ne modellenmiyor
PANEL_CLAIM: str        # iddia sınırı, her yanıtta
PANEL_REFERENCES: tuple[dict[str, str], ...]
VIPER_QUOTED: dict[str, Any]          # NASA'nın sayıları, alıntı olarak

@dataclass(frozen=True)
class PanelFace:  tilt_deg: float; azimuth_offset_deg: float; area_weight: float = 1.0

@dataclass(frozen=True)
class PanelArray:
    faces: tuple[PanelFace, ...]; azimuth_mode: str; azimuth_deg: float | None
    kind: str; source: str
    def reference_raw(self) -> float

def polar_tilt_deg(lat_deg: float) -> float                      # RoverDevKit min(80, |λ|)
def cos_incidence(elevation_deg, azimuth_deg, tilt_deg, panel_azimuth_deg) -> float
def raw_gain(elevation_deg, azimuth_deg, array, reference_azimuth_deg) -> float
def best_reference_azimuth(elevation_deg, azimuth_deg, array) -> tuple[float, float]
def panel_gain(elevation_deg, azimuth_deg, array, heading_deg=None) -> float
def gain_series(sun_track, array, headings_deg=None) -> np.ndarray          # (T,)
def array_for_rover(rover) -> PanelArray | None
def viper_corner_check() -> dict[str, float]                     # sonda 4, kodda
def panel_block(rover, array, gains, model, requested, reason=None) -> dict
def counterfactual_gains(sun_track, array) -> dict[str, dict]    # yatay/sabit/izleyen/serbest
```

### `backend/app/constants.py`

Beş yeni alan (dördü `MODELLED_FIELDS`'a, `panel_geometry_source` da) — hepsi değişmez tip:

| Alan | `lpr_1` | `luvmi_m` | `nasa_viper` | `cnsa_yutu_2` |
|---|---|---|---|---|
| `panel_tilt_deg` | 90,0 | 80,0 | 90,0 | 80,0 |
| `panel_face_azimuths_deg` | (90,0, −90,0, 180,0) | (0,0,) | (90,0, −90,0, 180,0) | (0,0,) |
| `panel_azimuth_mode` | `"free_heading"` | `"sun_tracking"` | `"free_heading"` | `"sun_tracking"` |
| `panel_azimuth_deg` | None | None | None | None |
| `panel_geometry_source` | `"assumption: …"` | `"assumption: …"` | `"assumption: …"` | `"assumption: …"` |

VIPER/LPR-1 kaynak dizesi PIP ve LSIC alıntılarını taşır ve eğimin çıkarım olduğunu söyler;
LUVMI-M/Yutu-2 dizesi "yayımlanmış panel geometrisi yok, RoverDevKit'in kutup kuralı (80°)
ve 2-DOF izleme varsayıldı" der. `MODELLED_FIELDS` ↔ `DECLARED_ONLY_FIELDS` bölüntüsünün
**tamlığı** da ilk kez testle kilitlenir (bugün yalnız ayrıklık test ediliyor).

### Dokunulan yerler (yalnız ekleme, hepsi `solar_gain=1.0` varsayılanlı)

| Dosya | Ne |
|---|---|
| `cost_engine.py` | `net_energy_per_metre_wh`, `move_battery_drain_wh`, `wait_battery_drain_wh`, `f_energy_cell` + docstring'deki üçlü söz |
| `cost_vec.py` | `_energy_per_metre_wh_grid`, `f_energy_cell_grid` (aynı işlem sırası) |
| `costmap.py` | `PlanContext.solar_gain: float = 1.0`, `EnergyLayer` geçirir |
| `cost_cube.py` | `wait_cost(..., solar_gain)`, `build_wait_cost_cube(..., gain_series)`, `build_cost_cube(..., gain_series)` |
| `pathfinder_4d.py` | `astar_4d(..., solar_gain_series)`; satır 1128/1272'deki satıriçi aritmetik |
| `simulation.py` | `simulate_path(..., solar_gain)` (tek epok skaleri) |
| `stress_test.py` | `cumulative_lit_gain` tablosu, üç drenaj yeri |
| `survival.py` | `_power_terms(rover, solar_gain)` — muhafazakâr `g_min` |
| `main.py` | `panel_model` alanı, `panel` bloğu, `GET /api/panel-gain`, `/api/illumination-series` içinde `panel` |

## Veri akışı

```
/api/plan-4d (panel_model="cos_incidence")
  └─ sun_track_for_series(metadata, n_slices, slice_hours, start_utc)   [SPICE]
       └─ panel.array_for_rover(rover)            [katalog, "assumption:"]
            └─ panel.gain_series(...)  →  g (T,)  [e ≤ 0 → 0; normalize]
                 ├─ build_cost_cube(gain_series=g)        → MOVE enerji kriteri
                 ├─ build_wait_cost_cube(gain_series=g)   → WAIT maliyeti
                 ├─ astar_4d(solar_gain_series=g)         → batarya durumu
                 └─ _survival_field_for_plan(solar_gain=g.min())   [B1, muhafazakâr]
  └─ yanıt: panel { model, applied, reason, geometry, source, gain{min,mean,max,series},
                    counterfactuals, viper_corner_check, claim, validity }
```

## Hata davranışı

| Durum | Davranış |
|---|---|
| `panel_model="cos_incidence"`, `start_utc` yok | **422** — "cos i needs an epoch" (A1/A2 deseni) |
| Kernel yok / SPICE hatası | **422** (istendiğinde); istenmediğinde blok `applied: false`, `reason` |
| Rover panel geometrisi bildirmiyor | **422** (istendiğinde); blok `available: false` + neden. Geometri **uydurulmaz** |
| Gölge serisi statik ama kernel var | `g(t)` yine hesaplanır; blok `shadow_model` ile birlikte kendi sağlayıcılığını yazar (`shadow_provenance["time_varying"]` **yeniden kullanılmaz**) |
| Güneş ufkun altında | `g = 0` (açık kayıt) |
| `p_solar_w` yok/None | `g` hesaplanır ama gelir sıfır; blok söyler |

## Test stratejisi

- **Birim (`test_panel.py`, ~40):** cos i'nin dört köşe durumu (dik geliş, teğet, arka yüz,
  β = 0 → sin e); `polar_tilt_deg`; normalizasyon (tek levhada `g == max(0, cos i)`);
  `raw_ref` = √2 üç dik yüzeyde; `best_reference_azimuth` = 135°; **NASA çapraz kontrolü
  452,5 W ↔ 450 W**; `e ≤ 0 → g = 0`; azimut çerçevesinin fark-değişmezliği; `gain_series`
  uzunluğu ve sırası; katalog geometrisi ve `"assumption:"` öneki; `MODELLED`/`DECLARED_ONLY`
  bölüntü tamlığı; `json.dumps(..., allow_nan=False)`.
- **Bit-eşitlik (birim):** `solar_gain=1.0` ⇒ dört `cost_engine` fonksiyonu ve iki `cost_vec`
  ikizi `np.array_equal`; `build_wait_cost_cube(gain_series=None)` eski küple bire bir;
  `astar_4d(solar_gain_series=None)` aynı yol, **aynı `nodes_expanded`, aynı `total_cost`**
  (C6 deseni); `COST_MODEL_ID` hâlâ `_v5`.
- **API (`test_panel_api.py`, ~14, çekirdeksiz):** `panel_model` alanı ve sınırları; blok şekli;
  epoksuz 422; geometrisiz rover 422; `GET /api/panel-gain` 200/422; `/api/illumination-series`
  içindeki blok; `/api/plan-4d` varsayılanında blok `applied: false`.
- **Gerçek grid (`test_panel_real_grid.py`, ~7, skip-korumalı):** üç standart rota
  **41 / 116 / 8 hamle** varsayılan `panel_model` ile aynen; `cos_incidence` ile 200 ve rotanın
  ne olduğu (ölçülüp pinlenir); kazanç serisi sondalarla tutarlı; karşı-olgu oranları; bekleme
  sayısının değişip değişmediği (A2 dwell etkisi).

## Kapsam dışı (ve nedeni)

- **2-B `/api/plan`** — epok yok (karar 7).
- **Verim, alan, toz, sıcaklık katsayısı, albedo/arazi yansıması** — katalogda yok, uydurulmaz.
- **Başlık kilitli planlama** — maliyet küpü yön başına olurdu (8× bellek); karşı-olgu ölçülür.
- **B3 DEM klonları Monte Carlo'su** — B5 ile aynı sürekli saat; B5 yapılır, B3'ün ayrı yolu
  ölçülüp not edilir.
- **C2 (batarya soğuk davranışı)** — ayrı madde; C1 onun bağımlılığı olarak duruyor.
- **`GET /api/survival`, hücre kartı, `/api/replan` ve `/api/dem-uncertainty`** — bunların
  `panel_model` bayrağı **yok**; alanları `solar_gain = 1.0` ile kuruluyor. Sessizce değil:
  `survival_model.panel_gain.applied` bu uçlarda `false` döner, yani okuyan bilir. Bağlanması
  ayrı bir iş; B3'ün Monte Carlo'su da (B5'inkinden farklı bir `RouteSky` yolu) aynı durumda.

---

## Uygulama sırasında bulunanlar ve ölçümler

### Bulunanlar (tasarımdan sapmalar, nedenleriyle)

1. **`PanelArray`'e ikinci bir eksen (`tilt_mode`) eklendi.** Tasarım yalnız azimut kipini
   öngörüyordu; ama "bugünkü model"in kendisi — Otten'ın 2 serbestlik dereceli dizisi — panelin
   **eğiminin de** Güneş'i izlemesi demektir ve sabit eğimli bir yüzle ifade edilemez. Karşı-olgu
   tablosundaki `sun_pointed` satırı bu yüzden `tilt_mode="sun_tracking"` (tek yüzey; çok yüzeyde
   tanımsız ve `__post_init__` reddediyor). Kilitleyen test:
   `test_a_two_axis_array_gains_exactly_one_whenever_the_sun_is_up`,
   `test_a_two_axis_array_with_several_faces_is_refused`.
2. **Karşı-olgu ortalamasının paydası "Güneş üstte" oldu, "panel ışık topluyor" değil.** İlk
   sürüm `mean_when_lit`'i `gains > 0` üzerinde alıyordu; bu, **sabit** bir paneli yalnız kendi iyi
   saatlerinde ortalıyor ve onu izleyen bir diziye karşı haksız yere kayırıyordu. Ölçülen fark
   büyük: sabit 80° levha bir yılda 0,667112 yerine **0,446938** (payda %33 değişiyor). Alan
   `mean_when_sun_up` olarak yeniden adlandırıldı, yanına `positive_fraction` (geometrinin hiç
   olmazsa bir şey topladığı dilim oranı) eklendi. Kilitleyen test:
   `test_counterfactuals_rank_the_way_the_geometry_says_they_must`.
3. **Tarama vektörleştirildi.** `free_heading` kipi dilim başına bir 1-B maksimizasyon ister;
   saf Python döngüsüyle birim testleri **43 s** sürüyordu, NumPy ızgarasıyla **3 s**. Determinizm
   korundu (aynı üç geçişli ızgara), çünkü bu sayılar yayımlanıyor.
4. **`_panel_gain_for_plan`, `shadow_provenance["time_varying"]`'i YENİDEN KULLANMIYOR.** Ufuk
   önbelleği yokken gölge serisi statiktir ama Güneş yine hareket eder; C1'in kapısı kendi
   sağlayıcılığıdır (kernel + epok + katalog geometrisi). Fonksiyonun docstring'i bunu yazıyor.
5. **Rapor betiğinde iki hata bulundu ve düzeltildi:** başlık kilitli karşı-olgu Güneş izini
   1 saatlik adımla örnekliyordu, oysa planın kendi `slice_hours`'ı otomatik türetiliyor (yanıttan
   okunuyor artık); ve yukarıdaki (2) numaralı payda hatası ilk üretilen raporda vardı.
6. **`g_min`'in penceresi düzeltildi.** Tasarım "alan ufku boyunca en küçük kazanç" diyordu ama
   ilk uygulama minimumu **planın** ufkundan alıyordu; oysa survival alanının ufku plandan uzundur
   (plan + kurtarma + 2 × en hızlı sürüş). Güneş planın bitiminden hemen sonra batıyorsa bu
   minimum **iyimser** kalırdı — bir güvenlik sınırı için yanlış yön. `_SurvivalOptions` artık
   skaler yerine `apply_panel_gain: bool` taşıyor; kazanç `n_total_slices` bilindikten sonra,
   alanın **kendi** dilimleri üzerinden hesaplanıyor ve önbellek anahtarına o giriyor. Yanıtta
   `survival.panel_gain` (uygulandı mı, `solar_gain`, `mean_gain`, kaç dilim) raporlanıyor.
   **Farkın büyüklüğü ölçüldü:** gündüz rotasında planın ufku ~120 dilim iken alanın ufku
   **520 dilim**; bu epokta minimum 0,9995465 ↔ ortalama 0,9995839, yani yakın — ama Güneş planın
   hemen ardından batan bir epokta aradaki fark her şey olurdu, ve doğru pencere ölçülmeden
   bilinemezdi.
7. **B5'in kendi kazanç serisi var, planınki değil.** İlk uygulamada `RouteSky`'a kazanç
   parametresi eklenmişti ama API'den hiç beslenmiyordu; yani `cos_incidence` ile yapılmış bir
   planın stres testi `g = 1` ile koşacak ve planın zaten düştüğü gelir konusunda **iyimser**
   olacaktı. `StressTestRequest` artık kendi `panel_model` alanını taşıyor ve kazanç, koşumun
   kendi (uzatılmış) dilimleri üzerinden kuruluyor — stres testi planın ufkunu aşar, planın
   serisi yetmezdi. Statik gökyüzünde (`horizon_map.npy` ya da epok yoksa) uygulanmaz ve
   `sky_model.panel_model.reason` bunu söyler: uzun dönem gölge ortalamasını anlık bir cos i ile
   çarpmak 2-B `/api/plan`'de reddedilen tutarsızlığın aynısı olurdu. Kilitleyen testler:
   `test_stress_test_reports_the_panel_model_and_refuses_to_pretend`,
   `test_the_stress_test_prices_its_runs_at_the_same_gain_the_plan_used`.
8. **Düşmanca gözden geçirme iki YANLIŞ SAYI buldu ve ikisi de düzeltildi.**
   (a) *Çok dilimli MOVE kenarı*: kod `(1 − ortalama maruziyet) × ortalama kazanç` yüklüyordu, oysa
   maliyet küpü her dilimi **kendi** kazancıyla fiyatlıyor, yani kenarın maliyeti
   `0,5·[(1−e_kalkış)·g_kalkış + (1−e_varış)·g_varış]` taşıyor. C1 öncesi terim maruziyette
   **afin** olduğu için ikisi eşitti; kazançla birlikte terim **çift-doğrusal** oluyor ve fark
   `0,25·p_solar·(e_varış−e_kalkış)·(g_kalkış−g_varış)·h` — terminatörü geçen bir kenarda **iki
   kat** (gösterilen örnekte 102 Wh ↔ 205 Wh, LPR-1 bataryasının %1,9'u, tek kenarda). Üstelik
   B5'in Monte Carlo'su çarpımın integralini alıyor, yani plan ile stres testi aynı kenarda
   ayrışıyordu. Artık ikisi de çarpımın yamuğunu kullanıyor; kazanç verilmeyen yolda ifade
   **harfi harfine** eskisi (yeniden çarpanlama IEEE-754'te bit-eşit değil).
   Kilitleyen test: `test_a_multislice_move_averages_the_slice_INCOMES_not_the_two_means`.
   (b) *Survival skaleri*: `np.min(field_gains)` alanın gece'ye uzanan ufkunda **tek bir karanlık
   dilim** yüzünden 0'a çöküyordu ve `_power_terms(rover, 0.0)` o zaman "dizisi hiç üretmeyen"
   bir rover modelliyordu — tamamen aydınlık bir hücrede, tamamen aydınlık bir anda bile. Bu
   muhafazakârlık değil, karanlığı **iki kez** saymak: alanın kendi `exposure` tablosu onu zaten
   taşıyor. Gözden geçirme bunu gerçek bir epokta gösterdi (24 saatlik plan tümüyle aydınlık,
   alanın ufku gün batımını aşıyor → `solar_gain` 0,0; tamamen aydınlık bir hücrede %30 SOC'de
   P_safe 1,0 → 0,904). Artık `panel.conservative_gain`: **ışık olan** dilimlerin en küçüğü,
   hiç ışık yoksa 1,0. Kilitleyen test:
   `test_a_safety_bound_takes_the_worst_gain_WITH_LIGHT_not_the_worst_number`.
9. **B5'in varsayılan yolu da bit-eşit değildi** (aynı gözden geçirme): MOVE bacağında güneş terimi
   `1 − 0,5·(e_f+e_t)` iken `0,5·((1−e_f)+(1−e_t))` olmuştu — cebirsel olarak aynı, IEEE-754'te
   rastgele çiftlerin **%25'inde** farklı; 2 000 koşumun 64'ünde `final_battery_wh` son basamakta
   kayıyordu. Kazanç verilmeyen yol artık orijinal ifadeyi kullanıyor.
10. **Üç yanlış/eksik ifade düzeltildi.** (a) **5 420 Wh PIP'te YOK** — o belgede hiçbir batarya
   sayısı geçmiyor (NASA'nın kendi tam metninde arandı: "5,420", "5420", "W-hr", "Battery capacity"
   → sıfır kez); sayı Bluethmann'ın 2. slaytından. PIP yalnız 410 W'ın kaynağı. (b) **"dört SHA-256
   kilidi kıpırdamadı" YANLIŞTI**: NASA VIPER'ın iki özeti checked-in değerlerle **C1'den önce de**
   eşleşmiyordu (temiz ağaçta `a55a2f64…`/`a3a690bb…` ↔ checked-in `593f8e46…`/`8788936c…`).
   Doğru ifade: **LPR-1'in iki özeti eşleşiyor ve C1'le kıpırdamıyor** — `solar_gain=1.0`
   varsayılanının bit-eşitliğinin asıl kanıtı budur. (c) Sözleşmedeki `/api/panel-gain` örneğinde
   Güneş azimutları başka bir pencereden kalmıştı (27,8° / 315,1°); gerçek yanıt 52,027° / 339,355°.
   Ayrıca raporda 422 "hamle" sütununa yazılıyordu, Otten alıntısı elipssiz kesiliyordu ve README
   satırı özelliği varsayılan açıkmış gibi anlatıyordu — üçü de düzeltildi.
11. **API yüzeyinde üç sözleşme kırığı bulundu ve düzeltildi.** (a) `/api/illumination-series`'in
   `panel` bloğu **varsayılan profilin** geometrisini yayımlıyordu ve yanıtta hangi rover olduğunu
   söyleyen hiçbir alan yoktu — başka bir profille planlayan bir istemci LPR-1'in geometrisini
   kendisininmiş gibi okurdu. Uca `rover_id` eklendi ve blok `rover_id` taşıyor. (b) Aynı uçta
   `requested`, isteğin değil **sonucun** özelliğiydi: kazanç kurulabildiyse `True` yazılıyordu,
   oysa o uçta kimse cos i istemiş değildi ve bu, belgelenen
   `applied = bool(requested and artefact is not None)` kuralını tersine çeviriyordu. Uca
   `panel_model` eklendi; `requested` artık yalnızca isteğe bakıyor. (c) `StressTestRequest`'in
   `panel_model` açıklaması epok/kernel yokken **422** vaat ediyordu ama uç 200 + `applied: false`
   döndürüyor (ve bir test bunu pinliyor) — açıklama davranışa uyduruldu. Kilitleyen testler:
   `test_illumination_series_names_whose_panel_it_is_describing`,
   `test_requested_is_a_property_of_the_request_not_of_the_outcome`.
12. **Varsayılan yol attığı bir seriyi hesaplıyordu.** `_panel_gain_for_plan` koşulsuz
   çağrılıyor ve `panel_model="sun_pointed"` iken dönen kazanç serisi atılıyordu (ölçüldü:
   120 dilimde ısınmış hâlde ~30 ms, soğukta 826 ms). Artık `build_gain` parametresi var: Güneş
   izi her zaman hesaplanıyor (blok Güneş yüksekliği aralığını ve karşı-olguları ondan üretiyor,
   ~30 ms), rover'ın kendi serisi yalnız istenince. Blok yine her zaman raporlanıyor.
13. **Dördüncü lens bit-eşitliği KANITLADI.** `backend/app`'in HEAD sürümünün bir kopyası
   kurulup aynı girdiler iki pakete birden verildi: dört maliyet-gridi SHA-256'sı, iki standart
   rota (41 / 31 219 / 3,445393 ve 116 / 171 117 / 7,837081 — `computation_time_ms` dışında her
   metrik), 4 000 koşumluk `/api/stress-test` yanıtının tamamı ve birim düzeyde on bir fonksiyon
   **bayt-bayt aynı**. Skaler ↔ vektörel ikizler altı farklı kazançta (1,0 / 0,9 / 0,5 /
   0,123456789 / 0,0 / 1e-9) 400/400 hücrede **bit-eşit** (1e-12 değil, tam eşit).
   `f_energy_cell`'in referansı gerçekten kazançsız: her kazançta `f(slope_max, gölge=1) = 1,0`.
14. **VIPER kısa leg'i (30 May 2027) ve 24 test daha C1'den bağımsız olarak kırık — ÖLÇÜLDÜ.**
   Tam paket **25 başarısız / 2 181 geçti / 5 atlandı (37 dk 56 s)** verdi. Bu sayı beklediğimden
   çoktu, o yüzden iddia etmeden önce **temiz bir HEAD worktree'sinde** (gitignore'lu
   `lunapath/data/processed`, `kernels/` ve `backend/data` junction'lanarak, yani gerçek-grid
   testleri orada da gerçekten koşarak) aynı paket koşturuldu: **25 başarısız / 2 102 geçti /
   13 atlandı (25 dk 34 s)** ve başarısız test listeleri **birebir aynı** (`comm` iki yönde de
   boş). Yani **C1 hiçbir şey kırmıyor**. Aritmetik de tam kapanıyor:
   2 102 + 71 (C1'in yeni testleri) + 8 (worktree'de `lunapath/data/benchmarks` olmadığı için
   atlanan MoonPlanBench testleri) = **2 181**. Kırık 25 testin hepsi `*_real_grid.py`
   dosyalarında ve tek bir birim ya da API testi düşmüyor; çoğunluğu 4af6989'un VIPER
   `slope_max_deg` 20°→15° düzeltmesinin arkasından gelen aynı 422 ile
   (`test_terrain_real_grid` gibi enerjiyle hiç ilgisi olmayanlar da var). **C1 bu testlerin
   hiçbirine dokunmadı** (özellik başına tek commit kuralı); `test_panel_real_grid.py` VIPER için
   hamle sayısı pinlemek yerine "iki panel modeli aynı cevabı veriyor" sözleşmesini kilitliyor.

### Ölçümler (Site11, coarsen 4, gerçek kernel + gerçek ufuk küpü)

**Geometri.** Pencere merkezi −88,9205°, −72,6721°; RoverDevKit kuralı `min(80°, |λ|)` → **80°**.
Güneş yüksekliği bir yılda **−2,5903° … +2,5543°**, saatlerin **%50,8**'inde ufkun üstünde.

**NASA'nın iki sayısı, bizim aritmetiğimiz.** Üç dik yüzey: bir yüzey dik gelişte ham kazanç
1,000000; en iyi başlıkta (ψ₀ = **135,00°**) **1,414214 = √2**. NASA'nın 320 W'ından öngörü
**452,5 W**, yayımlanan **450,0 W** → **+2,5 W (+%0,57)**; oranlar 1,41421 ↔ 1,40625.

**"~30 kat" ölçüldü** (izleyen 80° levha ÷ yatay levha, Güneş ufkun üstündeyken):

| Pencere | oran |
|---|---|
| 28 Eyl 2026 + 48 h | **32,3** |
| 28 Eyl 2026 + bir sinodik ay | 46,9 |
| 1 Eyl 2026 + bir yıl | **51,1** |
| sinodik ay bazında (13 ay) | **37,3 … 275,3**, üç ayda tanımsız (Güneş hiç doğmuyor) |

**Gerçek aydınlanma serisiyle ağırlıklı** (48 dilim × 0,5 h, 28 Eyl 2026, 500 × 500 hücre; sitenin
ortalama aydınlık kesri bu pencerede %0,91 — pencerenin ikinci yarısında site tümüyle karanlığa
giriyor): bugünkü modelin yüzdesi VIPER 3 yüzey **%99,96**, tek levha 80° izleyen **%98,92**,
sabit kuzeye bakan %62,26, yatay **%2,78**.

**Rotalar** (`panel_model` varsayılan ↔ `cos_incidence`):

| Rota | hamle | bekleme | maliyet | varış SOC | düğüm | ort. kazanç |
|---|---|---|---|---|---|---|
| LPR-1 gündüz 28 Eyl 2026 | 41 ↔ **41** | 0 ↔ 0 | 3,445393 ↔ 3,445454 | 92,64 ↔ 92,64 | 31 219 ↔ 31 222 | — ↔ 0,999613 |
| LPR-1 Ay gecesi 13 Eyl 2026 | 116 ↔ **116** | 0 ↔ 0 | 7,837081 ↔ **aynı** | 67,42 ↔ aynı | 171 117 ↔ aynı | — ↔ 0,000000 |
| VIPER kısa leg 30 May 2027 | 422 ↔ 422 (C1 öncesi de) | — | — | — | — | — |

**A2'nin dwell kararları:** her iki rotada da WAIT adımı sayısı 0 ve `cos_incidence` bunu
değiştirmiyor — kataloğun varsaydığı geometrilerde kazanç zaten ~0,99 olduğu için beklemenin
getirisi ölçülebilir biçimde kaymıyor. Ay gecesinde kazanç tümden sıfır ve plan **bit-eşit**:
ışık yokken yanlış yöne bakacak bir şey de yok.

**Başlık kilitli karşı-olgu** (yalnız ölçüm): gündüz rotasının 41 adımında serbest başlık
ortalaması **0,999615**, gidiş yönüne kilitli başlıkta **0,304732** (en az 0,250895, en çok
0,656739) — **3,3 kat** daha az. Ay gecesi rotasının 116 adımının hepsi sıfır kazançlı.

**Testler:** 46 birim (`test_panel.py`) + 16 API (`test_panel_api.py`, çekirdeksiz) + 9
skip-korumalı gerçek grid (`test_panel_real_grid.py`) = **71**. Rapor betiği 3,1 dk.
