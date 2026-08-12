# 07 — Termal Veri

> **Soru:** LunaPath'in ana iddiası termal güvenlik. Termal veri sentetik olduğu sürece bu iddia ne kadar geçerli? Gerçek veri nedir, nasıl alınır, modele nasıl bağlanır?
>
> **Kısa cevap:** Bu, projenin **en kritik tek belgesi**. LunaPath'in özgünlük iddiası termal güvenliktir; termal katman sentetik olduğu sürece iddia dayanaksızdır. Ay yüzey sıcaklığı **15+ yıldır sürekli ölçülüyor** (LRO/Diviner) ve ürünler halka açık. Ayrıca yüzey sıcaklığını rover iç sıcaklığına çeviren mevcut model (`T_iç = T_yüzey ± sabit`) fiziksel olarak yanlıştır ve **tek düğümlü (lumped capacitance) bir enerji dengesi** ile değiştirilmelidir. Bu iki düzeltme, projenin bilimsel ağırlığını en çok artıracak müdahalelerdir.

---

## 1. Mevcut termal zincirin eleştirisi

LunaPath'te termal karar üç aşamalıdır:

```
elevation ──► thermal_grid (sentetik T_yüzey)  ──► T_iç = T_yüzey ± ofset ──► f_thermal (çift sigmoid)
             [thermal_grid.py]                     [cost_engine.py:104]        [cost_engine.py:177]
```

Her aşamada bir problem var.

### 1.1 Aşama 1 — sentetik T_yüzey

[03](03_sentetik_minimum_veri.md) §2'de ayrıntılı eleştirildi. Özet: elevasyon–sıcaklık lineer eşlemesi Ay'da fiziksel temele sahip değil (atmosfer yok → lapse rate yok), doğrulama sirküler, +80 °C tepe sıcaklığı 1.5° güneş elevasyonunda erişilemez, gölge proxy'si tek komşuya bakıyor, zaman yok.

### 1.2 Aşama 2 — sabit ofset modeli (en ciddi model hatası)

```python
# cost_engine.py, surface_to_inner()  — offsetler rover katalogundan geliyor
if T_surface_C < 0:  T_inner = T_surface_C + thermal_offset_cold   # LPR-1: +60
else:                T_inner = T_surface_C + thermal_offset_hot    # LPR-1: -40
```

**Not (kodun lehine):** Ofsetler hard-code değil, `ROVERS` kataloğundan okunuyor ve rover'a göre değişiyor (LPR-1/VIPER: +60/−40, Yutu-2: +70/−30, LUVMI-M: `None` → ofset uygulanmaz, `f_thermal` T_yüzey ile çalışır). Bu parametrik tasarım iyidir. **Eleştiri parametrelere değil, modelin biçimine yöneliktir:** ofset, rover'a göre değişse bile hâlâ *sabit bir ötelemedir*.

**Neden yanlış:** İç sıcaklık, dış sıcaklığın **sabit bir ötelemesi değildir**. İç sıcaklığı belirleyen şey bir **enerji dengesidir**: ısıtıcı gücü, yalıtım (MLI) direnci, ısıl kütle, radyatör alanı ve görüş faktörleri. Sabit ofset, şu absürt sonuçları üretir:

| T_yüzey | T_iç (ofset modeli) | Fiziksel gerçeklik |
|---|---|---|
| −180 °C (93 K) | **−120 °C** | 25 W'lık Kapton ısıtıcıyla iyi yalıtılmış bir gövde −120 °C'ye **düşmez**; ya ~0 °C civarında tutulur ya da ısıtıcı yetersizse **kademeli olarak soğur** — sabit 60 K fark diye bir şey yok |
| −40 °C (233 K) | +20 °C | Tesadüfen makul |
| +60 °C (333 K) | +20 °C | Radyatör kapasitesine bağlı; sabit değil |

