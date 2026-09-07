# 03 — Sentetik ve Minimum Veri

> **Soru:** LunaPath'in sentetik termal/gölge verisi kabul edilebilir mi? Sentetik veri ne zaman meşru, ne zaman sahtekârlık? Projeyi taşıyacak **minimum** veri omurgası nedir?
>
> **Kısa cevap:** Sentetik veri kötü değil. **Etiketlenmemiş, doğrulanmamış ve alternatifi varken kullanılan** sentetik veri kötüdür. LunaPath'in sentetik termal gridi bugün üçüncü kategoriye giriyor: gerçek Diviner verisi ücretsiz ve indirilebilir durumdayken sentetik kullanılıyor. Çözüm sentetiği atmak değil — **gerçeği eklemek ve sentetiği baseline olarak tutmak.**

---

## 1. Sentetik verinin üç meşru kullanımı, bir gayrimeşru kullanımı

| Kullanım | Meşru mu? | LunaPath'te örnek |
|---|---|---|
| **1. Erken geliştirme / unblocking** — gerçek veri gelene kadar arayüzleri test etmek | ✅ Tamamen meşru, sektör standardı | `ay_termal_navigasyon_proje_dokumani.md` §10.3 Risk 7 bunu doğru öneriyor |
| **2. Kapsam genişletme** — gerçekte gözlenmemiş ama fiziksel olarak mümkün durumları test etmek (SEP fırtınası, ekipman arızası) | ✅ Meşru, hatta zorunlu | SEP olay senaryosu → [06](06_radyasyon_verisi.md) |
| **3. Etiketli veri üretimi** — gerçekte etiketlemenin imkânsız olduğu yerde (piksel-düzeyi ground truth) | ✅ Meşru, koşullu (sim2real kanıtı gerekir) | ViT hazard tespiti → [02](02_goruntu_isleme.md) §3.2 |
| **4. Var olan ölçümün yerine ikame** | ❌ **Gayrimeşru** — ölçüm varken model kullanmak | `thermal_grid`, `shadow_ratio` |

**LunaPath'in mevcut durumu tam olarak 4. kategoride** ve bu, referans belgesinin kendisinde de itiraf edilmiş:

> *"⚠️ Bu bir KABA PROXY'dir — elevasyon gölgenin nedeni değil sonucudur. Offline illumination fraction haritası her zaman tercih edilmelidir."* (`lunapath_referans_belgesi_2.md` §2.3.3)

> *"Bu gerçek bir termal model DEĞİLDİR. Ray-tracing veya ephemeris kullanmaz. Horizon masking yok. Zamana bağlı değişim yok."* (§3.2)

**Bu itiraflar iyi mühendisliktir.** Sorun itirafın olmaması değil, **itirafın ardından düzeltmenin yapılmamasıdır.** Hackathon'da bu kabul edilebilirdi; "gerçek hale getirme" fazında kabul edilemez.

---

## 2. Sentetik termal gridin teknik eleştirisi

`backend/app/thermal_grid.py` + `referans_belgesi_2.md` §3.2'deki algoritma:

```
T_base   = -180 + elev_norm × 260          # lineer elevasyon eşlemesi
T_aspect = cos(aspect) × (slope/25) × 40   # bakı düzeltmesi
T_shadow = clip(Δh_kuzey / (res × 0.1), 0, 1) × (-30)
T        = clip(T_base + T_aspect + T_shadow, -250, 130)
```

### 2.1 Beş yapısal problem

**(P1) Elevasyon–sıcaklık lineer eşlemesi fiziksel olarak yanlış.**
Ay'da atmosfer yoktur → **lapse rate yoktur**. Yükseklik ile sıcaklık arasında doğrudan nedensel ilişki yok. Kutupta korelasyon **dolaylıdır**: yüksek noktalar ufuk üstünde kaldığı için daha çok güneş görür. Ama bu bir *ufuk geometrisi* etkisidir, elevasyon etkisi değil. Sonuç: 40 km'lik bir pencerede en alçak nokta otomatik olarak −180 °C atanıyor; bu nokta gerçekte aydınlık bir düzlük olabilir.

