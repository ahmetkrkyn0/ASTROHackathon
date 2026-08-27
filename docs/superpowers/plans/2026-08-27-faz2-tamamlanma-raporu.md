# Faz 2 Tamamlanma Raporu

**Tarih:** 27 Ağustos 2026
**Branch:** `backend/physics` (fork noktası: `3b91162`)
**Plan:** [`2026-08-19-faz2-maliyet-mimarisi.md`](2026-08-19-faz2-maliyet-mimarisi.md)
**Master plan:** [`2026-08-19-lunapath-master-plan.md`](2026-08-19-lunapath-master-plan.md)
**Commit aralığı:** `3b91162..926fcff` (6 commit)
**Remote:** GitLab `seng2026/ASTROHackathon`, `backend/physics` branch'ine push edildi

---

## Özet

Faz 2'nin **altı görevi de plana sadık biçimde uygulandı ve commit'lendi.** Son test durumu: **145 pytest passed, 0 skipped** + `test_cost_engine.py` 42/42.

Ancak bu rapor bir "tamamlandı, sorunsuz" raporu **değil.** Kod yazımı bittikten sonra yapılan whole-branch review'da **2 Kritik + 2 Önemli + 1 Minör bulgu** çıktı; bunların ikisi Faz 2'nin bizzat yarattığı **regresyon.** Hiçbiri henüz düzeltilmedi — kullanıcı kararı bekliyor.

> **Faz 1 ile en önemli fark:** Faz 1'in kritik hataları final review'da bulunup **aynı fazda düzeltildi ve gerçek veriyle doğrulandı.** Faz 2'de bulgular tespit edildi ama düzeltme yapılmadı. Bu faz bu hâliyle "yeşil test" gösteriyor ama **iki canlı hata taşıyor.**

---

## Uygulanan görevler

| Görev | Ne | Commit | Test |
|---|---|---|---|
| 1 | `costmap.py` — `PlanContext`, `CostLayer`, `CostMap`, `explain()` | `cd1cdc9` | 8 |
| 2 | Dört AHP kriteri `CostLayer`'a taşındı | `31b0c1d` | +4 (12) |
| 3 | `/api/cell-telemetry` → `cost_breakdown` + `layer_validity` | `bb24cd9` | 3 |
| 4 | `schemas.py` + `corridor.py` — `Corridor` sözleşmesi | `da6c0f5` | 10 |
| 5 | `/api/plan` → `corridor` alanı | `42eb9e0` | 3 |
| 6 | `replan_triggers.py` (6 tetikleyici) + `/api/replan` | `926fcff` | 12 |

**Toplam yeni test:** 40. **Toplam suite:** 105 → 145.

### En güçlü nokta: eşitlik testi

Task 2'nin merkezi güvenlik ağı çalıştı. `default_cost_map(...).total()`, eski `compute_cost_grid()` ile **1e-9 mutlak toleransta bit-yakın aynı** çıkıyor — hem varsayılan ağırlıklarda hem override'lı ağırlıklarda, hem sonlu hem `inf` hücrelerde. Refaktör kanıtlanabilir şekilde davranış-koruyucu. `inf` yayılımı da ayrıca doğrulandı: 25°'yi aşan eğimde legacy ve layered yol aynı hücrelerde `inf` üretiyor.

---

## Final review bulguları — 5 adet, hiçbiri düzeltilmedi

### 🔴 C1 — `/api/cell-telemetry` geçilemez hücrelerde 500 dönüyor (REGRESYON)

Task 3'te eklenen `cost_breakdown` alanı, geçilemez bir hücrede `inf`, NaN girdide `NaN` taşıyor. Starlette'in `JSONResponse` renderer'ı `json.dumps(allow_nan=False)` kullanıyor ve **exception fırlatıyor:**

```
ValueError: Out of range float values are not JSON compliant
```

**Etki:** Kullanıcı haritada geçilemez bir hücreye (dik yamaç, aşırı soğuk, NaN) tıkladığında endpoint **HTTP 500** döner. Faz 2 öncesi aynı istek 200 dönüyordu — bu net bir **regresyon.**

