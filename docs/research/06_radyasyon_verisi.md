# 06 — Radyasyon Verisi

> **Soru:** LunaPath'in "donanım sağlığı" iddiası varken radyasyon neden hiç yok? Hangi veri mevcut, rota planlamaya nasıl girer?
>
> **Kısa cevap:** LunaPath, `health_score` ve `thermal_stress` modelliyor ama **radyasyonu tamamen atlıyor** — oysa Ay yüzeyinde donanımı bozan iki mekanizmanın biri termal, diğeri radyasyondur. İyi haber: radyasyon katmanı, termal katmandan **çok daha kolay** eklenir. Çünkü uzamsal olarak neredeyse düzgündür (rota seçimini az etkiler) ama **zamansal olarak patlayıcıdır** (SEP olayları) — yani "haritaya bir katman" değil, "senaryoya bir olay" olarak girer. Bu, düşük efor–yüksek getiri bir eklemedir.

---

## 1. Ay yüzeyi radyasyon ortamı — üç bileşen

| Bileşen | Nedir | Zaman davranışı | Uzamsal davranış |
|---|---|---|---|
| **GCR (Galaktik Kozmik Işın)** | Süpernovalardan gelen yüksek enerjili yüklü parçacıklar (çoğunlukla proton, ağır iyonlar) | Sürekli; 11 yıllık güneş çevrimiyle **ters** korelasyon (güneş minimumunda en yüksek) | Neredeyse izotropik; sadece **gökyüzü görüş açısı** (sky view factor) ile değişir |
| **SEP (Güneş Enerjik Parçacıkları)** | Güneş patlaması/CME kaynaklı ani proton akısı | **Kesikli, patlayıcı**: saatler–günler; büyüklüğü 10⁴× değişebilir | Güneş yönü + manyetik bağlantıya bağlı |
| **Albedo nötron / gama** | Kozmik ışınların regolitle etkileşiminden ikincil parçacıklar | GCR'yi takip eder | **Yüzeye yakın maksimum**; regolit derinliğiyle azalır |

### 1.1 Ölçülmüş değerler (gerçek veriye dayanan sayılar)

**Chang'E-4 / LND (Lunar Lander Neutron & Dosimetry)** — Ay yüzeyinde ilk doğrudan doz ölçümü (Zhang vd., *Science Advances*, 2020):

| Büyüklük | Değer | Not |
|---|---|---|
| Silikonda soğurulan doz hızı | **~13.2 µGy/h** (kaynaklar ~13–14 µGy/h bandı verir) | Mühendislik için doğrudan kullanılabilir |
| Doz eşdeğeri hızı (biyolojik) | **~60 µSv/h** | İnsan için; elektronik için **kullanılmaz** |
| GCR katkısı | **~%75** | Geri kalanı ikincil/nötr parçacıklar |
| Nötr parçacık katkısı (nötron+gama) | Güneş minimumu civarında **%23 ± 17** | Yerel regolit etkileşiminden |
| Enstrüman | 10 çift-segmentli silikon SSD yığını | Toplam doz D detektöründe, nötr parçacık C detektörünün iç segmentinde |

**LRO / CRaTER** — yörüngeden sürekli izleme (2009–):

| Büyüklük | Değer |
|---|---|
| 50 km yörüngede ölçülen doz | **~0.22–0.27 mGy/gün** |
| Enstrüman | 3 çift ince (140 µm) / kalın (1000 µm) silikon detektör (D1–D6), aralarında doku-eşdeğeri plastik (TEP) absorber |
| Değer | 15+ yıllık zaman serisi → **güneş çevrimi ve SEP olay kataloğu** |

### 1.2 Mühendislik çıkarımı — ve bu bilgi neden LunaPath'i güçlendirir

Yıllık toplam iyonlaştırıcı doz (TID) hesabı:

```
13.2 µGy/h × 8766 h/yıl = 1.157e-1 Gy/yıl
1 Gy = 100 rad         →  ≈ 11.6 rad(Si)/yıl
```

Karşılaştırma: CRaTER'ın 50 km yörüngede ölçtüğü 0.22–0.27 mGy/gün de yıllık **~8–10 rad(Si)** verir — aynı mertebe, tutarlı.

