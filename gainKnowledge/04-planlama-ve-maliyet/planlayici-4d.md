# 4-D Planlayıcı — "Bekle, Güneş Dönsün, Sonra Geç"

**Kodda:** `backend/app/pathfinder_4d.py`, `backend/app/cost_cube.py`
**API:** `POST /api/plan-4d`

---

## Nedir?

Zamanla genişletilmiş (time-expanded) A*. Durum artık iki değil **üç** bileşenli:

```
(satır, sütun, zaman_dilimi)
```

İki tür kenar var:

| Kenar | Hareket | Süre |
|---|---|---|
| **MOVE** | `(r, c, t) → (r', c', t + dt)` | `dt = ceil(sürüş_süresi / dilim_saati)` |
| **WAIT** | `(r, c, t) → (r, c, t + 1)` | Bir dilim |

**WAIT kenarı bu işin bütün noktası.**

---

## Hangi problemi çözüyor?

Ay kutbunda doğru cevap çoğu zaman şudur:

> **"Burada dur, Güneş dönsün, sonra geç."**

Bu bir statik planlayıcının **ifade edemeyeceği** bir karardır. 2-D A*'ın durumunda zaman yok; rover ya ilerliyor ya ilerlemiyor. "Şu an geçmek pahalı ama 3 saat sonra ucuz" cümlesi kurulamıyor.

4-D planlayıcı bu cümleyi kurabiliyor.

---

## Analoji: Trafik ışığı ve gelgit

**Trafik ışığı:** Kırmızı ışıkta duruyorsunuz. Neden? Çünkü şu anda geçmek yasak (sonsuz maliyet), ama 40 saniye sonra serbest olacak. Beklemek, hareket etmekten daha iyi bir *eylem*.

Bir GPS "durma" seçeneğini bilmiyorsa, sizi hep ışıksız ama uzun sokaklardan geçirirdi.

**Gelgit:** Deniz kıyısında bir kum bankından karşıya geçeceksiniz. Şu anda su yüksek, geçemezsiniz. Ama 4 saat sonra gelgit çekilecek ve yürüyerek geçebileceksiniz. Alternatif: 20 km dolaşmak.

Doğru cevap: **4 saat bekle.** Ama bu cevabı verebilmek için planlayıcının "zamanın geçmesi durumu değiştirir" fikrini bilmesi lazım.

Ay kutbunda Güneş, gelgittir.

---

## Nasıl çalışıyor?

### Maliyet küpü (`cost_cube.py`)

Maliyet artık tek bir grid değil, **grid yığını** — her zaman dilimi için bir tane.

```
maliyet_küpü[t, y, x]
```

Sadece zamana bağlı girdisi gölge olan hücreler her dilimde yeniden fiyatlanıyor. Eğim, enerji ve termal terimler paylaşılıyor (çünkü zamanla değişmiyorlar).

### Kabalaştırma bir optimizasyon değil, ölçek kararı

Bu önemli bir ayrım:

> 500×500 grid × 168 saatlik dilim = **42 milyon durum ≈ 1,3 GB.**

Bu yüzden 4-D planlayıcı kaba grid'de çalışıyor (80 m veya 320 m bloklar).

**Ve bu doğru olan:** aydınlanma 80 metre çözünürlükte değişmiyor. Yani kaba grid'de çözmek bir taviz değil, problemin doğal ölçeği.

### Kabalaştırma yöntemi — ince bir düzeltme

Yükseklik kabalaştırılırken `how="center"` kullanılıyor: bloğun **merkez hücresinin** değeri, blok ortalaması değil.

**Neden:** `/api/plan-4d` blok merkezlerini yol noktası olarak yayınlıyor. Rover iki merkez arasında sürerken karşılaştığı geometri, **o merkezlerdeki** geometri — iki bloğun ortalaması değil.

**Ölçülen etki:** Ortalama alma araziyi düzleştiriyordu ve kaba adım-eğimi kapısı **hiçbir şeyi reddetmiyordu**, ince kapı 1 894 kenarı reddederken. ("Round 4 review, L-11")

### Ufuk (horizon) boyutlandırma

Kaç dilim ileriye bakılacak? Varsayılan artık **en hızlı kapılı rotadan** (Dijkstra ile) boyutlanıyor.

Eski kural "BFS hamle sayısı × en yavaş kenar" idi ve slip altında taşıyordu: 113 hamlelik ay gecesi rotası eski kuralla **1 602 dilim** istiyordu, yenisiyle **270**.

---

## Reddetme sebepleri — tam liste

Planlayıcının bir kenarı reddedebileceği her sebep, `REJECTION_KEYS` sabitinde **bir kez** tanımlı:

| Anahtar | Anlamı |
|---|---|
| `step_slope` | Adım eğimi rover limitini aşıyor |
| `lateral_slope` | Yanal eğim limiti aşıyor (devrilme riski) |
| `nan_elevation` | Yükseklik verisi yok |
| `untraversable` | Geçilebilirlik maskesi kapalı |
| `corner_cut` | Köşe kesme yasağı |
| `cost_infinite` | Maliyet sonsuz |
| `horizon` | Zaman ufkunun ötesi |
| *(+ opsiyonel kısıtlar)* | safe haven, Dünya linki, termal dwell, survival |

**Neden tek yerde tanımlı:** Metrikler her zaman **tam anahtar kümesini** taşısın diye. Böylece bir çağıran *"kontrol edildi, hiç olmadı"* ile *"hiç sayılmadı"* arasındaki farkı görebiliyor. ("Round 4 review, H-2")

