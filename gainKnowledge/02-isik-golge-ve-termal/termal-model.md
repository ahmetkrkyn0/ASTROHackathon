# Termal Model — Yüzey Sıcaklığından İç Sıcaklığa

**Kodda:** `backend/app/thermal_model.py`, `backend/app/thermal_grid.py`, `backend/app/thermal_validation.py`
**API:** `layers/thermal`, `layers/thermal_min`

---

## Nedir?

İki soruyu cevaplayan katman:

1. **Yüzey sıcaklığı:** Bu hücrenin regoliti (Ay toprağı) kaç derece?
2. **İç sıcaklık:** Rover o hücrede dururken kendi içi kaç dereceye gelir?

İkisi çok farklı şeyler ve ikisi de gerekli. Yüzey sıcaklığı fiziksel bir alan; iç sıcaklık rover'ın hayatta kalıp kalmadığını belirleyen şey.

---

## Hangi problemi çözüyor?

Ay'ın güney kutbunda sıcaklık aralığı **+80 °C ile −180 °C** arası. Bir lityum batarya bu aralığın çoğunda çalışamaz:

| Rover | Batarya çalışma aralığı (iç) |
|---|---|
| LPR-1 | 0 … +35 °C |
| NASA VIPER | 0 … +35 °C |
| CNSA Yutu-2 | −10 … +30 °C |
| LUVMI-M | −100 … 0 °C |

Yani rover'ın iç sıcaklığı **35 derecelik bir pencerede** tutulmak zorunda, dışarısı 260 derecelik bir aralıkta gezinirken.

Termal model bu pencerenin ne zaman ve nerede tutulabildiğini söylüyor.

---

## Analoji: Termos içindeki çay

Bir termosa sıcak çay koyup buzdolabına koyduğunuzu düşünün.

- **Buzdolabının sıcaklığı** = yüzey sıcaklığı (çevre)
- **Çayın sıcaklığı** = rover'ın iç sıcaklığı
- **Termosun yalıtımı** = rover'ın termal tasarımı

Kritik gözlem: **çay anında buzdolabı sıcaklığına inmez.** Yavaş yavaş iner, üstel olarak. Ne kadar yavaş? Termosun kalitesine bağlı — buna **zaman sabiti (τ)** deniyor.

LPR-1 için τ = 7 200 saniye = **2 saat**. Yani rover'ın iç sıcaklığı, çevreyle arasındaki farkın yaklaşık üçte ikisini 2 saatte kapatıyor.

Bu zaman sabiti, [termal dwell (C6)](termal-dwell-ve-operasyon-zarfi.md) özelliğinin tamamının dayandığı sayı: rover'ın "ne kadar süre burada durabilirim" sorusunun cevabı bu eğrinin ne zaman zarfı terk ettiği.

---

## Nasıl çalışıyor?

### Yüzey sıcaklığı — iki model, tek arayüz

Kod, iki farklı sıcaklık modelini aynı protokolün arkasına koyuyor:

| Model | Ne yapıyor | Etiket |
|---|---|---|
| **`Heat1DModel`** | Hayne'in 1-B regolit ısı difüzyon modeli — gerçek fizik | `MODEL` |
| **`SyntheticModel`** | Yükseklik + bakı heuristiği — kaba tahmin | `SYNTHETIC` |

**Neden iki tane:** heat1d kütüphanesi kurulu değilse veya API'si değişmişse, sistem çökmek yerine sentetik modele düşer. Ama çıktı **`SYNTHETIC` etiketiyle** dolaşır — kimse onu fizik sanmaz.

### Sentetik modelin sabit referansı — bir hata düzeltmesi

Sentetik model yüksekliği bir sıcaklık aralığına eşliyor. Eskiden bu eşleme **pencerenin kendi min/max yüksekliğine** göre normalleştiriliyordu.

**Sonucu:** Aynı arazi farklı bir pencerede yüklendiğinde farklı sıcaklık, dolayısıyla farklı **geçilebilirlik** veriyordu. Yani fiziksel bir alan, haritanın nereden kırpıldığına bağlıydı.