Tipik radyasyon-sertleştirilmiş bir bileşenin TID toleransı **100 krad(Si) = 1000 Gy** mertebesindedir. Yani:

> **GCR kaynaklı TID, yüzey misyonları için sınırlayıcı faktör DEĞİLDİR.** 100 krad'lık bir parçanın GCR ile doyması binlerce yıl alır.

**Sınırlayıcı olan iki şey:**

1. **SEE (Single Event Effects)** — tek bir ağır iyon veya yüksek enerjili protonun anlık etkisi: SEU (bit flip), SEL (latch-up, kalıcı hasar riski), SET, SEFI (fonksiyonel kesinti). Bunlar doza değil, **akı ve LET spektrumuna** bağlıdır.
2. **SEP olayları** — birkaç saat içinde yılların dozunu verebilir ve akıyı **10.000 kata kadar** yükseltebilir. Bu, elektroniği anlık olarak devre dışı bırakabilir ve insanlı misyonlarda hayati risktir.

**LunaPath için bu, tam olarak kullanılabilir bir tasarım kararına dönüşür:**

| Modelleme yaklaşımı | Doğru mu? | Neden |
|---|---|---|
| Radyasyonu **uzamsal maliyet katmanı** yapmak (her hücreye farklı radyasyon maliyeti) | ❌ Büyük ölçüde **yanlış** | GCR neredeyse izotropiktir; 40 km'lik bir pencerede hücreler arası fark ihmal edilebilir |
| Radyasyonu **gökyüzü görüş faktörü** ile modüle etmek | ✅ **Kısmen doğru ve zarif** | Derin krater tabanı gökyüzünün yarısını görür → GCR dozu ~%40–50 azalır. Bu **gerçek, ölçülebilir, uzamsal** bir etkidir |
| Radyasyonu **zamansal olay** olarak modellemek (SEP senaryosu) | ✅ **Tamamen doğru** | Fiziğin gerçek yapısı budur |
| TID'i birikimli sağlık kaybı olarak modellemek | 🟡 Doğru ama etkisiz | Kısa misyonda anlamsız; uzun misyonda (yıllar) anlamlı |

> **Bu, LunaPath'e eklenebilecek en ilginç fikirdir:** *PSR'lar termal olarak ölümcül ama radyasyon açısından koruyucudur.* Derin bir krater tabanı, gökyüzünün büyük kısmını topografyayla kapatır → GCR dozunu düşürür. Yani **termal risk ile radyasyon riski ters yönde çalışır.** Bu, çok kriterli optimizasyonda gerçek bir trade-off'tur ve LunaPath'in maliyet fonksiyonunu felsefi olarak zenginleştirir: *sıcak kal ama ışınlan, ya da soğu ama korun.*

---

## 2. Gökyüzü görüş faktörü — DEM'den hesaplanabilir bir radyasyon katmanı

Bu, LunaPath'in mevcut veri setiyle (sadece DEM ile!) üretebileceği **gerçek fizikli, bağımsız** bir katmandır. Yeni veri indirmeye gerek yok.

```python
# lunapath/src/sky_view.py (yeni)
import numpy as np

def sky_view_factor(elev, res_m, n_azimuth=36, max_range_m=20_000):
    """Gokyuzu gorus faktoru (SVF) [0,1].
    1.0 = tam acik gokyuzu (duz ova), 0.5 = gokyuzunun yarisi kapali.

    Yontem: her azimutta ufuk yukseklik acisi theta_h bulunur;
    SVF = (1/N) * sum(cos^2(theta_h))   [izotropik akiya gore
    kati aci integrali, duz yuzey icin turetilen standart form]

    Not: ayni ray-marching altyapisi illumination hesabiyla
    paylasilir -> bir kez yaz, iki katman uret.
    """
    svf = np.zeros_like(elev, dtype=np.float32)
    for az in np.linspace(0, 360, n_azimuth, endpoint=False):
        theta_h = horizon_elevation(elev, res_m, az, max_range_m)  # derece
        svf += np.cos(np.radians(theta_h)) ** 2
    return svf / n_azimuth


def gcr_dose_rate_grid(svf, base_rate_uGy_h=13.2):
    """SVF ile modulasyon. Yaklasim:
    GCR primer akisi ~ SVF ile olcekli; albedo notron katkisi
    ters yonde artar (regolit gorunumu artinca) -> ilk mertebede
    ihmal edilip belirsizlik olarak raporlanmali."""
    return base_rate_uGy_h * svf
```