Ayrıca: bu model **T_iç'i T_yüzey'in fonksiyonu** yapıyor, yani rover'ın **geçmişini** tamamen yok sayıyor. Gerçekte rover 20 dakika önce güneşteyse ve şimdi gölgeye girdiyse, iç sıcaklığı hâlâ yüksektir. Bu, `THERMAL_TAU_S` sabitinin var olma nedenidir — ama sabit ofset modeliyle **birlikte kullanılamaz**; ikisi çelişir.

### 1.3 Aşama 3 — çift sigmoid `f_thermal`

Bu aşama aslında **iyi tasarlanmış**: batarya (0–35 °C) ve elektronik (−10–40 °C) operasyon aralıklarını ayrı sigmoidlerle cezalandırıp %60/%40 ağırlıklandırıyor. MRU [0,1] normalizasyonu tutarlı. **Bu aşamayı değiştirmeyin** — girdisini düzeltin.

Tek not: `f_thermal` T_yüzey alıp içinde T_iç'e çeviriyor. Ayrıştırın:

```python
def f_thermal_from_inner(T_inner_C, rover=None) -> float:   # saf penalty
def f_thermal(T_surface_C, rover=None) -> float:            # geriye uyum sarmalayıcı
```

Böylece dinamik termal model (§3) `f_thermal_from_inner`'ı doğrudan besleyebilir.

---

## 2. Gerçek termal veri: LRO/Diviner

### 2.1 Enstrüman ve ürünler

Diviner (Diviner Lunar Radiometer Experiment), 9 kanallı bir kızılötesi radyometre; 2009'dan bu yana Ay yüzey sıcaklığını haritalıyor. Temel referans: Paige vd., *Science* **330**, 479 (2010).

**Global High-Resolution Mosaics (GHRM):**

| Özellik | Değer |
|---|---|
| Grid | **128 ppd** (~250 m/px ekvatorda), 0.25 saat yerel zaman aralığı |
| Kapsam | **70°S – 70°N** silindirik projeksiyon |
| Ürünler | Kanal 6–9 parlaklık sıcaklığı (`tb6`…`tb9`), **bolometrik sıcaklık (`tbol`)**, **regolit sıcaklığı (`treg`)** |
| Zaman kesitleri | Gece yarısı (`m`) ve **eğim-düzeltilmiş gece yarısı** (`sam`) |
| Türev | **Kaya bolluğu (`ra`)** — eğim-düzeltilmiş gece yarısından |
| Arşiv | PDS4 bundle `urn:nasa:pds:lro_diviner_derived1`, DOI `10.17189/wj0s-w188` |

> ⚠️ **KRİTİK UYARI — doğrulanması gereken nokta:** GHRM ürünleri **70°S–70°N** kapsıyor. LunaPath'in çalışma bölgesi **80°S–90°S**, yani GHRM'nin **dışında**. Kutup için Diviner'ın ayrı kutup ürünlerini (polar temperature maps / PSR sıcaklık ürünleri) kullanmanız gerekir. **İlk iş bunu doğrulamak olmalı:** PDS Geosciences Node'da `lro_diviner` bundle'larını listeleyip kutup kapsamlı ürünü teyit edin. Yanlış ürünü indirip 40 km'lik pencerenizin tamamen NoData çıkması, kaybedilebilecek en can sıkıcı gündür.

`ay_termal_navigasyon_proje_dokumani.md` §13.1 zaten doğru başlıkları listelemiş: *"Diviner Global and Polar Temperature Maps"*, *"Seasonal Polar Temperatures on the Moon"*. Kutup ürününü buradan takip edin.

### 2.2 Hangi ürünü kullanmalı?

