# Frontend yapısı — ekip bilgilendirmesi

**Tarih:** 1 Eylül 2026 · **Branch:** `berke-3d-frontend`

Bu belge frontend'de neyi nasıl yapmaya başladığımızı anlatır. Amacı sizi bir
şeye zorlamak değil: aynı dosyalarda çakışmadan çalışabilmemiz ve yeni bir
modülü (chatbot dahil) kokpite takmanın nasıl olduğunu bilmeniz için.

Tam tasarım belgesi:
[`docs/superpowers/specs/2026-09-01-frontend-fazlar-design.md`](../superpowers/specs/2026-09-01-frontend-fazlar-design.md)

---

## 1. Ne yapıyoruz

Backend'de Faz 1–7 bitti ama frontend bu verinin çoğunu göstermiyor. Backend 18
uç yayınlıyor, `api.ts` bunların 7'sini çağırıyor. Koridor, yeniden planlama,
4B zaman ekseni, poz döngüsü, profil karşılaştırması, gerçek misyon
doğrulaması — hiçbiri ekranda yok.

Bunları **dokuz ayrı modül** olarak ekliyoruz:

| Sıra | Modül | Ne gösteriyor | Backend fazı |
|---|---|---|---|
| F0 | *(iskelet)* | Modül altyapısı — panel yok | — |
| F1 | `layer-provenance` | Her katman ölçüm mü model mi | 1 |
| F1–2 | `cost-explain` | Bu hücre neden pahalı — 4 bileşenin katkısı | 1–2 |
| F2a | `corridor` | Koridor şeridi, segment bütçeleri, sığınak noktaları | 2 |
| F2b | `replan` | 7 tetikleyici, telemetri enjeksiyonu, yeniden planlama | 2 |
| F3 | `time-axis` | Zaman kaydırıcısı, gölge animasyonu, "BEKLE" kararı | 3 |
| F7 | `pose-loop` | Poz → koridordan sapma → tetikleyici → replan | 7 |
| F5 | `profile-compare` | 4 profilin rotası ve metrikleri yan yana | 5 |
| F6 | `mission-validation` | Bizim rota ↔ Yutu-2 / Pragyan gerçek verisi | 6 |
| F4 | `ros-showcase` | ROS 2 entegrasyon vitrini (statik) | 4 |

---

## 2. Klasör düzeni

Şu an `frontend/src/` sekiz düz dosya, klasör yok. Ekleyeceğimiz yapı:

```
frontend/src/
├─ App.tsx           ← ORTAK. Faz başına ~1 satır uzuyor, içeriği taşınmıyor
├─ MapCanvas.tsx     ← ORTAK. Bir prop ekleniyor
├─ api.ts            ← ORTAK. Dokunulmuyor
├─ App.css           ← ORTAK. Dokunulmuyor
│
├─ mission/          ← paylaşılan durum, yuvalar, koordinat dönüşümü
├─ api/              ← yeni uç çağrıları, dosya başına bir uç ailesi
├─ overlay/          ← tuvale çizim sözleşmesi
└─ features/         ← HER MODÜL KENDİ KLASÖRÜ
    ├─ corridor/
    ├─ replan/
    ├─ time-axis/
    └─ ...
```

**Kilit fikir:** `features/<modül>/` klasörü tamamen o modülün sahibinindir.
Dışarıdan **yalnızca** `index.tsx` import edilir. İçini istediğiniz gibi
düzenlersiniz, kimse karışmaz.

Her modül klasörünün iskeleti:

| Dosya | Zorunlu | Ne |
|---|---|---|
| `index.tsx` | evet | Dışa açılan tek bileşen |
| `use<X>.ts` | evet | State + fetch. Modülün state'i burada, `App.tsx`'te değil |
| `<X>Panel.tsx` | evet | UI |
| `overlays.ts` | hayır | Tuvale ne çizeceği |
| `<x>.css` | hayır | Modüle özel stil, `.lp-<modül>-` ön ekiyle |

---

## 3. Yeni bir modül nasıl eklenir

