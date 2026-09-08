# LiDAR Algısı ile Yerel Engel Kaçınma Planı

**Durum:** Yazılım zinciri uygulandı; ROS 2/donanım doğrulaması bekliyor  
**Amaç:** Global rota, metre ölçekli kayaların konumunu önceden bilmeden
üretilsin. Rover, yalnızca LiDAR menzilinde gerçekten algıladığı engellere
tepki versin; güvenli küçük bir sapma yapabilsin veya gerekirse yeniden global
planlama istesin.

## 1. Hedef davranış

Bugünkü akışta 3B sahne, kayaları `Generate Route` öncesinde üretip
`obstacle_cells` olarak A* isteğine gönderiyor. Bu, simülasyon için görünürde
tutarlı olsa da roverın henüz görmediği kayalar hakkında global planlayıcıya
bilgi verir.

Hedef akış aşağıdaki gibi olmalı:

```text
DEM + görev kısıtları ──> global A* ──> global koridor / referans rota
                                                │
Rover pozu ──> LiDAR taraması ──> yerel işgal haritası
                                                │
                                  yerel kaçınma planı
                                                │
                         sürüş komutu / güvenli duruş / replan isteği
```

Bu mimaride LiDAR, yalnızca menzili içindeki ilk-dönüşlerden engel çıkarır.
Global rota, önceden üretilmiş kaya listesini veya sahne meshlerini asla
almaz. Algılanan bir engel, ilk kez görüldükten sonra yerel işgal haritasına
ve gerekirse yeniden-planlama isteğine girebilir.

## 2. Kapsam ve kararlar

### Dahil

- Global rota üretiminde kaya bilgisini kaldırmak.
- LiDAR nokta bulutundan, rover koordinat sisteminde yerel engel hücreleri
  üretmek.
- Global koridor içindeki kısa ufukta güvenli bir yerel sapma hesaplamak.
- Yerel sapma yoksa roverı durdurup algılanmış engellerle global replan
istemek.

## Uygulama durumu (başlangıç dilimi)

- [x] Global `/api/plan` içinden istemci tarafı `obstacle_cells` yolu kaldırıldı
  ve bu alan API sınırında reddediliyor.
- [x] LiDAR ilk-dönüşlerinden anonim yerel engel kümeleri ve rover-merkezli
  `unknown | free | occupied` grid üretiliyor.
- [x] Güven eşiği, bounded detour ve güvenli `STOP_AND_REPLAN` sonucu olan
  yerel karar çekirdeği eklendi; 3B LiDAR paneli gözlem/işgal/karar telemetrisi
  gösteriyor. Mevcut playback bu kararı henüz direksiyon komutuna çevirmiyor.
- [x] `/api/replan`, yalnızca önceden LiDAR tarafından gözlenmiş ve güveni
  yeterli engelleri kabul ediyor; ilk plan hâlâ bu veriyi kabul etmiyor.
- [x] `STOP_AND_REPLAN`, playback'i durdurur ve güveni yeterli gözlemleri
  otomatik olarak `/api/replan`'e yollar; yeni rota inceleme için yüklü ama
  otomatik olarak yeniden oynatılmaz.
- [x] `LOCAL_DETOUR` waypoint'leri playback'in yürütme izine eklenir; iz,
  bir sonraki global waypoint'te koridora yeniden bağlanır. Backend'in global
  planı ve onun enerji/risk özeti değiştirilmez; yürütülen yerel sapma açıkça
  istemci tarafı LiDAR yürütme izi olarak tutulur.
- [x] Yürütme izinin ROS karşılığı için güvenli varsayılanlı `LocalPlan` /
  `local_controller` köprüsü eklendi; denetleyici yalnızca yerel sapmayı
  sürer ve yeniden-planlama tetikleyicisinde durur.
- [ ] ROS içi yerel plan/replan yöneticisi ile ölçülen enerji/poz sonuçlarının
  plan özetiyle uzlaştırılması henüz tamamlanmamıştır.
