# Hayatta Kalma Politikası ve Şans Kısıtı (B1) — "Ya Yolda Bir Şey Ters Giderse?"

**Kodda:** `backend/app/survival.py`, `backend/app/pathfinder_4d.py`
**API:** `/api/plan-4d` içinde `max_failure_probability` (β), `GET /api/survival`, `GET /api/cell-telemetry?survival=true`, `POST /api/replan` içinde `recovery_policy`
**Özellik kodu:** B1

---

## Nedir?

Her duruma (**hücre, zaman, batarya seviyesi**) iki şey atayan bir katman:

1. **`P_safe`** — Bu durumdan başlayıp **en iyi mümkün politikayı** izlersek, hâlâ başarısızlıkla bitme olasılığı ne? (Yayınlanan `P_safe = 1 − başarısızlık olasılığı`)
2. **En iyi eylem** — Bu durumdan ne yapmalıyım? (kurtarma politikası)

Ve planlayıcıya bir kısıt: **`max_failure_probability = β`** — yürütme başarısızlık olasılığını β'nın üstüne çıkaracak hamleyi reddet.

---

## Hangi problemi çözüyor?

4-D planlayıcı **deterministikti**: bir rota rover'ın zarfının içindeydi ya da değildi. Ve yolda bir şey ters gittiğinde ne olacağını **hiçbir şey söylemiyordu.**

Ama gerçek misyonlarda bir şeyler ters gider:
- Tekerlek kuma saplanır
- Bir motor takılır
- Beklenmedik bir engel çıkar

Bu olduğunda rover bir süre hareketsiz kalır. Bu sürede batarya boşalmaya devam eder. Ve kurtulduğunda ilk plandaki konumunda değildir.

**Soru:** Bir rota "geçerli" ama arıza durumunda ölümcül ise, hâlâ geçerli midir?

---

## Analoji: Yakıt göstergesi ve benzin istasyonu

Arabayla yolculuk yapıyorsunuz. Yakıtınız yolu tamamlamaya **tam olarak** yetiyor.

Deterministik plan der ki: **"Geçerli. Yakıt yeter."**

Ama gerçek sürücü şunu sorar: *"Ya yolda lastik patlarsa? Yarım saat kenarda beklerim, motor çalışır, klima açık kalır... yakıt hâlâ yeter mi?"*

Ve daha derin bir soru: *"Şu anda bulunduğum noktadan, bir sorun çıkarsa en yakın benzin istasyonuna varabilir miyim?"*

İkinci soruya cevap verebilmek için, **yolun her noktası için** ayrı ayrı hesaplamanız gerekir. Ve cevap yakıt seviyenize bağlıdır: aynı noktada tam depoyla güvendesiniz, çeyrek depoyla değilsiniz.

B1 tam olarak bu hesabı yapıyor: **(konum, zaman, yakıt) üçlüsünün her kombinasyonu için "buradan kurtulabilir miyim" olasılığı.**

---

## Nasıl çalışıyor?

### Toronto STARS Lab'in yöntemi

Lamarre, Malhotra ve Kelly (Acta Astronautica 2023; IEEE Aerospace 2024) bunu **stokastik reach-avoid problemi** olarak modelliyor:

**Durum uzayı:** `(zaman kutusu, hücre, batarya kutusu)`

**Eylemler:** Her durumdan rover ya sekiz komşudan birine sürebilir ya da bir kutu bekleyebilir.

**Belirsizlik:** Bir sürüş **mobilite arızasına** uğrayabilir — sürülen mesafede Poisson dağılımlı, kilometre başına `α` oranıyla. Arıza olursa rover `R` saat yerinde çakılı kalır.

**Başarısızlık:** Batarya kutusu rezervin altına inerse VEYA zaman ufku dolarsa.

**Güvenlik:** Rover, o kümenin gerektirdiği şarjla güvenli kümede duruyorsa.

**Çözüm:** **Geriye doğru değer iterasyonu.** Sondan başa doğru, her durum için "en iyi politika bile buradan başarısızlıkla biterse olasılığı ne?" hesaplanıyor. Sonuç `V(x)`; yayınlanan `P_safe = 1 − V`. Ve arg-min eylem **kurtarma politikası**.

### Planlayıcıya bağlanması

