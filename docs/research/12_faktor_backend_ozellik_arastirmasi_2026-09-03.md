# 12 — Backend "Wow Faktörü" Özellik Araştırması: Sektörel Projelerden Ödünç Alınabilecek Teknikler

**Tarih:** 3 Eylül 2026 · **Branch:** `berke-3d` (HEAD `374d8bc`) · **Kapsam:** yalnızca araştırma, kod değişikliği yok
**Soru:** Bizim challenge'ımıza (Ay güney kutbunda termal güvenlik odaklı, çok kriterli, zaman-farkında rover rota planlama) benzeyen **gerçek misyonlar, akademik planlayıcılar, yarışmalar ve hackathon projeleri** hangi teknikleri kullanıyor; bunlardan hangileri **backend'e** eklenince jüride "wow" etkisi yaratır ve challenge'ın özüne (termal/enerji güvenliği, görev sürdürülebilirliği) gerçekten katkı sağlar?

> Bu belge [10_sektorel_projeler_envanteri.md](10_sektorel_projeler_envanteri.md) (kim ne yapmış) ve [11_backend_olgunluk_analizi_2026-08-30.md](11_backend_olgunluk_analizi_2026-08-30.md) (biz neredeyiz) belgelerinin **devamıdır**; onlarda zaten anlatılan şeyleri tekrar etmez, yalnızca **yeni** teknik ve özellikleri ele alır. Her kayıtta: **ne olduğu → hangi proje/kim → link → detaylı açıklama → LunaPath'te bugün ne var → projeye somut katkısı → efor ve wow puanı.**
>
> **Doğruluk notu:** Sayılar açık kaynaklardan (NASA NTRS, arXiv, PGDA/PDS, GitHub) derlendi; erişilemeyen (403/paywall) kaynaklarda özet/abstract düzeyinde kalındı ve bu belirtildi. Kullanmadan önce bağlantıdan teyit edin.

---

## 0. Yönetici özeti

Araştırmanın ana bulgusu: **LunaPath'in zaten yaptığı şey (SPICE efemeris + ray-cast ufuk + zaman-genişletilmiş A* + WAIT kenarı + 4 rover profili + provenance) NASA VIPER'ın strateji planlama zincirinin küçültülmüş bir kopyasıdır.** VIPER'ın yer yazılımı (SHERPA) ve CMU/Toronto akademik planlayıcıları bunun üstüne üç şey daha koyuyor ve LunaPath'te bu üçü yok:

1. **Güvenli liman (safe haven) + Dünya görünürlüğü (DTE) ekseni** — VIPER'da rota planlamanın *asıl* kısıtı güneş değil, "Dünya batmadan güvenli limana var" kuralıdır. LunaPath'te Dünya görünürlüğü hiç hesaplanmıyor.
2. **Belirsizlik ve risk sınırı** — "bu rotanın başarısızlık olasılığı ≤ %5" diyebilmek. LunaPath'te hiçbir çıktının hata bandı yok (11 no'lu belgede skorkartın en zayıf boyutu, 1/5).
3. **Dış kıyas (benchmark) ve doğrulama** — ölçülmüş bir referansa karşı sayı. NASA'nın kendisi 5 m/px DEM'lerle birlikte **100 hata klonu** ve **Dünya-görünürlük haritaları** yayınlıyor; ikisi de indirilip doğrudan kullanılabilir.

Bu üç eksende toplam **22 özellik/teknik** belgelendi. Aşağıdaki 10'u, efor/etki oranına göre en yüksek getirili olanlardır:

| # | Özellik | Kaynak projesi | Efor | Wow | Challenge etkisi |
|---|---|---|---|---|---|
| A1 | Safe-haven haritası (Ay günü bazlı) + "50 saat karanlık" kuralı + *time-to-safe-haven* katmanı | NASA VIPER / SHERPA | 2–3 gün | ★★★★★ | ★★★★★ |
| A4 | Dünya görünürlüğü (DTE) katmanı: SPICE ile Dünya az/el + ufuk → iletişim gölgesi; LOLA ürünüyle doğrulama | Mazarico 2011 / VIPER | 1–2 gün | ★★★★☆ | ★★★★☆ |
| B3 | DEM hata yayılımı: NASA'nın 100 DEM klonuyla Monte Carlo → P(geçilebilir), P(aydınlık) | NASA GSFC PGDA (Barker) | 2–3 gün | ★★★★★ | ★★★★☆ |
| B5 | Monte Carlo traverse stres testi (SHERPA "Traverse Evaluation" dağılımları ve metrikleri) | NASA VIPER / SHERPA | 2 gün | ★★★★☆ | ★★★★★ |
| B1 | Stokastik reach-avoid "kurtarma politikası" → risk-sınırlı rota (P_fail ≤ β) | Toronto STARS (Lamarre & Kelly) | 5–8 gün | ★★★★★ | ★★★★★ |
| A2 | Sürekli-aydınlık koridoru: 3B bağlı-bileşen budaması ile 4B planlayıcıyı hızlandırma ve "asla gölgeye girmez" kanıtı | CMU (Otten, Whittaker) | 2–3 gün | ★★★★☆ | ★★★★☆ |
| D2 | MoonPlanBench standart benchmark'ında koşup sonuç yayınlamak | arXiv 2512.21438 (Aralık 2025) | 1 gün | ★★★★☆ | ★★★☆☆ |
| D3 | Formal güvenlik kuralları: FRET ile yazılmış gereksinim + STL robustness monitörü (RTAMT) | NASA Ames FRET / AIT RTAMT | 2–3 gün | ★★★★☆ | ★★★★☆ |
| B2 | CVaR tabanlı risk-farkında maliyet (slip/termal dağılımlarından) | JPL STEP / Ishigami Lab | 2 gün | ★★★★☆ | ★★★★☆ |
| D1 | Herhangi-açı planlama (Theta* / Field D* enterpolasyonu) — MER'de uçmuş algoritma ailesi | JPL/CMU (Carsten 2007) | 1 gün | ★★★☆☆ | ★★☆☆☆ |

**Tek cümlelik öneri:** A1 + A4 + B5 üçlüsü bir haftada yapılır ve sunumda "NASA VIPER'ın planlama kısıtlarını ve stres-test metriklerini birebir uyguluyoruz" denmesini sağlar; B3 + B1 ise projenin en büyük akademik açığını (belirsizlik = 1/5) kapatır.

---

## 1. Yöntem ve seçim ölçütleri

Şu dört süzgeçten geçmeyen hiçbir şey bu listeye alınmadı:

1. **Kabul görmüş olma:** Uçmuş bir misyonda (MER, Yutu-2, Pragyan, VIPER) kullanılmış, hakemli yayında sayısal sonuçla gösterilmiş veya resmi bir yarışmada (Lunar Autonomy Challenge, ISRO BAH, NASA SRC2) uygulanmış olmalı.
2. **Backend'e ait olma:** Yalnızca `backend/app/` katmanında (planlayıcı, maliyet, fizik, API) uygulanabilir olmalı; algı/kamera/SLAM kapsam dışı (README zaten bunu reddediyor).
3. **Challenge'a özgü olma:** Termal güvenlik, enerji, gölge/aydınlanma, görev sürdürülebilirliği eksenlerinden en az birine doğrudan dokunmalı.
4. **Yeni olma:** 01–11 numaralı belgelerde zaten önerilmiş şeyler (Diviner indirme, heat1d, hiyerarşik planlama, D* Lite, radyasyon SEP senaryosu, ablasyon) burada yalnızca referans verilerek geçildi.

"Wow" puanı, jürinin (TÜBİTAK UZAY / rover topluluğu çevresi; bkz. `rover_project/AYAP2_ANALIZ.md`) *"bunu bir öğrenci ekibi yapmış olamaz"* diyeceği tahmini ile verildi. "Challenge etkisi" ise özelliğin proje belgesindeki (`ay_termal_navigasyon_proje_dokumani.md`) Modül 4–6 çıktılarına (risk, health, replanning, safe haven, alternatif rota) ne kadar dokunduğudur.

---

## 2. LunaPath'te bugün ne var (dürüst temel çizgi)

Aşağıdaki özellikler önerilirken hepsi mevcut kodun üzerine kurulur; tekrar yazılmaz.

