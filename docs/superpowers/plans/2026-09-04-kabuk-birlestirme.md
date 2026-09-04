# Kabuk Birleştirme — Uygulama Planı

> **Ajan işçiler için:** ZORUNLU ALT BECERİ: Bu planı görev görev uygulamak için
> `superpowers:subagent-driven-development` (önerilen) veya
> `superpowers:executing-plans` kullanın. Adımlar takip için onay kutusu
> (`- [ ]`) sözdizimi kullanır.

**Hedef:** Üç frontend dalını (`berke-3d-frontend`, `feature/ai-decision-chatbot`,
`goktug/ai-scene`) tek bir kayıt tabanlı mimaride birleştirmek; ekranda Göktuğ'un
tasarımı, altında chatbot dalının registry'si, içinde her üç dalın feature'ları.

**Mimari:** Göktuğ'un yerleşimi kabuk olarak alınır. Chatbot dalının
`shell/` + `features/registry.ts` + `mission/` + `overlay/` sözleşmesi kanonik
kabul edilir ve bir **mod** boyutuyla genişletilir. Paneller `App.tsx`'te elle
mount edilmek yerine kayda yazılır; `App.tsx` artık hiçbir feature'ı tanımaz.

**Teknoloji:** React 18, TypeScript 5.3 (strict), Vite 5, Vitest 2.1.9,
ESLint 9 (flat config), three.js.

**Spec:** `docs/superpowers/specs/2026-09-04-kabuk-birlestirme-design.md`

## Devir Durumu — 4 Eylül 2026

Bu bölüm planı devralan için. Geri kalan her şey ilk yazıldığı gibi, **aşağıda
sayılan düzeltmeler uygulanmış** hâlde.

**Dal:** `berke-3d-shell`. `berke-3d` `f17d943`'te ve bu iş boyunca hiç
değişmedi; birleşme Task 25'te, tek merge olarak.

**Biten:** Task 1–8 ve Task 7b. `git log --oneline f17d943..HEAD` hepsini
gösterir; her görev tek commit ve commit mesajı o görevde ne sapıldığını yazar.

**Kapı:** `cd frontend && npm run typecheck && npm run lint && npm test`.
Üçü de geçmeden commit yok. Şu an 35 test, 5 dosya.

**Uygulamayı çalıştırma:** `cd backend && python -m uvicorn app.main:app --port 8000`
ve `cd frontend && npm run dev`. `http://localhost:3000/?app` landing'i atlayıp
doğrudan hangara girer — tarayıcıda doğrulama yaparken bunu kullan.

### Uygulama sırasında bulunan ve plana işlenen düzeltmeler

| Bulgu | Etkisi |
|---|---|
| `Cell` bir demet, obje değil | Task 18–20'deki 39 `start`/`goal` dönüşümü iptal |
| `MissionValue`'da `hoverCell`/`cellTelemetry` bilerek yok | Task 21 feature'ın kendi telemetrisini çekmesine döndü |
| Chatbot'un context dosyaları lint'ten geçmiyor | `MissionContext` ve `OverlayContext` ikiye bölündü |
| Kanonik sözleşme salt okunur | Task 7b eklendi: ayrı `MissionActions` context'i |
| `draw2d.ts` bizde kalıyor | `sampleRamp` eklendi, 5 yeni test |

### Devralanın bilmesi gereken üç şey

1. **Her panelin modunu `App.tsx`'ten oku, varsayma.** Task 8'de az kalsın
   sessiz bir hata gitti: panel mod'suz kaydedilirse `plan` modunda da görünür.
   `App.tsx`'teki koşullu JSX hangi modda render ettiğini söyler; kayıt satırı
   onu birebir yansıtmalı.
2. **Chatbot dalından alınan her `.tsx`, bileşen + başka bir şey dışa açıyorsa
   lint'i kırar.** Çözüm bölmek, kuralı kapatmak değil. İki örneği var.
3. **`MissionValue`'ya alan eklerken gerekçesini yaz.** Sözleşmeyi peşin
   şişirme; her panel kendi görevinde ihtiyacı olanı ekler.

---

## Global Kısıtlar

Her görevin gereksinimleri örtük olarak bu bölümü içerir.

- **Dal:** tüm çalışma `berke-3d-shell` üzerinde. `berke-3d`'ye tek bir ara
  commit gitmez; birleşme, tüm fazlar bittikten sonra tek merge'dir.
- **Kapı:** her görevin son adımından önce, `frontend/` dizininde:
  `npm run typecheck && npm run lint && npm test` — üçü de geçmeden commit yok.
- **`scripts` bloğu `berke-3d`'den alınır.** `lint` script'ine `--ext ts,tsx`
  **asla** eklenmez: ESLint 9 flat config'de bu bayrak kaldırılmıştır.
- **`tailwindcss`, `postcss`, `autoprefixer` bağımlılıkları alınmaz.**
  `goktug/ai-scene`'de Tailwind kurulu ama devre dışıdır (postcss config yok,
  `@tailwind` direktifi yok, tek bir utility sınıfı kullanılmıyor).
- **Koordinat birimi:** her overlay komutunda ince ızgara `CellRef { row, col }`.
  CRS metresi veya tuval pikseli tutan bir feature, kaydolmadan önce
  `mission/geo.ts` üzerinden dönüştürür.
- **Test yazma kuralı:** bu repoda `jsdom` ve `@testing-library/react` **yok**.
  Bileşen render testi yazılamaz. Test edilebilir olan saf mantık saf fonksiyona
  çıkarılır ve Vitest ile test edilir; render doğrulaması `npm run dev` ile
  gözle yapılır ve görevin kapısında bu açıkça belirtilir.
- **Commit mesajları** İngilizce, repo konvansiyonuna uygun.

---

## Dosya Yapısı

Faz 5 sonunda `frontend/src/` hedefi:

```
src/
  App.tsx                 kabuk: SpaceBackdrop, TopBar, sahne, 5 slot. Feature tanımaz.
  App.css                 ai-scene'in 286 lp-* sınıfı + taşınan feature stilleri
  MapCanvas.tsx           2B tuval; overlay komutlarını çizer
  TerrainCanvas3D.tsx     three.js 3B arazi
  LandingPage.tsx         giriş ekranı
  SpaceBackdrop.tsx       zemin
  colormap.ts             renk rampaları

  shell/
    slots.tsx             5 slot, prop almaz          [chatbot'tan]
    FeatureHost.tsx       slot + mod filtresi          [chatbot'tan, mod eklenir]
    shell.css                                          [chatbot'tan]

  features/
    registry.ts           FEATURES dizisi + selectFeatures()  [chatbot'tan, genişletilir]
    registry.test.ts      selectFeatures birim testleri        [YENİ]
    assistant/            chatbot'un asistanı, /api/ai/chat'e bağlı
    <göktuğ'un 7 paneli>/
    <senin 9 feature'ın>/

  mission/
    MissionContext.tsx    provider + useMission + useFocusTelemetry  [chatbot'tan]
    types.ts              MissionValue, CellRef, GridMeta, FocusTelemetry, MissionMode
    selectors.ts                                       [chatbot'tan]
    geo.ts                koordinat dönüşümleri        [chatbot'tan]

  overlay/
    OverlayContext.tsx    Registry + Commands context  [chatbot'tan]
    types.ts              OverlayCommand ailesi        [chatbot'tan]
    useOverlays.ts                                     [chatbot'tan]
    draw2d.ts             KENDİ dosyamız, kanonik tiplere göre yeniden yazılır
    draw2d.test.ts        8 vakalık mevcut test, korunur

  net/                    senin API istemcin (client, plan4d, series, replan, …)
  grid/geo.ts             piksel/hücre dönüşümleri
```

`mission/MissionContext.ts`, `mission/MissionProvider.tsx` ve
`overlay/OverlayProvider.tsx` silinir. `features/_pending/` yalnızca Faz 1–3
arasında var olur ve Faz 5'te kaldırılır.

---

## Faz 0 — Kabuk iner

### Task 1: `goktug/ai-scene`'i birleştir ve yapı araçlarını uzlaştır

**Dosyalar:**
- Değiştir: `frontend/package.json`
- Çakışma çöz: `frontend/src/App.tsx` (ai-scene'inki alınır)
- Sil: `frontend/tailwind.config.js`
- Yeniden üret: `frontend/package-lock.json`

**Arayüzler:**
- Üretir: `MissionMode` tipini taşıyan `components/TopBar/TopBar.tsx`
  (`export type MissionMode = 'fleet' | 'plan' | 'analyze'`), Task 5 bunu
  `mission/types.ts`'e taşıyacak.

- [ ] **Adım 1: Dalda olduğunu doğrula ve merge'i başlat**

```bash
git rev-parse --abbrev-ref HEAD    # berke-3d-shell olmalı
git merge goktug/ai-scene
```

Beklenen: `package.json`, `package-lock.json`, `src/App.tsx` üçünde çakışma.

- [ ] **Adım 2: `App.tsx`'i ai-scene'inkiyle değiştir**

Bu bir çakışma çözümü değil, karardır: Göktuğ'un yerleşimi yeni kabuktur.

```bash
git checkout --theirs frontend/src/App.tsx
git add frontend/src/App.tsx
```

- [ ] **Adım 3: `package.json`'ı elle yaz**

`scripts` bloğu `berke-3d`'den aynen; `dependencies`'e ai-scene'in eklediği
üç paket **alınmaz**.

```json
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "lint": "eslint . --report-unused-disable-directives --max-warnings 0",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "test:watch": "vitest"
  },
```

`devDependencies` `berke-3d`'ninki olarak kalır:
`@eslint/js ^9.39.5`, `@types/react ^18.2.0`, `@types/react-dom ^18.2.0`,
`@types/three ^0.183.1`, `@vitejs/plugin-react ^4.2.0`, `eslint ^9.39.5`,
`eslint-plugin-react-hooks ^7.1.1`, `eslint-plugin-react-refresh ^0.5.6`,
`globals ^17.12.0`, `typescript ^5.3.0`, `typescript-eslint ^8.69.0`,
`vite ^5.0.0`, `vitest 2.1.9`.

`tailwindcss`, `postcss`, `autoprefixer` **eklenmez**.

- [ ] **Adım 4: Ölü Tailwind yapılandırmasını sil**

```bash
git rm frontend/tailwind.config.js
```

- [ ] **Adım 5: Kilidi yeniden üret**

```bash
rm frontend/package-lock.json
cd frontend && npm install
```

- [ ] **Adım 6: Kapı — üç kontrol**

```bash
cd frontend && npm run typecheck && npm run lint && npm test
```

Beklenen: üçü de geçer. `typecheck` kırılırsa en olası sebep, birleşen
`MapCanvas.tsx`'in iki daldan gelen overlay API'lerinden birine bakıyor
olmasıdır; o dosyanın `import` satırları `berke-3d-shell`'deki
`overlay/useOverlays.ts`'e bakmalıdır (Faz 1 bunu kanonikleştirecek).

- [ ] **Adım 7: Uygulamayı gözle doğrula**

```bash
cd frontend && npm run dev
```

`http://localhost:3000` açılır. Beklenen: LandingPage görünür; TopBar'dan
`fleet → plan → analyze` geçişleri çalışır. `berke-3d-frontend`'in dokuz
feature'ı **görünmez** — bu fazın beklenen çıktısıdır, hata değildir.

- [ ] **Adım 8: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
merge: take ai-scene's cockpit as the shell

App.tsx, App.css and the components/ tree come from goktug/ai-scene: its
layout is the agreed face of the merged product. The nine feature modules
from berke-3d-frontend are still on disk but no longer mounted; Phase 3
puts them back through the registry.

The scripts block stays berke-3d's. ai-scene's lint script carries
--ext ts,tsx, which ESLint 9 removed with flat config, and it has no test
script at all. Tailwind is dropped rather than merged: ai-scene declares it
but wires nothing -- no postcss config, no @tailwind directive, and not one
utility class in the components.
EOF
)"
```

---

## Faz 1 — İskelet kurulur

### Task 2: Taşınmamış dokuz feature'ı park et

`tsconfig.json` `"include": ["src"]` diyor: `src/` altındaki her dosya, hiçbir
yerden import edilmese bile typecheck edilir. Task 3 eski `mission/` ve
`overlay/` dosyalarını sileceği için, o dosyalara bakan dokuz feature önce
derleme kapsamından çıkarılmalıdır. Yoksa Faz 1'in kapısı hiç açılmaz.

**Dosyalar:**
- Değiştir: `frontend/tsconfig.json`, `frontend/eslint.config.js`
- Taşı: `frontend/src/features/{corridor,cost-explain,layer-provenance,mission-validation,pose-loop,profile-compare,replan,ros-showcase,time-axis}` → `frontend/src/features/_pending/` altına

**Arayüzler:**
- Üretir: `src/features/_pending/` — Task 14–21 her feature'ı buradan çıkarır;
  Task 24 dizin boşalınca yapılandırma satırlarını siler.

- [ ] **Adım 1: Dokuz dizini taşı**

```bash
cd frontend/src/features
mkdir _pending
git mv corridor cost-explain layer-provenance mission-validation pose-loop \
       profile-compare replan ros-showcase time-axis _pending/
