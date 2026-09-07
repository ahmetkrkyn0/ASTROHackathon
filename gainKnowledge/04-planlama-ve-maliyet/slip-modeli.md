# Slip Modeli (C3) — Tekerlek Döner, Araç İlerlemez

**Kodda:** `backend/app/slip_model.py`, bağlantı noktası `cost_engine.edge_travel_time_s`
**API:** `/api/rovers` içinde `slip_model`; her plan cevabında `slip_model` bloğu
**Özellik kodu:** C3

---

## Nedir?

**Slip** (kayma), tekerleğin döndüğü mesafe ile aracın gerçekten ilerlediği mesafe arasındaki fark.

Slip oranı 0,3 ise: tekerlek 10 metrelik dönüş yapıyor, araç 7 metre ilerliyor. **3 metrelik dönüş boşa gitti** — ama enerjisi harcandı, süresi geçti.

---

## Hangi problemi çözüyor?

Gevşek regolit (Ay toprağı) üzerinde tekerlekler kayar. Bu, süre ve enerji hesaplarını **sistematik olarak iyimser** yapar.

C3'ten önce `slip_model.py` bir yön iddiası taşıyordu ("eğim arttıkça slip artar") ama büyüklük vermeyi **reddediyordu**: katsayıları kabaca literatür şeklinde tahminlerdi, kendini `UNCALIBRATED` etiketliyordu ve **kasıtlı olarak hiçbir ürün onu çağırmıyordu.**

Sonuç: yayınlanan her süre ve enerji rakamı sistematik olarak iyimserdi. Ve bu ölçüldü:

- B5 (Monte Carlo), VIPER rotasını nominalde **%23'e** düşürmüştü
- B3 (DEM klonları), sürüş enerjisini **%6–10 düşük** buluyordu

Yani iki bağımsız doğrulama, aynı yöne işaret ediyordu: fizik modelinde eksik bir kayıp var.

---

## Analoji: Kumsalda koşmak

Sahilde ıslak, sıkı kumda koşmak kolaydır. Kuru, gevşek kuma girdiğinizde ayağınız kayar — aynı adım sayısıyla daha az yol gidersiniz ve çok daha çok yorulursunuz.

Şimdi bir de yokuş yukarı gevşek kumda koşmayı deneyin. Kayma dramatik artar; bir noktadan sonra adım atarsınız ama **hiç ilerlemezsiniz** — kum ayağınızın altından geriye akar.

Ay regoliti tam olarak bu: kuru, gevşek, ince taneli. Ve VIPER'ın tasarım gereksinimi diyor ki 15 derecelik yamaçta **%40'a kadar** kayma olabilir.

**Kritik nokta:** kayma sadece süreyi uzatmıyor. Tekerlek dönüyor demek, motor **çekiş gücü çekiyor** demek. Yani süre ve enerji **birlikte** büyüyor.

---

## Nasıl çalışıyor?

### Önce kaynaklar, sonra kablolama

C3'ün metodolojisi şuydu: eğriyi bağlamadan önce, her noktasının bir kaynağı olsun.

Eğri artık **sadece kaynaklı çapalardan (anchor)** geçiyor:

#### Çapa 1 — NASA VIPER

> *"Mobilite tasarım gereksinimleri, maksimum 15° eğimde maksimum %40 slip tanımladı."*
> — PSJ 2025, §3.5

Test koşulları: GRC-1 benzeşiği (simulant), MGRU test aracı, Optitrack izleme.

⚠️ **Bu bir ÜST SINIR, tipik değer değil.** Kodda böyle etiketli.

#### Çapa 2 — CNSA Yutu-2

> *"Chang'e-4 sahasında 8,86°'ye kadar eğimlerde slip oranlarının çoğu 0 ile −0,075 arasında."*
> — Nature Communications 2024

Çevrilmiş hâli: 0° → 0,0375 ± 0,01875 · 8,86° → 0,075

### Çapalar arası: log-lineer

Çapalar arasında ve son çapanın ötesinde eğri **log-lineer** ilerliyor.

**Gerekçe:** Gevşek zeminde slip eğrilerinin gösterdiği dışbükey biçim.
**Etiketi:** VARSAYIM. Ve öyle işaretli.

Tavan: **0,9**. Simetrik: `|eğim|` üzerinden, yani inişte de kayma var.

### Kaynak zorunluluğu

Her `SlipAnchor` nesnesi **zorunlu bir kaynak alanı** taşıyor. Kaynaksız çapa oluşturulamıyor.

Profiller arası aktarımlar `assumption:` ile başlıyor:

| Rover | Durum |
|---|---|
| **LPR-1** | Tamamen aktarım (kendi verisi yok) |
| **LUVMI-M** | Tamamen aktarım |
| **NASA VIPER** | Düz zemin noktası Yutu-2'den aktarım; 15° noktası kendi verisi |
| **CNSA Yutu-2** | Kendi verisi; ama 8,86° noktası **aktarılmadı** |

