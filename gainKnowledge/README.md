# gainKnowledge — LunaPath Feature Bilgi Tabanı

> **Amaç:** Jüri karşısında herhangi bir feature hakkında soru geldiğinde, derin teknik uzman olmasak bile **doğru ve kendinden emin** anlatabilmek.
>
> Bu bir kod dokümantasyonu değil. Her dosya bir feature'ı sıfırdan anlatıyor: nedir, hangi problemi çözer, nasıl çalışır, neyden ilham alındı, neye göre çalışır — ve jüriden gelebilecek sorularla cevapları.

**37 dosya · 8 kategori · ~6 900 satır**

---

## Nereden başlamalı?

Hiç bilmiyorsanız sırayla:

1. **[LunaPath Nedir?](00-genel-bakis/lunapath-nedir.md)** — Problemin ne olduğu, neden zor
2. **[Sistem Mimarisi](00-genel-bakis/sistem-mimarisi.md)** — Parçalar nasıl birleşiyor
3. **[Veri Kaynakları ve Etiketler](00-genel-bakis/veri-kaynaklari-ve-etiketler.md)** — "Bu sayıya nasıl güveniyorsunuz?" sorusunun cevabı

Sonra ilgilendiğiniz feature'ın dosyasına gidin. Her dosya kendi başına okunabilir.

---

## Her dosyanın yapısı

| Bölüm | İçerik |
|---|---|
| **Nedir?** | Tek paragrafta öz |
| **Hangi problemi çözüyor?** | Neden var, olmasaydı ne olurdu |
| **Analoji** | Günlük hayattan bir karşılık |
| **Nasıl çalışıyor?** | Adım adım, jargonsuz mekanizma |
| **Ölçülen sayılar** | Site11'de gerçekten ölçülmüş değerler |
| **İlham kaynağı** | Gerçek NASA/akademik referanslar |
| **İddia sınırı** | Ne söyleyebiliriz, ne söyleyemeyiz |
| **Kodda nerede?** | Dosya ve fonksiyon adresleri |
| **Jüri soruları** | Muhtemel sorular + hazır cevaplar |

---

## 00 · Genel Bakış

| Dosya | Konu |
|---|---|
| [LunaPath Nedir?](00-genel-bakis/lunapath-nedir.md) | Ay güney kutbunda rota planlama problemi, üç katmanlı yapı |
| [Sistem Mimarisi](00-genel-bakis/sistem-mimarisi.md) | Veri akışı, üç tasarım kuralı, feature bağımlılık haritası |
| [Veri Kaynakları ve Etiketler](00-genel-bakis/veri-kaynaklari-ve-etiketler.md) | MEASURED / MODEL / DERIVED / SYNTHETIC, en zayıf halka kuralı |

## 01 · Arazi ve Veri

| Dosya | Feature |
|---|---|
| [DEM ve Veri Hattı](01-arazi-ve-veri/dem-ve-veri-hatti.md) | Ham NASA verisinden yedi katmana |
| [Eğim ve Geçilebilirlik](01-arazi-ve-veri/egim-ve-gecilebilirlik.md) | Beş kurallı geçilebilirlik maskesi |
| [Pürüzlülük ve PSR](01-arazi-ve-veri/puruzluluk-ve-psr.md) | **C4** — LOLA LDRM beşinci kriter, PSR doğrulaması |
| [DEM Belirsizliği](01-arazi-ve-veri/dem-belirsizligi-100-klon.md) | **B3** — NASA'nın 100 istatistiksel klonu |
| [Rover Katalogu](01-arazi-ve-veri/rover-katalogu-ve-grid-uyarlama.md) | Dört araç, rover'a göre grid uyarlaması |

## 02 · Işık, Gölge ve Termal

| Dosya | Feature |
|---|---|
| [Ufuk ve Aydınlanma](02-isik-golge-ve-termal/ufuk-ve-aydinlanma.md) | Işın izlemeyle gölge hesabı |
| [Aydınlık Koridoru](02-isik-golge-ve-termal/aydinlik-koridoru.md) | **A2** — CMU'nun (t,y,x) hacim yöntemi |
| [Termal Model](02-isik-golge-ve-termal/termal-model.md) | Yüzey sıcaklığı ve iç sıcaklık gevşemesi |
| [Termal Dwell ve Zarf](02-isik-golge-ve-termal/termal-dwell-ve-operasyon-zarfi.md) | **C6** — NASA JSC'nin operasyon zarfı ve saplanma süresi |

## 03 · Konum ve İletişim

| Dosya | Feature |
|---|---|
| [Efemeris](03-konum-ve-iletisim/efemeris-gunes-ve-dunya-geometrisi.md) | SPICE ile Güneş ve Dünya geometrisi |
| [Dünya Görünürlüğü (DTE)](03-konum-ve-iletisim/dunya-gorunurlugu-dte.md) | **A4** — LOLA ile doğrulandı, RMSE 0,087 |
| [Poz, Lokalizasyon, Skyline](03-konum-ve-iletisim/pose-lokalizasyon-ve-skyline.md) | GPS'siz konumlandırma, kayma bütçesi |

