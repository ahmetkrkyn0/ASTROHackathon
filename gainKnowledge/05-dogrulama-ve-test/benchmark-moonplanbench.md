# Dış Benchmark: MoonPlanBench (D2) — Başkalarının Sınavına Girmek

**Kodda:** `backend/app/benchmark.py`
**API ucu:** **Yok** — sözleşme dokunulmadı
**Özellik kodu:** D2

---

## Nedir?

LunaPath'in, **kendi verisiyle değil, başkasının yayınladığı bir test setiyle** ve **başkasının kurallarıyla** değerlendirilmesi.

MoonPlanBench, Ay kutuplarının 36 doluluk (occupancy) grid'ini içeren akademik bir benchmark. LunaPath 36 haritanın hepsinde koşturuldu ve sonuç, makalenin kendi tablosunun **yanına** kondu.

---

## Hangi problemi çözüyor?

D2'den önce LunaPath'in tek planlayıcı karşılaştırması **Site11'deki kendi nav2 taban çizgisiydi.** Yani kendi sahasında, kendi kurallarıyla, kendi rakibine karşı.

Bu yeterli değil. Bir sistemin gerçekten iyi olup olmadığını anlamanın yolu, **bağımsız bir ölçüte** karşı test etmek.

---

## Analoji: Kendi sınavını yapmak vs. merkezi sınava girmek

Bir öğrenci kendi sorularını hazırlayıp kendine sınav yapsa ve 100 alsa, bu bir şey söylemez. Soruları kendi bildiklerinden seçmiştir.

Merkezi sınav farklı: **soruları başkası hazırlıyor**, herkes aynı sınava giriyor, sonuçlar karşılaştırılabilir.

Ama bir incelik var: **merkezi sınav belki sizin güçlü olduğunuz şeyi ölçmüyordur.** Bir müzisyeni matematik sınavına sokup "kötü" demek adaletsiz olur.

D2'nin en dürüst kısmı tam burası: sınava girdik, sonucu yayınladık, **ve sınavın neyi ölçmediğini de söyledik.**

---

## MoonPlanBench nedir?

**Kaynak:** Chancán, Banerjee, Nikolakopoulos — *Planetary Terrain Datasets and Benchmarks for Rover Path Planning*, arXiv:2512.21438v1, Aralık 2025. Kod: `github.com/mchancan/PlanetaryPathBench` (`86dc4b63` sürümü).