4-D planlayıcı her etikette bir **yürütme-hayatta kalma çarpanı** taşıyor. Her hamlede arıza dalları, arızanın rover'ı bıraktığı durumun `P_safe`'i ile kapatılıyor (AERO 2024 kuralı).

`max_failure_probability = β` verilirse, bu çarpanı β'nın üstüne çıkaracak hamle **reddediliyor**.

---

## Üç dürüst sapma — makalelerden ayrıldığımız yerler

Bu bölüm B1'in en değerli kısmı: **neyin Lamarre'a, neyin bize ait olduğu her cevapta yazıyor** (`SURVIVAL_CLAIM` ve `LAMARRE_QUOTED` sabitleri).

### Sapma 1: Arıza oranı ve kurtarma süresi VARSAYIM

Katalogdaki **hiçbir rover** bu iki sayıyı yayınlamıyor.

| Sabit | Değer | Kaynak |
|---|---|---|
| `FAILURE_RATE_PER_KM_ASSUMED` | **0,2** | Lamarre'ın "5 000 m'de 1 arıza"sı |
| `FAULT_RECOVERY_HOURS_ASSUMED` | **10 saat** | Varsayım |

Kaynak dizeleri `assumption:` ile başlıyor. **Profile alan eklenmedi** — çünkü katalogda durursa gelecekte biri onu spesifikasyon sanabilir.

### Sapma 2: Güvenli küme değişti — çünkü mecburduk

**Lamarre'ın hedef kümesi:** *"Ay gecesini hibernasyonla geçirecek şarjla bir safe haven'da olmak."*

**Ölçüm:** LPR-1'in Site11'de **üç epokun hiçbirinde** haven'ı yok. (VIPER: 19 / 0 / 862 kaba blok.)

**Sonuç:** O küme boş → `P_safe` **her yerde sıfır** olurdu → özellik hiçbir bilgi taşımazdı.

**Varsayılan değiştirildi — "leg" (bacak) kümesi:**
```
leg = rezerv şarjındaki hedef bloğu  ∪  hibernasyon şarjındaki her haven bloğu
```

`safe_set="haven"` seçeneği Lamarre'ın katı kümesi olarak **duruyor** — kaldırılmadı, sadece varsayılan değil.

### Sapma 3: Alt-kutu eşlemesi bu hamle boyutunda kullanılamaz

Bu, teknik olarak en ince bulgu.

**Lamarre'ın muhafazakâr kuralı:** Bir hamlenin enerji tüketimini, hep bir **alt SOC kutusuna** yuvarla.

**Bizim ölçeğimizde ne oluyor:**

| Büyüklük | Değer |
|---|---|
| 20 metrelik bir hamle | ~19 Wh |
| Bir SOC kutusu | **271 Wh** |

Yani alt-kutu haritası, karanlık hamle başına **tam bir kutu** yazıyordu — gerçek tüketimin yaklaşık **14 katı**.

**Ölçülen sonuç:** Standart gündüz rotasının başında `P_safe = 0,000`. Blokların %90'ı sıfırda. Yani özellik tamamen ölü.

