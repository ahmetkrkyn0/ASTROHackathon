# Koridor Sözleşmesi — Küresel Planlayıcının Yerel Planlayıcıya Verdiği Söz

**Kodda:** `backend/app/corridor.py`, `backend/app/schemas.py`
**Yayınlandığı yerler:** FastAPI JSON, ROS 2 `lunapath_msgs/Corridor` mesajı

---

## Nedir?

**Koridor**, LunaPath'in dışarıya verdiği tek sözleşme. Bir rota çizgisi değil, **içinde hareket edilebilecek bir hacim** ve o hacimle birlikte gelen bütçeler.

İçeriği:

| Alan | Ne |
|---|---|
| `waypoints` | Yol noktaları, projeksiyon metresi (x, y) |
| `half_width_m` | Segment başına izin verilen yanal sapma |
| `max_slope_deg` | Segment başına gözlenen eğim tavanı |
| `energy_budget_wh` | Segment başına enerji tahsisi |
| `thermal_budget_K_s` | Segment başına termal pay (batarya minimumunun üstündeki iç sıcaklık marjı × geçiş süresi) |
| `fallback_points` | Her yol noktası için en yakın safe haven noktası |

---

## Hangi problemi çözüyor?

LunaPath **küresel planlayıcı**. 5 metre çözünürlüklü yörünge verisiyle çalışıyor. Ama rover'ın önünde 30 santimlik bir kaya varsa, LunaPath onu göremez — o çözünürlüğün altında.

Rover üstündeki **yerel planlayıcı** (LiDAR/stereo kamera ile) o kayayı görüyor ama nereye gitmesi gerektiğini bilmiyor.

**İki planlayıcının konuşması gerekiyor.** Ama nasıl?

- Sadece bir çizgi verirseniz → yerel planlayıcı kayadan kaçamaz, çizgiye sadık kalmak zorunda
- Sadece bir hedef verirseniz → yerel planlayıcı, LunaPath'in bildiği tehlikeleri bilmeden yol seçer

**Koridor bu ikisinin ortası:** "Şu çizgiyi takip et, şu kadar sağa sola sapabilirsin, ve bu segment için şu kadar enerjin var."

---

## Analoji: Sürüş dersi

Bir sürüş eğitmeni yanınızda oturuyor. Size şunu **demiyor**: *"Direksiyonu 3 derece sağa çevir, sonra 12 metre sonra 5 derece sola."* Bu mikro yönetim olurdu ve zaten trafiğe göre değişecekti.

Ama şunu da demiyor: *"Eve git."* Bu da yetersiz — hangi yoldan, ne kadar sürede?

Söylediği şey: **"Bu şeritte kal, bu hızı geçme, benzin şu kadar var, sıkışırsan şu çıkışa gir."**

Bu tam olarak koridor sözleşmesi:
- **Şerit** = `half_width_m`
- **Hız/eğim sınırı** = `max_slope_deg`
- **Benzin** = `energy_budget_wh`
- **Acil çıkış** = `fallback_points`

Şeridin içindeki mikro kararlar (çukurdan kaçmak, yayaya yol vermek) sürücünün — yani yerel planlayıcının.

---

## Nasıl çalışıyor?

### Yarı genişlik nasıl hesaplanıyor?

