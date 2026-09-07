# Faz 7 Tamamlanma Raporu

**Tarih:** 30 Ağustos 2026
**Branch:** `backend/physics`
**Plan:** [`2026-08-30-faz7-odometri-plani.md`](2026-08-30-faz7-odometri-plani.md)
**Commit aralığı:** `1a00605..f2a3bf5` (7 commit)

---

## Özet

Altı görevin altısı da tamamlandı: **7 commit**, **95 yeni backend testi** (+ colcon tarafında 6 yeni dönüşüm testi), hepsi yeşil.

Faz 7'nin tek cümlelik iddiası korundu: **LunaPath odometri üretmez; odometri tüketir ve yörünge DEM'iyle doğrular.** Hiçbir SLAM/VO algoritması yazılmadı, hiçbir odometri kütüphanesi bağlanmadı (lisans yüzeyi sıfır) — yalnızca `nav_msgs/Odometry` mesajı tüketiliyor.

| Görev | Modül | Test |
|---|---|---|
| T1 | `app/pose.py` — `PoseEstimate` giriş sözleşmesi + quaternion→grid heading | 24 |
| T2 | `app/localization.py` — koridor içi projeksiyon, tetikleyici besleme | 19 |
| T3 | `app/slip_model.py` — slip modeli + `slip_accumulation` tetikleyicisi | 18 |
| T4 | `app/skyline.py` ⭐ — DEM ufuk küpünden mutlak konum + SPICE güneş köprüsü | 20 |
| T5 | `POST /api/pose` + ROS 2 `pose_monitor` + `ReplanTrigger.msg` | 10 (+6 colcon) |
| T6 | `app/localization_budget.py` + rapor script'i | 9 |

---

## Kapalı döngü ilk kez uçtan uca

`replan_triggers.py`'deki `corridor_violation` ve `localization_uncertainty` tetikleyicileri bugüne kadar girdilerini test fixture'larından alıyordu — üretimde onları besleyen hiçbir şey yoktu. Artık:

```
poz → project_onto_corridor → lateral_offset_m / half_width_m
    → evaluate_pose → tetikleyiciler → trigger_state
    → POST /api/replan (değişmeden) → yeni plan
```

Bu zincir `test_pose_endpoint.py::test_the_closed_loop_pose_to_replan`'da gerçek `/api/plan` → koridor → koridor dışı poz → `/api/replan` olarak uçtan uca test ediliyor. Aynı değerlendirme (`localization.evaluate_pose`) hem FastAPI endpoint'inin hem ROS düğümünün çağırdığı **tek** fonksiyon — politika iki kabuk arasında sapamaz.

Karar politikası: `localization_uncertainty` ateşlediğinde öneri `replan` değil **`stop_and_localize`** — koridordan geniş bir belirsizlikle replan yapmak, yalan bir pozdan plan yapmaktır.

---

## Slip düzeltmesinin `f_energy`'ye etkisi (kabul kriteri tablosu)

Gerçek `edge_energy_wh` ile, 80 m'lik kenar, `lpr_1`. Yeniden üretim:
`python -c "from app.cost_engine import edge_energy_wh; from app.slip_model import slip_ratio, effective_distance_m; ..."` (test_slip_model.py aynı ilişkiyi assert ediyor).

| Eğim | slip_ratio | Enerji (slipsiz) | Enerji (slipli) | Fark |
|---|---|---|---|---|
| 0° | 0.020 | 22.22 Wh | 22.68 Wh | +2.0% |
| 5° | 0.035 | 29.17 Wh | 30.21 Wh | +3.6% |
| 10° | 0.060 | 36.72 Wh | 39.07 Wh | +6.4% |
| 15° | 0.104 | 45.21 Wh | 50.47 Wh | +11.6% |
| 20° | 0.180 | 55.04 Wh | 67.17 Wh | +22.0% |
| 25° | 0.313 | 66.74 Wh | 97.13 Wh | +45.5% |

**Dürüstlük etiketi:** `SLIP_MODEL_VALIDITY = "UNCALIBRATED"` — katsayılar (`i0=0.02, k=0.11`) Ay regoliti için ölçülmüş değil. İddia **yön** iddiasıdır (eğimde enerji daha yüksek ve fark eğimle büyür), **büyüklük** iddiası değildir. Etiket modül adında, docstring'de ve tetikleyicinin her `detail` string'inde taşınıyor; testler de bu yüzden kesin fiziksel değer değil şekil/yön assert ediyor.

---

## T6'nın operasyonel bulgusu — sunum tablosu

`scripts/localization_budget.py`, gerçek 500×500 grid'de gerçek bir rota planlayıp koridorun kendi genişlikleriyle karşılaştırıyor ([docs/research/localization_budget.md](../../research/localization_budget.md)):

Rota 2.17 km, medyan yarı genişlik 15.8 m, minimum 5.0 m, σ₀ = 1 m:

| Kaynak | Drift | Sıfırlamasız mesafe | Rota sığar mı? |
|---|---|---|---|
| Ölü hesap (MER sınıfı) | %10 | **148 m** | **hayır** (~15 sıfırlama gerekir) |
| Görsel odometri (M2020 sınıfı) | %0.5 | 2.96 km | evet |
| VO + skyline sıfırlama | fix'ler arası | her güvenilir fix'te sıfırlanır | evet |

Planın sorduğu soru buydu: LunaPath'in ürettiği koridor gerçek bir odometri yığınının hata bütçesiyle uyumlu mu? Cevap: **VO sınıfı bir yığınla evet, salt ölü hesapla hayır** — ve bu, skyline/güneş sıfırlamasının neden T4'te inşa edildiğinin sayısal gerekçesi.

---

## T4 — skyline eşleme: tek çekirdeğin üçüncü ürünü

