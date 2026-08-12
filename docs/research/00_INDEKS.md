# LunaPath — Gerçekleştirme (Productionization) Araştırma Seti

> **Amaç:** LunaPath'i "hackathon prototipi"nden savunulabilir bir **mühendislik ürünü / araştırma aracı**na taşımak için gereken teknik boşlukları, sektör karşılıklarını ve somut yol haritalarını belgelemek.
>
> **Kapsam kararı:** Bu belgeler mevcut kodu değiştirmez. Her belge (a) LunaPath'te bugün ne var, (b) sektör/literatür ne yapıyor, (c) aradaki boşluk, (d) kapatma reçetesi biçiminde yazılmıştır.
>
> **Tarih:** 10 Ağustos 2026 · **Referans kod tabanı:** `main` @ `3e22809`

---

## Belgeler

| # | Belge | Konu | Ana çıktı |
|---|---|---|---|
| 01 | [Sektörel projelerde veriler](01_sektorel_veri_kaynaklari.md) | Gerçek misyon verisi, PDS4, veri yönetişimi, ECSS veri gereksinimleri | Veri omurgası spesifikasyonu + data contract |
| 02 | [Görüntü işleme](02_goruntu_isleme.md) | LROC NAC, SfS/fotoklinometri, kaya/krater tespiti, stereo, VO | Görüntü katmanı entegrasyon planı |
| 03 | [Sentetik & minimum veri](03_sentetik_minimum_veri.md) | Sentetik veri ne zaman meşru, minimum veri omurgası, sim2real | "Sentetik" etiketleme protokolü + ablasyon planı |
| 04 | [Açık kaynak modeller](04_acik_kaynak_modeller.md) | Araç zinciri, simülatörler, foundation model'ler, lisans | Bağımlılık ve model seçim matrisi |
| 05 | [Engel kaçınma](05_engel_kacinma.md) | Hazard detection, yerel planlayıcı, GESTALT/ENav, slip | İki katmanlı navigasyon mimarisi |
| 06 | [Radyasyon verisi](06_radyasyon_verisi.md) | CRaTER, LND, GCR/SEP, TID/SEU, maliyet katmanına ekleme | Radyasyon katmanı ve karar kuralları |
| 07 | [Termal veri](07_termal_veri.md) | Diviner ürünleri, termofiziksel modeller, sentetik gridin yerine ne gelir | Termal katman geçiş planı (sentetik → ölçüm) |
| 08 | [Global/local rotalama yükü](08_global_local_rotalama_yuku.md) | Hiyerarşik planlama, hesap bütçesi, uçuş bilgisayarı, latency | Hesaplama bütçesi ve mimari ayrıştırma |
| 09 | [Olgunluk kıyaslama](09_olgunluk_kiyaslama.md) | TRL, benzer projeler, LunaPath nerede duruyor | Olgunluk skorkartı + 3 aşamalı hedef |
| 10 | [Sektörel projeler envanteri](10_sektorel_projeler_envanteri.md) | Gerçek projeler: GitHub depoları, NASA/ESA araçları, şirketler, akademik planlayıcılar | Kim-ne-kullandı envanteri + ödünç alınacak 10 şey + atıf listesi |

---

## Bu setin çıkardığı 10 kritik bulgu

