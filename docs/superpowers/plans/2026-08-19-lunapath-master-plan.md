# LunaPath Entegrasyon — Ana Uygulama Planı (Master Plan)

> **Bu bir yönlendirme belgesidir, yürütme belgesi değildir.** Yürütülecek adımlar altı faz planında. Bu belge fazları, bağımlılıklarını, ortak kısıtları ve dosya haritasını tanımlar.

**Goal:** `docs/research/ENTEGRASYON_TEKNOLOJILERI.md`'de tanımlanan entegrasyonları, LunaPath'in çalışan prototipini bozmadan, altı bağımsız test edilebilir fazda koda geçirmek.

**Architecture:** Mevcut mimari korunuyor — `backend/app/` saf fonksiyonlardan oluşan çekirdek, `lunapath/src/` offline veri hattı, `frontend/` React kokpit. Fazlar bu çekirdeği **yerinden etmeden genişletiyor**: sentetik katmanlar gerçek fizikle değiştiriliyor (Faz 1), maliyet motoru katmanlı yapıya çevriliyor (Faz 2), planlayıcıya zaman ekseni ekleniyor (Faz 3), çekirdek ikinci bir kabuktan (ROS 2) servis ediliyor (Faz 4), yerel katman arayüzü sanal LiDAR ile test ediliyor (Faz 5), sonuçlar uçmuş misyon verisiyle doğrulanıyor (Faz 6).

**Tech Stack:** Python 3.11+ · FastAPI 0.115.6 · NumPy 2.2.1 · SciPy 1.15.0 · rasterio 1.4.3 · pyproj 3.7.2 · pytest · heat1d (MIT) · spiceypy (MIT) · ROS 2 Jazzy Jalisco + `grid_map` (BSD-3) · React 18 + three.js

**Spec:** [`docs/research/ENTEGRASYON_TEKNOLOJILERI.md`](../../research/ENTEGRASYON_TEKNOLOJILERI.md)

---

## Global Constraints

Bu kısıtlar **her fazın her görevi** için geçerlidir. Faz planları bunları tekrar etmez.

- **Python 3.11+.** `from __future__ import annotations` her yeni modülün ilk satırı (mevcut kod bu deseni kullanıyor).
- **İş mantığı `backend/app/` içinde kalır.** `backend/app/` altındaki hiçbir dosya `rclpy`, `fastapi` veya `matplotlib` import etmez. Kabuklar (FastAPI, ROS 2) çekirdeği çağırır, çekirdek kabuğu tanımaz.
- **Testler `backend/test_*.py` içinde, pytest stilinde** (`def test_*`). Çalıştırma: `cd backend && pytest`. Mevcut `test_cost_engine.py` ve `test_traversability.py` script stilinde — **onlara dokunulmaz**, yeni testler pytest stilinde yazılır.
- **Test importları `from app.X import Y` biçimindedir** (çalışma dizini `backend/`). Paket içi importlar `from .X import Y` biçimindedir.
- **Hiçbir test ağ erişimi, SPICE çekirdeği, DEM dosyası veya GPU gerektirmez.** Harici kaynak gerektiren kod yolları saf fonksiyonlardan ayrılır; testler saf tarafı kapsar.
- **Ağırlık anahtarları sabittir:** `w_slope`, `w_energy`, `w_shadow`, `w_thermal`. Varsayılan değerler `constants.py` rover kataloğundan gelir (LPR-1: 0.409 / 0.259 / 0.142 / 0.190).
- **Grid geometrisi asla sabitlenmez.** `resolution_m`, `shape`, `origin`, `crs` her zaman `lunapath/data/processed/metadata.json`'dan çalışma zamanında okunur — hiçbir yeni kod bunları sabit sayı olarak varsaymaz. **Gerekçe:** proje şu an 5 m/px, 500×500 (2.5 km pencere) bir `Site01` grid'i kullanıyor; önceki 80 m/px, 500×500 (40 km pencere) güney kutbu grid'i artık repoda yok. Fiziksel bir menzil/adım sayısı hesaplarken (ör. ufuk ışın izleme) sabit bir fiziksel menzil yerine **adım sayısı bütçesi** kullanılır (bkz. `horizon.py`'nin `max_steps` parametresi, Faz 1 Task 5) — böylece hesap yükü hangi çözünürlük yüklenirse yüklensin aynı kalır. Aynı şekilde enlem/boylam gibi konum-bağımlı değerler asla sabitlenmez; pencerenin merkezinden `pyproj` ile türetilir (Faz 1 Task 8). R=1737400 m (Ay yarıçapı) sabittir — bu, DEM'den bağımsız fiziksel bir sabittir. Testler bu kısıttan muaftır: sentetik küçük fixture grid'leri (ör. `(20, 20)`, `resolution_m=80.0`) kullanmakta serbesttirler, gerçek grid'i temsil etmeleri gerekmez.
- **Sıcaklık birimi °C** (Kelvin değil) — `thermal_grid`, `f_thermal`, `surface_to_inner` hepsi °C. heat1d Kelvin döner; dönüşüm adaptör katmanında yapılır.
- **Penaltı fonksiyonları MRU [0, 1] döner** (`f_slope`, `f_energy`, `f_shadow`, `f_thermal`). Aşılamaz kısıtlar `float("inf")` döner.
- **Lisans:** Proje MIT. **GPL lisanslı hiçbir bağımlılık eklenmez** (özellikle FAST-LIO2 — bkz. spec §5.4). Yeni bağımlılık eklenirken lisans `docs/DATA_LICENSES.md`'ye yazılır.
- **Her görev tek bir commit ile biter.** Commit mesajı Conventional Commits (`feat:`, `fix:`, `test:`, `refactor:`, `docs:`).
- **Geriye dönük uyumluluk:** `/api/plan`, `/api/plan-multi`, `/api/compare`, `/api/layers/{name}` yanıt şemaları **kırılmaz**; yeni alanlar eklenir, mevcut alanlar kaldırılmaz veya tip değiştirmez.