`clearance_map()` fonksiyonu, her hücrenin **en yakın geçilemez hücreye olan mesafesini** metre cinsinden hesaplıyor (SciPy'nin mesafe dönüşümüyle).

Sonra koridor bu açıklığın bir kısmını yanal sapma izni olarak yayınlıyor, `DEFAULT_MAX_HALF_WIDTH_M = 400 m` ile sınırlı.

### Harita kenarı = engel — kritik bir düzeltme

`clearance_map`, mesafe dönüşümünden **önce** maskeyi bir sıra geçilemez hücreyle çevreliyor.

**Neden:** `distance_transform_edt` mesafeyi dizinin **içindeki** en yakın `False` hücreye ölçüyor. Yani haritanın kenarındaki tamamen geçilebilir bir hücre, **çok büyük bir açıklık** değeri döndürüyordu.

**Sonucu:** `build_corridor` orada 400 metreye kadar bir yarı genişlik yayınlıyordu — **DEM'in dışına uzanan** bir yanal alan. Yani küresel planlayıcının hiçbir kanıtı olmayan bir bölgeyi, yerel planlayıcıya **izin olarak** veriyordu.

Yerel planlayıcı o izne güvenip haritanın dışına sürerdi.

("Round 3 review, M-12")

### Termal bütçe — ilginç bir birim

`thermal_budget_K_s` birimi **Kelvin × saniye**. Tuhaf görünüyor ama mantıklı:

> Batarya minimumunun üstündeki iç sıcaklık marjı, **segment geçiş süresi boyunca integre edilmiş.**

Yani "ne kadar sıcaklık payın var" ile "o payı ne kadar süre kullanacaksın" birleştirilmiş tek bir bütçe. Bir segmentte 5 K marjla 2 saat geçirmek, 10 K marjla 1 saat geçirmeye eşdeğer bir termal risk taşıyor.

### `fallback_points` — her adımda bir çıkış

Her yol noktası için **en yakın safe haven** noktası veriliyor.

Yani rover, koridorun herhangi bir noktasında sorun yaşarsa, nereye kaçacağını **hazır** biliyor — o an hesaplamak zorunda değil.

Kaynak: [safe haven](safe-haven.md).

### Simetrik çift

| Yön | Sözleşme | Dosya |
|---|---|---|
| **Dışarı** (LunaPath → yerel planlayıcı) | `Corridor` | `schemas.py` |
| **İçeri** (yerel planlayıcı → LunaPath) | `PoseEstimate` | `pose.py` |

İkisi ayrı dosyada, kasıtlı. Biri giden sözleşme, öbürü gelen.

### Çözünürlük bağlamsal

Kod bunu açıkça söylüyor: koridor, "metadata ile tanımlanmış bir DEM üzerindeki küresel planlayıcı" ile "rover üstündeki, metre altı çözünürlüklü yerel katman" arasındaki arayüz.

Şu anki Site11 çalışma seti 5 m/piksel — ama bu **proje geneli bir sabit değil**, o veri setinin özelliği.

---

## İki kabuktan da geçiyor

Aynı sözleşme:
- **FastAPI** üzerinden JSON olarak
- **ROS 2** üzerinden `lunapath_msgs/Corridor` mesajı olarak

Aynı veri, iki taşıma. Bu, LunaPath'in gerçek bir rover yazılım yığınına takılabileceğinin somut kanıtı.

---

## Piksel → metre dönüşümü

`corridor.py` bu dönüşümü kendi yapmıyor, `grid_frame.pixel_to_map_xy`'ye **devrediyor**.

> Faz 2'nin C2 bulgusu tam olarak bu formülün üç ayrı yerde bulunması ve birinin ters işaretli olmasıydı. Faz 4 kopyaları kaldırdı.

---

## Kodda nerede?

```
backend/app/schemas.py
  Corridor                      ← dışa giden sözleşme

backend/app/corridor.py
  build_corridor()              ← plandan koridor üretir
  clearance_map()               ← açıklık haritası (kenar = engel)
  DEFAULT_SAFE_SHADOW_RATIO = 0.2
  DEFAULT_MAX_HALF_WIDTH_M  = 400.0

backend/app/pose.py
  PoseEstimate                  ← içeri gelen sözleşme

lunapath_msgs/                  ← ROS 2 mesaj tanımları
```

---

## Jüri soruları

**S: "Neden sadece bir rota vermiyorsunuz?"**
Çünkü 5 metre çözünürlüklü yörünge verisi, rover'ın önündeki 30 santimlik kayayı göremez. Rover üstündeki yerel planlayıcı görür ama nereye gitmesi gerektiğini bilmez. Koridor, iki planlayıcının konuşma dili: "bu şeritte kal, bu kadar sapabilirsin, bu kadar enerjin var, sıkışırsan şuraya kaç."

**S: "Yarı genişliği nasıl belirliyorsunuz?"**
Her hücrenin en yakın geçilemez hücreye olan mesafesinden, 400 metre tavanla. Ve haritanın kenarı **engel sayılıyor** — bu bir hata düzeltmesi: eskiden kenar hücrelerinde 400 metreye kadar sapma izni yayınlanıyordu, DEM'in dışına doğru. Yerel planlayıcı o izne güvenip haritasız bölgeye sürerdi.

**S: "Termal bütçenin birimi neden Kelvin×saniye?"**
Çünkü termal risk hem marjın büyüklüğüne hem de o marjda geçirilen süreye bağlı. 5 K marjla 2 saat, 10 K marjla 1 saate eşdeğer. İkisini tek bir bütçede birleştirmek, yerel planlayıcının "yavaşlarsam termal olarak ne kaybederim" hesabını yapabilmesini sağlıyor.

**S: "Bu sözleşme gerçekten kullanılıyor mu?"**
Evet, iki taşıma üzerinden: FastAPI JSON ve ROS 2 `lunapath_msgs/Corridor` mesajı. ROS tarafında koridoru yayınlayan, pozu geri alan ve tetikleyicileri değerlendiren çalışan düğümler var.

**S: "`fallback_points` ne işe yarıyor?"**
Rover koridorun herhangi bir noktasında sorun yaşarsa nereye kaçacağını **önceden** biliyor. O an hesaplamak zorunda değil — ki muhtemelen o an hesaplayacak durumda da olmaz. Kaynağı safe haven katmanı.
