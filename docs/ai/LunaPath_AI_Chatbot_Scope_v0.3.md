# LunaPath — AI Karar-Destek Sohbet Katmanı · Kapsam Sözleşmesi v0.3

| | |
|---|---|
| **Durum** | Yürürlükte. Bu özellik için **kendi kendine yeten, yetkili** AI/sohbet sözleşmesi. |
| **Backend temeli** | `fea37ef5d90d998b9a24cc2de6631954028347d0`, backend sürüm `0.3.0` |
| **Kanıt** | `docs/BACKEND_ENVANTER.md`, `docs/backend_capabilities.json` |
| **Öncülü** | `docs/ai/LunaPath_AI01_Kapsam_Revizyon_v02.md` (v0.2), bu dizinde değiştirilmeden saklanır |
| **Jenerik sözleşme** | `docs/ai/LunaPath_AI01_Kapsam_ve_Arayuz_Sozlesmesi_v01.md` (AI-02 v0.1), bu dizinde değiştirilmeden saklanır |

---

## 0. Bu belgenin varlık nedeni

### 0.0 Normatif hiyerarşi

Çelişki hâlinde sıra yukarıdan aşağıdır:

| # | Kaynak | Rolü |
|---|---|---|
| 1 | **AI-02 v0.1** — `LunaPath_AI01_Kapsam_ve_Arayuz_Sozlesmesi_v01.md` | Jenerik, backend-bağımsız sözleşme |
| 2 | **AI-01 Kapsam Revizyonu v0.2** — `LunaPath_AI01_Kapsam_Revizyon_v02.md` | Denetim sonrası açık geçersiz kılmalar |
| 3 | `docs/BACKEND_ENVANTER.md` + `docs/backend_capabilities.json` | Somut backend gerçeği |
| 4 | Ölçülmüş uygulama bulguları | T-13, T-14, compare ≈ 21.3 s |

v0.2 **yalnızca** AI-02 §4, §8.2, §9, §11 ve §12/D-1 bölümlerini geçersiz kılar.
Dolayısıyla AI-02'nin §1 (B-1…B-3), §2 (S-1…S-12), §3 (**N-1…N-17**), §5 (veri
sözleşmesi), §6 (K1–K5 mimarisi), §7 (L1/L2/L3), §8.1 (`E-*` kodları), §8.3
(K5 sayı-topraklaması) ve §10 (kabul ilkeleri) bölümleri **bağlayıcıdır**.

### 0.1 Kaynak belge kurtarıldı — bu bölümün önceki iddiası geçersizdir

v0.3'ün ilk sürümü `AI-02 v0.1`'i **kurtarılamaz** ilan etmiş, N-1…N-17'yi,
`Quantity` sözleşmesini ve §6 katman mimarisini bilinmeyen sayarak yerlerine
yerel bir `R-1…R-12` kümesi koymuştu.

**Belge bulundu** ve `docs/ai/LunaPath_AI01_Kapsam_ve_Arayuz_Sozlesmesi_v01.md`
olarak değiştirilmeden depoya alındı (AI-02 · TASLAK v0.1 · 1 Eylül 2026).
O iddia burada geri çekilmiştir. Kayıp sayılan üç bölümün üçü de mevcut ve
bağlayıcıdır; bu belge artık onları yeniden üretmez, **onlara atıf yapar**.

`R-1…R-12` kümesi yerini kurtarılan **N-1…N-17**'ye bırakır. Yalnızca denetimden
doğan iki kural yerel kalır: **N-18** (asistan `/api/plan` çağırmaz) ve **N-19**
(doğrulanmamış alanlar çıktıda geçemez).

### 0.2 v0.2'nin numaralandırma tutarsızlığı

v0.2 §10 *"v0.1 §3'teki 19 yasak (N-1…N-19)"* diyor; v0.2 §2 ise `N-18`'i **yeni**
kural olarak §3.3'e ekliyor. N-18 aynı anda hem yeni hem de önceden var olan
19'luk kümenin üyesi olamaz. Kurtarılan AI-02 v0.1 §3 tam olarak **N-1…N-17**
içeriyor; N-18 ve N-19 gerçekten denetim sonrası eklerdir. Yani v0.2 §10'un
"§3'teki 19 yasak" ifadesi kaynağın kendisindeki bir yazım hatasıdır —
v0.1 §3'te 17 yasak vardır. Tutarsızlık **çözülmemiş olarak kayda geçirilmez**;
burada kurtarılan belgeye bakılarak giderilmiştir.

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

## 3. Davranış kuralları — N-1 … N-19

Bağlayıcı çerçeve, kurtarılan **AI-02 v0.1 §3**'tür. Aşağıdaki tablo o bölümü
özetler; çelişki hâlinde kaynak belge geçerlidir. Yalnızca N-18 ve N-19 denetimden
doğan yerel eklerdir.