| Mevcut yetenek | Kod | Bu belgedeki hangi özellik üstüne kuruluyor |
|---|---|---|
| SPICE Güneş vektörü (`spkpos`, `MOON_ME`, `LT+S`), CRS yakınsama düzeltmesi | `ephemeris.py` | A4 (Dünya için aynı çağrı) |
| Ray-cast topografik ufuk (Ay eğriliği dahil) | `horizon.py` | A2, A4, B3 |
| Zaman dilimli gölge serisi | `illumination_series.py` | A1, A2, A5 |
| Zaman-genişletilmiş A*, WAIT kenarı, `wait_cost` (güneş şarjı − idle − ısıtıcı) | `pathfinder_4d.py`, `cost_cube.py` | A1, A2, A3, B1, C1, C2 |
| Rover başına `h_max_shadow_h` (LPR-1 için **50 saat** — VIPER'ın 50 saatlik min-power dayanımıyla aynı) | `constants.py` | A1 |
| Statik safe-haven indeksleri (gölge oranına göre) | `corridor.py:_safe_haven_indices` | A1 |
| `check_comm_window(minutes_remaining)` tetikleyicisi (girdi dışarıdan geliyor, hesaplanmıyor) | `replan_triggers.py` | A4 |
| Simülasyon: `max_continuous_shadow_h` ihlal kontrolü | `simulation.py` | B5, C2 |
| Referans misyon hızları (Yutu-2, Pragyan) | `mission_reference.py` | D8 |
| `slip_model.py` — **UNCALIBRATED** etiketli | `slip_model.py` | C3 |
| Provenance (`layer_validity`, `weakest_validity`) | `terrain.py` / metadata | C4, C5 |
| `CostMap.explain()`, `/api/cell-telemetry`, nav2 baseline | `costmap.py`, `scripts/nav2_baseline.py` | D2, D4 |
| Uzamsal en-büyük-bileşen ön kontrolü (`bfs_move_count`) | `pathfinder_4d.py` | A2 (zamansal versiyonu), A3 |

---

# BÖLÜM A — Zaman-uzay planlama ve görev güvenliği

## A1. ✅ ⭐⭐⭐⭐⭐ Safe Haven haritası, "50 saat karanlık" kuralı ve *time-to-safe-haven* katmanı

> **Yapıldı (4 Eylül 2026, `berke-3d-backendEnhance`):** `safe_haven.py` — VIPER tanımı birebir (Dünya ufkun altındayken kesintisiz gölge ≤ `h_max_shadow_h`, pencerede en az bir kez aydınlanma, geçilebilirlik; bir sinodik ay, 2 h adım), saat cinsinden `time_to_safe_haven` (kapılı sürüş grafında çok kaynaklı Dijkstra), `GET /api/safe-haven` (dört ikili katman), `/api/cell-telemetry?start_utc=` içinde `safe_haven`, `/api/plan-4d` `require_safe_haven` (her durumda, bekleme dahil, `tts ≤ Dünya batışına kalan saat`; batış ufuk dışında 14 günlük ön-bakışla) ve SHERPA marjları (`time_to_sun_shadow_min/mean_h`, `time_to_dsn_shadow_min_h`, `time_to_zero_soc_min_h`). **Ölçüm (Site11, 13 sinodik ay):** Dünya-yok iki hafta sitenin ~6,5 gün karanlık kaldığı Ay gecesiyle çakışıyor; en kısa Dünya-yok karanlık Ay gününe göre 40–186 h. Safe haven nadir — NASA'nın dediği gibi: LPR-1 (50 h) yalnızca Kasım 2026'da ~40 hücre (%0,02), VIPER (96 h) en iyi Ay günü 30 Mayıs 2027'de %10,7, LUVMI-M (4 h) ve Yutu-2 (2 h) hiç; sitenin %1 / %10 haven sunması için gerekli dayanım aya göre 64–232 h / 82–298 h. Rapor: [safe_haven_report.md](safe_haven_report.md). Tasarım: [../superpowers/specs/2026-09-04-a1-safe-haven-design.md](../superpowers/specs/2026-09-04-a1-safe-haven-design.md). Sapma: `time_to_safe_haven` maliyet küpü üzerinde değil, saat cinsinden ve uzamsal (kenar süresi bu modelde aydınlanmadan bağımsız); zaman bağımlılığı `hours_until_earthset[t, c]` tarafında.

**Ne:** Rover'ın Dünya ufkun altındayken (her ayın ~2 haftası) park edip hayatta kalabileceği yerlerin haritası; rotanın her anında "buradan en yakın safe haven'a kaç saatte ve ne kadar enerjiyle varırım" bilgisi.

**Kim:** NASA Ames, VIPER misyonu strateji planlama ekibi (Mark Shirley, Edward Balaban) — SHERPA yazılımı.

**Linkler:**
- [An Overview of Mission Planning for the VIPER Rover (Shirley & Balaban, NASA, 2022, PDF)](https://www.nasa.gov/wp-content/uploads/2022/05/overview_of_mission_planning_for_the_viper_rover.pdf)
- [VIPER Mission Traverse Planning – Design, Strategies, and Dynamics (Ennico-Smith vd., NTRS 2023)](https://ntrs.nasa.gov/api/citations/20230004239/downloads/SSR2023-VIPER-Planning-Ennico.pdf?attachment=true)
- [SHERPA — An AI System for Mission Planning and Decision Support (Balaban vd., SpaceOps 2025, PDF)](https://publications.spaceops.org/2025/download.php?doc=559__4nupk3n2.pdf)
- [VIPER Lunar Operations (NASA Science)](https://science.nasa.gov/mission/viper/lunar-operations/)

**Detaylı açıklama (VIPER'ın kuralları, birebir):**
- Traverse **"leg"**lerden oluşur; bir leg = bir Ay günü. Her leg iniş noktasından veya bir **Safe Haven (SH)**'dan başlar.
- SH tanımı: *"Dünya ufkun altındayken kesintisiz gölge süresi 50 saati geçmeyen ve rover'ın hareketsiz beklerken güç üretebildiği konum."* VIPER'ın min-power modunda dayanımı **50 saat**, matkapla çalışırken gölge dayanımı **~9,5 saat**.
- Dünya ayın yaklaşık yarısında ufkun altında; "< 50 saat gölge" koşulunu sağlayan yerler **nadir**dir ve SH'lar misyonu uzatan asıl kaynaktır.
- SHERPA'nın planlama veri seti şunları içerir: **2 saatlik adımla gölge zaman serisi, time-to-shadow serisi, eğim haritası, PSR sınırları, Ay günü bazlı safe-haven haritaları, buz kararlılık derinliği, Güneş ve Dünya azimut/yükseklik serileri, uçuş kuralları.** Rota çözünürlüğü 20 m/px.
- VIPER için eğim sınırı 15°, hız 20 cm/s tepe, ancak **"Speed Made Good" ~1 cm/s** (zamanın %90'ı beklemede).
- Stratejik plan her science station, PSR girişi, şarj molası ve SH için konum + zaman verir; **nominal ve kontenjan (contingency) dalları** içerir.

**LunaPath'te bugün:** `corridor._safe_haven_indices` gölge oranına göre statik bir küme üretiyor; `h_max_shadow_h` rover başına var (LPR-1 için 50 saat, VIPER ile birebir). Ancak (a) SH'lar zamana bağlı değil, (b) Dünya görünürlüğüyle ilişkilendirilmiyor, (c) "buradan SH'a kaç saat" katmanı yok, (d) planlayıcı SH'a ulaşmayı **kısıt** olarak taşımıyor.

**Somut katkı (backend):**
1. `safe_haven.py`: `illumination_series` + (A4'teki) Dünya görünürlüğü serisi → her Ay günü için `safe_haven_mask[day]` = "Dünya ufkun altındayken maksimum kesintisiz gölge ≤ h_max_shadow_h(rover)". Rover profiline göre otomatik değişir (LUVMI-M için 4 saat → çok az SH; Yutu-2 için 96 saat → çok).
2. `time_to_safe_haven` katmanı: her hücre ve zaman dilimi için, mevcut `cost_cube` üzerinde SH kümesinden geri Dijkstra → saat cinsinden mesafe. `/api/cell-telemetry` bu değeri döndürür.
3. `pathfinder_4d`'e sert kısıt: `time_to_safe_haven(c,t) + Δ ≤ hours_until_earthset(t)` — VIPER'ın "Dünya batmadan SH'a var" kuralı.
4. Yeni rota metrikleri: **time-to-sun-shadow (min, ort)**, **time-to-DSN-shadow**, **time-to-0-SOC** — SHERPA'nın metrik listesinden.

**Neden wow:** Jüriye "VIPER'ın leg/safe-haven yapısını ve 50 saat kuralını aynı sayılarla uyguluyoruz; rover profilini değiştirince safe-haven haritası nasıl büzüşüyor görün" denir. Bu, challenge belgesindeki "6.7 Safe haven / recovery logic kapsamı" açık sorusunu tamamen kapatır.

**Efor:** 2–3 gün (A4'e bağımlı). **Doğruluk kanıtı:** SH kuralı ve 50 saat NASA belgelerinden birebir.

---

## A2. ✅ ⭐⭐⭐⭐ Sürekli-aydınlık koridoru: 3B (x, y, t) bağlı-bileşen analizi

> **Yapıldı (4 Eylül 2026, `berke-3d-backendEnhance`):** `illumination_corridor.py` — aydınlanma serisi + kaba geçilebilirlikten `(t, satır, sütun)` ikili `lit_safe` hacmi (iki aydınlık kuralı: `all` = bloktaki 16 ince hücrenin hepsi aydınlık, varsayılan; `majority` = blok ortalaması < 0,5, planlayıcının kendi eşiği), CMU'nun iki geçişli budaması **planlayıcının kendi kenarları üzerinde** (aynı kapılar `safe_haven._gated_edges`, aynı hamle süresi `d = ceil(kenar süresi / dilim)` — CMU'nun "bir sonraki dilimdeki 9 komşu" grafı 320 m blok ve otomatik dilimde birden çok dilim süren hamlelere genelleştirildi: hamle boyunca **iki blok da** aydınlık kalmalı), ileri erişilebilirlik (ilk dilimden gelemeyen kökler) ∧ geri erişilebilirlik (son dilime ulaşamayan çıkmazlar), dilim başına vektörize (ayrık hamle uzunlukları üzerinde düz dilimleme; 100 dilimde budama 56 ms); `scipy.ndimage.label` 26-komşuluk bileşenleri kıyas için; dwell (CMU metriği). Planlayıcı: `astar_4d(corridor_cube, corridor_lit_run_cube, require_continuous_illumination)` — başlangıç t0'da koridorda, bekleme koridor vokseline, hamle iki blok aydınlık kalarak; ret sayacı `continuous_illumination`; uygulanmasa da `states_outside_corridor` / `moves_outside_corridor` raporlanır. API: `/api/plan-4d` `require_continuous_illumination` + `lit_rule`; her yanıtta `illumination_corridor` bloğu (hacimler, budanan oran, bileşenler, başlangıç/hedef durumu, rota içeride mi, `max_dwell_hours` + fırsatlar, provenance ve **iddia sınırı**) ve `metrics.max_dwell_hours`; statik seride `require` → 422; koridor kapalıysa 404 gerekçesi sayılarla; `GET /api/illumination-corridor` küpü f32 (`corridor` / `lit_safe` / `dwell_hours`, `X-Series-*`). **Ölçüm (Site11, [illumination_corridor_report.md](illumination_corridor_report.md)):** VIPER 30 May 2027, varsayılan 9,6 h ufuk (100 × 0,0956 h, 125×125 @ 320 m): aydınlık-güvenli hacim **%40,5** (`all`; `majority` %45,8), budama yalnızca **%0,2** siliyor (10 saatte kutup aydınlanması neredeyse durağan; CMU'nun budaması 59 günlük pencerelerde anlamlı), CMU label 50 bileşen / en büyüğü %91 / 44'ü iki ucu tutuyor. **Standart haven→haven çifti Güneş-eşzamanlı değil**: başlangıç bloğu t0'da karanlık, hedef bloğu hiçbir dilimde aydınlık değil, rota 4,55 h gölgede (D3 ile tutarlı) → `require` 404 (gerekçe: "start block is never inside the corridor; goal ... 0 of 100 slices"). Koridor-içi çift (`corridor_pair`: kaba (105,89)→(94,27), 62 blok ≈ 19,8 km, 8 h ufuk / 0,1 h dilim): **`path_dark_hours` tümü 0, D3 LP-R01 ρ = 96,00 h = `h_max_shadow_h`**, en düşük SOC %93,6, 62 hamle / 0 bekleme, 7,90 h, dwell 8 h (ufka dayalı); planlama budamasız 452 ms / 7 233 düğüm, koridorla (`all`) 417 ms / 6 467 düğüm (**×1,08 süre, ×1,12 düğüm**; `majority` ×1,00 / ×1,08) — mütevazı: maliyet küpü gölgeyi zaten fiyatladığından budamasız rota da koridorda; "22 s → X s" türü kazanç bu gridde ölçülmedi. LPR-1 28 Eyl 2026: varsayılan 2,9 h ufukta aydınlık %4,8 (koridor 54 984 voksel, hedef 100/100 dilim koridorda ama başlangıç karanlık, rota 16/41 durum içeride), **8 h ufukta koridor yok** (aydınlık ada büzülüyor: 55 150 → 20 566 voksel). Ay gecesi 13 Eyl 2026: hiçbir voksel aydınlık değil, `require` 404 "no block is lit at any of the 246 slices". Koridor kurulumu 100 dilimde 135 ms (`all`) / 287 ms (`majority`), 246 dilimde ~0,3 s — her plan-4d yanıtına eklenen maliyet. Testler: 59 birim (elle hacimler, 26 tohumlu kaba-kuvvet BFS çapraz kontrolü, `ndimage.label` kapsaması, d > 1 hamleler, dwell, özet, çift seçimi), 8 planlayıcı, 12 API, 3 skip-korumalı gerçek grid. Tasarım: [../superpowers/specs/2026-09-04-a2-illumination-corridor-design.md](../superpowers/specs/2026-09-04-a2-illumination-corridor-design.md). Sapmalar: `scipy.ndimage.label` bileşenleri yalnızca kıyas (asıl budama hamle-süresi farkında erişilebilirlik); koridor üyeliği ile "hamle boyunca aydınlık" koşulu ayrıştırıldı (`forward_reach(run=…)`: hamlede geçilen voksel durum olmayabilir); geçişler zaman ekseninde fancy-index yerine ayrık `d` değerleri üzerinde dilimliyor (≤ 6 farklı değer; gather yolu yedek ve testle eşitliği sabit); `corridor_pair` yardımcı (spec'te yoktu; standart çiftler koridor dışında olduğundan rapor/test çifti seçer); `main.py`'de 2-B `corridor.build_corridor` ile ad çakışması → `build_illumination_corridor` takma adı; "3B koridor görselleştirmesi" frontend ekibine (veri sözleşmesinde alanlar).

**Ne:** Aydınlanma zaman serisi ve eğim maskesi birleştirilip **x-y-t hacminde** flood-fill ile "sürekli aydınlık ve güvenli eğimli" bağlı bileşenler bulunur; kökleri (başlangıç zamanına ulaşmayan) ve çıkmaz dalları (bitiş zamanına ulaşmayan) budanır; kalan hacim, "rover bu koridorun içinde kaldığı sürece **asla** gölgeye girmez" garantisi verir. Rota bu hacim içinde ileri-zamanlı A* ile bulunur.

**Kim:** CMU Robotics Institute — Nathan Otten, Heather Jones, David Wettergreen, William "Red" Whittaker (NIAC destekli).

**Linkler:**
- [Planning Routes of Continuous Illumination and Traversable Slope using Connected Component Analysis (ICRA 2015, PDF)](https://www.ri.cmu.edu/app/uploads/2018/01/ICRA2015_Otten_3109.pdf) · [RI sayfası](https://publications.ri.cmu.edu/planning-routes-of-continuous-illumination-and-traversable-slope-using-connected-component-analysis)
- [Strategic Autonomy for Reducing Risk of Sun-Synchronous Lunar Polar Exploration (FSR 2017, PDF)](https://publications.ri.cmu.edu/storage/publications/2018/01/FSR_2017_Otten_66.pdf)
- [Otten doktora tezi: Planning for Sun-Synchronous Lunar Polar Roving (CMU KiltHub)](https://kilthub.cmu.edu/articles/thesis/Planning_for_Sun-Synchronous_Lunar_Polar_Roving/6721082/1)

**Detaylı açıklama:**
- Girdi: LOLA 5 m/px (kutup yakını) + NAC stereo 2 m/px + 240 m/px geniş alan; **SPICE** ile Güneş vektörü; ray-tracing (Blender) ile aydınlanma görüntüsü; eşik ile ikili "aydınlık/gölge" haritası. Simülasyon **LRO WAC gerçek görüntüleriyle** doğrulanmış.
- 3×3×3 çekirdekle (26-komşuluk) flood-fill; en büyük bileşen seçilir; iki geçişli budama (zamanda ileri, sonra zamanı ters çevirip tekrar).
- Graf: her voksel düğüm, kenarlar yalnızca **bir sonraki zaman dilimindeki** 9 komşuya (ileri zaman). A* Öklid mesafeyle.
- Sonuçlar: Malapert Tepesi çevresinde 2 Ay döngüsünde (59 gün) **2,16 km, ort. 1,5 m/saat**; Shackleton çevresinde **34,7 km, 25 m/saat**; sırasıyla **45 ve 226 saat** kesintisiz bekleme (dwell) fırsatı — bilim için değerli.
- FSR 2017: "singularity" (haftalarca kesintisiz güneş alan noktalar) belirsizliğine karşı **"strategic autonomy"** — iletişimsiz kısa otonom sürüşlerle gölgeden uzaklaşma.
- Makalenin "future work"ü: sıcaklık ve iletişim (*"Dünya görünürlüğü güneşle neredeyse aynı biçimde modellenebilir"*) — bu tam olarak A4.

**LunaPath'te bugün:** `pathfinder_4d` uzamsal en-büyük-bileşeni kontrol ediyor (`bfs_move_count`, %76,4 bileşen ölçümü), ama **zamansal** bileşen analizi yok; A* tüm küpte arıyor.

**Somut katkı:**
1. `cost_cube` üretilirken `lit_and_safe[t,y,x]` ikili hacmi çıkarılır; `scipy.ndimage.label(..., structure=np.ones((3,3,3)))` ile bileşenler; iki geçişli budama.
2. Planlayıcıya `require_continuous_illumination=True` seçeneği: arama uzayı budanmış bileşenle sınırlanır → hem **hız** (11 no'lu belgede 22 s'lik koşumlar) hem **kanıt** ("rota tanım gereği gölgeye girmiyor").
3. Yeni metrik: `max_dwell_hours` (rotada beklenebilecek en uzun aydınlık süre) — bilim istasyonu yerleşimi için.
4. Rapor cümlesi: "Sun-synchronous yaklaşımını (CMU, NIAC) 4B planlayıcımızın ön-filtresi olarak uyguladık."

**Efor:** 2–3 gün. **Wow:** yüksek (görselleştirilebilir 3B koridor; frontend zaten 3B).

---

## A3. ⭐⭐⭐ Zaman sıkıştırma ve hedef-erişilebilirlik budamasıyla 4B planlamayı hızlandırma

**Ne:** Aydınlanmanın değişmediği zaman aralıklarını **sıkıştırma** (time compression), hedefe zaten ulaşamayacak durumları **erişilebilirlik** ile eleme, statik engellerden **ön-hesaplanmış sezgisel** kullanma.

**Kim:** CMU — Christopher Cunningham, Joseph Amato, Heather Jones, William Whittaker.

**Link:** [Accelerating energy-aware spatiotemporal path planning for the lunar poles (ICRA 2017, IEEE Xplore)](https://ieeexplore.ieee.org/document/7989508) — paywall; abstract düzeyinde. İlgili: [Cunningham vd., Locally-Adaptive Slip Prediction for Planetary Rovers Using Gaussian Processes (ICRA 2017)](https://arxiv.org/pdf/1805.05451) (özet: solar rover otonomisi).

**LunaPath'te bugün:** `auto_slice_hours` ve invariant-katman probing zaten var (11 no'lu belge §3.1) — yani time compression'ın **kısmi** hali mevcut; erişilebilirlik ön-kontrolü de var. Eksik: dilim aralığının **yerel** (hücre bazında) değil global olması ve hedef-erişilebilirlik budamasının zaman eksenini kapsamaması.

**Somut katkı:** (a) Dilim uzunluğunu gölge serisinin değişim oranına göre adaptif seç (değişim yoksa dilimi birleştir), (b) A2'deki bileşenden "hedefe ulaşan alt-hacim"i çıkarıp yalnızca onda ara, (c) `travel_hours` için tek seferlik statik Dijkstra tablosu → admissible sezgisel. Ölçülmüş hızlanma yayınlanır (`test_planner_benchmark.py`, 08 no'lu belge §6).

**Efor:** 1–2 gün (A2 sonrası). **Wow:** orta (sunumda "22 s → X s" grafiği).

---

## A4. ✅ ⭐⭐⭐⭐ Dünya görünürlüğü (Direct-to-Earth, DTE) katmanı ve iletişim gölgesi

> **Yapıldı (4 Eylül 2026, `berke-3d-backendEnhance`):** `earth_visibility` katmanı, `/api/earth-series`, `/api/comm-window`, `/api/plan-4d` `require_earth_visibility`, `/api/replan` ve `/api/pose` için hesaplanan `comm_minutes_remaining`. NASA LOLA "Average Earth Visibility" (PGDA 69, 60 m) ile karşılaştırma: **RMSE 0,087, Pearson r 0,96, 0,5 eşiğinde anlaşmazlık %9,4** (1 681 hücre) — ayrıntı [earth_visibility_validation.md](earth_visibility_validation.md). Doğrulama iki önceden var olan hatayı ortaya çıkardı ve kapattı: yerel gridlerin Site01 kalması ve 10 km ışın menzilinin uzak ufku kesmesi (ufuk küpü artık LOLA 40 m DEM ile 150 km'ye kadar iki ölçekli). Tasarım: [../superpowers/specs/2026-09-03-a4-dte-katmani-design.md](../superpowers/specs/2026-09-03-a4-dte-katmani-design.md).

**Ne:** Her hücre ve zaman dilimi için Dünya'nın ufkun üstünde olup olmadığı; buradan "iletişim gölgesi" haritası, "time-to-DSN-shadow" metriği ve A1'deki safe-haven kuralı için gerekli girdi.

**Kim / yöntem:** NASA GSFC LOLA ekibi — Mazarico vd. (2011) ufuk yöntemi; VIPER için zorunlu kısıt ("site dört ölçütü de sağlamalı: volatil, güneş, geçilebilir arazi, DTE").

**Linkler:**
- [Mazarico vd., Illumination conditions of the lunar polar regions using LOLA topography, Icarus 211 (2011)](https://www.researchgate.net/publication/251730356_Illumination_conditions_of_the_lunar_polar_regions_using_LOLA_topography)
- [PGDA "Lunar Polar Illumination" ürünleri — ortalama aydınlanma, PSR, **ortalama Dünya görünürlüğü**, gökyüzü görünürlüğü; 240/120/60 m; 18,6 yıl, saatlik](https://pgda.gsfc.nasa.gov/products/69)
- [NASA SVS 5027 — Güney kutbu aydınlanma animasyonu 2025–2028, 2 saat adım, DE421, 17.532 kare](https://svs.gsfc.nasa.gov/5027/)
- [Heldmann vd., Site selection and traverse planning… Haworth Crater, Acta Astronautica 127 (2016)](https://ui.adsabs.harvard.edu/abs/2016AcAau.127..308H/abstract) — Resource Prospector için DTE + güneş + eğim üçlü kısıt; traverse, terminatör batıya kayarken doğuya ilerler.
- [JPL IPN Progress Report 42-176: Lunar Pole Illumination and Communications Maps (Goldstone radar DEM)](https://ipnpr.jpl.nasa.gov/progress_report/42-176/176C.pdf) — en iyi sitede çok yıllık ortalama güneş %92, DTE %51.

**Detaylı açıklama:** Mazarico yöntemi, her hücre için azimut başına ufuk yükseklik açısı hesaplar ve gök cisminin (Güneş **veya Dünya**) yükseklik açısıyla karşılaştırır. LunaPath'in `horizon_map` çıktısı zaten tam bu ufuk küpüdür. Tek eksik: `ephemeris.sun_vector_body` yerine `spkpos("EARTH", ...)` ile Dünya vektörü; aynı `true_north_grid_azimuth` düzeltmesi geçerlidir. Kutupta Dünya'nın yükseklik açısı ±~6,7° arasında (libration) salınır; bu yüzden Dünya "görünürlüğü" saatler değil **günler** ölçeğinde değişir.

**LunaPath'te bugün:** `replan_triggers.check_comm_window` var ama girdisi (`comm_minutes_remaining`) hesaplanmıyor, dışarıdan bekleniyor. Dünya vektörü hiçbir yerde yok (grep ile doğrulandı).

**Somut katkı:**
1. `ephemeris.earth_track(...)` (5 satır: `SUN` → `EARTH`) + `illumination.illuminated_mask` aynı fonksiyonla → `earth_visible[t,y,x]`.
2. Katman `earth_visibility_fraction` (`layer_validity: DERIVED`), `/api/layers/earth_visibility`, `/api/illumination-series`'e paralel `/api/earth-series`.
3. Maliyet/kısıt: (a) "sürüş yalnızca DTE varken" seçeneği (VIPER teleoperasyon kuralı), (b) PSR girişleri hariç, (c) `comm_minutes_remaining` artık hesaplanıyor → mevcut tetikleyici gerçek veriyle çalışır.
4. **Doğrulama:** PGDA'nın 240 m "Average Earth Visibility" ürünü indirilip LunaPath'in uzun-dönem ortalamasıyla RMSE/korelasyon → **projenin ilk gerçek validation sayısı** (skorkart 4. boyut 1/5 → 2/5).

**Not (hackathon karşılaştırması):** ISRO Bharatiya Antariksh Hackathon 2026'daki iki proje bile Earth-LOS cezasını koymuş (bkz. Bölüm E). LunaPath'te bunun olmaması jüri gözünde eksik durur.

**Efor:** 1–2 gün. **Wow:** yüksek; validation ile birleşince çok yüksek.

---

## A5. ⭐⭐⭐ Zaman pencereli bilim-istasyonu sıralaması (cost-constrained TSP) ve görev zaman çizelgesi

**Ne:** Birden çok hedef noktayı (science station) hangi sırayla, hangi Ay gününde ziyaret edeceğini; "sürüşler güneşte, ziyaretler güneşte, toplam süre Dünya'nın ufkun üstünde olduğu süreyi aşmasın" kısıtlarıyla çözmek.

**Kim:**
- NASA VIPER "Traverse Planning Algorithm #1": **maliyet-kısıtlı, zaman pencereli, alt-küme seçen gezgin satıcı** (ziyaret edilen istasyon sayısını maksimize et; sürüş maliyeti = zaman; toplam ≤ Dünya-üstte süresi). Nobile/Haworth/Shoemaker site seçimi bununla yapıldı; sonra MCTS'e geçildi. [Shirley & Balaban 2022 (PDF)](https://www.nasa.gov/wp-content/uploads/2022/05/overview_of_mission_planning_for_the_viper_rover.pdf)
- Polytechnique Montréal — Chen, Jackson, Allard, Beltrame: [Path planning algorithm for a South Pole lunar rover mission, Acta Astronautica 237 (Aralık 2025) 349–360](https://www.sciencedirect.com/science/article/pii/S0094576525004898) — önce zamana bağlı tentatif sıra, sonra rota ile doğrulama; manuel planlamadan daha kısa süre/mesafe (abstract düzeyi; tam metin erişilemedi).

**LunaPath'te bugün:** `/api/plan-multi` ve `/api/compare` var ama sıralama (ordering) ve zaman penceresi yok.

**Somut katkı:** `/api/plan-mission`: girdi = hedef listesi + görev başlangıç zamanı; çözücü = OR-Tools CP-SAT (Apache-2.0) ile zaman pencereli TSP; sürüş maliyetleri `pathfinder_4d`'den; çıktı = Ay günü bazlı leg listesi (VIPER formatı) + ziyaret edilen istasyon sayısı + kaçırılanlar. **Wow:** "tek rota" yerine "tam görev zaman çizelgesi".

**Efor:** 3–4 gün. Challenge etkisi orta (Modül 6 "alternatif rota" ve Modül 7 "senaryo runner"a hizmet eder).

---

# BÖLÜM B — Belirsizlik, risk ve doğrulama (skorkartın en zayıf boyutu)

## B1. ✅ ⭐⭐⭐⭐⭐ Stokastik reach-avoid "kurtarma politikası" ve şans-kısıtlı görev planlama

> **Yapıldı (5 Eylül 2026, `berke-3d-backendEnhance`):** Toronto STARS'ın (Lamarre, Malhotra, Kelly; Acta Astronautica 2023 arXiv 2307.16786, IEEE AERO 2024 arXiv 2401.08558 — HTML'leri okundu, DP denklemi / üç sonuçlu Poisson arıza modeli / φ_L-φ_U min-max eşlemesi / güvenli küme doğrulandı; `gplanetary-nav` klonunda kurtarma politikası kodu **yok**, yalnız harita-graf-güneş kütüphanesi) reach-avoid formülasyonu LunaPath'in kendi kaba gridi (coarsen 4, 125 × 125), SPICE gölge serisi ve `cost_engine` enerji fiziği üzerinde kuruldu: yeni `backend/app/survival.py` — durum `(zaman kutusu, blok, SOC kutusu)`, eylemler planlayıcının 8 hamlesi + bekle (`direction_tables` `_gated_edges` ile kenar kenar aynı), arıza modeli `e^{−αρ}` / `1 − e^{−αρ/2}` (kaynakta bekleme) / `e^{−αρ/2} − e^{−αρ}` (hedefte), R saat ev-içi güçte bekleme (kümülatif gölge-saat integrali), geriye doğru **tek geçişli** değer iterasyonu (her eylem ≥ 1 kutu; NumPy, yalnız ilgili hücreler toplanır) → `P_safe[t, y, x, soc]` (float32) + politika (uint8: 0–7 hamle, 8 bekle, 254 güvenli, 255 yok); `rollout` (politikayı **sürekli** saat/SOC'de izleyen Monte Carlo, Lamarre'nin doğrulaması; isteğe bağlı önce plan, arızadan sonra politika); `survival_block`, `recovery_suggestion`, 2 girişlik alan önbelleği. **α ve R VARSAYIM:** `constants.FAILURE_RATE_PER_KM_ASSUMED = 0.2` (Lamarre'nin 1/5 000 m'si), `FAULT_RECOVERY_HOURS_ASSUMED = 10`, `FAILURE_MODEL_SOURCE` `"assumption: …"`; kataloğa alan yazılmadı. **Güvenli küme Lamarre'den sapar ve bunu söyler:** sonda Site11'de LPR-1 için üç epokta da (28 Eyl, 13 Eyl 2026, 30 May 2027) **haven yok** (VIPER: 19 / 0 / **862** kaba blok) → varsayılan `leg` = hedef bloğu (SOC ≥ rezerv) ∪ haven (SOC ≥ rezerv + tam-gölge ev-içi × `h_max_shadow_h`, kapasitede kapalı — VIPER'da 13 280 Wh > 4 000 Wh, "dolu batarya" kuralı); `haven` = yalnız haven (Lamarre). Karanlık saati ve termal DP durumunda **yok** (yalnız toparlanma beklemesinde R > h_max karanlıkta ölümcül; D3 termal ihlali güvensiz-durum tanımına alınmadı, C6'ya). **En büyük bulgu (sonda, spec § bulunanlar):** Lamarre'nin "alt enerji kutusu" konservatif eşlemesi bizim rejimde kullanılamaz — hamle 20 m/19 Wh, kutu 271 Wh → her karanlık hamle tam kutu düşer (≈ 14× kötümser): Site11 gündüz çiftinde başlangıç `P_safe = 0,000`, blokların %90'ı 0. SOC ekseninde **kutu merkezleri arasında doğrusal ara değer** (Lamarre'nin karşılaştırdığı "interpolation map", beklenen değerde yansız) kullanıldı, zaman ekseninde min-max korundu; konservatiflik artık **ampirik** olarak rollout ile denetlenir ve `SURVIVAL_CLAIM` bunu söyler. `pathfinder_4d.astar_4d(survival_field, max_failure_probability)`: her etikette yürütme hayatta-kalma çarpanı `surv' = surv · (p0 + p1·P_safe(f1) + p2·P_safe(f2))` (AERO 2024'ün "arıza dallarını V_S ile kapat" kuralı; kenar çarpanı etiket anahtarı çözünürlüğünde memoize), β verilince `1 − surv > β` olan hamle `failure_probability` reddi, başlangıçta `1 − P_safe(start) > β` ise optimal politika sınırıyla anında gerekçeli ret; β yokken `surv` baskınlık ekseni **kapalı** (yalnız-rapor: düğüm sayısı ve rota alansız planlayıcıyla aynı — testte), alan yokken **bit-eşit** (standart üç 4-B rota 41 / 116 / 8 hamle aynen, gerçek grid testinde). SHERPA'ya arıza olayı (`Perturbations.fault_rate_per_km`, `fault_recovery_h`; Poisson sayı + rota boyunca düzgün konum; ilk yarı kaynakta kalkış öncesi, ikinci yarı hedefte varış sonrası bekleme; rota değişmez; varsayılan 0 → B5 bit-eşit). API (yalnızca ekleme): `/api/plan-4d` `max_failure_probability` (β), `report_survival`, `failure_rate_per_km`, `recovery_hours`, `survival_soc_bins` (varsayılan 16), `survival_safe_set`, `survival_horizon_hours`; yanıt `survival` bloğu (her zaman; `requested/applied/beta`, `failure_model` + kaynak, `field` boyutları, `route` yürütme riski / min-ort `P_safe`, `shadow_model`, `haven_model`, `quoted`, `claim`), `path_survival_prob`, `path_recovery_prob`, `metrics.execution_failure_probability`; `/api/cell-telemetry?survival=true&goal_row&goal_col&soc_pct&t_hours` → `survival {p_safe, best_action_name, next_pixel …}`; `/api/replan` `recovery_policy: true` → `recovery_suggestion`; yeni `GET /api/survival` (kaba grid `p_safe` / `best_action`, f32 `X-Layer-Validity: MODEL`); `/api/stress-test` `faults` bloğu. Alan tavanı 100 M durum (m otomatik), ufuk = plan + R + 2 × en hızlı sürüş. **Ölçüm (Site11; `scripts/recovery_policy_report.py` → [recovery_policy_report.md](recovery_policy_report.md), 49 dk):** alanlar LPR-1 gündüz 65,3 M durum (261 kutu × 0,072 h, m = 2, 311 MB, DP 96 s), Ay gecesi 68,5 M (274 × 0,108 h, m = 3, DP 136 s), VIPER kısa leg 39,8 M (159 × 0,118 h, m = 1, DP 46 s); tam SOC'de başlangıç `P_safe` **0,985 / 0,883 / 1,000**, yarım bataryada 0,972 / **0,404** / 0,761; geçilebilir blokların ≥ 0,95 payı %52 / %48 / %36; α = 0 → başlangıç 1,000 / 0,998 / 1,000 (deterministik), α = 0,5 → 0,921 / 0,581 / 1,000. Yürütme riski (α = 0,2): gündüz **%1,65**, Ay gecesi **%11,05**, VIPER **%0,08**. **β süpürmesi:** gündüz β = 0,10 / 0,05 aynı 41 hamlelik rota (0 ret), β = 0,02'de de aynı rota ama aramada 13 811 hamle reddedildi; Ay gecesinde β = 0,10 / 0,05 / 0,02 **üçü de 404**: başlangıçtan optimal kurtarma politikası bile %11,7 başarısız (10 h karanlık bekleme + 116 hamle), yani bu çift bu α'da β ≤ 0,10 ile planlanamaz — belge "risk-sınırlı plan yalnız 0,5 km / 2 h uzun" (Lamarre, alıntı) sonucunu Site11'de **yeniden üretmedi**: rotalar ya aynı ya da olanaksız; VIPER kısa leg her β'da aynı 8 hamle. **Tahmin ≥ gerçekleşen (1 000 koşum, Wilson %95):** gündüz politika %1,51 ≥ %1,20 [0,69–2,09], plan + politika %1,65 ≥ %1,00; Ay gecesi politika %11,7 ≥ %4,6 [3,5–6,1], plan + politika %11,1 ≥ %4,0 — **konservatif, üç çiftte de tutuyor**, Ay gecesinde 2,5× fazla (zaman kutusu kötümserliği: her hamle ≥ 0,108 h); SHERPA sabit rota + arıza (σ = 0): üç çiftte tamamlanma **%100** (10 h bekleme rezervi tüketmiyor), SHERPA'nın kendi σ'larıyla + arıza: %100 / %94,1 (59 batarya) / %98,2. Katı haven kümesi VIPER 30 May 2027: 862 blok, 51,3 M durum, ort. `P_safe` 0,725, ≥ 0,95 %44, = 0 %4; LPR-1'de boş → `P_safe ≡ 0` (rapor § 2). **Kurtarma önerisi** (Ay gecesi, `/api/replan`): başlangıçtan **S** (piksel 190,34; `P_safe` 0,883 → 0,884); rota ortası durum (97,57, dilim 105, SOC %82) → **E** 0,969; yarım batarya → E 0,860; 10 h arıza sonrası (SOC %70, t = 13,8 h) → E 0,763. Süreler: alan 46–136 s (≈ 0,35–0,5 s/kutu); planlayıcı alanla gündüz 10–11 s (alansız 7 s), Ay gecesi 43 s (alansız 22 s), VIPER kısa leg 3 s (alansız 3 s); ilk çağrı alan kurma dahil 48–145 s. Tasarım: [spec](../superpowers/specs/2026-09-05-b1-recovery-policy-design.md) (sondalar, sapmalar, ölçümler), [plan](../superpowers/plans/2026-09-05-b1-recovery-policy.md). **Sapmalar:** SOC ara değeri (yukarıda); tavan 40 M → 100 M, K 20 → 16; yalnız-rapor modunda `surv` ekseni kapalı; kapasite eşiği "dolu batarya"; gölge serisi uzatması 64'er dilim kabalaştırılarak (ince seri 1,3 GB'a çıkıyordu); rollout'ta planlanan bekleme bir dilim; `/api/replan` önerisi tetikleyici ateşlemese de döner; TEMPEST yörünge-düzeyi arama ve waypoint ekseni kapsam dışı (A5). Testler: 33 birim (`test_survival.py`: Lamarre denklemleri, `direction_tables` ↔ `_gated_edges`, elle DP kapalı formları, monotonluk, min-max, karanlık bekleme, ara değer yansızlığı, rollout ↔ kapalı form, planlayıcı bit-eşitliği/β/erken ret, yalnız-rapor düğüm eşitliği) + 12 API (`test_survival_api.py`) + 4 SHERPA arıza (`test_stress_test_runs.py`) + 5 skip-korumalı gerçek grid (`test_survival_real_grid.py`: 41 / 116 / 8 hamle aynen, β sınırı, α = 0 deterministik, VIPER haven kümesi > 0, LPR-1 haven kümesi boş; 5 dk 37 s); tam paket 1 443 passed, 4 skipped (43 dk 1 s bu makinede; D2'nin 13 dk 49 s'sine karşı fark B1'den değil — A/B'de alansız planlayıcı eski koda karşı aynı düğüm sayısı ve ±%5 süre, `test_plan_4d_real_grid`'in 12 rastgele çifti tek başına 15,6 dk; B1'in 5 gerçek-grid testi ≈ 5 dk; skip'lerin ikisi D2'nin `LUNAPATH_PPB_DIR` klon testleri — bu koşumda ortam değişkeni yok — ikisi önceden var olan; tek uyarı önceden var olan `test_visibility_validation`'ınki; D2'deki 1 391'e +54 yeni test, −2 klon testi).

**Ne:** Rover'ın durumu (hücre, zaman, batarya) üzerinden **her durumdan güvenli konuma ulaşma olasılığını** dinamik programlamayla hesaplamak; sonra rota planlayıcıyı "başarısızlık olasılığı ≤ β" kısıtıyla çalıştırmak.

**Kim:** University of Toronto STARS Lab — Olivier Lamarre, Shantanu Malhotra, Jonathan Kelly. (10 no'lu belgede D1 olarak listelenmişti; burada **uygulanabilir formülasyon ve sayılar** veriliyor.)

**Linkler:**
- [Recovery Policies for Safe Exploration of Lunar PSRs by a Solar-Powered Rover (arXiv 2307.16786; Acta Astronautica 2023)](https://arxiv.org/abs/2307.16786)
- [Safe Mission-Level Path Planning for Exploration of Lunar Shadowed Regions (arXiv 2401.08558, IEEE AERO 2024)](https://arxiv.org/html/2401.08558v2)
- [utiasSTARS/gplanetary-nav (MIT lisans) — arazi + güneşlenme haritaları, planlama grafı, güneş gücü tahmini](https://github.com/utiasSTARS/gplanetary-nav)

**Detaylı açıklama (uygulanabilir düzeyde):**
- **Durum:** (c, t, b) — hücre, zaman, batarya enerjisi. **Eylemler:** 8 yön + "bekle" (5.000 s).
- **Arıza modeli:** Poisson, uzamsal oran α (ör. **5 km'de 1 arıza, 10 saat toparlanma**); sürüş iki yarıya bölünür, üç sonuç (nominal / ilk yarıda arıza / ikinci yarıda arıza).
- **Değer iterasyonu:** V(x)=1 güvensiz, 0 güvenli; V_k(x) = min_a E[V_{k+1}(f(x,a))]; ayrıklaştırma hatasına karşı **min-max konservatif** eşleme (komşu zaman kutularından riski büyük olanı al).
- **Enerji modeli:** güneş = görünür disk yüzdesi × panel alanı × verim × 1.367 W/m²; sürüş 60–300 W, bekleme 40–80 W, hibernasyon 30–40 W; batarya 10–30 kWh.
- **Veri:** 240 m/px, **saatlik** güneşlenme (JPL), Cabeus / LCROSS bölgesi, 2029 Ağustos–Ekim, 2.089 saatlik harita.
- **Sonuçlar:** LCROSS senaryosu **41,5 milyon durum**; tahmin edilen risk %0,4–9,8, gerçekleşen %0,0–4,6 (100.000 deneme) — konservatiflik korunmuş. Şans-kısıtlı görev: hedef β=%2 → gerçekleşen %1,5; **21 km** traverse, β=%5, risk-sınırlı plan risk-bilmez plandan yalnızca **0,5 km ve 2 saat** daha uzun.
- Safe haven kuralı: Ay gecesine girmeden **SOC ≥ %50 (15 kWh kapasitede)** ile SH'da olmak.

**LunaPath'te bugün:** deterministik 4B A*; arıza modeli yok; olasılık yok.

**Somut katkı:**
1. `survival.py`: mevcut `cost_cube` dilimlerini (t) ve `wait_cost` enerji fiziğini kullanarak (c, t, SOC_bin) üzerinde geri değer iterasyonu → `P_safe[t, y, x, soc]`. Grid 500×500 yerine `coarsen=4`'te (125×125) × 48 dilim × 20 SOC kutusu ≈ 15 M durum — Lamarre'nin 41,5 M'sinin altında; NumPy ile dakikalar.
2. Yeni katman `survival_probability` (MODEL etiketli) ve `/api/cell-telemetry`'de "bu hücreden bu saatte %X ihtimalle kurtulursun".
3. `pathfinder_4d`'e `max_failure_probability` parametresi: kenar geçişinde P_safe(hedef durum) ≥ 1−β kısıtı.
4. **Kurtarma politikası** çıktısı: her durum için en iyi eylem (argmin) → `/api/replan` bunu "acil durum önerisi" olarak döndürür (replan tetikleyicileri zaten var).

**Neden wow ve neden challenge'ın kalbi:** Challenge belgesi "termal ihlal durumunda fail mantığı mı, risk artışı mı?" (6.3) diye soruyor; bu özellik ikisini birleştirir: risk **sayı** olur ve rota o sayıya göre sınırlanır. 11 no'lu belgede "Lamarre'nin tüm katkısı bu eksende" deniyordu; burada o katkı LunaPath'e taşınır.

**Efor:** 5–8 gün (en pahalı ama en değerli kalem). **Bağımlılık:** A1/A4 (safe haven kümesi) önce yapılırsa daha anlamlı.

---

## B2. ✅ ⭐⭐⭐⭐ CVaR tabanlı risk-farkında maliyet (slip ve termal dağılımlarından)

> **Yapıldı (5 Eylül 2026, `berke-3d-backendEnhance`):** Yeni `backend/app/risk.py`: normal dağılım için kapalı form `CVaR_α = μ + σ·φ(z_α)/(1−α)` (`cvar_multiplier`; 2 M örnekli Monte Carlo ile doğrulandı; **α = 0,5 ortalama DEĞİL**, μ + 0,798σ; nominal = `risk_alpha` verilmemesi, grid v4 ile **bit-eşit** — Site11'de SHA-256 kilidi testte), slip kuyruğu `slip_cvar` (C3 çapa σ'sı ⊕ B3 eğim σ'sının delta yöntemiyle slip'e taşınması, log-doğrusal parçada `ds/dθ = k·s`; kap 0,9), eğim kuyruğu `slope_cvar = min(slope_max, θ + σ_θ·m_α)`, vektörize eşler skalerle bit-eşit (4 rover × 100 000 θ), `route_risk_summary` (rotanın ort./maks CVaR slip'i, risk-ayarlı saat/Wh `t·(1−μ)/(1−s_α)`), `risk_block`, `sigma_sources`; termal `thermal_cvar_cold_c` yalnızca **imza** (kaynaklı σ yok; ölçüldü: `f_thermal` Site11'de LPR-1 hücrelerinin %72,7'sinde, VIPER'ın %54,2'sinde zaten ≥ 0,99, aralık/4 soğuk kuyruğu α = 0,9'da bunu %94,0 / %81,2'ye çıkarıyor — doygunluk ekler, ayrım eklemez; C5/C6'ya). **α yalnızca sıralama maliyetine girer:** `f_slope` (eğim kuyruğu; `inf` kapısı nominal θ'da, geçilebilirlik α'dan bağımsız) ve `f_energy_cell` (slip kuyruğu; ölçek C3'ün slip'siz best/worst'ü) skaler ↔ `cost_vec` grid 1e-12; `compute_cost_grid`, `costmap` katmanları, `cost_cube` (`slope_sigma` blok-maks) α ve `slope_sigma` alır; `rover_grids.grids_for_rover(risk_alpha)` gridi `metadata["risk_alpha"]` ile anahtarlar ve klon `slope_sigma`'sını ekler; **süre, batarya, D3 marjları, B5 Monte Carlo, koridor bütçeleri ve safe-haven süreleri ortalama slip fiziğinde kalır** (fiziğe α reddedildi: nominali α'ya bağımlı kılar, B5'in hız/güç dağılımlarıyla çifte sayım). API (yalnızca ekleme): `/api/plan` ve `/api/plan-4d` `risk_alpha` (0,5–0,999; dışı 422), yanıtlarda `risk` bloğu (`validity: MODEL`, `criteria`, `sigma_sources`, `route`: ort./maks CVaR slip, maks eğim kuyruğu, risk-ayarlı saat/Wh, `claim`); yeni `POST /api/risk-sweep` (2-B; α listesi + nominal yan yana, `risk_matrix` her rota × her α, `comparison` nominale göre Δ, "risk iştahı sürgüsü"). **Ölçüm (Site11, 100 klon; `scripts/risk_sweep_report.py` → [risk_sweep_report.md](risk_sweep_report.md)):** σ_θ medyanı 1,54° (p95 1,99°); α = 0,99'da CVaR slip medyanı 0,199 → 0,497 (LPR-1), hücrelerin %26,6'sı 0,9 kapısında, eğim kuyruğu hücrelerin %4,1'inde (VIPER %14,5) sınıra dayanıyor; maliyet sıralaması nominale Spearman 0,985 (LPR-1) / 0,970 (VIPER), ortalama +%30 / +%25; enerji kriteri doygunluğu %14,6 → %40,3 (C3'ün slip'siz ölçek kararının bedeli). 2-B ince grid (`/api/risk-sweep`): α = 0,99 rotası nominalle %49–52 örtüşüyor (VIPER kısa leg %3), nominal fizikte kazanç **küçük**: LPR-1 gündüz −4,5 Wh, min SOC +0,07 pt, maks slip 0,586 → 0,563; Ay gecesi çifti −26 Wh (−%1,8), +0,018 km, min SOC +0,39 pt; VIPER standart −29 Wh, min SOC +0,58 pt; VIPER kısa leg maks slip **0,594 → 0,627** (α rotası nominal ölçütte daha güvenli değil). Risk matrisi (her rota her α'da yeniden fiyatlandı): LPR-1 gündüz ve VIPER standart çiftlerinde α = 0,99'da en düşük risk-ayarlı sürüş saatini **nominal rota** taşıyor (3,375 vs 3,696 h; 11,45 vs 12,20 h) — ağırlıklı kriterler kuyruk süresini minimize etmiyor (enerji doygunluğu, eğim sigmoidi); yalnız Ay gecesi çiftinde α rotası kazanıyor (5,528 vs 5,563 h). 4-B (coarsen 4) + B5 (1 000 koşum): LPR-1 28 Eyl α ∈ {0,5, 0,9, 0,99} aynı 42 hamlelik rotayı seçiyor (nominal 41; örtüşme %55), varış 2,98 h aynı, min SOC %92,5 → %93,1, ort. slip 0,326 → 0,313, B5 tamamlanma %100 / rezerv içinde %99,8 (değişmedi); Ay gecesi 116 hamle, α rotası %80 örtüşüyor, varış 6,75 h / SOC %67,4 / B5 %98,8 / %88,8 aynı; VIPER kısa leg her α'da aynı rota (B5 %99,6 / %95,0). Planlama 4-B α'da 6–7 s (nominal ilk çağrı 12 s), 2-B tarama dört plan 0,7–3,4 s. Tasarım: [spec](../superpowers/specs/2026-09-05-b2-cvar-risk-cost-design.md) (sondalar ve ölçümler dahil), [plan](../superpowers/plans/2026-09-05-b2-cvar-risk-cost.md). **Sapmalar:** α eğim kriterine de girdi (sonda: yalnız enerjiyle Spearman ≥ 0,9986 ve 4-B rotası hiç değişmiyordu); `/api/risk-sweep` yalnız 2-B (4-B için `/api/plan-4d.risk_alpha`); termal CVaR kanca; `COST_MODEL_ID` v4 kaldı (None yolu değişmedi); `/api/compare` ve `/api/plan-multi` α almıyor; Endo'nun "%11 → %95" sayıları alıntı olarak kaldı, bizim etkimiz küçük ve öyle yazıldı. Testler: 40 birim (kapalı form ↔ Monte Carlo, türev, kap, parite) + 16 maliyet yolu (skaler ↔ grid 1e-12, None bit-eşit, α monotonluğu, küp, önbellek anahtarı) + 13 API (422'ler, bloklar, tarama) + 5 skip-korumalı gerçek grid (v4 SHA kilidi, klon σ, 4-B tarama, `/api/risk-sweep`); tam paket 1 250 passed, 2 skipped (12:33).


**Ne:** Bir hücrenin maliyetini tek bir sayı yerine **dağılım** olarak ele alıp, "en kötü α'lık kuyruğun ortalaması" (Conditional Value-at-Risk) ile deterministik maliyete çevirmek. α, operatörün risk iştahı olur.

**Kim:**
- NASA JPL / Caltech — David Fan, Kyohei Otsu, Ali Agha-mohammadi vd.: **STEP** (DARPA Subterranean Challenge'da sahada kullanıldı). [arXiv 2103.02828 (RSS 2021)](https://arxiv.org/abs/2103.02828) · [Genişletilmiş sürüm, arXiv 2303.01614](https://arxiv.org/pdf/2303.01614)
- Keio Üniversitesi Ishigami Lab — Masafumi Endo vd.: **Mixture-of-Gaussian-Processes + CVaR**, [Risk-aware Path Planning via Probabilistic Fusion of Traversability Prediction (ICRA 2023, arXiv 2303.01169)](https://arxiv.org/abs/2303.01169): belirsiz görünümlü arazide başarı oranı **%11 → %95**, maksimum slip **%92,9 → %63,7** (sentetik veri, simülasyon).
- Aynı grubun devamı: [Deep Probabilistic Traversability with Test-time Adaptation (Sci. Rep. 2026, arXiv 2409.00641)](https://arxiv.org/html/2409.00641) — 10 no'lu belgede zaten var.

**Detaylı açıklama:** Slip s ~ p(s | eğim, arazi sınıfı); sınıf belirsizliği ile GP belirsizliği karıştırılır (∑_c P(c)·p(s|c)); risk = CVaR_α(slip) → seyahat süresi/enerji maliyetine dönüşür; A* aynen kalır. STEP aynı fikri çarpışma/basamak/slip risklerini birleştirerek MPC ile kullanır.

**LunaPath'te bugün:** `slip_model.py` deterministik ve kalibre edilmemiş; termal maliyet `f_thermal` deterministik.

**Somut katkı:** `cost_engine`'e `risk_alpha` parametresi; slip (C3'teki kalibrasyonla) ve iç sıcaklık için μ±σ; CVaR_α kapalı form (normal dağılım için μ + σ·φ(z_α)/(1−α)) → maliyet. `/api/plan`'a `risk_alpha` alanı; `/api/compare` ile α=0,5 / 0,9 / 0,99 rotaları yan yana. **Wow:** "risk iştahı sürgüsü" — jüriye canlı gösterilebilir. 

**Efor:** 2 gün. Challenge etkisi: 6.3 sorusunun "soft penalty" tarafını matematiksel olarak temellendirir.

---

## B3. ✅ ⭐⭐⭐⭐⭐ DEM hata yayılımı: NASA'nın 100 DEM klonuyla Monte Carlo → olasılıksal geçilebilirlik ve aydınlanma

> **Yapıldı (4 Eylül 2026, `berke-3d-backendEnhance`):** NASA PGDA'nın Site11 için yayınladığı **100 DEM klonunun tamamı** planlama penceresi için indirildi (`scripts/build_dem_clone_cache.py`; klon başına yalnızca 1 km dolgulu satır bandı, `/vsicurl/` ile 4 paralel bağlantı, 20 klon 452 s + 80 klon 1.889 s; sunucu tek bağlantıda ~170 KB/s). Bulgu: `_err.tif` klonları tam yüzey DEM'i, hata gerçekleşmesi `klon − surf`; 100 klonun hepsi sağlamayı geçti (`klon − surf` ortalaması −0,011 m, RMS 0,449 m = NASA `toterr` RMS'i 0,449 m; `toterr` medyanı 0,373 m NASA'nın 0,30–0,50 m aralığında, `slperr` medyanı 1,73°). `uncertainty.py`: her klon üretimle **aynı** eğim operatörü, geçilebilirlik kuralı ve ufuk yürüyücüsünden geçiyor → `p_traversable`, `slope_sigma` (+ NASA `elevation_sigma`/`slope_sigma_nasa`, MODEL etiketli) `/api/terrain` manifestinde; klon başına ufuk küpü plan-4d blok merkezlerinde (yakın 1 km klonlanmış, uzak alan sabit ve `neglected_horizon_shift_deg_max` ≤ 0,021° olarak raporlanıyor; yüzeyin iki-geçişli küpü üretim küpüyle **0,0°** farkla birebir) → `GET /api/uncertainty-series` (`p_illuminated[t]`); `POST /api/dem-uncertainty` rota bandı (B5'in `route_legs` + `simulate_runs`'ı klon başına, SHERPA σ = 0; isteğe bağlı birleşim); `/api/plan` ve `/api/plan-4d` yanıtına ucuz `uncertainty` bloğu (yalnızca klon varken). **Ölçüm (Site11, 100 klon):** eğim σ medyanı 1,52° vs NASA 1,73° (oran 0,88, korelasyon 0,42); klon eğimleri yüzeyden sistematik yüksek (medyan +0,16°, gürültü gradyanı şişirir) → VIPER haven→haven rotasında sürüş enerjisi p5/p50/p95 **2.258 / 2.293 / 2.334 Wh**, yüzey DEM'iyle nominal 2.127 Wh (bant nominalin %6–10 üstünde; en iyi tahmin DEM'i iyimser); VIPER için hücrelerin **%8,2'si** belirsiz geçilebilirlikte (LPR-1 %2,8); 30 Mayıs 2027'de hücrelerin **%10,8'i** (p50, 48 h) aydınlık/karanlık olarak kararsız; VIPER rotası plan-4d'nin blok-VE kuralıyla 100 klonun yalnızca **1'inde** tam geçilebilir (en düşük hücre P 0,27); SHERPA + klon birleşik tamamlanma **%17,8** (B5'te yüzey DEM'iyle %29,6). LPR-1 rotası 99/100 klonda geçilebilir, tamamlanma %100. Yakınsama: N=20'de tam topluluğa ort. |ΔP| 0,007, N=50'de 0,003. Süreler: klon başına ufuk 2,5 s, seri 0,2–0,4 s, band 1–4 s. Rapor: [dem_uncertainty_report.md](dem_uncertainty_report.md). Tasarım: [../superpowers/specs/2026-09-04-b3-dem-uncertainty-design.md](../superpowers/specs/2026-09-04-b3-dem-uncertainty-design.md). Sapmalar: termal alan ve Dünya görünürlüğü klonlanmadı (sabit, provenance söylüyor); yakın geçiş `np.rint` eşitlik kırılması yüzünden üretim bağlamıyla aynı indekslerdeki tuvalde koşuluyor; `duration_h` B5 politikasıyla dilim boşluğunu aşmadıkça değişmiyor (DEM'e duyarlı metrikler `drive_hours`/`gross_drive_wh`); `/api/compare` değişmedi.

**Ne:** Yükseklik modelinin hatasını eğim, ufuk ve gölgeye yaymak; her hücre için P(geçilebilir), P(aydınlık, t) ve rota metriklerine güven aralığı üretmek.

**Kim:** NASA GSFC Planetary Geodesy — Michael Barker, Erwan Mazarico vd. **NASA'nın kendisi her 5 m/px güney kutbu DEM'i için Z-belirsizlik, eğim-belirsizlik haritaları ve 100 istatistiksel klon yayınlıyor.**

**Linkler:**
- [PGDA — High-Resolution LOLA Topography for Lunar South Pole Sites (28 site; LDEM, eğim, **Z uncertainty**, **slope uncertainty**, **100 clones**)](https://pgda.gsfc.nasa.gov/products/78)
- [Barker vd., Improved LOLA elevation maps for south pole landing sites: Error estimates and their impact on illumination conditions, PSS (2021)](https://www.sciencedirect.com/science/article/abs/pii/S0032063320303329) — paywall; PGDA sayfasındaki sayılar: medyan RMS Z hatası **0,30–0,50 m**, medyan RMS eğim hatası **1,5–2,5°**, iz konumlandırma **10–20 cm yatay, 2–4 cm düşey**.
- Genel yöntem: [Deep Probabilistic Traversability (arXiv 2409.00641)](https://arxiv.org/html/2409.00641); arkeolojide en-düşük-maliyet-yol için Monte Carlo DEM hatası: [Lewis 2021, JAMT](https://link.springer.com/article/10.1007/s10816-021-09522-w).

**LunaPath'te bugün:** tek DEM, tek eğim, tek ufuk; belirsizlik yok (skorkart boyut 5 = 1/5).

**Somut katkı:**
1. Sevk edilen 5 m grid Site 11 ise (metadata'daki `NAC_SITE11`), PGDA'dan Site 11'in klonları indirilir; yoksa klonlar **eğim-belirsizlik haritasından** sentezlenir (`z + N(0, σ_z)` + uzamsal korelasyon).
2. `uncertainty.py`: N klon → N eğim → N geçilebilirlik maskesi → `P_traversable`; N ufuk → N gölge serisi → `P_illuminated[t]`. (Ufuk hesabı pahalı: N=20 ile başlanır, `coarsen` kullanılır.)
3. Rota metriklerinde **band**: N klonda aynı rota simüle edilir → enerji, süre, gölge saati için %5–%95 aralığı. `/api/plan` yanıtına `uncertainty` bloğu.
4. Provenance: `P_*` katmanları `DERIVED`, girdi pedigree'si NASA-STD-7009 "Results Uncertainty" faktörünü karşılar.

**Neden wow:** "NASA'nın yayınladığı 100 hata klonunu doğrudan Monte Carlo'ya soktuk; rotamızın enerji tüketimi 5,4 ± 0,6 kWh" — jüri için "belirsizlik nicelemesi" kutusu bir günde işaretlenir. Aynı zamanda 11 no'lu belgedeki "ufuk menzili sınırlaması" (§2.3) belirsizlik olarak dürüstçe raporlanır.

**Efor:** 2–3 gün. **Doğruluk kanıtı:** hata sayıları NASA'nın kendi ürününden.

---

## B4. ⭐⭐⭐ Global duyarlılık analizi (Sobol / SALib) — "hangi kriter gerçekten önemli?"

**Ne:** Maliyet ağırlıkları, rover parametreleri (kütle, F_net, batarya, ısıtıcı gücü) ve fizik sabitlerinin rota metriklerine katkısını **varyans ayrıştırmasıyla** (Sobol birinci-derece ve toplam indeksler, Saltelli örnekleme) ölçmek.

**Kim / araç:** [SALib — Sensitivity Analysis Library in Python (MIT)](https://www.researchgate.net/publication/312204236_SALib_An_open-source_Python_library_for_Sensitivity_Analysis); rover tasarım uzayında kullanımına örnek: [RoverDevKit (arXiv 2606.21755, 2026)](https://arxiv.org/abs/2606.21755) NSGA-II Pareto cepheleriyle tasarım duyarlılığı.

**LunaPath'te bugün:** yok; 11 no'lu belge ablasyon (A/B/C/D) istiyor, Sobol bunun nicel genellemesidir.

**Somut katkı:** `scripts/sensitivity_sobol.py`: 4 ağırlık + 6 rover parametresi → Saltelli N=512 → `plan` koşumu (coarsen ile) → çıktı: toplam enerji, süre, gölge saati, min iç sıcaklık için S1/ST tabloları. Beklenen (ve sunulabilir) bulgu: 11 no'lu belgedeki termal-eğim ρ=0,98 sorunu Sobol'da "w_thermal'ın toplam indeksi ~0" olarak görünür — **hatanın kendisi bir sunum slaydı olur** ve düzeltme sonrası tekrar ölçülür.

**Efor:** 1–2 gün. Wow: orta-yüksek (akademik jüri için yüksek).

---

## B5. ✅ ⭐⭐⭐⭐ Monte Carlo traverse stres testi — SHERPA "Traverse Evaluation" dağılımları ve metrik seti

> **Yapıldı (4 Eylül 2026, `berke-3d-backendEnhance`):** `stress_test.py` — SHERPA'nın kesik Gauss dağılımları birebir (gecikme σ 2 h, batarya σ %20 aşağı, güç σ %20 yukarı, hız σ %20/30/40/50 aşağı; DSN kesintisi ve SEP olayı olasılıkla, varsayılan 0 — yayınlanmış oran yok), "önde iken bekle, geride iken şarj molasını atla ve gölgeden bataryayla geç" politikası, planlayıcının kendi enerji aritmetiği (`move_battery_drain_wh` / `wait_battery_drain_wh`) rota-yerel gökyüzü sütunlarıyla N koşum üzerinde vektörize; `POST /api/stress-test` (Wilson %95 aralıklı tamamlanma / rezerv-içi / tam başarı oranları, ilk-neden arıza sayıları, SHERPA metriklerinin p5/p50/p95'i, histogramlar, durum başına varış/batarya zarfı, nominal koşum, karar). Ön koşul kapatıldı: `simulate_path` sürüşte güneş gelirini sayıyor (11 no'lu belge §2.3 madde 3; planlayıcı, 2-B simülatör ve MC aynı üç fonksiyon). **Ölçüm (Site11, 1.000 koşum, 1–2,4 s):** VIPER'ın haven→haven planı (30 Mayıs 2027, 40 hareket, 7,4 h, planlayıcıya göre en düşük batarya %32) nominalde hedefe varıyor ama SHERPA dağılımları altında yalnızca **%29,6** (CI 26,9–32,5) tamamlıyor, hız σ %50'de %15,8; arızaların hepsi batarya tükenmesi, tam başarı %1,4. LPR-1'in 28 Eylül 2026 rotası (2,2 h) her σ'da %100 tamamlıyor (en düşük batarya p5 %46–52), tam başarı %0 — o Ay gününde haven yok (A1). Bulgu: planlayıcı hareket süresini dilime yukarı yuvarlarken enerjiyi yalnızca sürüş süresi için düşüyor; nominal MC koşumu aradaki bekleme idaresini de sayınca VIPER rotasının en düşük bataryası %23'e iniyor — 4-B planlayıcı için açık bir düzeltme maddesi. Rapor: [stress_test_report.md](stress_test_report.md). Tasarım: [../superpowers/specs/2026-09-04-b5-stress-test-design.md](../superpowers/specs/2026-09-04-b5-stress-test-design.md). Sapmalar: aktivite süresi dağılımı uygulanmadı (rotada bilim aktivitesi yok, A5); `/api/compare` değiştirilmedi (2-B rotalar zamansız) — iki rotayı kıyaslamak iki `/api/stress-test` çağrısı, `verdict` ve `rates.*.ci95` kıyas anahtarı.

**Ne:** Planlanan rotayı, VIPER ekibinin kullandığı **aynı belirsizlik dağılımlarıyla** binlerce kez simüle edip başarı oranı ve gölge/iletişim/batarya marjlarının dağılımını üretmek.

**Kim:** NASA Ames SHERPA — Balaban, Shirley, Booth vd.

**Linkler:** [Shirley & Balaban 2022 (PDF, "Traverse Evaluation use case")](https://www.nasa.gov/wp-content/uploads/2022/05/overview_of_mission_planning_for_the_viper_rover.pdf) · [SHERPA SpaceOps 2025 (PDF)](https://publications.spaceops.org/2025/download.php?doc=559__4nupk3n2.pdf) · [NASA blog: AI and NASA's First Robotic Lunar Rover (Part 1)](https://www.nasa.gov/blogs/missions/2023/12/01/part-1-artificial-intelligence-and-nasas-first-robotic-lunar-rover/)

**Detaylı açıklama — VIPER'ın enjekte ettiği belirsizlikler (kesik Gauss):**

| Değişken | Dağılım | Ortalama | Std. sapma |
|---|---|---|---|
| Başlangıç zamanı | kesik Gauss (gecikme yönünde) | planlanan | **2 saat** |
| Başlangıç batarya | kesik Gauss (aşağı) | tam şarj | **%20** |
| Güç çekişi | kesik Gauss (yukarı) | CBE | **%20** |
| Etkin hız (SMG) | kesik Gauss (aşağı) | CBE | **%20/30/40/50** |
| Aktivite süresi | kesik Gauss (yukarı) | CBE | **%20** |
| DSN kesintisi, SEP olayı | modellenmiş olasılıkla enjekte | — | — |

Yürütme politikası (insan operatörü temsil eder): geride kalınca şarj molaları kısaltılır, opsiyonel aktiviteler atılır; **önde iken gölgeye rastlanırsa bekle, geride iken bataryayla gölgeden geç**.

**Hesaplanan metrikler (SHERPA listesi):** tamamlanma oranı, tam başarı oranı, ziyaret edilen istasyon/PSR sayısı, süre (normalize), odometri, **time-to-sun-shadow (min, ort)**, **time-to-DSN-shadow**, **time-to-0-SOC**, DSN gölge olay sayısı ve süresi, ISR mesafe birikimi, SEP istatistikleri — hepsinin std. sapması.

**LunaPath'te bugün:** `simulation.simulate_path` tek deterministik koşum; "sihirli yeniden şarj" sorunu var (11 no'lu belge §2.3).

**Somut katkı:**
1. Önce 11 no'lu belgenin 3. maddesi: `simulation.py` enerji fiziğini `cost_engine`/`wait_cost` ile birleştir (aksi halde MC anlamsız).
2. `/api/stress-test`: rota + N (varsayılan 1.000) → yukarıdaki dağılımlarla vektörleştirilmiş simülasyon (NumPy, saniyeler) → metrik dağılımları (p5/p50/p95) + histogram verisi.
3. Yürütme politikası: "önde/geride" kuralı `pathfinder_4d`'nin WAIT mantığıyla zaten uyumlu.
4. Çıktı `/api/compare`'a beslenir: iki rota artık "hangisi daha kısa" değil "**hangisi %95 güvenle SH'a varıyor**" diye kıyaslanır.

**Neden wow:** Jüriye "NASA'nın VIPER için kullandığı stres-test protokolünü aynı dağılım parametreleriyle uyguluyoruz" denir; sunumda tek slayt: "1.000 koşumda %97 SH'a vardı, en kötü %5'te 6 saat gölge marjı".

**Efor:** 2 gün (+ enerji birleştirmesi yarım gün).

---

# BÖLÜM C — Fizik modelini derinleştiren, ölçülmüş veriye dayanan eklemeler

## C1. ✅ ⭐⭐⭐ Güneş paneli geliş açısı ve panel geometrisi (cos i modeli)

> **Yapıldı (15 Eylül 2026, `tuna/backendEnhance`):** Yeni `backend/app/panel.py`: RoverDevKit'in (arXiv 2606.21755 § 3.4, **Jon Reifschneider / Duke University** — "Autonomous Mission Systems Lab" yalnız GitHub organizasyon adı) `cos i = sin e·cos β + cos e·sin β·cos(α☉ − ψ)` bağıntısı, **çok yüzeyli** bir dizi ve **normalize** kazanç `g = Σ_yüzey alan·max(0, cos i) / raw_ref`. **Belgeye beş düzeltme:** (1) formüldeki sembol `|λ|` (enlem), `|φ|` değil, ve kural makalede "typically" — makalenin **varsayılanı yatay dizidir**, yani `g ≡ 1` varsayılanımız RoverDevKit'in değil **Otten/Lamarre'ın** varsayımıdır; (2) "MAE %13,3" **ortanca** mutlak hatadır (ortalama %14,8), üstelik Pragyan'ın kendi kütle hatası da tesadüfen −%13,3; (3) makale 52 W ↔ 50 W için "+5%" yazıyor (aritmetik +%4) — alıntılandı, yeniden hesaplanmadı; (4) **belgenin önerdiği `p_solar_w × max(0, cos i)` geometriyi İKİ KEZ sayar**: kataloğun 410 W'ı VIPER PIP'inin *"three approximate 1 m2 solar arrays (one each on the port, starboard, and aft surfaces), generating 410 (TBR) W of total power"* toplamı, 450 W ise Bluethmann'ın (LSIC 2024, NTRS 20240013903 slayt 2) *"Solar arrays: 320W per panel (450W on corner)"* köşe değeri — ikisi de **en iyi geometrideki** sistem çıkışı; bu yüzden kazanç dizinin kendi `raw_ref`'ine bölünür (tek levhada `raw_ref = 1` ve kazanç tam olarak `max(0, cos i)`'dir); (5) "~30 kat" tek bir sayı değil, **pencereye bağlı**. **Bizim çapraz kontrolümüz (NASA'nın iki sayısı, aritmetik bizim):** üç dik yüzeyde bir yüzey dik gelişte ham kazanç 1, en iyi başlıkta (ψ₀ = 135°, Güneş iki yüzey normali arasında) **√2 = 1,414214**; NASA'nın 320 W'ından öngörü **452,5 W**, yayımlanan **450 W** → **+%0,57**. Model oranı 1,41421 ↔ yayımlanan 1,40625. **Katalog (beş alan, hepsi `"assumption:"` kaynaklı):** `panel_tilt_deg`, `panel_face_azimuths_deg`, `panel_azimuth_mode`, `panel_azimuth_deg`, `panel_geometry_source`; LPR-1 ve NASA VIPER üç yüzey (port/starboard/aft = +90 / −90 / 180°), eğim 90°, kip `free_heading` (NASA'nın kendi sürüş kipi: *"Omni-directional driving with sun on corner / Maximizing power generation"*, slayt 5; gimbal'ler yalnız HGA ve nav kameralarda, slayt 7 → dizi eklemsiz); eğimin 90° olduğu **çıkarımdır**, NASA "vertical" demiyor (NASA'nın VSAT'ı ayrı bir program). LUVMI-M ve Yutu-2 tek levha, `min(80°, |λ|)` = 80°, `sun_tracking`. `MODELLED_FIELDS`/`DECLARED_ONLY_FIELDS` bölüntüsünün **tamlığı** da ilk kez testle kilitlendi (bugüne dek yalnız ayrıklık test ediliyordu). **Bağlantı noktaları (hepsi `solar_gain=1.0` varsayılanlı, tek işlem sırasıyla `* (1.0 - ratio) * solar_gain`):** `cost_engine` (`net_energy_per_metre_wh`, `move_battery_drain_wh`, `wait_battery_drain_wh`, `f_energy_cell`), `cost_vec` ikizleri, `costmap.PlanContext.solar_gain`, `cost_cube.wait_cost`/`build_wait_cost_cube`/`build_cost_cube`, `pathfinder_4d.astar_4d(solar_gain_series=…)`, `simulation.simulate_path`, `stress_test` ve `survival`. **Üç sapma:** (a) `f_energy_cell`'in referans ölçeği `g = 1`'de **sabitlendi** (C3'ün `slip_free_view` deseni) — yoksa "en ucuz hücre" Güneş'in azimutuyla birlikte kayardı; (b) `build_wait_cost_cube`'un tekilleştirmesi kazanç verildiğinde **dilim başına** yapılıyor, bugünkü tüm-küp tablosu farklı dilimlerdeki aynı aydınlığı çökertirdi (kazanç yoksa eski yol aynen); (c) B1'in DP'sine dilim başına kazanç girmedi — `_power_terms` `p_solar_w`'yi `base_w`/`slope_w`'ye zıt işaretlerle gömüyor ve kapalı formlu drenaj buna dayanıyor, bu yüzden tek skaler geçiriliyor: alanın **kendi** ufku (plandan uzun — plan + kurtarma + 2 × en hızlı sürüş) boyunca **en küçük** kazanç, planınki değil (muhafazakâr, asla iyimser değil; `survival_model.panel_gain` raporluyor). B5 sürekli saatte ilerlediği için `RouteSky` kazanç verilince `∫(1−gölge)·g dt` kümülatifini de kuruyor ve `/api/stress-test` kendi `panel_model` alanını taşıyor: kazanç koşumun **kendi** (uzatılmış) dilimlerinden kuruluyor, yoksa `cos_incidence` ile yapılmış bir planın stres testi planın düştüğü gelir konusunda iyimser olurdu; statik gökyüzünde uygulanmıyor ve nedeni yazılıyor. **API (yalnızca ekleme):** `/api/plan-4d` `panel_model: "sun_pointed" | "cos_incidence"` (epok/kernel/geometri yoksa gerekçeli **422**), her yanıtta `panel` bloğu (geometri, kazanç serisi, beş karşı-olgu, `viper_corner_check`, `roverdevkit_quoted`), `GET /api/panel-gain`, `/api/illumination-series` ve `/api/rovers` içinde aynı blok; 2-B `/api/plan`'de `applied: false` + gerekçe (epok yok, `COST_MODEL_ID` **v5'te kaldı**). **Maliyet gridi bit-eşit:** temiz (stash'lenmiş) ağaçta ve C1'li ağaçta dört SHA-256 özeti de aynı çıkıyor — LPR-1'in ikisi checked-in değerlerle eşleşiyor, NASA VIPER'ın ikisi (`a55a2f64…`/`a3a690bb…` ↔ checked-in `593f8e46…`/`8788936c…`) **C1'den önce de** eşleşmiyordu (4af6989 VIPER'ın `slope_max_deg`'ini değiştirdi, maliyet gridi de onunla değişti). LPR-1'in özetlerinin kıpırdamaması, enerji yolundaki `solar_gain=1.0` varsayılanının gerçekten bit-eşit olduğunun kanıtıdır. **Ölçüm (Site11, `scripts/panel_cos_i_report.py` → [panel_cos_i_report.md](panel_cos_i_report.md)):** pencere merkezi −88,9205°, kutup eğimi 80°; Güneş yüksekliği bir yılda **−2,5903°…+2,5543°**, saatlerin %50,8'inde ufkun üstünde. **"~30 kat" ölçüldü:** izleyen 80° levha ÷ yatay levha oranı 28 Eyl 2026 + 48 h penceresinde **32,3**, bir sinodik ayda 46,9, bir yılda **51,1**; sinodik ay bazında **37,3 … 275,3** ve üç ayda Güneş hiç doğmadığı için **tanımsız**. Gerçek aydınlanma serisiyle (48 dilim × 0,5 h, tüm hücreler) bugünkü modelin yüzdesi: VIPER 3 yüzey **%99,96**, tek levha 80° izleyen **%98,92**, sabit kuzeye bakan %62,26, yatay **%2,78**. **Rotalar:** LPR-1 gündüz 41 hamle / 0 bekleme **her iki modelde de aynı** (maliyet 3,445393 → 3,445454, varış SOC 92,64 aynı, düğüm 31 219 → 31 222, ortalama kazanç 0,999613); Ay gecesi 116 hamle **bit-eşit** çünkü o epokta Güneş ufkun altında (kazanç serisi tümden 0) — ışık yoksa yanlış yöne bakacak bir şey de yok. **Başlık kilitli karşı-olgu (yalnız ölçüm, planlayıcı değişmedi):** gündüz rotasının 41 adımında serbest başlık ortalaması 0,999615 iken gidiş yönüne kilitli başlıkta **0,304732** (en az 0,250895) — **3,3 kat** daha az — VIPER'ın önünde panel yok, doğrudan Güneş'e sürmek hiçbir yüzü aydınlatmaz; NASA'nın "sun on corner" kipinin sebebi bu. **Sonucun dürüst özeti:** kataloğun varsaydığı geometrilerde kazanç 0,985–1,000, yani **C1 varsayılan katalogla rotayı neredeyse hiç değiştirmiyor**; çarpıcı sayılar karşı-olgulardadır ve bunlar model riskinin sınırıdır, hiçbir araç hakkında iddia değildir. **Testler:** 46 birim + 16 API + 9 skip-korumalı gerçek grid = **71**. **Düşmanca gözden geçirme** (4 bağımsız lens, her biri kendi ölçümünü koştu) **iki yanlış sayı** buldu ve ikisi de düzeltildi: (1) çok dilimli MOVE kenarı `(1−ortalama maruziyet)×ortalama kazanç` yüklüyordu, oysa maliyet küpü her dilimi kendi kazancıyla fiyatlıyor — terim kazançla birlikte çift-doğrusal olduğu için ikisi ayrışıyor ve terminatörü geçen bir kenarda fark **iki kat** (102 ↔ 205 Wh); artık ikisi de çarpımın yamuğunu kullanıyor; (2) survival skaleri `np.min` ile alanın geceye uzanan ufkundaki **tek bir karanlık dilim** yüzünden 0'a çöküyor ve dizisi hiç üretmeyen bir rover modelliyordu (tamamen aydınlık bir hücrede %30 SOC'de P_safe 1,0 → 0,904) — artık `panel.conservative_gain`: ışık **olan** dilimlerin en küçüğü. Ayrıca 5 420 Wh'ın PIP'e atfı, "dört SHA-256 kilidi" iddiası, sözleşmedeki Güneş azimutu örneği, raporun 422'yi "hamle" sütununa yazması, kesik Otten alıntısı, README'nin özelliği varsayılan açıkmış gibi anlatması ve `/api/illumination-series`'in başka bir rover'ın panelini isimsiz yayımlaması düzeltildi. Tasarım: [spec](../superpowers/specs/2026-09-15-c1-panel-cos-i-design.md), [plan](../superpowers/plans/2026-09-15-c1-panel-cos-i.md). **Not:** VIPER kısa leg (30 May 2027) bu koşumda her iki modelde de **422** ("start … not traversable at coarsen=4"); stash'lenmiş temiz checkout'ta da 422 — yani **C1'den önce de böyle**. **Ölçüldü:** tam paket C1'le **25 başarısız / 2 181 geçti / 5 atlandı** (37 dk 56 s); temiz bir HEAD worktree'sinde (gitignore'lu veri junction'lanarak) **25 başarısız / 2 102 geçti / 13 atlandı** (25 dk 34 s) ve **başarısız test listeleri birebir aynı** — yani C1 hiçbir şey kırmıyor (2 102 + 71 yeni test + 8 worktree'de erişilemeyen MoonPlanBench testi = 2 181). Kırık 25 testin hepsi `*_real_grid.py` dosyalarında, tek bir birim ya da API testi düşmüyor; çoğunluğu 4af6989'un VIPER `slope_max_deg` 20°→15° düzeltmesinin arkasından gelen aynı 422. C1 bu testlerin hiçbirine dokunmadı (özellik başına tek commit).

**Ne:** Şarj gücünü yalnızca "aydınlık oranı"yla değil, panel normali ile Güneş vektörü arasındaki açıyla (cos i) ve panel eğim/azimutuyla hesaplamak.

**Kim / kaynak:**
- [RoverDevKit (Autonomous Mission Systems Lab, arXiv 2606.21755, 2026; kod açık, Zenodo 10.5281/zenodo.20754999)](https://arxiv.org/html/2606.21755): P_solar = S₀·A·η·d·max(0, cos i); cos i = sin e cos β + cos e sin β cos(α_☉−ψ); kutup için panel eğimi min(80°, |φ|). Doğrulama: Pragyan tepe güç tahmini **52 W vs yayınlanan 50 W**; kütle modeli MAE %13,3.
- VIPER, panelleri Güneş'e dönük tutmak için **yan/çapraz sürebilir** ([NASA VIPER rover and instruments](https://science.nasa.gov/mission/viper/rover-and-instruments)); Otten 2015, 2-serbestlik dereceli dizi varsayımıyla "sıfırdan büyük her aydınlanma yeterli" demiştir.

**LunaPath'te bugün:** `wait_cost(illum_frac, …)` gücü `P_solar × illum_frac` alıyor; geliş açısı yok. `ephemeris.sun_azel_from_vector` Güneş yüksekliğini zaten veriyor.

**Somut katkı:** Rover kataloğuna `panel_tilt_deg`, `panel_azimuth_mode` (sabit / güneşi izler); `wait_cost` ve MOVE enerjisine cos i çarpanı; kutupta Güneş yüksekliği 1–2° iken dikey panel ile yatay panel arasındaki fark **~30 kat** — sunumda çarpıcı bir sayı. Ayrıca A2'nin "dwell" kararlarını etkiler.

**Efor:** 1 gün. Wow: orta; fiziksel doğruluk artışı yüksek.

---

## C2. ✅ ⭐⭐⭐ Batarya soğuk davranışı, hibernasyon ve "karanlık dayanımı" fiziği

> **Yapıldı (16 Eylül 2026, `tuna/backendEnhance`):** Yeni `backend/app/battery.py` — belgenin istediği dördü de. **Üç anahtar, üçü de varsayılan KAPALI ve kapalıyken bit-eşit.** **(a) `usable_fraction(T_inner)`:** soğuk uç 200 K (NASA Glenn'in 18650 ölçümü, **alıntı**; bir rover bataryasına taşınması C3'ün kayma çapaları gibi etiketli varsayım), sıcak uç profilin kendi `bat_op_min_c`'si — LPR-1 ve VIPER'da **tam olarak 0 °C**, yani NASA'nın "5,420 Wh beginning-of-life capacity at 0 C"siyle çakışıyor; bu yüzden **yeni katalog alanı gerekmedi**. Belgedeki **"0 °C'de ~%85" kullanılmadı**: kaynağı yok ve zaten 0 °C'de verilmiş bir kapasiteyi ikinci kez iskonto ederdi. Aradaki şekil kaynaksızdır, varsayılan doğrusal ve raporda üssü süpürülüyor. LUVMI-M `bat_op_min_c = −100 °C` beyan ediyor, yani donma noktasının **27 K altı** — iki çapa çelişiyor, eğri **gerekçeli reddediliyor**, rating noktası uydurulmuyor. **(b) Isıtıcı yasası doğrusal değil T⁴:** belgenin kendi gösterdiği kaynak (NASA JSC, Slusser/Wilcox/Hernandez, TFAWS23-PT-52 s. 3) `Q_rad = εσA(T_obj⁴ − T_env⁴)` yazıyor ve *"weighted to the 4th power"* diyor; ikisi de sunuldu (`radiative` / `delta_t`). **`k` ve `A` ayrı ayrı türetilmedi** — JSC'nin denklemi üçlüyü tek çarpım olarak taşıyor ve modele giren o: `εσA`, katalogdaki `p_heater_w`'den, etiketli bir boyutlandırma varsayımıyla. **Çapraz kontrol:** JSC'nin yayımladığı %26 (270 K→250 K), kendi yasalarından **%26,50** çıkıyor, fark **+0,50 puan** — C1'in `viper_corner_check`'inin muadili. **Kritik düzeltme:** ısıtıcı iç hedefi değil **yüzeyi** okuyor; `surface_to_inner` yüzeyin işaretine göre parçalı ve sıfırda 100 K sıçradığı için iç hedefle sürülen bir ısıtıcı **zemin ısınınca açılıyordu** (ölçüldü: yüzey −0,1 °C → 0 W, +0,1 °C → 11,1 W). **(c) `HIBERNATE` kenarı:** 4-B planlayıcıda üçüncü kenar ailesi, **atomik** (giriş + uyku + dawn pre-heat tek fiyatta, altıncı etiket ekseni yok). **Karanlıkta başlar** (ölçüldü: hibernasyon dört profilin ikisinde beklemeden ucuz — VIPER 100↔130 W, Yutu-2 5↔60 W — yani kapısız bir kenar planlayıcıyı güneşin altında şekerleme yapmaya iterdi) ve **aydınlıkta biter**, çünkü NASA'nın mimarisi öyle: *"Solar Array output triggers a 'Dawn Mode'"*, *"MBC in Dawn Mode operates on Solar Array power alone (Battery still Isolated)"* — yani **dawn pre-heat'in enerjisi bataryadan değil güneş dizisinden gelir**, bedel zaman ve güneş geliridir. Aynı kural hibernasyonun en tehlikeli açığını (karanlıkta girip karanlıkta çıkarak dayanımı sonsuza kadar sıfırlamak) kaynaklı bir kuralla kapatıyor. **Karanlık saati DURMUYOR**, `p_hibernate_w / p_shadow_w` hızında akıyor (LPR-1 1,6615 — hibernasyon saati *daha hızlı* yakıyor; VIPER 0,7692; Yutu-2 0,0833): durdurmak Yutu-2'nin 2 saatlik dayanımını **210 saate** çıkarır (×106) ve D3'ün LP-R01'ini ölçmediği bir sayı üzerinde geçirtirdi. Zarf **askıya alınmıyor, değiştiriliyor** — hibernasyonda `[200 K, envelope.hi]` geçerli ve **her ara dilimde** kontrol ediliyor (birinci mertebe gecikme başlangıcı ile hedefleri arasındaki aralığı terk edemez, yani iki uç hepsini sınırlar). Uyanamama NaN değil, kendi sayacı olan bir ret (`hibernate_unwakeable`), ve sayaç `no_path_reason_4d`'nin baştaki `lead` demetine de eklendi. **(d) `h_max_shadow_h` artık sabit değil:** yayımlanan dayanımın, bu durumun rezerv üstünde hâlâ teslim edebildiği kesirle **oranı**. `min(yayımlanan, türetilen)` denendi ve **çürütüldü**: LPR-1 66,71 / LUVMI-M 22,40 / Yutu-2 17,50 saat yayımlananın üstünde (yani `min` birim) ama **NASA VIPER 33,35 saat**, yayımlanan 50'nin altında — VIPER'ın kataloğu kendi içinde tutarsız (50 s × 130 W = 6 500 Wh > 5 420 Wh; NASA'nın 50 saati **min-power** modunda). Oran biçimi dört profilde de tam şarj + rating'te **tam olarak** yayımlanan sabiti veriyor; tutarsızlık düzeltilmedi, ölçüm olarak raporlandı. **Sentinel tuzağı kapatıldı:** iç sıcaklık bugüne dek yalnız `require_thermal_dwell` altında entegre ediliyordu ve kapalıyken sentinel `0.0` duruyor — **LPR-1/VIPER'ın rating sıcaklığıyla birebir aynı sayı**, yani derate sessizce 1,0 döner ve *koşmuş gibi görünürdü*. Artık izleme ile zorlama ayrı (`track_inner`), ve iç sıcaklık üretilemiyorsa **422**. **İki bayat katalog etiketi düzeltildi:** `constants.py:21`'in "p_hibernate_w now wired"ı **yanlıştı** (depoda tek okuyucusu yoktu — C2 onu gerçekten bağlayan özellik), ve `thermal_tau_s` `DECLARED_ONLY_FIELDS`'ta dururken C6 onu gönderildiği günden beri okuyordu; `MODELLED_FIELDS`'a taşındı **ve** `rover_catalog()`'a üst düzey anahtar olarak eklendi ki sayı API'den kaybolmasın. `HEATER_THERMOSTAT_ASSUMPTION_SOURCE`'un "no W-to-K coefficient" cümlesi C2 ile yanlışlandığı için aynı commit'te düzeltildi ve termostat artık **güç sınırlı**. **API (yalnızca ekleme):** `/api/plan-4d` üç bayrak + `battery_shape_exponent`, her yanıtta `battery` bloğu, `path_actions` (bir hibernasyon bir bekleme gibi yerinde durur — geometrik testle ayırt edilemez), `GET /api/battery-model`, `/api/rovers` içinde `thermal_tau_s` ve `battery_model`; 2-B `/api/plan`'de `applied: false` + gerekçe (*"the 2-D cost grid has no epoch"*). **Maliyet gridi bit-eşit:** `COST_MODEL_ID` **v5'te kaldı** ve LPR-1'in iki checked-in SHA-256 özeti bayt-eşit (VIPER'ınki C2'den önce de eşleşmiyordu). **Ölçüm (Site11, `scripts/battery_hibernation_report.py` → [battery_hibernation_report.md](battery_hibernation_report.md)):** **Spearman(gölge oranı, yüzey sıcaklığı) = −0,0014** — yani "karanlık = soğuk" varsayımı bu sahada yaklaşık olarak değil, **tamamen** bilgisiz; aydınlık ama soğuk 4 922 hücre (%2,34) var. Bu yüzden sıcaklık tabanlı ısıtıcı eskisinin bir sınırı **değil**: `delta_t` hücrelerin %13,89'unda, `radiative` %44,16'sında **daha fazla** çekiyor (ilk taslağın "her zaman ≤" iddiası ölçümle geri çekildi). Kalibrasyon: LPR-1 `kA` 0,166667 W/K, `εσA` 4,6845e-09 W/K⁴, ε=1'de **0,0826 m²** — 450 kg'lık bir araç için çok küçük, yani katalogdaki `p_heater_w` bir **idame** ısıtıcısı; JSC'nin 500 kg için ">400 kg batarya" bulgusuyla aynı yöne işaret ediyor. **Rotalar:** LPR-1 gündüz 41 hamle / maliyet 3,445393 (C1'in raporundaki sayının aynısı → gerçek gridde de bit-eşit); ısıtıcı modelleri rotayı değiştirmiyor, maliyeti +%0,17 ve SOC'yi −0,25 puan değiştiriyor. **En önemli ölçüm: Ay gecesi rotası `derated` altında 404** — *"11 757 edges would have drained the battery below the 20 percent reserve"*; C2 öncesi model aynı rotada en düşük SOC'yi rahat bir %67,42 diye bildiriyordu. Özellik bir sayıyı değil bir **güvenlik hükmünü** değiştiriyor. **Hibernasyon hiçbir standart rotada seçilmedi** ve nedeni dürüstçe yazıldı: gece rotasının en uzun sürekli karanlığı 4,80 saat, LPR-1'in dayanımı 50 saat — ihtiyaç yok; üstelik LPR-1'de hibernasyon beklemeden pahalı. Kenarın çalıştığı sentetik bir gecede kilitlendi: Yutu-2 20 saatlik karanlığı **bekleyerek geçemiyor**, hibernasyonla geçiyor (bütçeden 1,6667 saat, en soğuk iç sıcaklık −70 °C, donma noktasının üstünde). **Tasarım denetimi:** beş bağımsız düşmanca lens tasarımı yazılmadan önce denetledi ve **ilk taslağın dört iddiası ölçümle çürütüldü** (ısıtıcının iç hedefi okuması, "yeni ≤ eski", `min()` dayanımı, saatin durması); dördü de düzeltildi. **Testler:** 74 birim + 15 API + 10 skip-korumalı gerçek grid = **99**. Tasarım: [spec](../superpowers/specs/2026-09-16-c2-batarya-hibernasyon-design.md), [plan](../superpowers/plans/2026-09-16-c2-batarya-hibernasyon.md).

**Ne:** Bataryanın kullanılabilir kapasitesini sıcaklığa bağlamak, hibernasyon (donmuş batarya, sıfır yük) durumunu 4B planlayıcıya bir eylem olarak eklemek, ısıtıcı gücünü sıcaklık farkına göre modellemek.

**Kim / kaynak:**
- NASA Glenn — Oeftering, Bennett vd., [Battery Hibernation for Surviving the Lunar Night (2021 Space Power Workshop, NTRS)](https://ntrs.nasa.gov/api/citations/20210011101/downloads/Battery%20Hibernation%203-8-21.pdf): 18650 Li-ion hücrelerde elektrolit **<200 K (−70 °C)** donuyor, gerilim sıfıra düşüyor, **>200 K'de tamamen toparlıyor**; vakumda 4/4 başarılı; ISRO 3 üreticinin hücrelerini **−160 °C'de 14 gün** tutup kapasite kaybı görmedi; Surveyor 1 altı Ay gecesi hayatta kaldı. "Dawn mode" güç mimarisi tanımlı.
- [Lunar Power Hibernation (NTRS 2021)](https://ntrs.nasa.gov/api/citations/20210019184/downloads/Lunar%20Power%20Hibernation%20Extreme%20Environments%20WG%20%207-28-21.pdf)
- VIPER: gölgede matkapla **9,5 saat**, min-power modda **50 saat** dayanım ([Shirley & Balaban 2022](https://www.nasa.gov/wp-content/uploads/2022/05/overview_of_mission_planning_for_the_viper_rover.pdf)).
- NASA JSC — Slusser vd., [Surviving Night at the Lunar South Pole (TFAWS 2023)](https://tfaws.nasa.gov/wp-content/uploads/TFAWS23-PT-52-Paper.pdf): sadece bataryalı araçta gece için **>400 kg batarya** gerekebiliyor; ısıtıcı gücü T⁴ ile ölçeklenen yüzey alanına bağlı.
- [Energy storage selection and operation for night-time survival of small lunar surface systems (Acta Astronautica 2021)](https://www.sciencedirect.com/science/article/abs/pii/S0094576521002101)

**LunaPath'te bugün:** batarya sabit kapasite; ısıtıcı sabit güç; hibernasyon yok; `h_max_shadow_h` tek eşik.

**Somut katkı:** (a) `battery_usable_fraction(T_inner)` eğrisi (0 °C'de ~%85, −20 °C'de ~%60 tipik; katalogda parametre olarak, `MODEL` etiketli), (b) `heater_power = k·A·(T_survive − T_env)` — `thermal_model` iç sıcaklığını kullanır, (c) 4B planlayıcıda `HIBERNATE` kenarı: yük ≈ 0, ama çıkış için "dawn pre-heat" enerji/zaman bedeli, (d) `h_max_shadow_h` artık sabit değil, SOC ve sıcaklığın fonksiyonu. Challenge belgesi 6.5 ("bileşen bazlı sağlık skoru mu?") sorusuna somut bir "battery stress" bileşeni verir.

**Efor:** 2 gün. Wow: orta; jüri "hibernasyon" kelimesini VIPER/Chandrayaan bağlamında bilir.

---

## C3. ✅ ⭐⭐⭐⭐ Slip modelinin uçmuş/yer-test verisiyle kalibrasyonu (Yutu-2, VIPER, termal atalet)

> **Yapıldı (5 Eylül 2026, `berke-3d-backendEnhance`):** `slip_model.py` yeniden yazıldı — eğri **kaynaklı çapalardan** geçer: VIPER'ın PSJ 2025 §3.5'teki mobilite tasarım gereksinimi *"a maximum of 40% slip up a maximum slope of 15°"* (GRC-1 simülantı, %15–20 bağıl yoğunluk, MGRU; slip tekerlek dönüşü + Optitrack — belgedeki "enkoder+VO" düzeltildi; bir **üst sınır**, tipik değer değil) ve Yutu-2'nin Nature Communications 2024'te **ölçülmüş** slip oranı (*"most the wheel slip ratios are between 0 and −0.075"*, ≤ 8,86° eğimde, çoğunlukla skid; işaret atıldı: 0° → 0,0375 ± 0,01875 (aralık/4, `measured`), 8,86° → 0,075 üst uç (`measured_bound`)). Çapalar arası ve son çapa ötesi **log-doğrusal** (üstel; MER / terramekanik dışbükey biçim — **varsayım**), kap `MAX_SLIP_RATIO = 0,9`, `|θ|` simetrik, ilk çapa 0° zorunlu; her `SlipAnchor`'ın `source` alanı zorunlu, aktarılanlar `kind: "assumption"` ve `"assumption: …"` (LPR-1 ve LUVMI-M tamamen aktarım; VIPER 0° Yutu-2'den aktarım + 15° kendi kısıtı; Yutu-2 kendi iki ölçülmüş çapası + VIPER 15° aktarımı — 8,86° çapası VIPER'a aktarılmadı, mare regoliti ile gevşek GRC-1 farklı zeminler). Etiket `SLIP_MODEL_VALIDITY` `"UNCALIBRATED"` → `"MODEL"` (`"MEASURED"` asla; `SLIP_CLAIM` her yanıtta). **Tek noktadan bağlama:** `cost_engine.edge_travel_time_s` `d → d/(1−s(θ))`; tüm süre/enerji fonksiyonları, 2-B ve 4-B planlayıcı (satır içi drain aritmetiği değişmeden birebir), simülatör, koridor bütçeleri, B5 Monte Carlo, A1 safe-haven süreleri, A2 koridor dilimleri ve `auto_slice_hours` aynı sayıyı görür; vektörize eş `edge_travel_time_s_array` aynı işlem sırasıyla **bit-eşit** (bu platformda `np.exp/cos/log == math.*`, 1 M örnekte 0 ulp; her rover için 100 000 rastgele kenarda `np.array_equal`), `safe_haven._gated_edges` ve `illumination_corridor.edge_tables` onu kullanır (A2'nin "işlem sırası farklı" notu kalktı). B2 kancası `slip_stats(θ, rover) → (μ, σ)` (σ: Yutu-2 aralık/4; VIPER'da Yutu-2'nin bağıl yayılımı 0,5 aktarım, `source`'ta yazılı). Enerji kriteri `f_energy_cell` / `f_energy_cell_grid`: hücrenin enerjisi slip'li, **ölçek slip'siz en kötü hücre** (`slip_free_view`) — slip'li en kötü hücreye (25°, ×10) normalize etmek her sıradan hücreyi [0, 0,15]'e sıkıştırıp H-4 çöküşünü geri getiriyordu (ölçüldü: LPR-1'in karanlık 10° hücresi 0,58 → 0,07); `COST_MODEL_ID` v4. Varsayılan ufuk artık **en hızlı kapılı rota** ile (`safe_haven.gated_shortest_drive`, SciPy Dijkstra + öncül zinciri): `ceil(saat/dilim) + hamle + 20` (her hamle en fazla bir dilim yuvarlama kaybeder) — eski "BFS hamle × en yavaş kenar" sınırı slip'le tavanı aşıyordu (ölçüldü: Ay gecesi 113 hamle 1 602 > 1 000 → 270; LPR-1 günü 580 → 120). Katalog: `slip_curve` (`MODELLED_FIELDS`), `regolith` (`DECLARED_ONLY_FIELDS`: Yutu-2 iç sürtünme 21,5–42,0°, kohezyon 520–3 154 Pa, N 0,87–1,0, batma 8 mm (5–15), taşıma 4 kPa, `validity` "MEASURED at the Chang'e-4 site … not at the pole"; VIPER GRC-1 %15–20 "GROUND_TEST"; Bekker denklemi kodlanmadı, `read_by: "nothing"`). API (yalnızca ekleme): `/api/rovers` `slip_model` (validity, çapalar + kaynaklar, 0/5/10/15/20/25° tablo, referanslar) ve `declared_only.regolith`; `/api/plan`, `/api/plan-4d`, `/api/compare`, `/api/plan-multi` yanıtlarında `slip_model` bloğu (`route.mean_slip / max_slip / max_slip_slope_deg / distance_factor / extra_hours / extra_drawn_wh`, `applied`, `claim`). Termal atalet (Cunningham, RSS 2017): yalnızca `thermal_inertia_slip_scale` imzası, `NotImplementedError` (Diviner PRP ürünü adıyla) — Diviner yerelde yok, "modüle edildi" denmiyor. **Ölçüm (Site11, [slip_calibration_report.md](slip_calibration_report.md)):** eğri 0/5/10/15/20/25° → 0,037 / 0,083 / 0,182 / 0,400 / 0,881 / 0,900 (çarpan ×1,04 / 1,09 / 1,22 / 1,67 / 8,4 / 10; Yutu-2 kendi eğrisi 5° 0,055, 10° 0,102, 20° kap). Site11 dik (ince eğim medyanı ~10°, kaba blok p95 19–22°), bu yüzden etki büyük: LPR-1 28 Eyl (358,494)→(206,426) varış **2,16 → 2,98 h (×1,38)**, en düşük SOC %96,2 → %92,5, rota ortalama slip 0,326 (maks 0,537 @ 16,9°), slip'in eklediği 0,75 h / 321 Wh, otomatik dilim 0,0287 → 0,0359 h, B5 nominal en düşük SOC %97,9 → %94,5 (tamamlanma %100 aynı); Ay gecesi (186,34)→(494,450) 5,35 → 6,75 h (×1,26), SOC %72,7 → %67,4, LP-R02 52,7 → 47,5 pct; 2-B: LPR-1 469 → 597 Wh (×1,27), Ay gecesi 1 288 → 1 466 Wh (×1,14), VIPER 2 156 → 2 742 Wh (×1,27), 4,33 → 5,40 h, SOC %67,2 → %57,6. **VIPER'ın standart haven→haven leg'i slip'li modelde 404** (283 148 kenar bataryayı %20 rezervin altına düşürürdü; haven kuralsız ve 24 h ufukla da 404): rota slip'siz zaten %32 SOC ile marjinaldi (B5: %29,6 tamamlanma, %1,4 rezerv içinde) — modelin dürüst kararı, hata değil; en yakın uygulanabilir leg (358,494)→(346,462): 8 hamle, varış 1,53 → **2,23 h (×1,46)**, SOC %85,4 → %72,3, havende biter, ort. slip 0,465, SHERPA tamamlanma %100 → %99,6 / tam başarı %99,7 → %95,0, 2-B 540 → 920 Wh (×1,70); VIPER'ın 40 hamlelik leg'ini varsayan altı gerçek-grid testi bu leg'e uyarlandı (iddialar korundu), yeni test standart leg'in reddini ve gerekçesini ("reserve") kilitledi. Testler: 42 birim (`test_slip_model.py`), 15 `cost_engine` (`test_cost_engine_slip.py`: formül, 4 rover × 100 000 kenar bit-parite, 1/(1−s) oranları, kriter ölçeği, grid ↔ skaler), 9 katalog (`test_rover_validation.py`), 5 kapılı graf / Dijkstra (`test_safe_haven.py`), 2 koridor dilimi / `auto_slice_hours`, 5 API (çekirdeksiz, `test_slip_api.py`), 4 skip-korumalı gerçek grid; tam paket 1 176 passed, 2 skipped (12:25). Tasarım: [../superpowers/specs/2026-09-04-c3-slip-calibration-design.md](../superpowers/specs/2026-09-04-c3-slip-calibration-design.md). Sapmalar: enerji kriterinin ölçeği slip'siz kaldı (spec'te yoktu, ölçümle karar); `test_cost_engine_slip.py` ayrı dosya (`test_cost_engine.py` betik tarzı); `slip_free_view` yardımcı; raporda VIPER için "kısa leg" ve gevşetme (haven kuralsız, 24 h ufuk) satırları; `route_slip_summary` testleri uygulamadan sonra yazıldı (davranışı kilitler); tam 90°'de süre sonsuz değil çok büyük sonlu sayı (mevcut davranış, test 95°'ye çekildi).

**Ne:** `slip_model.py`'nin "UNCALIBRATED" etiketini kaldıracak referans eğriler ve regolit parametreleri.

**Kaynaklar (sayılarla):**
- **Yutu-2 (Chang'e-4), uçmuş veri:** Ding vd., [A 2-year locomotive exploration… by the Yutu-2 rover, Science Robotics (2022)](https://www.science.org/doi/10.1126/scirobotics.abj6660) — hafif slip/skid; ve dijital-ikiz çalışması [Lunar rock investigation and tri-aspect characterization of lunar farside regolith by a digital twin, Nature Communications (2024, açık erişim)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11258293/): iç sürtünme açısı **21,5–42,0°**, kohezyon **520–3.154 Pa**, batma üssü N **0,87–1,0**, ortalama tekerlek batması **8 mm (5–15)**, taşıma ~**4 kPa**, slip oranı **0 ile −0,075** arası; dijital ikizle hedef nokta hatası **0,367 m**. Bekker/Wong denklemleri makalede açık.
- **VIPER yer testi (güney kutbu için tasarım kısıtı):** [Investigating the Geotechnical Properties of the Lunar South Pole with NASA VIPER's Mobility System, PSJ (2025)](https://iopscience.iop.org/article/10.3847/PSJ/add13f): GRC-1 simülant, %15–20 bağıl yoğunluk (gevşek); **tasarım kısıtı: 15° eğimde %40 slip**; slip enkoder+VO'dan, batma HazCam desenlerinden.
- **Termal atalet → slip:** Cunningham, Nesnas, Whittaker, [Improving Slip Prediction on Mars Using Thermal Inertia Measurements (RSS 2017; Autonomous Robots 43(2) 2019)](https://roboticsproceedings.org/rss13/p38.pdf): Curiosity verisiyle, termal atalet düşük kumun yüksek slip verdiği gösterildi; görünüm-tabanlı modelden daha iyi. **LunaPath için özgün fikir:** Diviner gece sıcaklığı/termal atalet vekili, slip önceliğini modüle eder — termal katman ile mobilite katmanı arasında fiziksel bir köprü.
- Ek: [Modeling of slip rate-dependent traversability… sandy terrain (Frontiers 2024)](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2024.1320261/full); Ishigami vd. terramekanik temelli eğim geçilebilirliği (10 no'lu belge kaynakları).

**LunaPath'te bugün:** `slip_model.py` yön iddiası taşıyor, büyüklük iddiası taşımıyor.

**Somut katkı:** (a) Katalogda rover başına `slip_curve` = {0°: 0,02, 10°: 0,15, 15°: 0,40 (VIPER kısıtı), 20°: 0,7}; kaynak alanı zorunlu, (b) enerji = mesafe/(1−slip) düzeltmesi `edge_energy_wh`'ye, (c) Yutu-2 aralıklarıyla Bekker parametreleri `SYNTHETIC`→`MODEL(literature)` etiketine geçer, (d) B2 ile birleşince slip dağılımı (μ, σ) doğrudan CVaR'a girer. Sunum cümlesi: "Slip eğrimiz VIPER'ın 15°/%40 tasarım kısıtına ve Yutu-2'nin ölçülmüş regolit parametrelerine bağlı."

**Efor:** 1–2 gün. Wow: orta-yüksek (uçmuş veri adı geçince jüri dikkat kesilir).

---

## C4. ✅ ⭐⭐⭐⭐ Ölçülmüş pürüzlülük (roughness) katmanı — LOLA LDRM ürünleri

> **Yapıldı (5 Eylül 2026, `berke-3d-backendEnhance`):** NASA PGDA ürün 90'ın iki **ölçülmüş** ürünü planlama penceresine ko-registre edildi (`scripts/build_roughness_cache.py`): LOLA **LDRM pürüzlülüğü** `LDRM_80S_50MPP_ADJ_ROUGH_100M` (50 m/px, 100 m taban; dizinde 80S için yalnız 50 ve 1 000 m/px var — aşağıdaki "50–1.000 m taban" doğru, "10–240 m/px" LDEM'e aittir) ve **LPSR PSR maskesi** `LPSR_80S_20MPP_ADJ` (20 m/px). İkisi de COG; pencereler tek 512² tile (50×50 ve 125×125 px + kenar payı), `/vsicurl/` ile 10 s'de indi; CRS parametreleri bizimkiyle eşit (adlar farklı; `roughness.same_projection` parametre karşılaştırır); hedef transform origin = hücre (0,0)'ın **sol-üst köşesi** (Site11 TIF transformuyla doğrulandı; A4'ün yardımcısı merkez sayıyordu — 2,5 m, piksel-altı, sonuç değişmez); `nearest` yeniden örnekleme (5 m hücre kapsayan pikselin değerini **aynen** alır; bilinear ölçülmemiş blok-içi gradyan üretirdi). **Kayıt sağlaması:** NASA'nın 100 m fit-düzlemi eğimi ↔ bizim 5 m eğimin 50 m blok ortalaması Spearman **0,989** (2 500 blok; eşik 0,9 altında betik yazmaz). Yeni `backend/app/roughness.py`: `RoughnessScale` (bölgesel ECDF, 201 kantil düğümü; skaler `f` ↔ grid `f_grid` aynı `np.interp`, bit-eşit; NaN → 0,5, hücre geçilmez olmaz), `ecdf_scale_from_sample`, `same_projection`, `psr_shadow_overlap`, `route_roughness_summary`, `roughness_block`, iddia sabitleri. **Beşinci kriter `f_roughness`** (`cost_engine`/`cost_vec`; `costmap.RoughnessLayer` MEASURED, `PlanContext.roughness/roughness_scale`; `cost_cube` blok-maks; `rover_grids`/`pathfinder`/`data_loader` — ölçeksiz grid reddedilir), `w_roughness` beşinci ağırlık (`_WEIGHT_KEYS`, katalog dört rover **0,15 — varsayım**, yorumla; dört profil; `PlanWeights`; `/api/layers` ve `/api/terrain` parametresi; diğer dört ağırlık **yeniden ölçeklenmedi**, toplam 1,15), `COST_MODEL_ID` v5; katman yokken dört terim v4 ile **bit-eşit** (`metadata.cost_criteria` damgası; Site11'de iki yönlü SHA-256 kilidi: katmanla v5 `55e1bb3c…` / `593f8e46…`, katman çıkarılınca ya da `w_roughness=0` ile v4 `0e74607d…` / `8788936c…`). Normalizasyon: rover kataloğunda kaynaklı tolerans alanı yok, **uydurulmadı** → istatistiksel ölçek (**MODEL**): hücrenin 80–90°S bölgesinin 50 m pikselleri arasındaki persentil sırası (ürünün 36 tile'lık örneği, 9,4 M piksel; `roughness_meta.json["scale"]`); reddedilenler: doğrusal `r/63 m` (Site11 p95 0,028 → atıl), log-doğrusal p5–p95 (%15 doygunluk), grid-göreli persentil (pencereler arası karşılaştırılamaz). **PSR planlamaya girmez** (VIPER'ın hedefi PSR içi; termal kapı 14 016 PSR hücresinin LPR-1 için 13 933'ünü zaten kapatıyor — 83 geçilebilir, VIPER 78; gölge/termal kriterler karanlığı zaten fiyatlıyor): katman `psr` MEASURED; `/api/cell-telemetry` `roughness_m` / `f_roughness` / `in_psr` + `cost_breakdown.roughness`; `/api/plan` ve `/api/plan-4d` `roughness` bloğu (rota ort./maks m, ort. f, PSR hücresi, iddia); `GET /api/psr-validation` (Jaccard, recall, precision, gölge/termal içi-dışı); `risk.sigma_sources.roughness: "none"` (LDRM'nin yayımlanmış σ'sı yok → kuyruk yok). `cost` etiketi **yükselmedi** (DERIVED kalır; en zayıf girdi belirler — aşağıdaki "MODEL'e yükselir" cümlesi termal düzeltilince). **Ölçüm (Site11; `scripts/roughness_psr_report.py` → [roughness_psr_report.md](roughness_psr_report.md)):** pürüzlülük 100 m medyan 0,83 m (p5 0,40 / p95 1,78 / maks 4,87; 200 m 1,69, 400 m 3,30, 800 m 7,80, 1 600 m 23,6 m; Hurst medyan 0,92), bölge medyanı 0,57 → `f_roughness` Site11'de p5 0,23 / p50 0,78 / p95 0,98 (≥ 0,99 %2,3); **H-4: Spearman(pürüzlülük, eğim) 0,213** (50 m blok-ort. 0,227, blok-maks 0,321; `f_slope` ile 0,18) — eğimin yeniden ifadesi değil; eğim kutuları 0–5° → >20° medyan 0,72 → 1,08 m (PSJ 2025'in yönü, zayıf). w = 0,15'te maliyet gridi nominale Spearman 0,959 (LPR-1) / 0,945 (VIPER), ortalama +%24,5 / +%22,6, kriterin hücre maliyetindeki payı ort. %19 / %18. **PSR ↔ `shadow_ratio ≥ 0,99`: Jaccard 0,830** (PSR'ın %98,3'ü yakalandı, karanlıkların %84,2'si PSR; eşik 0,9 → 0,685, 1,0 → 0,833), **20 m ürün bloğunda 0,912**; PSR içinde ort. gölge 0,998, `thermal_min` medyanı −183,15 °C (90 K tabanı); `thermal_min ≤ −180 °C` olan 16 406 hücrenin 13 761'i PSR'da. 2-B (`/api/plan`, w ∈ {0, 0,05, 0,10, 0,15, 0,20, 0,30}): **LPR-1 Ay gecesi çifti** 0,05'te bile yer değiştiriyor (örtüşme 0,20; 0,15'te **0,05**, rota ort. pürüzlülük 0,75 → 0,66 m, mesafe aynı 2,727 km, ama 1 465,7 → 1 519,4 Wh (+%3,7), 4,366 → 4,429 h, min SOC 87,10 → 85,91 — daha düz zemin, daha pahalı enerji); LPR-1 gündüz 0,15'e kadar aynı, sonra örtüşme 0,97 (597,2 → 596,9 Wh); VIPER standart 0,30'a kadar aynı (sonra 0,87); VIPER kısa leg 0,20'den itibaren 0,83. 4-B (coarsen 4, w 0 → 0,15) + B5 1 000 koşum: LPR-1 28 Eyl **aynı** 41 hamlelik rota (2,979 h, %92,5, B5 %100 / %99,8); Ay gecesi 116 hamle, örtüşme 0,89, varış 6,749 h / %67,4 / B5 %98,8 / %88,8 aynı; VIPER kısa leg aynı 8 hamle (%99,6 / %95,0). Etki **küçük ve çifte bağlı**; öyle yazıldı. Planlama 2-B 0,2–1,0 s, 4-B 3–20 s. Tasarım: [spec](../superpowers/specs/2026-09-05-c4-roughness-psr-design.md) (sondalar ve ölçümler dahil), [plan](../superpowers/plans/2026-09-05-c4-roughness-psr.md). **Sapmalar:** `cost_criteria` damgası yalnız metadata alanı değil, yeniden-hesap koşulu da oldu (varsayılan rover'da depolanan v5 gridi katman çıkarılınca yeniden kullanılıyordu; test yakaladı); `_risk_sources` pürüzlülük kaynağı; 4-B bloğu blok-maks / "blok PSR'a değiyor" kuralıyla ve WAIT tekrarları atılarak; Hurst ve 200–1 600 m tabanlar yalnız `roughness_baselines.npz` (rapor); RMSD/CLASS/RGB indirilmedi; B2'nin v4 kilidi katmansız temel gride taşındı. Testler: 26 birim (`test_roughness.py`) + 30 maliyet yolu (`test_roughness_cost.py`) + 16 API (`test_roughness_api.py`, çekirdeksiz) + 6 yükleyici (`test_layer_validity.py` eki) + 10 skip-korumalı gerçek grid (`test_roughness_real_grid.py`: iki yönlü SHA kilidi, aralıklar, dört çift, `/api/psr-validation`); uyarlanan on mevcut test: `test_rover_grids`, `test_scenarios`, `test_review3_fixes`, `test_cost_engine_slip`, `test_risk_cost` (v5 kimliği + damgalı önbellek fixture'ı), `test_plan_endpoint`, `test_pathfinder` (beş ağırlık / `cost_criteria` damgası), `test_risk_sweep_real_grid` (v4 kilidi katmansız temelde); tam paket 1 338 passed, 2 skipped (12:55; tek uyarı önceden var olan `test_visibility_validation`'ınki).

**Ne:** DEM'in altında kalan (5–80 m arası) yüzey pürüzlülüğünü, LOLA'nın **ölçülmüş** çok-taban-uzunluklu pürüzlülük ürünlerinden yeni bir maliyet kriteri olarak eklemek. Diviner kaya bolluğu (rock abundance) **kullanılamaz**: kapsamı ±70–80° ile sınırlı ([Powell vd. 2023, JGR Planets](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2022JE007532), 128 ppd, ±70°) — bizim pencere 80–90°S.

**Kim / kaynak:**
- NASA GSFC — Barker vd., [A New View of the Lunar South Pole from LOLA, PSJ 4:183 (2023)](https://iopscience.iop.org/article/10.3847/PSJ/acf3e1) · [PGDA ürün sayfası](https://pgda.gsfc.nasa.gov/products/90): 60°S–90°S, 10–240 m/px; **LDRM pürüzlülük** (50–1.600 m taban, Hurst üssü, RMS yükseklik sapması, k-means yüzey sınıfları, RGB kompozit), hata tahminli eğim (LDSM), **PSR haritaları (506.349 özellik; 1.531'i > 1 km²)**, 20 m NAC mozaik. Veri DOI: 10.60903/gsfcpgda-lola-spole.
- Kuzey kutbu eşdeğeri ve metodoloji: [Large-scale Roughness Properties of the Lunar North and South Polar Regions (PSJ 2025)](https://iopscience.iop.org/article/10.3847/PSJ/adbc9d): >10° eğimlerde 50–200 m tabanda pürüzlülük artıyor; pürüzlülük **regolit sıcaklığıyla korele** (soğuk bölgeler daha pürüzsüz).
- Klasikler: Kreslavsky vd. 2013 (hektometre/kilometre pürüzlülük, IQR eğrilik), Rosenburg vd. 2011 (RMS eğim, Hurst).

**LunaPath'te bugün:** eğim ve bakı var; pürüzlülük yok; 11 no'lu belge "80 m/px'te 30 cm'lik kaya görünmez" diyor — pürüzlülük bunun **istatistiksel** vekilidir.

**Somut katkı:** 5. kriter `f_roughness` (`MEASURED` etiketli — projenin ilk ölçülmüş ikinci katmanı); `weakest_validity` mantığı gereği cost katmanı artık "SYNTHETIC" yerine "MODEL" seviyesine yükselebilir (termal düzeltildikten sonra). Ayrıca PGDA PSR shapefile'ı, `SYNTHETIC` PSR maskesinin yerine `MEASURED` maske olarak girer.

**Efor:** 1–2 gün (indirme + ko-registrasyon; `rasterio` zaten var).

---

## C5. ✅ ⭐⭐⭐ Termal doğrulama için doğru ürün kimlikleri (Diviner PRP + Williams 2019)

> **Yapıldı (16 Eylül 2026, `tuna/backendEnhance`):** Ürün kimliği birinci elden pinlendi — belgedeki PDS3 yolu **404**; ürün PDS4 paketi `urn-nasa-pds-lro_diviner_derived1/data_derived_prp/` altında (`dlre_prp_south.tab`, **604 800 210 B**, SHA-256 `393deaa5…`), ve silinen `scripts/diviner_validation.py`'nin işaret ettiği MIT Imbrium adresi **aydınlanma** ürünüydü, Diviner sıcaklığı değil. Biçim etiketten okundu (`dlre_prp.fmt`, `prpds.cat`), varsayılmadı; üç **kaynak-içi** uyumsuzluk kayda geçti: katalog düzyazısı ağı "288000 triangles" diyor ama etiket ve dosya boyutu **2 880 000** diyor (bir sıfır eksik); kapsama "kutup merkezli **kare**" olduğu için köşeler 80°'nin ekvator tarafına taşıyor (ölçüldü: −75,905°); ağ **Kaguya** DEM'inden (Araki 2009), bizim gridimiz LOLA'dan — ko-registrasyon farkı bir hata kaynağı olarak yazıldı. **Üç iddia sınırı düzeltildi:** (1) PRP ham ölçüm **değil** — kataloğun kendi ifadesiyle *"thermal model fits to first mapping year Diviner polar observations"*, CODMAC Level 5 / NASA Level 4 — yani karşılaştırma MODEL ↔ MODEL-ÖLÇÜME-OTURTULMUŞ'tur, belgenin "bu istatistiğin **ölçülmüş** karşılığıdır" cümlesi fazla güçlü; (2) `temp_avg` **yüzeyin 2 cm altında** hesaplanmış, bir yüzey alanı değil, hiçbir alanımızın karşılığı değil; (3) `ice_depth` modellenmiş bir ürün, karşılaştırmaya sokulmadı. **İstatistik tuzağı ölçümle çözüldü:** görev tanımı diskteki alanın gölge eşlenmiş olduğunu ve tersinin alınması gerektiğini söylüyordu — **ölçüldü, öyle değil**: `thermal_grid.npy` düzeltilmemiş sunlit peak tutuyor (16 253 hücre `shadow_ratio = 1` iken +43,4 °C'ye kadar okuyor, PSR tabanında **sıfır** hücre var, 250 000 hücrede yalnız **190 farklı değer** — bir 13×16 LUT imzası), eşleme yükleme anında bir kez yapılıyor ve `data_loader.py:64-75` `thermal_shadow_coupled`'ı açıkça **"legacy alias"** işaretliyor (yetkili anahtar `thermal_field: sunlit_peak`); dolayısıyla tersini almak çifte-ters olurdu. Doğru üç aday: **A** ham sunlit peak, **B** `annual_peak_c` (planlayıcının okuduğu), **C** `shadowed_equilibrium_c`. Yeni `scripts/build_diviner_prp_cache.py` (C4 deseni: `.part` üzerinden indir, boyutu etiketin `RECORD_BYTES × (FILE_RECORDS + 1)`'ine karşı doğrula, tek geçişte ayrıştır — **56 s**, 2 880 000 üçgen, medyan alan **0,1279 km²** ≈ **544 m** kenar, npz 66,6 MB; üçgen normalinden alan/eğim/gerçek-kuzey bakısı türetildi; köşeler yalnız −88,5° kutup tarafı için saklandı, yoksa +104 MB); `backend/app/thermal_validation.py` genişletildi (`thermal_comparison` **aynen** korundu, yedi mevcut testi kıpırdamadı; eklenenler `spearman_rho`, `rmse_ci95`, `error_statistics`, `compare_candidates`, `triangle_areas_km2`, `assign_cells_to_facets`, `aggregate_to_facets`, `grid_cell_centres`, `kelvin_to_c`, `cold_trap_area_check`, `PRP_QUOTED`/`WILLIAMS_QUOTED`). **`scripts/diviner_validation.py` silindi** ve yerine belgenin istediği `scripts/validate_thermal.py` geçti: o betik var olmayan biçimdeki bir **raster** için yazılmıştı (gerçek ürün 605 MB'lık ASCII üçgen ağı, `reproject` yolu onu tüketemez) ve gerçek veriyle hiç koşmamıştı; içindeki `destination_transform` ve Round 2 H-3 dersi (yarım hücre / üst kenar kaydı) `thermal_validation`'a taşındı, `test_review2_fixes.py`'nin iki testi **iddiaları tek karakter değişmeden** yönlendirildi. **Ölçüm (`scripts/validate_thermal.py` → [thermal_validation_report.md](thermal_validation_report.md), 3,9 s):** karşılaştırma **kabanın çözünürlüğünde** yapıldı — 5 m gridimiz her üçgenin ayak izinde (tam barycentric testle) toplulaştırıldı, PRP 5 m'e interpolasyon **yapılmadı** (yapılsaydı ~50 ölçüm 250 000 sahte örneğe dönerdi). **Site11 penceresi:** merkezi pencerede **50** üçgen, hücrelerimizi örten **71**. Ama uygulama sırasında bulunan bir yanlılık düzeltildi: bir Diviner fasetinin `temp_max`'ı **bütün** üçgenini (~0,128 km²) anlatır, pencere kenarında kırpılan faset ise bize yalnız kendi diliminden görünür — ölçüldü, **22 faset yarıdan az örtülüyor** (13'ü dörtte birden az, en küçüğü **%2**) ve bunları dâhil etmek uyumu **olduğundan iyi** gösteriyor (B RMSE süzgeçsiz 35,52 ↔ ≥%50'de 39,43 ↔ ≥%90'da 40,14). Ana sayı **örtme ≥ %50** süzgecine çekildi (**n = 49**) ve üç eşik de yayımlandı. Ortalama toplulaştırmada A RMSE **37,44 °C** (bias −10,38, ρ 0,290), **B RMSE 39,43 °C** (bias −23,19, ρ **0,457**, %95 GA **32,9–49,1 °C**), C 72,11 °C (bias −66,36); maksimum toplulaştırmada A/B bias **+62…63 °C**'ye fırlıyor (yanlış eşdeğer olduğu gösterilerek yayımlandı, çünkü PRP'nin üçgen değeri tek bir **fasetin** modellenmiş maksimumu, faset-altı topografyanın maksimumu değil). **Karar: doğru taraf B** — planlayıcının okuduğu alan ve istatistik eşleşmesi odur; A'nın küçük RMSE'si gölge eşlemesinin **yönünü** değil, PSR tabanının **değerini** suçluyor (B'nin sıra korelasyonu belirgin biçimde daha iyi: 0,457 ↔ 0,290). **LUT'un kendisi (enlem eşlenmiş, n = 5 009):** RMSE 55,30 °C, bias −4,35, ρ **0,811**; bakı marjinalleştirilmiş 13 eğim kutusunda Spearman **1,000** ve orta eğimlerde neredeyse birebir (6,9–9,2°: PRP −72,51 ↔ bizim −72,10 °C), ama düz zeminde **22 °C soğuğuz** (0–2,3°: −124,56 ↔ −146,37). Enlemin eşlenmesi zorunluydu: −88,9°'de Güneş'in maksimum yüksekliği ~0,5° ve enlemle hızla değişiyor. **Yeni bulgu 1 — bakı referans çerçevesi:** heat1d `slope_az`'ı kurulu paketin docstring'inde *"clockwise from north (0 = N, pi/2 = E)"*, yani **gerçek** kuzeyden sayıyor; bizim `make_aspect_grid` (`process_lunar_data.py:275`) açıyı **grid** koordinatlarında hesaplıyor; pencere boylamında (−72,669°) ayrışma **72,67°** — 22,5°'lik bakı kutularında ~3,2 kutu. 5°'lik tanısal tarama minimumu **295°**'te buldu: yakınsamanın −dalına (287,3°) **7,7°**, öteki dala 137,7° — yani büyüklük geometriden, **işaret ölçümden** doğrulandı. Ama kazanç küçük (55,30 → 53,87 °C, **%2,6**) ve tüm tarama 53,9–58,7 °C arasında geziniyor; toplam uyuşmazlığın çoğunu çerçeve **açıklamıyor**. LUT'un bakı duyarlılığı ayrıca ölçüldü: sabit eğimde yayılım **28,4 °C**'ye kadar (2,5°'de), sabit bakıda eğime bağlı yayılım **189,9 °C** — eğim baskın ama bakı ihmal edilebilir değil. **C5 bunu DÜZELTMEDİ**: düzeltmek `aspect_grid` → `thermal_grid` → maliyet gridi → **her rota** demek; kalibrasyon ayrı bir özellik. **Yeni bulgu 2 — PSR tabanı ilk kez ölçülebilir oldu:** `PSR_ANNUAL_MAX_K` = 90 K (Paige 2010'un 80–110 K bandının ortası) ve **iki yönlü** yanlış: Site11 penceresinde PRP'nin en soğuk faseti **161,5 K**, yani tabanımız **71 K fazla soğuk** — penceredeki **16 253** hiç-aydınlanmayan hücre oraya çakıldığı için B'nin bias'ı A'nınkinin iki katına çıkıyor, mekanizma bu; ama 88°S kutup tarafındaki fasetlerin **%16,30**'u 90 K'nin **altında** (en soğuğu **28,4 K**), yani bölge genelinde taban fazla **sıcak**. Tek bir sabit, PRP'nin **26,8–348,7 K**'lik gerçek yayılımını temsil edemiyor; bir **bant ortası**ydı, bir hücre değeri değil. **Ölçüldü, yazıldı, dokunulmadı.** **Yayımlanmış bir sayının kendi aritmetiğimizle yeniden üretimi (C1'in `viper_corner_check`, C2'nin `jsc_survival_temperature_check` muadili) — `cold_trap_area_check`:** Williams vd. (2019) 80°S kutup tarafında tepe T < 110 K soğuk tuzakları **1,3×10⁴ km²** veriyor; PRP her üçgenin **üç köşesini** taşıdığı için alan `½|(v₂−v₁)×(v₃−v₁)|` ile doğrudan hesaplandı → **14 749,1 km², +%13,4** (112 757 soğuk üçgen; 80°S kutup tarafı 2 261 956 üçgen / **292 387 km²** — analitik küresel başlık **288 139 km²**, +%1,47: gerçek topografyaya giydirilmiş bir ağ için tutarlı, bağımsız bir sağlama). **Künye farkı açıkça yazıldı:** Williams kendi 240 m/px mevsimsel haritalarından, biz PRP v2'den (Paige 2010 modeli, ~544 m, Kaguya ağı) — **iki farklı yayımlanmış ürün**; fark ürünler hakkında bilgidir, bizim hatamız değil. Bu kontrol yalnız PRP'ye dayandığı için Williams'ın rasterleri olmadan da koşuyor. **Gece minimumu: `unavailable` + gerekçe** — Williams'ın 240 m/px mevsimsel min haritaları diskte değil ve PRP yerine geçemez (iki sıcaklık sütunu yüzeyde yıllık **maksimum** ve 2 cm'de yıllık **ortalama**; hiçbiri mevsimsel minimum değil); ayrıca istatistik boşluğu adlandırıldı: Williams'ın "min"i mevsimsel minimum, bizim `thermal_min` bir **denge**, heat1d'in gece dibi (C6: −232,4 °C) üçüncü bir büyüklük. **Uydurma sayı, sentetik veri, "temsili" örnek yazılmadı.** **Bit-eşitlik:** C5 planlayıcıya dokunmadı — LPR-1'in checked-in v5 maliyet-gridi SHA-256'sı (`55e1bb3c…`) kıpırdamadı, `COST_MODEL_ID` `…_v5`'te kaldı, `layer_validity` ve `weakest_validity` yükselmedi (C4'ün kararı korundu: NASA'nın türetilmiş ürünü maliyet etiketini yükseltmez, en zayıf girdi yönetmeye devam eder). VIPER özeti kilide **alınmadı** — 4af6989'un `slope_max_deg` 20°→15° düzeltmesinden beri C5'ten **önce de** tutmuyordu; kovalanmadı, gerekçesi testin yanına yazıldı. Ayrıca `slip_model.py`'de **iki bayat etiket** düzeltildi ("`thermal_grid.npy` is SYNTHETIC" doğru değil: grid `Heat1DModel` çıktısı ve `metadata.json` termal katmanı `DERIVED` diyor; SYNTHETIC yalnız heat1d yokken geçerli — C2'nin "etiketin yalan söylemesine izin verme" dersi). Tasarım: [spec](../superpowers/specs/2026-09-16-c5-diviner-prp-thermal-validation-design.md) (üç zorunlu soru, sondalar, sapmalar), [plan](../superpowers/plans/2026-09-16-c5-diviner-prp-thermal-validation.md). **Sapmalar:** kenardan kırpılan fasetler için **örtme süzgeci** eklendi (tasarımda yoktu; uygulama sırasında ölçülüp bulundu ve ana sayıyı 35,52 → 39,43 °C'ye **kötüleştirdi** — kötü sayı yayımlandı); LUT heat1d yeniden koşulmadan gönderilen gridden geri kazanıldı (12–15 dk yerine bedava ve **planlayıcının gerçekten okuduğu** tabloyu verir) ve sadakati ölçülüp yayımlandı — 205/208 kutu dolu, düz hücre tepesi −146,37 °C (C6'nın −146,4 °C'siyle uyuşuyor), ama **%22,96** hücre tutmuyor, en büyük fark **5,89 °C**, farklar hep **komşu kutu**: gönderilen termal grid diskteki eğim/bakı gridlerinden belgelenmiş en-yakın-kutu kuralıyla **bit-eşit üretilemiyor**; nedeni **saptanmadı** (gridlerin sonradan yeniden üretilmiş olması bu büyüklükle tutarlı olurdu, ama bu hipotez, ölçüm değil). Ayrıca: enlem şeridi pencerenin kendi aralığına kilitlendi; tarama 15° yerine 5° (15°'te minimum 285–300 arası belirsizdi); bir API ucu **eklenmedi** (C5 bir rapor üretiyor, bir çalışma zamanı katmanı değil; uç eklemek `layer_validity` yüzeyine dokunmayı gerektirir ve bit-eşitlik iddiasını gereksizce genişletirdi); `.gitignore`'a dört satır eklendi (köke çapalı `data/raw/` deseni `lunapath/data/raw/`'ı kapsamıyordu — C6'nın `.npz` için yaşadığı boşluğun aynısı); `scripts/setup_caches.py`'ye `diviner` adımı eklendi. Testler: **27 birim** (`test_thermal_validation.py`: Spearman'ın tanımsız kaldığı üç durum ve sıra temelliliği, RMSE güven aralığının n ile daralması, üçgen alanının köşe sırasından bağımsızlığı, soğuk-tuzak maskeleme/monotonluk/şekil reddi, tam barycentric nokta-içinde testi, ortalama↔maksimum ayrımı ve boş fasetin NaN kalması, atanmamış hücrenin hiçbir fasete ulaşmaması, **örtme kesrinin kırpılmış faseti yakalaması ve süzgecin RMSE'yi gerçekten değiştirmesi**, `*_QUOTED` sözlüklerinin ayrılığı, `grid_cell_centres` ↔ `grid_frame` uyumu) + **18 skip-korumalı gerçek grid** (`test_thermal_validation_real_grid.py`: önbellek ↔ PDS etiketi satır/bayt eşleşmesi, `DERIVED` etiketinin korunması, 80°S kapsaması, ~544 m faset boyu, alanların köşelerden yeniden hesabı, kelvin birimleri ve `temp_max ≥ temp_avg`, soğuk-tuzak büyüklük mertebesi ve eşiğe monotonluğu, **pencerede 20–200 faset** kilidi — sahte örneklem büyüklüğüne karşı açık bir bekçi, her hücrenin tam bir fasete düşmesi, üç adayın **aynı** örnekleme karşı ölçülmesi ve C'nin ikisinden de kötü çıkması, PSR tabanının iki yönlü bulgusu, **kenardan kırpılan fasetlerin varlığı ve süzgecin RMSE'yi kötüleştirdiğinin kilitlenmesi**, **LPR-1 maliyet-gridi SHA kilidi**, `COST_MODEL_ID`, `layer_validity`'nin yükselmemesi). Tam paket **25 failed / 2 314 passed / 5 skipped** (33 dk 09 s) — temiz HEAD (e7f6cbe) referansı 25 failed / 2 280 passed / 5 skipped ile **FAILED listesi `comm` ile birebir aynı** (ne yeni kırmızı, ne düzelen; 25 başarısızın hepsi önceden var olan `*_real_grid.py` pencere kayması), +34 geçen test C5'in. Bu koşumdan sonra örtme süzgeci için 4 test daha eklendi (27 birim + 18 gerçek grid) ve doğrudan koşuldu, hepsi geçiyor. `ruff check backend/app` **12**'de kaldı (taban), yeni dosyalar **0**.


**Ne:** 07 ve 11 no'lu belgeler "Diviner'ı indirin" diyordu; burada **hangi ürün, hangi çözünürlük, hangi ID** netleştiriliyor ki doğrulama bir günde yapılabilsin.

- [LRO Diviner **Polar Resource Products (PRP)**, PDS Geosciences / ODE](https://ode.rsl.wustl.edu/moon/pagehelp/Content/Missions_Instruments/LRO/DIVINER/PRP.htm): yıllık ortalama yüzey sıcaklığı, yıllık **maksimum** yüzey sıcaklığı, buz permafrost derinliği; kutuptan 80°'ye; üçgen ağ (2,88 M üçgen); `DLRE_PRP_SOUTH.TAB`; veri seti ID `LRO-L-DLRE-5-PRP-V2.0`. **Not:** heat1d LUT'umuz `nanmax` (yıllık tepe) alıyor — PRP'nin "annual maximum" ürünü tam bu istatistiğin ölçülmüş karşılığıdır; RMSE doğrudan hesaplanır.
- [Williams vd., Seasonal Polar Temperatures on the Moon, JGR Planets (2019)](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2019JE006028): 240 m/px yaz/kış **max/avg/min/amplitude** haritaları, 80°'ye kadar; 80°S'nin kutup tarafında gerçek soğuk tuzaklar **1,3×10⁴ km²** (tepe T < 110 K).
- [ICES 2023: LRO Diviner Polar Mapping Data Products (Williams vd.)](https://www.hou.usra.edu/meetings/ices2023/pdf/4046.pdf)

**Somut katkı:** `scripts/validate_thermal.py`: PRP annual-max ↔ `thermal_grid.npy` (eğim/bakı LUT) RMSE + Spearman; Williams min ↔ heat1d gece minimumu. Bu, 11 no'lu belgede "#5 Diviner'a karşı RMSE" maddesinin uygulama reçetesidir. **Efor:** 1 gün (indirme dahil).

---

## C6. ✅ ⭐⭐⭐ VIPER termal "operasyon zarfı": (Güneş azimutu × yükseklik × eğim) sınır-durum matrisi ve "tolere edilebilir saplanma süresi"

> **Yapıldı (5 Eylül 2026, `berke-3d-backendEnhance`):** NASA JSC/MSFC'nin VIPER çerçeveleri (Slusser vd., ICES-2025-376 — PDF `pypdf` ile çıkarılıp tamamı okundu) LunaPath'in kendi modeliyle kuruldu; belgeye üç düzeltme: makalenin zarf grafiği **eğim × Güneş azimutu (rover başlığına göre), görevin maksimum Güneş yüksekliğinde** (yükseklik ekseni "ileri iş"; 16 azimut × 6 eğim 0–15° = **96 kararlı-durum**, negatif eğimler dışarıda, 60+ bileşen), "12 °C aşım / 77 °C" bir **aviyonik kutusunun AFT normalizasyon örneği** (AFT 65 °C; kombinasyon verilmiyor), "tolerable entrenched time" termal değil **haven penceresi** tabanlı (Ay gecesinden önce hedef haven'a en hızlı rota; termal transient bu süreyle sınırlanır; SOC/gölge/rota-üstü arıza dışarıda; VIPER hızı yüzünden "always at risk of reaching thermal balance"); `t_inner_min/max` diye alan yok, zarf `bat_op_*`/`elec_op_*`. Yeni `backend/app/thermal_dwell.py`: iç sıcaklık kataloğun `thermal_tau_s`'iyle birinci dereceden gevşeyerek `surface_to_inner(yüzey(t))`'ye gider; yüzey(t) 4-B küpün zaten entegre ettiği regolit dinamiğidir (`cost_cube.surface_temperature_series` dışa çıkarıldı, küp aynı diziyi kullanır — **bit-eşit**); zarf = batarya ∩ elektronik en dar aralık (LPR-1/VIPER [0, 35] batarya); kapalı formlu çıkış süresi (`exit_time_h`: dışarıda → 0, hedef içeride → ∞, aksi τ·ln(…)); `build_dwell_cube` tüm başlangıç dilimlerini birlikte ilerletir (aktif çiftler, `last_outside` emeklisi; `DWELL_MAX_STATES` 1 M ile başlangıç ekseni kutulanır — gündüz m = 2 → 1,2 s, gece m = 5, VIPER m = 1) → `max_dwell_h[t, y, x]` (+∞ açık uçlu, NaN geçilmez) + yan/bileşen + hedef serisi; `route_inner_trace`, `route_dwell_report`, `cell_dwell` (tek hücre: `illumination_series.cell_shadow_series` mmap tek profil), `thermal_dwell_block`, `entrenchment_block`; heat1d `Model` alt sınıfıyla Güneş yüksekliği/azimutu kaydeden `heat1d_envelope_samples` + `bin_envelope` + `envelope_matrix` (**Güneş yüksekliği × Güneş'e paralel eğim** `s_par = atan(tan s·cos Δaz)`; JSC'nin rover-gövdesi ekseni yok, "aynı yöntem, bizim model"). **Isıtıcı:** kataloğa alan yazılmadı; `heater_model="none"` (varsayılan: ısıtıcı yalnız enerjide, bugünkü fizik) / `"thermostat_assumed"` (`constants.HEATER_THERMOSTAT_ASSUMPTION_SOURCE` `"assumption: …"`: ısıtıcı alt sınırı tutar); `thermal_tau_s` olmayan LUVMI-M'de dwell "unavailable" + neden (regolit tau'su uydurulmadı), denge kararı yine verilir. **Planlayıcı (`astar_4d(max_dwell_cube, require_thermal_dwell)`):** ilk sürüm "kalış ≤ max_dwell" kuralını `stay_h` ekseniyle uyguladı, planlayıcı **iki karanlık blok arasında ileri-geri hamleyle** boşa çıkardı (testte bulundu) → kısıt iç sıcaklığın **kendisine** bağlandı: etiket iç sıcaklığını taşır (bekleme: beklenen blok, hamle: varılan blok hedefi), zarf dışına çıkan **her geçiş** (bekleme/hamle) `thermal_dwell` reddi; termal marj beşinci baskınlık ekseni (%10 tolerans, 10 kutu — %1/400 ile Site11 gündüzde arama 2,3 GB / 10 dk bitmedi, %5/20 ile 156 s); kısıt kapalıyken tolerans ∞, anahtar 0 → **bit-eşit** (standart üç 4-B rota 41 / 116 / 8 hamle aynen, aynı düğüm sayısı; testte). Her zaman raporlanır: `path_stay_hours`, `path_max_dwell_h`, `path_dwell_margin_h`, `path_inner_c`, `metrics.min_dwell_margin_h/states_past_thermal_dwell/max_stay_h/thermal_dwell_enforced`. **LP-R12 `thermal_dwell`** ("The rover shall always satisfy stay_h <= max_dwell_h", `always (dwell_margin_h >= 0)`; 4-B ve telemetri; 2-B'de uygulanamaz; `fret.json` 12 gereksinim; D3'ün LP-R04/R05 statik değerleri değişmedi). **Saplanma:** `replan_triggers.check_entrenchment` (ok < %50, warning, critical ≥ %80 tetikler, fail ≥ %100; eşikler bizim), `/api/replan` `state.entrenched_hours` (+ `actual_inner_c`) → `entrenchment` bloğu: termal geri sayım + **haven penceresi** (A4 Dünya bağlantısı − A1 `time_to_safe_haven_h`; ulaşılabilir haven yoksa bütçe 0) + `overall`/`limiting`; `tolerable_entrenched_hours` state'e enjekte. API (yalnızca ekleme): `/api/plan-4d` `require_thermal_dwell`, `initial_inner_c`, `heater_model`; yanıt `thermal_dwell` bloğu (her zaman) + dört liste; 404'e "Thermal dwell: …" cümlesi; `/api/cell-telemetry?thermal_dwell=true&lookahead_hours&initial_inner_c&heater_model` kart + `tolerable_entrenched`; `GET /api/thermal-dwell` (kaba katman f32, açık uçlu ufka kapatılır + `open_ended` alanı, `X-Layer-Validity: MODEL`); `GET /api/thermal-envelope` (önbellekten; yoksa 422, sentetik yok); `scripts/build_thermal_envelope_cache.py` (10 eğim × 13 Ay günü crank-nicolson: 235 159 örnek, 205/288 kutu, yüzey −232,4…+44,5 °C, Güneş −2,62…+2,60°; betik 233 s; sondada aynı koşum 41,5 s, makine o an regresyon testleriyle yüklüydü). **Ölçüm (Site11; sondalar spec'te; `scripts/thermal_dwell_report.py` → [thermal_dwell_report.md](thermal_dwell_report.md), 8,8 dk):** SPICE Güneş yüksekliği yıllık −2,59…+2,55° (JSC: kutupta 1,5° + enlem derecesi; −88,92° ↔ 2,6°); heat1d düz hücre tepesi **−146,4 °C**, 30° Güneş'e bakan +44,5 °C → sıcak dalda iç +4,5 °C zarf **içinde**: **JSC'nin sıcak yanı Site11'de yok**; LPR-1/VIPER zarf matrisi 205 kutunun 19'u sınırsız (yüzey −60…−25), 173'ü soğuk-, 13'ü "sıcak"-sınırlı — hepsi yüzey −24…0 °C, ofset modelinin +60 K soğuk dalı (artefakt, öyle yazıldı). Denge iç sıcaklığı LPR-1 hücrelerinin %33,6'sında (tepe) / %10,4'ünde (soğuk uç) zarfta; PSR tabanına karşı 17,5 → 0 °C **16 dk** (VIPER 18 dk). Dwell küpü dilim 0: gündüz sınırsız %3,2 / soğuk %96,0 / sıcak %0,8, medyan 0,547 h; gece %0 / %100, 0,547 h; VIPER %17,2 / %73,2 / %9,5, 0,622 h; B1'in 10 h arıza beklemesi blokların **%100 / %100 / %84,1**'inde dwell'i aşıyor (12 h ufuklu katman; B1 DP'sine bağlanmadı, sayı verildi). **D3 dinamikle:** üç standart rota da (kısıtsız, T₀ 17,5, ısıtıcı yok) zarfı ilk **0,53–0,70 h**'te terk ediyor ve dönmüyor (gündüz min −15,7 °C, 41 durumun 34'ü dışı; gece −115,9 °C, 109/117; VIPER −49,5 °C, 7/9) — ihlal sürüyor, artık "ne zaman" sayısıyla. **Kısıt:** `none` → üç rota da gerekçeli **404** (gündüz 229 435 ret / 127 s; gece 3 014 / 19 s; VIPER 318 / 15 s); `thermostat_assumed` → üçü de **200 ve aynı rota** (41 / 116 / 8; iç min +5,1 / +0,6 / +6,4 °C; gündüz 35 848 düğüm ↔ kısıtsız 31 219; 40 / 109 / 17 s) — soğuk yan ısıtıcıya bırakılınca sıcak yan bağlayıcı değil. **Saplanma örnekleri:** Ay gecesi başlangıcı (186,34) termal bütçe **0,485 h** (soğuk/batarya; 0,1 h → ok, 0,25 h → warning, 0,5 h → fail), rota ortası (390,230, dilim 105) 0,420 h, gündüz başlangıcı (358,494) 0,486 h; **haven penceresi LPR-1 için her yerde 0 h** (A1: Site11'de ulaşılabilir haven yok; gece başlangıcında Dünya bağlantısı da yok) → `overall` her saplanma süresinde **fail** (sınırlayıcı haven) — JSC'nin saati saplanmadan önce dolmuş; termal sütun tek başına okunur; replan çağrısı 1,3–5 s. Süreler: `/api/plan-4d` gündüz kısıtsız 17,5 s (planlayıcı 5,6 s, küp 1,2 s, yüzey serisi 0,8 s; ilk çağrı 31 s). Tasarım: [spec](../superpowers/specs/2026-09-05-c6-thermal-dwell-design.md) (kaynak notu, sondalar, sapmalar, ölçümler), [plan](../superpowers/plans/2026-09-05-c6-thermal-dwell.md). **Sapmalar:** kısıt kalış yerine sıcaklık ekseni; termal tolerans %10/10 kutu; `DWELL_MAX_STATES` 5 M → 1 M; `last_outside` emeklisi; `data/processed/` gitignore deseni kapsamadığı için `.npz` açıkça eklendi; B1 DP'sine termal bağlanmadı (sayı verildi). Testler: 41 birim (`test_thermal_dwell.py`: hedef ↔ skaler 1e-12, zarf kesişimi, kapalı form üç durum/yan/bileşen, monotonluk, termostat, küp ↔ kapalı form (sabit ve iki parçalı hedef), açık uçlu/NaN/bütçe kutulama/T₀ dışı, rota raporu, iç iz, yüzey serisi ↔ küp bit-eşit, planlayıcı bit-eşitliği (aynı düğüm), kısıt reddi/kabulü/kıpırdanma boşluğu/iz tutarlılığı, LP-R12 katalog/FRET/iz/telemetri, saplanma seviyeleri/blok, hücre serisi/kart, blok şekilleri, zarf kutulama/matris/önbellek; biri heat1d varsa atlanır) + 13 API (`test_thermal_dwell_api.py`, çekirdeksiz: alanlar/sınırlar, iki blok şekli, kısıt 404 / termostat 200, τ'suz 422, hücre kartı, replan seviyeleri/tetikleyici/`utc`, katman JSON+f32, zarf ucu 422/200) + 6 skip-korumalı gerçek grid (`test_thermal_dwell_real_grid.py`: 41 / 116 / 8 hamle aynen + blok tutarlılığı, küp kesirleri sondayla uyumlu, kısıt 200/404 gerekçeli, gece saplanma bloğu, kaba katman, zarf önbelleğinde LPR-1 için gerçek sıcak dal yok; 7 dk 2 s); D3'ün iki testi 12 gereksinime güncellendi; tam paket **1 502 passed, 5 skipped** (1 uyarı, **21 dk 25 s**; B1'deki 1 443 passed / 4 skipped'a C6'nın 60 testi eklendi — 59'u geçti, biri heat1d kuruluyken atlanır; skip'lerin ikisi D2'nin `LUNAPATH_PPB_DIR` klon testleri, ikisi önceden var; tek uyarı önceden var olan `test_visibility_validation`'ınki; B1'in kayıtlı 43 dk'sı yüklü makinedeydi, bu koşumda makine boştu).

**Ne:** Rover'ın belirli bir Güneş geometrisi ve eğimde **ne kadar süre hareketsiz kalabileceğini** (izin verilen uçuş sıcaklığı AFT aşılmadan) veren zarf; NASA JSC bunu VIPER için hesaplama matrisini küçültmek amacıyla geliştirdi.

**Kim:** NASA JSC / MSFC — Slusser, Turk, Stewart, Page, Barragan, Mittag: [Generalizing Lunar Vehicle Thermal Analysis: Lessons Learned from VIPER (ICES-2025-376)](https://ntrs.nasa.gov/api/citations/20250004028/downloads/ICES-2025-376_Final.pdf). Kutupta maksimum Güneş yüksekliği ~1,5°; "unlimited operations envelope" grafiği: Güneş azimutuna paralel eğim açısı vs. yükseklik; bazı kombinasyonlarda AFT **12 °C** aşılmış (77 °C); "tolerable entrenched time" (regolite saplanma durumunda dayanma süresi) çerçevesi.

**LunaPath'te bugün:** `thermal_model.Heat1DModel` eğim/bakı LUT; iç sıcaklık log-barrier; ama "bu hücrede en fazla kaç saat durabilirim" katmanı yok.

**Somut katkı:** `max_dwell_hours[y,x,t]` = iç sıcaklık modelinin AFT (rover kataloğundaki `t_inner_min/max`) sınırına ulaşma süresi; WAIT kenarı bu süreyi aşamaz; `replan_triggers`'a "entrenchment" senaryosu (hareket edemeyen rover, saplanma anından itibaren geri sayım). Challenge Modül 4 ("gölgede kalma süresini izlemek, warning/critical/fail") doğrudan bununla karşılanır.

**Efor:** 2 gün (heat1d çağrıları önbelleklenirse). Wow: orta-yüksek ("NASA JSC'nin VIPER için kullandığı zarf yaklaşımı").

---

# BÖLÜM D — Algoritma, kıyaslama ve mühendislik "wow"ları

## D1. ⭐⭐⭐ Herhangi-açı planlama: Theta* / Field D* — MER'de uçmuş algoritma ailesi

**Ne:** 8-komşuluk grid'in 45° kırıklı yollarını, hücre kenarlarındaki herhangi bir noktadan geçebilen (enterpolasyonlu) yollarla değiştirmek; %5–8 daha kısa ve fiziksel olarak daha gerçekçi rotalar.

**Kim:** CMU (Ferguson & Stentz) + JPL (Carsten, Rankin, Maimone): [Global Path Planning on Board the Mars Exploration Rovers (IEEE Aerospace 2007, PDF)](https://www-robotics.jpl.nasa.gov/media/documents/IEEEAC-Carsten-1125.pdf) — Field D* 2006 yazında Spirit ve Opportunity'ye yüklendi; **<1 MB bellek**, 50 m × 50 m maliyet haritası, 40 cm maliyet hücreleri; GESTALT'ın kapalı-koridor hatasını çözdü. [CMU haber](https://www.cs.cmu.edu/news/2007/carnegie-mellon-software-steers-nasas-mars-roverfirst-test-new-autonomous-capability-mars).
- Benchmark kanıtı: MoonPlanBench'te Theta* Ay kutup haritalarında **%100 başarı** (D2).

**LunaPath'te bugün:** 8-komşuluk A*; 05 ve 08 no'lu belgelerde Theta* adı geçiyor ama uygulanmamış.

**Somut katkı:** En ucuz yol: A* sonrası **görüş-hattı (line-of-sight) yumuşatma** (Theta*'ın post-process versiyonu) — maliyet katmanı üzerinde LOS kontrolüyle; 4B planlayıcı için zaman dilimi içinde geçerli. Metriklerde `path_length_m` düşer, `heading_changes` yeni metrik. Sunum: "MER'de uçan Field D* ailesinin herhangi-açı ilkesini uyguluyoruz."

**Efor:** 1 gün. Wow: orta (isim değeri yüksek, challenge etkisi düşük).

---

## D2. ✅ ⭐⭐⭐⭐ Dış benchmark: MoonPlanBench (Aralık 2025)

> **Yapıldı (5 Eylül 2026, `berke-3d-backendEnhance`):** MoonPlanBench'in **36 haritası** (12 LOLA kutup LDEM ürünü `LDEM_45N_100M … LDEM_875S_5M` × 10°/15°/20° eşik; makalenin tablo başlığındaki "her varyant 36 harita" yanlış, Drive listesi ve tablodaki 1/12'nin katı başarı oranları 12 harita/varyant verir) yazarların Google Drive klasöründen indirildi (`scripts/build_moonplanbench_cache.py`, bağımlılıksız `embeddedfolderview` + `uc?export=download`, dosya başına SHA-256'lı `moonplanbench_meta.json`; `lunapath/data/benchmarks/` gitignore; 7,0 MB; `.npy` uint8, sıfır olmayan = dolu; 243²–477²; hücre = ürün çözünürlüğü × 64 = **320 m – 7 680 m**, boş oran %51–96). Lisans: veri için makalenin CC BY-NC-SA 4.0'ı (Drive'da ve depo kökünde lisans dosyası yok); PathBench BSD-3, PythonRobotics MIT; yazarların adaptörleri vendor edilmedi, yalnız `--reference-dir <klon>` ile içe aktarılır. Yeni `backend/app/benchmark.py`: benchmark'ın başlangıç/hedef kuralı (`adapters/_common.auto_select_start_goal`: en büyük 8-bağlantılı boş bileşen, (satır, sütun) en küçük başlangıç, en uzak hedef) aynı BFS sırasıyla yeniden uygulandı — **36/36 harita deponun fonksiyonuyla aynı**; PathBench metrik tanımları (`basic_testing.get_results`/`analyzer`: uzunluk = Öklid hücre toplamı, düzgünlük = işaretsiz başlık açısı değişimi/iz noktası, açıklık = en yakın dolu hücreye ortalama mesafe, hedefe kalan, başarılı-koşu filtresi); occupancy→grids adaptörü (`traversable = occ == 0`, eğim/gölge 0, termal sabit; `traversable` DERIVED, diğerleri SYNTHETIC); dört mod: `dijkstra_cut` (benchmark'ın PythonRobotics hareket modeli: köşe-kesme serbest), `dijkstra_nocut` (LunaPath kuralı; `nav2_baseline` artık buradan içe aktarır), `lunapath_single` (`w_slope = 1`), `lunapath_multi` (LPR-1 varsayılanı); isteğe bağlı aynı-makine referanslar (PythonRobotics Dijkstra/A\*/Theta\*, Theta\* için ham ve Bresenham-döşenmiş uzunluk). API ucu **eklenmedi** (YAGNI; sözleşme belgesine dokunulmadı). Rapor: `scripts/moonplanbench_runner.py` (`--json` önce, `--from-json`, `--maps N`, `--reference-dir`, `--memory`) → [moonplanbench_report.md](moonplanbench_report.md). **Ölçüm (36 harita, bu makine, tam koşum 1 715 s):** `dijkstra_cut` başarı 100/100/100 %, ortalama uzunluk **651,81 / 636,16 / 620,24 hücre = makalenin Dijkstra satırı iki ondalıkta aynen** (Tablo 1, alıntı; harita başına uzunluklar aynı-makine PythonRobotics Dijkstra'yla aynı; MPB-10 başlangıç–hedef düz mesafe ortalaması 554,06 = makalede RRT-Connect'in %0 satırındaki 554,1; Theta\* döşenmiş 654,61 / 639,14 / 623,17 ↔ makale 654,81 / 639,14 / 623,17, ham 625,04 / 617,90 / 611,40). **LunaPath'in köşe-kesme yasağıyla** (`dijkstra_nocut`, `lunapath_single`, `lunapath_multi` üçü aynı) başarı **33,3 / 91,7 / 100 %**, başarılı haritalarda uzunluk 720,30 / 658,34 / 631,88, hedefe kalan ort. 364,0 / 55,7 / 0 hücre: MPB-10'da 12 haritanın **8'i yalnız köşe-kesmeyle bağlantılı** (`60S`, `75N`, `75S`, `80S`, `85N`, `85S`, `875N`, `875S`), MPB-15'te `875S`; kesmesiz Dijkstra'nın yol bulduğu her haritada LunaPath da buldu → fark planlayıcıda değil hareket modelinde; makalenin %100'ü sıfır genişlikli çapraz aralıklardan geçmeye dayanır. **Çok kriterli mod hiçbir şey satın almıyor:** maliyet gridi 36 haritanın hepsinde **tek değer** (0,190969; eğim 0, gölge 0, termal sabit), tek/çok kriter uzunlukları 36/36 aynı — belgedeki "X % gölge azalması" cümlesi bu benchmark'ta **kurulamaz**, öyle yazıldı. **Süre (tracemalloc kapalı):** LunaPath A\* harita başına ort. 0,22–0,39 s (maks 0,68 s; ort. 18–33 k düğüm, maks 99 160), saf Dijkstra 0,31–0,59 s; aynı makinede PythonRobotics Dijkstra 3,3–8,2 s, A\* 7,8–13,5 s (maks 29,7 s), Theta\* 4,7–8,1 s; makale 13–32 s (yazarların dizüstü, PathBench tekrar oynatması ve `tracemalloc` **açık**). Yöntem bulgusu: `tracemalloc` açıkken LunaPath 5,8–11,8 s (≈ 30×), Dijkstra 3,0–5,5 s (≈ 10×) — sondadaki "6–24 s" o yüzdendi; bellek bu yüzden ayrı `--memory` geçişinde ölçülür (LunaPath tepe 43,7–44,3 MB, Dijkstra 19–67 MB); hiçbir koşu 60 s'yi aşmadı; makalenin A\* başarısızlıkları (91 / 83 %) bu makinede oluşmadı (aynı A\* 36/36, maks 29,7 s). Tasarım: [spec](../superpowers/specs/2026-09-05-d2-moonplanbench-design.md) (sondalar, sapmalar, yeniden üretim kilitleri), [plan](../superpowers/plans/2026-09-05-d2-moonplanbench.md). **Sapmalar:** bellek/süre ayrı geçişler; 12 harita/varyant; `distance_to_goal` kısmi yolda son hücreden; gerçek veri testi BFS'yi modül fixture'ında bir kez hesaplar. Testler: 45 birim (`test_benchmark.py`; ikisi `LUNAPATH_PPB_DIR` klonu ister, yoksa atlanır) + 9 skip-korumalı gerçek veri (`test_benchmark_real_data.py`: 36 dosya, meta SHA'ları, 36 başlangıç/hedef çifti, `dijkstra_cut` üç varyantta makalenin Dijkstra uzunluğu ± 0,01 kilidi, dört mod bir haritada); tam paket 1 391 passed, 2 skipped (13:49; C4'teki 1 338'e +53; tek uyarı önceden var olan `test_visibility_validation`'ınki).


**Ne:** Ay kutuplarının LOLA DEM'lerinden türetilmiş **36 standart planlama haritası** (10°/15°/20° eğim eşikli üç varyant), tanımlı metrikler (başarı oranı, yol uzunluğu, süre, hedefe uzaklık, bellek, düzgünlük, engel açıklığı) ve referans planlayıcılar (Dijkstra, A*, Theta*, RRT ailesi, öğrenme tabanlı 4 model).

**Kim:** Marvin Chancán vd. — [Planetary Terrain Datasets and Benchmarks for Rover Path Planning (arXiv 2512.21438)](https://arxiv.org/abs/2512.21438) · [GitHub mchancan/PlanetaryPathBench](https://github.com/mchancan/PlanetaryPathBench) (veri CC BY-NC-SA 4.0; kod PythonRobotics/PathBench türevi). Sonuçlar: MoonPlanBench-10'da Dijkstra ve Theta* %100 başarı, ~651–654 hücre yol; RRT %8; öğrenme tabanlı modeller gezegen arazisine genellemiyor, en iyisi (WPN) 10× yavaş.

**LunaPath'te bugün:** yalnızca kendi nav2 baseline kıyası.

**Somut katkı:** `scripts/moonplanbench_runner.py`: LunaPath'in `pathfinder` (tek kriter: eğim) ve çok kriterli modunu 36 haritada koşturup aynı metrik tablosunu üretmek. Jüri için: "bağımsız bir benchmark'ta A*/Theta* ile aynı %100 başarı, artı çok kriterli maliyetin getirdiği X% gölge azalması." Ayrıca öğrenme tabanlı planlayıcı **kullanmama** kararımızın literatür kanıtı olur.

**Efor:** 1 gün. **Not:** veri lisansı ticari kullanımı kısıtlar; hackathon/akademik kullanım uygundur.

---

## D3. ✅ ⭐⭐⭐⭐ Formal güvenlik gereksinimleri: FRET (NASA) + STL robustness monitörü (RTAMT)

> **Yapıldı (4 Eylül 2026, `berke-3d-backendEnhance`):** 11 gereksinim **FRETISH kalıbında elle yazıldı** (`[scope] [condition] the rover shall [timing] [response]`; FRET aracı kurulmadı, "FRET ile üretildi" denmiyor), her biri elle STL'e çevrildi ve eşikleri rover kataloğundan okunuyor (`h_max_shadow_h`, `soc_min_pct`, `elec_op_*`, `bat_op_*`, `slope_max_deg`, `slope_lateral_max_deg`; tek katalog sabiti 6 h şarj son tarihi): [requirements/lunapath.fret.json](../requirements/lunapath.fret.json) + [README](../requirements/README.md), `fret_export()`'tan üretilir ve testle birebirliği korunur. `safety_monitor.py`: küçük STL AST'si, **iki motor** (RTAMT 0.3.5 ayrık-zaman offline + aynı semantiği taşıyan yerleşik değerlendirici; RTAMT'nin sonlu-iz kuralları — pencere kırpma, boş pencere ±∞ — ölçülüp testlere sabitlendi), pencereli davranışı türetilmiş **saat sayaçlarına** gömen iz çeviricileri (2-B `RoverState`, 4-B plan yanıtı, telemetri; mahsur kalan iz simülatörün kendi sınırıyla bir Ay günü uzatılır), kapsamlar örnek maskesi; her istekte iki motor çapraz kontrol edilir (`cross_check.max_abs_diff`, gerçek rotalarda **0**). API: `/api/plan`, `/api/plan-4d`, `/api/compare`/`/api/plan-multi` yanıtlarına `safety_margins` (gereksinim başına ρ, birim, ρ/ölçek, sağlandı/sınır/açık uçlu/beklemede, en kötü nokta, FRETISH + STL), `comparison.safety_margin_ranking`; `POST /api/safety-check` (telemetri izi); ROS 2 `safety_monitor_node.py` (BatteryState/Temperature/Float32/Odometry → `SafetyMonitorSession` → yeni ihlal başına bir `ReplanTrigger`, `trigger_id "safety:LP-R02"`). **Ölçüm (Site11):** VIPER haven→haven 30 May 2027 (41 durum, 7,36 h): gölge marjı 91,45 h, SOC 12,06 pp, adım eğimi **0,48°** (rota eğim sınırına yaslı, B3 ile tutarlı), yanal 1,19°, Dünya bağlantısı 199,93 h, haven 199,80 h (A1'in `min_haven_margin_h`'ı birebir); **LP-R04/R05 ihlal**: iç sıcaklık −7,96 °C elektronik / **−27,96 °C batarya** zarfının dışında (durum #16, hücre (73,118), 2,77 h) — statik `sunlit_peak` termal katmanı + `surface_to_inner` ofseti rover zarfıyla tutarsız, ısıtıcı gücü enerji modelinde sayılıp sıcaklık modelinde yok; hiçbir mevcut denetim (`check_profile_constraints`, planlayıcı) termali kontrol etmiyordu → C6'ya açık madde. LPR-1 28 Eyl 2026: gölge 49,79 h, SOC 76,16 pp, termal −17,96/−27,96 °C, **LP-R09 sınırsız ihlal** (Dünya bağlantısı 184,6 h sonra bitiyor, o Ay gününde ulaşılabilir haven yok — B5'in bulgusu formal kararla). 2-B `/api/compare` (VIPER, 4 profil): gölge 91,67 h, SOC 47,15 pp, eğim 2,58°, yanal 0,66°, batarya termali −46,04 °C — eski ikili `constraint_check` dördünde de "sağlandı" derken marj bloğu termal ihlali ve marjları veriyor. SHERPA dağılımlarından ρ (1.000 koşum): VIPER SOC marjı plan 12,1 pp → koşumlarda p5/p50/p95 **−20 / −20 / −4,9 pp** (rezerv ihlali %98,6), gölge 89,2/90,7/92,4 h; LPR-1 SOC 32,3/58,0/72,5 pp. Süreler: plan bloğu milisaniye (plan-4d 10–12 s'in içinde), compare 4 profil 0,8–1,0 s, `/api/safety-check` 500 örnek 12–15 ms yerleşik / 28–48 ms RTAMT. Testler: 57 birim (+3 ROS, rclpy yoksa atlanır), 17 API, 4 skip-korumalı gerçek grid. Rapor: [safety_monitor_report.md](safety_monitor_report.md). Tasarım: [../superpowers/specs/2026-09-04-d3-formal-safety-design.md](../superpowers/specs/2026-09-04-d3-formal-safety-design.md). Sapmalar: planlayıcının `path_haven_margin_h: None`'ı iki anlamlı (Dünya batmıyor +∞ / sonlu batış + haven yok −∞) — `path_time_to_haven_h` ile ayrıştırıldı; tek örnekli kapsamda (varış) RTAMT ayrık-zaman yorumlayıcısı çalışmadığından o gereksinim yerleşik motorla değerlendirilip girdide `engine` söyleniyor; rtamt'ın `antlr4-python3-runtime==4.7` pini ortamdaki omegaconf/hydra ile çakıştı, 4.9.3 çalışma zamanında doğrulandı ve sürüm uyarısı bastırıldı; `/api/stress-test`'e ρ dağılımı eklenmedi (raporda B5 dağılımlarından aritmetikle); monitör hatası planı düşürmez (blok yok, log).

**Ne:** "Rover hiçbir zaman 50 saatten uzun kesintisiz gölgede kalmayacak", "iç sıcaklık her zaman −40 °C üstünde olacak", "SOC %20'nin altına düşerse 6 saat içinde şarj başlayacak" gibi kuralları **yapılandırılmış doğal dilde (FRETISH)** yazıp otomatik olarak zamansal mantığa çevirmek; planlanan rotanın telemetri izini bu formüllerle **nicel** (robustness = kural ihlaline kaç saat / kaç derece kaldı) denetlemek.

**Kim / araçlar:**
- NASA Ames — [FRET: Formal Requirements Elicitation Tool (GitHub NASA-SW-VnV/fret, açık kaynak)](https://github.com/NASA-SW-VnV/fret) · [Giannakopoulou vd., NTRS 2020](https://ntrs.nasa.gov/api/citations/20200001989/downloads/20200001989.pdf) · [Space ROS dokümantasyonunda FRET](https://space-ros.github.io/docs/rolling/Related-Projects/FRET.html) · [Robotics: A New Mission for FRET Requirements (2024)](https://link.springer.com/chapter/10.1007/978-3-031-60698-4_22) · [Towards a Catalogue of Requirement Patterns for Space Robotic Missions (arXiv 2511.14438)](https://arxiv.org/pdf/2511.14438)
- AIT Avusturya — Dejan Ničković: [RTAMT — Runtime Robustness Monitors (GitHub, BSD-3)](https://github.com/nickovic/rtamt) · [STTT 2023 / arXiv 2501.18608](https://arxiv.org/abs/2501.18608): ayrık/yoğun zaman, online/offline STL, C++ arka uç, `rtamt4ros`.
- FRET → Copilot/Ogma → ROS 2 monitör düğümleri: [Monitoring ROS2: from Requirements to Autonomous Robots (arXiv 2209.14030)](https://arxiv.org/pdf/2209.14030).

**LunaPath'te bugün:** kısıtlar log-barrier ve `check_profile_constraints` ile; ROS 2 kabuğu var; ama gereksinimler formal değil, ihlal marjı ölçülmüyor.

**Somut katkı:**
1. `docs/requirements/lunapath.fret.json`: 8–10 FRETISH gereksinim (termal, gölge, SOC, eğim, DTE); FRET'in ürettiği LTL/STL formülleri belgeye.
2. `safety_monitor.py`: `simulate_path` telemetri izini RTAMT offline monitörüne verir → her kural için robustness ρ (saat/°C/%); `/api/plan` yanıtına `safety_margins` bloğu; `/api/compare` "en küçük marj" ile sıralar.
3. ROS 2 kabuğunda `rtamt4ros` düğümü → replan tetikleyicilerinin formal versiyonu.

**Neden wow:** "Gereksinimlerimiz NASA'nın FRET aracıyla formal olarak yazıldı ve her rota bu gereksinimlere karşı nicel olarak denetleniyor" — akademik jüri için nadir görülen bir olgunluk sinyali; challenge Modül 9 ("validation checklist") doğrudan karşılanır.

**Efor:** 2–3 gün. Bağımlılık: yok.

---

## D4. ✅ ⭐⭐⭐ Kontrastif açıklama: "neden bu rota, neden şu değil?"

**Ne:** Kullanıcının çizdiği/önerdiği alternatif rotanın neden seçilmediğini, ihlal edilen kısıtlar ve maliyet farklarıyla açıklamak; ayrıca "rotanın değişmesi için hangi ağırlığın ne kadar değişmesi gerekir" (karşı-olgusal) sorusunu yanıtlamak.

**Kim / literatür (XAIP):** [Krarup vd., Model-Based Contrastive Explanations for Explainable Planning (ICAPS 2019 XAIP)](https://strathprints.strath.ac.uk/69957/1/Krarup_etal_ICAPS2019_Model_based_contrastive_explanations_explainable_planning.pdf) · [Contrastive Explanations of Plans Through Model Restrictions (arXiv 2103.15575)](https://arxiv.org/pdf/2103.15575) · [Leveraging Counterfactual Paths for Contrastive Explanations of POMDP Policies (arXiv 2403.19760)](https://arxiv.org/pdf/2403.19760) · [Towards Transparent Robotic Planning via Contrastive Explanations (arXiv 2003.07425)](https://arxiv.org/pdf/2003.07425).

**LunaPath'te bugün:** `CostMap.explain()` ve `cost_breakdown` — "neden bu" var, "neden o değil" yok; 11 no'lu belge açıklanabilirliği 5/5 vermiş, bu onu **farklılaştırıcı** yapar.

**Somut katkı:** `/api/explain-contrast`: girdi = alternatif rota (nokta listesi) → çıktı = (a) ihlal edilen sert kısıtlar (hücre, hangi kural, ne kadar), (b) kriter bazında maliyet farkı, (c) **minimum ağırlık değişimi** (ikili arama ile: w_thermal'ı hangi değere çekince alternatif kazanır). Challenge Modül 6 "route rejection/explanation" çıktısı birebir.

**Efor:** 1–2 gün.

> **Yapıldı (16 Eylül 2026, `tuna/backendEnhance`):** Yeni `backend/app/contrastive.py` +
> yeni `POST /api/explain-contrast` (yalnızca ekleme; `pathfinder.py` **tek satır** değişmedi).
> Çekirdek bulgu şu: A\*'ın minimize ettiği g-skoru, sabit bir rota için ağırlık vektöründe
> **tam olarak afin** — `cost(R,w) = D(R) + Σ_k w_k·I_k(R) + B(R)`, burada `I_k` kriterin
> **yamuk çizgi integrali** ve bariyer ağırlıktan bağımsız. Bu yüzden "hangi ağırlık alternatifi
> öne geçirir" sorusu **kapalı form**, arama değil (belgenin önerdiği **ikili arama
> kullanılmadı** — gerekçesi aşağıda). Kimlik koşullu ve koşul varsayılmıyor: `MIN_CELL_COST`
> kelepçesi her rotada, **her değerlendirilen ağırlıkta** ölçülüyor (`PlanWeights` beş ağırlığın
> da 0 olmasına izin veriyor ve orada hücrelerin %100'ü kelepçeleniyor).
>
> **Belgenin "ikili arama ile" öncülü tutmadı.** "Alternatif kazanır" iki ayrı önerme:
> alternatif *gösterdiğimiz* rotadan ucuz olur (`vs_fact`, kapalı form, **0** yeniden planlama)
> ve planlayıcı alternatifi **döndürür** (`vs_replanned`). İkincisinde
> `Δ(w) = cost_alt(w) − min_R cost_R(w)` afin eksi afinlerin noktasal minimumu, yani
> **konveks**; sıfır kümesi bir **aralık**, yarı-doğru değil — dolayısıyla yüklem **monoton
> değil** ve ikili aramanın yakınsayacağı bir eşik yok. Konvekslik **ölçüldü** (41 nokta,
> 39 ikinci fark, en küçüğü **−6,8e-13**). `Δ_(ii) ≥ Δ_(i)` her noktada, bu yüzden (i) kutuda
> bir şey bulamıyorsa (ii) de bulamaz — **kanıtla, taramayla değil**.
>
> **"Minimum ağırlık değişimi" adı da hak edilmiyordu ve düzeltildi.** Üretilen şey
> `per_criterion_flip_threshold`: ters problemin **tek boyutlu kesiti**, bir ağırlık oynar,
> diğer dördü durur — bir **norm minimize etmiyor**. Gerçek ℓ₂-minimal ortak hamle
> (`l2_minimal_joint_move`) yanında, kapalı formda yayımlanıyor. Ağırlık **yeniden
> normalleştirilmiyor**: C4 `w_roughness`'ı toplama ekledi, ve dört profilin de ilk dördü
> tam 1,000000, toplam 1,150 (`get_rover` ile ölçüldü).
>
> **Sonuç sözlüğü dört değil on etiket.** Belgenin dördü (`hard_gate`,
> `dominated_on_every_criterion`, `outside_weight_bounds`, `found…`) burada; diğer altısı
> ölçümün erişilebilir gösterdiği ve dörde yıkılsa **uydurma olumsuz** üretecek hâller
> (`found_returned_by_planner`, `unresolved_by_scan`, `criterion_has_no_leverage`,
> `no_incumbent_route`, `clamp_binds`, `foil_is_the_fact`). `found` bilerek bölündü: bir konsolda
> "found: 0,42" okuyan operatör ağırlığı ayarlar ve **üçüncü** bir rota alır.
>
> **Ölçüm (Site11, `scripts/contrastive_explanation_report.py` →
> [contrastive_explanation_report.md](contrastive_explanation_report.md)):** 3 standart çift ×
> 3 alternatif türü = 9 vaka. `hard_gate` **3** (üç çiftte de kullanıcının çizeceği **düz
> çizgi**; 53/40/14 geçilemez hücre), `dominated_on_every_criterion` **2**,
> `found_vs_fact_only` **4**. `found_returned_by_planner` **hiç çıkmadı**: 41 noktalık tam
> eksen taraması planlayıcıyı alternatifi döndürmeye **hiçbir** ağırlıkta ikna etmedi.
> Yineleme maliyeti **0,2206 s** (0,1049 grid + 0,1157 A\*).
>
> **Manşet — karşı-olgusal modelin kendi gürültüsünün içinde olabiliyor.** Tek bir "model
> çözünürlüğü" yok: dört taban ölçüldü ve **dokuz mertebe** ayrışıyorlar (aritmetik ~1e-10;
> yayın 1e-4 — bu modül kendi float64 integrallerini farkladığı için **emekli**;
> bariyer tablosunun 1024 kovası 3,3e-4–4,2e-2; NASA'nın 20 DEM klonu **σ = 4,80–17,85**
> ağırlıklı metre). Bantlı 4 vakanın **2 tanesinde** fark arazi topluluğunun altında kaldı ve
> cevap `closer_than_the_model_resolves(level=terrain_ensemble)` oldu. *Ay gecesi / sapma*
> çiftinde nominal DEM "planlayıcının rotası 3,68 ağırlıklı metre ucuz" derken klonların
> **4 tanesinde işaret ters dönüyor**. Kapılar da tek bir rasterin özelliği: gündüz çiftinde
> planlayıcının **kendi** rotası 20 klonun **6'sında** takılıyor, VIPER kısa leg'de (15° limit)
> **her iki rota da 20/20'sinde**.
>
> **`risk_alpha` bant olarak kullanılmadı ve gerekçesi yazıldı:** o bir belirsizlik değil,
> operatörün **risk iştahı** (`risk.py` kendi söylüyor), en küçük üyesi bile μ+0,798σ olduğu
> için nominali ortalamaz, ve yalnız `f_slope`/`f_energy`'ye ulaşır — mesafe, bariyer ve
> gölge/termal/pürüzlülük hiç etkilenmez. **D5'in "94×" cümlesi de tekrarlanmadı:** o
> karşılaştırma saatteki bir **ortak-mod seviye kaymasıyla** bir cephe genişliğini yan yana
> koyuyordu, ve D4'ün farkı ağırlıklı metrede — ikisi arasında dönüşüm yok.
>
> **Bu maddedeki yöntem atfı birinci elden okununca düzeltildi.** Krarup vd. kontrastif
> **çerçeveyi** veriyor, ama `vs_replanned` onların **model kısıtlaması** tanımına (2103.15575,
> Tanım 4: kısıtlı modelin planları orijinalinkilerin alt kümesi olmalı) **girmiyor** —
> yeniden ağırlıklandırma plan kümesine dokunmaz, yalnız yeniden fiyatlar; bu bir model
> **revizyonu**. Krarup'a karşılık gelen aslında **(i)** rejimi (φ = "plan tam olarak
> alternatif" total kısıtlaması). Ağırlık karşı-olgusalı dört XAIP kaynağının **hiçbirinde
> yok**: evi **ters optimizasyon** — inverse shortest paths (Burton & Toint 1992) ve
> Heuberger'in taraması. Kriter bazında ayrıştırmanın (b) en yakın öncülü ise Sukkerd,
> Simmons & Garlan 2020 (arXiv:2004.12960), belgede hiç anılmıyordu. Hepsi
> `contrastive.CONTRASTIVE_QUOTED`'da, bizim sayılarımızla aynı tabloda değil.
>
> **Bit-eşitlik:** LPR-1 v5 maliyet-gridi SHA-256 özeti
> `55e1bb3cd3b9fb93403140b283cfa38fef8b93836a28512bc95f38db5ed893db` kıpırdamadı,
> `COST_MODEL_ID` `…_v5`'te, `pathfinder.py` değişmedi. 81 yeni test bunu kilitliyor.
>
> **2-B yalnız.** `pathfinder` `weighted_metres`, `pathfinder_4d` `weighted_hours` yayımlıyor;
> iki toplam karşılaştırılamaz, kod bunu guard'lıyor. 4-B kontrastı kapsam dışı, gerekçesi
> [tasarım belgesinde](../superpowers/specs/2026-09-16-d4-kontrastif-aciklama-design.md).

---

## D5. ✅ ⭐⭐⭐ Pareto cephesi: ağırlık tartışması yerine baskın-olmayan rota ailesi

> **Yapıldı (16 Eylül 2026, `tuna/backendEnhance`):** Yeni `backend/app/pareto.py` + yeni
> `POST /api/pareto` (yalnızca ekleme). Ağırlık **4-simpleksinden** tekdüze çekilen vektörlerle
> (normalize `standard_exponential` = Dirichlet(1,1,1,1), sabit tohum; numpy'ın `dirichlet`'iyle
> **1 ULP** ayrılıyor, bilerek ona bağlanmadı) 2-B planlayıcı koşuluyor, rotalar **hücre dizisinin
> SHA-256'sıyla** tekilleştiriliyor, mahsur rotalar **dışlanıyor** (totalleri yalnız yürüdükleri
> öneki anlattığı için erken başarısız olarak cepheye girerlerdi) ve dört hedefte baskınlık
> süzgecinden geçiriliyor. Hedefler yön alanlarıyla saklanıyor: `hours`
> (`summary.total_elapsed_hours`), `energy_wh` (`…total_energy_consumed_wh`, brüt),
> `shadow_exposure_h` (`…total_shadow_exposure` = Σ gölge_oranı·Δt — **gölge saati değil**),
> `thermal_risk` (`astar_metrics.max_thermal_risk`); dördü de `minimize`.
> **Belgenin "termal marj, büyük iyi" öncülü tutmuyor:** depoda rota düzeyinde marj yok,
> `max_thermal_risk` bir **ceza**. Baskınlık her hedefin **kendi yayın kuantumunda** (1e-4 sa /
> 1e-2 Wh / 1e-4 / 1e-4) karara bağlanıyor — kuantumun altındaki epsilon anlamsız olurdu.
>
> **Ölçüm (Site11, `scripts/pareto_front_report.py` → [pareto_front_report.md](pareto_front_report.md)):**
> dört senaryoda 25 vektör → **15-24 farklı rota → yalnız 1-2 baskın-olmayan**. Bütçe büyütülünce
> (9 → 211 vektör) farklı rota 9 → 65, cephe **1 → 4**: yani cephe tek nokta **değil**, ama
> bütçeden çok daha yavaş büyüyor — ilk manşet ("tek noktaya çöküyor") kendi ölçümümüzde düştü ve
> yayımlanmadı. Simpleksin bir **köşesi** (`w_slope=1`) cephede, bu yüzden `include_corners` var.
> `f_thermal` LPR-1'in 210 063 geçilebilir hücresinin **%72,7'sinde ≥ 0,99** (VIPER 161 793'ün
> %65,2'si), dolayısıyla `thermal_risk` çoğu senaryoda **sabit bir eksen**: "dört hedefli cephe"
> aslında **üç** hedefli ve yanıt bunu `constant_objectives`/`effective_objectives` ile söylüyor.
> Kalan eksenler aynı sıralamayı veriyor (Spearman, **farklı rotalar** üzerinden — ham örnekler
> pseudo-replikasyon olurdu): saat~enerji 0,995-1,000, saat~gölge 0,62-0,99.
>
> **Manşet.** Cephenin genişliği saatte **%0,179**, tüm örneklenen rotalarınki **%22,2**. Aynı
> rotaya B2'nin CVaR kuyruğu α=0,5'te **+%16,90** (α=0,99'da +%107,95) ekliyor — yani **hayatta
> kalanların arası modelin en iyimser belirsizlik bandından ~94× dar**. Ağırlık tartışması bu
> arazide iki ayrı sorudur: **kötü bir vektör seçmek ölçülebilir bir hatadır (%22), iyi vektörler
> arasında seçim yapmak bu modelin çözemeyeceği bir sorudur.** Nominal (rover varsayılanı) rota
> gündüz çiftinde baskılanıyor ama üç hedefte, dördüncüde **berabere**, ve kayıp %0,14-%0,34 —
> bandın iki mertebe altında; "varsayılan ağırlıklar yanlış" cümlesi bu ölçümden **çıkmaz**.
>
> **İddia sınırı.** Üretilen şeyin adı `non_dominated`; yanıt `pareto_front` anahtarı **taşımaz**.
> `completeness: "no_guarantee"` — ağırlıklı toplam yalnız *supported* çözümlere ulaşır
> (Boyd & Vandenberghe §4.7.4; Das & Dennis 1997; terminoloji Könen & Stiglmayr arXiv:2501.13842),
> **üstelik buradaki ağırlıklar hedefleri değil hücre başı maliyet kriterlerini skalerleştirdiği
> için o garanti bile geçerli değil**. *"Duality gap"* bu literatürün terimi değil, kullanılmadı.
> D5 darlığın **sonucunu** ölçüyor, **sebebini kurmuyor**: depo katmanların tek yükseklik gridinden
> türediğini ve iki kriterin Spearman'ının 1,000000 olduğunu zaten kaydetmişti (`cost_engine.py`).
>
> **Bu maddedeki iki atıf birinci elden okununca düzeltildi:** arXiv 1505.05947 (Lavin 2015) rota
> cephesi **üretmiyor** — her adımda açık listenin baskın-olmayanlarını bulup hemen tek düğüme
> indiriyor, çıktısı tek rota; arXiv 2606.21755 (RoverDevKit) ise ağırlıklı-toplam karşılaştırması
> **hiç içermiyor**, o atıf kullanılmadı. Gerçek emsal **ETH `lunar_planner`** (Richter, Kolvenbach,
> Valsecchi, Hutter; iSpaRo 2024, arXiv:2406.16376, MIT): `α+β+γ=1` simpleksinde ağırlıklı A*,
> taranıp sonradan analiz ediliyor — D5'in ucuz yoluyla **aynı yöntem**, aynı sınırla.
>
> **Ek olarak bayat etiket düzeltildi (C2/C5 deseni):** `constants.py` ağırlıkların "gradient-
> normalised expert weights, **not AHP**" olduğunu yazarken kod 7 yerde hâlâ "AHP" diyordu
> (`costmap`, `cost_engine` ×5, `pathfinder` ×2) — 11 no'lu belgenin tespiti. Yalnız yorum/docstring
> değişti, tek ifade değişmedi.
>
> **Bit-eşitlik:** LPR-1'in checked-in v5 maliyet-gridi SHA-256'sı (`55e1bb3c…`) kıpırdamadı,
> `COST_MODEL_ID` `…_v5`'te kaldı, nominal örneğin rotası ağırlıksız `astar` çağrısıyla **birebir
> aynı** — üçü de testte. **Kapsam dışı:** `pymoo`/NSGA-II (yeni pinli bağımlılık, C5'in `pandas`
> emsali), 4-B tarama (örnek başına 6-17 s), hipervolüm (1-4 elemanlı ve gürültü içindeki bir
> cephede darlığı gizlerdi), frontend çizimi. Süre: ~330 ms/örnek (gündüz), ~1 370 ms/örnek
> (Ay gecesi); uç nokta 40 vektörle sınırlı, modül API'si sınırsız. Tasarım:
> [spec](../superpowers/specs/2026-09-16-d5-pareto-cephesi-design.md) (sondalar ve ölçümler dahil),
> [plan](../superpowers/plans/2026-09-16-d5-pareto-cephesi.md). Testler: 25 birim + 22 API +
> 19 skip-korumalı gerçek grid = **66**.


**Ne:** Tek bir ağırlık vektörü yerine (süre, enerji, gölge saati, termal risk) uzayında **baskın-olmayan** rota kümesini üretmek; operatör cepheden seçer. 11 no'lu belge "AHP" etiketinin yanlış olduğunu söylüyordu — Pareto cephesi bu tartışmayı tamamen ortadan kaldırır.

**Kim / kanıt:** ETH `lunar_planner` çok-amaçlı optimizasyon (10 no'lu belge A1); [A Pareto Front-Based Multiobjective Path Planning Algorithm (arXiv 1505.05947, Mars rover örneği)](https://arxiv.org/pdf/1505.05947); [RoverDevKit NSGA-II tradespace](https://arxiv.org/html/2606.21755); ISRO BAH 2026 hackathon projesi de NSGA-II kullanmış (Bölüm E).

**Somut katkı:** Ucuz yol: ağırlık simpleksinde 20–40 örnek → `plan` → baskın-olmayan filtre (`/api/pareto`); pahalı yol: `pymoo` NSGA-II (Apache-2.0) ile rota geni. Çıktı frontend'de 2B/3B cephe grafiği. **Efor:** 1 gün (ucuz yol).

---

## D6. ✅ ⭐⭐⭐ Enerji-erişilebilirlik izokronları ("şu an nereye kadar gidebilirim?")

> **Yapıldı (16 Eylül 2026).** `POST /api/reachable` + `app/reachability.py`. Ama **bu
> maddenin algoritma öncülü yanlıştı ve üç atfından ikisi tutmadı** — hepsi kaynaklar
> birinci elden okunarak düzeltildi ve `REACHABILITY_CORRECTIONS` içine yazıldı.
>
> **(1) Dijkstra çalışmaz — ölçüldü.** `cost_engine.move_battery_drain_wh` işaretlidir
> (kendi docstring'i: "Positive drains, NEGATIVE CHARGES … NOT floored at zero"): düz ve
> aydınlık bir hücrede LPR-1'in paneli sürüşten fazla üretir, metre başına −0,245 Wh, düz
> hücrede başabaş gölge oranı **0,3908** (VIPER 0,2400). Site11'de coarsen 4, 48 dilim,
> 8 yön: **2026-09-05'te sürüş kenarlarının %28,94'ü (1 080 811 / 3 734 496, en kötü
> −5,735 Wh) ve bekleme kenarlarının %53,9'u negatif**. Tuzak: **2026-09-01'de tam olarak
> sıfır** — test paketinin çoğunun kullandığı epoch. Bir Dijkstra orada doğru görünür,
> aydınlık bir epoch'ta sessizce yanlış cevap verir ve hiçbir test kırmızıya dönmez.
> Tabanlanmış ikiz `net_energy_per_metre_wh` de kullanılamaz: `max(0,…)` olduğu için
> "güneşte sürerek menzil kazanamazsın" der, ki bu modelde yanlış ve yalnızca tek yönde
> yanlış.
>
> **(2) Tompkins Dijkstra demiyor.** 192 sayfalık tez tam metin okundu: **"Dijkstra"
> kelimesi 0 kez geçiyor**; TEMPEST'in arayıcısı **ISE**, "similar to A*", D* tarzı
> artımlı onarımla. §3.1.5 şarj edilebilir enerjiyi **non-monotonic RESOURCE PARAMETER**
> (bir DPARMS **durum değişkeni**) diye sınıflıyor — enerjiyi amaç fonksiyonuna koymanın
> tam tersi. Doyum kuralı `e_{i+1} = max(e_i + Δe, e_min)` / `> e_max` ise red,
> `pathfinder_4d`'in ileri yöndeki `min(e_cap_wh, battery − drain)`'inin aynası. §3.1.7'nin
> "the search will never terminate" cümlesi **kendi artımlı sezgisel aramasıyla** ilgili,
> Dijkstra'nın label-setting optimalliğiyle değil — modül bunu ona söyletmiyor. Ve **tez
> hiçbir uzamsal erişilebilirlik haritası hesaplamıyor** ("isochron" 0 kez); "Reachable
> State Space" mesafe–zaman düzleminde skaler bir varış aralığı.
>
> **(3) arXiv 2509.15062 doğru, ama bağlam.** "softplus ceza + SCP + NMPC" tarifi
> **doğrulandı** (§III-E, §III-F, §IV) ve sayıları `REACHABILITY_QUOTED`'a kondu
> (198,9 W / 200 W; rakipler 235,8 W ve 234,7 W). Belgenin söylemediği: makale **hiç
> erişilebilirlik kümesi hesaplamıyor**.
>
> **(4) "Fast Marching" atfı doğrulanamadı.** Sakayori & Ishigami 2021 ödeme duvarının
> arkasında (tandfonline ve ResearchGate HTTP 403); indekslenmiş özeti hiçbir Fast
> Marching'den söz etmiyor. D6 onu yöntem kaynağı göstermiyor.
>
> **Yerine yapılan:** ileri, **zaman-genişletilmiş** erişilebilirlik sweep'i. Durum
> `(dilim, kaba blok)`, blok başına iki alan: erişilebilecek **en yüksek şarj** ve
> **en düşük sürekli karanlık saati**. Her kenar saati en az bir dilim ilerlettiği için
> graf bir **DAG**'dır ve geçiş fonksiyonları monoton olduğundan ileri tarama alan başına
> **kesin**dir — öncelik kuyruğu yok, SOC bini yok. Negatif kenarlar tam da bu yüzden
> zararsız: taramanın bozulacak bir öncelik sırası yok. Kesinlik birim testinde **kaba
> kuvvetle** doğrulanıyor.
>
> İki alan **bağımsız** optimize edildiği için küme bir **gevşetmedir**: `/api/plan-4d`'in
> kabul ettiğini **içerir**. Güvenli yön tek yöndür — kümenin **dışındaki** blok "oraya
> gidemezsin" demektir; içindeki **adaydır**. Gerçek gridde `astar_4d` örneklenmiş
> bloklarda koşuldu: **11/11 = %100**, ve planlayıcının varış dilimi her satırda sweep'in
> ilk diliminden büyük ya da eşit. İçerme **yapılandırmaya karşı** kuruluyor
> (`planner_configuration` yanıtta): `allow_hibernate=True` üçüncü bir kenar ailesidir,
> karanlık saatini sıfırlar ve kümenin dışına meşru biçimde çıkabilir.
>
> **Kendi kendini yalanlayabilen alan:** kısa ufukta ve dolu bataryayla enerji kuralları
> **hiç tetiklenmiyor** — sınır saattir ve harita bir *kapılı mesafe dönüşümü*dür. Yanıt
> bunu `energy_binds` + `refusals` ile söylüyor. Bütçe eğrisi (LPR-1 gündüz, 2026-09-05):
> tam şarj 12 h'te **11 156** blok (`soc_floor` 0), çeyrek şarjda **182** blok
> (`soc_floor` 18 900) — %98,4 düşüş, ve ufuk dört katına çıksa bile 182'de kalıyor.
>
> **"N saat sonra" Site11'de saat ölçeğinde hiçbir şey değiştirmiyor** ve bu ölçüldü:
> +6 h ve +24 h'te aydınlık blok oranı değişiyor (%48,30 → %48,00 → %47,89) ama kümede
> **tek blok bile** değişmiyor; kutupta aydınlanma ~708 saatlik sinodik döngüyle döner.
> Etki gün ölçeğinde: +240 h'te pencere karanlığa giriyor, 7 362 blok **586**'ya düşüyor
> (Jaccard 0,080). Tabloya iki "aydınlık" sütunu tam da bu yüzden kondu — yoksa Jaccard
> 1,0 "küme zamanla sabittir" diye okunurdu ve güneşin hiç modellenmediği durumdan
> ayırt edilemezdi.
>
> **`time-to-0-SOC` tek başına yanıltıcı:** tam karanlıkta LPR-1 rezerve 66,7 h'te, sıfıra
> 83,4 h'te iner ama dayanımı **50 h**'tir — yani saf enerji sayısı, API'nin geri kalanının
> görev başarısızlığı saydığı bir durumu tarif eder. Yayımlanan işletme sayısı
> `hold_limit = min(rezerv, dayanım)` ve hangisinin bağladığı. Ayrıca karanlık saati
> **pozlamayla ağırlıklıdır** (`dark += hours × exposure`), yani duvar saati değildir:
> gerçek gridde dayanımın bağladığı bloklarda duruş **49,5–56,0 h** çıkıyor.
>
> **`skimage` eklenmedi.** Kurulu (0.26.0) ama `backend/requirements.txt`'te yok — yeni
> bağımlılık olurdu. Bantlar blok indisi + merdiven sınır blokları olarak, saf numpy ile.
> **`start_utc` zorunlu**: epoch olmadan gölge serisi uzun dönem **kesre** düşer (bir
> iklimoloji) ve "N saat sonra" farkı tam sıfır çıkardı.
>
> **Bit-eşitlik:** LPR-1'in checked-in v5 maliyet-gridi SHA-256'sı (`55e1bb3c…`)
> kıpırdamadı, `COST_MODEL_ID` `…_v5`'te. `/api/plan` ve `/api/plan-4d`'in değişmediği
> "birebir aynı" diye değil **kontrol ölçülerek** kanıtlandı: arada hiç D6 olmadan iki
> özdeş çağrı zaten 2 ve 8 yaprakta farklı çıkıyor (hepsi milisaniye sayacı ya da çağrı
> kimliği); D6'lı fark o kümenin alt kümesi. **Kapsam dışı:** ağırlık vektörü (uç onu
> kabul bile etmiyor — hiçbir ağırlık bir bloğu erişilebilir yapamaz), maliyet küpü,
> hibernasyon kenarı, belirsizlik yayılımı, frontend çizimi. Süre: 3 h ufuk 2,0 s,
> 12 h 9,3 s, 24 h 19,0 s (coarsen 4). Tasarım:
> [spec](../superpowers/specs/2026-09-16-d6-enerji-izokronlari-design.md) (sondalar ve
> ölçümler dahil), [plan](../superpowers/plans/2026-09-16-d6-enerji-izokronlari.md),
> [rapor](reachability_report.md). Testler: 30 birim + 18 API + 16 skip-korumalı gerçek
> grid = **64**.

**Ne:** Rover'ın mevcut konum, zaman ve SOC'siyle **ulaşabileceği bölge** (ve "N saat sonra"ki hali); `time-to-0-SOC` metriğinin uzamsal karşılığı.

**Kim / literatür:** Tompkins (CMU 2005) [Mission-Directed Path Planning for Planetary Rover Exploration](https://www.ri.cmu.edu/pub_files/pub4/tompkins_paul_2005_1/tompkins_paul_2005_1.pdf) (TEMPEST; Lamarre'nin de temeli); [Energy-Constrained Navigation for Planetary Rovers under Hybrid RTG-Solar Power (arXiv 2509.15062)](https://arxiv.org/html/2509.15062): anlık güç kısıtı P_cons ≤ P_avail (softplus cezası), SCP + NMPC, tepe güç limitin %0,55 içinde (rakipler %17 aşıyor); Fast Marching ile enerji haritaları ([Energy-aware trajectory planning for planetary rovers, Advanced Robotics 2021](https://www.tandfonline.com/doi/full/10.1080/01691864.2021.1959396)).

**Somut katkı:** `/api/reachable`: `cost_cube` üzerinde çok-kaynaklı Dijkstra (enerji bütçeli) → hücre kümesi + izokron poligonları (`skimage.measure.find_contours`). SHERPA'nın "time-to-0-SOC" metriği ile birlikte. **Efor:** 1 gün. Wow: görsel olarak yüksek (frontend'e hazır veri).

---

## D7. ⭐⭐⭐ Enerji modelinin gerçek rover ölçümüyle doğrulanması — UTIAS enav dataset

**Ne:** `edge_energy_wh`'nin eğim bağımlılığını (μ = 1 + k·sin θ) ölçülmüş güç-vs-eğim verisiyle kıyaslamak; projenin ilk "validation" kanıtı.

**Kim / veri:** University of Toronto STARS — Lamarre, Limoyo, Marić, Kelly, [The Canadian Planetary Emulation Terrain Energy-Aware Rover Navigation Dataset (IJRR 2020) — GitHub utiasSTARS/enav-planetary-dataset](https://github.com/utiasSTARS/enav-planetary-dataset): CSA Mars Emulation Terrain, **>1.200 m sürüş**, güç tüketimi, üst yüzey güneş ışınımı, IMU, tekerlek enkoderleri, GPS, 0,2 m çözünürlüklü yükseklik/eğim/bakı haritaları; IEEE DataPort'ta rosbag.

**Somut katkı:** `scripts/validate_energy_enav.py`: veri setinden (eğim, güç) çiftleri → LunaPath modelinin **şekli** (sin θ bağımlılığı) ile ölçüm arasında R²; g_Dünya→g_Ay ve kütle ölçeklemesi açıkça belgelenir. Ayrıca `simulation.py` ↔ `cost_engine.py` iki farklı enerji modeli sorununu (11 no'lu belge §2.3) "hangisi ölçüme yakın?" sorusuyla çözer. **Efor:** 2 gün (veri indirme ağır olabilir).

---

## D8. ⭐⭐ "Speed Made Good" ve yer-döngülü komuta kadansı — referans misyon modelinin tamamlanması

**Ne:** Rota süresi tahminlerine gerçek operasyon kadansını eklemek.

**Sayılar:** VIPER 20 cm/s tepe, **SMG ~1 cm/s**, zamanın %90'ı bekleme ([Ennico-Smith 2023](https://ntrs.nasa.gov/api/citations/20230004239/downloads/SSR2023-VIPER-Planning-Ennico.pdf?attachment=true)); Pragyan hamle başına ≤5 m, hamleler arası ~5 saat, 15° eğim sınırı, 27 Ağustos 2023'te 3 m önde 4 m çaplı krater için rota değişikliği (haber kaynakları: [Swarajya](https://swarajyamag.com/science/chandrayaan-3-how-pragyan-rover-is-navigating-the-tough-lunar-obstacle-course), [Tribune](https://www.tribuneindia.com/news/india/chandrayaan-3-pragyan-rover-comes-across-big-crater-on-lunar-surface-retraces-path-isro-releases-fresh-pictures-539165)).

**LunaPath'te bugün:** `mission_reference.py` Yutu-2 ve Pragyan günlük hızlarını veriyor.

**Somut katkı:** `ops_cadence` modeli: hamle uzunluğu + yer-döngü gecikmesi + DTE penceresi → "takvim süresi" ile "sürüş süresi" ayrı raporlanır; VIPER SMG referansı eklenir. 4B planlayıcıda `travel_hours` fiziksel hız yerine SMG kullanabilir. **Efor:** yarım gün.

---

## D9. ⭐⭐ (Opsiyonel) Ay navigasyon servisi (LCNS/Moonlight) kullanılabilirlik katmanı

**Ne:** 2028+ için ESA Moonlight LCNS'nin güney kutbunda günde ≥15 saat HHDOP < 3,5 hedefi ([ESA Moonlight](https://www.esa.int/Applications/Connectivity_and_Secure_Communications/ESA_s_Moonlight_programme_Pioneering_the_path_for_lunar_exploration), [UNOOSA ICG 2024 sunumu](https://www.unoosa.org/documents/pdf/icg/2024/WG-B_Lunar_PNT_Jun24/LunarPNT_Jun24_01_04.pdf)); de Gerlache çevresinde 320 km/11 gün rover konumlandırma simülasyonu ([Adv. Space Res. 2024](https://www.sciencedirect.com/science/article/abs/pii/S0273117724005829)). LunaPath'in `check_localization_uncertainty` tetikleyicisine "navigasyon servisi var/yok" girdisi olarak eklenebilir. Düşük öncelik; yalnızca "gelecek uyumluluğu" anlatısı için.

---

# BÖLÜM E — Hackathon ve yarışma projelerinden gözlemler

Amaç: rakip/akran ekiplerin jüri karşısına neyle çıktığını görmek. Bunlar **doğrulanmış** projeler değildir; "jüri beklentisi" için okunmalıdır.

| Proje | Kim / nerede | Ne yapmış | LunaPath için ders |
|---|---|---|---|
| [Lunaris — ISRO Bharatiya Antariksh Hackathon 2026, PS8](https://github.com/iamLakshikaTanwar/bah2026-ps8) (MIT) | Hindistan, 2026 | Faustini krateri buz tespiti + rover traverse: A*, **D* Lite, Theta*, RRT\*, NSGA-II**; eğim, aydınlanma, pürüzlülük, **Dünya görünürlüğü** katmanları; 70 saat gölge dayanımlı batarya modeli; AHP-MCDA iniş bölgesi | Hackathon seviyesinde bile DTE, herhangi-açı ve Pareto var (A4, D1, D5). Doğrulama iddiası yok — bizim avantajımız 263 test + provenance. |
| [Subsurface Lunar Ice Detection — BAH 2026](https://github.com/Brukrish2006/Subsurface-Lunar-Ice-Detection/blob/main/README.md) | Hindistan, 2026 | A* ile **Bekker-Wong** toprak mekaniği maliyeti; LOLA 5 m; PSR karanlık cezası, iletişim kesintisi cezası, **40 K altı "cold-shock"** cezası; SOC profili | Termal "soğuk şoku" ve toprak mekaniği hackathon'da da kullanılıyor (C3). |
| [Lunar Autonomy Challenge 2025 (NASA/JHU-APL/Caterpillar) — Stanford NavLab 1., MIT MAPLE 2.](https://arxiv.org/pdf/2603.17232) | ABD, 2025 | Stereo VO + pose-graph SLAM, U-Net++ segmentasyon, yay örnekleme yerel planlayıcı; cm düzeyi konumlandırma | 10 no'lu belge A2; yerel katman kapsam dışı — burada yeni bir şey yok. |
| [NASA Space Robotics Challenge Phase 2 (2019–2021)](https://arxiv.org/abs/2109.09620) | ABD, 114 takım | Çok-rover ISRU otonomisi (Gazebo); Team Mountaineers (WVU) yaklaşımı | Çok-rover koordinasyonu (CADRE) ilerde `plan-multi` için fikir; şimdilik kapsam dışı. |
| [NASA BIG Idea 2020 "Lunar PSR Challenge" — Michigan Tech T-REX (Artemis Award)](https://www.mtu.edu/news/2021/01/mtu-students-shoot-for-the-moon-and-win.html) | ABD, 2020 | PSR'a süperiletken tether ile güç/iletişim taşıyan rover; PSR'ın soğuğunu pasif soğutma olarak kullanma | Donanım odaklı; "PSR girişi = tether/enerji bütçesi" senaryosu B1'deki PSR-entry makro-aksiyonuna örnek. |
| [ESA-ESRIC Space Resources Challenge (2021–22)](https://www.esa.int/ESA_Multimedia/Images/2022/03/Rovers_compete_in_Space_Resources_Challenge) | Avrupa/Kanada, 12 takım | Gölgeli kutup analoğunda prospeksiyon; LUVMI-XR (Space Applications + Uni Luxembourg), Mission Control (Husky + LiDAR) | LUVMI-M profilimizin sahibi bu ekosistemde; yarışma sonuçları yayınlı değil. |

**Ders:** Hackathon projeleri "çok algoritma, sıfır doğrulama" profilinde. LunaPath'in farkı doğrulama ve dürüstlük; bu belgedeki A4/D1/D5 eklendiğinde algoritma çeşitliliğinde de geri kalınmaz.

---

## 3. Öncelik matrisi (efor × wow × challenge etkisi)

| # | Özellik | Efor (gün) | Wow | Challenge | Bağımlılık | Doğrulama kanıtı türü |
|---|---|---|---|---|---|---|
| A4 | DTE katmanı + LOLA Earth-visibility doğrulaması | 1–2 | 4 | 4 | — | **Ölçülmüş ürünle RMSE** |
| A1 | Safe haven (Ay günü) + time-to-SH + 50 h kuralı | 2–3 | 5 | 5 | A4 | NASA kuralı birebir |
| B5 | MC stres testi (SHERPA dağılımları/metrikleri) | 2 (+0,5) | 4 | 5 | enerji birleştirme | NASA protokolü birebir |
| B3 | DEM klonlarıyla Monte Carlo belirsizlik | 2–3 | 5 | 4 | — | NASA hata ürünleri |
| D3 | FRET gereksinimleri + RTAMT STL monitörü | 2–3 | 4 | 4 | — | Formal yöntem |
| A2 | 3B bağlı-bileşen aydınlık koridoru | 2–3 | 4 | 4 | — | CMU, WAC ile doğrulanmış yöntem |
| B2 | CVaR risk maliyeti | 2 | 4 | 4 | C3 (tercihen) | JPL saha + ICRA sonuçları |
| C3 | Slip kalibrasyonu (Yutu-2 / VIPER) | 1–2 | 4 | 3 | — | Uçmuş veri |
| C4 | LOLA pürüzlülük + PSR (MEASURED) | 1–2 | 4 | 3 | — | Ölçülmüş katman |
| D2 | MoonPlanBench koşumu | 1 | 4 | 3 | — | Dış benchmark |
| B1 | Reach-avoid kurtarma politikası, P_fail ≤ β | 5–8 | 5 | 5 | A1, B5 | Toronto formülasyonu |
| C6 | Termal operasyon zarfı / max dwell | 2 | 3 | 4 | — | NASA JSC yöntemi |
| C1 | ✅ Panel cos i modeli | 1 | 3 | 3 | — | RoverDevKit doğrulaması (alıntı) + NASA'nın 320/450 W çifti |
| C2 | Batarya soğuk/hibernasyon | 2 | 3 | 4 | C1 | NASA Glenn testleri |
| C5 | Diviner PRP/Williams termal RMSE | 1 | 3 | 3 | — | **Ölçülmüş ürünle RMSE** |
| D5 ✅ | Pareto cephesi | 1 | 3 | 3 | — | Literatür |
| D4 | Kontrastif açıklama | 1–2 | 3 | 4 | — | XAIP literatürü |
| D6 ✅ | Erişilebilirlik izokronları | 1 | 3 | 3 | — | Literatür |
| B4 | Sobol duyarlılık | 1–2 | 3 | 3 | — | SALib |
| A5 | Zaman pencereli TSP görev planı | 3–4 | 3 | 3 | A1 | VIPER Alg. #1 |
| D7 | enav dataset ile enerji doğrulama | 2 | 3 | 3 | — | **Ölçülmüş veri** |
| A3 | Zaman sıkıştırma hızlandırma | 1–2 | 2 | 2 | A2 | CMU |
| D1 | Theta*/LOS yumuşatma | 1 | 3 | 2 | — | MER uçuş yazılımı |
| D8 | SMG / komuta kadansı | 0,5 | 2 | 2 | — | VIPER/Pragyan sayıları |
| D9 | LCNS katmanı | 1 | 2 | 1 | — | ESA hedefleri |

---

## 4. Önerilen üç paket

**Paket 1 — "VIPER kuralları" (5 iş günü, demo-güvenli):** A4 → A1 → B5 (+ enerji birleştirme) → D8.
Sunum cümlesi: *"Rota planlayıcımız VIPER'ın leg/safe-haven yapısını, 50 saatlik karanlık kuralını ve DTE kısıtını uyguluyor; her rotayı NASA'nın stres-test dağılımlarıyla 1.000 kez simüle edip 'time-to-DSN-shadow' ve 'time-to-0-SOC' marjlarını raporluyoruz. Dünya görünürlüğü katmanımız LOLA'nın 18,6 yıllık ürünüyle X RMSE ile örtüşüyor."*

**Paket 2 — "Belirsizlik ve doğrulama" (5–6 iş günü):** B3 → C4 → C5 → D2 → B4.
Sunum cümlesi: *"NASA'nın yayınladığı 100 DEM klonuyla Monte Carlo yaptık; rotamızın enerji tüketimi %90 güven aralığıyla veriliyor. İki katmanımız (pürüzlülük, PSR) artık MEASURED etiketli, termal modelimiz Diviner PRP'ye karşı ölçüldü, planlayıcımız bağımsız MoonPlanBench'te %100 başarı verdi."*

**Paket 3 — "Risk sınırı ve formal güvenlik" (8–10 iş günü, akademik zirve):** C3 → B2 → D3 → B1 → D4.
Sunum cümlesi: *"Her rota için başarısızlık olasılığı üst sınırı (β) veriyoruz ve rover'ın her durumdan güvenli limana dönüş politikasını önceden hesaplıyoruz; güvenlik gereksinimleri NASA FRET ile formal yazıldı ve STL robustness ile her rotada nicel marj olarak denetleniyor."*

Üç paket birlikte 11 no'lu belgedeki skorkartı şu şekilde etkiler (tahmin): Veri gerçekliği 3→4, Validation 1→3, Belirsizlik 1→4, Otonomi kapsamı 3→4 ⇒ **33/50 → ~41/50**, TRL 4 iddiası savunulabilir.

---

## 5. Ne söylenebilir, ne söylenemez (bu belgedeki özellikler yapıldıktan sonra)

| İddia | Koşul |
|---|---|
| "VIPER ile aynı safe-haven ve 50 saat kuralını uyguluyoruz" | A1 tamam; kaynak: Shirley & Balaban 2022, Ennico 2023 |
| "Dünya görünürlüğü katmanımız LOLA ürünüyle doğrulandı" | A4 + PGDA 69 RMSE hesaplandı |
| "Belirsizlik nicelenmiştir" | B3 (klonlar) veya en az sentetik σ_z ile MC; B5 metrik dağılımları |
| "Rotanın başarısızlık olasılığı ≤ %β" | Yalnızca B1 yapılırsa; arıza oranı α'nın kaynağı (Lamarre: 1/5 km) açıkça yazılmalı |
| "Slip modelimiz kalibre edildi" | C3; ama "uçmuş veriye **bağlandı**" demek, "ölçüldü" dememek — LunaPath hâlâ saha verisi üretmiyor |
| "Gereksinimlerimiz formal olarak doğrulandı" | D3; "runtime monitoring ile denetlendi" doğru, "model checking ile ispatlandı" yanlış |
| "Bağımsız benchmark'ta %100 başarı" | D2; benchmark'ın yalnızca eğim eşikli occupancy olduğunu söyleyin |
| "Diviner kaya bolluğu kullanıyoruz" | **Söylenemez** — ürün 80–90°S'yi kapsamıyor (C4) |

---

## 6. Kaynaklar (bu belgede kullanılan tüm bağlantılar)

**NASA VIPER / SHERPA**
- [Overview of Mission Planning for the VIPER Rover — Shirley & Balaban, 2022 (PDF)](https://www.nasa.gov/wp-content/uploads/2022/05/overview_of_mission_planning_for_the_viper_rover.pdf)
- [VIPER Mission Traverse Planning — Ennico-Smith vd., NTRS 2023 (PDF)](https://ntrs.nasa.gov/api/citations/20230004239/downloads/SSR2023-VIPER-Planning-Ennico.pdf?attachment=true)
- [SHERPA — SpaceOps 2025 (PDF)](https://publications.spaceops.org/2025/download.php?doc=559__4nupk3n2.pdf) · [NASA blog Part 1](https://www.nasa.gov/blogs/missions/2023/12/01/part-1-artificial-intelligence-and-nasas-first-robotic-lunar-rover/) · [Aerospace America: VIPER's AI assistant](https://aerospaceamerica.aiaa.org/departments/vipers-ai-assistant/)
- [VIPER Traverse Planning — Shirley vd., LPSC 2022 #2874](https://www.hou.usra.edu/meetings/lpsc2022/pdf/2874.pdf) (403; erişilemedi) · [VIPER Lunar Operations](https://science.nasa.gov/mission/viper/lunar-operations/) · [VIPER Site Analysis, PSJ](https://iopscience.iop.org/article/10.3847/PSJ/ae061a)
- [Generalizing Lunar Vehicle Thermal Analysis: Lessons Learned from VIPER — ICES-2025-376](https://ntrs.nasa.gov/api/citations/20250004028/downloads/ICES-2025-376_Final.pdf)
- [Investigating the Geotechnical Properties of the Lunar South Pole with VIPER's Mobility System — PSJ 2025](https://iopscience.iop.org/article/10.3847/PSJ/add13f)
- [Resource Prospector traverse planning — Heldmann vd., NTRS 2015](https://ntrs.nasa.gov/api/citations/20150022104/downloads/20150022104.pdf) (404) · [Acta Astronautica 127 (2016)](https://ui.adsabs.harvard.edu/abs/2016AcAau.127..308H/abstract)

**CMU / Toronto akademik planlayıcılar**
- [Otten vd., ICRA 2015 (PDF)](https://www.ri.cmu.edu/app/uploads/2018/01/ICRA2015_Otten_3109.pdf) · [Otten vd., FSR 2017 (PDF)](https://publications.ri.cmu.edu/storage/publications/2018/01/FSR_2017_Otten_66.pdf) · [Otten tezi](https://kilthub.cmu.edu/articles/thesis/Planning_for_Sun-Synchronous_Lunar_Polar_Roving/6721082/1)
- [Cunningham vd., ICRA 2017 (IEEE Xplore)](https://ieeexplore.ieee.org/document/7989508) · [Cunningham, Nesnas, Whittaker — RSS 2017 (PDF)](https://roboticsproceedings.org/rss13/p38.pdf) · [Autonomous Robots 2019](https://link.springer.com/article/10.1007/s10514-018-9796-4)
- [Tompkins 2005 — Mission-Directed Path Planning (PDF)](https://www.ri.cmu.edu/pub_files/pub4/tompkins_paul_2005_1/tompkins_paul_2005_1.pdf)
- [Lamarre vd., arXiv 2307.16786](https://arxiv.org/abs/2307.16786) · [arXiv 2401.08558](https://arxiv.org/html/2401.08558v2) · [gplanetary-nav](https://github.com/utiasSTARS/gplanetary-nav) · [enav-planetary-dataset](https://github.com/utiasSTARS/enav-planetary-dataset)

**Risk / belirsizlik**
- [STEP — arXiv 2103.02828](https://arxiv.org/abs/2103.02828) · [arXiv 2303.01614](https://arxiv.org/pdf/2303.01614) · [RSS 2021 p021](https://www.roboticsproceedings.org/rss17/p021.pdf)
- [Endo vd., ICRA 2023 — arXiv 2303.01169](https://arxiv.org/abs/2303.01169) · [arXiv 2409.00641](https://arxiv.org/html/2409.00641)
- [SALib](https://www.researchgate.net/publication/312204236_SALib_An_open-source_Python_library_for_Sensitivity_Analysis) · [Multi-Objective Risk Assessment Framework — arXiv 2410.03917](https://arxiv.org/abs/2410.03917)

**NASA veri ürünleri (PGDA / PDS / SVS)**
- [PGDA 78 — 5 m DEM + belirsizlik + 100 klon](https://pgda.gsfc.nasa.gov/products/78) · [PGDA 90 — Güney kutbu LOLA (pürüzlülük, PSR, eğim hatası)](https://pgda.gsfc.nasa.gov/products/90) · [PGDA 69 — Kutup aydınlanma & Dünya görünürlüğü](https://pgda.gsfc.nasa.gov/products/69) · [PGDA 81 — South Pole LOLA DEM Mosaic](https://pgda.gsfc.nasa.gov/products/81)
- [Barker vd., PSJ 4:183 (2023)](https://iopscience.iop.org/article/10.3847/PSJ/acf3e1) · [Barker vd., PSS 2021 (hata tahminleri)](https://www.sciencedirect.com/science/article/abs/pii/S0032063320303329) · [PSJ 2025 kutup pürüzlülüğü](https://iopscience.iop.org/article/10.3847/PSJ/adbc9d)
- [Mazarico vd., Icarus 2011](https://www.researchgate.net/publication/251730356_Illumination_conditions_of_the_lunar_polar_regions_using_LOLA_topography) · [NASA SVS 5027](https://svs.gsfc.nasa.gov/5027/) · [JPL IPN 42-176](https://ipnpr.jpl.nasa.gov/progress_report/42-176/176C.pdf)
- [Diviner PRP (ODE)](https://ode.rsl.wustl.edu/moon/pagehelp/Content/Missions_Instruments/LRO/DIVINER/PRP.htm) · [Diviner GDR L3](https://ode.rsl.wustl.edu/moon/pagehelp/Content/Missions_Instruments/LRO/DIVINER/GDR_L3.htm) · [Williams vd., JGR Planets 2019](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2019JE006028) · [Powell vd., JGR Planets 2023](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2022JE007532) · [Diviner GHRM](https://ode.rsl.wustl.edu/MArs/pagehelp/Content/Missions_Instruments/Lunar%20Reconnaissance%20Orbiter%20(LRO)/DIVINER/GHRM.htm)
- [Artemis Lunar Surface Data Book ACD-50044 Rev A (NTRS)](https://ntrs.nasa.gov/api/citations/20230007818/downloads/ACD-50044%20Lunar%20Surface%20Data%20Book%20Rev%20A.pdf)

**Batarya / termal**
- [Battery Hibernation — NASA Glenn 2021 (NTRS)](https://ntrs.nasa.gov/api/citations/20210011101/downloads/Battery%20Hibernation%203-8-21.pdf) · [Lunar Power Hibernation (NTRS)](https://ntrs.nasa.gov/api/citations/20210019184/downloads/Lunar%20Power%20Hibernation%20Extreme%20Environments%20WG%20%207-28-21.pdf) · [TFAWS 2023 — Surviving Night at the Lunar South Pole](https://tfaws.nasa.gov/wp-content/uploads/TFAWS23-PT-52-Paper.pdf) · [Acta Astronautica 2021 — night-time survival energy storage](https://www.sciencedirect.com/science/article/abs/pii/S0094576521002101)
- [RoverDevKit — arXiv 2606.21755](https://arxiv.org/html/2606.21755) · [GitHub](https://github.com/Autonomous-Mission-Systems-Lab/roverdevkit)

**Uçmuş rover verisi**
- [Ding vd., Science Robotics 2022 (Yutu-2)](https://www.science.org/doi/10.1126/scirobotics.abj6660) · [Nature Communications 2024 — Yutu-2 dijital ikiz (açık erişim)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11258293/)
- [Carsten vd., Field D* on MER, IEEE Aerospace 2007 (PDF)](https://www-robotics.jpl.nasa.gov/media/documents/IEEEAC-Carsten-1125.pdf) · [CMU haber 2007](https://www.cs.cmu.edu/news/2007/carnegie-mellon-software-steers-nasas-mars-roverfirst-test-new-autonomous-capability-mars)
- Pragyan: [Swarajya](https://swarajyamag.com/science/chandrayaan-3-how-pragyan-rover-is-navigating-the-tough-lunar-obstacle-course) · [Tribune](https://www.tribuneindia.com/news/india/chandrayaan-3-pragyan-rover-comes-across-big-crater-on-lunar-surface-retraces-path-isro-releases-fresh-pictures-539165)

**Benchmark, formal yöntemler, açıklanabilirlik**
- [MoonPlanBench — arXiv 2512.21438](https://arxiv.org/abs/2512.21438) · [GitHub PlanetaryPathBench](https://github.com/mchancan/PlanetaryPathBench)
- [FRET (GitHub)](https://github.com/NASA-SW-VnV/fret) · [FRET NTRS 2020](https://ntrs.nasa.gov/api/citations/20200001989/downloads/20200001989.pdf) · [Space ROS FRET](https://space-ros.github.io/docs/rolling/Related-Projects/FRET.html) · [arXiv 2209.14030](https://arxiv.org/pdf/2209.14030) · [arXiv 2511.14438](https://arxiv.org/pdf/2511.14438) · [Adventures in FRET — arXiv 2503.24040](https://arxiv.org/pdf/2503.24040v1)
- [RTAMT (GitHub)](https://github.com/nickovic/rtamt) · [arXiv 2501.18608](https://arxiv.org/abs/2501.18608) · [PyPI](https://pypi.org/project/rtamt/)
- [Krarup vd., ICAPS 2019 XAIP](https://strathprints.strath.ac.uk/69957/1/Krarup_etal_ICAPS2019_Model_based_contrastive_explanations_explainable_planning.pdf) · [arXiv 2103.15575](https://arxiv.org/pdf/2103.15575) · [arXiv 2403.19760](https://arxiv.org/pdf/2403.19760) · [arXiv 2003.07425](https://arxiv.org/pdf/2003.07425)
- [Pareto path planning — arXiv 1505.05947](https://arxiv.org/pdf/1505.05947)

**Diğer akademik**
- [Chen, Jackson, Allard, Beltrame — Acta Astronautica 237 (2025)](https://www.sciencedirect.com/science/article/pii/S0094576525004898) · [PolyPublie](https://publications.polymtl.ca/67847/)
- [Spatiotemporal DL for Continuous Illumination Mapping… Chang'E-7 — Remote Sensing 18(17) 2950 (2026)](https://www.mdpi.com/2072-4292/18/17/2950) (Dice 0,983; 3ST-A*) · [Remote Sensing 17(9) 1589 (2025)](https://doi.org/10.3390/rs17091589)
- [Energy-Constrained Navigation under Hybrid RTG-Solar — arXiv 2509.15062](https://arxiv.org/html/2509.15062) · [Energy-aware trajectory planning — Advanced Robotics 2021](https://www.tandfonline.com/doi/full/10.1080/01691864.2021.1959396)
- [Slip rate-dependent traversability — Frontiers 2024](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2024.1320261/full)
- [ESA Moonlight](https://www.esa.int/Applications/Connectivity_and_Secure_Communications/ESA_s_Moonlight_programme_Pioneering_the_path_for_lunar_exploration) · [Adv. Space Res. 2024 — LCNS rover positioning](https://www.sciencedirect.com/science/article/abs/pii/S0273117724005829)

**Hackathon / yarışma**
- [ISRO BAH 2026 PS8 — Lunaris](https://github.com/iamLakshikaTanwar/bah2026-ps8) · [Subsurface Lunar Ice Detection](https://github.com/Brukrish2006/Subsurface-Lunar-Ice-Detection/blob/main/README.md) · [BAH 2026 (Hack2skill)](http://hack2skill.com/event/bah2026/)
- [Lunar Autonomy Challenge — Stanford (arXiv 2603.17232)](https://arxiv.org/pdf/2603.17232) · [NASA: Top prize awarded](https://www.nasa.gov/directorates/stmd/top-prize-awarded-in-lunar-autonomy-challenge-to-virtually-map-moons-surface) · [MIT MAPLE 2. sıra](https://aeroastro.mit.edu/news-impact/mit-maple-team-takes-second-place-in-lunar-autonomy-challenge/)
- [NASA SRC2 — arXiv 2109.09620](https://arxiv.org/abs/2109.09620) · [BIG Idea 2020 — MTU T-REX](https://www.mtu.edu/news/2021/01/mtu-students-shoot-for-the-moon-and-win.html) · [ESA-ESRIC Space Resources Challenge](https://www.esa.int/ESA_Multimedia/Images/2022/03/Rovers_compete_in_Space_Resources_Challenge)
