# A1 — Safe Haven haritası, "50 saat karanlık" kuralı ve time-to-safe-haven — Tasarım Belgesi

**Tarih:** 4 Eylül 2026
**Branch:** `berke-3d-backendEnhance`
**Kaynak:** [12_faktor_backend_ozellik_arastirmasi_2026-09-03.md → A1](../../research/12_faktor_backend_ozellik_arastirmasi_2026-09-03.md)
**Bağımlılık:** A4 (Dünya görünürlüğü serisi, `earth_visibility.py`) — tamamlandı.
**Kapsam:** yalnızca `backend/app/`, `backend/test_*.py`, `scripts/`, `docs/`. Frontend koduna dokunulmuyor; `docs/frontend/3b-veri-sozlesmesi.md`'ye ek bölüm yazılıyor.

---

## Amaç

VIPER'ın traverse planı "leg"lerden oluşur ve her leg bir **Safe Haven (SH)**'da
biter: Dünya ufkun altındayken (ayın ~2 haftası) rover komut alamaz, bu yüzden
o dönemi tek başına atlatabileceği bir yerde park etmiş olmalıdır. NASA'nın
tanımı (Shirley & Balaban 2022; Ennico-Smith vd. 2023), birebir:

> *Safe Haven: Dünya ufkun altındayken kesintisiz gölge süresi 50 saati
> geçmeyen ve rover'ın hareketsiz beklerken güç üretebildiği konum.*

LunaPath'te bugün `corridor._safe_haven_indices` uzun-dönem gölge oranına
göre statik bir küme üretiyor; `h_max_shadow_h` rover başına var (LPR-1 için
50 saat, VIPER'ın min-power dayanımıyla aynı). Eksikler: (a) SH zamana bağlı
değil, (b) Dünya görünürlüğüyle ilişkilendirilmiyor, (c) "buradan SH'a kaç
saat" katmanı yok, (d) planlayıcı SH'a ulaşmayı kısıt olarak taşımıyor.

Tek cümlelik iddia: **A4'ün Güneş + Dünya serileri bir Ay ayı boyunca
koşturulur; her hücre için "Dünya yokken en uzun kesintisiz karanlık" ölçülür
ve rover'ın `h_max_shadow_h` dayanımıyla karşılaştırılır; çıkan SH kümesinden
saat cinsinden geri-Dijkstra ile time-to-safe-haven katmanı üretilir; 4-B
planlayıcı her durumda "Dünya batmadan SH'a yetişebilir miyim" kuralını taşır
ve SHERPA'nın marj metriklerini (time-to-sun-shadow, time-to-DSN-shadow,
time-to-0-SOC) raporlar.**

## Mevcut durumdan kullanılanlar (yeniden yazılmaz)

| Yetenek | Kod | Bu tasarımda rolü |
|---|---|---|
| `body_track_for_series(..., body="SUN"/"EARTH")`, `_grid_north_azimuth`, `_parse_start_utc` | `illumination_series.py` | Bir Ay ayı boyunca Güneş ve Dünya izi |
| `illuminated_mask(horizon, az, el)` (sentinel kuralı dahil) | `illumination.py` | Adım başına "aydınlık mı" ve "Dünya görünür mü" maskeleri |
| `horizon_map.npy` (iki ölçekli, 72×500×500) | `illumination_series.horizon_cache_path` | Tek ufuk küpü |
| `build_earth_visibility_series`, `earth_visible_mask` | `earth_visibility.py` | Plan ufku içindeki Dünya küpü (A4) |
| `h_max_shadow_h` rover başına | `constants.py` | SH eşiği; profil değişince harita değişir |
| `gated_move_count` kapıları (adım eğimi, yanal eğim, köşe kesme), `edge_travel_time_s` trapez | `pathfinder_4d.py`, `cost_engine.py` | tts grafı **aynı** kapılar ve aynı kenar süreleriyle kurulur |
| `coarsen_traversable` (blok üzerinden AND) | `cost_cube.py` | SH ve Dünya küpü kaba gride tutucu indirgenir |
| `REJECTION_KEYS`, `no_path_reason_4d`, zarf takibi (batarya, gölge saati) | `pathfinder_4d.py` | Yeni `safe_haven_deadline` red anahtarı aynı kalıba eklenir |
| `encode_layer_f32`, `binary_layer_headers`, `_check_series_budget` | `terrain.py`, `main.py` | `/api/safe-haven` ikili alanları aynı tel biçimiyle |
| `scipy.sparse.csgraph.dijkstra(min_only=True)` (scipy 1.15) | — | Çok kaynaklı en kısa süre; Python döngüsü yerine C |

