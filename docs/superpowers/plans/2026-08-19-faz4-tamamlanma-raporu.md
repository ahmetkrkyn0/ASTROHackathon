# Faz 4 Tamamlanma Raporu

**Tarih:** 29 Ağustos 2026
**Branch:** `backend/physics`
**Plan:** [`2026-08-19-faz4-ros2.md`](2026-08-19-faz4-ros2.md)
**Master plan:** [`2026-08-19-lunapath-master-plan.md`](2026-08-19-lunapath-master-plan.md)
**Commit aralığı:** `daf4039..e33a873` (16 commit)

---

## Özet

Branch `backend/physics`'te kalıyor, hiçbir entegrasyon (merge/PR) yapılmadı — kullanıcı kararı.

**16 commit**, 8 görev (subagent-driven-development akışıyla, her biri fresh implementer + bağımsız task reviewer) + final whole-branch review'un tek fix dalgası + 2 plan-metni düzeltme commit'i. Son test suite: **245 pytest + 42 `test_cost_engine.py` + 23 `test_traversability.py` + 9 `colcon test` (ROS tarafı) — tümü yeşil.**

Görevlerden önce planın kendisi yeniden gözden geçirildi: araştırma dosyalarına ve o an gerçek olan koda karşı 13 bulgu (R1-R13) düzeltildi, görev sayısı 7'den 8'e çıktı (bkz. plan dosyasının "Revizyon notu" bölümü).

---

## En önemli sonuç

LunaPath'in planlama çekirdeği artık **iki bağımsız kabuktan** servis ediliyor — mevcut FastAPI ve yeni ROS 2 action server — ve ikisi de **aynı** `backend/app/` çekirdeğini çağırıyor, hiçbiri diğerinin yerine geçmiyor. Bunu iddia etmekle yetinilmedi:

- **Piksel ⇄ harita çerçevesi dönüşümü tek bir yerde yaşıyor** (`backend/app/grid_frame.py`). Faz 2'nin C2 bulgusu — aynı formülün üç kopyasının birbirinden kayması, canlı API'de 1.23 km sapma — bu fazda dördüncü bir kopya açılarak tekrarlanmadı; `corridor.py` yeni modüle delege ediyor.
- **Planın tek büyük açık riski kapatıldı.** `grid_map`'in eksen-ters indis konvansiyonu (K3: transpoze + çevirme, sadece column-major flatten değil) kağıt üzerinde türetilmişti, ortamda ROS kurulu değilken. Bu oturumda gerçek ROS 2 Jazzy kuruldu ve K3/K4 türetmesi **gerçek, bağımsız implementasyonlu C++ `grid_map_ros` kütüphanesine karşı** doğrulandı (kendi kendine tutarlı Python testlerine karşı değil) — `grid_map_visualization`'ın gerçek `GridMapRosConverter::toPointCloud`'u üzerinden 3 pikselde tam eşleşme (dx=dy=dz=0.0000), transpoze hatasını yakalayacak şekilde seçilmiş asimetrik piksellerle.
- **Çekirdek gerçekten ROS'suz.** `backend/app/` altında hiçbir dosya `rclpy` ya da `*_msgs` import etmiyor — doğrudan import satırlarına bakan bir grep ile doğrulandı (docstring'lerdeki mesaj tipi isimlerinden ayrıştırılarak).
- **Nav2 hata kodu semantiği birebir.** `lunapath_msgs/action/PlanTraverse`'ın 10 hata kodu, kurulu Nav2'nin `ComputePathToPose`'una karşı `diff` ile doğrulandı — fark yok.

---

## Görev sırasında bulunan plan-metni hataları (3)

Plan bu fazdan önce hiçbir zaman gerçek bir ROS kurulumuna karşı test edilmemişti. Implementer'lar gerçek ortama karşı çalışırken üç gerçek hata buldu, hepsi koda **ve** plan metnine yansıtıldı:

