# LunaPath — AI Karar-Destek Sohbet Katmanı · Kapsam Sözleşmesi v0.3

| | |
|---|---|
| **Durum** | Yürürlükte. Bu özellik için **kendi kendine yeten, yetkili** AI/sohbet sözleşmesi. |
| **Backend temeli** | `fea37ef5d90d998b9a24cc2de6631954028347d0`, backend sürüm `0.3.0` |
| **Kanıt** | `docs/BACKEND_ENVANTER.md`, `docs/backend_capabilities.json` |
| **Öncülü** | `docs/ai/LunaPath_AI01_Kapsam_Revizyon_v02.md` (v0.2), bu dizinde değiştirilmeden saklanır |

---

## 0. Bu belgenin varlık nedeni

v0.2 revizyon notu, `AI-02 "Kapsam ve Arayüz Sözleşmesi v0.1"` adlı bir belgenin §3
(yasak listesi N-1…N-17), §5.1 (`Quantity` sözleşmesi) ve §6 (katman mimarisi)
bölümlerine **normatif olarak atıf yapıyor** ama o bölümleri tekrarlamıyor.

`AI-02 v0.1` ve `AI-01` **kurtarılamaz durumda**. Beş bağımsız arama negatif döndü:
depo geçmişinin tamamı ve her dal; makine genelinde dosya adı taraması; on adet oturum
transcript dizini ve seksen altı oturum verisi dosyası; `.docx` iç metinleri; Windows
Recent kısayol envanteri (v0.2 için kısayol var, AI-01/AI-02 için yok). Bu iki belge
konuşma ürünüydü, hiçbir zaman dosya olmadı.

Bu yüzden v0.3:

1. v0.2'nin **hâlâ geçerli ve tam tanımlı** hükümlerini devralır;
2. eksik AI-02 bölümlerine olan **asılı normatif bağımlılıkları kaldırır**;
3. bugün gerçekten bildiğimiz ve onayladığımız kuralları **eksiksiz** yazar.

**Kayıp N-1…N-17 kuralları yeniden üretilmemiştir.** Hayal ürünü bir kural listesi,
olmayan bir listeden daha tehlikelidir. Aşağıdaki §3 bu özellik için geçerli davranış
çerçevesinin **tamamıdır**; başka hiçbir numaralı kurala atıf yapılmaz.

### 0.1 v0.2'den devralınan, hâlâ bağlayıcı hükümler

| v0.2 bölümü | Konu | v0.3'teki karşılığı |
|---|---|---|
| §2 / N-18 | Asistan `POST /api/plan` çağırmaz | §5 (yasak listesi), §3 R-5 |
| §2.1 | Ayrık ağırlık uzayı — dört profil örneklemesi | §7.2 |
| §3 | Yetenek durum tablosu | §8 |
| §4.1 | Kanonik alan adları | §4.1 |
| §4.2 | Tuzaklar T-1…T-12 | §4.2 |
| §4.3 / N-19 | BİLİNMİYOR alanları çıktıda geçemez | §3 R-9 |
| §5 | Bütçe | §6 |
| §7 | Üç kademeli izin | §5 |
| §G | Provenance merdiveni | §9 |

### 0.2 v0.2'nin numaralandırma tutarsızlığı

v0.2 §10 *"v0.1 §3'teki 19 yasak (N-1…N-19)"* diyor; v0.2 §2 ise `N-18`'i **yeni**
kural olarak §3.3'e ekliyor. N-18 aynı anda hem yeni hem de önceden var olan
19'luk kümenin üyesi olamaz. Bu tutarsızlık kaynağın kendisinde vardır ve burada
**çözülmemiştir**; yalnızca kayda geçirilmiştir. Muhtemel açıklama: v0.2, AI-02'nin
v0.1'inden farklı bir sürümüne karşı yazılmış. v0.3 numaralı N-kurallarına atıf
yapmaz; kendi `R-n` kural kümesini kullanır.

---

## 1. Mimari tez

> **LunaPath hesaplama otoritesidir. Dil modeli dil ve orkestrasyon yüzeyidir.**

Her teknik iddia, deterministik LunaPath hesaplarından, onaylı bir kanıt/araç
katmanı üzerinden gelir. Model kendi başına hiçbir sayı üretmez.

---

## 2. Eski "LLM ile rota açıklaması üretme" tavsiyesinin daraltılması

`docs/final/backend-research-library.md` (`origin/main`, satır 1552) şu tavsiyeyi
içerir:

> ❌ LLM ile "rota açıklaması üretmek". Cazip görünür, hiçbir teknik değer katmaz,
> hallucination riski taşır. `explain()` (§5.1) deterministik ve daha güçlü.

