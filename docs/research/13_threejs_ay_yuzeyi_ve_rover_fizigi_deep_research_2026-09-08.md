# LunaPath Three.js Ay yüzeyi ve rover fiziği — deep research raporu

**Tarih:** 8 Eylül 2026  
**Hedef kitle:** LunaPath geliştiricileri ve teknik karar vericiler  
**Kapsam:** Mevcut 2,5 × 2,5 km Site11/de Gerlache sahnesinin görsel gerçekçiliği, yüksek çözünürlüklü Ay verileri, Three.js render özellikleri, web tabanlı rover fiziği ve daha yüksek doğrulukta terramekanik seçenekleri  
**Karar ufku:** Önce mevcut React + Three.js arayüzünü bozmadan iyileştirmek; motor değişimini ancak ölçülmüş bir ihtiyaç varsa değerlendirmek  
**Yöntem:** Yerel kod denetimi + NASA/USGS/LROC veri ürünleri + Three.js/Rapier/Project Chrono birincil dokümantasyonu + yerel sentetik Rapier mikro-benchmark'ı. Web kaynakları 8 Eylül 2026 tarihinde kontrol edildi.

---

## 1. Kısa cevap

**Evet, yüzeyi belirgin biçimde daha kaliteli ve gerçekçi yapmak mümkün. Three.js'i değiştirmek gerekmiyor.** Şu anki yumuşak görünümün ana nedeni Three.js'in yetersizliği değil; render edilen ana geometrinin 5 m aralıklı ve büyük ölçüde enterpole edilmiş LOLA DEM olması, arazide normal/displacement/roughness haritalarının kullanılmaması, kayaların/rover'ın zemine Three.js gölgesi düşürmemesi ve Lambert tabanlı malzemenin Ay regolitinin yönlü yansıtmasını doğru temsil etmemesi.

En doğru yol tek bir “8K texture” koymak değildir. Üç ölçeği birlikte çözmek gerekir:

1. **Bilimsel makro geometri:** mevcut PGDA #78 LOLA DEM'i, aynı sahayı kapsayan PGDA #104 Shape-from-Shading SDEM ile değiştir.
2. **Yakın alan görsel mikro-detayı:** yönsüz, tekrar eden PBR normal/roughness katmanı ekle; bunu yalnız görselleştirme olarak etiketle ve rota maliyetine karıştırma.
3. **Işık ve temas hissi:** Lunar-Lambert/Hapke-benzeri BRDF ile yerel kaya/rover gölgelerini ekle.

Rover fiziği için en iyi web seçeneği **doğrudan `@dimforge/rapier3d`** kullanmaktır. Rapier; heightfield collider, rigid body, eklemler, sahne sorguları ve raycast araç denetleyicisi sunar. Ancak Rapier veya cannon-es, regolitin gömülme/sinkage ve gerçek tekerlek-toprak kaymasını fiziksel olarak çözmez. Bu düzey gerekiyorsa **Project Chrono SCM/CRM/DEM** ayrı bir yüksek doğruluk servis/simülatör olarak çalışmalı; Three.js yalnız sonucu göstermelidir.

### Önerilen karar

| Öncelik | Değişiklik | Beklenen katkı | Efor tahmini | Karar |
|---:|---|---|---:|---|
| 0 | `2400/2500` ROI manifestini tek kaynak yap | Cache komutunun sahayı sessizce değiştirmesini önler | 0,5–1,5 gün | **Önce yap** |
| 1 | PGDA #104 `deGerlache_Rim` SDEM + ortomozaik | Gerçek krater/eğim detayında en büyük bilimsel artış | 3–6 geliştirici-günü | **Yap** |
| 2 | Yakın alan yerel gölge + Lunar-Lambert shader | Derinlik, temas ve Ay'a özgü ışık davranışında en büyük görsel artış | 2–4 gün | **Yap** |
| 3 | Ölçeğe bağlı PBR normal/roughness, KTX2 | FPS görünümünde toz, granül ve küçük yüzey kırıkları | 2–4 gün | **Yap** |
| 4 | Terrain tile/LOD ve kaya batching | Daha yüksek detayın performans bütçesine sığması | 3–7 gün | **Yap, ölçümden sonra** |
| 5 | Rapier fizik sandbox'ı | Süspansiyon, gövde salınımı, temas ve devrilme demosu | 4–8 gün | **Ayrı modda yap** |
| 6 | Project Chrono terramekaniği | Sinkage, deformasyon, regolit kayması | 2–6 hafta+ | **Yalnız mühendislik doğruluğu gerekiyorsa** |
| — | Unity/Unreal'a geçiş | Bu darboğazları kendiliğinden çözmez | Çok yüksek | **Şimdi yapma** |

Eforlar kod tabanının mevcut durumuna göre mühendislik tahminidir; veri indirme süresi, GPU hedefleri ve kabul kriterleri netleşince değişebilir.

---

## 2. Araştırma soruları ve yanıt durumu

| Soru | Sonuç | Güven |
|---|---|---|
| Mevcut sahne neden yumuşak? | 5 m geometri + LOLA enterpolasyonu + eksik mikro-normal/gölge/ay BRDF birleşimi | Yüksek |
| Daha iyi ve aynı bölgeyi kapsayan DEM var mı? | Evet; PGDA #104 içindeki `A3CLR22_9_deGerlache_Rim` mevcut pencereyi kapsıyor | Yüksek |
| Daha yüksek çözünürlüklü gerçek görüntü var mı? | Mevcut kaynak zaten LROC NAC 1 m/px; ayrıca Site11'i kapsayan 1 m kontrollü de Gerlache mozaiği var. Doğrudan crop ölçümü kontrollü ürünün daha az derin gölge ve daha yüksek ham kenar enerjisi taşıdığını gösterdi; yine de coregistration gerekir | Yüksek |
| Hazır gerçekçi Ay PBR malzemesi var mı? | Poly Haven'da CC0, 11K–16K regolit setleri var; görsel mikro-detaydır, konumsal bilimsel veri değildir | Yüksek |
| Three.js'te kullanmadığımız yararlı özellikler var mı? | Normal/displacement/roughness map, shadow map/CSM, KTX2, LOD, BatchedMesh, GTAO, TSL ve glTF sıkıştırma yolları kullanılmıyor | Yüksek |
| Tarayıcıda rover fiziği mümkün mü? | Evet; Rapier heightfield + raycast vehicle ile mümkün | Yüksek |
| Tarayıcı fiziği gerçek regolit davranışı verir mi? | Hayır; rigid-body/Coulomb sürtünmesi terramekanik değildir | Yüksek |
| Küresel Ay + yerel saha ölçeği büyürse çözüm var mı? | NASA-AMMOS `3d-tiles-renderer` ve 3D Tiles/LOD yaklaşımı var; mevcut tek saha için şart değil | Orta-yüksek |

Kalan belirsizlikler: SDEM'in mevcut güneş/ufuk/rota sonuçlarını uçtan uca ne kadar değiştireceği, kontrollü LROC ile PGDA `GLDOMOS` adaylarından hangisinin SDEM hillshade/seam açısından en iyi olduğu ve hedef cihazların gerçek GPU bütçesi ancak entegrasyon/A-B benchmark'ı ile ölçülebilir. SDEM/coverage/belirsizlik rasterları ile kontrollü LROC'nin Site11 crop istatistikleri bu araştırmada doğrudan ölçülmüştür.

---

## 3. Mevcut uygulamanın teknik fotoğrafı

### 3.1 Şu anda doğru yapılanlar

- `frontend/package.json` doğrudan Three.js `^0.183.2` kullanıyor; modern WebGL2 tabanı var.
- `TerrainCanvas3D.tsx` içindeki arazi gerçek metre ölçeğinde: `500 × 500` grid, `5 m/px`, yaklaşık `250.000` vertex ve `498.002` üçgen.
- Rover'ın yatay uzunluğu 1,5 m'ye ölçekleniyor; kaya ve arazi boyutlarıyla aynı metrik uzayda.
- LROC NAC kırpımı sahaya coğrafi olarak hizalı. Kaynak `NAC_POLE_P892S3150.TIF` içinden 2500 × 2500 @ 1 m/px; frontend çıktısı 2048 × 2048.
- Renk dokuları `SRGBColorSpace` olarak işaretlenmiş.
- FPS'te eğik açı bulanıklığını azaltmak için ana dokularda `anisotropy = 16` zaten kullanılıyor.
- Çakıl katmanı `InstancedMesh` kullanıyor; bu doğru bir draw-call optimizasyonu.
- Apollo 15 örnekleri 15016 ve 15556'dan NASA Astromaterials 3D kaya geometrileri kullanılıyor.
- Kayalarda dünya-uzayı triplanar albedo eşlemesi var; UV'siz tarama meshleri için doğru yaklaşım.
- Büyük ölçekli güneş/gölge mantığı rastgele ışık yerine backend ufuk küpü ve SPICE zaman serisine bağlı.
- Kaynak temizliği büyük ölçüde düşünülmüş; geometry/material/renderer `dispose()` yolları mevcut.

### 3.2 Eksik veya sınırlı parçalar

| Katman | Şimdiki durum | Sonuç |
|---|---|---|
| Arazi geometrisi | Tek parça 500 × 500 `PlaneGeometry`, yalnız 5 m DEM yüksekliği | Rover yakınında her vertex arası 5 m; sub-metre rölyef yok |
| Arazi albedosu | 2048 LROC foto veya ayrıştırılmış detail JPG | Görüntü detayı var, gerçek mikro-geometri yok; bazı gölgeler fotoğrafa pişmiş |
| PBR haritaları | Arazi için normal, bump, displacement ve roughness map yok | Işık küçük girinti/çıkıntılara tepki vermiyor |
| BRDF | `MeshStandardMaterial`, `roughness=0.97`, `metalness=0`; Lambert açığı ışık şiddeti 3,6 ile kompanse ediliyor | Ortalama parlaklık artıyor ama Ay'ın görüş/yansıma yönüne bağlı davranışı oluşmuyor |
| Dinamik gölge | `renderer.shadowMap.enabled`, `castShadow`, `receiveShadow` yok | Kaya ve rover zemine temas etmiyormuş gibi algılanabilir |
| LOD | Arazi tek çözünürlük; çakılda elle mesafe derecelendirmesi var | Daha yoğun yakın geometriyi tüm sahaya yaymak pahalı olur |
| Doku sıkıştırma | JPG + `TextureLoader`; KTX2 yok | 4K/8K çoklu PBR haritaları GPU belleğini hızlı tüketir |
| Model sıkıştırma | GLTFLoader var; DRACO/KTX2/Meshopt bağlanmamış | Rover/gelecek kaya GLB'leri büyüdüğünde yükleme ve bellek maliyeti artar |
| Fizik | Pozisyon/heading ve tekerlek dönüşü kinematik animasyon | Gövde salınımı, teker temas kuvveti, süspansiyon, devrilme yok |

### 3.3 “Soft” görünümün sayısal nedeni

- 2,5 km genişliğe gerilen 2048 doku yaklaşık **1,22 m/texel** verir. Kaynak 1 m/px olduğundan 4096'ya büyütmek yeni ayrıntı yaratmaz; yalnız yeniden örnekleme yapar.
- Yerel provenance kaydı mevcut kutup mozaiği kırpımının yaklaşık `%52` derin gölgede, yalnız `%44` kullanılabilir sinyalde olduğunu; foto gölgesi ile uygulama epoğu gölgesinin IoU değerinin yaklaşık `%51` kaldığını belgeliyor. Yani “soft/boş” hissin bir bölümü çözünürlükten değil, kaynak görüntüde fiziksel olarak sinyal bulunmamasından geliyor.
- Geometri **5 m/vertex** olduğu için 1–4 m çukurlar, keskin krater dudakları ve küçük kaya gömülmeleri gerçek silüete dönüşemez.
- PGDA #78 kendi açıklamasında 5 m grid piksellerinin yaklaşık **%90'ının LOLA izleri arasında enterpole edildiğini** ve 5 m “pixel spacing”in her yerde 5 m gerçek ölçüm çözünürlüğü anlamına gelmediğini belirtir. Bu nedenle büyük 8K renk dokusu temel yumuşaklığı çözmez. [NASA PGDA #78](https://pgda.gsfc.nasa.gov/products/78)
- Three.js dokümantasyonuna göre bump/normal map yalnız ışık normalini değiştirir; displacement map ise gerçek vertexleri hareket ettirir. Displacement'ın etkili olması için yeterli vertex yoğunluğu gerekir. [Three.js MeshStandardMaterial](https://threejs.org/docs/pages/MeshStandardMaterial.html)

---

## 4. En önemli veri yükseltmesi: PGDA #104 SDEM