**Doğrulama tablosu (beklenen değerler):**

| Topografya | SVF | Doz hızı (µGy/h) | Yorum |
|---|---|---|---|
| Düz ova | ~1.00 | 13.2 | Referans |
| Sığ krater tabanı | ~0.85 | 11.2 | %15 koruma |
| Derin krater tabanı (Shackleton benzeri) | ~0.55–0.70 | 7.3–9.2 | **%30–45 koruma** |
| Dik yamacın dibi | ~0.60 | 7.9 | |
| Tepe zirvesi | ~1.00 | 13.2 | Maksimum maruziyet |

**Dürüstlük notu (belgeye yazın):** SVF-tabanlı modülasyon **birinci mertebe bir yaklaşımdır**. Gerçek transport hesabı (GEANT4/PHITS/HZETRN ile Monte Carlo) yapılmadan mutlak doz iddiası edilemez. Ancak **göreli** karşılaştırma (krater tabanı vs zirve) fiziksel olarak sağlamdır ve rota kararında kullanılabilir. Bu, [03](03_sentetik_minimum_veri.md) §3.1'deki "mekanizmadan türeyen model" testini **geçer** — çünkü katı açı geometrisinden türer, korelasyondan değil.

### 2.1 Regolit kalkanı (bonus, ucuz)

Regolit iyi bir kalkandır. Rover bir çıkıntının altına park ederse veya rejolitle kaplanmış bir barınağa girerse doz düşer. LunaPath'e bunu **safe haven özniteliği** olarak ekleyebilirsiniz:

```python
class SafeHaven(BaseModel):
    position: tuple[int, int]
    illumination_fraction: float     # sarj icin
    sky_view_factor: float           # radyasyon korumasi icin
    thermal_regime_K: float          # termal denge sicakligi
    reachability_h: float            # oraya ulasma suresi
    shelter_quality: Literal["open", "partial", "sheltered"]
```

SEP alarmı geldiğinde planlayıcı, **sadece en yakın** safe haven'a değil, **en iyi kalkanlı** safe haven'a yönelir. Bu, tek bir ek alanla üretilen anlamlı bir karar davranışıdır.

---

## 3. SEP olay senaryosu — LunaPath'e en doğru radyasyon eklemesi

### 3.1 Neden senaryo, neden katman değil

SEP olayı bir **zamansal olaydır**: dakikalar içinde başlar, saatler–günler sürer, akı büyüklüğü olağan seviyenin binlerce katına çıkabilir. Bir haritaya çizilemez; bir **senaryo tetikleyicisi** olarak modellenir.

LunaPath'in senaryo sistemi (`scenarios.py`, `MISSION_PROFILES`) bunun için **hazır bir altyapıdır.** Yeni bir olay tipi ekleyin:

```json
{
  "scenario_id": "south_pole_nobile_sep_event",
  "dem_file": "LDEM_80S_80MPP_ADJ.tiff",
  "events": [
    {
      "type": "SEP_ONSET",
      "t_offset_h": 6.5,
      "severity": "major",
      "flux_multiplier": 2000,
      "expected_duration_h": 18,
      "warning_lead_time_min": 30,
      "required_action": "SEEK_SHELTER"
    }
  ],
  "expected_outcomes": {
    "baseline": "SEP'i yok sayan plan gorevi tamamlar ama 18 saat maruz kalir",
    "sep_aware": "Plan T+6.0'da kalkanli safe haven'a saparak beklemeye gecer"
  }
}
```

### 3.2 Karar mantığı