**Neden testler yakalamadı:** `test_cell_telemetry_explain.py`'daki üç testin de fixture'ı `traversable=np.ones(...)` kullanıyor. Geçilemez hücre hiç test edilmedi.

**Doğrulama:** `TestClient` ile `traversable=zeros` grid üzerinde canlı çalıştırıldı, tam traceback alındı.

### 🔴 C2 — Corridor waypoint'lerinde y-ekseni işaret hatası (1.23 km)

`corridor.py::_pixel_to_metres` şunu hesaplıyor:

```python
return (origin_x + col * resolution_m, origin_y + row * resolution_m)
```

Ama `origin_y` rasterio'nun **üst kenarı** (`transform.f`) ve satır güneye doğru artıyor. Doğrusu `origin_y - row * resolution_m`.

**Gerçek metadata ile ölçülen hata:**

| row | Yanlış (+) lat | Doğru (−) lat | Mesafe |
|---|---|---|---|
| 0 | -89.4721 | -89.4721 | 0 km |
| 250 | -89.4809 | -89.4603 | 0.62 km |
| 499 | -89.4864 | -89.4458 | **1.23 km** |

**Etki:** `Corridor`'ın tüm varlık sebebi yerel planlayıcıya (Faz 4 ROS 2, Faz 5 LiDAR) "şu metre koordinatlarına git" demek. 1.2 km hata bu sözleşmeyi kullanılamaz kılar. `fallback_points` de aynı hatayı taşıyor — yani "güvenli sığınak" noktası da yanlış yerde.

**Kökeni:** Bu hata `serializer.py:89`'dan miras alındı. **Faz 1 raporu bu satırı açıkça "bilinçli olarak düzeltilmedi, ayrı bir görev gerektirir" diye flag'lemişti.** Faz 2 o bilinen hatalı konvansiyonu yeni bir dosyaya kopyaladı. Üç dosyada iki farklı konvansiyon var:

