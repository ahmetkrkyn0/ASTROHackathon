# API Yüzeyi ve Serileştirme — Dışarıya Açılan Kapı

**Kodda:** `backend/app/main.py`, `backend/app/serializer.py`, `backend/app/terrain.py`
**Toplam:** 33 uç nokta

---

## Nedir?

LunaPath'in FastAPI kabuğu. Otuz üç uç nokta, üç koordinat sistemi arasında çeviri, ve her cevaba iliştirilen metadata.

---

## Analoji: Restoranın servis penceresi

Mutfakta karmaşık işler oluyor. Servis penceresi, o karmaşıklığın dışarıya nasıl göründüğü.

İyi bir servis penceresinin iki özelliği var:
1. **Tabak eksiksiz gelir** — garnitür unutulmaz
2. **Alerjen bilgisi vardır** — içinde ne olduğu yazılıdır

LunaPath'in API'sinde bu ikincisi çok belirgin: her cevap, sayıların yanında **nereden geldiklerini** de taşıyor.

---

## 33 uç nokta

### Planlama

| Uç | Ne yapar |
|---|---|
| `POST /api/plan` | 2-D A* planı |
| `POST /api/plan-4d` | 4-D (zamanla genişletilmiş) plan |
| `POST /api/plan-multi` | Çoklu rota |
| `POST /api/compare` | Profil karşılaştırması |
| `POST /api/replan` | Yeniden planlama tetikleyici değerlendirmesi |

### Veri ve katmanlar

| Uç | Ne yapar |
|---|---|
| `POST /api/load-dem` | Ham DEM yükle |
| `POST /api/load-preprocessed` | İşlenmiş grid yükle |
| `GET /api/layers/{ad}` | Katman (JSON veya `?format=f32`) |
| `GET /api/terrain` | 3-D sahne manifestosu |
| `GET /api/cell-telemetry` | Hücre kartı — tek hücrenin bütün bilgileri |

### İleri özellikler

| Uç | Feature |
|---|---|
| `GET /api/safe-haven` | [A1](../04-planlama-ve-maliyet/safe-haven.md) |
| `GET /api/earth-series`, `GET /api/comm-window` | [A4](../03-konum-ve-iletisim/dunya-gorunurlugu-dte.md) |
| `GET /api/illumination-corridor`, `GET /api/illumination-series` | [A2](../02-isik-golge-ve-termal/aydinlik-koridoru.md) |
| `GET /api/thermal-dwell`, `GET /api/thermal-envelope` | [C6](../02-isik-golge-ve-termal/termal-dwell-ve-operasyon-zarfi.md) |
| `GET /api/survival` | [B1](../04-planlama-ve-maliyet/survival-reach-avoid.md) |
| `POST /api/dem-uncertainty`, `GET /api/uncertainty-series` | [B3](../01-arazi-ve-veri/dem-belirsizligi-100-klon.md) |
| `POST /api/risk-sweep` | [B2](../04-planlama-ve-maliyet/cvar-risk.md) |
| `GET /api/psr-validation` | [C4](../01-arazi-ve-veri/puruzluluk-ve-psr.md) |
| `POST /api/stress-test` | [B5](../05-dogrulama-ve-test/stres-testi-sherpa.md) |
| `POST /api/safety-check` | [D3](../05-dogrulama-ve-test/safety-monitor-stl-fretish.md) |

### Kataloglar, durum, AI

| Uç | Ne yapar |
|---|---|
| `GET /api/rovers` | Rover katalogu |
| `GET /api/profiles` | Misyon profilleri |
| `GET /api/scenarios`, `POST /api/scenarios/{id}/load` | Senaryolar |
| `GET /api/reference-missions` | Gerçek misyon kilometre taşları |
| `POST /api/pose` | Poz değerlendirmesi |
| `GET /api/lidar-scan` | Sanal LiDAR taraması |
| `GET /api/health` | Sağlık kontrolü |
| `POST /api/ai/chat` | [AI asistanı](../06-ai-asistani/ai-mimarisi-k1-k5.md) |

---

## Serileştirme: üç koordinat sistemi

| Sistem | Biçim | Kim kullanıyor |
|---|---|---|
| **Piksel** | (satır, sütun) | İç hesaplama |
| **Projeksiyon metresi** | (x, y) | Koridor sözleşmesi, ROS |
| **Coğrafi** | (boylam, enlem) | İnsan arayüzü |

Çeviri zinciri: `grid_frame.pixel_to_map_xy` → `serializer.pixel_to_lonlat`

Projeksiyon: **Ay Güney Kutup Stereografik → WGS84** (pyproj ile).

### Bir taşınabilirlik detayı

```python
os.environ.setdefault("PROJ_IGNORE_CELESTIAL_BODY", "YES")
```

PROJ kütüphanesi varsayılan olarak gökcismi eşleşmesini zorluyor — Ay koordinatlarını Dünya referans sistemine çevirmeyi reddediyor. Bu ayar o kontrolü geçersiz kılıyor.

### Yedek geometrinin hikâyesi

`serializer.py`'de son çare olarak kullanılan grid geometri sabitleri var. Bunlar **sadece** çağıran hiç metadata vermediğinde kullanılıyor.

Ama bir dönem sabit kodluydular ve **yanlıştı:**

> Bir yorum, "merkez piksel (250, 250), 80 m/px'te (176000, 48000) m'ye eşleniyor" diye türetiyordu — oysa o zamanki gönderilen grid 5 m/px'te (−15500, −4000) orijinliydi.
>
> **Sayılar yanlıştı VE yorum türetmeyi güncelmiş gibi sunuyordu**, yani grid'i anlamak için onu okuyan biri **başka bir saha** hakkında okuyordu.