---

## Faz haritası ve bağımlılıklar

```
FAZ 1 — Gerçek fizik ve veri
   │  (gölge düzeltmesi · heat1d · ufuk · SPICE)
   │
   ├──────────────► FAZ 2 — Maliyet mimarisi
   │                   │  (CostMap/explain · Corridor · replan)
   │                   │
   │                   ├──────────────► FAZ 4 — ROS 2 ekosistemi
   │                   │                   (lunapath_ros · grid_map · action)
   │                   │
   │                   └──────────────► FAZ 5 — LiDAR ve yerel katman
   │                                       (sensor_payload_w · sanal LiDAR)
   │
   └──────────────► FAZ 3 — Zaman ekseni
                       │  (illumination cube · BEKLE kenarı · 4B A*)
                       │
                       └──────────────► FAZ 6 — Doğrulama ve baseline
                                           (Yutu-2/Pragyan · ETH · Diviner)
```

**Zorunlu sıra:** Faz 1 → Faz 2. Faz 3, Faz 1'den sonra Faz 2'ye paralel yürütülebilir. Faz 4 ve Faz 5, Faz 2'nin `Corridor` şemasına bağlı ve **birbirinden bağımsız** — paralel yürütülebilir. Faz 6 en sonda.

**Neden bu sıra:** Faz 1 verinin kendisini gerçek yapıyor; üstüne kurulan her şey ondan sonra anlamlı. Faz 2 hem yeni kriterlerin yerini açıyor hem de Faz 4/5'in tükettiği `Corridor` sözleşmesini üretiyor — spec §2.5 ve §2.6 bunu "ön koşul" olarak işaretliyor.

---

## Faz planları