**Bu tavsiye silinmemiştir ve yok sayılmamaktadır.** Gerekçesi bugün de geçerlidir:
açıklanabilirlik LunaPath'in ayırt edici üstünlüğüdür ve deterministik
`CostMap.explain()` bir dil modelinin üreteceği metinden güçlüdür.

Tavsiye, **hedef aldığı mimariye** daraltılmıştır: rota açıklamasının **kaynağı**
olarak bir dil modeli kullanmak. Bu özellik tam tersini kurar.

### 2.1 LunaPath, LLM'i şunların **kaynağı** olarak KULLANMAZ

- rota matematiği
- optimizasyon olguları
- maliyetler
- kısıtlar
- provenance
- rota üretimi
- rota puanlama
- uygulanabilirlik (feasibility) iddiaları

Bu iddiaların hepsi, onaylı kanıt/araç katmanı üzerinden deterministik LunaPath
hesaplarından doğar.

### 2.2 LLM YALNIZCA şunları yapabilir

- kullanıcının doğal dildeki sorusunu anlamak;
- açıkça onaylanmış, salt-okunur analitik araçlar arasından seçim yapmak;
- sunucu tarafındaki sert bütçelerin içinde çalışmak;
- **zaten hesaplanmış**, tipli kanıtı doğal dilde karar-destek yanıtına dönüştürmek.

### 2.3 LLM ŞUNLARI YAPAMAZ

- rota üretmek;
- rota değiştirmek;
- misyon durumunu değiştirmek;
- metrik icat etmek;
- mevcut olmayan bir değeri çıkarsamak;
- planlayıcı matematiğini kendisi yeniden hesaplamak;
- araç kanıtının desteklemediği nedensel bir açıklama uydurmak.

Bu bir mimari açıklamadır, pazarlama metni değildir. §3'teki kurallar ve §11'deki
testler bunu zorlar.

---

## 3. Davranış kuralları (R-1 … R-12)

Bu liste, bu özellik için davranış çerçevesinin **tamamıdır**.

| # | Kural |
|---|---|
| **R-1** | Asistan yanıtı kullanıcının dilinde verir. |
| **R-2** | LunaPath TRL 3 civarı görev öncesi planlama ve karar destek aracıdır. "Otonom navigasyon", "gerçek zamanlı sürüş", "sertifikalı" gibi ifadeler kullanılmaz. (SRS `CON-12` ile hizalı.) |
| **R-3** | Her teknik iddia, mevcut bağlamda verilmiş ya da araç çıktısından gelen kanıta dayanır. Kanıtı olmayan sayı söylenmez. |
| **R-4** | Yapılmamış bir hesap yapılmış gibi anlatılmaz. |
| **R-5** | Asistan rota üretmez, rota değiştirmez, misyon durumunu değiştirmez. `POST /api/plan` ve §5'teki diğer yasak uçlar hiçbir koşulda çağrılmaz. |
| **R-6** | Ağırlıklar normalize edilmez. Toplamlarının 1 olduğu varsayılmaz, yüzdeye çevrilmez. |
| **R-7** | Birimi doğrulanmamış bir sayı sunulmaz. Birim uydurulmaz. |
| **R-8** | §4.2'deki dışlanan alanlar kullanılmaz, alıntılanmaz, özetlenmez. |
| **R-9** | Backend envanterinin BİLİNMİYOR listesindeki hiçbir alan asistan çıktısında olgu olarak geçemez. (v0.2 §4.3 / N-19.) |
| **R-10** | Kanıt yetersizse, neyin belirlenemediği açıkça söylenir. |
| **R-11** | Mevcut plan olguları ile dört profilli karşı-olgusal sonuçlar birbirinden açıkça ayrılır. |
| **R-12** | Profil karşılaştırması **ayrık duyarlılık**tır, tek değişkenli nedensel perturbasyon değildir. Bir profil enerjiye daha çok ağırlık verdiğinde **diğer ağırlıklar da değişir**; rotadaki farkın tamamı tek bir ağırlığa atfedilmez. |

Provenance sınırlamaları, maddi olarak ilgili olduğunda iletilir. Her yanıt gereksiz
uyarı yığınına boğulmaz.

---

## 4. Alan sözleşmesi

### 4.1 Kanonik alan adları — BAĞLAYICI