- Simülasyondaki kaya meshlerini yalnızca LiDAR ve görselleştirme için
  kullanmak; planlayıcının gizli girdisi yapmamak.

### Hariç

- Gerçek LiDAR sürücüsü, SLAM veya gerçek zamanlı ROS hareket denetleyicisi.
- Algılanmamış kayalara karşı güvenlik iddiası.
- DEM'in 5 m çözünürlüğünde çözülemeyen kaya boyutları için global geçiş
  garantisi.

### İlk sürüm için tercih

Yerel planlayıcı, global rotanın yerine tüm haritada rota aramaz. Mevcut
rover pozundan, global rota üzerinde `lookahead` mesafesindeki güvenli alt
hedefe kadar arama yapar. Arama başarısızsa **dur + global replan** davranışı
verir. Bu yaklaşım, yerel kaçınmayı gerçekçi tutar ve global/local görevleri
ayırır.

### ROS köprüsü — güncel sınır

- [x] ROS sözleşmesine `ObservedObstacle`, `ObservedObstacles` ve `LocalPlan`
  eklendi. `local_controller`, yalnızca `LOCAL_DETOUR` waypoint'lerini kabul
  eder; replan/güvenlik tetikleyicisinde sıfır hız komutu verir ve varsayılan
  olarak kapalıdır (`enabled=false`).
- [x] `lidar_perception`, TF zinciri geçerliyse `PointCloud2` dönüşlerinden
  kaynak/mesh kimliği taşımayan `ObservedObstacles` kümeleri üretir; TF veya
  veri geçersizse yayınlamak yerine güvenli biçimde veriyi reddeder.
- [x] `local_planner`, koridor + odometri + taze LiDAR gözlemini kullanarak
  `FOLLOW` / `LOCAL_DETOUR` / `STOP_AND_REPLAN` üretir. Koridora sığmayan
  engelde `local_obstacle_blocked_corridor` replan tetikleyicisi yayınlar.
- [x] `replan_coordinator`, aktif görevi ve map-frame odometriyi saklar;
  `replan` tetikleyicisinde sadece taze LiDAR gözlemlerini yeni `PlanTraverse`
  isteğine ekler. Planlayıcı bunları global maske olarak yalnız replan sırasında
  uygular, yeni `global_path`/koridor yayınlar.
- [x] `execution_monitor`, ölçülen map-frame odometriyi ve `BatteryState`
  SOC'sini aktif planın mesafe/enerji/süre özetiyle `ExecutionStatus` üzerinde
  karşılaştırır. Eksik batarya verisini sıfır tüketim diye yorumlamaz.
- [ ] Tüm zincirin gerçek ROS 2 Jazzy + donanım ortamında TF, sensör, velocity
  mux ve motor sürücüsüyle uçtan uca doğrulanması eksiktir.

## 3. Uygulama fazları

### Faz 0 — Davranışı ve veri sahipliğini dondur

1. Arayüz ve demo metinlerini şu iddiaya çekin: “LiDAR algılanan yerel
   engeller için kaçınma/replan tetikler.”
2. `RockDescriptor` listesinin test fixture/sahne gerçeği olduğunu belgeleyin;
   rota planı girdisi olmadığını açıkça yazın.
3. Her engel kaydına `source` (`lidar`), `observed_at`, güven (`confidence`)
   ve koordinat çerçevesi ekleyin. Sahne tarafından bilinen gerçek mesh kimliği
   bu sözleşmede taşınmamalıdır.

### Faz 1 — Global planlama sızıntısını kaldır

1. `PlanRequest.obstacle_cells` alanını ve `planRoute(..., obstacleCells)`
   parametresini kaldırın. Geçiş gerekiyorsa önce deprecated yapın; sonraki
   sürümde API doğrulamasında reddedin.
2. `App.tsx` içindeki plan öncesi `generateRockField` çağrısını ve bunun
   `obstacle_cells`'e dönüşmesini kaldırın.