```

- [ ] **Adım 2: `tsconfig.json`'a `exclude` ekle**

`"include": ["src"]` satırının hemen ardına:

```json
  "include": ["src"],
  "exclude": ["src/features/_pending"]
```

- [ ] **Adım 3: `eslint.config.js`'in ignores listesine ekle**

```js
  { ignores: ['dist', 'node_modules', 'public', 'src/features/_pending'] },
```

- [ ] **Adım 4: Kapı**

```bash
cd frontend && npm run typecheck && npm run lint && npm test
```

Beklenen: üçü de geçer. `_pending` altındaki dosyalar artık ne derleniyor ne
lint ediliyor.

- [ ] **Adım 5: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
chore: park the nine unmigrated features outside the build

tsconfig includes all of src, so files nothing imports are still
type-checked. The next commit deletes the old mission and overlay modules,
which these nine still import; parking them keeps the typecheck gate
meaningful until Phase 3 migrates them one at a time.
EOF
)"
```

### Task 3: Kanonik `mission/` sözleşmesini benimse

**Dosyalar:**
- Oluştur: `frontend/src/mission/types.ts`, `selectors.ts`, `geo.ts` (chatbot dalından birebir)
- Oluştur: `frontend/src/mission/MissionContext.ts` — iki context + `useMission` + `useFocusTelemetry`
- Oluştur: `frontend/src/mission/MissionProvider.tsx` — yalnızca provider bileşeni
- Sil: eski `MissionContext.ts` ve `MissionProvider.tsx` içerikleri (dosya adları
  kalır, içerikleri kanonikle değişir)

**Dosya düzeni chatbot dalınınkinden neden ayrılıyor.** O dalda provider ve iki
hook tek bir `MissionContext.tsx`'te duruyor. Bu projede lint bunu geçirmiyor:
`react-refresh/only-export-components`, bir modül hem bileşen hem başka bir şey
dışa açtığında Fast Refresh'in o modül için bozulduğunu söylüyor ve
`--max-warnings 0` altında bu bir hatadır. `berke-3d-frontend` aynı ayrımı
bağımsız olarak zaten yapmıştı — chatbot dalında flat config olmadığı için orada
uyarı hiç görülmedi. Kanonik olan sözleşmedir; dosya düzeni kendi araçlarımızın
gerekçeli tercihidir. Task 4'teki `draw2d.ts` istisnasıyla aynı mantık.

**Arayüzler:**
- Üretir: `MissionValue`, `CellRef { row: number; col: number }`, `GridMeta`,
  `FocusTelemetry`, `MissionProvider`, `useMission(): MissionValue`,
  `useFocusTelemetry(): FocusTelemetry`. Task 7 provider'ı mount eder;
  Task 14–21 `useMission`'ı tüketir.

- [ ] **Adım 1: Dört dosyayı chatbot dalından al**

Cherry-pick değil — o dalın `App.tsx`'i istenmiyor, yalnızca bu dosyalar.

```bash
git checkout origin/feature/ai-decision-chatbot -- \
  frontend/src/mission/MissionContext.tsx \
  frontend/src/mission/types.ts \
  frontend/src/mission/selectors.ts \
  frontend/src/mission/geo.ts
```

- [ ] **Adım 2: Eski iki dosyayı sil**

`MissionContext.ts` ile `MissionContext.tsx`'in yan yana durması Vite'ın
çözümleme sırası (`.ts` önce `.tsx` sonra) yüzünden derlemeyi kırar; bu silme
bir temizlik değil, zorunluluktur.

```bash
git rm frontend/src/mission/MissionContext.ts frontend/src/mission/MissionProvider.tsx
```

- [ ] **Adım 3: `MissionMode`'u `types.ts`'e taşı**

`components/TopBar/TopBar.tsx` bugün `MissionMode`'u kendisi tanımlıyor. Kayıt
bu tipe bağımlı olacağı için tipin sahibi mission katmanı olmalı.
`frontend/src/mission/types.ts` sonuna:

```ts
/**
 * Kokpitin hangi aşamada olduğunu söyleyen üçlü.
 *
 * Bir feature'ın hangi modlarda görüneceğini registry belirler; `TopBar` bu
 * değeri yalnızca değiştirir, tanımlamaz.
 */
export type MissionMode = 'fleet' | 'plan' | 'analyze'
```

- [ ] **Adım 4: `TopBar`'ı yeni kaynağa bağla**

`frontend/src/components/TopBar/TopBar.tsx` içindeki yerel
`export type MissionMode = …` satırı silinir, yerine:

```ts
import type { MissionMode } from '../../mission/types'
export type { MissionMode }
```

`export type { MissionMode }` satırı bilerek bırakılıyor: `App.tsx` bugün tipi
`TopBar`'dan alıyor ve o import Task 7'ye kadar çalışmaya devam etmeli.

- [ ] **Adım 5: Kapı**

```bash
cd frontend && npm run typecheck && npm run lint && npm test
```

Beklenen: geçer. `mission/` dosyalarını henüz kimse import etmiyor;
`MissionMode` yeni yerinden okunuyor.

- [ ] **Adım 6: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat(mission): adopt the chatbot branch's mission contract

MissionContext.tsx, types.ts, selectors.ts and geo.ts come over verbatim
and become canonical. The old MissionContext.ts and MissionProvider.tsx go:
leaving MissionContext.ts beside MissionContext.tsx would break the build,
because Vite resolves .ts before .tsx and the type-only file exports no
provider.

MissionMode moves out of TopBar and into mission/types.ts. The registry will
key feature visibility off it, so the mission layer owns it, not a component.
EOF
)"
```

### Task 4: Kanonik `overlay/` sözleşmesini benimse, `draw2d`'yi koru

Spec'in tek istisnası burada: tip sözleşmesi chatbot'tan, çizim uygulaması
bizden. `berke-3d-shell`'in `draw2d.ts`'i üç saf fonksiyon dışa açıyor ve
sekiz vakalık bir testi var; chatbot'unki geometrisini private tutuyor ve o
dalda hiç frontend testi yok.

**Dosyalar:**
- Üzerine yaz: `frontend/src/overlay/types.ts`, `frontend/src/overlay/useOverlays.ts` (chatbot'tan)
- Oluştur: `frontend/src/overlay/OverlayContext.ts` — context'ler + `EMPTY_COMMANDS` + `OverlayRegistry`
- Oluştur: `frontend/src/overlay/OverlayProvider.tsx` — yalnızca provider bileşeni
- Değiştir: `frontend/src/overlay/draw2d.ts` (kendi dosyamız, yeni tiplere göre)
- Değiştir: `frontend/src/overlay/draw2d.test.ts`
- Değiştir: `frontend/src/MapCanvas.tsx` — `OverlayLayer` → `readonly OverlayCommand[]`, 3 yerde

`MapCanvas` bu listede çünkü `drawOverlays`'in tek çağıranı o ve `overlays`
prop'unu taşıyor; planın ilk sürümü onu atlamıştı.

Chatbot'un `OverlayContext.tsx`'i de Task 3'teki `MissionContext.tsx` ile aynı
sebepten ikiye ayrılıyor: hem `OverlayProvider` bileşenini hem context'leri
dışa açıyor ve `react-refresh/only-export-components` bunu geçirmiyor.

**Arayüzler:**
- Üretir: `OverlayCommand` (`PolylineCommand | RibbonCommand | PointsCommand | FieldCommand`),
  `OverlayStyle { color; opacity?; widthPx?; dash?; radiusPx? }`,
  `OverlayProvider`, `useOverlays(): OverlayRegistry`,
  `useOverlayCommands(): readonly OverlayCommand[]`,
  ve `draw2d.ts`'ten `drawOverlays`, `ribbonEdges`, `normaliseToDomain`.

- [ ] **Adım 1: Üç dosyayı chatbot dalından al**

```bash
git checkout origin/feature/ai-decision-chatbot -- \
  frontend/src/overlay/OverlayContext.tsx \
  frontend/src/overlay/types.ts \
  frontend/src/overlay/useOverlays.ts
git rm frontend/src/overlay/OverlayProvider.tsx
```

- [ ] **Adım 2: Testi yeni tiplere göre yaz (önce test)**

`frontend/src/overlay/draw2d.test.ts` başındaki import ve fixture, `PixelPoint`
yerine `CellRef` kullanacak şekilde değişir. Geri kalan sekiz vaka aynen kalır —
davranış değişmiyor, yalnızca tipin adı değişiyor.

```ts
import { describe, expect, it } from 'vitest'
import { normaliseToDomain, ribbonEdges } from './draw2d'
import type { CellRef } from '../mission/types'

// A straight run east: col increases, row does not. The perpendicular is
// therefore purely in row, which makes every offset readable by eye.
const EAST: CellRef[] = [
  { row: 10, col: 0 },
  { row: 10, col: 1 },
  { row: 10, col: 2 },
]
```

- [ ] **Adım 3: Testi çalıştır, kırıldığını gör**

```bash
cd frontend && npm test -- draw2d
```

Beklenen: FAIL — `draw2d.ts` hâlâ `PixelPoint` bekliyor, tip uyuşmuyor.

- [ ] **Adım 4: `draw2d.ts`'i kanonik tiplere göre yeniden yaz**

Değişiklik mekaniktir; geometri mantığına dokunulmaz.

| eski | yeni |
|---|---|
| `import type { OverlayLayer, PixelPoint, OverlayStyle } from './types'` | `import type { OverlayCommand, OverlayStyle } from './types'` ve `import type { CellRef } from '../mission/types'` |
| `PixelPoint` | `CellRef` |
| `OverlayLayer` | `OverlayCommand` |
| `style.lineWidth` | `style.widthPx` |
| `style.radius` | `style.radiusPx` |
| `layer.halfWidthPx: number[]` | `command.halfWidthCells: number \| number[]` |
| `layer.data: Float32Array` + `domain` + `ramp: RampName` | `command.values: (number \| null)[]` + `command.ramp: FieldRamp` |

`halfWidthCells` skaler de olabildiği için `ribbonEdges`'in girişi normalize
edilir:

```ts
/**
 * Tek genişlik verildiyse her merkez noktası için tekrarlanır.
 *
 * Ayrı bir adım olarak duruyor çünkü ribbonEdges'in kendisi dizi bekliyor ve
 * o testlerin kapsadığı hâli; normalizasyonu çağrı yerine koymak sekiz vakayı
 * yeniden yazmayı gerektirirdi.
 */
