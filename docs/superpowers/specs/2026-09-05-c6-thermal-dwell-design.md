# C6 — VIPER termal operasyon zarfı ve tolere edilebilir saplanma süresi — Tasarım Belgesi

**Tarih:** 5 Eylül 2026 · **Dal:** `berke-3d-backendEnhance` · **Kaynak madde:**
[12_faktor_backend_ozellik_arastirmasi_2026-09-03.md § C6](../../research/12_faktor_backend_ozellik_arastirmasi_2026-09-03.md)
· **Bağımlılık:** D3 (LP-R04/R05, `safety_monitor`, `surface_to_inner`), A1 (haven marjı,
`safe_haven_for_grids`), A4 (`comm_window_from_metadata`), Round 4 termal dinamiği
(`cost_cube.build_cost_cube(couple_thermal)`, `relax_surface_c`) — hepsi tamamlandı.

**Yol:** mimari (yeni çekirdek modül `thermal_dwell.py`, planlayıcıya yeni etiket ekseni ve kısıt,
üç uca yeni blok, iki yeni uç, güvenlik kataloğuna yeni gereksinim, replan tetikleyicisi, heat1d
önbelleği, rapor betiği). Kullanıcı onay kapısını kaldırdı; tasarım otonom kesinleştirildi, sayılar
sondalardan (aşağıda) okunur.

**Kapsam:** yalnızca `backend/app/`, `backend/test_*.py`, `scripts/`, `docs/`. Frontend koduna
dokunulmaz; `docs/frontend/3b-veri-sozlesmesi.md`'ye "C6 eki" yazılır (yalnızca ekleme).

---

## Amaç

LunaPath'in termal modeli bugün **statik** bir zarf denetimidir: hücrenin yıllık tepe (`thermal`)
ya da soğuk-uç denge (`thermal_min`) yüzey sıcaklığı `surface_to_inner` ofsetiyle iç sıcaklığa
çevrilir ve rover kataloğunun batarya/elektronik zarfına (bizim "izin verilen uçuş sıcaklığı",
AFT) karşı okunur. D3 bunun sonucunu ölçtü: **her gerçek rotada** LP-R04/LP-R05 ihlal (VIPER
30 May 2027: elektronik −7,96 °C, batarya −27,96 °C; LPR-1 28 Eyl 2026: −17,96 / −27,96 °C),
çünkü denge iç sıcaklığı zarfın dışında ve modelde ne zaman ekseni ne ısıtıcı var. "Bu hücrede
en fazla kaç saat hareketsiz durabilirim" sorusunun sayısı yok.

NASA JSC/MSFC'nin VIPER için geliştirdiği iki çerçeve (Slusser vd., ICES-2025-376) tam bu
soruya cevap arıyor: **sınırsız operasyon zarfı** (hangi geometride rover süresiz durabilir) ve
**tolere edilebilir saplanma süresi** (hareket edemeyen rover'ın "saati dolmadan" kurtarılması
gereken süre). C6 bu ikisini LunaPath'in kendi modeliyle kurar.

Tek cümlelik iddia: **Rover'ın iç sıcaklığı, kataloğun `thermal_tau_s` zaman sabitiyle birinci
dereceden gevşeyerek `surface_to_inner(yüzey(t))` hedefine gider; yüzey(t) 4-B küpün zaten
entegre ettiği regolit dinamiğidir (`shadowed_equilibrium_c` + `relax_surface_c`). Her (dilim,
blok) için bu dinamiğin batarya/elektronik zarfını terk etmesine kalan süre `max_dwell_h[t, y, x]`
hesaplanır (kapalı formla, tüm başlangıç dilimleri için vektörize); `astar_4d` istenirse hiçbir
hücrede bu süreden uzun bekleyemez (`require_thermal_dwell`), istenmese bit-eşittir; rota boyunca
iç sıcaklık izi dinamikle yeniden çizilir ve D3'ün bulgusu yeniden ele alınır; `/api/replan`
saplanma anından itibaren iki geri sayım verir (termal dwell + A1'in haven penceresi: JSC'nin
tanımı) — warning/critical/fail; heat1d'nin Site11 enlemindeki transient'i (Güneş yüksekliği ×
Güneş'e paralel eğim) kutulanarak JSC'nin zarf grafiğinin bizim modeldeki karşılığı kurulur.**

## İddia sınırı (her blokta, raporun her bölümünde)

- **Termal model MODEL/UNCALIBRATED'dır.** Yüzey sıcaklığı heat1d LUT'u (yıllık tepe) + gölge
  bağlaması; regolit gevşemesi `REGOLITH_THERMAL_TAU_S` (`REGOLITH_LAG_VALIDITY = "UNCALIBRATED"`);
  iç sıcaklık ofsetleri kataloğun MODELLED alanları. Diviner doğrulaması C5'in işi; burada
  "termal doğruluk" iddiası yapılmaz. `validity: MODEL`, `thermal_lag_validity: UNCALIBRATED`
  her blokta.
- **`surface_to_inner` işarete göre parçalıdır ve bu, sonuçları belirler:** LPR-1/VIPER için yüzey
  < 0 → +60 K, yüzey ≥ 0 → −40 K. Batarya zarfına [0, 35] giren yüzey bantları **[−60, −25] °C**
  (soğuk dal) ve **[40, 75] °C** (sıcak dal); aradaki **−25…0 °C** yüzeyler iç sıcaklığı 35–60 °C'ye
  ("sıcak yan") ve 0…40 °C yüzeyler −40…0 °C'ye ("soğuk yan") atar. Sonda 3: Site11 enleminde
  heat1d'nin en sıcak yüzeyi 30° Güneş'e bakan eğimde +44,5 °C → sıcak dalda iç +4,5 °C, zarf
  **içinde**. Yani JSC'nin sıcak yanı (aşırı ısınma) bizim modelde Site11'de **yok**; zarfın
  "sıcak-sınırlı" kutuları ofset modelinin −25…0 °C bandıdır. Rapor bunu bu kelimelerle yazar;
  ofsetler yumuşatılmaz, kataloğa sayı eklenmez.
- **Isıtıcının sıcaklığa etkisi için kaynaklı parametre YOK.** `p_heater_w` yalnız enerji
  modelindedir (B5/B1). C6 iki ısıtıcı modeli sunar: `heater_model="none"` (varsayılan: pasif
  gevşeme, ısıtıcı sıcaklığa girmez — bugünkü fizik) ve `heater_model="thermostat_assumed"`
  (**VARSAYIM**: ısıtıcı iç sıcaklığı zarfın alt sınırında tutar; kaynak dizesi `"assumption: …"`
  ile `constants.HEATER_THERMOSTAT_ASSUMPTION_SOURCE`; gerekçe: kataloğun `p_shadow_w`/`p_heater_w`
  ve `h_max_shadow_h` alanları bir hayatta-kalma ısıtıcısının gölgede bataryayı zarfında tuttuğunu
  ima eder ama W → K katsayısı yayımlanmamıştır). Rapor ikisini de süpürür. Kataloğa alan yazılmaz.
- **Başlangıç iç sıcaklığı bir parametredir** (`initial_inner_c`; varsayılan: en dar zarfın orta
  noktası — LPR-1/VIPER 17,5 °C, Yutu-2 10 °C). Dwell küpü "bu dilimde bu bloğa nominal iç
  sıcaklıkla varan rover" için hesaplanır; rota izinin gerçek iç sıcaklığı ayrıca entegre edilir ve
  raporlanır (küp yaklaşımı, iz gerçeği).
- **`thermal_tau_s` olmayan profilde (LUVMI-M) dwell hesaplanamaz:** `dwell_model.model =
  "unavailable"`, `reason: rover declares no thermal_tau_s`; denge zarf kararı (içinde/dışında)
  yine raporlanır. Regolit tau'su rover gövdesine **uydurulmaz**.
- **JSC'nin sayıları alıntıdır:** kutupta maksimum Güneş yüksekliği 1,5° (kutuptan uzaklaşan her
  enlem derecesi +1°); 16 azimut × 6 eğim (0–15°, 3° adım) = **96 kararlı-durum** durumu, rover park
  hâlinde ve en yüksek güç durumunda; 60'tan fazla kritik bileşen; AFT normalizasyon örneği "AFT
  65 °C olan bir aviyonik kutusu 77 °C → 12 °C aşım"; park edilmiş araçta "tipik olarak birkaç
  saatte" sıcak nokta. Bizim sayılarımız Site11'de koşturulup okunur; iki set hiç karıştırılmaz
  (`JSC_QUOTED` sözlüğü, `quoted` alanı).