**Neden Yutu-2'nin 8,86° noktası aktarılmadı?** Çünkü mare regoliti ile gevşek GRC-1 simulantı **farklı zeminler**. Aktarmak yanlış olurdu ve yapılmadı.

### Etiket değişimi

`UNCALIBRATED` → **`MODEL`**

Ama **asla `MEASURED` değil** — çünkü burada hiçbir şey kutup regolitinde ölçülmedi.

---

## Tek bağlanma noktası

```python
# cost_engine.edge_travel_time_s
efektif_mesafe = d / (1 - slip(eğim, rover))
```

Bu **tek bir yerde** oluyor. Ve o tek yerden şunların hepsi besleniyor:

- 2-B ve 4-B planlayıcılar
- Simülatör
- Koridor bütçeleri
- Monte Carlo bacakları
- Safe haven mesafeleri
- `auto_slice_hours`

**Neden tek nokta:** Slip'i on ayrı yere eklemek gerekseydi, biri unutulur ve o tüketici diğerlerinden ayrışırdı. Tek nokta, tutarlılığı yapısal olarak garantiliyor.

### Vektörel ikizin bit-eşitliği

Vektörize `slip_ratio_array`, skalerle **aynı işlem sırasında** yazıldı ve **bit-eşit** doğrulandı: bu platformda **0 ulp**, profil başına 100 000 rastgele kenarda test edildi.

**Neden bu kadar sıkı:** Planlayıcının kenar aritmetiği ve vektörize grafikler (`safe_haven._gated_edges`, `illumination_corridor.edge_tables`) **aynı şekilde yuvarlamalı**. Bir ondalık basamak fark, bir kenarı bir grafiğe dâhil edip diğerinden çıkarabilir.

---

## İki sonuç ele alınmak zorunda kaldı

### 1. Enerji kriterinin ölçeği slip'siz kaldı

**Sorun:** Enerji kriterini slip dâhil en kötü hücreye göre normalleştirmek (25°'de slip 0,9 → slip'siz sürenin on katı), her sıradan hücreyi `[0, 0,15]` aralığına sıkıştırıyordu.

**Ölçüldü:** LPR-1'in karanlık 10° hücresi **0,58'den 0,07'ye** düştü. Yani kriter neredeyse ölüyordu — [maliyet motorundaki çöküş hikâyesinin](maliyet-motoru.md) tekrarı olacaktı.

**Karar:** Ölçek slip'siz en iyi/en kötü çifti olarak bırakıldı. `COST_MODEL_ID` → **v4**.

### 2. 4-B ufku taşıyordu

**Sorun:** Eski kural "BFS hamleleri × en yavaş kenar". Slip altında bu sınır taşıyordu.

**Ölçüldü:** 113 hamlelik ay gecesi rotası eski kuralla **1 602 dilim** istiyordu.

**Düzeltme:** Ufuk artık en hızlı kapılı rotadan (Dijkstra ile) boyutlanıyor → **270 dilim**.

---

## Site11'de ölçülen gerçek sayılar

### Eğri

| Eğim | Slip | Süre/enerji çarpanı |
|---|---|---|
| 0° | 0,037 | ×1,04 |
| 5° | 0,083 | ×1,09 |
| 10° | 0,182 | ×1,22 |
| 15° | 0,400 | ×1,67 |
| 20° | 0,881 | **×8,4** |
| 25° | 0,900 | **×10** |

**20 derecede süre 8,4 katına çıkıyor.** Bu, dik arazinin neden bu kadar pahalı olduğunun sayısal cevabı.

Ve Site11 dik: ince eğim medyanı ~10°, kaba blok p95 19–22°.

### Rotalara etkisi

**LPR-1, 2026-09-28:**

| Metrik | Slip öncesi | Slip sonrası |
|---|---|---|
| Varış süresi | 2,16 sa | **2,98 sa** (×1,38) |
| Minimum SOC | %96,2 | %92,5 |
| Rota ortalama slip | — | 0,326 (maks 0,537) |
| Slip'in eklediği | — | 0,75 sa / 321 Wh |

**Ay gecesi:** 5,35 → 6,75 saat

**2-B enerji:**

| Rota | Öncesi | Sonrası |
|---|---|---|
| LPR-1 gündüz | 469 Wh | 597 Wh (×1,27) |
| LPR-1 ay gecesi | 1 288 Wh | 1 466 Wh |
| VIPER standart | 2 156 Wh | **2 742 Wh** (×1,27) |

### VIPER'ın standart bacağı reddedildi

Slip eğrisi altında VIPER'ın standart haven-haven bacağı **404 dönüyor**: 283 148 kenar bataryayı %20 rezervin altına düşürürdü.

