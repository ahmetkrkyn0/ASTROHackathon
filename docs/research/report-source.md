# Research source — Three.js Ay yüzeyi ve rover fiziği

Bu dosya deep-research çalışma kaydıdır. Kullanıcıya sunulan sentez:

- `docs/research/13_threejs_ay_yuzeyi_ve_rover_fizigi_deep_research_2026-09-08.md`

## Araştırma kapsamı

- Site11/de Gerlache için daha yüksek gerçek arazi detayı
- Gerçek görüntü, albedo ve sentetik PBR ayrımı
- Mevcut Three.js özellik boşlukları ve ölçek/performans bütçesi
- Tarayıcı rigid-body araç fiziği ve yüksek doğruluk terramekaniği
- Mevcut backend/planlama/LiDAR semantiğini bozmayan aşamalı mimari

## Kanıt boşluğu matrisi

| Soru | Durum | Ana kanıt |
|---|---|---|
| Mevcut saha PGDA #104 SDEM içinde mi? | Kapatıldı | Yerel projected bounds + Zenodo region 9 README |
| Region 9 ürününün nicel doğruluğu nedir? | Kapatıldı | Bertone vd. 2026 Tablo 4/5 |
| ZIP içinde hangi gerçek dosyalar var? | Kapatıldı | Zenodo ZIP central directory + iç README, HTTP range |
| Site11 crop'unda coverage/nodata/belirsizlik nedir? | Kapatıldı | Yedi rasterın HTTP range ile in-memory raster analizi |
| Yeni SDEM mevcut LOLA crop'u ne kadar değiştirir? | Kapatıldı | 250.000 hücrede doğrudan yükseklik/eğim karşılaştırması |
| Veri pipeline'ı aynı ROI'yi koruyor mu? | Kapatıldı/olumsuz | `metadata.json=2400/2500`; setup/test/fixture=`1500/1000` |
| Site11'i kapsayan hazır yüksek çözünürlüklü görüntü var mı? | Kapatıldı | LROC `NAC_ROI_DEGERRIMLO1`, 1 m/px; doğrudan 2500×2500 crop ölçümü |
| Hazır 1–4 m DEM drop-in alternatifi var mı? | Kısmi/olumsuz | USGS 4 m güney kutbu ürünü Site11'i kapsamıyor; #104 5 m en iyi hazır bölgesel aday |
| PSR ayrıntısı #104 ile çözülüyor mu? | Kapatıldı/olumsuz | Hakemli #104 makalesi; ShadowCam gelecek çalışma |
| 500×500 collider tek başına ağır mı? | Ön bulgu kapatıldı | Yerel Rapier 0.12 sentetik mikro-benchmark |
| Gerçek rover controller + render p95 bütçesi | Açık | Güncel Rapier 0.20, gerçek GLB ve hedef tarayıcı benchmark'ı gerekir |
| Mevcut rover GLB'leri optimize mi? | Kapatıldı/olumsuz | GLB chunk denetimi: compression extension yok; Yutu 343.078 triangle/21,7 MB |
| Raycast controller gerçek VIPER hareketini temsil eder mi? | Kapatıldı/olumsuz | Rapier API + NASA VIPER dört bağımsız aktif wheel-module mimarisi |
| Hazır Three.js terrain kütüphanesi doğrudan takılabilir mi? | Kapatıldı/olumsuz | 3d-tiles-renderer, geo-three, THREE.Terrain, hello-terrain ve clipmap repo taraması |
| En iyi PBR seti hangisi? | Açık | Poly Haven adayları bulundu; A/B render ve GPU ölçümü gerekir |

## Birincil kaynak defteri

