# DEM Belirsizliği (B3) — "Ya Harita Yanlışsa?"

**Kodda:** `backend/app/uncertainty.py`, `scripts/build_dem_clone_cache.py`
**API:** `POST /api/dem-uncertainty`, `GET /api/uncertainty-series`, `/api/plan` ve `/api/plan-4d` içinde `uncertainty` bloğu
**Özellik kodu:** B3

---

## Nedir?

NASA, her 5 m/piksel güney kutbu DEM'i için sadece "en iyi tahmin" haritasını değil, **100 tane alternatif harita** da yayınlıyor. Bunlara *istatistiksel klon* deniyor: her biri, ölçüm hatası dâhilinde "arazi bu şekilde de olabilirdi" diyen eşit derecede geçerli bir yüzey.

B3, LunaPath'in **tüm hesap zincirini bu 100 harita üzerinde ayrı ayrı çalıştırıp** sonuçların dağılımını çıkarıyor.

---

## Hangi problemi çözüyor?

B3'ten önce sistemdeki her katman **tek bir** yükseklik modelinden türüyordu: tek eğim, tek ufuk, tek gölge. Hata çubuğu yoktu.

Ama yükseklik ölçümünün kendisi belirsiz. Uydunun lazer altimetresi ±0,45 m civarında hata yapıyor. Bu hata eğime yansıyor (eğim yükseklik farkından hesaplanıyor), eğim geçilebilirliğe yansıyor, geçilebilirlik rotaya yansıyor.

Yani: **"bu hücre geçilebilir" cümlesi aslında bir olasılık ifadesi, ama sistem onu kesinlik gibi sunuyordu.**

---

## Analoji: Hava durumu tahmini

Bir meteorolog "yarın 20 derece" demez. "20 derece, ±3 derece" der. Ya da daha iyisi: aynı modeli 100 farklı başlangıç koşuluyla çalıştırır ve "100 simülasyonun 80'inde yağmur yağdı" der. Buna **ensemble tahmini** denir.

B3 tam olarak budur. Tek bir arazi haritasıyla "bu yol geçilebilir" demek yerine, 100 olası arazi haritasıyla **"bu yol 100 haritanın kaçında geçilebilir kaldı"** diyoruz.

Ve cevap bazen ürkütücü — aşağıda göreceksiniz.

---

## Nasıl çalışıyor?

### Klonlar ne?

NASA'nın formülü: `klon = yüzey + toterr × ξ`

- `yüzey` = en iyi tahmin DEM'i
- `toterr` = Z-belirsizlik haritası (her hücrenin hata büyüklüğü)
- `ξ` = uzamsal olarak korele, birim varyanslı rastgele alan