```python
# backend/app/radiation.py (yeni)
SEP_ALERT_ACTIONS = {
    "minor":    {"action": "CONTINUE",       "note": "izle, plan degismez"},
    "moderate": {"action": "PREFER_SHELTER", "note": "rota kalkanli hucreleri tercih etsin"},
    "major":    {"action": "SEEK_SHELTER",   "note": "en iyi SVF'li erisilebilir haven'a git"},
    "extreme":  {"action": "SAFE_MODE",      "note": "dur, hibernate, telemetri minimum"},
}

def sep_response_plan(current_pos, havens, lead_time_min, severity, rover):
    """SEP uyarisi geldiginde: lead_time icinde ulasilabilir haven'lar
    arasindan en iyi kalkanliyi sec. Ulasilamiyorsa yerinde
    en iyi SVF'li hucreye kisa sapma yap."""
    reachable = [h for h in havens
                 if h.reachability_h * 60 <= lead_time_min]
    if not reachable:
        return local_best_shielding(current_pos, radius_m=200)
    return min(reachable, key=lambda h: h.sky_view_factor)  # kucuk SVF = iyi kalkan
```

**`warning_lead_time_min` gerçekçi mi?** SEP olayları için uyarı süresi olayın hızına bağlıdır; ilk gelen relativistik parçacıklar dakikalar içinde ulaşır, ana akı ise onlarca dakika–saatler alır. `30 dk` savunulabilir bir mühendislik varsayımıdır ama **varsayım olarak etiketlenmeli** ve hassasiyet analizi yapılmalı (`lead_time ∈ {10, 30, 60, 120}` dk için sonuç nasıl değişir?).

### 3.3 Bu eklemenin demo değeri

Bu, **anlatısı en güçlü** senaryodur:

> *"Rover Nobile krater kenarında ilerliyor. T+6.5 saatte güneşte bir patlama oluyor; radyasyon akısı 2000 katına çıkacak ve 30 dakika uyarı süremiz var. SEP-farkında planlayıcı, 12 dakika içinde erişilebilir 3 barınaktan gökyüzü görüş faktörü en düşük olanı (SVF 0.58, %42 kalkan) seçiyor ve rotayı 340 m saptırıyor. Bu sapma 90 Wh ve 2.4 saat gölge süresine mal oluyor. SEP-kör planlayıcı ise açık arazide 18 saat boyunca tam akıya maruz kalıyor."*

Bu tek senaryo, LunaPath'in dört ayrı iddiasını aynı anda kanıtlar: çok kriterli optimizasyon, dinamik replanning, safe haven mantığı ve donanım sağlığı farkındalığı.

---

## 4. Veri kaynakları ve modeller

### 4.1 Ölçüm verisi

