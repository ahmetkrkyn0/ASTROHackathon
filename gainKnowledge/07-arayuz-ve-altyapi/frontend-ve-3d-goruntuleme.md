# Arayüz ve 3-D Görüntüleme — Operatörün Gördüğü Şey

**Kodda:** `frontend/src/`, `backend/app/terrain.py`
**API:** `GET /api/terrain`, `GET /api/layers/{katman}?format=f32`

---

## Nedir?

React tabanlı bir operatör arayüzü. Otuz beşten fazla **özellik modülü** (`frontend/src/features/`), 2-D harita, 3-D arazi görüntüleyici ve sanal LiDAR simülasyonu.

---

## Hangi problemi çözüyor?

Backend 33 API ucundan JSON döndürüyor. Bir operatörün bu JSON'a bakarak karar vermesi imkânsız.

Arayüz, bu veriyi **görsel karara** çeviriyor: harita üstünde rota, katman renkleri, batarya grafiği, GO/NO-GO rozeti, güvenilirlik etiketi.

---

## Analoji: Kokpit

Bir uçağın kokpiti, motorun içindeki her sensörü ayrı ayrı göstermez. Pilotun karar vermesi için gereken şeyi gösterir: irtifa, hız, yakıt, uyarılar.

Ve şu ilke geçerli: **her göstergenin bir güvenilirlik durumu vardır.** Bir gösterge arızalıysa, pilot bunu bilmelidir — yanlış değer göstermek, hiç göstermemekten kötüdür.

LunaPath arayüzündeki **soyağacı rozeti** (`layer-provenance`) tam olarak bu: her katmanın yanında "bu ölçüm mü, model mi, demo mu" göstergesi.

---

## Özellik modülleri

Arayüz, backend özellikleriyle **birebir eşleşen** modüllere bölünmüş:

| Grup | Modüller |
|---|---|
| **Misyon kurulumu** | `mission-setup`, `mission-context`, `mission-constraints`, `mission-snapshot`, `mission-validation` |
| **Planlama** | `plan-request`, `route-model`, `corridor`, `solving-indicator`, `replan` |
| **Katmanlar** | `analysis-layers`, `layer-picker`, `layer-provenance`, `map-legend`, `coarse-fields` |
| **İleri özellikler** | `safe-haven`, `earth-visibility`, `illumination-corridor`, `thermal-envelope`, `uncertainty`, `risk-sweep`, `psr-validation`, `stress-test`, `safety-margins`, `benchmark` |
| **Analiz** | `route-analysis`, `profile-compare`, `cost-explain`, `mission-report` |
| **Zaman** | `time-axis`, `playback` |
| **Diğer** | `assistant` (AI sohbet), `pose-loop`, `ros-showcase`, `analysis-job` |

**`cost-explain` özellikle değerli:** `CostMap.explain()`'in çıktısını görselleştiriyor — yani *"neden bu rota?"* sorusunun görsel cevabı.

---

## İki veri yolu: JSON ve binary

Bu, mimari olarak ilginç bir ayrım.

| Yol | Kim kullanıyor | Format | Boyut |
|---|---|---|---|
| **JSON** (`/api/layers/{ad}`) | 2-D harita (`MapCanvas`) | İç içe Python float listesi | 500×500 için **~4,25 MB metin** (1,00 MB sayı için) |
| **Binary** (`?format=f32`) | 3-D görüntüleyici (`TerrainCanvas3D`) | Ham little-endian float32 | ~**1 MB** |

### Neden iki yol?

> *"`/api/layers` bir tarayıcıya iç içe Python float listesi veriyor. Gönderilen 500×500 grid için bu, 1,00 MB'lık sayıyı tarif eden ~4,25 MB metin — bu yüzden uç nokta 65 536 hücrelik bir önizlemeyle sınırlı ve frontend varsayılan olarak `downsample=2` kullanıyor."*
>
> *"Bir 3-D motor tam tersi ödünleşimi ister: bütün alan, doğal çözünürlükte, GPU'nun tükettiği bellek düzeninde."*

### Binary yük kasıtlı olarak başlıksız

```javascript
new Float32Array(await r.arrayBuffer())   // ← çözümlemenin tamamı
```

Yorumlamak için gereken her şey (şekil, coğrafi referans, katman başına aralık ve birim) **manifesto**dan geliyor (`GET /api/terrain`) — ve aynı değerler `X-Layer-*` HTTP başlıklarında tekrarlanıyor, böylece tek bir katmanı yalıtılmış olarak çeken bir çağıran asla tahmin yürütmüyor.

### Veri yok konvansiyonu: **NaN, ve yalnız NaN**