`horizon_map()` zaten her hücre için her azimutta ufuk açısı döndürüyor (Faz 1: gölge; Faz 5: sanal LiDAR). `match_skyline()` gözlenen bir ufuk profilini bu küpte arıyor: SSD skoru, en iyi hücre, ve **zorunlu** `ambiguity_ratio` (kazananın 3×3 komşuluğu hariç ikinci-en-iyi ile oran — komşu hücreler her zaman benzer görünür, o belirsizlik değil piksel-altı doğruluktur).

Düz platoda eşleşme **güvenli diye değil, etiketli döner**: `confident=False`. Sessizce yanlış hücre döndürmek bu modülün önlemek için kurulduğu tek şeydir ve düz-DEM testi tam bunu assert ediyor.

`expected_sun_angles()` SPICE köprüsü: Ay'da manyetik alan yok → mutlak yönelim gökten gelir. Test, grid/true kuzey farkının site boylamına (32.3°) eşit olduğunu doğruluyor — kutup merkezli stereografik CRS için bu tam olarak beklenen dönüş; Faz 2'nin çerçeve hatasının tekrarını yapısal olarak engelliyor.

**Sınır (planın zorunlu kıldığı):** 5 m/px DEM'den üretilen ufuk, kameranın gördüğünün alçak-geçiren filtrelenmiş hâlidir; yakın alan topografyası temsil edilmez. Bu bir **arayüz ve fizibilite kanıtıdır, konum belirleme ürünü değildir** — `skyline.py` docstring'i bunu aynen söylüyor.

---

## Plan tasarım-belgesi olduğu için verilen kararlar

Faz 6'nın aksine bu plan kod bloğu içermiyordu ("PLAN — kod yazılmadı"); şu kararlar uygulamada verildi ve commit mesajlarında gerekçeli:

1. **Aktif koridor tek-slot sunucu durumu** (`app.state.active_corridor`), `app.state.grids` deseniyle aynı: tek rover, sürülmekte olan tek rota. Koridor yokken `/api/pose` 409 döner.
2. **Slip sinyali** = koridor boyunca gerçek ilerleme (`along_track_m`) vs. estimator'ın kat ettiğini iddia ettiği mesafe. Mutlak fix'ler slip kontrolüne girmez (karşılaştırılacak mesafe taşımazlar).
3. **Quaternion→heading tek evde** (`app.pose.quaternion_to_grid_heading_deg`), ölçek-değişmez paydayla (`qw²+qx²−qy²−qz²` — ders kitabındaki `1−2(qy²+qz²)` yalnız birim normda eşdeğer). ROS tarafı bunu sarar, yeniden türetmez.
4. **Bilinmeyen kovaryans güvene çevrilmez:** ROS'ta negatif varyans "bilinmiyor" demektir; yapılandırılmış bir fallback yoksa mesaj reddedilir. NaN kovaryans da sözleşme sınırında reddedilir (≥0 kontrolü NaN'ı geçirir; geçseydi `check_localization_uncertainty` sessizce fail-open olurdu — review #4'ün deseni).
5. **Koridor ROS'ta latched yayınlanır** (`transient_local`): plan yapıldıktan sonra başlayan monitor da koridoru alır; yeni koridor kat-edilen-mesafe integralini sıfırlar.

---

## Kabul kriterleri

| Kriter | Durum |
|---|---|
| `PoseEstimate` tanımlı, `source` zorunlu, testli | ✅ 24 test |
| İki tetikleyici gerçek pozdan besleniyor | ✅ `trigger_state_from_pose` + e2e |
| `slip_accumulation` tetikleyicisi + birim testi | ✅ 6 test |
| `slip_ratio(20°)`'nin `f_energy` etkisi sayısal tabloyla | ✅ yukarıda |
| `match_skyline` bilinen hücreyi buluyor; düz arazide belirsizliği raporluyor | ✅ her ikisi testli |
| `/api/pose` → tetikleyici → `/api/replan` kapalı döngüsü uçtan uca | ✅ `test_the_closed_loop_pose_to_replan` |
| ROS `nav_msgs/Odometry` aboneliği; sıfır odometri kütüphanesi bağımlılığı | ✅ `pose_monitor.py` |
| `docs/research/localization_budget.md` üretildi; koridor vs. drift karşılaştırıldı | ✅ |
| "LunaPath odometri üretmez, tüketir ve DEM'iyle doğrular" net; SLAM/VO iddiası yok | ✅ modül docstring'leri + bu rapor |
| `skyline.py` çözünürlük sınırı belgede | ✅ docstring + bu rapor |

## Bilinen sınırlar

- ROS tarafı (colcon testleri dahil) bu Windows makinesinde **çalıştırılamadı** — ROS kurulu değil; dosyalar derleme-kontrolünden geçti (`py_compile`) ve mevcut colcon test desenine yeni testler eklendi. Doğrulama, WSL2 ROS ortamında `colcon test` gerektirir.
- Slip katsayıları kalibre edilmemiş; skyline eşleme 5 m/px bandıyla sınırlı; drift oranları başka araçların yayınlanmış değerleri. Üçü de ilgili modülde ve üretilen raporda etiketli.
- `slip_model.effective_distance_m` henüz `cost_engine`'in maliyet hattına **bağlanmadı** — plan T3'ü "düzeltme yönü + tetikleyici" olarak tanımlıyor; planlayıcı maliyetine entegrasyon, kalibrasyonsuz katsayılarla rotayı değiştirmemek için bilinçli olarak yapılmadı (yön iddiası ✅, büyüklük iddiası ❌ ilkesinin sonucu).

## Sonraki adım

Plan zinciri tamam (Faz 1–7). Bağımsız tam-backend review bu fazın hemen ardından yapılıp `docs/superpowers/reviews/` altına konacak.