**Düzeltme:** Değerler artık import zamanında **gönderilen metadata'dan okunuyor**, sabitler de yedeğin yedeği olarak duruyor. ("Round 3 review, L-7")

> *"Bu kayma tam olarak neden okundukları, güvenilmedikleri sebebidir."*

---

## Her cevapla giden metadata

API'nin ayırt edici özelliği: sayılar yalnız gelmiyor.

| Metadata | Ne söylüyor |
|---|---|
| `layer_validity` | Katmanın güvenilirlik etiketi (`MEASURED`/`MODEL`/`DERIVED`/`SYNTHETIC`) |
| `X-Layer-Validity` başlığı | Aynısı, HTTP başlığında |
| `X-Layer-*` başlıkları | Şekil, aralık, birim |
| `cost_model_id` | Hangi maliyet formülü sürümü |
| `risk_alpha`, `risk` | Risk iştahı ve eğim sigmasının kaynağı |
| `cost_criteria` | Hangi kriterler dâhildi |
| `claim` alanları | Her ileri özellikte iddia sınırları |
| `UNCERTAINTY_NOTE` | B3'ün belirsizlik uyarısı |

---

## Hata davranışı

| Kod | Ne zaman |
|---|---|
| **404** | Rota bulunamadı — **ve hangi kapının kaç kez kapandığı** detayda |
| **422** | Girdi doğrulama hatası, veya sessiz geri düşüşün reddedildiği durumlar (`engine=rtamt` paketsizken, önbelleksiz `thermal-envelope`) |
| `unavailable` | Katman hesaplanamadı — **sebebiyle birlikte** |

**Kritik ilke:** Sessiz geri düşüş yok. Bir şey hesaplanamıyorsa, sistem sahte bir varsayılan üretmiyor.

---

## Durum yönetimi

Grid'ler süreç ömrü boyunca bellekte tutuluyor. `POST /api/load-dem` veya `/api/load-preprocessed` ile değiştiriliyor.

Rover'a göre uyarlama her istekte `grids_for_rover` ile yapılıyor ve **temel grid'lere dokunmuyor** — [detay](../01-arazi-ve-veri/rover-katalogu-ve-grid-uyarlama.md).

---

## Kodda nerede?

```
backend/app/main.py           ← 33 uç, Pydantic modeller, hata eşlemesi
backend/app/serializer.py     ← koordinat çevirisi, cevap yapıları
backend/app/terrain.py        ← 3-D manifest, f32 transferi
backend/app/schemas.py        ← Corridor sözleşmesi
docs/BACKEND_ENVANTER.md      ← tam API envanteri
docs/backend_capabilities.json
```

---

## Jüri soruları

**S: "Kaç uç noktanız var?"**
33. On üç tanesi özellik matrisi çalışmasıyla eklendi (18'den 31'e, sonra 33). Ama sayıdan daha önemlisi: hepsi aynı çekirdeği çağırıyor, hiçbirinde planlama mantığı yok.

**S: "API cevapları ne içeriyor?"**
Sayıların yanında **nereden geldiklerini**. Her katmanın güvenilirlik etiketi hem gövdede hem `X-Layer-Validity` başlığında; maliyet formülü sürümü; risk iştahı ve eğim belirsizliğinin kaynağı; hangi kriterlerin dâhil olduğu; ve her ileri özellikte iddia sınırı metni. Bir sayıyı bağlamından ayırmak zor.

**S: "Hata durumunda ne oluyor?"**
Sessiz geri düşüş yok, bu bir ilke. Rota bulunamazsa 404 dönüyor ve **hangi kapının kaç kez kapandığını** söylüyor — mesela "229 435 geçiş termal zarf yüzünden reddedildi". Bir katman hesaplanamıyorsa `unavailable` ve sebep. RTAMT motoru istenip paket yoksa 422 — başka motora sessizce düşmüyor, çünkü hangi motorun çalıştığını bilmeden marja güvenemezsiniz.

**S: "Koordinat sistemleri nasıl yönetiliyor?"**
Üç sistem var: piksel (iç hesap), projeksiyon metresi (koridor ve ROS), coğrafi (insan arayüzü). Çeviri zinciri tek yerden geçiyor: `grid_frame.pixel_to_map_xy` sonra `serializer.pixel_to_lonlat`. Bu formül bir dönem üç ayrı dosyada kopyalanmıştı ve birinde işaret tersti.

**S: "Yedek geometri sabitleri neden var?"**
Çağıran hiç metadata vermezse diye. Ama hikâyesi öğretici: bir dönem sabit kodluydular ve yanlıştılar — üstelik yanındaki yorum türetmeyi güncelmiş gibi sunuyordu, yani grid'i anlamak için onu okuyan biri tamamen başka bir saha hakkında okuyordu. Şimdi değerler import zamanında gönderilen metadata'dan **okunuyor**; literaller yedeğin yedeği. Bu kayma, tam olarak neden okunup güvenilmedikleri sebebi.

**S: "PROJ ayarı nedir?"**
`PROJ_IGNORE_CELESTIAL_BODY=YES`. PROJ kütüphanesi varsayılan olarak gökcismi eşleşmesini zorluyor ve Ay koordinatlarını WGS84'e çevirmeyi reddediyor. Bu ayar o kontrolü geçersiz kılıyor — Ay verisiyle Dünya araçları kullanabilmek için gerekli.