function widthsFor(command: RibbonCommand): number[] {
  const { halfWidthCells, points } = command
  return typeof halfWidthCells === 'number'
    ? new Array(points.length).fill(halfWidthCells)
    : halfWidthCells
}
```

`normaliseToDomain` bugün `NaN` için `null` döndürüyor; kanonik `FieldCommand`
boş hücreyi `null` ile gösterdiği için çağrı yeri `NaN` yerine `null`
kontrolü yapar, fonksiyonun kendisi ve testleri değişmez.

**Yeni saf fonksiyon: `sampleRamp`.** Eski sözleşme dört isimli rampa taşıyordu
(`'viridis'`, `'magma'`, …) ve `draw2d` onları `colormap.ts`'ten çağırıyordu.
Kanonik `FieldCommand` bunun yerine kendi RGB duraklarını getiriyor, dolayısıyla
normalize edilmiş değer ile piksel arasında duran tek şey durakları örnekleyen
fonksiyon oluyor. Bu dosyanın kuralı gereği dışa açık ve saf yazılır — yanlış
olduğu her hâlde makul bir resim çizer: ters duraklar okumayı tersine çevirir,
bant indeksindeki bir kayma her rengi bir basamak öteler, yuvarlama atlanırsa
Canvas kesirli kanalı kırpar ve katmanın tamamı bir birim koyu okunur. Beş
vakayla test edilir; chatbot dalında bu mantık private ve testsizdi.

- [ ] **Adım 5: Testi çalıştır, geçtiğini gör**

```bash
cd frontend && npm test -- draw2d
```

Beklenen: sekiz vakanın tamamı PASS.

- [ ] **Adım 6: Kapı**

```bash
cd frontend && npm run typecheck && npm run lint && npm test
```

- [ ] **Adım 7: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat(overlay): adopt the canonical command types, keep our renderer

types.ts, OverlayContext.tsx and useOverlays.ts come from the chatbot
branch and become canonical. draw2d.ts does not: ours exports drawOverlays,
ribbonEdges and normaliseToDomain as pure functions with eight tests covering
NaN, repeated waypoints, degenerate segments and flat fields, while the
chatbot branch keeps that geometry private and ships no frontend tests at
all. The contract is what we adopt; the best-tested implementation of it
is what we keep.

Retyping is mechanical: PixelPoint becomes CellRef, lineWidth becomes
widthPx, radius becomes radiusPx, and a ribbon's scalar half-width is
expanded before it reaches ribbonEdges so the nine cases stay untouched.
EOF
)"
```

### Task 5: Kayda mod boyutunu ekle ve seçimi test et

Kaydın tek yeni mantığı budur ve saf bir fonksiyona çıkarıldığı için bu
repodaki test altyapısıyla (jsdom yok) gerçekten test edilebilir.

**Dosyalar:**
- Oluştur: `frontend/src/features/registry.ts`
- Oluştur: `frontend/src/features/registry.test.ts`

Planın ilk sürümü dosyanın var olduğunu varsayıyordu; yok. Chatbot'unki de
olduğu gibi alınamaz, çünkü `features/assistant`'ı import ediyor ve o dizin
Task 22'ye kadar gelmiyor. Dolayısıyla dosya buradan doğuyor: slot tipi ve
yorumları o daldan, `FEATURES` **boş** bir dizi olarak. Her feature kendi
görevinde kendi kaydını ekler — görevlerin tek tek incelenebilir olmasının
sebebi de bu.

**Arayüzler:**
- Üretir: `FeatureSlot`, `FeatureRegistration { id; slot; Component; modes? }`,
  `FEATURES: readonly FeatureRegistration[]`,
  `selectFeatures(features, slot, mode): readonly FeatureRegistration[]`.
  Task 6 `selectFeatures`'ı çağırır; Task 8–21 `FEATURES`'a kayıt ekler.

- [ ] **Adım 1: Başarısız testi yaz**

`frontend/src/features/registry.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { selectFeatures, type FeatureRegistration, type FeatureSlot } from './registry'
import type { MissionMode } from '../mission/types'

const Stub = () => null

function entry(
  id: string,
  slot: FeatureSlot,
  modes?: readonly MissionMode[],
): FeatureRegistration {
  return { id, slot, Component: Stub, modes }
}

describe('selectFeatures', () => {
  it('keeps only the asked-for slot', () => {
    const features = [entry('a', 'leftRail'), entry('b', 'rightRail')]
    expect(selectFeatures(features, 'leftRail', 'plan').map((f) => f.id)).toEqual(['a'])
  })

  it('treats a missing modes list as every mode', () => {
    const features = [entry('always', 'bottomDock')]
    for (const mode of ['fleet', 'plan', 'analyze'] as const) {
      expect(selectFeatures(features, 'bottomDock', mode).map((f) => f.id)).toEqual(['always'])
    }
  })

  it('drops a feature whose modes exclude the current one', () => {
    const features = [entry('analyseOnly', 'bottomDock', ['analyze'])]
    expect(selectFeatures(features, 'bottomDock', 'plan')).toEqual([])
    expect(selectFeatures(features, 'bottomDock', 'analyze').map((f) => f.id)).toEqual([
      'analyseOnly',
    ])
  })

  it('preserves registration order within a slot', () => {
    const features = [
      entry('first', 'rightRail'),
      entry('second', 'rightRail'),
      entry('third', 'rightRail'),
    ]
    expect(selectFeatures(features, 'rightRail', 'plan').map((f) => f.id)).toEqual([
      'first',
      'second',
      'third',
    ])
  })

  it('returns an empty list for a slot nothing registered', () => {
    expect(selectFeatures([entry('a', 'leftRail')], 'canvasOverlay', 'plan')).toEqual([])
  })
})
```

- [ ] **Adım 2: Testi çalıştır, kırıldığını gör**

```bash
cd frontend && npm test -- registry
```

Beklenen: FAIL — `selectFeatures` dışa açılmamış.

- [ ] **Adım 3: `registry.ts`'i genişlet**

`FeatureRegistration`'a `modes` eklenir ve seçim saf fonksiyona çıkarılır:

```ts
import type { ComponentType } from 'react'
import type { MissionMode } from '../mission/types'

export interface FeatureRegistration {
  /** Stable, unique, and used as the React key. */
  id: string
  slot: FeatureSlot
  /** The feature's public entrypoint. Nothing else about it is imported here. */
  Component: ComponentType
  /**
   * Modes this feature appears in. OMITTED MEANS EVERY MODE.
   *
   * The distinction is load-bearing: an empty array would hide the feature
   * everywhere, which is never what someone means when they leave the field
   * off, so the two are deliberately not the same value.
   */
  modes?: readonly MissionMode[]
}

/**
 * The features one slot shows in one mode, in registration order.
 *
 * A pure function rather than a hook so it can be tested without a DOM --
 * this project has neither jsdom nor testing-library, and the ordering and
 * mode rules are exactly the part worth pinning down.
 */
export function selectFeatures(
  features: readonly FeatureRegistration[],
  slot: FeatureSlot,
  mode: MissionMode,
): readonly FeatureRegistration[] {
  return features.filter(
    (feature) =>
      feature.slot === slot && (feature.modes === undefined || feature.modes.includes(mode)),
  )
}
```

- [ ] **Adım 4: Testi çalıştır, geçtiğini gör**

```bash
cd frontend && npm test -- registry
```

Beklenen: beş vaka da PASS.

- [ ] **Adım 5: Kapı ve commit**

```bash
cd frontend && npm run typecheck && npm run lint && npm test
cd .. && git add -A
git commit -m "$(cat <<'EOF'
feat(registry): give a registration a mode, and test the selection

ai-scene's cockpit shows a panel only in some of fleet/plan/analyze, which
the chatbot branch's registry had no way to say. A registration gains an
optional modes list, and the slot-plus-mode filter comes out as a pure
function so it can be tested -- this project has no jsdom, so logic that
stays inside a component is logic nothing can check.

An omitted modes list means every mode; an empty array means none. Nobody
means the latter by leaving the field off, so the two stay distinct.
EOF
)"
```

### Task 6: `FeatureHost`'u mod'a bağla ve canvas slot'unun konumlandırmasını geri getir