- **Sınırsız operasyon zarfı JSC'de rover gövdesine bağlıdır, bizde araziye:** JSC'nin eksenleri
  **eğim (radyal) × Güneş azimutu rover başlığına göre (açısal)**, Güneş yüksekliği görevin
  **maksimumunda** sabit; yükseklik ekseni makalede "ileri iş" (canlı gösterge). LunaPath'te rover
  gövdesi/TMS geometrisi yok; bizim matrisimiz **Güneş yüksekliği × Güneş'e paralel eğim bileşeni**
  (`s_par = atan(tan s · cos(az_Güneş − bakı))`, pozitif = Güneş'e bakan) → heat1d yüzey sıcaklığı
  (13 Ay günlük transient'in kutudaki maksimumu) → iç sıcaklık → "sınırsız / soğuk-sınırlı (h) /
  sıcak-sınırlı (h) / örneklenmedi". "Aynı yöntem, bizim model"; karşılaştırma değil.
- **Tolere edilebilir saplanma süresi JSC'de haven penceresidir, termal değil:** makale bu süreyi
  "hedef haven'a Ay gecesinden önce varmak için kalan zaman − en hızlı rota" olarak tanımlar ve
  termal transient'i bu süreyle **sınırlar**; VIPER için tam işlenmediğini, SOC/gölge/rota
  etkilerini içermediğini söyler. LunaPath'te haven penceresi A1'in `hours_until_earthset −
  time_to_safe_haven_h` marjıdır; C6 saplanma bloğunda **iki geri sayım** verir: termal dwell (bu
  özellik) ve haven penceresi (A1); toplam = küçüğü, hangisinin sınırlayıcı olduğu yazılır.
- **`require_thermal_dwell` verilmezse planlayıcı bugünkü davranışla bit-eşittir** (etiket ekseni
  kapalı: baskınlık toleransı sonsuz, anahtar bileşeni 0; standart üç 4-B rota ve 2-B SHA
  kilitleri testte). Dwell küpü ve rota izi **her zaman raporlanır** (A1/A2 kalıbı); küp
  hesaplaması ölçülür ve "Uygulama sırasında bulunanlar"a yazılır.
- **B1'in 10 h arıza beklemesi C6'nın kısıtına girmez** (tasarım kararı): B1'in DP durumunda
  termal yok (B1 spec'i); C6 raporu "bir hücrede 10 h bekleme max_dwell'i aşar mı" sorusunu
  Site11'de **sayıyla** cevaplar (arıza beklemesi hücrelerinin yüzde kaçında aşılıyor); DP'ye
  bağlanması ayrı bir iş olarak not edilir. B1'in rapor sayıları değişmez.
- **Sayı uydurma yok:** her max_dwell, zarf kutusu, rota etkisi ve saplanma örneği Site11'de
  koşturulup okunur; "her yerde 0" çıkıyorsa öyle yazılır.

## Kaynak notu (5 Eylül 2026'da PDF okundu: ICES-2025-376, 15 sayfa)

- **Makale:** Slusser, Turk, Stewart, Page, Barragan, Mittag — *Generalizing Lunar Vehicle Thermal
  Analysis: Lessons Learned from VIPER*, 54th ICES, Prag, 13–17 Temmuz 2025, ICES-2025-376
  (NTRS 20250004028). Metin `pypdf` ile çıkarıldı ve tamamı okundu.
- **§ III.D Güneş yüksekliği:** "At a tilt of ≈1.5° relative to the equatorial plane of the Sun,
  the maximum solar elevation angle at the lunar poles is 1.5°, increasing by one degree for every
  degree in latitude from the pole." Site11 merkezi −88,92° → beklenen maksimum ≈ 2,6°; SPICE
  ölçümü (sonda 3a) yıllık −2,59…+2,55°, heat1d'nin kendi yörüngesi −2,62…+2,60° — tutarlı.
- **§ V.G Unlimited Operations Envelope:** varsayımlar (1) en yüksek güç durumu, (2) rover her
  açıda olabilir, (3) hareket arızası/saplanma her ortamda ve her eğimde olabilir. Grafik "Downslope
  Solar Azimuth Angle vs. Slope Angle": radyal eksen eğim 0–15° (VIPER'ın ±15° gereksiniminin
  pozitif yarısı), açısal eksen Güneş azimutu **rover başlığına göre**; eğim yönü Güneş azimutuna
  **paralel** (en sıcak regolit) ve Güneş yüksekliği görev boyunca **maksimum** varsayılır →
  sınırlayıcı sıcak durumlar; "meets requirements at a given solar elevation angle/slope → able to
  perform without restrictions at any lower solar elevation angle or slope". Durum matrisi: 16
  azimut × 0–15° 3° adım = **96 kararlı-durum**; negatif (Güneş'ten uzağa alçalan) eğimler bilerek
  dışarıda (hibernasyondan sıcak ama 0°'den serin). 60+ kritik bileşen; AFT aşımı normalize edilip
  üst üste bindirilir (en kötü marj), kübik ara değer, ARC-STD-8070 marj konturları. **Örnek:**
  "an avionics box may have an AFT of 65°C and have a modeled temperature of 77°C in some cases
  – exceeding AFT by 12°" — bir normalizasyon örneği, belirli bir eğim/yükseklik kombinasyonu değil.
  Mavi = aşım riski yok ("unlimited"), kırmızı = aşım **mümkün**. İleri iş: "a sweep of cross-slope
  solar azimuth angles … in conjunction with varying solar elevation angles … a live indicator".
- **§ V.H Tolerable Entrenched Time:** park edilmiş araçta sıcak nokta ("typically a few hours");
  hareket hâlinde ihmal edilebilir; iki haven arasındaki en hızlı rota + Ay gecesi penceresi →
  "a finite amount of time possible for a vehicle to remain static before being unable to complete
  the direct traverse and arrive at the destination safe haven before lunar night"; nominal
  (kararlı-durum/kısa transient, sürüş) ve nominal-dışı (bu süreyle sınırlı transient, en kötü
  azimut/yükseklik) analizler ayrılır. Kısıtlar: SOC farkları, geçici gölge, arızanın rota boyunca
  herhangi bir yerde olması hesaba **girmez**; VIPER'ın yavaş hızı yüzünden "always at risk of
  reaching thermal balance with any environment"; yöntem LTV/basınçlı rover'a daha uygun.
- **§ V.I Contingency Modes:** güç durumlarını ayırma (bizim ısıtıcı/`p_hibernate_w` alanlarımızla
  akraba; kapsam dışı).
- **Araç:** Thermal Desktop (düz plaka modeli, advection rutinleri). Haven geceleri: 50 h kadar
  kısa, çoğu 85–150 h (Lunar Surface Data Book).
- **Araştırma belgesine düzeltmeler:** (1) başlıktaki "(Güneş azimutu × yükseklik × eğim)" ve
  "Güneş azimutuna paralel eğim açısı vs. yükseklik" → makalenin grafiği **eğim × azimut**
  (maksimum yükseklikte); yükseklik ekseni ileri iş. (2) "bazı kombinasyonlarda AFT 12 °C aşılmış
  (77 °C)" → normalizasyon örneği (aviyonik kutusu, AFT 65 °C), kombinasyon verilmiyor.
  (3) "tolerable entrenched time … regolite saplanma durumunda dayanma süresi" → haven penceresi
  tabanlı süre; termal transient bu süreyle **sınırlanır**. (4) "`t_inner_min/max`" diye bir katalog
  alanı yok; zarf `bat_op_*`/`elec_op_*`'tır.

## Mevcut durumdan kullanılanlar (yeniden yazılmaz)

| Yetenek | Kod | Bu tasarımda rolü |
|---|---|---|
| Yüzey dinamiği (`shadowed_equilibrium_c`, `relax_surface_c`, `sunlit_peak_from_annual_peak_c`, `REGOLITH_THERMAL_TAU_S`) | `thermal_model.py` | Yüzey(t) serisi; `relax_surface_c` iç gövde için de aynı birinci dereceden lag |
| 4-B küpün dilim-dilim termal entegrasyonu | `cost_cube.build_cost_cube(couple_thermal, slice_hours, tau_s)` | `surface_temperature_series` olarak dışa çıkarılır; küp aynı diziyi kullanır (bit-eşit) |
| `surface_to_inner`, `_surface_ceiling_c`, zarf alanları | `cost_engine.py`, `constants.ROVERS` | İç hedef ve zarf (`bat_op_*` ∩ `elec_op_*`) |
| Etiket-koyan A* (Pareto cephesi, `REJECTION_KEYS`, `no_path_reason_4d`, `path_dark_hours` kalıbı) | `pathfinder_4d.py` | Yeni `stay_h` ekseni ve `thermal_dwell` reddi aynı kalıpta |
| Gölge serisi (`build_shadow_series`), Güneş izi (`sun_track_for_series`), ufuk küpü (mmap) | `illumination_series.py`, `earth_visibility.comm_window_from_metadata` | Tek hücre gölge serisi (`cell_shadow_series`), haven penceresi (`trigger_minutes_remaining`) |
| Haven haritası ve `time_to_safe_haven_h` (A1) | `safe_haven.safe_haven_for_grids` | Saplanma bloğunun haven geri sayımı |
| Güvenlik kataloğu (FRETISH + STL, `trace_from_plan4d`, `trace_from_samples`, `fret_export`) | `safety_monitor.py` | LP-R12 `thermal_dwell` (sinyal `dwell_margin_h`) |
| Tetikleyici taksonomisi (`_TRIGGER_INPUTS`, skipped kalıbı) | `replan_triggers.py` | `entrenchment` tetikleyicisi |
| Katman tel biçimi (`encode_layer_f32`, `binary_layer_headers`, `layer_stats`) | `terrain.py` | `GET /api/thermal-dwell` |
| Sabit kalıbı (`*_MODEL_ID`, `*_VALIDITY`, `*_CLAIM`, `*_REFERENCES`, `*_QUOTED`) | `survival.py`, `risk.py` | `thermal_dwell.py` sabitleri |
| heat1d GitHub main (slope/slope_az, crank-nicolson), `Heat1DModel.available()` | `thermal_model.py` | Zarf matrisi için transient kayıt (alt sınıf) |

## Sondalar (5 Eylül 2026; atılabilir betikler, sayılar buraya)

**Sonda 2 — Site11'de denge iç sıcaklığı ve kapalı formlu dwell** (geçilebilir 210 063 ince hücre;
merkez enlem −88,9205°; `thermal_field: sunlit_peak`; yüzey tepe −146,4…+28,2 °C, medyan −47,2;
`thermal_min` −150,0…−28,0, medyan −96,0; gölge oranı ort. 0,614):

| Rover | İç @tepe (min / med / maks) | Batarya zarfında @tepe (soğuk / sıcak dışı) | @soğuk uç | Elektronik @tepe | PSR tabanına (−183 °C) karşı 17,5 → 0 °C süresi |
|---|---|---|---|---|---|
| LPR-1 (τ 7 200 s, [0, 35]) | −86,4 / 1,9 / 59,0 | **%33,6** (%48,9 soğuk, %17,6 sıcak) | **%10,4** (%89,6 soğuk) | %48,1 | **0,266 h (16 dk)**; −150 °C: 21 dk; −100 °C: 44 dk |
| VIPER (τ 8 000 s, [0, 35]) | aynı | %33,6 | %10,4 | %63,8 | 0,295 h (18 dk) |
| LUVMI-M (τ yok, [−100, 0], ofset yok) | −146,4 / −47,2 / 28,2 | %83,0 | %55,2 | — | hesaplanamaz |

Kapalı formlu max_dwell (T0 = 17,5 °C, sabit hedef): soğuk-uç hedefle LPR-1 hücrelerinin %10,4'ü
sınırsız, kalanı 0,36–12,4 h (medyan **0,73 h**, p95 2,9 h); tepe hedefle %33,6 sınırsız, kalanı
0,37–10,4 h (medyan 1,2 h; %48,9 soğuk-, %17,6 sıcak-sınırlı). **Cevap: "her yerde 0" değil, ama
gölgede çeyrek saat mertebesi.** B1'in 10 h arıza beklemesi bu dağılımda hücrelerin büyük
çoğunluğunda dwell'i aşar (raporda ölçülür).

**Sonda 3a — SPICE Güneş geometrisi, Site11 merkezi:** 13 Eyl 2026'dan 30 gün saatlik: yükseklik
−0,40…+2,10°, %72,5 ufuk üstü; 30 May 2027'den: −2,33…+0,08°, yalnız %12,1 ufuk üstü (VIPER
epoğu Ay gecesine yakın; A1'in 862 haven'ı Dünya penceresinden); yıllık günlük örnek (1 Haz 2026 +
400 gün): **−2,59…+2,55°**. Azimut her Ay gününde 360° tarar (kutup); grid-gerçek azimut farkı
287,33°. 1 840 SPICE çağrısı 0,2 s.

**Sonda 3b — heat1d transient, Site11 enlemi, Güneş'e paralel eğim × yükseklik** (10 eğim: 0,
2,5, …, 15, 20, 25, 30°; `ndays=13`, crank-nicolson; `Model.advance` alt sınıfla her adımda Güneş
yüksekliği/azimutu kaydedildi; 20–30 k örnek/koşum; toplam **41,5 s**):

| Eğim (Güneş'e bakan, tepe anı) | 0° | 5° | 10° | 15° | 20° | 25° | 30° |
|---|---|---|---|---|---|---|---|
| heat1d tepe yüzey (°C) | **−146,4** | −85,0 | −45,1 | −15,2 | +8,7 | +28,2 | **+44,5** |

Kutulu matris (yükseklik −3…3° × 0,5°; `s_par` −30…30° × 2,5°): kutuların %71'i örneklendi; T_max
Güneş ufuk altındayken (heat1d'nin düz-ufuk kırpması) −170…−230 °C, ufuk üstünde `s_par` ile
monoton artıyor (el 2,25°: s_par 1,2° → −112 °C, 11,2° → −30 °C, 26,2° → +34 °C). LPR-1/VIPER
(zarf [0, 35]): 205 örneklenen kutunun **19'u sınırsız** (yüzey −60…−25 °C), **13'ü "sıcak-sınırlı"**
(hepsi yüzey −24…0 °C → soğuk dal +60 → iç 36–60 °C: ofset artefaktı), **173'ü soğuk-sınırlı**.
Gerçek sıcak dal (yüzey ≥ 40 °C) hiçbir kutuda yok → **JSC'nin sıcak yanı Site11'de bağlayıcı
değil.** Bizim rotalarımız soğuk yanda.

## Tasarım kararları

1. **Zarf ve hedef.** `Envelope(lo, hi, lo_component, hi_component)`: `lo = max` ilan edilen alt
   sınırların (`bat_op_min_c`, `elec_op_min_c`), `hi = min` üst sınırların; hangi bileşenin sınırı
   olduğu yazılır (LPR-1: alt batarya 0, üst batarya 35; VIPER aynı; Yutu-2 alt batarya −10, üst
   batarya 30; LUVMI-M alt −100, üst 0, yalnız batarya). Hedef `inner_target_c(yüzey, rover)` =
   `surface_to_inner` vektörize (skalerle 1e-12 testte). `nominal_inner_c = (lo + hi)/2`.
2. **Dinamik.** `T_inner(t+Δ) = g + (T_inner(t) − g)·e^{−Δ/τ}` (`relax_surface_c` aynen; τ =
   `thermal_tau_s`). Sabit hedef için kapalı form `exit_time_h(T, g, lo, hi, τ)`: T zarf dışında →
   0; g ∈ [lo, hi] → ∞; g < lo → τ·ln((T − g)/(lo − g)); g > hi → τ·ln((g − T)/(g − hi)).
   Parça-sabit hedef serisi (dilim başına) için aynı form dilim içinde uygulanır.
3. **Dwell küpü, vektörize ve kapalı formlu.** Doğrusallık: `T(t; t0) = F[t] + e^{−(t−t0)/τ}·(T0 −
   F[t0])`, `F` = sıfırdan başlayan tek ileri geçiş (hedefin üstel hareketli ortalaması). Tüm
   başlangıç dilimleri `t0` bir 2-B durum dizisi (`T × H'W'`) olarak birlikte ilerletilir: adım `k`'de
   aktif `(t0, blok)` çiftleri için `T_k` kapalı formdan, hedef `g[t0+k]`; dilim içinde sınır
   aşılıyorsa `dwell = kΔ + τ·ln(…)`, aktif kümeden düşer; ufuk sonuna dek çıkmayan → **+∞**
   (`open_ended`, `lookahead_h[t0] = (T − t0)·Δ` yazılır). Çıktı `DwellCube`: `max_dwell_h`
   (float32, inf serbest, geçilmez blok NaN), `side` (int8: 0 yok, 1 soğuk, 2 sıcak), `component`
   (int8: 0 yok, 1 batarya, 2 elektronik), `lookahead_h`, `initial_inner_c`, `heater_model`,
   `tau_s`, özet. Bütçe: `DWELL_MAX_STATES = 5 000 000` (`T × H'W'`; Site11 Ay gecesi 270 × 15 625 =
   4,2 M → m = 1); aşılırsa başlangıç dilimleri `m`'lik kutulara toplanır (`slices_per_bin`,
   planlayıcı `floor` kutuyu okur; sapma raporda). Süre ölçülür (§ bulunanlar).
4. **Isıtıcı.** `heater_model="none"`: hedef olduğu gibi. `"thermostat_assumed"`: hedef
   `max(g, lo)` (ısıtıcı alt sınırı tutar, soğuk yan hiç çıkmaz; sıcak yan aynı); her blokta
   `heater_model` ve varsayım kaynağı; enerji tarafı zaten `p_shadow_w` ile planlayıcıda.
5. **Planlayıcı (`astar_4d(max_dwell_cube=None, require_thermal_dwell=False)`).** *(Uygulamada sapma —
   bkz. "Bulunanlar" 1: kalış ekseni yerine iç sıcaklık ekseni; aşağıdaki kalış kuralı tasarımın ilk hâlidir.)*
   Etiket beşinci eksen `stay_h` (hücrede kesintisiz hareketsiz saat; hamlede 0'a döner). Kısıt açıkken WAIT
   `(r, c, t) → (r, c, t+1)`: `stay' = stay + Δ`, kalış başlangıcı `t_arr = t − round(stay/Δ)`,
   `stay' > max_dwell[t_arr, r, c] + 1e-9` → `rejections["thermal_dwell"]`. Baskınlıkta az kalış
   baskın (tolerans Δ), anahtar `int(stay/Δ)`; **kısıt kapalıyken tolerans ∞ ve anahtar 0 →
   bit-eşit** (B1'in `surv` kalıbı). `no_path_reason_4d`: "N waits would have kept the rover
   stationary longer than the thermal dwell its inner temperature allows there
   (require_thermal_dwell: …)". Her zaman raporlanır (küp verilince, kısıt kapalı olsa da; yoldan
   sonradan hesaplanır): `path_stay_hours`, `path_max_dwell_h` (kalışın varış dilimindeki bütçe;
   ∞ → None), `path_dwell_margin_h`, `metrics.min_dwell_margin_h`, `states_past_thermal_dwell`
   (kısıt açıkken 0), `max_stay_h`, `thermal_dwell_enforced`. Küp yokken hepsi None.
6. **Rota iç sıcaklık izi (D3'ün yeniden ele alınışı).** `route_inner_trace(path_states,
   surface_series, Δ, rover, T0, heater)`: başlangıçta `T0`; her durumdan sonrakine geçen sürede hedef
   varılan bloğun yüzeyi (planlayıcının gölge saati kuralı: "saat rover'ın vardığı yerde"); durum
   başına `inner_c`, zarf dışı sayısı, ilk çıkış saati ve tarafı/bileşeni, min/maks. `thermal_dwell`
   bloğunda (`route.inner`) ve `path_inner_c` listesinde. **D3'ün `safety_margins` LP-R04/R05
   değerleri değişmez** (statik kalır; D3 raporu geçerli); dinamik iz yeni alandır.
7. **LP-R12 `thermal_dwell`** (`safety_monitor.REQUIREMENTS`): "The rover shall always satisfy
   stay_h <= max_dwell_h"; STL `always (dwell_margin_h >= 0)`; sinyal `dwell_margin_h` (h, açık uçlu
   +∞), eşik 0 (`fixed`), normalizer `hours_per_day`, `trace_kinds ("4d", "telemetry")`.
   `trace_from_plan4d(..., path_dwell_margin_h=None)` (yeni isteğe bağlı parametre; None → sinyal
   yok → `applicable: false`, mevcut izler aynen); `SAMPLE_KEYS += ("dwell_margin_h",)` (telemetri).
   `fret.json` yeniden üretilir, `docs/requirements/README.md` satır, D3 testi `range(1, 13)`.
   ROS düğümüne dokunulmaz (sinyal telemetri örneğinde isteğe bağlı).
8. **Saplanma tetikleyicisi.** `replan_triggers.check_entrenchment(entrenched_hours,
   tolerable_hours)`: oran `u = entrenched/tolerable`; seviye `ok` (< 0,5), `warning` [0,5, 0,8),
   `critical` [0,8, 1), `fail` (≥ 1); `triggered = seviye ∈ {critical, fail}`; `detail` seviyeyi ve
   kalan saati söyler. `_TRIGGER_INPUTS["entrenchment"] = ("entrenched_hours",
   "tolerable_entrenched_hours")`. Sabitler `ENTRENCHMENT_WARNING_FRAC = 0.5`,
   `ENTRENCHMENT_CRITICAL_FRAC = 0.8` (eşik seçimi bizim; kaynaklı değil, öyle yazılır).
9. **`POST /api/replan` saplanma bloğu.** `state.entrenched_hours` verilince ve `utc` + grid varsa:
   mevcut hücrenin ince yüzey serisi (`cell_shadow_series` + sunlit tepe + regolit gevşemesi,
   `lookahead_hours` varsayılan 24 h, dilim 0,5 h) → `T0 = state.actual_inner_c` (varsa) ya da
   nominal → termal dwell; haven geri sayımı `comm_window.trigger_minutes_remaining/60 −
   time_to_safe_haven_h[row, col]` (A4 + A1; yoksa `null` + neden); `overall.tolerable_h = min`,
   `limiting`; `tolerable_entrenched_hours` state'e enjekte edilir (sonluysa) ve tetikleyici koşar.
   Yanıt `entrenchment` bloğu (her iki modda; istenmemişse `null` + `entrenchment_model.reason`).
   Mevcut alanlar aynen.
10. **API (yalnızca ekleme).** `Plan4DRequest.require_thermal_dwell` (bool), `initial_inner_c`
    (−150…150), `heater_model` (`none`|`thermostat_assumed`). `/api/plan-4d` yanıtı `thermal_dwell`
    bloğu (her zaman): `model`, `validity`, `thermal_lag_validity`, `requested/applied`
    (`applied` = kısıt uygulandı), `envelope` (lo/hi/bileşenler), `initial_inner_c`,
    `heater_model` (+ `heater_source`), `tau_s`, `cube` (dilim/blok sayısı, `slices_per_bin`,
    dilim 0'da sınırsız/soğuk/sıcak kesirleri, sonlu dwell medyanı/p5, süre ms), `route`
    (`min_dwell_margin_h`, `states_past_thermal_dwell`, `max_stay_h`, `wait_steps`, `inner`
    {min, max, states_outside, first_exit_h, side, component}), `quoted`, `claim`; listeler
    `path_max_dwell_h`, `path_dwell_margin_h`, `path_inner_c` (üst düzey, B1 kalıbı). 404 metnine
    ret sayısı cümlesi. τ'suz rover + `require_thermal_dwell` → 422. `/api/cell-telemetry?
    thermal_dwell=true&start_utc=&t_hours=0&lookahead_hours=24&initial_inner_c=&heater_model=` →
    `thermal_dwell` {`max_dwell_h`, `open_ended`, `side`, `component`, `inner_equilibrium_c`
    {peak, cold_end}, `envelope_verdict` {peak, cold_end}, `initial_inner_c`, `lookahead_h`,
    `tolerable_entrenched` {thermal, haven, overall}} + `thermal_dwell_model`. `GET
    /api/thermal-dwell?start_utc=&rover_id=&t_hours=0&lookahead_hours=24&slice_hours=0.5&coarsen=4&
    initial_inner_c=&heater_model=&format=json|f32&field=max_dwell_h|side|open_ended` (kaba grid,
    `/api/survival` kalıbı; f32'de `max_dwell_h` = `min(dwell, lookahead)` ve `open_ended` ayrı
    alan; `X-Layer-Validity: MODEL`). `GET /api/thermal-envelope?rover_id=&initial_inner_c=&
    heater_model=` → zarf matrisi (önbellekten; yoksa 422 + neden).
11. **Zarf matrisi ve önbelleği.** `thermal_dwell.heat1d_envelope_samples(lat_deg, slopes, ndays=13)`
    (heat1d `Model` alt sınıfı `advance`'ta Güneş yüksekliği/azimutunu kaydeder; son fazın
    örnekleri T satırlarıyla hizalanır; heat1d yoksa/API değişmişse `RuntimeError` → çağıran
    "unavailable" der) ve `bin_envelope(samples, el_edges, sp_edges)` → `tmax, tmean, count`.
    `scripts/build_thermal_envelope_cache.py` → `lunapath/data/processed/thermal_envelope_heat1d.npz`
    + `thermal_envelope_meta.json` (enlem, eğimler, ndays, çözücü, heat1d sürümü, süre; gitignore
    satırları). `envelope_matrix(cache, rover, T0, heater)` → kutu başına yüzey T_max, iç, karar,
    dwell (h). Uç ve rapor bunu okur.
12. **`cost_cube.surface_temperature_series(base_grids, shadow_ratio_series, coarsen, slice_hours,
    tau_s) -> (T, H', W')`** dışa çıkarılır; `build_cost_cube(..., surface_series=None)` verilirse
    onu kullanır, verilmezse kendisi çağırır — aynı işlem sırası, **bit-eşit** (küp testleri ve
    Site11 SHA kilitleri). `/api/plan-4d` seriyi bir kez hesaplar, küpe ve dwell'e verir.
13. **`illumination_series.cell_shadow_series(metadata, row, col, n_slices, slice_hours, start_utc)`**
    → `(list[float], provenance)`: ufuk küpü mmap, tek hücre profili, `build_shadow_series` ile aynı
    statik geri dönüş (taban değeri) ve provenance şekli.
14. **Sabitler (`constants.py`):** `HEATER_THERMOSTAT_ASSUMPTION_SOURCE` (`"assumption: …"`);
    profillere alan **eklenmez**. `terrain.LAYER_UNITS/LAYER_DESCRIPTIONS`: `max_dwell_h` ("h"),
    `dwell_side` ("code") — manifeste girmez.
15. **Rapor** `scripts/thermal_dwell_report.py` (`--json` önce, `--from-json`; `--skip-envelope`,
    `--heater none,thermostat_assumed`) → `docs/research/thermal_dwell_report.md`: (1) JSC zarfı
    (alıntı) vs bizim matris (heat1d, Site11 enlemi; LPR-1 ve VIPER kararları; "aynı yöntem, bizim
    model"); (2) Site11'de rover başına denge iç sıcaklığı ve zarf içi kesir (D3 bulgusu dinamikle:
    standart rotalarda iç sıcaklık izi, ilk çıkış saati, LP-R04/R05 hâlâ ihlal mi); (3) max_dwell
    dağılımı iki epok × iki rover (küp; sınırsız/soğuk/sıcak; medyan; süre) ve B1'in 10 h
    beklemesinin aşıldığı blok kesri; (4) standart üç rotada `require_thermal_dwell` etkisi (WAIT,
    varış, SOC; 200/404 ve gerekçe), iki ısıtıcı modeli; (5) saplanma örnekleri (`/api/replan`, Ay
    gecesi çiftinde başlangıç ve rota ortası hücre; termal ve haven geri sayımı; seviyeler);
    (6) iddia sınırı ve sunum cümlesi.

## Bileşenler

### 1. `app/thermal_dwell.py` — yeni modül

```
THERMAL_DWELL_MODEL_ID = "inner_temperature_first_order_lag_v1"; THERMAL_DWELL_VALIDITY = "MODEL"
HEATER_MODELS = ("none", "thermostat_assumed"); SIDE_NONE/COLD/HOT = 0/1/2; COMPONENT_NONE/BATTERY/ELECTRONICS = 0/1/2
DWELL_MAX_STATES = 5_000_000; DEFAULT_DWELL_LOOKAHEAD_H = 24.0; DEFAULT_DWELL_SLICE_H = 0.5
THERMAL_DWELL_SCOPE, THERMAL_DWELL_CLAIM, THERMAL_DWELL_REFERENCES, JSC_QUOTED
ENVELOPE_EL_EDGES (−3…3, 0,5), ENVELOPE_SPAR_EDGES (−30…30, 2,5), ENVELOPE_SLOPES_DEG, ENVELOPE_CACHE_FILENAME, ENVELOPE_META_FILENAME

Envelope (lo, hi, lo_component, hi_component, components) ; rover_envelope(rover) -> Envelope | None
nominal_inner_c(rover) -> float | None
inner_target_c(surface_c, rover) -> ndarray            # surface_to_inner vektörize
apply_heater(target, envelope, heater_model) -> ndarray
exit_time_h(T, target, envelope, tau_s) -> (hours ndarray (inf), side int8, component int8)   # kapalı form
DwellCube (dataclass): max_dwell_h (T,H,W) f32; side; component; lookahead_h (T,); slice_hours; slices_per_bin;
    initial_inner_c; heater_model; tau_s; envelope; n_states; compute_ms; summary() ; at(t, r, c) -> (dwell, side, comp)
build_dwell_cube(surface_series (T,H,W), slice_hours, rover, traversable, initial_inner_c=None, heater_model="none",
    max_states=DWELL_MAX_STATES) -> DwellCube | None (τ/zarf yoksa)
dwell_unavailable_reason(rover) -> str | None
route_inner_trace(path_states, surface_series, slice_hours, rover, initial_inner_c, heater_model) -> dict
route_dwell_report(path_states, slice_hours, cube) -> dict   # stay/budget/margin listeleri + özet (planlayıcı da kullanır)
cell_dwell(sunlit_peak_c, base_shadow, shadow_series, slice_hours, rover, initial_inner_c, heater_model) -> dict
thermal_dwell_block(cube|None, route|None, requested, applied, reason, inner_trace|None, rover) -> dict
entrenchment_block(entrenched_h, thermal|None, haven|None) -> dict   # seviyeler, limiting
heat1d_envelope_samples(lat_deg, slopes, ndays=13) -> dict(el, s_par, t_c, slope) ; bin_envelope(...) ; envelope_matrix(cache, rover, T0, heater)
envelope_cache_path(metadata) ; load_envelope_cache(path) ; save_envelope_cache(path, arrays, meta)
```

### 2. `app/pathfinder_4d.py` — yalnızca ekleme
`REJECTION_KEYS += ("thermal_dwell",)`; `_dominated/_insert_label` beşinci eksen `stay` (+ `stay_tol`);
`label_of` yedinci öğe `stay_key`; WAIT dalında bütçe denetimi; `_empty` ve dönüşte yeni
alanlar/metrikler (küp yokken None); `no_path_reason_4d` yeni cümle.

### 3. `app/cost_cube.py`
`surface_temperature_series(...)`; `build_cost_cube(surface_series=None)`.

### 4. `app/illumination_series.py`
`cell_shadow_series(...)`.

### 5. `app/safety_monitor.py`
`SIGNAL_NAMES += ("dwell_margin_h",)`, `SAMPLE_KEYS += ("dwell_margin_h",)`, LP-R12, `trace_from_plan4d(path_dwell_margin_h=None)`,
`trace_from_samples` geçişi. `docs/requirements/lunapath.fret.json` yeniden üretilir.

### 6. `app/replan_triggers.py`
`ENTRENCHMENT_WARNING_FRAC`, `ENTRENCHMENT_CRITICAL_FRAC`, `entrenchment_level(u)`, `check_entrenchment(...)`, `_TRIGGER_INPUTS`.

### 7. `app/main.py`

| Uç | Değişiklik |
|---|---|
| `POST /api/plan-4d` | üç istek alanı; `surface_temperature_series` bir kez; `build_dwell_cube` (her zaman, τ'lu rover); `astar_4d(max_dwell_cube, require_thermal_dwell)`; `route_inner_trace`; `thermal_dwell` bloğu + üç liste; `_safety_margins_4d`'ye `path_dwell_margin_h` (LP-R12); 404 cümlesi; 422 (τ'suz rover + kısıt) |
| `GET /api/cell-telemetry` | `thermal_dwell=true` ile blok (ince hücre; haven/Dünya penceresi A1/A4 önbelleklerinden) |
| `POST /api/replan` | `state.entrenched_hours` → `entrenchment` bloğu, `tolerable_entrenched_hours` enjeksiyonu, tetikleyici |
| `GET /api/thermal-dwell` | kaba grid katmanı (json/f32) |
| `GET /api/thermal-envelope` | önbellekten matris |

### 8. `app/constants.py`, `app/terrain.py`, `.gitignore`
Yukarıdaki sabit ve etiketler; önbellek meta satırları.

### 9. `scripts/build_thermal_envelope_cache.py`, `scripts/thermal_dwell_report.py`, `scripts/export_fret_requirements.py` (yeniden koşturulur)

## Veri akışı

```
/api/plan-4d ─ build_shadow_series ─► surface_temperature_series (coarse, T×H'×W')
                                        ├─► build_cost_cube(surface_series=…)   (bit-eşit)
                                        └─► build_dwell_cube ─► DwellCube ─► astar_4d(max_dwell_cube, require) ─► path_states
                                                                             └─► route_dwell_report + route_inner_trace ─► thermal_dwell bloğu, LP-R12
/api/cell-telemetry?thermal_dwell=true ─ cell_shadow_series ─► cell_dwell ─► blok ; safe_haven_for_grids + comm_window ─► tolerable_entrenched
/api/replan(state.entrenched_hours, utc) ─ cell_dwell + haven penceresi ─► entrenchment_block ─► state.tolerable_entrenched_hours ─► check_entrenchment
/api/thermal-dwell ─ build_shadow_series(lookahead) ─► surface_temperature_series ─► build_dwell_cube ─► [t_hours] katman
/api/thermal-envelope ─ load_envelope_cache ─► envelope_matrix(rover, T0, heater)
scripts/build_thermal_envelope_cache.py ─ heat1d_envelope_samples ─► bin_envelope ─► .npz + meta
```

## Hata davranışı

- τ'suz ya da zarfsız rover: `thermal_dwell.dwell_model = unavailable` + neden; `require_thermal_dwell`
  ile 422; denge kararı yine verilir.
- `initial_inner_c` zarf dışı: küp her yerde 0 (kapalı formun tanımı); blok `initial_outside_envelope: true`.
- Gölge serisi statik (epok/ufuk küpü yok): dwell hesaplanır ama `shadow_model.static` ve neden taşınır
  (hedef zamanla değişmez; kararlar uzun-dönem gölge oranından).
- `cell_shadow_series`/haven/Dünya penceresi başarısızlığı: ilgili alt blok `null` + neden; uç düşmez.
- `/api/thermal-envelope`: önbellek yok → 422 + `scripts/build_thermal_envelope_cache.py` yönlendirmesi;
  heat1d yok → betik "unavailable" der ve dosya yazmaz.
- `state.entrenched_hours` ≤ 0 ya da sonlu değil → tetikleyici `skipped` (mevcut kalıp).
- Dwell küpü bütçeyi aşarsa `m` kutulama; `slices_per_bin` yanıtta.

## Test stratejisi

- **Birim (`test_thermal_dwell.py`, çekirdeksiz):** `inner_target_c` ↔ `surface_to_inner` (4 rover ×
  10 000 yüzey, 1e-12); `rover_envelope` bileşen seçimi; `exit_time_h` üç durum (0 / ∞ / sonlu),
  soğuk/sıcak yan, bileşen; monotonluk (daha sıcak hedef ⇒ soğuk yanda daha uzun); `build_dwell_cube`
  sabit hedefte kapalı formla eşit, iki-dilimli hedefte (aydınlık→gölge) elle çözümle eşit,
  `open_ended` ufuk, termostat soğuk yanı sonsuz yapar/sıcak yanı değiştirmez, τ'suz rover None,
  bütçe kutulama; `route_inner_trace` kapalı form; `route_dwell_report` kalış/marj; `astar_4d`: küp
  None ↔ küp verilmiş-kısıt kapalı **aynı yol, aynı düğüm, aynı metrik**; kısıt açıkken uzun
  bekleme reddi ve `thermal_dwell` sayacı, 404 gerekçesi; `check_entrenchment` dört seviye ve
  `triggered`; LP-R12 katalog/FRET/`trace_from_plan4d`/`trace_from_samples`; `bin_envelope` ve
  `envelope_matrix` sentetik örneklerle; `surface_temperature_series` ↔ `build_cost_cube` bit-eşit.
- **API (`test_thermal_dwell_api.py`, 16 × 16 fixture, statik gölge):** istek alanları ve sınırlar;
  `thermal_dwell` bloğu iki şekli; `require_thermal_dwell` ile soğuk fixture'da bekleme reddi (rota
  ya beklemesiz ya 404 gerekçeli); `path_*` listeleri; `safety_margins` LP-R12 satırı; cell-telemetry
  bloğu; replan `entrenchment` seviyeleri (utc'li, statik seri); `GET /api/thermal-dwell` json/f32
  başlıkları; `GET /api/thermal-envelope` 422 ve tmp önbellekle 200.
- **Gerçek grid (`test_thermal_dwell_real_grid.py`, skip-korumalı):** standart üç rota kısıtsız
  41 / 116 / 8 hamle; kısıtla sonuç (200 ya da gerekçeli 404) ve `thermal_dwell` bloğu tutarlılığı;
  küp özetinde sınırsız kesri sondayla uyumlu (LPR-1 gündüz dilim 0: %5–%45 aralığı); Ay gecesi
  başlangıç hücresinde replan saplanma bloğu; zarf önbelleği varsa maks yüzey < 60 °C ve LPR-1
  sıcak dal boş.

## Kapsam dışı

- Rover gövdesi/TMS geometrisi ve JSC'nin rover-başlığına göre azimut ekseni; bileşen bazlı 60+ AFT.
- Park edilmiş araç sıcak noktası (JSC § V.H Fig. 12; Thermal Desktop advection).
- Isıtıcı için W → K modeli (kaynak yok; termostat yalnız etiketli varsayım).
- B1 DP'sine termal durum (B1 spec'i; raporda yalnız sayı).
- Diviner doğrulaması (C5); ROS düğümüne yeni konu; frontend.
- `/api/plan` (2-B) için dwell (zaman ekseni yok; D3'ün statik marjı kalır).

## Uygulama sırasında bulunanlar ve ölçümler

### Bulunanlar (tasarımdan sapmalar, nedenleriyle)

1. **Kısıt kalışa değil iç sıcaklığa bağlandı (karar 5'ten sapma).** İlk sürüm "hücrede kesintisiz kalış
   ≤ `max_dwell`" kuralını `stay_h` etiket ekseniyle uyguladı; testte planlayıcı kuralı **iki karanlık blok
   arasında ileri-geri hamleyle** boşa çıkardı (her hamle kalış saatini sıfırlıyor; 4 × 4 toy gridde 20 dilim
   beklemek yerine kıpırdanarak hedefe vardı). Gölgede kıpırdanmak da soğutur; fiziksel olarak anlamlı büyüklük
   iç sıcaklığın kendisidir. Yeni kural: her etiket iç sıcaklığını taşır (bekleme: beklenen bloğun hedefi;
   hamle: **varılan** bloğun hedefi, planlayıcının gölge saati kuralı), zarf dışına çıkan **her geçiş**
   (bekleme ya da hamle) `thermal_dwell` sayacıyla reddedilir. Kalış bütçesini aşan bekleme zaten zarf
   dışına çıktığından eski kural bunun özel hâlidir. `DwellCube` bu yüzden hedef serisini (`target_c`) de
   taşır; `inner_after`/`inner_along` planlayıcı ve rapor için tek entegrasyon. Baskınlık ekseni "termal marj"
   (yakın sınıra uzaklık, fazlası baskın). Testler: kıpırdanma boşluğu (`…cannot_be_evaded_by_shuffling…`),
   1,0 h maruziyette −100/−90/−80 °C yüzeylerle ret/ret/kabul, kısıtlı rotanın izi post hoc izle ±1e-3.
2. **Termal eksen toleransı etiket patlaması yaptı.** Batarya ekseninin ayarıyla (%1 tolerans, 400 anahtar
   kutusu) Site11 gündüz rotasında kısıt açıkken arama **2,3 GB ve 10 dakikada bitmedi** (aynı düğüme güneşli ve
   gölgeli yollardan gelen etiketler onlarca K farklı, neredeyse hiçbiri budanmıyor); %5 / 20 kutuda olanaksız
   gündüz rotasının reddi 156 s. Karar: **%10 tolerans, 10 kutu** (`_THERMAL_MARGIN_TOL_FRAC`,
   `_THERMAL_MARGIN_BINS`); kısıt tam değerle denetlenir, yalnız budama kaba (3,5 K içindeki daha sıcak ama daha
   pahalı etiket düşebilir). Kısıt kapalıyken tolerans ∞ ve anahtar 0 → bit-eşit (testte aynı düğüm sayısı).
3. **Dwell küpü ufuk boyunca aktif çiftlerle O(T²)'ydi.** Termostat modunda hedef zarf içinde kalan hücreler
   (%99) ufuk sonuna dek adımlanıyordu: gündüz rotasında 9,5 s. `last_outside[c]` (bloğun hedefinin en son zarf
   dışında olduğu dilim) hesaplanıp bu dilimi geçen çiftler anında açık uçlu sayılınca termostat küpü **0,2–0,5 s**,
   pasif küp 2,6 s (gündüz, 120 dilim × 15 625 blok) / 7,6–8,7 s (gece, 270 dilim). Her `/api/plan-4d` çağrısında
   kurulduğu için başlangıç ekseni kutulandı: `DWELL_MAX_STATES` 5 M → **1 M** (gündüz m = 2 → 1,2 s; gece m = 5;
   VIPER m = 1). Kutulama yalnız raporu kabalaştırır: planlayıcının kısıtı küpü değil dilim başına hedef serisini okur.
4. **API fixture'ının dwell'i −100 °C yüzeyden değil bağlanmış dengeden gelir.** Statik gölge oranı 0,3 sunlit
   −100 °C'yi `shadowed_equilibrium_c` ile −113,5 °C'ye bağlar → LPR-1 iç hedef −53,5 °C → dwell **0,566 h**
   (0,725 değil). Test beklentileri modelin kendisinden hesaplanır (`_fixture_dwell_h`); replan seviye eşikleri
   buna göre (0,1 → ok, 0,4 → warning, 0,47 → critical, 5 → fail).
5. **`data/processed/` gitignore deseni `lunapath/data/processed/`'i kapsamıyor** (ortasında ayraç olan desen
   .gitignore köküne bağlı); `*.npy` ayrıca eşleşiyor ama `.npz` değil → `thermal_envelope_heat1d.npz` ve meta
   JSON açıkça eklendi (C4'ün `roughness_baselines.npz` satırı gibi).
6. **heat1d zarf önbelleği** (10 eğim × 13 Ay günü, crank-nicolson): 235 159 örnek, 205/288 kutu, yüzey
   −232,4…+44,5 °C, Güneş yüksekliği −2,62…+2,60°; betik **233 s** (sondada aynı koşum 41,5 s: makine o sırada
   regresyon testleriyle yüklüydü; yeniden ölçüm aşağıda).
7. **Güvenlik kataloğu 12 gereksinim:** LP-R12 eklendi; D3'ün iki testi (`range(1, 12)`, `REQ_IDS`) 13'e
   güncellendi; `fret.json` yeniden üretildi; 2-B izlerde `applicable: false` (sinyal yok), `n_applicable`
   değişmedi.
8. **Rover profili olmayan ısıtıcı katsayısı için tek varsayım sabiti** (`HEATER_THERMOSTAT_ASSUMPTION_SOURCE`);
   kataloğa alan yazılmadı. `heater_model="none"` varsayılan.

### Ölçümler (Site11, coarsen 4; 5 Eylül 2026)

**Sonda–uygulama tutarlılığı:** LPR-1 gündüz rotası dilim 0'da küp: sınırsız **%3,2**, soğuk-sınırlı %96,0,
sıcak-sınırlı %0,8, sonlu dwell medyanı 0,547 h (sonda, soğuk-uç hedefle: %10,4 sınırsız, medyan 0,73 h —
küp yüzeyi 4,3 h ufukta zamanla değişen gölgeyle entegre eder, sonda statik denge okur). Ay gecesi 13 Eyl:
sınırsız %0,0, soğuk %100, medyan 0,547 h. VIPER kısa leg 30 May 2027: sınırsız %17,2, soğuk %73,2, sıcak %9,5,
medyan 0,622 h.

**Standart rotalar (kısıtsız, bit-eşit: 41 / 116 / 8 hamle):** rota boyunca iç sıcaklık izi (T₀ 17,5 °C,
ısıtıcı yok) — gündüz: min −15,7 °C, ilk zarf çıkışı **0,666 h**, 41 durumun 34'ü zarf dışı; gece: min −115,9 °C,
ilk çıkış 0,530 h, 117 durumun 109'u dışı; VIPER: min −49,5 °C, ilk çıkış 0,697 h, 9 durumun 7'si dışı.
D3'ün statik ihlali dinamikle "ne zaman" sorusuna dönüşüyor: her üç rota da ilk **yarım–bir saatte** zarfı
terk ediyor ve bir daha girmiyor (ısıtıcı sıcaklık modelinde olmadığı için).

**Kısıt (`require_thermal_dwell`):**

| Rota | `none` | `thermostat_assumed` |
|---|---|---|
| LPR-1 gündüz | **404**, 229 435 geçiş reddi (65 448 ufuk), 127 s | **200**, aynı 41 hamle, 0 bekleme, 35 848 düğüm (kısıtsız 31 219), iç min +5,1 °C, 40 s |
| LPR-1 Ay gecesi | **404**, 3 014 ret, 18,6 s ("site 9,7 h ufuk boyunca karanlık") | **200**, aynı 116 hamle, 171 117 düğüm (kısıtsızla aynı), iç min +0,6 °C, 109 s |
| VIPER kısa leg | **404**, 318 ret, 14,8 s | **200**, aynı 8 hamle, 1 635 düğüm (aynı), iç min +6,4 °C, 17 s |

Okuma: pasif modelde Site11'de hiçbir standart rota termal zarfı tutmuyor (D3 ile tutarlı, artık kısıt olarak
da); termostat varsayımıyla üç rota da değişmeden geçiyor — soğuk yan ısıtıcıya bırakıldığında sıcak yan
bağlayıcı değil. `/api/plan-4d` gündüz ucu: kısıtsız 17,5 s (ikinci çağrı; planlayıcı 5,6 s, küp 2,3 s
(m = 1) → 1,2 s (m = 2), yüzey serisi 0,8 s, gölge serisi 0,5 s, maliyet küpü 0,9 s; kalan A1/A2/A4/D3
blokları), ilk çağrı 31 s (önbellek ısınması). Rapor koşumunda (`scripts/thermal_dwell_report.py`, 8,8 dk):
gündüz `none` 404 57,5 s, termostat 200 10,4 s (planlayıcı), gece `none` 404 28,5 s, termostat 67,3 s
(planlayıcı; kısıtsız 58,1 s), VIPER 14,3 s / 0,9 s — süreler makine yüküyle ±2× oynuyor.

**Dwell küpü (rapor § 3, `DWELL_MAX_STATES` 1 M):** gündüz 937 500 durum (m = 2) 1,26 s; gece 843 750 (m = 5)
1,10 s; VIPER 671 875 (m = 1) 0,94 s. B1'in 10 h arıza beklemesi 12 h ufuklu katmanda blokların **%100 / %100 /
%84,1**'inde dwell'i aşıyor (LPR-1 gündüz / gece / VIPER) — B1'in DP'sine bağlanmadı (B1 spec'i), yalnız sayı.

**Zarf matrisi (rapor § 1):** LPR-1 = VIPER (aynı zarf ve ofsetler): `none` 19 sınırsız / 173 soğuk / 13 "sıcak"
/ 83 örneklenmedi; `thermostat_assumed` **192 sınırsız / 0 soğuk / 13 sıcak** — sıcak-sınırlı kutuların yüzeyi
−23,5…−0,4 °C (ofset artefaktı), en sıcak yüzey +44,5 °C (30° Güneş'e bakan, yükseklik 1,75–2,25°).

**Saplanma (rapor § 5, `/api/replan`):** Ay gecesi başlangıcı (186,34) termal bütçe 0,485 h (soğuk/batarya);
rota ortası (390,230; dilim 105, 03:46 UTC) 0,420 h; gündüz başlangıcı (358,494) 0,486 h. Termal seviyeler:
0,1 h ok, 0,25 h warning (~%51), 0,5 h fail. **Haven penceresi LPR-1 için her yerde 0 h** (A1: Site11'de
ulaşılabilir haven yok; gece başlangıcında Dünya bağlantısı da 0 h) → `overall` her saplanma süresinde `fail`,
sınırlayıcı `haven` — JSC'nin saati saplanmadan önce dolmuş sayılır; rapor bunu okuma notu olarak yazar.
Replan çağrısı 1,3–5 s (ilk çağrı 15 s).

**Site11 denge istatistiği (rapor § 2):** sonda 2 ile birebir (LPR-1 zarf içi %33,6 tepe / %10,4 soğuk uç; PSR
tabanına 15,9 dk; VIPER 17,7 dk; LUVMI-M %83,0 / %55,2, dwell hesaplanamaz). Standart rotalarda D3'ün statik
ρ'ları aynen (gündüz R04 −17,96 / R05 −27,96; VIPER R04 +9,23 / R05 −5,77 — 4-B izde blok-ortalama termal),
LP-R12 marjı 0,31 / 0,27 / 0,32 h (bekleme yok; bütçe − 0).

**Testler:** 41 birim + 13 API + 6 gerçek grid (7 dk 2 s: standart üç rota + blok 192 s, kısıt üç rotada 178 s);
D3'ün iki testi 12 gereksinime güncellendi. Tam paket: tam paket **1 502 passed, 5 skipped** (1 uyarı, **21 dk 25 s**; B1'deki 1 443 passed / 4 skipped'a C6'nın 60 testi eklendi — 59'u geçti, biri heat1d kuruluyken atlanır; skip'lerin ikisi D2'nin `LUNAPATH_PPB_DIR` klon testleri, ikisi önceden var; tek uyarı önceden var olan `test_visibility_validation`'ınki; B1'in kayıtlı 43 dk'sı yüklü makinedeydi, bu koşumda makine boştu).