3. Kaya meshleri, rota oluşturulduktan sonra ve sadece aktif rover çevresindeki
   LiDAR penceresi için üretilebilsin. Deterministik dünya tohumu korunabilir;
   önemli kural, bu listenin global A* çağrısına ulaşmamasıdır.
4. `/api/plan` yalnızca DEM, rover kısıtları, maliyet ağırlıkları ve açıkça
   görev öncesi mevcut olduğu kanıtlanmış makro katmanlarla çalışsın.

### Faz 2 — LiDAR algısından yerel işgal haritası üret

1. LiDAR nokta bulutuna bir `perception` katmanı ekleyin:
   - zemin düzleminden yeterince yüksek noktaları aday engel seçmek,
   - komşu noktaları kümelendirmek,
   - minimum genişlik/yükseklik eşiğiyle mobilite engelini ayırmak,
   - ölçüm gürültüsünü güven skoruna yansıtmak.
2. Sonucu rover-merkezli, sabit çözünürlüklü bir `LocalOccupancyGrid` olarak
   tutun: `unknown | free | occupied` ve her hücre için güven/zaman damgası.
3. Haritayı odometriyle kaydırın; eski gözlemlerin güvenini azaltın. Bir
   LiDAR ilk dönüşü “engel” demek değildir: yalnızca sınıflandırma eşiğini
   geçen ve yeterli güvene ulaşan küme işgal hücresi olur.
4. Backend DEM LiDAR noktaları ile frontend kaya-mesh dönüşlerini aynı
   algı sözleşmesinde birleştirin. Planlayıcıya mesh veya gerçek kaya listesi
   değil, sadece bu algı sonucu verilir.

### Faz 3 — Yerel kaçınma planlayıcısı

1. Yeni bir saf çekirdek modül yazın: `local_planner.py` veya frontend
   simülasyonu için eşdeğer bağımsız TypeScript modülü. Girdi:
   `pose`, global koridorun ileri kesiti, `LocalOccupancyGrid`, rover çapı,
   emniyet payı, yerel DEM eğimi ve lookahead.
2. İşgal hücrelerini rover yarıçapı + emniyet payı kadar şişirin.
3. Bounded A*/D* Lite ile yalnızca yerel pencerede bir yol arayın. Maliyet:
   ilerleme, global koridordan sapma, eğim ve engel açıklığı. Çıktı:
   `FOLLOW`, `LOCAL_DETOUR`, `STOP_AND_REPLAN` veya `STOP_UNCERTAIN`.
4. Yerel rota, global koridoru terk etme sınırı ve azami sapma bütçesi
   taşısın. Bu sınırlar aşılırsa yerel plan “başarılı” sayılmaz; replan
   gerekir.
5. İlk sürümün hareket çıktısı direksiyon komutu değil, zaman damgalı yerel
   waypoint dizisi olsun. Böylece hareket denetleyicisi sonradan bağımsız
   entegre edilir.

### Faz 4 — Algılandıktan sonra global replan

1. `/api/replan` isteğine ham nokta bulutu yerine doğrulanmış
   `observed_obstacles` ekleyin: dünya/grid koordinatı, yarıçap, güven,
   gözlem zamanı ve kaynak.
2. Replan yalnızca güven eşiğini geçen, aktif zaman penceresindeki gözlemleri
   geçilemez/cezalı hücreye dönüştürsün. Böylece yeni global rota, öğrenilmiş
   engelleri bilir; henüz görülmemiş olanları bilmez.
3. `STOP_AND_REPLAN` kararı replan isteğini tetiklesin. Replan başarısızsa
   rover güvenli duruşta kalsın ve UI bunun “engelsiz yol bulundu” olmadığını
   açıkça göstersin.
4. Replan nedenine `local_obstacle_blocked_corridor` kimliğini ve gözlem
   özetini ekleyin; operatör bunun enerji/ısı tetikleyicisinden farklı olduğunu
   görebilsin.

### Faz 5 — UI, telemetri ve ROS köprüsü

