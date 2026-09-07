# 3-B veri hattı bağımsız denetimi

**Tarih:** 2026-08-30
**Dal:** `backend/physics` (denetim aralığı `aca8aaf..HEAD`, 6 commit)
**Kapsam:** `backend/app/terrain.py`, `backend/app/illumination_series.py`,
`backend/app/data_loader.py` (1 satırlık ekleme), `backend/app/main.py`'nin
yeni uç noktaları (`GET /api/terrain`, ikili (`format=f32`) katman/seri
yolları), `backend/test_terrain.py`, `backend/test_terrain_api.py`,
`backend/test_terrain_real_grid.py`, `docs/frontend/3b-veri-sozlesmesi.md`.
**Yazar:** `tunadeniz1304` — round 1-4 backend denetimlerinden (`docs/superpowers/reviews/2026-08-30-backend-review*.md`)
**sonra** eklendiği için hiçbir turdan geçmemişti; bu denetim onu kapatıyor.
**Yöntem:** Kod bağımsız bir reviewer ajanı tarafından, plana ve önceki round
bulgularına bakılmadan, gerçek dosyalar (`ephemeris.py`, `cost_cube.py`,
`data_loader.py`, `main.py`, değişiklik öncesi `illumination_series.py` blob'u
dahil) okunarak incelendi. Üç.js frontend'deki eksen/döndürme matematiği elle
doğrulandı, `str2et` çağrılarının tamamı `_ensure_kernels` sırasına göre tek
tek listelendi.

