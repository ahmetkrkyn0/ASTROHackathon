# Simülasyon Motoru — Planı Adım Adım Yaşamak

**Kodda:** `backend/app/simulation.py`, `backend/app/sensor_payload.py`
**Çıktı:** Her plan cevabında `simulation` ve `summary` blokları

---

## Nedir?

Planlayıcının bulduğu yolu **adım adım yürüten** motor. Her adımda rover'ın durumunu hesaplıyor: konum, zaman, batarya yüzdesi, iç sıcaklık, risk seviyesi.

Çıktı bir `RoverState` dizisi — yolun her noktası için bir anlık görüntü.

---

## Hangi problemi çözüyor?

Planlayıcı size bir **hücre dizisi** veriyor: "buradan, buraya, buraya git."

Ama şu sorular cevapsız:
- Bu yolculuk **kaç saat** sürer?
- Batarya **nereye kadar** yeter?
- **En düşük** batarya seviyesi nerede olur?
- Rover **nerede** en çok risk altında?
- Şarj için durması gerekir mi, gerekirse **nerede ve ne kadar**?

Maliyet, bir sıralama aracı — mutlak bir tahmin değil. Simülasyon mutlak tahminleri üretiyor.

---

## Analoji: Yol tarifi ve gerçek yolculuk

Navigasyon size "34 km, 28 dakika" der. Bu bir tahmin.

Ama gerçekte yolculuk şöyle geçer: ilk 5 km rahat, sonra bir rampa (yakıt tüketimi artıyor), sonra trafik (duruyorsunuz, klima yakıt yiyor), sonra iniş (biraz geri kazanıyorsunuz).

Simülasyon motoru bu **ikinci anlatıyı** üretiyor. Ve o anlatı olmadan bilemeyeceğiniz şeyler var: mesela benzin göstergesinin **en düşük** olduğu an yolun ortasında mı yoksa sonunda mı?

Sonunda ise sorun yok. Ortasında ve kritikse — plan tehlikeli.

---

## Nasıl çalışıyor?

Her adımda hesaplananlar:

| Büyüklük | Nasıl |
|---|---|
| **Sürüş süresi** | `cost_engine.edge_travel_time_s` — slip dâhil |
| **Sürüş enerjisi** | Çekiş gücü × süre |
| **Housekeeping** | Temel sistem gücü + ısıtıcı yükü |
| **Güneş kazancı** | Hücre aydınlıksa panel kredisi |
| **Batarya** | Yukarıdakilerin işaretli toplamı (`move_battery_drain_wh`) |
| **Risk seviyesi** | Batarya yüzdesine göre sınıflandırma (`_risk_level`) |

### Tek enerji modeli — B5'in getirdiği düzeltme

`simulate_path` artık **sürerken de güneş panelini kredilendiriyor** ve batarya `cost_engine`'in işaretli değerini izliyor.

**Sonucu:** `/api/plan`, `/api/plan-4d` ve Monte Carlo **tek bir enerji modeli** paylaşıyor. Öncesinde üç ayrı hesap vardı ve ayrışabilirlerdi.

### Şarj molası sınırı — güzel bir hata düzeltmesi

`MAX_RECHARGE_HOURS = 29,53 × 24 = ~709 saat` (bir Ay günü).

**Neden bir sınır gerekiyordu:**

Eskiden **hiçbir sınır yoktu.** Net şarjı 0,001 W olan bir hücre, **~618 yıllık** bir şarj molası üretiyordu — ve bu sayı sıradan bir `total_elapsed_hours` olarak, yorumsuz raporlanıyordu.

**Mantık:** Bir Ay gününden uzun şarj molası bir "mola" değil, **görevin sonu**. Güneş tekrar geldi ve rover hâlâ bataryasını dolduramadıysa, o hücre yükü hiç taşıyamıyor demektir.

("Round 3 review, M-10")

---

## LiDAR yükü (`sensor_payload.py`)

**LunaPath sensör taşımıyor — sensör için plan yapıyor.**

Bir LiDAR taşımak iki maliyet getiriyor:
1. Sürekli güç çekişi
2. Kalıcı gölgeli bir bölgede **kendi ısıtıcı yükü**

Bu modül, bir sensörün maliyet modeline gerçekten girdiği **tek yer**: algılama olarak değil, **kaynak bütçesi kalemi** olarak.

```
ek_enerji = (yük_gücü + ısıtıcı_gücü) × süre
```