### 3.1 Hesaplama yasakları (AI-02 §3.1)

| # | Kural |
|---|---|
| **N-1** | Asistan hiçbir sayıyı kendisi hesaplamaz — toplama, çıkarma, çarpma, bölme, yüzde, oran, ortalama, birim çevirme dahil. Tek sayı kaynağı deterministik çekirdektir. |
| **N-2** | Asistan yanıtında, aldığı analiz çıktısının `numeric_registry` alanında bulunmayan hiçbir sayı geçemez. Değerin "yükte bir yerde geçmesi" yeterli değildir; K1 onu açıkça kaydetmiş olmalıdır. |
| **N-3** | Asistan rota üretmez, waypoint önermez, koordinat uydurmaz. |
| **N-4** | Asistan maliyet fonksiyonunu, ağırlıkları veya fizik modelini değiştirmez. (Denetlenmiş `C-COMPARE` ayrık profil hesabı bunu ihlal etmez: hesabı deterministik K1 yapar ve mevcut profilleri kullanır.) |
| **N-5** | Asistan veri katmanı üretmez, doldurmaz, tahmin etmez. Eksik veri → `E-NODATA`. |

### 3.2 İddia yasakları (AI-02 §3.2)

| # | Yasak ifade | Doğru ifade |
|---|---|---|
| **N-6** | "Otonom navigasyon" / "engel kaçınma yapıyoruz" | "Global rota planlama; yerel engel kaçınma kapsam dışı" |
| **N-7** | "Gerçek NASA verisiyle çalışıyoruz" | Katmanın provenance etiketini olduğu gibi söyler |
| **N-8** | "Bu rota güvenlidir" / "rover'ı korur" | "Bu rota, tanımlı kısıtları ihlal etmiyor" — ve yalnızca deterministik kanıt destekliyorsa |
| **N-9** | "Bu alanda ilk/özgün/tek" | Karşılaştırmalı üstünlük iddiası kurmaz |
| **N-10** | "Rover üzerinde çalışabilir" | Sınır B-1 |
| **N-11** | "kesinlikle", "garanti", "%100" | Belirsizlik bandı varsa birlikte verilir |

### 3.3 Davranış yasakları (AI-02 §3.3)

| # | Kural |
|---|---|
| **N-12** | Asistan kullanıcıyı bir rotaya ikna etmeye çalışmaz; trade-off sunar, seçimi kullanıcıya bırakır. |
| **N-13** | Anlatım seviyesi **sonucu değiştirmez** — yalnızca anlatımı değiştirir. |
| **N-14** | Asistan güvenlik uyarılarını, kısıt ihlallerini veya belirsizlik beyanlarını hiçbir seviyede atlamaz veya yumuşatmaz. |
| **N-15** | Arazi, DEM ve fiziksel sıcaklık "ayarlanabilir parametre" gibi sunulmaz. |
| **N-16** | Asistan kısıt gevşetmeyi tavsiye etmez; yalnızca sonucunu gösterir. (Bu kesitte gevşetme analizi yeteneği zaten yok.) |
| **N-17** | LunaPath dışı konular (genel Ay bilimi, kod yazma, ödev) → `E-SCOPE`. |

### 3.4 Denetimden doğan yerel ekler

| # | Kural |
|---|---|
| **N-18** | Asistan `POST /api/plan` çağırmaz. Kullanıcının başlattığı planı okur; kendi hesaplarını yan etkisiz uçlar üzerinden yapar. (v0.2 §2.) |
| **N-19** | Backend envanterinin BİLİNMİYOR listesindeki hiçbir alan asistan çıktısında olgu olarak geçemez. (v0.2 §4.3.) |

Provenance sınırlamaları, maddi olarak ilgili olduğunda iletilir. Her yanıt gereksiz
uyarı yığınına boğulmaz (N-14 ile çelişmez: zorunlu uyarılar `warnings` kanalında
taşınır ve hiçbir seviyede gizlenemez).

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

## 12. Katman mimarisi — K1…K5 (AI-02 §6)

| Katman | Ne yapar | Ne YAPAMAZ | LLM? |
|---|---|---|---|
| **K1 — Analiz çekirdeği** | Tüm hesaplar; tüm sayıların tek kaynağı. `AnalysisEnvelope` üretir | Metin üretmek, seviye bilmek | Hayır |
| **K2 — Yönlendirici** | Serbest metni yetenek kodu + parametreye çevirir | Sayı üretmek, cevap yazmak | Evet |
| **K3 — Safeguard** | Yetenek varlığı, şema, aralık, izin, bağlam, bütçe denetimi | Yorum yapmak | Hayır |
| **K4 — Sözelleştirici** | Yalnızca doğrulanmış zarfı seviyeye göre anlatır | Hesap yapmak, kayıt dışı sayı kullanmak | Evet |
| **K5 — Çıkış denetimi** | Sayı-eşleme + yasak ifade taraması | Metni "düzeltmek" | Hayır |

