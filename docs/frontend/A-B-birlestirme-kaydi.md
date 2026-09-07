# A izi + B izi birleştirme kaydı

`goktug/tuna-backend-A` ← `origin/yedek/kisi-B`. Merge commit `f6f3365`.

`backend-enhance-entegrasyon-2-kisi.md` işi A ve B olarak bölmüştü. Bu belge iki izin nasıl
birleştiğini ve **hangi kararın neden alındığını** tutar. Diff'in göstermediği şey burada.

İki izin kendi kayıtları duruyor ve değiştirilmedi: `A-izi-ilerleme.md`,
`entegrasyon-durum-kisi-B.md`.

---

## Neden kolay bir merge değildi

İki bağımsız sebep:

**1. A'nın işi hiç commit edilmemişti.** Merge başlarken `HEAD`, merge-base'in **0 commit**
ilerisindeydi — 107 dosyalık iş yalnızca working tree'de duruyordu. Tek bir çakışma onu
silebilirdi. Bu yüzden merge'den önce 11 commit'e bölünüp `yedek/A-izi-tamamlandi` dalı ve
`A-izi-son` etiketi ile sabitlendi.

**2. İki taraf da §3'ün dört paylaşılan primitifini yazdı.** A, B'nin izi yokken derlenebilmek
için `capability.ts`, `errors.ts`, `routeIdentity.ts`, `missionTime.ts` ve `plan-request/`'i
kendisi yazmıştı (`A-izi-ilerleme.md` §"B kişisinin primitifleri" bunu açıkça kaydediyor). B de
aynı beşini yazdı. Sonuç metin çakışması değil **API uyuşmazlığı** oldu: A `status` discriminant
kullanıyordu, B `state`; A `ClassifiedError` döndürüyordu, B `Failure`. Her tarafın tüketicileri
kendi sürümüne yazılmıştı.

---

## Kararlar, ölçümle

Hiçbiri tercihle verilmedi. Her satırın arkasında sayılmış bir şey var.

| Primitif | Karar | Ölçüm |
|---|---|---|
| `mission/capability.ts` | **A'nınki** | A'da 23 importer, B'de **1** — ve o bir tane B'nin kendi testi. B'nin hiçbir feature'ı kendi capability'sini tüketmiyordu. |
| `mission/routeIdentity.ts` | **B'ninki** | A'nınki dört sabit camelCase anahtar tanıyordu (`requireEarthVisibility`, …); B'ninki gönderilen wire nesnesinin tamamı üzerinde jenerik ve `useAnalysisJob` onu zaten tüketiyordu. A'nın testinin kapsadığı her durum B'nin testinde de var. |
| `net/errors.ts` | **Birleştirildi** | İki tüketici kümesi de canlıydı (A 12, B 7). Seçmek bir tarafı yeniden yazmak demekti. |
| `mission/missionTime.ts` | **A'nın şekli, B'nin epoch'u** | A'nın `MissionTime` nesnesinin 9 tüketicisi var ve dilim aritmetiği ona bağlı; B'nin katkısı sabit epoch **kararı**ydı. |
| `features/plan-request/` | **Birleştirildi** | İkisi birbirini tamamlıyordu; aşağıya bakın. |

### `errors.ts` — iki söz dağarcığı, tek sınıflandırma

`classifyFailure`, `classifyError`'ın bir **izdüşümü** olarak yazıldı. İki görünüm de duruyor,
ama 404'ün nerede karara bağlandığı **tek bir yer**; dolayısıyla ikisi ileride "rota hayatta kalır
mı" sorusunda birbirinden ayrışamaz. `errors.test.ts` bunu ayrıca sınıyor.

Birleştirme sırasında **iki gerçek kusur** çıktı ve düzeltildi:

- **`instanceof ApiError` yanlış cevabı veriyordu.** Bu kod tabanı `ApiError`'ı **iki kez**
  tanımlıyor — `net/client.ts:4` ve `api/client.ts:23`, aralarında ilişki yok. `instanceof` birini
  tanıyıp diğerini tanımıyor, ve düştüğü dal eksik bir cache'i **transport hatası** olarak
  raporluyordu. `capability.ts`'te aynı kusurun sonucu daha kötüydü: eksik cache `error` olarak
  boyanıyordu — modülün var olma sebebi olan kuralın tam tersi. İkisi de artık `status`'ü yapısal
  okuyor.
- **503 hiç sınıflandırılmamıştı** ve `backend-fault`'a düşüyordu. Backend, grid yüklü değilken
  503 döndürüyor; bu bir dağıtım durumu, arıza değil.

