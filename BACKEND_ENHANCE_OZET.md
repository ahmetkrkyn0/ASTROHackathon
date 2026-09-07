# LunaPath backend genişletmesi — ekip bilgilendirme dosyası

**Dal:** `berke-3d-backendEnhance` · **Aralık:** `d401854..5173105` (12 commit) · **Tarih:** 3–6 Eylül 2026
**Kapsam:** yalnız backend, script'ler ve dokümanlar. Frontend koduna ve `berke-3d` dalına dokunulmadı.

Bu dosya, dalda yapılan on iki özelliğin tek noktadan özeti. Her bölüm kaynağını
gösterir: commit mesajı, ölçüm raporu, tasarım/plan belgesi, frontend veri sözleşmesi.
Sayıların hepsi Site11 penceresinde gerçekten koşturuldu; hiçbiri tahmin değil.
Nerede varsayım kullanıldıysa o satırda "varsayım" yazar.

---

## 1. Bir bakışta

| | |
|---|---|
| Commit | 12 (özellik başına tam olarak bir tane) |
| Değişen dosya | 157 · **+49 648 / −655** satır |
| Yeni backend modülü | 12 (`earth_visibility`, `safe_haven`, `stress_test`, `uncertainty`, `safety_monitor`, `illumination_corridor`, `risk`, `roughness`, `benchmark`, `survival`, `thermal_dwell`, `visibility_validation`) |
| Yeni API ucu | 13 (18 → 31) |
| Yeni test dosyası | 38 · Tam paket **1 502 geçti, 5 atlandı, 21 dk 25 s** |
| Yeni ölçüm raporu | 12 (`docs/research/*_report.md`) |
| Yeni tasarım + plan belgesi | 12 + 12 (`docs/superpowers/`) |
| Formal gereksinim | 11 → 12 (LP-R01 … LP-R12) |

### On iki özellik

| Kod | Ne | Dış kaynak | Kanıt türü | Commit |
|---|---|---|---|---|
| **A4** | Dünya görünürlüğü (DTE) katmanı, serisi, planlayıcı kuralı, iletişim penceresi | NASA PGDA ürün 69 (LOLA Average Earth Visibility) | Ölçülmüş ürünle RMSE | `0a749e9` |
| **A1** | Safe Haven haritası, time-to-haven katmanı, leg kuralı, SHERPA marjları | Shirley & Balaban 2022; Ennico-Smith vd. 2023 | NASA kuralı birebir | `51457d7` |
| **B5** | Monte Carlo traverse stres testi | SHERPA (Shirley & Balaban 2022; Balaban vd. 2025) | NASA protokolü birebir | `4e0dfae` |
| **B3** | DEM hata yayılımı, NASA'nın 100 Site11 klonu | PGDA ürün 78; Barker vd. 2021 | NASA hata ürünleri | `64acd65` |
| **D3** | FRETISH gereksinimler + STL robustness monitörü | NASA FRET; AIT RTAMT 0.3.5 | Formal yöntem (runtime monitoring) | `1991158` |
| **A2** | Sürekli-aydınlık (x, y, t) koridoru | Otten, Jones, Wettergreen, Whittaker (CMU) | Doğrulanmış yöntem | `a0f3782` |
| **C3** | Slip eğrisinin uçmuş veriyle çapalanması | Yutu-2 (Nat. Comms 2024); VIPER (PSJ 2025) | Uçmuş veri | `2597ef3` |
| **B2** | CVaR risk-farkında maliyet | Rockafellar & Uryasev 2000; JPL STEP; Endo vd. | Saha + ICRA sonuçları | `2a47e54` |
| **C4** | Ölçülmüş pürüzlülük (LOLA LDRM) + PSR maskesi | Barker vd. 2023; PGDA ürün 90 | Ölçülmüş katman | `4aae7c2` |
| **D2** | Dış benchmark MoonPlanBench koşumu | Chancán, Banerjee, Nikolakopoulos 2025 | Bağımsız benchmark | `8b0c5ad` |
| **B1** | Reach-avoid kurtarma politikası, P_fail ≤ β | Lamarre, Malhotra, Kelly (Toronto STARS) | Yayımlanmış formülasyon | `48ea152` |
| **C6** | Termal operasyon zarfı + tolere edilebilir saplanma süresi | NASA JSC/MSFC, ICES-2025-376 | NASA yöntemi | `5173105` |

### Dördü birden değişen omurga

Bu on iki özellik yalnız yeni modül eklemedi; üç merkezi yeri de değiştirdi:

- **Maliyet modeli** `COST_MODEL_ID` v3 → **v4** (C3, slip'siz enerji ölçeği) → **v5** (C4, beşinci kriter `f_roughness`). Her iki geçiş de Site11 gridlerinde SHA-256 ile kilitli; katman kaldırıldığında eski digest byte-byte geri geliyor.
- **4-B planlayıcı** `astar_4d` altı yeni kısıt taşıyor: DTE (A4), safe-haven leg (A1), sürekli aydınlık (A2), risk α (B2), şans kısıtı β (B1), termal zarf (C6). Hiçbiri istenmediğinde arama pre-özellik haliyle **bit-eşit** ve testle kilitli.
- **Enerji modeli** B5'te birleştirildi: `/api/plan`, `/api/plan-4d` ve Monte Carlo aynı `move_battery_drain_wh` aritmetiğini okuyor.

---

## 2. Ekiplere göre okuma yolu

| Ekip | Önce şunu oku | Neden |
|---|---|---|
| **Frontend** | Önce **§5.3 (ne çizilebilir)**, sonra `docs/frontend/3b-veri-sozlesmesi.md` (1 616 satır) | §5.3 her çıktının görsel karşılığını verir; sözleşme dosyası tel biçimini, başlıkları ve örnek JSON gövdelerini. |
| **ROS / entegrasyon** | `lunapath_ros/lunapath_ros/safety_monitor_node.py` + `docs/requirements/README.md` | D3 ile ROS tarafında telemetriden `ReplanTrigger` üreten formal monitör var. |
| **Sunum / rapor** | Bu dosyanın §7 (iddia sınırları) ve §9 (rakamlar) bölümleri + `docs/research/12_faktor_...md` §5 | Ne söylenebileceği ve söylenemeyeceği tablolanmış; her cümlenin arkasında ölçüm var. |
| **Veri / işleme** | `docs/research/*_report.md` + §6 (önbellekler) | Hangi NASA ürünü nereden, hangi lisansla, ne kadar sürede indiriliyor. |
| **Yeni katılan geliştirici** | `docs/superpowers/specs/*-design.md` | Her özelliğin tasarım kararları, reddedilen alternatifler ve sapmaları sonunda yazılı. |

---

## 3. Ortak kurallar (on iki özelliğin hepsinde geçerli)

1. **Etiket zinciri.** Her katman `MEASURED` / `DERIVED` / `MODEL` / `SYNTHETIC` etiketi taşır ve bir maliyet gridinin etiketi en zayıf girdisinin etiketidir (`weakest_validity`). C4 ölçülmüş bir katman ekledi ama maliyet etiketini yükseltmedi.
2. **Uydurma yok.** Bir girdi (çekirdek, önbellek, epok) yoksa alan üretilmez: yanıt `unavailable` ve gerekçesini döner. Sentetik bir yol varsa `SYNTHETIC` etiketiyle döner.
3. **Kaynaksız sayı katalogda yer almaz.** Aktarılan değerler `assumption:` ile başlayan kaynak dizesiyle işaretlenir (C3 slip çapaları, B1 arıza oranı α ve kurtarma süresi R, C6 termostat varsayımı).
4. **Alıntı ile ölçüm karışmaz.** Makalelerin kendi sayıları ayrı sabitlerde tutulur (`JSC_QUOTED`, `LAMARRE_QUOTED`, `PAPER_TABLE_1`) ve bizim ölçümümüzle aynı tabloya konmaz.
5. **Kısıt istenmediğinde bit-eşitlik.** Yeni her planlayıcı kısıtı kapalıyken aramanın aynı düğümleri açtığı testle kilitlenmiştir.
6. **Her özellik dört yerde kayıtlı:** commit mesajı, ölçüm raporu, tasarım + plan belgesi, frontend sözleşmesi eki (D2 hariç — API yüzeyi yok).

---

## 4. On iki özellik — ayrıntı

### A4 — Dünya görünürlüğü (DTE) katmanı · `0a749e9`

**Sorun.** VIPER yalnız doğrudan Dünya bağlantısıyla sürer. LunaPath Güneş'i ayrıntılı modelliyor, Dünya'yı hiç modellemiyordu; `check_comm_window` girdisini dışarıdan bekliyordu.

**Yapılan.** Güneş'in boru hattı (SPICE vektörü → yerel az/el → grid azimutu → arazi ufku) Dünya için de koşuyor. `app/earth_visibility.py`: dilim başına görünürlük serisi, uzun-dönem oran katmanı ve `comm_window` — ileri arama ile `comm_minutes_remaining` hesaplanan bir sayıya dönüştü (link yokken 0; VIPER linksiz sürmez).

**API.** `GET /api/earth-series`, `GET /api/comm-window`, `/api/terrain` ve `/api/layers` içinde `earth_visibility` katmanı; `POST /api/plan-4d` `require_earth_visibility` (linki olmayan bir hücreye varan her HAMLEyi reddeder, bekleme kısıtlanmaz), `path_earth_visible`, `metrics.moves_out_of_earth_view`; `/api/replan` ve `/api/pose` iletişim penceresini geometriden doldurur.

**Site11'de ölçülen.** 163 162 örnek, ürünün kendi 60 m çözünürlüğünde karşılaştırma: **RMSE 0,087, Pearson r 0,960**, 0,5 eşiğinde uyuşmazlık %9,4 (1 681 hücre). Projenin ölçülmüş bir ürüne bağlanan ilk modellenmiş katmanı.

**Bu doğrulama iki eski hatayı buldu.** (1) İlk koşum RMSE 0,665 ve r −0,16 verdi: işlenmiş gridler yanlış DEM penceresinden üretilmişti, pencere merkezi ve kuzey dönüşü 40 km kaymıştı — Site11 DEM'i yeniden indirildi, P1 hattı yeniden koşuldu, `metadata.json` byte-eşit çıktı. (2) 10 km ışın menzili uzak ufku kesiyordu; krater kenarından ufuk 10 km içinde 20° düşüyor ve karşı duvar hiç görülmüyordu. `build_horizon_cache.py` artık LOLA'nın 40 m kutup DEM'ini 10–150 km arasında da tarıyor: uzak alan (azimut, hücre) çiftlerinin **%27,5'inde ufku ortalama 4,2° yükseltti**, ışıklı oran zirvesi ~%47'ye ve terminatör tarihleri kaydı.

**İddia sınırı.** "Dünya görünürlüğü katmanımız LOLA ürünüyle doğrulandı" denebilir; sayı RMSE 0,087'dir.

**Dosyalar.** `app/earth_visibility.py`, `app/visibility_validation.py` · `scripts/build_earth_visibility_cache.py`, `scripts/earth_visibility_validation.py` · rapor `docs/research/earth_visibility_validation.md` · sözleşme eki "Dünya görünürlüğü — DTE katmanı" (satır ~322) · spec/plan `2026-09-03-a4-dte-katmani*`.

---

### A1 — Safe Haven, time-to-haven ve leg kuralı · `51457d7`

**Sorun.** VIPER'ın seyri bacaklardan oluşur ve her bacak bir Safe Haven'da biter: Dünya ufkun altındayken rover komut alamaz, o yüzden kendi başına hayatta kalacağı yerde park etmiş olmalıdır. LunaPath'te statik bir gölge-oranı haven kümesi ve kullanılmayan bir "50 saat" sayısı vardı.

**Yapılan.** NASA'nın tanımı birebir: **Dünya aşağıdayken sürekli gölge ≤ `h_max_shadow_h`** (LPR-1 50 h, NASA VIPER 96 h, LUVMI-M 4 h, Yutu-2 2 h), pencerede en az bir kez ışıklı, geçilebilir. `app/safe_haven.py` bu sayımı bir sinodik ay boyunca SHERPA'nın 2 saatlik kadansında yapar; `time_to_safe_haven_hours` en yakın haven'a **sürüş saatini** planlayıcının kendi kapılı grafiği üzerinde çok-kaynaklı Dijkstra ile verir; `hours_until_earthset_cube` plan ufkunun 14 gün ötesine bakar; `route_margins` SHERPA'nın time-to-sun-shadow / time-to-DSN-shadow / time-to-0-SOC marjlarını hesaplar.

**API.** `GET /api/safe-haven` (manifest + dört ikili katman), `GET /api/cell-telemetry?start_utc=` (hücrenin kararı ve en yakın haven'a süresi), `POST /api/plan-4d` `require_safe_haven` — başlangıç ve her BEKLEME dahil her durumda `time_to_haven ≤ kalan Dünya linki saati`; `path_time_to_haven_h`, `path_hours_until_earthset`, `path_haven_margin_h`, `metrics.min_haven_margin_h`, `ends_at_safe_haven`.

**Site11'de ölçülen (2026-09-07'den 13 sinodik ay).** Dünya linksiz iki hafta, bütün sahayı ~6,5 gün karartan ay gecesiyle çakışıyor; NASA'nın dediği gibi haven'lar seyrek: **en kısa linksiz karanlık ay gününe göre 40–186 saat**. LPR-1 (50 h) yalnız Kasım 2026'da ~40 hücre bulur, başka ayda hiç; NASA VIPER (96 h) 2027-05-30 ay gününde **%11'e** çıkar (22 837 hücre, en yakın haven'a medyan 2,2 saat, geçilebilir hücrelerin %99'u bir haven'a ulaşabiliyor); LUVMI-M ve Yutu-2 hiçbir zaman uygun değil. Sahanın %1'i / %10'u için gereken dayanım ay gününe göre 64–232 h / 82–298 h. Kural altında iki haven arası VIPER planı 8,4 s'de 200 saatlik marjla dönüyor.

**İddia sınırı.** "VIPER ile aynı safe-haven ve 50 saat kuralını uyguluyoruz" denebilir.

**Dosyalar.** `app/safe_haven.py` · `scripts/safe_haven_report.py` · rapor `docs/research/safe_haven_report.md` · sözleşme eki "Safe Haven — VIPER'ın leg kuralı" (~436) · spec/plan `2026-09-04-a1-safe-haven*` · 60 yeni test.

---

### B5 — SHERPA Monte Carlo stres testi · `4e0dfae`

**Sorun.** VIPER'ın planlama ekibi bir planı bir kez uygulanabilir diye kabul etmez: SHERPA her stratejik planı binlerce kez, kesilmiş Gauss dağılımlarına karşı koşturur. LunaPath'te tek bir deterministik simülasyon vardı.

**Yapılan.** Protokol aynı parametrelerle uygulandı: başlangıç zamanı σ 2 h (yalnız geç), başlangıç bataryası %20 (yalnız düşük), güç çekişi %20 (yalnız yüksek), etkin hız %20/30/40/50 (yalnız yavaş), olasılıkla DSN kesintisi ve SEP olayı; operatör politikası — programın önündeyse bekle, gerideyse şarj molalarını atla ve gölgede bataryayla sür. Çıktı bir dağılım: tamamlama, time-to-sun-shadow, time-to-DSN-shadow, time-to-0-SOC.

**Önce kapatılan önkoşul.** `simulate_path` artık sürerken paneli kredilendiriyor; batarya `cost_engine`'in işaretli `move_battery_drain_wh` değerini izliyor, yani `/api/plan`, `/api/plan-4d` ve Monte Carlo **tek enerji modeli** paylaşıyor.

**API.** `POST /api/stress-test` — bir plan-4d rotası × `n_runs` (varsayılan 1 000), parametre başına override, etiket. Uç nokta 1,0–2,4 s.

**Site11'de ölçülen (1 000 koşum, seed 0).** VIPER'ın haven-haven rotası, 2027-05-30 ay günü (40 hamle, 7,4 h, planın min bataryası %32): SHERPA'nın %20 hız σ'sında hedefe varış **%29,6** (%95 GA 26,9–32,5), σ %50'de %15,8; **her başarısızlık batarya tükenmesi**; koşumların yalnız %1,4'ü bütün marjlar sağlam bitiyor. Rota tamamen gölgede bataryayla sürülüyor ve planlayıcının tek marjı %20 rezerv. LPR-1'in 2,2 saatlik rotası (2026-09-28) her σ'da **%100** tamamlanıyor (GA 99,6–100, p5 min batarya %46–52); tam başarı sıfır, çünkü o ay gününde LPR-1'in haven'ı yok (A1) — karar metni bunu söylüyor.

**Bu koşumun bulduğu planlayıcı açığı.** `astar_4d` saati `ceil(travel / slice)` dilim ilerletiyor ama bataryayı yalnız sürüş süresi için düşüyor; Monte Carlo'nun nominal koşumu kalan süreyi housekeeping gücünde tutunca VIPER rotasının min bataryası %32 değil **%23** çıkıyor. Burada değiştirilmedi, planlayıcı takibi olarak spec'e yazıldı — **hâlâ açık.**

**İddia sınırı.** "NASA'nın stres-test protokolünü aynı parametrelerle uyguluyoruz" denebilir; "rotamız güvenli" denemez — VIPER rotası koşumların %70'inde bataryadan düşüyor.

**Dosyalar.** `app/stress_test.py` · `scripts/stress_test_report.py` · rapor `docs/research/stress_test_report.md` · sözleşme eki "Monte Carlo stres testi" (~537) · spec/plan `2026-09-04-b5-stress-test*` · 69 yeni test.

---

### B3 — DEM belirsizliği: NASA'nın 100 klonu · `64acd65`

**Sorun.** LunaPath'in her katmanı tek bir yükseklik modelinden türüyordu: tek eğim, tek ufuk, tek gölge, hata çubuğu yok.

**Yapılan.** NASA GSFC her 5 m/px güney kutbu DEM'i için Z-belirsizliği (`toterr`), eğim belirsizliği (`slperr`) ve **100 istatistiksel klon** yayımlıyor (PGDA 78). Site11'in klonları planlama penceresi için indirildi ve her biri LunaPath'in **kendi türetme zincirinden** geçirildi: hattın eğim operatörü, planlayıcının geçilebilirlik kuralı, ufuk taramacısı, B5'in enerji aritmetiği. Çıktı hücre başına olasılık, dilim başına olasılık ve rota başına bant — NASA-STD-7009'un istediği girdi soyağacıyla.

**Önce bulgu.** `_err.tif` klonları hata alanı değil, **tam yüzey DEM'i** (pencerede 528–955 m, yüzeyle korelasyon 1,0000). Hata gerçeklemesi `klon − yüzey` ve RMS'i NASA'nın kendi `toterr` RMS'ine eşit (0,449 m), uzamsal korelasyon 5 m'de 0,88, 100 m'de yok. 100 klonun her biri saklanmadan önce bu kontrolden geçiyor.

**API (yalnız eklemeler; önbellek yoksa hiçbiri görünmez).** `p_traversable`, `slope_sigma` (DERIVED), `elevation_sigma`, `slope_sigma_nasa` (MODEL — NASA'nın hata modeli, ölçüm değil) katmanları + `dem_uncertainty` soyağacı bloğu; `GET /api/uncertainty-series`; `POST /api/dem-uncertainty`; `/api/plan` ve `/api/plan-4d` üzerinde `uncertainty` bloğu.

**Site11'de ölçülen (100 klon).** Eğim σ: bizimki medyan **1,52°**, NASA `slperr` 1,73° (oran 0,88, hücre korelasyonu 0,42). Klon eğimleri yüzeyinkinin sistematik olarak üstünde (medyan +0,16°): sıfır ortalamalı yükseklik gürültüsü gradyanı şişirir, yani **en iyi tahmin DEM'i hepsinin en düzüdür**. `p_traversable`: VIPER'ın 20° limiti için hücrelerin **%8,2'si belirsiz** (LPR-1'in 25°'si için %2,8); %0,9'u yüzey DEM'inde geçilebilir görünüp P < 0,5. Yakınsama: ortalama |P₂₀ − P₁₀₀| 0,007. `p_illuminated` (2027-05-30): hücrelerin **%10,8'i** ışıklı ya da karanlık denemiyor. VIPER rotası: sürüş enerjisi p5/p50/p95 **2 258 / 2 293 / 2 334 Wh**, yüzey DEM'inde 2 127 Wh — bant planın %6–10 üstünde; rota planlayıcının blok-AND kuralı altında 100 klonun **1'inde** geçilebilir kalıyor; SHERPA klonlar üzerinde havuzlanınca tamamlama %29,6 → **%17,8**. LPR-1: 538/546/556 Wh (yüzey 506), 99/100 klonda geçilebilir, %100 tamamlama.

**Sabit tutulan ve her yanıtta söylenen.** Termal alan, 1 km ötesindeki uzak ufuk, Dünya linki ve safe-haven alanları klonlarla oynatılmadı.

**İddia sınırı.** "Belirsizlik nicelenmiştir; enerji tüketimi %90 güven bandıyla veriliyor" denebilir.

**Dosyalar.** `app/uncertainty.py` · `scripts/build_dem_clone_cache.py`, `scripts/dem_uncertainty_report.py` · rapor `docs/research/dem_uncertainty_report.md` · sözleşme eki "DEM belirsizliği" (~603) · spec/plan `2026-09-04-b3-dem-uncertainty*` · 47 yeni test.

---

### D3 — FRETISH gereksinimler + STL robustness monitörü · `1991158`

**Sorun.** Kısıt denetimi ikiliydi: `check_profile_constraints` marjsız "satisfied: true" diyor, `replan_triggers` eşik karşılaştırıyor ve hiçbiri — planlayıcılar da — termal zarfa bakmıyordu.

**Yapılan.** On bir güvenlik ve görev gereksinimi **FRETISH**'te yazıldı (NASA FRET'in yapılandırılmış doğal dili: `[scope] [condition] the rover shall [timing] [response]`); FRET aracının kendisi kurulmadı, cümleler grameri elle izliyor ve dosya bunu söylüyor. Her biri elle **STL**'e çevrildi, eşiği rover kataloğundan okunuyor ve her planlanan rota **space robustness** ile denetleniyor: gereksinim başına ρ, saat / °C / yüzde puanı / derece / metre biriminde, marjın en küçük olduğu yer ve bir karar.

**İki motor, her istekte çapraz kontrol.** AIT'nin RTAMT 0.3.5'i (ayrık zamanlı çevrimdışı STL) ve aynı semantikli yerleşik değerlendirici. RTAMT'nin sonlu-iz kuralları ölçülüp testlere sabitlendi. Zaman pencereli davranış türetilmiş saat sayaçlarına katlandı, böylece her formül sınırsız bir G/F ve robustness'ı örnekleme adımından bağımsız.

**API (yalnız eklemeler).** `safety_margins` bloğu `/api/plan`, `/api/plan-4d` ve simüle edilen her `/api/compare` ile `/api/plan-multi` sonucunda; `comparison.safety_margin_ranking`; `POST /api/safety-check` (telemetri izi; zamanın geri gitmesi, NaN, bilinmeyen motor ya da paketsiz `engine=rtamt` için 422 — sessiz geri düşüş yok). Monitör hatası loglanır ve blok atlanır; **bir planı asla düşürmez**. ROS tarafında `safety_monitor_node.py` telemetriden ihlal başına bir `ReplanTrigger` üretir (`trigger_id "safety:LP-R02"`).

**Site11'de ölçülen.** İki motor gerçek rotalarda bit düzeyinde aynı (çapraz kontrol 0), 20 rastgele iz × 6 formül ailesinde 1e-9'a kadar. VIPER haven-haven, 2027-05-30 (41 durum, 7,36 h): gölge marjı 91,45 h, SOC 12,06 pp, adım eğimi **0,48°** (rota limite yapışıyor, B3'ün bulduğu gibi), yanal eğim 1,19°, Dünya linki 199,93 h, haven marjı 199,80 h. **LP-R04 ve LP-R05 İHLAL:** iç sıcaklık −7,96 °C (elektronik zarfı −20…50) ve −27,96 °C (batarya zarfı 0…35), durum 16, hücre (73,118). Statik `sunlit_peak` termal katmanı artı `surface_to_inner` ofsetleri bataryayı zarfının 28 K altına koyuyor; ısıtıcı gücü enerji modelinde ücretlendiriliyor ama sıcaklık modelinde hiçbir şey ısıtmıyor ve mevcut hiçbir denetim buraya bakmamıştı. **Yumuşatılmadan raporlandı — C6'nın girdisi oldu.** LPR-1, 2026-09-28: gölge 49,79 h, SOC 76,16 pp, termal −17,96 / −27,96 °C ve haven leg kuralı sınırsız ihlal (link 184,6 saat sonra bitiyor, o ay günü ulaşılabilir haven yok). SHERPA'nın bozulmaları altında (1 000 koşum) VIPER'ın SOC marjı plandaki 12,1 pp'den p5/p50/p95 **−20,0 / −20,0 / −4,9 pp**'ye düşüyor (rezerv koşumların %98,6'sında delinmiş). `/api/compare` dört profilde batarya termali −46,04 °C gösterirken ikili `constraint_check` dördü için de "satisfied" diyor.

**Maliyet.** Plan içinde milisaniye; `/api/safety-check` 500 örnekle 12–15 ms (yerleşik), 28–48 ms (RTAMT).

**İddia sınırı.** "Gereksinimler FRETISH'te yazıldı, STL'e çevrildi ve her rota **runtime monitoring** ile nicel marjla denetleniyor" doğru. "FRET aracıyla üretildi" ve "model checking ile ispatlandı" **yanlış** — yalnız somut izler denetleniyor. Her yanıt bu sınırı `safety_margins.monitor.claim` alanında tekrarlar.

**Dosyalar.** `app/safety_monitor.py`, `lunapath_ros/.../safety_monitor_node.py` · `scripts/export_fret_requirements.py`, `scripts/safety_monitor_report.py` · `docs/requirements/README.md` + `lunapath.fret.json` (katalogla eşitliği testle kilitli) · rapor `docs/research/safety_monitor_report.md` · sözleşme eki "Formal güvenlik marjları" (~712) · spec/plan `2026-09-04-d3-formal-safety*` · 81 yeni test.

---

### A2 — Sürekli-aydınlık koridoru · `a0f3782`

**Sorun.** 4-B planlayıcı yalnız uzamsal bileşeni denetliyor ve küpü zamanda baştan sona arıyordu.

**Yapılan.** CMU (Otten, Jones, Wettergreen, Whittaker; ICRA 2015 / FSR 2017) kutup rotalarını bir (t, y, x) hacmi içinde planlar: aydınlanma serisi × eğim maskesi, 26-komşulukta taşma doldurma, iki budama geçişi (ileri: ilk dilimin ulaşamadığı kökleri at; geri: son dilime hiç ulaşmayan çıkmazları at), sonra hayatta kalanın içinde A*. Bu koridor planlayıcının **kendi kaba gridi ve kenarları** üzerinde kuruluyor: aynı geçilebilirlik, köşe, adım-eğimi ve yanal-eğim kapıları; sürüş süresi planlayıcının kendi işlem sırasında yeniden hesaplanıyor. Bir hamle `(r,c,t)→(r',c',t+d)` ancak **iki blok da t…t+d aralığındaki her dilimde ışıklı ve geçilebilirse** koridor kenarı. "Işıklı"nın anlamı istekte seçilir: `lit_rule="all"` (bloğun her ince hücresi ışıklı, varsayılan) ya da `"majority"` (blok ortalaması gölge < 0,5).

**API.** `require_continuous_illumination` + `lit_rule`; her `/api/plan-4d` yanıtında `illumination_corridor` bloğu (voksel sayısı, budanan oran, bileşenler, başlangıç/hedef durumu, rotanın içeride olup olmadığı, dwell fırsatları, soyağacı); `metrics.max_dwell_hours`; `GET /api/illumination-corridor` (f32 küp ya da JSON manifest); statik gölge serisinde zorlanırsa 422; kural rotayı kapatırsa 404 detayında koridorun sayıları.

**Site11'de ölçülen.** VIPER 2027-05-30, varsayılan 9,6 saatlik ufuk (100 × 0,0956 h, 320 m'de 125×125): geçilebilir hacmin **%40,5'i** ışıklı-ve-güvenli ("all"; "majority" ile %45,8); iki geçiş yalnız **%0,2** buduyor — kutup aydınlanması 10 saatte neredeyse durağan, CMU'nun budaması 59 günlük pencerelerde ısırır. 50 bağlı bileşen, en büyüğü %91. Standart haven-haven çifti güneş-senkron değil: başlangıç bloğu ilk dilimde karanlık, hedef bloğu hiç ışıklı olmuyor, rota 4,55 saat gölgede — kural onu sayılarla reddediyor. Koridor içi bir çift (62 blok, 8 h): `path_dark_hours` boyunca 0, LP-R01 ρ = 96,00 h = rover'ın tam dayanımı, 62 hamle / 0 bekleme, 7,90 h, min SOC %93,6. Planlama: kısıtsız 452 ms / 7 233 düğüm, koridor 417 ms / 6 467 düğüm (×1,08 süre) — **mütevazı ve öyle raporlandı**; maliyet küpü gölgeyi zaten fiyatladığı için kısıtsız rota da içeride kalıyor. "22 s → X s" gibi bir hızlanma iddiası yok. LPR-1 2026-09-28: 2,9 saatlik ufukta yalnız %4,8 ışıklı, 8 saatte koridor hiç yok; ay gecesi 2026-09-13: hiçbir blok ışıklı değil, 404 "246 dilimin hiçbirinde ışıklı blok yok".

**Koridor kurulum maliyeti.** 100 dilimde 135 ms ("all"), 246 dilimde ~0,3 s. İlk sürüm zaman ekseninde fancy index kullanıyordu (591 ms / 1,7 s); dilim başına dilimleme ×10 hızlı ve voksel-voksel aynı (iki yol da korunup çapraz kontrol ediliyor).

**İddia sınırı.** İddia MODEL hakkında (SPICE Güneş + ufuk küpü, 320 m bloklar, örneklenmiş dilimler) ve B3'ün bulgusu yanında taşınıyor: 2027-05-30'da hücrelerin %10,8'i klonlar arasında ışıklı/karanlık kararsız. "Gerçek yüzey rover'ı hiç gölgelemez" denmiyor.

**Dosyalar.** `app/illumination_corridor.py` · `scripts/illumination_corridor_report.py` · rapor `docs/research/illumination_corridor_report.md` · sözleşme eki "Sürekli-aydınlık koridoru" (~815) · spec/plan `2026-09-04-a2-illumination-corridor*` · 82 yeni test.

---

### C3 — Slip eğrisinin uçmuş veriyle çapalanması · `2597ef3`

**Sorun.** `slip_model.py` bir yön iddiası taşıyor ama büyüklük vermeyi reddediyordu: üsteli kaba bir tahmindi, kendini `UNCALIBRATED` etiketliyordu ve **bilerek hiçbir ürün onu çağırmıyordu**. Sonuç: her süre ve enerji rakamı sistematik olarak iyimserdi (B5 VIPER rotasını nominalde %23'e düşürmüştü, B3 sürüş enerjisini %6–10 düşük bulmuştu).

**Yapılan — önce kaynaklar, sonra kablolama.** Eğri artık yalnız kaynaklı çapalardan geçiyor. **VIPER:** "mobilite tasarım gereksinimleri maksimum 15° eğimde maksimum %40 slip tanımladı" (PSJ 2025 §3.5; GRC-1 benzeşiği, MGRU, Optitrack — bir **üst sınır**, tipik değer değil). **Yutu-2:** Chang'e-4 sahasında 8,86°'ye kadar eğimlerde "slip oranlarının çoğu 0 ile −0,075 arasında" (Nature Communications 2024): 0° → 0,0375 ± 0,01875, 8,86° → 0,075. Çapalar arası ve son çapanın ötesinde log-lineer (gevşek zeminde slip eğrilerinin gösterdiği dışbükey biçim — **varsayım, etiketli**), 0,9'da tavan, |eğim|'de simetrik. Her `SlipAnchor` zorunlu bir kaynak taşır; profiller arası aktarımlar `assumption:` ile başlar (LPR-1 ve LUVMI-M tamamen; VIPER'ın düz zemin noktası Yutu-2'den; Yutu-2'nin 8,86° noktası **aktarılmadı** — mare regoliti ile gevşek GRC-1 farklı zeminler). Etiket `UNCALIBRATED` → **`MODEL`**, asla `MEASURED`: burada hiçbir şey kutup regolitinde ölçülmedi.

**Tek bağlanma noktası.** `cost_engine.edge_travel_time_s` komut mesafesini tekerlek mesafesine çeviriyor: `d / (1 − slip(eğim, rover))`. Süre ve enerji birlikte büyüyor; 2-B ve 4-B planlayıcılar, simülatör, koridor bütçeleri, Monte Carlo bacakları, safe-haven mesafeleri ve `auto_slice_hours` aynı sayıyı okuyor. Vektörize ikiz aynı işlem sırasında yazıldı ve skalerle **bit-eşit** (bu platformda 0 ulp, profil başına 100 000 rastgele kenarda test edildi).

**İki sonuç ele alınmak zorunda kaldı.** (1) Enerji kriterinin ölçeği slip'siz en iyi/en kötü çifti olarak kaldı: slip dahil en kötü hücreye (25°'de slip 0,9, slip'siz sürenin on katı) göre normalize etmek her sıradan hücreyi [0, 0,15]'e sıkıştırıyordu — ölçüldü: LPR-1'in karanlık 10° hücresi 0,58'den 0,07'ye düştü. `COST_MODEL_ID` → **v4**. (2) Varsayılan 4-B ufku artık en hızlı kapılı rotadan boyutlanıyor (Dijkstra): eski "BFS hamleleri × en yavaş kenar" sınırı slip altında taşıyordu — 113 hamlelik ay gecesi rotası onunla 1 602 dilim istiyordu, bununla **270**.

**API (yalnız eklemeler).** `/api/rovers` her rover'da `slip_model` (etiket, kaynaklı çapalar, 0–25° tablo, referanslar) ve `declared_only.regolith` (Yutu-2'nin ölçülmüş Bekker aralıkları, VIPER'ın GRC-1 test yatağı — hiçbir şey okumuyor, Bekker denklemi kodlanmadı); `/api/plan`, `/api/plan-4d`, `/api/compare`, `/api/plan-multi` sonuçlarında `slip_model` bloğu (ortalama/maks slip, mesafe çarpanı, slip'in bu rotaya eklediği saat ve Wh).

**Site11'de ölçülen.** Eğri 0/5/10/15/20/25°: **0,037 / 0,083 / 0,182 / 0,400 / 0,881 / 0,900** (süre ve enerji ×1,04 / 1,09 / 1,22 / 1,67 / 8,4 / 10). Site11 dik: ince eğim medyanı ~10°, kaba blok p95 19–22°. LPR-1 2026-09-28: varış **2,16 → 2,98 h (×1,38)**, min SOC %96,2 → %92,5, rota ortalama slip 0,326 (maks 0,537), slip'in eklediği 0,75 h / 321 Wh. Ay gecesi: 5,35 → 6,75 h. 2-B enerji: LPR-1 469 → 597 Wh (×1,27), gece 1 288 → 1 466 Wh, VIPER 2 156 → **2 742 Wh** (×1,27). **VIPER'ın standart haven-haven bacağı eğri altında reddediliyor** (404: 283 148 kenar bataryayı %20 rezervin altına düşürürdü). Slip'siz plan zaten %32'de bitiyordu ve B5 koşumların yalnız %1,4'ünü rezerv içinde bulmuştu: modelin dürüst kararı, bir arıza değil. En yakın uygulanabilir bacak (358,494)→(346,462): 8 hamle, 1,53 → 2,23 h (×1,46), min SOC %85,4 → %72,3, haven'da bitiyor. Planlayıcı slip'li maliyet yüzeyinde 2,6–2,8× daha fazla düğüm açıyor (LPR-1 8 799 → 23 177).

**İddia sınırı.** "Slip modelimiz uçmuş veriye **bağlandı**" denebilir; "**ölçüldü**" denemez — LunaPath saha verisi üretmiyor ve kutup regolitinde ölçüm yok.

**Dosyalar.** `app/slip_model.py`, `app/cost_engine.py`, `app/cost_vec.py` · `scripts/slip_calibration_report.py` · rapor `docs/research/slip_calibration_report.md` (öncesi/sonrası) · sözleşme eki "Slip modeli" (~916) · spec/plan `2026-09-04-c3-slip-calibration*` · 82 yeni/uyarlanan test.

---

### B2 — CVaR risk-farkında maliyet · `2a47e54`

**Sorun.** Bir hücrenin maliyeti tek sayıydı: DEM'in en iyi tahmin eğiminde slip eğrisinin ortalaması. Oysa iki girdinin de artık yayılımı var — C3 her slip çapasına σ koydu, B3 NASA'nın 100 klonundan hücre başına eğim σ'sı verdi.

**Yapılan.** Operatör isterse ortalamayla değil, dağılımların **en kötü (1 − α) kuyruğunun ortalamasıyla** sıralayabiliyor: Koşullu Riske Maruz Değer, normal için kapalı formda `μ + σ·φ(z_α)/(1 − α)` (Rockafellar & Uryasev 2000). Fikir JPL'in STEP'i (Fan vd., RSS 2021; DARPA SubT'de sahada) ve Keio'dan Endo vd. (ICRA 2023).

**α nereye giriyor, nereye girmiyor.** `risk_alpha ∈ [0,5, 0,999]` isteğe bağlı ve yalnız **sıralama maliyetini** değiştiriyor: enerji kriteri hücreyi `min(0.9, CVaR_α(slip))` ile fiyatlıyor (σ_total² = σ_slip² + (k·s·σ_slope)², eğim σ'sı slip'e delta yöntemiyle taşınıyor), eğim kriterinin sigmoidi `min(slope_max, slope + σ_slope·m_α)` okuyor — ama **geçilemezlik kapısı nominal eğimde kalıyor**, yani geçilebilirlik asla α'ya bağlı değil. Sürüş süresi, batarya, formal marjlar, koridor bütçeleri ve Monte Carlo ortalamayı kullanmayı sürdürüyor: α'yı fiziğe koymak nominal saati bir tercihe bağlar ve B5'in kendi hız/güç dağılımlarını iki kez sayardı (tasarım alternatifi, reddedildi). `risk_alpha` verilmezse grid **bit-eşit**: `COST_MODEL_ID` v4'te kalıyor ve Site11 gridleri B2 öncesi SHA-256'larına kilitli. **α = 0,5 ortalama değildir** (μ + 0,798σ) ve bunu her yanıt söylüyor.

**Termal kuyruk reddediyor.** `risk.thermal_cvar_cold_c` bir kanca ve çalışmıyor: termal alanın yayımlanmış σ'sı yok, üstelik ölçüldü — `f_thermal` LPR-1'in geçilebilir hücrelerinin %72,7'sinde, VIPER'ınkilerin %54,2'sinde zaten doyuyor; α 0,9'da range/4 soğuk kuyruk bunu %94,0 / %81,2'ye çıkarıyor: daha çok doyma, daha iyi sıralama değil.

**API.** `risk_alpha` `/api/plan` ve `/api/plan-4d` isteklerinde (aralık dışı 422); her iki yanıtta `risk` bloğu (α, uygulanıp uygulanmadığı, MODEL etiketi, ölçü, çarpan, kapsam, kriter başına etki, slip ve eğim için σ kaynakları, rotanın CVaR slip'i ve risk-ayarlı saat/Wh, iddia); `POST /api/risk-sweep` aynı çifti nominal ve birkaç α'da yan yana planlıyor, nominal fizikle özetliyor, nominal rotayla hücre örtüşmesini ve bir **risk matrisi** (her rota her α'da yeniden fiyatlanmış) veriyor.

**Site11'de ölçülen (100 klon).** Eğim σ medyan 1,54° (p95 1,99). α = 0,99'da CVaR slip medyanı 0,199 → **0,497**, geçilebilir hücrelerin %26,6'sı 0,9 tavanında; α-sıralı maliyet gridi nominalle Spearman **0,985** (LPR-1) / 0,970 (VIPER) tutuyor. 2-B süpürme: α 0,99 rotası nominal rotayla %49–52 örtüşüyor ve nominal fizikteki kazanç küçük — LPR-1 gündüz 597,2 → 592,7 Wh; ay gecesi çifti 1 465,7 → **1 439,5 Wh (−%1,8)**, min SOC +0,39 puan; VIPER standart 2 741,8 → 2 713,0 Wh. **Risk matrisi dört çiftin ikisinde NOMİNAL rotayı kuyrukta daha ucuz buluyor** (LPR-1 gündüz α 0,99'da 3,375 h'e karşı 3,696 h): ağırlıklı kriterler kuyruk süresini minimize etmiyor — dürüst bir sonuç ve öyle raporlandı. 4-B'de LPR-1 her α'da aynı 42 hamleli rotayı seçiyor, varış 2,979 h değişmiyor, ortalama slip 0,326 → 0,313.

**İddia sınırı.** MODEL etiketli dağılımların CVaR'ı, **ölçülmüş bir risk değil**: slip σ'sı Yutu-2'nin aralığının ±2σ okunması ve 0,5'lik aktarılmış göreli yayılım (varsayımlar, her çapanın kaynağında yazılı), eğim σ'sı NASA klonlarından DERIVED, termal σ yok. Endo vd.'nin "%11 → %95 başarı" sonucu **onların sentetik sonucu**; alıntılanıyor, tekrarlanmıyor.

**Dosyalar.** `app/risk.py` · `scripts/risk_sweep_report.py` · rapor `docs/research/risk_sweep_report.md` · sözleşme eki "Risk iştahı" (~1023) · spec/plan `2026-09-05-b2-cvar-risk-cost*` · 74 yeni test.

---

### C4 — Ölçülmüş pürüzlülük + PSR maskesi · `4aae7c2`

**Sorun.** Şimdiye kadar tek `MEASURED` katman yükseklikti; her şey ondan türüyor ya da modelleniyordu ve yüzeyin pürüzlülüğü — 5 m'lik bir DEM'in gösteremediği kayaların istatistiksel vekili — hiçbir yerde yoktu.

**Yapılan.** NASA GSFC'nin güney kutbu yayını (Barker vd. 2023, PSJ 4:183; PGDA ürün 90) LOLA noktalarının kendisinden hesaplanmış çok-tabanlı pürüzlülüğü ve PSR'lerin 20 m/px haritasını yayımlıyor. C4 ikisini de planlama penceresine ko-registre ediyor: **100 m tabanlı pürüzlülük (50 m/px) ağırlıklı toplama beşinci kriter `f_roughness` olarak giriyor**; PSR maskesi bir katman, hücre kartı alanı ve kendi gölge modelimizin doğrulaması oluyor — planlama girdisi değil.

**Ko-registrasyon, yazmadan önce iki kontrol.** Ürünlerin projeksiyon **parametreleri** grid'inkine eşit mi (adlar farklı: "unnamed" ile "Moon (2015) - Sphere / Ocentric / South Polar") ve NASA'nın kendi 100 m düzlem-uyum eğimi bizim 5 m eğimimizin blok ortalamasıyla aynı sıralanıyor mu (2 500 blokta **Spearman 0,989**; 0,9'un altında yazmayı reddediyor). Grid'in kendi dönüşümüne `nearest` ile örnekleniyor — metadata orijininin hücre (0,0)'ın **sol üst köşesi** olduğu Site11 TIF'ine karşı doğrulandı; A4'ün yardımcısı hücre merkezi varsayıyordu, iki ürün için de 2,5 m alt-piksel ofset.

**Maliyet yolu.** `compute_cost_grid` `w_roughness · f_roughness` terimini dört terimli toplamdan **sonra** ekliyor, yani katman yokken gövde v4 formülünün işlem-işlem aynısı. `COST_MODEL_ID` → **v5**. Site11 iki yönlü SHA-256 ile kilitli: katmanla (LPR-1 `55e1bb3c…`, VIPER `593f8e46…`) ve katman kaldırıldığında ya da `w_roughness = 0` iken v4 digest'leri (`0e74607d…`, `8788936c…`) byte-byte geri geliyor. Kilit denemesi bir hata da buldu: saklanmış grid artık `metadata["cost_criteria"]` taşıyor ve eldeki katmanlar farklıysa yeniden hesaplanıyor.

**PSR planlamaya girmiyor — tasarımla.** VIPER'ın bilim hedefleri PSR'lerin içinde, üstelik soğuk uç termal kapısı Site11'in 14 016 PSR hücresinin **13 933'ünü** LPR-1 için zaten kapatıyor. Maske `MEASURED` bir katman, hücre kartında `in_psr`, her rota bloğunda `cells_in_psr` ve `GET /api/psr-validation`.

**Site11'de ölçülen.** Pürüzlülük 100 m tabanda medyan **0,83 m** (p5 0,40, p95 1,78, maks 4,87); 200/400/800/1600 m medyanları 1,69 / 3,30 / 7,80 / 23,6 m; Hurst medyanı 0,92. Bölge medyanı 0,57 m olduğu için Site11'de `f_roughness` p5 0,23 – p95 0,98 aralığına yayılıyor. **Eğimin yeniden ifadesi değil:** Spearman(pürüzlülük, eğim) 5 m'de 0,213 (blok ortalama/maks eğime karşı 0,227 / 0,321); medyan pürüzlülük 0–5° kuşağından >20° kuşağına 0,72 → 1,08 m yükseliyor (PSJ 2025'in yönü, zayıfça). w = 0,15'te maliyet gridi dört terimliyle Spearman 0,959 / 0,945 tutuyor. **PSR ↔ `shadow_ratio ≥ 0,99`: Jaccard 0,830** (PSR hücrelerinin %98,3'ü karanlık deniyor; bizim karanlık hücrelerimizin %84,2'si PSR), ürünün kendi 20 m bloklarında 0,912; maske içinde ortalama gölge 0,998, medyan `thermal_min` −183,15 °C. Rota etkisi küçük ve çifte bağlı: LPR-1 ay gecesi çifti w = 0,05'te bile kayıyor (0,15'te örtüşme 0,05, rota pürüzlülüğü 0,75 → 0,66 m, aynı 2,727 km, ama 1 465,7 → **1 519,4 Wh (+%3,7)**) — **daha düz zemin enerjiyle satın alınıyor**; VIPER standart rota 0,20'ye kadar değişmiyor.

**İddia sınırı.** Katman `MEASURED` ama 5 m gride 50 m/px ve 100 m tabanla postalanmış: her hücre **kendi pürüzlülüğünü değil**, onu kapsayan 50 m pikselin hektometre ölçekli blok istatistiğini taşıyor ve bu bir kaya sayımı değil. Kriterin [0,1] eşlemesi bir istatistiksel ölçek (`MODEL`): hücrenin 80–90°G bölgesindeki persentil sırası. `w_roughness = 0,15` **varsayım** (raporda 0–0,3 süpürüldü); katalogdaki hiçbir rover kaynaklı bir pürüzlülük toleransı bildirmiyor, o yüzden uydurulmadı. **"Diviner kaya bolluğu kullanıyoruz" denemez** — ürün 80–90°G'yi kapsamıyor ve kullanılmadı.

**Dosyalar.** `app/roughness.py` · `scripts/build_roughness_cache.py`, `scripts/roughness_psr_report.py` · rapor `docs/research/roughness_psr_report.md` · sözleşme eki "Ölçülmüş pürüzlülük ve PSR maskesi" (~1144) · spec/plan `2026-09-05-c4-roughness-psr*` · 88 yeni test.

---

### D2 — Dış benchmark: MoonPlanBench · `8b0c5ad`

**Sorun.** LunaPath'in tek planlayıcı karşılaştırması Site11'deki kendi nav2 taban çizgisiydi.

**Yapılan.** MoonPlanBench (Chancán, Banerjee, Nikolakopoulos, arXiv 2512.21438, Aralık 2025; PlanetaryPathBench @`86dc4b63`) ay kutuplarının 36 occupancy gridini yayımlıyor: 12 LOLA kutup LDEM ürünü × 10/15/20° eğim eşiği, 64× altörneklenmiş — hücre 320 m ile 7,68 km arası. LunaPath 36 haritanın hepsinde **benchmark'ın kendi problem tanımıyla** koşturuldu ve sonuç makalenin Tablo 1'inin yanına konuldu (tablo alıntı; ölçümle karıştırılmıyor).

**Benchmark'ın ne olduğu, kodundan okunup veride doğrulandı.** Haritalar `uint8` `.npy`, sıfır olmayan = dolu; 243² – 477² hücre, boş oran %51–96. Başlangıç ve hedef yayımlanmış bir liste değil, `auto_select_start_goal` tarafından **tanımlanıyor** (en büyük 8-bağlı boş bileşen, sözlükte en küçük (y,x) başlangıç, en uzak hedef) — aynı BFS sırasıyla yeniden yazıldı ve deponun fonksiyonuyla **36/36 haritada eşit**. Referans planlayıcılar (PythonRobotics) 8-komşulukta **köşe-kesme yasağı olmadan** hareket ediyor: iki dolu hücre arasından çapraz adım yasal.

**Ölçülen (36 harita).** Saf mesafe Dijkstra, benchmark'ın hareket modeliyle: **%100 / %100 / %100 başarı**, ortalama yol 651,81 / 636,16 / 620,24 hücre — makalenin Dijkstra satırı **iki ondalığa kadar, üç varyantta da**. LunaPath'in köşe-kesme yasağıyla: %33,3 / %91,7 / %100 ve 720,30 / 658,34 / 631,88 hücre. MoonPlanBench-10'da **on iki haritanın sekizi yalnız iki dolu hücre arasındaki çapraz hamlelerle bağlantılı**. Köşesiz Dijkstra'nın yol bulduğu her yerde LunaPath da buluyor: fark planlayıcıda değil, hareket modelinde. Çok kriterli mod burada hiçbir şey kazandırmıyor ve bunu söylüyor: haritalarda gölge, termal, slip, pürüzlülük ya da DEM katmanı olmadığı için maliyet gridi 36 haritanın hepsinde tek bir değer (0,190969). Süre (tracemalloc kapalı): LunaPath A* harita başına ortalama 0,22–0,39 s; aynı makinede PythonRobotics Dijkstra 3,3–8,2 s, A* 7,8–13,5 s; makale 13–32 s. **Yöntem bulgusu:** tracemalloc açıkken LunaPath 5,8–11,8 s'ye çıkıyor (~30×), o yüzden süre ve bellek ayrı geçişlerde ölçülüyor.

**İddia sınırı.** Yalnız occupancy'li, eğim eşikli, hücresi 320 m – 7,7 km olan bir benchmark **bir hareket modeli altında bağlantılılığı** ölçer, rover rota planlamasını değil. Makalenin %100'ü LunaPath'in reddettiği köşe kesmeye dayanıyor; **iki satır da gösteriliyor**. Öğrenmeli planlayıcı bulguları makalenin, alıntı.

**Dosyalar.** `app/benchmark.py` · `scripts/build_moonplanbench_cache.py`, `scripts/moonplanbench_runner.py`, `scripts/nav2_baseline.py` · rapor `docs/research/moonplanbench_report.md` · **API ucu yok**, sözleşme dokunulmadı · spec/plan `2026-09-05-d2-moonplanbench*` · 54 yeni test · veri lisansı CC BY-NC-SA 4.0, depoya girmiyor.

---

### B1 — Reach-avoid kurtarma politikası ve şans kısıtı · `48ea152`

**Sorun.** 4-B planlayıcı deterministikti: bir rota rover'ın zarfının içindeydi ya da değildi ve yolda bir şey ters gittiğinde ne olacağını hiçbir şey söylemiyordu.

**Yapılan.** Lamarre, Malhotra ve Kelly (Acta Astronautica 2023; IEEE Aerospace 2024) bunu stokastik bir reach-avoid problemiyle yanıtlıyor: (hücre, zaman, batarya) üzerinde Poisson mobilite-arıza modeliyle geriye doğru değer iterasyonu her durum için **en iyi politikanın bile başarısızlıkla bitme olasılığını** veriyor, argmin eylem ise bir kurtarma politikası; görev planlayıcı da yürütme başarısızlık olasılığı β'yı aşan planları reddediyor. B1 bunu LunaPath'in kaba gridi (coarsen 4), SPICE gölge serileri ve `cost_engine` enerji fiziği üzerinde kuruyor.

**Neyin onların, neyin bizim olduğu her yanıtta yazıyor.**
- **Arıza oranı ve kurtarma süresi VARSAYIM:** katalogdaki hiçbir rover ikisini de yayımlamıyor. `FAILURE_RATE_PER_KM_ASSUMED = 0,2` (onun "5 000 m'de 1 arıza"sı), `FAULT_RECOVERY_HOURS_ASSUMED = 10`, kaynak dizeleri `assumption:` ile başlıyor; **profile alan eklenmedi**.
- **Güvenli küme onun haven-only kümesinden sapıyor ve bunu söylüyor:** ölçüm LPR-1'in Site11'de üç epokun **hiçbirinde haven'ı olmadığını** buldu (VIPER: 19 / 0 / 862 kaba blok), o yüzden varsayılan "leg" kümesi = rezervdeki hedef bloğu ∪ hibernasyon şarjındaki her haven; "haven" onun katı kümesi olarak duruyor.
- **Onun muhafazakâr alt-bin eşlemesi bu hamle boyutunda kullanılamaz:** 20 m'lik bir hamle ~19 Wh çekiyor, bin ise 271 Wh — alt-bin haritası karanlık hamle başına tam bir bin (yaklaşık 14×) yazıyordu ve ölçüm standart gündüz rotasının başında `P_safe = 0,000` okuyordu, blokların %90'ı sıfırda. SOC bin merkezleri arasında lineer interpolasyonla (onun "interpolation map"i) aynı alan **0,985** okuyor. Muhafazakârlık artık **ampirik**: politikanın sürekli zamanlı Monte Carlo'suyla denetleniyor.

**Site11'de ölçülen (coarsen 4).** Alanlar: LPR-1 gündüz 28 Eyl 2026 **65,3 M durum** (DP 96 s), ay gecesi 13 Eyl 68,5 M (136 s), VIPER kısa bacak 30 May 2027 39,8 M (46 s). Başlangıçta tam bataryayla `P_safe` **0,985 / 0,883 / 1,000**; yarım bataryayla 0,972 / 0,404 / 0,761. Kısıtsız planların yürütme başarısızlık olasılığı: gündüz **%1,65**, ay gecesi **%11,05**, VIPER %0,08. β süpürmesi {0,10; 0,05; 0,02}: gündüz çifti her β'da 41 hamlelik rotasını koruyor (0,02'de arama 13 811 hamleyi reddedip aynı rotayı buluyor); **ay gecesi çifti üçünde de 404**, çünkü başlangıçtan optimal kurtarma politikası bile 0,1173 olasılıkla başarısız; VIPER 8 hamlesini koruyor. Makalenin "+0,5 km, +2 saat"i burada tekrarlanmadı: rotalar ya değişmiyor ya da uygulanamaz oluyor — rezerv ve karanlık zaten deterministik zarfın içinde. **Tahmin ≥ gerçekleşen** (1 000 koşum, Wilson %95): gündüz 1,51'e karşı 1,20 [0,69–2,09], gece 11,7'ye karşı 4,6 [3,5–6,1], VIPER 0,08'e karşı 0,0 — üçünde de muhafazakâr, gecede 2,5×. Katı haven kümesi: LPR-1 her epokta boş; VIPER 30 May 2027'de 862 blok, ortalama `P_safe` 0,725.

**Dürüst uyarı, raporda.** Gecede politika sürekli zamanda uygulandığında sabit plandan **daha çok** batarya arızası üretti (1 000 koşumun 38'i, sabit planda 0): en yakın bin merkezinden okunan politika rezervin yakınındaki 3 puanlık SOC farkını görmüyor.

**API.** `/api/plan-4d`: `max_failure_probability` (β), `report_survival`, `failure_rate_per_km`, `recovery_hours`, `survival_soc_bins`, `survival_safe_set`, `survival_horizon_hours`; `survival` bloğu ve iki durum listesi; 404 detayında şans kısıtı cümlesi. `GET /api/cell-telemetry?survival=true` (hücrenin `P_safe`'i ve en iyi eylemi), `POST /api/replan` `recovery_policy: true` → `recovery_suggestion`, `GET /api/survival` (kaba `p_safe` / `best_action`, f32, `X-Layer-Validity: MODEL`). SHERPA'ya arıza olayı eklendi (`fault_rate_per_km`, varsayılan sıfır → B5 bit-eşit).

**Maliyet.** Alan 46–136 s; alanla planlayıcı gündüz 10–11 s (alansız 7 s), gece 43 s (22 s), VIPER 3 s. `max_failure_probability` ya da `report_survival` verilmezse planlayıcı **B1 öncesiyle bit-eşit** — üç standart rota eskisi gibi 41 / 116 / 8 hamle.

**İddia sınırı.** "Rotanın başarısızlık olasılığı ≤ β" denebilir, ama **arıza oranı α'nın bir varsayım olduğu** (Lamarre'ın 1/5 km'si) açıkça söylenmeli. Onun sayıları (41,5 M durum; β %2 → gerçekleşen %1,5) alıntı olarak duruyor, bizim ölçümümüzle karışmıyor.

**Dosyalar.** `app/survival.py`, `app/pathfinder_4d.py` · `scripts/recovery_policy_report.py` (rapor 49 dk) · rapor `docs/research/recovery_policy_report.md` · sözleşme eki "Kurtarma politikası ve şans-kısıtlı planlama" (~1268) · spec/plan `2026-09-05-b1-recovery-policy*` · 54 yeni test.

---

### C6 — Termal operasyon zarfı ve tolere edilebilir saplanma süresi · `5173105`

**Sorun.** Termal denetim statikti: bir hücrenin yıllık-zirve ya da soğuk-uç yüzey sıcaklığı, kataloğun parçalı ofsetleriyle iç sıcaklığa çevrilip batarya/elektronik zarfına karşı okunuyordu. D3 sonucunu ölçtü: Site11'deki her gerçek rota LP-R04 ve LP-R05'i ihlal ediyor — çünkü denge zaten zarfın dışında ve modelin ne zaman ekseni ne de ısıtıcısı vardı.

**Yapılan.** NASA JSC/MSFC VIPER için tam bu soruya iki çerçeve kurmuştu (Slusser, Turk, Stewart, Page, Barragan, Mittag; ICES-2025-376): **sınırsız operasyon zarfı** ve **tolere edilebilir saplanma süresi**. C6 ikisini de LunaPath'in kendi modeliyle kuruyor, makalenin PDF'ini bunların gerçekte ne olduğu için okuyor ve her şeyi Site11'de ölçüyor.

**Makaleden okunan üç düzeltme (araştırma belgesine işlendi).** (1) JSC'nin zarf grafiği **eğim × rover başlığına göre Güneş azimutu**, misyonun **maksimum** Güneş yüksekliğinde (16 azimut × 6 eğim = 96 kararlı-durum vakası, 60+ bileşen, Thermal Desktop); belgedeki "azimut × yükseklik × eğim" yanlıştı — yükseklik ekseni makalenin gelecek işi. (2) "AFT'nin 12 °C üstünde / 77 °C" bir vakanın sonucu değil, bir aviyonik kutusu için **AFT normalizasyonu örneği**. (3) Onların "tolere edilebilir saplanma süresi" bir termal büyüklük değil, **haven penceresi** (ay gecesinden önce hedef güvenli limana varmak için kalan süre).

**Model.** `app/thermal_dwell.py`: zarf, bildirilen en dar kesişim (LPR-1/VIPER: batarya [0, 35] °C); iç sıcaklık kataloğun `thermal_tau_s` zaman sabitiyle `surface_to_inner(surface(t))`'ye doğru gevşiyor; `exit_time_h` sabit hedef için kapalı form (zaten dışarıdaysa 0, hedef içerideyse sınırsız, yoksa `τ·ln(...)`); `build_dwell_cube` bütün başlangıç dilimlerini birlikte ilerletip bir (başlangıç, blok) çiftini bloğun hedefi artık zarftan çıkamaz olduğu anda emekliye ayırıyor → **`max_dwell_h[t, y, x]`**. `cost_cube.surface_temperature_series` küpün zaten entegre ettiği yüzey serisi olarak dışarı çıkarıldı ve küp aynı diziyi kullanıyor — **bit-eşit, testli**: küp ile dwell tek bir yüzey görüyor.

**En büyük bulgu — kısıt sürede değil, sıcaklıkta.** İlk sürüm blok başına ardışık hareketsiz saatleri sınırlıyordu ve planlayıcı **iki karanlık blok arasında mekik dokuyarak** saatini sıfırlayıp aynı şekilde donmayı sürdürdü (kendi testi yakaladı). Bu yüzden zorlanan büyüklük **iç sıcaklığın kendisi**: her etiket onu taşıyor (bekleme: beklenen blok; hamle: varış bloğu) ve zarfın dışına çıkaracak her geçiş reddediliyor. Bir bloğun dwell süresini aşan bekleme tam olarak böyle bir geçiş. Beşinci baskınlık ekseni termal marj, tolerans zarf genişliğinin onda biri ve on anahtar kutusu — batarya ekseninin %1 / 400 kutusunda gündüz rotasının kısıtlı araması 2,3 GB ve on dakikayı aştı ve bitmedi.

**Isıtıcı.** Kaynaklı bir watt→kelvin bağı yok. `heater_model="none"` (varsayılan) ısıtıcıyı eskisi gibi yalnız enerji modelinde tutuyor; `"thermostat_assumed"` açık bir **varsayım** (`constants.HEATER_THERMOSTAT_ASSUMPTION_SOURCE`): hayatta kalma ısıtıcısı zarfın alt sınırını tutar. Katalog alanı eklenmedi. `thermal_tau_s` olmayan bir rover (LUVMI-M) dwell almıyor ("unavailable" + gerekçe), denge kararını koruyor.

**API.** `/api/plan-4d`: `require_thermal_dwell`, `initial_inner_c`, `heater_model`; her yanıtta `thermal_dwell` bloğu, `path_inner_c` / `path_max_dwell_h` / `path_dwell_margin_h` / `path_stay_hours` ve `metrics.min_dwell_margin_h`. `GET /api/cell-telemetry?thermal_dwell=true` hücre kartı ve tolere edilebilir saplanma süresi (termal + A1 haven penceresi). `POST /api/replan` `state.entrenched_hours` → `entrenchment` bloğu ve tetikleyici (ok / warning %50 / critical %80 / fail). `GET /api/thermal-dwell` katmanı; `GET /api/thermal-envelope` heat1d transient'inden Güneş yüksekliği × Güneş'e paralel eğim zarf matrisi (önbelleksiz 422, asla sentetik matris). Güvenlik kataloğuna **LP-R12** eklendi.

**Site11'de ölçülen.** SPICE Güneş yüksekliği bir yılda −2,59° … +2,55° (−88,92° enleminde). heat1d'nin düz hücre zirvesi −146,4 °C; Güneş'e bakan 30°'lik bir eğim +44,5 °C'ye çıkıyor, sıcak dal bunu **+4,5 °C** iç sıcaklığa eşliyor: **JSC'nin sıcak yanı Site11'de bizim modelimizde yok**. Zarf matrisi (LPR-1): 19 kutu sınırsız, 173 soğuk-sınırlı, 13 "sıcak-sınırlı" — on üçünün her biri, soğuk dalın +60 K'sının 35 °C üstüne attığı −23,5…−0,4 °C yüzey; **ofset modelinin eseri ve öyle etiketli**. Dwell küpü ilk dilimde: gündüz rotası %3,2 sınırsız / %96,0 soğuk / %0,8 sıcak, sonlu medyan **0,547 h**; ay gecesi 0/100/0, 0,547 h; VIPER 17,2/73,2/9,5, 0,622 h. **D3 dinamikle yeniden:** üç standart rota da (kısıtsız, 17,5 °C başlangıç, ısıtıcısız) zarfı **0,53–0,70 saat içinde** terk ediyor ve geri dönmüyor (gündüz min −15,7 °C, 42 durumun 34'ü dışarıda). İhlal duruyor; artık bir süresi var. Kısıt açıkken: ısıtıcı "none" üçünü de gerekçeli 404 ile reddediyor (gündüz 229 435 geçiş reddedildi); `"thermostat_assumed"` üçünü de **rota değişmeden** geçiriyor (41 / 116 / 8 hamle, iç sıcaklık minimumu +5,1 / +0,6 / +6,4 °C) — soğuk yan ısıtıcının olduğunda sıcak yan burada hiç bağlamıyor. Saplanma: termal bütçe ay gecesi başında 0,485 h, rota ortasında 0,420 h, gündüz başında 0,486 h; **haven penceresi LPR-1 için her yerde 0 saat** (A1: Site11'de ulaşılabilir haven yok), yani genel seviye her saplanma süresinde "fail" — JSC'nin saati rover sıkışmadan önce dolmuş ve rapor bunu söylüyor.

**İddia sınırı.** Termal model **MODEL / UNCALIBRATED**; her blok bunu söylüyor ve **hiçbir termal doğruluk iddiası yok** (Diviner doğrulaması C5'in işi). Isıtıcı bağı varsayım; JSC'nin sayıları `JSC_QUOTED`'da alıntı.

**Dosyalar.** `app/thermal_dwell.py` · `scripts/build_thermal_envelope_cache.py`, `scripts/thermal_dwell_report.py` · rapor `docs/research/thermal_dwell_report.md` · sözleşme eki "Termal operasyon zarfı" (~1424) · spec/plan `2026-09-05-c6-thermal-dwell*` · 60 yeni test.

---

## 5. API yüzeyi

Ayrıntı, örnek istek/yanıt gövdeleriyle birlikte: `docs/frontend/3b-veri-sozlesmesi.md`.

### 5.1 On üç yeni uç (18 → 31)

| Uç | Özellik | Ne döner |
|---|---|---|
| `GET /api/earth-series` | A4 | Dilim başına Dünya görünürlüğü serisi (`/api/illumination-series` ile aynı sözleşme ve bütçe) |
| `GET /api/comm-window` | A4 | Hesaplanmış iletişim penceresi ve kalan dakika |
| `GET /api/safe-haven` | A1 | Manifest + dört ikili katman (`safe_haven`, `max_dark_hours_without_dte`, `earth_below_hours`, `time_to_safe_haven`) |
| `POST /api/stress-test` | B5 | Bir plan-4d rotasının N koşumluk SHERPA dağılımları, Wilson %95 aralıkları, karar metni |
| `GET /api/uncertainty-series` | B3 | Dilim başına `p_illuminated`, klon küpleri üzerinde (f32) |
| `POST /api/dem-uncertainty` | B3 | Rota bandı (p5/p50/p95), klonlar arası geçilebilirlik, durum başına passability |
| `POST /api/safety-check` | D3 | Telemetri izinin 12 gereksinime karşı robustness'ı (422: zaman geri gidiyor / NaN / motor yok) |
| `GET /api/illumination-corridor` | A2 | (T, h, w) koridor küpü f32 (`corridor`, `lit_safe`, `dwell_hours`) ya da JSON manifest |
| `POST /api/risk-sweep` | B2 | Aynı çiftin nominal ve birkaç α'daki planları, örtüşme ve risk matrisi (2-B) |
| `GET /api/psr-validation` | C4 | PGDA PSR maskesi ↔ bizim gölge modelimiz: Jaccard, recall, precision |
| `GET /api/survival` | B1 | Kaba `p_safe` / `best_action` katmanı (f32, `X-Layer-Validity: MODEL`) |
| `GET /api/thermal-dwell` | C6 | `max_dwell_h` / `side` / `open_ended` katmanı (f32) |
| `GET /api/thermal-envelope` | C6 | Güneş yüksekliği × Güneş'e paralel eğim zarf matrisi (önbelleksiz 422) |

### 5.2 Mevcut uçlara eklenenler

| Uç | Yeni istek alanları | Yeni yanıt blokları |
|---|---|---|
| `POST /api/plan-4d` | `require_earth_visibility` (A4), `require_safe_haven` (A1), `require_continuous_illumination` + `lit_rule` (A2), `risk_alpha` (B2), `max_failure_probability` + `report_survival` + 5 alan (B1), `require_thermal_dwell` + `initial_inner_c` + `heater_model` (C6) | `uncertainty`, `safety_margins`, `illumination_corridor`, `slip_model`, `risk`, `roughness`, `survival`, `thermal_dwell` + durum başına diziler (`path_earth_visible`, `path_time_to_haven_h`, `path_haven_margin_h`, `path_survival_prob`, `path_inner_c`, `path_max_dwell_h`, `path_dwell_margin_h`, …) |
| `POST /api/plan` | `risk_alpha`, `weights.w_roughness` | `safety_margins`, `slip_model`, `risk`, `roughness`, `uncertainty` |
| `POST /api/compare`, `POST /api/plan-multi` | `w_roughness` | `safety_margins` her sonuçta; `comparison.safety_margin_ranking`, `largest_min_margin_profile` |
| `GET /api/cell-telemetry` | `start_utc` (A1), `survival=true` (B1), `thermal_dwell=true` (C6) | Haven kararı ve süresi, `P_safe` + en iyi eylem, termal dwell kartı, `roughness_m` / `f_roughness` / `in_psr`, `cost_breakdown.roughness` |
| `POST /api/replan` | `utc`, `recovery_policy`, `state.entrenched_hours`, `heater_model` | Hesaplanmış `comm_window`, `recovery_suggestion`, `entrenchment` bloğu + tetikleyici |
| `POST /api/pose` | — | Hesaplanmış `comm_minutes_remaining` |
| `GET /api/rovers` | — | `slip_model` (kaynaklı çapalar, 0–25° tablo), `declared_only.regolith` |
| `GET /api/terrain`, `GET /api/layers/{ad}` | `rover_id`, `format=f32` | Yeni katmanlar: `earth_visibility`, `p_traversable`, `slope_sigma`, `elevation_sigma`, `slope_sigma_nasa`, `roughness`, `psr` + `dem_uncertainty` soyağacı |

**Geriye uyum.** Hiçbir alan kaldırılmadı, hiçbir alanın anlamı değişmedi; eklemeler isteğe bağlı ve varsayılanları eski davranışı veriyor. Önbelleği olmayan katmanlar yanıtta hiç görünmez.

### 5.3 Frontend ne çizebilir

Bu dalın ürettiği her şeyin görselleştirme karşılığı. Tel biçimi, başlıklar ve örnek gövdeler
`docs/frontend/3b-veri-sozlesmesi.md`'de; burada **ne çizilebileceği** var.

#### a) Harita katmanı — `GET /api/layers/{ad}?format=f32`

`/api/terrain` manifestindeki 15 katmanın **yedisi bu dalda geldi**:

| Katman | Birim | Özellik | Çizim notu |
|---|---|---|---|
| `earth_visibility` | oran 0–1 | A4 | Uzun dönem DTE oranı; sürekli renk rampası |
| `p_traversable` | oran 0–1 | B3 | Geçilebilirlik olasılığı; 0,5 çevresi "belirsiz" bandı olarak vurgulanabilir |
| `slope_sigma` | derece | B3 | Bizim klon σ'mız |
| `slope_sigma_nasa` | derece | B3 | NASA'nın hata modeli (**MODEL**, ölçüm değil — rozet farkı önemli) |
| `elevation_sigma` | m | B3 | Z-belirsizliği |
| `roughness` | m | C4 | **MEASURED**; 50 m/px blok istatistiği, 5 m'ye postalanmış (bulanık görünmesi normal) |
| `psr` | ikili | C4 | Maske; dolgu ya da kontur olarak |

Manifestte olmayıp **kendi ucundan** f32 gelen katmanlar:

| Katman | Uç | Özellik | Çizim notu |
|---|---|---|---|
| `safe_haven`, `max_dark_hours_without_dte`, `earth_below_hours`, `time_to_safe_haven` | `GET /api/safe-haven` | A1 | Dördü tek çağrıda; `time_to_safe_haven` **NaN = ulaşılabilir haven yok** — sıfırla karıştırmayın |
| `p_safe`, `best_action` | `GET /api/survival` | B1 | `best_action` kategorik (yön/bekle) → ok alanı ya da kategori rengi |
| `max_dwell_h`, `side`, `open_ended` | `GET /api/thermal-dwell` | C6 | Sınırsız hücreler ufukta kırpılıyor, `open_ended` alanı onları ayırıyor; `side` soğuk/sıcak kategorisi |

**İki tuzak.** (1) Çözünürlük karışımı: ince katmanlar 5 m/px, 4-B türevli katmanlar (survival, thermal-dwell, corridor) `coarsen 4` ile **320 m blok**; üst üste bindirirken ölçek dönüşümü şart. (2) NaN "sıfır" değil: geçilemez ya da ulaşılamaz demek, ayrı renk ister.

#### b) Zaman ekseni — scrub ve animasyon

| Uç | Ne döner | Özellik |
|---|---|---|
| `GET /api/illumination-series` | Dilim başına gölge + Güneş azimut/yükseklik | (mevcut) |
| `GET /api/earth-series` | Dilim başına Dünya görünürlüğü | A4 |
| `GET /api/uncertainty-series` | Dilim başına `p_illuminated` + belirsiz hücre oranı | B3 |
| `GET /api/illumination-corridor` | (T, h, w) küp: `corridor` / `lit_safe` / `dwell_hours` | A2 |
| `GET /api/thermal-dwell`, `GET /api/survival` | `t_hours` parametresiyle istenen dilim | C6, B1 |

Beşi de aynı zaman ekseninde: tek bir kaydırıcı hepsini sürebilir. Koridor küpü özellikle
gösterişli — "rover'ın hiç gölgeye girmeden geçebileceği hacim" olarak animasyon.

#### c) Rota boyunca renk rampası ve alt grafik — `POST /api/plan-4d`

Durum başına diziler; rotanın üstünde renk ya da altında çizgi grafik olarak:

`path_earth_visible` (A4, ikili) · `path_time_to_haven_h`, `path_hours_until_earthset`,
`path_haven_margin_h` (A1) · `path_dark_hours`, batarya (mevcut) · `path_survival_prob`,
`path_recovery_prob` (B1) · `path_inner_c`, `path_max_dwell_h`, `path_dwell_margin_h`,
`path_stay_hours` (C6).

En anlatıcı ikisi: **`path_inner_c`** rotanın hangi durumunda zarfı terk ettiğini gösteriyor
(zarf bandını arka plana çizin), **`path_haven_margin_h`** sıfıra yaklaştıkça rover'ın komut
alamadan kalacağı süreyi gösteriyor.

#### d) Kart, rozet ve panel — her yanıtta gelen bloklar

| Blok | Özellik | Görsel karşılığı |
|---|---|---|
| `safety_margins` | D3 | 12 gereksinim × ρ + birim + marjın en küçük olduğu durum → marj tablosu ya da radar; ihlal kırmızı |
| `slip_model` | C3 | Rota ortalama/maks slip'i, eklediği saat ve Wh; `/api/rovers`'taki 0–25° tablo doğrudan **eğri grafiği** |
| `risk` | B2 | α sürgüsü, çarpan, kriter başına etki, σ kaynakları |
| `roughness` | C4 | Rota pürüzlülüğü, kriterin maliyetteki payı |
| `uncertainty` | B3 | p5/p50/p95 **bant grafiği** (yüzey DEM'inin değeri bandın içinde nerede) |
| `illumination_corridor` | A2 | Voksel sayısı, budanan oran, bileşen sayısı, dwell fırsatları |
| `survival` | B1 | `P_safe`, β, reddedilen geçiş sayısı |
| `thermal_dwell` | C6 | Kalan dwell saati, zarfın hangi yanı, ısıtıcı modeli |
| `entrenchment` (`/api/replan`) | C6 | **Geri sayım göstergesi**: ok / warning (%50) / critical (%80) / fail — termal bütçe ve haven penceresi yan yana |

Her blokta `validity` (`MEASURED` / `DERIVED` / `MODEL` / `SYNTHETIC`) ve çoğunda `claim` var:
**rozet olarak gösterin** — iddia sınırının kullanıcıya ulaştığı tek yer burası.

#### e) Dağılım ve karşılaştırma grafikleri

| Uç | Özellik | Görsel |
|---|---|---|
| `POST /api/stress-test` | B5 | Tamamlama oranı + Wilson %95 aralığı (hata çubuğu), p5/p50/p95, hazır **histogramlar**, durum başına varış ve batarya **yelpaze grafiği** (fan chart), kesinti istatistikleri, karar metni |
| `POST /api/dem-uncertainty` | B3 | 100 klonun bandı; durum başına geçilebilirlik |
| `POST /api/risk-sweep` | B2 | α'lar arası rotalar yan yana + nominal rotayla hücre örtüşmesi + **risk matrisi ısı haritası** |
| `GET /api/thermal-envelope` | C6 | Güneş yüksekliği × Güneş'e paralel eğim **ısı haritası** — JSC'nin zarf grafiğinin bizdeki karşılığı; kutular sınırsız / soğuk-sınırlı / sıcak-sınırlı olarak üç renk |
| `GET /api/psr-validation` | C4 | NASA maskesi ile bizim gölge modelimiz üst üste; Jaccard / recall / precision sayıları |

#### f) Hücre kartı — `GET /api/cell-telemetry`

Tek tıklamayla: beş kriterin `cost_breakdown` dökümü (C4 ile pürüzlülük de dahil),
`roughness_m` / `f_roughness` / `in_psr`, haven kararı ve en yakın haven'a süre (`start_utc` ile),
`P_safe` + en iyi eylem (`survival=true`), termal dwell kartı ve tolere edilebilir saplanma
süresi (`thermal_dwell=true`).

#### g) Henüz görsel karşılığı olmayan tek özellik

**D2 (MoonPlanBench)** çevrimdışı bir benchmark koşumu: API ucu yok, teslimatı
`docs/research/moonplanbench_report.md`. Sunumda kullanılacaksa rapordaki tablo doğrudan
ekrana alınır; canlı bir uçtan gelmez.

---

## 6. Veri, önbellekler ve lisanslar

Hiçbiri depoya girmiyor (`.gitignore`); her biri kendi provenance JSON'unu yazıyor.

| Script | Ürün | Ne indirir / üretir | Süre |
|---|---|---|---|
| `build_horizon_cache.py` | LOLA 40 m kutup DEM (`ldem_85s_40m.img`) | Ufuk küpü; A4 ile 10 km → **150 km** uzak alan taraması, ham DEM'in işlenmiş pencereyi kapsadığını doğruluyor | dakikalar |
| `build_earth_visibility_cache.py` | SPICE çekirdekleri | 18,6 yıllık saatlik Dünya görünürlüğü ortalaması (NASA ürününün kullandığı aralık) | dakikalar |
| `build_dem_clone_cache.py` | **PGDA 78** (Site11 DEM klonları) | `toterr`, `slperr` + ilk N klon, 1 km yakın-alan dolgusuyla, `/vsicurl/` aralık okumaları, 4 paralel bağlantı; klon başına ufuk küpü | klon başına ~2,5 s + indirme |
| `build_roughness_cache.py` | **PGDA 90** (LDRM roughness + LPSR PSR) | 9 pencere, ürün başına ~1 MB (150–650 MB yerine tek COG tile) | 10 s indirme, ~40 s toplam |
| `build_moonplanbench_cache.py` | MoonPlanBench (Google Drive) | 36 occupancy haritası, dosya başına SHA-256'lı meta; **CC BY-NC-SA 4.0** | dakikalar |
| `build_thermal_envelope_cache.py` | — (heat1d transient) | 10 eğim × 13 ay günü zarf örnekleri | 41,5 s (boş makine) – 233 s (yüklü) |

**Lisanslar.** NASA PGDA ürünleri kamuya açık; MoonPlanBench verisi CC BY-NC-SA 4.0 (ticari kullanım yok), PathBench BSD-3, PythonRobotics MIT. Ayrıntı: `docs/DATA_LICENSES.md`.

---

## 7. Formal gereksinimler (LP-R01 … LP-R12)

FRETISH cümlesi, elle yapılmış STL çevirisi, sinyal, birim ve rover parametresi:
`docs/requirements/lunapath.fret.json`. Dosya `app/safety_monitor.py`'deki katalogdan üretiliyor ve
`test_checked_in_fret_file_matches_the_catalogue` ikisi ayrıştığında kırmızıya dönüyor — **belge kodla sürüklenemez.**

| # | FRETISH | Getiren |
|---|---|---|
| LP-R01 | `shadow_continuous_h <= h_max_shadow_h` | D3 |
| LP-R02 | `soc_pct >= soc_min` | D3 |
| LP-R03 | `soc_pct < soc_min` olunca 6 saat içinde `charging` | D3 |
| LP-R04 | `elec_op_min_c <= inner_temp_c <= elec_op_max_c` | D3 |
| LP-R05 | `bat_op_min_c <= inner_temp_c <= bat_op_max_c` | D3 |
| LP-R06 | `drive_slope_deg <= slope_max_deg` | D3 |
| LP-R07 | `lateral_slope_deg <= slope_lateral_max_deg` | D3 |
| LP-R08 | Hareket modunda `earth_visible` | D3 (A4'ün katmanı) |
| LP-R09 | `time_to_haven_h <= hours_until_earthset` | D3 (A1'in kuralı) |
| LP-R10 | Sonunda `at_goal` | D3 |
| LP-R11 | Hedefteyken `soc_pct >= soc_min` | D3 |
| LP-R12 | `stay_h <= max_dwell_h` | **C6** |

---

## 8. Ölçüm raporları ve yeniden üretim

Hepsi `docs/research/` altında. Çoğu `--json <dosya>` ile ham çıktı yazıp `--from-json` ile yeniden render ediliyor,
yani rapor metnini düzeltmek için ölçümü tekrar koşturmak gerekmiyor.

| Rapor | Üreten komut | Önkoşul | Süre |
|---|---|---|---|
| `earth_visibility_validation.md` | `python scripts/earth_visibility_validation.py` | Ufuk küpü, çekirdek, PGDA 69 | dakikalar |
| `safe_haven_report.md` | `python scripts/safe_haven_report.py` | Ufuk küpü, çekirdek | dakikalar |
| `stress_test_report.md` | `python scripts/stress_test_report.py` | Ufuk küpü, çekirdek | dakikalar |
| `dem_uncertainty_report.md` | `python scripts/dem_uncertainty_report.py` | Klon önbelleği | dakikalar |
| `safety_monitor_report.md` | `python scripts/safety_monitor_report.py` | Ufuk küpü, çekirdek | dakikalar |
| `illumination_corridor_report.md` | `python scripts/illumination_corridor_report.py` | Ufuk küpü, çekirdek | dakikalar |
| `slip_calibration_report.md` | `python scripts/slip_calibration_report.py` | Ufuk küpü, çekirdek | dakikalar |
| `risk_sweep_report.md` | `python scripts/risk_sweep_report.py` | Klon önbelleği (+4-B için küp) | dakikalar |
| `roughness_psr_report.md` | `python scripts/roughness_psr_report.py` | Pürüzlülük önbelleği | dakikalar |
| `moonplanbench_report.md` | `python scripts/moonplanbench_runner.py [--reference-dir …] [--memory]` | Benchmark önbelleği | dakikalar |
| `recovery_policy_report.md` | `python scripts/recovery_policy_report.py --json <dosya>` | Ufuk küpü, çekirdek | **49 dk** |
| `thermal_dwell_report.md` | `python scripts/thermal_dwell_report.py --json <dosya>` | Ufuk küpü, çekirdek (+ zarf önbelleği) | **8,8 dk** |

Ek olarak dalın öncesinden gelen ve hâlâ geçerli olanlar: `nav2_baseline.md`, `localization_budget.md`,
`lidar_payload_comparison.md`.

---

## 9. Ne söylenebilir, ne söylenemez

Sunumda kullanılacak cümleler ve koşulları. Uzun hâli: `docs/research/12_faktor_backend_ozellik_arastirmasi_2026-09-03.md` §5.

| ✅ Söylenebilir | Dayanağı |
|---|---|
| "VIPER ile aynı safe-haven tanımını ve 50 saat kuralını uyguluyoruz" | A1; Shirley & Balaban 2022, Ennico-Smith 2023 |
| "Dünya görünürlüğü katmanımız NASA'nın LOLA ürünüyle doğrulandı: RMSE 0,087, r 0,960" | A4; PGDA 69, 163 162 örnek |
| "Her rotayı NASA'nın stres-test protokolüyle 1 000 kez simüle edip marj dağılımlarını raporluyoruz" | B5; SHERPA parametreleri birebir |
| "Belirsizlik nicelenmiştir; enerji tüketimi NASA'nın 100 DEM klonu üzerinde %90 bantla veriliyor" | B3; PGDA 78 |
| "Güvenlik gereksinimleri FRETISH'te yazıldı ve her rota STL robustness ile nicel marjla **denetleniyor**" | D3; iki motor, çapraz kontrol 0 |
| "Slip modelimiz uçmuş veriye (Yutu-2) ve VIPER'ın tasarım kısıtına **bağlandı**" | C3; her çapa kaynaklı |
| "İki katmanımız artık MEASURED etiketli (pürüzlülük, PSR)" | C4; PGDA 90 |
| "Bağımsız bir benchmark'ta koşturduk ve sonuçları makalenin tablosuyla yan yana koyduk" | D2 |
| "Rotanın yürütme başarısızlık olasılığına üst sınır (β) koyabiliyoruz" | B1; α'nın varsayım olduğu söylenerek |
| "Rover'ın iç sıcaklığının zarfı terk etmesine kaç saat kaldığını hesaplıyoruz" | C6 |

| ❌ Söylenemez | Neden |
|---|---|
| "Gereksinimlerimiz model checking ile ispatlandı" | Yalnız somut izler denetleniyor; hiçbir sonuç tüm izler için ispat değil (D3) |
| "FRET aracıyla üretildi" | Araç kurulmadı; cümleler grameri elle izliyor (D3) |
| "Slip modelimiz ölçüldü" | Kutup regolitinde ölçüm yok; etiket MODEL (C3) |
| "Diviner kaya bolluğu kullanıyoruz" | Ürün 80–90°G'yi kapsamıyor, kullanılmadı (C4) |
| "Termal modelimiz doğru" | Model UNCALIBRATED; Diviner doğrulaması yapılmadı — C5'in işi (C6) |
| "Bağımsız benchmark'ta %100 başarı" (koşulsuz) | %100 köşe-kesmeye dayanıyor; LunaPath'in kuralıyla %33,3 / %91,7 / %100 (D2) |
| "Rotamız güvenli" | B5: VIPER rotası koşumların ~%70'inde bataryadan düşüyor; D3: her gerçek rota termal zarfı ihlal ediyor |
| "Risk modelimiz ölçülmüş bir riski veriyor" | MODEL etiketli dağılımların CVaR'ı; termal σ hiç yok (B2) |
| "Bir hücrenin pürüzlülüğünü biliyoruz" | 50 m/px, 100 m tabanlı blok istatistiği; kaya sayımı değil (C4) |

---

## 10. Açık kalanlar

Bunlar bilinen ve yazılı; kapatılmadıkları için gizlenmiyorlar.

1. **Planlayıcı batarya/saat uyumsuzluğu (B5 bulgusu, hâlâ açık).** `astar_4d` saati `ceil(travel / slice)` dilim ilerletiyor ama bataryayı yalnız sürüş süresi için düşüyor; Monte Carlo'nun nominal koşumu VIPER rotasının min bataryasını %32 yerine **%23** buluyor.
2. **Termal zarf ihlali sürüyor.** D3 her gerçek rotanın LP-R04/R05'i ihlal ettiğini buldu; C6 buna bir **süre** verdi (0,53–0,70 saat) ama fiziği değiştirmedi. Pasif modelde üç standart rota da `require_thermal_dwell` altında 404. Isıtıcı varsayımıyla geçiyorlar — **kaynaklı bir ısıtıcı modeli hâlâ yok.**
3. **LPR-1'in Site11'de haven'ı yok.** A1 üç epokun hiçbirinde bulamadı; sonuç olarak B1'in katı haven kümesi boş ve C6'nın saplanma geri sayımı LPR-1 için her zaman "fail".
4. **Ay gecesi rotası şans kısıtı altında uygulanamaz.** B1: optimal kurtarma politikası bile 0,1173 olasılıkla başarısız, yani β ∈ {0,10; 0,05; 0,02} için 404.
5. **B1'in politikası rezerv yakınında kör.** Sürekli zamanda uygulandığında gecede sabit plandan daha çok batarya arızası üretiyor (1 000'de 38'e karşı 0): bin merkezinden okuma 3 puanlık SOC farkını görmüyor.
6. **Termal CVaR yok (B2 kancası reddediyor).** Termal alanın yayımlanmış σ'sı olmadığı için risk kuyruğu termalde uygulanmadı.
7. **Dokümantasyon boşluğu.** Kök `README.md`'de A4, A1 ve B5 için satır yok (diğer dokuzda var) ve mevcut dokuz satır "Özellikler" değil "Veri" başlığının altında duruyor. `docs/research/00_INDEKS.md` 12 Ağustos'tan beri güncellenmedi; on iki ölçüm raporunun hiçbiri indekste değil.

### Sıradaki işler (öncelik matrisinden)

| Kod | Ne | Efor (gün) | Neden sırada |
|---|---|---|---|
| **C1** | Panel geliş açısı (cos i) modeli | 1 | **Matriste sıradaki**; C2'nin önkoşulu |
| C2 | Batarya soğuk davranışı ve hibernasyon | 2 | Termal zarf ihlalinin diğer yarısı |
| C5 | Diviner PRP / Williams 2019 ile termal RMSE | 1 | C6'nın modelini ölçülmüş ürüne bağlar |
| D5 | Pareto cephesi | 1 | Ağırlık tartışmasını bitirir |
| D4 | Kontrastif açıklama ("neden bu rota?") | 1–2 | XAIP |
| B4 | Sobol duyarlılık (SALib) | 1–2 | Hangi kriterin gerçekten önemli olduğu |
| A5 | Zaman pencereli bilim-istasyonu sıralaması | 3–4 | A1'e bağlı |
| A3, D1, D6, D7, D8, D9 | Hızlandırma, Theta*, izokronlar, enav doğrulaması, SMG, LCNS | 0,5–2 | Matrise bakınız |

---

## 11. Doğrulama durumu

- **Tam paket: 1 502 geçti, 5 atlandı, 1 uyarı, 21 dk 25 s** (6 Eylül 2026, boş makinede). Uyarı `test_visibility_validation`'ın ve dalın öncesinden geliyor.
- Atlananlar: heat1d kuruluyken atlanan bir C6 testi, `LUNAPATH_PPB_DIR` verilmediğinde atlanan iki D2 klon testi, iki eski atlama.
- **Paket ilerleyişi:** A1 837 → B5 906 → B3 953 → D3 1 031 → C3 1 176 → B2 1 250 → C4 1 338 → D2 1 391 → B1 1 443 → C6 1 502.
- **Süre uyarısı:** yüklü makinede aynı paket 43 dakika sürebiliyor (B1 koşumunda öyle oldu); süre ölçümü için makineyi boş bırakın.
- **Gerçek grid testleri** (`test_*_real_grid.py`) DEM, ufuk küpü ya da çekirdek yoksa kendini atlar; CI'da atlanır, geliştirici makinesinde koşar.
- **Bit-eşitlik kilitleri:** her yeni planlayıcı kısıtı kapalıyken aynı düğümleri açıyor; C3'ün ve C4'ün maliyet gridleri iki yönlü SHA-256 ile kilitli; C3'ün vektörize slip ikizi skalerle 0 ulp.

---

## 12. Kaynakça

**NASA VIPER / SHERPA**
- Shirley & Balaban, *Overview of Mission Planning for the VIPER Rover*, 2022 — A1, B5
- Ennico-Smith vd., *VIPER Mission Traverse Planning*, NTRS 2023 — A1
- Balaban vd., *SHERPA*, SpaceOps 2025 — B5
- Slusser, Turk, Stewart, Page, Barragan, Mittag, *Generalizing Lunar Vehicle Thermal Analysis: Lessons Learned from VIPER*, **ICES-2025-376** — C6
- *Investigating the Geotechnical Properties of the Lunar South Pole with VIPER's Mobility System*, **PSJ 2025** — C3

**NASA veri ürünleri (GSFC Planetary Geodesy)**
- PGDA ürün 69 — LOLA Average Earth Visibility (A4)
- PGDA ürün 78 — Site DEM belirsizliği ve 100 klon; Barker vd. 2021 (B3)
- PGDA ürün 90 — LOLA LDRM roughness + LPSR PSR maskesi; Barker vd. 2023, **PSJ 4:183**, DOI 10.60903/gsfcpgda-lola-spole (C4)

**Akademik yöntemler**
- Otten, Jones, Wettergreen, Whittaker (CMU), ICRA 2015 / FSR 2017 — sürekli-aydınlık koridoru (A2)
- Lamarre, Malhotra, Kelly, **Acta Astronautica 2023** (arXiv 2307.16786) ve **IEEE Aerospace 2024** (arXiv 2401.08558) — reach-avoid kurtarma politikası (B1)
- Rockafellar & Uryasev 2000 — CVaR kapalı formu (B2)
- Fan vd. (JPL STEP), **RSS 2021**; Endo vd. (Keio), **ICRA 2023** — planlayıcı maliyetinde CVaR (B2)
- Chancán, Banerjee, Nikolakopoulos, **arXiv 2512.21438** (Aralık 2025) — MoonPlanBench (D2)
- Yutu-2 slip ölçümü, **Nature Communications 2024** — C3
- NASA FRET (Giannakopoulou vd. 2020) + AIT **RTAMT 0.3.5** — D3

**Kod ve veri**
- PlanetaryPathBench @`86dc4b63` (BSD-3), PythonRobotics (MIT), MoonPlanBench verisi (CC BY-NC-SA 4.0)
- heat1d (Hayne 2017) — yüzey termal modeli
- NAIF SPICE çekirdekleri — efemeris

---

*Bu doküman `berke-3d-backendEnhance` dalının `d401854..5173105` aralığını özetler.
Kaynaklar: on iki commit mesajı, `docs/research/*_report.md`, `docs/superpowers/specs|plans/`,
`docs/frontend/3b-veri-sozlesmesi.md`, `docs/requirements/`.*
