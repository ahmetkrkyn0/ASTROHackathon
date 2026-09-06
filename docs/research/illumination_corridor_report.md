# Sürekli-aydınlık koridoru (A2) — Site11 ölçüm raporu

Üretim: `scripts/illumination_corridor_report.py`, 2026-09-04T19:47:03Z. Kaynak: Otten, Jones, Wettergreen, Whittaker (ICRA 2015; FSR 2017) — CMU'nun Güneş-eşzamanlı (sun-synchronous) x-y-t bağlı-bileşen budaması, 4-B planlayıcımızın ön-filtresi olarak.

**İddia sınırı.** "Koridor içinde modelin gölge serisi hiç karanlık göstermez": SPICE Güneş konumu + ufuk küpü (72 azimut kutusu, iki ölçekli), 320 m kaba bloklar, örneklenmiş dilimler. Gerçek yüzey hakkında bir iddia değildir; B3'e göre 30 Mayıs 2027'de hücrelerin %10,8'i NASA'nın 100 DEM klonu arasında aydınlık/karanlık olarak kararsızdır.

Kısaltmalar: `all` = bloktaki 16 ince hücrenin hepsi aydınlık; `majority` = blok ortalaması < 0,5 (planlayıcının kendi karanlık eşiği). Hacimler voksel (kaba hücre × dilim) sayısıdır.

## 1. Standart çift (358,494)→(206,426), uçtaki varsayılan ufuk