**Sonuç:** 12 bulgu — 0 yüksek, 5 orta, 7 düşük. Hiçbiri veri bozulması ya da
mevcut uç noktalarda kırılma yaratmıyor; ikisi (seri endpoint'inin bellek
bütçesi ve CORS header'ları) gerçek risk taşıyor.

---

## Öne çıkan sonuç: kendiliğinden ifşa edilen SPICE hatası, ifşa edildiğinden daha ciddi

Planın kapanış notları (`docs/superpowers/plans/2026-08-30-3b-veri-hatti.md`,
"plandan sapmalar" #3) bir hatayı kendiliğinden bildirmişti: `spice.str2et`,
kernel havuzunu yükleyen `_ensure_kernels`'ten önce çağrılıyordu, soğuk süreçte
`SPICE(NOLEAPSECONDS)` fırlatıyordu, geniş bir `except` bunu sessizce statik
seriye çeviriyordu. İmplementer bunu "soğuk süreç" sorunu diye tanımlamıştı.

**Bağımsız inceleme daha kötüsünü buldu:** hata soğuk süreçle sınırlı değildi.
İstisna `_ensure_kernels`'e hiç ulaşmadan fırlıyordu, dolayısıyla kernel havuzu
**asla** yüklenmiyordu ve bir sonraki çağrı da aynı şekilde başarısız oluyordu.
`main.py`'de bu modüle giden başka hiçbir SPICE giriş noktası yok. Sonuç:
çalışan bir uvicorn sürecinde `/api/plan-4d`, zamanla değişen bir aydınlanma
serisi **hiçbir zaman** üretemiyordu — "bazen" değil, hiçbir zaman. Yalnızca
pytest altında çalışıyor gibi görünüyordu çünkü kardeş test modülleri aynı
Python sürecine kernel'i önceden yüklüyordu — round 3'ün M-1 bulgusunun yeşil
görünmesinin de sebebi bu.

**Düzeltme doğru ve tam:** ağaçtaki dört `str2et` çağrı yeri tek tek kontrol
edildi (`ephemeris.py`, `skyline.py`, `illumination_series.py`'nin iki yeri);
hepsi artık `_ensure_kernels`'ten sonra çağrılıyor. `skyline.py`'de zaten bu
sırayı açıklayan bir yorum vardı — bilgi kod tabanında mevcuttu, yeni modül
onu miras almamıştı.

**Tek gerçek eksik:** düzeltmeyi doğrulayan testler (`test_series_is_genuinely_time_varying`,
`test_manifest_and_binary_report_the_same_model`) `@needs_horizon` arkasında,
ve `horizon_map.npy` `.gitignore`'da — yani CI'da ve taze bir klonda muhtemelen
**skip** ediliyorlar, geçmiyorlar. "98 test geçti" rakamı skip'i pass'ten
ayırt etmiyor. Davranış değiştiren, bilinçli bir kısıt ihlaliyle gerekçelenen
bir düzeltme, varsayılan ortamda hiç çalışmayan testlerle korunuyor —
sessizce geri alınabilir. **Öneri:** `spiceypy`'yi mock'layan, `furnsh`
çağrılmadan `str2et` çağrılırsa patlayan, ucuz ve her zaman çalışan bir test
eklenmeli.

---

## Orta

### O-1 — Seri endpoint'inin bellek bütçesi, yanıt boyutunu ölçüyor, gerçek çalışma belleğini değil

`backend/app/main.py:1517-1537`. Bütçe kontrolü **downsample edilmiş** çıktı
üzerinden hesaplanıyor, ama `build_shadow_series` **tam çözünürlükte** çalışıp
dilim başına ayrı bir 500×500 float64 dizisi tutuyor:

```
GET /api/illumination-series?n_slices=1000&downsample=50&format=f32
  bütçe kontrolü: 1000 * 10*10 * 4  = 400 KB  -> geçer
  gerçek ayırma:  1000 * 500*500*8  = 2.0 GB
```

Kimlik doğrulama ya da rate limit yok — çıplak bir GET isteğiyle tetiklenebilir.
Aynı kök neden `/api/plan-4d`'de de var (önceden var olan, kapsam dışı) ama
burada ilk kez düz bir URL'den erişilebilir hale geliyor. **Düzeltme:**
`build_shadow_series` çağrılmadan önce `n_slices * base_shadow.size * 8`
üzerinden ikinci bir kontrol eklenmeli, ya da `step` seri inşasına daha erken
sokulmalı.

### O-2 — Seri endpoint'inin `X-Series-*` header'ları CORS allowlist'inde değil

`main.py:130`, `expose_headers`'ı yalnızca `BINARY_LAYER_HEADERS` (`X-Layer-*`)
ile dolduruyor. Seri yanıtı (`main.py:1547-1559`) `X-Series-Field/Slices/Rows/Cols/...`
set ediyor — hiçbiri expose edilmiyor. Cross-origin bir tarayıcıda bunlar
`undefined` okunur; modülün kendi docstring'inin ve CORS testinin önlemeye
çalıştığı hatanın ta kendisi, bir endpoint öteye taşınmış. Ayrıca seri
`X-Layer-Order: "row-major"` diyor ama manifest "slice-major, sonra row-major"
diyor — header-only bir tüketici zaman eksenini kaçırır (manifest'teki
`binary_format.shape` sayesinde bugün kırılmıyor, ama sözleşme yarım
uygulanmış). **Düzeltme:** `terrain.py`'ye bir `SERIES_HEADERS` tuple'ı
eklenip `expose_headers`'a katılmalı, CORS testi ikisini de kapsayacak şekilde
genişletilmeli.

### O-3 — Seri'nin dilim-sırası sözleşmesini varsayılan pakette doğrulayan test yok

`test_series_binary_is_slice_major_then_row_major`, senkron fixture'ın
`start_utc` taşımaması yüzünden her dilimin bayt-bayt aynı olduğu bir seriye
karşı çalışıyor — hiçbir permütasyon tespit edilemez. Gerçek sırayı doğrulayan
tek test (`test_series_is_genuinely_time_varying`) `@needs_horizon` arkasında,
yani O-genel bulgudaki aynı sebeple varsayılan pakette **çalışmıyor**.
Yayınlanan "slice-major, sonra row-major" sözleşmesi bu haliyle doğrulanmamış.
**Düzeltme:** fixture'a `build_shadow_series`'i monkeypatch'leyen sentetik,
zamanla değişen bir seri verilip `cube[i].mean()`'in kesin artan olduğu
doğrulanmalı.

### O-4 — `test_series_temperature_uses_the_planner_recipe` neredeyse totolojik

Statik seri altında `target == state` her dilimde, dolayısıyla `relax_surface_c`
no-op oluyor ve test, gevşetme sırasının `build_cost_cube` ile gerçekten
eşleşip eşleşmediğini doğrulamıyor. Round 4'ün H-3 düzeltmesini (başlangıç
durumu = uzun-vade dengesi, yıllık zirve değil) doğru kilitliyor ama isminin
vaat ettiği "aynı reçete" iddiasını kanıtlamıyor.

### O-5 — `test_terrain_real_grid.py`'nin skip koşulu, gitignore'lu olmayan bir dosyayı kontrol ediyor

`metadata.json` **commit'li** bir dosya (`.gitignore`'daki `data/processed/`
kuralı repo köküne bağlı, `lunapath/data/processed/`'i eşlemiyor — yalnızca
`*.npy` gerçekten ignore'lu). Taze bir klonda guard hiç tetiklenmiyor,
başlangıçta grid yüklenemiyor, `app.state.grids` `None` kalıyor, her istek
503 yerine `KeyError: 'grid'` ile patlıyor — tam olarak üç-dosyalı ayrımın
önlemeye çalıştığı sonuç. `test_plan_4d_real_grid.py`'de aynı desen zaten var
(bu bir regresyon değil, miras kalan bir kalıp), ama yeni dosyanın kendi
docstring'i gerekçeyi açıkça söylüyor ve guard onu uygulamıyor. **Düzeltme:**
guard `elevation_grid.npy` (ya da herhangi bir `.npy`) üzerinden yapılmalı.

---

## Düşük

- **D-1** — `data_loader.py`'nin tek satırlık `window_offset` eklemesi
  aslında "davranış değişmez" iddiasının aksine `/api/layers`, `/api/load-preprocessed`,
  `/api/load-dem` yanıtlarına yeni bir metadata alanı ekliyor. Zararsız ama
  ikinci, kayıt altına alınmamış bir kısıt sapması — bir insanın onaylaması
  iyi olur.
- **D-2** — `encode_layer_f32`, sonlu ama float32 aralığını (~3.4e38) aşan
  değerlerde teorik olarak hâlâ ±inf üretebilir (NaN dönüşümünden SONRA
  yapılan cast sırasında). Bugün hiçbir katman bu büyüklüğe ulaşmıyor ama
  docstring "yalnızca NaN"ı mutlak olarak vaat ediyor. Cast sonrası bir
  `np.isfinite` kontrolüyle iki satırda kapanır.
- **D-3** — Query string'ler el ile f-string ile kuruluyor, URL-encode
  edilmiyor (`main.py:1440,1576-1580`). `start_utc` gibi kullanıcı girdisi
  (`+` işareti içeren bir UTC offset) round-trip'te bozulabilir.
- **D-4** — `_series_field_cube`'un docstring'i `build_cost_cube`'u "adım
  adım" yansıttığını iddia ediyor; termal reçete aynı ama uzamsal indirgeme
  farklı (`coarsen_grid(how="mean")` vs. `[::step, ::step]`) —
  `downsample=1`'de özdeş, üzerinde ayrışıyor. Kod `/api/layers`'ın kendi
  downsample yaklaşımıyla tutarlı, sadece docstring yumuşatılmalı.
- **D-5** — `test_terrain_real_grid.py`'nin modül-kapsamlı `client` fixture'ı
  `app.state.grids`'i teardown'da temizlemiyor (`test_plan_4d_real_grid.py`
  bunu açıkça yapıyor). Bugün zararsız, `-p randomly` altında ya da gelecekte
  bir tuzak.
- **D-6** — `illumination_series.py`, `ephemeris.py`'den özel (`_`) bir
  yardımcıyı (`_ensure_kernels`) doğrudan import ediyor — düzeltme için doğru
  karar ama private bir ismi modül sözleşmesinin parçası yapıyor. Öneri:
  `ephemeris.py`'ye `_ensure_kernels`'i kendi çağıran, tüm `str2et` çağrı
  yerlerinin kullanacağı bir `utc_to_et()` sarmalayıcı eklensin.
- **D-7** — `terrain_manifest`, `rows`/`cols` için `metadata["shape"]`'e
  güveniyor, `binary_layer_headers` ise dizinin gerçek shape'ini raporluyor.
  İkisi bir gün ayrışırsa manifest'in `bytes_per_layer`'ı yanıltıcı olur.

---

## Güçlü yanlar (kayda değer)

- `terrain.py` gerçekten saf — hiçbir FastAPI import'u yok, `main.py`'nin
  eklemeleri gerçekten sadece kablolama.
- `+inf` → NaN dönüşümü **ikili yolda özellikle** ve doğru uygulanmış, üç
  farklı test açısıyla kapsanmış (birim testi, `grids_for_rover` üzerinden
  gerçek bir inf'i tetikleyen bir API testi, gerçek grid üzerinde NaN sayısı
  çapraz kontrolü).
- 8×6 kare-olmayan fixture gerekçesi gerçekten tutuyor — transpoze/eksen
  hatalarını yakalayan somut assertion'lar var (bu projenin ROS 2 fazının
  aynı sebeple harcadığı özenin bir benzeri).
- Manifest↔ikili tutarlılığı prosa değil, gerçek testlerle doğrulanmış
  (`binary_url`'lerin gerçekten fetch edilebilir olduğu, min/max/nodata'nın
  eşleştiği).
- Docs'taki three.js kod parçası **doğru** — eksen/döndürme matematiği elle
  çapraz kontrol edildi, tutarlı çıktı.
- Round 1-4'ün kurduğu "ölçerek doğrula, iddiayı prosa'ya bırakma" disiplini
  bu parçada da sürüyor.

---

## Genel değerlendirme

**Mergeye hazır mı?** Düzeltmelerle birlikte.

**Gerekçe:** İkili tel formatı, kullanıldığı her yolda doğru ve dürüst
uygulanmış — `+inf`→NaN dönüşümü özellikle ikili yolda, encoder gerçekten
saf, transpoze-yakalayan fixture gerekçesi gerçek. Mergeden önce ele alınması
gereken şey seri endpoint'inin katman endpoint'ine göre ikinci sınıf
muamele görmesi: header'ları cross-origin okunamıyor, yayınlanan
dilim-sırası sözleşmesi varsayılan pakette doğrulanmıyor, bayt bütçesi
yanıtı değil ~2 GB'lık gerçek çalışma belleğini ölçmüyor. SPICE düzeltmesi
gerçek ve az-raporlanmış bir bulgu; tek gerçek eksiği, gitignore'lu ufuk
önbelleği yokken hiçbir testin onu doğrulamaması.