| Kaynak | URL | Kullanım |
|---|---|---|
| PGDA #78 | https://pgda.gsfc.nasa.gov/products/78 | Mevcut LOLA veri tabanı ve enterpolasyon sınırı |
| PGDA #104 | https://pgda.gsfc.nasa.gov/products/104 | SDEM ürün ailesi |
| Bertone vd. 2026 | https://doi.org/10.3847/PSJ/ae5b70 | Metot, validasyon, PSR ve hesaplama maliyeti |
| Zenodo 17954508 | https://zenodo.org/records/17954508 | Region 9 arşivi, lisans, bounds ve dosyalar |
| LROC de Gerlache mosaic | https://data.lroc.im-ldi.com/lroc/view_rdr/NAC_ROI_DEGERRIMLO1 | 1 m/px makro görüntü |
| LROC de Gerlache pyramidal GeoTIFF | https://pds.mcp.nasa.gov/data/store/img/lunar_reconnaissance_orbiter/pds4/lroc/lro-l-lroc-5-rdr/LROLRC_2001/EXTRAS/BROWSE/NAC_ROI/DEGERRIMLO1/NAC_ROI_DEGERRIMLO1_P885S2933.PYR.TIF | Site11 2500×2500 crop'un doğrudan HTTP Range analizi |
| LROC NAC guide | https://www.lroc.asu.edu/data/support/downloads/LROC_NAC_Processing_Guide.pdf | Fotometrik normalizasyon |
| USGS ISIS lronacpho | https://isis.astrogeology.usgs.gov/8.3.0/Application/presentation/Tabbed/lronacpho/lronacpho.html | 2019 LROC ampirik normalizasyon modeli, katsayılar ve geçerlilik aralığı |
| ISIS LROCEmpirical implementation | https://github.com/DOI-USGS/ISIS3/blob/dev/isis/src/lro/apps/lronacpho/LROCEmpirical.cpp | Denklemin resmî kod düzeyindeki doğrulaması |
| USGS 4 m South Pole DEM | https://astrogeology.usgs.gov/search/map/moon_lro_south_pole_dem | Kapsam karşılaştırması |
| ShadowCam | https://techport.nasa.gov/projects/96950 | PSR görüntü alternatifi |
| Three.js docs/manual | https://threejs.org/docs/ | Render, materyal, sıkıştırma, LOD ve fizik addonları |
| NASA-AMMOS 3DTilesRendererJS | https://github.com/NASA-AMMOS/3DTilesRendererJS | Çok sahalı/küresel terrain streaming adayı |
| geo-three | https://github.com/tentone/geo-three | Tile LOD ve kutup projeksiyonu uyum değerlendirmesi |
| THREE.Terrain | https://github.com/IceCreamYou/THREE.Terrain | Procedural terrain sınırı |
| hello-terrain | https://github.com/kenjinp/hello-terrain | Erken aşama WebGPU/TSL LOD alternatifi |
| Rapier docs | https://rapier.rs/docs/user_guides/javascript/ | Heightfield, araç, determinism ve temas sınırları |
| NASA VIPER mobility | https://ntrs.nasa.gov/api/citations/20220000441/downloads/viper-mobility-2022-01-27.pdf | Dört bağımsız wheel-module mimarisi |
| Project Chrono | https://api.projectchrono.org/vehicle_terrain.html | SCM/DEM/CRM terramekaniği |
| Poly Haven Moon assets | https://polyhaven.com/ | CC0 yakın alan PBR adayları |
| Poly Haven API | https://polyhaven.com/our-api | Kanal, dosya boyutu, fiziksel ölçü ve hash doğrulaması |

## Yerel bulgular

- Three.js `0.183.2`; runtime fizik bağımlılığı yok.
- `@dimforge/rapier3d-compat@0.12.0` yalnız `@types/three` üzerinden dolaylı development bağımlılığı.
- Arazi 500×500 @ 5 m; 250.000 vertex ve 498.002 triangle.
- Terrain materyalinde normal/displacement/roughness map yok; renderer shadow map etkin değil.
- LROC frontend dokuları 2048×2048; kaynak crop 2500×2500 @ 1 m/px.
- Yerel sentetik Rapier testi: 250k height sample + 50 kutu, beş × 600 step; medyan 0,107 ms/step. Nihai tarayıcı benchmark'ı değildir.
- Region 9 crop: SDEM %100 geçerli; 15 m coverage gridinde %91,165 en az bir NAC katkısı, %77,242 en az üç solar bin.
- SDEM − mevcut LOLA crop mutlak farkı: medyan 0,690 m, p95 2,600 m; mutlak 5 m-baseline slope farkı medyan 1,617°, p95 5,560°.
- Kontrollü LROC Site11 crop'u `2500×2500 @ 1 m`; `DN<20` %25,904 (mevcut NAC_POLE provenance ~%52). 2048 ölçeğinde gradient mean 0,04023 vs 0,02686; Laplacian mean 0,07932 vs 0,05955.
- Kontrollü/mevcut high-pass phase correlation 512 px ölçekte `[+1,-1]` px kayma ve 0,607 korelasyon verdi; yaklaşık `+4,9/-4,9 m` offset nedeniyle coregistration zorunlu.
- Kritik ROI drift riski: `scripts/setup_caches.py` çalışan 2400/2500 penceresini 1500/1000 ile yeniden yazabiliyor.
- `lronacpho` 2019 modeli NAC görüntü normalizasyonudur; ileri render BRDF'si değildir. Resmî doküman fonksiyonu 15–65° phase aralığıyla sınırlar ve DEM-tabanlı açı hesabı sunar.
- Mevcut kod dört GLB tekerini front/rear ayırıp ön tekerlere bisiklet/Ackermann steering uygular; gerçek VIPER dört bağımsız drive/steering/aktif-suspension modülüdür.
- Terrain paket taramasında sabit 2,5 km bilimsel crop için drop-in kazanan çıkmadı; özel deterministik tile/LOD daha düşük riskli, `3d-tiles-renderer` ise küre/çok-saha büyümesinde güçlü aday.
- GLB denetimi: textured VIPER 119.604 triangle/10,06 MB ve dört ayrı wheel node; Yutu 343.078 triangle/21,69 MB ve tek node. Hiçbirinde Draco/Meshopt/KTX2 extension yok.

## Kalan doğrulama işleri

1. Kanonik 2400/2500 ROI manifestini setup scripti, testler ve fixture'lar için tek kaynak yap.
2. Eski LOLA ve SDEM ile iki sabit rota üzerinde cost/path/horizon sonuçlarını karşılaştır.
3. 1 m LROC kontrollü mozaiği ve PGDA ortomozaiğini aynı crop'ta görsel/fotometrik A/B test et.
4. Poly Haven near-field setlerini 2K/4K KTX2 olarak GPU bellek ve frame-time ile karşılaştır.
5. Rapier 0.20.x ile gerçek rover raycast controller'ını Chrome/Firefox hedef cihazlarda ölç.