**İçeriği (5 Eylül 2026'da depodan okunmuş hâliyle):**

- **36 doluluk grid'i** = 12 LOLA kutup DEM ürünü (LDEM_45N_100M … LDEM_875S_5M) × üç eğim/pürüzlülük eşiği (10°, 15°, 20°)
- 64 kat alt-örneklenmiş → hücre boyutu **320 m ile 7,68 km** arası
- `.npy` `uint8` formatında; sıfır olmayan = dolu
- 243² – 477² hücre, boş oran %51–96
- **Depoda değil** — yazarların Google Drive'ından çekiliyor
- Lisans: makale CC BY-NC-SA 4.0; Drive klasörünün kendi lisans dosyası yok. **Veri depoya girmiyor.**

---

## Nasıl çalışıyor?

### Benchmark'ın kuralları koddan okundu, tahmin edilmedi

Bu, D2'nin metodolojik özeni.

**Başlangıç ve hedef yayınlanmış bir liste değil** — `adapters/_common.auto_select_start_goal` fonksiyonu tarafından **tanımlanıyor**:

1. En büyük 8-bağlı boş bileşeni bul
2. Sözlük sırasına göre en küçük `(y, x)` = başlangıç
3. En uzak nokta = hedef

Bu fonksiyon **aynı BFS sırasıyla yeniden yazıldı** ve deponun kendi fonksiyonuyla **36/36 haritada eşit** çıktı.

> Yani "aynı problemi çözdüğümüzden" emin olmak için, problemin tanımını üreten kodu bile doğruladık.

### Kritik fark: köşe kesme

**Referans planlayıcılar** (PythonRobotics Dijkstra / A* / Theta*): 8-komşulukta, maliyetler 1 ve √2, **köşe kesme kuralı YOK** — yani iki dolu hücre arasından çapraz adım **yasal**.

**LunaPath** (ve nav2 taban çizgisi): köşe kesmeyi **reddediyor**. İki kayanın arasından çapraz geçmek fiziksel olarak mümkün değil.

**Çözüm:** Her iki hareket modeli de **yan yana** koşturuldu. Sonuçlar iki satır hâlinde gösteriliyor.

### Metrikler — PathBench'in kendi metrikleri

`basic_testing.get_results` ve `analyzer`'dan:

| Metrik | Tanım |
|---|---|
| Başarı | Ajanın son hücresi hedefe eşit |
| Yol uzunluğu | Öklid adımlarının toplamı (hücre cinsinden) |
| Düzgünlük | İşaretsiz başlık açısının ortalama mutlak değişimi |
| Açıklık | Her iz noktasının en yakın dolu hücreye ortalama mesafesi |
| Kalan mesafe | Son noktadan hedefe (hiç planlanmadıysa: başlangıçtan hedefe) |
| Planlama süresi | Saniye, 60 s limit |
| Bellek | `tracemalloc` zirvesi |

**Ortalama kuralı:** Uzunluk / adım / süre / düzgünlük / açıklık ortalamaları **yalnız başarılı koşumlar** üzerinden; kalan mesafe ve bellek **bütün koşumlar** üzerinden.

---

## Ölçülen sonuçlar (36 harita)

### Saf mesafe Dijkstra, benchmark'ın hareket modeliyle

| Eşik | Başarı | Ortalama yol (hücre) |
|---|---|---|
| MoonPlanBench-10 | **%100** | 651,81 |
| MoonPlanBench-15 | **%100** | 636,16 |
| MoonPlanBench-20 | **%100** | 620,24 |

**Makalenin Dijkstra satırıyla iki ondalık basamağa kadar aynı, üç varyantta da.**

Bu, uygulamamızın doğru olduğunun kanıtı: aynı problemi, aynı kurallarla çözünce aynı sayıyı üretiyoruz.

### LunaPath'in köşe kesme yasağıyla

| Eşik | Başarı | Ortalama yol |
|---|---|---|
| MoonPlanBench-10 | **%33,3** | 720,30 |
| MoonPlanBench-15 | %91,7 | 658,34 |
| MoonPlanBench-20 | **%100** | 631,88 |

### %33 neden? — kritik açıklama

> **MoonPlanBench-10'da on iki haritanın sekizi, YALNIZ iki dolu hücre arasındaki çapraz hamlelerle bağlantılı.**

Yani bu haritalarda başlangıç ve hedef, sadece fiziksel olarak imkânsız bir manevrayla birbirine bağlanıyor.

**Ve doğrulandı:** *"Köşesiz Dijkstra'nın yol bulduğu her yerde LunaPath da buluyor."*

**Sonuç:** Fark planlayıcıda değil, **hareket modelinde.**

Bu, benchmark'ın bir eleştirisi değil; benchmark'ın neyi ölçtüğünün tespiti.

### Hız

| Planlayıcı | Harita başına süre |
|---|---|
| **LunaPath A*** | **0,22 – 0,39 s** |
| PythonRobotics Dijkstra (aynı makine) | 3,3 – 8,2 s |
| PythonRobotics A* (aynı makine) | 7,8 – 13,5 s |
| Makalenin bildirdiği | 13 – 32 s |

LunaPath, referans uygulamalardan **bir mertebe hızlı.**

### Yöntem bulgusu: tracemalloc ölçümü bozuyor

`tracemalloc` (bellek profilleyici) açıkken LunaPath **5,8 – 11,8 saniyeye** çıkıyor — yaklaşık **30 kat yavaşlama.**

**Sonuç:** Süre ve bellek **ayrı geçişlerde** ölçülüyor.

> Bu, kendi başına yararlı bir metodoloji notu: Python'da bellek profilleyici açıkken ölçülen süre, süre değildir.

### Çok kriterli mod hiçbir şey kazandırmıyor — ve bunu söylüyoruz

LunaPath'in asıl gücü beş kriterli maliyet modeli. Ama:

> **Haritalarda gölge, termal, slip, pürüzlülük veya DEM katmanı olmadığı için, maliyet grid'i 36 haritanın hepsinde tek bir değer: 0,190969.**

Yani benchmark, LunaPath'in ayırt edici özelliğini **ölçemiyor**. Sadece doluluk var, arazi özelliği yok.

**Ve bu açıkça raporlanıyor** — "çok kriterli planlayıcımız burada da kazandı" gibi bir iddia yok.

---

## İddia sınırı

> **Yalnız doluluk bilgisi olan, eğim eşikli, hücresi 320 m – 7,7 km olan bir benchmark, bir hareket modeli altında BAĞLANTILILIĞI ölçer — rover rota planlamasını değil.**

Ek notlar:
- Makalenin %100 başarısı, LunaPath'in reddettiği köşe kesmeye dayanıyor. **İki satır da gösteriliyor.**
- Öğrenmeli planlayıcı bulguları makalenin — **alıntı**, tekrar edilmedi.
- Makalenin Tablo 1'i `PAPER_TABLE_1` sabitinde **alıntı olarak** duruyor ve hiçbir zaman bizim ölçümümüzle karıştırılmıyor.

---

## Kodda nerede?

```
backend/app/benchmark.py
  auto_select_start_goal()   ← benchmark'ın kuralı, yeniden yazılmış, 36/36 doğrulanmış
  CLAIM                      ← iddia sınırları
  PAPER_TABLE_1              ← makalenin sayıları, alıntı

scripts/build_moonplanbench_cache.py   ← Drive'dan veri çeker
scripts/moonplanbench_runner.py
scripts/nav2_baseline.py
docs/research/moonplanbench_report.md
```
54 yeni test. **API ucu yok** — bu bir değerlendirme aracı, ürün özelliği değil.

---

## Jüri soruları

**S: "Dış bir benchmark'ta test ettiniz mi?"**
Evet. MoonPlanBench — Aralık 2025'te yayınlanmış, 36 Ay kutbu doluluk grid'i içeren akademik bir benchmark. 36 haritanın hepsinde, benchmark'ın kendi problem tanımıyla koştuk.

**S: "Sonuç ne?"**
İki cevap var ve ikisini de veriyoruz. Benchmark'ın kendi hareket modeliyle (köşe kesme serbest) çalıştırdığımızda **%100 başarı** ve makalenin Dijkstra satırıyla **iki ondalık basamağa kadar aynı** sayılar — yani uygulamamız doğru. Kendi köşe kesme yasağımızla %33,3 / %91,7 / %100. Fark tamamen hareket modelinden.

**S: "%33 kötü bir sonuç değil mi?"**
Sebebi açık ve ölçüldü: MoonPlanBench-10'da on iki haritanın sekizinde başlangıç ve hedef **sadece iki dolu hücre arasındaki çapraz hamlelerle** bağlantılı. Yani o haritalarda "çözüm", fiziksel olarak imkânsız bir manevra. Biz o manevrayı reddediyoruz. Ve doğrulandı: köşesiz Dijkstra'nın yol bulduğu her yerde biz de buluyoruz.

**S: "Hızınız nasıl?"**
Harita başına 0,22–0,39 saniye. Aynı makinede PythonRobotics Dijkstra 3,3–8,2 s, A* 7,8–13,5 s. Makale kendi ölçümünde 13–32 s bildiriyor. Bir mertebe hızlıyız.

**S: "Çok kriterli planlayıcınız burada avantaj sağladı mı?"**
Hayır ve bunu açıkça söylüyoruz. Benchmark'ın haritalarında gölge, termal, slip, pürüzlülük veya yükseklik yok — sadece doluluk. Maliyet grid'imiz 36 haritanın hepsinde tek bir değer (0,190969) veriyor. Yani benchmark bizim ayırt edici özelliğimizi ölçemiyor. Bu bizim eksiğimiz değil, benchmark'ın kapsamı — ama iddia etmiyoruz.

**S: "Benchmark'ın kurallarını doğru uyguladığınızdan emin misiniz?"**
Evet, iki kanıtla. Birincisi: başlangıç/hedef seçimi yayınlanmış bir liste değil, bir fonksiyon tarafından tanımlanıyor; o fonksiyonu aynı BFS sırasıyla yeniden yazdık ve 36/36 haritada deponun kendi çıktısıyla eşit çıktı. İkincisi: benchmark'ın hareket modeliyle koştuğumuzda makalenin Dijkstra satırını iki ondalık basamağa kadar üretiyoruz.

**S: "Neden API ucu yok?"**
Çünkü bu bir ürün özelliği değil, bir değerlendirme aracı. Sözleşmeye dokunmadık.