## Fizik / kural notu

- Dünya'nın yüksekliği kutupta ±7° arasında ~27,3 günlük periyotla salınır;
  her hücrenin kendi ufku (−20°…+10°) olduğundan **Dünya'nın batış anı hücreye
  göre günlerce farklı**dır. Bu yüzden "Dünya batışına kalan süre" site-geneli
  bir sayı değil, `(dilim, hücre)` başına bir alandır.
- Güneş saatler, Dünya günler ölçeğinde değişir. SHERPA'nın planlama veri seti
  2 saatlik adımla gölge serisi kullanır; SH haritası da 2 saatlik adımla, bir
  **sinodik ay** (29,53 gün = 708,7 saat) boyunca hesaplanır — bu süre her
  hücre için en az bir tam "Dünya yok" dönemini kapsar.
- "Kesintisiz gölge" yalnızca **Dünya'nın görünmediği adımlarda** sayılır
  (tanımın lafzı: *Dünya ufkun altındayken*). Dünya görünürken karanlık
  olmak SH ölçütü değildir: o sırada rover komutla başka yere taşınabilir.
- "Hareketsiz beklerken güç üretebilme": pencere boyunca en az bir adımda
  aydınlık olmak. Sürekli karanlık bir hücre, Dünya-yok dönemi 50 saatten
  kısa olsa bile SH değildir.
- Rover profiline göre: LPR-1 50 h, NASA VIPER 96 h, LUVMI-M 4 h, Yutu-2 2 h.
  Harita profil değişince otomatik büzüşür/genişler.

---

## Bileşenler

### 1. `app/safe_haven.py` — yeni modül

```
DEFAULT_SAFE_HAVEN_SPAN_HOURS = 708.7     # bir sinodik ay
DEFAULT_SAFE_HAVEN_STEP_HOURS = 2.0       # SHERPA kadansı
DEFAULT_EARTHSET_LOOKAHEAD_HOURS = 336.0  # yarım libration döngüsü (A4 ile aynı)

max_dark_hours_without_dte(sun_visible, earth_visible, step_hours)
    -> (H, W) float: Dünya-yok adımlarındaki en uzun kesintisiz karanlık (saat)
safe_haven_mask(max_dark_no_dte_h, ever_lit, traversable, h_max_shadow_h)
    -> (H, W) bool
build_safe_haven_map(horizon, metadata, traversable, rover, start_utc,
                     span_hours=..., step_hours=...) -> (layers: dict, info: dict)
    layers: safe_haven (bool), max_dark_hours_without_dte (h), earth_below_hours (h),
            ever_lit (bool)
    info: model="spice_horizon", start_utc, span_hours, step_hours, n_steps,
          h_max_shadow_h, rover_id, safe_haven_fraction (geçilebilir hücreler
          içinde), safe_haven_cells, traversable_cells, earth_below_fraction
time_to_safe_haven_hours(safe, traversable, elevation, slope, resolution_m, rover)
    -> (H, W) float64: SH'a en kısa sürüş süresi (saat); SH'da 0, ulaşılamazsa inf
hours_until_earthset_cube(earth_cube, slice_hours, after_end_h=None)
    -> (T, H, W) float64: dilim t'de hücrede Dünya'nın batışına kalan saat;
       şu an görünmüyorsa 0; ufuk sonuna kadar görünür ve after_end_h yoksa inf
earthset_after_horizon_hours(horizon, metadata, end_utc, lookahead_hours, step_hours)
    -> (H, W) float64: ufuk sonundan sonraki ilk batışa kalan saat (ince grid; inf yoksa)
       Planlayıcı için blok başına **min** ile kaba gride iner (blok, herhangi bir
       ince hücresi bağlantıyı kaybettiğinde kaybeder — Dünya küpünün AND indirgemesiyle tutarlı)
route_margins(states, batteries_wh, shadow_cube, earthset_cube, slice_hours, rover)
    -> dict: time_to_sun_shadow_min_h / _mean_h, time_to_dsn_shadow_min_h,
             time_to_zero_soc_min_h
safe_haven_for_grids(grids, rover_id, start_utc, span_hours, step_hours)
    -> (layers, tts, info) | (None, None, {"model": "unavailable", "reason": ...})
    Sınırlı önbellek (8 giriş), anahtar: (processed_dir|id(grids), rover_id,
    start_utc, span, step, shape).
```