**Düzeltme:** Sabit referans kondu — `−3000 m … +4000 m` yüksekliği, `−180 °C … +80 °C` sıcaklığa eşliyor. Artık aynı hücre onu içeren her pencerede aynı değeri veriyor. ("Round 3 review, L-3")

### İki uç: yıllık zirve ve soğuk uç

Her hücre için iki sıcaklık hesaplanıyor:

| Fonksiyon | Ne verir | Nerede kullanılır |
|---|---|---|
| `annual_peak_c()` | Hücrenin bir yılda gördüğü **en sıcak** an | Sıcak taraf kontrolleri |
| `shadowed_equilibrium_c()` | Hücre sürekli gölgede kalırsa ulaşacağı **denge** | Geçilebilirlik kapısı, hayatta kalma |

Hayatta kalma bir **soğuk uç** sorusu — o yüzden geçilebilirlik kapısı soğuk uca bakıyor. Bu, düzeltilmiş bir hata: kod bir dönem tepe sıcaklığa bakıyordu. ("Round 4 review, H-3")

### Yüzeyden içeriye: `surface_to_inner`

Rover'ın iç sıcaklığı yüzeyle aynı değil. Katalogda iki ofset var:

| Alan | LPR-1 | Anlamı |
|---|---|---|
| `thermal_offset_cold` | +60 K | Soğuk tarafta rover içi, yüzeyden 60 K sıcak |
| `thermal_offset_hot` | −40 K | Sıcak tarafta rover içi, yüzeyden 40 K soğuk |

Bu **parçalı (piecewise) bir ofset modeli** — basit ama bilerek basit. Ve sınırları var: aşağıda, C6'nın bulduğu tuhaflığa sebep olan da bu.

### Gevşeme: `relax_surface_c`

İç sıcaklık hedefine anında ulaşmıyor, **birinci mertebeden gecikmeyle** yaklaşıyor:

```
T(t) = T_hedef + (T_başlangıç − T_hedef) · e^(−t/τ)
```

Bu, termos analojisindeki üstel soğuma. τ katalogdan geliyor (`thermal_tau_s`).

Regolit derisi için ayrı bir zaman sabiti var: `REGOLITH_THERMAL_TAU_S = 3600 s` (1 saat), etiketi **`UNCALIBRATED`**.

### Doğrulama altyapısı — hazır ama beslenmemiş

`thermal_validation.py`, modellenmiş sıcaklık grid'ini bir dış referansla (örneğin NASA'nın **Diviner** termal ölçüm cihazı) karşılaştıran saf bir fonksiyon: RMSE, MAE, bias ve en önemlisi **`misclassified_traversable_pct`** — iki grid'in "bu hücre −150 °C'nin üstünde mi" konusunda anlaşmadığı hücre oranı.

Bu son sayı bizim için kritik olan, çünkü geçilebilirliği belirleyen eşik o.

**Ama:** Diviner dosyası yerelde yok. Altyapı hazır, veri bekliyor. Bu açıkça "C5'in işi" olarak kayıtlı.

---

## Site11'de ölçülen gerçek sayılar

| Ölçüm | Değer |
|---|---|
| SPICE Güneş yüksekliği, bir yıl (−88,92° enlem) | **−2,59° … +2,55°** |
| heat1d'nin düz hücre zirvesi | **−146,4 °C** |
| Güneş'e bakan 30° eğimin zirvesi | **+44,5 °C** |
| Aynı eğimin iç sıcaklığı (sıcak dal) | **+4,5 °C** |
| PSR maskesi içinde medyan soğuk uç | **−183,15 °C** |

**Kritik sonuç:** Site11'de bizim modelimizde **sıcak taraf problemi yok.** Güneş'e bakan en dik yamacın bile iç sıcaklığı +4,5 °C — batarya zarfının (0…35 °C) rahatça içinde. Problem tamamen soğuk tarafta.

---

## Bilinen model kusuru — dürüstçe

C6 çalışması, ofset modelinin bir eserini ortaya çıkardı:

Zarf matrisinde 13 kutu **"sıcak-sınırlı"** görünüyor. İncelendiğinde: bunların hepsi yüzey sıcaklığı −23,5 ile −0,4 °C arasında olan hücreler. Yani **eksi** yüzey sıcaklığı, ama soğuk dalın +60 K ofseti bunları 35 °C'nin üstüne atıyor.