Grid'ler iki tür "yok" değeri taşıyor:
- **NaN** — alan tanımsız
- **+sonsuz** — `cost` içinde, hücre geçilemez (şu anki grid'de ~60 000 tane)

**JSON yolu ikisini de `null`'a düzleştiriyor.**

**float32 sonsuzluğu taşıyacaktı** — ve bir renk rampasına veya köşe konumuna ulaşan sonsuzluk, görünür bir delik değil **sessizce bozulmuş bir render** demek.

O yüzden ikisi de burada NaN oluyor ve **sayısı raporlanıyor**.

---

## 3-D görüntüleyici — iki kasıtlı karar

`TerrainCanvas3D.tsx`'in dokümanı iki şeyi "sonradan düzeltmeyin" diye işaretliyor:

### 1. Ortam ışığı neredeyse sıfır

> *"Ay'ın atmosferi yok, o yüzden hiçbir şey bir gölgeyi doldurmuyor — gölgeli bir yamaç siyahtır, koyu gri değil."*

Dünya'da gölgeler gri, çünkü atmosfer ışığı saçıyor. Ay'da gölge **siyah**. Bu, görsel bir tercih değil, **fiziksel doğruluk.**

Ve bu, projenin ana temasının görsel karşılığı: gölge Ay'da neden bu kadar ölümcül olduğunun anlık kavranışı.

### 2. Native çözünürlük

500×500 alanın tamamı, alt-örneklenmeden. Katman başına ~1 MB.

---

## Sanal LiDAR simülasyonu

`lidarSimulation.ts` — tarayıcıda çalışan, Three.js tabanlı bir LiDAR taraması.

Yapılandırma gerçekçi:

| Parametre | Değer |
|---|---|
| Maksimum menzil | 60 m |
| Minimum menzil | 1,5 m |
| Menzil gürültüsü σ | 0,02 m |
| Azimut adımı | **270** |
| Dikey kanal | 16 (−16° … +14°) |
| Tarama hızı | 5 Hz |

**Azimut 270 seçimi belgelenmiş:**

> *"270, 180 değil: tipik düşüşte ~1 400 dönüş, referans nokta bulutu yakalamalarına karşı FPS aralığında seyrek pus gibi okunuyordu. Bu açısal çözünürlük, arayüzün ilan ettiği '16 CH' dikey kanal sayısından bağımsız ve hâlâ backend'in 360-azimut tavanının rahat içinde."*

Yani sayı deneyle seçilmiş ve gerekçesi yazılı.

**Not:** Backend tarafında aynı ışın yürüyüşü çekirdeği [`horizon.py`](../02-isik-golge-ve-termal/ufuk-ve-aydinlanma.md)'de — LiDAR taraması, gölge hesabıyla **aynı geometriyi** kullanıyor.

---

## Karar mantığının frontend kopyası

`frontend/src/features/mission-report/report.ts`, GO/NO-GO kararının frontend uygulaması.

**Backend'le testle kilitli** — detay: [misyon raporu](../05-dogrulama-ve-test/rota-analizi-ve-misyon-raporu.md).

---

## Kodda nerede?

```
frontend/src/
  features/            ← 35+ özellik modülü
  MapCanvas.tsx        ← 2-D harita (JSON yolu)
  TerrainCanvas3D.tsx  ← 3-D arazi (binary yolu)
  lidarSimulation.ts   ← sanal LiDAR
  colormap.ts / sky.ts / grid/ / i18n/ / mission/ / net/ / overlay/ / shell/

backend/app/terrain.py
  ← sahne manifestosu, f32 transferi, NaN konvansiyonu
```

---

## Jüri soruları

**S: "Arayüz backend'in ne kadarını gösteriyor?"**
Neredeyse hepsini. 35'ten fazla özellik modülü var ve çoğu bir backend özelliğine birebir karşılık geliyor: safe haven, Dünya görünürlüğü, aydınlık koridoru, termal zarf, belirsizlik, risk süpürmesi, PSR doğrulaması, stres testi, güvenlik marjları, benchmark.

**S: "Neden iki ayrı veri yolu var?"**
Çünkü 2-D harita ile 3-D motor zıt şeyler istiyor. JSON yolu 500×500 grid için 1 MB sayıyı tarif eden 4,25 MB metin üretiyor — o yüzden önizleme sınırlı ve alt-örneklenmiş. 3-D motor tam alanı, doğal çözünürlükte, GPU'nun istediği bellek düzeninde istiyor. Binary yol tam olarak bunu veriyor: başlıksız `Float32Array`, ~1 MB.

**S: "3-D görüntüde neden gölgeler tamamen siyah?"**
Çünkü Ay'da öyle. Atmosfer olmadığı için ışığı saçan bir şey yok — gölgeli bir yamaç siyah, koyu gri değil. Bu bir görsel tercih değil, fiziksel doğruluk. Ve projenin ana temasının görsel özeti: gölgenin neden bu kadar ölümcül olduğunu bir bakışta anlatıyor.

**S: "NaN meselesi nedir?"**
Grid'lerde iki tür "yok" var: NaN (alan tanımsız) ve +sonsuz (`cost` içinde, geçilemez hücre — şu an ~60 000 tane). JSON yolu ikisini de `null`'a düzleştiriyor. Ama float32 sonsuzluğu taşırdı ve bir renk rampasına veya köşe konumuna ulaşan sonsuzluk, görünür bir delik değil **sessizce bozulmuş bir render** demek. O yüzden binary yolda ikisi de NaN oluyor ve sayısı raporlanıyor.

**S: "LiDAR simülasyonu gerçekçi mi?"**
Parametreleri gerçekçi: 60 m menzil, 2 cm menzil gürültüsü, 16 dikey kanal (−16° … +14°), 5 Hz. Azimut adımı 270 ve bu sayı deneyle seçilmiş: 180 ile tipik düşüşte tarama "seyrek pus" gibi görünüyordu. Ve önemlisi — backend tarafında LiDAR taraması, gölge hesabıyla **aynı ışın yürüyüşü çekirdeğini** kullanıyor.

**S: "Soyağacı rozeti ne?"**
Her katmanın yanında görünen güvenilirlik göstergesi: `measurement` / `model` / `demo`. Operatörün ekrandaki sayının ölçüm mü tahmin mi olduğunu görmesini sağlıyor. Arka planda dört basamaklı bir merdiven var (MEASURED/MODEL/DERIVED/SYNTHETIC) ve en zayıf girdi orada hesaplanıp sonra üç seviyeye indiriliyor.
