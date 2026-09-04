# Kabuk Birleştirme — Tasarım Belgesi

**Tarih:** 4 Eylül 2026
**Çalışma dalı:** `berke-3d-shell` (bu belgeyle birlikte `berke-3d`'den açılacak)
**Hedef dal:** `berke-3d`
**Kapsam:** `frontend/` mimarisi ve yerleşimi. Backend'e yalnızca chatbot dalının
zaten çakışmasız gelen `ai_*.py` dosyaları kadar dokunuluyor.

---

## Amaç

Üç dal aynı kokpiti üç ayrı mimariyle yazdı. Bu belge onları tek bir mimaride
birleştirir.

Tek cümlelik iddia: **ekranda Göktuğ'un tasarımı, altında chatbot dalının
kayıt tabanlı mimarisi, içinde her üç dalın feature'ları — ve App.tsx artık
hiçbir feature'ı tanımıyor.**

---

## Mevcut durum: üç mimari

| Dal | Yapı | Bileşenler veriyi nereden alıyor | Slot | Kayıt |
|---|---|---|---|---|
| `berke-3d-frontend` | `features/<ad>/` × 9 | Context (`useMission`, `useOverlays`) | 4, elle | yok |
| `feature/ai-decision-chatbot` | `features/<ad>/` × 1 | Context | 5, `FeatureHost` | `registry.ts` |
| `goktug/ai-scene` | `components/<Alan>/` × 15 | **Prop drilling** (her bileşende `Props`) | yok | yok |

`goktug/ai-scene`, diğer ikisinin mimarisinden hiçbirini kullanmıyor: ne slot,
ne context, ne kayıt. Buna karşılık Tailwind ekliyor, `App.css`'i 1 733 → 5 121
satıra çıkarıyor, `LandingPage` ve `SpaceBackdrop` yazıyor ve kokpiti üç moda
bölüyor: `fleet | plan | analyze`.

### Ölçülen çakışmalar

`berke-3d` (= `berke-3d-frontend`, f17d943) tabanına göre:

| Kaynak | Çakışan dosya | Cinsi |
|---|---|---|
| `goktug/ai-scene` | 3 | `package.json`, `package-lock.json`, `App.tsx` |
| `feature/ai-decision-chatbot` | 8 | 4 içerik + 4 **add/add** |

Dört `add/add` çakışmasının hepsi aynı sebepten: `berke-3d-frontend` ile
chatbot dalı **aynı dosya adlarına farklı mimari** yazmış —
`overlay/draw2d.ts`, `overlay/types.ts`, `overlay/useOverlays.ts`,
`shell/slots.tsx`.

### Çakışma üretmeyen, ondan daha tehlikeli olan

```
berke-3d-frontend :  mission/MissionContext.ts    (tipler + context + useMission)
chatbot           :  mission/MissionContext.tsx   (provider + useMission + useFocusTelemetry)
```

Farklı uzantı olduğu için git bunları ayrı dosya sayar; merge sessizce geçer,
ikisi de ağaçta kalır. Ama chatbot dalının `App.tsx:26` satırı şunu diyor:

```ts
import { MissionProvider } from './mission/MissionContext'
```

`frontend/vite.config.ts`'de `resolve.extensions` geçersiz kılınmamış, yani
Vite varsayılanı geçerli: `.mjs .js .mts .ts .jsx .tsx` — **`.ts`, `.tsx`'ten
önce.** Bu import chatbot'un provider'ı yerine `berke-3d-frontend`'in tip
dosyasını bulur, orada `MissionProvider` yoktur ve derleme, sebebi merge'de
görünmeyen bir hatayla kırılır. Faz 1'de dosya adlarının tekilleştirilmesi bu
yüzden bir temizlik işi değil, zorunluluktur.

---

## Karar: kanonik mimari `feature/ai-decision-chatbot`

Gerekçe teorik değil, dalın bugünkü acısı: **üç merge'in de ortak çakışma
dosyası `App.tsx`.** Kayıt tabanlı mimari tam olarak bunu ortadan kaldırır —
feature eklemek `App.tsx`'e dokunmaz. Dört kişi paralel dallarda çalışırken bu,
her birleştirmede kazanılan zamandır.

İki destekleyici bulgu:

1. **`berke-3d-frontend`'in 9 feature'ı zaten kayıt uyumlu.** Hiçbirine prop
   geçilmiyor — `<LayerProvenance />`, `<Replan />`, `<CostExplain />` — hepsi
   veriyi context'ten çekiyor. Chatbot'un `FeatureHost`'u da tam olarak bunu
   render ediyor: `<Component />`.
2. **Göktuğ'un yerleşimi zaten slot şeklinde.** `TopBar` altında sol ray, harita
   sahnesi, alt şerit, sağ ray ve yüzen bir asistan var. Bu, chatbot'un beş
   slot'uyla birebir örtüşüyor. Göktuğ farkında olmadan aynı iskeleti elle
   kurmuş.

### Eksik tek boyut: mod

Chatbot'un `FeatureRegistration`'ı `{ id, slot, Component }`. Göktuğ'da bir
panelin görünmesi `missionMode`'a bağlı. Kanonik sözleşme bu boyutu kazanır:

```ts
export type MissionMode = 'fleet' | 'plan' | 'analyze'

export interface FeatureRegistration {
  id: string
  slot: FeatureSlot          // leftRail | rightRail | bottomDock | canvasOverlay | globalOverlay
  Component: ComponentType
  /** Yazılmazsa: her modda görünür. */
  modes?: readonly MissionMode[]
}
```

`FeatureHost` artık slot **ve** mod'a göre filtreler; mod'u mission context'ten
okur. Göktuğ'un `missionMode === 'plan' ? … : …` koşullu JSX'i böylece
`App.tsx`'ten tamamen kalkar.

### Kalanlar ve gidenler

| Kanonik (chatbot dalından) | Silinecek (`berke-3d-frontend`'den) |
|---|---|
| `shell/slots.tsx`, `shell/FeatureHost.tsx` | `shell/slots.tsx` |
| `mission/types.ts`, `selectors.ts`, `geo.ts` ve `MissionContext.tsx`'in içeriği | `mission/MissionContext.ts`, `mission/MissionProvider.tsx` (içerik kanonikle değişir) |
| `overlay/OverlayContext.tsx`, `types.ts`, `useOverlays.ts` | `overlay/OverlayProvider.tsx`, `overlay/useOverlays.ts` |
| `features/registry.ts` (+ `modes`) | — |

**`overlay/draw2d.ts` bu kuralın istisnasıdır: `berke-3d-frontend`'inki kalır,
yalnızca kanonik tiplere göre yeniden yazılır.** Gerekçe ölçüldü:

| | `berke-3d-frontend` | chatbot |
|---|---|---|
| Dışa açılan | `drawOverlays`, `ribbonEdges`, `normaliseToDomain` | yalnızca `drawOverlayCommands` |
| Geometri | dışa açık, saf fonksiyon | private (`drawRibbon`, `sampleRamp`, …) |
| Test | `draw2d.test.ts` — 8 vaka | dalda **hiç frontend testi yok** |

Chatbot'un dosyası alınırsa NaN, tekrarlanan waypoint, dejenere segment ve düz
alan durumlarını kapsayan sekiz test silinir ve yerine gelen mantık private
olduğu için test edilemez. Bunlar koridor çizimini sessizce bozan uç
durumlardır. Kanonik olan tip sözleşmesidir, o sözleşmeyi en iyi test edilmiş
uygulama karşılar.

`goktug/ai-scene`'in `components/<Alan>/` klasörü `features/` altına taşınır ve
kayıt olur.

### Hangi asistan yaşar

| | `ai-scene` `MissionAssistant.tsx` | chatbot `features/assistant/` |
|---|---|---|
| Satır | 386 | — |
| Backend | **`fetch` yok**; `evidence` bir string literali | `POST /api/ai/chat` |
| Arka uç | — | `main.py:1626` + `ai_grounding`, `ai_evidence`, `ai_router`, `ai_tools` + testler |

Göktuğ'un asistanı görsel bir maket, chatbot'unki çalışan sistem. Sonuç:
**beyin chatbot'tan, görünüm Göktuğ'dan.** `MissionAssistant.tsx`'in mantığı
silinir, stili `ChatPanel`'e giydirilir.

---

## Dal stratejisi

```bash
git checkout -b berke-3d-shell berke-3d
git merge goktug/ai-scene
```

`berke-3d` dört kişinin dal açtığı ortak hedef. Bu migrasyonun ortasında dokuz
panel ekranda olmayacak ve tipler yarı taşınmış olacak; o ara durum ekibin
çektiği dalda duramaz. İş bitip kapılar yeşile döndüğünde `berke-3d`'ye tek ve
incelenebilir bir merge olarak iner. Ara commit'ler `berke-3d`'ye
gönderilmez.

---

## Fazlar

Her faz tek başına test edilebilir ve kendi kapısı vardır.

### Faz 0 — Kabuk iner

`berke-3d-shell` açılır, `goktug/ai-scene` merge edilir.

- `App.tsx` çakışmasında **bilinçli olarak ai-scene'inki alınır** — bu bir
  çözüm değil, karardır.
- `package.json`'da **`scripts` bloğu `berke-3d`'den aynen alınır.** ai-scene'in
  `lint` script'i `--ext ts,tsx` içeriyor; `berke-3d-frontend` ESLint 9 flat
  config'e (`eslint.config.js`) geçerken bu bayrağı bilerek atmıştı ve flat
  config'de `--ext` kaldırılmıştır. ai-scene'in satırı alınırsa `npm run lint`
  ilk çalıştırmada hata verir. ai-scene'de `test` script'i de yoktur.
- `dependencies`: ai-scene'in getirdiği `tailwindcss`, `postcss` ve
  `autoprefixer` **alınmaz.** Ölçüldü: `postcss.config.*` dosyası yok,
  `App.css`'te `@tailwind` direktifi yok, `vite.config.ts`'de postcss
  yapılandırması yok ve bileşenler tek bir Tailwind utility sınıfı bile
  kullanmıyor — yerleşimin tamamı `App.css`'teki 286 özel `lp-*` sınıfıyla
  yazılmış. Tailwind o dalda kurulu ama devre dışı; taşınacak bir altyapı yok.
  Bu bir varsayım değil, karar: Göktuğ yarım kalmış bir geçişin ortasındaysa
  bunu söylemeli, o hâlde ayrıca ele alınır.
- `package-lock.json` silinir, `npm install` ile yeniden üretilir.

**Kapı:** uygulama açılıyor; `fleet → plan → analyze` akışı çalışıyor.
`berke-3d-frontend`'in dokuz feature'ı henüz görünmüyor — bu fazın beklenen
çıktısı.

### Faz 1 — İskelet kurulur

`mission/`, `overlay/`, `shell/`, `features/registry.ts` chatbot dalından
**dosya olarak** alınır. Cherry-pick değil: o dalın `App.tsx`'i istenmiyor.

- `MissionMode` ve `modes` alanı `registry.ts`'e eklenir.
- `FeatureHost` mod filtresini kazanır.
- `mission/MissionContext.ts` çakışması dosya adı tekilleştirilerek kapatılır.
- `MissionProvider`, ai-scene'in `App.tsx`'indeki mevcut state'ten beslenir.

Bu son madde ölçüldü ve ucuz çıktı. İki dal da `berke-3d`'den dallandığı için
App seviyesindeki state isimleri neredeyse aynı:

| | Durum |
|---|---|
| Her ikisinde de var | `elevationLayer`, `selectedRoverId`, `weights`, `start`, `goal`, `planResult`, `hoverPoint`, `viewMode`, `dimension`, `focusTelemetry` |
| Yalnızca `berke-3d-frontend`'de | `rawCellTelemetry` |
| Yalnızca `ai-scene`'de | `missionMode`, `heaterW`, `payloadW`, `isSolving`, `planningEngaged`, `hudOpen`, `hudMinimized` |

`missionValue`'nun on girdisinden dokuzu ai-scene'de aynı isimle mevcut.
Taşınması gereken tek state `rawCellTelemetry` (`/api/cell-telemetry`
yanıtı).

`focusTelemetry` ayrıca doğrulandı: **`FocusTelemetry` tipi üç dalda da birebir
aynı** — `row, col, lat, lon, altitudeM, thermalC, resolutionM, spanKm`, aynı
tipler ve aynı sırayla. `berke-3d-frontend` ve `ai-scene` onu `App.tsx` içinde
yerel olarak tanımlamış, chatbot ise `mission/types.ts`'e çıkarmış. Yani
kanonik tip, üçünün de zaten yazdığı tipin taşınmış hâli; bu alanda uyarlama
gerekmiyor.

**Kapı:** uygulama görünüş olarak Faz 0'daki gibi; artık `MissionProvider` ve
`OverlayProvider` sarıyor, kayıt boş çalışıyor.

### Faz 2 — Göktuğ'un panelleri kayda geçer

ai-scene'in 15 bileşeninin hepsi feature değil. Ayrım netleştirilir:

| Kabuk olarak kalır | Feature olur (kayda geçer) |
|---|---|
| `SpaceBackdrop` (zemin) | `MissionSetupPanel` → `leftRail`, `plan` |
| `TopBar` (mod anahtarı) | `MissionSnapshotPanel` → `leftRail` |
| `MapCanvas`, `TerrainCanvas3D` (sahnenin kendisi) | `MissionContextPanel` → `rightRail` |
| `FleetSelectionView` (aşağıya bakınız) | `RouteAnalysisInspector` → `rightRail`, `analyze` |
| | `PlaybackBar` → `bottomDock`, `analyze` |
| | `LayerDropdown`, `RouteSolvingOverlay` → `canvasOverlay` |

Kabukta kalanlar prop almaya devam eder; yalnızca feature olanlar prop
drilling'den context'e geçer.

**`fleet` modu bir slot değildir.** ai-scene'de `missionMode === 'fleet'`
kokpitin tamamını `FleetSelectionView` ile değiştiriyor; bu bir raya oturmaz.
Kabuk "hangar mı, kokpit mi" kararını kendisi verir ve slot'lar yalnızca kokpit
dalının içinde bulunur. Tam ekran görünümler için `stage` diye yeni bir slot
**icat edilmez** — tek örneği olan bir soyutlama, soyutlama değildir.

Bu fazın asıl değeri, mod filtresinin gerçekten çalıştığını kanıtlamasıdır.

**Kapı:** her mod doğru panelleri gösteriyor; `App.tsx`'te ray panellerine ait
koşullu JSX kalmadı (kalan tek koşul: hangar/kokpit).

### Faz 3 — Dokuz feature taşınır

Her feature ayrı commit. Tip uyarlaması burada yapılır:

| `berke-3d-frontend` | kanonik |
|---|---|
| `PixelPoint` | `CellRef` |
| `lineWidth` | `widthPx` |
| `radius` | `radiusPx` |
| `halfWidthPx: number[]` | `halfWidthCells: number \| number[]` |

**Kapı:** feature feature; her biri kendi modunda ve rayında görünüyor.

### Faz 4 — Chatbot merge edilir

Asistan `globalOverlay` slot'una kaydolur. `MissionAssistant.tsx`'in 386
satırlık mock mantığı silinir, stili `ChatPanel`'e taşınır. Backend `ai_*.py`
dosyaları çakışmasız gelir.

Faz 1'in beklenen yan etkisi burada görünür: `overlay/` ve `shell/` dosyaları
o fazda chatbot dalından **birebir** kopyalandığı için, bu merge'de iki taraf
aynı içeriği taşır ve dört `add/add` çakışmasının hiçbiri oluşmaz. Bu, planın
doğru yürüdüğünün sınamasıdır — bu fazda `add/add` çakışması görülürse Faz 1'de
dosyalar değiştirilerek kopyalanmış demektir ve fark incelenmelidir.

**Kapı:** `/api/ai/chat` gerçek yanıt veriyor; arayüzde mock metin yok.

### Faz 5 — Temizlik

Ölü dosyalar, `TerrainView3D` / `TerrainCanvas3D` ikiliği, `App.css`
birleştirmesi.

---

## Riskler

Tehlike sırasına göre.

### 1. `hoverCell` → `selectedCell` — sessiz davranış değişikliği

Bu bir yeniden adlandırma değil. `berke-3d-frontend`'de `hoverCell` fareyle
üzerine gelinen hücre; chatbot'ta `selectedCell` seçili hücre. Farklı davranış
ve yanlış eşleme derlemeyi geçer, yalnızca davranışı bozar.

Kapsamı ölçüldü ve ilk sanıldığından çok dar çıktı. `useMission` on bir dosyada
çağrılıyor, ama anlamı değişen alanı **tek bir feature** kullanıyor:

| feature | `hoverCell` | `cellTelemetry` |
|---|---|---|
| `cost-explain` | 7 kullanım | 3 kullanım |
| diğer sekizi | 0 | 0 |

Dolayısıyla bu risk on bir dosyalık bir denetim değil, tek bir görevde verilen
tek bir karardır.

Uygulama sırasında kanonik tip okununca karar kendini yazdı. `MissionValue`'da
ne `hoverCell` ne `cellTelemetry` var ve bu bir eksiklik değil:
`MissionContext.ts`, imleci izleyen okumanın `useFocusTelemetry` ile
yayınlandığını, bir hücrenin telemetrisini isteyen feature'ın onu kendisinin
çekmesi gerektiğini yazıyor. `selectedCell` ise her zaman null — bu kokpitte
"hücre seç" diye bir kontrol yok.

Sonuç: `cost-explain`'in **davranışı korunur** (yine imlecin altındaki hücreyi
açıklar), yalnızca kaynağı değişir — konumu `useFocusTelemetry()`'den okur,
`/api/cell-telemetry`'yi kendi çağırır. `MissionValue` genişletilmez.

### 1b. Taşınmamış feature'lar derlemeyi kırar

`frontend/tsconfig.json` `"include": ["src"]` diyor: `src/` altındaki her dosya,
hiçbir yerden import edilmese bile typecheck edilir. Faz 1'de eski
`mission/MissionContext.ts` ve `overlay/OverlayProvider.tsx` silindiğinde henüz
taşınmamış dokuz feature bu dosyalara bakmaya devam edeceği için
`npm run typecheck` kırılır ve Faz 1'in kapısı hiç açılmaz.

Çözüm, Faz 1'in ilk adımıdır: dokuz feature dizini
`frontend/src/features/_pending/` altına alınır, bu yol `tsconfig.json`'a
`exclude` ve `eslint.config.js`'e `ignores` olarak eklenir. Faz 3 her feature'ı
kendi görevinde oradan çıkarır; `_pending` boşaldığında dizin ve iki
yapılandırma satırı Faz 5'te silinir.

### 2. `field` overlay komutu — performans

| | `berke-3d-frontend` | chatbot |
|---|---|---|
| Veri | `Float32Array` | `(number \| null)[]` |
| Boş hücre | `NaN` | `null` |
| Rampa | isimli (`'viridis'`, `'magma'`, …) | açık RGB durakları |

`Float32Array` → `(number|null)[]` boxing demektir; büyük grid'de ölçülebilir
yavaşlama olabilir. Sözleşmenin sahibi artık bu proje, dolayısıyla gerekirse
kanonik tip `Float32Array`'i de kabul edecek şekilde genişletilir. Faz 3'te
ölçülür; körlemesine kabul edilmez.

### 3. `CanvasOverlaySlot` konumlandırması

`berke-3d-frontend`'in slot'u içeriği
`position: absolute; inset: 0; pointer-events: none` olan bir div'e sarıyor.
Chatbot'un `FeatureHost`'u çıplak fragment döndürüyor — çünkü o dalın kaydında
hiç `canvasOverlay` feature'ı yok, bu duruma hiç girilmemiş. Sarmalayıcı geri
konmazsa harita üstü çizimler yanlış yere oturur.

### 4. `App.css` — 1 733'e karşı 5 121 satır

ai-scene'inki taban alınır; `berke-3d-frontend`'in feature CSS'leri seçilerek
taşınır, toptan değil. `lp-slot*` sınıfları için tek bir CSS kuralı yazılmamış
olduğu doğrulandı, dolayısıyla slot sarmalayıcılarının kaldırılmasının görsel
maliyeti yok.

---

## Test

`vitest` `berke-3d-frontend` ile geldi. Mevcut testler — `net/client.test.ts`,
`net/series.test.ts`, `grid/geo.test.ts`, `overlay/draw2d.test.ts` — Faz 3'te
tiplerle birlikte güncellenir. Backend `test_ai_*.py` chatbot dalından gelir ve
dokunulmaz.

Her fazın sonunda:

```bash
npm run typecheck && npm run lint && npm test
```

---

## Kapsam dışı

- Mod sistemi `fleet | plan | analyze` üçlüsünden daha genel yazılmaz.
- Dinamik veya tembel feature yükleme yok; kayıt, modül yüklenirken
  değerlendirilen düz bir dizidir.
- Rampa sistemi `colormap.ts`'in bugün sağladığından öteye genişletilmez.
- Bu belge dışındaki dallara (`cesium`, `frontend`, `goktug/ai-frontend`,
  `backend/physics`) dokunulmaz.
