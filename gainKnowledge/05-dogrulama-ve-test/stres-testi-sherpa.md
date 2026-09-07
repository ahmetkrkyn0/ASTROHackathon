# Monte Carlo Stres Testi (B5) — Planı Bin Kez Çalıştırmak

**Kodda:** `backend/app/stress_test.py`
**API:** `POST /api/stress-test`
**Özellik kodu:** B5

---

## Nedir?

Bir 4-D planı alıp, gerçek operasyonda karşılaşılan belirsizlikleri rastgele örnekleyerek **binlerce kez** simüle eden sistem. Varsayılan 1 000 koşum.

Çıktı tek bir sayı değil, bir **dağılım**: tamamlama oranı, güneşsizliğe kalan süre, DSN kesintisine kalan süre, batarya bitmesine kalan süre.

---

## Hangi problemi çözüyor?

VIPER'ın planlama ekibi bir planı **bir kez uygulanabilir olduğu için kabul etmez.**

Sebebi basit: deterministik simülasyon "her şey tam planlandığı gibi giderse" sorusuna cevap veriyor. Ama gerçekte:

- Kalkış gecikir
- Batarya beklenenden az dolu başlar
- Güç çekişi tahminden yüksek olur
- Rover planlanandan yavaş ilerler
- DSN (Derin Uzay Ağı) anteni kesinti yaşar
- Bir güneş parçacık olayı (SEP) sistemleri etkiler

Bunların **hepsi aynı anda kötü gitmeyecek**, ama bazıları gidecek. Soru: **kaç senaryoda plan hâlâ çalışıyor?**

---

## Analoji: Kaç kere denerseniz?

Yeni bir yolla işe gitmeyi düşünüyorsunuz. Bir kez deniyorsunuz ve 28 dakika sürüyor. "Harika, bu yol daha iyi" diyorsunuz.

Ama bir kere denemek hiçbir şey söylemiyor. O gün trafik hafifti belki, ışıklar denk geldi belki.

Gerçek soru: **"Bu yolu 100 kere denesem kaçında işe zamanında varırım?"**

Ve daha da önemlisi: **"Geç kaldığım durumlarda ne oldu?"** Hep aynı kavşak mı, yoksa her seferinde farklı bir sebep mi?

B5'in verdiği cevap tam olarak bu. Ve VIPER rotası için cevap **rahatsız edici**: koşumların sadece %29,6'sında hedefe varılıyor ve **her başarısızlık batarya tükenmesi.** Yani her seferinde aynı kavşak.

---

## Nasıl çalışıyor?

### SHERPA protokolü — birebir parametreler

Balaban vd.'nin SHERPA aracı (SpaceOps 2025) ve Shirley & Balaban 2022'de tanımlanan bozulmalar:

| Parametre | Dağılım | Yön |
|---|---|---|
| **Başlangıç zamanı** | σ = 2 saat | **Yalnız geç** (kesilmiş Gauss) |
| **Başlangıç bataryası** | σ = %20 | **Yalnız düşük** |
| **Güç çekişi** | σ = %20 | **Yalnız yüksek** |
| **Etkin hız** ("speed made good") | σ = %20 / 30 / 40 / 50 | **Yalnız yavaş** |
| **DSN kesintisi** | Modellenmiş olasılık | — |
| **SEP olayı** (güneş enerjik parçacık) | Modellenmiş olasılık | — |

**"Kesilmiş Gauss" ve tek yönlülük kritik:** Gerçek operasyonda sürprizler asimetriktir. Rover planlanandan **erken** başlamaz, **fazla** dolu bataryayla başlamaz. Simetrik bir dağılım, iyimser tarafı da örnekleyerek sonucu güzelleştirirdi.

### Operatör politikası

İnsan operatör bir politikayla taklit ediliyor:

| Durum | Davranış |
|---|---|
| **Programın gerisindeyse** | Şarj molalarını atlar ve gölgede bataryayla sürer |
| **Programın önündeyse ve gölge varsa** | Bekler |

Bu, gerçek bir operatörün yapacağı ödünleşimi modelliyor: zaman baskısı altında risk alınıyor.

### Aynı fizik, ayrı model değil

Monte Carlo, planı seçerken kullanılan **aynı fiziği** kullanıyor: `cost_engine`'in çekiş, housekeeping ve güneş aritmetiği, N koşum üzerinde vektörize.

**Neden önemli:** Farklı bir rover modeli kullansaydık, dağılımlar plan hakkında değil **ikinci bir model hakkında** olurdu.

### Dürüstlük kuralları

- Epoch ve ufuk küpü yoksa → gökyüzü statik, ve çağırana **söyleniyor**
- Dünya serisi yoksa → DSN marjı **yok**
- Bir oran her zaman **Wilson güven aralığıyla** raporlanıyor

---

## Önce kapatılan bir önkoşul

B5 çalışmadan önce bir tutarsızlık düzeltilmek zorundaydı:

`simulate_path` artık **sürerken güneş panelini kredilendiriyor**, ve batarya `cost_engine`'in işaretli `move_battery_drain_wh` değerini izliyor.

**Sonucu:** `/api/plan`, `/api/plan-4d` ve Monte Carlo **tek bir enerji modeli** paylaşıyor. Öncesinde üç ayrı hesap vardı.

---

## Site11'de ölçülen gerçek sayılar

### VIPER haven-haven rotası, 2027-05-30 ay günü

Plan: 40 hamle, 7,4 saat, planın minimum bataryası %32.