| Ürün | LunaPath'te kullanım | Öneri |
|---|---|---|
| `tbol` (bolometrik sıcaklık) | **Ana termal katman** — `thermal_grid`'in yerine geçer | ⭐ **Birincil hedef** |
| `treg` (regolit sıcaklığı) | Termal atalet/derinlik etkisi | 🟡 Faydalı |
| `ra` (kaya bolluğu) | **Bağımsız tehlike katmanı** — kaya yoğunluğu | ⭐ Bedava bonus ([02](02_goruntu_isleme.md)) |
| Maksimum/minimum sıcaklık haritaları | Hard-constraint (kriyojenik bölge) | ⭐ Zorunlu |
| Mevsimsel kutup sıcaklıkları | Zaman ekseni için | 🟡 P2 |

**`ra` (rock abundance) gözden kaçmasın:** Bu, Diviner'ın gece yarısı sıcaklık anomalilerinden türetilen bir **kaya bolluğu** ürünüdür — kayalar regolitten yavaş soğur, gece daha sıcak görünür. Yani termal veriyi indirdiğinizde, aynı pakette **bağımsız bir kaya tehlike katmanı** da geliyor. [02](02_goruntu_isleme.md)'deki görüntü tabanlı kaya tespiti işini yapmadan bile bir kaya katmanı kazanmış olursunuz.

### 2.3 Ölçülmüş sıcaklık bandı — modelin kalibre edilmesi gereken yer

Diviner'ın en bilinen bulgusu: Ay kutup PSR'ları **Güneş Sistemi'nin ölçülmüş en soğuk yerleri** arasındadır; en düşük değerler **~25 K** mertebesine iner (kuzey kutbunda Hermite A gibi kraterlerde). Güney kutup PSR tabanları tipik olarak **~30–50 K** bandındadır. Su buzunun uzun süreli kararlı olduğu eşik **~110 K**'dir.

**LunaPath'in mevcut sentetik modeliyle karşılaştırma:**

| | Sentetik model | Gerçeklik |
|---|---|---|
| Minimum | −250 °C (23 K) clip'i | ~25–40 K ✅ mertebe doğru |
| Maksimum | +80 °C (353 K) | Kutup aydınlık zirveleri **~200–260 K** ❌ **~100 K fazla iyimser** |
| Ortalama | Belgede "−50 °C civarı beklenir" (223 K) | Kutup için makul mertebe 🟡 |

**En büyük sistematik hata maksimumda.** +80 °C bir yüzey, `f_thermal` içinde T_iç = +40 °C üretir → penalty ~0.011 (ideal). Yani sentetik model, kutupta **var olmayan bir termal cennet** icat ediyor ve planlayıcı buraya çekiliyor. Bu, rotaların yüksek elevasyona sapma eğiliminin nedenidir. Düzeltme (P0, tek satır): `T_max_base = -13.0` (260 K).

### 2.4 Termofiziksel özellikler ve `H` parametresi

Diviner'dan türetilen küresel regolit termofiziksel modeli (Hayne vd., 2017, *JGR Planets*), derinliğe bağlı yoğunluk profili kullanır:

- `ρ_s` (yüzey) ve `ρ_d` (derin) sınır yoğunlukları arasında geçiş
- **`H` parametresi**: bu düşey profilin **ölçek yüksekliği** — temas iletkenliği bileşeninin ve yığın yoğunluğunun derinlikle büyümesini kontrol eder
- PSR içindeki regolitin gözenekliliği **PSR dışına göre belirgin biçimde yüksek** olabilir (dışta ~%40'a karşı içte ~%70'e kadar)

**LunaPath için pratik anlamı:** PSR içi ve dışı **farklı ısı iletkenliğine** sahiptir. Yani PSR'a giren rover, sadece daha soğuk bir ortamla değil, **daha yalıtkan bir zeminle** karşılaşır (temastan ısı kaybı azalır, ama regolitten ısı kazancı da azalır). İkinci mertebe bir etkidir; belgeleyin, modellemeyi P2'ye bırakın.

---

## 3. Doğru model: tek düğümlü (lumped capacitance) termal denge

Sabit ofset modelinin yerine geçecek, **hâlâ basit ama fiziksel** model:

```
C · dT_iç/dt = P_iç + P_ısıtıcı + P_güneş·α·A_abs
               − ε·σ·A_rad·(T_iç⁴ − T_uzay⁴)
               − (T_iç − T_yüzey)/R_temas
```

Ayrık zaman (rota üzerinde segment segment ilerlerken):

```python
# backend/app/thermal_dynamics.py (yeni)
import math

SIGMA = 5.670374419e-8   # Stefan-Boltzmann, W/m^2/K^4
T_SPACE_K = 3.0          # derin uzay

def step_inner_temperature(
    T_inner_K: float,
    T_surface_K: float,
    dt_s: float,
    *,
    C_J_per_K: float,        # rover isil kutlesi
    R_contact_K_per_W: float, # tekerlek/govde -> zemin isil direnci
    eps_A_rad_m2: float,      # emissivite x radyator alani
    P_internal_W: float,      # elektronik + itki
    P_heater_W: float,
    P_solar_absorbed_W: float,
) -> float:
    """Bir zaman adiminda ic sicakligi guncelle (ileri Euler).
    dt_s << tau olmali; aksi halde RK4 veya analitik cozum kullan."""
    Q_in  = P_internal_W + P_heater_W + P_solar_absorbed_W
    Q_rad = eps_A_rad_m2 * SIGMA * (T_inner_K**4 - T_SPACE_K**4)
    Q_cond = (T_inner_K - T_surface_K) / R_contact_K_per_W
    dT = (Q_in - Q_rad - Q_cond) * dt_s / C_J_per_K
    return T_inner_K + dT
```

### 3.1 `THERMAL_TAU_S = 7200` sabitini denetleyelim

Zaman sabiti `τ = C / (hA)` şeklinde türer. LPR-1 için:

```
C  ≈ m · c_p = 450 kg × ~900 J/(kg·K) ≈ 4.0 × 10⁵ J/K
τ  = 7200 s  ⟹  hA = C/τ = 4.0e5 / 7200 ≈ 56 W/K
```

**56 W/K, iyi yalıtılmış bir uzay aracı için çok yüksektir.** MLI'lı bir gövdede etkin iletkenlik tipik olarak **birkaç W/K** mertebesindedir. `hA = 5 W/K` alırsak:

```
τ = 4.0e5 / 5 = 80.000 s ≈ 22 saat
```

> **Bulgu:** `THERMAL_TAU_S = 7200 s` (2 saat), tüm araç için muhtemelen **bir mertebe küçük**. Bu değer küçük bir bileşen (ör. bir kamera muhafazası) için makul olabilir ama 450 kg'lık bir aracın gövdesi için değil. Referans belge bu sabiti 1800 s'den 7200 s'ye yükselttiğini not ediyor — doğru yönde ama yeterli değil.

**Bu neden önemli:** τ, rover'ın gölgede ne kadar dayanacağını belirler. τ küçükse model rover'ı **aşırı kırılgan** gösterir (birkaç saatte soğuyor), gerçekte ise ısıl kütle onu çok daha uzun korur. Bu, `H_MAX_SHADOW_H = 50` sabitiyle **çelişir**: 2 saatlik zaman sabitiyle 50 saat gölgede kalmak imkânsızdır (5τ sonunda denge sıcaklığına oturur).

**Aksiyon (P0, düşük efor, yüksek getiri):** `τ`'yu tek bir sabit olarak vermeyin; `C` ve `hA`'dan **türetin** ve türetmeyi belgeleyin. Böylece sayı savunulabilir hale gelir ve tutarlılık otomatik sağlanır.

### 3.2 Enerji bütçesi tutarlılık denetimi (iyi haber)

Aynı denetimi gölge/batarya sabitlerine uygulayınca sonuç **olumlu**:

```
Kullanılabilir enerji = E_CAP × (1 − SOC_MIN) = 5420 × 0.80 = 4336 Wh

Aktif gölge sürüşü (P_SHADOW_W = 65 W):     4336 / 65  ≈ 67 saat
Hibernate modu    (P_HIBERNATE_W = 108 W):  4336 / 108 ≈ 40 saat
```