**Dosyalar:**
- Değiştir: `frontend/src/shell/FeatureHost.tsx` (chatbot'tan alınır, mod eklenir)
- Değiştir: `frontend/src/shell/slots.tsx` (chatbot'tan alınır, canvas slot'u sarmalanır)
- Oluştur: `frontend/src/shell/shell.css` (chatbot'tan)

**Arayüzler:**
- Tüketir: Task 5'ten `selectFeatures`, `FEATURES`, `FeatureSlot`;
  Task 3'ten `useMission`.
- Üretir: `LeftRailSlot`, `RightRailSlot`, `BottomDock`, `CanvasOverlaySlot`,
  `GlobalOverlaySlot` — hiçbiri prop almaz. Task 7 bunları mount eder.

- [ ] **Adım 1: Üç dosyayı chatbot dalından al**

```bash
git checkout origin/feature/ai-decision-chatbot -- \
  frontend/src/shell/FeatureHost.tsx \
  frontend/src/shell/slots.tsx \
  frontend/src/shell/shell.css
```

- [ ] **Adım 2: `FeatureHost`'a mod filtresini ekle**

`frontend/src/shell/FeatureHost.tsx` tamamen:

```tsx
import { FEATURES, selectFeatures, type FeatureSlot } from '../features/registry'
import { useMission } from '../mission/MissionContext'

/**
 * Renders whichever features are registered for one slot in the current mode.
 *
 * Emits a fragment and nothing else: an empty slot produces no element, no
 * wrapper, no margin and no height, so a slot the cockpit has not filled yet
 * is invisible to layout.
 */
export function FeatureHost({ slot }: { slot: FeatureSlot }) {
  const { missionMode } = useMission()
  return (
    <>
      {selectFeatures(FEATURES, slot, missionMode).map(({ id, Component }) => (
        <Component key={id} />
      ))}
    </>
  )
}
```

- [ ] **Adım 3: `CanvasOverlaySlot`'un konumlandırma sarmalayıcısını geri koy**

Chatbot'un sürümü çıplak fragment döndürüyor; o dalın kaydında hiç
`canvasOverlay` feature'ı olmadığı için bu duruma hiç girilmemiş. Sarmalayıcı
olmadan harita üstü çizimler `.map-stage`'e göre boyutlanır ve yanlış yere
oturur. `frontend/src/shell/slots.tsx` içindeki `CanvasOverlaySlot`:

```tsx
/**
 * Absolutely positioned over the map, so its parent must be a containing
 * block. App.tsx gives the map shell an inline `position: relative` for
 * exactly this: without a positioned ancestor this sizes itself against the
 * stage and sits over the rails instead of over the map.
 */
export function CanvasOverlaySlot() {
  return (
    <div
      className="lp-slot lp-slot-canvas"
      style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}
    >
      <FeatureHost slot="canvasOverlay" />
    </div>
  )
}
```

Diğer dört slot chatbot'taki gibi kalır: sarmalayıcısız fragment.

- [ ] **Adım 4: Kapı**

```bash
cd frontend && npm run typecheck && npm run lint && npm test
```

Beklenen: geçer. Slot'ları henüz kimse mount etmiyor; `FeatureHost`
`useMission`'a bağlı ama Task 7'ye kadar render edilmiyor.

- [ ] **Adım 5: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat(shell): filter a slot's features by mission mode

FeatureHost now reads the mode from mission context and asks selectFeatures
which registrations belong in this slot right now. That is what lets
ai-scene's per-mode panels leave App.tsx.

CanvasOverlaySlot keeps the positioned wrapper the chatbot branch dropped.
Its registry has no canvasOverlay feature, so a bare fragment never showed
the problem: without a positioned ancestor the overlay sizes itself against
the stage and covers the rails instead of the map.
EOF
)"
```

### Task 7: Provider'ları mount et ve `rawCellTelemetry`'yi taşı

`missionValue`'nun on girdisinden dokuzu ai-scene'in `App.tsx`'inde zaten aynı
isimle var. Taşınması gereken tek state `rawCellTelemetry`.

**Dosyalar:**
- Değiştir: `frontend/src/App.tsx`
- Değiştir: `frontend/src/api.ts` (yalnızca `CellTelemetryResponse` tipi zaten yoksa)

**Arayüzler:**
- Tüketir: Task 3'ten `MissionProvider`, Task 4'ten `OverlayProvider`,
  Task 6'dan beş slot.
- Üretir: mount edilmiş `MissionValue` — Task 8'den itibaren her feature bunu
  `useMission()` ile okur.

- [ ] **Adım 1: `rawCellTelemetry` state'ini taşı**

`berke-3d-frontend`'in `App.tsx`'inde bu state `/api/cell-telemetry` yanıtını
ham hâliyle tutuyor ve `cost-explain` (Task 21) buna bağlı. `App.tsx`'te
**`rawCellTelemetry` taşınmaz.** Bu, planın ilk sürümünde vardı ve Task 3'te
düzeltildi: kanonik `MissionValue`'da ne `hoverCell` ne de `cellTelemetry`
alanı var, ve bu bir eksiklik değil, yazılı bir karar. `MissionContext.ts`'in
`useFocusTelemetry` yorumu şöyle bitiyor:

> A feature that needs the telemetry of a particular cell should fetch that
> cell: `fetchCellTelemetry(row, col)`.

Yani hücre telemetrisini App yayınlamaz; ihtiyacı olan feature kendi çeker.
`cost-explain` bunu Task 21'de yapacak. Bu adımda `App.tsx`'e yeni state
eklenmez.

- [ ] **Adım 2: `missionValue`'yu kur**

`App.tsx`'te, JSX'ten önce. Alanlar kanonik `MissionValue`'nun tam olarak
istediği kadar — fazlası TypeScript'in fazla-özellik denetimine takılır:

```tsx
const missionValue: MissionValue = useMemo(
  () => ({
    gridMeta: elevationLayer
      ? {
          rows: elevationLayer.shape[0],
          cols: elevationLayer.shape[1],
          resolutionM: focusTelemetry.resolutionM,
        }
      : null,
    roverId: selectedRoverId,
    weights,
    start,
    goal,
    planResult,
    // Kanonik tipte her zaman null: bu kokpitte "hücre seç" diye bir kontrol
    // yok. Analiz odağı isteyen feature selectors.ts'teki
    // selectStableAnalysisCell'i adıyla çağırır.
    selectedCell: null,
    activeViewMode: viewMode,
    dimension,
    missionMode,
  }),
  [
    dimension, elevationLayer, focusTelemetry.resolutionM, goal, missionMode,
    planResult, selectedRoverId, start, viewMode, weights,
  ],
)
```

`missionMode` kanonik tipe bu planla eklenen tek alandır; kayıt bir feature'ın
hangi modda görüneceğini ona bakarak süzüyor. `mission/types.ts`'teki
`MissionValue`'ya eklenmesi bu adımın parçasıdır.

`setStart`/`setGoal` **eklenmez**: kanonik `MissionValue` salt okunur ve
bugün hiçbir feature onları çağırmıyor. İhtiyaç çıkarsa o feature'ın kendi
görevinde, gerekçesiyle eklenir.

- [ ] **Adım 3: Provider'ları ve beş slot'u yerleştir**

`App.tsx`'in JSX'i `<MissionProvider value={missionValue} focusTelemetry={focusTelemetry}>`
ve içinde `<OverlayProvider>` ile sarılır. Beş slot Göktuğ'un mevcut
yerleşimindeki karşılıklarına konur:

- `<LeftRailSlot />` — sol ray bölümünün sonuna
- `<RightRailSlot />` — sağ ray bölümünün sonuna
- `<BottomDock />` — harita sahnesinin altına
- `<CanvasOverlaySlot />` — harita kabuğunun içine (kabuğa `position: relative` verilir)
- `<GlobalOverlaySlot />` — `.app-shell`'in doğrudan çocuğu olarak, toast
  yığınından **hemen önce**. Bu sıra `shell.css`'in kardeş seçicisinin
  çalışması için gereklidir.

Mevcut paneller bu adımda **yerinde bırakılır**; Faz 2 onları tek tek kayda
taşıyacak.

- [ ] **Adım 4: Kapı**

```bash
cd frontend && npm run typecheck && npm run lint && npm test
```

- [ ] **Adım 5: Gözle doğrula**

```bash
cd frontend && npm run dev
```

Beklenen: uygulama Task 1'deki gibi görünür ve davranır. Kayıt boş olduğu için
slot'lar hiçbir şey render etmez ve yerleşimde tek piksel değişmemelidir. Bir
kayma görürsen sebebi `GlobalOverlaySlot`'un yanlış ebeveyne konmasıdır.

- [ ] **Adım 6: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat(app): mount the mission and overlay providers with five empty slots

Nine of missionValue's ten inputs already existed in ai-scene's App.tsx
under the same names -- both branches grew from berke-3d -- so wiring the
provider is mapping, not porting. The exception is rawCellTelemetry, the
raw /api/cell-telemetry response, which comes over with its effect because
cost-explain depends on it.

hoverCell and selectedCell are separate fields on the canonical value.
They are not two names for one thing: one is the cell under the pointer,
the other a sticky selection, and cost-explain wants the first.

The registry is still empty, so every slot renders nothing and the layout
is unchanged. Phase 2 starts filling it.
EOF
)"
```

---

## Faz 2 — Göktuğ'un panelleri kayda geçer

### Task 7b: Eylem sözleşmesi

Planın ilk sürümünde yoktu; Task 8 açılınca ortaya çıktı ve Faz 2'nin
tamamının önkoşulu.

Kanonik `MissionValue` **salt okunur** ve bu kasıtlı: chatbot dalının tek
feature'ı okur, yazmaz. Göktuğ'un panelleri ise kokpitin kontrol yüzeyleri.
Ölçüm:

| panel | prop | geri çağırma |
|---|---|---|
| `MissionSetupPanel` | 14 | 6 |
| `LayerDropdown` | 6 | 3 |
| `RouteAnalysisInspector` | 6 | 2 |
| `PlaybackBar` | 4 | 2 |
| `MissionSnapshotPanel` | 5 | 1 |
| `MissionContextPanel` | 6 | 0 |
| `RouteSolvingOverlay` | 4 | 0 |

Yedinin beşi eylem istiyor. "Prop drilling'i context'e çevir" veri için
çalışıyor, eylemler için çalışmıyor — sözleşmede eylem yok.

**Karar: ayrı bir eylem context'i.** `MissionValue` salt okunur kalır;
`MissionActions` kendi context'inde yaşar. Bu, dosyanın zaten kurduğu ayrımın
aynısı (`MissionContext` / `FocusTelemetryContext`) ve sebebi de aynı: anlık
görüntü anlık görüntü olarak kalsın, bir düğme mission snapshot'ına abone
olmadan eylem alabilsin.

On iki eylem: `selectRover`, `setWeights`, `setClickMode`, `planRoute`,
`resetMission`, `setMissionMode`, `setPlaybackStep`, `setPayloadW`,
`setHeaterW`, `setViewMode`, `setDimension`, `toggleHud`.

Hepsi memoize; çoğu hiç değişmiyor, `planRoute` uç noktalara ve ağırlıklara
kapandığı için onlarla değişiyor — ki bağımlı bir efektin zaten yeniden koşması
gereken an o.

**Veri alanları bu görevde eklenmez.** Her panel kendi görevinde ihtiyacı olan
alanı `MissionValue`'ya gerekçesiyle ekler; sözleşmeyi peşin şişirmek, hangi
alanın neden var olduğunu okunmaz hale getirir.

**Kapı:** üç kontrol de geçer, uygulama değişmez — henüz eylemi tüketen yok.

---

Kalan görevler Task 8'in kurduğu biçimi izler. Adım adım:

1. `git mv components/<Alan>/<Panel>.tsx features/<ad>/`
2. `interface <Panel>Props` silinir; bileşen `React.FC` olur, prop almaz
3. Veri `useMission()`'dan, eylemler `useMissionActions()`'dan okunur
4. Eksik veri alanı varsa `mission/types.ts`'e **gerekçesiyle** eklenir ve
   `App.tsx`'teki `missionValue`'da doldurulur (bağımlılık dizisini unutma)
5. `features/<ad>/index.tsx` — tek satırlık giriş noktası
6. `registry.ts`'e bir kayıt satırı; **modu `App.tsx`'teki koşuldan oku**
7. `App.tsx`'ten JSX, import ve artık kullanılmayan handler silinir
8. Kapı + tarayıcıda gözle doğrulama, sonra commit

Task 8 (`mission-snapshot`) bu adımların hepsini içeren çalışan örnektir;
takıldığın yerde `6c639cd` commit'ine bak. `SpaceBackdrop`, `TopBar`, `MapCanvas`, `TerrainCanvas3D` ve
`FleetSelectionView` **kabukta kalır** ve prop almaya devam eder.

`FleetSelectionView` bilerek dışarıda: `fleet` modunda kokpitin tamamının
yerine geçiyor, bir raya oturmuyor. Kabuk "hangar mı kokpit mi" kararını kendisi
verir; tek örneği olan bir `stage` slot'u icat edilmez.

### Task 8: `MissionSnapshotPanel` → `leftRail`

**Dosyalar:**
- Taşı: `frontend/src/components/Analysis/MissionSnapshotPanel.tsx` → `frontend/src/features/mission-snapshot/MissionSnapshotPanel.tsx`
- Oluştur: `frontend/src/features/mission-snapshot/index.tsx`
- Değiştir: `frontend/src/features/registry.ts`, `frontend/src/App.tsx`

**Arayüzler:**
- Tüketir: `useMission()` — `planResult`, `roverId`, `weights`.
- Üretir: `MissionSnapshot` — prop almayan bileşen; kayıt id'si `'mission-snapshot'`.

- [ ] **Adım 1: Dosyayı taşı**

```bash
cd frontend/src
mkdir -p features/mission-snapshot
git mv components/Analysis/MissionSnapshotPanel.tsx features/mission-snapshot/
```

- [ ] **Adım 2: Prop'ları context'e çevir**

`MissionSnapshotPanel.tsx`'te `interface MissionSnapshotPanelProps` silinir.
Bileşen imzası prop'suz olur ve değerleri context'ten alır:

```tsx
import { useMission } from '../../mission/MissionContext'

export default function MissionSnapshotPanel() {
  const { planResult, roverId, weights } = useMission()
  // gövde değişmez; eski props.X kullanımları yukarıdaki adlara döner
}
```

- [ ] **Adım 3: Giriş noktasını yaz**

`frontend/src/features/mission-snapshot/index.tsx`:

```tsx
import MissionSnapshotPanel from './MissionSnapshotPanel'

/** Registry'nin gördüğü tek yüz. Panelin içi buranın dışına sızmaz. */
export function MissionSnapshot() {
  return <MissionSnapshotPanel />
}
```

- [ ] **Adım 4: Kayda ekle**

`frontend/src/features/registry.ts` içindeki `FEATURES` dizisine:

```ts
  // Her modda görünür: seçili rover ve ağırlıklar kokpitin sabit özeti.
  { id: 'mission-snapshot', slot: 'leftRail', Component: MissionSnapshot },
```

- [ ] **Adım 5: `App.tsx`'ten JSX'i ve prop'ları sil**

`<MissionSnapshotPanel … />` satırı ve `import MissionSnapshotPanel from …`
kaldırılır. Sol ray bölümünde yalnızca `<LeftRailSlot />` kalır.

- [ ] **Adım 6: Kapı ve gözle doğrulama**

```bash
cd frontend && npm run typecheck && npm run lint && npm test && npm run dev
```

Beklenen: panel sol rayda, üç modda da, taşımadan önceki yerinde ve
görünümünde.

- [ ] **Adım 7: Commit**

```bash
git add -A
git commit -m "feat(mission-snapshot): move the panel into the registry"
```

### Task 9: `MissionSetupPanel` → `leftRail`, yalnızca `plan`

`RoverSelectDrawer` bu panelin çocuğudur ve öyle kalır — kaydolmaz.

**Dosyalar:**
- Taşı: `frontend/src/components/Planning/MissionSetupPanel.tsx` ve `RoverSelectDrawer.tsx` → `frontend/src/features/mission-setup/`
- Oluştur: `frontend/src/features/mission-setup/index.tsx`
- Değiştir: `frontend/src/features/registry.ts`, `frontend/src/App.tsx`

**Arayüzler:**
- Tüketir: `useMission()` — `roverId`, `weights`, `start`, `goal`.
- Üretir: `MissionSetup`; kayıt id'si `'mission-setup'`, `modes: ['plan']`.

- [ ] **Adım 1: İki dosyayı taşı**

```bash
cd frontend/src
mkdir -p features/mission-setup
git mv components/Planning/MissionSetupPanel.tsx components/Planning/RoverSelectDrawer.tsx \
       features/mission-setup/
```

- [ ] **Adım 2: `MissionSetupPanel`'in prop'larını context'e çevir**

`interface MissionSetupPanelProps` silinir; `useMission()`'dan okunur.
`RoverSelectDrawer` prop almaya devam eder — o bir alt bileşen, kayıt değil ve
verisini ebeveyninden alır. Import yolu `./RoverSelectDrawer` olarak kalır.

- [ ] **Adım 3: Giriş noktasını yaz**

`frontend/src/features/mission-setup/index.tsx`:

```tsx
import MissionSetupPanel from './MissionSetupPanel'

export function MissionSetup() {
  return <MissionSetupPanel />
}
```

- [ ] **Adım 4: Kayda ekle**

```ts
  // Yalnızca plan modunda: hangar seçimi bittikten sonra anlamlı.
  { id: 'mission-setup', slot: 'leftRail', Component: MissionSetup, modes: ['plan'] },
```

- [ ] **Adım 5: `App.tsx`'ten koşullu JSX'i sil**

`missionMode === 'plan' ? <MissionSetupPanel … /> : …` üçlüsü kaldırılır; mod
kararı artık kayıtta.

- [ ] **Adım 6: Kapı ve gözle doğrulama**

```bash
cd frontend && npm run typecheck && npm run lint && npm test && npm run dev
```

Beklenen: panel yalnızca `plan` modunda görünür; `fleet` ve `analyze`'da yok.

- [ ] **Adım 7: Commit**

```bash
git add -A
git commit -m "feat(mission-setup): register the panel for plan mode only"
```

### Task 10: `MissionContextPanel` → `rightRail`

**Dosyalar:**
- Taşı: `frontend/src/components/Planning/MissionContextPanel.tsx` → `frontend/src/features/mission-context/`
- Oluştur: `frontend/src/features/mission-context/index.tsx`
- Değiştir: `frontend/src/features/registry.ts`, `frontend/src/App.tsx`

**Arayüzler:**
- Tüketir: `useMission()`, `useFocusTelemetry()`.
- Üretir: `MissionContextFeature`; kayıt id'si `'mission-context'`, mod yok
  (hem `plan` hem `analyze`'da görünüyor, `fleet`'te kokpit zaten yok).

- [ ] **Adım 1: Dosyayı taşı**

```bash
cd frontend/src
mkdir -p features/mission-context
git mv components/Planning/MissionContextPanel.tsx features/mission-context/
```

- [ ] **Adım 2: Prop'ları context'e çevir**

`interface MissionContextPanelProps` silinir. Odak telemetrisi ayrı hook'tan
gelir:

```tsx
import { useMission } from '../../mission/MissionContext'
import { useFocusTelemetry } from '../../mission/MissionContext'

export default function MissionContextPanel() {
  const { gridMeta, activeViewMode } = useMission()
  const focus = useFocusTelemetry()
  // gövde değişmez
}
```

- [ ] **Adım 3: Giriş noktasını yaz**

```tsx
import MissionContextPanel from './MissionContextPanel'

export function MissionContextFeature() {
  return <MissionContextPanel />
}
```

- [ ] **Adım 4: Kayda ekle**

```ts
  // Modsuz: App.tsx bu paneli hem plan hem analyze dalında render ediyordu.
  { id: 'mission-context', slot: 'rightRail', Component: MissionContextFeature },
```

- [ ] **Adım 5: `App.tsx`'ten iki ayrı mount'u sil**

`MissionContextPanel` bugün `App.tsx`'te **iki yerde** render ediliyor (plan
dalında bir, analyze dalında bir). İkisi de kaldırılır; kayıt tek girdiyle her
iki modu karşılar. Bu görev, koşullu JSX'in nasıl çoğaltmaya yol açtığının
somut örneğidir.

