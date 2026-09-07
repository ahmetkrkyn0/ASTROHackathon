# 09 — Sektörel Projelerin Olgunluğu ve Kıyaslama

> **Soru:** LunaPath gerçekte hangi olgunluk seviyesinde? Benzer projeler nerede? Ne iddia edebiliriz, ne iddia edemeyiz?
>
> **Kısa cevap:** LunaPath bugün **TRL 3 civarı bir analitik kavram kanıtıdır** ve NASA'nın model kredibilite ölçeğinde (NASA-STD-7009 ailesi) **düşük–orta** bandındadır. Bu kötü bir haber değil: bir hackathon prototipi için TRL 3 iyi bir sonuçtur ve **doğru şekilde iddia edilirse güçlüdür.** Asıl risk fazla iddia etmektir. Bu belge, dürüst bir skorkart ve üç aşamalı bir yükseltme planı verir.

---

## 1. Doğru ölçek hangisi? TRL değil, model kredibilitesi

LunaPath bir donanım değil, bir **model / karar destek yazılımıdır**. TRL bu tür ürünler için zorlanan bir ölçektir. NASA'nın model ve simülasyonlar için ayrı bir standardı vardır: **NASA-STD-7009 (Standard for Models and Simulations)** ve içindeki **Kredibilite Değerlendirme Ölçeği (Credibility Assessment Scale)**.

> ⚠️ Standardın güncel revizyonunu (7009A / sonraki) ve faktör isimlerini resmi belgeden teyit edin; aşağıdaki yapı standardın genel çerçevesini yansıtır.

Ölçek üç grup altında sekiz faktör kullanır:

| Grup | Faktör | LunaPath'te bugün |
|---|---|---|
**M&S Geliştirme** | **Verification** (kod, modeli doğru mu uyguluyor?) | 🟢 **İyi** — 9 test dosyası, doğrulama tabloları (`f_slope(15°)=0.500` vb.) |
| | **Validation** (model, gerçeği doğru mu yansıtıyor?) | 🔴 **Yok** — hiçbir katman ölçümle karşılaştırılmadı |
| | **Input Pedigree** (girdi verisinin kökeni/kalitesi) | 🔴 **Zayıf** — 2 katman sentetik, provenance kaydı yok |
**M&S Operasyonu** | **Results Uncertainty** (çıktı belirsizliği nicelendi mi?) | 🔴 **Yok** |
| | **Results Robustness** (sonuç varsayımlara ne kadar duyarlı?) | 🔴 **Yok** — hassasiyet analizi yapılmadı |
**Destekleyici Kanıt** | **Use History** (bu model daha önce nerede kullanıldı?) | 🔴 **Yok** (yeni) |
| | **M&S Management** (konfigürasyon, sürüm, süreç) | 🟡 **Orta** — git var, veri sürümleme yok |
| | **People Qualifications** | 🟡 Öğrenci ekibi, danışman/hakem incelemesi belirsiz |

**En çarpıcı bulgu:** LunaPath **verification** tarafında beklenenden iyi (matematik dondurulmuş, doğrulama tabloları var, testler var), **validation** tarafında ise sıfır. Yani *"kodu doğru yazdık"* kanıtlanmış, *"doğru modeli yazdık"* kanıtlanmamış.

> **Bu, projenin tek cümlelik teşhisidir ve tüm yol haritasını belirler.** Validation, Input Pedigree, Uncertainty ve Robustness dörtlüsünü kapatmak = [01](01_sektorel_veri_kaynaklari.md), [03](03_sentetik_minimum_veri.md), [07](07_termal_veri.md) belgelerini uygulamak.

### 1.1 TRL karşılığı