**`time_to_safe_haven_hours` grafı:** 8-komşuluk; kenar ağırlığı
`edge_travel_time_s(0.5·(slope_a + slope_b), d) / 3600` (astar_4d'nin MOVE
trapezi); `|dz|/d ≤ tan(slope_max_deg)`, `lateral_slope_tan ≤ tan(slope_lateral_max_deg)`,
köşe kesme yasağı — `gated_move_count` ile birebir, vektörize. Graf simetrik
olduğundan (her kapı iki yönde aynı) tek yönlü kenar listesi + `directed=False`
yeter. Testte, tts'nin sonlu olduğu hücre kümesi `gated_move_count`'un SH'dan
ulaşabildiği kümeyle aynı olmalıdır.

**Araştırma belgesinden sapma (bilinçli):** belge tts'yi "her zaman dilimi
için `cost_cube` üzerinde" tanımlıyor. `cost_cube` ağırlıklı-saat birimindedir
ve gölge/termal cezayı içerir; oysa "Dünya batmadan yetişir miyim" sorusu
**saat** ister ve bu modelde kenar süresi aydınlanmadan bağımsızdır
(`edge_travel_time_s` yalnızca eğime bağlı). tts bu yüzden saat cinsinden,
uzamsal (H, W) bir katmandır; zaman bağımlılığı kuralın öteki tarafında,
`hours_until_earthset[t, c]`'dedir.

### 2. `app/pathfinder_4d.py` — kısıt ve raporlama

`astar_4d(..., time_to_haven_hours=None, hours_until_earthset_cube=None,
require_safe_haven=False)`:

- `REJECTION_KEYS` + `"safe_haven_deadline"`.
- **Durum değişmezi:** her itilen durumda (MOVE varışı, WAIT varışı ve
  başlangıç) `tts[c] ≤ deadline[t, c]`. Şu an Dünya görünmüyorsa
  `deadline = 0`, dolayısıyla yalnızca SH hücrelerine izin verilir — VIPER'da
  Dünya batıkken rover SH'da parktır. `deadline = inf` (ufuk + ön-bakış içinde
  batış yok) her zaman geçer. WAIT'in de denetlenmesi zorunludur: aksi hâlde
  planlayıcı SH olmayan bir hücrede batışı bekleyebilir.
- Başlangıç kuralı sağlamıyorsa `_empty("Start ... cannot reach a safe haven
  before the Earth sets ...")` (SH değil ve Dünya yoksa ayrı cümle).
