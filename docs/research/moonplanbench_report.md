# MoonPlanBench dış benchmark (D2) — LunaPath raporu

Üretildi: 2026-09-05T07:33:07+00:00 (`scripts/moonplanbench_runner.py`). Veri: `lunapath/data/benchmarks/moonplanbench`. Modlar: `dijkstra_cut`, `dijkstra_nocut`, `lunapath_single`, `lunapath_multi`. Referans planlayıcılar: koşturuldu (run).

**İddia sınırı:** haritalar yalnızca eğim/pürüzlülük eşikli occupancy gridleridir (gölge, termal, slip, pürüzlülük, Dünya görünürlüğü katmanı yok; ham DEM yok); hücre 320 m – 7 680 m; LunaPath'in çok kriterli maliyet gridi bu haritalarda tek değerdir ve planlayıcı kendi güvenlik kurallarıyla en kısa yol aramasına indirgenir. Benchmark'ın referans planlayıcıları köşe-kesmeye izin verir, LunaPath vermez. Makale sayıları alıntıdır.

## 1. Veri kimliği, lisans, biçim

| | |
|---|---|
| Makale | Planetary Terrain Datasets and Benchmarks for Rover Path Planning — Marvin Chancán, Avijit Banerjee, George Nikolakopoulos (Luleå University of Technology), arXiv:2512.21438v1 (2025-12-24), https://arxiv.org/abs/2512.21438 |
| Kod deposu | https://github.com/mchancan/PlanetaryPathBench @ `86dc4b63f145` (veri depoda değil; README Google Drive'a yönlendirir) |
| Veri lisansı | CC BY-NC-SA 4.0 (the licence line of arXiv 2512.21438v1; the Drive folder and the repository root carry no licence file -- non-commercial use only) |
| Kod lisansları | PathBench/ BSD-3-Clause (Toma et al.); planners derived from PythonRobotics (MIT); the authors' adapters and run.py carry no licence statement -- not vendored, only imported at run time from a local clone when --reference-dir is given |
| Biçim | `.npy` uint8, sıfır olmayan = dolu (`run.py`: `occ = grid != 0`); ham DEM yayımlanmamış |
| Hücre boyutu | LDEM ürününün yerel çözünürlüğü × 64 (makale § 3.1.2'nin altörnekleme çarpanı; dosya adından türetilir) |
| Başlangıç / hedef | benchmark'ın `adapters/_common.auto_select_start_goal` kuralı yeniden uygulandı (en büyük 8-bağlantılı boş bileşen; (satır, sütun) en küçük başlangıç; en uzak hedef) |
| Zaman sınırı | 60 s (benchmark protokolü; burada koşu kesilmez, aşan koşu başarısız sayılır) |
| Rover (LunaPath modları) | `lpr_1` — eğim sınırı düz haritada etkisiz |
| Sağlama | `moonplanbench_meta.json`: 36 dosya, SHA-256 dosya başına; indirme 2026-09-05T06:54:28+00:00 |

| Varyant | Eşik | Harita | Şekil | Hücre (m) | Boş % | Başlangıç (satır, sütun) | Hedef | Düz mesafe (hücre) |
|---|---|---|---|---|---|---|---|---|
| MoonPlanBench-10 | 10° | `LDEM_45N_100M` | 450×450 | 6 400 | 76,8 | (0, 0) | (449, 448) | 634,28 |
| MoonPlanBench-10 | 10° | `LDEM_45S_100M` | 450×450 | 6 400 | 71,5 | (0, 0) | (449, 449) | 634,98 |
| MoonPlanBench-10 | 10° | `LDEM_60N_120M` | 243×243 | 7 680 | 73,1 | (0, 0) | (242, 242) | 342,24 |
| MoonPlanBench-10 | 10° | `LDEM_60S_120M` | 243×243 | 7 680 | 67,5 | (0, 0) | (242, 242) | 342,24 |
| MoonPlanBench-10 | 10° | `LDEM_75N_30M` | 477×477 | 1 920 | 66,9 | (0, 0) | (476, 476) | 673,17 |
| MoonPlanBench-10 | 10° | `LDEM_75S_30M` | 477×477 | 1 920 | 60,5 | (0, 2) | (476, 476) | 671,75 |
| MoonPlanBench-10 | 10° | `LDEM_80N_20M` | 475×475 | 1 280 | 65,0 | (0, 0) | (474, 472) | 668,92 |
| MoonPlanBench-10 | 10° | `LDEM_80S_20M` | 475×475 | 1 280 | 59,9 | (0, 88) | (474, 474) | 611,29 |
| MoonPlanBench-10 | 10° | `LDEM_85N_10M` | 474×474 | 640 | 62,5 | (72, 276) | (473, 51) | 459,81 |
| MoonPlanBench-10 | 10° | `LDEM_85S_10M` | 474×474 | 640 | 55,3 | (0, 258) | (473, 473) | 519,57 |
| MoonPlanBench-10 | 10° | `LDEM_875N_5M` | 474×474 | 320 | 58,2 | (0, 280) | (451, 1) | 530,32 |
| MoonPlanBench-10 | 10° | `LDEM_875S_5M` | 474×474 | 320 | 50,6 | (0, 300) | (473, 0) | 560,12 |
| MoonPlanBench-15 | 15° | `LDEM_45N_100M` | 450×450 | 6 400 | 90,1 | (0, 0) | (449, 449) | 634,98 |
| MoonPlanBench-15 | 15° | `LDEM_45S_100M` | 450×450 | 6 400 | 87,8 | (0, 0) | (449, 449) | 634,98 |
| MoonPlanBench-15 | 15° | `LDEM_60N_120M` | 243×243 | 7 680 | 88,4 | (0, 0) | (242, 242) | 342,24 |
| MoonPlanBench-15 | 15° | `LDEM_60S_120M` | 243×243 | 7 680 | 85,3 | (0, 0) | (242, 242) | 342,24 |
| MoonPlanBench-15 | 15° | `LDEM_75N_30M` | 477×477 | 1 920 | 84,8 | (0, 0) | (476, 476) | 673,17 |
| MoonPlanBench-15 | 15° | `LDEM_75S_30M` | 477×477 | 1 920 | 81,5 | (0, 0) | (476, 476) | 673,17 |
| MoonPlanBench-15 | 15° | `LDEM_80N_20M` | 475×475 | 1 280 | 83,4 | (0, 0) | (474, 472) | 668,92 |
| MoonPlanBench-15 | 15° | `LDEM_80S_20M` | 475×475 | 1 280 | 81,2 | (0, 0) | (474, 474) | 670,34 |
| MoonPlanBench-15 | 15° | `LDEM_85N_10M` | 474×474 | 640 | 82,1 | (0, 25) | (473, 473) | 651,49 |
| MoonPlanBench-15 | 15° | `LDEM_85S_10M` | 474×474 | 640 | 77,6 | (0, 0) | (473, 473) | 668,92 |
| MoonPlanBench-15 | 15° | `LDEM_875N_5M` | 474×474 | 320 | 78,8 | (0, 14) | (473, 473) | 659,10 |
| MoonPlanBench-15 | 15° | `LDEM_875S_5M` | 474×474 | 320 | 73,3 | (0, 0) | (473, 473) | 668,92 |
| MoonPlanBench-20 | 20° | `LDEM_45N_100M` | 450×450 | 6 400 | 96,4 | (0, 0) | (449, 449) | 634,98 |
| MoonPlanBench-20 | 20° | `LDEM_45S_100M` | 450×450 | 6 400 | 95,4 | (0, 0) | (449, 449) | 634,98 |
| MoonPlanBench-20 | 20° | `LDEM_60N_120M` | 243×243 | 7 680 | 95,5 | (0, 0) | (242, 242) | 342,24 |
| MoonPlanBench-20 | 20° | `LDEM_60S_120M` | 243×243 | 7 680 | 94,1 | (0, 0) | (242, 242) | 342,24 |
| MoonPlanBench-20 | 20° | `LDEM_75N_30M` | 477×477 | 1 920 | 94,0 | (0, 0) | (476, 476) | 673,17 |
| MoonPlanBench-20 | 20° | `LDEM_75S_30M` | 477×477 | 1 920 | 92,4 | (0, 0) | (476, 476) | 673,17 |
| MoonPlanBench-20 | 20° | `LDEM_80N_20M` | 475×475 | 1 280 | 93,1 | (0, 0) | (474, 472) | 668,92 |
| MoonPlanBench-20 | 20° | `LDEM_80S_20M` | 475×475 | 1 280 | 92,2 | (0, 0) | (474, 474) | 670,34 |
| MoonPlanBench-20 | 20° | `LDEM_85N_10M` | 474×474 | 640 | 92,5 | (0, 0) | (473, 473) | 668,92 |
| MoonPlanBench-20 | 20° | `LDEM_85S_10M` | 474×474 | 640 | 90,1 | (0, 0) | (473, 473) | 668,92 |
| MoonPlanBench-20 | 20° | `LDEM_875N_5M` | 474×474 | 320 | 90,8 | (0, 0) | (473, 473) | 668,92 |
| MoonPlanBench-20 | 20° | `LDEM_875S_5M` | 474×474 | 320 | 88,0 | (0, 0) | (473, 473) | 668,92 |

## 2. Metrik tablosu

Tanımlar PathBench'in (`basic_testing.get_results`, `analyzer`): başarı = son hücre hedefe eşit; yol = ardışık hücreler arası Öklid toplamı (hücre); adım/yol/süre/düzgünlük/açıklık **yalnız başarılı** koşuların ortalaması; hedefe kalan ve bellek tüm koşuların. Makale satırları **alıntı** (arXiv 2512.21438v1 Tablo 1; süreleri yazarların dizüstünde PathBench tekrar oynatması dahil ölçüldü, bizimkilerle karşılaştırılmaz).

Referans satırları: benchmark'ın kendi PythonRobotics planlayıcıları, bu makinede, yerel PlanetaryPathBench klonundan (Theta* için ham herhangi-açı uzunluğu parantezde; ölçülen uzunluk PathBench gibi Bresenham ile döşenmiş iz).

Bellek sütunu yalnız `--memory` geçişiyle dolar (§ 5); süre sütunları tracemalloc kapalı ölçümdür.

### MoonPlanBench-10 (10° eşik, 12 harita)

| Planlayıcı | Başarı | Yol (hücre) | Yol (km) | Süre ort. (s) | Süre maks (s) | Hedefe kalan (hücre) | Adım | Düzgünlük (rad/hamle) | Açıklık (hücre) | Bellek (MB) | Düğüm |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `dijkstra_cut` — Saf mesafe Dijkstra, benchmark hareket modeli (köşe-kesme serbest) | 100,0 % | 651,81 | 1 700,1 | 0,308 | 0,577 | 0,0 | 525,6 | 0,2439 | 1,37 | 36,1 | — |
| `dijkstra_nocut` — Saf mesafe Dijkstra, LunaPath kuralı (köşe-kesme yasak; nav2 baseline) | 33,3 % | 720,30 | 3 539,4 | 0,322 | 0,480 | 364,0 | 627,0 | 0,2956 | 1,56 | 18,9 | — |
| `lunapath_single` — LunaPath A*, tek kriter (w_slope = 1) | 33,3 % | 720,30 | 3 539,4 | 0,384 | 0,667 | 364,0 | 627,0 | 0,3042 | 1,61 | 43,7 | 31 546 |
| `lunapath_multi` — LunaPath A*, çok kriter (rover varsayılan ağırlıkları) | 33,3 % | 720,30 | 3 539,4 | 0,389 | 0,680 | 364,0 | 627,0 | 0,2908 | 1,63 | 43,7 | 31 567 |
| referans PythonRobotics Dijkstra (bu makine) | 100,0 % | 651,81 | — | 3,303 | 7,906 | 0,0 | 525,6 | 0,2386 | 1,36 | — | — |
| referans PythonRobotics AStar (bu makine) | 100,0 % | 651,81 | — | 7,825 | 20,480 | 0,0 | 525,6 | 0,2505 | 1,36 | — | — |
| referans PythonRobotics ThetaStar (bu makine) | 100,0 % | 654,61 (ham 625,04) | — | 6,485 | 15,039 | 0,0 | 532,0 | 0,4238 | 1,39 | — | — |
| makale Dijkstra (alıntı) | 100 % | 651,81 | — | 23,31 | — | 0 | — | — | — | — | — |
| makale ThetaStar (alıntı) | 100 % | 654,81 | — | 31,90 | — | 0 | — | — | — | — | — |
| makale AStar (alıntı) | 91 % | 639,94 | — | 30,82 | — | 56,1 | — | — | — | — | — |
| makale RRT (alıntı) | 8 % | 554,01 | — | 36,32 | — | 525,5 | — | — | — | — | — |
| makale Dynamic RRT (alıntı) | 8 % | 589,91 | — | 13,49 | — | 525,5 | — | — | — | — | — |
| makale RRT Connect (alıntı) | 0 % | 0 | — | 0 | — | 554,1 | — | — | — | — | — |

### MoonPlanBench-15 (15° eşik, 12 harita)

| Planlayıcı | Başarı | Yol (hücre) | Yol (km) | Süre ort. (s) | Süre maks (s) | Hedefe kalan (hücre) | Adım | Düzgünlük (rad/hamle) | Açıklık (hücre) | Bellek (MB) | Düğüm |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `dijkstra_cut` — Saf mesafe Dijkstra, benchmark hareket modeli (köşe-kesme serbest) | 100,0 % | 636,16 | 1 626,6 | 0,476 | 0,602 | 0,0 | 477,6 | 0,1308 | 2,09 | 61,6 | — |
| `dijkstra_nocut` — Saf mesafe Dijkstra, LunaPath kuralı (köşe-kesme yasak; nav2 baseline) | 91,7 % | 658,34 | 1 825,3 | 0,507 | 0,624 | 55,7 | 519,5 | 0,2031 | 2,29 | 56,8 | — |
| `lunapath_single` — LunaPath A*, tek kriter (w_slope = 1) | 91,7 % | 658,34 | 1 825,3 | 0,321 | 0,508 | 55,7 | 519,5 | 0,2054 | 2,29 | 44,3 | 32 820 |
| `lunapath_multi` — LunaPath A*, çok kriter (rover varsayılan ağırlıkları) | 91,7 % | 658,34 | 1 825,3 | 0,327 | 0,518 | 55,7 | 519,5 | 0,2321 | 2,30 | 44,3 | 32 979 |
| referans PythonRobotics Dijkstra (bu makine) | 100,0 % | 636,16 | — | 6,362 | 8,090 | 0,0 | 477,6 | 0,1353 | 2,08 | — | — |
| referans PythonRobotics AStar (bu makine) | 100,0 % | 636,16 | — | 13,452 | 29,723 | 0,0 | 477,6 | 0,1478 | 2,06 | — | — |
| referans PythonRobotics ThetaStar (bu makine) | 100,0 % | 639,14 (ham 617,90) | — | 8,061 | 13,262 | 0,0 | 482,7 | 0,2938 | 2,14 | — | — |
| makale Dijkstra (alıntı) | 100 % | 636,16 | — | 16,18 | — | 0 | — | — | — | — | — |
| makale ThetaStar (alıntı) | 100 % | 639,14 | — | 23,26 | — | 0 | — | — | — | — | — |
| makale AStar (alıntı) | 83 % | 621,25 | — | 32,45 | — | 72,1 | — | — | — | — | — |
| makale RRT (alıntı) | 42 % | 731,14 | — | 13,11 | — | 385,6 | — | — | — | — | — |
| makale Dynamic RRT (alıntı) | 50 % | 744,75 | — | 21,14 | — | 333,8 | — | — | — | — | — |
| makale RRT Connect (alıntı) | 8 % | 766,27 | — | 5,65 | — | 554,5 | — | — | — | — | — |

### MoonPlanBench-20 (20° eşik, 12 harita)

| Planlayıcı | Başarı | Yol (hücre) | Yol (km) | Süre ort. (s) | Süre maks (s) | Hedefe kalan (hücre) | Adım | Düzgünlük (rad/hamle) | Açıklık (hücre) | Bellek (MB) | Düğüm |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `dijkstra_cut` — Saf mesafe Dijkstra, benchmark hareket modeli (köşe-kesme serbest) | 100,0 % | 620,24 | 1 597,1 | 0,553 | 0,682 | 0,0 | 449,2 | 0,0654 | 3,30 | 66,8 | — |
| `dijkstra_nocut` — Saf mesafe Dijkstra, LunaPath kuralı (köşe-kesme yasak; nav2 baseline) | 100,0 % | 631,88 | 1 626,7 | 0,590 | 0,715 | 0,0 | 468,9 | 0,1148 | 3,42 | 66,7 | — |
| `lunapath_single` — LunaPath A*, tek kriter (w_slope = 1) | 100,0 % | 631,88 | 1 626,7 | 0,220 | 0,330 | 0,0 | 468,9 | 0,1140 | 3,46 | 43,7 | 17 895 |
| `lunapath_multi` — LunaPath A*, çok kriter (rover varsayılan ağırlıkları) | 100,0 % | 631,88 | 1 626,7 | 0,226 | 0,353 | 0,0 | 468,9 | 0,1445 | 3,47 | 43,9 | 18 908 |
| referans PythonRobotics Dijkstra (bu makine) | 100,0 % | 620,24 | — | 8,172 | 10,229 | 0,0 | 449,2 | 0,0648 | 3,23 | — | — |
| referans PythonRobotics AStar (bu makine) | 100,0 % | 620,24 | — | 8,395 | 21,328 | 0,0 | 449,2 | 0,0722 | 3,24 | — | — |
| referans PythonRobotics ThetaStar (bu makine) | 100,0 % | 623,17 (ham 611,40) | — | 4,704 | 8,118 | 0,0 | 454,2 | 0,1509 | 3,37 | — | — |
| makale Dijkstra (alıntı) | 100 % | 620,24 | — | 13,77 | — | 0 | — | — | — | — | — |
| makale ThetaStar (alıntı) | 100 % | 623,17 | — | 12,36 | — | 0 | — | — | — | — | — |
| makale AStar (alıntı) | 100 % | 620,24 | — | 19,52 | — | 0 | — | — | — | — | — |
| makale RRT (alıntı) | 100 % | 776,42 | — | 6,13 | — | 0 | — | — | — | — | — |
| makale Dynamic RRT (alıntı) | 100 % | 737,53 | — | 7,52 | — | 0 | — | — | — | — | — |
| makale RRT Connect (alıntı) | 25 % | 789,26 | — | 5,91 | — | 441,9 | — | — | — | — | — |

## 3. Başarı oranı farkları ve nedenleri

Benchmark'ın referans planlayıcıları (PythonRobotics `verify_node`) çapraz hamlede yalnız hedef hücreye bakar: iki dolu hücre arasından köşe keserek geçmek serbesttir. LunaPath ve nav2 baseline bunu reddeder (iki kardinal komşu da boş olmalı). Aşağıda `dijkstra_cut` ile bağlantılı olup `dijkstra_nocut` ile bağlantısız kalan haritalar: makalenin %100'ünün bu haritalarda sıfır genişlikli çapraz aralıklardan geçmeye dayandığı yerler.

- **MoonPlanBench-10:** yalnız köşe-kesmeyle bağlantılı 8/12 harita: `LDEM_60S_120M`, `LDEM_75N_30M`, `LDEM_75S_30M`, `LDEM_80S_20M`, `LDEM_85N_10M`, `LDEM_85S_10M`, `LDEM_875N_5M`, `LDEM_875S_5M`.
  - kesmesiz Dijkstra'nın yol bulduğu her haritada LunaPath'in iki modu da yol buldu: fark köşe-kesme kuralındadır, planlayıcıda değil.
  - 60 s'yi aşan koşu yok.
- **MoonPlanBench-15:** yalnız köşe-kesmeyle bağlantılı 1/12 harita: `LDEM_875S_5M`.
  - kesmesiz Dijkstra'nın yol bulduğu her haritada LunaPath'in iki modu da yol buldu: fark köşe-kesme kuralındadır, planlayıcıda değil.
  - 60 s'yi aşan koşu yok.
- **MoonPlanBench-20:** yalnız köşe-kesmeyle bağlantılı 0/12 harita.
  - kesmesiz Dijkstra'nın yol bulduğu her haritada LunaPath'in iki modu da yol buldu: fark köşe-kesme kuralındadır, planlayıcıda değil.
  - 60 s'yi aşan koşu yok.

## 4. Çok kriterli mod ne satın alıyor

Haritalar yalnızca eğim/pürüzlülük eşikli occupancy: gölge, termal, slip, pürüzlülük ve Dünya görünürlüğü katmanı yok, ham DEM de yayımlanmamış (eğim türetilemez). Adaptör eğimi ve gölgeyi 0, termali sabit verir; dört (beş) kriterin hepsi sabit kalır ve maliyet gridi tek değerdir. Araştırma belgesindeki "çok kriterli maliyetin getirdiği X % gölge azalması" cümlesi bu benchmark'ta **kurulamaz**.

| Varyant | Maliyet gridi benzersiz değer (min–maks, harita başına) | `lunapath_single` = `lunapath_multi` uzunluk (harita) | Aynı hücre dizisi (harita) |
|---|---|---|---|
| MoonPlanBench-10 | 1–1 | 12/12 | adım sayısı eşit 12/12 (hücre dizisi eşitlik kırma yüzünden farklı olabilir) |
| MoonPlanBench-15 | 1–1 | 12/12 | adım sayısı eşit 12/12 (hücre dizisi eşitlik kırma yüzünden farklı olabilir) |
| MoonPlanBench-20 | 1–1 | 12/12 | adım sayısı eşit 12/12 (hücre dizisi eşitlik kırma yüzünden farklı olabilir) |

Okuma: tek değerli gridde LunaPath A* en kısa yol aramasıdır; ağırlık seti yalnız sabitin büyüklüğünü (ve heap'teki eşitlik kırmayı) değiştirir. Çok kriterli modun ne satın aldığı yalnız bizim katmanlarımızın olduğu Site11'de ölçülebilir (nav2 baseline, C4 raporu).

## 5. Süre ve bellek

Bizim sürelerimiz planlayıcı çağrısının duvar saati (bu makine), `tracemalloc` kapalı. Bellek, aynı koşunun `tracemalloc` açık ikinci geçişindeki tepe değeridir; o geçişin süresi ayrı sütunda — tracemalloc bellek ayırmayı izlerken Python'u belirgin yavaşlatır. PathBench simülasyonu **tracemalloc açıkken** zamanlar ve süreye hücre hücre tekrar oynatmayı da katar (yazarların i7-1355U dizüstü, Python 3.8); makale MoonPlanBench için bellek vermiyor.

| Varyant | Planlayıcı | Süre ort. (s) | Süre maks (s) | Süre, tracemalloc açık (s) | Bellek ort. (MB) | Düğüm ort. | Aşan koşu |
|---|---|---|---|---|---|---|---|
| MoonPlanBench-10 | `dijkstra_cut` | 0,308 | 0,577 | 3,119 | 36,1 | — | 0 |
| MoonPlanBench-10 | `dijkstra_nocut` | 0,322 | 0,480 | 2,978 | 18,9 | — | 0 |
| MoonPlanBench-10 | `lunapath_single` | 0,384 | 0,667 | 11,694 | 43,7 | 31 546 | 0 |
| MoonPlanBench-10 | `lunapath_multi` | 0,389 | 0,680 | 11,827 | 43,7 | 31 567 | 0 |
| MoonPlanBench-10 | referans Dijkstra | 3,303 | 7,906 | — | — | — | 0 |
| MoonPlanBench-10 | referans AStar | 7,825 | 20,480 | — | — | — | 0 |
| MoonPlanBench-10 | referans ThetaStar | 6,485 | 15,039 | — | — | — | 0 |
| MoonPlanBench-10 | makale Dijkstra (alıntı; tracemalloc açık, tekrar oynatma dahil) | 23,31 | — | — | — | — | — |
| MoonPlanBench-10 | makale ThetaStar (alıntı; tracemalloc açık, tekrar oynatma dahil) | 31,90 | — | — | — | — | — |
| MoonPlanBench-10 | makale AStar (alıntı; tracemalloc açık, tekrar oynatma dahil) | 30,82 | — | — | — | — | — |
| MoonPlanBench-15 | `dijkstra_cut` | 0,476 | 0,602 | 4,742 | 61,6 | — | 0 |
| MoonPlanBench-15 | `dijkstra_nocut` | 0,507 | 0,624 | 4,599 | 56,8 | — | 0 |
| MoonPlanBench-15 | `lunapath_single` | 0,321 | 0,508 | 9,552 | 44,3 | 32 820 | 0 |
| MoonPlanBench-15 | `lunapath_multi` | 0,327 | 0,518 | 9,555 | 44,3 | 32 979 | 0 |
| MoonPlanBench-15 | referans Dijkstra | 6,362 | 8,090 | — | — | — | 0 |
| MoonPlanBench-15 | referans AStar | 13,452 | 29,723 | — | — | — | 0 |
| MoonPlanBench-15 | referans ThetaStar | 8,061 | 13,262 | — | — | — | 0 |
| MoonPlanBench-15 | makale Dijkstra (alıntı; tracemalloc açık, tekrar oynatma dahil) | 16,18 | — | — | — | — | — |
| MoonPlanBench-15 | makale ThetaStar (alıntı; tracemalloc açık, tekrar oynatma dahil) | 23,26 | — | — | — | — | — |
| MoonPlanBench-15 | makale AStar (alıntı; tracemalloc açık, tekrar oynatma dahil) | 32,45 | — | — | — | — | — |
| MoonPlanBench-20 | `dijkstra_cut` | 0,553 | 0,682 | 5,472 | 66,8 | — | 0 |
| MoonPlanBench-20 | `dijkstra_nocut` | 0,590 | 0,715 | 5,441 | 66,7 | — | 0 |
| MoonPlanBench-20 | `lunapath_single` | 0,220 | 0,330 | 5,835 | 43,7 | 17 895 | 0 |
| MoonPlanBench-20 | `lunapath_multi` | 0,226 | 0,353 | 6,120 | 43,9 | 18 908 | 0 |
| MoonPlanBench-20 | referans Dijkstra | 8,172 | 10,229 | — | — | — | 0 |
| MoonPlanBench-20 | referans AStar | 8,395 | 21,328 | — | — | — | 0 |
| MoonPlanBench-20 | referans ThetaStar | 4,704 | 8,118 | — | — | — | 0 |
| MoonPlanBench-20 | makale Dijkstra (alıntı; tracemalloc açık, tekrar oynatma dahil) | 13,77 | — | — | — | — | — |
| MoonPlanBench-20 | makale ThetaStar (alıntı; tracemalloc açık, tekrar oynatma dahil) | 12,36 | — | — | — | — | — |
| MoonPlanBench-20 | makale AStar (alıntı; tracemalloc açık, tekrar oynatma dahil) | 19,52 | — | — | — | — | — |

Harita başına en yavaş LunaPath koşuları:

- MoonPlanBench-10/`LDEM_45S_100M` `lunapath_multi`: 0,7 s, 76 187 düğüm
- MoonPlanBench-10/`LDEM_45S_100M` `lunapath_single`: 0,7 s, 76 207 düğüm
- MoonPlanBench-10/`LDEM_875N_5M` `lunapath_multi`: 0,7 s, 99 160 düğüm
- MoonPlanBench-10/`LDEM_875N_5M` `lunapath_single`: 0,6 s, 99 160 düğüm
- MoonPlanBench-10/`LDEM_80N_20M` `lunapath_multi`: 0,5 s, 73 830 düğüm

## 6. İddia sınırı ve sunum cümlesi

- Bu benchmark **yalnızca eğim (+ pürüzlülük) eşikli occupancy** gridleridir; hücre 320 m – 7 680 m (bölgesel ölçek, rover ölçeği değil). Başarı, bir hareket modeli altında bağlantılılık ve en kısa yol ölçümüdür; rota planlamasının fizik/termal/gölge boyutlarını ölçmez.
- Makalenin %100'ü köşe-kesmeye izin veren hareket modeline bağlıdır; LunaPath'in güvenlik kuralıyla başarı oranı düşer ve bu **saklanmaz**, iki satır ayrı ayrı verilir.
- Makaleden alınan her sayı "alıntı" etiketlidir; süreler makineler arası karşılaştırılmaz.
- Öğrenilmiş planlayıcılar koşturulmadı; "öğrenme tabanlı modeller gezegen arazisine genellemiyor" bulgusu makalenin kendi sonucudur (§ 3.3, § 4.2.3: Radish'te WPN dışında hiçbiri yol bulamadı, WPN 10× yavaş; Ay/Mars tablolarında öğrenilmiş satır yok) ve öğrenilmiş planlayıcı kullanmama kararımızın literatür dayanağı olarak **alıntı** kalır.

**Sunum cümlesi:** "Bağımsız, yalnızca eğim eşikli bir occupancy benchmark'ında (MoonPlanBench, 36 harita) benchmark'ın hareket modeliyle en kısa yol uzunluklarını makalenin Dijkstra satırıyla aynen ürettik (10°: 651,81, 15°: 636,16, 20°: 620,24; makale 10°: 651,81, 15°: 636,16, 20°: 620,24); LunaPath'in köşe-kesme yasağıyla başarı 10°: 33,3 %, 15°: 91,7 %, 20°: 100,0 % — makalenin %100'ü, düşük eşikli varyantta iki dolu hücre arasından çapraz geçmeye dayanıyor. Çok kriterli maliyet bu haritalarda tek değerdir; gölge/termal kazancı burada ölçülemez, Site11'de ölçülür."

Makine-okunur iddia (`app.benchmark.CLAIM`): MoonPlanBench maps are slope/roughness-thresholded occupancy grids only (no shadow, thermal, slip, roughness or Earth-visibility layer, no DEM released), at 320 m to 7 680 m per cell: LunaPath's multi-criteria cost grid is a single value on them and its planner reduces to a shortest-path search with its own safety rules. Success here measures connectivity under a motion model, not rover route planning. The benchmark's reference planners allow diagonal moves between two occupied cells; LunaPath refuses them. Every paper figure is a quotation from arXiv 2512.21438v1, not our measurement.

## Kaynaklar

- Planetary Terrain Datasets and Benchmarks for Rover Path Planning — Marvin Chancán, Avijit Banerjee, George Nikolakopoulos (Luleå University of Technology), arXiv:2512.21438v1, https://arxiv.org/abs/2512.21438
- https://github.com/mchancan/PlanetaryPathBench (commit `86dc4b63f14551e55607bad1ce520164d8a96359`); PathBench (Toma vd., BSD-3); PythonRobotics (Sakai vd., MIT)

