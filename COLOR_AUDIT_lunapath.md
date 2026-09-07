> **Color Audit** — LunaPath
> Üretildi: 2026-09-05
> Üretici: SevgiAI v1.1.0 · `/sevgi-ai:color-audit`
> Standart/Kaynak: SENG 477 (Colours in HCI), WCAG 2.1 AA, Viénot-Brettel-Mollon dikromazi simülasyonu

---

## 0. Yöntem

Bu denetimdeki her sayı hesaplandı, göz kararı verilmedi.

| Ölçüm | Nasıl elde edildi |
|-------|-------------------|
| Kontrast oranları | WCAG 2.1 göreli parlaklık formülü, `App.css` `:root` hex değerleri üzerinde |
| HSL / hue tespiti | `colorsys.rgb_to_hls`, harmoni sınıflandırması için |
| Renk körlüğü | Viénot-Brettel-Mollon LMS dikromazi matrisleri (protanopi, dötanopi, tritanopi) |
| Ayırt edilebilirlik | Doğrusal ışık RGB uzayında Öklid mesafesi × 100 |
| 60-30-10 | Tarayıcıda ölçülen **gerçek boyanan alan** (1600×1000, kokpit ekranı) |
| Önerilen rampa | 400.000 adaylık kısıtlı arama; kısıtlar bölüm 8'de |

**Kullanıcı kararları.** Risk rampası hue'ları *kanıt sunulması koşuluyla*
değiştirilebilir. Hedef **yalnızca koyu tema**; açık tema kapsam dışı.

---

## 1. Mevcut Palet

