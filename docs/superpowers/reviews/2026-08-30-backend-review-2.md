# Backend Bağımsız Review — 2. Tur (Faz 6 + Faz 7 sonrası)

**Tarih:** 30 Ağustos 2026 (gece) · **Branch:** `backend/physics` @ `89a44b7`
**Kapsam:** `backend/app/` (33 modül), `scripts/` (4), `lunapath_ros/` + `lunapath_msgs/` (tümü), test dosyaları
**Baseline:** 467 test yeşil

## Yöntem — bu review nasıl yapıldı

1. **Bağımsız reviewer:** Kodu yazmamış, sıfır bağlamla başlayan ayrı bir ajan tüm kapsamı satır satır okudu. Talimatı düşmancaydı: docstring'ler doğrulanacak iddia, gerçek değil. Her çalıştırılabilir bulgu rapordan önce bir üretim script'iyle **reprodüke edildi** (10 repro script'i); ROS-tarafı bulgular çalıştırılamadığı için satır alıntılarıyla `STATIC` etiketli.
2. **İkinci doğrulama:** Bulguların 9'u (3 HIGH'ın tamamı + M-1, M-2, M-4, M-7, L-1, L-11) bu rapor yazılmadan önce **ayrıca benim tarafımdan bağımsız reprodüksiyonlarla** yeniden çalıştırıldı; dokuzunun dokuzu birebir doğrulandı. STATIC bulgular kod alıntılarıyla karşılaştırılarak teyit edildi.
3. İlk review'un (21 bulgu, hepsi kapatıldı) kapalı bulguları yeniden raporlanmadı; bir tanesinin düzeltmesinin **eksik** olduğu kanıtla gösterildi (H-1).

**Hiçbir bulgu henüz fixlenmedi** — bu rapor okunup öncelik verildikten sonra başlanacak.

**Toplam: 22 bulgu — 0 Kritik · 3 Yüksek · 8 Orta · 11 Düşük**

---

## YÜKSEK

### H-1 · NaN telemetri tüm tetikleyicileri sessizce geçiyor; `/api/pose`'u 500'lüyor
`app/replan_triggers.py:30-98` · `app/main.py` (`ReplanRequest.state`, `PoseRequest.state`) — **DOĞRULANDI (2×)**

Python istemcisinin doğal olarak ürettiği çıplak `NaN` JSON literal'i (`json.dumps(float("nan"))`) Starlette tarafından kabul ediliyor, `dict[str, float]` validasyonundan geçiyor. NaN ile her karşılaştırma False olduğundan **altı tetikleyicinin altısı da "evaluated + temiz" raporlanıyor, hiçbiri skipped'a düşmüyor**:

```
tüm-NaN telemetri → fired: []  skipped: []  evaluated: [6 tetikleyicinin hepsi]
POST /api/replan  → 200, "no replan trigger fired"  (actual_soc = NaN iken!)
POST /api/pose    → 500 (Starlette allow_nan=False ile trigger_state'i echo edemiyor)
```

Bu, ilk review'un #4 bulgusunun (fail-open) **eksik kapanmış** hâli: düzeltme eksik *anahtarları* yakalıyor, sonlu olmayan *değerleri* yakalamıyor. `pose.py` aynı tehlikeyi kendi dört float alanı için sınırda kapatmış — `state` sözlüğü için kapatan yok.
**Öneri:** `state` değerlerini sınırda doğrula: sonlu değilse reddet ya da ilgili tetikleyiciyi `skipped`'a `"non-finite value"` gerekçesiyle düşür. Tek fix hem fail-open'ı hem 500'ü kapatır.

### H-2 · `/api/compare`'ın "most_efficient_profile"ı sıfıra sabitlenmiş metrikle seçiliyor — kazanan liste sırası, gerekçe uydurma
`app/scenarios.py:131,139` · `app/pathfinder.py:379-380` — **DOĞRULANDI (2×)**

`_compute_path_metrics` her yol için `"total_energy_wh": 0.0  # Not tracked in fast mode` yazıyor; `compare_results` ise `min(..., key=total_energy_wh)` ile "en verimli" profili seçip **"X uses the least energy"** cümlesi üretiyor. Sıfırların min'i ilk elemandır:

```
aynı sonuçlar, sıra değişti → most_efficient: 'balanced' → 'shadow'
recommendation: "... balanced uses the least energy."
```

`total_shadow_hours` (o da sabit 0) "safest" sıralamasına giriyor. `compare_results` için hiçbir test yok. Dürüstlük disiplinini merkeze koyan bir projede sabit-sıfır metrikten enerji iddiası üretmek tam olarak `layer_validity`'nin önlemeye kurulduğu şey.
**Öneri:** Ya gerçek bir niceliğe sırala (profil başına `summarize_simulation` veya `total_weighted_cost`), ya alanı ve cümleyi kaldırıp "fast modda izlenmiyor" de.

### H-3 · Diviner doğrulaması referansı bir pencere boyu kuzeye kaydırıyor
`scripts/diviner_validation.py:90-92` — **DOĞRULANDI (2×)** · *Faz 6'da bu oturumda yazılan kod*

`metadata.origin.y` pencerenin **üst** kenarıdır (`pixel_to_map_xy(0,0) → y = origin.y`, satır satır teyitli). Script ise alt kenar sanıp `from_origin(x, origin.y + rows*res)` kuruyor — örnekleme penceresi tam pencere yüksekliği kadar (üretim grid'inde 2.5 km) kuzeye kayıyor:

```
script top-left y: 2000.0   doğrusu: 1000.0   (100 satırlık sentetik grid)
```

Gerçek Diviner dosyası geldiği an `misclassified_traversable_pct` dahil her sayı **yanlış araziye karşı, makul görünen büyüklüklerle, sessizce** hesaplanır. Task 4'teki sentetik uçtan-uca testin bunu yakalayamamasının sebebi de kayıtlı olsun: test referans raster'ını **aynı yanlış transformla** üretmişti — iki taraf aynı miktar kayınca karşılaştırma hizalı çıktı. Kendi kendine tutarlı yanlış test.
**Öneri:** `from_origin(origin.x, origin.y, ...)` (piksel-merkez kaydı istenirse ± yarım hücre); testte referansı **bağımsız** yoldan üret.

---

## ORTA

### M-1 · 4-D planlayıcı, 2-D'nin yasakladığı diyagonal köşe-kesmeye izin veriyor
`app/pathfinder_4d.py` (MOVE kenarları + `bfs_move_count`) vs `app/pathfinder.py:287-293` — **DOĞRULANDI (2×)**

2×2 damalı grid'de (yalnız diyagonal bağlı): 2-D A* "No path found", 4-D A* `[(0,0),(1,1)]` döndürüyor, `bfs_move_count` 1 sayıyor. Aynı üründe iki planlayıcı aynı güvenlik yüklemi hakkında çelişiyor; `scripts/nav2_baseline.py`'deki Dijkstra da aynı eksiği taşıyor (karşılaştırmayı baseline lehine, yani LunaPath iddiası aleyhine — muhafazakâr yönde — eğiyor).
**Öneri:** İki-komşu-kardinal kontrolünü 4-D MOVE kenarlarına ve `bfs_move_count`'a uygula (horizon boyutlandırma argümanının tutması için ikisi tutarlı kalmalı); baseline'a da yansıt.

### M-2 · `astar_metrics.max_thermal_risk` hangi rover istenirse istensin varsayılan rover'ın zarfıyla hesaplanıyor
`app/pathfinder.py:383-385` — **DOĞRULANDI (2×)**

`f_thermal(t)` çıplak çağrılıyor → `lpr_1` çözülüyor. `luvmi_m` için −60 °C konforlu (risk 0.0) iken yanıt 0.3304 raporluyor; `/api/compare` bunu "safest" sıralamasına sokuyor. Maliyet grid'leri rover'ı doğru alıyor — rota değil, **raporlama ve sıralama** yanlış.
**Öneri:** `_compute_path_metrics`'e rover'ı geçir (astar zaten tutuyor).

### M-3 · `PoseEstimate` NaN/inf `heading_deg` kabul ediyor — kendi NaN-sınır kuralının atladığı tek float alan
`app/pose.py:88-98` — **DOĞRULANDI** · *Faz 7 kodu*

`nan % 360 = nan`, `inf % 360 = nan` → sonlu olmayan heading **kabul edilip NaN olarak saklanıyor**, hem de "NaN sınırda kapatılır" diyen modülde. Bugün heading'i tüketen yok (bkz. L-10 notu), yani NaN "doğrulanmış" sözleşme nesnesinin içinde ilk tüketiciyi (güneş-pusula kontrolü) bekleyen sessiz fail-open.
**Öneri:** `heading_deg`'i sonlu-olmayan reddi validator'üne ekle (sarmadan önce).

### M-4 · Switchback rotada en-yakın-segment projeksiyonu: `slip_accumulation` yanlış ateşliyor, along-track ışınlanıyor
`app/localization.py` (global argmin) — **DOĞRULANDI (2×)** · *Faz 7 kodu*

Firkete dönüşlü rotada (Ay yamacı tırmanışının standart şekli) dönüş bacağındaki poz, kendi segmentinin koridoru İÇİNDEyken gidiş bacağına yakınsarsa oraya yapışıyor:

```
dönüş bacağı: seg 2, along 1030 m, offset 0
16 m içe drift: seg 0, along 200 m, offset 14 (inside!) → slip ratio 0.14 → FIRED
```

Slipsiz rover'a `replan` önerisi (ROS'ta yayınlanmış `ReplanTrigger`); `progress_fraction` yarı rota geri sıçrıyor. Yön fail-closed ama Faz 7 döngüsünün gerçekçi rota şeklinde yanlış cevabı. Testler yalnız bitişik-segment durumunu kapsıyor.
**Öneri:** İlerleme takibi (segment aramasını son bilinen segmentin penceresine daralt veya koridor genişliğinden büyük geri sıçramayı yasakla); asgari, sınırı belgele.

