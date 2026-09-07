# Safe Haven (A1) — Rover'ın Sığınağı

**Kodda:** `backend/app/safe_haven.py`
**API:** `GET /api/safe-haven`, `GET /api/cell-telemetry?start_utc=`, `/api/plan-4d` içinde `require_safe_haven`
**Özellik kodu:** A1

---

## Nedir?

**Safe Haven** (güvenli sığınak), rover'ın **Dünya ile hiç iletişim kuramadığı ~iki hafta boyunca kendi başına hayatta kalabileceği** bir konum.

Bu bir "iyi bir yer" değil, **kesin kriterleri olan bir sınıflandırma**. Bir hücre ya safe haven'dır ya değildir.

Yanında iki türev bilgi geliyor:
- **`time_to_haven`** — bulunduğum yerden en yakın sığınağa kaç saatlik sürüş var?
- **Bacak (leg) kuralı** — her seyir bacağı bir safe haven'da bitmeli.

---

## Hangi problemi çözüyor?

VIPER teleoperasyonla sürülüyor — Dünya'daki bir operatör tarafından. Ama Dünya, Ay gökyüzünde sabit değil: 27 günlük librasyon salınımıyla ufkun altına iniyor ve **iki hafta boyunca hiçbir komut ulaşmıyor.**

O iki hafta boyunca rover tamamen kendi başına. Hareket edemez (komut yok), yardım isteyemez, sorun çözemez.

Dolayısıyla **link kesilmeden önce rover'ın hayatta kalabileceği bir yerde park etmiş olması gerekiyor.**

Bu, "iyi olurdu" seviyesinde bir istek değil — **karşılanmazsa görev biter.**

---

## Analoji: Dağda kulübe

Kışın dağda yürüyorsunuz. Hava kararmadan önce bir kulübeye varmanız lazım, çünkü gece dışarıda kalırsanız donarsınız.

Şimdi bu benzetmeyi tam oturtalım:

| Dağda | Ay'da |
|---|---|
| Gece çöküyor | Dünya ufkun altına iniyor (~2 hafta) |
| Telefonunuz çekmiyor | Radyo linki yok, komut gelmiyor |
| Kulübe = sığınak | Safe haven |
| Kulübede soba var | Hücre en az bir kez güneş görüyor → panel şarj ediyor |
| "Kaç saat dayanabilirim?" | `h_max_shadow_h` — rover'ın minimum güç dayanımı |
| "En yakın kulübe kaç saat?" | `time_to_haven` |

Ve şu kritik kural: **her yürüyüş etabınız bir kulübede bitmek zorunda.** Yolun ortasında "buraya kadar yeter" diyemezsiniz, çünkü orada gece geçiremezsiniz.

VIPER'ın seyri de öyle: bacaklardan oluşuyor ve her bacak bir safe haven'da bitiyor.

**Ve bir incelik daha:** Dağda gündüz gölgede yürümek sorun değil — çünkü telefonunuz çekiyor, sorun olursa yardım çağırırsınız. Sorun, **gece VE telsizsiz** olmak. Ay'da da öyle: **Dünya yukarıdayken karanlıkta olmak sayılmıyor**, çünkü operatör rover'ı oradan çekip alabilir. Sayılan tek şey, **link yokken** yaşanan kesintisiz karanlık.

---

## NASA'nın tanımı — birebir uygulanıyor

Shirley & Balaban (2022) ve Ennico-Smith vd. (2023):

> **Dünya ufkun altındayken kesintisiz gölge süresinin 50 saati aşmadığı ve rover'ın hareketsizken güç üretebildiği bir konum.**

50 saat, VIPER'ın minimum güç dayanımı. LunaPath bunu **rover başına** taşıyor:

| Rover | `h_max_shadow_h` |
|---|---|
| LPR-1 | **50 sa** |
| NASA VIPER | **96 sa** |
| LUVMI-M | **4 sa** |
| CNSA Yutu-2 | **2 sa** |

Yani **aynı kural, her profil için farklı harita üretiyor.** Yutu-2 için neredeyse hiçbir yer safe haven değil; VIPER için sahanın %11'i olabiliyor.

---

## Nasıl çalışıyor?

Üç parça, hepsi son ana kadar **saf dizi fonksiyonu**:

### 1. Sayım kuralı — `max_dark_hours_without_dte`

