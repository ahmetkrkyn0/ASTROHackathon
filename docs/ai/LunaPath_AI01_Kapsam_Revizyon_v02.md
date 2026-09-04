# LunaPath — AI-01 Kapsam Sözleşmesi · Revizyon Notu v0.2

> **Kaynak:** `BACKEND_ENVANTER.md` + `backend_capabilities.json`, commit `fea37ef`, backend `0.3.0`
> **Neyi geçersiz kılar:** `AI-02` (Kapsam ve Arayüz Sözleşmesi v0.1) belgesinin **§4, §8.2, §9, §11, §12/D-1** bölümleri. Diğer bölümler (özellikle §3 yasak listesi ve §6 katman mimarisi) **aynen geçerli**.
> **Durum:** §9 teyit listesi **kapandı**. System prompt yazımı artık açık — ancak §4'teki tuzak tablosu prompt'a **birebir** girmeli.

---

## 1. Denetimin kapsam belgesine etkisi — özet

Envanter dört varsayımı çürüttü, bir varsayımı beklenenden **iyi** çıkardı ve tasarımda bir **inversiyon** gerektiriyor.

| # | v0.1'deki varsayım | Gerçek | Etki |
|---|---|---|---|
| 1 | `C-DECOMPOSE` rota geneli, "düşük zorluk" | **Yalnızca hücre bazında.** Rota geneli bileşen toplamı hiçbir yerde biriktirilmiyor | 🔴 Faz-1 kapsamı değişiyor |
| 2 | `C-BINDING` log-bariyer slack'lerinden gelecek | Slack'ler **hiç saklanmıyor**; bunun yerine beklenmedik bir kaynak var: `constraint_check` | 🟠 Kaynak değişiyor, yetenek kalıyor |
| 3 | `C-SENSITIVITY` "düşük–orta zorluk" | Çalışıyor **ama önbellek yok** ve tek çözüm 2.8–4.8 s; ayrıca serbest ağırlık yalnızca `/api/plan` üzerinden mümkün — o da **durum yazıyor** | 🔴 Bütçe ve D-1 kararı değişiyor |
| 4 | `C-INFEASIBLE` orta zorluk | `/api/plan`'da tanı **düzyazıya gömülüp sayaçlar atılıyor**; ama `/api/compare`'de aynı bilgi **yapılandırılmış hâlde duruyor** | 🟠 Endpoint değişiyor |
| 5 | Provenance (S-11) belirsizdi | **Beklenenden güçlü.** Dört basamaklı `SYNTHETIC < DERIVED < MODEL < MEASURED` merdiveni, `layer_validity`, `X-Layer-Validity`, `shadow_model` blokları | 🟢 S-11 tam uygulanabilir |

**İnversiyon:** v0.1, asistanın birincil veri kaynağını örtük olarak `/api/plan` sanıyordu. Envanter tersini gösteriyor — bkz. §2.

---

## 2. Mimari inversiyon: birincil kaynak `/api/compare`, `/api/plan` değil

Bu, envanterden çıkan **en önemli tek karar**. Dört gerekçe:

| Kriter | `POST /api/plan` | `POST /api/compare` |
|---|---|---|
| **Yan etki** | `app.state.active_corridor`, `active_corridor_id`, `active_corridor_rover_id` yazar; `corridors` FIFO defterine ekler (`main.py:722-735`) | **Hiçbir durum yazmaz** — profil bazlı gridleri türetip atar (`main.py:1276`) |
| **Kısıt marjı** | **Yok.** `check_profile_constraints` çalışmaz | **Var.** `constraint_check` → `limit` + `actual` + `satisfied` + `enforced_in_search` |
| **Başarısızlık** | HTTP 404, gövde yalnızca `{"detail": "<düzyazı>"}`; `edges_rejected` ve `nodes_expanded` **atılır** (`main.py:627-628`) | **HTTP 200**, `results[]` içinde `error` **ve dolu `metrics`** (`main.py:1240-1265`) |
| **Karşıtsal malzeme** | Tek rota | **Dört profil bir arada** — yerleşik karşılaştırma tabanı |

