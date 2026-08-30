# LunaPath Backend — Bağımsız Kod İncelemesi

> ## ✅ DURUM: 21/21 BULGU DÜZELTİLDİ (2026-08-30)
>
> Tüm bulgular raporun 4 aşamalı sırasına göre düzeltildi ve her biri için
> regresyon testi yazıldı (`backend/test_review_fixes.py`, 65 test).
> Aşağıdaki bulgu açıklamaları **düzeltme öncesi** durumu anlatır; her
> maddenin sonunda ne yapıldığı yazılıdır.
>
> **Ölçülen sonuçlar:**
> - Enerji kriteri katkısı: %0.04 → **%24.18** (rota artık dört kritere de tepki veriyor)
> - Yanlış "geçilebilir" hücre: 93.762 → **0**
> - `compute_cost_grid`: 7.31 s → **0.129 s** (~57×)
> - Uçtan uca `/api/plan`: ~1.8 s → **0.62 s** (~3×)
> - Yeni regresyon testi: **65**; ayrıca dışlanan 65 harness testi suite'e geri döndü
> - CI: yoktu → `.gitlab-ci.yml` eklendi
>
> **Kapsam notu:** Bu inceleme ve düzeltmeler `backend/` klasörünün tamamını
> kapsar (23 modül), tek bir faz değil. 21 bulgunun yalnızca 1'i (#12) Faz 5
> koduydu; geri kalanı Faz 1–4'ten gelen mevcut koddan çıktı.

**Tarih:** 2026-08-30
**Kapsam:** `backend/` (23 modül, 4786 satır) + test altyapısı
**Branch:** `backend/physics` @ `820b9fa`
**Yöntem:** Her bulgu çalıştırılabilir kanıtla doğrulandı. Doğrulayamadıklarımı ayrıca işaretledim.