Güneş'in ve Dünya'nın görünürlük serilerini **bir sinodik ay** boyunca çalıştırıyor (SHERPA'nın 2 saatlik kadansında) ve her hücre için şunu ölçüyor:

> **Bir link-yok döneminin İÇİNE düşen en uzun kesintisiz karanlık.**

**Kritik nüans:** Dünya yukarıdayken yaşanan karanlık **sayılmıyor.** Çünkü rover o karanlıktan komutla çekilip çıkarılabilir.

Bu, tanımı "en uzun karanlık" ile "en uzun *çaresiz* karanlık" arasında ayıran şey — ve doğru olan ikincisi.

### 2. Maske — `safe_haven_mask`

Üç şart:

```
safe_haven =  linksiz_karanlık ≤ rover.h_max_shadow_h
           ∧  pencerede en az bir kez ışıklı        ← "güç üretebilme" şartı
           ∧  geçilebilir
```

İkinci şart NASA'nın tanımındaki *"rover hareketsizken güç üretebilir"* maddesi: hücre hiç güneş görmüyorsa panel çalışmaz, orada park etmek ölümdür.

### 3. Mesafe — `time_to_safe_haven_hours`

Her hücreden en yakın haven'a **sürüş saati**, planlayıcının **kendi kapılı grafiği** üzerinde çok-kaynaklı Dijkstra ile.

**"Kendi kapılı grafiği" kritik:** aynı eğim kapıları, aynı köşe kesme kuralı, aynı slip'li sürüş süresi. Yoksa safe haven "2 saat uzakta" der, planlayıcı oraya gidemez.

### Ek: `hours_until_earthset_cube`

Plan ufkunun **14 gün ötesine** bakıyor — "linkim ne kadar süre daha var?" sorusunun cevabı.

### Ek: `route_margins`

SHERPA'nın marjlarını hesaplıyor: time-to-sun-shadow, time-to-DSN-shadow, time-to-0-SOC.

---

## Planlayıcıya nasıl giriyor?

`require_safe_haven = true` olduğunda:

> **Başlangıç dâhil ve her BEKLEME dâhil her durumda:**
> `time_to_haven ≤ kalan Dünya linki saati`

Yani rover, her an, "şu anda yola çıksam link kesilmeden sığınağa varabilir miyim?" sorusuna evet cevabı verebilmeli.

Yayınlanan alanlar: `path_time_to_haven_h`, `path_hours_until_earthset`, `path_haven_margin_h`, `metrics.min_haven_margin_h`, `ends_at_safe_haven`.

---

## Dürüstlük kuralı

> *"Burada hiçbir şey hesaplayamadığı bir alanı uydurmaz: epoch, ufuk küpü veya kerneller olmadan harita `unavailable` olarak raporlanır — sebebiyle birlikte, asla boş veya 'her yer güvenli' bir grid olarak."*

Bu çok önemli: "her yer güvenli" varsayılanı, sistemi güvenli görünen ama ölümcül bir hâle sokardı.

---

## Site11'de ölçülen gerçek sayılar

**Senaryo:** 2026-09-07'den itibaren 13 sinodik ay

### Temel bulgu: Site11 acımasız

Dünya linksiz iki hafta, **bütün sahayı ~6,5 gün karartan ay gecesiyle çakışıyor.**

NASA'nın dediği gibi, haven'lar seyrek:

> **En kısa linksiz karanlık, ay gününe göre 40–186 saat.**

Yani en iyi hücrede bile en az 40 saat, en kötü ayda 186 saat çaresiz karanlık var.

### Rover başına sonuç

| Rover | Dayanım | Site11'de sonuç |
|---|---|---|
| **LPR-1** | 50 sa | Yalnız **Kasım 2026'da ~40 hücre**. Başka hiçbir ayda yok. |
| **NASA VIPER** | 96 sa | 2027-05-30 ay gününde **sahanın %11'i** = 22 837 hücre |
| **LUVMI-M** | 4 sa | **Hiçbir zaman uygun değil** |
| **CNSA Yutu-2** | 2 sa | **Hiçbir zaman uygun değil** |

**VIPER detayı:** en yakın haven'a medyan **2,2 saat**; geçilebilir hücrelerin **%99'u** bir haven'a ulaşabiliyor. Yani haven bulunduğunda erişim iyi.

### Gereken dayanım

| Kapsama hedefi | Gereken `h_max_shadow_h` |
|---|---|
| Sahanın %1'i | **64–232 sa** (ay gününe göre) |
| Sahanın %10'u | **82–298 sa** |

Yani Site11'de sahanın onda birine sığınak diyebilmek için rover'ın **300 saate yakın** minimum güç dayanımı olması gerekiyor. VIPER'ın 96 saati bunun üçte biri.

### Plan performansı

Kural altında iki haven arası VIPER planı **8,4 saniyede 200 saatlik marjla** dönüyor.

---

## Bu bulgunun diğer feature'lara etkisi

Safe haven bulunamaması, sistemin başka yerlerinde zincirleme sonuçlar doğurdu — ve bu, feature'ların gerçekten birbirine bağlı olduğunun kanıtı:

| Feature | Etki |
|---|---|
| **[B1 Survival](survival-reach-avoid.md)** | Lamarre'ın "hedef küme = safe haven" tanımı Site11'de **boş küme** verdiği için `P_safe` her yerde sıfır çıkardı. Varsayılan güvenli küme "bacak (leg)" kümesine değiştirildi. |
| **[C6 Termal dwell](../02-isik-golge-ve-termal/termal-dwell-ve-operasyon-zarfi.md)** | JSC'nin "tolere edilebilir saplanma süresi" haven penceresini gerektiriyor. LPR-1 için o pencere **her yerde 0 saat** — yani saat rover sıkışmadan önce dolmuş. |

---

## İlham kaynağı

- **Shirley & Balaban (2022)**, *An Overview of Mission Planning for the VIPER Rover*
- **Ennico-Smith vd. (2023)** — VIPER safe haven tanımı
- **SHERPA** (Balaban vd., SpaceOps 2025) — 2 saatlik kadans ve marj metrikleri

---

## İddia sınırı

✅ **Söylenebilir:** *"VIPER ile aynı safe-haven ve 50 saat kuralını uyguluyoruz."*

Bu, NASA'nın yayınlanmış tanımının birebir uygulanmış hâli — bizim yorumumuz değil.

---

## Kodda nerede?

```
backend/app/safe_haven.py
  max_dark_hours_without_dte()   ← linksiz karanlık sayımı
  safe_haven_mask()              ← üç şart
  time_to_safe_haven_hours()     ← çok-kaynaklı Dijkstra, kapılı grafik
  hours_until_earthset_cube()    ← 14 gün ötesi
  route_margins()                ← SHERPA marjları
  _gated_edges()                 ← planlayıcıyla ortak kenar kuralı

scripts/safe_haven_report.py
docs/research/safe_haven_report.md
```
60 yeni test.

---

## Jüri soruları

**S: "Safe haven nedir?"**
Rover'ın, Dünya ile iletişimin kesildiği ~iki hafta boyunca kendi başına hayatta kalabileceği bir konum. NASA'nın VIPER için tanımı net: Dünya ufkun altındayken kesintisiz gölge 50 saati aşmayacak ve rover hareketsizken güç üretebilecek. Biz bu tanımı birebir uyguluyoruz, sadece 50 saati rover başına parametreleştirdik.

**S: "Neden 50 saat?"**
VIPER'ın minimum güç dayanımı — yani ısıtıcı ve temel sistemler dışında her şey kapalıyken bataryanın dayandığı süre. Bizim katalogda LPR-1 için 50, VIPER için 96, Yutu-2 için 2, LUVMI-M için 4 saat. Aynı kural her araç için farklı harita üretiyor.

**S: "Dünya yukarıdayken karanlıkta olmak neden sayılmıyor?"**
Çünkü o karanlıktan çıkılabilir. Operatör komut gönderip rover'ı aydınlığa sürebilir. Tehlikeli olan, karanlık **ve** komutsuz olmak. Bu ayrım tanımın kalbi — "en uzun karanlık" ile "en uzun çaresiz karanlık" farklı şeyler ve doğru olan ikincisi.

**S: "Site11'de kaç safe haven buldunuz?"**
Dürüst cevap: çok az. LPR-1 için 13 sinodik ay boyunca sadece Kasım 2026'da ~40 hücre; başka hiçbir ayda yok. VIPER için (96 saat dayanımıyla) 2027-05-30 ay gününde sahanın %11'i, yani 22 837 hücre. Yutu-2 ve LUVMI-M için hiçbir zaman. Sebep: Site11'de linksiz iki hafta, sahayı 6,5 gün karartan ay gecesiyle çakışıyor.

**S: "Bu kötü bir sonuç değil mi?"**
Sonuç kötü, ölçüm iyi. NASA'nın kendi yayınları da haven'ların seyrek olduğunu söylüyor. Bizim kattığımız şey, **bunu belirli bir saha ve belirli araçlar için sayısallaştırmak**: "sahanın %10'una sığınak diyebilmek için 82–298 saat dayanım lazım" gibi bir cümle, misyon tasarımına doğrudan girdi.

**S: "`time_to_haven` nasıl hesaplanıyor?"**
Planlayıcının **kendi kapılı grafiği** üzerinde çok-kaynaklı Dijkstra ile — aynı eğim kapıları, aynı köşe kuralı, aynı slip'li sürüş süresi. Bu kritik: farklı bir grafik kullansak, safe haven "2 saat uzakta" derken planlayıcı oraya gidemeyebilirdi.

**S: "Bu bulgu başka neyi etkiledi?"**
İki büyük şeyi. B1 (hayatta kalma politikası) Toronto STARS Lab'in "hedef küme = safe haven" tanımını kullanacaktı; Site11'de o küme boş olduğu için hayatta kalma olasılığı her yerde sıfır çıkardı — güvenli kümeyi "bacak" kümesine değiştirdik ve bunu raporladık. C6'da (termal saplanma) haven penceresi LPR-1 için her yerde 0 saat çıktı, yani NASA JSC'nin "saati" rover daha sıkışmadan dolmuş.