1. **`GridMapInfo.header` alanı yok.** Planın `conversions.py` örneği bu alana atama yapıyordu; kurulu Jazzy'nin `grid_map_msgs`'inde `GridMapInfo`'nun kendi header'ı yok, yalnızca dıştaki `GridMap` mesajının var.
2. **`record_plan.sh`'ın action topic isimleri yanlıştı.** `/plan_traverse/_action/goal` ve `.../result` diye kaydedilmeye çalışılan isimler gerçek bir ROS 2 action server'da hiç var olmuyor — goal gönderme/result alma iki **servis** (`send_goal`, `get_result`); onları kaydetmek `planner_node.py`'de service introspection açmayı gerektiriyor (bu fazın kapsamı dışına not düşüldü). `feedback`/`status` gerçek topic ama alt-çizgi öneki yüzünden gizli, `--include-hidden-topics` gerekiyor.
3. **`PlanMetrics.msg`'de eksik alan.** Görev 3'ün brief'i incelenirken (dispatch öncesi), `high_or_above_steps_count`'un `summarize_simulation()`'ın gerçek çıktısında olduğu ama planın mesaj tanımında unutulduğu fark edildi — R6 revizyonunun önlemeye çalıştığı tam olarak bu sınıf hataydı.

---

## Final whole-branch review'da bulunan 2 bulgu

Sekiz görevin hiçbiri tek başına yakalayamadı — ikisi de görevler arası "dikiş yerlerinde" saklıydı:

### H1 — ROS kabuğu rover'a özgü grid uyarlamasını hiç yapmıyordu

FastAPI kabuğu (`main.py`) her plan isteğinde `_grids_for_rover()` çağırıyor: rover'ın `slope_max_deg`'ine göre traversability maskesini ve maliyet grid'ini yeniden hesaplıyor. `planner_node.py` bunu hiç çağırmıyordu — sunucu başlangıcında yüklenen varsayılan-rover grid'lerini kullanıyordu. Sonuç: `nasa_viper`/`cnsa_yutu_2` gibi daha düşük eğim limitli bir rover için 20-25° bandındaki bir hücre yanlışlıkla geçilebilir sayılıyor, `START_OCCUPIED`/`GOAL_OCCUPIED` yerine `NO_VALID_PATH` dönüyor, ve `Corridor.half_width_m` gerçekte olduğundan geniş bir güvenlik payı iddia ediyordu.

Kök neden aynı zamanda bir mimari ihlaldi: `_grids_for_rover` iki kabuğun da ihtiyaç duyduğu iş mantığıydı ama FastAPI kabuğunun dosyasında (`main.py`) yaşıyordu. Düzeltme: mantık `backend/app/rover_grids.py`'ye (saf çekirdek) taşındı, her iki kabuk da oradan çağırıyor. Gerçek doğrulama: `git stash` ile eski/yeni davranış A/B karşılaştırıldı — aynı istek eskiden `error_code=208`, düzeltmeden sonra doğru `error_code=205` dönüyor.

### M2 — `ros2 launch` PYTHONPATH olmadan çalışmıyordu

Launch dosyası tek-komut giriş noktası olması gerekirken, operatörün elle `export PYTHONPATH=...` yapmasını gerektiriyordu. Düzeltme: launch dosyası artık `backend/`'i kendi konumundan yukarı doğru arayıp `AppendEnvironmentVariable` ile PYTHONPATH'e ekliyor (`LUNAPATH_BACKEND_DIR` ortam değişkeniyle geçersiz kılınabilir). Gerçek, önceden `PYTHONPATH` set edilmemiş temiz bir WSL kabuğunda doğrulandı.

İkisi de tek bir fix dalgasında düzeltildi, tek bir scoped re-review ile onaylandı — yeni Critical/Important bulgu çıkmadı.

---

## Verilen kararlar (Rulings)

Otonom ilerlerken kullanıcı adına verilen önemli kararlar:

1. **Worktree yerine doğrudan `backend/physics`'te çalışma** — kullanıcı tercihi, izole workspace istemedi.
2. **ROS 2 Jazzy'nin WSL2'ye kurulumu** — Docker yerine WSL2 Ubuntu-24.04 seçildi (kullanıcı tercihi); `sudo` şifresi bu oturumdan girilemediği için kurulum komutları kullanıcıya verildi, kurulum bitince arka planda otomatik algılandı.
3. **Görev sırası: Task 2, Task 1'den önce** — Task 1 (ROS paket iskeleti) kurulumun bitmesini beklerken, Task 2 (`grid_frame.py`, saf Python, ROS bağımsız) hiçbir bağımlılığı olmadığı için öne alındı.
4. **`_grids_for_rover` mimari kararı** — final review'un H1 bulgusunu çözerken, mantığı `main.py`'den ayrı bir çekirdek modülüne (`rover_grids.py`) çıkarmak, sadece `planner_node.py`'ye kopyalamaktan tercih edildi — Global Constraint'in "iş mantığı çekirdekte kalır" kuralına uygun.
5. **Final review fix dalgasının kapsamı** — reviewer'ın "before merge" dediği yalnızca H1 ve M2 fix dalgasına alındı; M3-M5 ve L1-L7 (RViz path topic'i yok, pose frame_id doğrulanmıyor, grid_publisher gereksiz yeniden yayın, vb.) kayıtlı borç olarak bırakıldı — hiçbiri davranışı bugün yanlış yapmıyor.
6. **Branch entegrasyonu** — final review ve fix dalgası temiz bittikten, tüm test suite'leri (245+42+23+9) yeşil olduktan sonra kullanıcıya seçenek sunuldu; branch'i olduğu gibi bırakma seçildi.