**Kasıtlı olarak sonradan (post-hoc):** Yeniden planlamak yerine, zaten hesaplanmış bir simülasyon özetini düzeltiyor. Bu, aynı rover'ın sensörlü/sensörsüz karşılaştırmasının kapsamına uygun — tam bir rota yeniden optimizasyonuna değil.

`with_sensor_payload()` fonksiyonu, rover'ın LiDAR taşıyan bir varyantını üretiyor: `lpr_1` → `lpr_1_lidar`.

---

## `summarize_simulation` — skaler özet

`RoverState` dizisini tek sayılara indirgiyor: toplam süre, toplam enerji, minimum SOC, toplam gölge maruziyeti, vb.

⚠️ **Bilinen bir sorun:** `summary.total_shadow_exposure` alanının **kod tabanında hiçbir yerde birimi yok.** Birimi kimsenin adlandıramadığı bir sayı ifade edilemez — bu yüzden AI kanıt katmanı bu alanı **tuzak** olarak işaretleyip modele hiç göstermiyor.

---

## Bağlantılı modüller

| Modül | Ne yapıyor |
|---|---|
| [`route_analysis.py`](rota-analizi-ve-misyon-raporu.md) | Aynı diziden **dağılım** görünümü çıkarıyor (eğim bantları, risk yüzdeleri) |
| [`safety_monitor.py`](safety-monitor-stl-fretish.md) | Aynı diziyi STL **izine** çeviriyor |
| [`stress_test.py`](stres-testi-sherpa.md) | Aynı fiziği 1 000 koşumda vektörize ediyor |
| [`report.py`](rota-analizi-ve-misyon-raporu.md) | Özetten GO/NO-GO kararı üretiyor |

---

## Kodda nerede?

```
backend/app/simulation.py
  RoverState                 ← adım başına anlık görüntü
  simulate_path()            ← ana döngü
  summarize_simulation()     ← skaler özet
  _risk_level()              ← batarya → risk sınıfı
  _shadow_and_power_checks()
  MAX_RECHARGE_HOURS = 29.53 × 24

backend/app/sensor_payload.py
  sensor_energy_overhead_wh()
  with_sensor_payload()
  apply_sensor_overhead_to_summary()
```

---

## Jüri soruları

**S: "Simülasyon ne kadar gerçekçi?"**
Fizik modeli kadar. Çekiş enerjisi, housekeeping gücü, güneş kazancı ve slip'li sürüş süresi hepsi `cost_engine`'den geliyor — yani planlayıcının kullandığı **aynı** model. Termal kısım kalibre edilmemiş bir model, ve bunu söylüyoruz.

**S: "Planlayıcı zaten maliyeti hesaplıyorsa simülasyona ne gerek var?"**
Çünkü maliyet bir **sıralama** aracı, mutlak tahmin değil. "Bu yol şu yoldan iyi" der ama "bu yol 2,98 saat sürer ve batarya %92,5'e iner" demez. O sayıları simülasyon üretiyor — ve GO/NO-GO kararı, formal güvenlik marjları, Monte Carlo hepsi o sayıların üstüne kuruluyor.

**S: "618 yıllık şarj molası hikâyesi nedir?"**
Gerçek bir hata. Şarj molası süresinin üst sınırı yoktu; net şarjı 0,001 W olan bir hücre 618 yıllık bir mola üretiyor ve bu sıradan bir toplam süre olarak raporlanıyordu. Bir Ay gününden (709 saat) uzun mola artık hata sayılıyor — çünkü Güneş tekrar geldiği hâlde batarya dolmadıysa o hücre yükü hiç taşıyamıyor demektir.

**S: "LiDAR simüle ediyor musunuz?"**
Algılama anlamında hayır — LiDAR taramasının kendisi ayrı bir modül (`horizon.py`'nin ışın çekirdeği). Simülasyonda LiDAR sadece bir **kaynak bütçesi kalemi**: sürekli güç çekişi artı gölgede kendi ısıtıcı yükü. Bu, sensörün maliyet modeline gerçekten girdiği tek yer.

**S: "`total_shadow_exposure` alanı ne?"**
Birimi olmayan bir sayı ve bunu bir sorun olarak kayda geçirdik. Kod tabanında hiçbir yerde birimi tanımlı değil. AI asistanının kanıt katmanı bu alanı tuzak olarak işaretleyip modele hiç göstermiyor — çünkü birimi bilinmeyen bir sayı hakkında cümle kurulamaz.