- [ ] **Adım 6: Kapı ve gözle doğrulama**

```bash
cd frontend && npm run typecheck && npm run lint && npm test && npm run dev
```

Beklenen: panel `plan` ve `analyze` modlarında sağ rayda, **tek kez**.

- [ ] **Adım 7: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat(mission-context): register the panel once for both modes

App.tsx rendered this panel twice, once in the plan branch and once in the
analyze branch. One registration with no modes list covers both.
EOF
)"
```

### Task 11: `RouteAnalysisInspector` → `rightRail`, yalnızca `analyze`

**Dosyalar:**
- Taşı: `frontend/src/components/Analysis/RouteAnalysisInspector.tsx` → `frontend/src/features/route-analysis/`
- Oluştur: `frontend/src/features/route-analysis/index.tsx`
- Değiştir: `frontend/src/features/registry.ts`, `frontend/src/App.tsx`

**Arayüzler:**
- Tüketir: `useMission()` — `planResult`.
- Üretir: `RouteAnalysis`; kayıt id'si `'route-analysis'`, `modes: ['analyze']`.

- [ ] **Adım 1: Dosyayı taşı**

```bash
cd frontend/src
mkdir -p features/route-analysis
git mv components/Analysis/RouteAnalysisInspector.tsx features/route-analysis/
```

- [ ] **Adım 2: Prop'ları context'e çevir**

`interface RouteAnalysisInspectorProps` silinir; `planResult` `useMission()`'dan
okunur. `planResult` yokken bileşen `null` döndürmeye devam eder — `App.tsx`
bugün bunu `missionMode === 'analyze' && planResult &&` ile dışarıdan yapıyor,
sorumluluk bileşenin içine taşınır.

- [ ] **Adım 3: Giriş noktasını yaz**

```tsx
import RouteAnalysisInspector from './RouteAnalysisInspector'

export function RouteAnalysis() {
  return <RouteAnalysisInspector />
}
```

- [ ] **Adım 4: Kayda ekle**

```ts
  { id: 'route-analysis', slot: 'rightRail', Component: RouteAnalysis, modes: ['analyze'] },
```

- [ ] **Adım 5: `App.tsx`'ten koşulu ve JSX'i sil**

- [ ] **Adım 6: Kapı ve gözle doğrulama**

```bash
cd frontend && npm run typecheck && npm run lint && npm test && npm run dev
```

Beklenen: yalnızca `analyze` modunda ve yalnızca bir rota planlandıysa görünür.

- [ ] **Adım 7: Commit**

```bash
git add -A
git commit -m "feat(route-analysis): register the inspector for analyze mode"
```

### Task 12: `PlaybackBar` → `bottomDock`, yalnızca `analyze`

**Dosyalar:**
- Taşı: `frontend/src/components/Analysis/PlaybackBar.tsx` → `frontend/src/features/playback/`
- Oluştur: `frontend/src/features/playback/index.tsx`
- Değiştir: `frontend/src/features/registry.ts`, `frontend/src/App.tsx`

**Arayüzler:**
- Tüketir: `useMission()` — `planResult`.
- Üretir: `Playback`; kayıt id'si `'playback'`, `modes: ['analyze']`.

**Not:** `routePlaybackStep` state'i bugün `App.tsx`'te. Bu görevde
**taşınmaz**: iki yazarı olan bir state'i feature'ın içine gömmek `MapCanvas`'ı
kırar. `App.tsx`'te kalır ve `PlaybackBar` ona `useMission()` üzerinden erişir;
alan Task 7'de kurulan değere eklenir.

> **Bilinen kusur — `goktug/ai-scene`'den miras, bu planın kapsamı dışında.**
>
> 4 Eylül'de tarayıcıda üretilip doğrulandı: `PlaybackBar`'daki Play çalışıyor
> ama **yalnızca sayıları sürüyor.** Harita takip etmiyor.
>
> Sebep, aynı state'e yazan iki ayrı oynatma motoru:
>
> | | `MapCanvas` | `PlaybackBar` |
> |---|---|---|
> | Adım state'i | `animStep`, **private** | yok; `routePlaybackStep`'e yazar |
> | Timer | 33/66 ms | 50 ms |
> | Rotayı çizen | **bu** | — |
> | Dışarıdan sürülebilir mi | yalnızca ref'teki `startAnimation()` | `currentStep` prop'u |
>
> `MapCanvas`'ın `Props`'unda adımı **dışarıdan alan bir alan yok**. Plan
> geldiğinde `App.tsx:345` `startAnimation()`'ı çağırıyor, `MapCanvas` rotayı
> bir kez sonuna kadar çiziyor ve `onAnimationStepChange` ile adımı yukarı
> bildiriyor. Sonra Play'e basıldığında `PlaybackBar` `routePlaybackStep`'i
> sıfırlayıp ilerletiyor — sayaç, kaydırıcı, telemetri ve analiz paneli
> güncelleniyor, ama `animStep`'e kimse dokunamadığı için rota tam çizili
> kalıyor.
>
> Doğru düzeltme `animStep`'i `MapCanvas`'tan kaldırmaktır: tek doğru kaynak
> `App.tsx`'teki `routePlaybackStep` olur, `MapCanvas` gelen adıma kadar çizen
> saf bir görüntüleyiciye döner ve iki yazarlı durum ortadan kalkar. Yanına
> aralığın yavaşlatılması gerekir — 50 ms × 86 waypoint, tüm oynatmayı dört
> saniyede bitiriyor.
>
> **Karar (4 Eylül): düzeltme Göktuğ'a bırakıldı**, kendi feature'ı ve tasarım
> niyetini o biliyor. Bu görev `PlaybackBar`'ı yalnızca kayda taşır,
> davranışına dokunmaz. Göktuğ düzeltmeyi bu görevden önce yaparsa taşıma
> değişmez; sonra yaparsa `MapCanvas`'ın yeni prop'u `MissionValue`'daki
> `routePlaybackStep`'ten beslenir.

- [ ] **Adım 1: Dosyayı taşı**

```bash
cd frontend/src
mkdir -p features/playback
git mv components/Analysis/PlaybackBar.tsx features/playback/
```

- [ ] **Adım 2: `routePlaybackStep`'i mission değerine ekle**

`App.tsx`'teki `missionValue` nesnesine ve bağımlılık dizisine:

```tsx
  routePlaybackStep,
  setRoutePlaybackStep,
```

Aynı alanlar `mission/types.ts`'teki `MissionValue`'ya eklenir:

```ts
  /** Oynatma imleci; null ise rota durağan gösterilir. */
  routePlaybackStep: number | null
  setRoutePlaybackStep: (step: number | null) => void
```

- [ ] **Adım 3: Prop'ları context'e çevir ve giriş noktasını yaz**

```tsx
import PlaybackBar from './PlaybackBar'

export function Playback() {
  return <PlaybackBar />
}
```

- [ ] **Adım 4: Kayda ekle**

```ts
  { id: 'playback', slot: 'bottomDock', Component: Playback, modes: ['analyze'] },
```

- [ ] **Adım 5: `App.tsx`'ten JSX'i sil, `MapCanvas`'ın prop'una dokunma**

- [ ] **Adım 6: Kapı ve gözle doğrulama**

```bash
cd frontend && npm run typecheck && npm run lint && npm test && npm run dev
```

Beklenen: `analyze` modunda alt şeritte görünür; oynatma sırasında rota
`MapCanvas`'ta hâlâ animasyonlu.

- [ ] **Adım 7: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat(playback): register the playback bar for analyze mode

routePlaybackStep stays in App.tsx rather than moving into the feature:
MapCanvas reads it too, and burying a two-consumer state inside one feature
would break the other. It joins MissionValue instead.
EOF
)"
```

### Task 13: `LayerDropdown` ve `RouteSolvingOverlay` → `canvasOverlay`

İkisi de harita üstünde duran, kendi başına anlamlı olmayan küçük parçalar;
ayrı görevlere bölmek bir gözden geçirene fazladan karar kazandırmaz.