`H_MAX_SHADOW_H = 50` bu ikisinin **arasında** oturuyor; `H_DESIGN_SHADOW_H = 70` ise 4336/70 ≈ 62 W ≈ `P_SHADOW_W`'ya karşılık geliyor. **Yani gölge ve enerji sabitleri kendi içinde tutarlı ve fiziksel olarak türetilebilir durumda.** Bu, ekibin lehine bir bulgudur ve sunumda söylenmeye değer: *"Sabitlerimiz keyfi değil; gölge limiti, batarya kapasitesi ve gölge modu güç tüketiminden türetilebiliyor."*

**Karşıtlık:** Enerji tarafı tutarlı, termal zaman sabiti tarafı değil. Termal tarafı da aynı disipline getirmek gerekiyor.

---

## 4. Zaman ekseni: aydınlanmadan sıcaklığa

### 4.1 Neden zorunlu

`f_shadow(H_hours)` fonksiyonu **kümülatif gölge süresi** istiyor. Statik bir haritada "kümülatif gölge süresi" tanımsızdır. Mevcut proxy:

```python
estimate_shadow_hours(elev_norm, Δt) = (1 - elev_norm) × Δt
```

Bu, "alçaktaysan zamanının bir kısmı karanlıktır" der — ne uzamsal ne zamansal olarak fiziksel bir ifade. Doğru zincir:

```
zaman (UTC) ──SPICE──► güneş azimut/elevasyon ──ufuk maskesi──► aydınlık mı?
   ──► P_güneş(t) ──► SOC(t)
   ──► T_yüzey(t) [Diviner yerel-zaman ürünleri veya heat1d]
   ──► T_iç(t) [lumped capacitance]
   ──► f_thermal(T_iç), f_shadow(∫karanlık dt)
```

### 4.2 Üç seviyeli uygulama seçeneği

| Seviye | Yaklaşım | Efor | Doğruluk |
|---|---|---|---|
| **L1 — statik** (bugün) | Tek snapshot | — | ❌ Gölge süresi tanımsız |
| **L2 — hazır aydınlanma ürünü** | LOLA `average illumination` haritası → hücre başına "aydınlık kesri". `H_gölge = Σ (1 − illum_frac) × Δt` | **Düşük** | 🟡 İstatistiksel olarak doğru, olay bazında değil |
| **L3 — zaman-değişken** | SPICE ile güneş geometrisi + kendi ufuk maskeniz → her (hücre, zaman) için ikili aydınlık/gölge | Orta-yüksek | ✅ Fiziksel olarak doğru |

**Önerilen: L2'yi hemen yap, L3'ü hedef olarak koy.** L2, tek satırlık bir kavramsal düzeltmeyle mevcut `f_shadow`'u anlamlı hale getirir ve **indirilebilir bir ürüne** dayanır. `estimate_shadow_hours`'ın yeni hali:

```python
def estimate_shadow_hours(illum_frac: float, delta_t_hours: float) -> float:
    """illum_frac: LOLA average-illumination urunundan [0,1]
    (bu hucrenin bir ay/yil boyunca aydinlik kalma kesri).
    Donus: bu hucrede delta_t sure gecirmenin BEKLENEN golge katkisi."""
    return (1.0 - illum_frac) * delta_t_hours
```

Formül aynı görünüyor ama girdi artık **elevasyon değil, ölçülmüş aydınlanma kesri**. Bu, fiziksel olarak savunulabilir hale gelir — çünkü artık gerçekten "beklenen gölge süresi"dir.

