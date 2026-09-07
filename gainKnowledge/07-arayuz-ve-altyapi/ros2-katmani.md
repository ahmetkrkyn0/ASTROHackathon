# ROS 2 Katmanı — Gerçek Rover Yazılımına Köprü

**Kodda:** `lunapath_ros/`, `lunapath_msgs/`
**Düğümler:** `planner_node`, `grid_publisher`, `pose_monitor`, `safety_monitor_node`

---

## Nedir?

**ROS 2** (Robot Operating System 2), robotik dünyasının fiili standardı. Neredeyse her ciddi robot yazılım yığını ROS 2 üzerinde çalışıyor.

LunaPath'in ROS 2 katmanı, planlama çekirdeğini bu ekosisteme bağlayan **dört düğüm** ve **dört mesaj tipinden** oluşuyor.

---

## Hangi problemi çözüyor?

Bir web API'si güzeldir ama gerçek bir rover HTTP çağırmaz. Rover'ın üstünde ROS 2 çalışıyor: sensörler topic'lere yayın yapıyor, kontrolcüler abone oluyor, her şey mesajlarla konuşuyor.

Yani: **LunaPath gerçek bir rover'a takılabilir mi?**

ROS 2 katmanı bu sorunun cevabı — ve cevabın "evet" olmasının somut kanıtı.

---

## Analoji: İki dil konuşan bir uzman

Bir uzman düşünün — mesela bir mühendis. Bilgisi tek, ama iki dilde anlatabiliyor: Türkçe ve İngilizce.

Kritik nokta: **bilgi çevrilmiyor, sadece anlatım dili değişiyor.** Uzman iki farklı şey bilmiyor.

LunaPath'te de öyle: planlama matematiği **tek yerde** (`backend/app/`). FastAPI ve ROS 2, o matematiğin iki farklı "dili".

Ve eğer bilgi iki yerde olsaydı? Zamanla ayrışırdı — uzman Türkçe konuşurken bir şey, İngilizce konuşurken başka bir şey söylerdi.

---

## Dört düğüm

### 1. `planner_node.py` — PlanTraverse eylem sunucusu

ROS 2'nin **action** (eylem) arayüzü: uzun süren, iptal edilebilir, ilerleme bildiren istekler için.

Modül dokümanı çok net:

> *"Kasıtlı olarak ince: her hesaplama `backend/app` içinde yaşıyor. Kendinizi bu dosyada planlama mantığı yazarken bulursanız, o mantık çekirdeğe aittir."*

İçe aktardıkları: `app.pathfinder.astar`, `app.corridor.build_corridor`, `app.rover_grids.grids_for_rover`, `app.cost_engine.resolve_weights`, `app.data_loader.load_preprocessed_grids`.

**Yani düğüm hiçbir şey hesaplamıyor — çekirdeği çağırıyor.**

### 2. `grid_publisher.py` — Katmanları yayınlar

LunaPath katmanlarını **`grid_map`** topic'i olarak yayınlıyor (robotik dünyasının standart arazi haritası formatı).

**QoS ayarı `TRANSIENT_LOCAL` (latched):**

> *"Geç başlayan bir abone (RViz, rosbag2) haritayı bir sonraki zamanlayıcı tik'ini beklemeden alsın diye."*

Yani RViz'i planlayıcıdan sonra açsanız bile haritayı görüyorsunuz.

### 3. `pose_monitor.py` — Odometri tüketicisi

`POST /api/pose` ucunun **ROS ikizi**.

**Akış:** `nav_msgs/Odometry` girer → `PoseEstimate` sözleşmesine çevrilir → planlayıcının son yayınladığı koridora göre konumlanır → ateşlenen her tetikleyici için bir `lunapath_msgs/ReplanTrigger` yayınlanır.

#### İki kasıtlı tasarım kararı

**Hiçbir odometri kütüphanesi import edilmiyor.**