| Faz | Plan dosyası | Görev | Süre | Çıktı |
|---|---|---|---|---|
| **1** | [`faz1-gercek-fizik.md`](2026-08-19-faz1-gercek-fizik.md) | 8 | 5–7 gün | Gölge terimi düzeltilmiş, termal grid heat1d fiziğinde, ufuk/aydınlanma gerçek |
| **2** | [`faz2-maliyet-mimarisi.md`](2026-08-19-faz2-maliyet-mimarisi.md) | 6 | 4–5 gün | `CostMap.explain()`, `Corridor` sözleşmesi, `/api/replan` |
| **3** | [`faz3-zaman-ekseni.md`](2026-08-19-faz3-zaman-ekseni.md) | 5 | 5–7 gün | 4B A* + BEKLE kenarı; "planlayıcı beklemeyi seçti" demosu |
| **4** | [`faz4-ros2.md`](2026-08-19-faz4-ros2.md) | 7 | 5–6 gün | `lunapath_ros` action server, `grid_map` yayını, rosbag2, Nav2 baseline |
| **5** | [`faz5-lidar.md`](2026-08-19-faz5-lidar.md) | 5 | 3 gün | LiDAR'lı/LiDAR'sız profil kıyası, sanal LiDAR, koridor arayüz testi |
| **6** | [`faz6-dogrulama.md`](2026-08-19-faz6-dogrulama.md) | 4 | 3–4 gün | Yutu-2/Pragyan doğrulaması, rota istatistikleri, Diviner karşılaştırması |

**Toplam: 35 görev, 25–33 gün** (tek geliştirici, seri). Faz 3 ⇄ Faz 2 ve Faz 4 ⇄ Faz 5 paralelleştirilirse ~19–23 gün.

---

## Dosya haritası

Fazlar boyunca oluşturulacak ve değiştirilecek dosyalar. Her dosyanın **tek bir sorumluluğu** var.

### Yeni — `backend/app/` (çekirdek, kabuk bağımsız)