Üretim akışı:

```
KULLANICI → K2 (yapılandırılmış yönlendirme) → K3 (deterministik kapı)
          → K1 / AnalysisProvider → AnalysisEnvelope
          → K4 (sözelleştirme) → K5 (deterministik doğrulama) → KULLANICI
```

Mevcut plan özeti yolu ek hesap gerektirmez:

```
KULLANICI → K2 (answer_from_context) → K1 (snapshot'tan C-SUMMARY zarfı)
          → K4 → K5 → KULLANICI
```

**K2 çıktı kısıtı.** K2 asla serbest metin üretmez:

```ts
type RouterOutput =
  | { action: "invoke"; capability: string; params: object; rationale_key: string }
  | { action: "clarify"; missing: string[] }
  | { action: "refuse"; code: ErrorCode }
  | { action: "answer_from_context" };
```

K2 anlamsal yetenek tanımlayıcıları görür; backend uç adı veya ham alan yolu
**görmez**. K4 yalnızca `Metric` / `AnalysisEnvelope` verisi görür. Somut uç ve
alan bağlamaları `AnalysisProvider` / K3 adaptör kodunda kalır.

**K5 davranışı.** İhlal bulursa metni düzenlemez — **bloklar**, `E-GROUNDING`
döner ve yalnızca kayıtlı değerlerden kurulmuş deterministik bir Türkçe özet
gösterir. Sessiz düzeltme, hatanın görünmez hâle gelmesi demektir.

---

## 13. Veri sözleşmesi (AI-02 §5.1)

```ts
type Quantity   = { value: number; unit: string; precision?: number };
type Provenance = { source: "MEASURED"|"DERIVED"|"MODEL"|"SYNTHETIC";
                    layer?: string; dataset?: string; version?: string; note?: string };
type Metric     = { key: string; label: string; quantity: Quantity;
                    provenance: Provenance; uncertainty?: {...} };
type NumericRegistry = Metric[];
type Warning    = { code: string; severity: "info"|"caution"|"critical";
                    message: string; suppressible: false };
type AnalysisEnvelope<T> = {
  capability; request_echo; ok; payload?; error?;
  numeric_registry; warnings; provenance_summary; compute_ms; backend_version;
};
```

**Dört basamaklı ham merdiven korunur.** En zayıf-girdi hesabı `SYNTHETIC <
DERIVED < MODEL < MEASURED` üzerinde yapılır; §9'daki üç basamaklı
`displayPedigree` yalnızca bir **arayüz gösterim eşlemesidir** ve iç modelin
yerine geçmez.

**Türetilmiş yüzdeler.** K1 bir oranı yüzdeye çevirdiğinde ortaya çıkan `Metric`
`source: "DERIVED"` taşır ve kaynak metriği adıyla referanslar. Her oran için
otomatik yüzde üretilmez — yalnızca ürünün gerçekten ihtiyaç duyduğu yerde.

**Kanonik gösterim.** K1 her kayıtlı `Quantity` için tek bir kanonik gösterim
dizgesi üretir (ondalık virgül, **binlik ayracı yok**). K4 analitik nicelikleri
bu dizgeleri **birebir kopyalayarak** yazar; sayıyı serbestçe biçimlendiremez ve
kelimeyle yazamaz. K5'in toleransı **sıfırdır**: yuvarlama bir kez, K1'de,
`precision` uyarınca yapılır.

### 13.1 `warnings` ve `limitations` — anlamına göre ayrı

Bir madde **asla iki dizide birden** bulunmaz.

| Kanal | Anlamı |
|---|---|
| **`warnings`** | Zorunlu, yapılandırılmış, `suppressible: false`. K4 düzyazısından **bağımsız** render edilir, L1/L2/L3 boyunca değişmez (N-14). Kanıt geçerliliği, topraklama, kısıt veya yorum **maddi olarak etkilendiğinde** kullanılır. |
| **`limitations`** | Bilgilendirici kapsam/yetenek notu. Özelliğin neyi *kuramadığını* açıklar. Zorunlu uyarının yerine geçmez. |