Üç adım. Örnek olarak bir asistan paneli:

**1) Klasörünü aç:** `frontend/src/features/assistant/`

**2) `index.tsx` yaz:**

```tsx
import { useMission } from '../../mission/MissionContext'
import { useOverlays } from '../../overlay/useOverlays'
import { useAssistant } from './useAssistant'
import { AssistantPanel } from './AssistantPanel'
import './assistant.css'

export function Assistant() {
  const mission = useMission()          // kokpitin canlı durumu (salt okunur)
  const overlays = useOverlays()        // tuvale çizmek istersen
  const state = useAssistant(mission)   // kendi state'in, kendi fetch'lerin

  return <AssistantPanel {...state} />
}
```

**3) Bir yuvaya mount et** — `App.tsx`'te ilgili yuvaya tek satır:

```tsx
<RightRailSlot>
  <Assistant />
</RightRailSlot>
```

Bu kadar. Modülünüz kokpitin canlı durumunu okur, kendi ağ isteklerini kendisi
yapar, `App.tsx`'e hiçbir state eklemez.

### Dört yuva

| Yuva | Nerede |
|---|---|
| `<LeftRailSlot>` | Sol ray, mevcut kontrol bölümlerinin altında |
| `<RightRailSlot>` | Sağ ray, Mission Snapshot panelinin altında |
| `<BottomDock>` | Tuvalin altındaki şerit (zaman ekseni burada) |
| `<CanvasOverlaySlot>` | Tuvalin üstünde mutlak konumlu HUD katmanı |

---

## 4. `MissionContext` — okuyabileceğiniz canlı durum

`useMission()` size kokpitin o anki durumunu verir. Hepsi salt okunur:

```ts
{
  gridMeta:      { rows, cols, resolutionM } | null   // grid geometrisi
  roverId:       string                                // aktif rover
  weights:       { w_slope, w_energy, w_shadow, w_thermal }
  start:         [row, col] | null                     // seçili başlangıç
  goal:          [row, col] | null                     // seçili hedef
  planResult:    PlanResponse | null                   // son planın TAM yanıtı
  selectedCell:  [row, col] | null                     // kullanıcının tıkladığı hücre
  cellTelemetry: CellTelemetryResponse | null          // o hücrenin HAM telemetrisi
  activeLayer:   'surface' | 'thermal' | 'cost' | 'shadow'
               | 'traversability' | 'slope' | 'aspect'
  dimension:     '2d' | '3d'
}
```

Ayrıca iki eylem: `setStart(cell)` ve `setGoal(cell)`.

`planResult` ve `cellTelemetry` **ham backend yanıtlarıdır**, kırpılmamıştır —
`corridor`, `route_statistics`, `execution`, `cost_breakdown`, `layer_validity`
hepsi içindedir. Yani bir modül aynı veriyi ikinci kez çekmek zorunda değil.

Buraya yeni alan eklemek mümkün ama önce konuşalım: `MissionContext`
`App.tsx`'in *zaten sahip olduğu* değerleri yayınlar, yeni state için depo
değildir. Modülünüzün kendi state'i kendi hook'unda kalmalı.

---

## 5. Tuvale çizim

`MapCanvas.tsx`'e doğrudan dokunulmaz. Bunun yerine overlay kaydedilir:

```ts
const overlays = useOverlays()
overlays.register('assistant-highlight', [
  { kind: 'points', id: 'hit', points: [{ row: 120, col: 340 }], style: { color: '#38bdf8' } },
])
```

Dört overlay türü var: `polyline` (rota), `ribbon` (koridor gibi değişken
genişlikli şerit), `points` (işaretler), `field` (tüm grid'i boyayan skaler
alan).

**Tek kural:** koordinatlar her zaman **fine grid pikseli** (`{row, col}`).
CRS metresi veya coarse piksel varsa `mission/geo.ts` ile çevirin — o dönüşümün
tek kaynağı orası.

Bunun sebebi: aynı overlay listesi ileride 3B sahneye de beslenecek. Sözleşmeye
uyan bir modül, 3B'ye geçildiğinde hiç değişmeyecek.