**Bu bir arıza değil, modelin dürüst kararı.** Kanıt:
- Slip'siz plan zaten %32 batarya ile bitiyordu (zar zor)
- B5 Monte Carlo, koşumların sadece **%1,4'ünü** rezerv içinde bulmuştu

Yani rota zaten sınırdaydı; slip onu sınırın öbür tarafına itti.

**En yakın uygulanabilir bacak** (358,494)→(346,462): 8 hamle, 1,53 → 2,23 sa (×1,46), min SOC %85,4 → %72,3, haven'da bitiyor.

### Arama maliyeti

Planlayıcı slip'li maliyet yüzeyinde **2,6–2,8 kat daha fazla düğüm** açıyor (LPR-1: 8 799 → 23 177).

---

## API'ye eklenenler

| Nerede | Ne |
|---|---|
| `/api/rovers` | Her rover'da `slip_model`: etiket, kaynaklı çapalar, 0–25° tablo, referanslar |
| `/api/rovers` | `declared_only.regolith`: Yutu-2'nin ölçülmüş Bekker aralıkları, VIPER'ın GRC-1 test yatağı — **hiçbir şey okumuyor**, Bekker denklemi kodlanmadı |
| `/api/plan`, `/api/plan-4d`, `/api/compare`, `/api/plan-multi` | `slip_model` bloğu: ortalama/maks slip, mesafe çarpanı, slip'in bu rotaya eklediği saat ve Wh |

---

## İlham kaynağı

- **NASA VIPER** — PSJ 2025 §3.5, mobilite tasarım gereksinimi
- **CNSA Yutu-2** — Nature Communications 2024, Chang'e-4 saha ölçümleri
- **Bekker terramekaniği** — regolit-tekerlek etkileşiminin klasik teorisi (referans olarak yayınlanıyor, **kodlanmadı**)

---

## İddia sınırı

✅ **Söylenebilir:** *"Slip modelimiz uçmuş misyon verisine **bağlandı**."*
❌ **Söylenemez:** *"Slip modelimiz **ölçüldü**."*

LunaPath saha verisi üretmiyor ve kutup regolitinde slip ölçümü yok.

---

## Kodda nerede?

```
backend/app/slip_model.py
  SlipAnchor                 ← zorunlu kaynak alanı
  slip_ratio() / slip_ratio_array()   ← bit-eşit ikiz
  route_slip_summary()
  SLIP_MODEL_VALIDITY = "MODEL"
  rover_slip_block()

backend/app/cost_engine.py
  edge_travel_time_s()       ← TEK bağlanma noktası

scripts/slip_calibration_report.py
docs/research/slip_calibration_report.md   ← öncesi/sonrası
```
82 yeni/uyarlanan test.

---

## Jüri soruları

**S: "Slip modeliniz ölçüldü mü?"**
Hayır ve bunu net söylüyoruz. Uçmuş misyon verisine **bağlandı** — VIPER'ın 15°/%40 tasarım gereksinimi ve Yutu-2'nin Chang'e-4 saha ölçümleri. Ama kutup regolitinde hiçbir şey ölçülmedi, o yüzden etiket `MODEL`, asla `MEASURED`.

**S: "Neden eskiden kullanmıyordunuz?"**
Çünkü eski eğri kaynaksızdı — kabaca literatür şeklinde bir tahmindi. Kod kendini `UNCALIBRATED` etiketliyordu ve **bilinçli olarak** hiçbir ürün onu çağırmıyordu. Kaynaksız bir sayıyı hesaba katmak, hesabı iyileştirmez, sadece yanlışlığı gizler.

**S: "Bağladıktan sonra ne değişti?"**
Her şey %27 civarında pahalılaştı. VIPER'ın standart rotası artık **reddediliyor** — 283 148 kenar bataryayı rezerv altına düşürüyor. Bu kötü bir haber ama doğru bir haber: iki bağımsız doğrulama (Monte Carlo %23 tamamlama, DEM klonları %6-10 enerji açığı) zaten bu yöne işaret ediyordu.

**S: "20 derecede slip 0,881 çok yüksek değil mi?"**
Yüksek ve bu VIPER'ın 15°/%40 üst sınırından log-lineer ekstrapolasyonun sonucu. Ekstrapolasyonun kendisi bir varsayım ve öyle etiketli. Ama yönü doğru: dik yamaçta gevşek regolit üzerinde tekerlek dönüp araç ilerlemiyor.

**S: "Bekker denklemini neden kullanmadınız?"**
Çünkü Bekker parametreleri (kohezyon, sürtünme açısı, batma modülü) kutup regoliti için yayınlanmış değil. Yutu-2'nin ölçülmüş Bekker aralıklarını API'de **referans olarak** yayınlıyoruz ama hiçbir şey onları okumuyor — denklem kodlanmadı. Kullanmak, olmayan parametreleri uydurmak olurdu.