| TRL | Tanım | LunaPath |
|---|---|---|
| 1 | Temel ilkeler gözlendi | ✅ |
| 2 | Teknoloji konsepti formüle edildi | ✅ |
| **3** | **Analitik/deneysel kavram kanıtı** | ✅ **Buradayız** — çalışan uçtan uca hat, formüle edilmiş matematik, doğrulanmış implementasyon |
| 4 | Bileşen laboratuvarda geçerlendi | 🟡 **Gerçek veri + ablasyon ile ulaşılabilir** (bu setin P0/P1 paketleri) |
| 5 | Bileşen ilgili ortamda geçerlendi | ❌ Analog arazi testi veya gerçek misyon verisiyle karşılaştırma gerekir |
| 6 | Sistem modeli ilgili ortamda gösterildi | ❌ |
| 7–9 | Operasyonel / uçuşa nitelikli / uçmuş | ❌ |

**Hedef beyan:** *"LunaPath, TRL 3'te bir analitik kavram kanıtıdır; gerçek misyon veri ürünleriyle geçerleme ve belirsizlik nicelemesi tamamlandığında TRL 4 seviyesine ulaşacaktır."* Bu cümle savunulabilir, ölçülebilir ve dürüsttür.

---

## 2. Sektör manzarası — Ay yüzey otonomisi 2026 durumu

### 2.1 Uçan/uçacak sistemler