> ✅ **İyi haber — kod bu değişikliğe hazır.** `cost_engine.edge_shadow_hours(shadow_ratio, theta_deg, d_m)` fonksiyonu şu işi yapıyor:
> `shadow_hours = shadow_ratio × (kenar_geçiş_süresi_s / 3600)`
> Yani karanlık kesri × süre. Fonksiyon **imzası bile değişmiyor**; sadece `shadow_ratio_grid`'i besleyen kaynağı `1 − elev_norm`'dan `1 − illumination_frac`'a çevirmek yeterli. Bu, projedeki en yüksek getirili tek satırlık düzeltmedir: fiziksel geçerlilik `NOT_MEASURED` → `MEASURED`'a terfi ederken planlayıcı kodunda hiçbir değişiklik gerekmez.

L3 için altyapı [04](04_acik_kaynak_modeller.md) §2.1 (SpiceyPy) ve §2.2 (ufuk hesabı) ile paylaşımlıdır — aynı ray-marching kodu radyasyon SVF'sini de üretir ([06](06_radyasyon_verisi.md) §2). **Bir kez yaz, üç katman kazan.**

### 4.3 heat1d ile yüzey sıcaklığı dinamiği

Gerçek zaman-değişken yüzey sıcaklığı istiyorsanız, Diviner'ın kendi ekibinden açık kaynak bir 1-B termal model var: **[heat1d](https://github.com/phayne/heat1d)** (Paul Hayne). Girdi olarak güneş akısı zaman serisi + regolit termofiziksel parametreleri (H parametresi dahil) alır, derinlik-zaman sıcaklık profili üretir.

**Kullanım deseni:** Her hücre için heat1d koşmak imkânsız (500×500 = 250.000 koşum). Bunun yerine:

1. Birkaç **temsili rejim** seçin: {kalıcı gölge, düşük aydınlanma, orta, yüksek, kalıcı aydınlık} × {düz, kuzey yamaç, güney yamaç}
2. Her rejim için heat1d ile **sıcaklık zaman serisi** üretin (offline, bir kez)
3. Grid hücrelerini rejimlere **sınıflandırın** (illumination_frac + slope + aspect ile)
4. Planlama sırasında **lookup table**'dan oku

Bu, "fiziksel model" ile "hesaplanabilirlik" arasındaki doğru uzlaşmadır ve [08](08_global_local_rotalama_yuku.md)'in ana temasıyla (önceden hesapla, çalışma zamanında ara) uyumludur.

---

## 5. Doğrulama planı — sentetiği gerçekle ölçmek

[03](03_sentetik_minimum_veri.md) §4.2'deki A/B/C/D ablasyonunun termal kolu için somut metrikler:

| Metrik | Nasıl hesaplanır | Hedef |
|---|---|---|
| **RMSE** | `sqrt(mean((T_sentetik − T_diviner)²))` | Raporla (beklenti: 40–80 K, yani **çok büyük**) |
| **Bias** | `mean(T_sentetik − T_diviner)` | Beklenti: pozitif (sentetik iyimser) |
| **Pearson r** | Uzamsal korelasyon | Beklenti: 0.3–0.6 (mükemmelden uzak) |
| **Sınıf uyumu** | Güvenli/dikkat/tehlikeli üçlüsünde kaç hücre aynı sınıfta? | Confusion matrix olarak sun |
| **Yanlış-güvenli oranı** | Sentetiğin "güvenli", Diviner'ın "tehlikeli" dediği hücre yüzdesi | **En kritik sayı** — operasyonel risk budur |
| **Rota kararı farkı** | A ve D kollarının rotaları arasındaki Fréchet mesafesi | Raporla |

> **Bu tablo doldurulduğunda LunaPath bir hackathon projesi olmaktan çıkar.** Çünkü kendi modelinin hatasını nicelemiş, raporlamış ve düzeltmiş bir mühendislik çalışması haline gelir. Hakem/jüri karşısında "sentetik veri kullandık ama hatasını ölçtük ve gerçeğe geçtik" cümlesi, "gerçek veri kullandık" cümlesinden **daha** güçlüdür.

---

## 6. Boşluk analizi