| Dosya | Sorumluluk | Faz |
|---|---|---|
| `thermal_model.py` | `SurfaceThermalModel` protokolü + `Heat1DModel` + `SyntheticModel` adaptörleri | 1 |
| `horizon.py` | Topografyadan ufuk açısı haritası (saf numpy ray-marching) | 1 |
| `ephemeris.py` | SPICE güneş vektörü + saf geometri (`sun_azel_from_vector`) | 1 |
| `illumination.py` | `I(x, y, t)` — ufuk + güneş açısı → aydınlanma kesri | 1 |
| `costmap.py` | `CostLayer` protokolü, `CostMap`, `explain()` | 2 |
| `schemas.py` | `Corridor`, `PlanMetrics`, `ReplanTrigger` pydantic modelleri | 2 |
| `corridor.py` | Rota + geçilebilirlik → `Corridor` üretimi (`clearance`, bütçeler) | 2 |
| `replan_triggers.py` | 6 tetikleyicinin saf değerlendirme fonksiyonları | 2 |
| `cost_cube.py` | Zaman dilimli maliyet küpü üretimi | 3 |
| `pathfinder_4d.py` | `astar_4d` — (row, col, t) durum uzayı + BEKLE kenarı | 3 |
| `grid_frame.py` | Grid ⇄ harita çerçevesi geometrisi (saf, `rclpy`'siz) | 4 |
| `sensor_payload.py` | LiDAR taşımanın enerji/termal bütçe maliyeti | 5 |
| `mission_reference.py` | Kaynak künyeli gerçek misyon verisi (Yutu-2, Pragyan) | 6 |
| `route_analysis.py` | `PathAnalysis`'ten ilham rota istatistikleri | 6 |
| `thermal_validation.py` | Model ↔ Diviner karşılaştırma fonksiyonu (saf) | 6 |

### Yeni — `lunapath/src/` (offline hat)

| Dosya | Sorumluluk | Faz |
|---|---|---|
| `fetch_kernels.py` | NAIF SPICE çekirdek indirme (repoya girmez) | 1 |
| `virtual_lidar.py` | Yörünge DEM'inden sentetik LiDAR taraması | 5 |

> **Not — Imbrium kısayolu bilinçli olarak atlandı:** İlk taslak burada bir `fetch_imbrium.py` (MIT Imbrium AVGVISIB/LPSR indirme) öngörüyordu. Faz 1'in ufuk (`horizon.py`) + SPICE (`ephemeris.py`) hattı, spec §1.3'ün asıl hedefi olan **gerçek** aydınlanmayı zaten üretiyor; Imbrium AVGVISIB yalnızca bir kestirme alternatifiydi (spec §1.4) ve bu iki hat aynı sonuca farklı yollardan varıyor — ikisini birden kurmak gereksiz. Diviner Polar Resource Product karşılaştırması (spec §1.4'ün asıl talep ettiği harici doğrulama) Faz 6'da `thermal_validation.py` + `scripts/diviner_validation.py` ile, manuel indirme adımıyla karşılanıyor.

### Yeni — `scripts/` (offline araçlar ve raporlar)

| Dosya | Sorumluluk | Faz |
|---|---|---|
| `nav2_baseline.py` | Geometrik baseline vs. LunaPath A* kıyası → `docs/research/nav2_baseline.md` | 4 |
| `record_plan.sh` | Bir plan koşumunu `rosbag2` ile kaydeder | 4 |
| `lidar_payload_comparison.py` | LiDAR'lı/LiDAR'sız profil enerji kıyası → rapor | 5 |
| `diviner_validation.py` | Model termal grid ↔ Diviner referansı (veri yoksa nazikçe atlar) | 6 |

### Yeni — `lunapath_ros/` (ROS 2 paketi, ayrı kök)

| Dosya | Sorumluluk | Faz |
|---|---|---|
| `lunapath_ros/conversions.py` | `(row, col)` ⇄ ENU map frame; grid_map layout (saf, rclpy'siz) | 4 |
| `lunapath_ros/grid_publisher.py` | Katmanları `grid_map_msgs/GridMap` olarak yayınla | 4 |
| `lunapath_ros/planner_node.py` | `PlanTraverse` action server (ince kabuk) | 4 |
| `lunapath_msgs/action/PlanTraverse.action` | Action arayüzü (Nav2 hata kodu semantiği) | 4 |
| `lunapath_msgs/msg/{Corridor,PlanMetrics,MissionWeights}.msg` | Mesaj tanımları | 4 |

### Değiştirilecek — mevcut dosyalar

| Dosya | Ne değişiyor | Faz |
|---|---|---|
| `backend/app/cost_engine.py` | `f_shadow_cell` eklenir; `compute_cost_grid` onu kullanır | 1 |
| `backend/app/thermal_grid.py` | `thermal_model.py`'ye delege eder (fonksiyon imzası korunur) | 1 |
| `backend/app/constants.py` | `sensor_payload_w`, `sensor_heater_w` alanları | 5 |
| `backend/app/data_loader.py` | Yeni katmanlar (`illumination`, `clearance`) yüklenir | 1, 2 |
| `backend/app/main.py` | `/api/replan`, `/api/plan-4d`; `/api/cell-telemetry` → `explain`; `/api/plan` → `route_statistics` | 2, 3, 6 |
| `backend/app/serializer.py` | `build_plan_response` → `corridor`, `route_statistics` alanları | 2, 6 |
| `backend/requirements.txt` | `pytest`, `heat1d`, `spiceypy` | 1 |
| `lunapath/requirements.txt` | Pin'lenir (spec §1.10 kapsamında minimal) | 1 |
| `lunapath/src/process_lunar_data.py` | `make_shadow_ratio_grid` ufuk tabanlı; `make_thermal_grid` heat1d | 1 |
| `lunapath/data/processed/metadata.json` | Katman başına `validity` alanı | 1 |

---

## Faz kabul kriterleri (üst düzey)

Her faz, kendi planındaki görev kabul kriterlerine **ek olarak** şunu sağlamalıdır:

- [ ] `cd backend && pytest` — tüm testler geçiyor (yeni + mevcut)
- [ ] `python test_cost_engine.py` ve `python test_traversability.py` — çıkış kodu 0 (script stili mevcut testler bozulmamış)
- [ ] `/api/health`, `/api/plan` (LPR-1, varsayılan ağırlıklar, gerçek grid'de `/api/layers/traversable` ile bulunan iki geçilebilir nokta arasında — sabit piksel koordinatı varsayılmaz, bkz. Faz 1 Task 8 Step 8) hata vermeden yanıt dönüyor
- [ ] Faz boyunca eklenen her yeni bağımlılık `requirements.txt`'de pin'li ve lisansı MIT/BSD/Apache

---

## Riskler ve azaltımlar

| Risk | Etki | Azaltım | Faz |
|---|---|---|---|
| `heat1d` PyPI sürümü (0.3.1, 2020) README'deki `slope`/`slope_az` parametrelerini içermiyor | 🔴 Faz 1 Task 3 bloke | `thermal_model.py` adaptör deseni: `Heat1DModel` bir protokol implementasyonu; testler stub ile koşar. Gerçek kurulum başarısızsa `SyntheticModel` fallback devrede kalır, plan ilerlemeye devam eder | 1 |
| SPICE çekirdekleri birkaç yüz MB | 🟠 İndirme süresi | `fetch_kernels.py` ayrı script; testler saf geometri fonksiyonunu kapsar, çekirdek gerektirmez | 1 |
| Ufuk hesabı 500×500 × 360 azimut = ~56 milyar işlem | 🔴 Saf Python'da imkânsız | Azimut 72'ye (5°) düşürülür + numpy vektörizasyon; `max_range_m` 10 km'ye sınırlanır (Faz 1 Task 5). SPICE çekirdekleri veya ufuk hesabı başarısız olursa Faz 1 Task 8'deki hat, `layer_validity=SYNTHETIC` etiketiyle eski yükseklik-proxy'sine döner — sessizce değil, açıkça raporlayarak | 1 |
| ROS 2 Jazzy Windows'ta birinci sınıf değil | 🔴 Faz 4 bloke | Faz 4 Task 1 **sadece ortam kurulumu**: WSL2 + Ubuntu 24.04 veya `osrf/ros:jazzy-desktop`. Faz 3 bitmeden başlatılır | 4 |
| `grid_map` sütun-öncelikli veri düzeni | 🟠 RViz'de 90° dönmüş harita | Faz 4 Task 4'te asimetrik desen birim testi zorunlu | 4 |
| `CostMap` refaktörü mevcut maliyet çıktısını değiştirir | 🔴 Regresyon | Faz 2 Task 2 bir **eşitlik testi**: yeni `CostMap.total()` eski `compute_cost_grid()` ile bit-yakın aynı olmalı (tol 1e-9) | 2 |
| Kenar-bazlı eğim (`np.gradient` yerine gerçek yükseklik farkı) metrikleri değiştirir | 🟠 Doğrulama tabloları kayar | Bu plan **kapsam dışı** bırakıyor (spec "Sonraki aşamaya bırakılanlar"). `np.gradient` korunur | — |

---

## Kapsam dışı

Spec'in "Sonraki aşamaya bırakılanlar" tablosundaki her şey bu plan setinin dışındadır: radyasyon katmanı, pürüzlülük/kaya bolluğu kriterleri, maliyet ön-hesaplama, üç seviyeli hiyerarşi, anytime A*, hesaplama bütçesi analizi, slip düzeltmesi, safe haven, footprint erozyonu, SBOM/provenance disiplini, A/B/C/D ablasyon protokolü, NASA-STD-7009 skorkartı, MMGIS/cFS konumlandırması, AYAP-2 çok noktalı tur.

Ayrıca: gerçek LiDAR donanımı, simülatör kurulumu (OmniLRS/Gazebo), Nav2 C++ shim eklentisi, Space ROS kurulumu, algı yığını (SuperPoint/LunarLoc/SLAM), LuSNAR veri seti indirme, MIT Imbrium AVGVISIB indirme kısayolu (Faz 1'in ufuk+SPICE hattı aynı sonucu üretiyor — bkz. dosya haritasındaki not), ETH `lunar_planner`'ın gerçek kurulup çalıştırılması (Faz 6'da yalnızca `PathAnalysis`'ten ilham alınan istatistikler uygulanıyor, dış repo kurulmuyor).

---

## Yürütme

Her faz planı bağımsız olarak yürütülebilir ve kendi başına çalışan yazılım üretir. Sıra için yukarıdaki bağımlılık grafiğine bakın. Bir faza başlarken o fazın plan dosyasını açın ve `superpowers:subagent-driven-development` veya `superpowers:executing-plans` ile görev görev ilerleyin.