| Epoch | Kural | Dilim × saat | Geçilebilir voksel | Aydınlık-güvenli | Koridor | Budanan | CMU 26-komşuluk bileşen (sayı / en büyük / iki ucu tutan) | Başlangıç t0 koridorda | Hedef koridor dilimi | Rota koridorda | Rota gölge (h, maks) | `require` sonucu | Süre (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| VIPER, 30 May 2027 (haven->haven günü) | `all` | 100 × 0,0956 | 1 031 400 | 417 294 (40,5 %) | 416 646 | 0,2 % | 50 / 379 720 / 44 | hayır | 0 / 100 | hayır | 4,55 | 404 | 11,6 |
| VIPER, 30 May 2027 (haven->haven günü) | `majority` | 100 × 0,0956 | 1 031 400 | 472 207 (45,8 %) | 471 426 | 0,2 % | 44 / 424 436 / 34 | hayır | 0 / 100 | hayır | 4,55 | 404 | 6,3 |
| LPR-1, 28 Eyl 2026 | `all` | 100 × 0,0287 | 1 140 200 | 55 150 (4,8 %) | 54 984 | 0,3 % | 9 / 25 327 / 9 | hayır | 100 / 100 | hayır | 0,21 | 404 | 8,2 |
| LPR-1, 28 Eyl 2026 | `majority` | 100 × 0,0287 | 1 140 200 | 74 144 (6,5 %) | 73 952 | 0,3 % | 6 / 39 849 / 5 | hayır | 100 / 100 | hayır | 0,21 | 404 | 4,8 |
| LPR-1, Ay gecesi 13 Eyl 2026 | `all` | 246 × 0,0287 | 2 804 892 | 0 (0,0 %) | 0 | — | 0 / 0 / 0 | hayır | 0 / 246 | hayır | 4,03 | 404 | 12,9 |
| LPR-1, Ay gecesi 13 Eyl 2026 | `majority` | 246 × 0,0287 | 2 804 892 | 0 (0,0 %) | 0 | — | 0 / 0 / 0 | hayır | 0 / 246 | hayır | 4,03 | 404 | 9,0 |

- **VIPER, 30 May 2027 (haven->haven günü)**, `require_continuous_illumination` (`all`): 404 — Start (89, 123) is not inside the continuous-illumination corridor at the first slice: under require_continuous_illumination the rover must begin in a block that is lit and can stay lit (the shortest gated coarse route needs at least 40 moves at 100 slices of 0.0956 h) Continuous-illumination corridor (lit_rule=all): 416646 of 417294 lit-and-passable voxels survive the two-pass pruning (40.4 percent of the 1031400-voxel traversable volume); the start block is never inside the corridor; the goal block is inside the corridor for 0 of 100 slices and is not reachable from the start inside it.
- **LPR-1, 28 Eyl 2026**, `require_continuous_illumination` (`all`): 404 — Start (89, 123) is not inside the continuous-illumination corridor at the first slice: under require_continuous_illumination the rover must begin in a block that is lit and can stay lit (the shortest gated coarse route needs at least 40 moves at 100 slices of 0.0287 h) Continuous-illumination corridor (lit_rule=all): 54984 of 55150 lit-and-passable voxels survive the two-pass pruning (4.8 percent of the 1140200-voxel traversable volume); the start block is never inside the corridor; the goal block is inside the corridor for 100 of 100 slices and is not reachable from the start inside it.
- **LPR-1, Ay gecesi 13 Eyl 2026**, `require_continuous_illumination` (`all`): 404 — Start (46, 8) is not inside the continuous-illumination corridor at the first slice: under require_continuous_illumination the rover must begin in a block that is lit and can stay lit (the shortest gated coarse route needs at least 113 moves at 246 slices of 0.0287 h) The site is in darkness for the entire 7.1 h horizon from start_utc: no slice is lit, so the route must run on battery, or start at a lit epoch. Continuous-illumination corridor (lit_rule=all): 0 of 0 lit-and-passable voxels survive the two-pass pruning (0.0 percent of the 2804892-voxel traversable volume); no block is lit at any of the 246 slices (7.1 h) from start_utc; the start block is never inside the corridor; the goal block is inside the corridor for 0 of 246 slices and is not reachable from the start inside it.

## 2. Koridor-içi çift: budamalı vs budamasız planlama (8 h ufuk, 0.1 h dilim, en iyi 3 koşum)

Çift `illumination_corridor.corridor_pair` ile seçildi: dilim-0 koridor kesitinde standart başlangıca en yakın blok → koridor içinde ondan ulaşılabilen en uzak (Chebyshev) blok.

### VIPER, 30 May 2027 (haven->haven günü)

Koridor kurulumu (80 dilim): aydınlık-güvenli 334 056 / geçilebilir 825 120 voksel, koridor 333 627; süreler (ms) hacim 55, kenarlar 4, budama 46, dwell 3, toplam 108.
Çift: kaba (105,89) → (94,27), Chebyshev 62 blok, hedefe ilk varış dilimi 79, koridor içinde ulaşılabilir 1977 blok.

| Varyant | Durum | Planlama (ms) | Genişletilen düğüm | Hamle / bekleme | Varış (h) | Maliyet | Rota gölge maks (h) | Koridor dışı durum | Koridor reddi | LP-R01 ρ (h) | `h_max_shadow_h` | Maks dwell (h) | Dwell ufka dayalı | En düşük SOC (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| budamasız | 200 | 452 | 7 233 | 62 / 0 | 7,90 | 7,547 | 0,00 | 0 | 0 | 96,00 | 96 | 8,00 | evet | 93,6 |
| koridor, all | 200 | 417 | 6 467 | 62 / 0 | 7,90 | 7,547 | 0,00 | 0 | 1342 | 96,00 | 96 | 8,00 | evet | 93,6 |
| koridor, majority | 200 | 453 | 6 721 | 62 / 0 | 7,90 | 7,547 | 0,00 | 0 | 524 | 96,00 | 96 | 8,00 | evet | 93,6 |

- `koridor, all` vs budamasız: planlama süresi ×1,08, genişletilen düğüm ×1,12; koridor 333 627 / aydınlık-güvenli 334 056 voksel; CMU label 50 bileşen, en büyüğü 303 940 voksel, iki ucu tutan 45; koridor kurulumu 110 ms.

- `koridor, majority` vs budamasız: planlama süresi ×1,00, genişletilen düğüm ×1,08; koridor 377 369 / aydınlık-güvenli 378 020 voksel; CMU label 44 bileşen, en büyüğü 339 700 voksel, iki ucu tutan 34; koridor kurulumu 227 ms.

### LPR-1, 28 Eyl 2026

Koridor kurulumu (80 dilim): aydınlık-güvenli 20 566 / geçilebilir 912 160 voksel, koridor 0; süreler (ms) hacim 71, kenarlar 6, budama 42, dwell 4, toplam 124.

Dilim 0'da koridorda hiçbir blok yok: koridor-içi çift seçilemedi (koridor boş).

### LPR-1, Ay gecesi 13 Eyl 2026

Koridor kurulumu (80 dilim): aydınlık-güvenli 0 / geçilebilir 912 160 voksel, koridor 0; süreler (ms) hacim 49, kenarlar 6, budama 37, dwell 3, toplam 95.

Dilim 0'da koridorda hiçbir blok yok: koridor-içi çift seçilemedi (koridor boş).

## 3. Okuma

- Koridor içindeki her rotada `path_dark_hours` tanım gereği sıfırdır ve D3'ün LP-R01 marjı rover'ın tam gölge dayanımına eşittir (`h_max_shadow_h`): "rota gölgeye girmiyor" kanıtı planlayıcının kendi sayımı ve formal monitörle okunur.
- Standart haven→haven çifti CMU anlamında Güneş-eşzamanlı değildir: başlangıç bloğu t0'da karanlık; koridor kuralı onu tanım gereği reddeder. Hızlanma yalnızca koridor-içi çiftlerde anlamlıdır ve yukarıdaki tabloda ölçülmüştür.
- Dwell sayıları varsayılan kısa ufka (8 h) dayanır (`horizon_limited`); CMU'nun 45/226 saatlik dwell'leri 59 günlük pencerelerdendir.
- Budama bu ufuklarda çok az siler (%0,2–0,3): kutupta aydınlanma 10 saatte neredeyse durağandır, dolayısıyla aydınlık-güvenli hacmin hemen tamamı zaten ilk dilimden son dilime bağlıdır. CMU'nun budaması 59 günlük pencerelerde (aydınlık adaların doğup söndüğü ölçekte) anlamlıdır; bu ufuklarda koridorun değeri budama değil, garanti ve planlayıcının rotayı koridorda tutmasıdır.
- Hızlanma mütevazıdır: maliyet küpü gölgeyi zaten fiyatladığı ve sezgisel odaklı olduğu için budamasız rota da koridorun içinde kalır; koridor kuralı genişletmeyi bir miktar azaltır (yukarıdaki × oranları), yani "22 s → X s" türü bir kazanç bu gridde ölçülmemiştir. A3'ün hedef alt-hacmi (`prune_corridor(sources=başlangıç, sinks=hedef)`) budamayı rotaya özgü kılacak adaydır.
- LPR-1'in 28 Eylül 2026 gününde 8 saatlik koridor yoktur: aydınlık ada büzülür (2,9 h ufukta 55 150, 8 h ufukta 20 566 aydınlık-güvenli voksel) ve t0'daki hiçbir blok pencere sonuna kadar bağlı-aydınlık kalmaz; uç bunu `voxels.corridor = 0` ve 404 gerekçesiyle söyler.

Sunum cümlesi: **Sun-synchronous yaklaşımını (CMU, NIAC) 4-B planlayıcımızın ön-filtresi olarak uyguladık.** Tasarım: `docs/superpowers/specs/2026-09-04-a2-illumination-corridor-design.md`.