| Hız σ | Tamamlama oranı |
|---|---|
| **%20** | **%29,6** (%95 GA: 26,9 – 32,5) |
| %50 | **%15,8** |

**Ve:** *"Her başarısızlık batarya tükenmesi."*

**Ve:** Koşumların yalnız **%1,4'ü** bütün marjlar sağlam bitiyor.

**Teşhis:** Rota tamamen gölgede bataryayla sürülüyor ve planlayıcının tek marjı %20 rezerv. Yani plan hiçbir tampon içermiyor.

### LPR-1'in 2,2 saatlik rotası, 2026-09-28

| Hız σ | Tamamlama |
|---|---|
| Her σ'da | **%100** (GA 99,6 – 100) |

p5 minimum batarya: %46–52.

**Ama tam başarı sıfır** — çünkü o ay gününde LPR-1'in [safe haven'ı yok](../04-planlama-ve-maliyet/safe-haven.md). Karar metni bunu açıkça söylüyor.

Yani rota tamamlanıyor ama rover varış noktasında iki hafta hayatta kalamaz.

---

## Bu koşumun bulduğu planlayıcı açığı — hâlâ açık

Bu, dürüstlüğün en net örneklerinden biri:

**Bulgu:** `astar_4d` saati `ceil(sürüş_süresi / dilim)` kadar ilerletiyor, ama bataryayı **yalnız sürüş süresi için** düşüyor.

**Sonucu:** Monte Carlo'nun nominal koşumu, kalan süreyi housekeeping (temel sistem) gücünde tutunca, VIPER rotasının minimum bataryası **%32 değil %23** çıkıyor.

Yani planlayıcı, yuvarlama sonucu oluşan boş zamanda bataryanın boşalmadığını varsayıyor.

**Durumu:** Burada değiştirilmedi. Planlayıcı takibi olarak spec'e yazıldı ve **hâlâ açık.**

> Bir hatayı bulup düzeltememek utanç verici değil. Bulup **kaydetmemek** olurdu.

---

## Maliyet

`POST /api/stress-test`: **1,0 – 2,4 saniye** (1 000 koşum).

---

## İlham kaynağı

- **Shirley & Balaban (2022)**, *An Overview of Mission Planning for the VIPER Rover*
- **Balaban vd., SHERPA**, SpaceOps 2025 — "Traverse Evaluation" protokolü

---

## İddia sınırı

✅ **Söylenebilir:** *"NASA'nın stres-test protokolünü aynı parametrelerle uyguluyoruz."*

❌ **Söylenemez:** *"Rotamız güvenli."* — VIPER rotası koşumların **%70'inde** bataryadan düşüyor.

---

## Kodda nerede?

```
backend/app/stress_test.py
  SHERPA parametreleri (kesilmiş Gauss)
  operatör politikası
  fault_rate_per_km  ← B1'den eklendi, varsayılan 0 (bit-eşit)
  Wilson güven aralıkları

scripts/stress_test_report.py
docs/research/stress_test_report.md
```
69 yeni test.

---

## Jüri soruları

**S: "Neden 1 000 koşum?"**
SHERPA'nın kendi kadansı ve istatistiksel olarak yeterli: %29,6'lık bir oran için Wilson %95 güven aralığı 26,9–32,5, yani ±3 puan. Daha fazlası aralığı daraltır ama kararı değiştirmez.

**S: "Dağılımlar neden tek yönlü?"**
Çünkü gerçek operasyonda sürprizler asimetrik. Rover planlanandan erken başlamaz, fazla dolu bataryayla başlamaz, planlanandan hızlı gitmez. Simetrik dağılım kullanmak, iyimser tarafı örnekleyerek sonucu yapay olarak güzelleştirirdi. Bu parametrelerin hepsi SHERPA'dan alındı, biz uydurmadık.

**S: "Sonuç ne çıktı?"**
VIPER'ın haven-haven rotası koşumların **%29,6'sında** tamamlanıyor. Her başarısızlık batarya tükenmesi. Ve koşumların sadece %1,4'ü bütün marjlar sağlam bitiyor. Bu, o rotanın kabul edilemez olduğu anlamına geliyor — ve deterministik plan bunu göstermiyordu.

**S: "LPR-1 %100 tamamlıyorsa o rota iyi mi?"**
Rota iyi, varış noktası değil. Rover hedefe varıyor ama o ay gününde ulaşabileceği safe haven yok — yani iki haftalık iletişimsiz döneme orada yakalanırsa hayatta kalamaz. Sistem bunu "tam başarı sıfır" diye raporluyor. Bu, tek bir metriğe bakmanın neden yetmediğinin örneği.

**S: "Bir hata buldunuz ama düzeltmediniz mi?"**
Evet. Planlayıcı, zaman dilimi yuvarlaması sonucu oluşan boş zamanda bataryayı düşmüyor. Monte Carlo bunu yakaladı: VIPER rotasının gerçek minimum bataryası %32 değil %23. Kapsam dışıydı, spec'e planlayıcı takibi olarak yazıldı ve açık olduğunu raporlarımızda söylüyoruz.

**S: "Monte Carlo, planlayıcıdan farklı bir model mi kullanıyor?"**
Hayır, kasıtlı olarak aynı. `cost_engine`'in çekiş, housekeeping ve güneş aritmetiği N koşum üzerinde vektörize ediliyor. Farklı bir model kullansaydık, dağılımlar plan hakkında değil ikinci bir model hakkında olurdu.