| Kaynak | İçerik | Erişim | LunaPath'te kullanım |
|---|---|---|---|
| **LRO/CRaTER** | 15+ yıl doz + LET spektrumu, SEP olay kataloğu | PDS ([context](https://arcnav.psi.edu/urn:nasa:pds:context:instrument:crat.lro)), [LRO Data Products](https://science.nasa.gov/mission/lro/data-products/) | Baz doz hızı, güneş çevrimi bandı, gerçek SEP olay profilleri |
| **Chang'E-4 / LND** | Yüzeyde ilk doz ölçümü, nötr parçacık katkısı | Yayın (Science Advances 2020) | **Baz doz hızı için altın standart** (13.2 µGy/h) |
| **CRaTER mikrodozimetre güncellemesi** (Mazur vd. 2015) | GCR + solar proton dozu | AGU Space Weather | Doz hızı zaman serisi |
| **Matthiä vd. 2024** | Ay yüzeyinde maruziyet ve **kalkanlama etkileri** | AGU Space Weather | Kalkan kalınlığı → doz azaltımı; SVF modelinizi kalibre etmek için |
| **NOAA SWPC / ESA SSA** | Gerçek zamanlı uzay hava durumu, GOES proton akısı | Kamuya açık API | Canlı senaryo modu (bonus) |

### 4.2 Transport modelleri (mutlak doz iddiası gerekirse)

| Model | Ne yapar | Erişim |
|---|---|---|
| **NASA OLTARIS** | Web tabanlı uzay radyasyon analiz aracı; kalkan geometrisi + ortam → doz | Kayıtlı erişim, ücretsiz |
| **HZETRN** | Deterministik transport (OLTARIS'in çekirdeği) | NASA |
| **GEANT4** | Monte Carlo parçacık transportu | Açık (CERN lisansı) |
| **PHITS** | Monte Carlo (JAEA) | Kayıt gerekli |
| **Badhwar–O'Neill / ISO 15390** | GCR ortam modeli (güneş çevrimi bağımlı) | Standart / yayın |

**Öneri:** LunaPath'in kapsamında **transport hesabı yapmayın.** SVF-tabanlı göreli modülasyon + LND'nin ölçülmüş baz değeri + belirsizlik beyanı yeterli ve savunulabilirdir. Belgeye şu cümleyi yazın: *"Mutlak doz iddiası için OLTARIS/GEANT4 tabanlı transport hesabı gereklidir; bu çalışmada göreli kalkanlama karşılaştırması yapılmıştır."*

---

## 5. Elektronik etkileri — `health_score`'a nasıl girer

LunaPath'in mevcut `health_score` modeli sadece termal stresi biriktiriyor. Radyasyonu eklerken **doğru mekanizmayı** seçin:

| Mekanizma | Birikimli mi? | LunaPath'te modelleme |
|---|---|---|
| **TID** (toplam iyonlaştırıcı doz) | ✅ Evet, geri dönüşsüz | Birikimli sayaç; ama kısa misyonda etkisiz (§1.2) → **raporla, cezalandırma** |
| **DD** (yer değiştirme hasarı) | ✅ Evet | Aynı; optik/detektör dejenerasyonu |
| **SEU** (bit flip) | ❌ Olasılıksal, düzeltilebilir | **Oran (rate) olarak modelle**: `λ_SEU ∝ akı`. EDAC/watchdog ile kurtarılır → `replan_trigger` |
| **SEL** (latch-up) | ❌ Olasılıksal, **kalıcı hasar riski** | Düşük olasılık, yüksek sonuç → misyon riski olarak raporla |
| **SEFI** (fonksiyonel kesinti) | ❌ | Reset gerektirir → görev süresi kaybı |

**Somut öneri — `health_score`'u iki eksene ayır:**

```python
class HealthState(BaseModel):
    thermal_stress_accum: float      # mevcut model
    radiation_tid_rad: float         # birikimli, raporlanir
    seu_events_expected: float       # olasiliksal beklenen deger
    sep_exposure_h: float            # SEP sirasinda maruz kalinan sure
    # Tek bir skalar 'health' yerine bilesen bazli — belgede
    # acik soru olarak birakilmisti (proje dokumani §6.5); karar: BILESEN BAZLI
```

Bu, `ay_termal_navigasyon_proje_dokumani.md` §6.5'teki açık soruyu ("tek genel health score mu, bileşen bazlı mı?") **bileşen bazlı** lehine kapatır. Gerekçe: termal ve radyasyon **farklı zaman ölçeklerinde ve farklı geri dönüşlerle** çalışır (termal geri kazanılabilir, TID kazanılamaz); tek skalarda toplamak bilgi kaybıdır.

---

## 6. Boşluk analizi

| # | Boşluk | Etki | Efor | Öncelik |
|---|---|---|---|---|
| R1 | Radyasyon tamamen yok ama "donanım sağlığı" iddia ediliyor | 🟠 Yüksek (tutarlılık) | — | — |
| R2 | SVF katmanı yok (DEM'den üretilebilir, yeni veri gerekmez) | 🟠 Orta-yüksek | Orta | **P1** |
| R3 | SEP senaryosu yok | 🟠 Orta-yüksek (demo değeri çok yüksek) | Düşük | **P1** |
| R4 | `health_score` tek skalar, mekanizmaları ayırmıyor | 🟡 Orta | Düşük | **P1** |
| R5 | Safe haven'da kalkan niteliği yok | 🟡 Orta | Çok düşük | P1 |
| R6 | Mutlak doz için transport hesabı yok | 🟢 Düşük (kapsam dışı beyan edilirse) | Yüksek | Kapsam dışı |
| R7 | Canlı uzay hava durumu entegrasyonu yok | 🟢 Bonus | Düşük | P2 |

---

## 7. Yol haritası

### P1 — radyasyon katmanı + SEP senaryosu (2–4 gün)

1. **`sky_view.py`**: SVF hesabı (ray-marching; illumination hesabıyla altyapı paylaşımlı → [04](04_acik_kaynak_modeller.md) §2.2). 36 azimut yeterli. `numba` ile hızlandır.
2. **`radiation.py`**: `gcr_dose_rate_grid(svf)`, LND baz değeri 13.2 µGy/h, doğrulama tablosu (§2)
3. **`f_radiation` penalty** (opsiyonel, düşük ağırlıklı): nominal koşullarda etkisi küçük olmalı — bu **doğru** davranıştır ve belgelenmelidir
4. **SEP senaryosu**: `scenarios/` altına `*_sep_event.json`, `sep_response_plan()` fonksiyonu
5. **`HealthState`** bileşen bazlı refaktör
6. **`SafeHaven.sky_view_factor` + `shelter_quality`** alanları
7. **Metrikler**: `total_tid_rad`, `mean_dose_rate_uGy_h`, `sep_exposure_h`, `shielding_benefit_pct`

**Kabul kriteri:** SEP senaryosu iki kolda koşuyor (SEP-kör vs SEP-farkında) ve karşılaştırma tablosu şunları gösteriyor: sapma mesafesi (m), ek enerji (Wh), ek gölge süresi (h), **önlenen maruziyet (µGy)**, seçilen haven'ın SVF'si.

### P2 — genişletmeler
8. Canlı NOAA SWPC proton akısı ile "gerçek zamanlı mod"
9. CRaTER zaman serisinden gerçek SEP olay profilleri (senaryo kütüphanesi)
10. Matthiä vd. 2024 kalkanlama eğrileriyle SVF modelini kalibre et

---

## 8. Sunumda kullanılacak cümleler

- *"Radyasyonu uzamsal bir maliyet katmanı olarak modellemedik, çünkü GCR neredeyse izotropiktir ve 40 km'lik bir pencerede hücre farkı ihmal edilebilir. Bunun yerine topografyanın gerçek radyasyon etkisini — gökyüzü görüş faktörünü — modelledik."*
- *"Kalıcı gölgeli bölgeler termal olarak ölümcül ama radyasyon açısından koruyucudur. Bu, çok kriterli optimizasyonda gerçek bir çelişkidir ve maliyet fonksiyonumuz bunu görebiliyor."*
- *"GCR kaynaklı TID, kısa süreli yüzey misyonlarında sınırlayıcı faktör değil; ölçülmüş 13.2 µGy/h değeriyle yılda ~12 rad(Si) birikir ve tipik rad-hard bileşenlerin 100 krad toleransının çok altındadır. Bizim modellemeye değer bulduğumuz risk SEP olaylarıdır."*
- *"Mutlak doz iddiası için OLTARIS/GEANT4 transport hesabı gerekir; bu çalışma göreli kalkanlama karşılaştırmasıyla sınırlıdır."*

---

## Kaynaklar

- [Zhang et al. (2020), First measurements of the radiation dose on the lunar surface, Science Advances](https://www.science.org/doi/10.1126/sciadv.aaz1334) · [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7518862/)
- [The Lunar Lander Neutron and Dosimetry (LND) Experiment on Chang'E 4 (arXiv 2001.11028)](https://arxiv.org/pdf/2001.11028)
- [First measurements of low-energy cosmic rays on the lunar farside (Science Advances)](https://www.science.org/doi/10.1126/sciadv.abk1760)
- [Matthiä et al. (2024), Radiation Exposure and Shielding Effects on the Lunar Surface, Space Weather](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2024SW004095)
- [Mazur et al. (2015), Update on Radiation Dose From Galactic and Solar Protons at the Moon Using LRO/CRaTER, Space Weather](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/2015SW001175)
- [Cosmic Ray Enhancements in Lunar Radiation Environment Observed by CRaTER (JKPS)](https://link.springer.com/article/10.3938/jkps.74.614)
- [LRO CRaTER instrument — PDS context](https://arcnav.psi.edu/urn:nasa:pds:context:instrument:crat.lro)
- [LRO Data Products — NASA Science](https://science.nasa.gov/mission/lro/data-products/)
- [Variations of the Galactic Cosmic Rays in the Recent Solar Cycles (arXiv 2104.07862)](https://arxiv.org/pdf/2104.07862)