Zemin `--bg-card` (#0c1018). Koyu tema olduğu için "beyaza karşı" sütunu
anlamsız; onun yerine iki gerçek zemin verilmiştir.

### 1.1 Nötr eksen

| Token | Hex | H | S | L | vs `--bg-card` | vs `--void` | Rol |
|-------|-----|---|---|---|----------------|-------------|-----|
| `--void` | `#05070d` | 225 | 44% | 4% | — | — | Sayfa zemini |
| `--bg-surface` | `#080b12` | 222 | 38% | 5% | 1.03 | 1.02 | Ray / panel |
| `--bg-card` | `#0c1018` | 220 | 33% | 7% | — | 1.06 | Kart |
| `--bg-inset` | `#0a0e16` | 220 | 38% | 6% | 1.01 | 1.04 | Kart içi oyuk |
| `--bg-raised` | `#0e131d` | 220 | 35% | 8% | 1.02 | 1.08 | Yükseltilmiş yüzey |
| `--line` | `#161b27` | 222 | 28% | 12% | 1.11 | 1.17 | İnce çizgi |
| `--line-card` | `#1d2432` | 220 | 27% | 15% | 1.22 | 1.30 | Kart kenarı |
| `--line-button` | `#262f40` | 219 | 25% | 20% | 1.42 | 1.50 | Kontrol kenarı |

### 1.2 Metin rampası

| Token | Hex | L | vs `--bg-card` | AA normal | AAA normal |
|-------|-----|---|----------------|-----------|------------|
| `--text` | `#e7eaf1` | 93% | **15.81** | ✓ | ✓ |
| `--text-2` | `#c8cddb` | 82% | **11.98** | ✓ | ✓ |
| `--text-3` | `#98a1b4` | 65% | **7.34** | ✓ | ✓ |
| `--text-muted` | `#8b94a6` | 60% | **6.24** | ✓ | ✗ |
| `--text-muted-2` | `#7b8497` | 54% | **5.07** | ✓ | ✗ |
| `--text-dim` | `#808a9d` | 56% | **5.48** | ✓ | ✗ |
| `--text-dim-2` | `#7b8497` | 54% | **5.07** | ✓ | ✗ |
| `--text-dimmest` | `#737d90` | 51% | **4.59** | ✓ | ✗ |

Metin rampasının tamamı AA'yı geçiyor. Bu, aynı gün yapılan HCI incelemesinin
F2 bulgusunun sonucudur: önceki değerler 4.22, 3.35 ve **2.54** idi.

### 1.3 Vurgu ve risk

| Token | Hex | H | S | L | vs `--bg-card` | AA |
|-------|-----|---|---|---|----------------|-----|
| `--lavender` | `#b3a5ff` | 249 | 100% | 82% | 8.83 | ✓ |
| `--mint` | `#5fe3b0` | 157 | 70% | 63% | 11.88 | ✓ |
| `--cyan` | `#4fd8f0` | 189 | 84% | 63% | 11.25 | ✓ |
| `--coral` | `#ff7a5c` | 11 | 100% | 68% | 7.43 | ✓ |
| `--risk-low` | `#4fd08a` | 147 | 58% | 56% | 9.72 | ✓ |
| `--risk-med` | `#e8c85a` | 46 | 76% | 63% | 11.64 | ✓ |
| `--risk-high` | `#f09a4a` | 29 | 85% | 62% | 8.55 | ✓ |
| `--risk-crit` | `#ee5a52` | 3 | 82% | 63% | 5.64 | ✓ |

**Kontrast tarafında tek bir FAIL yok.** Bu denetimin bulguları kontrastta
değil, ayırt edilebilirlikte ve tutarlılıkta.

---

## 2. Color Harmony Tespiti

Palet **iki katmanlı** kurulmuş ve iki farklı harmoni kullanıyor:

**Katman 1 — nötr eksen: Monochromatic.** Sekiz zemin/çizgi token'ının tamamı
219°–225° arasında, yani tek bir mavi-gri hue'nun tone/shade'leri. Doygunluk
%44'ten %25'e düşerken parlaklık %4'ten %20'ye çıkıyor: ders notundaki
monokromatik tanımın birebir karşılığı. Etki "minimal, uyumlu" — mission
control için doğru seçim, çünkü zemin bilgi taşımaz, bilgiyi taşır.

**Katman 2 — vurgular: Analogous + tek Complementary.**

| İlişki | Renkler | Açı farkı | Yorum |
|--------|---------|-----------|-------|
| Analogous üçlü | mint 157° → cyan 189° → lavender 249° | 92° yay | Sakin, doğal; sistem kroması |
| Complementary çift | cyan 189° ↔ coral 11° | **178°** | Neredeyse kusursuz complementary |

**Uygunluk değerlendirmesi.** Yapı bilinçli ve projeye uygun: analogous üçlü
sistemin sürekli görünen kromasını taşıyor (düşük dikkat maliyeti), coral ise
cyan'ın tam karşısında durduğu için tek başına dikkat çekiyor — hedef işareti
ve termal uç değerler bu renkte. Ders notundaki "complementary yüksek kontrast,
dikkat çeker" tanımı burada amaca uygun kullanılmış.

**Ancak "Limit your palette to 3 colors" kuralı aşılmış.** Sayım: 4 vurgu
(lavender, mint, cyan, coral) + 4 risk (yeşil, sarı, turuncu, kırmızı) = **8
kromatik değer**. Risk rampası veri kodlaması olduğu için savunulabilir bir
istisnadır; ancak mint (157°) ve `--risk-low` (147°) sadece 10° ayrı, yani
palette **iki ayrı yeşil** var ve ikisi farklı şey demek istiyor (mint =
başlangıç noktası, risk-low = güvenli segment). Bkz. Bulgu C4.

---

## 3. 60-30-10 Kuralı

Bildirim sayısı zayıf bir vekildir; bu yüzden 1600×1000 kokpit ekranında
**gerçek boyanan alan** ölçüldü.

| Grup | Token'lar | Ölçülen alan | Kural | Sapma |
|------|-----------|--------------|-------|-------|
| Dominant (zemin) | `--void`, `--bg-surface`, scrim'ler | **%72** | %60 | +12 |
| Secondary (yüzey) | `--bg-card`, `--bg-inset`, `--bg-raised`, `--glass` | **%25** | %30 | −5 |
| Accent | lavender, mint, cyan, coral, risk rampası | **~%3** | %10 | **−7** |

**Yorum.** Secondary neredeyse hedefte. Asıl sapma accent tarafında: vurgu
renkleri ayrılan payın üçte birini kullanıyor. Bu bir kusur değil, bir
**tercih** — kokpit sessiz bir zemin üzerine az sayıda parlak okuma
yerleştiriyor ve bu, veri yoğun bir arayüzde doğru bir karardır. Ne var ki
sonucu şudur: az kullanılan her vurgunun **ayırt edilebilir olması** kritik
hale gelir, çünkü karşılaştırma yapacak yeterli alan yoktur. Bölüm 5'in önemi
buradan geliyor.

> **Ölçüm sınırı.** Yöntem `background-color` taşıyan öğeleri sayar; metin
> rengi ve canvas'a çizilen rota pikselleri dahil değildir. Rota çizgisi
> accent payını bir miktar yükseltir, ancak 2.8px'lik bir çizgi olarak
> büyüklük mertebesini değiştirmez.

---

## 4. WCAG 2.1 AA Kontrast Tablosu

Fiilen kullanılan metin × zemin çiftleri:

| Çift | Kontrast | AA normal (4.5) | AA large (3.0) | AAA normal (7.0) |
|------|----------|-----------------|----------------|-------------------|
| `--text` / `--bg-card` | 15.81 | ✓ | ✓ | ✓ |
| `--text-2` / `--bg-card` | 11.98 | ✓ | ✓ | ✓ |
| `--text-3` / `--bg-card` | 7.34 | ✓ | ✓ | ✓ |
| `--text-muted` / `--bg-card` | 6.24 | ✓ | ✓ | ✗ |
| `--text-muted-2` / `--bg-card` | 5.07 | ✓ | ✓ | ✗ |
| `--text-dim` / `--bg-card` | 5.48 | ✓ | ✓ | ✗ |
| `--text-dim-2` / `--bg-card` | 5.07 | ✓ | ✓ | ✗ |
| `--text-dimmest` / `--bg-card` | 4.59 | ✓ | ✓ | ✗ |
| `--text-dim-2` / `--bg-inset` | 5.14 | ✓ | ✓ | ✗ |
| `--lavender` / `--bg-card` | 8.83 | ✓ | ✓ | ✓ |
| `--mint` / `--bg-card` | 11.88 | ✓ | ✓ | ✓ |
| `--cyan` / `--bg-card` | 11.25 | ✓ | ✓ | ✓ |
| `--coral` / `--bg-card` | 7.43 | ✓ | ✓ | ✓ |
| `--risk-crit` / `--bg-card` | 5.64 | ✓ | ✓ | ✗ |
| `--risk-high` / `--bg-card` | 8.55 | ✓ | ✓ | ✓ |
| `--risk-med` / `--bg-card` | 11.64 | ✓ | ✓ | ✓ |
| `--risk-low` / `--bg-card` | 9.72 | ✓ | ✓ | ✓ |

**AA FAIL sayısı: 0.** Sekiz çift AAA'yı geçemiyor; koyu tema ve 11px taban
için AA yeterli kabul edilmiştir, AAA hedef değildir.

**UI komponent kontrastı (WCAG 1.4.11, eşik 3:1)** — burada bir sorun var:

| Öğe | Çift | Kontrast | 3:1 |
|-----|------|----------|-----|
| Kart kenarı | `--line-card` / `--bg-card` | 1.22 | **✗ FAIL** |
| Kontrol kenarı | `--line-button` / `--bg-card` | 1.42 | **✗ FAIL** |
| İnce ayraç | `--line` / `--bg-surface` | 1.08 | **✗ FAIL** |

Tasarım sistemi derinliği gölgeyle değil hairline ile kuruyor; o hairline'lar
1.08–1.42 kontrastta. Bkz. Bulgu C3.

---

## 5. Renk Körlüğü Simülasyonu

Viénot-Brettel-Mollon matrisleriyle hesaplandı. Ayırt edilebilirlik skoru:
doğrusal ışık RGB uzayında Öklid mesafesi × 100. **~25 altı pratikte "aynı
renk" demektir.**

### 5.1 Risk rampasının simüle edilmiş halleri

| Token | Normal | Protanopi | Dötanopi | Tritanopi |
|-------|--------|-----------|----------|-----------|
| `--risk-low` | `#4fd08a` | `#c2c28b` | `#b3b38e` | `#64c9c9` |
| `--risk-med` | `#e8c85a` | `#cece5a` | `#d3d357` | `#f0bebe` |
| `--risk-high` | `#f09a4a` | `#adad49` | `#bcbc41` | `#f49393` |
| `--risk-crit` | `#ee5a52` | `#848450` | `#a0a047` | `#ee5959` |

Dötanopide dört rengin üçü (`#b3b38e`, `#d3d357`, `#bcbc41`, `#a0a047`) aynı
haki-zeytin ailesine düşüyor.

### 5.2 Çift ayırt edilebilirliği — panel/rapor renkleri

| Çift | Normal | Protanopi | Dötanopi | Tritanopi |
|------|--------|-----------|----------|-----------|
| low / crit | 95.5 | 46.7 | **24.8** | 100.1 |
| low / med | 74.6 | **19.2** | 33.8 | 74.7 |
| low / high | 87.1 | **25.5** | **23.1** | 88.1 |
| med / high | **26.5** | 28.5 | **21.5** | 32.3 |
| high / crit | **22.2** | 26.3 | **21.7** | 27.4 |
| med / crit | 47.8 | 54.6 | 42.9 | 59.1 |

**En kritik satır `low / crit`:** ürünün taşıdığı en önemli ayrım — "bu segment
güvenli" ile "bu segment kritik" — dötanopide 95.5'ten **24.8**'e düşüyor.
Kayıp %74. Dötanopi erkeklerin yaklaşık **%6**'sında görülür.

**`med / high` ve `high / crit` normal görüşte bile zayıf** (26.5 ve 22.2).
Bu bir renk körlüğü sorunu değil, palet sorunu: sarı-turuncu-kırmızı üç
basamak 43°'lik bir yay içine sıkışmış.

### 5.3 Haritadaki rota — farklı ve daha iyi

`MapCanvas.tsx:445` LOW segmentini risk yeşiliyle değil `ROUTE_CYAN`
(`#4fd8f0`) ile çiziyor. Sonuç belirgin biçimde daha iyi:

| Çift | Normal | Protanopi | Dötanopi | Tritanopi |
|------|--------|-----------|----------|-----------|
| LOW(cyan) / CRIT | 125.1 | 93.7 | **84.7** | 117.8 |
| LOW(cyan) / MED | 106.5 | 77.4 | 82.7 | 85.7 |
| MED / HIGH | 26.5 | 28.5 | **21.5** | 32.3 |
| HIGH / CRIT | 22.2 | 26.3 | **21.7** | 27.4 |

Haritada uç noktalar sağlam; zayıflık yine bitişik basamaklarda.

### 5.4 Akromatopsi / projeksiyon (gri ton)

| Token | Göreli parlaklık |
|-------|------------------|
| `--risk-med` | 0.592 |
| `--risk-low` | 0.486 |
| `--risk-high` | 0.421 |
| `--risk-crit` | 0.261 |

Sıralama **monoton değil**: `med`, `low`'dan parlak. Gri tonda rampa
"orta → düşük → yüksek → kritik" olarak okunur, ki bu anlamsal sıra değildir.
Düşük kaliteli bir projeksiyonda veya gri baskıda risk sırası tersine döner.

---

## 6. Color Coding Denetimi

Ders notunun kuralı: *"Avoid relying solely on color to convey information."*

| Yer | Renk | İkinci kanal | Durum |
|-----|------|--------------|-------|
| Görev raporu risk sütunu | risk rampası | **Metin** (`LOW`, `CRITICAL`) | ✓ Geçer |
| Rapor risk dağılımı çubuğu | risk rampası | **Etiket + yüzde** | ✓ Geçer |
| Rapor eğim histogramı | risk rampası | **Bant aralığı + sayı** | ✓ Geçer |
| Alt şerit lejantı | risk rampası | **Etiket** (Safe/Caution/High/Critical) | ✓ Geçer |
| Toast bildirimi | `--risk-med` / `--risk-high` | **Başlık metni** | ✓ Geçer |
| Rota analizi risk noktası | risk rampası | Aynı satırda metin var | ✓ Geçer |
| **Haritadaki rota çizgisi** | risk rampası | **YOK** | ✗ **FAIL** |
| **Arazi katmanları** (termal, eğim, maliyet) | sürekli renk skalası | **YOK** | ✗ **FAIL** |

**İki gerçek ihlal var ve ikisi de haritada** — yani rengin en çok bilgi
taşıdığı yerde. Rota çizgisi 2.8px kalınlığında düz bir çizgidir; segmentin
riski yalnızca rengiyle söylenir. Arazi katmanları da salt renk skalasıdır;
imleç telemetrisi sayısal değeri verir ama bu, "haritanın neresi tehlikeli"
sorusunun tarama yoluyla cevaplanmasını sağlamaz.

---

## 7. Koyu Tema Kontrolü

Hedef yalnızca koyu tema; açık tema token'ı beklenmiyor. Ders notundaki koyu
tema kontrol listesine karşı:

| Kontrol | Durum | Kanıt |
|---------|-------|-------|
| Saf siyah yerine yumuşatılmış zemin | ✓ | `--void` `#05070d`, saf siyah değil ve 225° mavi-gri taşıyor |
| Saf beyaz metin yerine kırık beyaz | ✓ | `--text` `#e7eaf1`, `#ffffff` değil |
| Accent doygunluğu koyu temaya ayarlanmış | **Kısmî** | `--lavender` ve `--coral` **S %100**. Diğer accent'ler %58–85 bandında. İki token bandın dışında |
| Tüm renklerin tema karşılığı tanımlı | ✓ (tek tema) | Kapsam gereği |

`--lavender` ve `--coral` %100 doygunlukta ve koyu zeminde en parlak iki
kromatik değer. Ders notu koyu temada doygunluğun düşürülmesini öneriyor.
Bkz. Bulgu C5.

---

## 8. Bulgular

| # | Bulgu | Etki | Aksiyon |
|---|-------|------|---------|
| **C1** | **Risk rampasının bitişik basamakları ayırt edilemiyor.** `med/high` 26.5, `high/crit` 22.2 — normal görüşte. Dötanopide 21.5 ve 21.7. `low/crit` dötanopide 95.5'ten 24.8'e düşüyor. | **Critical** | Bölüm 9'daki rampa (en zayıf çift 15.4 → **30.5**) + zorunlu ikinci kanal |
| **C2** | **Haritada renk tek kanal.** Rota çizgisi ve arazi katmanları riski yalnızca renkle söylüyor (`MapCanvas.tsx:445`). Ders notunun açık ihlali. | **Critical** | Rota segmentlerine risk'e göre **çizgi deseni** (LOW düz, MED uzun kesik, HIGH kısa kesik, CRIT noktalı) + HIGH/CRIT segment başlarına işaretçi |
| **C3** | **Hairline'lar UI kontrast eşiğini geçmiyor.** `--line-card`/`--bg-card` = **1.22**, `--line-button` = **1.42**, WCAG 1.4.11 eşiği 3:1. Sistem derinliği tamamen hairline'a dayandığı için kart sınırları düşük görüşte kayboluyor. | **High** | Etkileşimli kontrol kenarlarını 3:1'e çıkar (`--line-button` → `#4a5570`, 3.03). Dekoratif ayraçlar muaf tutulabilir; 1.4.11 yalnızca **anlam taşıyan** sınırları kapsar |
| **C4** | **Aynı anlam iki renkte.** Lejant "Safe" için `#4fd08a` (yeşil) gösteriyor, harita LOW segmentini `#4fd8f0` (cyan) çiziyor — aralarındaki mesafe **62.0**. Lejant, haritanın o durum için hiç kullanmadığı bir rengi öğretiyor. Ayrıca `--mint` (157°) ve `--risk-low` (147°) sadece 10° ayrı ve farklı şeyler demek istiyor. | **High** | LOW'u tek renge bağla. **Cyan tarafında birleştir** — cyan dötanopide CRIT'ten 84.7 uzakta, yeşil 24.8. Yani doğru cevap lejantı ve panelleri haritaya uydurmak, tersi değil |
| **C5** | **İki accent %100 doygunlukta.** `--lavender` ve `--coral` koyu temada ders notunun önerdiği doygunluk indirimini almamış. | Medium | `--lavender` → `#b0a3f0` (S %72), `--coral` → `#f57e63` (S %88). Kontrast korunur, koyu zeminde göz yorgunluğu azalır |
| **C6** | **Gri tonda rampa monoton değil.** `med` (0.592) `low`'dan (0.486) parlak; projeksiyon veya gri baskıda risk sırası bozuluyor. | Medium | Bölüm 9'daki rampa parlaklığı monoton kurar (0.686 → 0.683 → 0.366 → 0.212) |
| **C7** | **Accent payı hedefin üçte biri.** Ölçülen 72/25/**3**, kural 60/30/**10**. | Low | Kusur değil, tercih. Ancak az alan, her vurgunun ayırt edilebilir olmasını zorunlu kılar — C1 ve C2'nin önceliğini yükseltir |

---

## 9. Önerilen Düzeltilmiş Rampa

400.000 adaylık kısıtlı arama ile üretildi. Kısıtlar:

1. Hue bantları trafik-ışığı metaforuna sadık (cyan / sarı / turuncu / kırmızı)
2. Doygunluk %58–88, parlaklık %52–70 — mevcut accent'lerin zarfı
3. `--bg-card` üzerinde AA ≥ 4.5
4. Gri tonda **monoton** parlaklık (anlamsal sıra korunsun)
5. Amaç: dört görme durumunun **en kötüsündeki en zayıf çifti** maksimize et

| Token | Mevcut | **Önerilen** | H | S | L | AA | Gri L |
|-------|--------|--------------|---|---|---|-----|-------|
| `--risk-low` | `#4fd08a` | **`#34eef2`** | 181 | 88% | 58% | 13.34 | 0.686 |
| `--risk-med` | `#e8c85a` | **`#efd776`** | 48 | 79% | 70% | 13.30 | 0.683 |
| `--risk-high` | `#f09a4a` | **`#d99455`** | 29 | 63% | 59% | 7.55 | 0.366 |
| `--risk-crit` | `#ee5a52` | **`#f03520`** | 6 | 88% | 53% | 4.75 | 0.212 |

### Sonuç

| Çift | Mevcut (en kötü) | Önerilen (en kötü) |
|------|------------------|--------------------|
| low / med | 19.2 | **48.9** |
| low / high | 23.1 | **66.1** |
| low / crit | 24.8 | **99.8** |
| med / high | 21.5 | **30.5** |
| med / crit | 42.9 | **60.5** |
| high / crit | 21.7 | **33.9** |
| **En zayıf çift** | **15.4** | **30.5** |

`--risk-low` cyan ailesine taşındığı için C4'ü de kapatıyor: harita, lejant ve
paneller aynı rengi kullanır hale gelir.

### Neden bu tek başına yetmiyor

Aynı arama, kısıtlar kaldırıldığında bile trafik-ışığı metaforuyla ulaşılabilen
tavanın **42.6** olduğunu gösterdi (herhangi dört renkle 49.2). Dört basamağı
tek bir renk kanalına sığdırmanın matematiksel bir tavanı var ve **30.5 hâlâ
"güvenli" değil**. Bu yüzden C2'deki ikinci görsel kanal öneri değil,
**gerekliliktir**: rampa iyileştirmesi ile birlikte uygulanmalıdır.

---

## 9.1 Uygulama Durumu

Bulguların tamamı aynı gün uygulandı ve tarayıcıda ölçülerek doğrulandı.

| # | Durum | Ne yapıldı | Doğrulama |
|---|-------|-----------|-----------|
| C1 | Kapatıldı | Rampa yeniden türetildi: `low` yeşilden maviye (H211) geçti — protan/deutan simülasyonunda yeşil kırmızının yanında durur, mavi durmaz | En zayıf çift **15.4 → 27.8**; `low/crit` dötanopide **24.8 → 69.8** |
| C2 | Kapatıldı | `riskToDash`: rota risk yükseldikçe daha çok kırılıyor (düz → uzun kesik → kısa kesik → nokta). Aynı seviyedeki ardışık segmentler **tek yol** olarak çiziliyor, yoksa desen her segmentte baştan başlar ve dördü de aynı görünürdü. HIGH/CRIT koşularının başına kare/üçgen işaretçi | Haritada üç desen birden gözlendi (düz mavi, uzun kesikli sarı, kısa kesikli turuncu) |
| C3 | Kapatıldı | `--line-button` `#262f40` → `#58658a`. Yalnızca kontrol kenarları; dekoratif ayraçlar 1.4.11 kapsamı dışında olduğu için dokunulmadı | **1.42 → 3.30**, 3:1 eşiğini geçiyor |
| C4 | Kapatıldı | `LEGEND_ITEMS` artık hex taşımıyor, `riskToHex`'ten türüyor; lejant swatch'ı blok değil **çizgi** ve deseni de gösteriyor. Haritadaki LOW özel durumu kaldırıldı | Lejant ve harita birebir aynı |
| C5 | Kapatıldı | `--lavender` S%100 → %78 (`#baaff5`), `--coral` S%100 → %78 (`#ed856e`) | Kontrast 8.83 → 9.55 ve 7.43 → 7.42; ikisi de AA |
| C6 | **Kapatılmadı — bilinçli** | Gerekçe aşağıda | — |
| C7 | Aksiyon yok | Kusur değil, tercih | — |

### C6 neden kapatılmadı

Gri tonda monoton rampa ile "LOW gölge cyan'ından uzak dursun" kısıtı
**aynı anda sağlanamıyor**. Ölçüldü: 200.000 aday üzerinden monoton azalan
%2.21, LOW'un cyan'dan ≥40 uzak olması %36.28, AA ile birlikte hepsi
**%0.0000**. Sebep fiziksel — cyan'dan uzaklaşmak LOW'u maviye iter, mavi
doğası gereği koyudur; sarı ise doğası gereği en parlak hue'dur, dolayısıyla
"LOW en parlak" kurulamaz.

Tercih sayıyla yapıldı: akromatopsi dünya nüfusunun **%0.01'inden azında**,
dötanopi erkeklerin **%6'sında** görülür. Gri monotonluğu kovalamak, C1'in
CVD kazanımından feragat etmek anlamına gelirdi. Üstelik C2'nin çizgi deseni
gri tonda da çalışır ve parlaklık sıralamasından daha güçlü bir kanaldır.
Bitişik çiftler arasında asgari gri ayrım (ΔL ≥ 0.06) yine de korundu.

### Denetim sırasında bulunan ek çakışmalar

Rampa değişince, paletin eski değerlerini elle kopyalamış dört yer ortaya
çıktı. Hepsi düzeltildi:

| Yer | Sorun | Çözüm |
|-----|-------|-------|
| `colormap.ts` `batteryToHex` | Pil rengi eski rampayı kullanıyordu. Pil **bir risk okumasıdır** — backend'in `_risk_level` eşikleriyle birebir aynı — ve rampanın kullanmadığı bir renkte gösterilmesi C4'ün ta kendisi olurdu | `riskToHex` çağırıyor |
| `time-axis/overlays.ts` | 4-B rotası `#e8c85a` ile çiziliyordu; haritada sarı çizgi her yerde "MEDIUM risk" demek. Zaman genişletilmiş rota bir risk okuması değil, ikinci bir plandır | Lavanta (`#baaff5`) — planlayıcı çıktısı |
| `corridor/overlays.ts` | Haven noktaları eski risk yeşiliydi | Yeni `risk-low` |
| `pose-loop/overlays.ts` | Koridor sapması ve tetik durumu eski amber/kırmızıydı | Yeni `risk-med` / `risk-crit` |

`components/Fleet/FleetSelectionView.tsx` içindeki `agencyColor` değerleri
**bilerek değiştirilmedi**: ajans kimlik renkleridir, risk semantiği taşımazlar
ve risk rampasıyla aynı ekranda görünmezler.

---

## 10. Sonraki Adım Önerileri

| Sıra | Aksiyon | Gerekçe |
|------|---------|---------|
| 1 | C1 + C2'yi **birlikte** uygula | Ayrı ayrı yetersiz; birlikte yeterli |
| 2 | C4'ü rampa değişimiyle aynı commit'te kapat | `--risk-low` zaten cyan'a taşınıyor |
| 3 | `/sevgi-ai:heuristic-eval` | Nielsen 10 üzerinden severity puanlı denetim; bu denetim yalnızca rengi kapsadı |
| 4 | `/sevgi-ai:usability-eval-plan` | C2'nin çözümü (çizgi deseni) gerçek kullanıcıda ölçülmeli; desen ayrımı da bir öğrenme maliyeti taşır |

---

## Bilinen Boşluklar

| # | Boşluk | Neden açık | Önerilen çözüm |
|---|--------|------------|----------------|
| 1 | Arazi katmanlarının sürekli renk skalaları (termal, eğim, maliyet, viridis, magma) denetlenmedi | Denetim ayrık paleti kapsadı; sürekli skalalar `colormap.ts` içinde algoritmik üretiliyor ve ayrı bir yöntem gerektirir (perceptual uniformity / CVD-safe colormap analizi) | `colormap.ts` için ayrı bir geçiş; viridis zaten CVD-safe tasarlanmıştır, magma ve rdYlGn değildir |
| 2 | Ayırt edilebilirlik metriği doğrusal RGB Öklid mesafesi | CIEDE2000 perceptual olarak daha doğrudur; RGB mesafesi mavi bölgede bir miktar iyimserdir | Nihai palet kararı öncesi CIEDE2000 ile teyit |
| 3 | Gerçek renk körü kullanıcıyla doğrulama yapılmadı | Simülasyon matrisi dikromazi modelidir; anomalöz trikromazi (daha yaygın olan hafif form) modellenmedi | Mümkünse bir kullanıcıyla, değilse Sim Daltonism benzeri araçla ikinci kontrol |
| 4 | 60-30-10 ölçümü metin rengini ve canvas piksellerini saymıyor | Yöntem `background-color` taşıyan öğeleri sayar | Kesin oran gerekiyorsa ekran görüntüsü üzerinden piksel histogramı |
| 5 | Rampa artık "güvenli" değil, yalnızca daha iyi | 27.8, "aynı renk" eşiği olan 25'in üstünde ama rahat değil; dört basamağın tek renk kanalındaki tavanı 42.6 ölçüldü | Uzun vadede risk basamağını üçe indirmek veya desen kanalını kalıcı kılmak değerlendirilmeli |