- Sonuç: `path_time_to_haven_h`, `path_hours_until_earthset`,
  `path_haven_margin_h` (üçü de `list[float|None]`, `inf → None`);
  `metrics.min_haven_margin_h`, `metrics.states_past_haven_deadline` (raporlanıp
  uygulanmadığında sayılır), `metrics.ends_at_safe_haven`,
  `metrics.safe_haven_enforced`. Alanlar verilmediğinde listeler `None`.
- `no_path_reason_4d`: "N transitions would have left the rover unable to
  reach a safe haven before the Earth sets (require_safe_haven: ...)".

### 3. SHERPA marj metrikleri — `safe_haven.route_margins`

Rota bulunduktan sonra, durum listesi ve küplerden (arama dışında):

| Metrik | Tanım |
|---|---|
| `time_to_sun_shadow_min_h`, `_mean_h` | Her durumda hücrenin bir sonraki karanlık dilimine kalan saat (şu an karanlıksa 0; ufuk sonuna kadar aydınlıksa sayılmaz); sonlu değerlerin min/ort'u, yoksa `None` |
| `time_to_dsn_shadow_min_h` | Durumlar boyunca `hours_until_earthset` en küçüğü (sonlu yoksa `None`) |
| `time_to_zero_soc_min_h` | Her durumda `battery_wh / housekeeping_w(tam gölge)`: rover o an tam gölgede kalsa bataryanın sıfıra inme süresi; en küçüğü |

### 4. `app/main.py` — uçlar

| Uç | Değişiklik |
|---|---|
| `GET /api/safe-haven?start_utc&rover_id&span_hours&step_hours&downsample&format&field` | JSON: `rover_id, h_max_shadow_h, start_utc, span_hours, step_hours, n_steps, safe_haven_model, safe_haven_fraction, safe_haven_cells, traversable_cells, earth_below_fraction, grid, fields{safe_haven, max_dark_hours_without_dte, earth_below_hours, time_to_safe_haven}, binary_format`. `format=f32&field=…` ile ikili katman (`encode_layer_f32`, `X-Layer-*` başlıkları; `time_to_safe_haven` ulaşılamaz → NaN). Ufuk küpü / çekirdek / epoch yoksa JSON `safe_haven_model.model="unavailable"` + `reason`, `fields` boş; ikili istek 404. `start_utc` zorunlu (422 yoksa). |
| `GET /api/cell-telemetry?...&start_utc=` | `start_utc` verilirse `safe_haven: {is_safe_haven, max_dark_hours_without_dte_h, earth_below_hours, time_to_safe_haven_h (None=ulaşılamaz), h_max_shadow_h, model}`; verilmezse veya hesaplanamazsa `safe_haven: null` ve `safe_haven_model` nedeni. |
| `POST /api/plan-4d` | İstek: `require_safe_haven: bool=false`. `start_utc` varsa SH haritası (sinodik ay, 2 h) ince gridde kurulur, blok-AND ile kaba gride iner, tts kaba gridde hesaplanır; Dünya batış küpü plan kadansındaki Dünya küpü + 336 h ön-bakıştan türetilir. Yanıt: `safe_haven_model`, `path_time_to_haven_h`, `path_hours_until_earthset`, `path_haven_margin_h`, `metrics.min_haven_margin_h`, `metrics.states_past_haven_deadline`, `metrics.ends_at_safe_haven`, `metrics.safe_haven_enforced`, `metrics.edges_rejected.safe_haven_deadline`, `metrics.time_to_sun_shadow_min_h/_mean_h`, `metrics.time_to_dsn_shadow_min_h`, `metrics.time_to_zero_soc_min_h`. Kısıt istenip harita/batış küpü yoksa 422. 404 metni kuralın kapattığı geçiş sayısını ve başlangıcın marjını söyler. |

### 5. `scripts/safe_haven_report.py`