**Dosyalar:**
- Taşı: `frontend/src/components/Map/LayerDropdown.tsx` → `frontend/src/features/layer-picker/`
- Taşı: `frontend/src/components/Map/RouteSolvingOverlay.tsx` → `frontend/src/features/solving-indicator/`
- Oluştur: `frontend/src/features/layer-picker/index.tsx`, `frontend/src/features/solving-indicator/index.tsx`
- Değiştir: `frontend/src/features/registry.ts`, `frontend/src/App.tsx`

**Arayüzler:**
- Tüketir: `useMission()` — `activeViewMode`; `isSolving` (Task 12'deki gibi
  `MissionValue`'ya eklenir).
- Üretir: `LayerPicker`, `SolvingIndicator`.

- [ ] **Adım 1: İki dosyayı taşı**

```bash
cd frontend/src
mkdir -p features/layer-picker features/solving-indicator
git mv components/Map/LayerDropdown.tsx features/layer-picker/
git mv components/Map/RouteSolvingOverlay.tsx features/solving-indicator/
```

- [ ] **Adım 2: `isSolving`'i mission değerine ekle**

`mission/types.ts`'te `MissionValue`'ya:

```ts
  /** Bir plan isteği uçuşta mı. */
  isSolving: boolean
```

`App.tsx`'te `missionValue` nesnesine ve bağımlılık dizisine `isSolving`
eklenir.

- [ ] **Adım 3: Prop'ları context'e çevir**

`LayerDropdown` `activeViewMode`'u, `RouteSolvingOverlay` `isSolving`'i
`useMission()`'dan okur; `Props` arayüzleri silinir.

- [ ] **Adım 4: İki giriş noktası yaz**

```tsx
// features/layer-picker/index.tsx
import LayerDropdown from './LayerDropdown'
export function LayerPicker() {
  return <LayerDropdown />
}
```

```tsx
// features/solving-indicator/index.tsx
import RouteSolvingOverlay from './RouteSolvingOverlay'
export function SolvingIndicator() {
  return <RouteSolvingOverlay />
}
```

- [ ] **Adım 5: Kayda ekle**

Kayıt sırası slot içindeki render sırasıdır; gösterge katman seçicinin üstünde
çizilmeli, bu yüzden sonra gelir.

```ts
  { id: 'layer-picker', slot: 'canvasOverlay', Component: LayerPicker },
  { id: 'solving-indicator', slot: 'canvasOverlay', Component: SolvingIndicator },
```

- [ ] **Adım 6: `App.tsx`'ten iki JSX'i sil**

- [ ] **Adım 7: Kapı ve gözle doğrulama**

```bash
cd frontend && npm run typecheck && npm run lint && npm test && npm run dev
```

Beklenen: katman açılır menüsü harita üstünde eski yerinde; plan isteği
sırasında çözüm göstergesi beliriyor. **Konum kayması varsa** sebebi Task 6'daki
`CanvasOverlaySlot` sarmalayıcısının ebeveyninde `position: relative`
olmamasıdır.

- [ ] **Adım 8: Commit**

```bash
git add -A
git commit -m "feat(canvas-overlay): register the layer picker and solving indicator"
```

---

## Faz 3 — Dokuz feature geri gelir

Her feature `_pending`'den çıkar, kanonik tiplere uyarlanır ve kaydolur.
Sıra kolaydan zora: önceki görevler deseni doğrular, `cost-explain` en sona
kalır çünkü tek gerçek semantik kararı o taşır.

Ölçülen bağımlılık haritası:

| feature | slot | mod | `useOverlays` | `start`/`goal` | `activeLayer` | `hoverCell` |
|---|---|---|---|---|---|---|
| `ros-showcase` | leftRail | — | – | – | – | – |
| `mission-validation` | rightRail | — | – | – | – | – |
| `corridor` | rightRail | — | ✓ | – | – | – |
| `pose-loop` | rightRail | — | ✓ | – | – | – |
| `layer-provenance` | leftRail | — | – | – | ✓ | – |
| `replan` | leftRail | plan | – | ✓ | – | – |
| `profile-compare` | rightRail | analyze | ✓ | ✓ | – | – |
| `time-axis` | bottomDock | analyze | ✓ | ✓ | – | – |
| `cost-explain` | rightRail | — | ✓ | – | – | ✓ |

### Task 14: `ros-showcase` ve `mission-validation` — yalnızca kayıt

İkisi de ne overlay ne de değişen bir mission alanı kullanıyor; taşıma
tamamen mekanik olduğu için tek görevde toplanıyor.

**Dosyalar:**
- Taşı: `frontend/src/features/_pending/ros-showcase` → `frontend/src/features/ros-showcase`
- Taşı: `frontend/src/features/_pending/mission-validation` → `frontend/src/features/mission-validation`
- Değiştir: `frontend/src/features/registry.ts`

**Arayüzler:**
- Tüketir: `useMission()` (değişmeyen alanlar).
- Üretir: kayıt id'leri `'ros-showcase'`, `'mission-validation'`.

- [ ] **Adım 1: İki dizini çıkar**

```bash
cd frontend/src/features
git mv _pending/ros-showcase _pending/mission-validation .
```

- [ ] **Adım 2: Kayda ekle**

`registry.ts` başına import, `FEATURES`'a iki satır:

```ts
import { RosShowcase } from './ros-showcase'
import { MissionValidation } from './mission-validation'
```

```ts
  { id: 'ros-showcase', slot: 'leftRail', Component: RosShowcase },
  { id: 'mission-validation', slot: 'rightRail', Component: MissionValidation },
```

- [ ] **Adım 3: Kapı**

```bash
cd frontend && npm run typecheck && npm run lint && npm test
```

Beklenen: geçer. Kırılırsa, iki feature'ın `useMission`'dan okuduğu bir alanın
kanonik `MissionValue`'da bulunmadığı anlamına gelir; eksik alan
`mission/types.ts`'e eklenir ve `App.tsx`'teki `missionValue`'da doldurulur.

- [ ] **Adım 4: Gözle doğrula**

```bash
cd frontend && npm run dev
```

Beklenen: ROS panosu sol rayda, doğrulama paneli sağ rayda.

- [ ] **Adım 5: Commit**

```bash
git add -A
git commit -m "feat(features): bring ros-showcase and mission-validation back through the registry"
```

### Task 15: `corridor` — overlay tiplerine uyarla

**Dosyalar:**
- Taşı: `frontend/src/features/_pending/corridor` → `frontend/src/features/corridor`
- Değiştir: `frontend/src/features/corridor/overlays.ts`, `frontend/src/features/registry.ts`

**Arayüzler:**
- Tüketir: `useOverlays()`, `OverlayCommand`.
- Üretir: kayıt id'si `'corridor'`.

- [ ] **Adım 1: Dizini çıkar**

```bash
cd frontend/src/features && git mv _pending/corridor .
```

- [ ] **Adım 2: `overlays.ts`'i kanonik tiplere çevir**

| eski | yeni |
|---|---|
| `OverlayLayer` | `OverlayCommand` |
| `PixelPoint` | `CellRef` |
| `style.lineWidth` | `style.widthPx` |
| `center` (ribbon) | `points` |
| `halfWidthPx: number[]` | `halfWidthCells: number[]` |

- [ ] **Adım 3: Kayıt fonksiyonunu yeni sözleşmeye çevir**

Kanonik `register` bir temizlik fonksiyonu döndürür; eski `unregister(id)`
çağrısı kalkar:

```ts
const overlays = useOverlays()
// MEMOISED. Her render'da yeniden kurulan bir dizi efekti sonsuza kadar tetikler.
const commands = useMemo(() => buildCorridorCommands(planResult), [planResult])
useEffect(() => overlays.register('corridor', commands), [overlays, commands])
```

- [ ] **Adım 4: Kayda ekle**

```ts
import { CorridorFeature } from './corridor'
```

```ts
  { id: 'corridor', slot: 'rightRail', Component: CorridorFeature },
```

- [ ] **Adım 5: Kapı ve gözle doğrulama**

```bash
cd frontend && npm run typecheck && npm run lint && npm test && npm run dev
```

Beklenen: koridor haritada tek bir birleşik şerit olarak çiziliyor; panel sağ
rayda. Şerit kenarları tırtıklıysa `halfWidthCells` birimi yanlış
(hücre bekleniyor, piksel verilmiş).

- [ ] **Adım 6: Commit**

```bash
git add -A
git commit -m "feat(corridor): retype the corridor overlay onto the canonical commands"
```

### Task 16: `pose-loop` — overlay tiplerine uyarla

**Dosyalar:**
- Taşı: `frontend/src/features/_pending/pose-loop` → `frontend/src/features/pose-loop`
- Değiştir: `frontend/src/features/pose-loop/overlays.ts`, `frontend/src/features/registry.ts`

**Arayüzler:**
- Tüketir: `useOverlays()`, `OverlayCommand`.
- Üretir: kayıt id'si `'pose-loop'`.

- [ ] **Adım 1: Dizini çıkar**

```bash
cd frontend/src/features && git mv _pending/pose-loop .
```

- [ ] **Adım 2: `overlays.ts`'i kanonik tiplere çevir**

`OverlayLayer` → `OverlayCommand`, `PixelPoint` → `CellRef`,
`style.lineWidth` → `style.widthPx`, `style.radius` → `style.radiusPx`
(poz işaretleri `points` komutu kullanıyor).

- [ ] **Adım 3: Kayıt fonksiyonunu temizlik döndüren biçime çevir**

```ts
const overlays = useOverlays()
const commands = useMemo(() => buildPoseCommands(poses), [poses])
useEffect(() => overlays.register('pose-loop', commands), [overlays, commands])
```

- [ ] **Adım 4: Kayda ekle**

```ts
import { PoseLoop } from './pose-loop'
```

```ts
  { id: 'pose-loop', slot: 'rightRail', Component: PoseLoop },
```

- [ ] **Adım 5: Kapı ve gözle doğrulama**

```bash
cd frontend && npm run typecheck && npm run lint && npm test && npm run dev
```

Beklenen: poz işaretleri haritada; panel sağ rayda.

- [ ] **Adım 6: Commit**

```bash
git add -A
git commit -m "feat(pose-loop): retype the pose overlay onto the canonical commands"
```

### Task 17: `layer-provenance` — `activeLayer` → `activeViewMode`

**Dosyalar:**
- Taşı: `frontend/src/features/_pending/layer-provenance` → `frontend/src/features/layer-provenance`
- Değiştir: `frontend/src/features/layer-provenance/useLayerProvenance.ts`, `frontend/src/features/registry.ts`

**Arayüzler:**
- Tüketir: `useMission()` — `activeViewMode`.
- Üretir: kayıt id'si `'layer-provenance'`.

- [ ] **Adım 1: Dizini çıkar**

```bash
cd frontend/src/features && git mv _pending/layer-provenance .
```

- [ ] **Adım 2: İki `activeLayer` kullanımını yeniden adlandır**

Bu bir isim değişikliğidir, anlam aynıdır: her ikisi de haritada o an gösterilen
katmanı söyler.

```ts
const { activeViewMode } = useMission()
```

Tip de değişir: `MapViewMode` yerine kanonik `ViewModeId`.

- [ ] **Adım 3: Kayda ekle**

```ts
import { LayerProvenance } from './layer-provenance'
```

```ts
  { id: 'layer-provenance', slot: 'leftRail', Component: LayerProvenance },
```

- [ ] **Adım 4: Kapı ve gözle doğrulama**

```bash
cd frontend && npm run typecheck && npm run lint && npm test && npm run dev
```

Beklenen: panel sol rayda; katman değiştirildiğinde köken bilgisi değişiyor.

- [ ] **Adım 5: Commit**

```bash
git add -A
git commit -m "feat(layer-provenance): read activeViewMode from the canonical mission value"
```

### Task 18: `replan` — kayda taşı

**Dosyalar:**
- Taşı: `frontend/src/features/_pending/replan` → `frontend/src/features/replan`
- Değiştir: `frontend/src/features/replan/useReplan.ts`, `frontend/src/features/registry.ts`

**Arayüzler:**
- Tüketir: `useMission()` — `start: CellRef | null`, `goal: CellRef | null`.
- Üretir: kayıt id'si `'replan'`, `modes: ['plan']`.

- [ ] **Adım 1: Dizini çıkar**

```bash
cd frontend/src/features && git mv _pending/replan .
```

- [ ] **Adım 2: `start`/`goal` kullanımlarını doğrula — değişiklik beklenmiyor**

Bu adım Task 3'te ölçülen bir düzeltmeyi taşıyor. Kanonik tip şu:

```ts
export type Cell = [row: number, col: number]        // DEMET
export interface CellRef { row: number; col: number } // obje, yalnızca overlay için
```

`MissionValue.start` ve `.goal` **demettir**, tıpkı `berke-3d-frontend`'deki
gibi. Bu planın ilk sürümü onları obje sanıyordu ve 13 kullanımın
dönüştürülmesini istiyordu; **gerek yok.** `const [row, col] = start` olduğu
gibi kalır, ağ sınırında dönüşüm de gerekmez.

Yapılacak tek şey: `useMission()`'dan okunan alanların adlarının tuttuğunu
doğrulamak. Tutmayan bir alan çıkarsa `mission/types.ts`'e eklenir ve
`App.tsx`'teki `missionValue`'da doldurulur.

- [ ] **Adım 3: Kayda ekle**

```ts
import { Replan } from './replan'
```

```ts
  { id: 'replan', slot: 'leftRail', Component: Replan, modes: ['plan'] },
```

- [ ] **Adım 4: Kapı ve gözle doğrulama**

```bash
cd frontend && npm run typecheck && npm run lint && npm test && npm run dev
```

Beklenen: panel yalnızca `plan` modunda; başlangıç/hedef seçiliyken yeniden
planlama isteği doğru hücreleri gönderiyor (ağ sekmesinden `[row, col]` olarak
doğrulanır).

- [ ] **Adım 5: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat(replan): bring replan back through the registry

No cell conversion after all: the canonical Cell is a tuple, the same shape
this feature already used, so start and goal are untouched. The plan's first
draft had them as objects and asked for thirteen rewrites that turned out to
be unnecessary.
EOF
)"
```

### Task 19: `profile-compare` — overlay tiplerine uyarla

**Dosyalar:**
- Taşı: `frontend/src/features/_pending/profile-compare` → `frontend/src/features/profile-compare`
- Değiştir: `frontend/src/features/profile-compare/overlays.ts`, `useProfileCompare.ts`, `frontend/src/features/registry.ts`

**Arayüzler:**
- Tüketir: `useMission()` — `start`, `goal`; `useOverlays()`.
- Üretir: kayıt id'si `'profile-compare'`, `modes: ['analyze']`.

- [ ] **Adım 1: Dizini çıkar**

```bash
cd frontend/src/features && git mv _pending/profile-compare .
```

- [ ] **Adım 2: `start`/`goal` kullanımlarını doğrula — değişiklik beklenmiyor**

10 kullanım (`start` 5, `goal` 5). Kanonik `Cell` bir demet olduğu için
(bkz. Task 18 Adım 2) bunlar olduğu gibi kalır; dönüşüm gerekmez.

- [ ] **Adım 3: `overlays.ts`'i kanonik tiplere çevir**

`OverlayLayer` → `OverlayCommand`, `PixelPoint` → `CellRef`,
`style.lineWidth` → `style.widthPx`. Karşılaştırma iki rotayı ayrı
`polyline` komutu olarak çiziyor; ikisinin `id`'si kayıt içinde benzersiz
kalmalı (`'profile-a'`, `'profile-b'`).

- [ ] **Adım 4: Kayıt fonksiyonunu temizlik döndüren biçime çevir**

```ts
const overlays = useOverlays()
const commands = useMemo(() => buildCompareCommands(left, right), [left, right])
useEffect(() => overlays.register('profile-compare', commands), [overlays, commands])
```

- [ ] **Adım 5: Kayda ekle**

```ts
import { ProfileCompare } from './profile-compare'
```

```ts
  { id: 'profile-compare', slot: 'rightRail', Component: ProfileCompare, modes: ['analyze'] },