> *"`nav_msgs/Odometry`, her odometri yığınının yayınladığı standart arayüz. Böylece LunaPath hangisinin sürdüğü konusunda agnostik kalıyor — KISS-ICP'yi stereo boru hattıyla değiştirin, bu düğüm değişmiyor."*

**Ve lisans faydası:**

> *"Bu ayrıca lisans yüzeyini sıfırda tutuyor (hiçbir GPL odometri kodu bağlanmıyor, sadece bir mesaj tipi tüketiliyor)."*

Bu ikinci nokta pratik ve önemli: GPL lisanslı bir kütüphaneyi bağlamak, projenin tamamının lisansını etkileyebilir.

**Bütün karar mantığı `app.localization.evaluate_pose`'da** — FastAPI ucunun çağırdığı **aynı fonksiyon**.

> *"Böylece tetikleyici politikası iki kabuk arasında ayrışamaz. Bu dosya sadece abonelik tesisatı."*

### 4. `safety_monitor_node.py` — Güvenlik monitörü

Telemetriden **ihlal başına bir `ReplanTrigger`** üretiyor: `trigger_id = "safety:LP-R02"` gibi.

[STL monitörünün](../05-dogrulama-ve-test/safety-monitor-stl-fretish.md) ROS tarafındaki karşılığı.

---

## Dört mesaj tipi (`lunapath_msgs/`)

| Mesaj | Ne taşıyor |
|---|---|
| `Corridor.msg` | [Koridor sözleşmesi](../04-planlama-ve-maliyet/koridor-sozlesmesi.md) — yol noktaları, yarı genişlikler, bütçeler, yedek noktalar |
| `MissionWeights.msg` | Maliyet kriteri ağırlıkları |
| `PlanMetrics.msg` | Plan sonuç metrikleri |
| `ReplanTrigger.msg` | Ateşlenen bir yeniden planlama tetikleyicisi |

---

## `conversions.py` — geometrinin nerede yaşadığı

> *"Bütün geometri `app.grid_frame`'de yaşıyor."*

Bu modül sadece ROS mesajı **montajı** yapıyor.

**Test stratejisi ilginç ve doğru:**

| Ne | Nerede test ediliyor | Neden |
|---|---|---|
| Mesaj montajı | `colcon test` altında | ROS kurulumu gerekiyor |
| Altındaki geometri | `backend/test_grid_frame.py` | ROS'suz test edilebilir |

Yani **matematiğin doğruluğu ROS kurmadan doğrulanabiliyor.**

### Kritik bir geometri detayı: grid_map transpoze

`grid_frame.py`'nin dokümanı bunu K3 konvansiyonu olarak yazıyor:

> **`grid_map` indislerini harita eksenlerine KARŞI sayıyor, dolayısıyla bir LunaPath (satır, sütun) dizisini bir grid_map matrisine çevirmek bir transpoze artı bir çevirmedir — sadece sütun-öncelikli düzleştirme değil.**

Bu, kolayca yapılabilecek ve sessizce yanlış harita üretecek bir hata. Türetmesi Faz 4 planında yazılı.

---

## Neden bu katman değerli?

**Somut cevap:** Bu, LunaPath'in akademik bir prototip değil, **entegre edilebilir bir bileşen** olduğunun kanıtı.

Ve mimari olarak: iki kabuk (FastAPI + ROS 2) tek çekirdeği paylaşıyor. Bu, projedeki *"saf çekirdek, ince kabuk"* kuralının en görünür sonucu.

> **Hatırlatma:** Bu kural bir kez ihlal edildi ve sonucu ağır oldu. Rover'a göre grid uyarlaması bir dönem `main.py` içindeydi (FastAPI kabuğu), dolayısıyla **ROS kabuğu hiçbir zaman uyarlanmış grid görmedi** — VIPER ile plan istendiğinde LPR-1'in eğim limitiyle planlanıyordu. `rover_grids.py` bu yüzden ayrı bir modül olarak çıkarıldı.