Gerçek grid + çekirdeklerle dört rover profili için SH kesrini, ortalama
tts'yi ve Dünya-yok kesrini ölçer; `docs/research/safe_haven_report.md` yazar.
Dış doğrulama ürünü yoktur (kural NASA belgesinden birebir); bu script
"profil değişince harita nasıl büzüşüyor" sayılarını üretir. Girdi yoksa
nasıl alınacağını yazar ve 0 ile çıkar; asla veri uydurmaz.

---

## Veri akışı

```
kernels + horizon_map.npy ──► body_track(SUN), body_track(EARTH) [708,7 h / 2 h]
        │                                  │
        ▼                                  ▼
 sun_visible[t]                     earth_visible[t]
        └──────────► max_dark_hours_without_dte ◄──────┘
                              │  ever_lit, traversable, h_max_shadow_h(rover)
                              ▼
                        safe_haven mask ──► time_to_safe_haven_hours (Dijkstra, saat)
                              │                       │
                              ├──► /api/safe-haven    ├──► /api/cell-telemetry (start_utc)
                              │                       │
                              └──► coarsen (AND) ─────┴──► astar_4d(require_safe_haven)
                                                              ▲
plan Earth küpü (A4) + 336 h ön-bakış ──► hours_until_earthset_cube ┘
```

## Hata davranışı

- Çekirdek / ufuk / epoch yokken hiçbir uç düşmez: `safe_haven_model`
  `unavailable` + `reason`; plan kısıtsız devam eder (kısıt açıkça istenmişse
  422); ikili istek 404.
- SPICE hataları A4 ile aynı gerekçeyle geniş yakalanır ve `reason`'a yazılır.
- `inf` hiçbir JSON'a sızmaz (`None`), ikilide `NaN`.

## Test stratejisi

- Saf fonksiyonlar (`max_dark_hours_without_dte`, `safe_haven_mask`,
  `hours_until_earthset_cube`, `time_to_safe_haven_hours`, `route_margins`)
  küçük el yapımı dizilerle; tts'nin `gated_move_count` ile ulaşılabilirlik
  tutarlılığı rastgele gridde.
- `build_safe_haven_map`: `test_earth_visibility.py`'nin `_script_ephemeris`
  kalıbıyla senaryolu Güneş + Dünya (çekirdeksiz), geçici ufuk küpü.
- Planlayıcı: oyuncak küplerde deadline kuralı — SH'a yetişemeyecek geçiş
  reddedilir, WAIT de denetlenir, başlangıç kuralı, kısıt kapalıyken yalnızca
  rapor, `inf` deadline serbest.
- Uçlar: `monkeypatch` ile `safe_haven_for_grids` / seri üreticileri;
  422/404 metinleri; ikili sözleşme.
- Gerçek grid: `test_safe_haven_real_grid.py` (skip-guarded): LPR-1'de SH
  kesri (0,1) aralığında ve VIPER ≥ LPR-1 ≥ LUVMI-M ≥ Yutu-2 sıralaması; plan
  kısıtı gerçek çiftte 200 veya gerekçeli 404.

## Uygulama sırasında bulunanlar ve ölçümler (4 Eylül 2026)