`warnings` örnekleri: `CELL_COST_BREAKDOWN_WEIGHT_MISMATCH` (ağırlık uyuşmazlığı
`cost_breakdown`'ı mevcut planın açıklaması olarak geçersiz kılar) · zorunlu
provenance/veri-geçerliliği kaydı · kısıt ihlali · `E-GROUNDING` sonrası
kullanıcıya görünen uyarı.

`limitations` örnekleri: "Rota geneli maliyet ayrışması mevcut değil" ·
"Duyarlılık, önceden tanımlı profiller üzerinden ayrıktır" · "Bu sonuç, geometrik
sapmanın kesin nedenini belirleyemez".

**Kısıt uyarıları için icat edilmiş eşik yoktur.** Bir kısıt uyarısı yalnızca
deterministik bir backend alanı gerektirdiğinde üretilir (`satisfied is False`
ya da backend'in açıkça verdiği durum/marj). AI tanımlı "sınıra yakın" eşiği yok.

---

## 14. Anlatım seviyesi — L1 / L2 / L3 (AI-02 §7)

| Seviye | Kullanıcı tanımı |
|---|---|
| **L1** | "Konuya yeniyim, genel hatlarıyla anlamak istiyorum" |
| **L2** | "Mühendislik geçmişim var, sayıları ve gerekçeleri görmek istiyorum" (görsel varsayılan) |
| **L3** | "Alan uzmanıyım, ham veri ve daha çok ayrıntı istiyorum" |

Seçim **açıktır**; davranıştan gizli çıkarım yapılmaz. İlk normal sohbet turundan
önce oturum-yerel **bir açık seçim/onay** istenir. Modal yok, kalıcılık yok.

Seviye **yalnızca anlatımı** değiştirir (N-13): aynı `AnalysisEnvelope`, aynı
`numeric_registry`, aynı `warnings`, aynı provenance. L3 arındırılmış zarfta
olmayan bir alana erişemez; ham backend JSON'u hiçbir seviyede görünmez.

---

## 15. Hata kodları (AI-02 §8.1)

| Kod | Anlamı | Örnek |
|---|---|---|
| `E-SCOPE` | Soru LunaPath kapsamı dışında | "Ay'ın yarıçapı nedir?", "Python kodu yaz" |
| `E-UNSUPPORTED` | Yetenek denetlenmiş backend'de mevcut değil | `C-CONTRAST`, `C-RECOURSE` |
| `E-SCHEMA` | Parametre şemaya uymuyor | K2 iki denemede geçerli `RouterOutput` üretemedi |
| `E-RANGE` | Parametre izinli aralık dışında | Grid dışı `row`/`col` |
| `E-BUDGET` | Hesap bütçesi aşıldı | Bir soruda ikinci `compare` |
| `E-NODATA` | Gerekli veri katmanı yok | — |
| `E-CONTEXT` | Analiz bağlamı yok/geçersiz | Plan yokken özet istendi |
| `E-GROUNDING` | K5 çıkış denetimi başarısız | Kayıtta olmayan sayı |

Her red **gerekçelidir**: kod + Türkçe neden. Alternatif yalnızca gerçekten
desteklenen bir alternatif varsa önerilir; uydurulmaz.

---

## 16. İzlenebilirlik

### AI-02 v0.1'den devralınan (bağlayıcı)

`B-1…B-3` sert sınırlar · `S-1…S-12` kapsam · `N-1…N-17` yasaklar ·
`Quantity` / `Provenance` / `Metric` / `NumericRegistry` / `Warning` /
`AnalysisEnvelope` · `AnalysisProvider` portu · `K1…K5` katman mimarisi ·
`L1/L2/L3` seviye modeli · `E-*` hata kodları · §8.3 K5 sayı-topraklaması ·
§10 kabul ilkeleri (`A-1…A-8`).

### v0.2 tarafından geçersiz kılınan

AI-02 §4 eski yetenek varsayımları · §8.2 üç-koşum / 15 s bütçesi ·
§9 backend teyit listesi · §11 faz planı · §12/D-1 izin varsayımı.

### Denetimden sonra eklenen

`N-18` (asistan `/api/plan` çağırmaz) · `N-19` (doğrulanmamış alan yüzeye çıkmaz) ·
`T-1…T-12` (v0.2 §4.2) · `T-13` (`comparison.recommendation` dışlanır) ·
`T-14` (grid olguları çalışma zamanından gelir) · ölçülen compare ≈ 21.3 s ·
OpenAI Responses API sağlayıcı kararı.

Tarihsel tutarsızlıklar silinmez; öncelik sırası §0.0'da kayıtlıdır.

---

## 17. Kapsam dışı

Bu kesitte uygulanmaz: rota geneli maliyet ayrışması · `POST /api/score-path` ·
`C-CONTRAST` · `C-RECOURSE` · keyfi ağırlıkla yeniden koşum · `dry_run` plan ·
`/api/plan` üzerinde `profile_id` · bariyer slack ifşası · AI ile rota üretimi ya da
değiştirilmesi · `replan` · `plan-4d` · `pose` araçları · `illumination-series`
araçları · otonom ajan döngüsü · SSE · WebSocket · iş kuyruğu · arka plan işçisi ·
compare ön-ısıtma · compare önbelleği · veritabanı · konuşma kalıcılığı.
