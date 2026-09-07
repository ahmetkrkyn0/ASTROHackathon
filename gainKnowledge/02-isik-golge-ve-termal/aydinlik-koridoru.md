# Sürekli-Aydınlık Koridoru (A2) — Hiç Karanlığa Girmeyen Yol

**Kodda:** `backend/app/illumination_corridor.py`
**API:** `GET /api/illumination-corridor`, `/api/plan-4d` içinde `require_continuous_illumination` + `lit_rule`
**Özellik kodu:** A2

---

## Nedir?

Arazinin (x, y, zaman) üç boyutlu hacminde, **"hem aydınlık hem güvenli"** olan bölgeleri bulup birbirine bağlayan bir ön filtre. Planlayıcı sonra sadece bu hacmin içinde arama yapıyor.

Sonuç garantisi: koridorun içinde kalan bir rover **tanım gereği hiç gölgeye girmez.**

---

## Hangi problemi çözüyor?

Bir rover için gölge sadece "karanlık" değil, **enerji kesintisi** demek. Güneş paneli çalışmıyor, batarya boşalıyor, ısıtıcı bataryayı yiyor.

Normal planlayıcı gölgeyi bir *maliyet* olarak görür: "burası pahalı ama geçebilirim." Bazı misyonlarda bu yeterli değil — istenen şey **kesin garanti**: "bu rota boyunca rover asla karanlıkta kalmayacak."

A2 bu garantiyi veriyor. Ve garantiyi arama sonrası kontrol ederek değil, **arama uzayını daraltarak** veriyor — yani planlayıcı karanlık bir yolu bulup sonra reddetmiyor, o yolu hiç görmüyor.

---

## Analoji: Güneş takip eden gölgelik

Bir plajda, çadırınızın gölgesi güneş hareket ettikçe kayıyor. Siz de "hep gölgede kalayım" derseniz, çadırın gölgesiyle birlikte yavaşça yer değiştirirsiniz.

A2'nin yaptığı şeyin tersi ama mantığı aynı: rover **hep ışıkta kalmak** istiyor ve ışık alanı zamanla kayıyor. Yani rover'ın "hep ışıkta" kalabilmesi için gideceği yol, ışığın hareketiyle uyumlu olmak zorunda.

Bir başka analoji daha net: **taş sekerek dere geçmek.** Derede bazı taşlar suyun üstünde, bazıları altında — ve gelgitle bu değişiyor. Siz sadece "şu an suyun üstünde olan taşlara" basabilirsiniz. A2, "hangi taşlardan hangi zamanda hangi taşa atlanabilir" grafiğini önceden çıkarıyor. Grafikte olmayan bir atlayış hiç düşünülmüyor.

---

## Nasıl çalışıyor?

### CMU'nun yöntemi

Carnegie Mellon Üniversitesi'nden Otten, Jones, Wettergreen ve Whittaker (ICRA 2015, FSR 2017) güneş-senkron kutup rotaları için şunu yapıyor:

1. Aydınlanma zaman serisini eğim maskesiyle çarpıp bir **(t, y, x) hacmi** kur
2. "Aydınlık ve güvenli eğimde" voksellerini 3×3×3 çekirdekle **taşma doldur** (flood fill) — yani birbirine bağlı bölgeleri bul
3. **İleri buda:** pencerenin başlangıcından ulaşılamayan kökleri at
4. **Geri buda:** pencerenin sonuna hiç ulaşamayan çıkmazları at
5. Hayatta kalan hacim = koridor. A* sadece orada arasın.

### LunaPath'in uyarlaması — ve neden aynen kopyalanamadı

CMU'nun hücreleri 5 metre ve zaman dilimleri uzun; onların grafiğinde rover bir sonraki dilimde dokuz komşudan birine gider.

LunaPath'in planlayıcısı **320 metrelik bloklarla** çalışıyor ve dilimler bir geçişe göre boyutlandırılmış. Yani bir hamle **birkaç dilim sürüyor**.

Bu yüzden koridor, planlayıcının **kendi kenarları üzerinde** kurulmak zorunda:

- Aynı geçilebilirlik kapıları
- Aynı köşe kesme kuralı
- Aynı adım eğimi ve yanal eğim kapıları
- Sürüş süresi planlayıcının kendi işlem sırasıyla yeniden hesaplanıyor

**Koridor kenarı kuralı:**

> Bir hamle `(r,c,t) → (r',c',t+d)` ancak **iki blok da t ile t+d arasındaki her dilimde ışıklı ve geçilebilirse** koridor kenarıdır.

Sebebi basit: rover geçiş boyunca ikisinden birinin içinde. Bekleme hamlesi için de her iki voksel gerekli.

### "Işıklı" ne demek? — istekte seçiliyor

| `lit_rule` | Anlamı | Karakteri |
|---|---|---|
| `"all"` (varsayılan) | Bloğun **her** ince hücresi ışıklı (blok gölge oranı sıfır) | Muhafazakâr |
| `"majority"` | Blok ortalaması gölge < 0,5 | Planlayıcının kendi karanlık eşiği |

Her iki durumda da koridor içindeki rota, planlayıcının muhasebesinde **sıfır gölge saati** biriktirir.

---

## Site11'de ölçülen gerçek sayılar

**Senaryo:** NASA VIPER, 2027-05-30, 9,6 saatlik ufuk (100 dilim × 0,0956 sa), 320 m'de 125×125 blok

| Ölçüm | Değer |
|---|---|
| Geçilebilir hacmin ışıklı-ve-güvenli oranı (`all`) | **%40,5** |
| Aynısı `majority` ile | %45,8 |
| İki budama geçişinin buduğu oran | **sadece %0,2** |
| Bağlı bileşen sayısı | 50 (en büyüğü %91) |

### Neden budama az budadı? — dürüst raporlama örneği

CMU'nun budama adımı 59 günlük pencerelerde çok iş yapıyor. Bizim 10 saatlik penceremizde neredeyse hiçbir şey budamıyor (%0,2).

**Sebebi:** Kutup aydınlanması 10 saatte neredeyse durağan. Güneş saatte 0,009 derece yükseliyor — 10 saatte gölge sınırı kayda değer kaymıyor.

Bu, tekniğin işe yaramadığı anlamına gelmiyor; **pencere boyutuna bağlı olduğu** anlamına geliyor. Ve öyle raporlanıyor.

### Standart rota koridoru geçemedi

VIPER'ın standart haven-haven çifti güneş-senkron değil:
- Başlangıç bloğu ilk dilimde karanlık
- Hedef bloğu hiç ışıklı olmuyor
- Rota 4,55 saat gölgede

Kural bu rotayı **sayılarla** reddediyor — 404 dönerken koridorun istatistiklerini de veriyor, böylece operatör neden reddedildiğini görüyor.

### Koridor içindeki bir çift ne veriyor?

62 blok, 8 saatlik pencere:

| Metrik | Değer |
|---|---|
| `path_dark_hours` | **0** (garanti çalıştı) |
| LP-R01 robustluk marjı | **96,00 saat** = rover'ın tam dayanımı |
| Hamle / bekleme | 62 / 0 |
| Süre | 7,90 saat |
| Minimum batarya | %93,6 |

### Performans — abartısız raporlama

| | Süre | Düğüm |
|---|---|---|
| Kısıtsız arama | 452 ms | 7 233 |
| Koridorlu arama | **417 ms** | 6 467 |

Hızlanma ×1,08. **Mütevazı ve öyle raporlandı.**

Sebebi: maliyet küpü gölgeyi zaten fiyatlıyor, o yüzden kısıtsız arama da genellikle koridorun içinde kalıyor. Literatürdeki bazı çalışmalardaki gibi "22 saniyeden X saniyeye" türü bir hızlanma iddiamız **yok**.

Koridor kurulum maliyeti: 100 dilimde 135 ms, 246 dilimde ~0,3 s.

> Optimizasyon notu: ilk sürüm zaman ekseninde "fancy indexing" kullanıyordu (591 ms / 1,7 s). Dilim başına dilimleme ×10 daha hızlı ve voksel-voksel aynı sonucu veriyor. İki yol da kodda korunup çapraz kontrol ediliyor.

