# 02 — Görüntü İşleme

> **Soru:** LunaPath'e görüntü işleme nasıl, nerede ve ne kadar girer? Hangi ürünler hazır, hangi model açık kaynak, sim2real riski ne?
>
> **Kısa cevap:** LunaPath'te bugün **hiç görüntü verisi yok** — sadece altimetriden türetilmiş grid'ler var. Oysa görüntü işleme iki farklı yerde iki farklı iş yapar: **(A) yörüngeden** (LROC NAC 1 m/px) global maliyet haritasını 80× iyileştirir ve kaya/krater tespiti sağlar; **(B) rover üzerinden** (stereo kamera) yerel engel kaçınmayı besler. LunaPath'in kimliğine (görev öncesi planlama) uygun olan **A**'dır ve maliyeti düşüktür. B, [05](05_engel_kacinma.md)'in konusudur ve simülasyon gerektirir.

---

## 1. İki ayrı görüntü işleme problemi — karıştırmayın

| | **A: Yörüngeden (orbital)** | **B: Rover üzerinden (in-situ)** |
|---|---|---|
| Girdi | LROC NAC ~1 m/px, WAC 100 m/px | Stereo Navcam/Hazcam |
| Amaç | Kaya/krater haritası, SfS DEM, hazard katmanı | Anlık engel tespiti, VO, SLAM |
| Zamanlama | **Görev öncesi, offline** | **Gerçek zamanlı, onboard** |
| Hesap bütçesi | Serbest (masaüstü/GPU) | Katı (bkz. [08](08_global_local_rotalama_yuku.md)) |
| LunaPath uygunluğu | ✅ Doğrudan uyar, mevcut mimariyi bozmaz | 🟡 Yeni katman + simülatör gerektirir |
| Sim2real riski | 🟢 Düşük (gerçek görüntü kullanılır) | 🔴 Yüksek (sentetik görüntüyle eğitim) |
| Öncelik | **P0/P1** | P2 |

> **Stratejik tavsiye:** A'yı yap, B'yi "mimaride yer ayrıldı, gelecek iterasyon" olarak belgele. B'ye yarım yamalak girmek, A'yı tam yapmaktan daha zayıf bir sonuç verir.

---

## 2. Yol A — Yörünge görüntüsünden maliyet katmanı

### 2.1 Neden gerekli: 80 m'de görünmeyen ne var?

| Tehlike | Tipik boyut | 80 m/px'de görünür mü? | 5 m/px'de? | 1 m/px'de? |
|---|---|---|---|---|
| Krater duvarı (>25° eğim) | 100 m+ | ✅ | ✅ | ✅ |
| Küçük krater (fresh, dik kenar) | 5–50 m | ❌ | 🟡 | ✅ |
| Kaya bloğu (boulder) | 0.5–10 m | ❌ | ❌ (gölgesinden 🟡) | ✅ |
| Basamak / rim çıkıntısı | 0.3–2 m | ❌ | ❌ | 🟡 |

Bugünkü LunaPath, 40 km × 40 km alanı 500×500 hücrede modelliyor. **Bir hücre 6400 m²** — yani bir futbol sahasından büyük. O hücreye "geçilebilir" demek, içinde 3 m'lik bir kaya olmadığını iddia etmek anlamına gelmez. Bu, projenin en büyük **sessiz varsayımıdır** ve mutlaka belgelenmelidir.

**Minimum dürüst formülasyon:** Bugünkü `traversability_grid`'in adı `regional_traversability` olmalı ve tanımı şu olmalı:

> "Bölgesel ölçekte (80 m baseline) geçilebilirlik. Araç ölçeği tehlikelerini (kaya, küçük krater, basamak) **kapsamaz**; bu tehlikeler için ayrı bir hazard katmanı gereklidir."

### 2.2 Hazır ürün: SfS (Shape-from-Shading) DEM'ler

Görüntüden DEM üretmenin iki yolu var:

**(a) Stereo fotogrametri** — iki farklı açıdan çekilmiş NAC çiftinden. Ames Stereo Pipeline (ASP) ile yapılır. Kutupta problemli: düşük güneş açısı, uzun gölgeler, düşük doku → korelasyon başarısız olur.

**(b) SfS / fotoklinometri** — tek görüntünün parlaklık deseninden eğim çıkarma. Piksel ölçeğine yakın detay verir ama **mutlak yükseklik referansı** için altimetriye bağlanmak (bundle adjustment) zorunludur.

