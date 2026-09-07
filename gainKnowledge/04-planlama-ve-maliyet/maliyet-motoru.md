# Maliyet Motoru — "Bu Hücreden Geçmek Ne Kadar Kötü?"

**Kodda:** `backend/app/cost_engine.py`, `backend/app/cost_vec.py`, `backend/app/costmap.py`
**Sürüm kimliği:** `COST_MODEL_ID = "weighted_cell_cost_shadow_aware_energy_slip_roughness_v5"`

---

## Nedir?

Maliyet motoru, arazinin her hücresine **0 ile 1 arasında bir "kötülük puanı"** veren sistem. Geçilemez hücreler sonsuz puan alıyor.

Puan beş kriterin ağırlıklı toplamı:

```
maliyet = w_eğim × f_eğim + w_enerji × f_enerji + w_gölge × f_gölge
        + w_termal × f_termal + w_pürüzlülük × f_pürüzlülük
```

Bu, planlayıcının gördüğü tek şey. Planlayıcı eğimi, sıcaklığı veya gölgeyi bilmez — sadece bu puanı bilir.

---

## Hangi problemi çözüyor?

"En iyi rota" tanımsız bir kavramdır, çünkü "iyi" birden fazla şeyi aynı anda ifade eder:

- En kısa mı? → gölgeden geçebilir
- En aydınlık mı? → çok uzun olabilir
- En düz mü? → çok soğuk yerden geçebilir
- En az enerji mi? → çok yavaş olabilir

Bu kriterler **birbiriyle çelişiyor**. Maliyet motoru, çelişkiyi tek bir sayıya indirgeyerek "en iyi"yi tanımlanabilir hâle getiriyor.

---

## Analoji: Otel puanlama sitesi

Bir otel arıyorsunuz. Site size her oteli tek bir puanla gösteriyor: 8,4 / 10.

Ama o puan aslında beş şeyden geliyor: temizlik, konum, personel, fiyat, konfor. Ve site sizin bunlara ne kadar önem verdiğinizi biliyor — mesela fiyat sizin için çok önemliyse fiyat ağırlığı yüksek.

İki kişi aynı otele bakıp farklı puan görebilir, çünkü ağırlıkları farklı.

LunaPath'te de öyle: **aynı arazi, farklı misyon profili → farklı maliyet haritası → farklı rota.** "Enerji tasarrufu" profili başka bir yol seçer, "hızlı keşif" profili başka.

---

## Beş kriter

### 1. `f_slope` — Eğim cezası

```
f_eğim = sigmoid(0.4 × (eğim − rahat_eğim))
```

Sigmoid eğrisi: rahat eğime kadar düşük ceza, sonra hızla tırmanıyor, sonra doyuyor.

`rover.slope_max_deg`'in üstünde **sonsuz** — yani geçilemez.

LPR-1: rahat eğim 15°, maksimum 25°.

### 2. `f_energy_cell` — Enerji cezası

*"Bu hücre, mümkün olan en ucuz hücreden (düz ve tamamen aydınlık) ne kadar daha fazla enerjiye mal oluyor?"*