**Sonuç kuralı (v0.1 §3.3'e eklenir):**

> **N-18.** Asistan `POST /api/plan` çağırmaz. Kullanıcının başlattığı planı **okur**; kendi hesaplarını `/api/compare`, `/api/plan-multi` ve saf okuma uçları üzerinden yapar.

Gerekçe yalnızca temizlik değil: asistan `/api/plan` çağırırsa kullanıcının ekranındaki aktif korridoru **sessizce değiştirir**. Kullanıcı "acaba enerji ağırlığı artsa?" diye sorar, asistan cevap verir, ve haritadaki rota altından kayar. Bu bir karar destek aracında kabul edilemez.

### 2.1 Bunun bedeli: serbest ağırlık perturbasyonu faz-1'de yok

Envanterin ortaya çıkardığı kısıt:

| Uç | Serbest ağırlık kabul ediyor mu? | Durum yazıyor mu? |
|---|---|---|
| `/api/plan` | ✅ `PlanWeights`, `[0,2]` doğrulamalı | ❌ **evet, yazıyor** |
| `/api/plan-multi` | ❌ yalnız profil id listesi | ✅ hayır |
| `/api/compare` | ❌ yalnız dört sabit profil | ✅ hayır |
| `/api/layers/*` | ✅ ama **doğrulama yok** | ✅ hayır — fakat **rota değil, grid** döner |

Yani "w_energy'yi 0.259'dan 0.35'e çıkar ve yeni rotayı göster" isteği bugün **yan etkisiz olarak karşılanamıyor.**

**Faz-1 çözümü — ayrık ağırlık uzayı:** Dört misyon profili zaten ağırlık uzayında dört örneklenmiş nokta:

| Profil | slope | energy | shadow | thermal |
|---|---|---|---|---|
| `balanced` | 0.409 | 0.259 | 0.142 | 0.190 |
| `energy_saver` | 0.250 | **0.450** | 0.150 | 0.150 |
| `fast_recon` | **0.500** | 0.150 | 0.100 | 0.250 |
| `shadow_traverse` | 0.200 | 0.150 | **0.300** | 0.350 |

Kullanıcı "enerjiye daha çok ağırlık verilse ne olur?" dediğinde asistan tek bir `/api/compare` çağrısıyla — yan etkisiz, tek koşumda — şunu diyebilir:

> *"Bu tam olarak `energy_saver` profilinin yaptığı şey: w_energy 0.259 yerine 0.450. Sonuç: enerji 1457.5 Wh yerine [X] Wh, mesafe [Y] m, sürekli gölge [Z] saat. Bedeli: eğim ağırlığı 0.409'dan 0.250'ye düşüyor, yani daha dik arazi kabul ediliyor."*

Bu, etkileşimli çok amaçlı optimizasyon literatüründeki **ayrık Pareto örneklemesi** desenidir (`AI-01` §3.5) ve akademik olarak savunulabilir. Sürekli perturbasyon faz-2'ye kalır — ve o zaman backend'den §6'daki `dry_run` bayrağı istenir.

---

## 3. Yetenek durum tablosu — GERÇEK

`AI-02` §4'ün yerine geçer.

| Kod | Durum | Gerçek kaynak | Kısıt / not | Faz |
|---|---|---|---|---|
| `C-SUMMARY` | ✅ **Tam** | Kullanıcının planından okunur; asistan çağırmaz | `summary` 18 alan + `astar_metrics` 18 alan + `route_statistics` 5 alan | 1 |
| `C-POINT` | ✅ **Tam** | `GET /api/cell-telemetry` | Saf okuma. **Ağırlık override kabul etmiyor** → §4 tuzak T-3 | 1 |
| `C-DECOMPOSE` | 🟡 **Kısmi** | `cell-telemetry` `cost_breakdown`, hücre bazında | **Rota geneli yok.** İstemci tarafında waypoint döngüsüyle toplanabilir ama ağırlık tutarsızlığı riski var (§4 T-3) | 1 (kısıtlı) |
| `C-BINDING` | 🟡 **Kısmi** | `/api/compare` → `constraint_check` | Yalnız 4 profil kısıtı: `max_shadow_h`, `max_energy_wh`, `min_soc` (+ yapısal `max_slope_deg`, `actual` daima `null`). Bariyer slack'leri **yok** | 1 |
| `C-COMPARE` | ✅ **Tam** | `POST /api/compare` | Saf okuma. **Yalnız piksel koordinat** | 1 |
| `C-INFEASIBLE` | 🟡 **Kısmi ama beklenenden iyi** | `/api/compare` → `results[].metrics.edges_rejected` | `/api/plan`'da kayıp. **Kritik keşif:** sayaçlar **başarılı** koşumlarda da dolu → "neden dolambaçlı" sorusunu cevaplar | 1 |
| `C-SENSITIVITY` | 🟡 **Ayrık** | `/api/compare` dört profil | Serbest ağırlık faz-2 (§2.1). Önbellek yok, her koşum tam çözüm | 1 (ayrık) |
| `C-CONTRAST` | ❌ **Yok** | — | `cost_engine.total_edge_cost()` var (`:742`) ama **hiçbir route çağırmıyor** | 2 |
| `C-RECOURSE` | ❌ **Yok** | — | v0.1'de zaten faz-2 | 2 |

**Faz-1 net kapsamı:** 4 tam + 4 kısmi yetenek. `C-CONTRAST` — XAIP literatürünün merkezindeki yetenek — bugün **imkânsız** ve tek bir endpoint ile açılıyor (§6 madde 1).

---

## 4. Alan bağlama tablosu ve tuzaklar

**Bu bölüm system prompt'a birebir girecek.** Envanterin en operasyonel çıktısı.

### 4.1 Kanonik alan adları

| Kavram | Doğru alan | Nerede |
|---|---|---|
| Toplam mesafe | `summary.total_distance_km` (km) veya `astar_metrics.total_distance_m` (m) | `/api/plan`, `/api/compare` results |
| **Toplam enerji** | `summary.total_energy_consumed_wh` | ⚠️ bkz. T-1 |
| **Sürekli gölge** | `summary.max_continuous_shadow_h` | ⚠️ bkz. T-1 |
| Minimum batarya | `summary.min_battery_pct` (0–100) | |
| Geçen süre | `summary.total_elapsed_hours` | |
| Maks. eğim (adım) | `astar_metrics.max_segment_slope_deg` | iki eğim tanımı var, `slope_definitions` alanı açıklıyor |
| Maks. eğim (hücre) | `astar_metrics.max_cell_slope_deg` | geçilebilirlik kapısı bunu kullanır |
| Ağırlıklı toplam maliyet | `astar_metrics.total_weighted_cost` (birim: `weighted_metres`) | bariyer dahil |
| Bariyerin payı | `astar_metrics.barrier_share` (kesir) | bileşen ayrımı **yok** |
| Reddedilen kenarlar | `astar_metrics.edges_rejected` | 5 sayaç |
| Hücre maliyet ayrışımı | `cost_breakdown` → `{slope, energy, shadow, thermal, total}` | `/api/cell-telemetry` |
| Veri kökeni | `layer_validity` → katman → `MEASURED\|MODEL\|DERIVED\|SYNTHETIC` | `/api/cell-telemetry` |
| Kısıt marjı | `constraint_check[key]` → `{limit, actual, satisfied, enforced_in_search, checked}` | **yalnız** `/api/compare`, `/api/plan-multi` |

### 4.2 Tuzaklar — prompt'ta açıkça yasaklanacak

| # | Tuzak | Kural |
|---|---|---|
| **T-1** | `astar_metrics.total_energy_wh` ve `astar_metrics.total_shadow_hours` **daima `null`** — "fast mode" tasarım kararı | Asistan bu iki alana **asla** bağlanmaz. Enerji → `summary.total_energy_consumed_wh`, gölge → `summary.max_continuous_shadow_h` |
| **T-2** | Üç ayrı ad uzayı: bileşen `shadow`, ağırlık `w_shadow`, grid katmanı `shadow_ratio` | Asistan üçünü karıştırmaz; kullanıcıya "gölge bileşeni" der, alan adını gerektiğinde doğru yazar |
| **T-3** | `/api/cell-telemetry` **ağırlık override kabul etmiyor** — `cost_breakdown` daima `metadata['cost_weights']` ile hesaplanır (`main.py:549`) | Kullanıcının planı varsayılan dışı ağırlıkla koştuysa, hücre ayrışımı o planla **tutarsız** olabilir. Asistan bu durumda ayrışımı ya sunmaz ya da tutarsızlık uyarısıyla sunar |
| **T-4** | `corridor_id` (uuid4) ve `computation_time_ms` her yanıtta farklı | İki yanıt karşılaştırılırken bu iki alan **hariç tutulur**; asistan bunları "değişti" diye raporlamaz |
| **T-5** | `summary.total_shadow_exposure` **birimi bilinmiyor** (envanter BİLİNMİYOR #3) | `Quantity.unit` zorunlu olduğu için bu alan sözleşmeye **giremez**. Asistan bu alanı hiç kullanmaz |
| **T-6** | `astar_metrics.max_thermal_risk` hesaplama yöntemi bilinmiyor (BİLİNMİYOR #4) | Sayı olarak aktarılabilir ama asistan **nasıl hesaplandığını açıklamaya çalışmaz** |
| **T-7** | `/api/compare` ve `/api/plan-multi` **yalnız piksel** kabul eder; `/api/plan` piksel **veya** coğrafi | Adaptör dönüşümü yapar; asistan koordinat biçimi bilmez |
| **T-8** | `/api/layers/*` ve `/api/terrain` ağırlık parametrelerinde **hiçbir doğrulama yok** (`w_slope=999` → HTTP 200) | Safeguard (K3) `[0,2]` kontrolünü **kendisi** yapar; backend doğrulamasına güvenmez |
| **T-9** | Ağırlıklar **normalize edilmiyor**, toplamları 1 olmak zorunda değil (`cost_engine.py:51-63`) | Asistan "ağırlıklar toplamı 1" varsayan hiçbir cümle kurmaz; yüzdeye çevirmez |
| **T-10** | Rover id'leri `nasa_viper` ve `cnsa_yutu_2` — `BELGE 00`'daki `viper`/`yutu_2` **yanlış** | Katalog id'leri yalnız `/api/rovers` canlı yanıtından alınır |
| **T-11** | `rover.declared_only` bloğu (`f_net_n`, `regen_efficiency`, `thermal_tau_s`, `h_design_shadow_h`) hesaplamada kullanılıyor mu **bilinmiyor** (BİLİNMİYOR #5) | Asistan bu değerleri **hiç** raporlamaz |
| **T-12** | Bilinmeyen katman **400**, diğer tüm girdi hataları **422** | Hata eşlemesi bu tutarsızlığı bilmeli |

### 4.3 Yeni genel kural

> **N-19.** Envanterin **BİLİNMİYOR** listesindeki hiçbir alan asistan çıktısında geçemez. Birimi doğrulanmamış bir sayı, birimsiz sunulamaz; birimsiz sunulamıyorsa hiç sunulmaz.

Bu kural, v0.1 §5.1'deki "birimi zorunlu `Quantity`" tasarımının doğal sonucu. Envanterin dürüstlüğü burada doğrudan güvenliğe çevriliyor: `total_shadow_exposure` ve `declared_only` alanları kendiliğinden eleniyor.

---

## 5. Bütçe revizyonu

`AI-02` §8.2'nin yerine geçer. Gerekçe: **plan yolunda önbellek yok** — aynı girdinin tekrarı ucuz değil (envanter §8: 2840 ms → 4848 ms).

| Sınır | v0.1 | **v0.2** | Gerekçe |
|---|---|---|---|
| Soru başına yeniden hesaplama | 3 | **1** | Tek `/api/compare` zaten 4 profil çözüyor. Ölçülen tek çözüm 2.8–4.8 s |
| Soru başına toplam süre | 15 s | **30 s** + ilerleme göstergesi | 4 profilli compare süresi **ölçülmedi** (envanter `typical_ms: null`) — üst sınır bilinmiyor |
| Oturum başına toplam | 50 | **20** | Önbellek yokluğu maliyeti gerçek |
| Saf okuma çağrısı (cell-telemetry vb.) | — | **20/soru** | Ucuz; rota ayrışımı için waypoint döngüsü gerekiyor |

**Ölçüm borcu:** `/api/compare` süresi bir sonraki adımda ölçülmeli. 4 profil × ~3 s = ~12 s beklenir ama grid türetme paylaşılabiliyorsa daha az olabilir. Bu sayı bilinmeden K2 yönlendiricisinin bütçe mantığı kalibre edilemez.

---

## 6. Backend'den istenecek değişiklikler — öncelik sırası

Envanterin E-1 listesi + denetimden çıkan iki ek madde. **Hepsi küçük**, hiçbiri matematiği değiştirmiyor.

| # | İstek | İş | Ne açar | Öncelik |
|---|---|---|---|---|
| **1** | Rota geneli bileşen ayrıştırması: waypoint'ler üzerinde `CostMap.explain()` döngüsü + toplam | ~8 satır | `C-DECOMPOSE` **tam** olur. "Maliyetin %52'si eğimden geldi" — literatürdeki en çok istenen açıklama | 🔴 **1** |
| **2** | Bir yolu puanlayan uç: mevcut `total_edge_cost()` (`cost_engine.py:742`) üzerine `POST /api/score-path` | ~20–30 satır | `C-CONTRAST` açılır. XAIP'in merkez yeteneği; "neden bu rota, benim çizdiğim değil" | 🔴 **1** |
| **3** | 404 gövdesini yapılandır: `_empty_result`'ın `metrics`'ini (`edges_rejected`, `nodes_expanded`) 404 gövdesine koy | ~3 satır | `C-INFEASIBLE` `/api/plan`'da da çalışır; asistan düzyazı ayrıştırmak zorunda kalmaz | 🟠 2 |
| **4** | `/api/cell-telemetry`'ye `w_*` sorgu parametreleri (`/api/layers` ile aynı imza, **ama `[0,2]` doğrulamalı**) | ~5 satır | T-3 tuzağı kapanır; hücre ayrışımı plan ağırlıklarıyla tutarlı olur | 🟠 2 |
| **5** | `/api/plan`'a opsiyonel `dry_run: bool = False` — `True` iken korridor yayımlama adımını atla (`main.py:722-735`) | ~3 satır | Serbest ağırlık perturbasyonu **yan etkisiz** olur → `C-SENSITIVITY` sürekli hâle gelir | 🟠 2 |
| **6** | `/api/plan`'a opsiyonel `profile_id` + mevcut `_attach_constraint_check` çağrısı | ~5 satır | Tek rota için de kısıt marjı; `C-BINDING` `/api/plan`'da çalışır | 🟡 3 |
| **7** | Bariyer slack'lerini sakla: dört fonksiyon bir `dict` de döndürsün, `_astar_core` yol boyu minimumu izlesin | ~10–15 satır | `C-BINDING` **derinleşir** — "hangi kısıta ne kadar yaklaşıldı" kenar düzeyinde | 🟡 3 |
| **8** | `/api/health` yanıtına commit kimliği | ~2 satır | `backend_version` alanı gerçek olur; envanter tazeliği izlenebilir | 🟡 3 |

**Tavsiye:** 1 ve 2 faz-1 öncesi yapılsın; toplam ~40 satır ve faz-1 kapsamını "4 tam + 4 kısmi"den "6 tam + 2 kısmi"ye çıkarıyor. 3–5 faz-2'ye, 6–8 fırsat buldukça.

---

## 7. D-1 kararının revizyonu

**v0.1'deki varsayılan:** *"Asistan yeni hesap tetikleyebilsin, 3 koşum bütçesiyle."*

**v0.2 kararı — üç kademeli izin:**

| Kademe | İzin | Uçlar |
|---|---|---|
| **Serbest** | Asistan istediği zaman çağırır | `/api/cell-telemetry`, `/api/layers`, `/api/terrain`, `/api/profiles`, `/api/rovers`, `/api/health`, `/api/reference-missions` |
| **Bütçeli** | Safeguard sayar, soru başına 1 | `/api/compare`, `/api/plan-multi` |
| **Yasak** | Hiçbir koşulda | `/api/plan`, `/api/replan`, `/api/load-dem`, `/api/load-preprocessed`, `/api/scenarios/{id}/load`, `/api/pose` |

Yasak listesinin gerekçesi tek tip değil ve prompt'ta ayrı ayrı belirtilmeli: `/api/plan` ve `/api/replan` **korridor durumunu yazar**; yükleme uçları **grid durumunu ve diski** değiştirir; `/api/pose` denetlenmedi (BİLİNMİYOR #1, #2) ve teyit edilene kadar yasak kalır.

`dry_run` (§6 madde 5) geldiğinde `/api/plan` "yasak"tan "bütçeli"ye taşınır — ve **yalnızca `dry_run: true` ile**.

---

## 8. Faz planı revizyonu

| Faz | v0.1 | **v0.2** |
|---|---|---|
| **F-0** | Teyit listesi + adaptör | ✅ **Teyit listesi kapandı.** Kalan: adaptör + `/api/compare` süre ölçümü |
| **F-1** | K1 yetenekleri panel olarak | Değişmedi, ama kapsam: `C-SUMMARY`, `C-POINT`, `C-COMPARE` **tam**; `C-DECOMPOSE`, `C-BINDING`, `C-INFEASIBLE` **kısmi**. Paralelde backend §6 madde 1–2 |
| **F-2** | Sohbet katmanı | Değişmedi |
| **F-3** | `C-CONTRAST` vb. | `C-CONTRAST` artık §6 madde 2'ye **bağımlı**; olmadan yapılamaz |
| **F-4** | `C-RECOURSE` | Değişmedi (opsiyonel) |

---

## 9. Denetimden çıkan yan bulgular

Kapsam belgesini ilgilendirmiyor ama kaydedilmeli.

1. **`BELGE 00` Ortak Varsayım Defteri güncellenmeli.** Rover id'leri `viper`/`yutu_2` değil, `nasa_viper`/`cnsa_yutu_2`. Ağırlıklar (`0.409/0.259/0.142/0.190`), batarya (5420 Wh), kütle (450 kg), hız (0.2 m/s), grid (500×500) **doğrulandı** ✅.

2. **`CLAUDE.local.md` güvenilir değil.** Envanter altı noktada koddan geride olduğunu gösterdi. AI katmanı alan adlarını ondan almamalı — bu envanter ve canlı yanıtlar tek kaynak.

3. **"Sentetik termal, fizik yok" iddiası artık yanlış.** SPICE efemeris + ufuk haritası + zaman ekseni mevcut; sentetik yol yalnızca geri düşüş. `shadow_model.model` alanı `"spice_horizon"` mu `"static"` mi olduğunu bildiriyor. Bu, `BELGE 09` §3'teki olgunluk skorkartını yukarı çekebilir — ayrı değerlendirilmeli.

4. **`/api/layers` doğrulama boşluğu bir güvenlik meselesi değil ama bir doğruluk meselesi.** Negatif ağırlık maliyet manzarasını tersine çeviriyor ve 3-B istemcisi renk rampasını çarpık aralığa göre ölçekliyor. Frontend ekibine iletilmeli.

5. **Eşzamanlılık:** `/api/plan` endpoint'leri `sync def` olduğu için threadpool'da koşuyor; iki eşzamanlı plan tek `active_corridor` slotu için yarışıyor. Asistan `/api/plan` çağırmadığı için (N-18) bu risk AI katmanında doğmuyor — ama bu, N-18'in ikinci bağımsız gerekçesi.

6. **Ölçülmemiş şey:** `/api/compare` süresi. Bütçe kalibrasyonunun tek eksik girdisi.

---

## 10. Sonraki adım

Sıra: **(a)** `/api/compare` süresini ölç → §5 bütçesini kesinleştir · **(b)** backend §6 madde 1–2'yi yaz · **(c)** adaptörü yaz · **(d)** system prompt.

System prompt yazımı artık teknik olarak açık. §4'teki 12 tuzak ve §7'deki üç kademeli izin listesi prompt'ın omurgasını oluşturacak; v0.1 §3'teki 19 yasak (N-1…N-19) ise davranış çerçevesini.