**Gerçek grid sonucu (Site11, `scripts/safe_haven_report.py`, 13 sinodik ay,
2 h adım, 355 örnek/ay):** Dünya'nın ufkun altında olduğu iki hafta, sitenin
tamamının ~6,5 gün karanlık kaldığı Ay gecesiyle çakışıyor. Eylül 2026'da
(7 Eyl başlangıç) Dünya 11–24 Eylül arasında hiçbir hücreden görünmüyor; Güneş
12–18 Eylül arasında hiçbir hücreye ulaşmıyor; bu yüzden geçilebilir her
hücrenin Dünya-yok kesintisiz karanlığı ≥ 156 h. Sonuç: **hiçbir profil için
safe haven yok** (VIPER'ın 96 saati dahil). Bu bir hata değil, kuralın
cevabıdır — NASA'nın "SH'lar nadirdir" tespitiyle uyumlu.

| Ay günü | En kısa Dünya-yok karanlık | Gerekli dayanım %1 / %10 / %50 | LPR-1 (50 h) | VIPER (96 h) | LUVMI-M (4 h) | Yutu-2 (2 h) |
|---|---|---|---|---|---|---|
| 2026-09-07 | 156 h | 158 / 188 / 342 h | 0 | 0 | 0 | 0 |
| 2026-11-05 | 40 h | 122 / 188 / 264 h | %0,02 (~40 hücre) | %0,41 | 0 | 0 |
| 2027-01-03 | 78 h | 98 / 146 / 208 h | 0 | %0,66 | 0 | 0 |
| 2027-05-30 | 62 h | 64 / 82 / 380 h | 0 | **%10,7** | 0 | 0 |
| 2027-06-29 | 104 h | 104 / 106 / 372 h | 0 | 0 | 0 | 0 |

Dünya-yok kesri ay boyunca %69–76 (A4'ün uzun-dönem 0,28 görünürlüğüyle
tutarlı); pencere boyunca en az bir kez aydınlanan geçilebilir hücre kesri
%62–100 (güney kışında düşer). Faz kayması (~2 gün/ay) NASA'nın "Ay günü
başına SH haritası" pratiğini doğruluyor; bu yüzden uç `start_utc` ister.

**Süreler:** harita 3,3–3,8 s (355 adım × 2 maske + SPICE), kapılı kenar
listesi 0,1 s (720 k kenar), ince grid Dijkstra 0,4 s (VIPER, 22 837 haven,
tts medyanı 2,2 h, geçilebilir hücrelerin %99,2'si sonlu). Sonuç önbelleğe
alınır; `/api/cell-telemetry` ikinci istekte anında.

**Plan (VIPER, 30 May 2027, coarsen 4, 256 dilim):** iki haven arasında 40
hamlelik rota kuralla 200 döner (8,4 s; `min_haven_margin_h` 199,7,
`ends_at_safe_haven` true, 5 586 geçiş bağlantısız/haven-olmayan hücrelere
girdiği için reddedildi, rota kısıtsız planla aynı). Bağlantısız ve haven
olmayan bir hedefe plan 404 (6,5 s), mesaj hedefi ve başlangıcın marjını
adlandırır.

**Bulunan sorun ve düzeltme — hedef sınırı:** kural açıkken hedef hiçbir
dilimde kuralı sağlayamıyorsa (bağlantısı yok ve haven değil) etiket-atayan
arama 256 dilim × 10 314 hücrenin tamamını dolaşıyordu (üretim gridinde 10
dakikada bitmedi; aynı çift kısıtsız 8,6 s). `astar_4d` artık hedefin kuralı
sağladığı son dilimi (`goal_last_ok`) hesaplar: hedef hiç sağlamıyorsa
arama yapmadan gerekçeli reddeder; sağlıyorsa o dilimden sonraya varan her
geçiş `safe_haven_deadline` olarak reddedilir (varış zamanı yalnızca büyür,
sonrası hedefte bitemez).

**Sapmalar (bilinçli):** `time_to_safe_haven` maliyet küpü üzerinde değil,
saat cinsinden ve uzamsal (bkz. Bileşenler §1); `earthset_after_horizon_hours`
1 saatlik kadansla örnekler (Dünya günde ~0,5° iner, bir ufuk kutusu
saatler sürer).

## Kapsam dışı (bilinçli)

- `corridor.build_corridor`'un `fallback_points`'i (2-B planlayıcı sözleşmesi)
  gölge-oranı kuralında kalır; SH katmanı ayrı yayınlanır.
- Leg/istasyon sıralaması ve kontenjan dalları (A5), PSR girişleri.
- SH'ın "en yakın SH koordinatı" (nearest index): tts yeter; gerekirse
  Dijkstra'nın `return_predecessors` ile sonra eklenir.
- Frontend görselleştirmesi; yalnızca sözleşme belgesi güncellenir.