## 04 · Planlama ve Maliyet

| Dosya | Feature |
|---|---|
| [Maliyet Motoru](04-planlama-ve-maliyet/maliyet-motoru.md) | Beş kriter, AHP ağırlıkları, iki kriterin çöküş hikâyesi |
| [2-D A* Planlayıcı](04-planlama-ve-maliyet/astar-2d-planlayici.md) | Hızlı statik planlama |
| [4-D Planlayıcı](04-planlama-ve-maliyet/planlayici-4d.md) | "Bekle, Güneş dönsün" kararı + bütün kısıtların buluştuğu yer |
| [Slip Modeli](04-planlama-ve-maliyet/slip-modeli.md) | **C3** — kaynaklı çapalarla kayma eğrisi |
| [CVaR Risk](04-planlama-ve-maliyet/cvar-risk.md) | **B2** — risk iştahı, kuyruk maliyeti |
| [Safe Haven](04-planlama-ve-maliyet/safe-haven.md) | **A1** — NASA'nın sığınak tanımı ve bacak kuralı |
| [Survival / Reach-Avoid](04-planlama-ve-maliyet/survival-reach-avoid.md) | **B1** — arıza olasılığı ve kurtarma politikası |
| [Koridor Sözleşmesi](04-planlama-ve-maliyet/koridor-sozlesmesi.md) | Küresel → yerel planlayıcı arayüzü |
| [Replan Tetikleyicileri](04-planlama-ve-maliyet/replan-tetikleyicileri.md) | Yedi bağımsız kontrol |

## 05 · Doğrulama ve Test

| Dosya | Feature |
|---|---|
| [Güvenlik Monitörü](05-dogrulama-ve-test/safety-monitor-stl-fretish.md) | **D3** — FRETISH + STL, 12 gereksinim, marjlı sonuç |
| [Stres Testi](05-dogrulama-ve-test/stres-testi-sherpa.md) | **B5** — SHERPA Monte Carlo, 1 000 koşum |
| [Benchmark](05-dogrulama-ve-test/benchmark-moonplanbench.md) | **D2** — MoonPlanBench, 36 harita |
| [Simülasyon Motoru](05-dogrulama-ve-test/simulasyon-motoru.md) | Adım adım batarya, sıcaklık, zaman |
| [Profiller ve Senaryolar](05-dogrulama-ve-test/misyon-profilleri-ve-senaryolar.md) | Dört misyon profili, kısıt ayrımı |
| [Rota Analizi ve Rapor](05-dogrulama-ve-test/rota-analizi-ve-misyon-raporu.md) | GO / GO-WITH-RISK / NO-GO kararı |
| [Dış Referans Doğrulamaları](05-dogrulama-ve-test/dis-referans-dogrulamalari.md) | LOLA, Diviner, gerçek misyon rakamları |

## 06 · AI Asistanı

| Dosya | Feature |
|---|---|
| [AI Mimarisi](06-ai-asistani/ai-mimarisi-k1-k5.md) | K2→K3→K1→K4→K5 sabit boru hattı |
| [Güvenlik ve Grounding](06-ai-asistani/ai-guvenlik-ve-grounding.md) | Sayı uydurmanın nasıl engellendiği |
| [Araçlar ve Ürün Rehberi](06-ai-asistani/ai-araclar-ve-urun-rehberi.md) | Yetki sınırı, kapalı kayıt |

## 07 · Arayüz ve Altyapı

| Dosya | Feature |
|---|---|
| [ROS 2 Katmanı](07-arayuz-ve-altyapi/ros2-katmani.md) | Dört düğüm, gerçek rover yazılımına köprü |
| [Frontend ve 3-D](07-arayuz-ve-altyapi/frontend-ve-3d-goruntuleme.md) | 35+ özellik modülü, JSON/binary iki yol |
| [API ve Serileştirme](07-arayuz-ve-altyapi/api-yuzeyi-ve-serilestirme.md) | 33 uç, üç koordinat sistemi |

---

## Özellik matrisi kodları

Bu proje, 12 ileri özelliği bir matris altında geliştirdi. Kodları jüri sorularında geçebilir:

| Kod | Feature | Dosya |
|---|---|---|
| **A1** | Safe Haven | [→](04-planlama-ve-maliyet/safe-haven.md) |
| **A2** | Sürekli-aydınlık koridoru | [→](02-isik-golge-ve-termal/aydinlik-koridoru.md) |
| **A4** | Dünya görünürlüğü (DTE) | [→](03-konum-ve-iletisim/dunya-gorunurlugu-dte.md) |
| **B1** | Reach-avoid kurtarma politikası | [→](04-planlama-ve-maliyet/survival-reach-avoid.md) |
| **B2** | CVaR risk-farkında maliyet | [→](04-planlama-ve-maliyet/cvar-risk.md) |
| **B3** | DEM belirsizliği (100 klon) | [→](01-arazi-ve-veri/dem-belirsizligi-100-klon.md) |
| **B5** | SHERPA Monte Carlo stres testi | [→](05-dogrulama-ve-test/stres-testi-sherpa.md) |
| **C3** | Slip eğrisinin çapalanması | [→](04-planlama-ve-maliyet/slip-modeli.md) |
| **C4** | Ölçülmüş pürüzlülük + PSR | [→](01-arazi-ve-veri/puruzluluk-ve-psr.md) |
| **C6** | Termal operasyon zarfı | [→](02-isik-golge-ve-termal/termal-dwell-ve-operasyon-zarfi.md) |
| **D2** | Dış benchmark (MoonPlanBench) | [→](05-dogrulama-ve-test/benchmark-moonplanbench.md) |
| **D3** | FRETISH + STL monitörü | [→](05-dogrulama-ve-test/safety-monitor-stl-fretish.md) |

---

## Sunumda kullanılabilecek en güçlü üç cümle

1. **"Dünya görünürlüğü katmanımız NASA'nın 18,6 yıllık LOLA ürünüyle doğrulandı: RMSE 0,087, Pearson r 0,960."**
   → Modellenmiş bir katmanın ölçülmüş bir ürüne bağlandığı tek yer. [A4](03-konum-ve-iletisim/dunya-gorunurlugu-dte.md)

2. **"Belirsizlik nicelenmiştir; enerji tüketimi %90 güven bandıyla veriliyor."**
   → NASA'nın kendi 100 DEM klonuyla. [B3](01-arazi-ve-veri/dem-belirsizligi-100-klon.md)

3. **"VIPER ile aynı safe-haven ve 50 saat kuralını uyguluyoruz."**
   → NASA'nın yayınlanmış tanımının birebir uygulaması. [A1](04-planlama-ve-maliyet/safe-haven.md)

---

## Sunumda ASLA söylenmemesi gerekenler

| ❌ Söylenmez | ✅ Doğrusu |
|---|---|
| "Slip modelimiz ölçüldü" | "Uçmuş misyon verisine **bağlandı**" — kutup regolitinde ölçüm yok |
| "Kaya haritamız var" | Pürüzlülük bir kaya sayımı değil, istatistiksel yayılım |
| "Diviner kaya bolluğu kullanıyoruz" | O ürün 80–90° Güney'i kapsamıyor, kullanılmadı |
| "Model checking ile ispatladık" | **Çalışma zamanı izleme** — yalnız somut izler denetleniyor |
| "FRET aracıyla üretildi" | Cümleler FRETISH gramerini **elle** izliyor |
| "Rotamız güvenli" | VIPER rotası koşumların %70'inde bataryadan düşüyor |
| "Termal modelimiz doğru" | `MODEL / UNCALIBRATED` — Diviner doğrulaması yapılmadı |
| "Gerçek yüzey rover'ı hiç gölgelemez" | Model içinde garanti var; %10,8 hücre klonlar arası kararsız |

---

## Bilinen açıklar (soru gelirse dürüstçe söylenecek)

| Açık | Nerede anlatılıyor |
|---|---|
| Planlayıcı, dilim yuvarlamasından doğan boş zamanda bataryayı düşmüyor (VIPER min SOC %32 değil %23) | [B5](05-dogrulama-ve-test/stres-testi-sherpa.md) |
| B1'in kurtarma politikası ay gecesinde sabit plandan daha çok batarya arızası üretti (1000 koşumun 38'i) | [B1](04-planlama-ve-maliyet/survival-reach-avoid.md) |
| Termal ofset modeli sınırda eser üretiyor (13 "sıcak-sınırlı" kutu aslında model eseri) | [C6](02-isik-golge-ve-termal/termal-dwell-ve-operasyon-zarfi.md) |
| CVaR, dört çiftin ikisinde nominal rotayı kuyrukta daha ucuz buluyor | [B2](04-planlama-ve-maliyet/cvar-risk.md) |
| `summary.total_shadow_exposure` alanının birimi hiçbir yerde tanımlı değil | [Simülasyon](05-dogrulama-ve-test/simulasyon-motoru.md) |
| Diviner termal doğrulaması yapılamadı (veri yerelde yok) | [Dış doğrulamalar](05-dogrulama-ve-test/dis-referans-dogrulamalari.md) |

---

## Kaynak dokümanlar

Bu bilgi tabanı şunlardan derlendi (ve hepsi kod okunarak doğrulandı):

- `backend/app/*.py` — modül dokümanları ve kaynak kodu
- `BACKEND_ENHANCE_OZET.md` — 12 özelliğin ölçüm raporları
- `docs/BACKEND_ENVANTER.md` — API envanteri
- `docs/research/*.md` — özellik başına ölçüm raporları
- `docs/requirements/` — FRETISH gereksinim katalogu
