# DEM ve Veri Hattı — Ham NASA Verisinden Kullanılabilir Haritaya

**Kodda:** `backend/app/data_loader.py`, `backend/app/grid_frame.py`, `backend/app/serializer.py`
**API:** `POST /api/load-dem`, `POST /api/load-preprocessed`, `GET /api/layers/{katman}`

---

## Nedir?

DEM = **Digital Elevation Model** (Sayısal Yükseklik Modeli). Ay yüzeyinin bir bölgesinin, her noktası için "bu nokta deniz seviyesinden (Ay'da: referans küreden) kaç metre yüksekte" bilgisini tutan devasa bir sayı tablosu.

Veri hattı, bu ham tablodan LunaPath'in kullanabileceği **yedi ayrı haritayı** üreten boru hattıdır: yükseklik, eğim, bakı, sıcaklık, gölge oranı, geçilebilirlik, maliyet.

---

## Hangi problemi çözüyor?

NASA'nın yayınladığı ham dosya bir GeoTIFF: sadece yükseklik sayıları var. Ama planlayıcı yüksekliği umursamaz. Planlayıcının bilmek istediği şey "bu hücreden geçebilir miyim ve geçmek bana neye mal olur".

Veri hattı bu çeviriyi yapar: **yükseklik → kullanılabilir karar bilgisi.**

Ayrıca ham dosya çok büyük. Ay güney kutbunun tamamı gigabaytlarca veri. Veri hattı bundan bir **pencere** kesip (bizim durumda 500×500 hücre = 2,5 km × 2,5 km) üstünde çalışılabilir hâle getirir.

---

## Analoji: Ham fotoğraftan haritaya

Bir drone ile bir araziyi fotoğrafladığınızı düşünün. Elinizdeki şey sadece piksel renkleri. Ama siz bu araziye kamp kuracaksınız, yani şunları bilmeniz lazım: nerede dik yamaç var, nerede gölge oluyor, nerede su birikiyor, çadır nereye kurulur.

Veri hattı bu "fotoğraftan haritaya" dönüşümü yapan kartografdır. Fotoğraftaki bilgi zaten vardı — ama işlenmeden kullanılamazdı.

---

## Nasıl çalışıyor?

### Adım 1: Ham DEM okunur

`rasterio` kütüphanesiyle GeoTIFF açılır, istenen pencere kesilir. Site11 penceresi 500×500 hücre, hücre başına 5 metre.

### Adım 2: Türetilmiş katmanlar hesaplanır

| Katman | Nasıl hesaplanır | Etiket |
|---|---|---|
| **Eğim (slope)** | Komşu hücreler arası yükseklik farkından, derece cinsinden | `DERIVED` |
| **Bakı (aspect)** | Yamacın hangi yöne baktığı (0 = Kuzey, 90 = Doğu) | `DERIVED` |
| **Ufuk haritası** | Her hücreden 72 farklı yöne ışın atılarak, o yöndeki en yüksek engelin açısı | `DERIVED` |
| **Sıcaklık** | heat1d modeli (veya yedek heuristik) | `MODEL` / `SYNTHETIC` |
| **Gölge oranı** | Ufuk + Güneş konumu | `DERIVED` |
| **Geçilebilirlik** | Eğim ve sıcaklık kurallarından | `DERIVED` |
| **Maliyet** | Beş kriterin ağırlıklı toplamı | en zayıf girdiye göre |

### Adım 3: Önbelleğe yazılır

Bu hesaplar pahalı (ufuk haritası tek başına dakikalar sürüyor). O yüzden sonuç `.npy` dosyaları olarak diske yazılır ve bir sonraki açılışta doğrudan okunur.

Önbellek **anahtarlı**: maliyet formülü değişirse `COST_MODEL_ID` sabiti değişir ve eski önbellek otomatik geçersiz olur. Şu anki değeri: `weighted_cell_cost_shadow_aware_energy_slip_roughness_v5`. Yani formül beş kez değişti ve her seferinde eski önbellekler doğru şekilde çöpe gitti.

### Adım 4: Koordinat çevirisi

