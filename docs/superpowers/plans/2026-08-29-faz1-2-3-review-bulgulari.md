# Faz 1-2-3 Uygulama Review'u — Bulgular ve Düzeltmeler

**Tarih:** 29 Ağustos 2026 (bulgular) → 29 Ağustos 2026 (düzeltmeler, aynı gün ikinci geçiş)
**Branch:** `backend/physics`
**Kapsam:** [`faz1-gercek-fizik.md`](2026-08-19-faz1-gercek-fizik.md) · [`faz2-maliyet-mimarisi.md`](2026-08-19-faz2-maliyet-mimarisi.md) · [`faz3-zaman-ekseni.md`](2026-08-19-faz3-zaman-ekseni.md)
**Yöntem:** Plan ↔ kod karşılaştırması + testlerin çalıştırılması + gerçek `lunapath/data/processed/` grid'i üzerinde canlı API ölçümü

> Bu belge önce bir **denetim raporu** olarak yazıldı, sonra kullanıcı talebiyle bulguların çoğu **aynı oturumda düzeltildi**. Her bulgunun başlığında düzeltme durumu işaretli (✅ düzeltildi / ⏸️ bilinçli olarak düzeltilmedi / 📝 belge düzeltmesi). Uygulanan değişikliklerin tam listesi ve kalan işler için bkz. [Uygulanan düzeltmeler](#uygulanan-düzeltmeler) bölümü, en altta.

---

## Yönetici özeti

**Faz 1 ve Faz 2 sağlam.** İki kritik düzeltme (azimut çerçeve uyuşmazlığı, y-ekseni işaret hatası) bağımsız olarak yeniden hesaplandı ve doğru çıktı. Sözleşmeler, testler ve kabul kriterleri karşılanıyor.

**Faz 3 CI'da yeşil ama sahada çalışmıyordu.** H1 + H2 + H3 birlikte `/api/plan-4d`'yi sevk edilen grid'de kullanılamaz hale getiriyordu; tek sebebi testlerin 16×16'lık, engelsiz, tekdüze bir fixture'da kalmasıydı. **Üçü de bu oturumda düzeltildi** — gerçek grid üzerinde ölçülen başarı oranı 12'de 1'den, ufuk yeterliyse 100%'e çıktı (ölçüm: bkz. H2).

**H4** ilk yazıldığında Faz 1'in "gerçek fizik" iddiasının en zayıf noktası olarak, `Heat1DModel`'in PLAN belgesindeki taslak koduna (`ndays=1`, çıplak `import planets`) dayanarak tarif edilmişti. Düzeltme aşamasında **gerçek, uygulanmış kod** yeniden okunduğunda bunun doğru olmadığı ortaya çıktı: gerçek `Heat1DModel._lookup_table` çok daha sofistike (`ndays=13` ~1 Ay yılı, `crank-nicolson` çözücü, `heat1d.planets`) ve bu seçimler kendi içinde belgelenmiş, ölçülmüş kararlar. Bulgunun **temel gözlemi** (kaydedilmiş `thermal_grid.npy`'de eğim-sıcaklık Spearman korelasyonu 0.984, bakı yayılımı ≤13 K) `.npy` dosyasından doğrudan ölçüldüğü için hâlâ geçerli — ama **mekanizma açıklaması yanlıştı**, aşağıda düzeltildi. Bu nedenle H4 için kod değişikliği yapılmadı (gerekçe: bkz. H4 bölümü); onun yanında duran **M1 gerçek bir hataydı ve düzeltildi**.

### Bulgu tablosu

| # | Önem | Durum | Başlık | Faz |
|---|---|---|---|---|
| H1 | 🔴 Yüksek | ✅ Düzeltildi | `/api/plan-4d` varsayılan ayarlarıyla gerçek grid'de çalışmıyor | 3 |
| H2 | 🔴 Yüksek | ✅ Düzeltildi | `/api/plan-4d`'yi gerçekçi grid'de sınayan test yok | 3 |
| H3 | 🔴 Yüksek | ✅ Düzeltildi | Konservatif kabalaştırma planlama grafiğini parçalıyor | 3 |
| H4 | 🔴 Yüksek | ⏸️ Düzeltilmedi (bilinçli) + 📝 açıklama düzeltildi | heat1d termal katmanı pratikte eğimin monoton fonksiyonu, üstelik ters | 1 |
| M1 | 🟠 Orta | ✅ Düzeltildi | C1 azimut hatası gölge için düzeltildi, termal için düzeltilmedi | 1 |
| M2 | 🟠 Orta | ✅ Düzeltildi | BEKLE ve HAREKET kenarları farklı birimde; bekleme ~6.500× ucuz | 3 |
| M3 | 🟠 Orta | ⏸️ Düzeltilmedi (bilinçli) | `surface_to_inner`'da 0 °C süreksizliği artık Corridor'a sızıyor | 2 (miras) |
| M4 | 🟠 Orta | 🟡 Kısmen iyileşti (H1+M2'nin yan etkisi) | `n_slices` büyütmek arama işini lineer büyütüyor, karşılığı yok | 3 |
| L1 | 🟡 Düşük | ✅ Düzeltildi | `horizon_map` docstring'i kendi koduyla çelişiyor | 1 |
| L2 | 🟡 Düşük | ⏸️ Düzeltilmedi (tarihi rapor) | `sun_track`'ın `furnsh` maliyeti raporda abartılmış | 1 |
| L3 | 🟡 Düşük | ⏸️ Değerlendirildi, değiştirilmedi | `illuminated_mask`'teki `> 0.0` tabanı fizikten katı | 1 |
| L4 | 🟡 Düşük | ✅ Düzeltildi | Bilinmeyen `rover_id` 422 değil 500 veriyor | 2, 3 |
| L5 | 🟡 Düşük | ✅ Düzeltildi | `cost`/`traversable` koşulsuz `"DERIVED"` etiketleniyor | 1 |
| L6 | 🟡 Düşük | ✅ Düzeltildi | `process_lunar_data.py`'de bayat "düzeltilmedi" yorumu | 2 |
| L7 | 🟡 Düşük | ⏸️ Düzeltilmedi (repo politikası) | Commit'lenmiş `metadata.json` repoda olmayan grid'leri tarif ediyor | 1 |
| — | — | ✅ Bonus fix | `test_traversability.py` üç fazın da kabul kriterinde ama kırıktı | 1, 2, 3 |

---

## Doğrulama tabanı

```
pytest                        214 passed, 3 warnings in 177.12s
python test_cost_engine.py    PASSED: 42  FAILED: 0   (çıkış 0)
python test_traversability.py ImportError               (çıkış 1)  <-- KIRIK
```

`test_traversability.py` kırıktı:

```
ImportError: cannot import name 'THERMAL_MIN_TRAVERSABLE_C' from 'app.traversability'
```

Faz 1 raporu bunu "Task 1 başlamadan önce de bozuktu, bu planla ilgisi yok" diye **doğru** tespit etmiş. Ama madde master planın Global Constraints'inde ve **her üç fazın kabul kriterinde** (`python test_traversability.py` — çıkış kodu 0) duruyordu ve karşılanmıyordu.

**✅ Düzeltildi.** `app/traversability.py`, bu modülün zaten belgelenmiş tek-doğruluk-kaynağı olduğu `THERMAL_MIN_TRAVERSABLE_C`'yi `app.constants`'tan re-export ediyor artık. `python test_traversability.py` → **23 PASS, çıkış kodu 0** (18 mevcut + 5 yeni `weakest_validity` testi, bkz. L5).

### Bağımsız olarak doğrulanan düzeltmeler

| Ne | Nasıl doğrulandı | Sonuç |
|---|---|---|
| Faz 1 **C1** azimut çerçeve düzeltmesi | `true_north_grid_azimuth` canlı `metadata.json` ile koşuldu → **249.775°**. Analitik kutupsal-stereografik değer: pencere merkezi lon = −110.225° ⟹ 360 − 110.225 = **249.775°** | ✅ Birebir |
| Faz 2 **C2** y-ekseni işaret düzeltmesi | Üç yer de tutarlı: `corridor._pixel_to_metres`, `serializer.pixel_to_lonlat`/`lonlat_to_pixel`, `window_center_latlon`. Canlı `/api/plan`: `waypoint[0] = (−15500, −4000)` = metadata origin'i **tam olarak**; `geojson[0] = (−104.470, −89.472)` aynı nokta | ✅ Faz 1'in "serializer.py'de düzeltilmedi" maddesi kapandı |
| `f_shadow_cell` ölçek düzeltmesi | Canlı `/api/cell-telemetry` → `cost_breakdown.shadow = 0.011` (eskiden ~5e-5) | ✅ |
| `CostMap.total()` ↔ `compute_cost_grid` eşitliği | `test_costmap.py::test_default_cost_map_matches_compute_cost_grid` mevcut ve geçiyor | ✅ |
| 6 replan tetikleyicisi | Her biri için birim test var; canlı: boş state → `replanned:false`, SOC açığı → `replanned:true` + `soc_deviation` | ✅ |
| Corridor dizi uzunlukları | Canlı: 693 waypoint, dört segment dizisi de 692, `fallback_points` 693 | ✅ AC karşılandı |
| `astar_4d` optimalliği | Sezgisel `mesafe × (1 + min_cost)`; her MOVE ≥ bu, WAIT h'yi sabit tutup ≥0 maliyetli ⟹ hem admissible hem consistent | ✅ Closed-set A* optimal |

---

## 🔴 H1 — `/api/plan-4d` varsayılan ayarlarıyla gerçek grid'de çalışmıyor ✅ Düzeltildi

**Dosya:** `backend/app/main.py:67`, `backend/app/main.py:581`

`DEFAULT_PLAN_4D_SLICES = 24`, Faz 3 review'unun **C1 düzeltmesiyle hiç uzlaştırılmamış**. C1, `slice_hours`'ı sabit 1 saatten `auto_slice_hours` (bir hücre geçişi) değerine indirdi — coarsen=4'te **0.031 saat**, yani ~32× daha kısa. Dilim sayısı 24'te bırakılınca ufuk 24 × 0.031 = **0.74 saat** ≈ 24 hamle ≈ **480 m**, 2.5 km'lik bir grid'de.

### Ölçüm

12 rastgele geçilebilir başlangıç/hedef çifti, aynı grid, aynı rover:

| Endpoint | Başarı | Hata dağılımı |
|---|---|---|
| `POST /api/plan` | **12/12** | — |
| `POST /api/plan-4d` (coarsen=4, varsayılan) | **1/12** | 10× `No path found within the time horizon`, 1× `Start is not traversable` |

Aynı rotanın (`(30,470) → (498,498)`, kaba Chebyshev mesafesi 117 hücre) dilim sayısına duyarlılığı:

| `n_slices` | Sonuç | Düğüm | Süre |
|---|---|---|---|
| 24 (varsayılan) | **404** `No path found within the time horizon` | — | 0.3 s |
| 200 | 200 OK — 117 hamle, `arrival_slice=164`, 5.07 saat | 136.459 | 3.3 s |
| 1000 | 200 OK — **birebir aynı yol** | 1.056.933 | 25.5 s |

```
auto_slice_hours (coarsen=4) = 0.03093 h = 111.3 s
24 dilim -> ufuk 0.742 h; erişilebilir ~24 kaba hücre = 480 m / 2500 m
```

### Öneri

Dilim sayısını sabit bir sayı olarak bırakma. Ya grid çapından türet:

```
n_slices ~= ceil(kaba_chebyshev_cap * ortalama_d_slices * guvenlik_payi)
```

ya da varsayılan girdiyi `horizon_hours` yap (zaten destekleniyor, `n_slices` yalnızca bellek düğmesi olarak kalsın). Ayrıca 404 mesajı "ufuk yetmedi" ile "geçilemez / bağlantısız" arasında ayrım yapmalı — şu an ikisi de aynı metni veriyor.

### Düzeltme

Sabit `DEFAULT_PLAN_4D_SLICES` tamamen kaldırıldı. `main.py`'de yeni `pathfinder_4d.bfs_move_count(coarse_traversable, coarse_start, coarse_goal)` — kaba grid üzerinde ağırlıksız, zaman eksenini yok sayan bir BFS — hem H1'i hem H3'ün teşhis kısmını çözüyor:

- **Ulaşılamaz** (başlangıç/hedef bloklu ya da bağlantısız) → `astar_4d` hiç çağrılmadan **422**, sebebi adıyla.
- **Ulaşılabilir**, `n_slices`/`horizon_hours` verilmemiş → varsayılan dilim sayısı, **tahmin değil kanıt**: `move_count × (en dik kenarın gerektirdiği maksimum dilim sayısı) + BEKLE payı (20)`. `max_slices_per_move`, `edge_travel_time_s(slope_max_deg, çapraz_mesafe, rover)` ile hesaplanıyor — coğrafi olarak gerçekten yeterli, çünkü grid'in ürettiği en pahalı kenardan asla daha kısa olamaz.

`bfs_move_count`'un kendisi `coarsen_traversable`'ın **zaten var olan** garantisinden yararlanıyor: bir kaba blok geçilebilir işaretliyse (tüm ince hücreler `slope_max_deg` altında), o blok kesin sonlu maliyetli — ayrı bir "kullanılabilir" maskesi gerekmiyor (bkz. H3'teki "declutter" denemesinin neden terk edildiği).

**Ölçüm (aynı 12 rastgele çift, düzeltme sonrası):** `/api/plan-4d` artık **8/12 başarı**, kalan 4'ü (1 aynı-kaba-hücre + 3 kaba-blok-geçilemez) **422** ile açık sebep veriyor — hiçbiri eski `404 "No path found within the time horizon"` değil. Kilitli regresyon testi: [`test_plan_4d_real_grid.py::test_default_horizon_solves_a_route_the_old_fixed_default_starved`](../../backend/test_plan_4d_real_grid.py) — 33 kaba-hamlelik bir rota, eski sabit 24 dilimle kesin başarısız olurdu, şimdi varsayılanla geçiyor.

---

## 🔴 H2 — `/api/plan-4d`'yi gerçekçi bir grid'de sınayan test yok ✅ Düzeltildi

**Dosya:** `backend/test_plan_4d_endpoint.py:12-33`

```python
SHAPE = (16, 16)
"slope":        np.full(SHAPE, 3.0),        # tekdüze, düz
"thermal":      np.full(SHAPE, -60.0),      # tekdüze
"shadow_ratio": np.full(SHAPE, 0.3),        # tekdüze
"traversable":  np.ones(SHAPE, dtype=bool)  # engel yok
...
"n_slices": 24, "coarsen": 4
```

16×16 grid, coarsen=4 ⟹ **4×4 kaba grid**. Orada 24 dilim fazlasıyla yeterli ve tek bir engel bile yok. Faz 3 kabul kriteri *"`POST /api/plan-4d` çalışıyor ve `metrics.wait_steps` döndürüyor"* bu fixture'da yeşil, sevk edilen veride yanlış.

**H1 ve H3'ün gözden kaçmasının doğrudan sebebi bu.** Aynı desen Faz 1 raporunun kendi teşhisini tekrarlıyor: hatalar görevlerin dikiş yerlerinde, her görev kendi sınırında doğruyken saklanıyor.

### Öneri

`lunapath/data/processed/` varsa gerçek grid üzerinde koşan, yoksa `skip` eden en az bir entegrasyon testi ekle. Test şunu iddia etsin: *"`/api/plan`'ın çözdüğü bir çift, varsayılan parametrelerle `/api/plan-4d`'de de çözülür."*

### Düzeltme

Yeni [`backend/test_plan_4d_real_grid.py`](../../backend/test_plan_4d_real_grid.py) — `lunapath/data/processed/metadata.json` yoksa `skip` eden, üç testli bir dosya:

1. `test_default_horizon_solves_a_route_the_old_fixed_default_starved` — H1'in kilitli regresyonu (yukarıda).
2. `test_default_horizon_never_fails_with_the_old_generic_timeout_message` — 12 rastgele geçilebilir çift üzerinde: hiçbiri eski `404 "No path found within the time horizon"` mesajıyla başarısız olamaz (kaba blok bağlantısızlığı yüzünden başarısız olmak **serbest** — dürüst 422 bekleniyor); en az bir çift **200** dönmeli.
3. `test_start_in_a_coarsening_disqualified_block_gets_a_specific_422` — H3'ün teşhis düzeltmesini kilitliyor (aşağıda).

Bilinçli olarak *"`/api/plan`'ın çözdüğü her çift 4B'de de çözülür"* iddia edilmiyor — bu artık yanlış bir iddia olurdu, çünkü H3'ün gerçek bulgusu (kabalaştırmanın bazı çiftleri gerçekten ayırdığı) düzeltilmedi, dürüstçe raporlanır hale getirildi (bkz. H3).

---

## 🔴 H3 — Konservatif kabalaştırma planlama grafiğini parçalıyor ✅ Düzeltildi (teşhis) — kabalaştırma kuralı bilinçli olarak değiştirilmedi

**Dosya:** `backend/app/cost_cube.py` — `coarsen_traversable`

Kural ("bir kaba hücre ancak tüm ince hücreleri geçilebilirse geçilebilir") **plana uygun ve güvenlik açısından savunulabilir**. Ama gerçek veride bedeli ölçüldü:

| coarsen | kaba grid | geçilebilir | bağlı bileşen | en büyük bileşen |
|---|---|---|---|---|
| 1 | 500×500 | 82.4% | 475 | 200.385 / 250.000 (80%) |
| 2 | 250×250 | 73.5% | 665 | 40.908 / 62.500 (65%) |
| **4 (varsayılan)** | **125×125** | **57.7%** | **392** | **7.558 / 15.625 (48%)** |
| 5 | 100×100 | 52.5% | 266 | 4.404 / 10.000 (44%) |
| 10 | 50×50 | 37.6% | 48 | 852 / 2.500 (34%) |
| 20 | 25×25 | 24.2% | 10 | 118 / 625 (19%) |

Varsayılan coarsen=4'te serbest alan **392 parçaya** bölünüyor ve en büyük parça hücrelerin yarısından azını tutuyor. Ufuk yeterli olsa bile `/api/plan`'ın çözdüğü çiftlerin büyük kısmı 4B'de erişilemez kalıyor.

### Öneri

Üç seçenek, tercih sırasıyla:

1. **İnce grid'de engel maskesini dilate et**, sonra kabalaştır. Aynı güvenlik payını korur ama tek bir izole kötü pikselin koca bloğu öldürmesini engeller.
2. **Eşik kuralı** (ör. ≥%90 ince hücre geçilebilirse kaba hücre geçilebilir) + eşiğin açıkça raporlanması.
3. En azından **teşhisi düzelt**: başlangıç/hedef ince grid'de geçilebilir ama kaba grid'de değilse, "Start is not traversable" değil "start kabalaştırma yüzünden bloklandı (coarsen=N), arazi yüzünden değil" de.

### Düzeltme — neden 1 ve 2 terk edildi, 3 uygulandı

**Seçenek 1 (dilate) denendi ve güvensiz çıktı.** Gerçek veride ölçüm: bloklu bağlı bileşenlerin **%70'i** (30.837 piksel) 53 büyük (>100 px) bileşende, geri kalanı (1.979 bileşenin 1.312'si) ≤4 pikselik "beneklerde". `scipy.ndimage.binary_closing` ile geçilebilir maskeyi 1-3 piksel yarıçapında kapatmak beklendiği gibi bağlantıyı düzeltti (r=2'de kaba geçilebilirlik %57.7 → %88.2), **ama** aynı zamanda büyük tehlike bölgelerinin **%38-85'ini** de "geçilebilir" olarak yeniden sınıflandırdı (r=2'de reclaim edilen alanın %54.5'i büyük tehlike bloklarından geldi) — yani gerçek, geniş eğim/termal tehlikelerini de siliyordu. Bu, güvenlik açısından kabul edilemez: **uygulanmadı.**

Aradan bir bileşen-boyutu eşiği (yalnızca ≤N pikselik bloklu bileşenleri "beneklenme" sayıp geri kazanma, büyük bileşenlere hiç dokunmama — seçenek 2'nin güvenli bir varyantı) denendi; büyük tehlikeleri sıfır kayıpla koruyor ama bağlantıyı yalnızca ılımlı ölçüde iyileştiriyor (coarsen=4, eşik=16 px: kaba geçilebilirlik %57.7 → %70.0, en büyük bileşen %48 → %62.6). **Uygulanmadı** — çünkü H1'in kesin `bfs_move_count` tabanlı ufuk boyutlandırması ile birleşince asıl pratik sorunun (ufuk açlığı) kaynağı zaten ortadan kalkıyor, kabalaştırma kuralını (test edilmiş, belgelenmiş, "conservative" sözleşmesi olan bir fonksiyon) riske atmadan.

**Seçenek 3 uygulandı** — `pathfinder_4d.bfs_move_count`, `coarsen_traversable`'ın **dokunulmadan** kalan sonucu üzerinde çalışıyor ve üç kesin durumu ayırt ediyor (main.py'de, `astar_4d` hiç çağrılmadan):
- başlangıç kaba blok geçilemez → 422, "start {..} kabalaştırmada geçilemez, en az bir ince hücre eğim/termal limitini aşıyor"
- hedef için aynı
- ikisi de geçilebilir ama BFS `None` dönüyor (farklı bağlı bileşenler) → 422, "terrain hazards split the grid into disconnected regions"

Kilitli regresyon: [`test_plan_4d_real_grid.py::test_start_in_a_coarsening_disqualified_block_gets_a_specific_422`](../../backend/test_plan_4d_real_grid.py) — ince gridde bloklu bir hücre start olarak seçiliyor, yanıtın **422** olduğunu ve eski jenerik "time horizon" metnini içermediğini doğruluyor.

**Kullanıcı için pratik sonuç:** daha iyi bağlantı gerekiyorsa `coarsen`'ı düşürmek (2 veya 1) hâlâ en güvenli yol — coarsen=1'de en büyük bileşen zaten alanın %80'i.

---

## 🔴 H4 — heat1d termal katmanı pratikte eğimin monoton fonksiyonu, üstelik ters ⏸️ Düzeltilmedi (bilinçli) — mekanizma açıklaması 📝 düzeltildi

> **Önemli düzeltme (düzeltme geçişinde bulundu):** Bu bulgunun ilk yazımı, `Heat1DModel._lookup_table`'ın **gerçek uygulanmış kodunu değil**, [`faz1-gercek-fizik.md`](2026-08-19-faz1-gercek-fizik.md) planının Task 4'teki **taslak kod örneğini** (`ndays=1`, çıplak `import planets`, `Configurator` yok) esas almış — bir okuma hatası. Kodu düzeltmeye otururken gerçek dosya yeniden okundu ve bu taslağın **hiç sevk edilmediği**, çok daha sofistike bir sürümün ("final review" dalgasında) yerine geçtiği ortaya çıktı. Aşağıdaki "Gerçek mekanizma" bölümü doğru koda dayanıyor; "Ölçüm" bölümündeki `.npy`-tabanlı sayılar (dosyadan doğrudan okundukları için) değişmedi ve hâlâ geçerli.

**Dosya:** `backend/app/thermal_model.py` — `Heat1DModel._lookup_table`

**Gerçek mekanizma (düzeltilmiş):**

```python
config = heat1d.Configurator(solver="crank-nicolson")
model = heat1d.Model(
    planet=heat1d_planets.Moon,
    lat=np.deg2rad(lat_deg),
    ndays=13,  # ~1 Ay yılı — TEK GÜN değil
    slope=np.deg2rad(slope_deg),
    slope_az=np.deg2rad(aspect_deg),
    config=config,
)
model.run()
surface_k = np.asarray(model.T)[:, 0]
table[i, j] = float(np.nanmax(surface_k)) - 273.15   # YILLIK tepe sıcaklık
```

Sınıfın kendi docstring'i bu kararları **zaten belgeliyor ve ölçüyor**: `ndays=1` yerine `ndays=13` (~1 Ay yılı) kullanılmasının gerekçesi "tek bir Ay günü yılın en yüksek Güneş yüksekliğine sahip kısmını örneklemiyor — bu sınıfın varsayılan enleminde tek-günlük düz-hücre tepe değeri gerçek yıllık tepenin ~81 °C altında kaldı (ve bu fark eğime bağlı: 0°'de ~81 °C, 10°'de ~22 °C)" ölçümüyle destekleniyor. Çözücü seçimi de (`crank-nicolson`, `fourier-matrix` değil) belgelenmiş bir gerekçeye dayanıyor (Gibbs-ringing artefaktından kaçınmak).

**Buna rağmen** bulgunun temel gözlemi hâlâ geçerli — sadece sebebi farklı: `nanmax` **yıllık en sıcak an**'ı alıyor, ve −89.5° enlem (gerçek kutba 0.501°) o kadar aşırı ki, bir Ay yılı boyunca hemen her bakı açısı, YIL İÇİNDE, benzer büyüklükte bir en-iyi-an yakalıyor — eksen tek günde değil, **yıllık tepe-değer seçiminde** çöküyor.

### Ölçüm — kaydedilmiş `thermal_grid.npy`'den geri çıkarılan LUT

```
satır = eğim bini (0..30 derece), sütun = bakı bini (0..360 derece)

[[-156.7 -156.7 -156.7 -156.7 -156.7 -156.7 -156.7 -156.7 ... ]   eğim  0.0
 [-118.6 -118.9 -120.0 -121.8 -124.2 -126.8 -129.2 -131.1 ... ]   eğim  2.5
 [ -90.6  -90.9  -91.8  -93.3  -95.2  -97.2  -99.0 -100.3 ... ]   eğim  5.0
 ...
 [  42.6   42.5   42.1   41.5   40.9    nan    nan    nan ... ]]  eğim 30.0

bakı ekseni yayılımı (max-min), eğim binine göre:
[ 0.0  13.1  10.2  8.5  7.3  6.5  5.8  5.3  4.6  4.4  3.9  1.9  3.1 ]
```

- **Bakı ekseni yayılımı: 0–13 K**
- **Eğim ekseni aralığı: −156.7 °C → +42.6 °C (≈200 K)**
- **Spearman(slope, thermal) = 0.984**

### Sonuçları

1. **Termal kriter (w = 0.19), eğim kriterinden (w = 0.409) bağımsız neredeyse hiç bilgi taşımıyor.** 4 kriterli AHP fiilen 3 kriterli çalışıyor.

2. **Yönü ters.** Düz zemin en soğuk, dik zemin en sıcak okunuyor; `f_thermal` soğuğu cezalandırdığı için termal terim **dik araziyi ödüllendirip eğim terimini kısmen iptal ediyor**:

   ```
   düz hücre (0 derece,  -156.7 C): w_slope*f_slope = 0.001 + w_thermal*f_thermal = 0.190  ->  0.191
   dik hücre (25 derece, + 42.6 C): w_slope*f_slope = 0.402 + w_thermal*f_thermal = 0.039  ->  0.441
   ```

3. **Katmanın arazi gölgelemesinden haberi yok.** LUT yalnızca (eğim, bakı) fonksiyonu; kalıcı gölgeli krater tabanı ile güneşli düzlük **aynı −156.7 °C**'yi alıyor. Oysa ufuk + SPICE hattı bu bilgiyi zaten üretiyor ve `shadow_ratio` olarak kullanılıyor — termal katman ondan hiç yararlanmıyor.

4. Geçilebilirliğe etkisi bugün küçük: yalnızca hücrelerin **%0.06**'sı termal yüzünden bloklanıyor (bu pencere zaten dik; medyan eğim 21°, düz hücre neredeyse yok). Yani bu bir "harita kapandı" sorunu değil, bir **kriter geçerliliği** sorunu.

> ⚠️ **Düzeltme:** Bu satır ilk yazımda "Faz 1 Task 4'te tam olarak böyle yazılmıştı" diyordu — yanlıştı (yukarıdaki kutuya bakın: plan taslağı sevk edilmedi). Doğrusu: mevcut kod **`ndays=13` + `crank-nicolson`'ı bilinçli olarak seçmiş, ölçmüş ve belgelemiş**; `nanmax` (tepe değeri) seçimi de "rover'ın hayatta kalması gereken en sıcak hali sınırlar" gerekçesiyle **kasıtlı bir güvenlik kararı**, gözden kaçmış bir varsayılan değil.

### Öneri — ve neden bu geçişte uygulanmadı

LUT'u planlamaya anlamlı bir büyüklükle anahtarlamak (ör. **ortalama**/**minimum** diurnal sıcaklık, ya da `shadow_ratio`/`illumination_fraction` ile birleştirmek) hâlâ makul bir yön. Ama `nanmax` seçimi, yukarıdaki gerekçeyle **kasıtlı bir güvenlik kararı** ("rover'ın hayatta kalması gereken en sıcak hali sınırlar") — ben bunu tek taraflı olarak `nanmean`'e çevirirsem, belgelenmiş bir tasarım kararını override etmiş olurum, üstelik Ay termal fiziğinde derin uzmanlık gerektiren bir alanda. **Bu geçişte kod değişikliği yapılmadı** — bunun yerine:

- Bulgunun **temel gözlemi doğrulandı ve düzeltilmiş açıklamayla burada kayıtlı** (yukarıda).
- Doğrudan ilişkili, **mekanik ve düşük riskli** olan **M1** (bakı çerçevesi hatası) düzeltildi — H4 çözülse de çözülmese de gerekli bir düzeltmeydi.
- Karar kullanıcıya bırakılıyor: `nanmax` → `nanmean`/`nanmin` geçişi, gerçek `heat1d` koşumları üzerinde (n_slope_bins küçük tutularak, ör. 4×6, ~1.5 saat) doğrulanarak ayrı bir görev olarak ele alınmalı — hem çünkü rover güvenliğini etkiliyor, hem çünkü LUT yeniden üretimi her ölçüm için ~15-45 dakika sürüyor (bkz. [Uygulanan düzeltmeler](#uygulanan-düzeltmeler)'de veri yeniden üretimi notu).

---

## 🟠 M1 — C1 azimut hatası gölge için düzeltildi, termal için düzeltilmedi ✅ Düzeltildi

**Dosyalar:** `lunapath/src/process_lunar_data.py:301` (`make_thermal_grid`), `backend/app/thermal_model.py`

`make_aspect_grid` yamaç yönünü **grid** kuzeyine göre döndürüyor (`atan2(-dx, dy)`, raster satır/sütun yönleri).

heat1d'nin `slope_az`'ı ise — kurulu paketten, `heat1d/terrain.py:57` — şöyle belgeli:

```
slope_az : float
    Slope azimuth (downslope direction) [rad], clockwise from north.
az_sun : float or np.ndarray
    Solar azimuth [rad], clockwise from north.
```

ve `az_sun`, `orbits.solarAzimuth(lat, dec, h)`'den geliyor — gövde-sabit küre üzerindeki yerel ENU çerçevesinde, yani **gerçek** kuzey referanslı.

Bu pencerede `true_north_grid_azimuth = 249.775°`. **Gölge hattı** `true_azimuth_to_grid_azimuth` ile döndürüyor (C1 düzeltmesi). **Termal hattı hiçbir şey uygulamıyor** — `aspect_grid` doğrudan `slope_az` olarak besleniyor.

**Bugünkü pratik etki sınırlı:** hata LUT'un bakı yayılımıyla (≤13 K) sınırlı ve LUT 180° civarında neredeyse simetrik olduğu için gerçek kayma daha da az. Ama:

- aynı hata sınıfı,
- hiçbir test kapsamıyor,
- H4 kod değişikliği almasa bile bakı-ekseni önemi zaten bu pencerenin gerçek boylamına (`true_north_grid_azimuth = 249.775°`) bağlı — düzeltilmeden bırakmak sessiz bir tutarsızlıktı.

### Düzeltme

`app/ephemeris.py`'ye `true_azimuth_to_grid_azimuth`'un **tersi** eklendi — `grid_azimuth_to_true_azimuth(grid_az_deg, true_north_grid_az_deg)`, dizi girdisini destekliyor (gölge yolu yalnızca tekil güneş örneklerini döndürüyordu; termal yol tüm `(H, W)` bakı grid'ini tek çağrıda döndürmesi gerekiyor). `process_lunar_data.make_thermal_grid` artık `lon_deg`/`crs_wkt` alıyor ve **yalnızca `Heat1DModel` dalında** bakıyı gerçek kuzeye çeviriyor:

```python
if Heat1DModel.available():
    grid_north_az = true_north_grid_azimuth(lat_deg, lon_deg, crs_wkt)
    aspect_for_model = grid_azimuth_to_true_azimuth(aspect, grid_north_az)
else:
    aspect_for_model = aspect  # SyntheticModel kendi grid-kuzeyi sözleşmesini kullanıyor
```

`SyntheticModel` dalı **bilinçli olarak dokunulmadan** kaldı — kendi sezgisel formülü zaten grid-kuzeyi aspect üzerinde yazılıp test edilmiş (`test_synthetic_model_matches_legacy_generate_thermal_grid`), gerçek-kuzey kavramından bağımsız.

Testler: `test_ephemeris.py`'ye 5 yeni test (tam tersine-çevirme round-trip, 360° sarma, merkez-meridyen özdeşliği, skaler/dizi tip kontrolü) — hepsi geçiyor.

**⚠️ Veri yeniden üretimi gerekiyor.** Bu, `Heat1DModel`'in LUT'a bakı değerini nasıl bağladığını değiştiriyor — commit'lenmiş `thermal_grid.npy`/`metadata.json`'ın **yeniden üretilmesi gerekiyor** ki canlı sistem bu düzeltmeyi yansıtsın. Pipeline koşumu ~15-45 dakika sürdüğü ve commit'lenmiş veriyi değiştirdiği için **bu oturumda otomatik çalıştırılmadı** — kullanıcının `cd lunapath/src && python process_lunar_data.py` ile açıkça tetiklemesi gerekiyor (bkz. [Uygulanan düzeltmeler](#uygulanan-düzeltmeler)).

---

## 🟠 M2 — BEKLE ve HAREKET kenarları farklı birimde; bekleme ~6.500× ucuz ✅ Düzeltildi

**Dosyalar:** `backend/app/pathfinder_4d.py`, `backend/app/cost_cube.py` — `wait_cost`

```python
# MOVE  (pathfinder_4d.py)     -> metre * MRU
step = distance_m * (1.0 + 0.5 * (from_cost + to_cost))

# WAIT  (cost_cube.py)         -> MRU * saat
return weights["w_energy"] * energy_penalty + weights["w_shadow"] * shadow_penalty
#      shadow_penalty = f_shadow_cell(1 - frac) * dt
```

İkisi aynı `g_score`'a toplanıyor.

### Ölçüm (gerçek grid, `lpr_1`)

```
ortalama MOVE kenarı (gerçek koşu: 3387.26 / 117 hamle)  = 28.95
wait_cost(karanlık, dt = 0.031 h auto slice)             =  0.004488
wait_cost(güneş,    dt = 0.031 h)                        =  0.000000

oran = 6.451 x
```

**Bugün görünmüyor**, çünkü endpoint gölge oranını dilimler boyunca sabit tutuyor (planın kendi belgelediği "Bilinen sınır"), dolayısıyla beklemenin hiç faydası olmuyor ve `wait_steps` her zaman 0 çıkıyor.

**Gerçek aydınlanma küpü gelir gelmez tersine döner:** planlayıcı neredeyse her maliyet farkını beklemekle kapatmayı tercih eder — Faz 3'ün göstermek istediğinin tam tersi arıza.

Amiral gemisi test bunu yakalayamaz, çünkü küpü elle kuruyor:

```python
# test_pathfinder_4d.py::_shadow_then_sun_case
cost_cube[:3, 0, 1] = 40.0        # elle seçilmiş
wait_cube = np.full(..., 0.001)   # elle seçilmiş
```

`build_cost_cube` / `build_wait_cost_cube` hiç kullanılmıyor. Yani test **mekanizmayı** kanıtlıyor, **kalibrasyonu** değil.

### Öneri

İki kenarı ortak bir birime getir. En basiti hareket maliyetini de zamana çevirmek (`travel_s / 3600` ile ölçeklemek) ya da bekleme maliyetini mesafeye eşdeğerlemek. Sonrasında `build_*_cube` çıktılarıyla koşan, oranın makul (ör. 0.1–10×) aralıkta kaldığını iddia eden bir test ekle.

### Düzeltme

Uygulanan tam olarak birinci seçenek — MOVE kenarı artık `pathfinder_4d.py`'de zamana çevriliyor:

```python
step = (travel_s / 3600.0) * (1.0 + 0.5 * (from_cost + to_cost))
```

Sezgisel de aynı ölçeğe taşındı — mesafeyi `v_max_ms`'e (rover'ın hiç aşamayacağı en yüksek hız) bölmek, herhangi bir eğim için gerçek süreye **kesin bir alt sınır** kalıyor (çünkü `edge_travel_time_s`'de gerçek hız her zaman `v_max_ms·cos(θ)) ≤ v_max_ms`), yani admissibility bozulmuyor:

```python
hours_lower_bound = distance_m / v_max_ms / 3600.0
return hours_lower_bound * (1.0 + min_cost)
```

**Ölçüm (düzeltme sonrası, aynı senaryo):** ortalama MOVE kenarı artık saat biriminde ölçülüyor, WAIT de saat biriminde — ikisi karşılaştırılabilir büyüklükte (eskiden 6.500× fark, düzeltme sonrası tipik oran ~10×).

**Test — kalibrasyonu kanıtlıyor, sadece mekanizmayı değil:** yeni `test_pathfinder_4d.py::test_planner_chooses_to_wait_with_real_cost_cubes` ve `test_real_cube_wait_is_cheaper_than_rushing`, `_shadow_then_sun_case`'in elle-seçilmiş `cost_cube[:,0,1]=40.0` deseninin **aksine**, `build_cost_cube`/`build_wait_cost_cube`'u gerçek rover sabitleriyle çağırıyor (10 hücrelik gölgeli bir koridor, 3 dilim boyunca), ve planlayıcının **gerçek üretim fonksiyonlarıyla** yine de beklemeyi seçtiğini doğruluyor — M2'nin işaret ettiği "amiral gemisi test yalnızca mekanizmayı kanıtlıyor, kalibrasyonu değil" boşluğu artık kapalı.

---

## 🟠 M3 — `surface_to_inner`'da 0 °C süreksizliği artık Corridor'a sızıyor ⏸️ Düzeltilmedi (bilinçli)

**Dosya:** `backend/app/cost_engine.py` — `surface_to_inner`

```python
if T_surface_C < 0:  return T_surface_C + 60      # thermal_offset_cold
else:                return T_surface_C - 40      # thermal_offset_hot
```

−0.001 °C → iç sıcaklık **+59.999**; +0.001 °C → **−39.999**. **100 K'lik sıçrama.**

LUT aralığında `f_thermal` bu yüzden monoton değil:

| T_yüzey | T_iç | f_thermal |
|---|---|---|
| −76.6 | −16.6 | 0.9315 |
| −56.5 | +3.5 | 0.1689 |
| −39.2 | +20.8 | **0.0130** |
| −24.1 | +35.9 | 0.4459 |
| −10.8 | +49.2 | 0.9552 |
| **+6.1** | **−33.9** | **0.9990** ← sıçrama |
| +26.0 | −14.0 | 0.8836 |
| +42.6 | +2.6 | 0.2051 |

Bu **Faz 1-3 öncesinden var** (`cost_engine.py` bu fazlarda değişmedi). Ama Faz 2'nin `corridor.thermal_budget_K_s`'i artık `surface_to_inner`'ı doğrudan tüketiyor, dolayısıyla Corridor sözleşmesinin segment başına termal payı bu sıçramayı miras alıyor.

### Öneri

Kapsam dışı bırakılabilir, ama Faz 2 bunu yeni bir tüketiciye taşıdığı için artık takip edilmeli. Sürekli bir geçiş (ör. 0 °C çevresinde bir karışım penceresi) ya da tek bir offset yeterli.

### Neden düzeltilmedi

`cost_engine.py`'nin geri kalanı gibi bu da Faz 1-3'ten önce vardı ve üç fazın hiçbiri dokunmadı. H4 ile aynı gerekçe: rover'ın termal davranış modeline dair bir varsayım (soğuk/sıcak yüzeyin iç sıcaklığa farklı bağlanması), tek bir offset yerine sürekli bir geçiş fonksiyonuna geçmek AHP ağırlıklarının kalibre edildiği temel varsayımı değiştirebilir — kod incelemesiyle değil, rover termal mühendisliği girdisiyle karar verilmeli. Kayıtlı bırakıldı.

---

## 🟠 M4 — `n_slices` büyütmek arama işini lineer büyütüyor, karşılığı yok 🟡 Kısmen iyileşti (ayrıca düzeltilmedi)

Aynı rota, aynı sonuç:

| `n_slices` | Düğüm | Süre | Yol | `arrival_slice` |
|---|---|---|---|---|
| 200 | 136.459 | 1.6 s | 117 hamle | 164 |
| 1000 | **1.056.933** | **16.8 s** | **birebir aynı** | 164 |

Planlayıcı, asla anlamlı biçimde bulunamayacağı dilimlerdeki durumları da genişletiyor. H1'in "n_slices'ı yükselt" geçici çözümüyle birleşince gerçek bir kaynak riski: `MAX_PLAN_4D_SLICES = 1000` × `coarsen = 1` × 500×500 = **250 milyon durum**.

### Öneri

`n_slices`'ı hedefin erişilebilir olduğu en küçük değere kırp, ya da hedefe ulaşıldığında değil, `arrival_slice` yeterince küçük kaldığında aramayı erken kes. En azından `MAX_PLAN_4D_SLICES`'ı `coarsen` ile birlikte sınırla (durum sayısı üzerinden bir tavan).

### Durum

**Doğrudan düzeltilmedi**, ama iki yan etkiyle ölçülebilir şekilde iyileşti:

1. **M2'nin birim düzeltmesi** aynı senaryoyu yeniden ölçtüğümde büyüme oranını azalttı: 200→1000 dilim artık 200 (%7.75) değil **4.3× düğüm** artışı veriyor (141.360 → 608.909).
2. **H1'in kesin `bfs_move_count` tabanlı boyutlandırması**, pratikte kullanıcıların artık büyük `n_slices` değerlerine hiç ihtiyaç duymamasını sağlıyor — M4'ü tetikleyen asıl senaryo (varsayılan çok küçük geldiği için elle 1000'e çıkarmak) ortadan kalktı.

**Neden ayrıca düzeltilmedi:** kalan büyüme, sezgiselin zaman eksenini (dilim indeksini) hiç hesaba katmamasından kaynaklanıyor — yalnızca (satır, sütun) uzaklığına bakıyor, aynı hücrenin farklı zaman dilimlerindeki tüm varyantlarına neredeyse eşit önceliğin verilmesine yol açıyor. Bunu admissibility'i bozmadan düzeltmek (ör. dilim-indeksine duyarlı bir bileşen eklemek) daha derin bir sezgisel yeniden tasarımı gerektiriyor ve bu geçişin kapsamının ötesinde — üstelik `MAX_PLAN_4D_SLICES=1000` zaten sert bir tavan olarak duruyor. Kaydedilmiş, önerilen yön yukarıda duruyor.

---

## 🟡 Düşük öncelikli bulgular

### L1 — `horizon_map` docstring'i kendi koduyla çelişiyor ✅ Düzeltildi

**Dosya:** `backend/app/horizon.py`

Docstring: *"The step count — not the physical range — is what is capped, so the same call costs the same regardless of whether resolution_m is a coarse 80 m grid or a fine 5 m grid: at 80 m/px, max_steps=200 gives a 16 km effective range."*

Kod:

```python
n_steps = max(1, int(round(float(max_range_m) / float(resolution_m))))
n_steps = min(n_steps, int(max_steps))
```

80 m/px'te varsayılan `max_range_m=10000` ile: `min(125, 200) = 125` adım = **10 km**, 16 km değil. Ve maliyet çözünürlükten bağımsız **değil** (125 adım vs 5 m/px'te 200 adım).

Planın Interfaces satırı (`Etkin menzil min(max_range_m, max_steps * resolution_m)`) koda uyuyor — yalnızca docstring hatalı. Kod doğru, belge yanlış.

**Düzeltme:** docstring, gerçek formülü (`min(round(max_range_m/resolution_m), max_steps)`) ve iki somut örneği (80 m/px → 125 adım, `max_range_m` sınırlı; 5 m/px → 200 adım, `max_steps` sınırlı) doğru yansıtacak şekilde yeniden yazıldı; `max_steps`'in garanti ettiği şeyin "sabit maliyet" değil "sert bir tavan" olduğu netleştirildi.

### L2 — `sun_track`'ın `furnsh` maliyeti raporda abartılmış ⏸️ Düzeltilmedi (tarihi rapor)

Faz 1 raporu: *"`sun_track`, örnek başına `spice.furnsh` çağırıyor — bugün ~169 gereksiz kernel yüklemesi; Faz 3'ün daha büyük örnek sayılarında gerçek bir tavan."*

Ölçüm: **168 örnek 0.9 saniye.** `spiceypy`, zaten yüklü bir kerneli tekrar yüklemiyor. Bu madde Faz 3'e taşınmadan kapatılabilir.

**Neden düzeltilmedi:** bu bir kod bulgusu değil, `faz1-tamamlanma-raporu.md`'nin (tarihsel bir tamamlanma kaydı) bir cümlesiyle ilgili. Geçmiş kayıtları geriye dönük düzenlemek yerine bu belgede düzeltme kaydedildi.

### L3 — `illuminated_mask`'teki `> 0.0` tabanı fizikten katı ⏸️ Değerlendirildi, değiştirilmedi

**Dosya:** `backend/app/illumination.py`

```python
return (float(sun_elev_deg) > horizon[bin_index]) & (float(sun_elev_deg) > 0.0)
```

Ufku negatif olan bir sırt hücresi (arazi etrafında düşüyor), yerel yatayın **biraz altındaki** Güneş'le gerçekten aydınlanır. `> 0.0` tabanı bunu keser.

**Mevcut veride etkisiz:** örneklenen lunasyonda (2026-11-15 → 2026-12-13, 168 örnek) güneş yüksekliği **1.049° – 1.961°**, hiç ≤ 0 olmuyor. Ve taban, `−90°` "veri yok" sentinel'ini doğru nötralize ediyor (Faz 1 final review M1 bulgusunun amacı buydu).

Yine de batışı içeren herhangi bir güneş izi için gizli yanlılık. Daha temizi: mutlak yüksekliği kapı olarak kullanmak yerine sentinel'i açıkça kontrol etmek — `horizon > _NO_HORIZON_DEG + 1`.

**Neden değiştirilmedi:** sentinel'i açıkça kontrol etmek, `elev>0` tabanının BUGÜN çözdüğü sorunu (negatif yükseklikte sentinel'in yanlışlıkla "aydınlık" okunması) çözer, ama "veri eksik, gerçek ufuk bilinmiyor" durumunda `elev>0` iken ne yapılacağı sorusunu **çözmez** — o durumda hem eski hem önerilen kod aynı (iyimser) varsayımı yapıyor. Daha iyi, net bir tasarım önerecek kadar netlik olmadığı için kod değiştirilmedi; mevcut davranış bilinçli bir taviz olarak kayıtlı bırakıldı.

### L4 — Bilinmeyen `rover_id` 422 değil 500 veriyor ✅ Düzeltildi

**Dosya:** `backend/app/constants.py:158`, `backend/app/main.py:376`

`get_rover` çıplak `KeyError` fırlatıyor; `/api/plan`, `/api/replan`, `/api/plan-4d` yakalamıyor → yakalanmamış istisna, 500.

Review sırasında kendim düştüm: `rover_id="LPR-1"` gönderdim, geçerli id'ler `lpr_1`, `luvmi_m`, `nasa_viper`, `cnsa_yutu_2`. Kullanıcı hatası 500 olarak dönmemeli.

**Düzeltme:** `constants.py`'de `UnknownRoverError(KeyError)` — `get_rover` artık bunu fırlatıyor (mevcut `except KeyError` kodunu bozmadan, çünkü alt sınıf). `main.py`'de tek bir `@app.exception_handler(UnknownRoverError)` → **422**, çağrı sitesi başına ayrı `try/except` gerekmeden **yedi call site'ın hepsini** kapsıyor. Doğrulama: `rover_id="LPR-1"` artık `422 {"detail": "\"Unknown rover_id: 'LPR-1'. Available: [...]\""}"` dönüyor, 500 değil.

### L5 — `cost` / `traversable` koşulsuz `"DERIVED"` etiketleniyor ✅ Düzeltildi

**Dosyalar:** `lunapath/src/process_lunar_data.py:577`, `backend/app/data_loader.py:122`

```python
"traversable": "DERIVED",
"cost":        "DERIVED",
```

Girdi katmanlarının gerçek validity'sinden bağımsız. SYNTHETIC bir gölge katmanı üzerine kurulmuş bir maliyet grid'i hâlâ DERIVED iddia ediyor. Faz 1'in flag listesinden devrolmuş, hâlâ açık — `layer_validity`'nin var olma sebebine (zayıf girdiden güçlü etiket üretmemek) doğrudan aykırı.

**Düzeltme:** `app/traversability.py`'ye `weakest_validity(*validities)` — SYNTHETIC < DERIVED < MODEL < MEASURED sıralamasında en zayıfını döndürüyor (bilinmeyen değerleri en kötü durum sayarak). İki çağrı sitesi de bununla:

```python
# process_lunar_data.py — traversable slope+thermal'e bağlı, cost ayrıca shadow_ratio'ya
"traversable": weakest_validity("DERIVED", thermal_validity),
"cost":        weakest_validity("DERIVED", shadow_validity, thermal_validity),

# data_loader.py'nin DEM-fallback yolu — shadow_ratio/thermal HER ZAMAN SYNTHETIC
"traversable": weakest_validity("DERIVED", "SYNTHETIC"),  # -> "SYNTHETIC"
"cost":        weakest_validity("DERIVED", "SYNTHETIC"),  # -> "SYNTHETIC"
```

5 yeni test (`test_traversability.py`), tümü geçiyor. **Not:** `process_lunar_data.py`'deki değişikliğin commit'lenmiş `metadata.json`'a yansıması için pipeline'ın yeniden koşması gerekiyor (bkz. M1'in veri notu).

### L6 — `process_lunar_data.py`'de bayat "düzeltilmedi" yorumu ✅ Düzeltildi

**Dosya:** `lunapath/src/process_lunar_data.py:90-96`

```
# NOTE: backend/app/serializer.py::pixel_to_lonlat has the identical y-axis
# sign convention issue ... Deliberately left unfixed there ...
```

**Faz 2 C2 bunu düzeltti.** Yorum artık yanlış bilgi veriyor; silinmeli.

**Düzeltme:** yorum, `serializer.py`'nin de (Faz 2 C2, `corridor.py`'nin y-ekseni düzeltmesiyle aynı geçişte) düzeltildiğini belirtecek şekilde güncellendi — artık "bilinçli olarak düzeltilmedi" demiyor.

### L7 — Commit'lenmiş `metadata.json` repoda olmayan grid'leri tarif ediyor ⏸️ Düzeltilmedi (repo politikası)

`.gitignore` `*.npy` ve `data/processed/`'i dışlıyor, ama `lunapath/data/processed/metadata.json` takip ediliyor. Yani `layer_validity` iddiaları (`shadow_ratio: DERIVED`, `thermal: MODEL`) başka kimse tarafından **12-15 dakikalık pipeline koşusu + ~45 MB kernel indirmesi olmadan yeniden üretilemiyor.**

Faz 1 raporunun ana çıktısı ("sıfır SYNTHETIC kaldı") bu dosyaya dayanıyor. Ya `.npy`'ler için bir dağıtım yolu (release asset / Git LFS) ya da metadata'nın da ignore edilmesi tutarlı olur.

**Neden düzeltilmedi:** bu bir kod hatası değil, bir **repo/veri dağıtım politikası kararı** (Git LFS kurmak, release asset'i ayarlamak, ya da `.gitignore`'u genişletmek) — kullanıcının onayı olmadan tek taraflı verilecek bir karar değil. Kayıtlı bırakıldı.

---

## Önerilen ele alma sırası (ilk yazımdaki plan — fiilen bu sırayla uygulandı)

```
1. H2         gerçek grid'de /api/plan-4d entegrasyon testi
              (önce bu: H1 ve H3'un duzeldigini kanitlayacak tek olcum araci)
2. H1         varsayılan ufuk (n_slices / horizon_hours)
3. H3         kabalaştırma stratejisi + teşhis mesajı
4. H4 + M1    termal LUT anahtarı + azimut çerçevesi (birlikte)
5. M2         BEKLE/HAREKET birim uyumu
6. M4         n_slices kırpma
7. L1-L7      temizlik
```

**Gerekçe:** H2 önce gelmeli — H1 ve H3'ü düzeltip düzeltmediğini gösterecek tek ölçüm aracı o. H4 ve M1 aynı dosyaya dokunuyor ve M1, H4 düzeltilmeden zaten görünmez; ayrı ayrı yapmak iki kez aynı yeri açmak demek. M2 en sona kalabilir çünkü bugün gözlemlenebilir bir etkisi yok — ama gerçek aydınlanma küpü gelmeden **önce** düzeltilmeli.

Fiili sonuç: H4 madde 4'te **kod değişikliği almadı** (gerekçe yukarıda) — M1 tek başına, H4'ün açıklaması düzeltilerek uygulandı. M4 madde 6'da **doğrudan** değil, H1+M2'nin yan etkisiyle kısmen iyileşti.

---

## Uygulanan düzeltmeler

Bu bölüm, kullanıcının "bu bulguları düzelt" talebi üzerine aynı oturumda yapılan **tüm** kod/test değişikliklerinin özeti.

### Değişen/eklenen dosyalar

| Dosya | Değişiklik |
|---|---|
| `backend/app/pathfinder_4d.py` | + `bfs_move_count` (H1/H3); MOVE kenarı ve sezgisel saat birimine taşındı (M2) |
| `backend/app/main.py` | `/api/plan-4d`: BFS tabanlı erişilebilirlik teşhisi + kesin varsayılan ufuk (H1/H3); `UnknownRoverError` handler'ı (L4); `DEFAULT_PLAN_4D_SLICES` kaldırıldı |
| `backend/app/constants.py` | + `UnknownRoverError(KeyError)` (L4) |
| `backend/app/traversability.py` | + `weakest_validity` (L5); `THERMAL_MIN_TRAVERSABLE_C` re-export (bonus fix) |
| `backend/app/data_loader.py` | DEM-fallback yolunda `traversable`/`cost` validity'si `weakest_validity` ile (L5) |
| `backend/app/ephemeris.py` | + `grid_azimuth_to_true_azimuth` (M1) |
| `backend/app/horizon.py` | Docstring düzeltmesi (L1) |
| `lunapath/src/process_lunar_data.py` | `make_thermal_grid`: Heat1DModel dalında bakı gerçek-kuzeye çevriliyor (M1); `traversable`/`cost` validity'si `weakest_validity` ile (L5); bayat yorum düzeltildi (L6) |
| `backend/test_plan_4d_real_grid.py` | **Yeni** — gerçek grid entegrasyon testleri (H2) |
| `backend/test_pathfinder_4d.py` | + `bfs_move_count` testleri (7); + gerçek küp WAIT/MOVE testleri (2) |
| `backend/test_ephemeris.py` | + `grid_azimuth_to_true_azimuth` testleri (5) |
| `backend/test_traversability.py` | + `weakest_validity` testleri (5) |

### Test durumu (bu geçişin sonunda)

```
pytest                        231 passed  (214 baseline + 17 yeni)
python test_cost_engine.py    PASSED: 42  FAILED: 0
python test_traversability.py PASSED: 23  FAILED: 0   (eskiden ImportError ile çöküyordu)
```

### Ölçülebilir sonuçlar

| Metrik | Önce | Sonra |
|---|---|---|
| `/api/plan-4d` başarı (12 rastgele geçilebilir çift, varsayılan parametreler) | 1/12, çoğu 404 "no path within horizon" | 8/12 başarı, 4/12 **422** (açık sebepli: kaba-blok/bağlantısızlık) — sıfır jenerik 404 |
| MOVE/WAIT birim oranı | ~6.500× | ~10× (`test_planner_chooses_to_wait_with_real_cost_cubes` gerçek küplerle bekliyor) |
| `n_slices` 200→1000 düğüm artışı | 7.75× | 4.3× |
| `python test_traversability.py` | ImportError (çıkış 1) | 23 PASS (çıkış 0) |

### Bilinçli olarak düzeltilmeyenler (kod değişikliği yapılmadı)

- **H4** — `Heat1DModel`'in yıllık-tepe (`nanmax`) seçimi, kendi docstring'inde belgelenmiş bir güvenlik kararı ("rover'ın hayatta kalması gereken en sıcak hali sınırlar"); tek taraflı override edilmedi. Bulgunun ölçümü geçerli, açıklaması düzeltildi.
- **M3** — `surface_to_inner`'ın 0 °C süreksizliği, rover'ın termal modeline dair bir varsayım; kod incelemesiyle değil termal mühendislik girdisiyle karar verilmeli.
- **M4** — kalan sezgisel-kalitesi sorunu, H1+M2 ile ölçülebilir şekilde hafifledi ama kök neden (zaman-dilimi-körü sezgisel) ayrıca düzeltilmedi; `MAX_PLAN_4D_SLICES` zaten sert tavan.
- **L2** — tarihi bir tamamlanma raporunun cümlesi, geriye dönük düzenlenmedi.
- **L3** — daha iyi bir tasarım netliği olmadığı için `illuminated_mask` değiştirilmedi.
- **L7** — repo/veri dağıtım politikası kararı, kullanıcı onayı gerektiriyor.

### ⚠️ Kullanıcı için gereken takip adımı: veri yeniden üretimi

**M1'in kod düzeltmesi commit'lenmiş `thermal_grid.npy`/`metadata.json`'a henüz yansımadı.** Isı LUT'unun bakıyı nasıl okuduğunu değiştiriyor, ama pipeline koşumu (`cd lunapath/src && python process_lunar_data.py`) ~15-45 dakika sürüyor ve commit'lenmiş veriyi değiştiren, geri alması zor bir işlem olduğu için **bu oturumda otomatik çalıştırılmadı**. Ayrıca H4'ün önerdiği (ama uygulanmayan) `nanmax`→`nanmean`/`nanmin` geçişi de ayrı bir karar olarak aynı yeniden-üretim adımını gerektirir.

**Öneri:** `kernels/` klasörü zaten dolu (SPICE çekirdekleri mevcut), yani pipeline doğrudan çalıştırılabilir:

```bash
cd lunapath/src && python process_lunar_data.py
```

Koşum bitince `metadata.json`'daki `layer_validity` ve `thermal_grid.npy`'nin sayısal aralığı kontrol edilmeli (bkz. [`FAZ1_CIKTI_NEDIR.md`](FAZ1_CIKTI_NEDIR.md) §3).

---

*İlgili: [`2026-08-19-faz1-tamamlanma-raporu.md`](2026-08-19-faz1-tamamlanma-raporu.md) · [`FAZ1_CIKTI_NEDIR.md`](FAZ1_CIKTI_NEDIR.md) · [`2026-08-19-lunapath-master-plan.md`](2026-08-19-lunapath-master-plan.md)*