---

## Kullanıcıya kalan (flag edilen, düzeltilmeyen)

Final review'un "follow-up, engelleyici değil" dediği bulgular:

- **RViz'de rota görünmüyor** — `nav_msgs/Path`, sürekli bir topic değil, action Result'ın bir parçası; RViz config'indeki Path display'in bağlanacağı bir topic yok. Faz 5'in yerel katmanı sürekli bir koridora ihtiyaç duyarsa çözülmeli.
- **Gelen pose'un `header.frame_id`'si doğrulanmıyor** — `moon_map` dışında bir çerçevede gönderilen bir pose sessizce yanlış yorumlanıyor. `map`→`moon_map` birim dönüşüm olduğu için bugün zararsız.
- **`cancel_callback` ACCEPT dönüyor ama hiç onurlandırılmıyor** — `is_cancel_requested` hiç kontrol edilmiyor.
- **`grid_publisher`, ~7 MB'lık mesajı 5 saniyede bir gereksiz yeniden yayınlıyor** — TRANSIENT_LOCAL zaten geç gelen abonelere veriyor; timer'ın kendisi gereksiz.
- **Eşzamanlı goal limiti yok** — her goal kendi 500×500 maliyet grid'ini hesaplıyor, backpressure yok.
- **Kabul kriterindeki `grep` komutu yanlış pozitif veriyor** — docstring'lerdeki mesaj tipi isimlerini eşleştiriyor; `^\s*(from|import)` + `--include=*.py` ile daraltılmalı.
- **`nav2_baseline.py` her çalıştırmada çıktı dosyasını komple eziyor** — elle eklenen H4 analiz paragrafı bir sonraki script çalıştırmasında sessizce kaybolur.
- Task-seviyesi review'larda park edilen küçük bulgular (test'lerin bir kısmında zayıf assertion'lar, `_geometry`'nin shape doğrulaması eksik, vb.) — ledger'da kayıtlı, kod sağlığını etkilemiyor.

---

## Sayılar

| Metrik | Değer |
|---|---|
| Toplam commit (`daf4039..e33a873`) | 16 |
| Görev sayısı | 8 (+ final review fix dalgası + 2 plan-metni düzeltme commit'i) |
| Fix round sayısı | Task 6: 1, Final review: 1 |
| Son pytest sonucu (`backend/`) | 245 passed |
| `test_cost_engine.py` | 42/42 PASS |
| `test_traversability.py` | 23/23 PASS |
| `colcon test --packages-select lunapath_ros` | 9/9 PASS |
| Kritik bulgu (task-level) | 0 |
| Önemli bulgu (final review) | 2 (H1, M2 — ikisi de düzeltildi, gerçek ROS ortamında doğrulandı) |
| Plan metninde bulunup düzeltilen hata | 3 (GridMapInfo.header, record_plan.sh topic isimleri, PlanMetrics eksik alan) |
| K3/K4 gerçek `grid_map_ros`'a karşı doğrulandı mı | Evet — 3/3 piksel tam eşleşme |

---

## Sonraki adım

Faz 5 — [`2026-08-19-faz5-lidar.md`](2026-08-19-faz5-lidar.md) · Faz 4 ile **paralel yürütülebilir** (ikisi de yalnızca Faz 2'nin `Corridor` şemasına bağlı). Faz 4'ün bıraktığı takip notları (RViz path topic'i, `_grids_for_rover` testi, frame_id doğrulaması) Faz 5 planlanırken göz önünde bulundurulmalı.