---

## 6. Çakışmayı önleme kuralları

Dört dosya ortak, gerisi serbest:

| Dosya | Kural |
|---|---|
| `App.tsx` | Faz/modül başına birkaç satır. Değişiklik **ayrı bir commit** olsun, içine başka iş karışmasın |
| `MapCanvas.tsx` | Sadece overlay prop'u üzerinden. Yeni çizim kodu buraya yazılmaz, `overlay/draw2d.ts`'e yazılır |
| `api.ts` | Dokunulmuyor. Yeni uçlar `api/` klasöründe ayrı dosyalara |
| `App.css` | Dokunulmuyor. Modül stili `features/<modül>/<x>.css` içinde, `.lp-<modül>-` ön ekiyle |

`features/<sizin-modülünüz>/` altındaki her şey sizindir — kimse dokunmaz,
review'da da içine karışılmaz.

---

## 7. Bilmeniz gereken tuzaklar

Backend'e bağlanırken kaynaktan doğruladığımız şeyler:

- **`astar_metrics.total_energy_wh` ve `total_shadow_hours` her zaman `null`.**
  (`pathfinder.py:734-735`) Gerçek enerji `summary.total_energy_consumed_wh`,
  gerçek gölge `summary.total_shadow_exposure` /
  `summary.max_continuous_shadow_h`. Mevcut `api.ts` bunları yanlış tipliyor.
- **Maliyet bileşeni `shadow`, grid katmanı `shadow_ratio`.** Aynı şey değiller.
- **`cost_breakdown`'da `null` = GEÇİLEMEZ**, "veri yok" değil. Sonsuz maliyet
  JSON'a `null` olarak yazılıyor.
- **`plan-4d`'de `path_pixels` fine grid, `path_pixels_coarse` coarse grid.**
  Çizerken `path_pixels` kullanın.
- **`corridor.waypoints` CRS metresi**, piksel değil.
- **Katmanları `format=f32` ile çekin.** JSON yolunda 65 536 hücre tavanı var,
  ikili yolda yok — ve 500×500 float32 sadece 1 MB.
- **Zaman serisi ufuk önbelleği ister.** Yoksa `shadow_model.model === "static"`
  döner ve animasyon anlamsızdır. Bir kez:
  `python scripts/build_horizon_cache.py`
- **`backend/data/scenarios/` şu an boş**, yani `/api/scenarios` boş liste döner.

Daha uzun liste tasarım belgesinin "Tuzaklar" bölümünde.

---

## 8. Dürüstlük kuralları

Backend'in `validity` etiketi disiplinini frontend'de de sürdürüyoruz. Yeni bir
modül yazarken bunlara uymanızı rica ederiz:

1. `UNCALIBRATED` / `SYNTHETIC` etiketli bir sayı etiketsiz gösterilmez.
2. Değerlendirilemeyen bir kontrol "temiz" gösterilmez (`skipped` görünür kalır).
3. `null` bir sayı 0 olarak çizilmez.
4. Statik bir model animasyonluymuş gibi sunulmaz.

---

## 9. Sonra yapılacaklar

- **rosbridge ile canlı ROS 2 bağlantısı.** Şu an `lunapath_ros` içinde
  rosbridge/websocket yok, yani ROS 2'nin frontend'e açılan bir yüzeyi yok.
  Bu yüzden Faz 4 şimdilik **statik vitrin** olarak gösteriliyor: `grid_map`
  katmanları, `PlanTraverse` action arayüzü, `rosbag2` kaydı, Nav2 baseline
  tablosu, RViz görseli — canlı bağlantı iddiası yok. rosbridge eklenirse
  vitrin canlı veriye bağlanabilir.
- **3B overlay çizimi (`draw3d.ts`).** Sözleşme kuruluyor, uygulaması sonra.
  Modüller değişmeyecek.
- **`App.tsx` refactor'ü.** Dokuz modül bittikten sonra ayrı bir karar olarak
  ele alınacak. Şimdilik `App.tsx` bugünkü haliyle duruyor.