---

## Kodda nerede?

```
lunapath_ros/
  lunapath_ros/planner_node.py         ← PlanTraverse action server
  lunapath_ros/grid_publisher.py       ← grid_map yayını (latched QoS)
  lunapath_ros/pose_monitor.py         ← odometri → ReplanTrigger
  lunapath_ros/safety_monitor_node.py  ← STL ihlali → ReplanTrigger
  lunapath_ros/conversions.py          ← mesaj montajı
  launch/lunapath.launch.py
  test/test_conversions.py

lunapath_msgs/msg/
  Corridor.msg · MissionWeights.msg · PlanMetrics.msg · ReplanTrigger.msg

backend/app/grid_frame.py                ← bütün geometri, ROS'suz test edilebilir
backend/test_grid_frame.py
docs/ROS2_KULLANIM_KILAVUZU.md
docs/ROS2_SETUP.md
```

---

## Jüri soruları

**S: "ROS 2 desteği gerçek mi yoksa dekoratif mi?"**
Gerçek: dört çalışan düğüm ve dört mesaj tipi. Ama asıl kanıt şu — bu düğümler backend'in kodunu **çağırıyor**, kopyalamıyor. `planner_node.py` `app.pathfinder.astar`'ı import ediyor. Planlama mantığının tek satırı ROS tarafında yok.

**S: "Neden ROS 2 gerekli?"**
Çünkü gerçek bir rover HTTP çağırmaz. Rover üstünde ROS 2 çalışır: sensörler topic'lere yayın yapar, kontrolcüler abone olur. ROS 2 katmanı, LunaPath'in gerçek bir rover yazılım yığınına takılabileceğinin somut kanıtı.

**S: "Hangi odometri sistemini kullanıyorsunuz?"**
Hiçbirini ve bu kasıtlı. `nav_msgs/Odometry` her odometri yığınının yayınladığı standart arayüz. Biz o mesajı tüketiyoruz, hiçbir odometri kütüphanesi import etmiyoruz. Sonuç: KISS-ICP'yi stereo görsel odometriyle değiştirin, düğüm değişmiyor. Bonus olarak lisans yüzeyimiz sıfır — hiçbir GPL kod bağlanmıyor.

**S: "İki kabuk arasında tutarlılığı nasıl sağlıyorsunuz?"**
Karar mantığı tek yerde. `pose_monitor` düğümü `app.localization.evaluate_pose`'u çağırıyor — FastAPI ucunun çağırdığı **aynı fonksiyon**. Düğüm sadece abonelik tesisatı. Bu kuralı bir kez ihlal ettik ve sonucu ağır oldu: rover'a göre grid uyarlaması FastAPI kabuğunun içindeydi, o yüzden ROS tarafı VIPER ile plan yaparken LPR-1'in eğim limitini kullanıyordu.

**S: "ROS kurmadan test edebiliyor musunuz?"**
Matematiği evet. Bütün geometri `app.grid_frame`'de ve ROS'suz test ediliyor (`backend/test_grid_frame.py`). Sadece mesaj montajı `colcon test` altında test ediliyor, çünkü o ROS mesaj paketlerini import ediyor. Bu ayrım, çekirdek matematiğin ROS kurulumu olmayan bir makinede doğrulanabilmesini sağlıyor.

**S: "grid_map dönüşümünde ne özel?"**
`grid_map` indislerini harita eksenlerine **karşı** sayıyor. Yani LunaPath'in (satır, sütun) dizisini grid_map matrisine çevirmek bir transpoze artı bir çevirme — sadece sütun-öncelikli düzleştirme değil. Bu, kolayca yapılıp sessizce yanlış harita üretecek bir hata; türetmesi Faz 4 planında yazılı ve konvansiyon `grid_frame.py`'nin başında belgeli.