| Sistem | Durum (Ağu 2026) | Otonomi seviyesi | LunaPath'e göre |
|---|---|---|---|
| **Yutu-2** (Chang'e-4, CNSA) | 🟢 2019'dan beri operasyonel, **6+ yıl** | Görsel SLAM + rota planlama + rover kontrolü; öncülüne göre lokalizasyon/haritalama/otonom navigasyon/hareket planlamada belirgin ilerleme | **Ay'daki en olgun otonomi** |
| **Pragyan** (Chandrayaan-3, ISRO) | ⚪ Görev tamamlandı (2023) | 🟡 **Yer-döngülü**: her hareket için navcam verisi Dünya'ya indirilip DEM üretiliyor; komut başına **~5 m** | LunaPath'in konumlandırmasına **en yakın operasyonel model** |
| **Blue Ghost M1** (Firefly, CLPS) | ✅ 2 Mart 2025 başarılı iniş; **10 NASA yükünden 8'i hedeflerine ulaştı** | Rover yok (lander) | CLPS'in çalıştığının kanıtı |
| **IM-2 / Athena** (Intuitive Machines) | ❌ 6 Mart 2025, **yan yattı**, görev erken sona erdi | Hedeflenen yüzey mobilitesi gerçekleşemedi | Kutba yakın inişin ne kadar zor olduğunun kanıtı |
| **ispace M2 / Resilience + Tenacious** | ❌ 5–6 Haziran 2025 **çakılma**; lazer telemetre (LRF) anomalisi geçerli mesafe ölçümü engelledi | ~5 kg mikro-rover, lander çevresinde dairesel, saniyede birkaç cm | İniş hâlâ çözülmemiş bir problem |
| **CADRE** (JPL) | 🟡 IM-3 ile; pencere 2026'ya uzanıyor | 🟢 **Çok-robot dağıtık otonomi** gösterimi: 3 rover, el bagajı boyutu, 2 stereo kamera + navigasyon sensörleri + multistatik GPR; doğrudan komut almadan işbirliği | Otonomi araştırmasının **öncü ucu** |
| **VIPER** (NASA) | 🟡 **Diriltildi**: Temmuz 2024'te iptal (~800 M$), **Eylül 2025'te Blue Origin ile yeniden**; Blue Moon MK1, 190 M$ CLPS görev emri, **2027 hedefi**; güney kutbu, PSR'lara giriş, su buzu | Kutup, termal/enerji kısıtlı planlama | **LunaPath'in referans senaryosunun gerçek karşılığı** |
| **EMRS** (Avrupa Ay Rover Sistemi) | 🟡 Breadboard + **analog arazi test kampanyası** | Geliştirme aşamasında | TRL 4–5 yolculuğunun nasıl göründüğünün örneği |

**VIPER'ın iptal-ve-diriltme hikâyesi LunaPath için doğrudan anlamlıdır:** Tamamen inşa edilmiş, test edilmiş bir rover, **maliyet ve lander gecikmesi** nedeniyle iptal edildi. Yani bu alandaki asıl risk teknik değil, **program riski**dir. Bu, "görev öncesi planlama araçlarının" değerini artırır: erken, ucuz analiz maliyeti düşürür.

### 2.2 Akademik/araştırma manzarası — LunaPath'in gerçek rakipleri

Bunlar dergilerde/konferanslarda yayınlanmış, LunaPath ile **aynı problemi** çözen çalışmalardır. Bilmemek risk, atıf vermek güçtür.

| Çalışma | Ne yapıyor | LunaPath'e göre |
|---|---|---|
| **Lamarre, Malhotra, Kelly (IEEE AERO 2024)** — [arXiv 2401.08558](https://arxiv.org/abs/2401.08558) | Güneş enerjili rover ile PSR keşfi; **şans kısıtlı (chance-constrained)** görev-seviyesi planlama; bilinen ortalama oranlarda rastgele arızalar; **stokastik erişilebilirlik** analiziyle güvenli geçiş politikaları; Cabeus krateri / LCROSS bölgesinde çok günlük uzun menzilli sürüşler | 🔴 **LunaPath'ten ileride**: stokastik, arıza-farkında, çok günlük. LunaPath deterministik ve statik. **En yakın komşu, mutlaka atıf verilmeli** |
| **Risk-Aware Coverage Path Planning for Lunar Micro-Rovers** — [arXiv 2404.18721](https://arxiv.org/html/2404.18721v1) | Global (PDS DEM, offline maliyet) + local (VLP-16 LiDAR, miyopik algılama) hibrit; `mc = α(mc_static + mc_visited·V_i) + β·mc_DEM`; HDL graph SLAM; **gerçek arazi testi** (kaplama %80 killi / %65 kumlu zeminde, lokalizasyon MAE 0.41 / 0.32 m); CLOVER 7 kg mikro-rover, ROS1 | 🔴 **LunaPath'ten ileride**: gerçek donanım + saha testi. LunaPath yalnızca simülasyon |
| **Deep Learning for Lunar Rover Global Path Planning** — [Sensors 24(3), 844](https://www.mdpi.com/1424-8220/24/3/844) | Statik (eğim), zaman-değişken (ısı akısı, aydınlanma) ve yola-bağlı (termal + güç durumu) kısıtları grid'e ceza fonksiyonu olarak gömüyor; **rover'ın beklemesine izin veriyor**; RL ile kaynak-kısıtlı en kısa yol | 🟡 **Kısmen ileride**: zaman ekseni ve bekleme kararı var. LunaPath'te ikisi de yok ([08](08_global_local_rotalama_yuku.md) §3.3) |
| **Comprehensive Review of Path-Planning Algorithms for Planetary Rovers** — [Remote Sensing 17(11), 1924](https://www.mdpi.com/2072-4292/17/11/1924) | Alanın 2025 taksonomisi; arazi değişkenliği, engeller, **aydınlanma ve sıcaklık dalgalanmaları** vurgusu; sabah/akşam ve yüksek enlem aydınlanmasının güç verimliliğine etkisi | 📚 **Konumlandırma referansı** — LunaPath'i literatür haritasına yerleştirmek için |
| **Learning-Based End-to-End Path Planning for Lunar Rovers with Safety Constraints** — [PMC7866010](https://pmc.ncbi.nlm.nih.gov/articles/PMC7866010/) | Uçtan uca öğrenilmiş planlama | 🟡 Farklı yaklaşım; LunaPath'in açıklanabilirlik avantajı burada değerli |
| **Deep Probabilistic Traversability with Test-time Adaptation** — [arXiv 2409.00641](https://arxiv.org/pdf/2409.00641) | Belirsizlik-farkında gezegen rover navigasyonu | 🔴 Belirsizlik modellemesinde ileride |

### 2.3 Dürüst konumlandırma sonucu

| İddia | Savunulabilir mi? |
|---|---|
| "Ay kutbu için termal-güvenlik odaklı çok kriterli rota planlama prototipi geliştirdik" | ✅ **Evet** |
| "Fizik-temelli, peer-review edilmiş formüllerle çalışan bir maliyet modeli kurduk ve implementasyonunu doğrulama tablolarıyla test ettik" | ✅ **Evet** |
| "4 farklı misyon profilinin trade-off'larını sayısal ve görsel olarak karşılaştırıyoruz" | ✅ **Evet** — bu gerçek ve özgün bir katkı |
| "Aynı senaryoyu farklı **rover platformlarında** (VIPER, Yutu-2, LUVMI-M, LPR-1) koşup platform duyarlılığını gösteriyoruz" | ✅ **Evet** — `constants.py:14`'teki 4 profilli rover kataloğu. **Referans belgede yazmayan, kodda var olan bir üstünlük; mutlaka öne çıkarın** |
| "Gerçek NASA verisi kullanıyoruz" | 🟡 **Kısmen** — DEM gerçek, termal ve gölge sentetik. Düzeltilene kadar bu cümleyi kurmayın |
| "Bu alanda ilk/özgün" | ❌ **Hayır** — §2.2'deki çalışmalar var |
| "Otonom navigasyon sistemi" | ❌ **Hayır** — engel kaçınma yok ([05](05_engel_kacinma.md)) |
| "Rover üzerinde çalışabilir" | 🟡 Hesap bütçesi analizi yapıldıktan sonra **evet** ([08](08_global_local_rotalama_yuku.md) §4.3) |
| "Görev öncesi planlama ve karar destek aracı" | ✅ **En doğru konumlandırma** |

`ay_termal_navigasyon_proje_dokumani.md` §6.1'de "projenin tam konumlandırması" açık soru olarak bırakılmıştı. **Karar önerisi: "görev öncesi planlama + karar destek aracı"**, rover-üzeri otonomi modülü değil. Gerekçeler:

1. Mevcut mimari (offline grid ön-işleme + REST API + web arayüzü) tam olarak bunu destekliyor
2. Pragyan gibi gerçek bir Ay misyonu bugün böyle çalışıyor → **operasyonel ilgi gerçek**
3. Otonomi iddiası, olmayan bileşenleri (perception, yerel planlayıcı, gerçek zamanlı kısıtlar) görünür kılar
4. Karar destek iddiası, olan bileşenleri (çok kriterli karşılaştırma, açıklanabilirlik, senaryo analizi) öne çıkarır

---

## 3. Olgunluk skorkartı

10 boyut × 5 puan. **Bugün** ve **P0+P1 sonrası hedef**.

| # | Boyut | Bugün | Kanıt / gerekçe | Hedef | Nasıl |
|---|---|---|---|---|---|
| 1 | **Veri gerçekliği** | 🔴 **2/5** | 7 katmandan 1'i ölçüm (DEM); termal + gölge sentetik; tüm katmanlar tek girdiden türüyor | 🟢 **4/5** | [01](01_sektorel_veri_kaynaklari.md), [07](07_termal_veri.md) P0/P1 |
| 2 | **Fizik modeli** | 🟡 **3/5** | Enerji ve gölge sabitleri **tutarlı ve türetilebilir** (iyi); **4 rover profilli parametrik katalog** (LPR-1, LUVMI-M, VIPER, Yutu-2) — belgede yok, kodda var, güçlü; ama T_yüzey→T_iç sabit ofset, `τ` türetilmemiş | 🟢 **4/5** | [07](07_termal_veri.md) §3 lumped capacitance |
| 3 | **Verification** (kod doğruluğu) | 🟢 **4/5** | 9 test dosyası, doğrulama tabloları, matematik dondurulmuş — **hackathon için üstün** | 🟢 **5/5** | Heuristic admissibility testi ([08](08_global_local_rotalama_yuku.md) §6.1) |
| 4 | **Validation** (model gerçekliği) | 🔴 **1/5** | Hiçbir katman/çıktı ölçümle karşılaştırılmadı | 🟢 **4/5** | Ablasyon A/B/C/D ([03](03_sentetik_minimum_veri.md) §4.2) |
| 5 | **Belirsizlik yönetimi** | 🔴 **1/5** | Hard-limit'ler noktasal, hata bandı yok, hassasiyet analizi yok | 🟡 **3/5** | Belirsizlik bandı ([01](01_sektorel_veri_kaynaklari.md) §3.4), Monte Carlo (100 clone) |
| 6 | **Hesaplama olgunluğu** | 🟡 **2/5** | `computation_time_ms` ölçülüyor ama benchmark/bütçe analizi yok, ön-hesaplama yapılmıyor | 🟢 **4/5** | [08](08_global_local_rotalama_yuku.md) P0/P1 |
| 7 | **Zaman / dinamik** | 🔴 **1/5** | Statik snapshot; `f_shadow(H)` girdisi tanımsız; bekleme kararı yok | 🟡 **3/5** | L2 illumination_frac, ardından zaman-genişletilmiş graf |
| 8 | **Otonomi kapsamı** | 🟡 **2/5** | Global planlama var; yerel katman, perception, replanning yok | 🟡 **3/5** | Koridor sözleşmesi + replan tetikleyicileri ([05](05_engel_kacinma.md)) |
| 9 | **Açıklanabilirlik** | 🟢 **4/5** | Analitik maliyet fonksiyonu, `/api/cell-telemetry`, profil karşılaştırması — **projenin en güçlü yanı** | 🟢 **5/5** | `CostMap.explain()` ([04](04_acik_kaynak_modeller.md) §5.1) |
| 10 | **Belgeleme / tekrar-üretilebilirlik** | 🟡 **3/5** | Kapsamlı Türkçe dokümanlar (iyi); veri sürümleme, lisans kaydı, determinizm testi yok | 🟢 **4/5** | [01](01_sektorel_veri_kaynaklari.md) §3.2, §3.7 |
| | **TOPLAM** | **23/50** | | **39/50** | |

### 3.1 Skorkartın söylediği şey

- **Güçlü yanlar (koru):** verification, açıklanabilirlik, belgeleme. Bunlar öğrenci projelerinde nadirdir ve LunaPath'in gerçek sermayesidir.
- **Kritik zayıflıklar (kapat):** validation, belirsizlik, veri gerçekliği, zaman. Dördü de aynı kökten geliyor: **gerçek veri yok.**
- **Bilinçli kapsam dışı (belgele):** otonomi kapsamı, yerel katman.

**En verimli hamle:** Gerçek veriyi ekle (Diviner + illumination) → boyut 1, 4, 5, 7 aynı anda yükselir. **Tek müdahale, dört boyut.** Bu, yol haritasının neden [07](07_termal_veri.md) ile başlaması gerektiğinin nedenidir.

---

## 4. Üç aşamalı yükseltme planı

### Aşama I — "Dürüst ve Doğrulanmış" (1–2 hafta, TRL 3 → 4 eşiği)

| # | İş | Belge | Çıktı |
|---|---|---|---|
| 1 | Kutup Diviner ürününü doğrula ve indir | [07](07_termal_veri.md) §7 P0 | `thermal_grid_diviner.npy` |
| 2 | LOLA illumination + PSR indir | [01](01_sektorel_veri_kaynaklari.md) §5 | `illumination_frac.npy`, `psr_mask.npy` |
| 3 | `metadata.json` v2 + `physical_validity` | [01](01_sektorel_veri_kaynaklari.md) §3.1 | Provenance kaydı |
| 4 | Hizalama + şema doğrulama kapıları (CI'da kırıyor) | [01](01_sektorel_veri_kaynaklari.md) §3.3, §3.5 | `align.py`, `schemas.py` |
| 5 | **A/B/C/D ablasyon raporu** | [03](03_sentetik_minimum_veri.md) §4.2 | `ablation_report.md` — **en önemli tek çıktı** |
| 6 | `T_max_base` düzeltmesi, `f_thermal` ayrıştırma | [07](07_termal_veri.md) §7 P0 | |
| 7 | Benchmark tablosu + heuristic admissibility testi | [08](08_global_local_rotalama_yuku.md) §6 | `planner_benchmark.md` |
| 8 | Hesaplama bütçesi analizi (RAD750/HPSC) | [08](08_global_local_rotalama_yuku.md) §4.3 | Bütçe tablosu |
| 9 | Konumlandırma kararı + iddia denetimi | Bu belge §2.3 | README/sunum güncellemesi |
| 10 | `DATA_LICENSES.md`, determinizm testi, pin'ler | [01](01_sektorel_veri_kaynaklari.md), [04](04_acik_kaynak_modeller.md) | |

**Aşama I çıktısı:** *"Gerçek NASA ölçüm verisiyle çalışan, kendi sentetik baseline'ının hatasını niceleyen, hesaplama bütçesi analiz edilmiş bir çok kriterli rota planlayıcı."* Bu, TRL 4 iddiası için gereken minimum kanıt setidir.

### Aşama II — "Fiziksel ve Dinamik" (3–4 hafta, TRL 4)

| # | İş | Belge |
|---|---|---|
| 11 | Lumped capacitance termal model, `τ = C/(hA)` | [07](07_termal_veri.md) §3 |
| 12 | Belirsizlik bandı + üçlü traversability | [01](01_sektorel_veri_kaynaklari.md) §3.4 |
| 13 | Maliyet ön-hesaplama (8 yönlü dizi) + float32 | [08](08_global_local_rotalama_yuku.md) §2 |
| 14 | SVF (gökyüzü görüş faktörü) + **SEP senaryosu** | [06](06_radyasyon_verisi.md) §2, §3 |
| 15 | SfS 5 m ürünü + `f_roughness` + koridor rafinasyonu | [02](02_goruntu_isleme.md) §2.5 |
| 16 | `Corridor` sözleşmesi + replan tetikleyicileri + safe haven erişilebilirliği | [05](05_engel_kacinma.md) §4 |
| 17 | Slip düzeltmesi | [05](05_engel_kacinma.md) §3.1 |
| 18 | SpiceyPy + L2 zaman modeli (illumination_frac) | [04](04_acik_kaynak_modeller.md) §2.1, [07](07_termal_veri.md) §4.2 |
| 19 | `CostMap` + `explain()` refaktörü | [04](04_acik_kaynak_modeller.md) §5.1 |
| 20 | Bileşen bazlı `HealthState` | [06](06_radyasyon_verisi.md) §5 |

### Aşama III — "Zaman-Uzay Planlayıcı" (6–10 hafta, TRL 4→5 yolu)

| # | İş | Belge |
|---|---|---|
| 21 | Zaman-genişletilmiş graf + **bekleme kenarı** | [08](08_global_local_rotalama_yuku.md) §3.3 |
| 22 | Üç seviyeli hiyerarşi (A/B/C) | [08](08_global_local_rotalama_yuku.md) §3.2 |
| 23 | Anytime A* + suboptimality bound | [08](08_global_local_rotalama_yuku.md) §5 |
| 24 | 100-clone Monte Carlo rota kararlılığı | [01](01_sektorel_veri_kaynaklari.md) §2.1 |
| 25 | heat1d ile rejim-tabanlı yüzey sıcaklığı | [07](07_termal_veri.md) §4.3 |
| 26 | Kaya tespiti (Diviner `ra` + NAC/YOLO) | [02](02_goruntu_isleme.md) §2.3 |
| 27 | Çok bölgeli senaryo kütüphanesi (Shackleton, Nobile, de Gerlache, Malapert) | [01](01_sektorel_veri_kaynaklari.md) §5 |
| 28 | Literatür karşılaştırması: Lamarre vd. senaryosunu tekrarla | Bu belge §2.2 |

**Madde 28 özellikle değerli:** Lamarre vd. Cabeus krateri / LCROSS bölgesinde çok günlük sürüşler koşuyor. Aynı bölgede aynı senaryoyu koşup sonuçları karşılaştırmak, LunaPath'i literatüre **ölçülebilir biçimde** bağlar. Bu, akademik yayın için gereken en önemli adımdır.

---

## 5. Kıyaslama özeti — tek tabloda

| Boyut | LunaPath (bugün) | LunaPath (Aşama II) | Lamarre vd. 2024 | Risk-Aware Coverage 2024 | Pragyan (uçmuş) | Yutu-2 (uçmuş) |
|---|---|---|---|---|---|---|
| Gerçek veri | 🟡 DEM only | 🟢 DEM+Diviner+illum | 🟢 | 🟢 PDS DEM | 🟢 | 🟢 |
| Termal model | 🔴 Sentetik | 🟢 Ölçüm + fizik | 🟡 | ❌ | 🟢 Donanım | 🟢 Donanım |
| Zaman ekseni | 🔴 Yok | 🟡 L2 | 🟢 Çok günlük | ❌ | 🟢 | 🟢 |
| Stokastik / arıza | 🔴 Yok | 🔴 Yok | 🟢 Şans kısıtlı | ❌ | — | — |
| Yerel planlama | 🔴 Yok | 🟡 Arayüz | ❌ | 🟢 LiDAR + Bug | 🟡 Yer-döngülü | 🟢 SLAM |
| Gerçek donanım testi | 🔴 Yok | 🔴 Yok | ❌ | 🟢 Saha testi | 🟢 Uçtu | 🟢 Uçtu |
| Çok kriterli trade-off | 🟢 **4 profil** | 🟢 **5+ kriter** | 🟡 | 🟡 2 terim | ❌ | ❌ |
| Açıklanabilirlik | 🟢 **Güçlü** | 🟢 **Çok güçlü** | 🟡 | 🟡 | — | — |
| Belgeleme | 🟢 Güçlü | 🟢 Güçlü | 🟢 Yayın | 🟢 Yayın | 🟢 | 🟢 |

**LunaPath'in gerçek ayırt edici üstünlüğü sağdan ikinci ve üçüncü satırlardır:** çok kriterli profil karşılaştırması ve açıklanabilirlik. Rakiplerin hiçbiri "aynı harita, aynı start/goal, 4 farklı misyon felsefesi, yan yana sayısal karşılaştırma" yapmıyor. **Bunu öne çıkarın; otonomi iddiası yerine bunu satın.**

---

## 6. Sunum/rapor için hazır çerçeve

**Açılış (dürüst konumlandırma):**
> *"LunaPath, Ay güney kutbunda görev yapacak rover'lar için bir **görev öncesi planlama ve karar destek aracıdır.** Rover üzerinde çalışan bir otonomi modülü değildir; operatörün ve görev planlayıcısının, aynı harita üzerinde farklı misyon felsefelerinin ürettiği rotaları ve trade-off'larını sayısal olarak karşılaştırmasını sağlar."*

**Özgünlük iddiası (savunulabilir):**
> *"Klasik planlayıcılar tek bir maliyet fonksiyonu optimize eder. Biz dört fizik-temelli kriteri (eğim, enerji, gölge, termal) MRU [0,1] normalizasyonuyla ortak bir ölçeğe getirip, dört farklı misyon profilinin aynı problemde nasıl farklı kararlar verdiğini gösteriyoruz — ve her kararın hangi kriterden geldiğini hücre bazında açıklıyoruz."*

**Olgunluk beyanı (ölçülebilir):**
> *"TRL 3'te bir analitik kavram kanıtıyız. Verification tarafımız güçlü: matematik dondurulmuş, doğrulama tablolarıyla test edilmiş, 9 test dosyası var. Validation tarafımızda ise açık bir boşluk vardı: termal katmanımız sentetikti. Bunu kapatmak için gerçek Diviner ölçümlerine geçtik ve kendi sentetik modelimizin hatasını niceledik — RMSE X K, hücrelerin %Y'sinde yanlış-güvenli sınıflandırma."*

**Kapsam dışı beyanı (güç göstergesi):**
> *"Yerel engel kaçınma, perception ve gerçek zamanlı onboard yürütme kapsam dışıdır. Ancak yerel katmana giden arayüzü — koridor sözleşmesini — tanımladık: waypoint dizisi, segment bazlı açıklık, termal/enerji bütçesi, zaman penceresi ve geri dönüş noktaları. Bu, sistemimizin bir otonomi yığınının üst katmanı olarak nasıl konumlandığını gösterir."*

**Literatür farkındalığı (kritik):**
> *"Bu problemi çözen başka çalışmalar var. Lamarre, Malhotra ve Kelly (IEEE AERO 2024) şans kısıtlı formülasyon ve stokastik erişilebilirlik kullanıyor; bizim yaklaşımımız deterministik ama çok kriterli trade-off analizi ve açıklanabilirlik tarafında farklılaşıyor. Bir sonraki adımımız aynı bölgede (Cabeus/LCROSS) senaryolarını tekrarlayıp doğrudan karşılaştırma yapmak."*

---

## 7. Kabul kriterleri

- [ ] Konumlandırma kararı verilmiş ve tüm belgelerde tutarlı ("görev öncesi planlama / karar destek")
- [ ] TRL beyanı ve NASA-STD-7009 tarzı kredibilite tablosu belgede
- [ ] Skorkart doldurulmuş; "bugün" ve "hedef" kolonları güncel tutulan bir yaşayan belge
- [ ] §2.3 iddia denetim tablosundaki ❌ satırları hiçbir sunumda/README'de geçmiyor
- [ ] §2.2'deki en az 4 çalışmaya atıf verilmiş
- [ ] Aşama I'in 10 maddesi tamamlanmış → TRL 4 iddiası için kanıt seti hazır

---

## Kaynaklar

- [NASA Selects Blue Origin to Deliver VIPER Rover to Moon's South Pole](https://www.nasa.gov/news-release/nasa-selects-blue-origin-to-deliver-viper-rover-to-moons-south-pole/)
- [NASA revives VIPER lunar rover mission with Blue Origin lander award — SpaceNews](https://spacenews.com/nasa-revives-viper-lunar-rover-mission-with-blue-origin-lander-award/)
- [CADRE — JPL](https://www.jpl.nasa.gov/missions/cadre/) · [NASA's Mini Rover Team Is Packed for Lunar Journey](https://www.nasa.gov/missions/tech-demonstration/cadre/nasas-mini-rover-team-is-packed-for-lunar-journey/)
- [Blue Ghost successfully starts lunar surface mission while IM-2 lands sideways — NASASpaceflight](https://www.nasaspaceflight.com/2025/03/blue-ghost-im-2-landings/)
- [ispace Resilience crash landing — Spaceflight Now](https://spaceflightnow.com/2025/06/06/ispaces-resilience-lander-crash-lands-on-the-moon/) · [Status Update on ispace Mission 2](https://ispace-inc.com/news-en/?p=7664)
- [Private Japanese moon lander crashed due to laser errors — Space.com](https://www.space.com/space-exploration/launches-spacecraft/private-japanese-moon-lander-crashed-due-to-laser-errors-ispace-says)
- [Lamarre, Malhotra, Kelly (2024), Safe Mission-Level Path Planning… (arXiv 2401.08558)](https://arxiv.org/abs/2401.08558)
- [Risk-Aware Coverage Path Planning for Lunar Micro-Rovers (arXiv 2404.18721)](https://arxiv.org/html/2404.18721v1)
- [A Comprehensive Review of Path-Planning Algorithms for Planetary Rover Exploration (Remote Sensing 17(11), 1924)](https://www.mdpi.com/2072-4292/17/11/1924)
- [A Deep Learning Approach to Lunar Rover Global Path Planning (Sensors 24(3), 844)](https://www.mdpi.com/1424-8220/24/3/844)
- [Learning-Based End-to-End Path Planning for Lunar Rovers with Safety Constraints](https://pmc.ncbi.nlm.nih.gov/articles/PMC7866010/)
- [Deep Probabilistic Traversability with Test-time Adaptation (arXiv 2409.00641)](https://arxiv.org/pdf/2409.00641)
- [Breadboarding the European Moon Rover System (arXiv 2411.13978)](https://arxiv.org/pdf/2411.13978)
- [Prospect and Research Progress of Lunar Intelligent Robot Technology (ScienceDirect)](https://www.sciencedirect.com/org/science/article/pii/S2692765926000372)
- [A Review of Control Techniques For Lunar Rovers (ACM)](https://dl.acm.org/doi/pdf/10.1145/3704558.3704563)
- [Space Science in 2026: New lunar explorers — NASASpaceFlight](https://www.nasaspaceflight.com/2026/01/space-science-2026-preview/)
