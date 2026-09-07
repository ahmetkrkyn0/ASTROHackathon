# Faz 1 Çıktısı Nedir, Ne Yaptık, Nasıl Okunur

**Amaç:** Bu belge Faz 1'in tam olarak neyi değiştirdiğini, çıktının nasıl doğrulanacağını ve **neden bazı yerlerde hâlâ "sentetik gibi" hissettirebileceğini** dürüstçe açıklar. Abartısız: neyin gerçek fizik olduğu, neyin sınırlı kaldığı burada net.

---

## 1. Faz 1 ne değiştirdi (tek cümle)

`lunapath/src/process_lunar_data.py` iki katmanı **uydurma formülden gerçek fiziğe** taşıdı:

| Katman | Öncesi | Sonrası |
|---|---|---|
| **Termal (`thermal_grid`)** | `generate_thermal_grid()` — yükseklik + bakıdan uydurulan sentetik ısı | **`heat1d`** — Paul Hayne'in (Diviner ekibi) gerçek 1B regolit termal difüzyon modeli |
| **Gölge (`shadow_ratio_grid`)** | `1 - normalize(yükseklik)` — "alçak = karanlık" varsayımı | **SPICE + ufuk ışın izleme** — gerçek güneş konumu (`sun_track`) vs topografik ufuk açısı (`horizon_map`) |

Ayrıca her katman artık `metadata.json`'da bir **`layer_validity`** etiketi taşıyor: `MEASURED` (ölçüm), `MODEL` (fizik modeli), `DERIVED` (türetilmiş), `SYNTHETIC` (uydurma proxy). Bu, "hangi katman gerçek, hangisi değil" sorusunu makine-okunur hale getiriyor — daha önce bu bilgi hiçbir yerde yoktu.

---

## 2. Nasıl çalıştırılır

```bash
# 1) (bir kez) SPICE kernellerini indir — kernels/ klasörü boşsa gerekli
python lunapath/src/fetch_kernels.py

# 2) Pipeline'ı çalıştır
cd lunapath/src
python process_lunar_data.py
```

**⚠️ Sessiz bekleme uyarısı — bu bir hata değil, bilinen bir sınırlama:**
`horizon: azimuth 72/72` yazdıktan sonra ekran **~12-15 dakika hiçbir şey yazmaz.** Bu `heat1d`'nin gerçek termal tabloyu (13 eğim × 16 bakı = 208 hücre) inşa ettiği aşamadır. `metadata.json` ve `.npy` dosyaları **ancak bu aşama bitince** yazılır. Terminal donmuş gibi görünse de süreç çalışıyordur — `tasklist` (Windows) ile `python.exe`'nin hâlâ çalıştığını doğrulayabilirsin.

```bash
# 3) Sonucu doğrula
cat ../data/processed/metadata.json   # layer_validity alanına bak
```

`layer_validity`'de `shadow_ratio` **`SYNTHETIC`** ise: `kernels/` klasörü yok/eksik demektir — hata değil, tasarımlı dürüst geri düşüş (fallback). `fetch_kernels.py`'yi çalıştırıp tekrar dene.

---

## 3. Çıktıyı nasıl doğrularsın (kendi gözünle)

### a) `layer_validity` — en hızlı kontrol

```json
"layer_validity": {
  "elevation": "MEASURED",
  "shadow_ratio": "DERIVED",   // SPICE + ufuk hesabı çalıştıysa
  "thermal": "MODEL",          // heat1d çalıştıysa
  ...
}
```
Hepsi `SYNTHETIC` değilse, gerçek fizik çalışmış demektir.

### b) Sayısal aralık kontrolü

```python
import numpy as np
thermal = np.load("lunapath/data/processed/thermal_grid.npy")
print(thermal.min(), thermal.max())   # ör. -156.7 ... +42.6 (°C) — heat1d aralığı
```