Bir de **gerçek bir anlam ayrımı** çıktı. Aynı üç kelime, iki karşıt anlam:

```
planner   "goal (300, 300) falls in coarse block (75, 75) at coarsen=4,
           which is not traversable"        -> operatör hedefi geçilemez bir
                                               yere koydu. Bir misyon bulgusu.
analysis  "path_states: state 14 (49, 21, 14) is not traversable"
                                            -> planlanmış bir rotayı yanlış
                                               hücre boyunda gönderdik. Bizim.
```

Hiçbir metin listesi bu ikisini ayıramaz. `endpoint` ipucu tam olarak bunun için var: bir
**analiz**, zaten var olan bir rota *hakkında* sorulur, dolayısıyla misyonun imkânsız olduğunu
keşfedemez.

### `plan-request/` — iki katlama noktası, bir liste

İki taraf da haklıydı ve birbirini tamamlıyordu:

- **B ölçtü:** `POST /api/plan` `require_safe_haven` ve kardeşlerini 200 ile kabul edip
  **sessizce yok sayıyor** — rota kısıtsız haliyle bayt-bayt aynı dönüyor ve yanıtta bunu söyleyen
  hiçbir alan yok.
- **A çözdü:** A'nın `PlanRequestContext`'i `endpoint: 'plan' | 'plan-4d'` taşıyor; üç çevresel
  katkıcı yalnızca `plan-4d` altında alan katıyor ve anahtarları 4-B "Plan through time"
  düğmesinin yanında duruyor.

Birleşik hâl:

```
store.ts -> readPlanConstraints()   -> POST /api/plan      (2-B)   fields(state)
applyPlanRequestContributors()      -> POST /api/plan-4d   (4-B)   fields(state, context)
```

Bağlam istemeyen tek katkıcı `risk` — ve o, `/api/plan`'ın gerçekten uyguladığı tek alan.
Diğer dördü bağlamsız çağrıldığında `null` dönüyor. **Koruma bu**: unutulabilecek bir kontrol
değil, imzanın kendisi.

İki yan sonuç:

- `mission-constraints` paneli artık `STORE_CONTRIBUTORS` render ediyor — listeyi elle ikinci kez
  yazmak yerine her katkıcıya sorarak türetilen liste. Aksi hâlde panelde, yanındaki düğmeye
  basıldığında hiçbir şey yapmayan dört anahtar dururdu.
- Store'un `rebuild()`'i artık `mergeContributedFields` kullanıyor, düz `Object.assign` değil.
  `roughnessWeightContributor` `{ weights: { w_roughness } }` döndürüyor ve düz bir assign, dört
  temel ağırlığı tek anahtarlık bir nesneyle **ezerdi** — sürgüler dördü gösterirken rota tek
  kritere göre yeniden planlanırdı.

### Misyon saati: sabit epoch

`SESSION_MISSION_TIME.startUtc` artık `new Date()` değil, `MISSION_EPOCH_UTC`
(`2026-09-07T00:00:00Z`). A'nın şekli (epoch + offset + span + sliceHours) korundu çünkü dokuz
tüketici ve dilim aritmetiği ona bağlı; B'nin gerekçesi alındı çünkü daha güçlü: keyfi bir epoch
tekrarlanamayan bir demo demek ve bazı ürünler belirli epoch'lar için kurulmuş cache'lerden
okunuyor. `A-izi-ilerleme.md`'de kayıtlı SPICE çökmesi de keyfi bir epoch altında görülmüştü.

B'nin iki tüketicisi (`useStressTest`, `useUncertainty`) artık `missionTimeUtc(missionTime)`
çağırıyor; epoch yoksa gövde `null` dönüyor ve iş **çalışmıyor** — yerine uydurma bir "şimdi"
konmuyor.

---

## Satır sonları

B'nin ilk commit'i (`7c2e927`) repo geneli bir renormalize'dı ve A'nın CRLF dosyaları
(`App.tsx`, `mission/types.ts`, `features/registry.ts`, `api.ts`, `colormap.ts`, `net/types.ts`)
tam olarak B'nin LF'e çevirdikleriydi. Merge'den **önce** aynı `.gitattributes` alınıp
`git add --renormalize .` koşuldu (commit `557ad3e`, 19 dosya, `.gitattributes` dışında hepsi saf
satır sonu). Bu yapılmasaydı altı dosya her satırında çakışırdı ve gerçek değişiklikler gürültünün
içinde kaybolurdu.

`core.autocrlf=true` yerelde açık; yeni dosyalar zaten LF olarak index'e giriyordu, o yüzden
renormalize yalnızca eski CRLF blob'larına dokundu.

---

## Doğrulama