Üç ayrı koordinat sistemi var ve bunlar sürekli birbirine çevriliyor:

1. **Piksel** — (satır, sütun). Dizinin içindeki yer.
2. **Projeksiyon metresi** — (x, y). Ay Güney Kutup Stereografik projeksiyonunda metre.
3. **Coğrafi** — (boylam, enlem). İnsanın anlayacağı hâli.

Bu çeviri `grid_frame.py`'de **tek bir yerde** duruyor:

```
x = origin_x + sütun * çözünürlük
y = origin_y - satır  * çözünürlük        ← eksi işaretine dikkat
```

Eksi işareti kritik: `origin` pencerenin **sol üst** köşesi ve satır numarası aşağı (güneye) doğru artıyor.

> **Gerçek hikâye:** Bu formül bir dönem üç ayrı dosyada kopyalanmıştı ve birinde işaret tersti. Projede "Faz 2 C2 bulgusu" olarak geçiyor. Şimdi tek yerde ve diğerleri oradan çağırıyor.

---

## Neye göre çalışıyor?

- **Veri:** NASA LRO / LOLA LDEM ürünleri, Site11 penceresi
- **Çözünürlük:** 5 m/piksel (planlayıcı kaba ızgarada 80 m veya 320 m blok kullanabilir)
- **Boyut:** 500×500 hücre
- **Projeksiyon:** Ay Güney Kutup Stereografik
- **Referans yarıçap:** 1 737 400 m

---

## İlham kaynağı

Bu doğrudan NASA'nın kendi veri hattının uyarlaması. LOLA ekibi yükseklik ürünlerini yayınlıyor; eğim/bakı/ufuk türetmesi standart jeomorfometri. Özel olan kısım, bunların **tek bir tutarlı önbellek şeması** altında toplanması ve her katmanın kendi güvenilirlik etiketini taşıması.

---

## Kodda nerede?

| Ne | Nerede |
|---|---|
| DEM okuma + önbellek | `backend/app/data_loader.py` |
| Piksel ↔ metre çevirisi | `backend/app/grid_frame.py` → `pixel_to_map_xy` |
| Metre ↔ coğrafi çeviri | `backend/app/serializer.py` → `pixel_to_lonlat` |
| Katman servisi | `main.py` → `GET /api/layers/{katman}` |
| Binary 3-D transferi | `backend/app/terrain.py` |

---

## Jüri soruları

**S: "Veriyi nereden aldınız?"**
NASA LRO'nun LOLA aletinin yayınladığı sayısal yükseklik modelleri. Ay güney kutbundan Site11 adlı bölgeyi kestik: 500×500 hücre, 5 metre çözünürlük.

**S: "5 metre çözünürlük yeterli mi?"**
Küresel planlama için evet, yerel manevra için hayır. Zaten sistem bunu kabul ediyor: LunaPath **küresel planlayıcı**, çıktısı bir "koridor" — yani "şu çizgiyi takip et, şu kadar sağa sola sapabilirsin". Koridorun içindeki metre altı manevra, rover üstündeki yerel planlayıcının işi. Bu ayrım [koridor sözleşmesi dosyasında](../04-planlama-ve-maliyet/koridor-sozlesmesi.md).

**S: "Neden önbellek kullanıyorsunuz, her seferinde hesaplasanız olmaz mı?"**
Ufuk haritası tek başına 500×500 grid'de dakikalarca sürüyor (72 azimut yönü × 250 000 hücre × ışın yürüyüşü). Bir plan isteği 2 saniyede dönmeli. Önbellek zorunlu — ama formül değiştiğinde otomatik geçersiz olan cinsten.

**S: "Aynı hücreyi farklı pencerelerde yüklerseniz aynı sonucu alır mısınız?"**
Şimdi evet. Bir dönem almıyorduk: sentetik sıcaklık modeli pencerenin kendi min/max yüksekliğine göre normalleştiriyordu, yani aynı arazi farklı kırpmada farklı sıcaklık ve farklı geçilebilirlik veriyordu. Sabit bir yükseklik referansı (−3000 m / +4000 m) konularak düzeltildi.