Bu fiziksel değil, parçalı ofset modelinin sınır davranışı. **Ve öyle etiketlenmiş** — "ofset modelinin eseri" diye raporlanıyor, gerçek bir sıcak problem gibi sunulmuyor.

---

## İlham kaynağı

- **heat1d** — Paul Hayne'in 1-B regolit ısı difüzyon modeli. Gezegen yüzey termal modellemesinde standart araç.
- **Diviner** — NASA LRO'nun termal radyometresi; doğrulama referansı olarak hedefleniyor.

---

## İddia sınırı

- ❌ **Termal doğruluk iddiası yok.** Model `MODEL / UNCALIBRATED` etiketli ve bu etiket her cevapla gidiyor.
- ❌ **Isıtıcının watt→kelvin bağı yok.** Katalogdaki `p_heater_w` sadece enerji modelinde; sıcaklık modelinde ısıtıcı ancak açık bir varsayım olarak devreye giriyor (`heater_model="thermostat_assumed"`).
- ⚠️ Ofset modeli parçalı ve sınırda eser üretiyor (yukarıda).

---

## Kodda nerede?

```
backend/app/thermal_model.py
  SurfaceThermalModel        ← protokol (iki model, tek arayüz)
  Heat1DModel / SyntheticModel
  annual_peak_c()            ← yıllık zirve
  shadowed_equilibrium_c()   ← soğuk uç denge
  surface_to_inner()         ← yüzey → rover içi
  relax_surface_c()          ← üstel gevşeme
  REGOLITH_THERMAL_TAU_S     ← 3600 s
  REGOLITH_LAG_VALIDITY      ← "UNCALIBRATED"

backend/app/thermal_grid.py
  generate_thermal_grid()    ← sentetik yedek
  ELEV_REF_MIN_M / MAX_M     ← sabit referans (−3000 / +4000)

backend/app/thermal_validation.py
  thermal_comparison()       ← Diviner karşılaştırma altyapısı
```

---

## Jüri soruları

**S: "Sıcaklık verisi gerçek mi?"**
Ölçüm değil, model. heat1d — Hayne'in 1-B regolit ısı difüzyon modeli, gezegen bilimi literatüründe standart. Etiketi `MODEL` ve kalibre edilmemiş; bunu her API cevabında söylüyoruz. Sentetik yedek de var, ama o `SYNTHETIC` etiketiyle dolaşıyor.

**S: "Kalibre etmediyseniz sayılara nasıl güveniyorsunuz?"**
Sayının mutlak doğruluğuna güvenmiyoruz — **sıralamasına** ve **dinamiğine** güveniyoruz. Yani "bu hücre şundan soğuk" ve "iç sıcaklık şu hızla düşüyor" ifadeleri kullanılabilir. "Bu hücre tam olarak −146,4 °C" iddiası yok. Diviner doğrulama altyapısı kodda hazır, veri dosyası eksik.

**S: "İç sıcaklık nasıl hesaplanıyor?"**
İki adımda: yüzey sıcaklığı katalogdaki parçalı ofsetlerle hedef iç sıcaklığa çevriliyor, sonra rover oraya anında değil zaman sabitiyle (LPR-1: 2 saat) üstel olarak yaklaşıyor. Bu ikinci adım C6'nın tamamının dayandığı şey.

**S: "Modelde bildiğiniz bir hata var mı?"**
Var ve raporluyoruz. Parçalı ofset modeli sınırda eser üretiyor: yüzey sıcaklığı −23,5 ile −0,4 °C arasındaki 13 kutu, +60 K soğuk ofseti yüzünden "sıcak-sınırlı" görünüyor. Fiziksel değil, model eseri — ve rapor bunu bu kelimelerle söylüyor.

**S: "Ay'da +80 °C mi oluyor gerçekten?"**
Ekvatorda evet. Ama Site11'de (−88,92° enlem) bizim modelimizde en sıcak nokta Güneş'e bakan 30 derecelik bir yamaçta +44,5 °C. Düz zeminde zirve −146,4 °C. Kutup bölgesi sürekli soğuk.