### M-5 · Slip tetikleyicisinin operatör mesajı karşılaştırdığı nicelikleri yanlış adlandırıyor
`app/slip_model.py` docstring + detail · tek üretim çağrısı `app/localization.py` — **STATIC, kod teyitli** · *Faz 7 kodu*

`commanded_m` parametresine, sözleşmenin "**komut edilen değil**, odometrinin kendi ölçümü" diye tanımladığı `distance_travelled_m` veriliyor; detail ise "X of Y m **commanded**" diyor — Y'yi kimse komut etmedi. Replan'ı gerekçelendiren kanıt cümlesi kendi girdilerini yanlış tanımlıyor.
**Öneri:** Parametreleri `map_progress_m` / `odometer_claim_m` yap ya da en azından detail + docstring'i "claim" diyecek şekilde düzelt.

### M-6 · `distance_travelled_m`'in epoch'u HTTP sözleşmesinde tanımsız — kümülatif odometri taze koridora karşı slip'i yanlış ateşler
`app/pose.py` alan açıklaması · `/api/pose` vs `pose_monitor.py:93-96` — **STATIC, kod teyitli** · *Faz 7 kodu*

ROS kabuğu integral sıfırlamayı açıkça yapıyor ("yeni koridor → `_travelled_m = 0`); HTTP sözleşmesi susuyor. Boot'tan-beri-kümülatif gönderen doğal istemci, rover'ın mevcut konumundan yeni planlanan koridora karşı `along_track ≈ 0 / büyük iddia` → slip fires → replan → tekrar sıfırlanan along-track → **döngü**. İki kabuk aynı alan için farklı sözleşme uyguluyor.
**Öneri:** Epoch'u alan açıklaması + endpoint docstring'ine yaz ("aktif koridorun başından beri; her planla sıfırla") ya da `/api/plan` koridor id döndürsün, pose onu echo etsin.

### M-7 · `min_battery_pct` batarya-bitti olaylarını gizliyor: 0'a düşüş, şarj-sonrası değerle eziliyor
`app/simulation.py:171-194, 253` — **DOĞRULANDI (2×)**

Şarj, `RoverState` kaydedilmeden önce koştuğu için bataryayı N kez bitiren rota `min_battery_pct: 100.0` raporlayabiliyor:

```
küçük batarya, her adım şarj → min_battery_pct: 100.0   total_recharges: 7
```

"Bataryaya ne kadar yaklaştık" sorusuna cevap veren tek özet alanı, tam da şarj molalı rotalarda tersini söylüyor.
**Öneri:** Şarj öncesi minimumu kaydet (tükenmiş değeri de kapsayan `min`, ya da şarjdan önce tükenmiş state'i yayınla).

### M-8 · Aynı yanıtta iki çelişen seyir-süresi modeli: simülasyon vs maliyet motoru ~1.6×'a kadar ayrışıyor
`app/simulation.py:152-158` vs `app/cost_engine.py:177-191` — **DOĞRULANDI, aritmetik teyitli**

`/api/plan` yanıtındaki koridorun `thermal_budget_K_s`'i motor modelini (`d/(v·cos²θ)`), özetin `total_elapsed_hours`'u simülasyon modelini (`max(0.2, 1−θ/50)`) entegre ediyor; 4-D saat de motoru kullanıyor:

| Eğim | motor t | sim t | oran |
|---|---|---|---|
| 10° | 25.78 s | 31.25 s | 1.21 |
| 20° | 28.31 s | 41.67 s | 1.47 |
| 24.9° | 30.39 s | 49.80 s | 1.64 |

Hangisinin otoriter olduğu hiçbir yerde yazmıyor.
**Öneri:** Tek kinematik model seç (üç tüketicisi olan motorunki makul aday) ve simülasyon adım süresini ondan türet; ya da ayrışmayı açıkça belgele.

---

## DÜŞÜK

### L-1 · `serializer` fallback origin'i kendi türetme yorumuyla 40 km çelişiyor
`app/serializer.py:24-29` — **DOĞRULANDI (2×).** Yorum C2-öncesi konvansiyonla türetilmiş; mevcut `y = origin − row·res` altında sabit, pencerenin ALT kenarı. Yalnız metadata'sız fallback yolu (üretimde kullanılmıyor) — latent. **Öneri:** `48000 + 250*80` olarak yeniden türet ya da fallback sabitlerini sil.

### L-2 · `slip_model`'in enerji/süre düzeltmeleri ölü kod; modül maliyet hattını beslediğini ima ediyor
`app/slip_model.py:71-88` — **DOĞRULANDI (grep).** `effective_distance_m` / `slip_energy_multiplier`'ı üretimde kimse çağırmıyor. Tamamlanma raporu bilinçli-bağlanmadı diye açıklıyor ama modülün kendisi söylemiyor. **Öneri:** Docstring'e tek cümle ("maliyet hattına bilinçli bağlanmadı; yalnız tetikleyici canlı").

### L-3 · SPICE kernel'leri her çağrıda yeniden `furnsh` ediliyor
`app/ephemeris.py` + `app/skyline.py` — **STATIC.** `sun_track(N)` meta-kernel'i N+1 kez yüklüyor; uzun süreli süreçte CSPICE kernel-limit hatasına birikir. **Öneri:** Süreç başına bir kez (`_loaded` set'i veya `ktotal` kontrolü).

### L-4 · Aynı "grid yüklü değil" durumu bazı endpoint'lerde 400, bazılarında 503
`app/main.py` (`_get_grids` vs `_active_grids`) — **STATIC.** İlk review #7 depoyu birleştirdi, durum sözleşmesini birleştirmedi. **Öneri:** `_get_grids`'i 503'e katla.

### L-5 · `load_scenario_endpoint` grid yüklemeyi sessizce atlayabiliyor; bozuk DEM'de 500
`app/main.py:1007-1023` — **STATIC.** `dem_file` yoksa 200 + hiçbir şey yüklenmedi; `load_and_preprocess_dem` sarılmamış. **Öneri:** `{"status": "loaded"|"dem_missing"}` + `/api/load-dem`'in hata eşlemesi.

### L-6 · Aktif koridorun kimliği yok: yanıt tamamlanmadan atanıyor, eşzamanlı planlar sessizce eziyor
`app/main.py` — **STATIC** · *Faz 7 kodu.* Serileştirmesi başarısız olan plan bile koridoru değiştirir; iki eşzamanlı `/api/plan` tek slot için yarışır; `/api/pose` hangi plana karşı yargıladığını söylemez. **Öneri:** Atamayı yanıt kurulduktan sonraya al; `/api/plan` + `/api/pose`'da koridor kimliği (timestamp + rover_id) echo'la.

### L-7 · `evaluate_pose` pozu koridora çağrı başına iki kez projekte ediyor
`app/localization.py` — **STATIC** · *Faz 7 kodu.* `project_onto_corridor` + `trigger_state_from_pose` içindeki ikinci çağrı: odometri frekansında 2× maliyet + ıraksama riski. **Öneri:** fix'i parametreyle geçir.

### L-8 · Slip kontrolü koşmadığında ne `evaluated` ne `skipped`'da görünüyor
`app/localization.py` — **STATIC** · *Faz 7 kodu.* Mutlak fix / sıfır mesafede "kontrol edildi-temiz" ile "kontrol edilemedi" ayrımı kayboluyor — #4'ün tam korumaya çalıştığı ayrım. **Öneri:** Koşmadığında `skipped`'a gerekçeyle ekle.

### L-9 · Gözlenen skyline'daki tek NaN bin tüm eşleşmeyi öldürüyor, boş arama uzayından ayırt edilemez biçimde
`app/skyline.py:125-142` — **DOĞRULANDI** · *Faz 7 kodu.* Kısmen kapanmış ufuk (mast/lander görüşte — gerçekçi çekim) eşlenemez oluyor; `None` "arama uzayı boş" anlamına da geliyor. **Öneri:** NaN bin'leri SSD'den maskele (geçerli bin sayısına normalize) ya da ayrı hata türü.

### L-10 · `/api/cell-telemetry`'de `rover_id` parametresi yok — açıklama hep varsayılan rover'la
`app/main.py:382-425` — **STATIC.** `nasa_viper` için plan yapan frontend, hücre tooltip'lerini `lpr_1` ağırlıklarıyla görür. (İlgili not: `PoseEstimate.heading_deg` zorunlu alan ama kodda sıfır tüketicisi var.) **Öneri:** Opsiyonel `rover_id` + `grids_for_rover`.

### L-11 · `nav2_baseline.py`'nin varsayılan başlangıcı bilinen geçilemez hücre — parametresiz çağrı hep düşüyor
`scripts/nav2_baseline.py:102` — **DOĞRULANDI (2×).** Kardeş script'ler `(150,150)`'ye düzeltilmiş, bu `(100,100)`'de kalmış. **Öneri:** `(150,150)`.

---

## Düşmanca yoklandı, temiz çıktı

`quaternion_to_grid_heading_deg` (ölçek-değişmezlik + pusula kimliği) · `grid_frame` dönüşümleri (kare-olmayan fixture dahil) · `horizon_map` ışın geometrisi · A* octile + 4-D saat sezgiselleri (kabul edilebilirlik) · `_resolve_dem_path` kaçış koruması (#3 fix) · `rover_grids` maske/maliyet güveni (#2/#5) · `evaluate_triggers_detailed` eksik-anahtar raporu (#4'ün anahtar yarısı) · şarjın güneş + saat gerektirmesi (#13) · segment-birleşiminde projeksiyon sürekliliği · `wait_cost` ölçeklemesi (M2) · `thermal_comparison` NaN/boş-kesişim yolları · `mission_reference` aritmetiği · `localization_budget` cebiri · `sensor_payload` kaydırması (#12).

## Özet

| Önem | Adet | Bugünkü (Faz 6+7) kodda |
|---|---|---|
| KRİTİK | 0 | — |
| YÜKSEK | 3 | 1 (H-3) |
| ORTA | 8 | 4 (M-3, M-4, M-5, M-6) |
| DÜŞÜK | 11 | 4 (L-2, L-7, L-8, L-9) |
| **Toplam** | **22** | **9** |

En yeni kod, bulguların 9'unu taşıyor — beklenen dağılım: en az review görmüş kod en çok bulguyu verir; bu review tam da o yüzden Faz 7'nin hemen ardına konuldu.

**Önerilen fix sırası:** H-1 → H-3 → H-2 → M-4/M-5/M-6 (üçü aynı slip hattı, birlikte ele alınmalı) → M-2 → M-7 → M-1 → M-8 → M-3 → LOW'lar.