```

- [ ] **Adım 6: Kapı ve gözle doğrulama**

```bash
cd frontend && npm run typecheck && npm run lint && npm test && npm run dev
```

Beklenen: `analyze` modunda sağ rayda; iki profil rotası haritada ayrı
renklerde.

- [ ] **Adım 7: Commit**

```bash
git add -A
git commit -m "feat(profile-compare): retype cells and overlay commands for analyze mode"
```

### Task 20: `time-axis` — `field` komutuna uyarla

**Dosyalar:**
- Taşı: `frontend/src/features/_pending/time-axis` → `frontend/src/features/time-axis`
- Değiştir: `frontend/src/features/time-axis/overlays.ts`, `useTimeAxis.ts`, `frontend/src/features/registry.ts`

**Arayüzler:**
- Tüketir: `useMission()` — `start`, `goal`, `planResult`; `useOverlays()`.
- Üretir: kayıt id'si `'time-axis'`, `modes: ['analyze']`.

- [ ] **Adım 1: Dizini çıkar**

```bash
cd frontend/src/features && git mv _pending/time-axis .
```

- [ ] **Adım 2: `start`/`goal` kullanımlarını doğrula — değişiklik beklenmiyor**

16 kullanım (`start` 9, `goal` 7). Kanonik `Cell` bir demet olduğu için
(bkz. Task 18 Adım 2) bunlar olduğu gibi kalır; dönüşüm gerekmez.

- [ ] **Adım 3: `overlays.ts`'i kanonik tiplere çevir**

Zaman ekseni gölge/aydınlık alanını `field` komutuyla boyuyor. Bu, tip
farkının en derin olduğu yer:

| eski | yeni |
|---|---|
| `data: Float32Array` | `values: (number \| null)[]` |
| boş hücre `NaN` | boş hücre `null` |
| `domain: [min, max]` | `ramp.min`, `ramp.max` |
| `ramp: 'thermal'` | `ramp.colors: Array<[number, number, number]>` |

Rampa durakları `colormap.ts`'ten okunur; isim orada zaten tanımlı olduğu için
yeni renk uydurulmaz.

- [ ] **Adım 4: Kayıt fonksiyonunu temizlik döndüren biçime çevir**

```ts
const overlays = useOverlays()
const commands = useMemo(() => buildTimeAxisCommands(slice), [slice])
useEffect(() => overlays.register('time-axis', commands), [overlays, commands])
```

- [ ] **Adım 5: `field` dönüşümünün maliyetini ölç (Risk 2)**

Tarayıcı konsolunda, en büyük ızgarayla bir dilim çizilirken:

```js
performance.mark('field-start')
// dilim değiştirilir
performance.mark('field-end')
performance.measure('field', 'field-start', 'field-end')
```

Dönüşüm ölçülebilir bir gecikme yaratıyorsa (kare başına ~16 ms'yi aşıyorsa),
`FieldCommand`'ı `values: (number | null)[] | Float32Array` kabul edecek şekilde
genişlet ve `draw2d.ts`'te iki durumu ayır. Sözleşmenin sahibi bu proje;
performans için tipi genişletmek meşrudur, sessizce yavaşlamak değildir.

- [ ] **Adım 6: Kayda ekle**

```ts
import { TimeAxis } from './time-axis'
```

```ts
  { id: 'time-axis', slot: 'bottomDock', Component: TimeAxis, modes: ['analyze'] },
```

- [ ] **Adım 7: Kapı ve gözle doğrulama**

```bash
cd frontend && npm run typecheck && npm run lint && npm test && npm run dev
```

Beklenen: `analyze` modunda alt şeritte; dilim kaydırıldığında gölge alanı
haritada güncelleniyor ve boş hücreler **boyanmadan** kalıyor (altındaki katman
görünür).

- [ ] **Adım 8: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat(time-axis): retype the shadow field onto the canonical command

The field command carries values as (number | null)[] rather than a
Float32Array, and an empty cell as null rather than NaN. Ramp stops come
from colormap.ts, which already names the thermal ramp, so no colour is
invented here.

The conversion was measured against the largest grid before landing; see
the plan's Risk 2 if a later grid makes it visible.
EOF
)"
```

### Task 21: `cost-explain` — telemetriyi kendi çeker

Faz 3'ün tek semantik kararı burada. Diğer sekiz feature `hoverCell`'e hiç
dokunmuyor; bu feature 7 kez kullanıyor ve `cellTelemetry`'yi 3 kez.

**Dosyalar:**
- Taşı: `frontend/src/features/_pending/cost-explain` → `frontend/src/features/cost-explain`
- Değiştir: `frontend/src/features/cost-explain/useCostExplain.ts`, `overlays.ts`, `frontend/src/features/registry.ts`

**Arayüzler:**
- Tüketir: `useFocusTelemetry()` — imleci izleyen `row`/`col`;
  `fetchCellTelemetry(row, col)`; `useOverlays()`.
- Üretir: kayıt id'si `'cost-explain'`.

- [ ] **Adım 1: Dizini çıkar**

```bash
cd frontend/src/features && git mv _pending/cost-explain .
```

- [ ] **Adım 2: Veriyi kanonik yoldan al**

Planın ilk sürümü `hoverCell` ve `cellTelemetry`'yi `MissionValue`'ya
ekletiyordu. Task 3 bunun yanlış olduğunu gösterdi: kanonik tipte bu iki alan
**bilerek** yok ve gerekçesi `MissionContext.ts`'te yazılı —

> A feature that needs the telemetry of a particular cell should fetch that
> cell: `fetchCellTelemetry(row, col)`.

Davranış korunur, kaynak değişir. `cost-explain` yine **imlecin altındaki**
hücreyi açıklar; imleç konumunu artık `useFocusTelemetry()`'den okur (o hook
`hoverPoint ?? goal ?? start`'ı izler, tam da bu feature'ın istediği şey) ve
`/api/cell-telemetry`'yi kendi çağırır.

Bu, App'ten bir yük almak anlamına da geliyor: telemetriyi tek tüketicisi
çekiyor, kokpit onu herkese yayınlamıyor.

```ts
const focus = useFocusTelemetry()
// Istek imlecle birlikte saniyede onlarca kez tetiklenebilir; hucre
// degismedikce yeniden cekilmez ve ucus halindeki istek iptal edilir.
useEffect(() => {
  const controller = new AbortController()
  fetchCellTelemetry(focus.row, focus.col, controller.signal)
    .then(setTelemetry)
    .catch(ignoreAbort)
  return () => controller.abort()
}, [focus.row, focus.col])
```

`selectedCell` bu feature tarafından **okunmaz**: kanonik tipte her zaman null
ve bir seçim değil, seçim yokluğunu bildiren bir alan.

- [ ] **Adım 3: `hoverCell` erişimlerini yeni kaynağa bağla**

7 kullanım `useMission().hoverCell` yerine `focus.row` / `focus.col`'a döner.
Demet açma (`const [row, col] = hoverCell`) tamamen kalkar; `FocusTelemetry`
zaten `row` ve `col` alanlarını ayrı ayrı taşıyor.

- [ ] **Adım 4: `overlays.ts`'i kanonik tiplere çevir**

Vurgulanan hücre `points` komutuyla çiziliyor: `PixelPoint` → `CellRef`,
`style.radius` → `style.radiusPx`.

- [ ] **Adım 5: Kayda ekle**

```ts
import { CostExplain } from './cost-explain'
```

```ts
  { id: 'cost-explain', slot: 'rightRail', Component: CostExplain },
```

- [ ] **Adım 6: Kapı ve gözle doğrulama**

```bash
cd frontend && npm run typecheck && npm run lint && npm test && npm run dev
```

Beklenen: fare haritada gezdirildiğinde — **tıklamadan** — sağ raydaki döküm
paneli hücre başına güncelleniyor. Yalnızca tıklamayla güncelleniyorsa
`selectedCell`'e bağlanmış demektir, geri alınmalı.

- [ ] **Adım 7: `_pending`'in boşaldığını doğrula**

```bash
ls frontend/src/features/_pending
```

Beklenen: boş.

- [ ] **Adım 8: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat(cost-explain): keep hover semantics, not selection