NASA GSFC'nin PGDA #104 ürünü, 13 Artemis III aday bölgesi için 5 m/px Shape-from-Shading DEM yayımlıyor. LROC NAC görüntüleri kalibre edilip LOLA DEM'e projekte ediliyor, bundle adjustment uygulanıyor ve Ames Stereo Pipeline SfS araçlarıyla aydınlık bölgelerde kısa ölçekli topoğrafya geri kazanılıyor. Ürün LOLA jeodezik referansını korurken enterpole boşluklara krater ve eğim detayı ekliyor. Arşiv; SDEM, hillshade, maksimum-aydınlatmalı ortomozaik, görüntü kapsamı, en iyi giriş çözünürlüğü, çok tabanlı eğim ve VRM roughness içeriyor. [NASA PGDA #104](https://pgda.gsfc.nasa.gov/products/104)

### 4.1 Mevcut saha gerçekten kapsanıyor mu?

Evet. Yerel `metadata.json` penceresi:

- X: `-32500 … -30000 m`
- Y: `8500 … 11000 m`
- merkez: `-72.6721° lon, -88.9205° lat`

Dört köşe yaklaşık `-75.3432 … -69.8637° lon`, `-88.9717 … -88.8685° lat` aralığındadır. Zenodo bölge #9 sınırı `-81.1582 … -51.5819° lon`, `-89.0162 … -88.3335° lat`; dolayısıyla pencerenin tamamı içeride kalır. Gerekli arşiv:

```text
A3CLR22_9_deGerlache_Rim.zip
boyut: 1,340,667,387 byte (~1.34 GB ondalık)
lisans: CC BY 4.0
DOI: 10.5281/zenodo.17954508
```

Kaynak: [Zenodo — Archived Dataset for “Enhanced Topography Models…”](https://zenodo.org/records/17954508)

Zenodo sunucusunun HTTP range desteği kullanılarak 1,34 GB arşivin merkezi dizini ve bölge README'si tam arşiv indirilmeden doğrulandı. Arşivde 425 kayıt var; Site11 göçü için önemli üst düzey dosyalar şunlar:

| Dosya | İçerik | Sıkıştırılmamış / ZIP içi boyut |
|---|---|---:|
| `A309_GLDELEV_005.tif` | SfS nihai yükseklik, Float32, 5 m/px | 22,15 / 22,13 MB |
| `A309_GLDMASK_005.tif` | Piksel başına katkı veren aydınlatılmış NAC sayısı | 0,27 / 0,27 MB |
| `A309_GLDSIGM_005.tif` | Simülasyon/pertürbasyon tabanlı yükseklik belirsizliği | 27,45 / 27,14 MB |
| `A309_GLDDIFF_005.tif` | SDEM − LOLA referans farkı | 30,48 / 30,38 MB |
| `A309_GLDOMOS_005.tif` | Maksimum-aydınlatmalı NAC ortomozaiği | 31,65 / 31,66 MB |
| `A309_GLDBRES_005.tif` | Kullanılan en iyi giriş görüntüsü çözünürlüğü | 0,14 / 0,12 MB |
| `A309_GLDSBCT_005.tif` | Piksel başına farklı güneş yönü/bin sayısı | 0,15 / 0,15 MB |
| `SLOPE_MAPS/*` / `ROUGHNESS_MAPS/*` | Çok tabanlı eğim ve VRM haritaları | Her biri için çoklu GeoTIFF |

Arşivin büyük kısmını 194 ayarlanmış kamera JSON'u ve 195 map-projected NAC GeoTIFF'i oluşturuyor. İlk uygulama spike'ında bunların tamamı gerekli değil. Normal indirme akışı ZIP'in tamamını getirir; ancak Zenodo range isteklerini kabul ettiği için kontrollü bir “yalnız gerekli ZIP entry'lerini çıkar” aracı teknik olarak mümkündür. Daha basit ve daha az özel kodlu yol, arşivi bir kez geliştirici makinesinde indirip yalnız kırpılmış/türetilmiş ürünleri proje veri deposuna almaktır.

README'de belirsizlik dosyası `A309_GLDISGM_005.tif` diye yazılmış olsa da arşivde gerçek ad `A309_GLDSIGM_005.tif`'tir. İndirme betiği README adını körlemesine kullanmamalıdır.

### 4.2 Neden aynı 5 m/px ürün daha keskin olabilir?

“Piksel aralığı” ve “etkin çözünürlük” aynı şey değildir. Mevcut LOLA gridinin çok sayıda hücresi seyrek lazer izleri arasında pürüzsüz enterpolasyondur. SfS, birden çok güneş yönündeki NAC gölgelendirmesinden yerel eğim sinyali çıkardığı için aynı 5 m grid üzerinde daha fazla kısa dalga topoğrafya taşır. NASA'nın karşılaştırmaları SDEM eğim haritalarında ek küçük kraterler ve kısa ölçekli özellikler gösterir. [PGDA #104 yöntem ve ürün açıklaması](https://pgda.gsfc.nasa.gov/products/104)

Hakemli ürün makalesi bu farkı nicel olarak da doğrular. Tüm 13 bölgede SDEM'in LOLA noktalarına mutlak yükseklik farkı medyanı `0,537 m`; SDEM–LDEM farkı medyanı `0,464 m`'dir. Mevcut sahayı içeren **region 9** için SDEM–LDEM mutlak farkı medyanı tüm piksellerde `0,433 m`, doğrudan LOLA destekli piksellerde `0,411 m`, LOLA izi olmayan/enterpole piksellerde `0,443 m`'dir. Region 9 bundle adjustment sonucu medyan yeniden-projeksiyon hatası `0,266 px`, p95 `0,333 px` ve medyan map-projection p85 farkı `1,253 m` olarak raporlanır. Bunlar SDEM'in “daha keskin görünüyor” olmasının rastgele gürültü eklemekten ibaret olmadığını destekler; yine de piksel bazında mutlak doğruluk garantisi değildir. [Bertone vd. 2026 — hakemli ürün ve validasyon makalesi](https://doi.org/10.3847/PSJ/ae5b70)

Makale, aydınlatılmış bölgelerde etkin çözünürlüğün 5 m/px'e yaklaştığını ve SDEM'in LOLA'nın kaçırdığı onlarca metre çapındaki kraterleri geri getirdiğini bildiriyor. Buna karşılık PSR'ler mevcut NAC/SfS düzeninde çözülemiyor; buralar alttaki LDEM'e doğru düzgünleştiriliyor ve kapsam/solar-bin maskeleriyle ayrılmalı. Yazarlar ShadowCam verisini gelecek çalışma olarak gösteriyor.

Bu yine de sub-metre DEM değildir. Rover FPS görünümünde 5 m altı toz/çakıl/küçük oluklar için görsel mikro-normal veya sentetik yerel geometri gerekecektir. Makalenin verdiği maliyet de önemlidir: büyük bir bölge için 5 m SfS yaklaşık 30 Haswell CPU üzerinde 72 saatken 1 m çözüm aynı donanımda bir aydan uzun sürebilir. Bu nedenle 1 m'ye “kendimiz hemen üretelim” projenin normal entegrasyon işinden ayrı bir fotogrametri/HPC projesidir.

### 4.3 Site11 crop'unda ölçülen gerçek ürün istatistikleri

ZIP içindeki yedi ana raster, tam arşiv indirilmeden HTTP range + in-memory GeoTIFF ile okundu. Sonuçlar doğrudan projenin `X=-32500…-30000`, `Y=8500…11000` sınırlarına aittir:

| Ölçüm | Site11 sonucu | Yorum |
|---|---:|---|
| `GLDELEV` grid eşleşmesi | `row=2400`, `col=2500`, `500×500 @ 5 m` | Mevcut metadata ile tam eşleşiyor |
| Geçerli SDEM yükseklik hücresi | 250.000 / 250.000 (%100) | Nodata deliği yok; bu her hücrenin NAC ile çözüldüğü anlamına gelmez |
| En az 1 aydınlatılmış NAC katkısı | %91,165 | Kalan %8,835 coverage=0; bu kesim LDEM'e bağlı/fallback olarak ele alınmalı |
| En az 3 güneş yönü/bin | %77,242 | SfS için daha güvenilir çok-yönlü aydınlatma bölümü |
| Katkı görüntüsü sayısı | medyan 11, p95 15, maksimum 21 | Coverage rasterı 15 m gridde |
| En iyi giriş çözünürlüğü | aydınlatılmış hücrelerin %98,289'u ≤1,2 m/px | `GLDBRES` 15 m gridde; 1,1–1,9 m/px aralığı |
| `GLDSIGM` pseudo-belirsizlik | medyan 0,035 m; p95 0,25 m; maksimum 1,98 m | Toplam mutlak doğruluk değildir; makale yukarı kalibrasyon öneriyor |
| SDEM yükseklik aralığı | 529,285–956,976 m | Referans yarıçap 1.737.400 m |

Önemli bir dosya şeması ayrıntısı: `GLDELEV`, `GLDSIGM` ve `GLDDIFF` gerçekten 5 m/px ve `3200×3200`; `GLDMASK`, `GLDBRES` ve `GLDSBCT` ise adlarında `_005` geçmesine rağmen bu arşivde `1066×1066 @ 15 m` gridindedir. Entegrasyon bunları doğrudan 500×500 sanmamalı; nearest-neighbor/alan semantiğine uygun yeniden örnekleme yapmalı ve kaynak çözünürlüğünü metadata'ya yazmalıdır.

Arşivdeki SDEM ile projenin mevcut `Site11_final_adj_5mpp_surf.tif` dosyası tam aynı transform/pencere üzerinde piksel piksel karşılaştırıldı:

| Fark metriği | Sonuç |
|---|---:|
| Yeni − eski yükseklik | medyan `+0,173 m`, ortalama `+0,182 m` |
| Mutlak yükseklik farkı | medyan `0,690 m`, p95 `2,600 m`, p99 `3,842 m`, maksimum `9,550 m` |
| Mutlak 5 m-baseline slope farkı | medyan `1,617°`, p95 `5,560°`, maksimum `24,642°` |
| `>20°` hücre oranı | eski `%9,193`, SDEM `%9,760` |
| 20° eşiğini yeni aşan / artık aşmayan | `%2,577` / `%2,010` |

Bu sonuç iki şeyi aynı anda söylüyor: genel yükselti referansı korunuyor, fakat rota maliyetini etkileyebilecek yerel eğimler anlamlı biçimde değişiyor. Dolayısıyla SDEM yalnız görsel mesh'e takılıp backend slope/cost/horizon önbellekleri eski bırakılmamalı. Ayrıca crop içindeki mutlak fark medyanının tüm region 9 medyanından (`0,433 m`) yüksek olması, bölgesel ortalamanın Site11 özelindeki değişimi temsil etmediğini gösterir.

### 4.4 Entegrasyon reçetesi

#### Ön koşul: tek kanonik ROI seçimi

Depoda şu anda sessiz ama kritik bir tutarsızlık var:

| Kaynak | Beklediği pencere |
|---|---|
| Çalışan `lunapath/data/processed/metadata.json` | `row=2400`, `col=2500` |
| Ekrandaki LROC texture provenance ve bu rapordaki Site11 crop | `row=2400`, `col=2500` |
| `scripts/setup_caches.py` sabitleri | `row=1500`, `col=1000` |
| `backend/test_terrain_real_grid.py` | `row=1500`, `col=1000` |
| Frontend kayıtlı fixture açıklaması | `row=1500`, `col=1000` |

`setup_caches.py` kendi açıklamasında processed gridleri yeniden yazdığını açıkça söylüyor. Bu yüzden kullanıcı `python scripts/setup_caches.py` çalıştırdığında mevcut görünen de Gerlache sahası başka bir pencereye dönüşebilir; texture, kaya seed'leri, rota fixture'ları ve coğrafi etiketler birbirinden kopabilir. SDEM geçişinden önce:

1. Kanonik ROI manifesti tek dosyada tanımlanmalı (`bounds`, projected CRS, row/col yalnız türetilmiş bilgi).
2. `setup_caches.py`, testler, frontend fixture'ları ve texture provenance bu manifestten beslenmeli.
3. Cache dosyaları `source_dem_sha256 + bounds + resolution + pipeline_version` anahtarıyla doğrulanmalı; uyuşmazlıkta backend başlamayı reddetmeli veya açık uyarı vermeli.
4. Bu raporun değerlendirdiği ve kullanıcının şu anda gördüğü saha korunacaksa kanonik seçim `2400/2500` olmalıdır.

Bu, görsel bir ayrıntı değildir; düzeltilmeden yapılan DEM göçü “başarılı” görünüp yanlış coğrafyada planlama yapabilir.

1. Zenodo bölge #9 arşivini indir ve checksum doğrula.
2. SDEM GeoTIFF'ini mevcut **projeksiyon koordinatı sınırlarıyla** kırp; eski `row_offset/col_offset` değerlerini yeni rastera kopyalama.
3. Çıktıyı tam `500 × 500 @ 5 m` gridine hizala; piksel merkezleri/origin için regresyon testi yaz.
4. Maksimum-aydınlatmalı ortomozaiği aynı bounds ile kırp. Bunu doğrudan “saf albedo” diye etiketleme; önce veri açıklaması ve kalan gölge etkisini doğrula.
5. `elevation_grid`, slope, aspect, traversability, horizon, illumination, termal, cost, roughness ve DEM belirsizlik önbelleklerini yeni veri kimliğiyle yeniden üret.
6. Eski/yeni DEM farkı için min/median/p95/max yükseklik farkı, slope farkı, geçilebilir hücre değişimi ve iki sabit rotanın değişimini raporla.
7. Metadata'ya `source_product`, DOI, bölge adı, SHA-256, crop bounds, resampling yöntemi ve `effective_resolution`/coverage referanslarını ekle.

**Kritik risk:** SfS özellikle aydınlatılmış alanlarda güçlenir; kalıcı veya derin gölgede ayrıntı kazanımı aynı değildir. `best_input_resolution`, `coverage` ve solar-bin haritaları UI'da güven katmanı olarak saklanmalıdır. SfS detayı “her piksel eşit güvenilir” diye sunulmamalıdır.

### 4.5 Diğer NASA veri seçenekleri

| Kaynak | Uygun kullanım | Bu proje için hüküm |
|---|---|---|
| [PGDA #78](https://pgda.gsfc.nasa.gov/products/78) | 5 m LOLA referansı, hata/klon ürünleri | Mevcut taban; belirsizlik için değerli, görsel geometri için daha yumuşak |
| [PGDA #104](https://pgda.gsfc.nasa.gov/products/104) | SfS ile güçlendirilmiş yerel topoğrafya ve ortomozaik | **Site11 için birinci tercih** |
| [PGDA #90](https://pgda.gsfc.nasa.gov/products/90) | Büyük alan DEM, effective resolution, slope/roughness, PSR | Bölgesel bağlam ve doğrulama; yakın FPS geometrisi için fazla kaba |
| [LROC de Gerlache Rim kontrollü mozaik](https://data.lroc.im-ldi.com/lroc/view_rdr/NAC_ROI_DEGERRIMLO1) | Site11'i kapsayan 1 m/px, 16-bit kontrollü NAC mozaik | **Makro görüntü için en yüksek çözünürlüklü hazır aday**; albedo değil, düşük güneşli görüntü |
| [LROC NAC işleme kılavuzu](https://www.lroc.asu.edu/data/support/downloads/LROC_NAC_Processing_Guide.pdf) | ~1 m/px görüntü, kontrollü mozaik ve fotometrik düzeltme | Gölgeleri albedodan ayırmak için `lronacpho`/yüksek incidence için `photomet` değerlendirilmelidir |
| [USGS LROC NAC güney kutbu 4 m DEM](https://astrogeology.usgs.gov/search/map/moon_lro_south_pole_dem) | Eski stereo tabanlı 4 m DEM | Site11'e uygun değil: ürün en güneyde yaklaşık `-88,564°`, sahamız `-88,972 … -88,869°` |
| [ShadowCam](https://techport.nasa.gov/projects/96950) | PSR içinde yaklaşık 1,7 m/px görüntü | PSR görünümü/kaya analizi için gelecek aday; hazır, geodezik olarak uyumlu Site11 DEM'i değildir |
| [NASA CGI Moon Kit](https://svs.gsfc.nasa.gov/4720/) | Küresel Ay görünümü için 4K/8K/16K renk ve global displacement | Küre görünümünü iyileştirir; 2,5 km yerel sahayı keskinleştirmez |

NASA CGI Moon Kit'in 2025 renk haritası 4K, 8K ve 16K sürümlere sahip; ancak NASA sayfası bunun estetik için optimize edildiğini, bilimsel kullanımda kaynak veriye dönülmesi gerektiğini açıkça söyler. Global displacement en yüksek 64 pixel/degree'dir ve yerel 5 m sahadan çok daha kabadır. Bu veri yalnız küresel Ay görünümünde kullanılmalıdır. [NASA SVS CGI Moon Kit](https://svs.gsfc.nasa.gov/4720/)

LROC'nin de Gerlache kontrollü mozaiği tam saha kapsamı açısından özellikle güçlüdür: `-89,02 … -87,79°` enlem ve `-83,18 … -41,31°` boylam, 1 m/px, 144 NAC görüntüsü/656 segment, 5–20 m tahmini mutlak konum doğruluğu. Hazır 1 m GeoTIFF yaklaşık 731,67 MB; 5 m sürümü 84,18 MB'dir. 2,5 km pencereyi sunucu tarafında kırpmak, 731 MB dosyayı tarayıcıya göndermekten çok daha doğrudur. [LROC ürün sayfası](https://data.lroc.im-ldi.com/lroc/view_rdr/NAC_ROI_DEGERRIMLO1_P885S2933)

#### Kontrollü mozaiğin doğrudan Site11 crop ölçümü

Pyramidal LROC GeoTIFF'in tamamını indirmeden HTTP Range ile `X=-32.500…-30.000`, `Y=8.500…11.000 m` penceresi okundu. Dosya `29.500 × 26.000`, 1 m/px ve 256×256 tiled `uint8`; Site11 crop'u tam `2.500 × 2.500` pikseldir. [LROC 1 m pyramidal GeoTIFF](https://pds.mcp.nasa.gov/data/store/img/lunar_reconnaissance_orbiter/pds4/lroc/lro-l-lroc-5-rdr/LROLRC_2001/EXTRAS/BROWSE/NAC_ROI/DEGERRIMLO1/NAC_ROI_DEGERRIMLO1_P885S2933.PYR.TIF)

| Ölçüm | Mevcut `NAC_POLE` crop | Kontrollü de Gerlache crop | Yorum |
|---|---:|---:|---|
| `DN < 20` derin gölge | ~%52 | **%25,904** | Kullanılabilir fotoğraf sinyali belirgin biçimde artıyor |
| 2048'e eşitlenmiş robust-normalized gradient mean | 0,02686 | **0,04023** | Kontrollü ürünün ham foto katmanında daha çok yüksek-frekans kenar var |
| Aynı ölçekte Laplacian mean | 0,05955 | **0,07932** | Keskinlik heuristic'i kontrollü ürün lehine |
| 512 px high-pass phase correlation | referans | shift `[+1,-1]` px, korelasyon `0,607` | Yaklaşık `+4,9/-4,9 m`, bileşik ~`6,9 m` yerel offset işareti |

Gradient/Laplacian sayıları bilimsel çözünürlük kanıtı değil; farklı mozaikleme, dinamik aralık ve JPEG de sonucu etkiler. Ayrıca mevcut `nac-site11-detail-2048.jpg` lokal normalizasyon nedeniyle daha yüksek edge skoru üretir, fakat saf albedo değildir. Buna rağmen iki doğrudan sonuç güçlüdür:

1. Kontrollü mozaik mevcut foto modundaki gölge boşluğunu yaklaşık yarıya indiriyor.
2. Orientation aynı görünse de ölçülen birkaç metrelik offset, ürünün **coregistration yapılmadan değiştirilmemesi** gerektiğini doğruluyor.

Önerilen seçim süreci: kontrollü crop'u önce SDEM hillshade'e sub-pixel/feature tabanlı kaydet, seam ve gölge maskesini incele, sonra `photo` modu için değiştir. `scientific material` için hâlâ fotometrik normalizasyon gerekir; daha aydınlık mozaik otomatik olarak albedo değildir. Son aday karşılaştırmasında PGDA `GLDOMOS` aynı metriklerle ölçülmelidir.

---

## 5. Yüksek kaliteli yüzey texture/PBR araştırması

### 5.1 Bilimsel makro doku

Mevcut LROC NAC texture doğru sahaya ait olduğundan kaldırılmamalıdır. Daha doğru yaklaşım:

- **Makro fotoğraf:** LROC'nin 1 m de Gerlache kontrollü mozaiği veya PGDA #104 maksimum-aydınlatmalı ortomozaik.
- **Makro albedo adayı:** fotometrik olarak normalize edilmiş LROC NAC; doğrulama yapılmadan “gerçek albedo” etiketi verilmemeli.
- **Makro normal:** SDEM'den türetilmiş, 5 m ölçekli world-space normal.
- **Canlı aydınlatma:** SPICE güneş vektörü + horizon visibility + lunar BRDF.
- **Foto modu:** çekim anının gerçek görüntüsü, üzerindeki gölgeleriyle ayrı mod olarak kalabilir.

LROC işleme kılavuzu, farklı aydınlatma ve görüş açılarını normalize etmek için `lronacpho` uygulamasını önerir; 2019 ampirik model `μ0/(μ+μ0)` çarpanını ve phase/incidence/emission terimlerini kullanır. Kılavuz, `>60°` incidence görüntülerinde `photomet` yönteminin daha iyi sonuç verebildiğini de belirtir. de Gerlache mozaiğinin örnek görüntüleri yaklaşık `88–91°` incidence taşıdığı için bu ayrım Site11 için teorik değil, doğrudan önemlidir. [LROC NAC Processing Guide](https://www.lroc.asu.edu/data/support/downloads/LROC_NAC_Processing_Guide.pdf)

PGDA #104 `GLDOMOS` her pikselde en parlak geçerli girdiyi seçen, birden çok güneş azimutunu birleştiren **maksimum-aydınlatmalı ortomozaiktir**. Dolayısıyla görsel olarak çok ayrıntılı olsa da fiziksel, gölgesiz bir albedo haritası değildir. Üzerine canlı güneş ve shadow map uygulanırsa “baked light + live light” çift gölgelendirmesi oluşabilir. Önerilen mod ayrımı:

- `photo`: kontrollü/mozaik görüntü + çok sınırlı ek ışık;
- `scientific material`: düşük frekanslı normalize reflectance + SDEM normal + canlı güneş/ufuk gölgesi;
- `presentation`: scientific material + açıkça sentetik yakın PBR mikro-normal/roughness.

### 5.2 Görsel mikro PBR setleri

Poly Haven 2025'te laboratuvarda çekilmiş, CC0 lisanslı Ay regolit setleri yayımladı. Bunlar diffuse, displacement, OpenGL/DX normal, roughness ve AO kanalları içerir:

| Varlık | Fiziksel alan / çözünürlük | Kullanım önerisi |
|---|---|---|
| [Moon Flat Macro 02](https://polyhaven.com/a/moon_flat_macro_02) | 0,4 m; 11K | Genel yakın alan için en nötr taban; ilk tercih |
| [Moon Macro 01](https://polyhaven.com/a/moon_macro_01) | 0,4 m; 16K | Daha iri/düzensiz regolit varyantı |
| [Moon Dusted 05](https://polyhaven.com/a/moon_dusted_05) | 0,5 m; 16K | Tozlu ve daha oyuklu yakın alan varyantı |
| [Moon Meteor 02](https://polyhaven.com/a/moon_meteor_02) | 3,2 m; 16K | Seyrek yerel krater decal/patch; tüm sahaya tekrar etme |
| [Moon Rock 02](https://polyhaven.com/a/moon_rock_02) | 0,3 m; 6K tris, LOD'lar | Küçük kaya çeşitliliği |
| [Moon Rock 07](https://polyhaven.com/a/moon_rock_07) | 0,1 m; 13K tris, LOD'lar | Yakın plan, pütürlü küçük taş |

Bu setler **gerçek Ay lokasyonu ölçümü değildir**; Spaceport Rostock laboratuvarında oluşturulmuş görsel malzemedir. Siteye ait makro krater/albedo yerine geçmemeli; yalnız 0–100/150 m yakın alanda, düşük genlikli ve yönsüz mikro-detay olarak karıştırılmalıdır.

#### Hangi dosyalar gerçekten indirilmeli?

Poly Haven API doğrulamasında dört terrain adayının hepsinde `Diffuse`, `Displacement`, `nor_gl`, `nor_dx`, `Rough`, `AO` ve packed `arm` kanalları bulunuyor. Three.js için **OpenGL normal (`nor_gl`)** seçilmeli; DirectX normalin Y yönü ters olduğundan yanlış seçim çukur/tümsek algısını çevirebilir. [Poly Haven API](https://polyhaven.com/our-api)

İlk A/B denemesi için tüm ZIP veya 16K set gerekli değildir:

| Dosya | 2K kaynak indirme | 4K kaynak indirme | İlk spike kararı |
|---|---:|---:|---|
| `Moon Flat Macro 02 nor_gl` JPG | ~1,87 MiB | ~9,18 MiB | **2K ile başla**, sonra KTX2 normal profiline dönüştür |
| `Moon Flat Macro 02 Rough` JPG | ~1,60 MiB | ~7,17 MiB | 2K yeterli başlangıç; `NoColorSpace` |
| Diffuse | ~2,28 MiB | ~10,55 MiB | Site11 makro renginin yerine kullanma; çok düşük yakın-detail katkısı opsiyonel |
| Displacement | ~0,24 MiB JPG | ~0,90 MiB JPG | İlk fazda alma; dense near tile oluşmadan geometriyi keskinleştirmez |

Bu değerler sıkıştırılmış **ağ dosyası** boyutlarıdır, GPU belleği değildir. API'nin sağladığı MD5 değerleri asset manifestine kaydedilmeli; build sırasında KTX2 üretimi aynı kaynak kimliğinden tekrarlanabilmelidir.

Fiziksel tekrar ölçeği ayrıca önemlidir: `Moon Flat Macro 02` yalnız `0,4 m` genişliğindedir. Bunu tüm `2.500 m` sahaya gerçek ölçeğinde döşemek bir eksende `6.250` tekrar demektir. Bu yüzden bütün terrain materyalinde sürekli örneklemek yerine:

- kamera/rover çevresindeki near tile'da world-space metre koordinatıyla örnekle;
- `Moon Meteor 02` gibi `3,2 m` orta ölçekli normal ile `0,4 m` ince normali iki ayrı frekansta karıştır;
- iki örneği farklı rotasyon/offset ile **reoriented normal mapping** mantığında birleştir; normal vektörlerini yalnız toplama;
- makro LROC/SDEM kimliğini korumak için sentetik diffuse katkısını düşük, normal/roughness katkısını baskın tut;
- fiziksel ölçek görsel amaçla değiştirilirse manifestte `SYNTHETIC_SCALE` olarak yaz.

2K kaynak, 0,4 m alanda yaklaşık `0,195 mm/texel` örnek yoğunluğudur; rover seviyesindeki tipik kamerada zaten oldukça yüksektir. 4K kararı yalnız 20–50 cm kamera mesafesinde gerçek fark gösteren sabit ekran görüntüsü ve GPU ölçümüyle verilmelidir.

### 5.3 Önerilen çok ölçekli shader

```text
RENK = LROC/PGDA makro albedo
NORMAL = normalize(
  SDEM makro normal
  + nearFade * PBR mikro normal
  + veryNearFade * seyrek detail-normal/decal
)
ROUGHNESS = 0.90–1.00 aralığında PBR roughness varyasyonu
GÖLGE = backend horizon visibility × yerel kaya/rover shadow map
BRDF = Lunar-Lambert başlangıç, kalibre edilmiş Hapke ileri seçenek
```

Önerilen mesafe bantları bir başlangıç tahminidir:

- `0–50 m`: 2K/4K mikro normal + roughness tam etki
- `50–150 m`: yumuşak fade-out
- `150 m+`: yalnız SDEM makro normal/albedo

Bu bantlar FPS ekran görüntüsü ve GPU profiliyle ayarlanmalıdır. Geçiş için smoothstep ve iki farklı dönüş/ölçekli örnek kullanmak tekrar desenini azaltır. Mikro **albedo** etkisi çok düşük tutulmalı; aksi halde gerçek LROC coğrafi kimliği kaybolur.

### 5.4 Displacement ne zaman kullanılmalı?

Three.js `displacementMap` gerçek vertexleri hareket ettirir; gölge ve silüeti etkiler. Ancak mevcut 5 m vertex aralığında 40 cm'lik texture displacement örneklenemez. Çözüm:

- Tüm 2,5 km mesh'i sub-metre tessellate etme.
- Rover/kamera çevresinde 50–100 m'lik daha yoğun bir **near-field tile** üret.
- Makro yüksekliği SDEM'den, mikro yüksekliği düşük genlikli PBR haritasından al.
- Yakın tile sınırını orta LOD ile skirts/morphing kullanarak birleştir.
- Bilimsel modda mikro displacement yalnız görsel olsun. Fizik ve LiDAR'a girerse metadata'da `SYNTHETIC` olarak işaretlensin.

### 5.5 Doku çözünürlüğü ve GPU belleği

Three.js kılavuzu sıkıştırılmamış GPU bellek maliyeti için yaklaşık `width × height × 4 × 1.33` formülünü verir. Buna göre tek RGBA+mipmap texture yaklaşık:

| Boyut | Yaklaşık GPU belleği |
|---:|---:|
| 2K | 22 MB |
| 4K | 89 MB |
| 8K | 357 MB |
| 16K | 1,43 GB |

Dört ayrı 8K PBR haritası pratik değildir. JPG dosyasının diskte küçük olması GPU'da küçük olduğu anlamına gelmez. [Three.js texture memory guide](https://threejs.org/manual/en/textures.html)

Site11 makro görüntüsü için özel karar daha nettir:

| Boyut | 2,5 km sahada yer örnek aralığı | RGBA+mipmap yaklaşık GPU belleği | Bilgi durumu |
|---:|---:|---:|---|
| 2048 | 1,221 m/texel | 22,3 MB | Mevcut; 1 m kaynaktan yaklaşık %18 doğrusal ayrıntı kaybı |
| **2500** | **1,000 m/texel** | **33,3 MB** | Kaynağın gerçek örneklemesini korur; önerilen High/Balanced A/B adayı |
| 4096 | 0,610 m/texel | 89,3 MB | 1 m kaynaktan yeni bilgi yaratmaz; yalnız upsample |

Three.js'in mevcut `WebGLRenderer`ı WebGL2 kullanır; 2500 gibi NPOT boyutu sırf eski WebGL1 kısıtları nedeniyle 2048'e zorlamak gerekmez. [Three.js WebGLRenderer](https://threejs.org/docs/pages/WebGLRenderer.html) Kontrollü crop'un boyutu ayrıca 2500 ve block-compression için 4'ün katıdır. Bu nedenle makro foto için native `2500×2500` türev üretmek, “yüksek kalite” preset'inde 4096 kullanmaktan hem daha doğru hem daha ucuzdur. Düşük preset için 1024/2048 türev saklanabilir.

Bu nedenle:

- yakın alan için çoğunlukla **2K veya 4K** yeterlidir;
- albedo/normal/roughness setlerini **KTX2/Basis Universal** olarak hazırla;
- mipmap üret;
- normal/displacement/roughness texture'larını `NoColorSpace`, albedo'yu `SRGBColorSpace` yap;
- texture yüklenmeden önce cihazın `maxTextureSize` ve `getMaxAnisotropy()` değerini oku;
- hard-coded `16` yerine `Math.min(16, renderer.capabilities.getMaxAnisotropy())` kullan.

KTX2Loader, Basis Universal dokuları GPU'nun desteklediği sıkıştırılmış formata transcode eder. [Three.js KTX2Loader](https://threejs.org/docs/pages/KTX2Loader.html) KTX 2.0 ayrıca mip düzeylerini küçükten büyüğe aktarmaya uygun bir kapsayıcıdır. [Khronos KTX 2.0 specification](https://registry.khronos.org/KTX/specs/2.0/ktxspec.v2.html)

KTX2 profilini kanal tipine göre seç:

| İçerik | Başlangıç codec'i | Color space | Neden |
|---|---|---|---|
| LROC/PGDA görsel foto | ETC1S ve UASTC A/B; bant genişliği önceliğinde ETC1S | sRGB | Gri makro görüntüde ETC1S küçük olabilir; krater/gölge kenarında blok artefaktı ölçülmeli |
| Mikro normal | **UASTC + Zstd** | Linear / `NoColorSpace` | Normal ve diğer non-color map'lerde yüksek kalite gerekir |
| Roughness/packed ARM | UASTC ilk aday | Linear / `NoColorSpace` | Kanallar birbiriyle ilişkili renk değildir; ETC1S artefaktı yüzey parlaklığını oynatabilir |
| Bilimsel DEM/uncertainty | Lossy Basis kullanma | Sayısal veri | Yükseklik ve belirsizlik görsel texture değil, doğruluk korunması gereken grid'dir |

Khronos kılavuzu yüksek kaliteli normal/non-color veride UASTC'yi, destek varsa ASTC 4×4 veya BC7 transcode hedefini önerir; normal map RDO için `0,25–0,75` aralığını deneme bandı olarak verir. Bunlar son ayar değil, SSIM/normal-angle hata ve hedef GPU boyutuyla seçilecek encoder başlangıçlarıdır. [Khronos KTX Developer Guide](https://github.com/KhronosGroup/3D-Formats-Guidelines/blob/main/KTXDeveloperGuide.md) [Khronos `toktx` artist guide](https://github.com/KhronosGroup/3D-Formats-Guidelines/blob/main/subpages/KTXArtistGuide_toktx.md)

---

## 6. Three.js'te kullanılmayan ama işe yarayacak özellikler

### 6.1 Özellik matrisi

| Özellik/kütüphane | Mevcut kullanım | Ne kazandırır | Öncelik / not |
|---|---|---|---|
| `normalMap` + `roughnessMap` | Yok | Vertex eklemeden yakın alan ışık ayrıntısı | **Çok yüksek** |
| `displacementMap` | Yok | Yakın tile'da gerçek silüet/gölge | Yüksek; yoğun geometri şart |
| WebGL shadow maps | Yok | Kaya/rover temas gölgesi | **Çok yüksek**; yakın alanla sınırla |
| `CSM` | Yok | Orbit–FPS arasında uzun menzilli yönlü gölge | Orta; 3 cascade varsayılanı maliyetlidir |
| `KTX2Loader` | Yok | 4K PBR setinin indirme/GPU maliyetini azaltır | **Yüksek** |
| `THREE.LOD` | Yok | Kaya model seviyelerini mesafeyle değiştirir | Orta-yüksek |
| `BatchedMesh` | Yok | Farklı kaya geometrilerini aynı materyalle daha az draw call'da gösterir | **Yüksek** kaya sayısı büyürse |
| `InstancedMesh` | Çakılda var | Aynı geometriyi çok sayıda çizer | Koru; büyük kayalarda genişletilebilir |
| `GTAOPass` | Yok | Temas/oyuk algısını artırır | Düşük dozda, yalnız presentation modu |
| `SMAAPass`/TAA | Yok | Kenar kırılmalarını azaltır | Orta; önce mevcut MSAA'yı ölç |
| TSL/NodeMaterial | Yok | Lunar BRDF, ölçek karışımı ve WebGPU'ya taşınabilir shader | Orta-yüksek; shader büyüdükçe değerlendir |
| DRACO/Meshopt/KTX2 glTF | Yok | Rover/kaya GLB indirme ve GPU veri maliyetini azaltır | Orta |
| `three-mesh-bvh` | Yok | Büyük mesh üzerinde hızlı raycast/spatial query | Şimdilik düşük; özel heightfield picker zaten verimli |
| `3d-tiles-renderer` | Yok | Küresel/çok bölgeli streaming LOD | Gelecek; tek 2,5 km saha için fazla |
| Dinamik camera near/far veya `reversedDepthBuffer` | Yok; kamera `0.1…100000 m` | Terrain overlay/marker z-fighting'ini azaltır | Orta-yüksek; küre↔FPS geçişinde ölç |

### 6.2 En büyük görsel boşluk: yerel gölge

Three.js'te shadow maps varsayılan olarak kapalıdır. Mevcut kod da bilinçli olarak büyük ölçekli gölgeyi backend horizon cube'dan alıyor; fakat bu sistem kayaların ve rover gövdesinin yakın zemine düşürdüğü gölgeyi üretmiyor. [Three.js WebGLRenderer shadow map özellikleri](https://threejs.org/docs/pages/WebGLRenderer.html)

Önerilen hibrit:

- **Uzak/topografik gölge:** mevcut SPICE + horizon maskesi; bilimsel kaynak olmaya devam eder.
- **Yakın nesne gölgesi:** rover merkezli 100–200 m ortografik directional shadow camera; yalnız rover ve yakın kayalar `castShadow`, terrain near tile `receiveShadow`.
- Kamera hızlı hareket etmiyorsa shadow map'i her frame değil, güneş/kamera/rover anlamlı değiştiğinde güncelle.
- Orbit geniş görünümünde CSM kalite preset'i opsiyonel olabilir. Three.js CSM modülü varsayılan üç cascade ve 2048 shadow map sunar; bunun GPU maliyeti ölçülmelidir. [Three.js CSM](https://threejs.org/docs/pages/CSM.html)

Bu yöntem backend gölgesini kaldırmaz; iki farklı ölçeğin fiziksel etkisini çarpar.

Başlangıç shadow bütçesi için rover merkezli `200 m` genişlikte 2048 harita nominal olarak yaklaşık `9,8 cm/texel`, `100 m` genişlikte yaklaşık `4,9 cm/texel` verir. Bu, metre-altı kaya/teker temasını okumak için 4096'ya körlemesine çıkmaktan daha dengelidir. 4096 çözünürlük piksel sayısını ve ham depth depolamasını dört katına çıkarır.

Uygulama ayrıntıları:

- `renderer.shadowMap.enabled = true`; ilk denemede `PCFSoftShadowMap` ve düşük `radius` kullan. Havasız yüzeyde geniş, sisli Dünya tipi gölge yumuşaması doğru görünmez.
- Ortografik shadow camera'nın left/right/top/bottom alanını yalnız near tile'a sar; bütün 2,5 km'yi tek haritaya koyma.
- Güneş çok alçak olduğu için acne düzeltmesinde önce küçük `normalBias` A/B testi yap; yüksek değer gölgeyi kayadan ayırır. Three.js de `normalBias`ın sığ ışık açılı büyük sahnelerde yararlı, fakat gölgeyi bozabileceğini belirtir.
- `sun.shadow.autoUpdate = false` yapıp rover/camera tile değiştirince veya Güneş yönü eşik aşınca `needsUpdate = true` kullan. Böylece statik kayalar için ikinci render pass her frame zorunlu olmaz.
- Gölge atlasını debug görünümünde göster; peter-panning, acne ve frustum dışı kesilmeyi üç sabit güneş açısında kabul testi yap.

[Three.js LightShadow](https://threejs.org/docs/pages/LightShadow.html)

### 6.3 Ay'a özgü BRDF

Mevcut `MeshStandardMaterial` taş/regolit için doğru PBR tabanıdır; `metalness=0`, yüksek roughness mantıklıdır. `MeshPhysicalMaterial`ın clearcoat, transmission, sheen ve iridescence özellikleri regolit için çözüm değildir ve piksel başına daha pahalıdır. [Three.js MeshPhysicalMaterial](https://threejs.org/docs/pages/MeshPhysicalMaterial.html)

Asıl ihtiyaç custom BRDF'dir. USGS ISIS dokümanı Lunar-Lambert modelini Lambert ve Lommel-Seeliger karışımı olarak tanımlar:

```text
F = (1 - L) * μ0 + 2L * μ0 / (μ0 + μ)
μ0 = cos(incidence), μ = cos(emission)
```

[USGS ISIS photomet](https://isis.astrogeology.usgs.gov/8.2.0/Application/presentation/PrinterFriendly/photomet/photomet.html)

Burada iki ayrı problemi birbirine karıştırmamak gerekir:

- **NAC texture ön işleme:** Görüntünün çekildiği andaki incidence/emission/phase etkisini azaltıp ortak referans geometriye normalize etmek.
- **Gerçek zamanlı ileri render:** Normalize edilmiş taban yansıtırlığını, seçilen görev zamanının Güneş ve kamera geometrisiyle yeniden aydınlatmak.

USGS ISIS'in güncel `lronacpho` dokümanındaki 2019 LROC ampirik fotometri fonksiyonu şudur:

```text
F(μ, μ0, α) = μ0 / (μ + μ0) × exp(
  B0 + B1 α² + B2 α + B3 √α + B4 μ + B5 μ0 + B6 μ0²
)

μ0 = cos(incidence), μ = cos(emission), α = phase
```

Dokümanda verilen broadband örnek katsayıları `B0=-1.479654495`, `B1=-0.000083528`, `B2=0.012964707`, `B3=-0.237774774`, `B4=0.556075496`, `B5=0.663671460`, `B6=-0.439918609` değerleridir. Çıktı pikseli `input × F(reference angles) / F(pixel angles)` şeklinde normalize edilir. ISIS ayrıca fonksiyonun **15–65° phase** aralığında geçerli olduğunu, `USEDEM=true` seçilirse fotometrik açıların yüzey pürüzlülüğünü hesaba katan DEM üzerinden hesaplanabildiğini belirtir. [USGS ISIS lronacpho](https://isis.astrogeology.usgs.gov/8.3.0/Application/presentation/Tabbed/lronacpho/lronacpho.html) [Resmî ISIS uygulaması](https://github.com/DOI-USGS/ISIS3/blob/dev/isis/src/lro/apps/lronacpho/LROCEmpirical.cpp)

Bu katsayılar doğrudan Three.js shaderına yapıştırılacak evrensel bir Ay materyali değildir: `lronacpho` bir **görüntü normalizasyon modeli**, Three.js tarafında gereken ise ileri yönlü bir BRDF'dir. Katsayılar kullanılan bant, açı birimi, kalibrasyon dosyası ve geçerlilik aralığıyla birlikte ele alınmalıdır. En güvenli uygulama, NAC ürününü ISIS'te normalize etmek; shaderı ise Lunar-Lambert ile başlatıp aynı kamera/Güneş geometrisindeki LROC referanslarına karşı test etmektir. Böylece mevcut fotoğraf gölgesinin canlı directional light ile ikinci kez aydınlatıldığı “double-lighting” etkisi azaltılır.

NASA'nın VIPER Rover Simulation sunumu, lunar regolitin opposition effect gösterdiğini ve görsel simülatörün Hapke BRDF kullandığını belirtir. [NASA NTRS — VIPER Rover Simulation / Visual Simulation](https://ntrs.nasa.gov/api/citations/20210010712/downloads/VIPER%20RSIM%20VRT.pdf?attachment=true)

Önerilen sıra:

1. `onBeforeCompile` ile basit ve test edilebilir Lunar-Lambert diffuse uygula.
2. LROC referans görüntüsüyle parlaklık/phase davranışını kalibre et.
3. Yalnız ihtiyaç kalırsa Hapke parametreleri ve opposition surge ekle.
4. Shader karmaşıklığı büyürse TSL'ye taşı. TSL hem GLSL/WebGL hem WGSL/WebGPU hedeflerine kod üretebilir ve `positionNode` ile özel displacement yolunu destekler. [Three.js TSL specification](https://threejs.org/docs/TSL.html)

`DirectionalLight.intensity = 3.6` ile genel parlaklığı artırmak geçici kompanzasyondur; görüş açısına bağlı yansıtmayı yeniden üretmez.

### 6.4 GTAO kullanılsın mı?

`GTAOPass`, Three.js dokümantasyonuna göre SSAO'dan daha kaliteli ama daha pahalıdır. [Three.js GTAOPass](https://threejs.org/docs/pages/GTAOPass.html) Çok düşük yoğunlukta kaya-zemin teması ve küçük oyukları okunur kılabilir. Ancak AO:

- gerçek zamanlı güneş görünürlüğü değildir;
- gölgeli bölgelerde sahte dolgu/kontrast yaratabilir;
- slope/cost/thermal gibi veri katmanlarına uygulanmamalıdır.

Bu yüzden yalnız `presentation/cinematic` kalite preset'inde ve toggle ile kullanılmalıdır.

### 6.5 LOD, batching ve büyük sahne

- `THREE.LOD`, mesafeye göre üç farklı mesh seviyesi seçebilir. [Three.js LOD](https://threejs.org/docs/pages/LOD.html)
- `BatchedMesh`, aynı materyali paylaşan fakat farklı geometrileri olan nesnelerde draw call sayısını azaltır; mevcut farklı kaya şekilleri için `InstancedMesh`ten daha esnektir. [Three.js BatchedMesh](https://threejs.org/docs/pages/BatchedMesh.html)
- `SceneOptimizer` otomatik batching için deneysel olarak işaretlidir; üretim yoluna körlemesine alınmamalı, ölçümlü bir araç olarak denenmelidir. [Three.js SceneOptimizer](https://threejs.org/docs/pages/SceneOptimizer.html)
- `three-mesh-bvh`, triangle mesh raycast ve spatial query'leri hızlandırır; fakat mevcut arazi tıklaması özel heightfield kesişimi kullandığı için bugün zorunlu değildir. Karmaşık tiled mesh, rock picking veya CPU collision sorguları artarsa değerlidir. [three-mesh-bvh](https://github.com/gkjohnson/three-mesh-bvh)
- Küresel Ay ile çok sayıda yüksek detaylı bölge aynı sahnede stream edilecekse NASA-AMMOS/JPL'nin `3d-tiles-renderer` projesi Three.js, texture overlays, LOD fade, WMS/WMTS ve lunar Cesium örneği sunar. Tek mevcut saha için dönüştürme maliyeti gereksizdir; gelecekte küre → site geçişi büyürse değerlidir. [NASA-AMMOS 3DTilesRendererJS](https://github.com/NASA-AMMOS/3DTilesRendererJS)

#### Harici terrain kütüphaneleri için bakım ve uyum taraması

8 Eylül 2026 tarihli depo/NPM taraması şu kararı destekliyor:

| Kütüphane | Güçlü yanı | Bu projedeki uyumsuzluk / risk | Karar |
|---|---|---|---|
| [3d-tiles-renderer](https://github.com/NASA-AMMOS/3DTilesRendererJS) `0.5.2` | Aktif NASA-AMMOS projesi; quadtree streaming, LRU, geospatial eklentiler, lunar/globe örnekleri | Önce SDEM'i 3D Tiles pipeline'ına dönüştürmek gerekir | Birden çok saha/küre streaming'i başlayınca **en güçlü aday** |
| [three-mesh-bvh](https://github.com/gkjohnson/three-mesh-bvh) `0.9.14` | Aktif ve olgun; raycast, shapecast, BVH refit | Düzenli 500×500 gridin LOD/texture işini kendi başına çözmez | Kaya/mesh picking ve tiled collider sorgusu artınca ekle |
| [geo-three](https://github.com/tentone/geo-three) `0.1.15` | Planar/küresel tile ağacı, CPU/GPU height data, özel provider | Varsayılan koordinat/provider modeli Dünya Web Mercator ve web harita servislerine dönük; kutupta özel provider/projeksiyon gerekir | Mimari referans; doğrudan benimseme riski yüksek |
| [three.terrain.js](https://github.com/IceCreamYou/THREE.Terrain) `3.1.1` | Procedural noise, filtreleme, scatter ve blended material | Ölçülmüş Site11 yüzeyinin yerine procedural topoğrafya üretir; bilimsel provenance'ı bozar | Yalnız sentetik test patch'i/dağılım deneyi |
| [hello-terrain](https://github.com/kenjinp/hello-terrain) | Değişken LOD, TSL, texture painting ve elevation manipulation | Çok genç; WebGPU + React Three Fiber örnek yolu mevcut raw Three/WebGL mimarisinden büyük sapma | İzlenecek teknoloji; bugün production bağımlılığı yapma |
| [cdlod](https://github.com/nickyvanurk/cdlod) / [geo-clipmap](https://github.com/tschie/geo-clipmap) | CDLOD/geometry clipmap için okunabilir prototipler | İlki küçük deneysel repo, ikincisinin kod aktivitesi eski; ürün yaşam döngüsü/uyumluluk yükü bize kalır | Algoritma referansı, doğrudan dependency değil |

Three.js'in `SimplifyModifier` eklentisi otomatik LOD üretebilir, ancak çıktıyı non-indexed geometriye çevirir. Bu yüzden paylaşılan tile sınırlarını ve bilimsel grid örneklerini koruması gereken terrain için uygun ilk seçim değildir; kaya LOD üretiminde denenebilir. Terrain LOD'ları projected bounds'tan deterministik şekilde her 2ⁿ örneği alarak offline üretmek daha denetlenebilirdir. [Three.js SimplifyModifier](https://threejs.org/docs/pages/SimplifyModifier.html)

`DecalGeometry`, teker izi veya lokal görsel işaret eklemek için yararlıdır; köşelerde deformasyon yapabilir ve ürettiği iz fiziksel zemin deformasyonu değildir. SDEM ya da collider'ı değiştirmeden yalnız presentation katmanında kullanılmalıdır. [Three.js DecalGeometry](https://threejs.org/docs/pages/DecalGeometry.html)

Proje `three@0.183.2`, NPM'de araştırma gününde güncel sürüm `0.185.1` idi. Kalite artışı sürüm yükseltmesinden kendiliğinden gelmez; Three.js addon'ları çekirdek sürümle birlikte pinlenmeli ve renderer/shader golden testleri geçmeden yükseltilmemelidir.

#### Mevcut rover GLB bütçesinin doğrudan denetimi

GLB JSON/BIN chunk'ları dosyalardan okunarak yapılan denetim:

| Varlık | Dosya | Vertex | Triangle | Texture | Yapı / sıkıştırma |
|---|---:|---:|---:|---:|---|
| Textured VIPER | 10.062.376 byte | 70.051 | 119.604 | 3 embedded JPEG, toplam ~5,02 MiB | 5 node/mesh; dört wheel node ayrı; compression extension yok |
| Eski VIPER | 9.770.808 byte | 358.383 | 119.604 | Yok | Aynı triangle ama büyük ölçüde tekrarlı/non-indexed vertex; compression extension yok |
| Yutu | 21.686.960 byte | 202.251 | 343.078 | 3 embedded JPEG, toplam ~7,49 MiB | Tek node/mesh; wheel node yok; compression extension yok |

Üç dosyada da `extensionsUsed=[]`; yani `KHR_draco_mesh_compression`, `EXT_meshopt_compression` ve `KHR_texture_basisu` kullanılmıyor. Özellikle Yutu tek görünür rover için bile 343 bin triangle ve 21,7 MB olduğundan orbit görünümündeki küçük ekran alanına göre pahalıdır; ayrıca tek mesh olduğu için teker/süspansiyon fiziğine doğrudan uygun değildir.

Önerilen asset pipeline:

1. Kaynağı `gltf-transform inspect` ve `validate` ile CI'da doğrula.
2. VIPER'ın `wheel_fl/rl/fr/rr` node adlarını ve pivotlarını koruyan bir optimizasyon fixture'ı yaz.
3. `weld → reorder → meshopt` veya ölçümlü Draco varyantı üret; Three.js'te ilgili decoder'ı `GLTFLoader`a açıkça bağla.
4. Embedded JPEG'leri gerektiğinde KTX2'ye çevir; normal map varsa kalite için UASTC/ETC1S A/B testi yap.
5. Ayrı `near/mid/far` LOD dosyaları üret. Silüet, teker çapı ve sensör yerleri tolerans testinden geçmeden otomatik simplification kabul edilmesin.
6. Fizik collider'ını yüksek-poly görsel mesh'ten üretme; metre ölçülü basit convex/compound parçalardan ayrı tut.

glTF Transform; inspect/validate, weld, reorder, simplify, Meshopt/Draco ve KTX2 ETC1S/UASTC komutlarını aynı araç zincirinde sunar. Meshoptimizer da indexing → vertex-cache → isteğe bağlı overdraw → vertex-fetch → quantization sırasını önerir. [glTF Transform CLI](https://gltf-transform.dev/cli) [meshoptimizer](https://github.com/zeux/meshoptimizer) Three.js tarafında `GLTFLoader`, Draco/Meshopt/KTX2 entegrasyon noktalarını sağlar. [Three.js GLTFLoader](https://threejs.org/docs/pages/GLTFLoader.html)

### 6.6 WebGPU'ya şimdi geçilmeli mi?

Hayır. Mevcut darboğaz veri/BRDF/gölge/LOD'dur; renderer API'si değil. Önce WebGL2 yolunda hedef kalite ve frame budget ölçülmeli. TSL ile yeni shaderları taşınabilir yazmak, daha sonra WebGPU geçişini kolaylaştırır. Tam renderer göçü ilk fazın kapsamına alınmamalıdır.

### 6.7 Ölçek ve depth precision

Mevcut `PerspectiveCamera(45, 1, 0.1, 100000)` ayarı `far/near = 1.000.000` oranına sahiptir. Aynı kamerada santimetre-altı rover detayı, 2,5 km arazi ve uzaktaki gökyüzünü tutmak depth-buffer hassasiyetini gereksiz yere dağıtır; yüzeye çok yakın route/marker/grid katmanlarında z-fighting oluşabilir. Bu, texture “softluğu” değildir ama ölçeği büyüttükçe görsel kararlılığı bozar.

Öneri sırası:

1. FPS modunda near plane'i mümkün olduğunca yükselt (`0,1` yerine model/kamera davranışının izin verdiği `0,2–0,5 m`) ve far'ı yalnız yerel sahaya yetecek değere indir.
2. Orbit/küre görünümünde ayrı kamera clipping değerleri kullan; yıldız göğü depth yazmadan çizilebilir.
3. Hâlâ gerekirse ve `EXT_clip_control` varsa Three.js `reversedDepthBuffer` seçeneğini A/B test et. Doküman bunu `logarithmicDepthBuffer`a göre daha hızlı ve daha doğru seçenek olarak tanımlar; destek yoksa fallback gerekir. [Three.js WebGLRenderer](https://threejs.org/docs/pages/WebGLRenderer.html)
4. Overlay'lerde büyük keyfi Y offsetleri yerine polygon offset/depthTest politikası ve tek bir terrain height sampler kullan.

---

## 7. Rover fiziği araştırması

### 7.1 Mevcut fizik seviyesi

Şu an rover:

- backend rotasındaki konuma taşınıyor;
- DEM normaline göre eğiliyor;
- heading sınırlı oranda dönüyor;
- tekerlekler gidilen mesafeye göre görsel olarak dönüyor;
- gerçek temas, kütle, atalet, süspansiyon, motor kuvveti veya devrilme hesabı yapmıyor.

Bu, **kinematik rota oynatma**dır ve görev planının doğru görselleştirilmesi için gayet meşrudur. Fizik motoru eklemek mevcut planlamanın yerine geçmemeli.

### 7.2 Motor karşılaştırması

| Motor | Tarayıcı | Heightfield | Araç desteği | Deforme toprak | Bu proje için |
|---|---|---|---|---|---|
| **Rapier 3D** | WASM/JS | Evet | `DynamicRayCastVehicleController` | Hayır | **Birinci tercih** |
| cannon-es | Saf JS/TS | Evet | `RaycastVehicle` | Hayır | Daha basit alternatif |
| Three.js `RapierPhysics` addon | Evet | `addHeightfield` | Düşük seviyeli wrapper; doğrudan controller için Rapier gerekir | Hayır | Demo için iyi, üretimde fazla sınırlı/CDN bağımlı |
| JoltPhysics.js | WASM/asm.js; çok iş parçacıklı build var | Evet | `VehicleControllerSettings` | Hayır | Güçlü ikinci aday; C++ benzeri API ve daha ağır entegrasyon |
| PhysX WASM (`physx-js-webidl`) | WASM | Evet | PhysX Vehicles | Hayır | Kapsamlı ama topluluk binding'i; bu proje için gereğinden karmaşık |
| Ammo.js/Bullet | WASM/asm.js | Evet | Raycast vehicle | Soft body var, regolit yok | Three.js örnekleri var; proje aktifliği nedeniyle yeni seçim olarak zayıf |
| Project Chrono | Native C++/GPU; web için doğrudan değil | Rigid + heightmap | Gelişmiş vehicle/tire modelleri | SCM, granular DEM, FEA, CRM | Yüksek doğrulukta dış simülatör |

Three.js'in resmi Rapier addon'u `addHeightfield()` sağlar, ancak Rapier'ı CDN'den otomatik yükler ve aktif internet bağlantısı ister. [Three.js RapierPhysics](https://threejs.org/docs/pages/RapierPhysics.html) Projenin offline/dev güvenilirliği için doğrudan, versiyonu pinlenmiş `@dimforge/rapier3d` veya Vite/WASM sorunu çıkarsa `@dimforge/rapier3d-compat` daha kontrollüdür. Rapier ana build geniş tarayıcı desteği/performans, compat build ise daha büyük paket karşılığında WASM'i JS'e gömme seçeneği sunar. [Rapier TypeScript bindings](https://github.com/dimforge/rapier/tree/master/typescript)

Rapier'ın eski `rapier.js` deposu 12 Temmuz 2026'da arşivlenip ana `dimforge/rapier` deposunun `typescript` klasörüne taşındı; yeni entegrasyon eski depoya sabitlenmemelidir. [Rapier eski depo geçiş notu](https://github.com/dimforge/rapier.js)

8 Eylül 2026 NPM metadata kontrolünde `@dimforge/rapier3d` ve `@dimforge/rapier3d-compat` güncel sürümü `0.20.0`'dır. Projede görünen `0.12.0`, `@types/three` üzerinden gelen dolaylı bir development bağımlılığıdır; runtime özelliği sayılmamalı ve uygulama bu paketi doğrudan bağımlılık olarak, kilitli/test edilmiş sürümle eklemelidir. Jolt'ın `DOUBLE_PRECISION` build seçeneği birkaç kilometreden büyük dünyalar için yararlı olabilir; mevcut saha merkez etrafında yaklaşık ±1,25 km tutulduğu sürece origin-rebasing ve yerel metre koordinatı Rapier/f32 için daha basit çözümdür. [JoltPhysics.js](https://github.com/jrouwe/JoltPhysics.js)

### 7.3 Rapier ile önerilen tasarım

```text
SDEM Float32 heights
   ├── Three.js terrain mesh (render)
   ├── Rapier fixed heightfield collider (temas)
   └── backend grid (planlama/LiDAR; bilimsel temel)

Rover
   ├── compound/convex chassis collider
   ├── dynamic rigid body
   ├── raycast wheels + suspension
   └── rendered GLB, rigid-body pose'unu takip eder
```

Rapier heightfield'ları büyük basit araziler için triangle mesh'ten daha az bellek kullanır. Dinamik gövdelerde triangle mesh collider önerilmez; rover gövdesinde convex/compound collider kullanılmalıdır. Rapier'ın 3D heightfield API'si yüksekliği yerel Y ekseninde ve matrisi **column-major** sırada bekler. Mevcut `elevation_grid`/Three.js vertex sırası için açık transpose/eksen çevirimi ve köşe fixture testi zorunludur. [Rapier colliders](https://rapier.rs/docs/user_guides/javascript/colliders/) [Rapier Heightfield API](https://rapier.rs/javascript3d/classes/Heightfield.html)

Başlangıç parametreleri:

- gravity: `{x: 0, y: -1.625, z: 0}` m/s²
- fixed timestep: `1/60 s` veya ölçülmüş stabil alt-adım
- gerçek metre/kilogram/saniye birimleri
- rover profiline göre kütle ve center-of-mass
- her teker için yarıçap, suspension rest length/stiffness/damping, motor force, brake, steering ve friction-slip
- hızlı hareket/ince collider varsa CCD

Rapier raycast vehicle controller teker ekleme, engine force, steering, brake, suspension stiffness/compression/relaxation, max travel, friction slip ve temas sorguları sunar. [Rapier DynamicRayCastVehicleController](https://rapier.rs/javascript3d/classes/DynamicRayCastVehicleController.html) Three.js'in resmi [Rapier terrain](https://threejs.org/examples/physics_rapier_terrain.html) ve [vehicle controller](https://threejs.org/examples/physics_rapier_vehicle_controller.html) örnekleri entegrasyonun teknik olarak mümkün olduğunu doğrular.

#### Raycast otomobil modeli ile VIPER-benzeri rover modeli aynı şey değil

Repo kodu GLB içindeki dört tekeri ayırıyor fakat yalnız ön/arka sınıflaması yaparak ön tekerlere bisiklet/Ackermann yaklaşımından steering veriyor. NASA'nın VIPER mimarisi ise dört bağımsız wheel module, her köşede drive + steering + **aktif suspension**, 50 cm çap/20 cm genişlikte rijit grouser'lı teker ve yaklaşık 450 kg roving mass tarif eder; yana/çapraz sürüş ve yerinde dönüş de sistemin parçasıdır. [NASA VIPER mobility architecture](https://ntrs.nasa.gov/api/citations/20220000441/downloads/viper-mobility-2022-01-27.pdf) [NASA — VIPER rover and instruments](https://science.nasa.gov/mission/viper/rover-and-instruments/)

Bu nedenle doğruluk seviyeleri şöyle ayrılmalıdır:

| Seviye | Temsil | Ne kadar doğru? |
|---|---|---|
| Görsel sürüş sandbox'ı | Rapier `DynamicRayCastVehicleController`; dört ayrı teker parametresi | Süspansiyon hissi, eğim/temas ve çarpışma demosu için yeterli; teker gerçek bir rigid collider değildir |
| VIPER-benzeri mekanizma | Dört wheel-module gövdesi, revolute steering/drive ve suspension bağlantıları; ayrı motor limitleri | Aktif suspension/omnidirectional steering davranışına yaklaşır; GLB hierarchy ve kontrolcü yeniden modellenir |
| Terramekanik doğrulama | Chrono SCM/granular veya doğrulanmış harici model | Sinkage, grouser ve regolit slip iddiaları için gerekli |

Rapier revolute, prismatic, spherical ve generic joint'leri; ayrıca constraint ve reduced-coordinate multibody joint setlerini destekler. Bunlar ikinci seviye prototipi teknik olarak mümkün kılar. Ancak dört modüllü modelin parametreleri ve gerçek teker temas şekli doğrulanmadan raycast sonucu “VIPER fiziği” diye adlandırılmamalıdır. [Rapier joints](https://rapier.rs/docs/user_guides/javascript/joints/) NASA'nın yayımladığı gereksinimler arasında yaklaşık `15°` eğim, `15 cm` engel, `10 cm/s` nominal ve `20 cm/s` üst hız değerleri bulunur; bunlar iyi acceptance fixture'larıdır, varsayılan controller tuning sayıları değildir. [NASA VIPER mobility overview](https://ntrs.nasa.gov/api/citations/20240013903/downloads/LSIC_2024-Tech%20Infusion_Panel-VIPER_Mob-HW.pdf?attachment=true)

### 7.4 Yerel Rapier mikro-benchmark'ı

Mevcut kurulumdaki dolaylı `@dimforge/rapier3d-compat@0.12.0` ile, proje dosyası değiştirmeden Node 22 üzerinde şu sentetik test çalıştırıldı:

- `500 × 500 = 250.000` Float32 yükseklik örneği (`499 × 499` heightfield hücresi);
- Ay yerçekimi `-1,625 m/s²`;
- 50 dinamik kutu;
- çalışma başına 600 fizik adımı, 5 tekrar.

| Ölçüm | Sonuç |
|---|---:|
| Heightfield girdi dizisi | 0,954 MiB |
| Heightfield oluşturma | 1,025–1,802 ms |
| Fizik adımı medyanı | 0,107 ms/adım |
| Gözlenen aralık | 0,104–0,157 ms/adım |

Bu ölçüm **rover performans garantisi değildir**: eski motor sürümü, Node ortamı, sentetik düz araziye yakın yükseklikler ve basit kutular kullanır; render, raycast araç controller'ı, gölgeler ve tarayıcı ana thread yükü yoktur. Sonuç yalnız şunu destekler: mevcut 500×500 heightfield boyutu tek başına bariz bir engel değildir. Üretim kararı `0.20.x` ile gerçek rover collider/controller'ı, Chrome/Firefox ve hedef laptoplarda p50/p95 frame ölçümü sonrasında verilmelidir.

### 7.5 Planlama animasyonu ile fizik çatışmasın

İki ayrı mod önerilir:

1. **Mission playback — varsayılan:** Backend path authoritative; rover kinematik gider. Mevcut raporlar ve rota telemetrisi değişmez.
2. **Physics sandbox — opsiyonel:** Kullanıcı manuel sürer veya path-following controller fizik gövdesine kuvvet uygular. Devrilme, temas ve süspansiyon görselleşir; sonuç “simülasyon” olarak etiketlenir.

Üçüncü bir `physics-assisted playback` ancak controller'ın rotadan sapma sınırı ve reset davranışı tanımlandıktan sonra eklenmelidir. Aksi halde aynı ekranda backend'in “gidilen rota”sı ile fizik motorunun gerçek konumu ayrışır.

### 7.6 Rapier neyi çözmez?

Rapier temas sürtünmesi Coulomb modelidir ve dokümanında statik/dinamik sürtünmeyi ayırmadığını belirtir. [Rapier friction](https://rapier.rs/docs/user_guides/javascript/colliders/#friction) Bu nedenle aşağıdakiler doğrudan “gerçek” olmaz:

- regolite gömülme/sinkage;
- teker altında zemin deformasyonu ve iz;
- shear displacement ve bulldozing;
- eğim/nem/kompaksiyonla değişen gerçek slip;
- teker dişi ile granül temasının mühendislik doğruluğu.

Bunlar için görsel teker izi decal'i yapılabilir; fakat fizik kanıtı olarak sunulmamalıdır.

### 7.7 Daha yüksek doğruluk: Project Chrono

Project Chrono::Vehicle şu terrain seçeneklerini sunar:

- rigid mesh/heightmap;
- **SCM (Soil Contact Model):** Bekker-Wong ailesinden, az parametreli, hareketli patch ve GPU backend seçenekli; dokümana göre yakın gerçek zaman hedefi;
- granular DEM;
- FEA;
- SPH tabanlı CRM.

[Project Chrono terrain models](https://api.projectchrono.org/vehicle_terrain.html)

LunaPath için uygun entegrasyon modeli:

```text
Three.js UI  <── WebSocket/REST telemetry ──>  Python backend
                                                 │
                                                 └── Chrono native worker/container
                                                     SDEM + rover + soil params
```

Chrono tarayıcı bundle'ına gömülmemeli. Belirli bir 20–100 m test patch'i, rover hız/poz/roll/pitch, wheel slip ve sinkage telemetrisi üretir; web arayüzü bunu oynatır. Bu, Gazebo/Unity/Unreal entegrasyonundan daha doğrudan bir terramekanik değer sağlar.

---

## 8. Önerilen hedef mimari: üç doğruluk sınıfı

| Mod | Geometri | Malzeme/ışık | Fizik | İddia |
|---|---|---|---|---|
| **Scientific** | PGDA #104 SDEM | Normalize NAC + SPICE/horizon + lunar BRDF | Kinematik rota veya SDEM rigid collider | Konumsal olarak izlenebilir |
| **Presentation** | SDEM + visual near tile | PBR micro-normal, local shadows, düşük GTAO | İsteğe bağlı Rapier | Görsel gerçekçilik; mikro detay sentetik |
| **Physics lab** | SDEM + etiketli test patch'i | Aynı shader | Rapier veya dış Chrono | Simülasyon varsayımları/parametreleri açık |

Bu ayrım kritik. Aynı mikro PBR texture'ı hem ekranda “toz” gibi göstermek hem de planlayıcıya ölçülmüş kaya yüksekliği gibi vermek veri sızıntısıdır. Her katman manifestte şu alanları taşımalıdır:

```json
{
  "validity": "MEASURED | DERIVED | MODEL | SYNTHETIC",
  "affects_render": true,
  "affects_collision": false,
  "affects_lidar": false,
  "affects_planning": false,
  "source": "...",
  "scale_m": 0.4
}
```

---

## 9. Uygulama planı

### Faz 0 — ROI'yi tekilleştir, ölç ve referansları kilitle (1–2 gün)

- Kanonik pencereyi `2400/2500` projected bounds manifesti olarak tanımla.
- `setup_caches.py`, real-grid testleri ve frontend fixture'larındaki `1500/1000` drift'ini kaldır.
- Backend açılışında cache input identity/bounds uyuşmasını doğrula.
- Orbit, 10 m FPS ve 2 m FPS için aynı kamera/güneş konumlarında ekran görüntüleri oluştur.
- `renderer.info` ile calls/triangles/geometries/textures ölç.
- Chrome Performance panelinde p50/p95 frame time ve ana thread long task ölç.
- GPU/devicePixelRatio/maxTextureSize/maxAnisotropy kaydet.
- Kalite hedeflerini masaüstü `high`, entegre GPU `balanced`, mobil `low` diye ayır.

**Çıkış kriteri:** Setup komutu sahayı değiştirmiyor; backend/texture/fixture aynı bounds'u raporluyor; her sonraki faz aynı kamera/güneş ve aynı cihazda önce/sonra karşılaştırılabilir.

### Faz 1 — Görsel quick wins (2–4 gün)

- Yakın kaya/rover directional shadow map ekle.
- Terrain için Lunar-Lambert shader prototipi ekle; mevcut `surface/photo/data` modlarını bozma.
- `Moon Flat Macro 02` 2K/4K normal + roughness'i yalnız yakın alanda blend et.
- Hard-coded anisotropy'yi cihaz maksimumuna bağla.
- “Scientific / Presentation” toggle veya kalite preset'i ekle.

**Çıkış kriteri:** Kaya ayaklarında belirgin temas gölgesi; FPS'te mikro rölyef; veri layer renkleri değişmeden kalır; p95 frame time hedef preset'te kabul sınırını aşmaz.

### Faz 2 — PGDA #104 veri göçü (3–6 gün + indirme/önbellek zamanı)

- Bölge #9 SDEM ve ortomozaiği indir.
- Sabit row/col yerine projected bounds crop aracı ekle.
- Yeni input identity/provenance yaz.
- Tüm türetilmiş grid ve cache'leri yeniden üret.
- Eski/yeni sayısal fark ve rota regresyon raporu çıkar.
- UI'da SfS coverage/effective input resolution uyarısı ekle.

**Çıkış kriteri:** Grid origin/CRS/shape birebir testten geçer; endpoint, rota, kaya ve LiDAR hizası korunur; eski/yeni fark raporu vardır.

### Faz 3 — Performanslı çok ölçekli arazi (4–8 gün)

- Terrain'i örneğin 32/64-cell tile'lara böl.
- 3 LOD üret; sınır çatlakları için skirts veya geomorph uygula.
- 50–100 m near-field yoğun mesh ve mesafe fade'i ekle.
- PBR dokuları KTX2'ye çevir; albedo ve normal için uygun encoder profillerini görsel test et.
- Büyük/farklı kaya meshlerini BatchedMesh veya LOD+InstancedMesh ile grupla.
- Texture/geometry dispose ve LRU bütçesi ekle.

**Çıkış kriteri:** Kamera ilerlerken pop/crack yok; kalite presetleri bellek bütçesini aşmıyor; replan sırasında tile/rock kimliği değişmiyor.

### Faz 4 — Rapier fizik sandbox (4–8 gün)

- `@dimforge/rapier3d` sürümünü doğrudan pinle; CDN wrapper kullanma.
- SDEM heightfield collider oluştur ve yön/row-major eşlemesini fixture ile test et.
- Convex/compound rover chassis collider, kütle ve center-of-mass ekle.
- İlk spike'ta raycast wheel controller + lunar gravity + fixed timestep ekle ve modu açıkça `Presentation physics` olarak etiketle.
- VIPER doğruluğu hedeflenirse ikinci spike'ta dört bağımsız steering/drive/suspension modülünü Rapier joint'leriyle kur; mevcut front-only Ackermann animasyonunu fizik referansı sayma.
- Physics debug render ve reset mekanizması ekle.
- Kinematik mission playback'i varsayılan ve bağımsız tut.

**Çıkış kriteri:** Rover düz zeminde kararlı; 5/10/15° ramp ve 15 cm rijit engel testleri tekrarlanabilir; teker temasları mesh ile hizalı; pause/resume frame hızından bağımsız; route playback sonucu değişmez. VIPER etiketi kullanılacaksa dört teker steering/suspension state'i ayrı telemetri verir.

### Faz 5 — Terramekanik araştırma spike'ı (2–6 hafta+)

- Project Chrono SCM ile 20–50 m patch PoC.
- Literatür/deney temelli regolit parametre seti ve belirsizlik aralığı tanımla.
- Wheel slip/sinkage/energy sonuçlarını mevcut cost modelle karşılaştır.
- Ancak doğrulama verisi varsa planlayıcıya bağla; yoksa `MODEL` olarak raporla.

---

## 10. Kalite ve performans bütçesi

Aşağıdakiler kaynak gerçeği değil, önerilen kabul hedefleridir:

| Preset | Hedef | Terrain | Shadows | PBR | AO |
|---|---|---|---|---|---|
| Low | entegre GPU / güvenli fallback | tek mesh, mevcut DEM | kapalı veya 1024 near | 1K normal | kapalı |
| Balanced | tipik laptop | tiled SDEM, orta LOD | 2048 near | 2K KTX2 | kapalı |
| High | ayrık GPU | near dense tile + LOD | 2048/4096 near veya sınırlı CSM | 4K KTX2 | düşük GTAO |

Önerilen ölçülebilir kapılar:

- Balanced: p95 frame time ≤ 33 ms; High masaüstü: p95 ≤ 16,7–22 ms hedefi.
- Kamera hareketinde 100 ms üzeri texture upload/dosya decode takılması olmamalı; `renderer.initTexture()` ile ön yükleme denenebilir. [Three.js WebGLRenderer](https://threejs.org/docs/pages/WebGLRenderer.html)
- GPU texture bütçesi preset bazında belirlenmeli; 8K ham çoklu PBR setleri reddedilmeli.
- `renderer.info.memory.textures/geometries` ve `renderer.info.render.calls/triangles` development HUD'da gösterilmeli.
- Sahne yeniden kurulumunda texture, render target, post-process pass ve physics world yaşam döngüleri kapatılmalı. [Three.js cleanup guide](https://threejs.org/manual/en/cleanup.html)

---

## 11. Kabul testleri

### Veri ve koordinat

- SDEM dört köşe koordinatı beklenen lon/lat ile tolerans içinde.
- Render vertex `(row,col)` yüksekliği backend `elevation_grid[row,col]` ile eşit.
- Start/goal raycast, rover ve rock placement aynı hücreye düşüyor.
- Eski/yeni DEM provenance ve checksum UI/API'da okunabilir.

### Görsel

- 3 sabit kamera × 3 güneş açısı golden screenshot.
- Yüzey normal map'i data layer'larda devre dışı.
- Yerel gölge yönü SPICE güneş yönüyle tutarlı.
- PBR tekrar deseni 0–150 m bandında bariz değil.
- Orbit ve FPS geçişinde LOD çatlağı/popping yok.

### Fizik

- Sabit timestep ile aynı input aynı platformda tolerans içinde aynı poz verir.
- Heightfield Y yönü ve satır/kolon dönüşümü ters değil.
- Rover kütlesi/COM/collider ölçüleri metre-kilogram biriminde test edilir.
- Raycast tekerin engeli fiziksel teker collider'ı gibi tırmandığı varsayılmaz; 15 cm step testi iki yaklaşımda ayrı raporlanır.
- VIPER-benzeri modda dört bağımsız steering ve suspension komutu ile yana sürüş/yerinde dönüş fixture'ları vardır.
- Mission playback fizik kapalıyken önceki path zamanlaması ve raporlar birebir kalır.
- Fizik sonucu hiçbir zaman kaynak etiketi olmadan “gerçek rover performansı” diye sunulmaz.

### Performans

- Preset başına p50/p95 frame, draw calls, triangles, texture count ve tahmini GPU belleği kaydı.
- 2D ↔ 3D, orbit ↔ FPS ve replan döngülerinde texture/geometry sayısı sürekli artmıyor.
- KTX2 desteklenmezse kontrollü JPG/PNG fallback var.

---

## 12. Yapılmaması gerekenler

- **Sadece 8K/16K JPG koyma:** dosya çözünürlüğü geometri çözünürlüğü değildir; GPU belleğini büyütür.
- **1 m NAC görüntüsünü displacement olarak kullanma:** parlaklık yükseklik değildir; albedo ve gölgeyi sahte topoğrafyaya dönüştürür.
- **PBR mikro displacement'ı planlama verisi yapma:** bu texture Site11 ölçümü değildir.
- **Tüm 2,5 km'yi 10 cm mesh yapma:** yaklaşık 25.000 × 25.000 vertex ölçeği tarayıcı için anlamsızdır; tile/LOD gerekir.
- **MeshPhysicalMaterial'a geçip gerçekçilik bekleme:** clearcoat/transmission/iridescence regolit problemine karşılık gelmez.
- **GTAO'yu bilimsel shadow layer olarak kullanma:** ekran-uzayı efekti, güneş görünürlüğü değildir.
- **Rapier friction sonucunu regolit slip doğrulaması sayma:** rigid Coulomb sürtünmesi terramekanik değildir.
- **Fizik gövdesini mevcut path playback'e sessizce bağlama:** rota telemetrisiyle görsel poz ayrışabilir.
- **WebGPU/Unity/Unreal göçünü ilk çözüm yapma:** kaynak veri ve shader eksikleri başka motorda da kalır.

---

## 13. Son karar ve uygulanacak minimum paket

En iyi maliyet/sonuç paketi şudur:

1. `A3CLR22_9_deGerlache_Rim` SDEM'i mevcut bounds'a al.
2. Aynı paketin maksimum-aydınlatmalı ortomozaiğini değerlendir; mümkünse LROC fotometrik normalizasyon hattı kullan.
3. Terrain `MeshStandardMaterial` tabanını koru; Lunar-Lambert diffuse ekle.
4. Rover/kaya için 100–200 m yerel shadow map ekle.
5. `Moon Flat Macro 02` setinden yalnız near-field normal/roughness kullan; 2K/4K KTX2 yap.
6. Terrain'i tile/LOD'a geçir; büyük kaya ailesini BatchedMesh/LOD ile optimize et.
7. Mission playback'i koru; Rapier'ı ayrı `Physics sandbox` olarak ekle.
8. Sinkage/slip mühendislik hedefi doğarsa Chrono SCM PoC yap.

Bu paket Three.js tabanını, backend API'lerini ve mevcut rota/LiDAR modelini korur. En büyük değişiklik renderer değiştirmek değil, **daha iyi kaynak geometri + Ay'a özgü shader + ölçek bazlı detay + açık doğruluk etiketleri** eklemektir.

---

## 14. Kaynak defteri

### NASA / LROC / USGS veri ve fiziksel görünüm

| Kaynak | Yayıncı / tarih | Bu raporda kullanımı |
|---|---|---|
| [High-Resolution LOLA Topography for Lunar South Pole Sites — PGDA #78](https://pgda.gsfc.nasa.gov/products/78) | NASA GSFC PGDA | Mevcut DEM'in 5 m grid ve enterpolasyon sınırı |
| [Enhanced Topography Models… Shape-from-Shading — PGDA #104](https://pgda.gsfc.nasa.gov/products/104) | NASA GSFC PGDA; veri 2025/2026 | 13 bölge SDEM yöntemi ve ürün içeriği |
| [Bertone vd. 2026, PSJ 7:118](https://doi.org/10.3847/PSJ/ae5b70) | AAS/IOP, CC BY 4.0; 20 Mayıs 2026 | Region 9 doğruluk metrikleri, PSR sınırı ve hesaplama maliyeti |
| [Zenodo dataset 10.5281/zenodo.17954508](https://zenodo.org/records/17954508) | Bertone vd.; 16 Aralık 2025, kayıt güncelleme 7 Nisan 2026 | Bölge #9 dosyası, boyut, bounds README ve CC BY 4.0 |
| [A New View of the Lunar South Pole — PGDA #90](https://pgda.gsfc.nasa.gov/products/90) | NASA GSFC PGDA | Bölgesel DEM/effective resolution/slope/roughness/PSR seçenekleri |
| [de Gerlache Rim kontrollü NAC mozaiği](https://data.lroc.im-ldi.com/lroc/view_rdr/NAC_ROI_DEGERRIMLO1) | NASA/GSFC/ASU LROC; 2023 ürünü | Site11'i kapsayan 1 m görüntü, kapsam, konum doğruluğu ve boyut |
| [LROC NAC Processing Guide](https://www.lroc.asu.edu/data/support/downloads/LROC_NAC_Processing_Guide.pdf) | LROC/ASU; erişilen sürüm 2025 | NAC projeksiyon, mozaik ve fotometrik normalizasyon |
| [USGS LROC NAC South Pole 4 m DEM](https://astrogeology.usgs.gov/search/map/moon_lro_south_pole_dem) | USGS Astrogeology; 2013 | 4 m stereo alternatifinin Site11'i kapsamadığının doğrulanması |
| [ShadowCam project](https://techport.nasa.gov/projects/96950) | NASA TechPort/ASU | PSR görüntüleme ölçeği ve kullanım sınırı |
| [NASA CGI Moon Kit](https://svs.gsfc.nasa.gov/4720/) | NASA SVS; 2019, güncelleme 9 Ocak 2026 | Global renk/displacement seçenekleri ve bilimsel kullanım sınırı |
| [USGS ISIS photomet](https://isis.astrogeology.usgs.gov/8.2.0/Application/presentation/PrinterFriendly/photomet/photomet.html) | USGS Astrogeology / ISIS | Lunar-Lambert, Lommel-Seeliger ve Hapke model tanımları |
| [USGS ISIS lronacpho](https://isis.astrogeology.usgs.gov/8.3.0/Application/presentation/Tabbed/lronacpho/lronacpho.html) | USGS Astrogeology / ISIS 8.3.0 | 2019 LROC ampirik normalizasyon denklemi, örnek katsayılar ve geçerlilik sınırları |
| [ISIS LROCEmpirical kaynak kodu](https://github.com/DOI-USGS/ISIS3/blob/dev/isis/src/lro/apps/lronacpho/LROCEmpirical.cpp) | USGS Astrogeology, CC0-1.0 | Denklemin resmî uygulaması, derece/radyan ve referans-geometri davranışı |
| [VIPER Rover Simulation / Visual Simulation](https://ntrs.nasa.gov/api/citations/20210010712/downloads/VIPER%20RSIM%20VRT.pdf?attachment=true) | NASA NTRS | Hapke BRDF ve opposition effect'in NASA rover simülasyonunda kullanımı |
| [Astromaterials 3D Sample Catalog](https://ares.jsc.nasa.gov/astromaterials3d/sample-catalog.htm?origin=A15) | NASA JSC | Mevcut 15016/15556 kaya geometrilerinin kaynağı |

### Three.js ve web render

| Kaynak | Yayıncı | Bu raporda kullanımı |
|---|---|---|
| [MeshStandardMaterial](https://threejs.org/docs/pages/MeshStandardMaterial.html) | Three.js | PBR, normal/bump/displacement/roughness ve color-space kuralları |
| [MeshPhysicalMaterial](https://threejs.org/docs/pages/MeshPhysicalMaterial.html) | Three.js | Ek materyal özellikleri ve piksel maliyeti |
| [Texture](https://threejs.org/docs/pages/Texture.html) | Three.js | Mipmap, anisotropy ve texture özellikleri |
| [Texture memory guide](https://threejs.org/manual/en/textures.html) | Three.js | Ham GPU bellek hesabı |
| [Color Management](https://threejs.org/manual/en/color-management.html) | Three.js | sRGB renk ve NoColorSpace veri texture ayrımı |
| [WebGLRenderer](https://threejs.org/docs/pages/WebGLRenderer.html) | Three.js | GPU capabilities, renderer info ve shadow map |
| [LightShadow](https://threejs.org/docs/pages/LightShadow.html) | Three.js | Shadow resolution, bias/normalBias ve kontrollü güncelleme |
| [KTX2Loader](https://threejs.org/docs/pages/KTX2Loader.html) | Three.js | Basis Universal GPU texture transcode |
| [GLTFLoader](https://threejs.org/docs/pages/GLTFLoader.html) | Three.js | DRACO, KTX2 ve Meshopt decoder bağlantıları |
| [glTF Transform CLI](https://gltf-transform.dev/cli) | Don McCurdy / açık kaynak | GLB inspect/validate, geometry optimizasyonu ve KTX2 asset pipeline'ı |
| [meshoptimizer](https://github.com/zeux/meshoptimizer) | zeux, MIT | Index/cache/fetch/quantization ve gltfpack optimizasyon sırası |
| [LOD](https://threejs.org/docs/pages/LOD.html) | Three.js | Mesafe tabanlı model seviyeleri |
| [BatchedMesh](https://threejs.org/docs/pages/BatchedMesh.html) | Three.js | Farklı geometrilerde draw-call azaltma |
| [SimplifyModifier](https://threejs.org/docs/pages/SimplifyModifier.html) | Three.js | Kaya LOD üretimi; non-indexed çıktı nedeniyle terrain sınırı riski |
| [DecalGeometry](https://threejs.org/docs/pages/DecalGeometry.html) | Three.js | Yalnız görsel teker izi/lokal yüzey detayı |
| [CSM](https://threejs.org/docs/pages/CSM.html) | Three.js | Cascade shadow map |
| [GTAOPass](https://threejs.org/docs/pages/GTAOPass.html) | Three.js | Opsiyonel ekran-uzayı ambient occlusion |
| [TSL specification](https://threejs.org/docs/TSL.html) | Three.js | Taşınabilir özel shader/displacement |
| [three-mesh-bvh](https://github.com/gkjohnson/three-mesh-bvh) | gkjohnson | Hızlı raycast ve spatial query |
| [NASA-AMMOS 3DTilesRendererJS](https://github.com/NASA-AMMOS/3DTilesRendererJS) | NASA-AMMOS/JPL, Apache-2.0 | Gelecekte küresel/tiled streaming terrain |
| [geo-three](https://github.com/tentone/geo-three) | tentone, MIT | Tile/LOD mimarisi ve kutup projeksiyonu uyumsuzluk değerlendirmesi |
| [THREE.Terrain](https://github.com/IceCreamYou/THREE.Terrain) | IceCreamYou, MIT | Procedural terrain'ın ölçülmüş DEM yerine kullanılmaması |
| [hello-terrain](https://github.com/kenjinp/hello-terrain) | kenjinp, MIT; erken aşama | WebGPU/TSL terrain LOD için izlenecek teknoloji |
| [cdlod](https://github.com/nickyvanurk/cdlod) / [geo-clipmap](https://github.com/tschie/geo-clipmap) | Topluluk prototipleri | Dependency yerine terrain LOD algoritma referansı |
| [KTX 2.0 specification](https://registry.khronos.org/KTX/specs/2.0/ktxspec.v2.html) | Khronos | GPU texture container ve supercompression |
| [KTX Developer Guide](https://github.com/KhronosGroup/3D-Formats-Guidelines/blob/main/KTXDeveloperGuide.md) | Khronos | ETC1S/UASTC ve normal/non-color transcode seçimi |
| [`toktx` artist guide](https://github.com/KhronosGroup/3D-Formats-Guidelines/blob/main/subpages/KTXArtistGuide_toktx.md) | Khronos | UASTC kalite/RDO başlangıç aralıkları |

### PBR varlıkları

| Kaynak | Lisans / tarih | Bu raporda kullanımı |
|---|---|---|
| [Poly Haven API](https://polyhaven.com/our-api) | Poly Haven, CC0 API; 18 Temmuz 2026 | Kanal, çözünürlük, fiziksel boyut, dosya boyutu ve MD5 doğrulaması |
| [Moon Flat Macro 02](https://polyhaven.com/a/moon_flat_macro_02) | Poly Haven, CC0; 2025 | Önerilen nötr near-field regolit seti |
| [Moon Macro 01](https://polyhaven.com/a/moon_macro_01) | Poly Haven, CC0; 2025 | Alternatif regolit varyantı |
| [Moon Dusted 05](https://polyhaven.com/a/moon_dusted_05) | Poly Haven, CC0; 2025 | Tozlu yüzey varyantı |
| [Moon Meteor 02](https://polyhaven.com/a/moon_meteor_02) | Poly Haven, CC0; 2025 | Seyrek yakın krater patch'i |
| [Moon Rock 02](https://polyhaven.com/a/moon_rock_02) | Poly Haven, CC0; 2025 | LOD'lu küçük kaya modeli |
| [Moon Rock 07](https://polyhaven.com/a/moon_rock_07) | Poly Haven, CC0; 2025 | Yakın plan küçük kaya modeli |

### Fizik ve terramekanik

| Kaynak | Yayıncı | Bu raporda kullanımı |
|---|---|---|
| [Three.js RapierPhysics](https://threejs.org/docs/pages/RapierPhysics.html) | Three.js | Resmi heightfield wrapper ve CDN sınırı |
| [Rapier JavaScript getting started](https://rapier.rs/docs/user_guides/javascript/getting_started_js/) | Dimforge | WASM/NPM/compat entegrasyonu |
| [Rapier TypeScript bindings](https://github.com/dimforge/rapier/tree/master/typescript) | Dimforge, Apache-2.0 | Güncel resmi JS depo konumu ve build seçenekleri |
| [Rapier colliders](https://rapier.rs/docs/user_guides/javascript/colliders/) | Dimforge | Heightfield, trimesh, convex collider ve friction sınırları |
| [Rapier Heightfield API](https://rapier.rs/javascript3d/classes/Heightfield.html) | Dimforge | 3D matris sırası, eksen ve ölçek sözleşmesi |
| [Rapier determinism](https://rapier.rs/docs/user_guides/javascript/determinism/) | Dimforge | Tekrarlanabilir simülasyon koşulları ve başlangıç girdisi sınırları |
| [DynamicRayCastVehicleController](https://rapier.rs/javascript3d/classes/DynamicRayCastVehicleController.html) | Dimforge | Teker, süspansiyon, motor, fren ve temas API'si |
| [Rapier joints](https://rapier.rs/docs/user_guides/javascript/joints/) | Dimforge | Revolute/prismatic/generic ve multibody eklemli rover olanağı |
| [VIPER mobility architecture](https://ntrs.nasa.gov/api/citations/20220000441/downloads/viper-mobility-2022-01-27.pdf) | NASA NTRS | Dört bağımsız wheel module, aktif suspension ve teker boyutları |
| [VIPER mobility overview](https://ntrs.nasa.gov/api/citations/20240013903/downloads/LSIC_2024-Tech%20Infusion_Panel-VIPER_Mob-HW.pdf?attachment=true) | NASA NTRS | Kütle, hız, eğim, engel ve mekanizma kabul fixture'ları |
| [cannon-es](https://github.com/pmndrs/cannon-es) | pmndrs, MIT | Saf JS alternatif motor |
| [cannon-es Heightfield](https://pmndrs.github.io/cannon-es/docs/classes/Heightfield.html) | pmndrs | Terrain collider yeteneği |
| [cannon-es RaycastVehicle](https://pmndrs.github.io/cannon-es/docs/classes/RaycastVehicle.html) | pmndrs | Araç controller alternatifi |
| [JoltPhysics.js](https://github.com/jrouwe/JoltPhysics.js) | Jolt topluluğu, MIT | WASM build seçenekleri, vehicle ve double-precision alternatifi |
| [PhysX WASM WebIDL](https://github.com/fabmax/physx-js-webidl) | Topluluk binding'i / NVIDIA PhysX 5.6.1 | Heightfield ve vehicle destekli güçlü fakat daha karmaşık alternatif |
| [Three.js physics guide](https://threejs.org/manual/en/physics.html) | Three.js | Rapier/Jolt/PhysX/Ammo ekosisteminin güncel bakım durumu |
| [Project Chrono terrain models](https://api.projectchrono.org/vehicle_terrain.html) | Project Chrono; doküman üretimi 7 Eylül 2026 | Rigid, SCM, granular DEM, FEA ve CRM karşılaştırması |

---

## 15. Araştırma sınırlamaları

- PGDA #104 bölge #9 arşivinin tamamı bu araştırma sırasında indirilmedi; resmi ZIP merkezi dizini ve iç README HTTP range ile okunarak exact filename/byte boyutları doğrulandı. Raster piksel değerleri, nodata oranı ve Site11 crop içindeki gerçek coverage hâlâ entegrasyon spike'ında ölçülmelidir.
- Poly Haven varlıkları görsel kalite açısından incelendi; tarayıcı içi A/B render yapılmadı. En iyi set görüntü testinden sonra seçilmeli.
- Efor tahminleri mevcut kod karmaşıklığına dayalıdır. Rapier tablosundaki tek mikro-benchmark yerel sentetik ölçümdür; güncel motor/gerçek rover/tarayıcı performansının yerine geçmez.
- Rapier rigid-body önerisi mühendislik düzeyinde regolit doğrulaması değildir.
- Bu rapor uygulama yapmaz; uygulanacak değişikliklerin sırası, test kapıları ve geri dönüş sınırını tanımlar.
