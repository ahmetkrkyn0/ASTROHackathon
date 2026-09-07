# B1 — Stokastik reach-avoid kurtarma politikası ve şans-kısıtlı 4-B planlama — Tasarım Belgesi

**Tarih:** 5 Eylül 2026 · **Dal:** `berke-3d-backendEnhance` · **Kaynak madde:**
[12_faktor_backend_ozellik_arastirmasi_2026-09-03.md § B1](../../research/12_faktor_backend_ozellik_arastirmasi_2026-09-03.md)
· **Bağımlılık:** A1 (safe haven maskesi, `time_to_safe_haven_hours`), B5 (SHERPA simülatörü),
C3 (slip'li kenar süresi) — üçü de tamamlandı.

**Yol:** mimari (yeni çekirdek modül `survival.py`, planlayıcıya yeni etiket ekseni ve kısıt, üç
uca yeni blok, bir yeni uç, SHERPA'ya arıza olayı, rapor betiği). Kullanıcı onay kapısını
kaldırdı; tasarım otonom kesinleştirildi, sayılar sondalardan (aşağıda) okunur.

**Kapsam:** yalnızca `backend/app/`, `backend/test_*.py`, `scripts/`, `docs/`. Frontend koduna
dokunulmaz; `docs/frontend/3b-veri-sozlesmesi.md`'ye "B1 eki" yazılır (yalnızca ekleme).

---

## Amaç

LunaPath'in 4-B planlayıcısı bugün deterministiktir: bir rota ya zarfın içindedir ya değildir;
"bu rotada işler ters giderse ne olur" sorusunun sayısı yoktur. Toronto STARS'ın (Lamarre,
Malhotra, Kelly) formülasyonu bu sayıyı üretir: rover'ın durumu **(hücre, zaman, batarya)**
üzerinde geriye doğru değer iterasyonuyla her durumdan **güvenli kümeye ulaşamama olasılığı**
`V(x)` (biz `P_safe = 1 − V` yayımlarız); arıza modeli Poisson (km başına α, toparlanma R saat);
sonra görev planlayıcısı "**görev başarısızlık olasılığı ≤ β**" şans kısıtıyla koşar ve her
durumdaki en iyi eylem (argmin) **kurtarma politikası** olur.

Tek cümlelik iddia: **Mevcut kaba grid (coarsen 4), gölge serisi ve `cost_engine` enerji fiziği
üzerinde (t, hücre, SOC kutusu) durum uzayı kurulur; Lamarre'nin üç sonuçlu arıza modeli ve
min-max konservatif eşlemesiyle geriye doğru tek geçişte `P_safe[t, y, x, soc]` ve politika
küpü hesaplanır (Site11'de ≈ 40 M durum, ~15 s); `astar_4d` her etiketinde yürütme
hayatta-kalma çarpanını taşır ve `max_failure_probability = β` verildiğinde `1 − surv > β`
olan geçişleri reddeder; `/api/plan-4d` `survival` bloğunu, `/api/cell-telemetry` hücrenin
`P_safe`'ini ve en iyi eylemini, `/api/replan` kurtarma önerisini, `GET /api/survival` katmanı
döndürür; tahmin edilen risk, politikayı izleyen Monte Carlo ve arıza olaylı SHERPA ile
gerçekleşen riske karşı denetlenir (konservatiflik).**

## İddia sınırı (her blokta, raporun her bölümünde)

- **Lamarre'nin sayıları alıntıdır, bizim ölçümümüz değil:** 41,5 M durum (LCROSS, 240 m/px,
  1 h × 250 Wh); 2,5 M durum (deney 1, 1 h × 100 Wh); tahmin/gerçekleşen risk karşılaştırması
  100 000 Monte Carlo (deney 3) — belgedeki "tahmin %0,4–9,8 / gerçekleşen %0,0–4,6" aralığı
  belgeden alıntıdır, makale HTML'inde bu iki aralık doğrulanamadı (yalnız "conservative"
  nitelemesi doğrulandı); AERO 2024: β = %2 → gerçekleşen %1,5 (**10 000** deneme, belgedeki
  "100 000" değil), risk-sınırlı plan risk-bilmez plana göre **+0,5 km, +2 h**; Ay gecesi kuralı
  "26 Eylül 2029'a kadar SOC ≥ %50 (15 000 Wh)". Bizim sayılarımız Site11'de koşturulup okunur.
- **Arıza oranı α ve toparlanma R VARSAYIMDIR:** hiçbir rover profili kaynaklı arıza oranı
  taşımıyor. Varsayılan α = 0,2 / km (Lamarre deney 3 ve AERO 2024 Tablo II: "1 arıza / 5 000 m"),
  R = 10 h (36 000 s) — kataloğa **sayı yazılmaz**; `constants` iki sabiti `assumption:`
  kaynağıyla taşır, her yanıt `failure_model.source` ile söyler, rapor α ∈ {0, 0,2, 0,5} / km
  süpürür.
- **Güvenli küme Lamarre'den sapar ve bunu söyler:** Lamarre'nin hedef kümesi "safe haven'da,
  Ay gecesini hibernasyonla geçecek SOC'de" durumlardır. A1'in ölçümü ve bu belgenin sondası
  (aşağıda) Site11'de LPR-1 için **hiçbir epokta haven olmadığını** gösterdi; o küme ile
  `P_safe ≡ 0` çıkar. Varsayılan güvenli küme bu yüzden **"leg"**: `{hedef bloğu, SOC ≥ rezerv}
  ∪ {haven bloğu, SOC ≥ hibernasyon eşiği}`; Lamarre'nin katı kümesi `safe_set="haven"` olarak
  seçilebilir ve raporda VIPER 30 Mayıs 2027 epoğunda (862 kaba haven bloğu) ölçülür.