| Kavram | Doğru alan |
|---|---|
| Mesafe | `summary.total_distance_km` veya `astar_metrics.total_distance_m` |
| **Enerji** | `summary.total_energy_consumed_wh` |
| **Sürekli gölge** | `summary.max_continuous_shadow_h` |
| Minimum batarya | `summary.min_battery_pct` |
| Geçen süre | `summary.total_elapsed_hours` |
| Segment eğimi | `astar_metrics.max_segment_slope_deg` |
| Hücre eğimi | `astar_metrics.max_cell_slope_deg` |
| Ağırlıklı maliyet | `astar_metrics.total_weighted_cost` (birim: `weighted_metres`) |
| Bariyer payı | `astar_metrics.barrier_share` |
| Reddedilen kenarlar | `astar_metrics.edges_rejected` |
| Hücre ayrışımı | `cost_breakdown.{slope,energy,shadow,thermal,total}` |
| Kısıt marjları | `constraint_check` |

### 4.2 Asla kullanılmayacak alanlar

| Alan | Gerekçe |
|---|---|
| `astar_metrics.total_energy_wh` | Daima `null` — "fast mode" tasarım kararı (T-1) |
| `astar_metrics.total_shadow_hours` | Daima `null` (T-1) |
| `summary.total_shadow_exposure` | Birimi bilinmiyor (T-5, R-7, R-9) |
| `comparison.recommendation` | Bayat ve yanıltıcı (T-13) |
| `rover.declared_only` | Hesaplamada kullanılmıyor (T-11) |
| `computation_time_ms` | Deterministik olmayan gürültü (T-4) |
| `corridor_id` | Deterministik olmayan gürültü (T-4) |

### 4.3 Ad uzayları ayrıdır

| Kavram | Ad |
|---|---|
| Maliyet bileşeni | `shadow` |
| Ağırlık | `w_shadow` |
| Grid katmanı | `shadow_ratio` |

Üçü karıştırılmaz.

### 4.4 Tuzaklar

**T-1 … T-12 v0.2 §4.2'den aynen geçerlidir.** Bu sürümde iki tuzak eklenmiştir.

#### T-13 — `comparison.recommendation` kanıt değildir

`/api/compare` yanıtındaki `comparison.recommendation` alanı şu cümleyi taşır:

> *"Energy and shadow totals are not tracked in fast mode, so neither ranking is an
> energy claim."*

Bu ifade `astar_metrics` için doğruydu ve **yanıtın bütünü için yanlıştır**: aynı
yanıttaki profil başına `simulation_summary` bloğu gerçek `total_energy_consumed_wh`
ve `max_continuous_shadow_h` değerlerini taşır.

AI katmanı bu alanı **asla**:

- alıntılamaz;
- özetlemez;
- kanıt olarak işlemez;
- dil modeline geçirmez.

Enerji ve gölge karşılaştırması yapılandırılmış profil metrikleri,
`simulation_summary` ve `constraint_check` üzerinden yapılır.

Ayrıca `comparison.most_efficient_profile` **adı yüzünden** "enerji kazananı" diye
tanımlanmaz; `most_efficient` ölçütü `total_weighted_cost`'tur. Enerji
karşılaştırması `simulation_summary.total_energy_consumed_wh` ile yapılır.

#### T-14 — Çalışma zamanı grid olguları statik tasarım belgelerini yener

Misyon ve grid olguları **güncel backend/çalışma zamanı metadata'sından** gelir.
Statik SRS/tasarım boyutları yüklü grid'i geçersiz kılamaz.

Asistan, çalışma zamanı kanıtı desteklemedikçe şunları iddia etmez:

- "bu 5 km'lik bir bölge"
- "bu 40 km'lik bir bölge"
- ya da başka bir grid genişliği.

Gerekçe: SRS `AD-01` eski bölgeyi 500×500 @ 80 m (40 km), yeni birincil bölgeyi
1000×1000 @ 5 m (5 km) olarak tanımlar. Ölçülen çalışma zamanı durumu ise 500×500
@ 5 m'dir; bu `span_km = 2.5` demektir. Üç değer de birbirinden farklıdır ve
yalnızca çalışma zamanı olgusu bağlayıcıdır.

---

## 5. Uç nokta izinleri — SERT SUNUCU POLİTİKASI

| Kademe | Uçlar |
|---|---|
| **SERBEST** | `GET /api/cell-telemetry`, `GET /api/layers/*`, `GET /api/terrain`, `GET /api/profiles`, `GET /api/rovers`, `GET /api/health`, `GET /api/reference-missions` |
| **BÜTÇELİ** | `POST /api/compare`, `POST /api/plan-multi` |
| **YASAK** | `POST /api/plan`, `POST /api/replan`, `POST /api/load-dem`, `POST /api/load-preprocessed`, `POST /api/scenarios/{id}/load`, `POST /api/pose` |