Bu küçük bir detay ama teşhis kabiliyeti için kritik: bir rota bulunamadığında hangi kapının kaç kez kapandığını görüyorsunuz.

---

## Opsiyonel kısıtlar — hepsi burada birleşiyor

4-D planlayıcı, projedeki bütün ileri özelliklerin buluştuğu yer:

| Parametre | Ne yapıyor | Feature |
|---|---|---|
| `require_earth_visibility` | Linksiz hücreye varan **hareketi** reddeder (bekleme serbest) | [A4](../03-konum-ve-iletisim/dunya-gorunurlugu-dte.md) |
| `require_safe_haven` | Her durumda `time_to_haven ≤ kalan link saati` | [A1](safe-haven.md) |
| `require_continuous_illumination` + `lit_rule` | Aydınlık koridoru dışını hiç aramaz | [A2](../02-isik-golge-ve-termal/aydinlik-koridoru.md) |
| `require_thermal_dwell` + `initial_inner_c` + `heater_model` | İç sıcaklığı zarf dışına çıkaran geçişi reddeder | [C6](../02-isik-golge-ve-termal/termal-dwell-ve-operasyon-zarfi.md) |
| `max_failure_probability` (β) | Yürütme başarısızlık olasılığını β'nın üstüne çıkaran hamleyi reddeder | [B1](survival-reach-avoid.md) |
| `risk_alpha` | Sıralama maliyetini CVaR kuyruğuyla değiştirir | [B2](cvar-risk.md) |

---

## Baskınlık eksenleri (dominance axes)

4-D arama sadece maliyet değil, birden fazla durum değişkenini takip ediyor. Bir etiket (label) başka bir etiketi ancak **her eksende** en az o kadar iyiyse baskılıyor.

C6 beşinci ekseni ekledi: **termal marj.**

**Kuantizasyon kritik:** Termal marj toleransı zarf genişliğinin onda biri, on anahtar kutusu.

Denenen alternatif: batarya ekseninin %1'i / 400 kutu → gündüz rotasının kısıtlı araması **2,3 GB ve on dakikayı aştı, bitmedi.**

Yani kaba kuantizasyon bir tercih değil, hesaplanabilirlik zorunluluğu.

---

## Ölçülen performans

| Senaryo | Süre | Düğüm |
|---|---|---|
| VIPER, kısıtsız | 452 ms | 7 233 |
| VIPER, aydınlık koridoruyla | 417 ms | 6 467 |
| İki haven arası VIPER planı (A1 kuralıyla) | 8,4 s | — |

Koridor kurulumu: 100 dilimde 135 ms, 246 dilimde ~0,3 s.

---

## 2-D planlayıcı dokunulmadı

Bu bilinçli: 4-D bir **yerine geçiş değil**, ek bir planlayıcı. 2-D hâlâ hızlı karşılaştırmalar, profil süpürmeleri ve çok-rota istekleri için kullanılıyor.

---

## Kodda nerede?

```
backend/app/pathfinder_4d.py
  astar_4d()                 ← zamanla genişletilmiş arama
  gated_move_count()
  REJECTION_KEYS             ← tam reddetme taksonomisi
  baskınlık eksenleri

backend/app/cost_cube.py
  build_cost_cube()          ← zaman dilimli maliyet yığını
  build_wait_cost_cube()
  coarsen_grid()             ← how="center" (merkez, ortalama değil)
  coarsen_traversable()
  auto_slice_hours()
  surface_temperature_series()  ← C6 ile bit-eşit paylaşılan seri
```

---

## Jüri soruları

**S: "4-D ne demek? Dört boyut nerede?"**
Durum uzayı (satır, sütun, zaman) üç bileşenli, ama arama dört boyutlu bir uzayda ilerliyor: üç durum + maliyet ekseni. Pratikte önemli olan zamanın durum olmasının kendisi — çünkü bu, "bekle" kararını mümkün kılıyor.

**S: "Beklemek gerçekten işe yarıyor mu?"**
Bazı senaryolarda evet, bazılarında hayır — ve sistem bunu dürüstçe raporluyor. Aydınlık koridoru testinde LPR-1 her risk seviyesinde aynı 42 hamleli rotayı seçti, sıfır bekleme. Ama bu, seçeneğin var olmadığı anlamına gelmiyor; o senaryoda beklemenin faydası yoktu. Önemli olan planlayıcının seçeneği **değerlendirebilmesi**.

**S: "Neden kaba grid? Hassasiyet kaybetmiyor musunuz?"**
Kaybetmiyoruz, çünkü aydınlanma 80 metre çözünürlükte zaten değişmiyor. Kabalaştırma bir optimizasyon değil, problemin doğal ölçeği. Alternatif 42 milyon durum ve 1,3 GB — hesaplanamaz.

**S: "Rota bulunamazsa ne oluyor?"**
404 dönüyor ve **hangi kapının kaç kez kapandığını** söylüyor. Örneğin C6 kısıtı açıkken gündüz rotası için "229 435 geçiş reddedildi (termal zarf)". Bu, operatörün hangi kısıtı gevşetmesi gerektiğini görmesini sağlıyor. Reddetme sebepleri tek bir sabitte tanımlı, o yüzden metrikler her zaman tam.

**S: "Bütün kısıtları aynı anda açabilir misiniz?"**
Teknik olarak evet, ama pratikte Site11'de sonuç genelde "rota yok" oluyor — ve bu bir bulgu. Örneğin A1 kuralı LPR-1 için Site11'de hiç safe haven bulamıyor, o yüzden `require_safe_haven` ile LPR-1 planı çıkmıyor. Bunu gizlemiyoruz.