En kötü kabul edilebilir hücre (rover'ın eğim limitinde, tamamen gölgede) 1,0 okuyor.

**Bu kriterin iki kez düzeltilmesi gerekti ve hikâyesi öğretici — aşağıda.**

### 3. `f_shadow_cell` — Gölge cezası

Hücre başına gölge oranı vekili. (Yol bağımlı olan `f_shadow` versiyonu birikmiş gölge saatlerini alıyor ve üstel; rover'ın `h_max_shadow_h` dayanımına ulaşınca 1,0.)

### 4. `f_thermal` — Termal ceza

Hücrenin **iki ucu da** değerlendiriliyor: yıllık zirve ve soğuk uç denge sıcaklığı. **Kötü olan kazanıyor.**

> Mantığı: bir hücre iki uçtan birinde bile hayatta kalınamazsa, diğer uç onu güvenli yapmıyor. Rover zarfın **içinde** oturmak zorunda, ucunda değil. ("Round 4 review, H-3")

### 5. `f_roughness` — Pürüzlülük cezası (C4)

NASA'nın ölçülmüş LDRM verisi, bölgesel yüzdelik sıralamasıyla 0-1'e eşleniyor. Detay: [pürüzlülük ve PSR](../01-arazi-ve-veri/puruzluluk-ve-psr.md).

---

## Ağırlıklar nereden geliyor?

**AHP** (Analytic Hierarchy Process — Analitik Hiyerarşi Süreci) ile belirlenmiş. LPR-1 için:

| Kriter | Ağırlık |
|---|---|
| Eğim | **0,409** |
| Enerji | **0,259** |
| Termal | **0,190** |
| Gölge | **0,142** |
| Pürüzlülük | **0,15** (C4, katalog varsayılanı) |

Her rover'ın kendi ağırlık vektörü var. Ve `resolve_weights` istekten gelen ağırlıkları üstüne yazıyor — **normalizasyon yok, toplam kontrolü yok.** Toplamın 1 olması bir konvansiyondu, planlayıcının okuduğu bir kısıt değil. C4 beşinci ağırlığı eklerken dördünü yeniden ölçeklemedi, tam da bu yüzden.

---

## En öğretici hikâye: iki kriterin çökmesi

Bu bölüm, jüriye anlatılabilecek en iyi teknik hikâyelerden biri — çünkü sistemin kendi kendini denetlediğini gösteriyor.

### Çöküş 1: Enerji terimi hiçbir şeye karar vermiyordu

**Belirti:** `w_energy` ağırlığını 0,0'dan 2,0'a süpürdüler. Rota **byte-byte aynı** kaldı.

**Teşhis:** Eski `f_energy` bir kenarın enerjisini **batarya kapasitesinin oranı** olarak raporluyordu. 5 metrelik bir kenar ~1,4 Wh çekiyor, batarya 5 420 Wh. Yani terim `[0,00026 – 0,00074]` aralığında sıkışmıştı — diğer kriterler `[0,02 – 1,0]` aralığında gezinirken.

0,259 ağırlıkla çarpıldığında hücre maliyetine katkısı: **%0,04.**

**Sonuç:** AHP ağırlık vektörünün dörtte biri hiçbir şeye karar vermiyordu.

**Düzeltme:** `f_energy_cell` — mutlak enerji yerine **göreli** enerji ("en ucuz hücreye göre kaç kat pahalı"). Bu oran kenar uzunluğundan bağımsız, dolayısıyla grid çözünürlüğüyle sessizce yeniden ölçeklenmiyor.

### Çöküş 2: Düzeltme daha ince bir problem bıraktı

**Belirti:** Düzeltilmiş enerji terimi **sadece eğimi** okuyordu. `f_slope` de sadece eğimi okuyordu.

**Ölçüm:** Üretim eğim dağılımı üzerinde iki cezanın Spearman korelasyonu: **tam olarak 1,000000.**

**Teşhis:** Dört AHP kriterinden ikisi, **farklı eğriler altında aynı sıralamayı** ifade ediyordu. `w_slope + w_energy` = 0,668 — yani varsayılan ağırlık vektörünün üçte ikisi **tek bir tercihi** ifade ediyordu, iki değil.

**Düzeltme:** Enerji terimi artık **gölgeyi de okuyor.** Sebebi fiziksel: karanlık bir hücrede ısıtıcı yükü, bir geçişin maliyetinin gerçek ve birinci mertebeden parçası. Ve bu, "bu eğimi tırmanmak rahat mı" sorusundan gerçekten farklı bir soru.

`COST_MODEL_ID` → **v3**. ("Round 3 review, H-4")

### Aynı çöküş gölge teriminde de olmuştu

`f_shadow_cell`'in dokümanı aynı çöküşü kaydediyor — orada düzeltilmiş, enerjide gözden kaçmıştı.

**Ders:** Bir ağırlık vektörü ne kadar özenle hesaplanırsa hesaplansın, altındaki kriterler aynı şeyi ölçüyorsa hiçbir anlamı yok. **Ağırlıkları test etmenin yolu, süpürüp sonucun değişip değişmediğine bakmak.**

---

## `edge_travel_time_s` — sistemin tek kalbi

Bu fonksiyon, projedeki **en kritik tek fonksiyon**. Her süre ve her enerji rakamı ondan türüyor:

```
edge_travel_time_s
    ├─ edge_energy_wh
    ├─ per-metre enerjiler
    ├─ move_battery_drain_wh
    ├─ maliyet grid'inin enerji kriteri
    ├─ 4-D planlayıcının hamle uzunluğu
    ├─ simülatör
    ├─ koridor bütçeleri
    ├─ Monte Carlo bacakları
    ├─ safe haven mesafeleri
    ├─ koridor dilim sayıları
    └─ auto_slice_hours
```

C3 (slip modeli) tam olarak buraya bağlandı: komut mesafesi, tekerlek mesafesine çevriliyor (`d / (1 − slip)`).

**Tek bağlanma noktası olduğu için** her tüketici otomatik olarak tutarlı. Slip'i on ayrı yere eklemek gerekseydi, biri unutulurdu.

---

## Katmanlı maliyet haritası (`costmap.py`)

Nav2'nin `costmap_2d` desenini ödünç alıyor: maliyet tek bir dizi değil, **katman yığını**. Her katman kendi ağırlığını, kendi soyağacını ve kendi güncellemesini taşıyor.

**Kazancı:** `CostMap.explain()` — hücre başına hangi kriterin maliyeti sürüklediğinin dökümü. Bu, *"neden bu rota?"* sorusunun teknik cevabı.

Yeni bir kriter eklemek, monolitik bir fonksiyonu düzenlemek değil, bir `CostLayer` eklemek demek.

---

## Vektörel ikiz (`cost_vec.py`)

Her cezanın iki hâli var:

| Dosya | Ne | Rol |
|---|---|---|
| `cost_engine.py` | Tek hücre için skaler fonksiyonlar | **Doğruluk kaynağı** — dokümanların ve testlerin anlattığı formüller |
| `cost_vec.py` | Tüm grid için NumPy fonksiyonları | Hız |

**Neden var:** Katmanlı maliyet haritası eskiden `np.vectorize` kullanıyordu — ki bu, dizi şeklinde bir API'nin arkasındaki Python döngüsüdür, gerçek vektörleştirme değil. Her iki maliyet yolu da 500×500 çağrı başına ~1,3–1,5 saniye tutuyordu, üstelik istek yolunda, plan başına iki kez.

**Garanti:** `test_review_fixes`, buradaki her fonksiyonun `cost_engine` karşılığıyla girdi alanı boyunca eşleştiğini iddia ediyor. Yani birini değiştirip diğerini unutursanız **test kırılır**, planlayıcı sessizce `CostMap.explain()`'den ayrışmaz.

---

## Sürüm kilidi

`COST_MODEL_ID` her formül değişikliğinde artıyor:

| Sürüm | Değişiklik |
|---|---|
| v1 | İlk hâli |
| v2 | `f_energy` → `f_energy_cell` (çöküş 1) |
| v3 | Enerji terimi gölgeyi de okuyor (çöküş 2) |
| v4 | `edge_travel_time_s` slip uyguluyor (C3) |
| v5 | Beşinci kriter: pürüzlülük (C4) |

**Neden önemli:** Diskteki bir `.npy` maliyet grid'i veya bir önbellek dizini, eski formülle hesaplanmışsa artık geçerli olmadığını **anlayabiliyor** — sessizce yeniden kullanılmıyor.

Not: B2 (risk iştahı) bu kimliği artırmıyor. `risk_alpha=None` iken grid v4'ün işlem-işlem aynısı; bir alfa altında kurulmuş grid ayrıca `metadata["risk_alpha"]` ile anahtarlanıyor.

---

## Kodda nerede?

```
backend/app/cost_engine.py
  f_slope() / f_energy_cell() / f_shadow_cell() / f_thermal() / f_roughness()
  compute_cost_grid()        ← beş kriterin ağırlıklı toplamı
  edge_travel_time_s()       ← TEK bağlanma noktası
  edge_energy_wh() / gross_energy_per_metre_wh() / housekeeping_power_w()
  resolve_weights()          ← rover varsayılanı + istek üstüne yazımı
  COST_MODEL_ID

backend/app/cost_vec.py      ← vektörel ikizler (testle kilitli)
backend/app/costmap.py       ← katmanlı harita, CostMap.explain()
```

---

## Jüri soruları

**S: "Ağırlıkları nasıl belirlediniz?"**
AHP — Analitik Hiyerarşi Süreci ile, kriterleri ikili karşılaştırarak. LPR-1 için eğim 0,409, enerji 0,259, termal 0,190, gölge 0,142. Ama daha önemlisi: bu ağırlıkların gerçekten iş yapıp yapmadığını **test ettik** ve iki tanesinin yapmadığını bulduk.

**S: "Ağırlıkların iş yapmaması ne demek?"**
Enerji ağırlığını 0'dan 2'ye süpürdüğümüzde rota byte-byte aynı kaldı. Çünkü enerji terimi batarya kapasitesinin oranı olarak hesaplanıyordu ve 5 metrelik bir kenar 5 420 Wh'lik bataryanın binde birini bile çekmiyordu. Terim matematiksel olarak doğru, pratik olarak ölüydü. Göreli enerjiye çevirerek düzelttik.

**S: "Kriterler birbirinden bağımsız mı?"**
Şimdi evet, ama bir dönem değildi. Düzeltilmiş enerji terimi sadece eğimi okuyordu ve `f_slope` de öyle — ikisinin Spearman korelasyonu tam 1,000000 çıktı. Yani ağırlık vektörünün üçte ikisi tek bir tercihi ifade ediyordu. Enerji terimine gölgeyi de okuttuk; karanlık hücredeki ısıtıcı yükü gerçek ve eğimden bağımsız bir maliyet.

**S: "Pürüzlülük eğimin tekrarı değil mi?"**
Değil, ölçtük: Spearman 0,213. Detay [pürüzlülük dosyasında](../01-arazi-ve-veri/puruzluluk-ve-psr.md).

**S: "Neden 'neden bu rota?' sorusuna cevap verebiliyorsunuz?"**
Çünkü maliyet tek bir dizi değil, katman yığını (Nav2'nin costmap_2d deseni). `CostMap.explain()` her hücre için hangi kriterin maliyeti sürüklediğini döküyor. Tek bir toplam sayı olsaydı bu mümkün olmazdı.

**S: "İki ayrı implementasyon riskli değil mi?"**
Riskli, o yüzden testle kilitledik. `cost_vec` içindeki her fonksiyon, `cost_engine` karşılığıyla girdi alanı boyunca karşılaştırılıyor. Birini değiştirip diğerini unutursanız test kırılıyor.