**Çözüm:** SOC kutu merkezleri arasında **doğrusal interpolasyon** (Lamarre'ın kendi "interpolation map" alternatifi). Aynı alan artık **0,985** okuyor.

**Ve muhafazakârlık artık ampirik:** Politika, sürekli zamanlı Monte Carlo ile denetleniyor — "tahmin ≥ gerçekleşen" ilişkisi ölçülüyor.

---

## Site11'de ölçülen gerçek sayılar

### Alan boyutu ve süresi (coarsen 4)

| Senaryo | Durum sayısı | DP süresi |
|---|---|---|
| LPR-1 gündüz (28 Eyl 2026) | **65,3 M** | 96 s |
| LPR-1 ay gecesi (13 Eyl 2026) | 68,5 M | 136 s |
| VIPER kısa bacak (30 May 2027) | 39,8 M | 46 s |

### Başlangıç `P_safe`

| Senaryo | Tam batarya | Yarım batarya |
|---|---|---|
| LPR-1 gündüz | **0,985** | 0,972 |
| LPR-1 ay gecesi | **0,883** | **0,404** |
| VIPER kısa bacak | **1,000** | 0,761 |

**Ay gecesi, yarım bataryayla 0,404** — yani %60 ihtimalle görev başarısız. Bu sayı bir operatör için doğrudan karar dayanağı.

### Kısıtsız planların yürütme başarısızlık olasılığı

| Senaryo | Olasılık |
|---|---|
| Gündüz | **%1,65** |
| Ay gecesi | **%11,05** |
| VIPER | %0,08 |

### β süpürmesi {0,10 · 0,05 · 0,02}

| Senaryo | Sonuç |
|---|---|
| Gündüz çifti | Her β'da **41 hamlelik rotasını koruyor**. β=0,02'de arama 13 811 hamleyi reddedip **aynı rotayı** buluyor. |
| Ay gecesi çifti | **Üçünde de 404** — çünkü başlangıçtan en iyi kurtarma politikası bile 0,1173 olasılıkla başarısız |
| VIPER | 8 hamlesini koruyor |

**Makalenin "+0,5 km, +2 saat" sonucu burada tekrarlanmadı.** Bizim rotalarımız ya değişmiyor ya da uygulanamaz oluyor. Sebebi: rezerv ve karanlık **zaten deterministik zarfın içinde** kısıtlanmış.

### Doğrulama: tahmin ≥ gerçekleşen

1 000 sürekli-zaman Monte Carlo koşumu, Wilson %95 güven aralığıyla:

| Senaryo | Tahmin | Gerçekleşen [%95 GA] |
|---|---|---|
| Gündüz | 1,51 | 1,20 [0,69 – 2,09] |
| Ay gecesi | 11,7 | 4,6 [3,5 – 6,1] |
| VIPER | 0,08 | 0,0 |

**Üçünde de muhafazakâr** — tahmin gerçekleşenden yüksek. Gecede 2,5 kat.

Bu iyi bir özellik: model kötümser, iyimser değil.

### Katı haven kümesiyle

- LPR-1: her epokta **boş**
- VIPER, 30 May 2027: 862 blok, ortalama `P_safe` 0,725

---

## Dürüst uyarı — rapordaki olumsuz bulgu

> **Ay gecesinde, politika sürekli zamanda uygulandığında, sabit plandan DAHA ÇOK batarya arızası üretti** (1 000 koşumun 38'i; sabit planda 0).

**Sebebi:** En yakın kutu merkezinden okunan politika, rezervin yakınındaki **3 puanlık SOC farkını görmüyor.**

Yani kurtarma politikası, kritik sınıra yakın durumlarda kuantizasyon yüzünden yanlış eylem seçebiliyor.

**Bu bulgu raporda duruyor.** Gizlenmiş veya küçültülmüş değil.

---

## Maliyet

| | Süre |
|---|---|
| Alan hesabı (DP) | 46–136 s |
| Alanla planlayıcı, gündüz | 10–11 s (alansız: 7 s) |
| Alanla planlayıcı, gece | 43 s (alansız: 22 s) |
| Alanla planlayıcı, VIPER | 3 s |

**Bit-eşitlik:** `max_failure_probability` veya `report_survival` verilmezse planlayıcı **B1 öncesiyle bit-eşit** — üç standart rota eskisi gibi 41 / 116 / 8 hamle.

---

## API yüzeyi

| Uç / parametre | Ne verir |
|---|---|
| `/api/plan-4d` → `max_failure_probability` (β) | Şans kısıtı |
| `/api/plan-4d` → `report_survival` | Kısıt uygulamadan sadece raporla |
| `/api/plan-4d` → `failure_rate_per_km`, `recovery_hours` | Varsayımları üstüne yaz |
| `/api/plan-4d` → `survival_soc_bins`, `survival_safe_set`, `survival_horizon_hours` | Alan parametreleri |
| `/api/plan-4d` cevabı → `survival` bloğu | İki durum listesi; 404 detayında şans kısıtı cümlesi |
| `GET /api/cell-telemetry?survival=true` | Hücrenin `P_safe`'i ve en iyi eylemi |
| `POST /api/replan` → `recovery_policy: true` | `recovery_suggestion` |
| `GET /api/survival` | Kaba `p_safe` / `best_action` katmanı (f32, `X-Layer-Validity: MODEL`) |

SHERPA'ya (B5) arıza olayı eklendi: `fault_rate_per_km`, varsayılan sıfır → **B5 bit-eşit** kalıyor.

---

## İlham kaynağı

**Lamarre, Malhotra, Kelly** — University of Toronto STARS Lab
- Acta Astronautica 2023
- IEEE Aerospace 2024

Güneş enerjili bir rover için Ay güney kutbunda stokastik reach-avoid planlama.

---

## İddia sınırı

✅ **Söylenebilir:** *"Rotanın başarısızlık olasılığı ≤ β."*
⚠️ **Ama mutlaka eklenmeli:** *"Arıza oranı α bir varsayımdır"* (Lamarre'ın 1/5 km'si).

📎 Lamarre'ın kendi sayıları (41,5 M durum; β %2 → gerçekleşen %1,5) **alıntı olarak** duruyor, bizim ölçümümüzle karışmıyor.

---

## Kodda nerede?

```
backend/app/survival.py
  değer iterasyonu (tek geri sweep)
  SURVIVAL_CLAIM / LAMARRE_QUOTED
  FAILURE_RATE_PER_KM_ASSUMED = 0.2
  FAULT_RECOVERY_HOURS_ASSUMED = 10
  safe_set: "leg" (varsayılan) | "haven" (katı)

backend/app/pathfinder_4d.py
  astar_4d() içinde β kısıtı

scripts/recovery_policy_report.py   ← rapor 49 dakika
docs/research/recovery_policy_report.md
```
54 yeni test.

---

## Jüri soruları

**S: "Bu ne işe yarıyor?"**
Bir rotanın sadece "geçerli" değil, "arıza durumunda da kurtarılabilir" olduğunu söylüyor. Somut örnek: LPR-1'in ay gecesi rotası deterministik olarak geçerli, ama yarım bataryayla başlarsa hayatta kalma olasılığı **0,404**. Bu sayıyı görmeden o rotayı onaylarsınız.

**S: "Neden tek geri sweep yetiyor?"**
Çünkü her eylem en az bir zaman kutusu ilerletiyor (planlayıcının kendi `ceil` kuralı). Bu, problemi zamanda katmanlı hâle getiriyor, yani döngü yok. Makalelerin alt/üst zaman min-max'ına gerek kalmıyor — tek geri sweep **kesin** sonuç veriyor.

**S: "Toronto'nun makalesini birebir uyguladınız mı?"**
Hayır, üç yerde saptık ve üçünü de her cevapta söylüyoruz. (1) Arıza oranı ve kurtarma süresi varsayım — hiçbir rover yayınlamıyor. (2) Güvenli küme değişti: onların "safe haven" kümesi Site11'de LPR-1 için boş, o yüzden `P_safe` her yerde sıfır olurdu. (3) Onların muhafazakâr alt-kutu yuvarlaması bizim hamle boyutumuzda tüketimi 14 katına çıkarıyordu ve `P_safe` 0,000 okuyordu; interpolasyona geçtik.

**S: "Sonuçlarınız makaleninkine benziyor mu?"**
Bir yerde benzemiyor ve bunu söylüyoruz. Makale "şans kısıtı rotayı +0,5 km, +2 saat uzatıyor" diyor. Bizde rotalar ya hiç değişmiyor ya da tamamen uygulanamaz oluyor. Sebebi: bizim deterministik zarfımız (rezerv, karanlık dayanımı) zaten çok sıkı — stokastik kısıt eklenecek boşluk bırakmıyor.

**S: "Modeliniz güvenilir mi?"**
Doğrulaması var: 1 000 sürekli-zaman Monte Carlo koşumuyla karşılaştırdık. Üç senaryoda da tahmin **gerçekleşenden yüksek** — yani model kötümser, ki güvenlik için doğru yön. Gecede 2,5 kat kötümser.

**S: "Bilinen bir kusuru var mı?"**
Var ve raporda yazıyor: ay gecesinde kurtarma politikası sürekli zamanda uygulandığında sabit plandan **daha çok** batarya arızası üretti (1 000 koşumun 38'i). Sebebi kuantizasyon — en yakın kutu merkezinden okunan politika, rezervin yakınındaki 3 puanlık SOC farkını görmüyor. Bu, politikanın rapor amaçlı kullanılıp doğrudan uygulanmaması gerektiğini söylüyor.