Yasak listesinin gerekçesi tek tip değildir: `/api/plan` ve `/api/replan`
**korridor durumunu yazar**; yükleme uçları **grid durumunu ve diski** değiştirir;
`/api/pose` denetlenmemiştir (envanter BİLİNMİYOR #1, #2).

Ayrıca bu ilk kesitte AI erişimine **açılmayan** uçlar:

- `POST /api/plan-4d`
- `GET /api/illumination-series`

Gerekçe: denetlenmiş AI izin sözleşmesinin dışındadırlar.

**İlk kesit bu izin tablosundan daha AZ araç açar** (§7). Bu bilinçlidir.

---

## 6. Bütçe — ölçülmüş veriyle

Ölçülen tek `POST /api/compare` çağrısı (start `[50,50]`, goal `[440,440]`,
rover `lpr_1`): **HTTP 200, duvar saati 21.3175 s**, dört profil, profil başına
`computation_time_ms` toplamı 17.9727 s.

İlk kesit için sert, sunucu tarafında zorlanan soru başına limitler:

| Limit | Değer |
|---|---|
| `compare` aracı | en fazla **1** |
| Serbest/okuma analitik çağrısı | en fazla **20** |
| Araç döngüsü turu | en fazla **4** |

Bir soruda ikinci `compare` yapılmaz.

**Uygulanmayanlar ve nedeni:** compare ön-ısıtma yok, compare önbelleği yok,
arka plan işi yok, SSE yok, oturum kalıcılık sistemi yok.

v0.2 §5'teki *"oturum başına 20 yeniden hesaplama"* fikri bu ilk **durumsuz** dikey
kesitte **uygulanmamıştır**, çünkü kalıcı sohbet oturumu durumu açıkça kapsam
dışıdır. Burada kayda geçirilmiştir; zorlanıyormuş gibi davranılmaz.

---

## 7. Araç katmanı

### 7.1 İlk kesit araç kümesi

| Araç | Amaç |
|---|---|
| `inspect_cell` | Belirli bir grid hücresi hakkındaki soruları deterministik backend telemetrisiyle yanıtlar |
| `compare_mission_profiles` | Yan etkisiz ayrık duyarlılık / profil karşılaştırması |

Mevcut planın özeti **araç gerektirmez**; kullanıcının hâlihazırda ürettiği
`PlanResponse`'undan arındırılarak model bağlamına konur.

Kayıt defterinde `plan`, `replan`, `load_dem`, `pose`, `score_path`, keyfi HTTP,
kabuk ya da dosya sistemi aracı **yoktur**.

### 7.2 `compare_mission_profiles` koordinat almaz

Araç, modelden **keyfi koordinat kabul etmez**. `start`, `goal` ve `rover_id`
salt-okunur misyon anlık görüntüsünden gelir. Bu bilinçlidir: model, kullanıcının
arkasından farklı bir rota konumu seçemez.

Dört misyon profili ağırlık uzayında dört örneklenmiş noktadır; bu, etkileşimli çok
amaçlı optimizasyon literatüründeki **ayrık Pareto örneklemesi** desenidir. Sürekli
ağırlık perturbasyonu bu kesitte yoktur (R-12).

### 7.3 Model yetkilendirme sınırı değildir

Her istenen fonksiyon adı ve argümanı sunucu tarafında doğrulanır. Model bilinmeyen
ya da yasak bir fonksiyon isterse çalıştırılmaz; deterministik bir araç hatası
döndürülür ya da güvenle sonlandırılır.

OpenAI'nin yerleşik `web search`, `file search`, `computer use`, `shell` ve
`code execution` araçları bu özellikte **etkinleştirilmez**. Model yalnızca açıkça
tanımladığımız özel fonksiyonları görür.

---

## 8. Yetenek durumu — abartılmadan

| Kod | Durum |
|---|---|
| `C-SUMMARY` | **VAR** |
| `C-POINT` | **VAR** |
| `C-COMPARE` | **VAR** |
| `C-BINDING` | **KISMİ** — `constraint_check` üzerinden |
| `C-INFEASIBLE` | **KISMİ** — compare sonuç metrikleri üzerinden |
| `C-SENSITIVITY` | **AYRIK** — dört misyon profili boyunca |
| `C-DECOMPOSE` | **YALNIZCA HÜCRE** |
| `C-CONTRAST` | **YOK** |
| `C-RECOURSE` | **YOK** |

Kısmi yetenekler tam gibi sunulmaz.

---

## 9. Provenance sözleşmesi

### 9.1 Ham merdiven korunur

```
SYNTHETIC < DERIVED < MODEL < MEASURED
```

En zayıf girdi kazanır. **En zayıf-girdi hesabı önce ham dört basamaklı merdiven
üzerinde yapılır**, sonra görüntüleme etiketine eşlenir.

### 9.2 Üç basamaklı arayüz eşlemesi

Mevcut arayüz pedigree'si üç basamaklıdır. Kilitlenen eşleme:

| Ham `layer_validity` | Görüntüleme pedigree'si |
|---|---|
| `MEASURED` | `measurement` / **Ö** |
| `MODEL` | `model` / **M** |
| `DERIVED` | `model` / **M** |
| `SYNTHETIC` | `demo` / **D** |

### 9.3 Kanıt her ikisini de taşır

Pratik olduğu her yerde kanıt hem ham hem görüntüleme değerini korur:

- `rawValidity`: `MEASURED | MODEL | DERIVED | SYNTHETIC`
- `displayPedigree`: `measurement | model | demo`

Ham validity yok edilmez.

### 9.4 Birim zorunluluğu

Sayısal kanıt/nicelikler için **birim bulunmak zorundadır**. Birimi bilinmeyen
değerler dışlanır. Birim uydurulmaz. (R-7.)

---

## 10. Sağlayıcı kararı — KİLİTLİ

| | |
|---|---|
| Sağlayıcı | OpenAI API |
| API | Responses API |
| Varsayılan model | `gpt-5.6-terra` |
| SDK | resmî Python `openai==3.6.0` |
| Konum | **yalnızca sunucu tarafı** |

Ortam değişkenleri:

| Değişken | Anlam |
|---|---|
| `LUNAPATH_OPENAI_API_KEY` | API anahtarı. Asla commit edilmez, asla loglanmaz. |
| `LUNAPATH_OPENAI_MODEL` | Model kimliği. Varsayılan `gpt-5.6-terra`. |
| `LUNAPATH_AI_PROVIDER` | Sağlayıcı seçici. Varsayılan `openai`. Test/geliştirme için `stub`. |

`.env.example` boş yer tutucularla depoda bulunur. Gerçek `.env` `.gitignore`
tarafından yoksayılır.

**Frontend'e anahtar konmaz.** Tarayıcı yalnızca `/api/ai/chat` ile konuşur.
`VITE_OPENAI_API_KEY`, frontend `.env` enjeksiyonu ve tarayıcı tarafı OpenAI
çağrısı yasaktır.

OpenAI sağlayıcısı seçili ve anahtar yoksa, açık bir yapılandırma/servis hatası
döndürülür. Sahte bir kullanıcı yanıtına **sessizce düşülmez**.

Stub sağlayıcı yalnızca testler ve açık yerel arayüz doğrulaması içindir; üretim
yedeği hâline gelmez.

---

## 11. Doğrulama yükümlülüğü

Aşağıdakiler otomatik testlerle kanıtlanır:

- §4.2'deki dışlanan alanların hiçbiri kanıta ulaşmaz;
- `comparison.recommendation` kanıta ulaşmaz;
- `computation_time_ms` ve `corridor_id` soyulur;
- sayısal nicelikler birim taşır, birimi bilinmeyenler dışlanır;
- en zayıf-girdi provenance hesabı ham merdiven üzerinde doğrudur;
- dört basamaklı → üç basamaklı eşleme doğrudur;
- yalnızca `inspect_cell` ve `compare_mission_profiles` çağrılabilir;
- bilinmeyen araç reddedilir; `plan`/`replan`/yükleme/`pose` kayıt defteri üzerinden erişilemez;
- soru başına en fazla bir `compare`, en fazla 20 okuma;
- istemci `system`/`developer` rolü veremez;
- mevcut plan arındırıcısı `summary.total_energy_consumed_wh` ve
  `summary.max_continuous_shadow_h` kullanır, `astar_metrics` karşılıklarını asla;
- sohbet turu aktif korridoru değiştirmez.

---

## 12. Kapsam dışı

Bu kesitte uygulanmaz: rota geneli maliyet ayrışması · `POST /api/score-path` ·
`C-CONTRAST` · `C-RECOURSE` · keyfi ağırlıkla yeniden koşum · `dry_run` plan ·
`/api/plan` üzerinde `profile_id` · bariyer slack ifşası · AI ile rota üretimi ya da
değiştirilmesi · `replan` · `plan-4d` · `pose` araçları · `illumination-series`
araçları · otonom ajan döngüsü · SSE · WebSocket · iş kuyruğu · arka plan işçisi ·
compare ön-ısıtma · compare önbelleği · veritabanı · konuşma kalıcılığı.