| Kontrol | Sonuç |
|---|---|
| `npm run typecheck` | temiz |
| `npm run lint` | temiz (`--max-warnings 0`) |
| `npx vitest run` | **38 dosya / 427 test** (A 332 + B'nin paketi + 6 yeni) |
| `npm run build` | 241 modül, temiz |
| Dosya kaybı denetimi | B'nin ve A'nın her dosyası mevcut (`git ls-tree` karşılaştırması) |
| Feature kaydı | 33 kayıt, çift yok — B'nin 26'sı + A'nın 7'si |

**İki non-regression testi de yeşil**, ve bu merge'ün en güçlü sinyali: iki bağımsız test, iki
farklı katkıcı tasarımına karşı aynı kuralı sınıyor ("tüm ileri kısıtlar kapalıyken istek gövdesi
bayt-bayt eski").

- `net/planRequest.nonregression.test.ts` — 4-B gövdesi (A)
- `__tests__/nonRegression.test.ts` + `features/plan-request/planRequest.test.ts` — 2-B gövdesi (B)

### Canvas yerleşimi

`canvasOverlay` yuvasında artık A'nın `analysis-layers`'ı ile B'nin `map-legend`'i birlikte.
Çakışmıyorlar: birincisi `top: 68px; right: 24px`, ikincisi `bottom: 18px; left: 50%`.

---

## Backend: ölçüldü, merge kaynaklı değil

Bu merge `backend/` ve `lunapath/src/` altında **hiçbir dosyaya dokunmadı** — B'nin dalı da
dokunmamıştı (`git log b8143f4..HEAD -- backend/ lunapath/src/` boş). Yine de tam suite koşuldu ve
iki şey çıktı; ikisi de merge'den önce de oradaydı.

**1. Ağır modüller çok yavaş.** `python -m pytest -q` 47 dakikada bitmedi. Dosya başına
ölçüldüğünde on üç modül 75 saniyeyi aşıyor — hepsi gerçek veri okuyanlar:

```
test_benchmark_real_data.py          test_safe_haven_real_grid.py
test_earth_visibility_real_grid.py   test_safety_monitor_real_grid.py
test_illumination_corridor_real_grid.py  test_slip_calibration_real_grid.py
test_plan_4d_real_grid.py            test_survival_real_grid.py
test_risk_sweep_real_grid.py         test_thermal_dwell_real_grid.py
test_thermal_model.py                test_uncertainty_real_grid.py
```

Geri kalan her modül 20 saniyenin altında ve geçiyor. `CLAUDE.local.md`'deki "~4.5 dakika" rakamı
80 m grid dönemine ait; 5 m'de bu modüller ağırlaştı.

**2. `test_uncertainty_real_grid.py` içinde bir hata var, ve bilinen sınıftan:**

```
test_the_surface_two_pass_horizon_is_the_production_cube
AssertionError: assert 12.564656891849795 < 5.0
```

Eşik **Site11** üzerinde kalibre edilmiş — testi ekleyen commit'in adı bunu söylüyor
(`64acd65 feat(uncertainty): ... NASA's 100 Site11 DEM clones`). Yerel veri başka bir pencere.
`test_plan_4d_real_grid.py`'nin `CLAUDE.local.md` §3'te kayıtlı üç hatasıyla **aynı sınıf**: başka
bir bölge/çözünürlük için seçilmiş sabit sayılar. Bu modüller `metadata.json` yokken tümüyle
atlandığı için CI yeşil; yalnızca yerel pipeline çıktısı olan makine görüyor.

Hızlı doğrulama (15 saniye, 102 test, hepsi geçer):

```bash
cd backend
"C:/Users/goktugtabak/AppData/Local/Programs/Python/Python311/python.exe" -m pytest -q   test_plan_endpoint.py test_cost_vec.py test_review_fixes.py
```

---

## Bu makinede iş gören not

**`backend/.venv` artık boş değil ve `python`'u gölgeliyor.** `CLAUDE.local.md` onu "yalnızca pip
ve setuptools" diye tanıtıyor; bu artık doğru değil — dolu, ama içindeki `fastapi 0.115.6` kırık
(dairesel import). `backend/.venv/Scripts` PATH'te olduğu için bare `python` venv'inkine çözülüyor
ve pytest **37 collection hatası** veriyor. Merge ile ilgisi yok: merge `backend/` altında hiçbir
dosyaya dokunmadı ve B'nin dalı da dokunmamıştı.

Sistem yorumlayıcısını açıkça çağırın:

```bash
cd backend
"C:/Users/goktugtabak/AppData/Local/Programs/Python/Python311/python.exe" -m pytest -q
```