1. **En büyük tek zayıflık termal katmandır.** `thermal_grid.py` elevasyondan lineer bir sıcaklık uydurur; gerçek ölçüm (Diviner) mevcut ve indirilebilir. Bu, projenin en kolay kapatılabilir en büyük açığıdır → [07](07_termal_veri.md).
2. **Gölge modeli de proxy.** `shadow_ratio = 1 - elev_norm` fiziksel olarak yanlıştır (elevasyon gölgenin nedeni değil, sonucudur). NASA'nın hazır illumination/PSR ürünleri 20–240 m çözünürlükte mevcut → [01](01_sektorel_veri_kaynaklari.md), [07](07_termal_veri.md).
3. **Zaman ekseni yok.** Sistem statik bir snapshot üzerinde planlıyor. Kutup aydınlanması saatlik değişir; gerçek problem **zaman-uzay (spatiotemporal)** planlamadır → [08](08_global_local_rotalama_yuku.md).
4. **Yerel katman hiç yok.** Sadece global planlayıcı var. 80 m/px grid'de bir kaya görünmez; gerçek rover'ları öldüren şey 30 cm'lik kayadır → [05](05_engel_kacinma.md).
5. **Görüntü işleme sıfır.** Projede tek bir görüntü tabanlı ürün yok; oysa LROC NAC 1 m/px mozaikleri ve SfS 5 m/px DEM'leri ücretsiz → [02](02_goruntu_isleme.md).
6. **Radyasyon tamamen eksik** ama LunaPath'in "donanım sağlığı" iddiası varken bu ciddi bir boşluk. Ekleme maliyeti düşük (skaler + SEP olay senaryosu) → [06](06_radyasyon_verisi.md).
7. **Sentetik veri kötü değil, etiketlenmemiş sentetik veri kötüdür.** ECSS-E-HB-40-02A sentetik veri kullanımını yasaklamıyor; izlenebilirlik ve temsil edicilik kanıtı istiyor → [03](03_sentetik_minimum_veri.md).
8. **Açık kaynak yığın hazır.** OmniLRS, POLAR, LuSNAR, heat1d, ASP/ISIS, SpiceyPy — sıfırdan yazılacak hiçbir şey yok → [04](04_acik_kaynak_modeller.md).
9. **Hesap bütçesi hiç konuşulmamış.** Bugünkü A* bir masaüstünde çalışıyor; RAD750 sınıfı bir uçuş bilgisayarında ~1000× daha az bütçe var. Bu, mimariyi belirleyen kısıttır → [08](08_global_local_rotalama_yuku.md).
10. **Konumlandırma netleşmeli.** LunaPath bugün TRL 3 civarı bir **görev öncesi planlama / karar destek** aracıdır. Bunu net söylemek onu zayıflatmaz, güçlendirir → [09](09_olgunluk_kiyaslama.md).
11. **NASA'nın kendi traverse planlama araçları zaten var ve ücretsiz** (Moon Trek, xGDS) — LunaPath'in ayrışması gereken yer geometri değil, **fizik-temelli çok kriterli maliyet**. Ayrıca ETH'nin MIT lisanslı `lunar_planner`'ı ve Lunar Autonomy Challenge birincisinin açık kodu doğrudan incelenebilir → [10](10_sektorel_projeler_envanteri.md).

---

## Önerilen okuma sırası

- **Ekip lideri / sunum:** 09 → 00 (bu belge) → 01
- **Veri kişisi (P1):** 01 → 07 → 03 → 02
- **Planlayıcı kişisi (P3):** 08 → 05 → 07
- **Backend (P4):** 08 → 01 (data contract) → 04
- **Frontend (P5):** 02 (görselleştirme) → 09 (skorkart)

---

## Ortak varsayım defteri

Bu setteki tüm belgeler şu ortak varsayımlar üzerine kuruludur. Değişirlerse ilgili belge güncellenmelidir.

| Varsayım | Değer | Kaynak |
|---|---|---|
| Hedef bölge | Ay güney kutbu, 80°S–90°S | `lunapath/data/processed/metadata.json` |
| Mevcut DEM | `LDEM_80S_80MPP_ADJ.tiff`, 80 m/px | `process_lunar_data.py:45` |
| Çalışma penceresi | 500×500 px = 40 km × 40 km | `metadata.json` |
| CRS | Moon (2015) Sphere, South Polar Stereographic, R=1737400 m | `metadata.json` |
| Rover kataloğu | **4 profil**: `lpr_1` (varsayılan), `luvmi_m`, `viper`, `yutu_2` | `backend/app/constants.py:14` |
| Varsayılan rover | LPR-1 (VIPER/MoonRanger türevi, kurgusal) | `constants.py:15` |
| Rover kütlesi / hız (LPR-1) | 450 kg / 0.2 m/s | `constants.py:17-18` |
| Batarya (LPR-1) | 5420 Wh | `constants.py:21` |
| Maliyet ağırlıkları | [0.409, 0.259, 0.142, 0.190] | `metadata.json` |