| # | Boşluk | Etki | Efor | Öncelik |
|---|---|---|---|---|
| T1 | Termal katman sentetik, Diviner mevcutken | 🔴 **Çok yüksek — projenin ana iddiası** | Orta | **P0** |
| T2 | Kutup Diviner ürününün varlığı/kapsamı doğrulanmadı (GHRM 70°S'te bitiyor) | 🔴 Yüksek (blokaj riski) | Çok düşük | **P0** |
| T3 | `T_max_base = +80 °C` kutupta fiziksel değil | 🔴 Yüksek (planlayıcıyı yanlış çekiyor) | Çok düşük | **P0** |
| T4 | Sabit ofset T_yüzey→T_iç modeli fiziksel değil | 🔴 Yüksek | Orta | **P0/P1** |
| T5 | `THERMAL_TAU_S` türetilmemiş, muhtemelen ~10× küçük | 🟠 Yüksek (H_MAX_SHADOW ile çelişiyor) | Düşük | **P1** |
| T6 | Zaman ekseni yok → `f_shadow` girdisi tanımsız | 🟠 Yüksek | Düşük (L2) / Yüksek (L3) | **P1** |
| T7 | `f_thermal` T_iç'i içeride hesaplıyor (ayrıştırılmalı) | 🟡 Orta | Çok düşük | P1 |
| T8 | Kaya bolluğu (`ra`) ürünü kullanılmıyor (bedava) | 🟡 Orta | Düşük | P1 |
| T9 | Termofiziksel özellikler (H parametresi, PSR gözenekliliği) modellenmiyor | 🟢 Düşük-orta | Yüksek | P2 |
| T10 | Diviner ile karşılaştırma/validasyon yok | 🟠 Yüksek | Düşük (veri gelince) | **P1** |

---

## 7. Yol haritası

### P0 — "acil düzeltmeler ve blokaj kaldırma" (1 gün)

1. **Kutup Diviner ürününü doğrula.** PDS Geosciences'ta `lro_diviner` bundle'larını listele, 80–90°S kapsayan sıcaklık ürününü teyit et. Bulunamıyorsa alternatif: yayınlanmış kutup sıcaklık haritalarını (Paige vd. 2010 kutup ürünleri, mevsimsel kutup sıcaklıkları) takip et.
2. **`T_max_base_C`'yi −13 °C'ye (260 K) çek**, gerekçesini kodda yorum olarak yaz. Bu tek satır, planlayıcının yüksek elevasyona yapay çekimini kaldırır.
3. **`f_thermal`'i ayrıştır**: `f_thermal_from_inner()` + geriye uyumlu sarmalayıcı.
4. **`metadata.json`'a `physical_validity`** yaz → [01](01_sektorel_veri_kaynaklari.md) §3.1.

### P1 — "gerçek veriye geç ve modeli fizikselleştir" (4–6 gün)

5. Diviner `tbol` (kutup) indir → hizala → `thermal_grid_diviner.npy`; sentetiği `thermal_grid_synthetic.npy` olarak koru
6. **A/B/C/D ablasyon koşusu** + §5 doğrulama tablosu → `docs/research/ablation_report.md`
7. LOLA `average illumination` indir → `estimate_shadow_hours`'ı illumination_frac ile besle (L2)
8. **`thermal_dynamics.py`**: lumped capacitance modeli; `τ`'yu `C` ve `hA`'dan türet; `H_MAX_SHADOW_H` ile tutarlılığı test et
9. Diviner `ra` (kaya bolluğu) → yeni bağımsız tehlike katmanı
10. Metrikler: `min_surface_temp_K`, `min_inner_temp_K`, `thermal_violation_count`, `time_below_bat_op_min_h`, `synthetic_vs_measured_rmse_K`

**Kabul kriteri (P1):**
- `thermal_grid` kaynağı `LRO/Diviner`, `physical_validity: MEASURED`
- Ablasyon tablosu dolu, **yanlış-güvenli hücre oranı** sayısal olarak raporlanmış
- `THERMAL_TAU_S` artık sabit değil, `C/(hA)`'dan türetilmiş ve `H_MAX_SHADOW_H` ile tutarlı
- Rota üzerinde `T_iç(t)` eğrisi çizilebiliyor (frontend'de zaman serisi grafiği)

### P2 — "derinleştir"
11. SPICE + ufuk maskesi ile L3 zaman-değişken aydınlanma
12. heat1d ile rejim-tabanlı yüzey sıcaklığı lookup tablosu
13. H parametresi / PSR gözenekliliği ikinci mertebe etkileri

---

## 8. Sunumda kullanılacak cümleler

- *"Termal katmanımız artık sentetik değil; LRO/Diviner'ın 15 yıllık bolometrik sıcaklık ölçümlerine dayanıyor. Sentetik modelimizi bir kontrol kolu olarak tutup hatasını niceledik: RMSE X K, ve sentetik model hücrelerin %Y'sini yanlışlıkla güvenli işaretliyordu."*
- *"İç sıcaklığı yüzey sıcaklığının sabit bir ötelemesi olarak modellemiyoruz. Tek düğümlü bir enerji dengesi kuruyoruz: ısıtıcı gücü, radyatör kaybı ve zeminle temas iletimi. Bu, termal zaman sabitini bir varsayım olmaktan çıkarıp ısıl kütle ve yalıtımdan türetilen bir büyüklüğe dönüştürdü."*
- *"Gölge ve enerji sabitlerimiz kendi içinde tutarlı: 50 saatlik gölge limiti, 4336 Wh kullanılabilir enerji ve 65 W gölge modu tüketiminden türetiliyor."*
- *"Ay kutup PSR'ları Güneş Sistemi'nin ölçülmüş en soğuk yerleri arasında, ~25–40 K bandında. Su buzu ~110 K altında kararlı. Bizim rover'ımızın batarya alt limiti 0 °C = 273 K — yani bilimsel olarak en değerli hedef, mühendislik olarak en ölümcül bölge. Projemizin varlık nedeni bu çelişkidir."*

---

## Kaynaklar

- [Paige et al. (2010), Diviner Lunar Radiometer Experiment, Science 330, 479](https://www.science.org/doi/10.1126/science.1197135)
- [The global surface temperatures of the Moon as measured by Diviner (Icarus)](https://www.sciencedirect.com/science/article/pii/S0019103516304869)
- [LRO Diviner Global High-Resolution Mosaics (GHRM) — ODE/WUSTL](https://ode.rsl.wustl.edu/moon/pagehelp/Content/Missions_Instruments/Lunar%20Reconnaissance%20Orbiter%20(LRO)/DIVINER/GHRM.htm)
- [LRO Diviner Lunar Radiometer Global Data Products (Planetary Data Workshop)](https://www.hou.usra.edu/meetings/planetdata2017/pdf/7095.pdf)
- [Hayne et al. (2017), Global Regolith Thermophysical Properties of the Moon From Diviner, JGR Planets](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/2017JE005387)
- [Global regolith thermophysical properties of the Moon (arXiv 1711.00977)](https://arxiv.org/pdf/1711.00977)
- [A Model for the Thermophysical Properties of Lunar Regolith at Low Temperatures (Diviner/UCLA)](https://luna1.diviner.ucla.edu/~dap/pubs/096.pdf)
- [Powell et al. (2023), High-Resolution Nighttime Temperature and Rock Abundance Mapping, JGR Planets](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2022JE007532)
- [Thermophysical Properties of Lunar Regolith from Diviner (ApJ)](https://iopscience.iop.org/article/10.3847/1538-4357/addd1d)
- [Thermal Stability of Ice at Shackleton Crater (PSJ)](https://iopscience.iop.org/article/10.3847/PSJ/ae3c86)
- [heat1d — Thermal model for planetary science (GitHub)](https://github.com/phayne/heat1d)
- [Paul Hayne — Lunar Regolith projects](https://phayne.github.io/projects/5_lunar-regolith/)