**Kritik nokta — sektörün çözdüğü şey:** LROC görüntüleri **LOLA 5 m/px kutup ürününe bundle-adjust edilerek** SfS uygulanıyor. Böylece ürün hem piksel ölçeğinde detaylı hem de LOLA jeodezik referans çerçevesine mutlak bağlı. Bu, "LOLA iz aralarındaki yumuşak interpolasyon boşluklarını" doldurur.

**LunaPath için sonuç: kendiniz SfS yapmanız gerekmiyor.** Ürün hazır:

| Ürün | Çözünürlük | Kapsam | İçerik |
|---|---|---|---|
| [PGDA #104 SDEM'ler](https://pgda.gsfc.nasa.gov/products/104) | **5 m/px** | 13 Artemis III aday bölgesi, >4500 km² | elevation, hillshade, ortomozaik, **slope**, **roughness** |
| [USGS Astropedia — NAC Haworth Photoclinometry DEM](https://astrogeology.usgs.gov/search/map/lunar_lro_nac_haworth_photoclinometry_dem_1m) | **1 m/px** | Haworth krateri | DEM |
| [PGDA #78](https://pgda.gsfc.nasa.gov/products/78) | 5 m/px | 27 site | LDEM + slope + **belirsizlik + 100 clone** |

**`roughness` katmanı LunaPath için doğrudan altın:** Şu anda maliyet fonksiyonunda pürüzlülük terimi yok. SfS ürünleri hazır roughness veriyor. Bu, 5. bir bağımsız penalty (`f_roughness`) için sıfır-modelleme-maliyetli bir girdi.

### 2.3 Kaya (boulder) tespiti — açık kaynak durumu

Bu, literatürde **çözülmüş ve yayınlanmış** bir problem:

- **Küresel Ay kaya haritası**, LRO NAC optik görüntülerinden derin öğrenme ile üretildi (Aussel vd., 2025, JGR Planets). Regolit ve protolith çıkarımları için.
- **Eğitim verisi hazır ve açık:** 512×512 piksel NAC karoları, elle işaretlenmiş kayalar; **~12.000 kaya (>2 m çap), 650 görüntü**. Bounding box kayanın **aydınlık kısmının** çevresine çizilmiş.
- **Model:** ImageNet-önceden eğitilmiş **YOLOv5s6** fine-tune. Kaya + gölgesi birlikte tespit edilir.
- Prieur vd. (2023): Dünya, Ay ve Mars'ta instance segmentation ile bireysel kaya haritalama.

**Yöntemin fiziksel özü (ve neden kutupta işe yarar):** Kaya doğrudan değil, **gölgesinden** tespit edilir. Güneş azimut/elevasyonu biliniyorsa gölge uzunluğundan kaya yüksekliği çıkarılır:

```
h_kaya ≈ L_gölge × tan(güneş_elevasyonu)
```

Kutupta güneş elevasyonu ~1.5° olduğu için `tan(1.5°) ≈ 0.026` → **1 m'lik kaya ~38 m gölge yapar.** Bu, kutbu kaya tespiti için hem çok kolay (gölgeler dev, 1 m/px'de bariz) hem çok zor (gölgeler örtüşür, doygunluk) hale getirir.

> **Bu, LunaPath'e eklenebilecek en "havalı" ve en savunulabilir görüntü işleme bileşeni:** NAC mozaiğinden kaya yoğunluğu haritası → `rock_density_grid` → yeni bir hard/soft constraint. Ekvatorda zor olan iş kutupta gölge geometrisi sayesinde daha erişilebilir.

### 2.4 Krater tespiti

Krater tespiti (crater detection algorithms, CDA) uzun bir literatüre sahip; hem klasik (Hough, template matching) hem CNN tabanlı (DeepMoon vb.) modeller var. LunaPath için değeri **kaya tespitinden daha az**, çünkü büyük kraterler DEM'de zaten görünüyor. Değerli olan kısım: **taze (fresh) küçük kraterler** — dik kenarlı, DEM'de kaybolan, ama optikte parlak ejekta halkasıyla belli olan.

**Öneri:** Krater tespitini P2'ye bırakın. Kaya tespiti daha yüksek getiri/maliyet oranına sahip.

### 2.5 Yol A entegrasyon reçetesi

```
lunapath/src/
  orbital_imagery.py      # (yeni) NAC/SfS urun yukleme + hizalama
  rock_detection.py       # (yeni) YOLO cikarim -> rock_density_grid
```

**Adımlar:**

1. **Bölge seç ve daralt.** 40 km × 40 km alanı 1 m/px'de işlemek 1.6 milyar piksel = pratik değil. **Hiyerarşik yaklaşım:**
   - Global planlama: 80 m (mevcut) veya 20 m
   - "Koridor" analizi: global rota bulunduktan sonra rotanın ±500 m bandını 5 m/px'de yeniden değerlendir
   - Kritik noktalar: sadece rota üstündeki N kritik hücre için 1 m/px NAC karosu

   Bu, [08](08_global_local_rotalama_yuku.md)'deki hesap bütçesi mantığının doğal uzantısıdır ve gerçek misyon planlamasının çalışma şeklidir.

2. **`f_roughness` penalty ekle** (SfS roughness ürününden):

```python
# backend/app/cost_engine.py'ye eklenecek
def f_roughness(rms_height_m: float, rover=None) -> float:
    """RMS yuzey puruzlulugu -> [0,1] penalty.
    Gerekce: tekerlek yaricapinin ~%40'ini asan puruzluluk
    surekli sarsinti ve slip artisi uretir."""
    cfg = _resolve_rover(rover)
    r_ref = 0.4 * float(cfg["wheel_radius_m"])
    return 1.0 - math.exp(-(rms_height_m / r_ref) ** 2)
```

> ⚠️ **Ön koşul:** `wheel_radius_m` şu anda `constants.py` içindeki `ROVERS` kataloğunda **yok**. Bu penalty'yi eklemeden önce dört rover profilinin (`lpr_1`, `luvmi_m`, `viper`, `yutu_2`) tümüne `wheel_radius_m` ve tercihen `ground_clearance_m` alanları eklenmelidir. `ground_clearance_m`, kaya tehlikesi için doğal hard-limit'i de verir: gövde açıklığından yüksek kaya = geçilemez.

Ağırlıkları yeniden normalize etmek gerekir (5 kritere geçiş). AHP matrisini yeniden kurmak yerine, mevcut 4 ağırlığı `(1 - w_rough)` ile ölçekleyip `w_rough` eklemek pratik ve savunulabilir bir ara çözümdür — ama bunu belgeleyin.

3. **`rock_density_grid` üret** ve iki şekilde kullan:
   - **Soft:** `f_rock(n_rocks_per_100m2)` penalty
   - **Hard:** eşik üstü hücreler `traversable = False` (rover'ın gövde açıklığından büyük kaya sayısı > 0 ise)

4. **UI:** NAC mozaiğini frontend'de gerçek arka plan olarak göster. Şu an `MapCanvas.tsx` sentetik/DEM görselleştirme yapıyor; **gerçek Ay görüntüsü** üstüne rota çizmek sunum etkisini dramatik biçimde artırır (bkz. `frontend/public/textures/moon-lroc-wac-global-1024.jpg` — zaten WAC dokusu var, ama global ve 1024 px; kutup NAC mozaiği ile değiştirilebilir).

---

## 3. Yol B — Rover üzeri görüntü işleme (referans için)

Bu yola girmeye karar verirseniz bilinmesi gerekenler:

### 3.1 Kutup aydınlanması perception'ı kırar

Ay güney kutbunun perception açısından tanımlayıcı özelliği: **güneş ufukta (~1.5°)**. Sonuçlar:

- Uzun, keskin gölgeler → terrain feature'ları **saklar**
- Aydınlık/gölge arası dinamik aralık kamera dinamik aralığını aşar → HDR zorunlu
- Stereo korelasyon doku yokluğunda başarısız (feature-sparse görüntüler)
- Doğrudan güneşe bakış → lens flare, saturation
- Gölge içinde sinyal ≈ gürültü → aktif aydınlatma (LED/lazer) gerekir

Kutup için yayınlanmış perception çalışmaları bunu doğruluyor: bölge-tabanlı yöntemler (K-means ile gri seviye segmentasyonu → doku/parlaklık ile zemin/gölge/tehlike sınıflandırma → güneş açısına göre gölge değerlendirmesi → hazard haritası) tam olarak bu problemi hedefliyor.

### 3.2 Referans sonuç: ViT ile düşük aydınlanmada hazard tespiti

Somut, sayısal bir referans (Sensors/MDPI, 2023):

| Özellik | Değer |
|---|---|
| Veri | **Sentetik**: Blender 3.2 + NASA güney kutup DTM (90 km × 90 km) |
| Boyut | **125.000** görüntü, 384×384 RGB; %60/%20/%20 split |
| Etiket | İkili safe/hazardous: `slope < 8°` **ve** `roughness < 10%` |
| Aydınlanma | Güneş lambası **1.5° elevasyon**, rastgele azimut |
| Model | ViT-Base (ImageNet ön-eğitimli) + özel decoder, **105 M param** |
| Baseline | UNet, **17 M param** |
| Sonuç | ViT IoU **~%80** (5.000–9.000 m yükseklik bandında); UNet her bantta daha kötü |
| Çıkarım süresi | ViT **0.346 s**/görüntü, UNet **0.012 s**/görüntü (RTX 3090) |
| Anlamlı detay | Test setinin **4.891/25.000'i tamamen siyah** |

**LunaPath için üç ders:**

1. **%20 civarı görüntü tamamen karanlık.** Perception tek başına yeterli değil; **a priori harita** (yani LunaPath'in yaptığı iş) karanlıkta tek bilgi kaynağıdır. Bu, LunaPath'in varlık gerekçesini güçlendiren bir bulgu — sunumda kullanın.
2. **0.346 s/görüntü bir masaüstü GPU'da.** Uçuş bilgisayarında bu 10–100× daha yavaş olur. Onboard ViT bugün gerçekçi değil ([08](08_global_local_rotalama_yuku.md)).
3. **Yazarların kendi sim2real uyarısı:** "Blender'daki kamera modeli gerçek bir CMOS sensöründen farklı çalışır" ve "görüntülerde gürültü olmaması, veri setinin gerçek veriyle nasıl karşılaştırılacağı konusunda iddia edilmesini engelliyor." Sentetik veriyle eğitip gerçekte çalışacağını iddia etmek **kanıt gerektirir** → [03](03_sentetik_minimum_veri.md).

### 3.3 Gerçek görüntü veri setleri (sim2real köprüsü)

Yol B'ye girerseniz, sentetik veriyi **gerçek analog veriyle** doğrulamak zorundasınız. Ücretsiz ve hazır:

| Veri seti | İçerik | Neden değerli |
|---|---|---|
| **NASA POLAR** ([ti.arc.nasa.gov/dataset/IRG_PolarDB](https://ti.arc.nasa.gov/dataset/IRG_PolarDB/)) | ~**2.600 HDR stereo çift**, 13 arazi senaryosu (seyrek/yoğun kaya, kraterler, farklı boyutlar) | **Dünya'da ama kontrollü kutup benzeri aydınlanmada** çekildi — gerçek sensör, gerçek gölge |
| **POLAR Traverse** ([ti.arc.nasa.gov/dataset/PolarTrav](https://ti.arc.nasa.gov/dataset/PolarTrav/), [arXiv 2403.12194](https://arxiv.org/html/2403.12194)) | Düz hat traverse simülasyonu, **1 m aralıkla** stereo görüntü, regolit simülantı yatağı | Ardışık kareler → VO/SLAM testi |
| **POLAR-Sim** ([arXiv 2309.12397](https://arxiv.org/abs/2309.12397), [Dryad](https://datadryad.org/dataset/doi:10.5061/dryad.ksn02v7hf)) | 13 senaryonun **digital twin**'i (mesh + doku + malzeme) + POLAR'ın tamamı için **23.000 etiket** (bbox + semantik: kaya, gölge, krater) | **Gerçek görüntülerin etiketi + eşleşen sentetik sahne** → sim2real ölçümü için ideal çift |
| **LuSNAR** ([github.com/zqyu9/LuSNAR-dataset](https://github.com/zqyu9/LuSNAR-dataset), [arXiv 2407.06512](https://arxiv.org/abs/2407.06512)) | **108 GB**, Unreal Engine ile 9 sahne; stereo + LiDAR + IMU senkron; panoramik semantik etiket, yoğun derinlik, nokta bulutu, rover pozu | Tek pakette 2D/3D semseg, visual SLAM, LiDAR SLAM, stereo matching, 3D rekonstrüksiyon benchmark'ı |

**POLAR + POLAR-Sim ikilisi, sim2real ölçmenin en temiz yolu:** aynı sahnenin gerçek ve sentetik hali + ortak etiketler. "Sentetikte eğit, gerçekte test et" ölçümünü doğrudan yapabilirsiniz.

### 3.4 Görsel odometri ve lokalizasyon

Rover'ın nerede olduğunu bilmesi, engel kaçınmanın önkoşuludur:

- **VO (visual odometry):** Ardışık stereo kare arasındaki feature takibi ile hareket kestirimi. Mars 2020'de VO, "Thinking-While-Driving" ile sürüş sırasında sürekli çalışıyor. Chandrayaan-3 Pragyan görüntüleri üzerinde VO analizleri yayınlandı.
- **Yutu-2:** görsel SLAM + rota planlama + rover kontrolü ile 6 yılı aşan operasyon; öncülü Yutu'ya kıyasla lokalizasyon, haritalama, otonom navigasyon ve hareket planlamada belirgin ilerleme.
- **DEM-anchored SLAM / segment tabanlı global lokalizasyon** (ör. LunarLoc) — yörünge DEM'ini referans alarak drift'i sıfırlama.

**LunaPath ile bağlantısı:** LunaPath'in ürettiği rota, rover'ın **konumunu bildiği** varsayımına dayanır. Gerçekte konum belirsizliği birikir (Ay'da GPS yok, manyetik alan yok). Bu, planlayıcıya girmesi gereken bir belirsizliktir:

> "Rota, ±X m konum belirsizliği altında hâlâ güvenli mi?" — Rota koridoru genişliği bu belirsizliğe göre ayarlanmalı. Dar bir güvenli geçitten geçen bir rota, 20 m konum hatası varsa güvenli değildir.

Bu, **çok az projenin düşündüğü** ve LunaPath'in düşük maliyetle ekleyebileceği bir olgunluk göstergesidir: `path_corridor_clearance_m` metriği = rota üzerindeki her nokta için en yakın `traversable=False` hücreye mesafe. Minimumu rapor edin.

---

## 4. Boşluk analizi

| # | Boşluk | Etki | Efor | Öncelik |
|---|---|---|---|---|
| I1 | Hiç görüntü tabanlı ürün yok | 🔴 Yüksek (görsel + teknik) | — | — |
| I2 | 80 m hücrede araç-ölçeği tehlike görünmez, bu belgelenmemiş | 🔴 Yüksek (savunulabilirlik) | Çok düşük | **P0** |
| I3 | `roughness` penalty yok (ürün hazırken) | 🟠 Orta-yüksek | Düşük | **P1** |
| I4 | Kaya yoğunluğu katmanı yok | 🟠 Orta-yüksek | Orta | P1 |
| I5 | Frontend gerçek NAC mozaiği kullanmıyor | 🟡 Orta (sunum) | Düşük | P1 |
| I6 | Konum belirsizliği / koridor açıklığı metriği yok | 🟠 Orta | Düşük | P1 |
| I7 | Rover üzeri perception yok | 🟡 Kapsam kararı | Yüksek | P2 |

---

## 5. Yol haritası

### P0 — dürüstlük düzeltmesi (yarım gün)
- `traversability_grid` → `regional_traversability_grid` yeniden adlandır, docstring'e ölçek sınırlamasını yaz
- README ve `referans_belgesi_2.md`'ye "araç ölçeği tehlikeler kapsam dışı" notu

### P1 — yörünge görüntüsü entegrasyonu (3–5 gün)
1. Bir hedef bölge seç ki hem PGDA 5 m SDEM'i hem NAC mozaiği olsun (ör. de Gerlache–Kocher Massif, Shackleton rim)
2. `orbital_imagery.py`: SfS elevation + slope + **roughness** yükle, referans grid'e hizala ([01](01_sektorel_veri_kaynaklari.md) §3.3)
3. `f_roughness` ekle, ağırlıkları yeniden normalize et, doğrulama tablosu üret
4. Hiyerarşik koridor analizi: 80 m global rota → ±500 m bandı 5 m'de yeniden değerlendir → rota "rafine" edildi mi karşılaştırması
5. Frontend: NAC/hillshade arka plan + koridor bandı gösterimi
6. `path_corridor_clearance_m` metriğini `PathResult.metrics`'e ekle

**Kabul kriteri:** Aynı start/goal için "80 m global rota" ile "5 m koridorda rafine rota" arasındaki farkı sayısal gösteren bir karşılaştırma tablosu. Bu tek başına güçlü bir demo hikâyesidir: *"Kaba haritada güvenli görünen rota, yüksek çözünürlükte bakınca 3 noktada kayalık çıktı ve rota şöyle değişti."*

### P2 — kaya tespiti (5–8 gün)
7. NAC karolarını indir, YOLOv5/v8 fine-tune (açık eğitim verisi ile) veya hazır global kaya haritasını kullan
8. Gölge uzunluğu → kaya yüksekliği dönüşümü, güneş geometrisiyle
9. `rock_density_grid` → soft penalty + hard eşik

### P3 — rover üzeri perception (araştırma dalı, kapsam dışı önerilir)
10. OmniLRS/LunarSim ile sentetik stereo üret ([04](04_acik_kaynak_modeller.md))
11. POLAR + POLAR-Sim ile sim2real ölçümü
12. Yerel hazard haritası → [05](05_engel_kacinma.md) mimarisi

---

## 6. Sık yapılan hatalar (kontrol listesi)

- ❌ NAC görüntülerini DEM'e **hizalamadan** üstüne bindirmek. NAC'ın kendi geometrisi var; bundle adjustment olmadan 10-100 m kayma normaldir.
- ❌ Gölgeyi "veri yok" saymak. Gölge **bilgidir** (kaya var, çukur var). NoData ile gölgeyi ayırın.
- ❌ Fotoklinometriyi mutlak referans olmadan kullanmak → uzun dalga boylu sistematik hata (bowl/dome artefaktları).
- ❌ Kutup görüntülerini normalize etmek için global min/max kullanmak. Yerel/adaptif kontrast (CLAHE benzeri) gerekir; aksi halde her şey siyah veya beyaz olur.
- ❌ ImageNet ön-eğitimli modeli tek kanallı gri Ay görüntüsüne 3-kanal tekrarıyla besleyip renk istatistiği uyumsuzluğunu görmezden gelmek. Normalizasyon istatistiklerini veri setinden yeniden hesaplayın.
- ❌ Sentetik görüntüye sensör gürültüsü eklememek (ViT çalışmasının kendi itirafı). Poisson (shot) + Gaussian (read) gürültüsü, PRNU, sıcak piksel, kuantizasyon ekleyin.

---

## Kaynaklar

- [Image-Based Lunar Hazard Detection in Low Illumination Simulated Conditions via Vision Transformers (Sensors, 2023)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10535458/)
- [Aussel et al. (2025), Global Lunar Boulder Map From LRO NAC Optical Images Using Deep Learning, JGR Planets](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2025JE008981)
- [Automated Boulder Counting: Deep Learning for Boulder Detection (LPSC 2023)](https://www.hou.usra.edu/meetings/lpsc2023/pdf/2663.pdf)
- [A Large Training Dataset of Boulder Sizes and Shapes (LPSC 2022)](https://www.hou.usra.edu/meetings/lpsc2022/pdf/1835.pdf)
- [Lunar LRO NAC Haworth Photoclinometry DEM 1m — USGS Astropedia](https://astrogeology.usgs.gov/search/map/lunar_lro_nac_haworth_photoclinometry_dem_1m)
- [Enhanced Topography Models for Lunar South Pole with Shape-from-Shading — PGDA #104](https://pgda.gsfc.nasa.gov/products/104)
- [NASA POLAR Stereo Dataset](https://ti.arc.nasa.gov/dataset/IRG_PolarDB/)
- [NASA POLAR Traverse Dataset](https://ti.arc.nasa.gov/dataset/PolarTrav/) · [arXiv 2403.12194](https://arxiv.org/html/2403.12194)
- [POLAR-Sim: Augmenting NASA's POLAR Dataset (arXiv 2309.12397)](https://arxiv.org/abs/2309.12397) · [Dryad veri](https://datadryad.org/dataset/doi:10.5061/dryad.ksn02v7hf)
- [LuSNAR dataset (arXiv 2407.06512)](https://arxiv.org/abs/2407.06512) · [GitHub](https://github.com/zqyu9/LuSNAR-dataset)
- [Vision Based Obstacle Detection Using Rover Stereo Images (ISPRS)](https://isprs-archives.copernicus.org/articles/XLII-2-W13/1471/2019/isprs-archives-XLII-2-W13-1471-2019.pdf)
- [Efficient Stereo Vision for Feature-sparse Lunar Images (CMU)](https://www.andrew.cmu.edu/user/wleemoor/wleemoor-revisedproposal.pdf)
- [Autonomous robotics is driving Perseverance rover's progress on Mars (Science Robotics)](https://www.science.org/doi/10.1126/scirobotics.adi3099)
- [LunarLoc: Segment-Based Global Localization on the Moon (arXiv 2506.16940)](https://arxiv.org/pdf/2506.16940)