> **Not:** Bu inceleme Faz 5 çalışmamdan bağımsız yapıldı. Faz 5'te kendi yazdığım
> kod da (`sensor_payload.py`) incelemeye dahildir ve bir bulgu (#12) oradan çıktı.

---

## Özet

| Seviye | Adet | Ne demek |
|---|---|---|
| 🔴 **KRİTİK** | 3 | Yanlış sonuç üretiyor veya güvenlik açığı; fix öncelikli |
| 🟠 **YÜKSEK** | 5 | Gerçek bug ya da ciddi risk; production'a gitmeden düzeltilmeli |
| 🟡 **ORTA** | 7 | Doğruluğu bozmuyor ama performans/bakım/dayanıklılık sorunu |
| 🔵 **DÜŞÜK** | 6 | Temizlik, tutarlılık, ölü kod |

**En önemli üç bulgu:**
1. **Enerji kriteri planlamada tamamen etkisiz** (#1) — AHP ağırlığının %25.9'u hiçbir şey yapmıyor, kanıtlandı
2. **Rover uyumsuzluğunda 93.762 hücre yanlışlıkla "geçilebilir"** (#2) — güvenlik etkisi var
3. **`/api/load-dem` path traversal** (#3) — sunucudaki herhangi bir dosya okunabilir

---

## 🔴 KRİTİK

### #1 — `f_energy` planlamada tamamen etkisiz: AHP ağırlığının %25.9'u ölü

**Yer:** [`app/cost_engine.py:70-75`](backend/app/cost_engine.py#L70-L75) (`f_energy`), [`app/cost_engine.py:322`](backend/app/cost_engine.py#L322)

`f_energy` enerjiyi `e_cap_wh` (5420 Wh) ile normalize ediyor, ama tek hücrelik bir kenarın
enerjisi ~1.4 Wh. Sonuç: terim `~0.00026–0.00074` aralığında kalıyor, diğer kriterler ise
`0.02–1.0` aralığında. Ağırlıklı toplamda enerji **%0.04** katkı yapıyor.

**Kanıt — bu tam olarak `f_shadow_cell`'in docstring'inde anlatılan hatanın aynısı**
(orada gölge için düzeltilmiş, enerjide düzeltilmemiş):

```
5 m çözünürlükte ağırlıklı katkılar (lpr_1, tipik hücre):
  slope@10deg      0.048754  (18.42%)
  energy@10deg     0.000110  ( 0.04%)   <-- w_energy = 0.259 olmasına rağmen
  shadow@0.5       0.025904  ( 9.79%)
  thermal@-100C    0.189957  (71.76%)

f_energy dinamik aralığı (eğim 0 -> 24 derece): 0.000256 -> 0.000741
```

**Rota üzerinde kesin kanıt** — `w_energy`'yi 0.0'dan 2.0'a (izin verilen maksimum)
çıkardım, rota **byte-byte aynı** kaldı:

```
route with w_energy=0.259: 363 nodes
route with w_energy=0.000: 363 nodes   IDENTICAL ROUTE: True
route with w_energy=2.000: 363 nodes   identical to baseline: True

KONTROL (diğer kriterler sıfırlanınca rota değişiyor mu?):
  w_slope   =0 -> route changed: True
  w_energy  =0 -> route changed: False   <-- tek etkisiz kriter
  w_shadow  =0 -> route changed: True
  w_thermal =0 -> route changed: True
```

**Neden kritik:** Proje "çok kriterli rota planlama" iddiasında ve AHP ağırlıkları
sunumun merkezinde. Dört kriterden biri fiilen yok. Kullanıcı enerji ağırlığını
değiştirdiğinde arayüzde hiçbir şey değişmiyor — sessiz başarısızlık.

**✅ DÜZELTİLDİ.** `f_energy_cell` eklendi: eğimin düz zemine göre getirdiği fazla
enerjinin `slope_max_deg`'de 1.0'a normalize edilmiş oranı. Üç tüketici de
(`total_edge_cost`, `compute_cost_grid`, `EnergyLayer`) bu fonksiyona bağlandı.
Katkı %0.04 → %24.18; `w_energy` artık rotayı değiştiriyor. Ek fayda: oran
çözünürlükten bağımsız, yani aynı arazi 5 m ve 80 m'de aynı puanı alıyor.

**Önceki öneri:** `f_shadow_cell`'de yapılanın aynısı — hücre bazlı bir normalizasyon.
Örn. enerjiyi `e_cap_wh` yerine "tipik kenar enerjisi" ile ölçekle ya da eğime bağlı
`mu` çarpanını doğrudan MRU'ya taşı. **Not:** ağırlıkların yeniden kalibrasyonu gerekir,
çünkü enerji terimi ilk kez gerçekten devreye girecek.

---

### #2 — `grids_for_rover` saklanmış maskeye körü körüne güveniyor: 93.762 hücre yanlış "geçilebilir"

**Yer:** [`app/rover_grids.py:37-46`](backend/app/rover_grids.py#L37-L46)

```python
traversable = (
    base_grids["traversable"]                    # <-- doğrulama yok
    if rover_id == default_rover_id
    else compute_traversability_bool(...)
)
```

`rover_id == default_rover_id` olduğunda saklanmış maske doğru kabul ediliyor. Ama
`default_rover_id` sadece `metadata.json`'dan gelen bir **etiket** — maskenin gerçekten
o rover için hesaplandığının garantisi yok.

**Kanıt** — metadata `nasa_viper` (20°) diyor ama saklanmış maske 25° ile üretilmiş:

```
returned (trusted stored mask): 206028
correct for nasa_viper       : 112266
MISMATCH -> cells wrongly passable: 93762
```

**Neden kritik:** VIPER'ın 20° limitinin üstündeki 25°'lik araziden rota geçirilir.
Bu bir *güvenlik* sınırı, kozmetik değil. Tetiklenmesi için `metadata.json`'ın yanlış
`default_rover_id` taşıması yeterli — P1 hattı farklı rover ile çalıştırılırsa olur.

**✅ DÜZELTİLDİ.** Maske her zaman `slope`/`thermal`'dan yeniden hesaplanıyor
(ölçüldü: varsayılan yolda 0.001 s). Ayrıca saklanmış `cost` gridi de artık
maskeyle karşılaştırılıyor; uyuşmazsa yeniden hesaplanıyor. Yanlış hücre: 0.

**Önceki öneri:** Ya maskeyi her zaman yeniden hesapla (ölçtüm: 500×500 için ~0.05 s, ihmal
edilebilir), ya da metadata'ya maskenin üretildiği rover + eşiği yaz ve yükleme
sırasında doğrula.

---

### #3 — `/api/load-dem` path traversal: sunucudaki herhangi bir dosya hedeflenebilir

**Yer:** [`app/main.py:270`](backend/app/main.py#L270), aynısı [`app/main.py:838`](backend/app/main.py#L838) (`load_scenario_endpoint`)

```python
dem_path = os.path.join(DATA_DIR, "dem", req.dem_file)   # sanitizasyon yok
```

`os.path.join` mutlak yol verilince önceki parçaları **atar**.

**Kanıt:**

```
DATA_DIR = C:\Users\tuna9\Desktop\ASTROHackathon\backend\data
  '../../../../etc/passwd'        -> C:\Users\tuna9\Desktop\etc\passwd
  '..\..\..\Windows\win.ini'      -> C:\Users\tuna9\Desktop\ASTROHackathon\Windows\win.ini
  '/etc/shadow'                   -> C:\etc\shadow
  'C:\Windows\win.ini'            -> C:\Windows\win.ini        <-- DATA_DIR tamamen atlandı
```

**Sınır:** Dosya `rasterio.open()`'a gidiyor, yani doğrudan içerik sızdırma sınırlı
(rasterio olmayan formatı reddeder). Ancak: (a) hata mesajları dosya varlığını sızdırır
(`404 DEM file not found` vs rasterio hatası), (b) rasterio çok sayıda format destekler,
(c) kimlik doğrulama yok — endpoint herkese açık.

**✅ DÜZELTİLDİ.** `_resolve_dem_path()` eklendi ve hem `/api/load-dem` hem
senaryo yükleyici oradan geçiyor. Tüm saldırı vektörleri 422; meşru dosya
adları hâlâ 404/200 veriyor.

**Önceki öneri:**
```python
dem_root = Path(DATA_DIR, "dem").resolve()
dem_path = (dem_root / req.dem_file).resolve()
if not dem_path.is_relative_to(dem_root):
    raise HTTPException(422, "dem_file must stay within the DEM directory")
```

---

## 🟠 YÜKSEK

### #4 — `evaluate_triggers` fail-open: eksik telemetri = "replan gerekmiyor"

**Yer:** [`app/replan_triggers.py:100-127`](backend/app/replan_triggers.py#L100-L127)

Her kontrol `if "key" in state` ile korunuyor. Alan yoksa kontrol **hiç çalışmıyor** ve
`/api/replan` `replanned: false` döndürüyor.

**Kanıt:**
```
empty state                          -> []
partial (only actual_soc)            -> []
dangerously low SOC but no planned_soc -> []    <-- SOC 0.01 (%1 batarya!)
corridor violation w/o half_width    -> []      <-- 9999 m sapma
```

**Neden yüksek:** Bu bir güvenlik mekanizması. Bozuk/eksik telemetri paketi — ki tam da
bir arıza sırasında beklenir — "her şey yolunda" cevabı üretiyor. Sessiz, loglanmıyor.

**✅ DÜZELTİLDİ.** `evaluate_triggers_detailed()` eklendi; `fired` / `evaluated` /
`skipped` döndürüyor ve `/api/replan` bunları yanıta koyuyor. Eksik alan artık
yanıtta görünüyor. `evaluate_triggers()` geriye dönük uyumlu bırakıldı.

**Önceki öneri:** Değerlendirilen ve atlanan tetikleyicileri response'ta döndür
(`evaluated: [...], skipped: [...]`), böylece çağıran eksik alanı görür. Kritik alanlar
için (SOC) eksiklik başlı başına bir tetikleyici olmalı.

---

### #5 — Maliyet gridi her istekte iki kez hesaplanıyor (~0.75 s boşa)

**Yer:** [`app/pathfinder.py:110-117`](backend/app/pathfinder.py#L110-L117) vs [`app/rover_grids.py:46-59`](backend/app/rover_grids.py#L46-L59)

`grids_for_rover` `grids["cost"]`'u hesaplıyor; `astar` onu **yok sayıp** aynı gridi
baştan hesaplıyor.

**Kanıt:**
```
grids_for_rover(viper)     : 0.795s     <-- cost hesaplandı
astar total                : 1.765s     <-- içinde 0.747s tekrar hesap
astar's internal recompute : 0.747s
identical to grids['cost'] : True       <-- birebir aynı grid
```

Tek bir `/api/plan` isteği ~1.8 s sürüyor, bunun ~0.75 s'i tamamen boşa. `/api/compare`
5 profil × 2 hesap = 10 kez çağırıyor.

**✅ DÜZELTİLDİ.** `astar` artık `grids["cost"]`'u yeniden kullanıyor — ancak
metadata'daki rover, ağırlıklar **ve** `cost_model` damgası eşleşirse.
Bu sırada diskteki P1 gridinin eski formülle üretildiği ortaya çıktı; bu yüzden
`COST_MODEL_ID` sürümlemesi eklendi ve bayat grid otomatik yenileniyor.
Aynı rota, `astar` içinde 3.44 s tasarruf.

**Önceki öneri:** `astar`'a opsiyonel `cost_grid` parametresi ekle; `grids.get("cost")` varsa
ve ağırlıklar eşleşiyorsa onu kullan.

---

### #6 — 4D küp bellek patlaması: `MAX_PLAN_4D_SLICES` `coarsen`'i hesaba katmıyor

**Yer:** [`app/main.py:79`](backend/app/main.py#L79), [`app/main.py:626-634`](backend/app/main.py#L626-L634)

`n_slices` 1000'e kadar serbest, ama `coarsen` 1 olabiliyor. `build_cost_cube`
`np.stack` ile T dilimi **tam materyalize** ediyor, `build_wait_cost_cube` de aynısını.

**Kanıt (float64, 500×500 taban grid):**
```
coarsen=1  coarse=500x500  T=1000 -> cost_cube 2000.0 MB  + wait_cube = 4000.0 MB
coarsen=1  coarse=500x500  T= 100 -> cost_cube  200.0 MB  + wait_cube =  400.0 MB
coarsen=4  coarse=125x125  T=1000 -> cost_cube  125.0 MB  + wait_cube =  250.0 MB
```

Tek bir istek 4 GB istiyor. Üstelik `shadow_series = [base_shadow] * n_slices` **aynı
gridin 1000 kopyası** — şu an aydınlatma sabit tutulduğu için tümü özdeş.

**✅ DÜZELTİLDİ.** `MAX_PLAN_4D_CUBE_BYTES` (512 MiB) ve `_check_cube_budget()`
eklendi; küpler inşa edilmeden önce `T × H' × W' × 8 × 2` bütçesi denetleniyor.
4 GB'lık istek 422 ile reddediliyor, makul kombinasyonlar geçiyor.

**Önceki öneri:** Cap'i dilim sayısı yerine **bellek** üzerinden koy:
`n_slices * coarse_h * coarse_w * 8 * 2 <= MAX_CUBE_BYTES`. Ayrıca aydınlatma gerçekten
zamanla değişene kadar sabit dilimler için broadcast/lazy görünüm kullan.

---

### #7 — `_grids` global'i ile `app.state.grids` iki ayrı doğruluk kaynağı

**Yer:** [`app/main.py:84`](backend/app/main.py#L84), 4 ayrı senkronizasyon noktası (93-94, 258-262, 277-283, 837-845)

İki depo elle senkronize ediliyor. `_active_grids` ikisini `or` ile birleştiriyor,
ama `_get_grids` **sadece** global'e bakıyor. `health` de sadece global'e bakıyor.

Sonuçlar:
- Bir yol güncellenip diğeri unutulursa endpoint'ler farklı grid görür
- `/api/plan-multi`, `/api/compare`, `/api/layers` `_get_grids()` kullanıyor → `app.state`'e yazan bir test/çağrı bunlar tarafından görülmez
- Global mutable state + `uvicorn --workers>1` = her worker farklı grid

**✅ DÜZELTİLDİ.** Modül seviyesindeki `_grids` global'i tamamen kaldırıldı;
`_set_grids()` / `_current_grids()` üzerinden tek kaynak `app.state.grids`.

**Önceki öneri:** Tek kaynak — `app.state.grids`. `_get_grids`'i `_active_grids`'e indirge.

---

### #8 — Aynı maliyet formülünün iki bağımsız implementasyonu

**Yer:** [`app/cost_engine.py:301-351`](backend/app/cost_engine.py#L301-L351) (`compute_cost_grid`, `ndenumerate` döngüsü) vs [`app/costmap.py:64-73`](backend/app/costmap.py#L64-L73) (`CostMap.total`, `np.vectorize`)

**Şu an sonuçlar birebir aynı** (doğruladım — bu iyi haber):
```
inf-pattern identical : True
max abs diff on finite: 0.0
allclose              : True
```

Ama iki ayrı kod yolu, aynı formül. Biri değişip diğeri değişmezse planlayıcı ile
`explain()` (yani "neden bu rota?" cevabı) sessizce ayrışır — kullanıcıya gösterilen
gerekçe gerçek maliyetle uyuşmaz. Fiziksel bir eşitlik testi yok.

Ayrıca ikisi de yavaş: `compute_cost_grid` 1.32 s, `CostMap.total` 1.54 s (500×500).
`np.vectorize` gerçek vektörizasyon değil, Python döngüsünün etrafındaki bir sarmalayıcı.

**✅ DÜZELTİLDİ.** `app/cost_vec.py` eklendi (gerçek NumPy dizi formları) ve her
iki yol da oraya bağlandı. Skaler formlar referans olarak kaldı; testler
13.000+ örnek üzerinde 4 rover için birebir eşitliği doğruluyor.
`compute_cost_grid` 7.31 s → 0.129 s.

> Not: vektörizasyon sırasında `cos`'un formülde **kare** girdiği gözden kaçtı
> ve eşitlik testi bunu anında yakaladı — testin değeri hemen görüldü.

**Önceki öneri:** Kısa vadede iki yolun eşitliğini doğrulayan bir test ekle (#8'in bugüne kadar
fark edilmemesinin tek sebebi şans). Orta vadede tek implementasyona indir ve gerçekten
vektörize et (`math.exp` → `np.exp`), ~50× hızlanma beklenir.

---

## 🟡 ORTA

### #9 — `/api/layers` `downsample` doğrulanmıyor: 500 ve sessiz grid çevirme

**Yer:** [`app/main.py:803-805`](backend/app/main.py#L803-L805)

```
downsample=  0 -> ValueError: slice step cannot be zero    -> yakalanmıyor -> HTTP 500
downsample= -1 -> shape (4, 5)   <-- grid sessizce ters çevrildi
downsample= -2 -> shape (2, 3)   <-- ters + seyreltilmiş
```

Negatif değer hata vermiyor, **yanlış yönde bir harita** döndürüyor. Ayrıca
`downsample=1` ile `cost` katmanı ~5.1 MB JSON üretiyor (limit yok).

**✅ DÜZELTİLDİ.** `Query(1, ge=1, le=50)` uygulandı; 0 ve negatif değerler 422.

### #10 — `/api/plan-multi` ve `/api/compare` start/goal doğrulaması yok

**Yer:** [`app/main.py:697-729`](backend/app/main.py#L697-L729), [`app/main.py:732-756`](backend/app/main.py#L732-L756)

`start: list[int]` — uzunluk kısıtı yok, `tuple(req.start)` doğrudan `astar`'a gidiyor.

```
start=(1, 2, 3)   -> RAISES IndexError: too many indices for array   -> HTTP 500
start=(999, 999)  -> error='Start out of bounds'                     -> düzgün
start=(-1, -1)    -> error='Start out of bounds'                     -> düzgün
```

`/api/plan` bu doğrulamayı yapıyor (422 döndürüyor), bu iki endpoint yapmıyor.

**✅ DÜZELTİLDİ.** `PixelPair = conlist(int, min_length=2, max_length=2)` her iki
endpoint'e uygulandı; hatalı uzunluk 422.

**Önceki öneri:** `conlist(int, min_length=2, max_length=2)` + `/api/plan`'daki sınır kontrolünü paylaş.

### #11 — `pixel_to_lonlat`'ın `-80°` koruması yakalanmıyor → 500

**Yer:** [`app/serializer.py:94-99`](backend/app/serializer.py#L94-L99), çağrı [`app/main.py:412-424`](backend/app/main.py#L412-L424)

`ValueError` fırlatıyor, `build_plan_response` `except Exception` ile yakalayıp
`500 Internal serialization error` veriyor. Aslında bu bir **girdi/konfigürasyon** hatası (422).

**Mevcut grid'de tetiklenmiyor** (doğruladım — en kuzey köşe -89.45°, eşik -80°), yani
şimdilik latent. Kutup dışı bir DEM yüklenirse tüm `/api/plan` çağrıları 500 verir ve
mesaj gerçek sebebi gizler.

Hiçbir test bu korumayı kapsamıyordu.

**✅ DÜZELTİLDİ.** `/api/plan` artık `ValueError`'ı ayrı yakalayıp 422 + gerçek
sebebi döndürüyor. Kutupsal grid hâlâ 200.

### #12 — `apply_sensor_overhead_to_summary` `min_battery_pct`'i güncellemiyor *(kendi Faz 5 kodum)*

**Yer:** [`app/sensor_payload.py:38-59`](backend/app/sensor_payload.py#L38-L59)

Fonksiyon `total_energy_consumed_wh` ve `final_battery_pct`'i düzeltiyor ama
`min_battery_pct` dokunulmadan geçiyor. Sonuç: `min_battery_pct < final_battery_pct`
olabilir — mantıksal olarak imkânsız bir özet (minimum, sondan büyük olamaz).

`risk_level` sayaçları (`critical_steps_count` vb.) da eski batarya eğrisine ait.

**✅ DÜZELTİLDİ.** `min_battery_pct` aynı kaydırmayı alıyor (sıfırda kesiliyor),
bayat risk sayaçları `None` yapılıp `risk_counts_valid: False` ekleniyor.
Yüksüz rover için özet aynen geçiyor.

### #13 — `simulate_path`'te ışınlanan yeniden şarj

**Yer:** [`app/simulation.py:150-154`](backend/app/simulation.py#L150-L154)

```python
if i > 0 and battery_wh <= 0.0:
    battery_wh = battery_capacity_wh      # anında %100
    recharge_count += 1
```

Batarya bitince **anında ve yerinde** tam dolum: süre geçmiyor, güneş şartı aranmıyor,
konum değişmiyor. Gölgedeki bir hücrede bile oluyor. `total_elapsed_hours` artmıyor,
dolayısıyla `sensor_overhead_wh` (#12) de bu süreyi görmüyor.

Bu bir "sonsuz enerji" kaçağı — rota fizibilitesini olduğundan iyi gösterir.

**✅ DÜZELTİLDİ.** Şarj artık hücrenin gerçek güneş girdisiyle sınırlı
(`p_solar_w × (1-shadow)` eksi idle/ısıtıcı) ve **süre maliyeti** var:
`elapsed_hours` şarj kadar ilerliyor. Kullanılabilir güneş yoksa şarj olmuyor —
rover %0'da kalıyor. Ölçüldü: karanlıkta 0 şarj, aydınlıkta 6.

**Önceki öneri:** En azından `p_solar_w` ve `shadow_ratio`'ya bağlı bir şarj süresi ekle; ya da
şarjı reddedip rotayı "enerji yetersiz" olarak işaretle. Hangisi olursa olsun, mevcut
davranış response'ta açıkça belirtilmeli.

### #14 — `generate_thermal_grid`'in gölge proxy'si sadece kuzey komşuya bakıyor

**Yer:** [`app/thermal_grid.py:38-43`](backend/app/thermal_grid.py#L38-L43)

```python
height_diff[1:, :] = elevation_grid[:-1, :] - elevation_grid[1:, :]   # yalnızca kuzey
```

- Doğu/batı/güneydeki bir sırt **hiç gölge yapmıyor**
- Satır 0 yapısal olarak hiç gölge cezası almıyor (`height_diff[0,:]` hiç yazılmıyor)
- Docstring "Sun at ~1.5° above horizon" diyor ama kodda güneş yüksekliği hiç kullanılmıyor

**Kanıt:**
```
elevation: satır 0'da 100 m'lik sırt, gerisi düz
thermal:   [[  80.  80.  80.  80.]     <-- sırdın kendisi, ceza 0
            [-210. -210. -210. -210.]   <-- sadece hemen güneyi cezalı
            [-180. -180. -180. -180.]
            [-180. -180. -180. -180.]]
```

**✅ DÜZELTİLDİ.** Gölge proxy'si 8-komşuluktaki en büyük yükselmeye bakıyor;
artık doğu/batı/güney sırtları da gölge yapıyor ve satır 0 muaf değil.
Docstring'deki gerçekleşmeyen "Sun at ~1.5°" iddiası da düzeltildi.

**Hafifletici:** Bu grid `layer_validity: SYNTHETIC` olarak işaretli ve gerçek hat
`horizon.py` + SPICE kullanıyor. Yani dürüstlük etiketi doğru. Yine de `/api/load-dem`
yolu bunu üretiyor ve rota planlamada kullanılıyor.

### #15 — CORS: `allow_origins=["*"]` + `allow_credentials=True`

**Yer:** [`app/main.py:56-62`](backend/app/main.py#L56-L62)

**Kanıt (canlı istek):**
```
access-control-allow-origin: *
access-control-allow-credentials: true
```

Bu kombinasyon spec dışı ve tarayıcılar genelde reddeder — ama Starlette bazı yollarda
Origin'i yankılar, o zaman "herhangi bir origin, kimlik bilgisiyle" anlamına gelir.
Şu an kimlik doğrulama yok, o yüzden istismar edilebilir bir şey yok; ama auth eklendiği
gün bu doğrudan bir CSRF kapısı olur.

**✅ DÜZELTİLDİ.** Wildcard origin ile `allow_credentials` artık ilan edilmiyor.
`LUNAPATH_CORS_ORIGINS` ortam değişkeniyle origin listesi verilirse credentials
otomatik açılıyor.

---

## 🔵 DÜŞÜK

### #16 — Ölü kod: `pathfinder._OFFSETS` / `_CELL_M` / `_DIAG_M` hiç kullanılmıyor

**Yer:** [`app/pathfinder.py:35-49`](backend/app/pathfinder.py#L35-L49)

Modül seviyesindeki `_OFFSETS` yerel `offsets` tarafından gölgeleniyordu ve
`_CELL_M = 80.0` sabiti **gerçek grid 5.0 m** iken 80 m diyordu.

**✅ DÜZELTİLDİ.** Üçü de silindi.

### #17 — `_cache_key` DEM içeriğini ve dizini yok sayıyor, çözünürlüğü `int()` ile kırpıyor

**Yer:** [`app/data_loader.py:243-251`](backend/app/data_loader.py#L243-L251)

```
same basename, different dirs collide:
   /a/dem.tif -> dem_80m_fabb4bff
   /b/dem.tif -> dem_80m_fabb4bff      <-- aynı anahtar, farklı dosya

resolution truncation:
   80.0 -> dem_80m_fabb4bff
   80.9 -> dem_80m_fabb4bff            <-- aynı anahtar, farklı çözünürlük
   80.4 -> dem_80m_fabb4bff
```

Aynı isimli farklı DEM'ler birbirinin cache'ini okuyordu.

**✅ DÜZELTİLDİ.** Anahtar artık tam yol + `size` + `mtime_ns` + kırpılmamış
çözünürlük + `COST_MODEL_ID` üzerinden SHA-256. Çakışmalar bitti.

### #18 — 65 test pytest'ten dışlanmış, CI yok

**Yer:** [`backend/pytest.ini`](backend/pytest.ini)

```ini
addopts = --ignore=test_cost_engine.py --ignore=test_traversability.py
```

Bu iki dosya `def test_*` içermiyor (0 sonuç); kendi `check()` harness'ları var ve
`sys.exit(1 if FAIL else 0)` ile bitiyor. Yani **42 + 23 = 65 test** yalnızca biri elle
`python test_cost_engine.py` çalıştırırsa koşuyor.

`.github/workflows` ve `.gitlab-ci.yml` yok — hiçbir otomatik doğrulama yok.

**✅ DÜZELTİLDİ.** `backend/test_legacy_harness.py` eklendi: iki harness'ı
subprocess olarak çalıştırıp çıkış kodunu assert ediyor (65 assertion suite'e
geri döndü, çalışan kod bozulmadan). `.gitlab-ci.yml` eklendi — backend suite ve
lunapath offline testleri her push/MR'da koşuyor.

### #19 — `@app.on_event("startup")` kullanımdan kaldırıldı

**Yer:** [`app/main.py:87`](backend/app/main.py#L87)

FastAPI 0.115'te deprecated'di.

**✅ DÜZELTİLDİ.** `@asynccontextmanager` tabanlı `_lifespan` handler'a taşındı.

### #20 — `bfs_move_count` içinde ölü kontrol

**Yer:** [`app/pathfinder_4d.py:73-74`](backend/app/pathfinder_4d.py#L73-L74)

```python
row, col = queue.popleft()
if (row, col) == goal:      # buraya asla ulaşılmaz
    return int(dist[row, col])
```

`start == goal` yukarıda ele alınıyor, hedef ise push anında işaretleniyor.

**✅ DÜZELTİLDİ.** Ölü kontrol kaldırıldı, hedef tespiti push tarafına alındı.
BFS davranışı testlerle doğrulandı (düz/çapraz/aynı hücre/duvar).

### #21 — `_slope_multiplier` negatif eğimde 1.0'ın altına iniyor

**Yer:** [`app/simulation.py:40-46`](backend/app/simulation.py#L40-L46)

```
slope -5.00 -> multiplier 0.7000     <-- yokuş aşağı "bedava enerji"
```

**Pratikte tetiklenmiyordu** — gerçek grid'de eğim hep pozitif (min 0.056°).

**✅ DÜZELTİLDİ.** `max(0.0, slope_deg)` ile kapatıldı.

---

## Doğruladığım ama sorun ÇIKMAYAN noktalar

Dürüstlük adına — şunları şüphelendim, test ettim, **temiz çıktılar**:

| Kontrol | Sonuç |
|---|---|
| `pathfinder` octile sezgiseli admissible mi? | ✅ Doğru formül, `h_scale = 1+min_cost` gerçekten alt sınır |
| `astar_4d` sezgiseli admissible mi? | ✅ `v_max_ms` bölen olarak alt sınırı koruyor |
| WAIT kenarı optimal mi seçiliyor? | ✅ Ucuz pencere gelene kadar 10 slice bekleyip geçti |
| `compute_cost_grid` vs `CostMap.total` | ✅ Birebir aynı (`max diff 0.0`) — ama #8'e bak |
| `grids_for_rover` rover adaptasyonu | ✅ VIPER için 206028 → 112266 hücre, doğru daralma |
| `pixel_to_lonlat` / `map_xy_to_pixel` yön uzlaşımı | ✅ Satır çıkarma tutarlı, Faz 2 C2 düzeltmesi yerinde |
| Gerçek grid'de NaN var mı? | ✅ Yok (slope/thermal/shadow: 0 NaN) |
| Faz 5 regresyonu | ✅ 263 + 42 + 23 + 10 test geçiyor |

---

## Önerilen fix sırası

**Aşama 1 — güvenlik ve doğruluk (fix'e buradan başlanmalı)**
1. #3 path traversal — küçük, izole, hemen kapatılır
2. #2 traversable maske güveni — güvenlik sınırı
3. #1 `f_energy` normalizasyonu — **en büyük iş**, ağırlık rekalibrasyonu gerektirir

**Aşama 2 — dayanıklılık**
4. #4 fail-open tetikleyiciler
5. #6 4D bellek cap'i
6. #9, #10 girdi doğrulama (küçük, hızlı)

**Aşama 3 — performans ve bakım**
7. #5 çift maliyet hesabı (~%40 istek süresi kazancı)
8. #7 tek grid kaynağı
9. #8 eşitlik testi + tek implementasyon
10. #18 CI + dışlanan testler

**Aşama 4 — temizlik**
11. #11–#17, #19–#21

---

## Notlar

- Bu bir *bağımsız* inceleme: kodun kendi yorumlarındaki "Faz N review" bulgularını
  doğru kabul etmedim, yeniden test ettim. Çoğu gerçekten düzeltilmiş durumda.
- Kod kalitesi genel olarak **yüksek**: yorumlar neden-odaklı, geçmiş hatalar
  belgelenmiş, `layer_validity` provenance takibi dürüst bir tasarım.
- En büyük sistemik risk teknik değil, **süreçsel**: CI olmaması (#18) yüzünden
  #1 gibi bir bulgu aylarca fark edilmeden durabiliyor.