Yani her klon, "hata bu şekilde dağılsaydı arazi böyle olurdu" senaryosu. Ve hata **uzamsal olarak korele** — yani komşu hücrelerin hataları bağımsız değil, birlikte hareket ediyor (Site11'de ölçüldü: 5 m'de korelasyon 0,88, 100 m'de kaybolmuş).

### İlk bulgu: dosyalar sanılan şey değildi

Bu, projedeki güzel detektiflik anlarından biri.

NASA'nın `_err.tif` dosyaları isimlerinden dolayı "hata alanı" sanıldı. Ama açıldığında değerler 528–955 metre çıktı — hata değil, **tam yüzey yüksekliği**. Yüzeyle korelasyon 1,0000.

Doğru yorum: dosyalar tam DEM klonları. Hata gerçeklemesi `klon − yüzey`. Doğrulandı: bu farkın RMS'i NASA'nın kendi `toterr` RMS'ine eşit çıktı (**0,449 m**).

100 klonun her biri saklanmadan önce bu kontrolden geçiyor.

### Zincirden geçirme

Her klon, LunaPath'in **kendi** türetme zincirinden geçiyor — NASA'nın hazır ürünleri değil, bizim operatörlerimiz:

```
klon DEM → eğim operatörü → geçilebilirlik kuralı → ufuk taramacısı → enerji aritmetiği
```

Çıktılar:

| Çıktı | Anlamı |
|---|---|
| `p_traversable` | Hücrenin kaç klonda geçilebilir olduğu (0–1) |
| `slope_sigma` | Eğimin klonlar arası standart sapması (`DERIVED`) |
| `elevation_sigma` | Yükseklik belirsizliği |
| `slope_sigma_nasa` | NASA'nın kendi eğim hata modeli (`MODEL` — ölçüm değil) |
| `p_illuminated` | Zaman dilimi başına, hücrenin kaç klonda aydınlık olduğu |
| Rota bandı | Süre, enerji ve kesintisiz gölgenin %5–95 aralığı |

### Ne klonlandı, ne sabit tutuldu?

Bu açıkça belirtiliyor, ima edilmiyor:

**Klonlanan:** eğim, geçilebilirlik, ufuk (1 km'ye kadar yakın alan)
**Sabit tutulan:** termal alan (heat1d modeli, eğime zayıf bağımlı ve pahalı), 1 km ötesindeki uzak ufuk, Dünya linki, safe haven alanları

Uzak ufuk için ihmal edilen etki **sınırıyla birlikte raporlanıyor:** bir sırtın yükseklik hatası ufku `dz/d` kadar kaydırır — medyan 0,45 m hata için 100 m'de 0,26°, 1 km'de 0,026°. Kutup Güneşi saatte ~0,009° tırmandığı için bu ihmal edilebilir ama söylenmeden geçilmiyor.

---

## Site11'de ölçülen gerçek sayılar

### Eğim belirsizliği

| Ölçüm | Değer |
|---|---|
| Bizim eğim σ medyanı | **1,52°** |
| NASA'nın `slperr` medyanı | 1,73° |
| Oran | 0,88 |
| Hücre bazında korelasyon | 0,42 |

### Şaşırtıcı bulgu: en iyi tahmin, hepsinin en düzü

Klon eğimleri, yüzey DEM'inin eğimlerinin **sistematik olarak üstünde** (medyan +0,16°).

**Sebebi:** sıfır ortalamalı yükseklik gürültüsü, gradyanı şişirir. Rastgele gürültü eklemek araziyi ortalamada daha dik gösterir, daha düz değil.

**Sonucu:** "en iyi tahmin DEM'i, mevcut bütün olasılıkların en düzüdür." Yani gerçek arazi büyük ihtimalle haritadan daha engebeli. Bu, planlamanın sistematik olarak iyimser olduğu anlamına gelir.

### Geçilebilirlik belirsizliği

| Rover | Belirsiz hücre oranı |
|---|---|
| NASA VIPER (20° limit) | **%8,2** |
| LPR-1 (25° limit) | %2,8 |

Ve daha keskin bir sayı: hücrelerin **%0,9'u yüzey DEM'inde geçilebilir görünüyor ama olasılığı 0,5'in altında** — yani harita "geçebilirsin" diyor, istatistik "muhtemelen geçemezsin" diyor.

### Aydınlanma belirsizliği

2027-05-30 tarihinde: hücrelerin **%10,8'i** ışıklı mı karanlık mı olduğu söylenemiyor. Onda biri belirsiz.

### Rota bandı — en çarpıcı sonuç

**NASA VIPER rotası:**

| Ölçüm | Değer |
|---|---|
| Sürüş enerjisi p5 / p50 / p95 | **2 258 / 2 293 / 2 334 Wh** |
| Yüzey DEM'inde plan | 2 127 Wh |
| Fark | Bant, planın **%6–10 üstünde** |
| Rotanın geçilebilir kaldığı klon sayısı | **100 klonun 1'inde** |
| SHERPA tamamlama oranı (klonlar havuzlanınca) | %29,6 → **%17,8** |

**LPR-1 rotası:**

| Ölçüm | Değer |
|---|---|
| Enerji p5/p50/p95 | 538 / 546 / 556 Wh (yüzey: 506) |
| Geçilebilir kaldığı klon | **99/100** |
| Tamamlama | %100 |

**Bu sonucun anlamı:** VIPER için planlanan rota, arazinin belirsizliği hesaba katıldığında neredeyse hiçbir olası arazide geçilebilir kalmıyor. LPR-1 rotası ise sağlam. Bu, tek bir haritayla asla göremeyeceğiniz bir bulgu.

### Yakınsama

100 klon yeterli mi? Ölçüldü: ortalama `|P₂₀ − P₁₀₀| = 0,007`. Yani 20 klonla 100 klon arasındaki fark binde 7. Yakınsamış.

---

## İlham kaynağı

- **NASA GSFC Planetary Geodesy, PGDA ürün 78** — Barker, Mazarico ve arkadaşları. Z-belirsizliği (`toterr`), eğim belirsizliği (`slperr`) ve 100 istatistiksel klon.
- **NASA-STD-7009** — modelleme ve simülasyon standardı. Girdi soyağacı (pedigree) ve belirsizlik nicelemesi zorunluluğu buradan geliyor.

---

## Kodda nerede?

```
backend/app/uncertainty.py          ← klon zinciri, olasılık katmanları
scripts/build_dem_clone_cache.py    ← klonları indirir, doğrular, önbelleğe yazar
scripts/dem_uncertainty_report.py   ← ölçüm raporunu üretir
docs/research/dem_uncertainty_report.md
```
47 yeni test eklendi.

**Not:** Klon önbelleği yerelde yoksa bu uçların hiçbiri görünmüyor — `unavailable` dönüyor, sahte belirsizlik uydurulmuyor.

---

## Jüri soruları

**S: "Bu ne işe yarıyor pratikte?"**
Bir rotayı "geçilebilir" diye onaylamadan önce, o rotanın haritadaki hataya ne kadar duyarlı olduğunu görüyorsunuz. VIPER örneğimizde plan geçerli görünüyordu ama 100 olası arazinin sadece 1'inde geçerli kaldı. Bu, bir görevi kaybettirecek türden bir bilgi.

**S: "Neden 100 klon? Daha fazlası daha iyi olmaz mı?"**
100'ü NASA yayınlıyor, sayı bizim seçimimiz değil. Ama yeterli olduğunu ölçtük: 20 klonla 100 klon arasındaki olasılık farkı ortalama 0,007. Yakınsamış.

**S: "Her şeyi klonlamadınız — bu bir eksiklik değil mi?"**
Eksiklik ama gizlenmiş değil. Termal alan, uzak ufuk, Dünya linki ve safe haven sabit tutuldu; sebepleri ve ihmal edilen etkinin büyüklük sınırı her cevapta raporlanıyor. Termal alan heat1d modeli, çok pahalı ve eğime zayıf bağımlı; uzak ufuk için hesapladık, etki 1 km'de 0,026 derece — Güneş'in saatte tırmandığı açının üçte biri.

**S: "Klon eğimlerinin yüzeyden dik çıkması bir hata mı?"**
Hayır, matematiksel olarak beklenen bir sonuç: sıfır ortalamalı gürültü gradyanı şişirir. Ama önemli bir sonucu var — en iyi tahmin haritası, olası bütün arazilerin en düzü. Yani planlarımız sistematik olarak iyimser ve bunu artık niceliksel olarak biliyoruz.

**S: "Ne söyleyebilirsiniz?"**
"Belirsizlik nicelenmiştir; enerji tüketimi %90 güven bandıyla veriliyor." Bu cümleyi kurabiliyoruz ve arkasında NASA'nın kendi klonları var.