**(P2) Doğrulama kriteri sirküler.**
`validate_thermal_grid` şunu kontrol ediyor: *"Elevasyon-sıcaklık korelasyonu > 0.5 beklenir"*. Ama sıcaklık **elevasyondan üretildiği** için bu korelasyon inşaat gereği ~1.0'dır. Bu bir doğrulama değil, tekrar-ölçümdür (tautology). Gerçek doğrulama, **bağımsız bir ölçümle** (Diviner) karşılaştırmadır.

**(P3) Sıcaklık aralığı kutup için yanlış.**
Kod +80 °C (353 K) tepe sıcaklığı üretiyor. Ay güney kutbunda güneş elevasyonu ~1.5°'dir; bu kadar sığ geliş açısıyla yüzey **353 K'ya çıkamaz**. Kutup aydınlık zirvelerinin tipik ölçüm bandı ~200–260 K (−73…−13 °C) mertebesindedir; 353 K ekvator öğle değeridir. Bu, `f_thermal`'in "ideal" bölge üretmesine ve termal penalty'nin **sistematik olarak iyimser** olmasına yol açar.

**(P4) Gölge proxy'si yön-kör ve tek-piksel.**
`height_diff[1:, :] = elevation[:-1, :] - elevation[1:, :]` sadece **bir kuzey komşusuna** bakıyor. Gerçek gölgeyi belirleyen şey, güneş azimutu yönünde **ufuk hattının tamamıdır** (10 km öteki bir masif gölge yapabilir). `res × 0.1` bölmesi (80 m grid'de 8 m) keyfi bir ölçek sabitidir.

**(P5) Zaman yok.**
Kutup aydınlanması **saatler mertebesinde** değişir. Statik bir snapshot, "rover 50 saat gölgede kalır" gibi bir metriği hesaplarken kendi kendisiyle çelişir: gölge süresi ancak zaman-değişken bir aydınlanma alanı varsa tanımlıdır. Şu anki `estimate_shadow_hours(elev_norm, Δt) = (1 - elev_norm) × Δt` formülü, "alçaktaysan zamanının %X'i karanlıktasın" der — ki bu ne uzamsal ne zamansal olarak fiziksel bir ifadedir.

### 2.2 Buna karşılık: sentetik gridin ne işe yaradığı

Adil olalım — sentetik grid iki gerçek iş yapıyor:

1. **Pipeline'ı uçtan uca çalışır hale getirdi.** Bu, mühendislik olarak doğru sıralamadır (önce çalışan sistem, sonra doğru veri).
2. **Uzamsal yapı üretiyor.** Rota planlayıcının "farklı maliyet bölgeleri arasında seçim yapması" davranışını test etmek için yeterli. Yani **algoritma testi için geçerli, sonuç iddiası için geçersiz.**

**Bu ayrımı belgeleyin:** sentetik grid bir *fixture*'dır, bir *ürün* değildir.

---

## 3. Minimum veri omurgası — yeniden tanımlanmış

`ay_termal_navigasyon_proje_dokumani.md` §14 beş katmanlı bir omurga öneriyor: sıcaklık, DEM, slope, shadow/illumination, PSR maskesi. **Bu liste doğru ama eksik ve önem sıralaması yok.** Aşağıdaki tablo, her katman için "olmazsa ne kırılır" analizidir:

| Katman | Zorunluluk | Yoksa ne olur | Gerçek kaynak | Sentetik kabul edilebilir mi? |
|---|---|---|---|---|
| **Elevation (DEM)** | 🔴 **Kritik** | Hiçbir şey çalışmaz | LOLA LDEM | ❌ Asla — mevcut ve ücretsiz |
| **Slope** | 🔴 **Kritik** | Hard-constraint yok | DEM'den türetilir (ölçek beyanı ile) | 🟡 Türetilmiş, sentetik değil |
| **Illumination fraction** | 🔴 **Kritik** | Gölge/enerji modelinin temeli yok | LOLA illumination (60/120/240 m) | ❌ Ürün var |
| **Yüzey sıcaklığı** | 🔴 **Kritik** | Projenin ana iddiası dayanaksız | Diviner tbol | ❌ Ürün var |
| **PSR maskesi** | 🟠 Yüksek | Kalıcı gölge/kriyojenik bölge ayrımı yok | LOLA PSR 20 m | ❌ Ürün var |
| **Roughness** | 🟠 Yüksek | Pürüzlülük penalty'si yok | SfS SDEM roughness | 🟡 Geçici olarak DEM varyansından |
| **Rock abundance** | 🟡 Orta | Kaya tehlikesi görünmez | Diviner rock abundance / NAC DL | 🟡 Kabul edilebilir |
| **Thermal inertia (H-param)** | 🟡 Orta | Soğuma/ısınma dinamiği kaba | Diviner türev ürünleri | ✅ Sabit varsayım kabul edilebilir |
| **Radyasyon** | 🟡 Orta | Donanım sağlığı modeli eksik | CRaTER/LND'den skaler | ✅ **Sentetik/skaler tamamen meşru** → [06](06_radyasyon_verisi.md) |
| **Rover parametreleri** | 🔴 Kritik | Model kalibre edilemez | Gerçek rover verisi gizli/yok | ✅ **Sentetik zorunlu** (LPR-1 doğru yaklaşım) |
| **Zaman-değişken aydınlanma** | 🟠 Yüksek | Gölge süresi tanımsız | Ephemeris + ufuk hesabı | 🟡 Basitleştirilmiş ephemeris kabul edilebilir |
| **Dünya görünürlüğü** | 🟢 Bonus | İletişim kısıtı yok | LOLA Earth-illumination | ❌ Ürün var |

### 3.1 "Sentetik meşruiyet testi" — 4 soru

Bir katmanı sentetik üretmeye karar vermeden önce:

1. **Gerçek ürün var mı ve erişilebilir mi?** Varsa → sentetik gayrimeşru. (Termal ve illumination burada takılıyor.)
2. **Sentetik model, fiziksel bir mekanizmadan mı türüyor, korelasyondan mı?** Mekanizmadan türüyorsa savunulabilir (ör. LPR-1 termal denge modeli). Korelasyondan türüyorsa değil (ör. elevasyon→sıcaklık).
3. **Sentetiğin hatası nicelenebilir mi?** En az bir gerçek ölçümle karşılaştırılabiliyor mu? Karşılaştırılamıyorsa, sonucun üzerine bina kurulamaz.
4. **Sonuçtaki hassasiyet ölçüldü mü?** Sentetik parametreyi ±%50 oynatınca rota değişiyor mu? Değişiyorsa sonuç sentetiğe bağımlıdır ve bu rapor edilmelidir.

LPR-1 rover parametreleri bu testi **geçiyor** (1: gerçek rover verisi kamuya kapalı; 2: VIPER/MoonRanger'dan mekanizma temelli türetme; 3: literatür bandıyla karşılaştırılabilir; 4: hassasiyet analizi yapılabilir). Termal grid **1 ve 2'de kalıyor.**

---

## 4. Sentetik veriyi savunulabilir yapan protokol

### 4.1 Zorunlu etiketleme

Her sentetik ürün üç alanla birlikte gelmeli:

```json
{
  "layer": "thermal",
  "physical_validity": "MODEL",
  "model": {
    "id": "SYNTH-THERM-v1",
    "mechanism": "elevation-aspect proxy (NOT a radiative balance model)",
    "inputs": ["elevation", "slope", "aspect"],
    "free_parameters": {
      "T_min_base_C": -180.0, "T_max_base_C": 80.0,
      "aspect_delta_max_C": 40.0, "shadow_penalty_C": -30.0
    },
    "known_limitations": [
      "no ray-tracing / horizon masking",
      "no time dependence",
      "artificial monotone correlation with elevation (r ~ 1.0)",
      "peak temperature (+80 C) unphysical for 1.5 deg solar elevation"
    ],
    "validated_against": null,
    "intended_use": "algorithm fixture only; NOT for mission conclusions"
  }
}
```

`validated_against: null` alanı boş kaldığı sürece, o katmandan üretilen hiçbir sayı "sonuç" olarak sunulmamalı. Bu alan dolduğunda (`"LRO/Diviner tbol, RMSE = X K, bias = Y K"`) katman terfi eder.

### 4.2 Ablasyon protokolü (en önemli tek öneri)

Sentetiği atmayın — **karşılaştırma kolu (control arm)** olarak tutun. Bu, projeyi savunulabilir kılan asıl mekanizmadır:

| Kol | Termal katman | Gölge katmanı | Amaç |
|---|---|---|---|
| **A (baseline)** | Sentetik v1 | Elevasyon proxy | Mevcut sistem |
| **B** | **Diviner tbol** | Elevasyon proxy | Termalin tek başına etkisi |
| **C** | Sentetik v1 | **LOLA illumination** | Gölgenin tek başına etkisi |
| **D (hedef)** | **Diviner tbol** | **LOLA illumination** | Gerçek sistem |

Her kol için aynı start/goal ile 4 misyon profili koştur ve raporla:

- Rota **geometrik** farkı: Fréchet mesafesi veya ortalama sapma (m)
- Metrik farkı: toplam mesafe, enerji, max eğim, gölge süresi, max termal risk
- **Karar farkı:** A ile D aynı hücreleri mi geçiyor? Kaç hücrede ayrılıyor?
- **Yanlış güven ölçümü:** A'nın "güvenli" dediği ama D'nin "tehlikeli" dediği hücre sayısı → **bu sayı, sentetik modelin operasyonel riskidir.**

> **Sunum cümlesi:** *"Sentetik termal modelimiz, gerçek Diviner verisiyle karşılaştırıldığında rotanın %N'inde farklı karar üretiyor ve M hücreyi yanlışlıkla güvenli işaretliyor. Bu yüzden gerçek veriye geçtik."* — Bu cümle, sentetikle kalıp hiç ölçmemekten kat kat güçlüdür.

### 4.3 Hassasiyet analizi (sentetiği tutmanız gerekiyorsa)

Sentetik parametreleri Monte Carlo ile örnekleyin:

```python
# backend/test_thermal_sensitivity.py (yeni)
import itertools, numpy as np

PARAM_GRID = {
    "T_min_base_C": [-220, -180, -140],
    "T_max_base_C": [40, 80, 120],
    "aspect_delta_max_C": [20, 40, 60],
    "shadow_penalty_C": [-15, -30, -45],
}

def test_route_stability_under_synthetic_params(grids, start, goal):
    routes = []
    for combo in itertools.product(*PARAM_GRID.values()):
        params = dict(zip(PARAM_GRID, combo))
        g = regenerate_thermal(grids, **params)
        routes.append(astar(g, start, goal, WEIGHTS_BALANCED))
    # Rapor: rotalarin kac tanesi ayni? ortalama sapma? metrik dagilimi?
    assert route_dispersion(routes) < TOLERANCE, (
        "Rota, sentetik parametrelere asiri duyarli -> sonuc raporlanamaz")
```

81 kombinasyonun tümü aynı rotayı veriyorsa, "sonucumuz sentetik parametre seçimine duyarsız" diyebilirsiniz — bu güçlü bir savunmadır. Rotalar dağılıyorsa, **bunu rapor edin ve gerçek veriye geçin.** İkisi de savunulabilir; ölçmemek savunulamaz.

---

## 5. Sim2real: sentetik görüntü/dinamik ile eğitim

ML bileşeni eklerseniz (görüntü tabanlı hazard tespiti, öğrenilen traversability, RL kontrol) sentetik veri kaçınılmaz olur. Sektörün öğrendiği dersler:

### 5.1 Domain randomization

Tek bir simüle ortamda eğitmek yerine, her episode başında simülasyon parametrelerini rastgeleleştirmek modelin genelleşmesini artırır. Ay bağlamında randomize edilen tipik parametreler:

- **Çevresel:** yerçekimi vektörü, güneş azimut/elevasyon, albedo, toz yoğunluğu
- **Yüzey mekaniği:** granüler medya parametreleri (sürtünme, kohezyon, batma), tekerlek-toprak etkileşimi
- **Platform:** rover base frame'inde küçük ofsetler, sensör montaj hatası, kamera intrinsics
- **Sensör:** shot/read gürültüsü, motion blur, pozlama, ölü piksel

**Sim2Dust** ([arXiv 2508.11503](https://arxiv.org/html/2508.11503)) tam olarak bunu yapıyor: prosedürel arazi üretimi + geniş domain randomization ile masif paralel simülasyonda RL eğitip, politikayı **zero-shot** olarak fiziksel bir tekerlekli rover'a ve Ay-analog tesisine aktarıyor. Öne çıkardığı zorluk: **tekerleğin granüler medyayla etkileşiminin karmaşık dinamiği** — sim2real boşluğunun asıl kaynağı burada.

### 5.2 "Ne kadar sentetik veri yeter?" sorusunun dürüst cevabı

Literatürde **tek bir oran yok** ve olması da beklenmez; oran göreve, mimariye ve domain gap'in büyüklüğüne bağlıdır. Ancak sağlam pratikler var:

1. **Sentetik ön-eğitim + küçük gerçek fine-tune** genellikle en iyi getiri/maliyet oranını verir. Prithvi-EO-2.0 gibi ön-eğitimli modellerde de aynı desen: ön-eğitimli başlatma rastgele başlatmadan **daha hızlı yakınsıyor** ve birçok görevde SOTA'yı geçiyor.
2. **Gerçek veri "test seti" olarak kutsaldır.** Sentetikte eğitin, **gerçekte ölçün**. Gerçek veriyi eğitime karıştırıp sonra aynı dağılımda test etmek, sim2real boşluğunu ölçmez.
3. **Ölçüt sayı değil, eğridir:** gerçek veri miktarını 0, 1, 5, 10, 25, 50, 100 örnek olarak artırıp performans eğrisi çizin. Doygunluk noktası, ihtiyacınız olan gerçek veri miktarıdır.
4. POLAR + POLAR-Sim ikilisi bu ölçümü **hazır** sunuyor: aynı 13 sahnenin gerçek HDR stereo görüntüleri, digital twin mesh'leri ve **her ikisi için ortak 23.000 etiket** ([02](02_goruntu_isleme.md) §3.3).

### 5.3 ECSS ne diyor?

**ECSS-E-HB-40-02A** (Space engineering — Machine learning qualification handbook, 15 Kasım 2024) sentetik veriyi yasaklamıyor. İstediği şeyler:

- AI'ın bu uygulama için **uygun olup olmadığının** önce değerlendirilmesi
- Verinin ilgili parametrelere göre **seçilmesi ve nitelendirilmesi** (data qualification)
- Eğitim sonrası **doğrulama ve geçerleme** (V&V) ile operasyonel hazırlığın kanıtlanması
- AI bileşeninin izole değil, **sistem mühendisliği bağlamında** ele alınması
- **"Safety cage architecture"** — AI çıktısının etrafına deterministik güvenlik kısıtları koymak
- Şu an **kritiklik kategorileri B, C, D** kapsanıyor (en kritik A değil)

> **LunaPath için doğrudan sonuç:** Mevcut mimari (hard constraint `θ > 25° → INF` + log-barrier) tam olarak bir safety cage'dir. ML eklerseniz, ML **cage'in içine** girer, cage'in yerine geçmez. Bunu bu terminolojiyle anlatmak, projeyi ECSS diline bağlar ve olgunluk algısını yükseltir.

---

## 6. Boşluk analizi

| # | Boşluk | Etki | Efor | Öncelik |
|---|---|---|---|---|
| S1 | Sentetik termal, ölçüm varken ikame olarak kullanılıyor | 🔴 Çok yüksek | Orta | **P0** |
| S2 | Sentetik gölge proxy'si, ölçüm varken kullanılıyor | 🔴 Yüksek | Düşük | **P0** |
| S3 | Doğrulama sirküler (elevasyon-sıcaklık korelasyonu) | 🔴 Yüksek | Çok düşük | **P0** |
| S4 | Sentetik katmanlar makine-okunabilir şekilde etiketli değil | 🟠 Yüksek | Düşük | **P0** |
| S5 | Ablasyon (A/B/C/D) yok → sentetiğin etkisi bilinmiyor | 🟠 Yüksek | Orta | **P1** |
| S6 | Hassasiyet analizi yok | 🟠 Orta | Düşük | P1 |
| S7 | +80 °C tepe sıcaklık kutup için fiziksel değil | 🟠 Orta | Çok düşük | P1 |
| S8 | Zaman ekseni yok (gölge süresi tanımsız) | 🟠 Yüksek | Yüksek | P1/P2 |
| S9 | ML eklenirse sim2real ölçüm planı yok | 🟡 Şartlı | Orta | P2 |

---

## 7. Yol haritası

### P0 — "sentetiği dürüstçe etiketle" (yarım gün, kod değişmez)
1. `metadata.json`'a `physical_validity` + `model` bloğu (§4.1)
2. `validate_thermal_grid`'deki sirküler korelasyon kontrolünü kaldır veya "SANITY (not validation)" olarak yeniden adlandır
3. Frontend'de sentetik katmanlara **"SENTETİK — ölçüm değil"** badge'i
4. `T_max_base` değerini kutup için gerçekçi banda çek (~260 K / −13 °C) ve gerekçesini yaz

### P1 — "gerçeği ekle, sentetiği kontrol kolu yap" (3–5 gün)
5. Diviner tbol + LOLA illumination indir/hizala → [01](01_sektorel_veri_kaynaklari.md) §5, [07](07_termal_veri.md)
6. **A/B/C/D ablasyon koşusu** (§4.2) → `docs/research/ablation_report.md` üret
7. Hassasiyet testi (§4.3) CI'ya ekle
8. `validated_against` alanını doldur: sentetik vs Diviner RMSE / bias / korelasyon

**Kabul kriteri:** `docs/` altında şu tablo mevcut:

| Kol | Rota uzunluğu (m) | Enerji (Wh) | Max termal risk | D'den sapma (m) | Yanlış-güvenli hücre |
|---|---|---|---|---|---|
| A | … | … | … | … | … |
| B | … | … | … | … | … |
| C | … | … | … | … | … |
| D | … | … | … | 0 | 0 |

### P2 — zaman ekseni ve ML (kapsam kararı gerektirir)
9. Basitleştirilmiş ephemeris + ufuk maskesi ile zaman-değişken aydınlanma (bkz. [07](07_termal_veri.md) §4)
10. ML eklenirse: ECSS safety cage çerçevesi + POLAR/POLAR-Sim ile sim2real eğrisi

---

## 8. Kırmızı çizgiler (asla yapma)

- ❌ Sentetik veriden üretilmiş bir sayıyı, kaynağını belirtmeden metrik olarak sunmak
- ❌ Sentetik veriyi kendisinden türeyen bir istatistikle "doğrulamak"
- ❌ Gerçek ürün mevcut ve erişilebilirken sentetik kullanıp bunu "veri yoktu" diye açıklamak
- ❌ Sentetik eğitim + sentetik test yapıp "%X doğruluk" iddia etmek
- ❌ Sentetik parametreleri sonuç iyi görünsün diye ayarlamak (`referans_belgesi_2.md` §11 buna davet ediyor: *"Termal grid'de tüm değerler çok soğuk → T_min_base ve T_max_base'i ayarla"* — bu, veriyi sonuca uydurmaktır ve **açıkça reddedilmeli**)

> Son madde ciddi bir problemdir ve mevcut belgede yazılı. Sorun giderme tablosundaki bu satır, "beklenen çıktıya göre girdiyi ayarla" demektir; bu, bilimsel geçerliliği ortadan kaldırır. **Düzeltme:** sıcaklıklar çok soğuk çıkıyorsa doğru aksiyon parametre ayarı değil, **gerçek veriye geçmektir.**

---

## Kaynaklar

- [ECSS-E-HB-40-02A — Space engineering: Machine learning qualification handbook (15 Kasım 2024)](https://ecss.nl/wp-content/uploads/2024/12/ECSS-E-HB-40-02A(15November2024).pdf)
- [ESA AI STAR — ECSS ML Qualification Handbook'a giriş](https://www.aistar.esa.int/advancing-the-european-space-industry-with-ai-introduction-to-the-ecss-e-hb-40-02a-machine-learning-qualification-handbook)
- [Sim2Dust: Mastering Dynamic Waypoint Tracking on Granular Media (arXiv 2508.11503)](https://arxiv.org/html/2508.11503)
- [Benchmarking Domain Randomisation for Visual Sim-to-Real Transfer (arXiv 2011.07112)](https://arxiv.org/pdf/2011.07112)
- [A Survey of Sim-to-Real Methods in RL (arXiv 2502.13187)](https://arxiv.org/pdf/2502.13187)
- [The Reality Gap in Robotics: Challenges, Solutions, and Best Practices (Annual Reviews)](https://www.annualreviews.org/content/journals/10.1146/annurev-control-031924-100130)
- [POLAR-Sim (arXiv 2309.12397)](https://arxiv.org/abs/2309.12397) · [NASA POLAR Stereo Dataset](https://ti.arc.nasa.gov/dataset/IRG_PolarDB/)
- [Image-Based Lunar Hazard Detection via Vision Transformers (Sensors 2023)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10535458/)
- [NASA Prithvi: first AI geospatial foundation model in orbit](https://science.nasa.gov/science-research/ai-foundation-model-in-orbit/)
- [Hayne et al. (2017), Global regolith thermophysical properties of the Moon from Diviner, JGR Planets](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/2017JE005387)