1. 3B görünümde algılanmamış kayaları normal sahne öğesi olarak göstermeyin;
   LiDAR tarafından algılanan kümeyi ayrı “observed obstacle” işaretiyle
   gösterin. Demo modunda gerçek-kaya görünürlüğü gerekiyorsa bu, fiziksel
   gerçeklik değil simülasyon gerçeği olarak etiketlensin.
2. HUD'a şu durumları ekleyin: LiDAR menzili, algılanan engel sayısı, yerel
   plan durumu, koridordan sapma, en yakın engel ve replan gerekçesi.
3. ROS katmanında yeni bir `LocalPlan`/`ObservedObstacles` mesajı veya mevcut
   `ReplanTrigger` ayrıntısına referans ekleyin. `pose_monitor` yalnızca
   koridor takibi yapmaya devam etsin; engel algılama mantığı ona gizlice
   eklenmesin.

## 4. Önerilen API sözleşmesi

```ts
type ObservedObstacle = {
  x_m: number
  y_m: number
  radius_m: number
  confidence: number        // [0, 1]
  observed_at_s: number
  source: 'lidar'
}

type LocalPlanRequest = {
  pose: PoseEstimate
  corridor: Corridor
  occupancy: LocalOccupancyGrid
  lookahead_m: number
}

type LocalPlanResponse = {
  decision: 'FOLLOW' | 'LOCAL_DETOUR' | 'STOP_AND_REPLAN' | 'STOP_UNCERTAIN'
  waypoints: Array<{ x_m: number; y_m: number }>
  nearest_obstacle_m: number | null
  corridor_deviation_m: number
  reason: string
}
```

`POST /api/plan` içinde `obstacle_cells` bulunmayacak. `POST /api/replan`,
yalnızca `observed_obstacles` kabul edecek; istemci sunucuya sahne meshlerini,
rock ID'lerini veya tüm kaya alanını gönderemeyecek.

## 5. Kabul kriterleri ve testler

1. **Sızıntı yok:** Global plan HTTP gövdesinde kaya/engel listesi yoktur.
   Rota öncesi üretilen ya da LiDAR menzili dışındaki bir kaya, ilk global rota
   geometrisini değiştiremez.
2. **Algı nedenselliği:** Bir kaya, ancak LiDAR menziline girip yeterli sayıda
   tutarlı dönüş ürettikten sonra `occupied` olur.
3. **Yerel kaçınma:** Koridoru kısmen kapatan algılanmış kaya, belirtilen
   emniyet açıklığını koruyan kısa bir yerel sapmaya yol açar.
4. **Güvenli başarısızlık:** Yerel pencere kapalıysa rover durur ve tek bir
   engel-kaynaklı replan isteği oluşur; engelin içinden rota çizilmez.
5. **Öğrenilmiş replan:** Replan sonrası global rota algılanmış engeli
   kullanabilir, ancak henüz gözlenmemiş başka bir kaya yüzünden değişmez.
6. **Provenance:** Her UI/telemetri çıktısı, engelin `LiDAR-observed` mi yoksa
   DEM kaynaklı makro kısıt mı olduğunu ayırt eder.
7. **Regresyon:** Mevcut DEM/eğim/termal kısıt testleri, `obstacle_cells`
   kaldırıldığında aynı sonuçları verir. LiDAR kapalıyken rover, global koridoru
   takip eder veya bilinmeyen alan politikasına göre durur; gizli kaya haritası
   kullanmaz.

## 6. Uygulama sırası

Önce Faz 1'i tek başına tamamlayıp sızıntıyı kaldırın ve test edin. Ardından
Faz 2 + Faz 3'ü sentetik sabit kayalarla çalıştırın. En son Faz 4 ile replan
entegrasyonunu, Faz 5 ile ROS/UI görünürlüğünü ekleyin. Böylece her ara sürüm,
yanlışlıkla “LiDAR kaçınıyor” iddiası taşımadan dürüstçe demo edilebilir.