- **Kesintisiz karanlık saati DP durumunda yoktur** (Lamarre'nin durumunda da yok): rezerv
  ihlali ve ufuk dışına çıkış başarısızlıktır; `h_max_shadow_h` yalnız **toparlanma beklemesinde**
  (karanlık hücrede R > h_max ise başarısızlık) girer. Planlayıcının kendi gölge saati etiketi
  aynen çalışır. D3'ün termal zarf ihlali bulgusu güvensiz-durum tanımına **girmez** (aksi hâlde
  her durum güvensiz olurdu; termal C6'ya bırakıldı).
- **Zaman ayrıklaştırması iyimser değil, kötümserdir ve ölçülür:** DP zaman kutusu plan
  diliminin tam katıdır (`m` dilim; 40 M durum tavanına göre otomatik), her eylem en az bir kutu
  sürer (`ceil`, planlayıcının kendi kuralı); Lamarre'nin φ_L/φ_U min-max eşlemesi `floor ≥ 1`
  olan hamlelerde geçişte, planlayıcı okumasında ise her zaman (komşu iki kutunun küçük
  `P_safe`'i) uygulanır. Raporda `m` süpürmesi (kısa leg) kutu genişliğinin `P_safe`'e etkisini
  gösterir.
- **Konservatiflik denetimi bir sayı yumuşatma fırsatı değildir:** "tahmin ≥ gerçekleşen"
  tutmazsa tutmadığı yazılır. İki gerçekleşme ölçülür: (i) politikayı izleyen Monte Carlo
  (`survival.rollout`, sürekli saat/SOC, Lamarre'nin doğrulaması) — DP'nin `V(start)`'ı ve
  planlayıcının yürütme riski **buna karşı** denetlenir; (ii) SHERPA (B5) sabit-rota tekrarı,
  arıza olayı eklenmiş — planlanan rotayı arıza sonrası **değiştirmeden** sürdüren bir
  politikadır, planlayıcının tahmini (arıza sonrası **optimal** kurtarma) ile bire bir
  karşılaştırılamaz; bilgi olarak raporlanır.
- **`max_failure_probability` verilmezse planlayıcı bugünkü davranışla bit-eşittir** (standart
  üç 4-B rota ve 2-B SHA kilitleri testte); `survival` bloğu istenmedikçe DP koşmaz ve plan-4d
  süresi değişmez.

## Kaynak / yöntem notu (5 Eylül 2026'da doğrulandı)

- **Makale 1 — arXiv 2307.16786** (Acta Astronautica 2023, *Recovery Policies for Safe Exploration
  of Lunar PSRs by a Solar-Powered Rover*), HTML okundu. Durum `x = (c, t, b)`; eylem kümesi
  **8 komşu + bekle** (δt_wait 5 000 s deney 1, deney 3'te değişken). Değer fonksiyonu **başarısızlık
  olasılığı**: `V_k(x) = 1_{X\O}(x) + 1_{O\S}(x) · min_a E[V_{k+1}(f(x,a))]`, sınır `V_N = 1_{X\S}`
  (güvenli 0, diğerleri 1); sonsuz ufuk, yakınsayana dek (ε = 1e-5; "rover sonlu sürede
  terminal duruma girer"). Arıza: Poisson, uzamsal oran α (deney 1: 1/1 000 m, R = 18 000 s;
  deney 3: **1/5 000 m, R = 36 000 s**); sürüş iki yarıya bölünür, **üç sonuç**:
  `Pr(F=0) = e^{−αρ}`, `Pr_h1 = 1 − e^{−αρ/2}` (kaynak hücrede), `Pr_h2 = e^{−αρ/2} − e^{−αρ}`
  (hedef hücrede); yalnız hareket eylemleri etkilenir. Konservatif eşleme: `Φ = {φ_L, φ_U}`
  (alt/üst zaman kutusu, ikisi de **alt enerji kutusu**), `V̂_k(z) = … min_a max_{φ∈Φ}
  E[V̂_{k+1}(φ(f(z,a)))]`. Güvenli küme deney 1: `S = {x : ζ_{c(x)}(t(x)) ≤ b(x)}` (haven h için
  gereken SOC serisi); deney 3: ortalama irradyans ≥ 500 W/m² olan yörünge hücresi + Ay gecesini
  ≥ 5 000 Wh ile geçebilme. Enerji: panel 1,5 m² × %30 × 1 367 W/m²; deney 3'te 60–300 W sürüş,
  40 W bekleme, 30 W hibernasyon, 50 W arıza-çözme, 30 kWh. Veri: 240 m/px, saatlik JPL görünürlük
  (%0/20/…/100), Cabeus, 1 Ağu–27 Eki 2029, 2 089 harita. Durum sayısı 2,5 M (deney 1) /
  **41,5 M** (deney 3); politika süresi ~10 s … 2 500+ s (zamanın çoğu geçiş matrislerinde);
  Monte Carlo deney 3: 100 000 arıza profili.
- **Makale 2 — arXiv 2401.08558v2** (IEEE AERO 2024, *Safe Mission-Level Path Planning …*), HTML
  okundu. Şans kısıtı **yörünge düzeyinde**: `Pr{∧ x_i ∈ X_i | x_0, π} ≥ 1 − β` (Denk. 7);
  Risk-Bounded TEMPEST geriye doğru arama, `⟨c, t, b, w⟩`; yeni açılan düğümün yürütme riski
  ileri-zaman ardıllarından hesaplanır, arıza sonucu durumlar `V_S` (kurtarma değer fonksiyonu)
  ile yapay olarak sonlandırılır; düğüm yalnız β'yı sağlıyorsa genişletilir. Amaç: ardışık
  waypoint'ler arası **süre**. α = 1/5 000 m, R = 36 000 s. ROI 1: 30 dk × 150 Wh, 1 154 561 durum,
  1 889 s; β = %2 → **%1,5** gerçekleşen (**10 000** deneme); risk-sınırlı plan **+0,5 km, +2 h**.
  LCROSS: 1 h × 250 Wh (TEMPEST) / 30 dk × 200 Wh (politika); SH kuralı: 26 Eyl 2029'a kadar
  hibernasyonla **SOC ≥ %50 (15 000 Wh)**. Enerji Tablo I/V: 110/300 W sürüş, 80/40 W bekleme,
  30 W hibernasyon, 80/50 W arıza-çözme, 7/30 kWh.
- **Kod — utiasSTARS/gplanetary-nav** (MIT, `--depth 1` klon): arazi/güneşlenme katmanları, planlama
  grafı (8-komşu), `numba_energy` parça-sabit güç serisinin zaman integrali, en kısa/en hızlı/en az
  enerji yol. **Kurtarma politikası, değer iterasyonu, arıza modeli ve konservatif eşleme bu depoda
  YOK** (`grep -ri "recovery|value iteration|poisson"` yalnız README atfı). DP formülasyonu
  makalelerden alındı; depodan yalnız enerji integrali kalıbı (parça-sabit güç → kümülatif toplam)
  benimsendi.
- **Belgedeki sayıların düzeltmeleri:** "100 000 deneme" → deney 3'ün Monte Carlo'su 100 000,
  β = %2 sonucu 10 000 deneme; "tahmin %0,4–9,8 / gerçekleşen %0,0–4,6" HTML'den doğrulanamadı
  (alıntı olarak kalır, "belgeden" etiketiyle); "sürüş 60–300 W" doğru (deney 3 dört model);
  "bekleme 40–80 W" doğru (deney 1: 80, deney 3: 40); "hibernasyon 30–40 W" doğru; "batarya
  10–30 kWh" doğru (7 kWh AERO ROI 1'de).

## Mevcut durumdan kullanılanlar (yeniden yazılmaz)

| Yetenek | Kod | Bu tasarımda rolü |
|---|---|---|
| Kaba geometri (`_coarse_geometry`: AND geçilebilirlik, blok-maks eğim, blok-merkez yükseklik) | `main.py` | DP'nin uzamsal gridi = planlayıcının gridi |
| Kapılı kenarlar (adım eğimi, yanal eğim, köşe kesme) ve vektörize kenar süresi | `safe_haven._gated_edges`, `cost_engine.edge_travel_time_s_array` | `direction_tables`: yön başına izin maskesi + saat + çekiş gücü, planlayıcının `_OFFSETS` sırasıyla |
| Enerji fiziği (`housekeeping_power_w`, `move_battery_drain_wh`, `wait_battery_drain_wh`) | `cost_engine.py` | DP geçiş drenajları; testte skaler ile bit-eşit |
| Gölge serisi (`build_shadow_series`, SPICE/statik provenance), `coarsen_grid` | `illumination_series.py`, `cost_cube.py` | Plan dilimlerinin blok ortalaması → DP kutusu maruziyeti; ufuk uzatması için kaydırılmış epokla ek seri |
| A1 haven maskesi (`safe_haven_for_grids` önbelleği, `coarsen_traversable`) | `safe_haven.py` | Güvenli kümenin haven bileşeni |
| `gated_shortest_drive` | `safe_haven.py` | DP ufkunun "toparlanma sonrası sürüş" payı |
| Etiket-koyan A* (Pareto cephesi, `_dominated/_insert_label`, `REJECTION_KEYS`, `no_path_reason_4d`) | `pathfinder_4d.py` | Yeni `surv` ekseni ve `failure_probability` reddi aynı kalıba |
| SHERPA (`Perturbations`, `sample_perturbations`, `simulate_runs`, `summarize_runs`) | `stress_test.py` | Arıza olay penceresi (Poisson, sabit rota) |
| `encode_layer_f32`, `binary_layer_headers`, `layer_stats` | `terrain.py` | `GET /api/survival` ikili biçimi `/api/safe-haven` ile aynı |
| `risk.py` sabit kalıbı (`*_MODEL_ID`, `*_VALIDITY`, `*_CLAIM`, `*_REFERENCES`) | `risk.py` | `survival.py` sabitleri aynı kalıpta |

## Sondalar (5 Eylül 2026; atılabilir betik `probe_b1.py`, sayılar buraya)

Site11, coarsen 4 (125 × 125 = 15 625 blok):

| | LPR-1 | NASA VIPER |
|---|---|---|
| Geçilebilir kaba blok | 11 402 (%73,0) | 10 314 (%66,0) |
| Otomatik dilim (`auto_slice_hours`, 20 m) | 0,0359 h (2,15 dk) | 0,1176 h |
| Gündüz rotası (358,494)→(206,426): en hızlı kapılı sürüş / hamle / varsayılan dilim / plan ufku | 2,15 h / 40 / 120 / 4,31 h | 7,23 h / 41 / 123 / 14,47 h |
| Ay gecesi (186,34)→(494,450) | 4,80 h / 116 / 270 / 9,69 h | 16,00 h / 116 / 273 / 32,11 h |
| Kısa leg (358,494)→(346,462) | 0,53 h / 8 / 43 / 1,54 h | 1,76 h / 8 / 43 / 5,06 h |
| Haven, 28 Eyl 2026 (ince hücre / kaba blok) | **0 / 0** | 1 158 (%0,58) / 19 |
| Haven, 13 Eyl 2026 | **0 / 0** | 0 / 0 |
| Haven, 30 May 2027 | **0 / 0** | 22 837 (%11,5) / **862** |

- **Bir geri DP kutusu** (NumPy, K = 20 SOC kutusu, 8 yön × 3 sonuç + bekle = 25 `take_along_axis`
  toplaması, 312 500 durum/kutu): **101 ms**; K = 40: 187 ms. Gölge serisi 100 dilim: 0,10 s.
- **Sonuç 1 — durum sayısı:** belgedeki "48 dilim × 20 SOC ≈ 15 M" 1 saatlik kutu varsayıyordu.
  Plan diliminde (0,036 h) 10 h toparlanma + ufuk ≈ 16,5 h → 460 kutu → **144 M durum (575 MB
  float32)**: API için fazla. Karar: DP kutusu = `m` × plan dilimi, `m` otomatik öyle ki durum
  sayısı ≤ **40 M** (≈ 128 kutu; gündüz rotasında m = 4 → 0,14 h; Ay gecesinde m = 6 → 0,22 h;
  VIPER gündüz m = 3 → 0,35 h) → ≈ 13–20 s/alan. Rapor `max_states` ile daha ince kutuyu ölçer.
- **Sonuç 2 — güvenli küme:** LPR-1'in üç epokta da haven'ı yok → Lamarre'nin katı kümesi LPR-1
  için boş; "leg" kümesi (hedef ∪ haven) varsayılan. VIPER 30 May 2027'de 862 kaba haven bloğu →
  katı küme orada ölçülür. α = 0 ve leg kümesiyle DP deterministiktir: `P_safe ∈ {0, 1}` ve
  planlayıcının ulaştığı her durumda 1 olmalı (test).

## Tasarım kararları

1. **Durum uzayı** `(t_kutu, satır, sütun, k)`; `k` SOC kutusu: `[k·Δ, (k+1)·Δ)`, `Δ = e_cap /
   K`, K = 20 varsayılan (istekle 8–40). Temsilci SOC = kutunun **alt kenarı** (Lamarre'nin "alt
   enerji kutusu" konservatifliği); `k' = k − ceil(D/Δ)` tam sayı kaydırma (`b_lo = kΔ` olduğundan
   `floor((kΔ − D)/Δ) = k − ceil(D/Δ)`), üst kenar `K − 1`'de kapanır (şarj tavanı).
2. **Zaman ekseni** `step = m · slice_hours`, `m = ceil(gerekli_kutu / tavan_kutu)` ≥ 1;
   `n_bins = ceil(ufuk / step)`. Her eylem ≥ 1 kutu (`d = max(1, ceil(τ/step))`); `floor(τ/step) ≥ 1`
   ise `{floor, ceil}` üzerinden min-max (her sonuç terimi kendi en kötü φ'siyle: Lamarre'nin
   ortak-φ maksimumunun üst sınırı, konservatif). Planlayıcı okuması: `t_saat / step`'in
   `floor`/`ceil` kutularından **küçük** `P_safe`, SOC'nin `floor` kutusu.
3. **DP ufku** (`survival_horizon_hours`, varsayılan otomatik): plan ufku + R + en hızlı kapılı
   sürüş saati (toparlanma sonrası hedefe dönüş payı); 168 h tavan. Ufuk ötesine düşen her
   geçiş başarısızlık (Lamarre'nin O dışı = başarısızlık kuralı; konservatif). Plan dilimleri
   dışındaki kutular için gölge serisi kaydırılmış epokla uzatılır (statik seride sabit).
4. **Eylemler:** planlayıcının `_OFFSETS` sırasıyla 8 hamle (N, S, W, E, NW, NE, SW, SE) + bekle
   (kod 8); politika `uint8`: 0–8 eylem, 254 = güvenli (soğurucu), 255 = eylem yok
   (başarısız/geçilmez). Hamle süresi/mesafesi/çekiş gücü `direction_tables`'dan (kapılar
   `_gated_edges` ile aynı; testte `gated_move_count` ulaşılabilirliğiyle tutarlılık).
5. **Geçiş enerjisi:** hamle `D = (çekiş + ev-içi(ē) − p_solar(1 − ē)) · τ`, `ē = ½(s[t, c] +
   s[t + d, c'])` (planlayıcının trapezi); bekle `D = (ev-içi(s[t, c]) − p_solar(1 − s[t, c])) ·
   step`; toparlanma beklemesi `D_rec = ∫_{t_a}^{t_a + R} (ev-içi(s) − p_solar(1 − s)) ds`, kümülatif
   maruziyet küpü `cum[t]` (kutu başına saat) doğrusal ara değerle (gplanetary-nav'ın parça-sabit
   integral kalıbı). Arıza-çözme gücü katalogda yok → ev-içi güç (bekleme ile aynı; Lamarre 50–80 W).
6. **Arıza modeli:** hamlede `p0 = e^{−αρ}`, `p1 = 1 − e^{−αρ/2}` → kaynak hücrede `(c, t + τ/2 + R,
   b − D/2 − D_rec(c))`, `p2 = e^{−αρ/2} − e^{−αρ}` → hedef hücrede `(c', t + τ + R, b − D − D_rec(c'))`;
   beklemede arıza yok. Karanlık (`s ≥ 0,5`) hücrede R > `h_max_shadow_h` ise sonuç başarısızlık.
7. **Güvensiz / güvenli:** `k` kutusunun üst kenarı ≤ rezerv (`e_cap · soc_min_pct`) → başarısız
   (V = 1, soğurucu); güvenli küme hücre başına SOC eşiği `safe_soc_min_wh` (H', W'; `inf` = asla):
   hedef bloğu → rezerv; haven bloğu → `min(e_cap, rezerv + ev-içi(1,0) · h_max_shadow_h)`
   (Lamarre'nin ζ_h(t)'sinin katalog türevi: dayanım süresince tam-gölge ev-içi gücü); `safe_set =
   "leg"` ikisini, `"haven"` yalnız haven'ı alır. Kutu alt kenarı ≥ eşik → V = 0, soğurucu.
8. **Değer iterasyonu:** `V[T] = 1_{¬S}`; `t = T−1 … 0` için `V[t] = min_a max_φ Σ_o p_o ·
   V[φ(f_o)]`, güvenli/başarısız kutular önce yazılır; NumPy vektörize (yön başına
   `take_along_axis`, `np.roll` yerine dilimleme). Çıktı `p_safe = 1 − V` (float32) ve `policy`
   (uint8). Sonsuz ufuk yerine tek geriye doğru geçiş yeter: her eylem ≥ 1 kutu ilerler.
9. **Planlayıcı (`astar_4d`)**: `survival_field=None, max_failure_probability=None` — ikisi de
   None ise **bit-eşit**. Alan verilince her etiket `surv` (yürütme hayatta-kalma çarpanı, 1'den
   başlar) taşır; hamlede `surv' = surv · (p0 + p1 · P_safe(f1) + p2 · P_safe(f2))` (AERO 2024'ün
   "arıza dallarını V_S ile sonlandır" kuralı; beklemede değişmez); baskınlıkta yüksek `surv`
   baskın (tolerans 0,001); anahtar 1 000 kutu. β verilince `1 − surv' > β` olan hamle
   `failure_probability` sayacına; başlangıçta `1 − P_safe(start) > β` ise optimal politika
   sınırıyla hemen ret (gerekçeli). Her zaman raporlanır: `path_survival_prob` (yürütme,
   durum başına), `path_recovery_prob` (durumun kendi `P_safe`'i), `metrics.execution_failure_probability`,
   `min_recovery_prob`, `start_recovery_prob`, `survival_enforced`.
10. **API (yalnızca ekleme):** `Plan4DRequest.max_failure_probability` (0 < β < 1),
    `report_survival` (bool; β verilince zaten açık), `failure_rate_per_km` (≥ 0, varsayılan
    varsayım 0,2), `recovery_hours` (> 0, ≤ 72, varsayılan 10), `survival_soc_bins` (8–40),
    `survival_safe_set` ("leg"|"haven"), `survival_horizon_hours` (≤ 168). Yanıt `survival`
    bloğu her zaman (istenmemişse `requested: false` + `reason`). `/api/cell-telemetry?survival=true&
    goal_row&goal_col&soc_pct&t_hours&failure_rate_per_km&recovery_hours&safe_set` → `survival`
    + `survival_model`. `ReplanRequest.recovery_policy` (bool) → `recovery_suggestion` (mevcut
    alanlar aynen). `GET /api/survival` (`/api/safe-haven` kalıbı; `format=f32&field=p_safe|
    best_action`). Alan önbelleği: 2 giriş (≈ 200 MB/giriş), anahtar tüm parametreler + hedef.
11. **SHERPA (B5) arıza olayı:** `Perturbations.fault_rate_per_km` (0 = yok), `fault_recovery_h`
    (10); koşu başına Poisson sayı + rota mesafesi boyunca düzgün konumlar; hamle ayağının ilk
    yarısındaki arızalar kalkıştan önce kaynak hücrede, ikinci yarısındakiler varıştan sonra hedef
    hücrede R saat bekletir (ev-içi × güç çarpanı − güneş); rota **değişmez**. Özet `faults`
    bloğu; `PerturbationOverrides` iki alan.
12. **Monte Carlo doğrulama (`survival.rollout`)**: sürekli saat (h) ve SOC (Wh); politika
    `(floor(t/step), c, floor(b/Δ))`'den okunur; isteğe bağlı plan durum listesi verilirse rover
    önce planı izler (aynı üç sonuçlu arıza örneklemesi), arıza beklemesinden sonra politikaya
    geçer; sonuç güvenli/başarısız/ufuk; Wilson %95 aralığı. Tahmin ≥ gerçekleşen denetimi
    raporda; testte deterministik (α = 0) ve küçük DP'de kapalı formla.
13. **Rapor** `scripts/recovery_policy_report.py` (`--json` önce, `--from-json`; `--n-runs`,
    `--skip-sherpa`, `--max-states`) → `docs/research/recovery_policy_report.md`: (1) formülasyon
    ve Lamarre ile fark tablosu (alıntılar); (2) Site11'de durum uzayı, süre, `P_safe` dağılımı
    (LPR-1 28 Eyl 2026 ve 13 Eyl 2026; VIPER 30 May 2027; α süpürmesi; leg/haven kümesi);
    (3) β süpürmesi {yok, 0,10, 0,05, 0,02} → hamle/süre/SOC/yürütme riski, hangi çiftte bağlayıcı;
    (4) tahmin vs gerçekleşen (rollout 1 000 koşum; SHERPA arıza olaylı 1 000 koşum);
    (5) kurtarma politikası örnekleri (Ay gecesi çiftinde bir durumdan öneri; `/api/replan`);
    (6) iddia sınırı ve sunum cümlesi.

## Bileşenler

### 1. `app/survival.py` — yeni modül

```
SURVIVAL_MODEL_ID = "reach_avoid_value_iteration_v1"; SURVIVAL_VALIDITY = "MODEL"
SAFE_SETS = ("leg", "haven"); ACTION_NAMES = ("N","S","W","E","NW","NE","SW","SE","wait")
ACTION_WAIT = 8; ACTION_SAFE = 254; ACTION_NONE = 255
DEFAULT_SOC_BINS = 20; MAX_SURVIVAL_STATES = 40_000_000; MAX_SURVIVAL_HORIZON_HOURS = 168.0
SURVIVAL_SCOPE, SURVIVAL_CLAIM, SURVIVAL_REFERENCES (iki makale + gplanetary-nav), LAMARRE_QUOTED (alıntı sözlüğü)

fault_outcome_probabilities(rate_per_km, distance_m) -> (p0, p1, p2)
haven_hibernation_soc_wh(rover) -> float
safe_soc_requirement(traversable, haven_mask|None, goal|None, rover, safe_set) -> (H, W) float64 (inf = asla)
direction_tables(traversable, elevation|None, slope|None, resolution_m, rover) -> DirectionTables
    allowed (8, H, W) bool; travel_h (8, H, W); distance_m (8,); traction_w (8, H, W)
bin_shadow_series(shadow_series [(H, W)…], slices_per_bin) -> (n_bins, H, W) blok ortalaması
auto_slices_per_bin(n_slices_needed, cells, n_soc_bins, max_states) -> int
build_survival_field(traversable, elevation, slope, resolution_m, rover, shadow_bins, step_hours,
                     slices_per_bin, safe_soc_min_wh, n_soc_bins, failure_rate_per_km, recovery_hours,
                     provenance) -> SurvivalField
SurvivalField (dataclass): p_safe (T, H, W, K) float32; policy (T, H, W, K) uint8; step_hours;
    slices_per_bin; n_bins; soc_bin_wh; e_cap_wh; reserve_wh; exposure (T, H, W); cumulative (T+1, H, W);
    rate_per_km; recovery_h; safe_soc_min_wh; tables; rover; provenance
    soc_bin(wh) -> int; bins_of_hours(h) -> (lo, hi); p_safe_at(slice, r, c, wh) -> float
    recovery_drain_wh(r, c, from_h) -> float
    move_survival_factor(slice, r, c, nr, nc, wh, travel_h, distance_m, drain_wh) -> (factor, p1, p2, ps1, ps2)
    best_action(slice, r, c, wh) -> dict(code, name, target, p_safe_now, p_safe_next)
    n_states; nbytes; info() -> dict
rollout(field, start, start_slice, battery_wh, n_runs, seed, plan_states=None, plan_legs=None) -> dict
survival_block(field|None, result|None, beta, requested, reason=None) -> dict (API bloğu)
recovery_suggestion(field, r, c, battery_wh, coarsen, slice=0) -> dict
```

### 2. `app/pathfinder_4d.py` — yalnızca ekleme

`REJECTION_KEYS += ("failure_probability",)`; `_empty` metriklerine `execution_failure_probability`,
`min_recovery_prob`, `start_recovery_prob`, `survival_enforced`, `path_survival_prob/path_recovery_prob`
(None). `_dominated/_insert_label` dördüncü eksen `surv` (+ `surv_tol`) — cephe demetleri 4'lü.
`label_of` beşinci öğe `surv_key`. `no_path_reason_4d` yeni cümle: "N moves would have pushed the
execution failure probability over β (max_failure_probability)". Alan yokken `surv = 1.0` sabit →
tüm kararlar aynı → bit-eşit.

### 3. `app/stress_test.py`

`Perturbations.fault_rate_per_km = 0.0`, `fault_recovery_h = 10.0`; `sample_perturbations` →
`fault_positions_m (n, F)` (NaN dolgu), `fault_count`; `simulate_runs` hamle ayağında iki yarı
sayımı ve beklemeler (`RunResults.fault_count`, `fault_hold_h`); `summarize_runs` → `faults` bloğu
(`rate_per_km`, `recovery_h`, `runs_with_fault`, `mean_faults`, `mean_hold_h`) + metrik dağılımı.

### 4. `app/main.py`

| Uç | Değişiklik |
|---|---|
| `POST /api/plan-4d` | İstek alanları (karar 10). Alan istenince `_survival_field_for_plan(...)` (kaba geometri, plan gölge serisi + uzatma, A1 haven maskesi blok-AND, hedef, K, α, R, ufuk) önbellekten; `astar_4d(survival_field=…, max_failure_probability=β)`; yanıt `survival` bloğu + `path_survival_prob`, `path_recovery_prob`; 404 metnine β cümlesi (ret sayısı, başlangıç `P_safe`). |
| `GET /api/cell-telemetry` | `survival=true` ve `start_utc` ile: `survival {p_safe, best_action, best_action_name, next_cell (ince piksel), p_safe_next, soc_pct, t_hours, safe_set, step_hours}`; aksi `null` + `survival_model.reason`. |
| `POST /api/replan` | `recovery_policy=true` ve `utc` ile `recovery_suggestion` (mevcut hücre, `state.actual_soc` ya da 1,0, kutu 0): eylem, hedef hücre, `P_safe` şimdi/sonra, model, iddia; yoksa `null`. |
| `GET /api/survival` | `start_utc` (zorunlu), `rover_id`, `goal_row/goal_col` (leg için zorunlu), `horizon_hours` (≤ 168, varsayılan 24), `soc_pct`, `t_hours`, `coarsen`, `failure_rate_per_km`, `recovery_hours`, `safe_set`, `soc_bins`, `format`, `field`. JSON: `survival_model`, `grid`, `fields{p_safe, best_action}` (min/maks/nodata/`binary_url`), `summary` (P_safe ≥ 0,95/0,5 blok kesri, ortalama). Kaba grid (H', W'); ikili `X-Layer-*` başlıkları `DERIVED` yerine `MODEL`. |

### 5. `app/constants.py`

`FAILURE_RATE_PER_KM_ASSUMED = 0.2`, `FAULT_RECOVERY_HOURS_ASSUMED = 10.0`, `FAILURE_MODEL_SOURCE`
(`"assumption: Lamarre, Malhotra, Kelly …"`); profillere alan **eklenmez** (kaynaksız sayı
kataloğa yazılmaz).

### 6. `app/terrain.py`

`LAYER_UNITS`/`LAYER_DESCRIPTIONS`'a `survival_probability` (fraction, MODEL) ve `best_action`
(code); `TERRAIN_LAYERS`'a **girmez** (hedefe/epoğa bağlı, `/api/survival`'dan servis edilir).

### 7. `scripts/recovery_policy_report.py` → `docs/research/recovery_policy_report.md`; README satırı
(D2'nin altı); araştırma belgesi ✅ + Yapıldı; sözleşme eki; spec/plan.

## Veri akışı

```
grids (rover) ──► _coarse_geometry (coarsen) ──► direction_tables (kapılar, τ, çekiş)
        │                                              │
        ├── build_shadow_series (plan) + uzatma ──► bin_shadow_series (m) ──► exposure, cumulative
        │                                              │
        └── safe_haven_for_grids (A1) ──► blok-AND ──► safe_soc_requirement (∪ hedef) ─┐
                                                                                        ▼
                                  build_survival_field (geri değer iterasyonu) ──► p_safe, policy
                                          │                       │                    │
                                          ▼                       ▼                    ▼
                          astar_4d(surv etiketi, β)   /api/cell-telemetry, /api/survival   /api/replan önerisi
                                          │
                                          ▼
                     survival bloğu ◄── rollout (MC) / SHERPA(arıza) ── rapor (tahmin ≥ gerçekleşen)
```

## Hata davranışı

- β istenip alan kurulamıyorsa (grid bölünemez, hedef geçilmez vb.) 422 gerekçeli; statik gölge
  serisiyle DP **koşar** ve `survival.shadow_model = static` der (uzay-zaman iddiası yapılmaz).
- Alan tavanı: `n_states > MAX_SURVIVAL_STATES` olamaz (m otomatik); `survival_horizon_hours` >
  168 → 422.
- `inf`/NaN JSON'a sızmaz; ikili katmanda geçilmez blok NaN.
- Planlayıcı `max_failure_probability` verilip alan verilmezse `_empty` hata metni.
- Rollout ve SHERPA ufku aşan koşumlar "horizon" nedeniyle başarısız sayılır (uydurma yok).

## Test stratejisi

- **Birim (`test_survival.py`, çekirdeksiz):** `fault_outcome_probabilities` (toplam 1, α = 0 →
  (1, 0, 0), Lamarre'nin 1/5 km × 320 m sayısı); `direction_tables` ↔ `_gated_edges` aynı kenar
  kümesi ve saat (rastgele grid); SOC kutu kaydırması kapalı form; 3 × 3 × 3 dilim × 3 SOC elle
  DP (kapalı form); monotonluk (daha çok SOC ⇒ `P_safe` ≥; daha çok α ⇒ ≤); güvenli hücre
  `P_safe = 1`; α = 0 ve ulaşılabilir hedefte `P_safe = 1`; min-max konservatiflik (iki eşlemenin
  küçüğü); `rollout` α = 0 deterministik = DP; küçük DP'de rollout ≈ kapalı form (Wilson);
  `recovery_suggestion`, `survival_block` şekli.
- **Planlayıcı (`test_pathfinder_4d.py`'ye ek, `test_survival.py` içinde):** alan yokken mevcut
  fixture'larla aynı `path_states/metrics` (bit-eşit); alan + β ile ret sayacı; β=None + alan →
  yalnız rapor; β ihlalinde 404 metni.
- **SHERPA:** `fault_rate_per_km = 0` → önceki sonuçlarla aynı (seed); oranla `fault_count` Poisson
  ortalaması; bekleme süresi ve drenaj.
- **API (`test_survival_api.py`, çekirdeksiz TestClient, statik gölge):** istek alanları/422'ler,
  `survival` bloğu (requested false/true), β ile 200/404, cell-telemetry `survival`, replan
  `recovery_suggestion`, `GET /api/survival` JSON + f32 başlıkları.
- **Gerçek grid (`test_survival_real_grid.py`, skip-korumalı):** standart üç 4-B rota
  `max_failure_probability=None` ile 41/116/8 hamle aynı; β = 0,05 ile `min recovery ≥ 1 − β` ve
  `execution_failure_probability ≤ β`; VIPER 30 May "haven" kümesinde `P_safe` > 0 blok var;
  2-B SHA kilitleri değişmez (mevcut testler).

## Kapsam dışı (bilinçli)

- Yörünge düzeyinde geriye doğru TEMPEST araması (waypoint dizisi, `w` ekseni): A5 (TSP görev planı)
  ile birlikte; burada β tek leg'in yürütme riskine uygulanır.
- Kesintisiz karanlık saatinin DP durumuna alınması (×K_dark durum) ve termal zarf (C6).
- Arıza-çözme gücü, SOC'ye bağlı hibernasyon güç eğrisi (C2).
- Frontend; `/api/compare`, `/api/plan-multi` (2-B planlayıcı zaman eksenine sahip değil).
- Lamarre'nin JPL 240 m/px güneşlenme haritaları (bizim SPICE serimiz kullanılır).

## Uygulama sırasında bulunanlar ve ölçümler (5 Eylül 2026)

### Tasarımdan sapmalar (nedenleriyle)

1. **Lamarre'nin "alt enerji kutusu" eşlemesi bizim rejimde kullanılamaz; SOC ekseninde kutu
   merkezleri arasında doğrusal ara değer kullanıldı.** Lamarre'de bir hamle (240 m, 0,1 m/s, 300 W)
   ≈ 200 Wh çeker ve kutu 250 Wh'tir: alt kutuya yuvarlama en çok 2× kötümserdir. LunaPath'te bir
   hamle (20 m, 0,2 m/s) karanlıkta ≈ 19 Wh çeker, kutu 271 Wh'tir (K = 20): `ceil(19/271) = 1` →
   **her karanlık hamle tam bir kutu düşürür** (≈ 14× kötümserlik). Sonda (alt-kutu eşlemesiyle,
   Site11 LPR-1 28 Eyl, 115 kutu × 0,144 h): başlangıç bloğunda **`P_safe = 0,000`**, geçilebilir
   blokların **%90,3'ü 0**, ortalama 0,094 — planlayıcının 2,98 h'te %92,5 SOC ile bulduğu rota için
   fiziksel olarak anlamsız. Karar: kutu temsilcisi merkez; geçişte varılan şarj iki merkez arasında
   doğrusal ağırlıklarla okunur (Lamarre'nin karşılaştırdığı "interpolation map"; beklenen değerde
   yansız, `test_a_chain_of_small_drains_is_unbiased_in_expectation`). Aynı ölçüm ara değerle:
   başlangıç `P_safe` **0,985** (tam SOC) / 0,964 (yarım), ortalama 0,879, blokların %52'si ≥ 0,95,
   %1,5'i 0. Konservatiflik artık yapısal değil **ampirik**: rollout ile denetlenir (rapor § 4) ve
   `SURVIVAL_CLAIM` bunu söyler. Zaman ekseninde min-max (φ_L/φ_U) korundu.
2. **Güvenli küme eşiği en üst kutunun merkezinde kapanır.** VIPER'ın hibernasyon şarjı (rezerv
   800 Wh + 130 W × 96 h = 13 280 Wh) kapasiteyi (4 000 Wh) aşar ve `e_cap`'te kapanır; hiçbir kutu
   merkezi `e_cap`'e ulaşmadığından katı haven kümesi asla güvenli olmuyordu (ilk gerçek grid koşumu:
   `safe_cells > 0`, `P_safe ≡ 0`). "Kapasiteye eşit eşik = dolu batarya" kuralı eklendi
   (`test_a_requirement_at_capacity_means_a_full_battery_is_safe`).
3. **Durum tavanı 40 M → 100 M, K varsayılanı 20 → 16, ufuk payı `2 × en hızlı sürüş`.** Her eylem
   ≥ 1 kutu sürdüğünden DP'nin saati gerçek saatten yavaştır (m kadar); Ay gecesi çiftinde (116 hamle)
   m = 6'da 25 h'lik DP-zamanı 24,5 h ufka sığmıyordu. 100 M tavanla m = 2–3 (0,072–0,108 h; hamleler
   0,036–0,07 h → ≤ 2–3× zaman kötümserliği), VIPER m = 1. Bedeli bellek/süre: LPR-1 alanları 65–68 M
   durum (311–327 MB), DP 96–136 s; VIPER 40 M, 46 s (rapor sayıları aşağıdaki tabloda).
4. **Bellek:** `_survival_model_for_grids` tüm ufuk için ince (500 × 500) gölge serisi üretiyordu
   (668 dilim × 2 MB ≈ 1,3 GB; ilk gerçek grid koşumunda süreç 1,67 GB). Uzatma 64'er dilimlik
   parçalar hâlinde üretilip hemen kabalaştırılıyor (`_SHADOW_EXTENSION_CHUNK`).
5. **DP toplama:** arıza sonuçlarının varış kutusu hücreden hücreye değiştiğinden ilk sürüm her
   benzersiz kutu için tüm gridi topluyordu (≈ 2 s/kutu); yalnız o kutuya düşen hücreler toplanınca
   ≈ 0,37 s/kutu (16 SOC kutusu, 8 yön × 3 sonuç × 2 φ + bekle).
6. **Rollout'ta planlanan bekleme bir plan dilimi**, politikanın beklemesi bir DP kutusu sürer.
7. **Eşitlikte politika hamleyi seçer** (bekleme son değerlendirilir, yalnız kesin daha iyiyse):
   kurtarma önerisi "hangi yöne" demeli.
8. `gplanetary-nav` klonunda kurtarma politikası kodu **yok**; formülasyon makalelerden.
9. `/api/replan` önerisi tetikleyici ateşlemese de döner (`recovery_policy: true` ise); D3'ün termal
   ihlali güvensiz-durum tanımına girmedi (spec'teki karar korundu).

### Ölçümler (Site11, coarsen 4; `scripts/recovery_policy_report.py`, rapor [recovery_policy_report.md](../../research/recovery_policy_report.md))


| Çift | α (1/km) | Durum | Kutu × adım (m) | DP (s) | `P_safe` ort. (tam SOC, bin 0) | ≥ 0,95 | = 0 | Başlangıç tam / yarım | Yürütme riski |
|---|---|---|---|---|---|---|---|---|---|
| LPR-1 gündüz 28 Eyl 2026 | 0 | 65,3 M | 261 × 0,072 h (2) | 44 | 0,981 | %96,5 | %1,5 | 1,000 / 0,9995 | 0 |
| | 0,2 | 65,3 M | 261 × 0,072 h (2) | 96 | 0,880 | %52,0 | %1,5 | 0,985 / 0,972 | %1,65 |
| | 0,5 | 65,3 M | 261 × 0,072 h (2) | 97 | 0,720 | %15,7 | %0,6 | 0,921 / 0,896 | %9,07 |
| LPR-1 Ay gecesi 13 Eyl 2026 | 0 | 68,5 M | 274 × 0,108 h (3) | 52 | 0,980 | %97,0 | %1,5 | 0,998 / 0,579 | 0 |
| | 0,2 | 68,5 M | 274 × 0,108 h (3) | 136 | 0,921 | %47,6 | %1,5 | 0,883 / 0,404 | %11,05 |
| | 0,5 | 68,5 M | 274 × 0,108 h (3) | 104 | 0,765 | %31,8 | %0,6 | 0,581 / 0,221 | %43,3 |
| VIPER kısa leg 30 May 2027 | 0 | 39,8 M | 159 × 0,118 h (1) | 24 | 0,724 | %60,1 | %8,7 | 1,000 / 0,789 | 0 |
| | 0,2 | 39,8 M | 159 × 0,118 h (1) | 46 | 0,647 | %35,5 | %8,7 | 1,000 / 0,761 | %0,08 |
| | 0,5 | 39,8 M | 159 × 0,118 h (1) | 46 | 0,562 | %21,5 | %0,8 | 1,000 / 0,720 | %0,43 |

- Katı (`haven`) küme: LPR-1 her epokta boş (`P_safe ≡ 0`); VIPER 30 May 2027 862 blok, 51,3 M durum,
  DP 64,7 s, ort. `P_safe` 0,725, ≥ 0,95 %44,4, ≥ 0,5 %77,0, = 0 %4,1 (24 h ufuk, tam SOC).
- **β süpürmesi (α = 0,2, R = 10 h):** gündüz β = 0,10 / 0,05 aynı 41 hamle (2,979 h, min SOC %92,5,
  0 ret), β = 0,02 aynı rota, aramada 13 811 hamle reddedildi; Ay gecesi β ∈ {0,10, 0,05, 0,02}
  **404** ("even the optimal recovery policy from there fails with probability 0.1173"); VIPER kısa
  leg her β'da aynı 8 hamle (0 ret). Lamarre'nin "+0,5 km / +2 h" sonucu Site11'de üretilmedi:
  rota ya aynı ya olanaksız (rezerv ve karanlık zaten deterministik zarfta; β yalnız arıza
  dallarını fiyatlıyor).
- **Tahmin ≥ gerçekleşen (1 000 koşum, Wilson %95):**

| Çift | Ölçüm | Tahmin | Gerçekleşen | Wilson | Sonuç |
|---|---|---|---|---|---|
| Gündüz | yalnız politika | %1,51 | %1,20 | %0,69–2,09 | konservatif |
| Gündüz | plan + politika | %1,65 | %1,00 | %0,54–1,83 | konservatif |
| Gündüz | SHERPA sabit rota, yalnız arıza (σ = 0) | %1,65 | %0,0 | — | konservatif |
| Ay gecesi | yalnız politika | %11,73 | %4,60 (38 batarya, 8 ufuk) | %3,47–6,08 | konservatif (2,5×) |
| Ay gecesi | plan + politika | %11,05 | %4,00 (27 batarya, 13 ufuk) | %2,95–5,40 | konservatif |
| Ay gecesi | SHERPA yalnız arıza (σ = 0) | %11,05 | %0,0 | — | konservatif |
| Ay gecesi | SHERPA σ + arıza / σ yalnız | — | %5,9 (59 batarya) / %1,2 | — | bilgi |
| VIPER | yalnız politika / plan + politika | %0,00 / %0,08 | %0,0 | %0–0,38 | konservatif |
| VIPER | SHERPA σ + arıza / σ yalnız / yalnız arıza | — | %1,8 / %0,4 / %0,0 | — | bilgi |

  Okuma: DP'nin kötümserliği zaman ekseninden gelir (her hamle ≥ bir kutu: Ay gecesinde 116 hamle
  × 0,108 h = 12,5 h DP-zamanı, gerçek 6,75 h; 10 h bekleme + ikinci arıza ufku aşar). Politika
  sürekli zamanda gerçek plandan **daha çok** batarya başarısızlığı üretti (Ay gecesi: 38 / 27'ye
  karşı sabit rotada 0): en yakın kutu merkezinden okunan politika rezerv yakınında 3 puanlık SOC
  farkını görmüyor. Raporda öyle yazıldı; yumuşatılmadı.
- **Kurtarma önerisi** (Ay gecesi): başlangıç → S (`P_safe` 0,883 → 0,884); rota ortası (97,57,
  dilim 105, SOC %82) → E 0,969; yarım batarya → E 0,860; 10 h arıza sonrası (SOC %70, t = 13,8 h)
  → E 0,763. VIPER kısa leg başlangıcı 30 May 2027'de **haven** (öneri "safe").
- **Süreler:** alan kurma 46–136 s (LPR-1 274 kutu ≈ 0,35–0,5 s/kutu; `/api/replan`'in 24 h'lik alanı 83,8 M durum, 118 s); gölge serisi uzatması ≤ 1 s;
  rollout 1 000 koşum 0,6–1,3 s; planlayıcı alanla: gündüz 10–11 s (alansız 7 s), Ay gecesi 43 s (alansız 22 s), VIPER kısa leg 3 s (alansız 3 s); ilk çağrı alan kurma dahil 48–145 s. Rapor toplam 49 dk (ikinci koşum, optimize planlayıcı; ilk koşum 77 dk: yalnız-rapor modunda `surv` ekseni açıkken Ay gecesi planlayıcısı 281 s / 1,2 M düğüm sürüyordu).
- **Tam paket:** 1 443 passed, 4 skipped (43 dk 1 s bu makinede; D2'nin 13 dk 49 s'sine karşı fark B1'den değil — A/B'de alansız planlayıcı eski koda karşı aynı düğüm sayısı ve ±%5 süre, `test_plan_4d_real_grid`'in 12 rastgele çifti tek başına 15,6 dk; B1'in 5 gerçek-grid testi ≈ 5 dk; skip'lerin ikisi D2'nin `LUNAPATH_PPB_DIR` klon testleri — bu koşumda ortam değişkeni yok — ikisi önceden var olan; tek uyarı önceden var olan `test_visibility_validation`'ınki; D2'deki 1 391'e +54 yeni test, −2 klon testi).