This is the one feature the hoverCell/selectedCell split actually touches;
the other eight never read either field. It explains the cost of the cell
under the pointer and fetches /api/cell-telemetry for it, so the panel has
to follow the cursor. Binding it to selectedCell would make it update only
on click, which is a different feature.
EOF
)"
```

---

## Faz 4 — Chatbot birleşir

### Task 22: `feature/ai-decision-chatbot`'u birleştir

**Dosyalar:**
- Merge: backend `ai_*.py` ve testleri (çakışmasız), `frontend/src/features/assistant/`, `frontend/src/api/assistant.ts`
- Çakışma çöz: `frontend/src/App.tsx`, `App.css`, `MapCanvas.tsx`, `api.ts`

**Arayüzler:**
- Üretir: `features/assistant/` — `Assistant` bileşeni; `postAiChat` istemcisi;
  `POST /api/ai/chat` ucu.

- [ ] **Adım 1: Merge'i başlat**

```bash
git merge origin/feature/ai-decision-chatbot
```

- [ ] **Adım 2: `add/add` çakışması olmadığını doğrula — bu planın sınavı**

Beklenen: `overlay/` ve `shell/` dosyalarında **hiç çakışma yok.** Task 3, 4 ve
6 bu dosyaları o daldan birebir aldığı için iki taraf aynı içeriği taşır.

`add/add` çakışması **görülürse** durulur: Faz 1'de bir dosya değiştirilerek
kopyalanmış demektir. Fark incelenir (`git diff origin/feature/ai-decision-chatbot -- <dosya>`),
sapma kasıtlıysa (Task 4'teki `draw2d.ts` gibi) bizimki korunur, değilse
düzeltilir.

- [ ] **Adım 3: Dört içerik çakışmasını çöz**

- `App.tsx`: **bizimki** taban. Chatbot'un kattığı tek şey `<GlobalOverlaySlot />`;
  o zaten Task 7'de yerinde. Chatbot'un slot ve provider satırları alınmaz.
- `App.css`: **bizimki** taban; chatbot'un `assistant.css`'i ayrı dosya olarak
  zaten geliyor, `App.css`'e karıştırılmaz.
- `MapCanvas.tsx`: kanonik `useOverlayCommands()`'ı çağıran hâl korunur.
- `api.ts`: iki taraf da yeni uç eklemiş; **ikisi de alınır**, çakışan tek şey
  import sırasıdır.

- [ ] **Adım 4: Backend testlerini çalıştır**

```bash
cd backend && python -m pytest test_ai_router.py test_ai_grounding.py \
  test_ai_evidence.py test_ai_chat_endpoint.py -q
```

Beklenen: hepsi geçer. Bu testler chatbot dalından değişmeden geldi.

- [ ] **Adım 5: Kapı**

```bash
cd frontend && npm run typecheck && npm run lint && npm test
```

- [ ] **Adım 6: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
merge: bring in the AI assistant and its backend

The four add/add conflicts this merge would normally carry did not appear:
Phase 1 took overlay/ and shell/ from this branch verbatim, so both sides
hold the same files. draw2d.ts is the deliberate exception and stays ours.

App.tsx keeps our shell; the only thing this branch adds to it is
GlobalOverlaySlot, which Phase 1 already mounted.
EOF
)"
```

### Task 23: Asistanı kaydet, maketi sil

**Dosyalar:**
- Değiştir: `frontend/src/features/registry.ts`
- Değiştir: `frontend/src/features/assistant/assistant.css`
- Sil: `frontend/src/components/Assistant/MissionAssistant.tsx`
- Değiştir: `frontend/src/App.tsx`

**Arayüzler:**
- Tüketir: `Assistant` (chatbot'tan), `useMission()`.
- Üretir: kayıt id'si `'assistant'`, `slot: 'globalOverlay'`.

- [ ] **Adım 1: Asistanı kanonik mission değerine bağla**

`features/assistant/index.tsx`, `useAssistant.ts` ve `aiContext.ts` bugün
chatbot dalının `MissionValue` şeklini bekliyor. Kanonik değerle farkları
uyarlanır: `activeViewMode` adı aynı, `start`/`goal` zaten `CellRef`,
`hoverCell` asistan tarafından okunmuyor.

- [ ] **Adım 2: Kayda ekle**

```ts
import { Assistant } from './assistant'
```

```ts
  // Yüzen, raylı değil: asistan görevin üstünde açılır ve iki ray da
  // kapalıyken çalışmaya devam etmeli.
  { id: 'assistant', slot: 'globalOverlay', Component: Assistant },
```

- [ ] **Adım 3: Göktuğ'un maketini sil**

```bash
git rm frontend/src/components/Assistant/MissionAssistant.tsx
```

`App.tsx`'ten `<MissionAssistant … />` ve import'u kaldırılır.

- [ ] **Adım 4: Görsel dili taşı**

`MissionAssistant.tsx` silinmeden önce görünümü `assistant.css`'e taşınır:
launcher düğmesinin konumu, pencere ölçüleri, gölge ve renkler. Mantık
taşınmaz — o dosyada `fetch` yoktu, `evidence` bir string literaliydi.

Taşınacak sınıflar `App.css`'te `lp-` önekiyle zaten tanımlıysa oradan
okunur; `assistant.css` yalnızca `.chat-launcher` ve `.chat-window`
kurallarını sahiplenir.

- [ ] **Adım 5: Kapı ve uçtan uca doğrulama**

```bash
cd backend && uvicorn app.main:app --port 8000 &
cd frontend && npm run dev
```

Tarayıcıda asistan açılır ve bir soru sorulur. Beklenen: yanıt
`POST /api/ai/chat`'ten geliyor (ağ sekmesinden doğrulanır), maket metni
görünmüyor, kanıt satırı gerçek uç yanıtından geliyor.

- [ ] **Adım 6: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat(assistant): register the real assistant, delete the mock

ai-scene's MissionAssistant was 386 lines with no fetch: its evidence line
was a string literal. The chatbot branch's assistant talks to
POST /api/ai/chat and is covered by the ai_* test suite. The look comes from
the mock, the behaviour from the real one.

It registers in globalOverlay rather than a rail: the assistant floats over
the mission and has to keep working with both rails collapsed.
EOF
)"
```

---

## Faz 5 — Temizlik

### Task 24: Ölü yolları ve geçici yapılandırmayı kaldır

**Dosyalar:**
- Sil: `frontend/src/features/_pending/` (boş)
- Değiştir: `frontend/tsconfig.json`, `frontend/eslint.config.js`
- Sil: `frontend/src/components/` (boşaldıysa)
- Karar: `frontend/src/TerrainView3D.tsx` ile `TerrainCanvas3D.tsx` ikiliği

**Arayüzler:** yok — bu görev yalnızca siler.

- [ ] **Adım 1: `_pending`'i ve iki yapılandırma satırını kaldır**

```bash
rmdir frontend/src/features/_pending
```

`tsconfig.json`'dan `"exclude": ["src/features/_pending"]` satırı silinir.
`eslint.config.js`'in ignores listesinden `'src/features/_pending'` çıkarılır.

- [ ] **Adım 2: `components/` altında ne kaldığını denetle**

```bash
find frontend/src/components -type f
```

Beklenen: yalnızca kabukta kalanlar — `TopBar/TopBar.tsx`,
`Fleet/FleetSelectionView.tsx`. Başka bir şey kaldıysa ya Faz 2'de atlanmıştır
ya da hiçbir yerden import edilmiyordur; ikisi de burada karara bağlanır.

- [ ] **Adım 3: `TerrainView3D` / `TerrainCanvas3D` ikiliğini çöz**

`TerrainView3D.tsx` chatbot ve ai-scene dallarında **birebir aynı** dosya,
`TerrainCanvas3D.tsx` ise ayrı bir uygulama. Hangisinin `App.tsx` tarafından
render edildiği bulunur:

```bash
grep -n "TerrainView3D\|TerrainCanvas3D" frontend/src/App.tsx
```

Render edilmeyen silinir. İkisi de kullanılıyorsa hangisinin hangi durumda
çizdiği bir yorumla yazılır ve ikisi de kalır.

- [ ] **Adım 4: Kapı**

```bash
cd frontend && npm run typecheck && npm run lint && npm test && npm run build
```

`npm run build` bu görevde ilk kez çalıştırılıyor: ölü dosya silmek bir
üretim derlemesini kırabilir ve `typecheck` bunu her zaman yakalamaz.

- [ ] **Adım 5: Beş modun tamamını gözle doğrula**

```bash
cd frontend && npm run dev
```

Kontrol listesi:
- `fleet` — hangar görünümü, rover kartları, ray yok
- `plan` — sol rayda kurulum + anlık görüntü + ROS + köken; sağ rayda bağlam +
  koridor + poz + doğrulama + maliyet dökümü
- `analyze` — sağ rayda rota denetçisi + profil karşılaştırma; alt şeritte
  oynatma + zaman ekseni
- her modda — asistan sağ altta açılıyor ve gerçek yanıt veriyor
- harita üstünde — katman seçici ve çözüm göstergesi doğru yerde

- [ ] **Adım 6: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
chore: remove the pending-features scaffold and dead paths

_pending is empty, so the tsconfig exclude and the eslint ignore that kept
it out of the build go with it. Also settles the TerrainView3D /
TerrainCanvas3D duplication that came in from two branches at once.
EOF
)"
```

### Task 25: `berke-3d`'ye birleştir

**Dosyalar:** yok — yalnızca dal işlemi.

- [ ] **Adım 1: Son kapıyı tam çalıştır**

```bash
cd frontend && npm run typecheck && npm run lint && npm test && npm run build
cd ../backend && python -m pytest -q
```

Dördü de geçmeden bu göreve devam edilmez.

- [ ] **Adım 2: `berke-3d`'ye merge et**

```bash
git checkout berke-3d
git merge --no-ff berke-3d-shell
```

Beklenen: çakışma yok. `berke-3d` bu iş boyunca hiç değişmediği için
`berke-3d-shell` onun düz bir soyu.

- [ ] **Adım 3: Ekibe haber ver**

`feature/ai-decision-chatbot` ve `goktug/ai-scene` artık `berke-3d`'nin
içinde. Kendi dallarında çalışmaya devam edenler `git merge berke-3d` yapıp
kendi taraflarında çözmeli.

---

## Öz Değerlendirme

**Spec kapsamı.** Spec'in her bölümü bir göreve bağlandı: kanonik sözleşme
(Task 3–6), mod boyutu (Task 5), dal stratejisi (Task 1, 25), altı faz
(Task 1–24), Risk 1 `hoverCell` (Task 21), Risk 1b park etme (Task 2, 24),
Risk 2 `field` performansı (Task 20 Adım 5), Risk 3 canvas konumlandırma
(Task 6 Adım 3), Risk 4 `App.css` (Task 22 Adım 3), `draw2d` istisnası
(Task 4), asistan seçimi (Task 23).

**Bilinen boşluk.** Faz 2'de `MissionSnapshotPanel`, `MissionSetupPanel`,
`MissionContextPanel` ve `RouteAnalysisInspector`'ın `useMission`'dan tam
olarak hangi alanları okuduğu, dosyaların prop arayüzleri okunmadan
kesinleştirilemedi; her görevin 2. adımı bu eşlemeyi yapan kişiye bırakılıyor.
Eksik çıkan alan `mission/types.ts`'e eklenir ve `App.tsx`'te doldurulur —
Task 14 Adım 3 bu durumu açıkça öngörüyor.

**Tip tutarlılığı.** `CellRef` (Task 3'te tanımlanır) Task 4, 15–21'de aynı
adla kullanılıyor. `selectFeatures` (Task 5) Task 6'da aynı imzayla çağrılıyor.
`OverlayCommand` (Task 4) Task 15, 16, 19, 20, 21'de tutarlı.
`MissionMode` (Task 3) Task 5, 6 ve tüm kayıt satırlarında aynı.
`MissionValue` Task 7, 12, 13'te büyüyor; her büyüme hem `types.ts`'e hem
`App.tsx`'e yazılıyor.