### Diğer senaryolar — sistem "yok" demeyi biliyor

| Senaryo | Sonuç |
|---|---|
| LPR-1, 2026-09-28, 2,9 saatlik ufuk | Sadece %4,8 ışıklı; 8 saatte koridor **hiç yok** |
| LPR-1, ay gecesi 2026-09-13 | Hiçbir blok ışıklı değil → 404: *"246 dilimin hiçbirinde ışıklı blok yok"* |

---

## İlham kaynağı

**Otten, Jones, Wettergreen, Whittaker** — Carnegie Mellon University
- ICRA 2015
- FSR 2017
- Otten'in doktora tezi

Güneş-senkron kutup rotası planlama: aydınlanma zaman serisini eğim maskesi üstüne yığıp (t, y, x) hacmi kurma, taşma doldurma, çift yönlü budama.

**Bizim katkımız:** koridorun planlayıcının kendi kaba grid'i, kendi kenarları ve kendi dilim aritmetiği üzerinde kurulması — çünkü bizim hamlelerimiz birden fazla dilim sürüyor, CMU'nunkiler tek dilim.

---

## İddia sınırı

- İddia **MODEL** hakkında: SPICE Güneş konumu, ufuk küpü (72 azimut, iki ölçek), 320 m bloklar, örneklenmiş dilimler.
- B3'ün bulgusu her cevapla birlikte taşınıyor: **2027-05-30'da hücrelerin %10,8'i klonlar arasında ışıklı/karanlık kararsız.**
- ❌ **"Gerçek yüzey rover'ı hiç gölgelemez" denmiyor.** Modelimizin içinde garanti var; gerçeklikte belirsizlik payı var ve o pay sayıyla ifade ediliyor.

---

## Kodda nerede?

```
backend/app/illumination_corridor.py
  edge_tables()              ← planlayıcının kenarlarıyla koridor grafiği
  UNCERTAINTY_NOTE           ← her cevapla giden B3 uyarısı

scripts/illumination_corridor_report.py
docs/research/illumination_corridor_report.md
```
82 yeni test eklendi.

---

## Jüri soruları

**S: "Bu ne kadar hızlandırdı planlamayı?"**
Çok az: ×1,08. Ve bunu saklamıyoruz. Sebebi, maliyet küpünün gölgeyi zaten fiyatlıyor olması — kısıtsız arama da çoğu zaman koridorda kalıyor. A2'nin değeri hız değil, **garanti**: "bu rota boyunca rover asla karanlığa girmeyecek" cümlesini kurabilmek.

**S: "Neden CMU'nun kodunu kullanmadınız?"**
Yöntemleri uygulanabilir ama grafikleri bizimkiyle uyumsuz. Onlarda bir hamle bir dilim; bizde bir hamle birkaç dilim (320 m blok, geçişe göre boyutlanmış dilim). Koridoru planlayıcının kendi kenarları üzerinde kurmak zorundaydık, yoksa koridor bir yolu "var" derken planlayıcı onu yürüyemezdi.

**S: "Budama işe yaramadı mı?"**
Bizim 10 saatlik penceremizde neredeyse yaramadı (%0,2). Sebebini biliyoruz ve söylüyoruz: kutup aydınlanması o sürede neredeyse durağan. CMU 59 günlük pencerelerle çalışıyor, orada ısırıyor. Bu, tekniğin değil pencere boyutunun sonucu.

**S: "Hiç sonuç vermediği durumlar oldu mu?"**
Evet ve bu iyi bir şey. Ay gecesinde 246 dilimin hiçbirinde ışıklı blok yok — sistem 404 dönüp bunu tam olarak bu cümleyle söylüyor. Sahte bir koridor uydurmuyor.

**S: "Standart VIPER rotanız koridordan geçemedi, bu başarısızlık değil mi?"**
Hayır, bulgu. O rota güneş-senkron değil: hedef bloğu hiç ışıklı olmuyor ve rota 4,55 saat gölgede. A2 bunu sayılarla gösterdi. Bir planlama aracının işi, kötü planı geçirmek değil, neden geçmediğini söylemek.