- `process_lunar_data.py:118` → `origin_y - row*res` ✅ (Faz 1'de düzeltilmişti)
- `serializer.py:89` → `origin_y + row*res` ❌ (Faz 1'de flag'lendi, dokunulmadı)
- `corridor.py:807` → `origin_y + row*res` ❌ (Faz 2'de yeni yazıldı, hatalı)

**Neden testler yakalamadı:** `test_waypoints_are_projected_metres_not_pixels` sadece `x1 - x0 == RES_M` (sütun ekseni) kontrol ediyor. Satır ekseni hiç test edilmiyor.

### 🟡 I1 — `/api/cell-telemetry` tek hücre için 250.000 hücre hesaplıyor (1.7 s)

`CostMap.explain()` her katmanın `contribution(ctx)`'ini çağırıyor; bu fonksiyonlar `np.vectorize` ile **tüm grid'i** hesaplıyor, sonra tek indeks okunuyor.

**Ölçülen:**

| Grid | `explain()` süresi |
|---|---|
| 100×100 | 55 ms |
| **500×500 (üretim)** | **1705 ms** |

**Etki:** Frontend'de haritada her hücre tıklamasında 1.7 saniye bekleme. Faz 2 öncesi bu endpoint milisaniyelerdeydi.

**Not:** Plan Task 2'de "Optimising this is explicitly out of scope" diyor — ama bu, tüm-grid hesabının *tek hücrelik bir endpoint'e* bağlanmasını kapsamıyordu. Bu, Task 2 kararının Task 3'te öngörülmeyen sonucu.

### 🟡 I2 — `CostLayer.validity` hardcoded, gerçek provenance'ı yansıtmıyor

`ShadowLayer.validity = "DERIVED"` ve `ThermalLayer.validity = "MODEL"` sınıf sabitleri. Bunlar hiçbir zaman `metadata["layer_validity"]`'ye bakmıyor.

**Somut çelişki:** `/api/load-dem` yolu, `data_loader.py:223-224`'te dürüstçe `shadow_ratio: "SYNTHETIC"`, `thermal: "SYNTHETIC"` diyor. Ama aynı grid üzerine kurulan `default_cost_map()` hâlâ `ShadowLayer.validity == "DERIVED"` raporluyor.

**Etki:** Katman, kendi provenance'ı hakkında yalan söylüyor — Faz 1'in `layer_validity` mekanizmasının önlemek için var olduğu tam da bu. (Faz 1 raporu benzer bir bulguyu "cost/traversable her zaman DERIVED" diye not etmişti; Faz 2 aynı deseni katman seviyesine taşıdı.)

### ⚪ M1 — `Corridor.energy_budget_wh` teorik olarak `inf` olabilir

`edge_energy_wh` ≥90° eğimde `inf` dönüyor, `build_corridor` bunu korumasız saklıyor. `slope=95` ile doğrulandı: `energy_budget_wh=[inf]` → strict JSON başarısız.

**Pratik risk düşük:** Mevcut pencerede maksimum eğim 56.22°. Gerçek DEM'de ≥90° yok. Ama C1 ile aynı kökten — savunma amaçlı guard eklenmeli.

---

## Plandan sapmalar (bilinçli, kod-dışı)

Plandaki test kodu bu kod tabanının gerçek şemasıyla iki noktada uyuşmuyordu:

1. **Endpoint fixture'ları** — Plan `app.state.grids = grids` sonra `with TestClient(app)` diyor. Ama startup lifespan context'e girişte çalışıp `.npy` bulamayınca `app.state.grids = None` yapıyor. Grid enjeksiyonu context'e **girdikten sonraya** alındı. Bu, kod tabanının mevcut `test_plan_endpoint.py` deseniyle aynı.

2. **`/api/replan` response assertion'ı** — Plan `payload["plan"]["path_pixels"]` bekliyor. Ama `build_plan_response` `path_pixels` döndürmüyor; şeması `{status, astar_metrics, summary, geojson, corridor[, waypoints, rover]}`. Assertion `geojson.geometry.coordinates` üzerine çevrildi.

Her ikisi de test-tarafı uyarlama; hiçbir üretim kodu davranışı plandan saptırılmadı.

---

## Kurulum durumu — sistem artık gerçek fizikle çalışıyor

Faz 1 raporunun "bu makinede yeniden üretilemez" sorunu **çözüldü:**

| Bileşen | Durum |
|---|---|
| DEM | ✅ `lunapath/data/raw/Site01_final_adj_5mpp_surf.tif` (3200×3200 @ 5 m/px, güney kutbu) |
| `heat1d` | ✅ 0.4.1 (GitHub `main`, slope/slope_az destekli) — `Heat1DModel.available() == True` |
| `spiceypy` | ✅ 6.0.0 |
| NAIF kernelleri | ✅ İndirildi (`de440s.bsp`, `moon_pa_de440_200625.bpc`, `moon_de440_250416.tf`, `naif0012.tls`) |
| SPICE doğrulaması | ✅ `sun_track()` güney kutbunda ~0.94–1.08° güneş yüksekliği döndürüyor (beklenen bant) |
| Frontend | ✅ `npm install` + `tsc --noEmit` temiz |
| P1 pipeline | ⏳ Çalışıyor — horizon 72/72 bitti, heat1d LUT (13×16=208 hücre) aşamasında |

**Anlamlı sonuç:** heat1d kurulduğu için Faz 1'de SKIP olan 2 test artık **gerçek heat1d simülasyonuyla çalışıp geçiyor** (`145 passed, 0 skipped` — öncesi `143 passed, 2 skipped`). Test süresi 2 s → 218 s çıktı çünkü gerçek termal difüzyon modeli koşuyor.

---

## Faz 2 kabul kriterleri

| Kriter | Durum |
|---|---|
| `pytest` tüm testler geçiyor | ✅ 145 passed, 0 skipped |
| `default_cost_map().total()` == `compute_cost_grid()` (1e-9) | ✅ Test kanıtlıyor |
| `/api/cell-telemetry` → `cost_breakdown` 4 katman + total | ⚠️ Çalışıyor **ama geçilemez hücrede 500** (C1) |
| `/api/plan` → `corridor` dolu, segment dizileri `len(waypoints)-1` | ⚠️ Çalışıyor **ama koordinatlar 1.2 km yanlış** (C2) |
| `/api/replan` tetikleyici yoksa `false`, varsa yeni rota | ✅ |
| 6 replan tetikleyicisinin her biri için birim testi | ✅ 10 test |

**4/6 tam, 2/6 "çalışıyor ama hatalı".**

---

## Kullanıcıya kalan kararlar

Hiçbir bulgu düzeltilmedi. Öneri sırası:

1. **C1'i düzelt (küçük, acil)** — `explain()` çıktısındaki `inf`/`NaN`'ı `None`'a çevir veya endpoint'te `math.isfinite` guard koy. Regresyon olduğu için öncelikli. Ayrıca geçilemez hücre için bir test eklenmeli.

2. **C2'yi düzelt (küçük ama dikkat isteyen)** — `corridor.py::_pixel_to_metres`'te `+` → `-`. **Ama:** `serializer.py:89` aynı hatayı taşıyor ve canlı API'nin `lon/lat` çıktısını besliyor. Faz 1'in reviewer uyarısıyla aynı durum: *sadece birini düzeltmek tutarsızlık yaratır.* İkisini birlikte ele almak, ya da en azından corridor'ı düzeltip serializer'ın hâlâ hatalı olduğunu açıkça belgelemek gerekiyor. Satır eksenini test eden bir assertion şart.

3. **I1'i ele al (orta)** — `CostLayer`'a hücre-bazlı bir yol ekle (`contribution_at(row, col, ctx)`) veya `explain()` için 1×1 slice'lı `PlanContext` kur. 1.7 s → ~ms.

4. **I2'yi ele al (küçük)** — `default_cost_map()`'e `metadata["layer_validity"]` geçir, katman validity'sini oradan türet.

5. **M1'e guard ekle (çok küçük)** — `build_corridor`'da `energy_budget_wh` için sonluluk kontrolü.

**Ayrıca Faz 1'den devreden, hâlâ açık:**

- `test_traversability.py` `1d95e27`'den beri `ImportError` ile ölü (`THERMAL_MIN_TRAVERSABLE_C`). Faz 1 ve Faz 2 ile ilgisi yok ama artık iki fazdır "bilinen bozuk" olarak taşınıyor.
- `sun_track` örnek başına `spice.furnsh` çağırıyor (~169 gereksiz yükleme) — Faz 3'ün daha büyük örnek sayılarında gerçek tavan.
- heat1d LUT cache'i bellek-içi; her pipeline koşumu sıfırdan ~12-15 dk.

---

## Sayılar

| Metrik | Değer |
|---|---|
| Toplam commit (`3b91162..926fcff`) | 6 |
| Görev sayısı | 6/6 tamamlandı |
| Yeni test | 40 (105 → 145) |
| Son pytest | 145 passed, 0 skipped |
| `test_cost_engine.py` | 42/42 PASS |
| Kritik bulgu | **2 (ikisi de açık)** |
| Önemli bulgu | **2 (ikisi de açık)** |
| Minör bulgu | 1 (açık) |
| Faz 2'nin yarattığı regresyon | 2 (C1, C2) |
| Düzeltilen bulgu | **0** |

---

## Sonraki adım

Faz 3-6 planları `docs/superpowers/plans/` altında hazır:

- [`2026-08-19-faz3-zaman-ekseni.md`](2026-08-19-faz3-zaman-ekseni.md)
- [`2026-08-19-faz4-ros2.md`](2026-08-19-faz4-ros2.md)
- [`2026-08-19-faz5-lidar.md`](2026-08-19-faz5-lidar.md)
- [`2026-08-19-faz6-dogrulama.md`](2026-08-19-faz6-dogrulama.md)

**Öneri:** Faz 3'e geçmeden önce en azından C1 ve C2 düzeltilmeli. Faz 4 (ROS 2) ve Faz 5 (LiDAR) doğrudan `Corridor` sözleşmesini tüketiyor — C2 düzeltilmeden o fazlar 1.2 km hatalı koordinatların üzerine inşa edilir.