Eski sentetik model çok daha dar/öngörülebilir bir aralık üretirdi; heat1d gerçek fiziksel uç değerlere ulaşabiliyor (güney kutbunda gölgede -150°C'nin altı, güneşte oda sıcaklığı üstü — gerçek Diviner ölçümleriyle aynı mertebede).

---

## 4. "Neden hâlâ sentetik gibi görünüyor" — dürüst açıklama

Bu **gerçek bir gözlem**, göz yanılması değil. İki bilinen, tasarım-kaynaklı sınırlama var:

### 4.1 Termal katman kaba nicemlenmiş (quantized)

`heat1d` her piksel için ayrı simülasyon **koşturmuyor** — çok pahalı olurdu (piksel başına saniyeler). Bunun yerine **13 eğim × 16 bakı açısı = 208 hücrelik bir arama tablosu (LUT)** kuruyor, her piksel en yakın hücreye atanıyor.

**Sonuç:** 500×500 = 250.000 pikselde **en fazla ~208 farklı sıcaklık değeri** olabilir. Gerçek ölçtük: **165 farklı değer.** Görsel olarak bu, sürekli bir sıcaklık alanı yerine "blok blok" bir görünüm verir — özellikle düz arazide.

**Bu bir hata değil**, LUT yaklaşımının bilinen bedeli (bkz. Faz 1 planı, Task 4). Düzeltme yolu: hücre sayısını artırmak (13×16 → daha fazla) ya da gerçekten piksel-bazlı koşum (çok daha yavaş).

### 4.2 Gölge katmanı sınırlı ufuk menzilinde

`horizon_map`'in `max_steps=200` parametresi, hesap yükünü çözünürlükten bağımsız tutmak için **fiziksel menzili** sınırlıyor. 5 m/px'te bu, **~1 km efektif ufuk menzili** demek. Ama kutup bölgesindeki gerçek gölgeler genelde **onlarca km öteden** gelen dağ/krater kenarlarından düşer.

**Sonuç:** Yakın-alan ufku doğru hesaplanıyor ama uzak-alan gölgeleri görülemiyor → gölge katmanı **gerçek fizik ama muhtemelen az-gölgeleme (under-shadowing)** eğiliminde. Gözlemlediğimiz **139 farklı gölge oranı değeri** (168 güneş örneğinin ortalaması olduğu için matematiksel üst sınır zaten ~169) bunu destekliyor.

**Bu da bir hata değil**, çözünürlükten-bağımsızlık kararının (Faz 1 başında verilen kullanıcı kararı) bilinen bedeli.

### 4.3 Kısaca

> Katmanlar **gerçekten** `heat1d` ve `SPICE`'tan geliyor — uydurma formüle geri dönülmedi. Ama ikisi de **düşük çözünürlüklü/kaba yaklaşımlarla** çalışıyor (LUT + sınırlı ufuk menzili), bu yüzden görsel olarak eski sentetik versiyona göre daha "pürüzsüz"/"sürekli" bir iyileşme hissettirmiyor. Fiziksel doğruluk arttı; görsel çözünürlük henüz artmadı.

---

## 5. Bir sonraki adım olarak neyi iyileştirebilir

Final whole-branch review'da zaten not düşülmüş, Faz 2/3'e bırakılmış maddeler:

- **heat1d LUT hücre sayısını artırmak** (13×16 → örn. 25×32) — daha yumuşak termal geçişler, ama LUT inşa süresi de artar.
- **İki-aşamalı ufuk hesabı**: yakın alan (bugünkü gibi ince) + uzak alan (daha kaba grid'de, daha uzun menzil), `np.maximum` ile birleştirilir — kutup gölgelerinin gerçek kaynağı olan uzak relief'i yakalar.
- **heat1d LUT'una ilerleme çıktısı + disk-üstü cache** — 12-15 dakikalık sessiz bekleme sorununu çözer, her koşumda sıfırdan hesaplamayı önler.

---

*İlgili: [`2026-08-19-faz1-tamamlanma-raporu.md`](2026-08-19-faz1-tamamlanma-raporu.md) (tam commit/karar geçmişi), [`2026-08-19-faz1-gercek-fizik.md`](2026-08-19-faz1-gercek-fizik.md) (orijinal görev planı).*
