Bu bilgi tabanında tek bir dosya var:
"LunaPath — Birleşik Araştırma Kütüphanesi" (11 araştırma belgesi, BELGE 00–10).

Cevap vermeden önce:
1. Dosyanın başındaki "SORU → BELGE YÖNLENDİRME TABLOSU"ndan ilgili belgeyi bul.
2. Teknik terim geçiyorsa "TERİM → BELGE İNDEKSİ"nden birincil belgeyi doğrula.
3. Cevabında hangi belgeye dayandığını "(BELGE 07 §3)" biçiminde belirt.

Kurallar:
- "Bugün LunaPath'te var olan" ile "önerilen" ayrımını asla karıştırma.
- Sayısal parametreler için BELGE 00'daki Ortak Varsayım Defteri'ni kaynak al.
- BELGE 10'daki depo/proje bilgileri değişkendir; kesin konuşma, teyit gerektiğini söyle.
- LunaPath'i TRL 3 civarı görev öncesi planlama/karar destek aracı olarak konumlandır;
  fazla iddiadan kaçın.


# LunaPath — Birleşik Araştırma Kütüphanesi

> **Bu dosya nedir:** LunaPath "gerçekleştirme (productionization)" araştırma setinin **11 belgesinin tamamının tek dosyada birleştirilmiş hâli**. 
> Amaç: Claude proje bağlamına (project knowledge) tek parça hâlinde yüklenip **hiçbir bilgi kaybı olmadan** bütün olarak okunabilmesi.
>
> **İçerik birebir korunmuştur.** Hiçbir cümle özetlenmedi, kısaltılmadı, silinmedi. Tablolar, kod blokları, bağlantılar ve kaynakça listeleri olduğu gibi aktarıldı.
>
> **Yapılan tek değişiklik biçimseldir:**
> 1. Her belgenin `#` (H1) başlığı, birleşik dosyada `##` (H2) düzeyinde bir *belge bölümü* başlığına dönüştürüldü; belge içi tüm başlıklar 1 kademe indirildi (H2→H3, H3→H4). Kod bloklarının içindeki `#` yorum satırlarına dokunulmadı.
> 2. Belgeler arası bağlantılar (`07_termal_veri.md` gibi) dosya-içi çapalara (`#belge-07`) çevrildi; artık tek dosya içinde çalışıyorlar.
> 3. Her belgenin üst düzey bölüm başlığına, parçalı okuma (RAG) hâlinde bile kaynağı belli olsun diye `[B07]` biçiminde bir **belge etiketi** eklendi.
> 4. Belge içeriklerinin **öncesine** bir navigasyon katmanı (yönlendirme tablosu, terim→belge indeksi, ayrıntılı içindekiler) eklendi.
>
> **Kaynak belgeler:** `00_INDEKS.md` … `10_sektorel_projeler_envanteri.md` (11 dosya) · **Belge tarihi:** 10 Ağustos 2026 · **Referans kod tabanı:** `main` @ `3e22809`

---

<a id="kullanim"></a>

## NASIL KULLANILIR — asistan için okuma talimatı

Bu dosya bir **referans kütüphanesidir**, düz baştan sona okunacak bir anlatı değil. Bir soru geldiğinde izlenecek yol:

1. **Önce yönlendirme tablosuna bak** (aşağıdaki *SORU → BELGE* tablosu). Soru hangi belgenin alanına giriyor?
2. **Terim indeksinden doğrula.** Soruda geçen teknik terimi (`Diviner`, `RAD750`, `GESTALT`, `PSR`, `sim2real` …) terim indeksinde ara; terimin en yoğun geçtiği belge büyük ihtimalle doğru belgedir.
3. **İlgili belge bölümüne git** (`BELGE 07` gibi) ve o belgenin *Kısa cevap* bloğunu oku — her belge, kendi sorusunun cevabını ilk paragrafta özetler.
4. **Çapraz bağlantıları izle.** Belgeler birbirine `#belge-08` biçiminde atıf yapar; bir konu neredeyse her zaman iki belgede birden ele alınmıştır (örn. termal → `BELGE 07` + `BELGE 03`; hesap yükü → `BELGE 08` + `BELGE 05`).

**Uyulması gereken kurallar:**

- Bu belgeler **mevcut kodu değiştirmez**; her biri (a) LunaPath'te bugün ne var, (b) sektör/literatür ne yapıyor, (c) aradaki boşluk, (d) kapatma reçetesi yapısındadır. Bir öneriyi aktarırken bu dört katmanı karıştırma — özellikle *bugün var olan* ile *önerilen* ayrımını koru.
- `BELGE 10` içindeki proje/depo bilgileri açık web kaynaklarından derlenmiştir ve **değişkendir** (yıldız sayısı, sürüm, misyon tarihi). Kesin ifade kurmadan önce bağlantıdan teyit gerektiğini belirt.
- Sayısal parametreler (rover kütlesi, batarya, ağırlıklar, çözünürlük) için **Ortak Varsayım Defteri**ni kaynak al; belge metinlerinde geçen türetilmiş sayılar bu defterden hesaplanmıştır.
- Bir iddiayı savunurken belgenin *olgunluk* çerçevesine sadık kal: LunaPath bugün **TRL 3 civarı bir görev öncesi planlama / karar destek aracıdır** (`BELGE 09`). Fazla iddia etmek bu setin açıkça uyardığı ana risktir.

---

<a id="yonlendirme"></a>

## SORU → BELGE YÖNLENDİRME TABLOSU

| Belge | Başlık | Hangi soruları cevaplar | Ana çıktı | Ayırt edici terimler |
|---|---|---|---|---|
| [**B00**](#belge-00) | LunaPath — Gerçekleştirme (Productionization) Araştırma Seti | İndeks, ortak varsayımlar, 11 kritik bulgu | Setin haritası ve okuma sırası | `uçuş bilgisayarı`, `hesap bütçesi`, `data contract` |
| [**B01**](#belge-01) | 01 — Sektörel Projelerde Veriler | Gerçek misyon verisi, PDS4, veri yönetişimi, ECSS veri gereksinimleri | Veri omurgası spesifikasyonu + data contract | `PGDA`, `LOLA`, `illumination`, `ECSS`, `LROC`, `PDS4` |
| [**B02**](#belge-02) | 02 — Görüntü İşleme | LROC NAC, SfS/fotoklinometri, kaya/krater tespiti, stereo, VO | Görüntü katmanı entegrasyon planı | `kaya`, `NAC`, `POLAR`, `stereo`, `krater`, `SfS`, `sim2real` |
| [**B03**](#belge-03) | 03 — Sentetik ve Minimum Veri | Sentetik veri ne zaman meşru, minimum veri omurgası, sim2real | "Sentetik" etiketleme protokolü + ablasyon planı | `ECSS`, `sim2real`, `RMSE`, `Prithvi` |
| [**B04**](#belge-04) | 04 — Açık Kaynak Model ve Araç Ekosistemi | Araç zinciri, simülatörler, foundation model'ler, lisans | Bağımlılık ve model seçim matrisi | `lisans`, `SPICE`, `OmniLRS`, `Apache`, `heat1d`, `cFS`, `TerraTorch` |
| [**B05**](#belge-05) | 05 — Engel Kaçınma | Hazard detection, yerel planlayıcı, GESTALT/ENav, slip | İki katmanlı navigasyon mimarisi | `slip`, `D* Lite`, `traversability`, `GESTALT`, `ENav`, `CADRE`, `Yutu-2` |
| [**B06**](#belge-06) | 06 — Radyasyon Verisi | CRaTER, LND, GCR/SEP, TID/SEU, maliyet katmanına ekleme | Radyasyon katmanı ve karar kuralları | `SEP`, `radyasyon`, `SVF`, `GCR`, `TID`, `CRaTER`, `LND` |
| [**B07**](#belge-07) | 07 — Termal Veri | Diviner ürünleri, termofiziksel modeller, sentetik gridin yerine ne gelir | Termal katman geçiş planı (sentetik → ölçüm) | `Diviner`, `regolit`, `PSR`, `heat1d`, `regolith`, `lumped capacitance`, `batarya` |
| [**B08**](#belge-08) | 08 — Global / Local Rotalandırma ve Hesaplama Yükü | Hiyerarşik planlama, hesap bütçesi, uçuş bilgisayarı, latency | Hesaplama bütçesi ve mimari ayrıştırma | `HPSC`, `RAD750`, `uçuş bilgisayarı` |
| [**B09**](#belge-09) | 09 — Sektörel Projelerin Olgunluğu ve Kıyaslama | TRL, benzer projeler, LunaPath nerede duruyor | Olgunluk skorkartı + 3 aşamalı hedef | `TRL`, `VIPER`, `kredibilite`, `Yutu-2`, `CADRE`, `NASA-STD-7009`, `lumped capacitance` |
| [**B10**](#belge-10) | 10 — Sektörel Ay Rota Planlama Projeleri Envanteri | Gerçek projeler: GitHub depoları, NASA/ESA araçları, şirketler, akademik planlayıcılar | Kim-ne-kullandı envanteri + ödünç alınacak 10 şey + atıf listesi | `ROS`, `SLAM`, `MAPP`, `xGDS`, `VIPER`, `MoonRanger`, `MMGIS` |

**Rol bazlı okuma sırası** (kaynak indeksten):

- **Ekip lideri / sunum:** `BELGE 09` → `BELGE 00` → `BELGE 01`
- **Veri kişisi (P1):** `BELGE 01` → `BELGE 07` → `BELGE 03` → `BELGE 02`
- **Planlayıcı kişisi (P3):** `BELGE 08` → `BELGE 05` → `BELGE 07`
- **Backend (P4):** `BELGE 08` → `BELGE 01` (data contract) → `BELGE 04`
- **Frontend (P5):** `BELGE 02` (görselleştirme) → `BELGE 09` (skorkart)

---

<a id="terim-indeksi"></a>

## TERİM → BELGE İNDEKSİ

Bir terimin hangi belgelerde, kaç kez geçtiği. İlk sıradaki belge o terimin **birincil kaynağıdır**. (Otomatik sayım; büyük/küçük harf duyarsız.)

| Terim | Belgeler (geçiş sayısı) |
|---|---|
| `termal` | [B07](#belge-07) (22) · [B09](#belge-09) (20) · [B03](#belge-03) (19) · [B10](#belge-10) (11) · [B06](#belge-06) (10) · [B04](#belge-04) (9) |
| `DEM` | [B01](#belge-01) (21) · [B02](#belge-02) (19) · [B10](#belge-10) (14) · [B09](#belge-09) (12) · [B05](#belge-05) (8) · [B03](#belge-03) (7) |
| `A*` | [B10](#belge-10) (21) · [B08](#belge-08) (19) · [B05](#belge-05) (13) · [B04](#belge-04) (11) · [B09](#belge-09) (7) · [B01](#belge-01) (5) |
| `gölge` | [B02](#belge-02) (21) · [B07](#belge-07) (19) · [B03](#belge-03) (15) · [B05](#belge-05) (8) · [B01](#belge-01) (4) · [B09](#belge-09) (4) |
| `Diviner` | [B07](#belge-07) (35) · [B01](#belge-01) (12) · [B03](#belge-03) (12) · [B09](#belge-09) (6) · [B10](#belge-10) (4) · [B00](#belge-00) (2) |
| `kaya` | [B02](#belge-02) (31) · [B07](#belge-07) (10) · [B04](#belge-04) (7) · [B10](#belge-10) (6) · [B00](#belge-00) (3) · [B05](#belge-05) (2) |
| `POLAR` | [B02](#belge-02) (18) · [B10](#belge-10) (12) · [B03](#belge-03) (7) · [B04](#belge-04) (6) · [B00](#belge-00) (3) · [B01](#belge-01) (3) |
| `ROS` | [B10](#belge-10) (30) · [B04](#belge-04) (5) · [B09](#belge-09) (5) · [B05](#belge-05) (3) · [B02](#belge-02) (1) · [B03](#belge-03) (1) |
| `stereo` | [B02](#belge-02) (14) · [B10](#belge-10) (12) · [B05](#belge-05) (7) · [B04](#belge-04) (4) · [B01](#belge-01) (3) · [B00](#belge-00) (2) |
| `illumination` | [B01](#belge-01) (14) · [B03](#belge-03) (9) · [B07](#belge-07) (6) · [B09](#belge-09) (5) · [B04](#belge-04) (3) · [B06](#belge-06) (3) |
| `LOLA` | [B01](#belge-01) (20) · [B03](#belge-03) (7) · [B09](#belge-09) (6) · [B02](#belge-02) (3) · [B07](#belge-07) (3) · [B10](#belge-10) (3) |
| `SEP` | [B06](#belge-06) (33) · [B00](#belge-00) (2) · [B03](#belge-03) (2) · [B09](#belge-09) (2) · [B05](#belge-05) (1) · [B10](#belge-10) (1) |
| `radyasyon` | [B06](#belge-06) (25) · [B00](#belge-00) (5) · [B03](#belge-03) (3) · [B05](#belge-05) (2) · [B07](#belge-07) (2) · [B09](#belge-09) (2) |
| `aydınlanma` | [B10](#belge-10) (10) · [B07](#belge-07) (5) · [B01](#belge-01) (4) · [B02](#belge-02) (4) · [B03](#belge-03) (4) · [B04](#belge-04) (4) |
| `NAC` | [B02](#belge-02) (21) · [B00](#belge-00) (3) · [B04](#belge-04) (3) · [B01](#belge-01) (2) · [B05](#belge-05) (2) · [B09](#belge-09) (2) |
| `PGDA` | [B01](#belge-01) (26) · [B02](#belge-02) (7) · [B04](#belge-04) (1) |
| `PSR` | [B07](#belge-07) (10) · [B01](#belge-01) (7) · [B09](#belge-09) (4) · [B03](#belge-03) (3) · [B05](#belge-05) (3) · [B10](#belge-10) (3) |
| `SLAM` | [B10](#belge-10) (14) · [B02](#belge-02) (6) · [B09](#belge-09) (5) · [B00](#belge-00) (3) · [B04](#belge-04) (1) · [B05](#belge-05) (1) |
| `lisans` | [B04](#belge-04) (15) · [B01](#belge-01) (5) · [B10](#belge-10) (5) · [B00](#belge-00) (2) · [B06](#belge-06) (1) · [B09](#belge-09) (1) |
| `regolit` | [B07](#belge-07) (13) · [B06](#belge-06) (6) · [B05](#belge-05) (5) · [B02](#belge-02) (2) · [B04](#belge-04) (2) · [B03](#belge-03) (1) |
| `krater` | [B02](#belge-02) (13) · [B06](#belge-06) (6) · [B09](#belge-09) (2) · [B10](#belge-10) (2) · [B00](#belge-00) (1) · [B01](#belge-01) (1) |
| `ECSS` | [B01](#belge-01) (13) · [B03](#belge-03) (9) · [B00](#belge-00) (2) · [B04](#belge-04) (1) |
| `VIPER` | [B10](#belge-10) (10) · [B09](#belge-09) (8) · [B00](#belge-00) (2) · [B02](#belge-02) (1) · [B03](#belge-03) (1) · [B05](#belge-05) (1) |
| `SVF` | [B06](#belge-06) (22) · [B07](#belge-07) (1) · [B09](#belge-09) (1) |
| `heat1d` | [B04](#belge-04) (9) · [B07](#belge-07) (9) · [B10](#belge-10) (4) · [B00](#belge-00) (1) · [B09](#belge-09) (1) |
| `TRL` | [B09](#belge-09) (16) · [B10](#belge-10) (4) · [B00](#belge-00) (2) |
| `traversability` | [B05](#belge-05) (7) · [B01](#belge-01) (6) · [B02](#belge-02) (4) · [B09](#belge-09) (3) · [B03](#belge-03) (1) · [B10](#belge-10) (1) |
| `HPSC` | [B08](#belge-08) (15) · [B04](#belge-04) (5) · [B09](#belge-09) (1) |
| `SfS` | [B02](#belge-02) (9) · [B01](#belge-01) (3) · [B10](#belge-10) (3) · [B00](#belge-00) (2) · [B04](#belge-04) (2) · [B03](#belge-03) (1) |
| `OmniLRS` | [B04](#belge-04) (11) · [B10](#belge-10) (6) · [B00](#belge-00) (1) · [B02](#belge-02) (1) · [B05](#belge-05) (1) |
| `SPICE` | [B04](#belge-04) (14) · [B07](#belge-07) (4) · [B00](#belge-00) (1) · [B09](#belge-09) (1) |
| `TID` | [B06](#belge-06) (9) · [B05](#belge-05) (3) · [B09](#belge-09) (3) · [B00](#belge-00) (1) · [B03](#belge-03) (1) · [B08](#belge-08) (1) |
| `VO` | [B10](#belge-10) (7) · [B02](#belge-02) (5) · [B05](#belge-05) (4) · [B00](#belge-00) (1) · [B08](#belge-08) (1) |
| `GCR` | [B06](#belge-06) (15) · [B00](#belge-00) (1) |
| `LuSNAR` | [B04](#belge-04) (6) · [B02](#belge-02) (5) · [B10](#belge-10) (4) · [B00](#belge-00) (1) |
| `hazard` | [B02](#belge-02) (7) · [B03](#belge-03) (3) · [B05](#belge-05) (2) · [B08](#belge-08) (2) · [B00](#belge-00) (1) · [B01](#belge-01) (1) |
| `sim2real` | [B02](#belge-02) (7) · [B03](#belge-03) (6) · [B00](#belge-00) (1) · [B04](#belge-04) (1) |
| `slip` | [B05](#belge-05) (12) · [B00](#belge-00) (1) · [B02](#belge-02) (1) · [B09](#belge-09) (1) |
| `CADRE` | [B10](#belge-10) (6) · [B05](#belge-05) (4) · [B09](#belge-09) (4) |
| `MAPP` | [B10](#belge-10) (13) · [B07](#belge-07) (1) |
| `CRaTER` | [B06](#belge-06) (8) · [B00](#belge-00) (1) · [B01](#belge-01) (1) · [B02](#belge-02) (1) · [B03](#belge-03) (1) · [B07](#belge-07) (1) |
| `LUVMI` | [B10](#belge-10) (8) · [B09](#belge-09) (2) · [B00](#belge-00) (1) · [B02](#belge-02) (1) · [B07](#belge-07) (1) |
| `cFS` | [B04](#belge-04) (9) · [B10](#belge-10) (3) · [B08](#belge-08) (1) |
| `Apache` | [B04](#belge-04) (10) · [B10](#belge-10) (2) |
| `LROC` | [B01](#belge-01) (6) · [B02](#belge-02) (4) · [B00](#belge-00) (2) |
| `MoonRanger` | [B10](#belge-10) (10) · [B00](#belge-00) (1) · [B03](#belge-03) (1) |
| `ablasyon` | [B03](#belge-03) (3) · [B07](#belge-07) (3) · [B09](#belge-09) (3) · [B00](#belge-00) (1) · [B01](#belge-01) (1) |
| `maliyet fonksiyonu` | [B01](#belge-01) (3) · [B08](#belge-08) (3) · [B06](#belge-06) (2) · [B09](#belge-09) (2) · [B02](#belge-02) (1) |
| `xGDS` | [B10](#belge-10) (10) · [B00](#belge-00) (1) |
| `D* Lite` | [B05](#belge-05) (8) · [B04](#belge-04) (1) · [B08](#belge-08) (1) |
| `SpiceyPy` | [B04](#belge-04) (7) · [B00](#belge-00) (1) · [B07](#belge-07) (1) · [B09](#belge-09) (1) |
| `MMGIS` | [B10](#belge-10) (9) |
| `Moon Trek` | [B10](#belge-10) (8) · [B00](#belge-00) (1) |
| `RAD750` | [B08](#belge-08) (7) · [B00](#belge-00) (1) · [B09](#belge-09) (1) |
| `Yutu-2` | [B09](#belge-09) (4) · [B05](#belge-05) (3) · [B02](#belge-02) (1) · [B07](#belge-07) (1) |
| `regolith` | [B07](#belge-07) (6) · [B03](#belge-03) (1) · [B04](#belge-04) (1) · [B05](#belge-05) (1) |
| `PDS4` | [B01](#belge-01) (4) · [B04](#belge-04) (2) · [B00](#belge-00) (1) · [B07](#belge-07) (1) |
| `lunar_planner` | [B10](#belge-10) (7) · [B00](#belge-00) (1) |
| `ENav` | [B05](#belge-05) (5) · [B00](#belge-00) (1) · [B01](#belge-01) (1) |
| `GESTALT` | [B05](#belge-05) (6) · [B00](#belge-00) (1) |
| `LND` | [B06](#belge-06) (5) · [B00](#belge-00) (1) · [B03](#belge-03) (1) |
| `Nav2` | [B04](#belge-04) (6) · [B10](#belge-10) (1) |
| `Prithvi` | [B04](#belge-04) (5) · [B03](#belge-03) (2) |
| `RMSE` | [B07](#belge-07) (3) · [B03](#belge-03) (2) · [B09](#belge-09) (1) · [B10](#belge-10) (1) |
| `TerraTorch` | [B04](#belge-04) (7) |
| `hesap bütçesi` | [B00](#belge-00) (2) · [B02](#belge-02) (2) · [B05](#belge-05) (1) · [B09](#belge-09) (1) |
| `lumped capacitance` | [B07](#belge-07) (4) · [B09](#belge-09) (2) |
| `uçuş bilgisayarı` | [B08](#belge-08) (3) · [B00](#belge-00) (2) · [B02](#belge-02) (1) |
| `Lunar Autonomy Challenge` | [B10](#belge-10) (4) · [B00](#belge-00) (1) |
| `SEU` | [B06](#belge-06) (4) · [B00](#belge-00) (1) |
| `batarya` | [B07](#belge-07) (4) · [B00](#belge-00) (1) |
| `spatiotemporal` | [B10](#belge-10) (4) · [B00](#belge-00) (1) |
| `kredibilite` | [B09](#belge-09) (4) |
| `Ames Stereo Pipeline` | [B02](#belge-02) (1) · [B04](#belge-04) (1) · [B10](#belge-10) (1) |
| `NASA-STD-7009` | [B09](#belge-09) (3) |
| `OMPL` | [B04](#belge-04) (3) |
| `data contract` | [B00](#belge-00) (2) · [B01](#belge-01) (1) |
| `fotoklinometri` | [B02](#belge-02) (2) · [B00](#belge-00) (1) |

---

<a id="icindekiler"></a>

## AYRINTILI İÇİNDEKİLER

**[BELGE 00 — Gerçekleştirme (Productionization) Araştırma Seti](#belge-00)**  
  [Belgeler](#b00-s1) · [Bu setin çıkardığı 10 kritik bulgu](#b00-s2) · [Önerilen okuma sırası](#b00-s3) · [Ortak varsayım defteri](#b00-s4)

**[BELGE 01 — Sektörel Projelerde Veriler](#belge-01)**  
  [1. LunaPath'in mevcut veri durumu (dürüst envanter)](#b01-s1) · [2. Sektör gerçek misyonlarda ne kullanıyor?](#b01-s2) · [3. Sektörel veri disiplini: LunaPath'te olmayan 7 pratik](#b01-s3) · [4. Boşluk analizi ve öncelikli yol haritası](#b01-s4) · [5. Somut indirme rehberi](#b01-s5) · [6. Sektörel veri disiplinini standarda bağlama](#b01-s6) · [7. Kabul kriterleri (bu belgenin "bitti" tanımı)](#b01-s7) · [Kaynaklar](#b01-s8)

**[BELGE 02 — Görüntü İşleme](#belge-02)**  
  [1. İki ayrı görüntü işleme problemi — karıştırmayın](#b02-s1) · [2. Yol A — Yörünge görüntüsünden maliyet katmanı](#b02-s2) · [3. Yol B — Rover üzeri görüntü işleme (referans için)](#b02-s3) · [4. Boşluk analizi](#b02-s4) · [5. Yol haritası](#b02-s5) · [6. Sık yapılan hatalar (kontrol listesi)](#b02-s6) · [Kaynaklar](#b02-s7)

**[BELGE 03 — Sentetik ve Minimum Veri](#belge-03)**  
  [1. Sentetik verinin üç meşru kullanımı, bir gayrimeşru kullanımı](#b03-s1) · [2. Sentetik termal gridin teknik eleştirisi](#b03-s2) · [3. Minimum veri omurgası — yeniden tanımlanmış](#b03-s3) · [4. Sentetik veriyi savunulabilir yapan protokol](#b03-s4) · [5. Sim2real: sentetik görüntü/dinamik ile eğitim](#b03-s5) · [6. Boşluk analizi](#b03-s6) · [7. Yol haritası](#b03-s7) · [8. Kırmızı çizgiler (asla yapma)](#b03-s8) · [Kaynaklar](#b03-s9)

**[BELGE 04 — Açık Kaynak Model ve Araç Ekosistemi](#belge-04)**  
  [1. Mevcut bağımlılık envanteri (ve değerlendirmesi)](#b04-s1) · [2. Gezegen bilimi veri araç zinciri](#b04-s2) · [3. Termal modelleme — hazır açık kaynak](#b04-s3) · [4. Simülatörler — LunaPath'e ne kadar gerekli?](#b04-s4) · [5. Planlama ve navigasyon kütüphaneleri](#b04-s5) · [6. Uçuş yazılımı çatıları (uçuş iddiası kurarsanız)](#b04-s6) · [7. Açık kaynak ML modelleri](#b04-s7) · [8. Lisans, ihracat ve atıf](#b04-s8) · [9. Seçim matrisi — LunaPath için nihai öneri](#b04-s9) · [10. Yol haritası](#b04-s10) · [Kaynaklar](#b04-s11)

**[BELGE 05 — Engel Kaçınma](#belge-05)**  
  [1. Terminolojiyi netleştir (bu, sunumda en çok karışan yer)](#b05-s1) · [2. Gerçek rover'lar nasıl yapıyor?](#b05-s2) · [3. Ay kutbuna özel engel kaçınma zorlukları](#b05-s3) · [4. LunaPath için önerilen iki katmanlı mimari](#b05-s4) · [5. Boşluk analizi](#b05-s5) · [6. Yol haritası](#b05-s6) · [7. Kabul kriterleri](#b05-s7) · [Kaynaklar](#b05-s8)

**[BELGE 06 — Radyasyon Verisi](#belge-06)**  
  [1. Ay yüzeyi radyasyon ortamı — üç bileşen](#b06-s1) · [2. Gökyüzü görüş faktörü — DEM'den hesaplanabilir bir radyasyon katmanı](#b06-s2) · [3. SEP olay senaryosu — LunaPath'e en doğru radyasyon eklemesi](#b06-s3) · [4. Veri kaynakları ve modeller](#b06-s4) · [5. Elektronik etkileri — `health_score`'a nasıl girer](#b06-s5) · [6. Boşluk analizi](#b06-s6) · [7. Yol haritası](#b06-s7) · [8. Sunumda kullanılacak cümleler](#b06-s8) · [Kaynaklar](#b06-s9)

**[BELGE 07 — Termal Veri](#belge-07)**  
  [1. Mevcut termal zincirin eleştirisi](#b07-s1) · [2. Gerçek termal veri: LRO/Diviner](#b07-s2) · [3. Doğru model: tek düğümlü (lumped capacitance) termal denge](#b07-s3) · [4. Zaman ekseni: aydınlanmadan sıcaklığa](#b07-s4) · [5. Doğrulama planı — sentetiği gerçekle ölçmek](#b07-s5) · [6. Boşluk analizi](#b07-s6) · [7. Yol haritası](#b07-s7) · [8. Sunumda kullanılacak cümleler](#b07-s8) · [Kaynaklar](#b07-s9)

**[BELGE 08 — Global / Local Rotalandırma ve Hesaplama Yükü](#belge-08)**  
  [1. Bugünkü yükün anatomisi](#b08-s1) · [2. En yüksek getirili optimizasyon: maliyeti tamamen ön-hesapla](#b08-s2) · [3. Hiyerarşi: neden zorunlu, nasıl kurulur](#b08-s3) · [4. Nerede koşacak? Yer vs rover](#b08-s4) · [5. Anytime planlama: sert zaman limitiyle nasıl baş edilir](#b08-s5) · [6. Ölçüm planı (benchmark)](#b08-s6) · [7. Boşluk analizi](#b08-s7) · [8. Yol haritası](#b08-s8) · [9. Sunumda kullanılacak cümleler](#b08-s9) · [Kaynaklar](#b08-s10)

**[BELGE 09 — Sektörel Projelerin Olgunluğu ve Kıyaslama](#belge-09)**  
  [1. Doğru ölçek hangisi? TRL değil, model kredibilitesi](#b09-s1) · [2. Sektör manzarası — Ay yüzey otonomisi 2026 durumu](#b09-s2) · [3. Olgunluk skorkartı](#b09-s3) · [4. Üç aşamalı yükseltme planı](#b09-s4) · [5. Kıyaslama özeti — tek tabloda](#b09-s5) · [6. Sunum/rapor için hazır çerçeve](#b09-s6) · [7. Kabul kriterleri](#b09-s7) · [Kaynaklar](#b09-s8)

**[BELGE 10 — Sektörel Ay Rota Planlama Projeleri Envanteri](#belge-10)**  
  [Özet: manzaranın şekli](#b10-s1) · [A. Açık kaynak, doğrudan Ay rota planlama](#b10-s2) · [B. Kurum araçları (NASA / ESA)](#b10-s3) · [C. Ticari şirket projeleri (uçmuş / uçacak)](#b10-s4) · [D. Akademik planlayıcılar (LunaPath'in gerçek rakipleri)](#b10-s5) · [E. Yarışma: Lunar Autonomy Challenge (NASA + JHU/APL + Caterpillar)](#b10-s6) · [F. Planlama için altyapı: simülatörler, veri setleri, araçlar](#b10-s7) · [G. LunaPath vs sektör: kim ne kullanmış tablosu](#b10-s8) · [H. Doğrudan ödünç alınabilecek 10 şey (öncelik sıralı)](#b10-s9) · [I. Atıf listesi (yayın/rapor yazarken)](#b10-s10) · [Kaynaklar (bu belgede kullanılan tüm bağlantılar)](#b10-s11)

---

<a id="belge-00"></a>

## BELGE 00 — Gerçekleştirme (Productionization) Araştırma Seti

> **Belge kimliği:** `BELGE 00` (bölüm başlıklarında `[B00]` etiketiyle işaretlidir) · **Kaynak dosya:** `00_INDEKS.md`  
> **Konu:** İndeks, ortak varsayımlar, 11 kritik bulgu  
> **Ana çıktı:** Setin haritası ve okuma sırası  
> **Ayırt edici terimler:** `uçuş bilgisayarı`, `hesap bütçesi`, `data contract`

> **Amaç:** LunaPath'i "hackathon prototipi"nden savunulabilir bir **mühendislik ürünü / araştırma aracı**na taşımak için gereken teknik boşlukları, sektör karşılıklarını ve somut yol haritalarını belgelemek.
>
> **Kapsam kararı:** Bu belgeler mevcut kodu değiştirmez. Her belge (a) LunaPath'te bugün ne var, (b) sektör/literatür ne yapıyor, (c) aradaki boşluk, (d) kapatma reçetesi biçiminde yazılmıştır.
>
> **Tarih:** 10 Ağustos 2026 · **Referans kod tabanı:** `main` @ `3e22809`

---

<a id="b00-s1"></a>

### [B00] Belgeler

| # | Belge | Konu | Ana çıktı |
|---|---|---|---|
| 01 | [Sektörel projelerde veriler](#belge-01) | Gerçek misyon verisi, PDS4, veri yönetişimi, ECSS veri gereksinimleri | Veri omurgası spesifikasyonu + data contract |
| 02 | [Görüntü işleme](#belge-02) | LROC NAC, SfS/fotoklinometri, kaya/krater tespiti, stereo, VO | Görüntü katmanı entegrasyon planı |
| 03 | [Sentetik & minimum veri](#belge-03) | Sentetik veri ne zaman meşru, minimum veri omurgası, sim2real | "Sentetik" etiketleme protokolü + ablasyon planı |
| 04 | [Açık kaynak modeller](#belge-04) | Araç zinciri, simülatörler, foundation model'ler, lisans | Bağımlılık ve model seçim matrisi |
| 05 | [Engel kaçınma](#belge-05) | Hazard detection, yerel planlayıcı, GESTALT/ENav, slip | İki katmanlı navigasyon mimarisi |
| 06 | [Radyasyon verisi](#belge-06) | CRaTER, LND, GCR/SEP, TID/SEU, maliyet katmanına ekleme | Radyasyon katmanı ve karar kuralları |
| 07 | [Termal veri](#belge-07) | Diviner ürünleri, termofiziksel modeller, sentetik gridin yerine ne gelir | Termal katman geçiş planı (sentetik → ölçüm) |
| 08 | [Global/local rotalama yükü](#belge-08) | Hiyerarşik planlama, hesap bütçesi, uçuş bilgisayarı, latency | Hesaplama bütçesi ve mimari ayrıştırma |
| 09 | [Olgunluk kıyaslama](#belge-09) | TRL, benzer projeler, LunaPath nerede duruyor | Olgunluk skorkartı + 3 aşamalı hedef |
| 10 | [Sektörel projeler envanteri](#belge-10) | Gerçek projeler: GitHub depoları, NASA/ESA araçları, şirketler, akademik planlayıcılar | Kim-ne-kullandı envanteri + ödünç alınacak 10 şey + atıf listesi |

---

<a id="b00-s2"></a>

### [B00] Bu setin çıkardığı 10 kritik bulgu

1. **En büyük tek zayıflık termal katmandır.** `thermal_grid.py` elevasyondan lineer bir sıcaklık uydurur; gerçek ölçüm (Diviner) mevcut ve indirilebilir. Bu, projenin en kolay kapatılabilir en büyük açığıdır → [07](#belge-07).
2. **Gölge modeli de proxy.** `shadow_ratio = 1 - elev_norm` fiziksel olarak yanlıştır (elevasyon gölgenin nedeni değil, sonucudur). NASA'nın hazır illumination/PSR ürünleri 20–240 m çözünürlükte mevcut → [01](#belge-01), [07](#belge-07).
3. **Zaman ekseni yok.** Sistem statik bir snapshot üzerinde planlıyor. Kutup aydınlanması saatlik değişir; gerçek problem **zaman-uzay (spatiotemporal)** planlamadır → [08](#belge-08).
4. **Yerel katman hiç yok.** Sadece global planlayıcı var. 80 m/px grid'de bir kaya görünmez; gerçek rover'ları öldüren şey 30 cm'lik kayadır → [05](#belge-05).
5. **Görüntü işleme sıfır.** Projede tek bir görüntü tabanlı ürün yok; oysa LROC NAC 1 m/px mozaikleri ve SfS 5 m/px DEM'leri ücretsiz → [02](#belge-02).
6. **Radyasyon tamamen eksik** ama LunaPath'in "donanım sağlığı" iddiası varken bu ciddi bir boşluk. Ekleme maliyeti düşük (skaler + SEP olay senaryosu) → [06](#belge-06).
7. **Sentetik veri kötü değil, etiketlenmemiş sentetik veri kötüdür.** ECSS-E-HB-40-02A sentetik veri kullanımını yasaklamıyor; izlenebilirlik ve temsil edicilik kanıtı istiyor → [03](#belge-03).
8. **Açık kaynak yığın hazır.** OmniLRS, POLAR, LuSNAR, heat1d, ASP/ISIS, SpiceyPy — sıfırdan yazılacak hiçbir şey yok → [04](#belge-04).
9. **Hesap bütçesi hiç konuşulmamış.** Bugünkü A* bir masaüstünde çalışıyor; RAD750 sınıfı bir uçuş bilgisayarında ~1000× daha az bütçe var. Bu, mimariyi belirleyen kısıttır → [08](#belge-08).
10. **Konumlandırma netleşmeli.** LunaPath bugün TRL 3 civarı bir **görev öncesi planlama / karar destek** aracıdır. Bunu net söylemek onu zayıflatmaz, güçlendirir → [09](#belge-09).
11. **NASA'nın kendi traverse planlama araçları zaten var ve ücretsiz** (Moon Trek, xGDS) — LunaPath'in ayrışması gereken yer geometri değil, **fizik-temelli çok kriterli maliyet**. Ayrıca ETH'nin MIT lisanslı `lunar_planner`'ı ve Lunar Autonomy Challenge birincisinin açık kodu doğrudan incelenebilir → [10](#belge-10).

---

<a id="b00-s3"></a>

### [B00] Önerilen okuma sırası

- **Ekip lideri / sunum:** 09 → 00 (bu belge) → 01
- **Veri kişisi (P1):** 01 → 07 → 03 → 02
- **Planlayıcı kişisi (P3):** 08 → 05 → 07
- **Backend (P4):** 08 → 01 (data contract) → 04
- **Frontend (P5):** 02 (görselleştirme) → 09 (skorkart)

---

<a id="b00-s4"></a>

### [B00] Ortak varsayım defteri

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

[↑ İçindekiler](#icindekiler) · [↑ Yönlendirme tablosu](#yonlendirme)

---

<a id="belge-01"></a>

## BELGE 01 — Sektörel Projelerde Veriler

> **Belge kimliği:** `BELGE 01` (bölüm başlıklarında `[B01]` etiketiyle işaretlidir) · **Kaynak dosya:** `01_sektorel_veri_kaynaklari.md`  
> **Konu:** Gerçek misyon verisi, PDS4, veri yönetişimi, ECSS veri gereksinimleri  
> **Ana çıktı:** Veri omurgası spesifikasyonu + data contract  
> **Ayırt edici terimler:** `PGDA`, `LOLA`, `illumination`, `ECSS`, `LROC`, `PDS4`

> **Soru:** Gerçek Ay/gezegen yüzey projeleri hangi veriyi, hangi formatta, hangi disiplinle kullanıyor? LunaPath bunun neresinde?
>
> **Kısa cevap:** LunaPath bugün **tek bir DEM'den türetilmiş 7 katman** kullanıyor ve bunların 2'si (termal, gölge) fiziksel ölçüm değil, elevasyondan uydurulmuş proxy. Sektör ise **çok kaynaklı, sürümlenmiş, izlenebilir, belirsizliği nicelenmiş** veri kullanıyor — ve bu verinin neredeyse tamamı halka açık ve ücretsiz. Boşluk teknik yetenek değil, **veri disiplini** boşluğudur.

---

<a id="b01-s1"></a>

### [B01] 1. LunaPath'in mevcut veri durumu (dürüst envanter)

| Katman | Kaynak | Gerçek ölçüm mü? | Dosya |
|---|---|---|---|
| `elevation_grid` | LOLA `LDEM_80S_80MPP_ADJ` | ✅ Evet (altimetri) | `process_lunar_data.py:45` |
| `slope_grid` | `np.gradient(elevation)` | 🟡 Türetilmiş (yöntem bağımlı) | `process_lunar_data.py:132` |
| `aspect_grid` | `np.gradient(elevation)` | 🟡 Türetilmiş | `process_lunar_data.py:139` |
| `shadow_ratio_grid` | `1 - elev_norm` | ❌ **Proxy — fiziksel temeli yok** | `process_lunar_data.py:148` |
| `thermal_grid` | Elevasyon + aspect + komşu farkı | ❌ **Sentetik** | `backend/app/thermal_grid.py` |
| `traversability_grid` | slope > 25° veya T < −150 °C | 🟡 Kural tabanlı | `backend/app/traversability.py` |
| `cost_grid` | 4 penalty ağırlıklı toplam | 🟡 Model çıktısı | `backend/app/cost_engine.py:296` |

**Kritik gözlem:** Zincirin **tamamı tek bir girdiden** (elevasyon) türüyor. Bu, katmanlar arasında yapay bir korelasyon üretir: `shadow_ratio` ve `thermal` matematiksel olarak `elevation`'ın monoton fonksiyonlarıdır. Yani maliyet fonksiyonunda 4 bağımsız kriter varmış gibi görünse de, gerçekte **~2 bağımsız bilgi kanalı** (elevasyon ve eğim) vardır. Bu, AHP ağırlıklarının anlamını zayıflatır ve "4 profil neden benzer rota üretiyor?" sorusunun (`referans_belgesi_2.md` §11'de not edilmiş) asıl nedenidir.

> **Bu, çözülmesi gereken 1 numaralı veri problemidir.** Ağırlıkları oynatmak çözmez; bağımsız veri kanalı eklemek çözer.

---

<a id="b01-s2"></a>

### [B01] 2. Sektör gerçek misyonlarda ne kullanıyor?

#### 2.1 Ay güney kutbu için fiili standart veri yığını

Artemis dönemi iniş bölgesi analizlerinde (ör. Artemis III aday bölge çalışmaları) tekrar tekrar aynı dörtlü kullanılıyor:

| Ürün | Çözünürlük | Ne için | Erişim |
|---|---|---|---|
| **LOLA LDEM (kutup)** | 20 m/px (85°S–90°S), 10/40/60/120/240 m çeşitleri | Topografya, eğim, ufuk hattı | PDS Geosciences / PGDA |
| **LOLA 5 m/px site DEM'leri** | 5 m/px, 27 aday bölge | Yüksek çözünürlük yerel analiz | [PGDA #78](https://pgda.gsfc.nasa.gov/products/78) |
| **SfS 5 m/px SDEM'ler** | 5 m/px, 13 Artemis III bölgesi, >4500 km² | LOLA iz aralarını doldurma | [PGDA #104](https://pgda.gsfc.nasa.gov/products/104) |
| **LROC NAC kutup mozaiği** | ~1 m/px | Kaya/krater tespiti, hazard | LROC / USGS Astropedia |
| **LROC WAC** | 100 m/px | Bağlam, hillshade | LROC |
| **LOLA illumination / PSR** | 240 m (→65°), 120 m (→75°), 60 m (→85°), PSR 20 m | Aydınlanma oranı, kalıcı gölge | [imbrium.mit.edu ILLUMINATION](https://imbrium.mit.edu/BROWSE/EXTRAS/ILLUMINATION) |
| **Diviner tbol / treg / rock abundance** | 128 ppd (~250 m ekvatorda) | Yüzey sıcaklığı, termal atalet | PDS4 `urn:nasa:pds:lro_diviner_derived1` |
| **CRaTER** | Yörünge zaman serisi | Radyasyon ortamı | PDS / LRO |

**Doğruluk figürleri (PGDA 5 m/px ürünleri, LunaPath'in belirsizlik bütçesi için kullanılabilir):**
- Medyan RMS yükseklik hatası: **0.30–0.50 m**
- Medyan RMS eğim hatası: **1.5–2.5°**
- İz geolokasyon belirsizliği: yatay ~10–20 cm, düşey ~2–4 cm
- Her site için **100 "clone" dosyası** (istatistiksel topluluk) → belirsizlik yayılımı için doğrudan kullanılabilir

> **Bu son madde LunaPath için altın değerinde.** 100 clone ile Monte Carlo koşup "rota, DEM belirsizliği altında ne kadar kararlı?" sorusuna sayısal cevap verebilirsiniz. Hiçbir hackathon projesi bunu yapmaz; jüri/hakem için bu tek başına ayırt edici bir kanıttır.

#### 2.2 Eğimin "türetilmiş" olması bir detay değil

`np.gradient` (2. mertebe merkezi fark) eğimi **düzleştirir**. Sektörde eğim, misyon gereksinimine bağlı olarak farklı **baseline**'larda hesaplanır:

- **Rover tekerlek tabanı ölçeği** (~1–2 m): devrilme ve tırmanma limiti için
- **Araç boyu ölçeği** (~2–5 m): gövde açıklığı için
- **Bölgesel ölçek** (~20–100 m): enerji ve rota için

LunaPath 80 m'de tek bir eğim üretiyor ve bunu 25° hard-limit ile karşılaştırıyor. **80 m baseline'da 25° eğim, 2 m baseline'da 40°+ olabilir.** Yani mevcut `traversable` maskesi sistematik olarak **iyimser**.

**Reçete:** Eğimi tek sayı olarak değil, **ölçek-bağımlı üçlü** olarak üretin:

```python
# lunapath/src/slope_multiscale.py (yeni)
def slope_at_baseline(elev, res_m, baseline_m):
    """Belirtilen baseline'da eğim (derece). Adyacent-point yerine
    baseline ölçeğinde sonlu fark kullanır."""
    k = max(1, int(round(baseline_m / res_m)))
    dz_dy = (elev[2*k:, :] - elev[:-2*k, :]) / (2 * k * res_m)
    dz_dx = (elev[:, 2*k:] - elev[:, :-2*k]) / (2 * k * res_m)
    # ... pad + birleştir
    return np.degrees(np.arctan(np.hypot(dz_dx, dz_dy)))

SLOPE_BASELINES_M = {"vehicle": 5.0, "regional": 80.0}
```

80 m DEM'de `vehicle` baseline'ı **hesaplanamaz** — bu da tam olarak 5 m/px ürüne geçme gerekçenizdir. Bunu belgeleyin: "80 m veride araç ölçeği eğim gözlemlenemez, bu nedenle traversability alt-tahminlidir."

---

<a id="b01-s3"></a>

### [B01] 3. Sektörel veri disiplini: LunaPath'te olmayan 7 pratik

Gerçek projelerde veriyi "indir ve kullan" değil, **yönetilen bir varlık** olarak ele alırlar. ECSS'in yazılım (ECSS-E-ST-40C), ürün güvencesi (ECSS-Q-ST-80C) ve makine öğrenmesi (ECSS-E-HB-40-02A, 15 Kasım 2024) belgeleri bunu şart koşar.

#### 3.1 Veri kaynağı künyesi (provenance)

**Sektörde:** Her ürün için mission/instrument/product ID, sürüm, DOI, üretim tarihi, işleme seviyesi (raw/calibrated/derived) kayıtlı.

**LunaPath'te:** `metadata.json` sadece origin/resolution/shape/crs tutuyor. Kaynak dosya adı bile yok.

**Reçete — `metadata.json` v2 şeması:**

```json
{
  "schema_version": "2.0",
  "generated_utc": "2026-08-10T12:00:00Z",
  "generator": { "script": "process_lunar_data.py", "git_sha": "3e22809" },
  "grid": {
    "shape": [500, 500], "resolution_m": 80.0,
    "crs_wkt": "PROJCS[\"Moon (2015) - Sphere ... \"]",
    "origin": { "x": 176000.0, "y": 48000.0 },
    "window_offset": { "row": 3200, "col": 6000 },
    "nodata": "NaN"
  },
  "sources": [
    {
      "layer": "elevation",
      "product_id": "LDEM_80S_80MPP_ADJ",
      "instrument": "LRO/LOLA",
      "processing_level": "derived",
      "native_resolution_m": 80.0,
      "archive": "PDS Geosciences Node",
      "doi": null,
      "sha256": "<dosya hash'i>",
      "license": "Public domain (NASA)",
      "retrieved_utc": "2026-07-01T00:00:00Z"
    },
    {
      "layer": "thermal",
      "product_id": "SYNTHETIC:elevation_aspect_proxy_v1",
      "instrument": null,
      "processing_level": "model",
      "physical_validity": "NOT_MEASURED",
      "model_ref": "docs/archive/lunapath_referans_belgesi_2.md#32",
      "known_limitations": [
        "ray-tracing yok", "horizon masking yok",
        "zamana bağlı değişim yok", "elevasyonla yapay korelasyon"
      ]
    }
  ],
  "uncertainty": {
    "elevation_rms_m": null,
    "slope_rms_deg": null,
    "note": "80 m ürün için resmi belirsizlik yayınlanmadı; 5 m ürünlerde 0.30-0.50 m / 1.5-2.5 deg"
  }
}
```

`physical_validity: "NOT_MEASURED"` alanı **kritik**: sentetik olanı sentetik olarak işaretlemek, projeyi zayıflatmaz, güvenilir yapar. Frontend bunu okuyup katman üstünde "SENTETİK" badge'i gösterebilir.

#### 3.2 Sürümleme ve tekrar-üretilebilirlik

**Sektörde:** Aynı girdi + aynı kod = bit-bit aynı çıktı. Ürünler `v1.0`, `v1.1` olarak arşivlenir, eski sürümler silinmez.

**LunaPath'te:** `process_lunar_data.py` her koşumda `data/processed/*.npy` üzerine yazıyor. Hangi sürümle üretildiği kayıtlı değil. `find_action_window()` deterministik ama bu hiçbir yerde iddia edilmemiş.

**Reçete:**
- Çıktı dizinini içeriğe göre adlandır: `data/processed/<dem_sha8>_<res>m_<win_r>_<win_c>/`
- `metadata.json`'a `git_sha` yaz
- CI'da "aynı girdi → aynı hash" testi (regression guard):

```python
# backend/test_pipeline_determinism.py (yeni)
def test_pipeline_is_deterministic(tmp_path):
    a = run_pipeline(SMALL_FIXTURE_DEM)
    b = run_pipeline(SMALL_FIXTURE_DEM)
    for k in a: assert np.array_equal(a[k], b[k], equal_nan=True)
```

- Büyük ikili dosyalar için **DVC** veya **git-lfs**; `.npy` dosyaları repoya girmemeli (`.gitignore` kontrolü yapın).

#### 3.3 Katman hizalama sözleşmesi (alignment contract)

**Sektörde:** Farklı enstrümanlardan gelen ürünler tek bir "reference frame + projection + grid" üzerine resample edilir; her adım loglanır.

`docs/archive/ay_termal_navigasyon_proje_dokumani.md` §10.1 Risk 2 bu riski zaten tanımlamış ama kod bunu **doğrulamıyor** — çünkü tek kaynak var, hizalama sorunu henüz doğmadı. Diviner ve illumination ekleyince **hemen** doğacak:

- LOLA 80 m: polar stereographic, MOON_ME, R = 1737400 m küre
- Diviner GHRM: 128 ppd **silindirik (cylindrical)** projeksiyon, 70°S–70°N → **kutup için ayrı kutup ürünü gerekir**
- Illumination: polar stereographic ama 60/120/240 m

**Reçete — hizalama kapısı (gate):**

```python
# lunapath/src/align.py (yeni)
REQUIRED = ("crs_wkt", "resolution_m", "shape", "origin")

def assert_aligned(*metas):
    ref = metas[0]
    for m in metas[1:]:
        for k in REQUIRED:
            if m[k] != ref[k]:
                raise ValueError(f"Hizalama ihlali: {k}: {m[k]} != {ref[k]}")

def reproject_to_reference(src_path, ref_meta, resampling):
    """rasterio.warp.reproject ile referans grid'e getir.
    Kategorik maskeler (PSR, traversable) icin nearest,
    surekli alanlar (T, illumination) icin bilinear."""
```

**Resampling kuralı** (sık yapılan hata): PSR maskesini bilinear ile resample ederseniz 0.37 gibi anlamsız değerler çıkar. Kategorik → `nearest`; sürekli → `bilinear`/`cubic`; **downsampling'de sürekli alanlar için `average`** (rasterio `Resampling.average`), çünkü nokta örnekleme aliasing üretir. Mevcut kodda `find_action_window` doğru şekilde `Resampling.average` kullanıyor (`process_lunar_data.py:75`) — bu iyi, aynı disiplini diğer katmanlara taşıyın.

#### 3.4 Belirsizlik bütçesi

**Sektörde:** Her katmanın hatası nicelenir ve karar zincirinde yayılır. "Eğim 24.8°" değil, "eğim 24.8° ± 2.1°" denir.

**LunaPath'te:** Hiç yok. 25° hard-limit, hatasız bir ölçüm varsayıyor. RMS eğim hatası 1.5–2.5° ise, 25° limitine **±2.5° bant** eklemek zorunludur.

**Reçete — üç bölgeli karar:**

| Durum | Kural |
|---|---|
| `slope + 2σ < 25°` | Geçilebilir (yüksek güven) |
| `slope - 2σ < 25° ≤ slope + 2σ` | **Belirsiz** → yüksek maliyet + "yerel doğrulama gerekli" bayrağı |
| `slope - 2σ ≥ 25°` | Geçilemez |

Bu, ikili maskeyi **üçlü** yapar ve `traversability.py`'de tek satırlık bir değişikliktir ama savunulabilirlik açısından büyük bir sıçramadır. Mars 2020 ENav'ın ACE (Approximate Clearance Evaluation) algoritması tam olarak bu mantıkla çalışır: kesinlik yerine **clearance/güvenlik payı** değerlendirir.

#### 3.5 Veri sözleşmesi (data contract) — modüller arası

`ay_termal_navigasyon_proje_dokumani.md` §12 "erken sabitlenmesi gerekenler" listesi doğru ama şema olarak yazılmamış. Sektörde bu bir **makine-okunabilir şemadır** (JSON Schema / Pydantic / Protobuf).

**Reçete:** `backend/app/schemas.py` (yeni) — tüm grid'ler için tek doğrulayıcı:

```python
from pydantic import BaseModel, Field
from typing import Literal

class LayerSpec(BaseModel):
    name: str
    dtype: Literal["float32", "float64", "bool", "uint8"]
    units: str                      # "m", "deg", "degC", "dimensionless", "bool"
    valid_min: float | None
    valid_max: float | None
    nodata: Literal["nan", "sentinel", "mask"]
    physical_validity: Literal["MEASURED", "DERIVED", "MODEL", "NOT_MEASURED"]

LAYER_SPECS = {
  "elevation":    LayerSpec(name="elevation", dtype="float64", units="m",
                            valid_min=-10000, valid_max=10000, nodata="nan",
                            physical_validity="MEASURED"),
  "slope":        LayerSpec(name="slope", dtype="float64", units="deg",
                            valid_min=0, valid_max=90, nodata="nan",
                            physical_validity="DERIVED"),
  "thermal":      LayerSpec(name="thermal", dtype="float64", units="degC",
                            valid_min=-250, valid_max=130, nodata="nan",
                            physical_validity="NOT_MEASURED"),
  # ...
}

def validate_layer(name, arr):
    spec = LAYER_SPECS[name]
    assert str(arr.dtype) == spec.dtype, f"{name}: dtype {arr.dtype}"
    finite = arr[np.isfinite(arr)]
    if spec.valid_min is not None:
        assert finite.min() >= spec.valid_min, f"{name}: min {finite.min()}"
    # ...
```

Bu, `print_validation()`'ın (`process_lunar_data.py:250`) **yazdırmak** yerine **kırmak** (fail) versiyonudur. Şu an validasyon konsola bakan insana güveniyor; CI'ya güvenmeli.

#### 3.6 Birim ve işaret konvansiyonu

Sektörde en pahalı hatalar birim hatalarıdır (Mars Climate Orbiter, 1999). LunaPath'te riskli noktalar:

| Alan | Şu anki durum | Risk |
|---|---|---|
| Sıcaklık | °C (`thermal_grid`) | Ay literatürünün **tamamı Kelvin** kullanır. Diviner ürünleri K. Çeviri hatası kaçınılmaz. |
| Aspect | 0°=Kuzey, saat yönü | Ay güney kutbunda "kuzey" = kutuptan dışa. Güneş azimutu ile karıştırma riski yüksek. |
| Gölge | `shadow_ratio` [0,1] boyutsuz **ama** `f_shadow(H_hours)` saat bekliyor | İki farklı büyüklük aynı isimle dolaşıyor |

**Reçete:**
1. **İç temsilde Kelvin'e geçin**, sadece UI'da °C gösterin. `constants.py`'de `BAT_OP_MIN_K = 273.15` vb.
2. Değişken isimlerine birim ekleyin: `shadow_ratio_dimensionless`, `shadow_hours_cum_h`. `cost_engine.py`'de `edge_shadow_hours` zaten doğru adlandırılmış — bu deseni her yere yayın.
3. Aspect için açık bir docstring: "0° = grid-kuzeyi (+row azalan yön), saat yönünde artar, güneş azimutu ile aynı referans değildir."

#### 3.7 Lisans ve atıf

NASA PDS ürünleri kamu malı ancak **atıf beklenir**; bazı türev ürünler (ör. Zenodo'daki SfS SDEM'ler) CC lisanslıdır ve DOI ile atıf zorunludur. Kaguya/JAXA ürünlerinin ayrı kullanım koşulları vardır.

**Reçete:** `docs/DATA_LICENSES.md` (yeni) — her ürün için satır: ürün, sağlayıcı, lisans, atıf metni, DOI, indirme tarihi. README'deki "*Uzay verilerinin lisans ve kullanım koşullarına uygun kullanın*" uyarısı iyi bir niyet beyanı ama **uygulanabilir bir kayıt değil**.

---

<a id="b01-s4"></a>

### [B01] 4. Boşluk analizi ve öncelikli yol haritası

| # | Boşluk | Etki | Efor | Öncelik |
|---|---|---|---|---|
| G1 | Tüm katmanlar tek girdiden türüyor (yapay korelasyon) | 🔴 Çok yüksek — maliyet fonksiyonunun anlamı zayıf | Orta | **P0** |
| G2 | Termal veri sentetik | 🔴 Çok yüksek — projenin ana iddiası | Orta | **P0** |
| G3 | Gölge modeli fiziksel değil | 🔴 Yüksek | Düşük | **P0** |
| G4 | Provenance / sürümleme yok | 🟠 Yüksek (savunulabilirlik) | Düşük | **P0** |
| G5 | Belirsizlik bütçesi yok | 🟠 Yüksek | Orta | P1 |
| G6 | Eğim tek ölçekte, iyimser | 🟠 Orta-yüksek | Orta | P1 |
| G7 | Hizalama doğrulaması yok | 🟠 Orta (yeni veri gelince kritik) | Düşük | P1 |
| G8 | Şema/validasyon CI'da kırmıyor | 🟡 Orta | Düşük | P1 |
| G9 | Kelvin/°C karmaşası | 🟡 Orta | Düşük | P1 |
| G10 | Lisans kaydı yok | 🟡 Düşük-orta | Çok düşük | P2 |

#### P0 paketi — "veriyi gerçek yap" (tahmini 2–3 gün, 1 kişi)

1. **Diviner tbol kutup ürününü indir ve hizala** → `thermal_grid`'i gerçek ölçümle değiştir, sentetiği `thermal_grid_synthetic.npy` olarak yanında tut (ablasyon için gerekli, bkz. [03](#belge-03)).
2. **LOLA illumination/PSR ürününü indir ve hizala** → `shadow_ratio`'yu gerçek average-illumination ile değiştir.
3. **`metadata.json` v2 şemasına geç** (§3.1) — `physical_validity` alanı dahil.
4. **`assert_aligned` kapısını ekle** ve pipeline'da çağır.
5. **Korelasyon raporu üret:** 7 katmanın çift-yönlü Pearson/Spearman matrisi. Hedef: `|corr(thermal, elevation)| < 0.8`. Bugün bu değer ~1.0'a yakın olmalı (kodda zaten `generate_thermal_grid` doğrudan `elev_norm`'dan türüyor); gerçek Diviner ile 0.4–0.7 bandına düşmesi beklenir.

**Kabul kriteri:** `python lunapath/src/process_lunar_data.py` çalıştığında, çıktı `metadata.json` içinde en az 3 farklı `instrument` değeri (`LRO/LOLA`, `LRO/Diviner`, `LRO/LOLA-illumination`) bulunması ve korelasyon matrisinin `docs/` altına yazılması.

#### P1 paketi — "veriyi savunulabilir yap" (tahmini 3–4 gün)

6. Çok ölçekli eğim (§2.2) + belirsizlik bandı (§3.4) → üçlü traversability
7. `schemas.py` + CI'da kıran validasyon
8. Kelvin geçişi
9. 100-clone Monte Carlo ile rota kararlılığı raporu (5 m/px bölgeye geçilirse)

#### P2 paketi — "veriyi ölçeklenebilir yap"

10. DVC/git-lfs, `DATA_LICENSES.md`, çok bölgeli senaryo kütüphanesi (Shackleton, Nobile, de Gerlache, Malapert), tile-tabanlı işleme (bellek sınırı için)

---

<a id="b01-s5"></a>

### [B01] 5. Somut indirme rehberi

> Dosya adları ve yollar zamanla değişebilir; her indirmede `sha256` ve tarih kaydedin.

| İhtiyaç | Nereden | Not |
|---|---|---|
| Kutup DEM 20 m | PDS Geosciences LOLA RDR / [PGDA #81](https://pgda.gsfc.nasa.gov/products/81) (South Pole LOLA DEM Mosaic) | Mevcut 80 m'den 4× iyi; hesap yükü 16× |
| Site DEM 5 m + **100 clone** | [PGDA #78](https://pgda.gsfc.nasa.gov/products/78) | 27 site; GeoTIFF; belirsizlik ürünleri dahil |
| SfS SDEM 5 m (13 bölge) | [PGDA #104](https://pgda.gsfc.nasa.gov/products/104), Zenodo `10.5281/zenodo.17954508` | Eleve + hillshade + ortomozaik + eğim + roughness |
| Aydınlanma & PSR | [imbrium.mit.edu/BROWSE/EXTRAS/ILLUMINATION](https://imbrium.mit.edu/BROWSE/EXTRAS/ILLUMINATION) | 60/120/240 m; hem Güneş hem **Dünya** aydınlanması (iletişim penceresi için!) |
| PSR 20 m (en yeni) | Barker vd. 2023, [A New View of the Lunar South Pole from LOLA](https://iopscience.iop.org/article/10.3847/PSJ/acf3e1) / [PGDA #90](https://pgda.gsfc.nasa.gov/products/90) | Belirsizlik tahminleri ile |
| Diviner sıcaklık | PDS4 bundle `urn:nasa:pds:lro_diviner_derived1`, DOI `10.17189/wj0s-w188` | Detay: [07](#belge-07) |
| SLDEM2015 (global bağlam) | [PGDA #54](https://pgda.gsfc.nasa.gov/products/54) | LOLA+Kaguya TC birleşik, 59 m/px |
| LROC NAC / WAC | LROC arşivi, USGS Astropedia | Detay: [02](#belge-02) |

**Dünya aydınlanma katmanı gözden kaçmasın:** LunaPath'in bugünkü modelinde iletişim/veri indirme kısıtı yok. Kutupta Dünya görünürlüğü topografyaya bağlıdır ve gerçek görev planlamasında **birinci sınıf kısıttır** (komut alma, telemetri gönderme). Bu, maliyet fonksiyonuna 5. bir kriter olarak eklenebilecek, veri olarak **hazır bekleyen** bir ayırt edici özelliktir.

---

<a id="b01-s6"></a>

### [B01] 6. Sektörel veri disiplinini standarda bağlama

Akademik/jüri savunması için "biz keyfimize göre değil, standarda göre yaptık" demek güçlüdür:

| Standart | İlgili kısım | LunaPath'te karşılığı |
|---|---|---|
| **PDS4** | Ürün etiketleme, `Product_Observational`, birim sözlüğü | `metadata.json` v2'yi PDS4 alan adlarına yakın tutun |
| **ECSS-E-ST-40C** | Yazılım gereksinim/tasarım/V&V yaşam döngüsü | Modül contract'ları, test piramidi |
| **ECSS-Q-ST-80C** | Yazılım ürün güvencesi | Kritiklik sınıfı beyanı |
| **ECSS-E-HB-40-02A** (15 Kas 2024) | **ML nitelendirme el kitabı** — veri hazırlama, temsil edicilik, V&V, kritiklik B/C/D, "safety cage" mimarisi | ML eklerseniz zorunlu okuma → [04](#belge-04) |
| **ISO 19115 / OGC** | Coğrafi metadata | CRS/WKT kaydı |

> ECSS ML el kitabı **sentetik veriyi yasaklamaz**; veri seçiminin gerekçelendirilmesini, temsil ediciliğin gösterilmesini ve AI bileşeninin etrafına deterministik bir "safety cage" konmasını ister. LunaPath'in hard-constraint + log-barrier yapısı zaten bir safety cage'in embriyosudur — bunu bu isimle anlatmak, mimariyi standarda bağlar.

---

<a id="b01-s7"></a>

### [B01] 7. Kabul kriterleri (bu belgenin "bitti" tanımı)

- [ ] `metadata.json` v2 şeması yürürlükte, en az 3 bağımsız enstrüman kaynağı listeli
- [ ] Hiçbir katman `physical_validity: NOT_MEASURED` değilken "gerçek veri" olarak sunulmuyor (UI badge dahil)
- [ ] `assert_aligned` + `validate_layer` CI'da kırıyor
- [ ] Katman korelasyon matrisi üretiliyor ve `|corr(thermal, elevation)| < 0.8`
- [ ] `docs/DATA_LICENSES.md` mevcut
- [ ] Pipeline determinizm testi geçiyor
- [ ] Eğim ve traversability belirsizlik bandıyla üçlü

---

<a id="b01-s8"></a>

### [B01] Kaynaklar

- [High-Resolution LOLA Topography for Lunar South Pole Sites — PGDA #78](https://pgda.gsfc.nasa.gov/products/78)
- [Enhanced Topography Models with Shape-from-Shading — PGDA #104](https://pgda.gsfc.nasa.gov/products/104)
- [South Pole LOLA DEM Mosaic — PGDA #81](https://pgda.gsfc.nasa.gov/products/81)
- [A New View of the Lunar South Pole from LOLA — PGDA #90](https://pgda.gsfc.nasa.gov/products/90)
- [High-resolution Lunar Topography (SLDEM2015) — PGDA #54](https://pgda.gsfc.nasa.gov/products/54)
- [Barker et al. (2023), A New View of the Lunar South Pole from LOLA, PSJ](https://iopscience.iop.org/article/10.3847/PSJ/acf3e1)
- [LOLA illumination products (polar stereographic) — MIT Imbrium](https://imbrium.mit.edu/BROWSE/EXTRAS/ILLUMINATION)
- [Mazarico et al. (2014), Illumination conditions at the lunar south pole using high resolution DTMs from LOLA, Icarus](https://www.sciencedirect.com/science/article/abs/pii/S0019103514004278)
- [LRO Diviner Global High-Resolution Mosaics (ODE/WUSTL)](https://ode.rsl.wustl.edu/moon/pagehelp/Content/Missions_Instruments/Lunar%20Reconnaissance%20Orbiter%20(LRO)/DIVINER/GHRM.htm)
- [Lunar Surface Data Book (ACD-50044 Rev A), NTRS](https://ntrs.nasa.gov/api/citations/20230007818/downloads/ACD-50044%20Lunar%20Surface%20Data%20Book%20Rev%20A.pdf)
- [ECSS-E-HB-40-02A Machine Learning Qualification Handbook (15 Kasım 2024)](https://ecss.nl/wp-content/uploads/2024/12/ECSS-E-HB-40-02A(15November2024).pdf)
- [ESA AI STAR — ECSS ML Qualification Handbook tanıtımı](https://www.aistar.esa.int/advancing-the-european-space-industry-with-ai-introduction-to-the-ecss-e-hb-40-02a-machine-learning-qualification-handbook)
- [Lunar South Pole Atlas — LPI/USRA](https://www.lpi.usra.edu/lunar/lunar-south-pole-atlas/)

[↑ İçindekiler](#icindekiler) · [↑ Yönlendirme tablosu](#yonlendirme)

---

<a id="belge-02"></a>

## BELGE 02 — Görüntü İşleme

> **Belge kimliği:** `BELGE 02` (bölüm başlıklarında `[B02]` etiketiyle işaretlidir) · **Kaynak dosya:** `02_goruntu_isleme.md`  
> **Konu:** LROC NAC, SfS/fotoklinometri, kaya/krater tespiti, stereo, VO  
> **Ana çıktı:** Görüntü katmanı entegrasyon planı  
> **Ayırt edici terimler:** `kaya`, `NAC`, `POLAR`, `stereo`, `krater`, `SfS`, `sim2real`, `hazard`, `LuSNAR`, `LROC`

> **Soru:** LunaPath'e görüntü işleme nasıl, nerede ve ne kadar girer? Hangi ürünler hazır, hangi model açık kaynak, sim2real riski ne?
>
> **Kısa cevap:** LunaPath'te bugün **hiç görüntü verisi yok** — sadece altimetriden türetilmiş grid'ler var. Oysa görüntü işleme iki farklı yerde iki farklı iş yapar: **(A) yörüngeden** (LROC NAC 1 m/px) global maliyet haritasını 80× iyileştirir ve kaya/krater tespiti sağlar; **(B) rover üzerinden** (stereo kamera) yerel engel kaçınmayı besler. LunaPath'in kimliğine (görev öncesi planlama) uygun olan **A**'dır ve maliyeti düşüktür. B, [05](#belge-05)'in konusudur ve simülasyon gerektirir.

---

<a id="b02-s1"></a>

### [B02] 1. İki ayrı görüntü işleme problemi — karıştırmayın

| | **A: Yörüngeden (orbital)** | **B: Rover üzerinden (in-situ)** |
|---|---|---|
| Girdi | LROC NAC ~1 m/px, WAC 100 m/px | Stereo Navcam/Hazcam |
| Amaç | Kaya/krater haritası, SfS DEM, hazard katmanı | Anlık engel tespiti, VO, SLAM |
| Zamanlama | **Görev öncesi, offline** | **Gerçek zamanlı, onboard** |
| Hesap bütçesi | Serbest (masaüstü/GPU) | Katı (bkz. [08](#belge-08)) |
| LunaPath uygunluğu | ✅ Doğrudan uyar, mevcut mimariyi bozmaz | 🟡 Yeni katman + simülatör gerektirir |
| Sim2real riski | 🟢 Düşük (gerçek görüntü kullanılır) | 🔴 Yüksek (sentetik görüntüyle eğitim) |
| Öncelik | **P0/P1** | P2 |

> **Stratejik tavsiye:** A'yı yap, B'yi "mimaride yer ayrıldı, gelecek iterasyon" olarak belgele. B'ye yarım yamalak girmek, A'yı tam yapmaktan daha zayıf bir sonuç verir.

---

<a id="b02-s2"></a>

### [B02] 2. Yol A — Yörünge görüntüsünden maliyet katmanı

#### 2.1 Neden gerekli: 80 m'de görünmeyen ne var?

| Tehlike | Tipik boyut | 80 m/px'de görünür mü? | 5 m/px'de? | 1 m/px'de? |
|---|---|---|---|---|
| Krater duvarı (>25° eğim) | 100 m+ | ✅ | ✅ | ✅ |
| Küçük krater (fresh, dik kenar) | 5–50 m | ❌ | 🟡 | ✅ |
| Kaya bloğu (boulder) | 0.5–10 m | ❌ | ❌ (gölgesinden 🟡) | ✅ |
| Basamak / rim çıkıntısı | 0.3–2 m | ❌ | ❌ | 🟡 |

Bugünkü LunaPath, 40 km × 40 km alanı 500×500 hücrede modelliyor. **Bir hücre 6400 m²** — yani bir futbol sahasından büyük. O hücreye "geçilebilir" demek, içinde 3 m'lik bir kaya olmadığını iddia etmek anlamına gelmez. Bu, projenin en büyük **sessiz varsayımıdır** ve mutlaka belgelenmelidir.

**Minimum dürüst formülasyon:** Bugünkü `traversability_grid`'in adı `regional_traversability` olmalı ve tanımı şu olmalı:

> "Bölgesel ölçekte (80 m baseline) geçilebilirlik. Araç ölçeği tehlikelerini (kaya, küçük krater, basamak) **kapsamaz**; bu tehlikeler için ayrı bir hazard katmanı gereklidir."

#### 2.2 Hazır ürün: SfS (Shape-from-Shading) DEM'ler

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

#### 2.3 Kaya (boulder) tespiti — açık kaynak durumu

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

#### 2.4 Krater tespiti

Krater tespiti (crater detection algorithms, CDA) uzun bir literatüre sahip; hem klasik (Hough, template matching) hem CNN tabanlı (DeepMoon vb.) modeller var. LunaPath için değeri **kaya tespitinden daha az**, çünkü büyük kraterler DEM'de zaten görünüyor. Değerli olan kısım: **taze (fresh) küçük kraterler** — dik kenarlı, DEM'de kaybolan, ama optikte parlak ejekta halkasıyla belli olan.

**Öneri:** Krater tespitini P2'ye bırakın. Kaya tespiti daha yüksek getiri/maliyet oranına sahip.

#### 2.5 Yol A entegrasyon reçetesi

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

   Bu, [08](#belge-08)'deki hesap bütçesi mantığının doğal uzantısıdır ve gerçek misyon planlamasının çalışma şeklidir.

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

<a id="b02-s3"></a>

### [B02] 3. Yol B — Rover üzeri görüntü işleme (referans için)

Bu yola girmeye karar verirseniz bilinmesi gerekenler:

#### 3.1 Kutup aydınlanması perception'ı kırar

Ay güney kutbunun perception açısından tanımlayıcı özelliği: **güneş ufukta (~1.5°)**. Sonuçlar:

- Uzun, keskin gölgeler → terrain feature'ları **saklar**
- Aydınlık/gölge arası dinamik aralık kamera dinamik aralığını aşar → HDR zorunlu
- Stereo korelasyon doku yokluğunda başarısız (feature-sparse görüntüler)
- Doğrudan güneşe bakış → lens flare, saturation
- Gölge içinde sinyal ≈ gürültü → aktif aydınlatma (LED/lazer) gerekir

Kutup için yayınlanmış perception çalışmaları bunu doğruluyor: bölge-tabanlı yöntemler (K-means ile gri seviye segmentasyonu → doku/parlaklık ile zemin/gölge/tehlike sınıflandırma → güneş açısına göre gölge değerlendirmesi → hazard haritası) tam olarak bu problemi hedefliyor.

#### 3.2 Referans sonuç: ViT ile düşük aydınlanmada hazard tespiti

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
2. **0.346 s/görüntü bir masaüstü GPU'da.** Uçuş bilgisayarında bu 10–100× daha yavaş olur. Onboard ViT bugün gerçekçi değil ([08](#belge-08)).
3. **Yazarların kendi sim2real uyarısı:** "Blender'daki kamera modeli gerçek bir CMOS sensöründen farklı çalışır" ve "görüntülerde gürültü olmaması, veri setinin gerçek veriyle nasıl karşılaştırılacağı konusunda iddia edilmesini engelliyor." Sentetik veriyle eğitip gerçekte çalışacağını iddia etmek **kanıt gerektirir** → [03](#belge-03).

#### 3.3 Gerçek görüntü veri setleri (sim2real köprüsü)

Yol B'ye girerseniz, sentetik veriyi **gerçek analog veriyle** doğrulamak zorundasınız. Ücretsiz ve hazır:

| Veri seti | İçerik | Neden değerli |
|---|---|---|
| **NASA POLAR** ([ti.arc.nasa.gov/dataset/IRG_PolarDB](https://ti.arc.nasa.gov/dataset/IRG_PolarDB/)) | ~**2.600 HDR stereo çift**, 13 arazi senaryosu (seyrek/yoğun kaya, kraterler, farklı boyutlar) | **Dünya'da ama kontrollü kutup benzeri aydınlanmada** çekildi — gerçek sensör, gerçek gölge |
| **POLAR Traverse** ([ti.arc.nasa.gov/dataset/PolarTrav](https://ti.arc.nasa.gov/dataset/PolarTrav/), [arXiv 2403.12194](https://arxiv.org/html/2403.12194)) | Düz hat traverse simülasyonu, **1 m aralıkla** stereo görüntü, regolit simülantı yatağı | Ardışık kareler → VO/SLAM testi |
| **POLAR-Sim** ([arXiv 2309.12397](https://arxiv.org/abs/2309.12397), [Dryad](https://datadryad.org/dataset/doi:10.5061/dryad.ksn02v7hf)) | 13 senaryonun **digital twin**'i (mesh + doku + malzeme) + POLAR'ın tamamı için **23.000 etiket** (bbox + semantik: kaya, gölge, krater) | **Gerçek görüntülerin etiketi + eşleşen sentetik sahne** → sim2real ölçümü için ideal çift |
| **LuSNAR** ([github.com/zqyu9/LuSNAR-dataset](https://github.com/zqyu9/LuSNAR-dataset), [arXiv 2407.06512](https://arxiv.org/abs/2407.06512)) | **108 GB**, Unreal Engine ile 9 sahne; stereo + LiDAR + IMU senkron; panoramik semantik etiket, yoğun derinlik, nokta bulutu, rover pozu | Tek pakette 2D/3D semseg, visual SLAM, LiDAR SLAM, stereo matching, 3D rekonstrüksiyon benchmark'ı |

**POLAR + POLAR-Sim ikilisi, sim2real ölçmenin en temiz yolu:** aynı sahnenin gerçek ve sentetik hali + ortak etiketler. "Sentetikte eğit, gerçekte test et" ölçümünü doğrudan yapabilirsiniz.

#### 3.4 Görsel odometri ve lokalizasyon

Rover'ın nerede olduğunu bilmesi, engel kaçınmanın önkoşuludur:

- **VO (visual odometry):** Ardışık stereo kare arasındaki feature takibi ile hareket kestirimi. Mars 2020'de VO, "Thinking-While-Driving" ile sürüş sırasında sürekli çalışıyor. Chandrayaan-3 Pragyan görüntüleri üzerinde VO analizleri yayınlandı.
- **Yutu-2:** görsel SLAM + rota planlama + rover kontrolü ile 6 yılı aşan operasyon; öncülü Yutu'ya kıyasla lokalizasyon, haritalama, otonom navigasyon ve hareket planlamada belirgin ilerleme.
- **DEM-anchored SLAM / segment tabanlı global lokalizasyon** (ör. LunarLoc) — yörünge DEM'ini referans alarak drift'i sıfırlama.

**LunaPath ile bağlantısı:** LunaPath'in ürettiği rota, rover'ın **konumunu bildiği** varsayımına dayanır. Gerçekte konum belirsizliği birikir (Ay'da GPS yok, manyetik alan yok). Bu, planlayıcıya girmesi gereken bir belirsizliktir:

> "Rota, ±X m konum belirsizliği altında hâlâ güvenli mi?" — Rota koridoru genişliği bu belirsizliğe göre ayarlanmalı. Dar bir güvenli geçitten geçen bir rota, 20 m konum hatası varsa güvenli değildir.

Bu, **çok az projenin düşündüğü** ve LunaPath'in düşük maliyetle ekleyebileceği bir olgunluk göstergesidir: `path_corridor_clearance_m` metriği = rota üzerindeki her nokta için en yakın `traversable=False` hücreye mesafe. Minimumu rapor edin.

---

<a id="b02-s4"></a>

### [B02] 4. Boşluk analizi

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

<a id="b02-s5"></a>

### [B02] 5. Yol haritası

#### P0 — dürüstlük düzeltmesi (yarım gün)
- `traversability_grid` → `regional_traversability_grid` yeniden adlandır, docstring'e ölçek sınırlamasını yaz
- README ve `referans_belgesi_2.md`'ye "araç ölçeği tehlikeler kapsam dışı" notu

#### P1 — yörünge görüntüsü entegrasyonu (3–5 gün)
1. Bir hedef bölge seç ki hem PGDA 5 m SDEM'i hem NAC mozaiği olsun (ör. de Gerlache–Kocher Massif, Shackleton rim)
2. `orbital_imagery.py`: SfS elevation + slope + **roughness** yükle, referans grid'e hizala ([01](#belge-01) §3.3)
3. `f_roughness` ekle, ağırlıkları yeniden normalize et, doğrulama tablosu üret
4. Hiyerarşik koridor analizi: 80 m global rota → ±500 m bandı 5 m'de yeniden değerlendir → rota "rafine" edildi mi karşılaştırması
5. Frontend: NAC/hillshade arka plan + koridor bandı gösterimi
6. `path_corridor_clearance_m` metriğini `PathResult.metrics`'e ekle

**Kabul kriteri:** Aynı start/goal için "80 m global rota" ile "5 m koridorda rafine rota" arasındaki farkı sayısal gösteren bir karşılaştırma tablosu. Bu tek başına güçlü bir demo hikâyesidir: *"Kaba haritada güvenli görünen rota, yüksek çözünürlükte bakınca 3 noktada kayalık çıktı ve rota şöyle değişti."*

#### P2 — kaya tespiti (5–8 gün)
7. NAC karolarını indir, YOLOv5/v8 fine-tune (açık eğitim verisi ile) veya hazır global kaya haritasını kullan
8. Gölge uzunluğu → kaya yüksekliği dönüşümü, güneş geometrisiyle
9. `rock_density_grid` → soft penalty + hard eşik

#### P3 — rover üzeri perception (araştırma dalı, kapsam dışı önerilir)
10. OmniLRS/LunarSim ile sentetik stereo üret ([04](#belge-04))
11. POLAR + POLAR-Sim ile sim2real ölçümü
12. Yerel hazard haritası → [05](#belge-05) mimarisi

---

<a id="b02-s6"></a>

### [B02] 6. Sık yapılan hatalar (kontrol listesi)

- ❌ NAC görüntülerini DEM'e **hizalamadan** üstüne bindirmek. NAC'ın kendi geometrisi var; bundle adjustment olmadan 10-100 m kayma normaldir.
- ❌ Gölgeyi "veri yok" saymak. Gölge **bilgidir** (kaya var, çukur var). NoData ile gölgeyi ayırın.
- ❌ Fotoklinometriyi mutlak referans olmadan kullanmak → uzun dalga boylu sistematik hata (bowl/dome artefaktları).
- ❌ Kutup görüntülerini normalize etmek için global min/max kullanmak. Yerel/adaptif kontrast (CLAHE benzeri) gerekir; aksi halde her şey siyah veya beyaz olur.
- ❌ ImageNet ön-eğitimli modeli tek kanallı gri Ay görüntüsüne 3-kanal tekrarıyla besleyip renk istatistiği uyumsuzluğunu görmezden gelmek. Normalizasyon istatistiklerini veri setinden yeniden hesaplayın.
- ❌ Sentetik görüntüye sensör gürültüsü eklememek (ViT çalışmasının kendi itirafı). Poisson (shot) + Gaussian (read) gürültüsü, PRNU, sıcak piksel, kuantizasyon ekleyin.

---

<a id="b02-s7"></a>

### [B02] Kaynaklar

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

[↑ İçindekiler](#icindekiler) · [↑ Yönlendirme tablosu](#yonlendirme)

---

<a id="belge-03"></a>

## BELGE 03 — Sentetik ve Minimum Veri

> **Belge kimliği:** `BELGE 03` (bölüm başlıklarında `[B03]` etiketiyle işaretlidir) · **Kaynak dosya:** `03_sentetik_minimum_veri.md`  
> **Konu:** Sentetik veri ne zaman meşru, minimum veri omurgası, sim2real  
> **Ana çıktı:** "Sentetik" etiketleme protokolü + ablasyon planı  
> **Ayırt edici terimler:** `ECSS`, `sim2real`, `RMSE`, `Prithvi`

> **Soru:** LunaPath'in sentetik termal/gölge verisi kabul edilebilir mi? Sentetik veri ne zaman meşru, ne zaman sahtekârlık? Projeyi taşıyacak **minimum** veri omurgası nedir?
>
> **Kısa cevap:** Sentetik veri kötü değil. **Etiketlenmemiş, doğrulanmamış ve alternatifi varken kullanılan** sentetik veri kötüdür. LunaPath'in sentetik termal gridi bugün üçüncü kategoriye giriyor: gerçek Diviner verisi ücretsiz ve indirilebilir durumdayken sentetik kullanılıyor. Çözüm sentetiği atmak değil — **gerçeği eklemek ve sentetiği baseline olarak tutmak.**

---

<a id="b03-s1"></a>

### [B03] 1. Sentetik verinin üç meşru kullanımı, bir gayrimeşru kullanımı

| Kullanım | Meşru mu? | LunaPath'te örnek |
|---|---|---|
| **1. Erken geliştirme / unblocking** — gerçek veri gelene kadar arayüzleri test etmek | ✅ Tamamen meşru, sektör standardı | `ay_termal_navigasyon_proje_dokumani.md` §10.3 Risk 7 bunu doğru öneriyor |
| **2. Kapsam genişletme** — gerçekte gözlenmemiş ama fiziksel olarak mümkün durumları test etmek (SEP fırtınası, ekipman arızası) | ✅ Meşru, hatta zorunlu | SEP olay senaryosu → [06](#belge-06) |
| **3. Etiketli veri üretimi** — gerçekte etiketlemenin imkânsız olduğu yerde (piksel-düzeyi ground truth) | ✅ Meşru, koşullu (sim2real kanıtı gerekir) | ViT hazard tespiti → [02](#belge-02) §3.2 |
| **4. Var olan ölçümün yerine ikame** | ❌ **Gayrimeşru** — ölçüm varken model kullanmak | `thermal_grid`, `shadow_ratio` |

**LunaPath'in mevcut durumu tam olarak 4. kategoride** ve bu, referans belgesinin kendisinde de itiraf edilmiş:

> *"⚠️ Bu bir KABA PROXY'dir — elevasyon gölgenin nedeni değil sonucudur. Offline illumination fraction haritası her zaman tercih edilmelidir."* (`lunapath_referans_belgesi_2.md` §2.3.3)

> *"Bu gerçek bir termal model DEĞİLDİR. Ray-tracing veya ephemeris kullanmaz. Horizon masking yok. Zamana bağlı değişim yok."* (§3.2)

**Bu itiraflar iyi mühendisliktir.** Sorun itirafın olmaması değil, **itirafın ardından düzeltmenin yapılmamasıdır.** Hackathon'da bu kabul edilebilirdi; "gerçek hale getirme" fazında kabul edilemez.

---

<a id="b03-s2"></a>

### [B03] 2. Sentetik termal gridin teknik eleştirisi

`backend/app/thermal_grid.py` + `referans_belgesi_2.md` §3.2'deki algoritma:

```
T_base   = -180 + elev_norm × 260          # lineer elevasyon eşlemesi
T_aspect = cos(aspect) × (slope/25) × 40   # bakı düzeltmesi
T_shadow = clip(Δh_kuzey / (res × 0.1), 0, 1) × (-30)
T        = clip(T_base + T_aspect + T_shadow, -250, 130)
```

#### 2.1 Beş yapısal problem

**(P1) Elevasyon–sıcaklık lineer eşlemesi fiziksel olarak yanlış.**
Ay'da atmosfer yoktur → **lapse rate yoktur**. Yükseklik ile sıcaklık arasında doğrudan nedensel ilişki yok. Kutupta korelasyon **dolaylıdır**: yüksek noktalar ufuk üstünde kaldığı için daha çok güneş görür. Ama bu bir *ufuk geometrisi* etkisidir, elevasyon etkisi değil. Sonuç: 40 km'lik bir pencerede en alçak nokta otomatik olarak −180 °C atanıyor; bu nokta gerçekte aydınlık bir düzlük olabilir.

**(P2) Doğrulama kriteri sirküler.**
`validate_thermal_grid` şunu kontrol ediyor: *"Elevasyon-sıcaklık korelasyonu > 0.5 beklenir"*. Ama sıcaklık **elevasyondan üretildiği** için bu korelasyon inşaat gereği ~1.0'dır. Bu bir doğrulama değil, tekrar-ölçümdür (tautology). Gerçek doğrulama, **bağımsız bir ölçümle** (Diviner) karşılaştırmadır.

**(P3) Sıcaklık aralığı kutup için yanlış.**
Kod +80 °C (353 K) tepe sıcaklığı üretiyor. Ay güney kutbunda güneş elevasyonu ~1.5°'dir; bu kadar sığ geliş açısıyla yüzey **353 K'ya çıkamaz**. Kutup aydınlık zirvelerinin tipik ölçüm bandı ~200–260 K (−73…−13 °C) mertebesindedir; 353 K ekvator öğle değeridir. Bu, `f_thermal`'in "ideal" bölge üretmesine ve termal penalty'nin **sistematik olarak iyimser** olmasına yol açar.

**(P4) Gölge proxy'si yön-kör ve tek-piksel.**
`height_diff[1:, :] = elevation[:-1, :] - elevation[1:, :]` sadece **bir kuzey komşusuna** bakıyor. Gerçek gölgeyi belirleyen şey, güneş azimutu yönünde **ufuk hattının tamamıdır** (10 km öteki bir masif gölge yapabilir). `res × 0.1` bölmesi (80 m grid'de 8 m) keyfi bir ölçek sabitidir.

**(P5) Zaman yok.**
Kutup aydınlanması **saatler mertebesinde** değişir. Statik bir snapshot, "rover 50 saat gölgede kalır" gibi bir metriği hesaplarken kendi kendisiyle çelişir: gölge süresi ancak zaman-değişken bir aydınlanma alanı varsa tanımlıdır. Şu anki `estimate_shadow_hours(elev_norm, Δt) = (1 - elev_norm) × Δt` formülü, "alçaktaysan zamanının %X'i karanlıktasın" der — ki bu ne uzamsal ne zamansal olarak fiziksel bir ifadedir.

#### 2.2 Buna karşılık: sentetik gridin ne işe yaradığı

Adil olalım — sentetik grid iki gerçek iş yapıyor:

1. **Pipeline'ı uçtan uca çalışır hale getirdi.** Bu, mühendislik olarak doğru sıralamadır (önce çalışan sistem, sonra doğru veri).
2. **Uzamsal yapı üretiyor.** Rota planlayıcının "farklı maliyet bölgeleri arasında seçim yapması" davranışını test etmek için yeterli. Yani **algoritma testi için geçerli, sonuç iddiası için geçersiz.**

**Bu ayrımı belgeleyin:** sentetik grid bir *fixture*'dır, bir *ürün* değildir.

---

<a id="b03-s3"></a>

### [B03] 3. Minimum veri omurgası — yeniden tanımlanmış

`ay_termal_navigasyon_proje_dokumani.md` §14 beş katmanlı bir omurga öneriyor: sıcaklık, DEM, slope, shadow/illumination, PSR maskesi. **Bu liste doğru ama eksik ve önem sıralaması yok.** Aşağıdaki tablo, her katman için "olmazsa ne kırılır" analizidir:

| Katman | Zorunluluk | Yoksa ne olur | Gerçek kaynak | Sentetik kabul edilebilir mi? |
|---|---|---|---|---|
| **Elevation (DEM)** | 🔴 **Kritik** | Hiçbir şey çalışmaz | LOLA LDEM | ❌ Asla — mevcut ve ücretsiz |
| **Slope** | 🔴 **Kritik** | Hard-constraint yok | DEM'den türetilir (ölçek beyanı ile) | 🟡 Türetilmiş, sentetik değil |
| **Illumination fraction** | 🔴 **Kritik** | Gölge/enerji modelinin temeli yok | LOLA illumination (60/120/240 m) | ❌ Ürün var |
| **Yüzey sıcaklığı** | 🔴 **Kritik** | Projenin ana iddiası dayanaksız | Diviner tbol | ❌ Ürün var |
| **PSR maskesi** | 🟠 Yüksek | Kalıcı gölge/kriyojenik bölge ayrımı yok | LOLA PSR 20 m | ❌ Ürün var |
| **Roughness** | 🟠 Yüksek | Pürüzlülük penalty'si yok | SfS SDEM roughness | 🟡 Geçici olarak DEM varyansından |
| **Rock abundance** | 🟡 Orta | Kaya tehlikesi görünmez | Diviner rock abundance / NAC DL | 🟡 Kabul edilebilir |
| **Thermal inertia (H-param)** | 🟡 Orta | Soğuma/ısınma dinamiği kaba | Diviner türev ürünleri | ✅ Sabit varsayım kabul edilebilir |
| **Radyasyon** | 🟡 Orta | Donanım sağlığı modeli eksik | CRaTER/LND'den skaler | ✅ **Sentetik/skaler tamamen meşru** → [06](#belge-06) |
| **Rover parametreleri** | 🔴 Kritik | Model kalibre edilemez | Gerçek rover verisi gizli/yok | ✅ **Sentetik zorunlu** (LPR-1 doğru yaklaşım) |
| **Zaman-değişken aydınlanma** | 🟠 Yüksek | Gölge süresi tanımsız | Ephemeris + ufuk hesabı | 🟡 Basitleştirilmiş ephemeris kabul edilebilir |
| **Dünya görünürlüğü** | 🟢 Bonus | İletişim kısıtı yok | LOLA Earth-illumination | ❌ Ürün var |

#### 3.1 "Sentetik meşruiyet testi" — 4 soru

Bir katmanı sentetik üretmeye karar vermeden önce:

1. **Gerçek ürün var mı ve erişilebilir mi?** Varsa → sentetik gayrimeşru. (Termal ve illumination burada takılıyor.)
2. **Sentetik model, fiziksel bir mekanizmadan mı türüyor, korelasyondan mı?** Mekanizmadan türüyorsa savunulabilir (ör. LPR-1 termal denge modeli). Korelasyondan türüyorsa değil (ör. elevasyon→sıcaklık).
3. **Sentetiğin hatası nicelenebilir mi?** En az bir gerçek ölçümle karşılaştırılabiliyor mu? Karşılaştırılamıyorsa, sonucun üzerine bina kurulamaz.
4. **Sonuçtaki hassasiyet ölçüldü mü?** Sentetik parametreyi ±%50 oynatınca rota değişiyor mu? Değişiyorsa sonuç sentetiğe bağımlıdır ve bu rapor edilmelidir.

LPR-1 rover parametreleri bu testi **geçiyor** (1: gerçek rover verisi kamuya kapalı; 2: VIPER/MoonRanger'dan mekanizma temelli türetme; 3: literatür bandıyla karşılaştırılabilir; 4: hassasiyet analizi yapılabilir). Termal grid **1 ve 2'de kalıyor.**

---

<a id="b03-s4"></a>

### [B03] 4. Sentetik veriyi savunulabilir yapan protokol

#### 4.1 Zorunlu etiketleme

Her sentetik ürün üç alanla birlikte gelmeli:

```json
{
  "layer": "thermal",
  "physical_validity": "MODEL",
  "model": {
    "id": "SYNTH-THERM-v1",
    "mechanism": "elevation-aspect proxy (NOT a radiative balance model)",
    "inputs": ["elevation", "slope", "aspect"],
    "free_parameters": {
      "T_min_base_C": -180.0, "T_max_base_C": 80.0,
      "aspect_delta_max_C": 40.0, "shadow_penalty_C": -30.0
    },
    "known_limitations": [
      "no ray-tracing / horizon masking",
      "no time dependence",
      "artificial monotone correlation with elevation (r ~ 1.0)",
      "peak temperature (+80 C) unphysical for 1.5 deg solar elevation"
    ],
    "validated_against": null,
    "intended_use": "algorithm fixture only; NOT for mission conclusions"
  }
}
```

`validated_against: null` alanı boş kaldığı sürece, o katmandan üretilen hiçbir sayı "sonuç" olarak sunulmamalı. Bu alan dolduğunda (`"LRO/Diviner tbol, RMSE = X K, bias = Y K"`) katman terfi eder.

#### 4.2 Ablasyon protokolü (en önemli tek öneri)

Sentetiği atmayın — **karşılaştırma kolu (control arm)** olarak tutun. Bu, projeyi savunulabilir kılan asıl mekanizmadır:

| Kol | Termal katman | Gölge katmanı | Amaç |
|---|---|---|---|
| **A (baseline)** | Sentetik v1 | Elevasyon proxy | Mevcut sistem |
| **B** | **Diviner tbol** | Elevasyon proxy | Termalin tek başına etkisi |
| **C** | Sentetik v1 | **LOLA illumination** | Gölgenin tek başına etkisi |
| **D (hedef)** | **Diviner tbol** | **LOLA illumination** | Gerçek sistem |

Her kol için aynı start/goal ile 4 misyon profili koştur ve raporla:

- Rota **geometrik** farkı: Fréchet mesafesi veya ortalama sapma (m)
- Metrik farkı: toplam mesafe, enerji, max eğim, gölge süresi, max termal risk
- **Karar farkı:** A ile D aynı hücreleri mi geçiyor? Kaç hücrede ayrılıyor?
- **Yanlış güven ölçümü:** A'nın "güvenli" dediği ama D'nin "tehlikeli" dediği hücre sayısı → **bu sayı, sentetik modelin operasyonel riskidir.**

> **Sunum cümlesi:** *"Sentetik termal modelimiz, gerçek Diviner verisiyle karşılaştırıldığında rotanın %N'inde farklı karar üretiyor ve M hücreyi yanlışlıkla güvenli işaretliyor. Bu yüzden gerçek veriye geçtik."* — Bu cümle, sentetikle kalıp hiç ölçmemekten kat kat güçlüdür.

#### 4.3 Hassasiyet analizi (sentetiği tutmanız gerekiyorsa)

Sentetik parametreleri Monte Carlo ile örnekleyin:

```python
# backend/test_thermal_sensitivity.py (yeni)
import itertools, numpy as np

PARAM_GRID = {
    "T_min_base_C": [-220, -180, -140],
    "T_max_base_C": [40, 80, 120],
    "aspect_delta_max_C": [20, 40, 60],
    "shadow_penalty_C": [-15, -30, -45],
}

def test_route_stability_under_synthetic_params(grids, start, goal):
    routes = []
    for combo in itertools.product(*PARAM_GRID.values()):
        params = dict(zip(PARAM_GRID, combo))
        g = regenerate_thermal(grids, **params)
        routes.append(astar(g, start, goal, WEIGHTS_BALANCED))
    # Rapor: rotalarin kac tanesi ayni? ortalama sapma? metrik dagilimi?
    assert route_dispersion(routes) < TOLERANCE, (
        "Rota, sentetik parametrelere asiri duyarli -> sonuc raporlanamaz")
```

81 kombinasyonun tümü aynı rotayı veriyorsa, "sonucumuz sentetik parametre seçimine duyarsız" diyebilirsiniz — bu güçlü bir savunmadır. Rotalar dağılıyorsa, **bunu rapor edin ve gerçek veriye geçin.** İkisi de savunulabilir; ölçmemek savunulamaz.

---

<a id="b03-s5"></a>

### [B03] 5. Sim2real: sentetik görüntü/dinamik ile eğitim

ML bileşeni eklerseniz (görüntü tabanlı hazard tespiti, öğrenilen traversability, RL kontrol) sentetik veri kaçınılmaz olur. Sektörün öğrendiği dersler:

#### 5.1 Domain randomization

Tek bir simüle ortamda eğitmek yerine, her episode başında simülasyon parametrelerini rastgeleleştirmek modelin genelleşmesini artırır. Ay bağlamında randomize edilen tipik parametreler:

- **Çevresel:** yerçekimi vektörü, güneş azimut/elevasyon, albedo, toz yoğunluğu
- **Yüzey mekaniği:** granüler medya parametreleri (sürtünme, kohezyon, batma), tekerlek-toprak etkileşimi
- **Platform:** rover base frame'inde küçük ofsetler, sensör montaj hatası, kamera intrinsics
- **Sensör:** shot/read gürültüsü, motion blur, pozlama, ölü piksel

**Sim2Dust** ([arXiv 2508.11503](https://arxiv.org/html/2508.11503)) tam olarak bunu yapıyor: prosedürel arazi üretimi + geniş domain randomization ile masif paralel simülasyonda RL eğitip, politikayı **zero-shot** olarak fiziksel bir tekerlekli rover'a ve Ay-analog tesisine aktarıyor. Öne çıkardığı zorluk: **tekerleğin granüler medyayla etkileşiminin karmaşık dinamiği** — sim2real boşluğunun asıl kaynağı burada.

#### 5.2 "Ne kadar sentetik veri yeter?" sorusunun dürüst cevabı

Literatürde **tek bir oran yok** ve olması da beklenmez; oran göreve, mimariye ve domain gap'in büyüklüğüne bağlıdır. Ancak sağlam pratikler var:

1. **Sentetik ön-eğitim + küçük gerçek fine-tune** genellikle en iyi getiri/maliyet oranını verir. Prithvi-EO-2.0 gibi ön-eğitimli modellerde de aynı desen: ön-eğitimli başlatma rastgele başlatmadan **daha hızlı yakınsıyor** ve birçok görevde SOTA'yı geçiyor.
2. **Gerçek veri "test seti" olarak kutsaldır.** Sentetikte eğitin, **gerçekte ölçün**. Gerçek veriyi eğitime karıştırıp sonra aynı dağılımda test etmek, sim2real boşluğunu ölçmez.
3. **Ölçüt sayı değil, eğridir:** gerçek veri miktarını 0, 1, 5, 10, 25, 50, 100 örnek olarak artırıp performans eğrisi çizin. Doygunluk noktası, ihtiyacınız olan gerçek veri miktarıdır.
4. POLAR + POLAR-Sim ikilisi bu ölçümü **hazır** sunuyor: aynı 13 sahnenin gerçek HDR stereo görüntüleri, digital twin mesh'leri ve **her ikisi için ortak 23.000 etiket** ([02](#belge-02) §3.3).

#### 5.3 ECSS ne diyor?

**ECSS-E-HB-40-02A** (Space engineering — Machine learning qualification handbook, 15 Kasım 2024) sentetik veriyi yasaklamıyor. İstediği şeyler:

- AI'ın bu uygulama için **uygun olup olmadığının** önce değerlendirilmesi
- Verinin ilgili parametrelere göre **seçilmesi ve nitelendirilmesi** (data qualification)
- Eğitim sonrası **doğrulama ve geçerleme** (V&V) ile operasyonel hazırlığın kanıtlanması
- AI bileşeninin izole değil, **sistem mühendisliği bağlamında** ele alınması
- **"Safety cage architecture"** — AI çıktısının etrafına deterministik güvenlik kısıtları koymak
- Şu an **kritiklik kategorileri B, C, D** kapsanıyor (en kritik A değil)

> **LunaPath için doğrudan sonuç:** Mevcut mimari (hard constraint `θ > 25° → INF` + log-barrier) tam olarak bir safety cage'dir. ML eklerseniz, ML **cage'in içine** girer, cage'in yerine geçmez. Bunu bu terminolojiyle anlatmak, projeyi ECSS diline bağlar ve olgunluk algısını yükseltir.

---

<a id="b03-s6"></a>

### [B03] 6. Boşluk analizi

| # | Boşluk | Etki | Efor | Öncelik |
|---|---|---|---|---|
| S1 | Sentetik termal, ölçüm varken ikame olarak kullanılıyor | 🔴 Çok yüksek | Orta | **P0** |
| S2 | Sentetik gölge proxy'si, ölçüm varken kullanılıyor | 🔴 Yüksek | Düşük | **P0** |
| S3 | Doğrulama sirküler (elevasyon-sıcaklık korelasyonu) | 🔴 Yüksek | Çok düşük | **P0** |
| S4 | Sentetik katmanlar makine-okunabilir şekilde etiketli değil | 🟠 Yüksek | Düşük | **P0** |
| S5 | Ablasyon (A/B/C/D) yok → sentetiğin etkisi bilinmiyor | 🟠 Yüksek | Orta | **P1** |
| S6 | Hassasiyet analizi yok | 🟠 Orta | Düşük | P1 |
| S7 | +80 °C tepe sıcaklık kutup için fiziksel değil | 🟠 Orta | Çok düşük | P1 |
| S8 | Zaman ekseni yok (gölge süresi tanımsız) | 🟠 Yüksek | Yüksek | P1/P2 |
| S9 | ML eklenirse sim2real ölçüm planı yok | 🟡 Şartlı | Orta | P2 |

---

<a id="b03-s7"></a>

### [B03] 7. Yol haritası

#### P0 — "sentetiği dürüstçe etiketle" (yarım gün, kod değişmez)
1. `metadata.json`'a `physical_validity` + `model` bloğu (§4.1)
2. `validate_thermal_grid`'deki sirküler korelasyon kontrolünü kaldır veya "SANITY (not validation)" olarak yeniden adlandır
3. Frontend'de sentetik katmanlara **"SENTETİK — ölçüm değil"** badge'i
4. `T_max_base` değerini kutup için gerçekçi banda çek (~260 K / −13 °C) ve gerekçesini yaz

#### P1 — "gerçeği ekle, sentetiği kontrol kolu yap" (3–5 gün)
5. Diviner tbol + LOLA illumination indir/hizala → [01](#belge-01) §5, [07](#belge-07)
6. **A/B/C/D ablasyon koşusu** (§4.2) → `docs/research/ablation_report.md` üret
7. Hassasiyet testi (§4.3) CI'ya ekle
8. `validated_against` alanını doldur: sentetik vs Diviner RMSE / bias / korelasyon

**Kabul kriteri:** `docs/` altında şu tablo mevcut:

| Kol | Rota uzunluğu (m) | Enerji (Wh) | Max termal risk | D'den sapma (m) | Yanlış-güvenli hücre |
|---|---|---|---|---|---|
| A | … | … | … | … | … |
| B | … | … | … | … | … |
| C | … | … | … | … | … |
| D | … | … | … | 0 | 0 |

#### P2 — zaman ekseni ve ML (kapsam kararı gerektirir)
9. Basitleştirilmiş ephemeris + ufuk maskesi ile zaman-değişken aydınlanma (bkz. [07](#belge-07) §4)
10. ML eklenirse: ECSS safety cage çerçevesi + POLAR/POLAR-Sim ile sim2real eğrisi

---

<a id="b03-s8"></a>

### [B03] 8. Kırmızı çizgiler (asla yapma)

- ❌ Sentetik veriden üretilmiş bir sayıyı, kaynağını belirtmeden metrik olarak sunmak
- ❌ Sentetik veriyi kendisinden türeyen bir istatistikle "doğrulamak"
- ❌ Gerçek ürün mevcut ve erişilebilirken sentetik kullanıp bunu "veri yoktu" diye açıklamak
- ❌ Sentetik eğitim + sentetik test yapıp "%X doğruluk" iddia etmek
- ❌ Sentetik parametreleri sonuç iyi görünsün diye ayarlamak (`referans_belgesi_2.md` §11 buna davet ediyor: *"Termal grid'de tüm değerler çok soğuk → T_min_base ve T_max_base'i ayarla"* — bu, veriyi sonuca uydurmaktır ve **açıkça reddedilmeli**)

> Son madde ciddi bir problemdir ve mevcut belgede yazılı. Sorun giderme tablosundaki bu satır, "beklenen çıktıya göre girdiyi ayarla" demektir; bu, bilimsel geçerliliği ortadan kaldırır. **Düzeltme:** sıcaklıklar çok soğuk çıkıyorsa doğru aksiyon parametre ayarı değil, **gerçek veriye geçmektir.**

---

<a id="b03-s9"></a>

### [B03] Kaynaklar

- [ECSS-E-HB-40-02A — Space engineering: Machine learning qualification handbook (15 Kasım 2024)](https://ecss.nl/wp-content/uploads/2024/12/ECSS-E-HB-40-02A(15November2024).pdf)
- [ESA AI STAR — ECSS ML Qualification Handbook'a giriş](https://www.aistar.esa.int/advancing-the-european-space-industry-with-ai-introduction-to-the-ecss-e-hb-40-02a-machine-learning-qualification-handbook)
- [Sim2Dust: Mastering Dynamic Waypoint Tracking on Granular Media (arXiv 2508.11503)](https://arxiv.org/html/2508.11503)
- [Benchmarking Domain Randomisation for Visual Sim-to-Real Transfer (arXiv 2011.07112)](https://arxiv.org/pdf/2011.07112)
- [A Survey of Sim-to-Real Methods in RL (arXiv 2502.13187)](https://arxiv.org/pdf/2502.13187)
- [The Reality Gap in Robotics: Challenges, Solutions, and Best Practices (Annual Reviews)](https://www.annualreviews.org/content/journals/10.1146/annurev-control-031924-100130)
- [POLAR-Sim (arXiv 2309.12397)](https://arxiv.org/abs/2309.12397) · [NASA POLAR Stereo Dataset](https://ti.arc.nasa.gov/dataset/IRG_PolarDB/)
- [Image-Based Lunar Hazard Detection via Vision Transformers (Sensors 2023)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10535458/)
- [NASA Prithvi: first AI geospatial foundation model in orbit](https://science.nasa.gov/science-research/ai-foundation-model-in-orbit/)
- [Hayne et al. (2017), Global regolith thermophysical properties of the Moon from Diviner, JGR Planets](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/2017JE005387)

[↑ İçindekiler](#icindekiler) · [↑ Yönlendirme tablosu](#yonlendirme)

---

<a id="belge-04"></a>

## BELGE 04 — Açık Kaynak Model ve Araç Ekosistemi

> **Belge kimliği:** `BELGE 04` (bölüm başlıklarında `[B04]` etiketiyle işaretlidir) · **Kaynak dosya:** `04_acik_kaynak_modeller.md`  
> **Konu:** Araç zinciri, simülatörler, foundation model'ler, lisans  
> **Ana çıktı:** Bağımlılık ve model seçim matrisi  
> **Ayırt edici terimler:** `lisans`, `SPICE`, `OmniLRS`, `Apache`, `heat1d`, `cFS`, `TerraTorch`, `SpiceyPy`, `Nav2`, `LuSNAR`

> **Soru:** LunaPath'i gerçekleştirmek için neyi sıfırdan yazmalı, neyi hazır almalı? Hangi açık kaynak modeller ve araçlar var, lisansları ne, hangisi uçuşa/akademiye uygun?
>
> **Kısa cevap:** LunaPath'in yol haritasındaki işlerin **neredeyse hiçbiri sıfırdan yazılmak zorunda değil.** Termal model (heat1d), ufuk/aydınlanma hesabı (SPICE + ASP), simülatör (OmniLRS), veri seti (POLAR, LuSNAR), planlama altyapısı (Nav2, OMPL), uçuş yazılımı çatısı (cFS, F´), foundation model (Prithvi/Clay/TerraMind + TerraTorch) — hepsi açık ve olgun. Asıl karar **neyi almayacağınız**: her bağımlılık bir bakım ve nitelendirme yüküdür.

---

<a id="b04-s1"></a>

### [B04] 1. Mevcut bağımlılık envanteri (ve değerlendirmesi)

```
backend/requirements.txt   fastapi 0.115.6, uvicorn 0.34.0, rasterio 1.4.3,
                           numpy 2.2.1, scipy 1.15.0, pyproj 3.7.2, httpx
lunapath/requirements.txt  rasterio, numpy, matplotlib, scipy   (pin YOK)
frontend/package.json      react 18, three 0.183, vite 5, typescript 5
```

| Bulgu | Değerlendirme |
|---|---|
| Backend pin'li, `lunapath/` pin'siz | 🟠 Tutarsız. `lunapath/requirements.txt` de pin'lenmeli; aksi halde tekrar-üretilebilirlik ([01](#belge-01) §3.2) kırılır |
| `rasterio` + `pyproj` seçimi | ✅ Doğru. GDAL ekosisteminin Pythonic yüzü; planetary CRS desteği var |
| Ağır ML/CV yığını yok | ✅ Şu an doğru — gereksiz ağırlık taşınmıyor |
| Harita için Leaflet yok, **three.js** var | 🟡 Referans belge Leaflet planlıyor (§10), kod three.js'e geçmiş. Belge güncellenmeli. 3D görselleştirme için three.js daha güçlü ama coğrafi CRS desteği yok — piksel uzayında çalışmak zorunda |
| `matplotlib` sadece `lunapath/` içinde | ✅ Doğru ayrım (offline görselleştirme backend'e sızmıyor) |
| Lock dosyası yok (`requirements.txt` ≠ lock) | 🟠 `pip-tools` / `uv` ile `requirements.lock` üretin |
| SBOM yok | 🟡 Uzay/savunma bağlamında beklenir; `pip-audit` + `cyclonedx-py` ile 10 dakikalık iş |

**P0 aksiyonu:** `lunapath/requirements.txt`'i pin'le, tek bir `requirements.lock` üret, `pip-audit` CI adımı ekle.

---

<a id="b04-s2"></a>

### [B04] 2. Gezegen bilimi veri araç zinciri

Bu katmanda **hiçbir şey yazmayın** — 30 yıllık, doğrulanmış araçlar var.

| Araç | Ne yapar | Lisans | LunaPath'te nerede |
|---|---|---|---|
| **GDAL / rasterio** | Raster I/O, reproject, resample | MIT/X (GDAL: MIT-benzeri) | ✅ Kullanılıyor |
| **pyproj / PROJ** | CRS dönüşümleri (planetary CRS dahil) | MIT / X-11 | ✅ Kullanılıyor (`serializer.py`) |
| **SpiceyPy** (NAIF SPICE sarmalayıcı) | **Efemeris, güneş/Dünya pozisyonu, ışık geometrisi** | MIT (SpiceyPy); SPICE toolkit kendi lisansı | ❌ **Eksik — zaman ekseni için zorunlu** |
| **USGS ISIS** | Gezegen görüntü kalibrasyonu, kamera modelleri, projeksiyon | Public domain (US Gov) | ❌ NAC işlerseniz gerekli |
| **Ames Stereo Pipeline (ASP)** | Stereo DEM üretimi, SfS, bundle adjustment, **`sun_position`/gölge araçları** | Apache 2.0 | ❌ SfS/stereo yapacaksanız |
| **planetarypy / pvl** | PDS3/PDS4 etiket okuma | BSD/MIT | 🟡 PDS4 ürünlerine geçince gerekli |
| **GeoPandas / shapely** | ROI shapefile'ları (PGDA ürünleriyle gelir) | BSD | 🟡 Faydalı |
| **xarray + zarr** | Çok boyutlu (zaman × y × x) etiketli dizi, chunk'lı I/O | Apache 2.0 | ❌ **Zaman ekseni eklendiğinde neredeyse zorunlu** |
| **rioxarray** | rasterio ↔ xarray köprüsü | Apache 2.0 | 🟡 |

#### 2.1 Neden SpiceyPy kritik

LunaPath'in en büyük yapısal eksiği zaman ekseni ([03](#belge-03) §2.1-P5). Zamanı doğru yapmanın tek ciddi yolu **efemeris**tir. SPICE ile:

```python
import spiceypy as spice
spice.furnsh("kernels/lunapath.tm")   # meta-kernel: LSK, PCK, SPK

def sun_azel_at(et, lon_deg, lat_deg):
    """Verilen efemeris zamaninda (et), Ay yuzeyindeki bir noktada
    Gunes'in azimut/elevasyonunu dondurur. MOON_ME sabit gövde çerçevesi."""
    # subsolar / illumination geometry:
    _, _, solar_inc, emission, phase = spice.ilumin(
        "Ellipsoid", "MOON", et, "MOON_ME", "LT+S", "SUN", point_xyz)
    return 90.0 - np.degrees(solar_inc), azimuth_from(...)
```

Gerekli kernel'lar (NAIF'ten ücretsiz): `naif0012.tls` (leapseconds), `pck00011.tpc` / `moon_pa_de440_200625.bpc` (gövde yönelimi), `de440s.bsp` (gezegen efemerisi), `moon_de440_220930.tf` (çerçeveler).

**Kernel'lar toplamda birkaç yüz MB'tır** — repoya koymayın, indirme script'i yazın.

#### 2.2 Ufuk (horizon) hesabı — kendiniz yazmalı mısınız?

Aydınlanma haritası hazır ürün olarak indirilebiliyor ([01](#belge-01)), ama **kendi DEM'iniz üzerinde arbitrary zamanda** aydınlanma istiyorsanız ufuk hesabı gerekir. Bu, yazmanız gereken **ender** bileşenlerden biridir çünkü tam olarak sizin grid'inize özel.

Standart algoritma (Mazarico vd.'nin kutup illumination çalışmalarında kullanılan yaklaşımın basitleştirilmiş hali):

```python
def horizon_elevation_map(elev, res_m, n_azimuth=360, max_range_m=50_000):
    """Her piksel icin, her azimutta ufuk yukseklik acisi (derece).
    Cikti: (n_azimuth, H, W) — buyuk! chunk'la veya azaltilmis azimutla calis.

    Yontem: her azimut icin ray-marching; ilerledikce
    max(atan((z_j - z_0) / d_j)) izlenir.
    Kure egriligi duzeltmesi: z_eff = z_j - d_j^2 / (2 R_moon)
    """
```

**Hesap yükü uyarısı:** 500×500 grid, 360 azimut, 625 adım (50 km / 80 m) = **56 milyar işlem** → saf Python imkânsız. Çözümler:
- Azimut sayısını 72'ye (5°) düşür → 11 milyar
- `numba.njit(parallel=True)` veya `cupy` (GPU)
- **En pratik:** hazır illumination ürününü kullan, kendi hesabını sadece küçük koridorlarda yap

Bu, [08](#belge-08)'in ana temasının bir örneğidir: doğru cevap "her yerde her şeyi hesapla" değil, **hiyerarşi**dir.

---

<a id="b04-s3"></a>

### [B04] 3. Termal modelleme — hazır açık kaynak

| Araç | Ne yapar | Lisans | Değerlendirme |
|---|---|---|---|
| **heat1d** ([github.com/phayne/heat1d](https://github.com/phayne/heat1d)) | 1-B gezegen termal modeli (Hayne'in kendi kodu, Diviner ekibi) | Açık (repo lisansını doğrulayın) | ⭐ **En yüksek getirili tek bağımlılık.** Diviner türev ürünlerinin arkasındaki model ailesinden |
| **KRC** (Mars/Ay termal modeli, USGS) | Termofiziksel model | Public domain | 🟡 Fortran; kurulum eforu var |
| **Hayne et al. 2017 H-parametresi** | Derinliğe bağlı yoğunluk/iletkenlik modeli | Yayın | ⭐ Parametre kaynağı olarak kullan |

`heat1d` ile LunaPath'in kazandığı şey: **sıcaklığı bir harita olarak okumak yerine, bir rover'ın gölgeye girip çıkarken yüzey/derinlik sıcaklık geçmişini simüle etmek.** Bu, `THERMAL_TAU_S = 7200` gibi tek bir zaman sabitini fiziksel bir modelle değiştirir → detay [07](#belge-07).

---

<a id="b04-s4"></a>

### [B04] 4. Simülatörler — LunaPath'e ne kadar gerekli?

| Simülatör | Temel | Öne çıkan | Lisans | LunaPath için |
|---|---|---|---|---|
| **OmniLRS** ([github.com/OmniLRS/OmniLRS](https://github.com/OmniLRS/OmniLRS), [arXiv 2309.08997](https://ar5iv.labs.arxiv.org/html/2309.08997)) | NVIDIA Isaac Sim / Omniverse | **Hızlı prosedürel Ay arazi üretimi, çok-robot, sentetik veri pipeline'ı, ROS1+ROS2 binding** | Açık kaynak (repo) | ⭐ Sentetik görüntü/veri gerekirse **birinci tercih** |
| **LunarSim** ([github.com/PUTvision/LunarSim](https://github.com/PUTvision/LunarSim)) | — | Yüksek görsel doğruluk, ROS 2, CV algoritma geliştirme odaklı | Açık kaynak | 🟡 OmniLRS'e alternatif, daha hafif |
| **Isaac Lab / Isaac Sim** | Omniverse | Yüksek doğruluklu fizik, RL eğitim çatısı | Ücretsiz (NVIDIA lisansı), GPU şart | 🟡 RL yapacaksanız |
| **Gazebo (Harmonic)** | ODE/DART/Bullet | Olgun, hafif, eklenti mimarisi | Apache 2.0 | ✅ Hafif ihtiyaçlar için |
| **CoppeliaSim + Bullet** | — | Lunar micro-rover coverage çalışmasında kullanıldı ([arXiv 2404.18721](https://arxiv.org/html/2404.18721v1)) | Ücretsiz (edu) / ticari | 🟡 |
| **Project Chrono** | Çoklu-cisim + granüler (DEM/SPH) | POLAR-Sim'in arkasındaki motor; **tekerlek-regolit etkileşimi** | BSD-3 | ⭐ Terramekanik ciddiyet isterseniz |
| **CARLA türevi "Lunar Simulator"** | CARLA | Ay için uyarlanmış | MIT (CARLA) | 🟢 Niş |

#### 4.1 Karar: LunaPath simülatöre girmeli mi?

**Hayır — mevcut kimlik için gerekli değil.** LunaPath bir **görev öncesi planlama / karar destek** aracıdır ([09](#belge-09)); simülatör, rover üzeri otonomi geliştirirseniz gerekir. Simülatöre girmek:

- ➕ Sentetik görüntü/LiDAR üretir, ML eğitimi mümkün olur, yerel planlayıcı test edilebilir
- ➖ GPU + kurulum + öğrenme eğrisi (Isaac Sim'de günler), ekip odağını dağıtır, sim2real yükü doğar

**Önerilen orta yol:** Simülatör kurmayın, ama **simülatör çıktılarını (veri setleri) kullanın**. LuSNAR (108 GB, hazır UE sahneleri) ve POLAR-Sim, simülatör kurmadan sentetik veri erişimi sağlar.

---

<a id="b04-s5"></a>

### [B04] 5. Planlama ve navigasyon kütüphaneleri

| Kütüphane | Ne verir | Lisans | Değerlendirme |
|---|---|---|---|
| **ROS 2 + Nav2** | Global/local planner ayrımı, costmap_2d katman mimarisi, recovery behaviors, behavior tree | Apache 2.0 | ⭐ **Mimari şablon olarak paha biçilmez** (kod olarak almasanız da) |
| **OMPL** | Örnekleme tabanlı planlayıcılar (RRT*, PRM, BIT*) | BSD-3 | 🟡 Grid tabanlı problemde gereksiz |
| **`networkx`** | Genel graf algoritmaları | BSD | ❌ Referans belge doğru reddetmiş ("çok ağır") |
| **`heapq` (stdlib)** | Öncelik kuyruğu | PSF | ✅ Kullanılıyor, doğru seçim |
| **`numba`** | JIT ile A* çekirdeğini 10–100× hızlandırma | BSD-2 | ⭐ **En düşük maliyetli performans kazancı** |
| **`scikit-image`** | Morfoloji, mesafe dönüşümü (`distance_transform_edt` → koridor açıklığı!) | BSD-3 | ⭐ `path_corridor_clearance_m` için hazır |
| **`pathfinding` / `python-astar`** | Hazır A* | MIT | ❌ Kendi maliyet modelinizle uyumsuz; kendi A*'ınız doğru karar |

#### 5.1 Nav2'nin costmap katman mimarisini ödünç alın

Nav2'nin en değerli fikri kodu değil, **deseni**: costmap tek bir dizi değil, üst üste binen **katmanlar** (static, obstacle, inflation, ...) ve her katman kendi güncelleme döngüsüne sahip. LunaPath'te bugün `cost_grid` tek seferde hesaplanıp donuyor (`compute_cost_grid`). Katmanlı yapıya geçmek:

```python
# backend/app/costmap.py (yeni)
class CostLayer(Protocol):
    name: str
    validity: Literal["MEASURED", "DERIVED", "MODEL"]
    def contribution(self, ctx: PlanContext) -> np.ndarray: ...
    def is_static(self) -> bool: ...   # True -> bir kez hesapla, cache'le

class CostMap:
    def __init__(self, layers: list[CostLayer]): ...
    def total(self, ctx) -> np.ndarray:
        # static katmanlar cache'ten, dinamikler her cagrida
        ...
    def explain(self, row, col, ctx) -> dict[str, float]:
        """Bu hucrenin maliyetine hangi katman ne kadar katki yapti?"""
```

**`explain()` metodu, LunaPath'in "neden bu rota seçildi" hedefinin ([ay_termal_navigasyon_proje_dokumani.md](../archive/ay_termal_navigasyon_proje_dokumani.md) §8 Modül 8) doğru teknik cevabıdır** ve mevcut `/api/cell-telemetry` endpoint'inin (`main.py:279`) doğal uzantısıdır.

---

<a id="b04-s6"></a>

### [B04] 6. Uçuş yazılımı çatıları (uçuş iddiası kurarsanız)

| Çatı | Sahip | Lisans | Not |
|---|---|---|---|
| **NASA cFS (core Flight System)** | NASA GSFC | Apache 2.0 | Uçuşta kanıtlanmış; app tabanlı mimari; HPSC ile birlikte tanıtılıyor |
| **F´ (F Prime)** | NASA JPL | Apache 2.0 | Küçük uçuş sistemleri; **Ingenuity'de uçtu**; C++; öğrenmesi cFS'ten kolay |
| **Basilisk** | ASU/LASP | ISC | Astrodinamik simülasyon çatısı |
| **NASA 42** | GSFC | NOSA | Tutum/dinamik simülasyonu |
| **KubOS / Zephyr / RTEMS / VxWorks** | Çeşitli | Çeşitli / ticari | RTOS katmanı |

**LunaPath için tavsiye:** Kod olarak benimsemeyin. Ama mimari belgede **"onboard tarafa taşınırsa F´ veya cFS app'i olarak paketlenir"** cümlesini kurun ve modül sınırlarınızı buna uygun tutun (saf fonksiyonlar, I/O'dan ayrık çekirdek). Bu tek cümle, olgunluk algısını ciddi biçimde yükseltir ve zaten mevcut kod yapısıyla uyumludur (`cost_engine.py` saf fonksiyonlardan oluşuyor — bu iyi).

---

<a id="b04-s7"></a>

### [B04] 7. Açık kaynak ML modelleri

#### 7.1 Coğrafi/uzaktan algılama foundation model'leri

Şu an üretime hazır sayılan üçlü ve destek araçları:

| Model | Geliştiren | Ne için | Erişim |
|---|---|---|---|
| **Prithvi-EO-2.0** | NASA + IBM | Genel EO temel modeli; **yörüngede çalışan ilk coğrafi foundation model** | Hugging Face, açık |
| **Clay v1.5** | Clay Foundation | Farklı kaynak/çözünürlüklere esnek | Açık |
| **TerraMind** | IBM + ESA (2025) | **Çok-modlu**: optik + SAR + **DEM** ortak eğitim | Açık |
| **DOFA** | — | Frekans-farkında mimari, çapraz-sensör genelleme | Açık |
| **SatMAE / ScaleMAE** | — | Masked autoencoder; etiketsiz görüntüden temsil | Açık |
| **TerraTorch** ([torchgeo/terratorch](https://github.com/torchgeo/terratorch)) | — | **Yukarıdakilerin tümü için fine-tune araç kiti** | Apache 2.0 |

**Kritik uyarı — bunlar Dünya modelleridir.** Prithvi HLS/Sentinel çok-bantlı Dünya verisiyle, 13 yıllık gözlem üzerine eğitildi. Ay'da:
- Bant yapısı uyuşmaz (NAC tek kanallı pankromatik)
- İstatistikler uyuşmaz (albedo, kontrast, gölge rejimi tamamen farklı)
- Ön-eğitim domain'i uzak → transfer kazancı belirsiz

**Yine de denemeye değer** çünkü fine-tune maliyeti düşük ve literatür ön-eğitimli başlatmanın rastgele başlatmadan **daha hızlı yakınsadığını** gösteriyor. Ama **iddia etmeden önce ölçün** — baseline olarak ImageNet-önceden-eğitimli bir ResNet/ViT ve sıfırdan bir UNet mutlaka bulunsun ([02](#belge-02) §3.2'deki ViT vs UNet karşılaştırması tam bu deseni izliyor).

#### 7.2 Görev-özel modeller

| Model | Görev | Not |
|---|---|---|
| **YOLOv5/v8/v11** | Kaya (boulder) tespiti | Ay kaya tespiti literatürü **YOLOv5s6 fine-tune** ile çalışıyor; ~12.000 etiketli kaya açık ✅ |
| **SAM / SAM 2** | Sıfır-shot segmentasyon | Prompt tabanlı; etiketleme hızlandırıcı olarak ideal (insanı %10 işe indirir) |
| **DINOv2/v3** | Kendini-denetimli görsel temsil | Ay görüntüsünde etiketsiz ön-eğitim için güçlü aday |
| **UNet / SegFormer / Mask2Former** | Semantik segmentasyon | LuSNAR benchmark'ı bunlarla kıyaslanıyor |
| **Depth Anything v2** | Monokular derinlik | Stereo çalışmadığında (kutupta doku yok) ilginç yedek |

#### 7.3 LunaPath'e ML **eklemeli mi?**

`lunapath_referans_belgesi_2.md` ML'i scope dışına almış (§9: *"Scope dışı — zaman kalırsa: cost weight suggestion (Nelder-Mead)"*). **Bu karar doğruydu ve büyük ölçüde hâlâ doğru.** Ancak "gerçekleştirme" fazında iki ML fırsatı gerçekten yüksek getirili:

**(a) Kaya tespiti (denetimli, offline, yörünge görüntüsü)** — düşük risk, açık eğitim verisi, doğrudan yeni bir bağımsız veri kanalı üretir. **Öneri: yap.**

**(b) Ağırlık öğrenme / tercih öğrenme (inverse RL)** — "operatörün seçtiği rotalardan ağırlıkları öğren". Bilimsel olarak çekici ama **veri yok** (operatör tercihi yok). **Öneri: yapma**, ama AHP ağırlıklarına **duyarlılık analizi** yap (bu, ML olmadan aynı soruyu cevaplar).

**Yapmayın listesi:**
- ❌ End-to-end RL ile rota üretimi. Literatürde var ([Learning-Based End-to-End Path Planning for Lunar Rovers](https://pmc.ncbi.nlm.nih.gov/articles/PMC7866010/), [Deep Learning Approach to Lunar Rover Global Path Planning](https://www.mdpi.com/1424-8220/24/3/844)) ama LunaPath'in güçlü yanı **açıklanabilirlik**tir; RL bunu yok eder ve ECSS safety cage gereksinimini zorlaştırır.
- ❌ LLM ile "rota açıklaması üretmek". Cazip görünür, hiçbir teknik değer katmaz, hallucination riski taşır. `explain()` (§5.1) deterministik ve daha güçlü.

---

<a id="b04-s8"></a>

### [B04] 8. Lisans, ihracat ve atıf

| Konu | Kural | LunaPath aksiyonu |
|---|---|---|
| **Proje lisansı** | MIT (repoda mevcut) | ✅ Uygun; permissive |
| **GPL bulaşması** | GPL'li bir kütüphaneyi link'lerseniz MIT dağıtımınız sorun yaşar | Bağımlılık lisanslarını tarayın (`pip-licenses`) |
| **NASA yazılımı** | Genellikle Apache 2.0 veya NOSA; NOSA GPL-uyumlu değildir | cFS/F´ Apache 2.0 → sorun yok; 42 NOSA → dikkat |
| **NVIDIA Isaac** | Kendi EULA'sı, ücretsiz ama açık kaynak değil | Kullanırsanız README'de belirtin |
| **Veri lisansları** | NASA PDS kamu malı, atıf beklenir; Zenodo türevleri CC-BY olabilir; JAXA/Kaguya ayrı koşullar | `docs/DATA_LICENSES.md` → [01](#belge-01) §3.7 |
| **ITAR / EAR** | Uzay yazılımı bazı yargı alanlarında ihracat kontrolüne tabidir. **Açık kaynak, kamuya açık akademik veri ve genel amaçlı algoritmalar tipik olarak kapsam dışıdır**, ancak spesifik rover uçuş yazılımı olabilir | Şu an risk yok (kamu verisi + genel algoritma). Gerçek bir rover programına bağlanırsa **hukuki danışmanlık gerekir** — bunu bir riskler maddesi olarak kaydedin |

---

<a id="b04-s9"></a>

### [B04] 9. Seçim matrisi — LunaPath için nihai öneri

| Katman | Al (adopt) | Yazma | Erteleme (defer) |
|---|---|---|---|
| Raster I/O & CRS | ✅ rasterio, pyproj | — | — |
| Efemeris/geometri | ✅ **SpiceyPy** (+ NAIF kernel'ları) | — | — |
| Zaman-boyutlu dizi | ✅ **xarray** (+ zarr) | — | — |
| Termal fizik | ✅ **heat1d** | — | KRC |
| Ufuk/aydınlanma | 🟡 hazır ürün al; koridor için **kendi ray-marching**'ini yaz (numba) | — | Tam-alan ufuk hesabı |
| Hızlandırma | ✅ **numba** | — | Cython, GPU |
| Morfoloji/mesafe | ✅ **scikit-image** | — | — |
| Kaya tespiti | ✅ **YOLO + açık Ay kaya veri seti** | — | Krater tespiti |
| Foundation model | 🟡 **TerraTorch + Prithvi** (deneysel, ölçerek) | — | Kendi ön-eğitim |
| Etiketleme | ✅ **SAM 2** (hızlandırıcı) | — | — |
| Costmap mimarisi | 🟡 **Nav2 deseni** (kod değil, tasarım) | ✅ Kendi `CostMap` sınıfı | Nav2 entegrasyonu |
| Planlayıcı çekirdeği | — | ✅ **Kendi A*/D* Lite** (maliyet modeli özel) | OMPL |
| Simülatör | ❌ Kurmayın | — | OmniLRS (ML'e girerseniz) |
| Veri setleri | ✅ POLAR, POLAR-Sim, LuSNAR (indir, kullan) | — | — |
| Uçuş yazılımı | ❌ | — | F´ / cFS (uçuş iddiası doğarsa) |
| ML rota planlama | ❌ Yapmayın | — | — |

---

<a id="b04-s10"></a>

### [B04] 10. Yol haritası

#### P0 (yarım gün)
1. `lunapath/requirements.txt` pin'le, `requirements.lock` üret
2. `pip-audit` + `pip-licenses` CI adımı
3. README'ye "üçüncü taraf bileşenler ve lisansları" bölümü

#### P1 (2–4 gün)
4. **SpiceyPy + kernel indirme script'i** → güneş azimut/elevasyon fonksiyonu (zaman ekseninin temeli)
5. **numba** ile A* çekirdeği JIT — ölçülmüş öncesi/sonrası benchmark ile
6. **scikit-image** `distance_transform_edt` → `path_corridor_clearance_m` metriği
7. `CostMap` + `CostLayer` refaktörü, `explain()` dahil

#### P2 (5–10 gün)
8. **heat1d** entegrasyonu → [07](#belge-07)
9. Koridor için numba ray-marching ufuk hesabı
10. Kaya tespiti (YOLO fine-tune) → [02](#belge-02)
11. Mimari belgeye "F´/cFS uyumlu modül sınırları" bölümü

#### Kabul kriterleri
- [ ] Tüm bağımlılıklar pin'li, lock dosyası var, SBOM üretilebiliyor
- [ ] Lisans envanteri belgeli, GPL bulaşması yok
- [ ] `spiceypy` ile verilen bir UTC zamanında güneş azimut/elevasyon üretilebiliyor
- [ ] A* benchmark'ı öncesi/sonrası ölçülmüş (hedef: 500×500'de <500 ms)
- [ ] `CostMap.explain(row, col)` her katmanın katkısını döndürüyor

---

<a id="b04-s11"></a>

### [B04] Kaynaklar

- [OmniLRS: A Photorealistic Simulator for Lunar Robotics (arXiv 2309.08997)](https://ar5iv.labs.arxiv.org/html/2309.08997) · [GitHub](https://github.com/OmniLRS/OmniLRS)
- [LunarSim (GitHub, PUTvision)](https://github.com/PUTvision/LunarSim)
- [POLAR-Sim (arXiv 2309.12397)](https://arxiv.org/abs/2309.12397)
- [LuSNAR dataset (GitHub)](https://github.com/zqyu9/LuSNAR-dataset) · [arXiv 2407.06512](https://arxiv.org/abs/2407.06512)
- [heat1d — Thermal model for planetary science (phayne)](https://github.com/phayne/heat1d)
- [Hayne et al. (2017), Global regolith thermophysical properties, JGR Planets](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/2017JE005387)
- [TerraTorch — GFM fine-tuning toolkit](https://github.com/torchgeo/terratorch)
- [Awesome Remote Sensing Foundation Models](https://github.com/Jack-bo1220/Awesome-Remote-Sensing-Foundation-Models)
- [NASA Prithvi — first geospatial foundation model in orbit](https://science.nasa.gov/science-research/ai-foundation-model-in-orbit/)
- [Global Lunar Boulder Map from NAC using Deep Learning (JGR Planets 2025)](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2025JE008981)
- [Learning-Based End-to-End Path Planning for Lunar Rovers with Safety Constraints](https://pmc.ncbi.nlm.nih.gov/articles/PMC7866010/)
- [A Deep Learning Approach to Lunar Rover Global Path Planning (Sensors 24(3), 844)](https://www.mdpi.com/1424-8220/24/3/844)
- [Risk-Aware Coverage Path Planning for Lunar Micro-Rovers (arXiv 2404.18721)](https://arxiv.org/html/2404.18721v1)
- [The Dawn of the HPSC Era in Space Computing (Microchip white paper)](https://ww1.microchip.com/downloads/aemDocuments/documents/MPU64/ProductDocuments/SupportingCollateral/Dawn-of-HPSC-Era-in-Space-Computing-White-Paper.pdf)
- [cFS on HPSC (NTRS 20250000356)](https://ntrs.nasa.gov/api/citations/20250000356/downloads/Powell-cFS-2025-HPSC_for2025Jan29.pdf)

[↑ İçindekiler](#icindekiler) · [↑ Yönlendirme tablosu](#yonlendirme)

---

<a id="belge-05"></a>

## BELGE 05 — Engel Kaçınma

> **Belge kimliği:** `BELGE 05` (bölüm başlıklarında `[B05]` etiketiyle işaretlidir) · **Kaynak dosya:** `05_engel_kacinma.md`  
> **Konu:** Hazard detection, yerel planlayıcı, GESTALT/ENav, slip  
> **Ana çıktı:** İki katmanlı navigasyon mimarisi  
> **Ayırt edici terimler:** `slip`, `D* Lite`, `traversability`, `GESTALT`, `ENav`, `CADRE`, `Yutu-2`

> **Soru:** LunaPath'te engel kaçınma var mı? Gerçek rover'lar bunu nasıl yapıyor? LunaPath'e ne eklenmeli, neresi kapsam dışı bırakılmalı?
>
> **Kısa cevap:** LunaPath'te **engel kaçınma yok** — sadece bir *engel maskesi* var (`traversability_grid`). Bu ikisi aynı şey değildir. Engel maskesi "haritada bildiğim engelleri atla" der; engel kaçınma "yolda karşılaştığım bilinmeyen engelden kurtul" demektir. Gerçek rover'lar bunu **iki ayrı katmanda** yapar ve LunaPath şu an sadece üst katmanı temsil ediyor. Dürüst konumlandırma: LunaPath **global planlayıcıdır**; engel kaçınma onun **tüketicisidir**, parçası değil.

---

<a id="b05-s1"></a>

### [B05] 1. Terminolojiyi netleştir (bu, sunumda en çok karışan yer)

| Terim | Ne yapar | Zaman ölçeği | LunaPath'te |
|---|---|---|---|
| **Traversability analysis** | Haritadan "burası geçilebilir mi" | Offline | ✅ Var (`traversability.py`) |
| **Global path planning** | Başlangıç→hedef optimal rota | Offline / dakikalar | ✅ Var (`pathfinder.py` A*) |
| **Local path planning** | Sonraki 5–20 m için yörünge | Saniyeler | ❌ Yok |
| **Hazard detection** | Sensörle anlık tehlike tespiti | 0.1–2 s | ❌ Yok |
| **Obstacle avoidance** | Tespit edilen tehlikeden kaçınma manevrası | 0.1–2 s | ❌ Yok |
| **Replanning** | Yeni bilgiyle global rotayı güncelleme | Saniyeler–dakikalar | 🟡 Kısmi (`/api/replan` endpoint'i planlanmış) |
| **Recovery / safe haven** | Sıkışma/kritik durumda kurtarma | Dakikalar–saatler | 🟡 Belgede var, kodda yok |

**LunaPath'in şu an yaptığı iş satır 1–2'dir.** `main.py`'de `/api/replan` referans belgede tanımlı ama endpoint listesinde görünmüyor — bu, en yakın genişleme noktasıdır.

---

<a id="b05-s2"></a>

### [B05] 2. Gerçek rover'lar nasıl yapıyor?

#### 2.1 MER/MSL kuşağı: GESTALT

Mars keşif rover'larının otonom navigasyon çekirdeği **GESTALT** (Grid-based Estimation of Surface Traversability Applied to Local Terrain) yaklaşımıdır. Temel fikir:

1. Stereo görüntüden **yerel yükseklik haritası** (local elevation map) üret
2. Her hücre için bir **"goodness"** skoru hesapla: eğim, pürüzlülük, basamak yüksekliği, veri yoğunluğu
3. Rover'ın **fiziksel ayak izini** (footprint) hücrenin üzerine yerleştir ve o footprint'in güvenliğini değerlendir
4. Aday **yay (arc)** hareketlerini goodness haritası üzerinde puanla
5. En iyi yayı seç, kısa mesafe (0.5–1 m) sür, tekrar et

**Kritik tasarım kararı:** GESTALT hücre-bazlı değil, **footprint-bazlı** değerlendirir. Rover 2 m genişse, 1 m'lik bir kaya bir hücreyi değil, footprint'i etkiler. LunaPath'te bu hiç modellenmiyor: hücre maliyeti tek bir noktanın maliyetidir, rover'ın gövdesi yoktur.

#### 2.2 Mars 2020 (Perseverance): ENav + ACE

Perseverance'ın **ENav** (Enhanced Navigation) yazılımı GESTALT'ın evrimi:

- Aday yolları **sıralar**, sonra en yüksek sıralı yolları **ACE** (Approximate Clearance Evaluation) algoritmasıyla güvenlik açısından değerlendirir
- Üç bütünleşik yetenek: **HazDet** (navcam ile engel tespiti + otomatik alternatif rota), **VO** (görsel odometri ile hareket kestirimi), ve **"Thinking-While-Driving"** — sürerken aynı anda VO yapıp arazi haritası üretip yay harmanlama/seçme
- Ölçek kanıtı: **Sol 1312 (28 Ekim 2024) itibarıyla 32.1 km sürüşün ~%90'ı ENav ile arazi değerlendirilerek yapıldı**

**ACE'nin fikri LunaPath için doğrudan alınabilir:** ACE, kesin bir "geçilebilir/geçilemez" ikilisi yerine **açıklık (clearance) payı** hesaplar. Bu, [01](#belge-01) §3.4'te önerilen belirsizlik bandı yaklaşımının aynısıdır ve LunaPath'e 20 satır kodla girer.

#### 2.3 Ay tarafındaki durum: otonomi seviyeleri çok farklı

| Rover | Otonomi seviyesi | Kanıt |
|---|---|---|
| **Yutu-2** (Chang'e-4, 2019–) | 🟢 En yüksek Ay otonomisi: **görsel SLAM + rota planlama + rover kontrolü**; öncülü Yutu'ya göre lokalizasyon, haritalama, otonom navigasyon ve hareket planlamada belirgin ilerleme; 6+ yıl operasyon | Yayınlanmış görsel lokalizasyon çalışmaları |
| **Pragyan** (Chandrayaan-3, 2023) | 🟡 **Yer-döngüde (ground-in-the-loop)**: her hareket için navigasyon kamerası verisi Dünya'ya indirilip DEM üretiliyor, sonra komut gidiyor; tek komutta **en fazla ~5 m** | Basında ve teknik değerlendirmelerde belirtildi |
| **CADRE** (JPL, IM-3 ile, pencere 2026'ya uzanıyor) | 🟢 **Çok-robot dağıtık otonomi** teknoloji gösterimi; her rover el bagajı boyutunda, 2 stereo kamera + navigasyon sensörleri + multistatik GPR; doğrudan komut almadan işbirliği | JPL CADRE sayfası |
| **Tenacious** (ispace M2, 2025) | 🟡 Lander'a yakın, dairesel, **saniyede birkaç cm**; misyon iniş anomalisiyle kayboldu | ispace açıklamaları |
| **VIPER** (2027 hedefi, Blue Moon MK1) | 🟢 Kutup, PSR'a girme, matkap; termal/enerji kısıtlı planlama | NASA/Blue Origin |

**LunaPath için önemli çıkarım:** Ay'da Pragyan seviyesinde bir yer-döngü mimarisi **hâlâ operasyonel gerçeklik**. Bu, LunaPath'in "görev öncesi planlama aracı" konumlandırmasının **zayıflık değil, sektörle uyum** olduğu anlamına gelir. Pragyan tarzı bir operasyonda LunaPath'in ürettiği rota, insan operatörün karar destek girdisidir — bu tam olarak gerçek bir ihtiyaçtır.

---

<a id="b05-s3"></a>

### [B05] 3. Ay kutbuna özel engel kaçınma zorlukları

| Zorluk | Neden Ay kutbunda daha kötü | Etkisi |
|---|---|---|
| **Güneş ufukta (~1.5°)** | Uzun, keskin gölgeler arazi özelliklerini saklar | Stereo korelasyon başarısız; gölge = "bilgi yok" bölgesi |
| **Dinamik aralık** | Aydınlık kaya + kalıcı gölge aynı karede | HDR zorunlu; doygunluk/gürültü |
| **Doku yokluğu** | Feature-sparse regolit | VO ve stereo drift |
| **Doğrudan güneşe bakış** | Rover ufka doğru bakınca güneş kadraja girer | Flare, kör bölge |
| **Gölge içi görüş** | Sinyal ≈ gürültü | Aktif aydınlatma (LED/lazer) veya termal kamera gerekir |
| **Toz** | Elektrostatik yapışkan regolit, optik yüzey kirlenmesi | Zamanla performans düşüşü |
| **Slip** | Eğimli, gevşek regolit | Kat edilen mesafe ≠ komut edilen mesafe |
| **İletişim penceresi** | Kutupta Dünya görünürlüğü topografyaya bağlı | Yer-döngü mimarisi kesintiye girer |
| **Termal** | Gölgede kalma süresi donanımı sınırlar | Kaçınma manevrası **termal bütçeyi** harcar |

**Son madde LunaPath için özgün bir katkı fırsatı:** Klasik engel kaçınma literatüründe kaçınma manevrasının maliyeti "ekstra mesafe"dir. Ay kutbunda kaçınma manevrasının maliyeti **ekstra gölge süresi ve termal stres**tir. Yani:

> *"Engelden kaçınmak için 40 m sağa saptım" → "bu sapma beni 8 dakika daha gölgede tuttu, iç sıcaklığım 3 K düştü, termal bütçemin %6'sını harcadım."*

Bu, LunaPath'in maliyet modelinin **yerel katmana taşınmış hali**dir ve literatürde az işlenmiş bir açıdır. Ayırt edici özellik olarak öne çıkarılabilir.

#### 3.1 Slip / terramekanik

Regolit üzerinde eğim arttıkça **slip oranı üstel olarak artar** (lunar micro-rover coverage çalışması bunu pitch açısıyla traversability metriği olarak kullanıyor). Bu, LunaPath'in enerji modelinde eksik:

```python
# cost_engine.py: f_energy su an sadece egim ve mesafeye bakiyor
# Eksik: slip nedeniyle harcanan bosa enerji
def slip_ratio(theta_deg: float, soil="regolith") -> float:
    """Kabaca: i = i0 * exp(k * theta). Literaturde kalibrasyon gerekir.
    i=0.2 -> komut edilen 1 m icin gercekte 0.8 m ilerlenir."""
    return min(0.9, 0.02 * math.exp(0.11 * theta_deg))

def effective_distance(d_m, theta_deg):
    return d_m / (1.0 - slip_ratio(theta_deg))
```

`slip_ratio(20°) ≈ 0.18` → 20° eğimde enerji ve süre **%22 daha yüksek**. Bu, `f_energy`'nin sistematik olarak iyimser olduğu anlamına gelir. Düzeltme tek satırlıktır ve fiziksel gerekçesi güçlüdür.

---

<a id="b05-s4"></a>

### [B05] 4. LunaPath için önerilen iki katmanlı mimari

```
┌────────────────────────────────────────────────────────────────┐
│  KATMAN 1 — GLOBAL (LunaPath'in bugünkü işi)                   │
│  Girdi : yörünge verisi (DEM, Diviner, illumination, PSR, NAC)  │
│  Çıktı : koridor + waypoint dizisi + termal/enerji bütçesi      │
│  Ölçek : 20–80 m hücre, 10–40 km, saatler-günler                │
│  Yer   : YERDE (görev öncesi) veya rover'da (nadiren)           │
│  Algo  : çok kriterli A* / D* Lite                              │
└──────────────────────────┬─────────────────────────────────────┘
                           │ koridor + bütçe + fallback noktaları
┌──────────────────────────▼─────────────────────────────────────┐
│  KATMAN 2 — LOKAL (kapsam dışı, arayüz tanımlı)                 │
│  Girdi : stereo/LiDAR + koridor kısıtı + kalan bütçe            │
│  Çıktı : yay/yörünge komutu (0.5–20 m)                          │
│  Ölçek : 0.1–0.5 m hücre, 5–20 m, saniyeler                     │
│  Yer   : ROVER'DA                                               │
│  Algo  : GESTALT/ENav benzeri arc değerlendirme, DWA veya MPC    │
└────────────────────────────────────────────────────────────────┘
```

#### 4.1 Katman 1'in Katman 2'ye vermesi gereken şey — "koridor sözleşmesi"

LunaPath'in çıktısı bugün bir **piksel dizisi**. Bu, yerel planlayıcı için yeterli değil. Yerel planlayıcının ihtiyacı:

```python
# backend/app/schemas.py'ye eklenecek
class Corridor(BaseModel):
    """Global planlayicinin yerel planlayiciya verdigi sozlesme."""
    waypoints: list[tuple[float, float]]     # metre, proje CRS'inde
    half_width_m: list[float]                # her segment icin izinli yanal sapma
    max_slope_deg: list[float]               # segment bazli egim limiti
    thermal_budget_K_s: list[float]          # segment icin ayrilan termal stres butcesi
    energy_budget_wh: list[float]            # segment icin ayrilan enerji
    time_window_utc: list[tuple[str, str]]   # segmentin gecerli oldugu zaman penceresi
    fallback_points: list[tuple[float, float]]  # en yakin safe haven / bekleme noktasi
    replan_triggers: dict                    # hangi kosulda global'e geri don
```

**Bu şema, LunaPath'i "rota çizen bir demo"dan "bir otonomi yığınının üst katmanı"na dönüştürür** — kod yazmadan, sadece çıktı formatını doğru tanımlayarak. Olgunluk açısından bu, en yüksek getirili düşük-maliyetli hamledir.

`half_width_m` nasıl hesaplanır: `scikit-image`'ın `distance_transform_edt` fonksiyonu ile, `traversable=False` hücrelere olan mesafe → rota üzerindeki her noktada mevcut açıklık.

```python
from scipy.ndimage import distance_transform_edt

clearance_m = distance_transform_edt(traversable) * resolution_m
half_width = [min(clearance_m[r, c], MAX_CORRIDOR_HALF_WIDTH_M) for r, c in path]
```

#### 4.2 Replanning: D* Lite mi, A*'ı yeniden koşmak mı?

Referans belge D* Lite'ı seçenek olarak listeliyor. Dürüst değerlendirme:

| Yöntem | Ne zaman kazanır | LunaPath için |
|---|---|---|
| **A*'ı sıfırdan koş** | Grid küçük, değişim büyük, hesap bütçesi var | ✅ 500×500'de bugün en pratik. Ölçün: mevcut A* zaten `computation_time_ms` raporluyor |
| **D* Lite** | Grid büyük, **lokal ve seyrek** değişim, tekrarlı planlama | 🟡 Rover üzeri gerçek zamanlı senaryoda değerli; yerde offline planlamada kazancı sınırlı |
| **Segment replanning** | Rotanın sadece bir kısmı bozulmuş | ✅ Ucuz ve yeterli — referans belgede zaten "basit segment replanning" olarak planlanmış |
| **Anytime (ARA*)** | Sert zaman limiti var, "yeterince iyi" cevap lazım | ⭐ Onboard senaryoda **doğru** cevap → [08](#belge-08) |

**Öneri:** D* Lite'ı "yapacağız" diye söz vermeyin. Bunun yerine:
1. Mevcut A* koşum süresini **ölçün** (zaten metriklerde var)
2. Segment replanning'i uygulayın (basit, ölçülebilir)
3. Belgeye şu cümleyi yazın: *"Grid boyutu 2000×2000'e çıkarsa veya onboard tekrarlı planlama gerekirse D* Lite'a geçiş için mimari hazırdır; mevcut ölçekte A*'ın tam koşumu X ms sürüyor ve D* Lite'ın karmaşıklık ek yükünü haklı çıkarmıyor."*

Bu, "D* Lite yaptık" demekten daha güçlü bir mühendislik ifadesidir çünkü **ölçüme dayanır.**

#### 4.3 Replanning tetikleyicileri (somut liste)

Referans belge "event-triggered replanning" diyor ama tetikleyicileri saymıyor. Somut liste:

| Tetikleyici | Eşik önerisi | Aksiyon |
|---|---|---|
| Bilinmeyen engel tespit edildi | Yerel planlayıcı koridoru terk etmek zorunda | Global replan (segment) |
| SOC bütçeden sapma | Gerçek SOC < planlanan SOC − %10 | Global replan + profil `energy_saver`'a geç |
| İç sıcaklık sapması | T_iç, tahminden 5 K aşağıda | Global replan + `shadow_traverse` profiline geç |
| Slip birikimi | Kat edilen/komut edilen < 0.75 | Yerel yeniden kalibrasyon + eğim limitini düşür |
| Zaman kayması | Plan zamanından >30 dk sapma | **Aydınlanma değişti** → global replan zorunlu |
| SEP olayı uyarısı | Radyasyon eşiği → [06](#belge-06) | Safe haven'a git, bekle |
| İletişim penceresi kapanıyor | Dünya görünürlüğü < X dk | Konservatif moda geç |
| Konum belirsizliği | Kestirim kovaryansı > koridor yarı genişliği | Dur, lokalizasyon düzelt |

**Bu tablonun kendisi bir çıktıdır.** `backend/app/replan_triggers.py` olarak kodlanabilir ve her tetikleyici için bir birim testi yazılabilir. Jüri/hakem karşısında "replanning yapıyoruz" demenin somut kanıtı budur.

#### 4.4 Safe haven mantığı — belgede var, kodda yok

`ay_termal_navigasyon_proje_dokumani.md` §6.7 bunu açık soru olarak bırakmış. Karar önerisi: **safe haven'ı zorunlu kısıt yapın, opsiyon değil.**

Gerekçe: LPR-1 sabitlerinde `H_MAX_SHADOW_H = 50` ve `H_DESIGN_SHADOW_H = 70` var. Bu, "50 saatten fazla gölgede kalırsan öl" demek. Bir rota bu limiti aşmıyorsa bile, **rota üzerindeki her noktadan 50 saat içinde bir güvenli noktaya erişilebilir olmalıdır** — aksi halde rota tek bir arıza ile ölümcül hale gelir.

Bu, klasik planlamada **"return-to-safety reachability"** kısıtıdır ve şöyle formüle edilir:

```python
def is_recoverable(node, illumination_grid, cost_grid, t_now, rover) -> bool:
    """Bu node'dan, kalan enerji ve H_MAX_SHADOW ile
    aydinlik/sarj bolgesine erisilebilir mi?
    Geriye dogru Dijkstra ile 'safe set'e mesafe hesapla."""
```

**Uygulama tavsiyesi:** Safe set'e mesafeyi **bir kez** çok kaynaklı Dijkstra ile hesaplayıp grid olarak saklayın (`recovery_cost_grid`). Sonra A* içinde `if recovery_cost[node] > remaining_budget: skip` tek satırlık bir kontrol olur. Hesaplama maliyeti: bir Dijkstra koşumu = A* ile aynı mertebede.

Bu, literatürdeki chance-constrained/reachability tabanlı yaklaşımlarla aynı ailedendir: Lamarre, Malhotra ve Kelly'nin güneş enerjili rover için PSR keşfi çalışması ([arXiv 2401.08558](https://arxiv.org/abs/2401.08558), IEEE AERO 2024), bilinen ortalama oranlarda rastgele arızaları hesaba katan bir **şans kısıtlı (chance-constrained) görev-seviyesi planlama** problemi kuruyor ve **stokastik erişilebilirlik (stochastic reachability) analizi** ile güvenli geçiş politikaları buluyor; Cabeus krateri / LCROSS çarpma bölgesinde çok günlük uzun menzilli sürüşlerle doğruluyor.

> **Bu, LunaPath'in en yakın akademik komşusudur.** Aynı problemi, aynı bölgede, daha ileri bir formülasyonla çözüyor. Bunu bilmek ve atıf vermek, LunaPath'i literatüre bağlar; görmezden gelmek jüri karşısında risk oluşturur.

---

<a id="b05-s5"></a>

### [B05] 5. Boşluk analizi

| # | Boşluk | Etki | Efor | Öncelik |
|---|---|---|---|---|
| O1 | "Engel kaçınma var" izlenimi verilirken yok | 🔴 Yüksek (savunulabilirlik) | Çok düşük | **P0** |
| O2 | Rover footprint modellenmiyor (nokta olarak ele alınıyor) | 🟠 Yüksek | Düşük | **P0** |
| O3 | Koridor/açıklık çıktısı yok | 🟠 Yüksek | Düşük | **P1** |
| O4 | Slip modellenmiyor → enerji iyimser | 🟠 Orta-yüksek | Çok düşük | **P1** |
| O5 | Replanning tetikleyicileri tanımlı değil | 🟠 Orta-yüksek | Düşük | **P1** |
| O6 | Safe haven erişilebilirlik kısıtı yok | 🟠 Yüksek | Orta | **P1** |
| O7 | Yerel planlayıcı arayüzü tanımsız | 🟡 Orta | Düşük | P1 |
| O8 | Yerel planlayıcı yok | 🟡 Kapsam kararı | Yüksek | P2/kapsam dışı |

---

<a id="b05-s6"></a>

### [B05] 6. Yol haritası

#### P0 — dürüstlük + footprint (1 gün)
1. README/sunum dilinden "engel kaçınma" ifadesini çıkar veya "harita tabanlı engel maskesi (yerel kaçınma kapsam dışı)" olarak düzelt
2. **Footprint kontrolü ekle:** hücre değerlendirmesini `k×k` pencereye çevir (rover genişliği / hücre boyutu). 80 m hücrede rover 1 hücreden küçük → footprint = 1 hücre, ama **bunu kodda açıkça belirt** ki 5 m'ye geçince otomatik doğru davransın:

```python
# traversability.py
def footprint_traversable(traversable, rover_width_m, res_m):
    """Rover ayak izi kadar bir pencerede TUM hucreler gecilebilir olmali.
    scipy.ndimage.minimum_filter ile erosion."""
    k = max(1, int(np.ceil(rover_width_m / res_m)))
    if k == 1:
        return traversable  # cozunurluk rover'dan kaba: footprint modellenemez
    return minimum_filter(traversable.astype(np.uint8), size=k).astype(bool)
```

#### P1 — koridor + kısıtlar (3–5 gün)
3. `Corridor` şeması + `distance_transform_edt` ile `half_width_m`
4. `slip_ratio` → `f_energy` düzeltmesi + doğrulama tablosu
5. `replan_triggers.py` + her tetikleyici için birim testi
6. `recovery_cost_grid` (safe haven erişilebilirlik) + A*'da tek satır kısıt
7. `/api/replan` endpoint'ini gerçekten uygula (segment replanning)
8. Metriklere ekle: `min_corridor_clearance_m`, `max_recovery_cost_h`, `slip_adjusted_energy_wh`

**Kabul kriteri (P1):** Aynı senaryoda "safe haven kısıtı kapalı" ve "açık" iki rota üretilip karşılaştırılıyor. Kısıt açıkken rota daha uzun ama her noktadan kurtarılabilir olduğu **sayısal olarak gösteriliyor** (`max_recovery_cost_h < H_MAX_SHADOW_H`).

#### P2 — yerel katman (kapsam kararı; önerilen: kapsam dışı, arayüz tanımlı)
9. OmniLRS/LunarSim ile sentetik stereo → yerel hazard haritası
10. GESTALT benzeri arc değerlendirme veya MPC
11. Koridor sözleşmesi üzerinden Katman 1 ↔ Katman 2 kapalı döngü testi

---

<a id="b05-s7"></a>

### [B05] 7. Kabul kriterleri

- [ ] Belge ve sunumda global/lokal ayrımı net; "engel kaçınma" iddiası yok veya kapsamı belirtilmiş
- [ ] Footprint erozyonu kodda mevcut ve çözünürlük sınırı belgelenmiş
- [ ] `Corridor` şeması yayınlanmış, `half_width_m` üretiliyor
- [ ] Slip düzeltmesi `f_energy`'de, doğrulama tablosu güncellenmiş
- [ ] 8 replanning tetikleyicisi kodlu ve test edilmiş
- [ ] `recovery_cost_grid` üretiliyor, safe haven kısıtı açık/kapalı karşılaştırması var
- [ ] Lamarre vd. (2024) ve ENav/ACE literatürüne atıf yapılmış

---

<a id="b05-s8"></a>

### [B05] Kaynaklar

- [Mars 2020 Autonomous Rover Navigation (Semantic Scholar)](https://www.semanticscholar.org/paper/MARS-2020-AUTONOMOUS-ROVER-NAVIGATION-McHenry-Abcouwer/c20138d836a7359ca83b8a35aafed060abe46b53)
- [Autonomous robotics is driving Perseverance rover's progress on Mars (Science Robotics)](https://www.science.org/doi/10.1126/scirobotics.adi3099)
- [Driving Farther and Faster With Autonomous Navigation (NASA Science)](https://science.nasa.gov/missions/mars-2020-perseverance/driving-farther-and-faster-with-autonomous-navigation-and-helicopter-scouting)
- [Surface System Software and Rover Navigation — JPL Robotics](https://www-robotics.jpl.nasa.gov/what-we-do/flight-projects/mars-science-laboratory/surface-system-software-and-rover-navigation/)
- [Lamarre, Malhotra, Kelly (2024), Safe Mission-Level Path Planning for Exploration of Lunar Shadowed Regions by a Solar-Powered Rover, IEEE AERO (arXiv 2401.08558)](https://arxiv.org/abs/2401.08558)
- [Risk-Aware Coverage Path Planning for Lunar Micro-Rovers (arXiv 2404.18721)](https://arxiv.org/html/2404.18721v1)
- [A Comprehensive Review of Path-Planning Algorithms for Planetary Rover Exploration (Remote Sensing 17(11), 1924)](https://www.mdpi.com/2072-4292/17/11/1924)
- [Deep Probabilistic Traversability with Test-time Adaptation (arXiv 2409.00641)](https://arxiv.org/pdf/2409.00641)
- [Vision Based Obstacle Detection Using Rover Stereo Images (ISPRS)](https://isprs-archives.copernicus.org/articles/XLII-2-W13/1471/2019/isprs-archives-XLII-2-W13-1471-2019.pdf)
- [CADRE — JPL](https://www.jpl.nasa.gov/missions/cadre/)
- [A precise visual localisation method for the Chinese Chang'e-4 Yutu-2 rover (Photogrammetric Record)](https://www.researchgate.net/profile/Youqing-Ma/publication/339552801_A_precise_visual_localisation_method_for_the_Chinese_Chang'e-4_Yutu-2_rover)
- [Breadboarding the European Moon Rover System: analogue field test campaign (arXiv 2411.13978)](https://arxiv.org/pdf/2411.13978)

[↑ İçindekiler](#icindekiler) · [↑ Yönlendirme tablosu](#yonlendirme)

---

<a id="belge-06"></a>

## BELGE 06 — Radyasyon Verisi

> **Belge kimliği:** `BELGE 06` (bölüm başlıklarında `[B06]` etiketiyle işaretlidir) · **Kaynak dosya:** `06_radyasyon_verisi.md`  
> **Konu:** CRaTER, LND, GCR/SEP, TID/SEU, maliyet katmanına ekleme  
> **Ana çıktı:** Radyasyon katmanı ve karar kuralları  
> **Ayırt edici terimler:** `SEP`, `radyasyon`, `SVF`, `GCR`, `TID`, `CRaTER`, `LND`, `SEU`

> **Soru:** LunaPath'in "donanım sağlığı" iddiası varken radyasyon neden hiç yok? Hangi veri mevcut, rota planlamaya nasıl girer?
>
> **Kısa cevap:** LunaPath, `health_score` ve `thermal_stress` modelliyor ama **radyasyonu tamamen atlıyor** — oysa Ay yüzeyinde donanımı bozan iki mekanizmanın biri termal, diğeri radyasyondur. İyi haber: radyasyon katmanı, termal katmandan **çok daha kolay** eklenir. Çünkü uzamsal olarak neredeyse düzgündür (rota seçimini az etkiler) ama **zamansal olarak patlayıcıdır** (SEP olayları) — yani "haritaya bir katman" değil, "senaryoya bir olay" olarak girer. Bu, düşük efor–yüksek getiri bir eklemedir.

---

<a id="b06-s1"></a>

### [B06] 1. Ay yüzeyi radyasyon ortamı — üç bileşen

| Bileşen | Nedir | Zaman davranışı | Uzamsal davranış |
|---|---|---|---|
| **GCR (Galaktik Kozmik Işın)** | Süpernovalardan gelen yüksek enerjili yüklü parçacıklar (çoğunlukla proton, ağır iyonlar) | Sürekli; 11 yıllık güneş çevrimiyle **ters** korelasyon (güneş minimumunda en yüksek) | Neredeyse izotropik; sadece **gökyüzü görüş açısı** (sky view factor) ile değişir |
| **SEP (Güneş Enerjik Parçacıkları)** | Güneş patlaması/CME kaynaklı ani proton akısı | **Kesikli, patlayıcı**: saatler–günler; büyüklüğü 10⁴× değişebilir | Güneş yönü + manyetik bağlantıya bağlı |
| **Albedo nötron / gama** | Kozmik ışınların regolitle etkileşiminden ikincil parçacıklar | GCR'yi takip eder | **Yüzeye yakın maksimum**; regolit derinliğiyle azalır |

#### 1.1 Ölçülmüş değerler (gerçek veriye dayanan sayılar)

**Chang'E-4 / LND (Lunar Lander Neutron & Dosimetry)** — Ay yüzeyinde ilk doğrudan doz ölçümü (Zhang vd., *Science Advances*, 2020):

| Büyüklük | Değer | Not |
|---|---|---|
| Silikonda soğurulan doz hızı | **~13.2 µGy/h** (kaynaklar ~13–14 µGy/h bandı verir) | Mühendislik için doğrudan kullanılabilir |
| Doz eşdeğeri hızı (biyolojik) | **~60 µSv/h** | İnsan için; elektronik için **kullanılmaz** |
| GCR katkısı | **~%75** | Geri kalanı ikincil/nötr parçacıklar |
| Nötr parçacık katkısı (nötron+gama) | Güneş minimumu civarında **%23 ± 17** | Yerel regolit etkileşiminden |
| Enstrüman | 10 çift-segmentli silikon SSD yığını | Toplam doz D detektöründe, nötr parçacık C detektörünün iç segmentinde |

**LRO / CRaTER** — yörüngeden sürekli izleme (2009–):

| Büyüklük | Değer |
|---|---|
| 50 km yörüngede ölçülen doz | **~0.22–0.27 mGy/gün** |
| Enstrüman | 3 çift ince (140 µm) / kalın (1000 µm) silikon detektör (D1–D6), aralarında doku-eşdeğeri plastik (TEP) absorber |
| Değer | 15+ yıllık zaman serisi → **güneş çevrimi ve SEP olay kataloğu** |

#### 1.2 Mühendislik çıkarımı — ve bu bilgi neden LunaPath'i güçlendirir

Yıllık toplam iyonlaştırıcı doz (TID) hesabı:

```
13.2 µGy/h × 8766 h/yıl = 1.157e-1 Gy/yıl
1 Gy = 100 rad         →  ≈ 11.6 rad(Si)/yıl
```

Karşılaştırma: CRaTER'ın 50 km yörüngede ölçtüğü 0.22–0.27 mGy/gün de yıllık **~8–10 rad(Si)** verir — aynı mertebe, tutarlı.

Tipik radyasyon-sertleştirilmiş bir bileşenin TID toleransı **100 krad(Si) = 1000 Gy** mertebesindedir. Yani:

> **GCR kaynaklı TID, yüzey misyonları için sınırlayıcı faktör DEĞİLDİR.** 100 krad'lık bir parçanın GCR ile doyması binlerce yıl alır.

**Sınırlayıcı olan iki şey:**

1. **SEE (Single Event Effects)** — tek bir ağır iyon veya yüksek enerjili protonun anlık etkisi: SEU (bit flip), SEL (latch-up, kalıcı hasar riski), SET, SEFI (fonksiyonel kesinti). Bunlar doza değil, **akı ve LET spektrumuna** bağlıdır.
2. **SEP olayları** — birkaç saat içinde yılların dozunu verebilir ve akıyı **10.000 kata kadar** yükseltebilir. Bu, elektroniği anlık olarak devre dışı bırakabilir ve insanlı misyonlarda hayati risktir.

**LunaPath için bu, tam olarak kullanılabilir bir tasarım kararına dönüşür:**

| Modelleme yaklaşımı | Doğru mu? | Neden |
|---|---|---|
| Radyasyonu **uzamsal maliyet katmanı** yapmak (her hücreye farklı radyasyon maliyeti) | ❌ Büyük ölçüde **yanlış** | GCR neredeyse izotropiktir; 40 km'lik bir pencerede hücreler arası fark ihmal edilebilir |
| Radyasyonu **gökyüzü görüş faktörü** ile modüle etmek | ✅ **Kısmen doğru ve zarif** | Derin krater tabanı gökyüzünün yarısını görür → GCR dozu ~%40–50 azalır. Bu **gerçek, ölçülebilir, uzamsal** bir etkidir |
| Radyasyonu **zamansal olay** olarak modellemek (SEP senaryosu) | ✅ **Tamamen doğru** | Fiziğin gerçek yapısı budur |
| TID'i birikimli sağlık kaybı olarak modellemek | 🟡 Doğru ama etkisiz | Kısa misyonda anlamsız; uzun misyonda (yıllar) anlamlı |

> **Bu, LunaPath'e eklenebilecek en ilginç fikirdir:** *PSR'lar termal olarak ölümcül ama radyasyon açısından koruyucudur.* Derin bir krater tabanı, gökyüzünün büyük kısmını topografyayla kapatır → GCR dozunu düşürür. Yani **termal risk ile radyasyon riski ters yönde çalışır.** Bu, çok kriterli optimizasyonda gerçek bir trade-off'tur ve LunaPath'in maliyet fonksiyonunu felsefi olarak zenginleştirir: *sıcak kal ama ışınlan, ya da soğu ama korun.*

---

<a id="b06-s2"></a>

### [B06] 2. Gökyüzü görüş faktörü — DEM'den hesaplanabilir bir radyasyon katmanı

Bu, LunaPath'in mevcut veri setiyle (sadece DEM ile!) üretebileceği **gerçek fizikli, bağımsız** bir katmandır. Yeni veri indirmeye gerek yok.

```python
# lunapath/src/sky_view.py (yeni)
import numpy as np

def sky_view_factor(elev, res_m, n_azimuth=36, max_range_m=20_000):
    """Gokyuzu gorus faktoru (SVF) [0,1].
    1.0 = tam acik gokyuzu (duz ova), 0.5 = gokyuzunun yarisi kapali.

    Yontem: her azimutta ufuk yukseklik acisi theta_h bulunur;
    SVF = (1/N) * sum(cos^2(theta_h))   [izotropik akiya gore
    kati aci integrali, duz yuzey icin turetilen standart form]

    Not: ayni ray-marching altyapisi illumination hesabiyla
    paylasilir -> bir kez yaz, iki katman uret.
    """
    svf = np.zeros_like(elev, dtype=np.float32)
    for az in np.linspace(0, 360, n_azimuth, endpoint=False):
        theta_h = horizon_elevation(elev, res_m, az, max_range_m)  # derece
        svf += np.cos(np.radians(theta_h)) ** 2
    return svf / n_azimuth


def gcr_dose_rate_grid(svf, base_rate_uGy_h=13.2):
    """SVF ile modulasyon. Yaklasim:
    GCR primer akisi ~ SVF ile olcekli; albedo notron katkisi
    ters yonde artar (regolit gorunumu artinca) -> ilk mertebede
    ihmal edilip belirsizlik olarak raporlanmali."""
    return base_rate_uGy_h * svf
```

**Doğrulama tablosu (beklenen değerler):**

| Topografya | SVF | Doz hızı (µGy/h) | Yorum |
|---|---|---|---|
| Düz ova | ~1.00 | 13.2 | Referans |
| Sığ krater tabanı | ~0.85 | 11.2 | %15 koruma |
| Derin krater tabanı (Shackleton benzeri) | ~0.55–0.70 | 7.3–9.2 | **%30–45 koruma** |
| Dik yamacın dibi | ~0.60 | 7.9 | |
| Tepe zirvesi | ~1.00 | 13.2 | Maksimum maruziyet |

**Dürüstlük notu (belgeye yazın):** SVF-tabanlı modülasyon **birinci mertebe bir yaklaşımdır**. Gerçek transport hesabı (GEANT4/PHITS/HZETRN ile Monte Carlo) yapılmadan mutlak doz iddiası edilemez. Ancak **göreli** karşılaştırma (krater tabanı vs zirve) fiziksel olarak sağlamdır ve rota kararında kullanılabilir. Bu, [03](#belge-03) §3.1'deki "mekanizmadan türeyen model" testini **geçer** — çünkü katı açı geometrisinden türer, korelasyondan değil.

#### 2.1 Regolit kalkanı (bonus, ucuz)

Regolit iyi bir kalkandır. Rover bir çıkıntının altına park ederse veya rejolitle kaplanmış bir barınağa girerse doz düşer. LunaPath'e bunu **safe haven özniteliği** olarak ekleyebilirsiniz:

```python
class SafeHaven(BaseModel):
    position: tuple[int, int]
    illumination_fraction: float     # sarj icin
    sky_view_factor: float           # radyasyon korumasi icin
    thermal_regime_K: float          # termal denge sicakligi
    reachability_h: float            # oraya ulasma suresi
    shelter_quality: Literal["open", "partial", "sheltered"]
```

SEP alarmı geldiğinde planlayıcı, **sadece en yakın** safe haven'a değil, **en iyi kalkanlı** safe haven'a yönelir. Bu, tek bir ek alanla üretilen anlamlı bir karar davranışıdır.

---

<a id="b06-s3"></a>

### [B06] 3. SEP olay senaryosu — LunaPath'e en doğru radyasyon eklemesi

#### 3.1 Neden senaryo, neden katman değil

SEP olayı bir **zamansal olaydır**: dakikalar içinde başlar, saatler–günler sürer, akı büyüklüğü olağan seviyenin binlerce katına çıkabilir. Bir haritaya çizilemez; bir **senaryo tetikleyicisi** olarak modellenir.

LunaPath'in senaryo sistemi (`scenarios.py`, `MISSION_PROFILES`) bunun için **hazır bir altyapıdır.** Yeni bir olay tipi ekleyin:

```json
{
  "scenario_id": "south_pole_nobile_sep_event",
  "dem_file": "LDEM_80S_80MPP_ADJ.tiff",
  "events": [
    {
      "type": "SEP_ONSET",
      "t_offset_h": 6.5,
      "severity": "major",
      "flux_multiplier": 2000,
      "expected_duration_h": 18,
      "warning_lead_time_min": 30,
      "required_action": "SEEK_SHELTER"
    }
  ],
  "expected_outcomes": {
    "baseline": "SEP'i yok sayan plan gorevi tamamlar ama 18 saat maruz kalir",
    "sep_aware": "Plan T+6.0'da kalkanli safe haven'a saparak beklemeye gecer"
  }
}
```

#### 3.2 Karar mantığı

```python
# backend/app/radiation.py (yeni)
SEP_ALERT_ACTIONS = {
    "minor":    {"action": "CONTINUE",       "note": "izle, plan degismez"},
    "moderate": {"action": "PREFER_SHELTER", "note": "rota kalkanli hucreleri tercih etsin"},
    "major":    {"action": "SEEK_SHELTER",   "note": "en iyi SVF'li erisilebilir haven'a git"},
    "extreme":  {"action": "SAFE_MODE",      "note": "dur, hibernate, telemetri minimum"},
}

def sep_response_plan(current_pos, havens, lead_time_min, severity, rover):
    """SEP uyarisi geldiginde: lead_time icinde ulasilabilir haven'lar
    arasindan en iyi kalkanliyi sec. Ulasilamiyorsa yerinde
    en iyi SVF'li hucreye kisa sapma yap."""
    reachable = [h for h in havens
                 if h.reachability_h * 60 <= lead_time_min]
    if not reachable:
        return local_best_shielding(current_pos, radius_m=200)
    return min(reachable, key=lambda h: h.sky_view_factor)  # kucuk SVF = iyi kalkan
```

**`warning_lead_time_min` gerçekçi mi?** SEP olayları için uyarı süresi olayın hızına bağlıdır; ilk gelen relativistik parçacıklar dakikalar içinde ulaşır, ana akı ise onlarca dakika–saatler alır. `30 dk` savunulabilir bir mühendislik varsayımıdır ama **varsayım olarak etiketlenmeli** ve hassasiyet analizi yapılmalı (`lead_time ∈ {10, 30, 60, 120}` dk için sonuç nasıl değişir?).

#### 3.3 Bu eklemenin demo değeri

Bu, **anlatısı en güçlü** senaryodur:

> *"Rover Nobile krater kenarında ilerliyor. T+6.5 saatte güneşte bir patlama oluyor; radyasyon akısı 2000 katına çıkacak ve 30 dakika uyarı süremiz var. SEP-farkında planlayıcı, 12 dakika içinde erişilebilir 3 barınaktan gökyüzü görüş faktörü en düşük olanı (SVF 0.58, %42 kalkan) seçiyor ve rotayı 340 m saptırıyor. Bu sapma 90 Wh ve 2.4 saat gölge süresine mal oluyor. SEP-kör planlayıcı ise açık arazide 18 saat boyunca tam akıya maruz kalıyor."*

Bu tek senaryo, LunaPath'in dört ayrı iddiasını aynı anda kanıtlar: çok kriterli optimizasyon, dinamik replanning, safe haven mantığı ve donanım sağlığı farkındalığı.

---

<a id="b06-s4"></a>

### [B06] 4. Veri kaynakları ve modeller

#### 4.1 Ölçüm verisi

| Kaynak | İçerik | Erişim | LunaPath'te kullanım |
|---|---|---|---|
| **LRO/CRaTER** | 15+ yıl doz + LET spektrumu, SEP olay kataloğu | PDS ([context](https://arcnav.psi.edu/urn:nasa:pds:context:instrument:crat.lro)), [LRO Data Products](https://science.nasa.gov/mission/lro/data-products/) | Baz doz hızı, güneş çevrimi bandı, gerçek SEP olay profilleri |
| **Chang'E-4 / LND** | Yüzeyde ilk doz ölçümü, nötr parçacık katkısı | Yayın (Science Advances 2020) | **Baz doz hızı için altın standart** (13.2 µGy/h) |
| **CRaTER mikrodozimetre güncellemesi** (Mazur vd. 2015) | GCR + solar proton dozu | AGU Space Weather | Doz hızı zaman serisi |
| **Matthiä vd. 2024** | Ay yüzeyinde maruziyet ve **kalkanlama etkileri** | AGU Space Weather | Kalkan kalınlığı → doz azaltımı; SVF modelinizi kalibre etmek için |
| **NOAA SWPC / ESA SSA** | Gerçek zamanlı uzay hava durumu, GOES proton akısı | Kamuya açık API | Canlı senaryo modu (bonus) |

#### 4.2 Transport modelleri (mutlak doz iddiası gerekirse)

| Model | Ne yapar | Erişim |
|---|---|---|
| **NASA OLTARIS** | Web tabanlı uzay radyasyon analiz aracı; kalkan geometrisi + ortam → doz | Kayıtlı erişim, ücretsiz |
| **HZETRN** | Deterministik transport (OLTARIS'in çekirdeği) | NASA |
| **GEANT4** | Monte Carlo parçacık transportu | Açık (CERN lisansı) |
| **PHITS** | Monte Carlo (JAEA) | Kayıt gerekli |
| **Badhwar–O'Neill / ISO 15390** | GCR ortam modeli (güneş çevrimi bağımlı) | Standart / yayın |

**Öneri:** LunaPath'in kapsamında **transport hesabı yapmayın.** SVF-tabanlı göreli modülasyon + LND'nin ölçülmüş baz değeri + belirsizlik beyanı yeterli ve savunulabilirdir. Belgeye şu cümleyi yazın: *"Mutlak doz iddiası için OLTARIS/GEANT4 tabanlı transport hesabı gereklidir; bu çalışmada göreli kalkanlama karşılaştırması yapılmıştır."*

---

<a id="b06-s5"></a>

### [B06] 5. Elektronik etkileri — `health_score`'a nasıl girer

LunaPath'in mevcut `health_score` modeli sadece termal stresi biriktiriyor. Radyasyonu eklerken **doğru mekanizmayı** seçin:

| Mekanizma | Birikimli mi? | LunaPath'te modelleme |
|---|---|---|
| **TID** (toplam iyonlaştırıcı doz) | ✅ Evet, geri dönüşsüz | Birikimli sayaç; ama kısa misyonda etkisiz (§1.2) → **raporla, cezalandırma** |
| **DD** (yer değiştirme hasarı) | ✅ Evet | Aynı; optik/detektör dejenerasyonu |
| **SEU** (bit flip) | ❌ Olasılıksal, düzeltilebilir | **Oran (rate) olarak modelle**: `λ_SEU ∝ akı`. EDAC/watchdog ile kurtarılır → `replan_trigger` |
| **SEL** (latch-up) | ❌ Olasılıksal, **kalıcı hasar riski** | Düşük olasılık, yüksek sonuç → misyon riski olarak raporla |
| **SEFI** (fonksiyonel kesinti) | ❌ | Reset gerektirir → görev süresi kaybı |

**Somut öneri — `health_score`'u iki eksene ayır:**

```python
class HealthState(BaseModel):
    thermal_stress_accum: float      # mevcut model
    radiation_tid_rad: float         # birikimli, raporlanir
    seu_events_expected: float       # olasiliksal beklenen deger
    sep_exposure_h: float            # SEP sirasinda maruz kalinan sure
    # Tek bir skalar 'health' yerine bilesen bazli — belgede
    # acik soru olarak birakilmisti (proje dokumani §6.5); karar: BILESEN BAZLI
```

Bu, `ay_termal_navigasyon_proje_dokumani.md` §6.5'teki açık soruyu ("tek genel health score mu, bileşen bazlı mı?") **bileşen bazlı** lehine kapatır. Gerekçe: termal ve radyasyon **farklı zaman ölçeklerinde ve farklı geri dönüşlerle** çalışır (termal geri kazanılabilir, TID kazanılamaz); tek skalarda toplamak bilgi kaybıdır.

---

<a id="b06-s6"></a>

### [B06] 6. Boşluk analizi

| # | Boşluk | Etki | Efor | Öncelik |
|---|---|---|---|---|
| R1 | Radyasyon tamamen yok ama "donanım sağlığı" iddia ediliyor | 🟠 Yüksek (tutarlılık) | — | — |
| R2 | SVF katmanı yok (DEM'den üretilebilir, yeni veri gerekmez) | 🟠 Orta-yüksek | Orta | **P1** |
| R3 | SEP senaryosu yok | 🟠 Orta-yüksek (demo değeri çok yüksek) | Düşük | **P1** |
| R4 | `health_score` tek skalar, mekanizmaları ayırmıyor | 🟡 Orta | Düşük | **P1** |
| R5 | Safe haven'da kalkan niteliği yok | 🟡 Orta | Çok düşük | P1 |
| R6 | Mutlak doz için transport hesabı yok | 🟢 Düşük (kapsam dışı beyan edilirse) | Yüksek | Kapsam dışı |
| R7 | Canlı uzay hava durumu entegrasyonu yok | 🟢 Bonus | Düşük | P2 |

---

<a id="b06-s7"></a>

### [B06] 7. Yol haritası

#### P1 — radyasyon katmanı + SEP senaryosu (2–4 gün)

1. **`sky_view.py`**: SVF hesabı (ray-marching; illumination hesabıyla altyapı paylaşımlı → [04](#belge-04) §2.2). 36 azimut yeterli. `numba` ile hızlandır.
2. **`radiation.py`**: `gcr_dose_rate_grid(svf)`, LND baz değeri 13.2 µGy/h, doğrulama tablosu (§2)
3. **`f_radiation` penalty** (opsiyonel, düşük ağırlıklı): nominal koşullarda etkisi küçük olmalı — bu **doğru** davranıştır ve belgelenmelidir
4. **SEP senaryosu**: `scenarios/` altına `*_sep_event.json`, `sep_response_plan()` fonksiyonu
5. **`HealthState`** bileşen bazlı refaktör
6. **`SafeHaven.sky_view_factor` + `shelter_quality`** alanları
7. **Metrikler**: `total_tid_rad`, `mean_dose_rate_uGy_h`, `sep_exposure_h`, `shielding_benefit_pct`

**Kabul kriteri:** SEP senaryosu iki kolda koşuyor (SEP-kör vs SEP-farkında) ve karşılaştırma tablosu şunları gösteriyor: sapma mesafesi (m), ek enerji (Wh), ek gölge süresi (h), **önlenen maruziyet (µGy)**, seçilen haven'ın SVF'si.

#### P2 — genişletmeler
8. Canlı NOAA SWPC proton akısı ile "gerçek zamanlı mod"
9. CRaTER zaman serisinden gerçek SEP olay profilleri (senaryo kütüphanesi)
10. Matthiä vd. 2024 kalkanlama eğrileriyle SVF modelini kalibre et

---

<a id="b06-s8"></a>

### [B06] 8. Sunumda kullanılacak cümleler

- *"Radyasyonu uzamsal bir maliyet katmanı olarak modellemedik, çünkü GCR neredeyse izotropiktir ve 40 km'lik bir pencerede hücre farkı ihmal edilebilir. Bunun yerine topografyanın gerçek radyasyon etkisini — gökyüzü görüş faktörünü — modelledik."*
- *"Kalıcı gölgeli bölgeler termal olarak ölümcül ama radyasyon açısından koruyucudur. Bu, çok kriterli optimizasyonda gerçek bir çelişkidir ve maliyet fonksiyonumuz bunu görebiliyor."*
- *"GCR kaynaklı TID, kısa süreli yüzey misyonlarında sınırlayıcı faktör değil; ölçülmüş 13.2 µGy/h değeriyle yılda ~12 rad(Si) birikir ve tipik rad-hard bileşenlerin 100 krad toleransının çok altındadır. Bizim modellemeye değer bulduğumuz risk SEP olaylarıdır."*
- *"Mutlak doz iddiası için OLTARIS/GEANT4 transport hesabı gerekir; bu çalışma göreli kalkanlama karşılaştırmasıyla sınırlıdır."*

---

<a id="b06-s9"></a>

### [B06] Kaynaklar

- [Zhang et al. (2020), First measurements of the radiation dose on the lunar surface, Science Advances](https://www.science.org/doi/10.1126/sciadv.aaz1334) · [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7518862/)
- [The Lunar Lander Neutron and Dosimetry (LND) Experiment on Chang'E 4 (arXiv 2001.11028)](https://arxiv.org/pdf/2001.11028)
- [First measurements of low-energy cosmic rays on the lunar farside (Science Advances)](https://www.science.org/doi/10.1126/sciadv.abk1760)
- [Matthiä et al. (2024), Radiation Exposure and Shielding Effects on the Lunar Surface, Space Weather](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2024SW004095)
- [Mazur et al. (2015), Update on Radiation Dose From Galactic and Solar Protons at the Moon Using LRO/CRaTER, Space Weather](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/2015SW001175)
- [Cosmic Ray Enhancements in Lunar Radiation Environment Observed by CRaTER (JKPS)](https://link.springer.com/article/10.3938/jkps.74.614)
- [LRO CRaTER instrument — PDS context](https://arcnav.psi.edu/urn:nasa:pds:context:instrument:crat.lro)
- [LRO Data Products — NASA Science](https://science.nasa.gov/mission/lro/data-products/)
- [Variations of the Galactic Cosmic Rays in the Recent Solar Cycles (arXiv 2104.07862)](https://arxiv.org/pdf/2104.07862)

[↑ İçindekiler](#icindekiler) · [↑ Yönlendirme tablosu](#yonlendirme)

---

<a id="belge-07"></a>

## BELGE 07 — Termal Veri

> **Belge kimliği:** `BELGE 07` (bölüm başlıklarında `[B07]` etiketiyle işaretlidir) · **Kaynak dosya:** `07_termal_veri.md`  
> **Konu:** Diviner ürünleri, termofiziksel modeller, sentetik gridin yerine ne gelir  
> **Ana çıktı:** Termal katman geçiş planı (sentetik → ölçüm)  
> **Ayırt edici terimler:** `Diviner`, `regolit`, `PSR`, `heat1d`, `regolith`, `lumped capacitance`, `batarya`, `RMSE`

> **Soru:** LunaPath'in ana iddiası termal güvenlik. Termal veri sentetik olduğu sürece bu iddia ne kadar geçerli? Gerçek veri nedir, nasıl alınır, modele nasıl bağlanır?
>
> **Kısa cevap:** Bu, projenin **en kritik tek belgesi**. LunaPath'in özgünlük iddiası termal güvenliktir; termal katman sentetik olduğu sürece iddia dayanaksızdır. Ay yüzey sıcaklığı **15+ yıldır sürekli ölçülüyor** (LRO/Diviner) ve ürünler halka açık. Ayrıca yüzey sıcaklığını rover iç sıcaklığına çeviren mevcut model (`T_iç = T_yüzey ± sabit`) fiziksel olarak yanlıştır ve **tek düğümlü (lumped capacitance) bir enerji dengesi** ile değiştirilmelidir. Bu iki düzeltme, projenin bilimsel ağırlığını en çok artıracak müdahalelerdir.

---

<a id="b07-s1"></a>

### [B07] 1. Mevcut termal zincirin eleştirisi

LunaPath'te termal karar üç aşamalıdır:

```
elevation ──► thermal_grid (sentetik T_yüzey)  ──► T_iç = T_yüzey ± ofset ──► f_thermal (çift sigmoid)
             [thermal_grid.py]                     [cost_engine.py:104]        [cost_engine.py:177]
```

Her aşamada bir problem var.

#### 1.1 Aşama 1 — sentetik T_yüzey

[03](#belge-03) §2'de ayrıntılı eleştirildi. Özet: elevasyon–sıcaklık lineer eşlemesi Ay'da fiziksel temele sahip değil (atmosfer yok → lapse rate yok), doğrulama sirküler, +80 °C tepe sıcaklığı 1.5° güneş elevasyonunda erişilemez, gölge proxy'si tek komşuya bakıyor, zaman yok.

#### 1.2 Aşama 2 — sabit ofset modeli (en ciddi model hatası)

```python
# cost_engine.py, surface_to_inner()  — offsetler rover katalogundan geliyor
if T_surface_C < 0:  T_inner = T_surface_C + thermal_offset_cold   # LPR-1: +60
else:                T_inner = T_surface_C + thermal_offset_hot    # LPR-1: -40
```

**Not (kodun lehine):** Ofsetler hard-code değil, `ROVERS` kataloğundan okunuyor ve rover'a göre değişiyor (LPR-1/VIPER: +60/−40, Yutu-2: +70/−30, LUVMI-M: `None` → ofset uygulanmaz, `f_thermal` T_yüzey ile çalışır). Bu parametrik tasarım iyidir. **Eleştiri parametrelere değil, modelin biçimine yöneliktir:** ofset, rover'a göre değişse bile hâlâ *sabit bir ötelemedir*.

**Neden yanlış:** İç sıcaklık, dış sıcaklığın **sabit bir ötelemesi değildir**. İç sıcaklığı belirleyen şey bir **enerji dengesidir**: ısıtıcı gücü, yalıtım (MLI) direnci, ısıl kütle, radyatör alanı ve görüş faktörleri. Sabit ofset, şu absürt sonuçları üretir:

| T_yüzey | T_iç (ofset modeli) | Fiziksel gerçeklik |
|---|---|---|
| −180 °C (93 K) | **−120 °C** | 25 W'lık Kapton ısıtıcıyla iyi yalıtılmış bir gövde −120 °C'ye **düşmez**; ya ~0 °C civarında tutulur ya da ısıtıcı yetersizse **kademeli olarak soğur** — sabit 60 K fark diye bir şey yok |
| −40 °C (233 K) | +20 °C | Tesadüfen makul |
| +60 °C (333 K) | +20 °C | Radyatör kapasitesine bağlı; sabit değil |

Ayrıca: bu model **T_iç'i T_yüzey'in fonksiyonu** yapıyor, yani rover'ın **geçmişini** tamamen yok sayıyor. Gerçekte rover 20 dakika önce güneşteyse ve şimdi gölgeye girdiyse, iç sıcaklığı hâlâ yüksektir. Bu, `THERMAL_TAU_S` sabitinin var olma nedenidir — ama sabit ofset modeliyle **birlikte kullanılamaz**; ikisi çelişir.

#### 1.3 Aşama 3 — çift sigmoid `f_thermal`

Bu aşama aslında **iyi tasarlanmış**: batarya (0–35 °C) ve elektronik (−10–40 °C) operasyon aralıklarını ayrı sigmoidlerle cezalandırıp %60/%40 ağırlıklandırıyor. MRU [0,1] normalizasyonu tutarlı. **Bu aşamayı değiştirmeyin** — girdisini düzeltin.

Tek not: `f_thermal` T_yüzey alıp içinde T_iç'e çeviriyor. Ayrıştırın:

```python
def f_thermal_from_inner(T_inner_C, rover=None) -> float:   # saf penalty
def f_thermal(T_surface_C, rover=None) -> float:            # geriye uyum sarmalayıcı
```

Böylece dinamik termal model (§3) `f_thermal_from_inner`'ı doğrudan besleyebilir.

---

<a id="b07-s2"></a>

### [B07] 2. Gerçek termal veri: LRO/Diviner

#### 2.1 Enstrüman ve ürünler

Diviner (Diviner Lunar Radiometer Experiment), 9 kanallı bir kızılötesi radyometre; 2009'dan bu yana Ay yüzey sıcaklığını haritalıyor. Temel referans: Paige vd., *Science* **330**, 479 (2010).

**Global High-Resolution Mosaics (GHRM):**

| Özellik | Değer |
|---|---|
| Grid | **128 ppd** (~250 m/px ekvatorda), 0.25 saat yerel zaman aralığı |
| Kapsam | **70°S – 70°N** silindirik projeksiyon |
| Ürünler | Kanal 6–9 parlaklık sıcaklığı (`tb6`…`tb9`), **bolometrik sıcaklık (`tbol`)**, **regolit sıcaklığı (`treg`)** |
| Zaman kesitleri | Gece yarısı (`m`) ve **eğim-düzeltilmiş gece yarısı** (`sam`) |
| Türev | **Kaya bolluğu (`ra`)** — eğim-düzeltilmiş gece yarısından |
| Arşiv | PDS4 bundle `urn:nasa:pds:lro_diviner_derived1`, DOI `10.17189/wj0s-w188` |

> ⚠️ **KRİTİK UYARI — doğrulanması gereken nokta:** GHRM ürünleri **70°S–70°N** kapsıyor. LunaPath'in çalışma bölgesi **80°S–90°S**, yani GHRM'nin **dışında**. Kutup için Diviner'ın ayrı kutup ürünlerini (polar temperature maps / PSR sıcaklık ürünleri) kullanmanız gerekir. **İlk iş bunu doğrulamak olmalı:** PDS Geosciences Node'da `lro_diviner` bundle'larını listeleyip kutup kapsamlı ürünü teyit edin. Yanlış ürünü indirip 40 km'lik pencerenizin tamamen NoData çıkması, kaybedilebilecek en can sıkıcı gündür.

`ay_termal_navigasyon_proje_dokumani.md` §13.1 zaten doğru başlıkları listelemiş: *"Diviner Global and Polar Temperature Maps"*, *"Seasonal Polar Temperatures on the Moon"*. Kutup ürününü buradan takip edin.

#### 2.2 Hangi ürünü kullanmalı?

| Ürün | LunaPath'te kullanım | Öneri |
|---|---|---|
| `tbol` (bolometrik sıcaklık) | **Ana termal katman** — `thermal_grid`'in yerine geçer | ⭐ **Birincil hedef** |
| `treg` (regolit sıcaklığı) | Termal atalet/derinlik etkisi | 🟡 Faydalı |
| `ra` (kaya bolluğu) | **Bağımsız tehlike katmanı** — kaya yoğunluğu | ⭐ Bedava bonus ([02](#belge-02)) |
| Maksimum/minimum sıcaklık haritaları | Hard-constraint (kriyojenik bölge) | ⭐ Zorunlu |
| Mevsimsel kutup sıcaklıkları | Zaman ekseni için | 🟡 P2 |

**`ra` (rock abundance) gözden kaçmasın:** Bu, Diviner'ın gece yarısı sıcaklık anomalilerinden türetilen bir **kaya bolluğu** ürünüdür — kayalar regolitten yavaş soğur, gece daha sıcak görünür. Yani termal veriyi indirdiğinizde, aynı pakette **bağımsız bir kaya tehlike katmanı** da geliyor. [02](#belge-02)'deki görüntü tabanlı kaya tespiti işini yapmadan bile bir kaya katmanı kazanmış olursunuz.

#### 2.3 Ölçülmüş sıcaklık bandı — modelin kalibre edilmesi gereken yer

Diviner'ın en bilinen bulgusu: Ay kutup PSR'ları **Güneş Sistemi'nin ölçülmüş en soğuk yerleri** arasındadır; en düşük değerler **~25 K** mertebesine iner (kuzey kutbunda Hermite A gibi kraterlerde). Güney kutup PSR tabanları tipik olarak **~30–50 K** bandındadır. Su buzunun uzun süreli kararlı olduğu eşik **~110 K**'dir.

**LunaPath'in mevcut sentetik modeliyle karşılaştırma:**

| | Sentetik model | Gerçeklik |
|---|---|---|
| Minimum | −250 °C (23 K) clip'i | ~25–40 K ✅ mertebe doğru |
| Maksimum | +80 °C (353 K) | Kutup aydınlık zirveleri **~200–260 K** ❌ **~100 K fazla iyimser** |
| Ortalama | Belgede "−50 °C civarı beklenir" (223 K) | Kutup için makul mertebe 🟡 |

**En büyük sistematik hata maksimumda.** +80 °C bir yüzey, `f_thermal` içinde T_iç = +40 °C üretir → penalty ~0.011 (ideal). Yani sentetik model, kutupta **var olmayan bir termal cennet** icat ediyor ve planlayıcı buraya çekiliyor. Bu, rotaların yüksek elevasyona sapma eğiliminin nedenidir. Düzeltme (P0, tek satır): `T_max_base = -13.0` (260 K).

#### 2.4 Termofiziksel özellikler ve `H` parametresi

Diviner'dan türetilen küresel regolit termofiziksel modeli (Hayne vd., 2017, *JGR Planets*), derinliğe bağlı yoğunluk profili kullanır:

- `ρ_s` (yüzey) ve `ρ_d` (derin) sınır yoğunlukları arasında geçiş
- **`H` parametresi**: bu düşey profilin **ölçek yüksekliği** — temas iletkenliği bileşeninin ve yığın yoğunluğunun derinlikle büyümesini kontrol eder
- PSR içindeki regolitin gözenekliliği **PSR dışına göre belirgin biçimde yüksek** olabilir (dışta ~%40'a karşı içte ~%70'e kadar)

**LunaPath için pratik anlamı:** PSR içi ve dışı **farklı ısı iletkenliğine** sahiptir. Yani PSR'a giren rover, sadece daha soğuk bir ortamla değil, **daha yalıtkan bir zeminle** karşılaşır (temastan ısı kaybı azalır, ama regolitten ısı kazancı da azalır). İkinci mertebe bir etkidir; belgeleyin, modellemeyi P2'ye bırakın.

---

<a id="b07-s3"></a>

### [B07] 3. Doğru model: tek düğümlü (lumped capacitance) termal denge

Sabit ofset modelinin yerine geçecek, **hâlâ basit ama fiziksel** model:

```
C · dT_iç/dt = P_iç + P_ısıtıcı + P_güneş·α·A_abs
               − ε·σ·A_rad·(T_iç⁴ − T_uzay⁴)
               − (T_iç − T_yüzey)/R_temas
```

Ayrık zaman (rota üzerinde segment segment ilerlerken):

```python
# backend/app/thermal_dynamics.py (yeni)
import math

SIGMA = 5.670374419e-8   # Stefan-Boltzmann, W/m^2/K^4
T_SPACE_K = 3.0          # derin uzay

def step_inner_temperature(
    T_inner_K: float,
    T_surface_K: float,
    dt_s: float,
    *,
    C_J_per_K: float,        # rover isil kutlesi
    R_contact_K_per_W: float, # tekerlek/govde -> zemin isil direnci
    eps_A_rad_m2: float,      # emissivite x radyator alani
    P_internal_W: float,      # elektronik + itki
    P_heater_W: float,
    P_solar_absorbed_W: float,
) -> float:
    """Bir zaman adiminda ic sicakligi guncelle (ileri Euler).
    dt_s << tau olmali; aksi halde RK4 veya analitik cozum kullan."""
    Q_in  = P_internal_W + P_heater_W + P_solar_absorbed_W
    Q_rad = eps_A_rad_m2 * SIGMA * (T_inner_K**4 - T_SPACE_K**4)
    Q_cond = (T_inner_K - T_surface_K) / R_contact_K_per_W
    dT = (Q_in - Q_rad - Q_cond) * dt_s / C_J_per_K
    return T_inner_K + dT
```

#### 3.1 `THERMAL_TAU_S = 7200` sabitini denetleyelim

Zaman sabiti `τ = C / (hA)` şeklinde türer. LPR-1 için:

```
C  ≈ m · c_p = 450 kg × ~900 J/(kg·K) ≈ 4.0 × 10⁵ J/K
τ  = 7200 s  ⟹  hA = C/τ = 4.0e5 / 7200 ≈ 56 W/K
```

**56 W/K, iyi yalıtılmış bir uzay aracı için çok yüksektir.** MLI'lı bir gövdede etkin iletkenlik tipik olarak **birkaç W/K** mertebesindedir. `hA = 5 W/K` alırsak:

```
τ = 4.0e5 / 5 = 80.000 s ≈ 22 saat
```

> **Bulgu:** `THERMAL_TAU_S = 7200 s` (2 saat), tüm araç için muhtemelen **bir mertebe küçük**. Bu değer küçük bir bileşen (ör. bir kamera muhafazası) için makul olabilir ama 450 kg'lık bir aracın gövdesi için değil. Referans belge bu sabiti 1800 s'den 7200 s'ye yükselttiğini not ediyor — doğru yönde ama yeterli değil.

**Bu neden önemli:** τ, rover'ın gölgede ne kadar dayanacağını belirler. τ küçükse model rover'ı **aşırı kırılgan** gösterir (birkaç saatte soğuyor), gerçekte ise ısıl kütle onu çok daha uzun korur. Bu, `H_MAX_SHADOW_H = 50` sabitiyle **çelişir**: 2 saatlik zaman sabitiyle 50 saat gölgede kalmak imkânsızdır (5τ sonunda denge sıcaklığına oturur).

**Aksiyon (P0, düşük efor, yüksek getiri):** `τ`'yu tek bir sabit olarak vermeyin; `C` ve `hA`'dan **türetin** ve türetmeyi belgeleyin. Böylece sayı savunulabilir hale gelir ve tutarlılık otomatik sağlanır.

#### 3.2 Enerji bütçesi tutarlılık denetimi (iyi haber)

Aynı denetimi gölge/batarya sabitlerine uygulayınca sonuç **olumlu**:

```
Kullanılabilir enerji = E_CAP × (1 − SOC_MIN) = 5420 × 0.80 = 4336 Wh

Aktif gölge sürüşü (P_SHADOW_W = 65 W):     4336 / 65  ≈ 67 saat
Hibernate modu    (P_HIBERNATE_W = 108 W):  4336 / 108 ≈ 40 saat
```

`H_MAX_SHADOW_H = 50` bu ikisinin **arasında** oturuyor; `H_DESIGN_SHADOW_H = 70` ise 4336/70 ≈ 62 W ≈ `P_SHADOW_W`'ya karşılık geliyor. **Yani gölge ve enerji sabitleri kendi içinde tutarlı ve fiziksel olarak türetilebilir durumda.** Bu, ekibin lehine bir bulgudur ve sunumda söylenmeye değer: *"Sabitlerimiz keyfi değil; gölge limiti, batarya kapasitesi ve gölge modu güç tüketiminden türetilebiliyor."*

**Karşıtlık:** Enerji tarafı tutarlı, termal zaman sabiti tarafı değil. Termal tarafı da aynı disipline getirmek gerekiyor.

---

<a id="b07-s4"></a>

### [B07] 4. Zaman ekseni: aydınlanmadan sıcaklığa

#### 4.1 Neden zorunlu

`f_shadow(H_hours)` fonksiyonu **kümülatif gölge süresi** istiyor. Statik bir haritada "kümülatif gölge süresi" tanımsızdır. Mevcut proxy:

```python
estimate_shadow_hours(elev_norm, Δt) = (1 - elev_norm) × Δt
```

Bu, "alçaktaysan zamanının bir kısmı karanlıktır" der — ne uzamsal ne zamansal olarak fiziksel bir ifade. Doğru zincir:

```
zaman (UTC) ──SPICE──► güneş azimut/elevasyon ──ufuk maskesi──► aydınlık mı?
   ──► P_güneş(t) ──► SOC(t)
   ──► T_yüzey(t) [Diviner yerel-zaman ürünleri veya heat1d]
   ──► T_iç(t) [lumped capacitance]
   ──► f_thermal(T_iç), f_shadow(∫karanlık dt)
```

#### 4.2 Üç seviyeli uygulama seçeneği

| Seviye | Yaklaşım | Efor | Doğruluk |
|---|---|---|---|
| **L1 — statik** (bugün) | Tek snapshot | — | ❌ Gölge süresi tanımsız |
| **L2 — hazır aydınlanma ürünü** | LOLA `average illumination` haritası → hücre başına "aydınlık kesri". `H_gölge = Σ (1 − illum_frac) × Δt` | **Düşük** | 🟡 İstatistiksel olarak doğru, olay bazında değil |
| **L3 — zaman-değişken** | SPICE ile güneş geometrisi + kendi ufuk maskeniz → her (hücre, zaman) için ikili aydınlık/gölge | Orta-yüksek | ✅ Fiziksel olarak doğru |

**Önerilen: L2'yi hemen yap, L3'ü hedef olarak koy.** L2, tek satırlık bir kavramsal düzeltmeyle mevcut `f_shadow`'u anlamlı hale getirir ve **indirilebilir bir ürüne** dayanır. `estimate_shadow_hours`'ın yeni hali:

```python
def estimate_shadow_hours(illum_frac: float, delta_t_hours: float) -> float:
    """illum_frac: LOLA average-illumination urunundan [0,1]
    (bu hucrenin bir ay/yil boyunca aydinlik kalma kesri).
    Donus: bu hucrede delta_t sure gecirmenin BEKLENEN golge katkisi."""
    return (1.0 - illum_frac) * delta_t_hours
```

Formül aynı görünüyor ama girdi artık **elevasyon değil, ölçülmüş aydınlanma kesri**. Bu, fiziksel olarak savunulabilir hale gelir — çünkü artık gerçekten "beklenen gölge süresi"dir.

> ✅ **İyi haber — kod bu değişikliğe hazır.** `cost_engine.edge_shadow_hours(shadow_ratio, theta_deg, d_m)` fonksiyonu şu işi yapıyor:
> `shadow_hours = shadow_ratio × (kenar_geçiş_süresi_s / 3600)`
> Yani karanlık kesri × süre. Fonksiyon **imzası bile değişmiyor**; sadece `shadow_ratio_grid`'i besleyen kaynağı `1 − elev_norm`'dan `1 − illumination_frac`'a çevirmek yeterli. Bu, projedeki en yüksek getirili tek satırlık düzeltmedir: fiziksel geçerlilik `NOT_MEASURED` → `MEASURED`'a terfi ederken planlayıcı kodunda hiçbir değişiklik gerekmez.

L3 için altyapı [04](#belge-04) §2.1 (SpiceyPy) ve §2.2 (ufuk hesabı) ile paylaşımlıdır — aynı ray-marching kodu radyasyon SVF'sini de üretir ([06](#belge-06) §2). **Bir kez yaz, üç katman kazan.**

#### 4.3 heat1d ile yüzey sıcaklığı dinamiği

Gerçek zaman-değişken yüzey sıcaklığı istiyorsanız, Diviner'ın kendi ekibinden açık kaynak bir 1-B termal model var: **[heat1d](https://github.com/phayne/heat1d)** (Paul Hayne). Girdi olarak güneş akısı zaman serisi + regolit termofiziksel parametreleri (H parametresi dahil) alır, derinlik-zaman sıcaklık profili üretir.

**Kullanım deseni:** Her hücre için heat1d koşmak imkânsız (500×500 = 250.000 koşum). Bunun yerine:

1. Birkaç **temsili rejim** seçin: {kalıcı gölge, düşük aydınlanma, orta, yüksek, kalıcı aydınlık} × {düz, kuzey yamaç, güney yamaç}
2. Her rejim için heat1d ile **sıcaklık zaman serisi** üretin (offline, bir kez)
3. Grid hücrelerini rejimlere **sınıflandırın** (illumination_frac + slope + aspect ile)
4. Planlama sırasında **lookup table**'dan oku

Bu, "fiziksel model" ile "hesaplanabilirlik" arasındaki doğru uzlaşmadır ve [08](#belge-08)'in ana temasıyla (önceden hesapla, çalışma zamanında ara) uyumludur.

---

<a id="b07-s5"></a>

### [B07] 5. Doğrulama planı — sentetiği gerçekle ölçmek

[03](#belge-03) §4.2'deki A/B/C/D ablasyonunun termal kolu için somut metrikler:

| Metrik | Nasıl hesaplanır | Hedef |
|---|---|---|
| **RMSE** | `sqrt(mean((T_sentetik − T_diviner)²))` | Raporla (beklenti: 40–80 K, yani **çok büyük**) |
| **Bias** | `mean(T_sentetik − T_diviner)` | Beklenti: pozitif (sentetik iyimser) |
| **Pearson r** | Uzamsal korelasyon | Beklenti: 0.3–0.6 (mükemmelden uzak) |
| **Sınıf uyumu** | Güvenli/dikkat/tehlikeli üçlüsünde kaç hücre aynı sınıfta? | Confusion matrix olarak sun |
| **Yanlış-güvenli oranı** | Sentetiğin "güvenli", Diviner'ın "tehlikeli" dediği hücre yüzdesi | **En kritik sayı** — operasyonel risk budur |
| **Rota kararı farkı** | A ve D kollarının rotaları arasındaki Fréchet mesafesi | Raporla |

> **Bu tablo doldurulduğunda LunaPath bir hackathon projesi olmaktan çıkar.** Çünkü kendi modelinin hatasını nicelemiş, raporlamış ve düzeltmiş bir mühendislik çalışması haline gelir. Hakem/jüri karşısında "sentetik veri kullandık ama hatasını ölçtük ve gerçeğe geçtik" cümlesi, "gerçek veri kullandık" cümlesinden **daha** güçlüdür.

---

<a id="b07-s6"></a>

### [B07] 6. Boşluk analizi

| # | Boşluk | Etki | Efor | Öncelik |
|---|---|---|---|---|
| T1 | Termal katman sentetik, Diviner mevcutken | 🔴 **Çok yüksek — projenin ana iddiası** | Orta | **P0** |
| T2 | Kutup Diviner ürününün varlığı/kapsamı doğrulanmadı (GHRM 70°S'te bitiyor) | 🔴 Yüksek (blokaj riski) | Çok düşük | **P0** |
| T3 | `T_max_base = +80 °C` kutupta fiziksel değil | 🔴 Yüksek (planlayıcıyı yanlış çekiyor) | Çok düşük | **P0** |
| T4 | Sabit ofset T_yüzey→T_iç modeli fiziksel değil | 🔴 Yüksek | Orta | **P0/P1** |
| T5 | `THERMAL_TAU_S` türetilmemiş, muhtemelen ~10× küçük | 🟠 Yüksek (H_MAX_SHADOW ile çelişiyor) | Düşük | **P1** |
| T6 | Zaman ekseni yok → `f_shadow` girdisi tanımsız | 🟠 Yüksek | Düşük (L2) / Yüksek (L3) | **P1** |
| T7 | `f_thermal` T_iç'i içeride hesaplıyor (ayrıştırılmalı) | 🟡 Orta | Çok düşük | P1 |
| T8 | Kaya bolluğu (`ra`) ürünü kullanılmıyor (bedava) | 🟡 Orta | Düşük | P1 |
| T9 | Termofiziksel özellikler (H parametresi, PSR gözenekliliği) modellenmiyor | 🟢 Düşük-orta | Yüksek | P2 |
| T10 | Diviner ile karşılaştırma/validasyon yok | 🟠 Yüksek | Düşük (veri gelince) | **P1** |

---

<a id="b07-s7"></a>

### [B07] 7. Yol haritası

#### P0 — "acil düzeltmeler ve blokaj kaldırma" (1 gün)

1. **Kutup Diviner ürününü doğrula.** PDS Geosciences'ta `lro_diviner` bundle'larını listele, 80–90°S kapsayan sıcaklık ürününü teyit et. Bulunamıyorsa alternatif: yayınlanmış kutup sıcaklık haritalarını (Paige vd. 2010 kutup ürünleri, mevsimsel kutup sıcaklıkları) takip et.
2. **`T_max_base_C`'yi −13 °C'ye (260 K) çek**, gerekçesini kodda yorum olarak yaz. Bu tek satır, planlayıcının yüksek elevasyona yapay çekimini kaldırır.
3. **`f_thermal`'i ayrıştır**: `f_thermal_from_inner()` + geriye uyumlu sarmalayıcı.
4. **`metadata.json`'a `physical_validity`** yaz → [01](#belge-01) §3.1.

#### P1 — "gerçek veriye geç ve modeli fizikselleştir" (4–6 gün)

5. Diviner `tbol` (kutup) indir → hizala → `thermal_grid_diviner.npy`; sentetiği `thermal_grid_synthetic.npy` olarak koru
6. **A/B/C/D ablasyon koşusu** + §5 doğrulama tablosu → `docs/research/ablation_report.md`
7. LOLA `average illumination` indir → `estimate_shadow_hours`'ı illumination_frac ile besle (L2)
8. **`thermal_dynamics.py`**: lumped capacitance modeli; `τ`'yu `C` ve `hA`'dan türet; `H_MAX_SHADOW_H` ile tutarlılığı test et
9. Diviner `ra` (kaya bolluğu) → yeni bağımsız tehlike katmanı
10. Metrikler: `min_surface_temp_K`, `min_inner_temp_K`, `thermal_violation_count`, `time_below_bat_op_min_h`, `synthetic_vs_measured_rmse_K`

**Kabul kriteri (P1):**
- `thermal_grid` kaynağı `LRO/Diviner`, `physical_validity: MEASURED`
- Ablasyon tablosu dolu, **yanlış-güvenli hücre oranı** sayısal olarak raporlanmış
- `THERMAL_TAU_S` artık sabit değil, `C/(hA)`'dan türetilmiş ve `H_MAX_SHADOW_H` ile tutarlı
- Rota üzerinde `T_iç(t)` eğrisi çizilebiliyor (frontend'de zaman serisi grafiği)

#### P2 — "derinleştir"
11. SPICE + ufuk maskesi ile L3 zaman-değişken aydınlanma
12. heat1d ile rejim-tabanlı yüzey sıcaklığı lookup tablosu
13. H parametresi / PSR gözenekliliği ikinci mertebe etkileri

---

<a id="b07-s8"></a>

### [B07] 8. Sunumda kullanılacak cümleler

- *"Termal katmanımız artık sentetik değil; LRO/Diviner'ın 15 yıllık bolometrik sıcaklık ölçümlerine dayanıyor. Sentetik modelimizi bir kontrol kolu olarak tutup hatasını niceledik: RMSE X K, ve sentetik model hücrelerin %Y'sini yanlışlıkla güvenli işaretliyordu."*
- *"İç sıcaklığı yüzey sıcaklığının sabit bir ötelemesi olarak modellemiyoruz. Tek düğümlü bir enerji dengesi kuruyoruz: ısıtıcı gücü, radyatör kaybı ve zeminle temas iletimi. Bu, termal zaman sabitini bir varsayım olmaktan çıkarıp ısıl kütle ve yalıtımdan türetilen bir büyüklüğe dönüştürdü."*
- *"Gölge ve enerji sabitlerimiz kendi içinde tutarlı: 50 saatlik gölge limiti, 4336 Wh kullanılabilir enerji ve 65 W gölge modu tüketiminden türetiliyor."*
- *"Ay kutup PSR'ları Güneş Sistemi'nin ölçülmüş en soğuk yerleri arasında, ~25–40 K bandında. Su buzu ~110 K altında kararlı. Bizim rover'ımızın batarya alt limiti 0 °C = 273 K — yani bilimsel olarak en değerli hedef, mühendislik olarak en ölümcül bölge. Projemizin varlık nedeni bu çelişkidir."*

---

<a id="b07-s9"></a>

### [B07] Kaynaklar

- [Paige et al. (2010), Diviner Lunar Radiometer Experiment, Science 330, 479](https://www.science.org/doi/10.1126/science.1197135)
- [The global surface temperatures of the Moon as measured by Diviner (Icarus)](https://www.sciencedirect.com/science/article/pii/S0019103516304869)
- [LRO Diviner Global High-Resolution Mosaics (GHRM) — ODE/WUSTL](https://ode.rsl.wustl.edu/moon/pagehelp/Content/Missions_Instruments/Lunar%20Reconnaissance%20Orbiter%20(LRO)/DIVINER/GHRM.htm)
- [LRO Diviner Lunar Radiometer Global Data Products (Planetary Data Workshop)](https://www.hou.usra.edu/meetings/planetdata2017/pdf/7095.pdf)
- [Hayne et al. (2017), Global Regolith Thermophysical Properties of the Moon From Diviner, JGR Planets](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/2017JE005387)
- [Global regolith thermophysical properties of the Moon (arXiv 1711.00977)](https://arxiv.org/pdf/1711.00977)
- [A Model for the Thermophysical Properties of Lunar Regolith at Low Temperatures (Diviner/UCLA)](https://luna1.diviner.ucla.edu/~dap/pubs/096.pdf)
- [Powell et al. (2023), High-Resolution Nighttime Temperature and Rock Abundance Mapping, JGR Planets](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2022JE007532)
- [Thermophysical Properties of Lunar Regolith from Diviner (ApJ)](https://iopscience.iop.org/article/10.3847/1538-4357/addd1d)
- [Thermal Stability of Ice at Shackleton Crater (PSJ)](https://iopscience.iop.org/article/10.3847/PSJ/ae3c86)
- [heat1d — Thermal model for planetary science (GitHub)](https://github.com/phayne/heat1d)
- [Paul Hayne — Lunar Regolith projects](https://phayne.github.io/projects/5_lunar-regolith/)

[↑ İçindekiler](#icindekiler) · [↑ Yönlendirme tablosu](#yonlendirme)

---

<a id="belge-08"></a>

## BELGE 08 — Global / Local Rotalandırma ve Hesaplama Yükü

> **Belge kimliği:** `BELGE 08` (bölüm başlıklarında `[B08]` etiketiyle işaretlidir) · **Kaynak dosya:** `08_global_local_rotalama_yuku.md`  
> **Konu:** Hiyerarşik planlama, hesap bütçesi, uçuş bilgisayarı, latency  
> **Ana çıktı:** Hesaplama bütçesi ve mimari ayrıştırma  
> **Ayırt edici terimler:** `HPSC`, `RAD750`, `uçuş bilgisayarı`

> **Soru:** LunaPath'in planlayıcısı ne kadar pahalı? Nerede koşacak — yerde mi, rover'da mı? Global ve yerel katmanlar arasındaki iş bölümü ne olmalı? Zaman ekseni eklenince maliyet ne olur?
>
> **Kısa cevap:** Hesaplama yükü, LunaPath'te **hiç konuşulmamış ama mimariyi belirleyen** kısıttır. Bugünkü A* bir masaüstünde çalışıyor; uçuş bilgisayarında ~400–1000× daha az bütçe var. İyi haber: LunaPath'in maliyet fonksiyonu **tamamen ön-hesaplanabilir** — 8 yönlü maliyet dizisi olarak vektörleştirilirse A*'ın iç döngüsü saf dizi okumasına iner ve 10–100× hızlanır. Kötü haber: zaman ekseni eklenince problem boyutu **K katına** çıkar ve tek düz grid çözümü çöker; hiyerarşi zorunlu hale gelir.

---

<a id="b08-s1"></a>

### [B08] 1. Bugünkü yükün anatomisi

#### 1.1 Problem boyutu

| Büyüklük | Değer |
|---|---|
| Grid | 500 × 500 = **250.000 düğüm** |
| Komşuluk | 8-yönlü → **~2.000.000 kenar** |
| Katman sayısı | 7 |
| Bellek (float64) | 7 × 250.000 × 8 B = **14 MB** |
| Bellek (float32) | **7 MB** |
| Performans hedefi (referans belge §8, Aşama 3) | 500×500'de **< 2 saniye** |

#### 1.2 Kenar başına gerçek maliyet

`total_edge_cost` (`cost_engine.py:252`) her kenar için şunları çağırıyor:

| Bileşen | Transandantal işlem |
|---|---|
| `f_slope` | 1 `exp` |
| `f_energy` | `sin`, `cos`, `cos`, 1 bölme (+ mesafe hesabı) |
| `f_shadow` | 2 `exp` |
| `f_thermal` | 4 `exp` (iki sigmoid çifti) |
| `log_barrier_penalty` | 5 `log` |
| **Toplam** | **~15 transandantal + ~20 aritmetik işlem** |

Bir düğüm genişletmesi 8 kenar → **~120 transandantal işlem**. Tam genişletme (worst case) → **~30 milyon transandantal işlem** + Python fonksiyon çağrı ek yükü.

**Saf Python'da fonksiyon çağrı ek yükü baskın:** kenar başına ~6 fonksiyon çağrısı × ~1 µs ≈ 6 µs → düğüm başına ~50 µs → 250.000 düğüm için **~12 saniye**. Yani mevcut mimari, kötü senaryoda 2 saniye hedefini **6× aşar**. (Gerçekte A* hedefe doğru heuristic ile daha az düğüm genişletir; `nodes_expanded` metriği kodda zaten mevcut — bunu **ölçün ve raporlayın.**)

---

<a id="b08-s2"></a>

### [B08] 2. En yüksek getirili optimizasyon: maliyeti tamamen ön-hesapla

Bu, LunaPath'in yapısındaki **kullanılmamış büyük bir fırsat**. Maliyet bileşenlerini ayrıştırın:

| Bileşen | Neye bağlı | Ön-hesaplanabilir mi? |
|---|---|---|
| `f_slope(θ_ab)` | Sadece a ve b hücrelerinin geometrisi | ✅ **Evet** — yön başına bir dizi |
| `f_energy(θ_ab, d)` | Aynı | ✅ **Evet** |
| `f_shadow(H)` | **Kümülatif** gölge süresi | ❌ Yola bağlı |
| `f_thermal(T_b)` | Sadece hedef hücre | ✅ **Evet** — tek dizi |
| `log_barrier(θ, SOC, T_iç)` | SOC ve T_iç **kümülatif** | ❌ Yola bağlı |

**Kritik gözlem:** `f_slope`, `f_energy` ve `f_thermal` — yani ağırlıkların **%85.8'i** (0.409 + 0.259 + 0.190) — tamamen yola bağımsızdır ve önceden hesaplanabilir.

```python
# backend/app/precompute.py (yeni)
import numpy as np

DIRS = [(-1,-1), (-1,0), (-1,1), (0,-1), (0,1), (1,-1), (1,0), (1,1)]

def precompute_edge_costs(elev, slope, thermal, res_m, weights):
    """8 yon icin (H, W) maliyet dizisi uret. Tamamen vektorel.
    A*'in ic dongusu bundan sonra sadece dizi okumasi yapar.

    Donus: dict[(dr,dc)] -> (H, W) float32 array
           edge_cost[(dr,dc)][r, c] = (r,c)'den (r+dr, c+dc)'ye gitme maliyeti
    """
    H, W = elev.shape
    f_th = f_thermal_vec(thermal)          # node-bazli, bir kez
    out = {}
    for dr, dc in DIRS:
        d_m = res_m * (2 ** 0.5 if dr and dc else 1.0)
        # kaydirilmis yukseklik farkindan gercek gecis egimi
        dz = shift(elev, dr, dc) - elev
        theta = np.degrees(np.arctan(np.abs(dz) / d_m))
        cost = (weights["w_slope"]  * f_slope_vec(theta)
              + weights["w_energy"] * f_energy_vec(theta, d_m)
              + weights["w_thermal"] * shift(f_th, dr, dc))
        cost[theta > 25.0] = np.inf          # hard constraint
        out[(dr, dc)] = cost.astype(np.float32)
    return out
```

**Maliyet:** 8 × 250.000 = 2M vektörel değerlendirme → numpy'da **~50–200 ms, bir kez**.
**Kazanç:** A*'ın iç döngüsü `cost = edge_cost[(dr,dc)][r, c]` — tek dizi indeksleme. Yola bağlı terimler (`f_shadow`, `log_barrier`) sadece **gerçekten genişletilen** düğümlerde hesaplanır.

Bu değişiklikle **2 saniye hedefi rahatça tutulur** ve `numba` bile gerekmeyebilir. Ayrıca **çoklu profil koşumu bedavaya yakın hale gelir**: 4 profil = 4 farklı ağırlık seti = 4 kez ön-hesaplama (toplam ~1 s) ama ardından 4 A* koşumu çok hızlı. `/api/compare` endpoint'inin performansı doğrudan iyileşir.

> **Uyarı — geometrik doğruluk:** Mevcut kod eğimi `np.gradient` ile hücre-merkezli hesaplıyor, sonra kenar için kullanıyor. Yukarıdaki ön-hesaplama **kenar boyunca gerçek yükseklik farkını** kullanıyor — bu daha doğrudur ve rotanın gerçek tırmanış açısını temsil eder. Geçiş yaparken metrikler değişecektir; bu bir hata değil, **düzeltmedir** ve belgelenmelidir.

---

<a id="b08-s3"></a>

### [B08] 3. Hiyerarşi: neden zorunlu, nasıl kurulur

#### 3.1 Boyut patlaması

| Senaryo | Düğüm sayısı | Bellek (float32, 8 yön) | Değerlendirme |
|---|---|---|---|
| Bugün: 80 m, 40 km, statik | 250 K | 8 MB | ✅ Rahat |
| 20 m, 40 km, statik | **4 M** | 128 MB | 🟡 Masaüstünde tamam, uçuşta sınırda |
| 5 m, 40 km, statik | **64 M** | 2 GB | ❌ Düz grid çöker |
| 80 m, 40 km, **24 zaman adımı** | 6 M | 192 MB | 🟡 |
| 80 m, 40 km, **168 zaman adımı** (1 hafta, saatlik) | **42 M** | 1.3 GB | ❌ |
| 20 m + 48 zaman adımı | **192 M** | 6 GB | ❌❌ |

**Sonuç net:** LunaPath'in yol haritasındaki iki hedef — daha yüksek çözünürlük ([02](#belge-02)) ve zaman ekseni ([07](#belge-07)) — **düz grid mimarisiyle birlikte imkânsızdır.** Hiyerarşi bir optimizasyon değil, **mimari zorunluluktur**.

#### 3.2 Önerilen üç seviyeli mimari

```
┌─ SEVİYE A: MİSYON PLANLAMA (kaba uzay + zaman) ──────────────────┐
│  Grid  : 160–320 m (mevcut 80 m'nin 2–4× kabası)                 │
│  Zaman : saatlik, 1–7 gün ufuk                                   │
│  Boyut : ~15K hücre × 168 adım ≈ 2.5 M durum → yönetilebilir     │
│  Soru  : "Hangi gün, hangi saatte, hangi kaba koridordan?"        │
│  Çıktı : zaman damgalı kaba waypoint dizisi + bekleme kararları   │
│  Algo  : zaman-genişletilmiş graf üzerinde A* / Dijkstra          │
└──────────────────────────┬───────────────────────────────────────┘
                           │ kaba koridor + zaman penceresi
┌─ SEVİYE B: KORİDOR PLANLAMA (LunaPath'in bugünkü işi) ───────────┐
│  Grid  : 20–80 m, sadece koridor bandı (±500 m)                  │
│  Zaman : sabit (Seviye A'nın verdiği pencere içinde)             │
│  Boyut : ~25K–100K hücre → hızlı                                 │
│  Soru  : "Koridor içinde hangi hücrelerden?"                     │
│  Çıktı : Corridor sözleşmesi ([05](05_engel_kacinma.md) §4.1)     │
│  Algo  : çok kriterli A* (mevcut kod)                            │
└──────────────────────────┬───────────────────────────────────────┘
                           │ waypoint + açıklık + bütçe
┌─ SEVİYE C: YEREL (kapsam dışı, arayüz tanımlı) ──────────────────┐
│  Grid  : 0.1–0.5 m, 5–20 m ufuk                                  │
│  Algo  : arc/DWA/MPC + hazard detection → [05]                   │
└─────────────────────────────────────────────────────────────────┘
```

**Neden bu bölünme doğru:** Her seviye kendi ölçeğinde **doğru soruyu** soruyor. Zamanı kaba uzayda çözmek (Seviye A) doğrudur çünkü aydınlanma saatler ölçeğinde değişir ve 80 m'lik detay bu kararı etkilemez. Uzayı ince çözmek (Seviye B) doğrudur çünkü kaya/eğim metrelerde değişir ve zaman bu kararı etkilemez.

Bu, koridor tabanlı hiyerarşik yaklaşımın literatürdeki karşılığıdır ve lunar micro-rover risk-farkında coverage planlama çalışmasının global (offline DEM maliyeti, `β` terimi) + local (gerçek zamanlı miyopik algılama) ayrımıyla aynı felsefeyi paylaşır: `mc = α(mc_static + mc_visited·V_i) + β·mc_DEM`, burada `α + β = 1` ile arazi-farkındalık ve kapsama verimliliği arasında ayar yapılıyor.

#### 3.3 Zaman-genişletilmiş graf: somut formülasyon

Seviye A için durum: `(hücre, zaman_dilimi)`. Kenarlar:

```python
# Hareket kenari: (cell_i, t) -> (cell_j, t + travel_time)
# Bekleme kenari: (cell_i, t) -> (cell_i, t + 1)   <- KRITIK
```

**Bekleme kenarı olmadan bu problem çözülemez.** Ay kutbunda doğru cevap sıklıkla *"bekle, güneş gelsin, sonra geç"*dir. Literatürde bu açıkça modelleniyor: rover'ın aşırı ısı girdisinden kaçınmak için **beklemesine izin verilir**; kısıtlar statik (arazi eğimi) ve yola-bağlı (rover termal ve güç durumu) tiplere ayrılır, çevresel girdiler (Ay'daki ısı akısı ve aydınlanma) ise **zamana bağlıdır**.

Bekleme kenarının maliyeti:

```python
def wait_cost(cell, t, dt_h, illum_frac, rover):
    """Beklemek bedava degildir: idle guc + termal drift.
    Aydinlikta bekleme SOC'yi ARTIRIR (sarj) -> negatif enerji maliyeti.
    Golgede bekleme hem SOC hem sicaklik kaybettirir."""
    solar_in = rover["P_SOLAR_W"] * illum_frac[cell]
    net_w = solar_in - rover["P_IDLE_W"] - rover["P_HEATER_W"]
    d_soc = net_w * dt_h / rover["E_CAP_WH"]
    return (w_energy * max(0.0, -d_soc)
            + w_shadow * f_shadow_increment(1.0 - illum_frac[cell], dt_h)
            + w_thermal * thermal_drift_penalty(cell, dt_h))
```

> **Bu, LunaPath'e eklenebilecek en yüksek bilimsel değerli tek özelliktir.** "Beklemek bir karardır" fikri, projeyi statik rota çizen bir araçtan **zaman-uzay görev planlayıcısına** dönüştürür ve mevcut sabitlerin (`P_SOLAR_W`, `P_IDLE_W`, `P_HEATER_W`, `SOC_MIN_PCT`) hepsini anlamlı hale getirir. Bugün bu sabitler kodda duruyor ama planlama kararını etkilemiyor.

---

<a id="b08-s4"></a>

### [B08] 4. Nerede koşacak? Yer vs rover

#### 4.1 İletişim gerçekliği

| Büyüklük | Değer |
|---|---|
| Dünya–Ay tek yön ışık süresi | ~1.28 s |
| Gidiş-dönüş | ~2.6 s |
| Pratik komut çevrimi (DSN planlama, yer işleme, operatör onayı) | **saatler** |
| Pragyan operasyonel gerçeklik | Her hareket için navcam verisi Dünya'ya indirilip DEM üretiliyor; **tek komutta en fazla ~5 m** |
| Kutupta Dünya görünürlüğü | Topografyaya bağlı, kesintili |

**Sonuç:** Işık süresi problem değil; **operasyonel çevrim** problem. 2.6 saniyelik gecikme bir joystick için bile tolere edilebilir, ama gerçek operasyonlarda çevrim saatler sürer.

#### 4.2 İş bölümü kararı

| Seviye | Nerede | Gerekçe |
|---|---|---|
| **A — Misyon planlama** | 🌍 **YERDE** | Saatler-günler ufuk; yer bilgisayarı sınırsız; insan onayı gerekir |
| **B — Koridor planlama** | 🌍 **YERDE** (ana), 🛰️ rover'da (yedek/replan) | Yerde tam kalite; rover'da kısıtlı bütçeyle segment replan |
| **C — Yerel** | 🛰️ **ROVER'DA** (zorunlu) | Saniyeler; Dünya'ya sorulamaz |

**LunaPath'in doğru konumu Seviye A + B, yerde.** Bu, projeyi zayıflatmaz — Pragyan bugün tam olarak böyle çalışıyor ve VIPER gibi kutup misyonlarında görev öncesi termal/enerji kısıtlı planlama, yer tarafında yapılan **kritik** bir iştir.

#### 4.3 Onboard bütçe: sayılarla

Rover'da koşturma iddiası kurarsanız, karşı karşıya olduğunuz gerçek:

| Platform | Performans | Not |
|---|---|---|
| **RAD750** (LRO, Curiosity, Perseverance, JWST) | **110–200 MHz**, ~**266 MIPS** | 20 yıldır BLEO misyonlarının fiili standardı |
| Modern dizüstü (çok çekirdek + SIMD) | ~10⁵ MIPS mertebesi | **~400–1000× fark** |
| **PIC64-HPSC** (NASA HPSC / Microchip + SiFive RISC-V) | **26.000 DMIPS**, **1 TFLOPS** bf16 / **2 TOPS** int8, 3U SpaceVPX | Geleneksel uzay işlemcilerine göre **~100×**; sanallaştırma, AI, TSN Ethernet, PCIe, CXL 2.0, post-kuantum kripto |

**PIC64-HPSC'nin ilan edilen kullanım senaryolarından biri doğrudan** "Ay yüzeyinde rover hazard avoidance gibi gerçek zamanlı görevleri yerel işlem gücüyle yürütmek" olarak tanımlanıyor. Yani LunaPath'in yerel katman hayali, **2020'lerin ikinci yarısında donanım olarak mümkün hale geliyor** — ama bugünün uçan donanımında değil.

**Somut bütçe egzersizi (belgede olması gereken):**

```
Varsayım: RAD750 sınıfı, planlayıcıya CPU'nun %20'si ayrılmış, 10 s bütçe
→ etkin ~530 M komut

Ön-hesaplanmış maliyetle A*, düğüm başına ~50 komut (dizi okuma + heap)
→ ~10 M düğüm genişletmesi bütçesi

500×500 grid, hedef-yönlü heuristic ile tipik ~%20 genişletme = 50 K düğüm
→ ✅ RAHAT SIĞAR (bütçenin %0.5'i)

2000×2000 (20 m) grid, %20 genişletme = 800 K düğüm
→ ✅ Sığar (bütçenin %8'i)

Zaman-genişletilmiş (168 adım), %5 genişletme = 2.1 M düğüm
→ 🟡 Sınırda; bellek (1.3 GB) asıl darboğaz
```

> **Bu tablo LunaPath'in en güçlü olgunluk kanıtlarından biri olabilir.** "Algoritmamız uçuş bilgisayarı sınıfı bir platformda hesaplama bütçesinin %X'ini kullanır" cümlesi, hiçbir hackathon projesinin söylemediği bir şeydir ve söylemek için **sadece bir hesap tablosu** gerekir.

#### 4.4 Bellek darboğazı

Uçuş bilgisayarlarında RAM tipik olarak **128–512 MB** mertebesindedir (RAD750 sistemleri). LunaPath:

| Konfigürasyon | Bellek | Uçuşta? |
|---|---|---|
| 500×500, float32, 7 katman + 8 yön maliyet | ~15 MB | ✅ Rahat |
| 2000×2000, float32 | ~240 MB | 🟡 Sınırda |
| Zaman-genişletilmiş 168 adım | 1.3 GB | ❌ Hayır |

**Reçete:** `float64` → `float32` geçişi tek satırlık bir değişiklikle belleği yarıya indirir ve termal/eğim hassasiyeti için `float32` (7 anlamlı basamak) **fazlasıyla** yeterlidir. Mevcut pipeline `float64` kullanıyor (`process_lunar_data.py` "P1 grid standardı" olarak `float64` seçmiş) — bunu gözden geçirin. Elevasyon için `float32` ~0.001 m çözünürlük verir; LOLA'nın kendi belirsizliği 0.30–0.50 m'dir.

---

<a id="b08-s5"></a>

### [B08] 5. Anytime planlama: sert zaman limitiyle nasıl baş edilir

Onboard senaryoda bütçe aşılırsa ne olacak? İki kötü seçenek ve bir iyi seçenek:

| Yaklaşım | Sonuç |
|---|---|
| ❌ Bitene kadar koş | Zaman limiti ihlali → görev yazılımı watchdog |
| ❌ Kes ve rota yok | Rover bekler → enerji/termal kayıp |
| ✅ **Anytime (ARA\*)** | Gevşetilmiş heuristic (`ε > 1`) ile hızlı bir **suboptimal ama geçerli** rota bul, kalan zamanla `ε`'yi 1'e doğru azaltarak iyileştir |

ARA*'ın LunaPath için avantajı: `ε`-suboptimal garanti verir. Yani *"bütçe dolduğunda elimizdeki rota, optimalin en fazla %20 üzerindedir"* diyebilirsiniz. Bu, uzay yazılımında **kanıtlanabilir sınır** anlamına gelir ve deterministik kesme davranışından çok daha savunulabilirdir.

**Uygulama maliyeti düşük:** mevcut A*'a `epsilon` parametresi + dış döngü:

```python
def anytime_astar(grids, start, goal, weights, budget_ms, eps_schedule=(3.0, 2.0, 1.5, 1.2, 1.0)):
    best, t0 = None, time.perf_counter()
    for eps in eps_schedule:
        remaining = budget_ms - (time.perf_counter() - t0) * 1000
        if remaining <= 0: break
        r = astar(grids, start, goal, weights, h_weight=eps, deadline_ms=remaining)
        if r["path_pixels"]:
            best = r | {"suboptimality_bound": eps}
    return best
```

**`suboptimality_bound` alanını `PathResult.metrics`'e ekleyin.** Bu, tek bir alanla olgunluk sinyali verir.

---

<a id="b08-s6"></a>

### [B08] 6. Ölçüm planı (benchmark)

`pathfinder.py` zaten `computation_time_ms` ve `nodes_expanded` raporluyor — **altyapı hazır, kullanılmıyor.** Eksik olan sistematik ölçüm:

```python
# backend/test_planner_benchmark.py (yeni)
CASES = [
    # (grid_boyutu, start-goal mesafesi, profil, engel yogunlugu)
    (100, "kisa",  "balanced",       "dusuk"),
    (500, "orta",  "balanced",       "orta"),
    (500, "uzun",  "energy_saver",   "orta"),
    (500, "uzun",  "shadow_traverse","yuksek"),
    (2000,"uzun",  "balanced",       "orta"),
]

def test_benchmark_table(benchmark_writer):
    """Cikti: docs/research/planner_benchmark.md
    Kolonlar: case, nodes_expanded, expansion_ratio, time_ms,
              time_per_node_us, path_length, cost, peak_memory_mb"""
```

**Raporlanması gereken metrikler:**

| Metrik | Neden |
|---|---|
`nodes_expanded / total_nodes` | Heuristic'in ne kadar etkili olduğu (**admissibility kanıtı**) |
`time_per_node_us` | Platform bağımsız karşılaştırma birimi |
`peak_memory_mb` | Uçuş bütçesi analizi için |
`precompute_ms` vs `search_ms` | Ön-hesaplama kazancını göstermek |
`suboptimality_bound` | Anytime modda |
`replan_ms` | Segment replanning maliyeti (tam koşumla karşılaştırma) |

#### 6.1 Heuristic admissibility — sessiz bir risk

Referans belge heuristic'i şöyle tanımlıyor: *"Euclidean mesafe × minimum edge cost (admissible)"*.

**Bu iddianın kanıtlanması gerekir.** `min_edge_cost` gerçekten tüm kenarların alt sınırı mı? Maliyet fonksiyonunda `max(0.01, C)` clamp'ı var (`C = max(0.01, C)`), yani teorik minimum 0.01'dir. Heuristic `0.01 × euclid_distance / cell_size` kullanıyorsa admissible'dır ama **çok gevşektir** (neredeyse Dijkstra'ya döner → yavaş). Daha sıkı bir alt sınır kullanılıyorsa admissibility bozulabilir → **optimal olmayan rota, "optimal" olarak sunulur.**

**Aksiyon:** Bir test yazın:

```python
def test_heuristic_is_admissible(grids, weights):
    """Rastgele 1000 (node, goal) cifti icin:
    h(node, goal) <= gercek_optimal_maliyet(node, goal)
    Gercek optimal: geriye dogru Dijkstra ile tam cozum."""
```

Bu, "optimal rota buluyoruz" iddiasının **tek geçerli kanıtıdır** ve şu an yok.

---

<a id="b08-s7"></a>

### [B08] 7. Boşluk analizi

| # | Boşluk | Etki | Efor | Öncelik |
|---|---|---|---|---|
| C1 | Hesaplama bütçesi hiç analiz edilmemiş | 🟠 Yüksek (olgunluk) | Düşük | **P0** |
| C2 | Maliyet ön-hesaplanmıyor (10–100× kayıp) | 🟠 Yüksek | Orta | **P0/P1** |
| C3 | Heuristic admissibility kanıtlanmamış | 🔴 Yüksek (optimallik iddiası) | Düşük | **P0** |
| C4 | Benchmark tablosu yok (altyapı hazırken) | 🟠 Orta-yüksek | Düşük | **P0** |
| C5 | Hiyerarşi yok → yüksek çözünürlük ve zaman imkânsız | 🔴 Yüksek (yol haritası blokajı) | Yüksek | **P1** |
| C6 | Zaman-genişletilmiş graf ve **bekleme kenarı** yok | 🔴 Yüksek (bilimsel değer) | Yüksek | **P1** |
| C7 | Anytime/suboptimality sınırı yok | 🟡 Orta | Düşük | P1 |
| C8 | `float64` bellek israfı | 🟡 Orta | Çok düşük | P1 |
| C9 | Onboard/yer iş bölümü belgelenmemiş | 🟠 Orta-yüksek | Çok düşük | **P0** |

---

<a id="b08-s8"></a>

### [B08] 8. Yol haritası

#### P0 — "ölç ve belgele" (1–2 gün, kod değişikliği minimal)
1. **Benchmark tablosu üret** (§6) → `docs/research/planner_benchmark.md`
2. **Heuristic admissibility testi** yaz ve geçir (§6.1)
3. **Hesaplama bütçesi analizi** belgele (§4.3) — RAD750 ve HPSC karşılaştırmalı tablo
4. **Yer/rover iş bölümü** bölümünü mimari belgeye ekle (§4.2)

#### P1 — "hızlandır ve hiyerarşiye geç" (5–8 gün)
5. **`precompute_edge_costs`** (§2) — öncesi/sonrası benchmark ile
6. `float64` → `float32`
7. Anytime A* + `suboptimality_bound` metriği (§5)
8. **Seviye A/B ayrımı**: kaba grid (160–320 m) + zaman-genişletilmiş graf + **bekleme kenarı** (§3.3)
9. Koridor daraltma (Seviye A çıktısı → Seviye B girdisi)
10. Segment replanning + `replan_ms` ölçümü

**Kabul kriteri (P1):**
- Benchmark tablosu ön-hesaplama öncesi/sonrası **ölçülmüş hızlanmayı** gösteriyor
- Zaman-genişletilmiş planlayıcı, bir senaryoda **"beklemeyi seçtiğini"** gösteriyor (aydınlık gelene kadar bekle → sonra geç). Bu, tek başına güçlü bir demo.
- 20 m grid'de plan süresi < 5 s
- Hesaplama bütçesi tablosu belgede

#### P2
11. Numba/Cython ile çekirdek JIT (ön-hesaplama yetmezse)
12. D* Lite (ölçüm gerektiriyorsa — [05](#belge-05) §4.2)
13. cFS/F´ app paketleme iskeleti ([04](#belge-04) §6)

---

<a id="b08-s9"></a>

### [B08] 9. Sunumda kullanılacak cümleler

- *"Maliyet fonksiyonumuzun %86'sı yola bağımsızdır ve tamamen ön-hesaplanabilir. Bu sayede A*'ın iç döngüsü saf dizi okumasına indi ve 500×500 grid'de plan süresi X ms'ye düştü."*
- *"Planlayıcımız, RAD750 sınıfı bir uçuş bilgisayarında hesaplama bütçesinin tahmini %0.5'ini kullanır. Yeni nesil HPSC platformlarında (26.000 DMIPS, 1 TFLOPS) zaman-genişletilmiş planlama da onboard mümkün hale gelir."*
- *"Zamanı kaba uzayda, uzayı sabit zamanda çözüyoruz. Bu bir kısıtlama değil, doğru ayrıştırma: aydınlanma saatlerde değişir, kaya metrelerde."*
- *"Planlayıcımız beklemeyi bir karar olarak modelliyor. Bazen doğru cevap 'daha hızlı git' değil, 'dur, güneş gelsin, sonra geç'tir."*
- *"Anytime modunda bütçe dolduğunda elimizdeki rotanın optimale göre kanıtlanmış bir üst sınırı var — deterministik kesme yerine ε-suboptimal garanti."*

---

<a id="b08-s10"></a>

### [B08] Kaynaklar

- [Safe Mission-Level Path Planning for Exploration of Lunar Shadowed Regions by a Solar-Powered Rover (arXiv 2401.08558, IEEE AERO 2024)](https://arxiv.org/abs/2401.08558)
- [Risk-Aware Coverage Path Planning for Lunar Micro-Rovers Leveraging Global and Local Environmental Data (arXiv 2404.18721)](https://arxiv.org/html/2404.18721v1)
- [A Comprehensive Review of Path-Planning Algorithms for Planetary Rover Exploration (Remote Sensing 17(11), 1924)](https://www.mdpi.com/2072-4292/17/11/1924)
- [A Deep Learning Approach to Lunar Rover Global Path Planning Using Environmental Constraints and Rover Internal Resource Status (Sensors 24(3), 844)](https://www.mdpi.com/1424-8220/24/3/844)
- [Mars 2020 Autonomous Rover Navigation](https://www.semanticscholar.org/paper/MARS-2020-AUTONOMOUS-ROVER-NAVIGATION-McHenry-Abcouwer/c20138d836a7359ca83b8a35aafed060abe46b53)
- [RAD750 SpaceWire-Enabled Flight Computer for LRO (SpaceWire Conference 2007)](https://klabs.org/DEI/Processor/PowerPC/rad750/papers/spacewire_con_2007.pdf)
- [PIC64-HPSC Series — Microchip](https://www.microchip.com/en-us/products/microprocessors/64-bit-mpus/pic64-hpsc)
- [Microchip: Highest Performance 64-bit HPSC MPU Family for Autonomous Space Computing](https://www.microchip.com/en-us/about/news-releases/products/microchip-unveils-industrys-highest-performance-64-bit-hpsc-mpu)
- [The Dawn of the HPSC Era in Space Computing (white paper)](https://ww1.microchip.com/downloads/aemDocuments/documents/MPU64/ProductDocuments/SupportingCollateral/Dawn-of-HPSC-Era-in-Space-Computing-White-Paper.pdf)
- [HPSC for Lunar and Planetary Missions (NTRS 20250002070)](https://ntrs.nasa.gov/api/citations/20250002070/downloads/Powell-LPSC-2024-HPSC_for2025Mar12%2002252025_v2.pdf)
- [NASA HPSC program page](https://www.nasa.gov/game-changing-development-projects/high-performance-spaceflight-computing-hpsc)
- [Surface System Software and Rover Navigation — JPL Robotics](https://www-robotics.jpl.nasa.gov/what-we-do/flight-projects/mars-science-laboratory/surface-system-software-and-rover-navigation/)

[↑ İçindekiler](#icindekiler) · [↑ Yönlendirme tablosu](#yonlendirme)

---

<a id="belge-09"></a>

## BELGE 09 — Sektörel Projelerin Olgunluğu ve Kıyaslama

> **Belge kimliği:** `BELGE 09` (bölüm başlıklarında `[B09]` etiketiyle işaretlidir) · **Kaynak dosya:** `09_olgunluk_kiyaslama.md`  
> **Konu:** TRL, benzer projeler, LunaPath nerede duruyor  
> **Ana çıktı:** Olgunluk skorkartı + 3 aşamalı hedef  
> **Ayırt edici terimler:** `TRL`, `VIPER`, `kredibilite`, `Yutu-2`, `CADRE`, `NASA-STD-7009`, `lumped capacitance`

> **Soru:** LunaPath gerçekte hangi olgunluk seviyesinde? Benzer projeler nerede? Ne iddia edebiliriz, ne iddia edemeyiz?
>
> **Kısa cevap:** LunaPath bugün **TRL 3 civarı bir analitik kavram kanıtıdır** ve NASA'nın model kredibilite ölçeğinde (NASA-STD-7009 ailesi) **düşük–orta** bandındadır. Bu kötü bir haber değil: bir hackathon prototipi için TRL 3 iyi bir sonuçtur ve **doğru şekilde iddia edilirse güçlüdür.** Asıl risk fazla iddia etmektir. Bu belge, dürüst bir skorkart ve üç aşamalı bir yükseltme planı verir.

---

<a id="b09-s1"></a>

### [B09] 1. Doğru ölçek hangisi? TRL değil, model kredibilitesi

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

> **Bu, projenin tek cümlelik teşhisidir ve tüm yol haritasını belirler.** Validation, Input Pedigree, Uncertainty ve Robustness dörtlüsünü kapatmak = [01](#belge-01), [03](#belge-03), [07](#belge-07) belgelerini uygulamak.

#### 1.1 TRL karşılığı

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

<a id="b09-s2"></a>

### [B09] 2. Sektör manzarası — Ay yüzey otonomisi 2026 durumu

#### 2.1 Uçan/uçacak sistemler

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

#### 2.2 Akademik/araştırma manzarası — LunaPath'in gerçek rakipleri

Bunlar dergilerde/konferanslarda yayınlanmış, LunaPath ile **aynı problemi** çözen çalışmalardır. Bilmemek risk, atıf vermek güçtür.

| Çalışma | Ne yapıyor | LunaPath'e göre |
|---|---|---|
| **Lamarre, Malhotra, Kelly (IEEE AERO 2024)** — [arXiv 2401.08558](https://arxiv.org/abs/2401.08558) | Güneş enerjili rover ile PSR keşfi; **şans kısıtlı (chance-constrained)** görev-seviyesi planlama; bilinen ortalama oranlarda rastgele arızalar; **stokastik erişilebilirlik** analiziyle güvenli geçiş politikaları; Cabeus krateri / LCROSS bölgesinde çok günlük uzun menzilli sürüşler | 🔴 **LunaPath'ten ileride**: stokastik, arıza-farkında, çok günlük. LunaPath deterministik ve statik. **En yakın komşu, mutlaka atıf verilmeli** |
| **Risk-Aware Coverage Path Planning for Lunar Micro-Rovers** — [arXiv 2404.18721](https://arxiv.org/html/2404.18721v1) | Global (PDS DEM, offline maliyet) + local (VLP-16 LiDAR, miyopik algılama) hibrit; `mc = α(mc_static + mc_visited·V_i) + β·mc_DEM`; HDL graph SLAM; **gerçek arazi testi** (kaplama %80 killi / %65 kumlu zeminde, lokalizasyon MAE 0.41 / 0.32 m); CLOVER 7 kg mikro-rover, ROS1 | 🔴 **LunaPath'ten ileride**: gerçek donanım + saha testi. LunaPath yalnızca simülasyon |
| **Deep Learning for Lunar Rover Global Path Planning** — [Sensors 24(3), 844](https://www.mdpi.com/1424-8220/24/3/844) | Statik (eğim), zaman-değişken (ısı akısı, aydınlanma) ve yola-bağlı (termal + güç durumu) kısıtları grid'e ceza fonksiyonu olarak gömüyor; **rover'ın beklemesine izin veriyor**; RL ile kaynak-kısıtlı en kısa yol | 🟡 **Kısmen ileride**: zaman ekseni ve bekleme kararı var. LunaPath'te ikisi de yok ([08](#belge-08) §3.3) |
| **Comprehensive Review of Path-Planning Algorithms for Planetary Rovers** — [Remote Sensing 17(11), 1924](https://www.mdpi.com/2072-4292/17/11/1924) | Alanın 2025 taksonomisi; arazi değişkenliği, engeller, **aydınlanma ve sıcaklık dalgalanmaları** vurgusu; sabah/akşam ve yüksek enlem aydınlanmasının güç verimliliğine etkisi | 📚 **Konumlandırma referansı** — LunaPath'i literatür haritasına yerleştirmek için |
| **Learning-Based End-to-End Path Planning for Lunar Rovers with Safety Constraints** — [PMC7866010](https://pmc.ncbi.nlm.nih.gov/articles/PMC7866010/) | Uçtan uca öğrenilmiş planlama | 🟡 Farklı yaklaşım; LunaPath'in açıklanabilirlik avantajı burada değerli |
| **Deep Probabilistic Traversability with Test-time Adaptation** — [arXiv 2409.00641](https://arxiv.org/pdf/2409.00641) | Belirsizlik-farkında gezegen rover navigasyonu | 🔴 Belirsizlik modellemesinde ileride |

#### 2.3 Dürüst konumlandırma sonucu

| İddia | Savunulabilir mi? |
|---|---|
| "Ay kutbu için termal-güvenlik odaklı çok kriterli rota planlama prototipi geliştirdik" | ✅ **Evet** |
| "Fizik-temelli, peer-review edilmiş formüllerle çalışan bir maliyet modeli kurduk ve implementasyonunu doğrulama tablolarıyla test ettik" | ✅ **Evet** |
| "4 farklı misyon profilinin trade-off'larını sayısal ve görsel olarak karşılaştırıyoruz" | ✅ **Evet** — bu gerçek ve özgün bir katkı |
| "Aynı senaryoyu farklı **rover platformlarında** (VIPER, Yutu-2, LUVMI-M, LPR-1) koşup platform duyarlılığını gösteriyoruz" | ✅ **Evet** — `constants.py:14`'teki 4 profilli rover kataloğu. **Referans belgede yazmayan, kodda var olan bir üstünlük; mutlaka öne çıkarın** |
| "Gerçek NASA verisi kullanıyoruz" | 🟡 **Kısmen** — DEM gerçek, termal ve gölge sentetik. Düzeltilene kadar bu cümleyi kurmayın |
| "Bu alanda ilk/özgün" | ❌ **Hayır** — §2.2'deki çalışmalar var |
| "Otonom navigasyon sistemi" | ❌ **Hayır** — engel kaçınma yok ([05](#belge-05)) |
| "Rover üzerinde çalışabilir" | 🟡 Hesap bütçesi analizi yapıldıktan sonra **evet** ([08](#belge-08) §4.3) |
| "Görev öncesi planlama ve karar destek aracı" | ✅ **En doğru konumlandırma** |

`ay_termal_navigasyon_proje_dokumani.md` §6.1'de "projenin tam konumlandırması" açık soru olarak bırakılmıştı. **Karar önerisi: "görev öncesi planlama + karar destek aracı"**, rover-üzeri otonomi modülü değil. Gerekçeler:

1. Mevcut mimari (offline grid ön-işleme + REST API + web arayüzü) tam olarak bunu destekliyor
2. Pragyan gibi gerçek bir Ay misyonu bugün böyle çalışıyor → **operasyonel ilgi gerçek**
3. Otonomi iddiası, olmayan bileşenleri (perception, yerel planlayıcı, gerçek zamanlı kısıtlar) görünür kılar
4. Karar destek iddiası, olan bileşenleri (çok kriterli karşılaştırma, açıklanabilirlik, senaryo analizi) öne çıkarır

---

<a id="b09-s3"></a>

### [B09] 3. Olgunluk skorkartı

10 boyut × 5 puan. **Bugün** ve **P0+P1 sonrası hedef**.

| # | Boyut | Bugün | Kanıt / gerekçe | Hedef | Nasıl |
|---|---|---|---|---|---|
| 1 | **Veri gerçekliği** | 🔴 **2/5** | 7 katmandan 1'i ölçüm (DEM); termal + gölge sentetik; tüm katmanlar tek girdiden türüyor | 🟢 **4/5** | [01](#belge-01), [07](#belge-07) P0/P1 |
| 2 | **Fizik modeli** | 🟡 **3/5** | Enerji ve gölge sabitleri **tutarlı ve türetilebilir** (iyi); **4 rover profilli parametrik katalog** (LPR-1, LUVMI-M, VIPER, Yutu-2) — belgede yok, kodda var, güçlü; ama T_yüzey→T_iç sabit ofset, `τ` türetilmemiş | 🟢 **4/5** | [07](#belge-07) §3 lumped capacitance |
| 3 | **Verification** (kod doğruluğu) | 🟢 **4/5** | 9 test dosyası, doğrulama tabloları, matematik dondurulmuş — **hackathon için üstün** | 🟢 **5/5** | Heuristic admissibility testi ([08](#belge-08) §6.1) |
| 4 | **Validation** (model gerçekliği) | 🔴 **1/5** | Hiçbir katman/çıktı ölçümle karşılaştırılmadı | 🟢 **4/5** | Ablasyon A/B/C/D ([03](#belge-03) §4.2) |
| 5 | **Belirsizlik yönetimi** | 🔴 **1/5** | Hard-limit'ler noktasal, hata bandı yok, hassasiyet analizi yok | 🟡 **3/5** | Belirsizlik bandı ([01](#belge-01) §3.4), Monte Carlo (100 clone) |
| 6 | **Hesaplama olgunluğu** | 🟡 **2/5** | `computation_time_ms` ölçülüyor ama benchmark/bütçe analizi yok, ön-hesaplama yapılmıyor | 🟢 **4/5** | [08](#belge-08) P0/P1 |
| 7 | **Zaman / dinamik** | 🔴 **1/5** | Statik snapshot; `f_shadow(H)` girdisi tanımsız; bekleme kararı yok | 🟡 **3/5** | L2 illumination_frac, ardından zaman-genişletilmiş graf |
| 8 | **Otonomi kapsamı** | 🟡 **2/5** | Global planlama var; yerel katman, perception, replanning yok | 🟡 **3/5** | Koridor sözleşmesi + replan tetikleyicileri ([05](#belge-05)) |
| 9 | **Açıklanabilirlik** | 🟢 **4/5** | Analitik maliyet fonksiyonu, `/api/cell-telemetry`, profil karşılaştırması — **projenin en güçlü yanı** | 🟢 **5/5** | `CostMap.explain()` ([04](#belge-04) §5.1) |
| 10 | **Belgeleme / tekrar-üretilebilirlik** | 🟡 **3/5** | Kapsamlı Türkçe dokümanlar (iyi); veri sürümleme, lisans kaydı, determinizm testi yok | 🟢 **4/5** | [01](#belge-01) §3.2, §3.7 |
| | **TOPLAM** | **23/50** | | **39/50** | |

#### 3.1 Skorkartın söylediği şey

- **Güçlü yanlar (koru):** verification, açıklanabilirlik, belgeleme. Bunlar öğrenci projelerinde nadirdir ve LunaPath'in gerçek sermayesidir.
- **Kritik zayıflıklar (kapat):** validation, belirsizlik, veri gerçekliği, zaman. Dördü de aynı kökten geliyor: **gerçek veri yok.**
- **Bilinçli kapsam dışı (belgele):** otonomi kapsamı, yerel katman.

**En verimli hamle:** Gerçek veriyi ekle (Diviner + illumination) → boyut 1, 4, 5, 7 aynı anda yükselir. **Tek müdahale, dört boyut.** Bu, yol haritasının neden [07](#belge-07) ile başlaması gerektiğinin nedenidir.

---

<a id="b09-s4"></a>

### [B09] 4. Üç aşamalı yükseltme planı

#### Aşama I — "Dürüst ve Doğrulanmış" (1–2 hafta, TRL 3 → 4 eşiği)

| # | İş | Belge | Çıktı |
|---|---|---|---|
| 1 | Kutup Diviner ürününü doğrula ve indir | [07](#belge-07) §7 P0 | `thermal_grid_diviner.npy` |
| 2 | LOLA illumination + PSR indir | [01](#belge-01) §5 | `illumination_frac.npy`, `psr_mask.npy` |
| 3 | `metadata.json` v2 + `physical_validity` | [01](#belge-01) §3.1 | Provenance kaydı |
| 4 | Hizalama + şema doğrulama kapıları (CI'da kırıyor) | [01](#belge-01) §3.3, §3.5 | `align.py`, `schemas.py` |
| 5 | **A/B/C/D ablasyon raporu** | [03](#belge-03) §4.2 | `ablation_report.md` — **en önemli tek çıktı** |
| 6 | `T_max_base` düzeltmesi, `f_thermal` ayrıştırma | [07](#belge-07) §7 P0 | |
| 7 | Benchmark tablosu + heuristic admissibility testi | [08](#belge-08) §6 | `planner_benchmark.md` |
| 8 | Hesaplama bütçesi analizi (RAD750/HPSC) | [08](#belge-08) §4.3 | Bütçe tablosu |
| 9 | Konumlandırma kararı + iddia denetimi | Bu belge §2.3 | README/sunum güncellemesi |
| 10 | `DATA_LICENSES.md`, determinizm testi, pin'ler | [01](#belge-01), [04](#belge-04) | |

**Aşama I çıktısı:** *"Gerçek NASA ölçüm verisiyle çalışan, kendi sentetik baseline'ının hatasını niceleyen, hesaplama bütçesi analiz edilmiş bir çok kriterli rota planlayıcı."* Bu, TRL 4 iddiası için gereken minimum kanıt setidir.

#### Aşama II — "Fiziksel ve Dinamik" (3–4 hafta, TRL 4)

| # | İş | Belge |
|---|---|---|
| 11 | Lumped capacitance termal model, `τ = C/(hA)` | [07](#belge-07) §3 |
| 12 | Belirsizlik bandı + üçlü traversability | [01](#belge-01) §3.4 |
| 13 | Maliyet ön-hesaplama (8 yönlü dizi) + float32 | [08](#belge-08) §2 |
| 14 | SVF (gökyüzü görüş faktörü) + **SEP senaryosu** | [06](#belge-06) §2, §3 |
| 15 | SfS 5 m ürünü + `f_roughness` + koridor rafinasyonu | [02](#belge-02) §2.5 |
| 16 | `Corridor` sözleşmesi + replan tetikleyicileri + safe haven erişilebilirliği | [05](#belge-05) §4 |
| 17 | Slip düzeltmesi | [05](#belge-05) §3.1 |
| 18 | SpiceyPy + L2 zaman modeli (illumination_frac) | [04](#belge-04) §2.1, [07](#belge-07) §4.2 |
| 19 | `CostMap` + `explain()` refaktörü | [04](#belge-04) §5.1 |
| 20 | Bileşen bazlı `HealthState` | [06](#belge-06) §5 |

#### Aşama III — "Zaman-Uzay Planlayıcı" (6–10 hafta, TRL 4→5 yolu)

| # | İş | Belge |
|---|---|---|
| 21 | Zaman-genişletilmiş graf + **bekleme kenarı** | [08](#belge-08) §3.3 |
| 22 | Üç seviyeli hiyerarşi (A/B/C) | [08](#belge-08) §3.2 |
| 23 | Anytime A* + suboptimality bound | [08](#belge-08) §5 |
| 24 | 100-clone Monte Carlo rota kararlılığı | [01](#belge-01) §2.1 |
| 25 | heat1d ile rejim-tabanlı yüzey sıcaklığı | [07](#belge-07) §4.3 |
| 26 | Kaya tespiti (Diviner `ra` + NAC/YOLO) | [02](#belge-02) §2.3 |
| 27 | Çok bölgeli senaryo kütüphanesi (Shackleton, Nobile, de Gerlache, Malapert) | [01](#belge-01) §5 |
| 28 | Literatür karşılaştırması: Lamarre vd. senaryosunu tekrarla | Bu belge §2.2 |

**Madde 28 özellikle değerli:** Lamarre vd. Cabeus krateri / LCROSS bölgesinde çok günlük sürüşler koşuyor. Aynı bölgede aynı senaryoyu koşup sonuçları karşılaştırmak, LunaPath'i literatüre **ölçülebilir biçimde** bağlar. Bu, akademik yayın için gereken en önemli adımdır.

---

<a id="b09-s5"></a>

### [B09] 5. Kıyaslama özeti — tek tabloda

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

<a id="b09-s6"></a>

### [B09] 6. Sunum/rapor için hazır çerçeve

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

<a id="b09-s7"></a>

### [B09] 7. Kabul kriterleri

- [ ] Konumlandırma kararı verilmiş ve tüm belgelerde tutarlı ("görev öncesi planlama / karar destek")
- [ ] TRL beyanı ve NASA-STD-7009 tarzı kredibilite tablosu belgede
- [ ] Skorkart doldurulmuş; "bugün" ve "hedef" kolonları güncel tutulan bir yaşayan belge
- [ ] §2.3 iddia denetim tablosundaki ❌ satırları hiçbir sunumda/README'de geçmiyor
- [ ] §2.2'deki en az 4 çalışmaya atıf verilmiş
- [ ] Aşama I'in 10 maddesi tamamlanmış → TRL 4 iddiası için kanıt seti hazır

---

<a id="b09-s8"></a>

### [B09] Kaynaklar

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

[↑ İçindekiler](#icindekiler) · [↑ Yönlendirme tablosu](#yonlendirme)

---

<a id="belge-10"></a>

## BELGE 10 — Sektörel Ay Rota Planlama Projeleri Envanteri

> **Belge kimliği:** `BELGE 10` (bölüm başlıklarında `[B10]` etiketiyle işaretlidir) · **Kaynak dosya:** `10_sektorel_projeler_envanteri.md`  
> **Konu:** Gerçek projeler: GitHub depoları, NASA/ESA araçları, şirketler, akademik planlayıcılar  
> **Ana çıktı:** Kim-ne-kullandı envanteri + ödünç alınacak 10 şey + atıf listesi  
> **Ayırt edici terimler:** `ROS`, `SLAM`, `MAPP`, `xGDS`, `VIPER`, `MoonRanger`, `MMGIS`, `Moon Trek`, `LUVMI`, `lunar_planner`

> **Amaç:** Şu anda gerçekten var olan, kullanılan veya yayınlanmış Ay yüzeyi rota/traverse planlama projelerini tek yerde toplamak. Her kayıt için: **kim yaptı, ne kullandı, ne yaptı, kod açık mı, kaynak nerede.**
>
> **Nasıl okunur:** Her kayıtta `🔓` = kod/veri açık, `🔒` = kapalı/kurum içi, `📄` = yayın var kod yok. `⭐` = LunaPath'in doğrudan ödünç alabileceği/karşılaştırması gereken kayıt.
>
> **Doğruluk notu:** Aşağıdaki bilgiler açık web kaynaklarından derlendi. Depo yıldız sayıları, sürümler ve misyon tarihleri değişkendir; **kullanmadan önce bağlantıdan teyit edin.** Fetch edilemeyen (403/paywall) kaynaklarda ayrıntı seviyesi düşüktür ve bu belirtilmiştir.
>
> **Tarih:** 10 Ağustos 2026

---

<a id="b10-s1"></a>

### [B10] Özet: manzaranın şekli

Araştırmanın en önemli çıkarımı şu: **Ay rota planlama alanı üç ayrı dünyaya bölünmüş ve bu dünyalar birbirini pek okumuyor.**

| Dünya | Kim | Ne yapıyor | Kod |
|---|---|---|---|
| **1. Kurum operasyon araçları** | NASA JPL/Ames, ESA | Gerçek misyonları planlıyor; olgun, ağır, GIS-merkezli | Kısmen açık (MMGIS, xGDS) |
| **2. Akademik planlayıcılar** | Üniversiteler (ETH, CMU, Toronto, Çin) | Algoritma yeniliği; çok kriterli, zaman-farkında | Nadiren açık |
| **3. Ticari rover şirketleri** | Lunar Outpost, Astrobotic, ispace, Astrolab | Uçan donanım + kapalı otonomi yığını | Kapalı |

**LunaPath'in konumu:** 2. dünyada (akademik planlayıcı), ama 1. dünyanın araçlarını (MMGIS/Moon Trek) hiç kullanmıyor ve 2. dünyadaki en yakın rakiplerini ([09](#belge-09) §2.2) referans almıyor. Bu envanterin işi o boşluğu kapatmak.

---

<a id="b10-s2"></a>

### [B10] A. Açık kaynak, doğrudan Ay rota planlama

#### A1. ⭐🔓 `leggedrobotics/lunar_planner` — ETH Zürich Robotic Systems Lab

**LunaPath'e en yakın açık kaynak proje. Mutlaka incelenmeli.**

| | |
|---|---|
| **Kim** | ETH Zürich, Robotic Systems Lab (Julia Richter vd.) |
| **Ne** | Gezegen araştırmacıları için Ay misyon planlamasını basitleştiren araç: **rota planlama** + **rota analizi** |
| **Yaklaşım** | Dört bacaklı (quadruped) robot için **çok amaçlı (multi-objective) global rota planlama optimizasyonu**; enerji verimliliği ve aydınlanma dikkate alınıyor |
| **Veri** | 3 hazır bölge: Aristarchus Irregular Mare Patch, Aristarchus Central Peak, Herodotus Mons; ek haritalar wiki'den indirilebilir |
| **Stack** | Python 3.8+, **GDAL**, GUI; Linux/macOS/Windows; Ubuntu ve Windows için hazır ikili dosyalar (Git LFS) |
| **Lisans** | **MIT** |
| **Yayın** | Richter vd., *Multi-Objective Global Path Planning for Lunar Exploration With a Quadruped Robot*, iSpaRo 2024 |
| **Kaynak** | [GitHub](https://github.com/leggedrobotics/lunar_planner) · [arXiv 2406.16376](https://arxiv.org/html/2406.16376v1) |

**LunaPath ile karşılaştırma:**

| | LunaPath | lunar_planner |
|---|---|---|
| Çok kriterli maliyet | ✅ 4 kriter (eğim/enerji/gölge/termal) | ✅ Çok amaçlı optimizasyon |
| Termal kriter | ✅ (sentetik) | ❌ |
| Aydınlanma | 🟡 Elevasyon proxy | ✅ |
| GUI | ✅ Web (React) | ✅ Masaüstü |
| Rota analizi | 🟡 Metrikler | ✅ Ayrı analiz aracı |
| Platform | Tekerlekli rover | Dört bacaklı robot |
| Lisans | MIT | MIT |

> **Aksiyon:** Bu depoyu klonlayıp `path analysis tool` kısmını inceleyin. LunaPath'in metrik seti ile karşılaştırıp eksik metrikleri alın. **Termal kriter LunaPath'in gerçek farkı** — bunu net söyleyebilmek için rakibin ne yapmadığını bilmek gerekir.

#### A2. ⭐🔓 `Stanford-NavLab/lunar_autonomy_challenge` — Stanford NavLab

**Lunar Autonomy Challenge birincisi. Uçtan uca çalışan bir Ay otonomi yığını, açık kaynak.**

| | |
|---|---|
| **Kim** | Stanford NavLab |
| **Ne** | NASA/JHU-APL Lunar Autonomy Challenge için tam yığın: lokalizasyon + haritalama + planlama |
| **Lokalizasyon** | Stereo görsel odometri + **pose graph SLAM**; **SuperPoint** (keypoint) + **LightGlue** (eşleme); GTSAM ile Levenberg-Marquardt, loop closure |
| **Haritalama** | Semantik etiketli 3D landmark'lardan iki harita: **geometrik harita** (180×180 grid, hücre yüksekliği = z medyanı) ve **kaya haritası** (majority voting) |
| **Planlama** | **Global:** lander etrafında yapılandırılmış spiral (iç içe 3×3 grid hücrelerinin çevresi). **Lokal:** sabit-eğrilikli **yay (arc) örnekleme**, hedef waypoint'e en yakın ve engelsiz yayı seç |
| **Segmentasyon** | **U-Net++**, simülatör görüntüleriyle fine-tune |
| **Sensör** | 8 monokrom kamera (ön/arka stereo çift, yan, kol üstü), her biri LED ışıklı + IMU |
| **Aydınlanma stratejisi** | Öğrenilmiş feature eşleme; SuperPoint+LightGlue **aşırı aydınlanma değişimine dayanıklı** olduğu için seçildi |
| **Sonuç** | Santimetre seviyesi lokalizasyon: **RMSE 0.038–0.061 m**; yarışma **1. sırası** |
| **Kaynak** | [GitHub](https://github.com/Stanford-NavLab/lunar_autonomy_challenge) · [arXiv 2603.17232](https://arxiv.org/html/2603.17232v1) |

> **Aksiyon:** LunaPath'in **eksik olduğu yerin** ([05](#belge-05) Katman 2) referans implementasyonu bu. Yerel yay-örnekleme planlayıcı ve LED'li kamera yaklaşımı, "kutupta perception nasıl yapılır" sorusunun somut cevabı. Kod okumak, sıfırdan yazmaktan hızlı.

#### A3. 🔓 `NASA-AMMOS/MMGIS` — NASA JPL AMMOS

| | |
|---|---|
| **Kim** | NASA JPL, AMMOS (Advanced Multi-Mission Operations System) |
| **Ne** | **Multi-Mission Geographic Information System** — Dünya, Ay ve gezegen görselleştirme, araştırma, bilim, **planlama ve operasyon** için web tabanlı haritalama ve mekânsal veri altyapısı |
| **Kullanım** | Mars'ın tam ölçekli haritalanması için üretildi; Perseverance, Ingenuity, Curiosity rota izleri önyüklü demo |
| **Neden önemli** | LunaPath'in frontend'inin yeniden icat etmeye çalıştığı şeyin **gerçek misyon-sınıfı** hali |
| **Kaynak** | [GitHub](https://github.com/NASA-AMMOS/MMGIS) |

> **Aksiyon:** LunaPath'i MMGIS'e **rakip** değil, **eklenti** olarak konumlandırma seçeneğini değerlendirin. LunaPath backend'i bir planlama servisi olarak kalıp, görselleştirmeyi MMGIS'e bırakmak hem eforu düşürür hem "misyon araç zincirine entegre" iddiası verir. Bu, [09](#belge-09)'daki *Use History* faktörünü yükseltir.

#### A4. 🔓 `jasmeet0915/artemis_mission_simulator`

| | |
|---|---|
| **Ne** | ROS 2 tabanlı, **simülatör-agnostik Ay güney kutbu dijital ikizi**; Artemis misyonlarını simüle etmek için |
| **Amaç** | Rover, drone, humanoid ve diğer Ay yüzey sistemleri için plug-and-play test alanı |
| **Kaynak** | [GitHub](https://github.com/jasmeet0915/artemis_mission_simulator) · [Open Robotics Discourse duyurusu](https://discourse.openrobotics.org/t/introducing-artemis-mission-simulator-attempting-to-simulate-nasas-artemis-missions-on-moon-before-they-actually-go/55387) |

#### A5. 🔓 Küçük ölçekli / öğrenci depoları (düşük olgunluk, referans amaçlı)

| Depo | Ne | Not |
|---|---|---|
| [`rakshanda33/Lunar-Navigation-Path-Planner`](https://github.com/rakshanda33/Lunar-Navigation-Path-Planner) | Güney kutbunda güneş enerjili rover için 100 m+ güvenli rota; **Chandrayaan görüntüsü**; engelden kaçınma + 10+ bilimsel durak; arazi ve güneş maruziyeti optimizasyonu | LunaPath'e konsept olarak yakın, ölçek çok küçük |
| [`alessioborgi/MoonBot-Navigation`](https://github.com/alessioborgi/MoonBot-Navigation) | C++; **Dijkstra** rota planlama + SLAM + engel tespiti + gripper | Robotik odaklı |
| [`knamatame0729/ORBSLAM3-Semantic-Mapping`](https://github.com/knamatame0729/ORBSLAM3-Semantic-Mapping) | Semantik segmentasyon + ORB-SLAM3 → rover tabanlı **Ay arazi haritalama**, 3D semantik harita | Perception tarafı |
| `chandrabhraman/lunar-rover-path-planning` | MATLAB tabanlı Ay rover rota planlama | [MATLAB Central](https://www.mathworks.com/matlabcentral/fileexchange/128759-lunar-rover-path-planning) · *ayrıntılar doğrulanmadı* |
| `iamLakshikaTanwar/bah2026-ps8` | Chandrayaan-2 radar ile yüzey altı su-buzu + **rota planlama, DEM, enerji-farkında rover traverse planlama** | Hackathon projesi (BAH 2026) |

> **Dürüst değerlendirme:** A5'teki depolar LunaPath'ten daha olgun değil. Bunları **rakip** değil, "bu problemin popüler olduğunun kanıtı" olarak görün. LunaPath'in gerçek rakipleri A1, A2 ve D bölümündeki yayınlardır.

---

<a id="b10-s3"></a>

### [B10] B. Kurum araçları (NASA / ESA)

#### B1. ⭐🔓 NASA Moon Trek (Solar System Treks Project, JPL)

| | |
|---|---|
| **Kim** | NASA JPL, Solar System Treks Project (SSTP) |
| **Ne** | Tarayıcı tabanlı gezegen veri görselleştirme ve analiz portalı |
| **Araçlar** | **Görüş hattı (line of sight) analizi**, **traverse rota planlama**, **3D traverse rota görselleştirme** |
| **Hedef** | *"Moon Trek'in en yeni araçları Artemis dönemi Ay misyon planlaması ve keşfi için hedeflenmiştir"* |
| **Kaynak** | [trek.nasa.gov/moon](https://trek.nasa.gov/moon/) · [EGU 2023 bildirisi (ADS)](https://ui.adsabs.harvard.edu/abs/2023EGUGA..25..969L/abstract) |

> **Bu, LunaPath'in en doğrudan kurumsal karşılığıdır ve NASA tarafından ücretsiz sunulmaktadır.** Moon Trek'te traverse planlama zaten var. **LunaPath'in ayrışması gereken yer tam burası:** Moon Trek geometrik/görsel planlama yapar; LunaPath **fizik-temelli çok kriterli maliyet + rover donanım sağlığı** getirir. Sunumda bu karşılaştırmayı **kendiniz** yapın — jüri yapmadan önce.

#### B2. 🔓 NASA Ames xGDS — Exploration Ground Data Systems

| | |
|---|---|
| **Kim** | NASA Ames Research Center, Intelligent Robotics Group (IRG) |
| **Ne** | NASA analog saha deneylerini destekleyen yazılım araçları; iki ana ürün: **xGDS Web Tools** ve **VERVE** (Visual Environment for Remote Virtual Exploration) |
| **Yetenek** | Gözlem notları, enstrüman verisi, fotoğraf, video, örneklerin zaman ve haritalanmış konumunu senkronize ederek hızlı bilimsel karar desteği |
| **⭐ Kritik detay** | *"Araçlar, süre ve kat edilen mesafeyi tahmin etmek için **basit bir araç yetenek modeli** (ör. hız, veri toplama aktiviteleri) içeren bir **traverse planlayıcı** sağlar"* |
| **Kaynak** | [NASA Ames xGDS](https://ti.arc.nasa.gov/tech/asr/groups/intelligent-robotics/xgds/) · [NTRS Overview](https://ntrs.nasa.gov/api/citations/20190025706/downloads/20190025706.pdf) · [Acta Astronautica 90:268](https://www.sciencedirect.com/science/article/pii/S0094576512000057) |

> **Aksiyon:** xGDS'in traverse planlayıcısı **"basit bir araç yetenek modeli"** kullanıyor. LunaPath'in modeli bundan **çok daha zengin** (fizik-temelli enerji, termal, log-barrier). Bu, LunaPath'in katkısını konumlandırmak için mükemmel bir karşılaştırma noktasıdır: *"Mevcut analog planlama araçları basit hız/mesafe modelleri kullanıyor; biz fizik-temelli çok kriterli bir maliyet modeli getiriyoruz."*

#### B3. 🔒 JPL RSVP — Robot Sequencing and Visualization Program

| | |
|---|---|
| **Kim** | NASA JPL |
| **Ne** | Mars rover hareketlerinin **tamamının** planlandığı operasyon yazılımı: yüzeyde sürüş + karmaşık robotik kol/turret etkileşimleri |
| **Miras** | Mars Pathfinder → MER → MSL → Mars 2020 |
| **M2020 eklentileri** | **MobSketch**, **ArmSketch** (sekans otomasyonu), **SSim** (flight-software-in-the-loop simülasyon), hedef değerlendirme ve rafinasyon |
| **Kod** | 🔒 Kapalı |
| **Kaynak** | [RSVP for MSL](https://www-robotics.jpl.nasa.gov/what-we-do/flight-projects/mars-science-laboratory/rsvp-msl/) · [RSVP Mars 2020](https://www-robotics.jpl.nasa.gov/what-we-do/flight-projects/mars-2020-rover/rsvp-mars-2020/) |

> **Neden önemli:** LunaPath'in "operatör karar desteği" konumlandırması için **altın standart referans**. RSVP'nin varlığı, insan-döngüde rota planlama araçlarının gerçek ve vazgeçilmez olduğunu kanıtlar ([09](#belge-09) §2.3).

#### B4. ⭐ NASA VIPER'ın yer yazılımı — **açık kaynak yığın kullanıyor**

Bu, envanterin en çarpıcı bulgularından biri:

| | |
|---|---|
| **Misyon** | VIPER (Volatiles Investigating Polar Exploration Rover), Ay güney kutbu; iptal (2024) → diriltildi (2025), Blue Moon MK1 ile 2027 hedefi |
| **Yer araçları** | *"VIPER'ın Dünya tabanlı operasyon araçlarının, hesaplama modüllerinin ve yüksek doğruluklu simülasyonlarının çoğu **ROS 2 ve Gazebo** tabanlıdır"* |
| **Telemetri/analiz** | **NASA Open MCT** (web tabanlı telemetri görüntüleme) VIPER dahil misyonlarda kullanılıyor |
| **Alıntı** | *"VIPER yerde ROS kullanıyor — bu kadar çok insanın bu kadar düzenli kullandığı bir şey"* |
| **Kaynak** | [MIT Technology Review: NASA's next lunar rover will run open-source software](https://www.technologyreview.com/2021/04/12/1022420/nasa-lunar-rover-viper-open-source-software/) |

> **LunaPath için stratejik sonuç:** Ay kutup misyonunun **kendi yer planlama araçları ROS 2 + Gazebo üzerine kurulu.** Yani LunaPath'in [04](#belge-04)'te "ROS 2/Nav2 desenini ödünç al" tavsiyesi, sadece iyi mühendislik değil — **hedef misyonun fiili standardıyla hizalanmak** anlamına geliyor. Bunu sunumda söylemek konumlandırmayı ciddi biçimde güçlendirir.

#### B5. 🔓 Space ROS — NASA + Blue Origin + Open Robotics

| | |
|---|---|
| **Ne** | ROS 2'den türetilmiş, **güvenlik-kritik uzay robotiği** için sertleştirilmiş açık kaynak çatı; ROS 2 API'sine uyumlu, platform/proje bağımsız |
| **Kim** | NASA, Open Robotics, Blue Origin ortaklığı (Blue Origin–NASA anlaşmasıyla başladı) |
| **Demolar** | Canadarm2, Curiosity rover, **Ay arazisi** |
| **Kaynak** | [github.com/space-ros](https://github.com/space-ros) · [space.ros.org](https://space.ros.org/pages/faq.html) · [AIAA SciTech 2023](https://arc.aiaa.org/doi/10.2514/6.2023-2709) · [NTRS PDF](https://ntrs.nasa.gov/api/citations/20220017761/downloads/Space_ROS_SciTech.pdf) |

#### B6. 📄 ESA ADE (OG10) — Autonomous Decision Making in Very Long Traverses

| | |
|---|---|
| **Kim** | H2020, GMV koordinasyonlu; DFKI Bremen, Oxford vd. (ESA Space Robotics Technologies SRC kümesi) |
| **Hedef** | Gezegen rover keşfi için kapsamlı otonom sistem: **sol başına ≥1 km** traverse, bilimsel veri toplamayı maksimize etme, nominal ve beklenmedik durumlarda uygun kararlar, her an güvenliği sağlama |
| **Ana bileşen** | **ADAM** (Autonomous Decision Making Module) — ilginç özellik bulunduğunda veya **çevresel tehlike tanındığında** nominal planı otonom ve güvenli şekilde değiştirir |
| **Kaynak** | [h2020-ade.gmv.com](https://h2020-ade.gmv.com/) · [DFKI proje sayfası](https://robotik.dfki-bremen.de/en/research/projects/ade-og10.html) · [i-SAIRAS 2020 bildirisi](https://www.hou.usra.edu/meetings/isairas2020fullpapers/pdf/5033.pdf) · [CORDIS 821988](https://cordis.europa.eu/project/id/821988) |

> **Aksiyon:** ADAM'ın "tehlike tanındığında planı değiştir" mantığı, LunaPath'in [05](#belge-05) §4.3'teki **replanning tetikleyicileri** tablosunun kurumsal karşılığıdır. i-SAIRAS bildirisi ücretsiz PDF — tetikleyici taksonomisini oradan alıp LunaPath'e uyarlayın.

#### B7. 📄 ESA EMRS — European Moon Rover System

| | |
|---|---|
| **Ne** | Gelecek karmaşık Ay misyonları için modüler, çok amaçlı rover |
| **Durum** | **Breadboard + analog saha test kampanyası** yapıldı |
| **Neden önemli** | TRL 3 → 4/5 yolculuğunun somut örneği ([09](#belge-09)) |
| **Kaynak** | [arXiv 2411.13978](https://arxiv.org/pdf/2411.13978) |

#### B8. 🔒/📄 Space Applications Services — LUVMI / LUVMI-X / LUVMI-M

| | |
|---|---|
| **Kim** | Space Applications Services (BE), ESA fonlu + ticari |
| **Ne** | Düşük kütleli, modüler, genişletilebilir Ay rover platform ailesi; yük taşıma ve mobilite |
| **Otonomi** | **Tele-operasyonlu, opsiyonel otonom modlar** — daha hızlı traverse ve **PSR'a girerken güvenlik** için |
| **⭐ LunaPath bağlantısı** | **`LUVMI-M`, LunaPath'in rover kataloğunda mevcut** (`constants.py`) — yani projeniz zaten gerçek bir Avrupa rover platformunu parametrize ediyor. Bunu vurgulayın. |
| **Kaynak** | [spaceapplications.com/products/lunar-rover-luvmi-x](https://www.spaceapplications.com/products/lunar-rover-luvmi-x) · [Yeni misyon duyuruları](https://www.spaceapplications.com/news/space-applications-services-expands-lunar-rover-development-with-new-commercial-and-esa-funded-missions) |

---

<a id="b10-s4"></a>

### [B10] C. Ticari şirket projeleri (uçmuş / uçacak)

Bu bölümdeki otonomi yazılımlarının hiçbiri açık kaynak değil. Değeri: **hangi yeteneklerin gerçekten uçtuğunu** göstermesi.

#### C1. ⭐ Lunar Outpost — MAPP (Mobile Autonomous Prospecting Platform)

| | |
|---|---|
| **Kim** | Lunar Outpost (US) |
| **Misyon** | **Lunar Voyage 1**, Mart 2025, Intuitive Machines IM-2 lander ile |
| **Sonuç** | **İlk ABD ticari rover'ı Ay yüzeyine ulaştı**; ancak lander yan yattığı için rover **dışarı çıkamadı** |
| **⭐ Kritik detay** | Buna rağmen alt sistemler **TRL 9** doğrulaması aldı: **navigasyon bilgisayarı**, **otonom termal kontrol sistemi**, **stereo kameralar**, güç yönetimi. *"Ana otonomi sistemleri ve yazılımı TRL 9'a ulaştı."* |
| **İş modeli** | "Rover-as-a-service" — tek seferlik misyon değil, müşteri için veri üretimi; NASA ve DoD ilgisi |
| **Kaynak** | [NASASpaceflight: Lunar Outpost MAPP](https://www.nasaspaceflight.com/2025/12/lunar-outpost-mapp/) · [MAPP ürün sayfası](https://www.lunaroutpost.com/mapp) · [Lunar Voyage 1 Update](https://www.lunaroutpost.com/post/lunar-voyage-1-update) · [Space.com misyon kontrol](https://www.space.com/astronomy/moon/we-are-ready-to-drive-take-a-look-inside-lunar-outposts-moon-rover-mission-control-photos) |

> **LunaPath için en anlamlı kayıt bu.** "Otonom **termal kontrol** sistemi" TRL 9 aldı — yani **termal yönetim, ticari Ay rover'larında zaten birinci sınıf bir otonomi problemi.** LunaPath'in termal odağı moda değil, sektörün gerçek gündemi. Bu cümleyi sunuma koyun.

#### C2. Astrobotic + CMU — MoonRanger

| | |
|---|---|
| **Kim** | Carnegie Mellon Üniversitesi + Astrobotic (+ NASA Ames işbirliği); teknik liderlik: William "Red" Whittaker |
| **Ne** | Bavul boyutunda otonom Ay rover'ı; NASA LSITP kapsamında **5.6 M$** sözleşme |
| **Otonomi** | Ay yüzeyinin **3D haritalarını** oluşturuyor; **uzun menzilli ve iletişim-kesintili (communication-denied) keşif** gösterimi; **stereo kamera ile görsel odometri + güneş sensörü** ile bağımsız yönelim |
| **⭐ LunaPath bağlantısı** | LPR-1 referans rover'ı **VIPER ve MoonRanger'dan türetildi** (`lunapath_referans_belgesi_2.md` §2.1) |
| **Kaynak** | [CMU RI: MoonRanger Passes Key NASA Review](https://www.ri.cmu.edu/moonranger-passes-key-nasa-review-ahead-of-lunar-mission/) · [Astrobotic: Final Production](https://www.astrobotic.com/astrobotics-moonranger-moves-into-final-production/) · [Astrobotic: $5.6M sözleşme](https://www.astrobotic.com/astrobotic-awarded-5-6-million-nasa-contract-to-deliver-autonomous-moon-rover/) |

> **"İletişim-kesintili keşif"** MoonRanger'ın tanımlayıcı yeteneği ve LunaPath'in [08](#belge-08) §4'teki yer/rover iş bölümü tartışmasının tam merkezinde. Kutupta Dünya görünürlüğü kesintili olduğu için bu bir lüks değil zorunluluk.

#### C3. Venturi Astrolab — FLEX Rover

| | |
|---|---|
| **Ne** | Robotik kargo taşıma + gelecekte mürettebatlı; Artemis dönemi lojistiği için **sürekli** yüzey operasyonu |
| **Otonomi** | **Üç sürüş modu: mürettebatlı, uzaktan (remote), tam otonom** |
| **Tasarım ömrü** | Bakımsız **10 yıla kadar** |
| **Kaynak** | [Payload Field Guide: Lunar Rovers](https://payloadspace.com/payload-field-guide-lunar-rovers/) · [SpaceNews: ground transportation contracts](https://spacenews.com/companies-race-to-win-ground-transportation-contracts-for-the-moon/) |

#### C4. ispace + Toyota

| | |
|---|---|
| **Durum** | ispace Mission 2 (Resilience + **Tenacious** mikro-rover) Haziran 2025'te lazer telemetre (LRF) anomalisiyle çakıldı |
| **Yeni gelişme** | **Toyota**, ispace'in yeni nesil küçük rover geliştirmesine teknik değerlendirme ve sistem tasarımı desteği veriyor |
| **Ayrıca** | JAXA + Toyota **"Lunar Cruiser"** basınçlı rover: astronot yokken **otonom çalışacak** — sürekli keşif ve mobilite |
| **Kaynak** | [ispace: Toyota desteği](https://ispace-inc.com/news-en/?p=7983) · [Toyota LUNAR CRUISER](https://global.toyota/en/mobility/technology/lunarcruiser/index.html) · [ispace Mission 2 durum](https://ispace-inc.com/news-en/?p=7664) |

#### C5. NASA JPL — CADRE

| | |
|---|---|
| **Ne** | 3 adet el bagajı boyutunda rover; **çok-robot dağıtık otonomi** teknoloji gösterimi |
| **Sensör** | 2 stereo kamera + navigasyon sensörleri + **multistatik yer-nüfuz radarı (GPR)** |
| **Uçuş** | IM-3 ile Reiner Gamma; pencere 2026'ya uzanıyor |
| **Otonomi iddiası** | Mission control'den **doğrudan komut almadan** işbirliği içinde veri toplama |
| **Kaynak** | [JPL CADRE](https://www.jpl.nasa.gov/missions/cadre/) · [NASA: Mini Rover Team Packed](https://www.nasa.gov/missions/tech-demonstration/cadre/nasas-mini-rover-team-is-packed-for-lunar-journey/) |

---

<a id="b10-s5"></a>

### [B10] D. Akademik planlayıcılar (LunaPath'in gerçek rakipleri)

#### D1. ⭐📄 Lamarre, Malhotra & Kelly (2024) — Şans kısıtlı PSR keşfi

| | |
|---|---|
| **Ne** | Güneş enerjili rover ile Ay gölgeli bölge keşfi için **görev-seviyesi** rota planlama |
| **Yöntem** | **Şans kısıtlı (chance-constrained)** planlama problemi; bilinen ortalama oranlarda rastgele arızalar; mevcut planlama teknikleri + **stokastik erişilebilirlik (stochastic reachability)** analizi ile güvenli geçiş politikaları |
| **Doğrulama** | **Cabeus krateri** yörünge arazi ve aydınlanma haritaları; **LCROSS çarpma bölgesinde çok günlük, uzun menzilli sürüşler** |
| **Yayın** | IEEE Aerospace Conference (AERO'24), Big Sky MT, 2–9 Mart 2024 |
| **Kaynak** | [arXiv 2401.08558](https://arxiv.org/abs/2401.08558) |

> **LunaPath'in en yakın komşusu.** Aynı problem, aynı tür bölge, daha ileri (stokastik) formülasyon. **Atıf zorunlu.** [09](#belge-09) Aşama III madde 28: aynı bölgede senaryoyu tekrarlayıp doğrudan karşılaştırma yapmak.

#### D2. ⭐📄 Distributed Safety-Map Path Planning (Remote Sensing 2025)

*"A Safe and Efficient Global Path-Planning Method Considering Multiple Environmental Factors of the Moon Using a Distributed Computation Strategy"*

| | |
|---|---|
| **Güvenlik kriterleri** | **Arazi eğimi, pürüzlülük (roughness), aydınlanma, kaya bolluğu (rock abundance)** ile bir güvenlik değerlendirme kural seti |
| **Yöntem** | **DPPS-STP** — güvenlik-haritası **karo piramidi (tile pyramid)** tabanlı dağıtık rota planlama stratejisi |
| **Algoritma** | **OC-WHT-A\*** — hash tablosu tabanlı open/closed listelerle **ağırlıklı A\***, **Spark cluster** üzerinde |
| **Sonuç** | Tehlikeli node sayısını azaltıyor, krater engellerinden kaçınıyor; uzun mesafeli görevlerde tek makineli OC-WHT-A*'a göre **ortalama 11.5× hızlanma** |
| **Kaynak** | [MDPI Remote Sensing 17(5), 924](https://www.mdpi.com/2072-4292/17/5/924) *(tam metin fetch edilemedi; ayrıntılar özet/arama snippet'inden)* |

> **LunaPath için üç ders:** (1) **Pürüzlülük ve kaya bolluğu** kriter olarak kullanılıyor — LunaPath'te ikisi de yok ([02](#belge-02) §2.5, [07](#belge-07) §2.2 `ra`). (2) **Karo piramidi**, [08](#belge-08) §3'teki hiyerarşi ihtiyacının somut çözümü. (3) Hız problemi gerçek ve çözümü dağıtım — LunaPath'in ön-hesaplama yaklaşımı ([08](#belge-08) §2) daha hafif bir alternatif.

#### D3. ⭐📄 Sun-Synchronous Path Planning (Remote Sensing 2025)

*"A Spatiotemporal U-Net-Based Data Preprocessing Pipeline for Sun-Synchronous Path Planning in Lunar South Polar Exploration"*

| | |
|---|---|
| **Konu** | Ay güney kutbunda **güneş-senkron** rota planlama için **uzamsal-zamansal (spatiotemporal) U-Net** tabanlı veri ön işleme hattı |
| **Neden kritik** | Başlık, LunaPath'in **en büyük eksiğini** (zaman ekseni, [08](#belge-08) §3.3) doğrudan hedefliyor |
| **Kaynak** | [MDPI Remote Sensing 17(9), 1589](https://www.mdpi.com/2072-4292/17/9/1589) · DOI `10.3390/rs17091589` *(tam metin fetch edilemedi — **okunması gereken ilk yayın**)* |

> **Aksiyon: Bu yayını okuyun.** "Güneş-senkron rota planlama" = rover'ı güneşin hareketiyle senkronize hareket ettirmek, yani sürekli aydınlıkta kalmak. Kutup için doğru cevap büyük olasılıkla budur ve LunaPath'in `shadow_traverse` profili bunun kaba bir yaklaşımıdır.

#### D4. 📄 Diğer önemli yayınlar

| Yayın | Katkı | Kaynak |
|---|---|---|
| **Comprehensive Review of Path-Planning Algorithms for Planetary Rover Exploration** (2025) | Alanın taksonomisi; aydınlanma ve sıcaklık dalgalanmaları vurgusu; sabah/akşam ve yüksek enlem aydınlanmasının güç verimliliğine etkisi | [Remote Sensing 17(11), 1924](https://www.mdpi.com/2072-4292/17/11/1924) |
| **Review of Global Path Planning Algorithms for Lunar Rovers Considering Spatiotemporal Constraints** (2026) | **Uzamsal-zamansal kısıtlar** özelinde derleme | [SciEngine ZRHT](https://www.sciengine.com/ZRHT/doi/10.3724/zrht.1674-5825.2026012) |
| **A robust method for large-scale route optimization on lunar surface utilizing a multi-level map model** | **Çok seviyeli harita modeli** ile büyük ölçekli rota optimizasyonu → hiyerarşi | [Chinese J. Aeronautics](https://www.sciencedirect.com/science/article/pii/S1000936124005442) |
| **Risk-Aware Coverage Path Planning for Lunar Micro-Rovers** | Global (PDS DEM) + local (VLP-16 LiDAR) hibrit; **gerçek saha testi**; CLOVER 7 kg rover, ROS1, CoppeliaSim | [arXiv 2404.18721](https://arxiv.org/html/2404.18721v1) |
| **A Deep Learning Approach to Lunar Rover Global Path Planning Using Environmental Constraints and Rover Internal Resource Status** | Statik + zaman-değişken + yola-bağlı kısıtlar; **rover'ın beklemesine izin veriyor**; RL ile kaynak-kısıtlı en kısa yol | [Sensors 24(3), 844](https://www.mdpi.com/1424-8220/24/3/844) |
| **Multi-Objective Global Path Planning for Lunar Exploration With a Quadruped Robot** | A1'in yayını | [arXiv 2406.16376](https://arxiv.org/html/2406.16376v1) |
| **Learning-Based End-to-End Path Planning for Lunar Rovers with Safety Constraints** | Uçtan uca öğrenilmiş planlama | [PMC7866010](https://pmc.ncbi.nlm.nih.gov/articles/PMC7866010/) |
| **Deep Probabilistic Traversability with Test-time Adaptation** | Belirsizlik-farkında gezegen rover navigasyonu | [arXiv 2409.00641](https://arxiv.org/pdf/2409.00641) |
| **LunarLoc: Segment-Based Global Localization on the Moon** | Segment tabanlı global lokalizasyon | [arXiv 2506.16940](https://arxiv.org/pdf/2506.16940) |
| **Visual SLAM with DEM Anchoring for Lunar Surface Navigation** | Yörünge DEM'ine sabitlenmiş SLAM ile drift sıfırlama | [arXiv 2603.17229](https://arxiv.org/pdf/2603.17229) |
| **Transferable Deep RL for Cross-Domain Navigation: from Farmland to the Moon** | Domain transfer ile Ay navigasyonu | [arXiv 2510.23329](https://arxiv.org/pdf/2510.23329) |
| **CISRU: robotics software suite for rover-rover and astronaut-rover interaction** | Çok-ajan Ay/Mars robotik yazılım paketi | [arXiv 2311.03122](https://arxiv.org/pdf/2311.03122) |

---

<a id="b10-s6"></a>

### [B10] E. Yarışma: Lunar Autonomy Challenge (NASA + JHU/APL + Caterpillar)

| | |
|---|---|
| **Kim** | NASA, Johns Hopkins APL, **Caterpillar Inc.**, Embodied AI; APL tarafından NASA için yönetiliyor |
| **Simülatör** | **Unreal Engine + CARLA** özel Ay sürümü; gerçekçi araç dinamiği, fotogerçekçi Ay arazisi |
| **Görev** | Simüle lander etrafındaki **27 m × 27 m** bölgeyi haritalamak; araç: NASA **ISRU Pilot Excavator (IPEx)** rover'ının dijital ikizi (4 tekerlek, diferansiyel direksiyon, **8 monokrom kamera**) |
| **Kapsam** | 2025 sürümü **sadece haritalama** (kazı dahil değil) |
| **Ölçek** | Nitelemede **31 takım**, 15 eyaletten **229 öğrenci**; final Şubat 2025 sonrası, kazananlar Mayıs 2025 |
| **Kaynak** | [lunar-autonomy-challenge.jhuapl.edu](https://lunar-autonomy-challenge.jhuapl.edu/) · [Challenge dokümantasyonu](https://lunar-autonomy-challenge.jhuapl.edu/Challenge-Documentation/index.php) · [NASA STMD seçilen takımlar](https://www.nasa.gov/directorates/stmd/lunar-autonomy-challenge-selected-teams) |

> **LunaPath ekibi için doğrudan fırsat:** Bu, tam olarak sizin profilinizdeki bir yarışma (öğrenci ekibi, Ay otonomisi, simülatör tabanlı). Birinci olan takımın kodu açık (A2). Gelecek çağrıları takip edin — LunaPath'in kod tabanı buraya taşınabilir bir temel.

---

<a id="b10-s7"></a>

### [B10] F. Planlama için altyapı: simülatörler, veri setleri, araçlar

Bu bölüm [04](#belge-04) ile örtüşür; burada sadece **envanter satırları** olarak veriliyor.

| Ad | Ne | Lisans/erişim | Kaynak |
|---|---|---|---|
| **OmniLRS** | Isaac Sim tabanlı Ay robotiği simülatörü; prosedürel arazi, çok-robot, sentetik veri hattı, ROS1+ROS2 | Açık | [GitHub](https://github.com/OmniLRS/OmniLRS) · [arXiv 2309.08997](https://ar5iv.labs.arxiv.org/html/2309.08997) |
| **LunarSim** | Yüksek görsel doğruluk + ROS 2, CV algoritma geliştirme | Açık | [GitHub](https://github.com/PUTvision/LunarSim) |
| **Space Robotics Bench (SRB)** | Isaac Sim üzerine uzay robotiği görev/ortam koleksiyonu | Açık | [andrejorsula.github.io/space_robotics_bench](https://andrejorsula.github.io/space_robotics_bench) |
| **PANGU** | Dundee Üniversitesi/ESA gezegen-asteroit sahne üretim aracı | ESA/lisanslı | [pangu.software](https://pangu.software) |
| **Ames Stereo Pipeline** | DTM, ortogörüntü, 3D nokta bulutu üretimi (stereo + SfS) | Apache 2.0 | [GitHub](https://github.com/NeoGeographyToolkit/StereoPipeline) |
| **NASA POLAR / POLAR Traverse** | Gerçek HDR stereo, kutup benzeri aydınlanma | Açık | [POLAR](https://ti.arc.nasa.gov/dataset/IRG_PolarDB/) · [Traverse](https://ti.arc.nasa.gov/dataset/PolarTrav/) |
| **POLAR-Sim** | POLAR'ın digital twin'i + **23.000 etiket** | Açık | [arXiv 2309.12397](https://arxiv.org/abs/2309.12397) · [Dryad](https://datadryad.org/dataset/doi:10.5061/dryad.ksn02v7hf) |
| **LuSNAR** | 108 GB, 9 UE sahne, stereo+LiDAR+IMU, semantik/derinlik/poz | Açık | [GitHub](https://github.com/zqyu9/LuSNAR-dataset) |
| **cFS / F´** | NASA uçuş yazılımı çatıları | Apache 2.0 | [cFS](https://cfs.gsfc.nasa.gov) · [F´](https://fprime.jpl.nasa.gov) |
| **awesome-space-robotics** | Uzay robotiği kaynak listesi (küratörlü) | Açık | [GitHub](https://github.com/AndrejOrsula/awesome-space-robotics) |
| **heat1d** | Gezegen 1-B termal modeli (Diviner ekibi) | Açık | [GitHub](https://github.com/phayne/heat1d) |

---

<a id="b10-s8"></a>

### [B10] G. LunaPath vs sektör: kim ne kullanmış tablosu

| Proje | DEM | Aydınlanma | Sıcaklık | Pürüzlülük | Kaya | Zaman ekseni | Bekleme kararı | Stokastik | Yerel planlayıcı | Kod |
|---|---|---|---|---|---|---|---|---|---|---|
| **LunaPath (bugün)** | ✅ LOLA 80 m | 🟡 Proxy | 🟡 Sentetik | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | 🔓 MIT |
| **LunaPath (Aşama II hedefi)** | ✅ 5–20 m | ✅ LOLA | ✅ Diviner | ✅ SfS | ✅ `ra` | 🟡 L2 | ❌ | ❌ | 🟡 Arayüz | 🔓 |
| ETH `lunar_planner` (A1) | ✅ | ✅ | ❌ | 🟡 | ❌ | ❌ | ❌ | ❌ | ❌ | 🔓 MIT |
| Stanford NavLab (A2) | ❌ (in-situ) | — | ❌ | ✅ | ✅ | — | ❌ | ❌ | ✅ Arc | 🔓 |
| NASA Moon Trek (B1) | ✅ | ✅ | 🟡 | ❌ | ❌ | 🟡 | ❌ | ❌ | ❌ | 🔓 Portal |
| NASA xGDS (B2) | ✅ | 🟡 | ❌ | ❌ | ❌ | ✅ Süre | ❌ | ❌ | ❌ | 🔓 |
| Lamarre vd. (D1) | ✅ | ✅ | 🟡 | ❌ | ❌ | ✅ Çok günlük | ✅ | ✅ **Şans kısıtlı** | ❌ | 📄 |
| DPPS-STP (D2) | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | 📄 |
| Sun-Synchronous (D3) | ✅ | ✅ | 🟡 | ? | ? | ✅ | ? | ? | ❌ | 📄 |
| Risk-Aware Coverage (D4) | ✅ | ❌ | ❌ | ✅ Pitch | ✅ LiDAR | ❌ | ❌ | ❌ | ✅ Bug | 📄 |
| Sensors 24(3) 844 (D4) | ✅ | ✅ | ✅ Isı akısı | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | 📄 |

#### Tablonun söylediği üç şey

1. **LunaPath'in özgün olduğu tek kolon "Sıcaklık"** — ve o kolon bugün sentetik. [07](#belge-07)'yi uygulamak, tablodaki tek gerçek farkı **gerçek** yapmak demektir. Bu, tüm yol haritasının en yüksek getirili işidir.
2. **Pürüzlülük ve kaya, rakiplerin çoğunda var, LunaPath'te yok.** İkisi de indirilebilir ürünle geliyor (SfS roughness, Diviner `ra`) — yani düşük efor, doğrudan rekabet paritesi.
3. **Zaman ekseni + bekleme kararı, en olgun üç çalışmanın (D1, D3, Sensors 844) ortak özelliği.** LunaPath'te ikisi de yok. Bu, alanın "state of the art" çizgisi ve LunaPath'in en belirgin geride kaldığı yer.

---

<a id="b10-s9"></a>

### [B10] H. Doğrudan ödünç alınabilecek 10 şey (öncelik sıralı)

| # | Ne | Kimden | Neden | Efor |
|---|---|---|---|---|
| 1 | **Rota analizi araç seti** ve metrikleri | ETH `lunar_planner` (A1) | Aynı problemi çözen MIT lisanslı kod; metrik setinizi tamamlar | Düşük |
| 2 | **Pürüzlülük + kaya bolluğu kriterleri** | DPPS-STP (D2) | Rekabet paritesi; veri hazır | Düşük |
| 3 | **Replanning tetikleyici taksonomisi** | ESA ADE/ADAM (B6) | i-SAIRAS bildirisi ücretsiz; kurumsal referans | Düşük |
| 4 | **Karo piramidi (tile pyramid) hiyerarşisi** | DPPS-STP (D2), multi-level map (D4) | [08](#belge-08)'deki ölçek probleminin kanıtlanmış çözümü | Orta |
| 5 | **Güneş-senkron planlama kavramı** | Sun-Synchronous (D3) | Kutup için doğru zaman modeli | Orta |
| 6 | **Bekleme kenarı + kaynak-kısıtlı formülasyon** | Sensors 24(3) 844 (D4) | Zaman ekseninin somut kurulumu | Orta |
| 7 | **Yerel yay-örnekleme planlayıcı** | Stanford NavLab (A2) | Katman 2'nin referans implementasyonu, açık kod | Orta |
| 8 | **ROS 2 + Gazebo hizalaması** | VIPER yer araçları (B4) | Hedef misyonun fiili standardı | Orta |
| 9 | **MMGIS'e eklenti konumlandırması** | NASA AMMOS (A3) | *Use History* + entegrasyon iddiası | Orta |
| 10 | **Şans kısıtlı / stokastik erişilebilirlik** | Lamarre vd. (D1) | Alanın en ileri formülasyonu; yayın hedefi | Yüksek |

---

<a id="b10-s10"></a>

### [B10] I. Atıf listesi (yayın/rapor yazarken)

LunaPath'in bir rapor veya yayında **mutlaka** referans vermesi gerekenler:

1. Lamarre, Malhotra & Kelly (2024) — arXiv 2401.08558 — *en yakın komşu*
2. Richter vd. (2024) — arXiv 2406.16376 — *açık kaynak muadil*
3. Remote Sensing 17(5), 924 (2025) — *çok faktörlü güvenlik haritası*
4. Remote Sensing 17(9), 1589 (2025) — *güneş-senkron planlama*
5. Remote Sensing 17(11), 1924 (2025) — *alan derlemesi*
6. Sensors 24(3), 844 (2024) — *zaman-değişken kısıtlar + bekleme*
7. arXiv 2404.18721 — *global+local hibrit, saha testi*
8. Paige vd. (2010), Science 330, 479 — *Diviner*
9. Hayne vd. (2017), JGR Planets — *termofiziksel özellikler*
10. Barker vd. (2023), PSJ — *LOLA güney kutbu / PSR*

---

<a id="b10-s11"></a>

### [B10] Kaynaklar (bu belgede kullanılan tüm bağlantılar)

**Açık kaynak depolar**
- [leggedrobotics/lunar_planner](https://github.com/leggedrobotics/lunar_planner)
- [Stanford-NavLab/lunar_autonomy_challenge](https://github.com/Stanford-NavLab/lunar_autonomy_challenge)
- [NASA-AMMOS/MMGIS](https://github.com/NASA-AMMOS/MMGIS)
- [jasmeet0915/artemis_mission_simulator](https://github.com/jasmeet0915/artemis_mission_simulator)
- [rakshanda33/Lunar-Navigation-Path-Planner](https://github.com/rakshanda33/Lunar-Navigation-Path-Planner)
- [alessioborgi/MoonBot-Navigation](https://github.com/alessioborgi/MoonBot-Navigation)
- [knamatame0729/ORBSLAM3-Semantic-Mapping](https://github.com/knamatame0729/ORBSLAM3-Semantic-Mapping)
- [space-ros](https://github.com/space-ros) · [space.ros.org FAQ](https://space.ros.org/pages/faq.html)
- [OmniLRS](https://github.com/OmniLRS/OmniLRS) · [LunarSim](https://github.com/PUTvision/LunarSim)
- [NeoGeographyToolkit/StereoPipeline](https://github.com/NeoGeographyToolkit/StereoPipeline)
- [zqyu9/LuSNAR-dataset](https://github.com/zqyu9/LuSNAR-dataset)
- [AndrejOrsula/awesome-space-robotics](https://github.com/AndrejOrsula/awesome-space-robotics)
- [phayne/heat1d](https://github.com/phayne/heat1d)
- [GitHub topic: lunar-exploration](https://github.com/topics/lunar-exploration)
- [MATLAB Central: lunar-rover-path-planning](https://www.mathworks.com/matlabcentral/fileexchange/128759-lunar-rover-path-planning)

**Kurum araçları**
- [NASA Moon Trek](https://trek.nasa.gov/moon/) · [Moon Trek EGU 2023 (ADS)](https://ui.adsabs.harvard.edu/abs/2023EGUGA..25..969L/abstract)
- [NASA Ames xGDS](https://ti.arc.nasa.gov/tech/asr/groups/intelligent-robotics/xgds/) · [xGDS Overview (NTRS)](https://ntrs.nasa.gov/api/citations/20190025706/downloads/20190025706.pdf) · [Acta Astronautica 90:268](https://www.sciencedirect.com/science/article/pii/S0094576512000057)
- [JPL RSVP for MSL](https://www-robotics.jpl.nasa.gov/what-we-do/flight-projects/mars-science-laboratory/rsvp-msl/) · [RSVP Mars 2020](https://www-robotics.jpl.nasa.gov/what-we-do/flight-projects/mars-2020-rover/rsvp-mars-2020/)
- [MIT Tech Review: VIPER open-source software](https://www.technologyreview.com/2021/04/12/1022420/nasa-lunar-rover-viper-open-source-software/)
- [Space ROS SciTech (NTRS)](https://ntrs.nasa.gov/api/citations/20220017761/downloads/Space_ROS_SciTech.pdf) · [AIAA 2023-2709](https://arc.aiaa.org/doi/10.2514/6.2023-2709) · [Robot Report: Open Robotics + Blue Origin + NASA](https://www.therobotreport.com/open-robotics-developing-space-ros/)
- [Artemis Geospatial Data Team Capabilities (NTRS)](https://ntrs.nasa.gov/api/citations/20230006633/downloads/Artemis%20Geospatial%20Data%20Team%20Capabilities%20-%20Strives%20(final).pdf)
- [ESA ADE (GMV)](https://h2020-ade.gmv.com/) · [ADE DFKI](https://robotik.dfki-bremen.de/en/research/projects/ade-og10.html) · [ADE i-SAIRAS 2020](https://www.hou.usra.edu/meetings/isairas2020fullpapers/pdf/5033.pdf) · [CORDIS 821988](https://cordis.europa.eu/project/id/821988)
- [Space Applications LUVMI-X](https://www.spaceapplications.com/products/lunar-rover-luvmi-x) · [Yeni rover girişimleri](https://www.spaceapplications.com/news/space-applications-services-expands-lunar-rover-development-with-new-commercial-and-esa-funded-missions)
- [European Moon Rover System (arXiv 2411.13978)](https://arxiv.org/pdf/2411.13978)

**Ticari**
- [NASASpaceflight: Lunar Outpost MAPP](https://www.nasaspaceflight.com/2025/12/lunar-outpost-mapp/) · [MAPP](https://www.lunaroutpost.com/mapp) · [Lunar Voyage 1 Update](https://www.lunaroutpost.com/post/lunar-voyage-1-update) · [Space.com mission control](https://www.space.com/astronomy/moon/we-are-ready-to-drive-take-a-look-inside-lunar-outposts-moon-rover-mission-control-photos) · [Wikipedia: Lunar Outpost](https://en.wikipedia.org/wiki/Lunar_Outpost_(company))
- [CMU RI: MoonRanger NASA review](https://www.ri.cmu.edu/moonranger-passes-key-nasa-review-ahead-of-lunar-mission/) · [Astrobotic MoonRanger production](https://www.astrobotic.com/astrobotics-moonranger-moves-into-final-production/) · [Astrobotic $5.6M](https://www.astrobotic.com/astrobotic-awarded-5-6-million-nasa-contract-to-deliver-autonomous-moon-rover/)
- [Payload Field Guide: Lunar Rovers](https://payloadspace.com/payload-field-guide-lunar-rovers/) · [SpaceNews: lunar ground transportation](https://spacenews.com/companies-race-to-win-ground-transportation-contracts-for-the-moon/)
- [ispace + Toyota](https://ispace-inc.com/news-en/?p=7983) · [Toyota Lunar Cruiser](https://global.toyota/en/mobility/technology/lunarcruiser/index.html) · [ispace Mission 2 status](https://ispace-inc.com/news-en/?p=7664)
- [JPL CADRE](https://www.jpl.nasa.gov/missions/cadre/)

**Akademik**
- [arXiv 2401.08558](https://arxiv.org/abs/2401.08558) · [arXiv 2406.16376](https://arxiv.org/html/2406.16376v1) · [arXiv 2404.18721](https://arxiv.org/html/2404.18721v1) · [arXiv 2603.17232](https://arxiv.org/html/2603.17232v1) · [arXiv 2409.00641](https://arxiv.org/pdf/2409.00641) · [arXiv 2506.16940](https://arxiv.org/pdf/2506.16940) · [arXiv 2603.17229](https://arxiv.org/pdf/2603.17229) · [arXiv 2510.23329](https://arxiv.org/pdf/2510.23329) · [arXiv 2311.03122](https://arxiv.org/pdf/2311.03122)
- [Remote Sensing 17(5), 924](https://www.mdpi.com/2072-4292/17/5/924) · [17(9), 1589](https://www.mdpi.com/2072-4292/17/9/1589) · [17(11), 1924](https://www.mdpi.com/2072-4292/17/11/1924) · [Sensors 24(3), 844](https://www.mdpi.com/1424-8220/24/3/844)
- [SciEngine: Spatiotemporal constraints review](https://www.sciengine.com/ZRHT/doi/10.3724/zrht.1674-5825.2026012) · [Chinese J. Aeronautics: multi-level map](https://www.sciencedirect.com/science/article/pii/S1000936124005442) · [PMC7866010](https://pmc.ncbi.nlm.nih.gov/articles/PMC7866010/)

**Yarışma**
- [Lunar Autonomy Challenge](https://lunar-autonomy-challenge.jhuapl.edu/) · [Dokümantasyon](https://lunar-autonomy-challenge.jhuapl.edu/Challenge-Documentation/index.php) · [NASA STMD seçilen takımlar](https://www.nasa.gov/directorates/stmd/lunar-autonomy-challenge-selected-teams)

[↑ İçindekiler](#icindekiler) · [↑ Yönlendirme tablosu](#yonlendirme)

---

<!-- BİRLEŞİK DOSYA SONU — 11 kaynak belge, içerik birebir korunmuştur. -->