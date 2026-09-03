# 11 — LunaPath Backend: Akademik ve Fiziksel Olgunluk Analizi

**Tarih:** 30 Ağustos 2026 · **Branch:** `backend/physics` · **Kapsam:** yalnızca analiz, kod değişikliği yok
**Analiz tabanı:** 4.786 satır backend Python, 263 geçen test (7 dk 3 sn), sevk edilmiş `lunapath/data/processed/` grid'i üzerinde bağımsız ölçüm

> Bu belge [09_olgunluk_kiyaslama.md](09_olgunluk_kiyaslama.md)'nin **yerini almaz, onu günceller.** 09 yazıldığında zaman ekseni, ROS 2 katmanı, `CostMap` refaktörü ve SPICE/heat1d entegrasyonu henüz yoktu; o belgedeki 23/50 skoru bugün geçersizdir.

---

## 0. Tek cümlelik teşhis

> **LunaPath backend'i, mühendislik disiplini bakımından bir hackathon prototipinin çok üstünde (üst-çeyrek lisansüstü seviye); fiziksel geçerlilik bakımından ise hâlâ tek bir ölçümle karşılaştırılmamış bir modeldir. "Kodu doğru yazdık" güçlü biçimde kanıtlanmış, "doğru modeli yazdık" ise hâlâ kanıtlanmamıştır — ve ekip bunu kendi belgelerinde açıkça yazacak dürüstlüğü göstermiştir.**

09 no'lu belgenin teşhisi (verification güçlü / validation sıfır) **hâlâ geçerlidir.** Değişen şey, verification tarafının o günden bu yana daha da güçlenmesi ve zaman/otonomi eksenlerinin fiilen kapanmasıdır.

---

## 1. Ne değişti — 09'dan bu yana kapanan boşluklar

09 no'lu belge şu maddeleri "yok" diye işaretlemişti. Bugün kodda mevcut ve testli:

| 09'daki iddia | Bugünkü gerçek | Kanıt |
|---|---|---|
| "Zaman ekseni: 🔴 Yok, statik snapshot, bekleme kararı yok" | ✅ **Zaman-genişletilmiş A\* mevcut**, WAIT kenarı dahil | `backend/app/pathfinder_4d.py` (275 satır), `cost_cube.py` (244 satır), `test_pathfinder_4d.py` |
| "`f_shadow(H)` girdisi tanımsız" | ✅ Hücre-seviyesi `f_shadow_cell` ayrıştırıldı; kümülatif `f_shadow` planlayıcıda kaldı | `cost_engine.py:96-118` |
| "Termal sentetik" | 🟡 **Kısmen kapandı** — heat1d (Hayne 2017) 1-D regolit difüzyon modeli entegre; `layer_validity: MODEL` | `thermal_model.py:Heat1DModel`, `metadata.json` |
| "Gölge sentetik (`1 - normalize(elevation)`)" | ✅ **Kapandı** — SPICE efemeris + ray-cast topografik ufuk | `ephemeris.py`, `horizon.py`, `illumination.py`; `layer_validity: DERIVED` |
| "Otonomi kapsamı: yerel katman, replanning yok" | ✅ `Corridor` sözleşmesi + 6 replan tetikleyicisi + ROS 2 action server | `corridor.py`, `replan_triggers.py`, `lunapath_ros/` (506 satır) |
| "`CostMap.explain()` refaktörü (Aşama II, madde 19)" | ✅ Yapılmış | `costmap.py`, `test_costmap.py` |

**Sonuç:** 09'un "Aşama II" listesinin (3-4 hafta, TRL 4) büyük kısmı ve "Aşama III"ün 21. maddesi (zaman-genişletilmiş graf + bekleme kenarı) tamamlanmış. Bu, belgede planlanandan **belirgin biçimde ileri** bir noktadır.

---

## 2. Fiziksel doğruluk — madde madde denetim

### 2.1 🟢 Doğru ve savunulabilir olanlar

**Enerji modeli — fiziksel olarak türetilebilir.**
`edge_energy_wh` şu formu kullanıyor: `E = P_base · μ · t`, burada `μ = 1 + k·sin(θ)` ve `k = m·g_Ay/F_net`.
Katalogdaki dört rover için bu ilişkiyi bağımsız olarak doğruladım:

| Rover | m (kg) | F_net (N) | m·g_Ay/F_net | Kodda `mu_coeff` |
|---|---|---|---|---|
| LPR-1 | 450 | 210 | **3.471** | 3.471 ✅ |
| LUVMI-M | 40 | 50 | **1.296** | 1.296 ✅ |
| NASA VIPER | 450 | 200 | **3.645** | 3.645 ✅ |
| CNSA Yutu-2 | 140 | 80 | **2.835** | 2.835 ✅ |

Dördü de birebir tutuyor (g_Ay = 1.62 m/s²). Bu, "sabitleri uydurduk" değil, **tek bir fiziksel ilişkiden türetilmiş bir katalog** demektir. Akademik olarak savunulabilir, çünkü boyut analizi doğru: eğim arttıkça yerçekimi bileşeni net çekiş kuvvetine oranlanıyor.

**Güneş geometrisi — gerçek efemeris, gerçek konvansiyon.**
`ephemeris.py` NAIF SPICE (`spkpos`, `MOON_ME` çerçevesi, `LT+S` düzeltmesi) kullanıyor. Kritik olarak, projeksiyon yakınsaması (*grid north* ≠ *true north*) **kapalı-form bir formül varsayılmadan, gerçek CRS üzerinden sayısal olarak** hesaplanıyor (`true_north_grid_azimuth`). Bu, çoğu öğrenci projesinin — ve dürüst olmak gerekirse bazı yayınların — gözden kaçırdığı bir ayrıntıdır. Review belgesi bu değeri analitik olarak da doğrulamış (249.775°, kutupsal-stereografik beklenen değerle birebir).

**Topografik ufuk — Ay eğriliği dahil.**
`horizon.py` her hücre ve her azimut için ray-marching yapıyor ve `dz -= d²/(2R_Ay)` ile eğrilik düzeltmesi uyguluyor. 10 km menzilde bu düzeltme ~2.9 m'dir — kutupta güneş yüksekliği 1-2° mertebesinde olduğu için **ihmal edilemez** ve doğru şekilde dahil edilmiş.

**heat1d entegrasyonu — gerçek API araştırmasıyla.**
`Heat1DModel` docstring'i, PyPI sürümünün eğim desteği olmadığını, GitHub `main`'in `python/` alt dizinine taşındığını, `fourier-matrix` çözücüsünün eğimli yüzeylerde Gibbs halkalanması ürettiğini ve bu yüzden `crank-nicolson` seçildiğini belgeliyor. `ndays=13` (~1 Ay yılı) seçimi ölçümle gerekçelendirilmiş (tek gün, yıllık tepeyi 81 °C kaçırıyor). **Bu, kütüphaneyi "import edip çalıştırdık" değil, kütüphaneyi anlayarak kullanmaktır.**

**Provenance (veri kökeni) takibi.**
`layer_validity` alanı her katmanı `MEASURED / DERIVED / MODEL / SYNTHETIC` olarak etiketliyor; `weakest_validity()` ise türetilmiş katmanların (cost, traversable) **en zayıf girdilerinin** etiketini miras almasını sağlıyor. Bu, NASA-STD-7009'un "Input Pedigree" faktörünün doğrudan karşılığıdır ve öğrenci projelerinde neredeyse hiç görülmez.

**Log-barrier kısıtları.**
`log_barrier_penalty` interior-point yönteminin standart formu (`-μ·Σ log(slack)`). Eğim, yanal eğim, SOC ve iç sıcaklık için ayrı slack terimleri var; her biri sınıra yaklaşınca maliyet düzgün biçimde ıraksıyor. Bu, sert `if` eşiklerine göre matematiksel olarak üstündür.

**A\* optimalliği korunmuş.**
`pathfinder_4d`'de MOVE ve WAIT kenarları aynı birime (saat) getirilmiş ve sezgisel `mesafe / v_max` kullanıyor — `v_max` rover'ın ulaşabileceği en yüksek hız olduğu için bu **kanıtlanabilir biçimde admissible**. Review belgesi bunu ayrıca consistency açısından da doğrulamış. Çoğu proje sezgiseli "yeterince iyi" diye bırakır; burada optimallik argümanı açıkça yazılmış.

### 2.2 🔴 Fiziksel geçerliliği kırılmış olan: termal katman

Bu, backend'in **tek en ciddi doğruluk sorunudur** ve ekip bunu kendi review belgesinde (H4) zaten tespit etmiştir. Sevk edilmiş `thermal_grid.npy` üzerinde bağımsız olarak yeniden ölçtüm:

```
Spearman(slope, thermal)        = 0.9845
Spearman(slope, shadow_ratio)   = 0.1504
Spearman(shadow_ratio, thermal) = 0.1360
thermal aralığı: -156.7 °C  →  +42.6 °C
```

**Üç ayrı sorun aynı anda:**

1. **Kriter bağımsızlığı çökmüş.** ρ = 0.9845, termal kriterinin eğim kriterinden neredeyse hiç bağımsız bilgi taşımadığı anlamına gelir. 4 kriterli ağırlıklandırma fiilen **3 kriterli** çalışıyor; w_thermal = 0.190'lık ağırlık, eğim kriterinin gizli bir tekrarına gidiyor.

2. **İşaret ters.** Düz zemin −156.7 °C, dik zemin +42.6 °C okunuyor. `f_thermal` soğuğu cezalandırdığı için **termal terim dik araziyi ödüllendiriyor** ve eğim terimini kısmen iptal ediyor. Bu, nav2 baseline karşılaştırmasında ölçülebilir bir semptom üretmiş: LunaPath'in `max_slope_deg` değeri geometrik baseline'dan **daha kötü** çıkmış (24.99 vs 24.96).

3. **Katman arazi gölgelemesini bilmiyor.** LUT yalnızca (eğim, bakı) fonksiyonu. Kalıcı gölgeli krater tabanı ile güneşli düzlük aynı sıcaklığı alıyor — oysa `shadow_ratio` katmanı bu bilgiyi zaten üretiyor (ρ(shadow, thermal) = 0.136, yani ikisi neredeyse ilişkisiz).

**Kök neden — analizim:** Bu bir kodlama hatası değil, bir **istatistik seçimi** sorunudur. `_lookup_table` `np.nanmax(surface_k)` alıyor, yani **yıllık tepe sıcaklık**. Bu seçim kendi içinde savunulabilir bir güvenlik kararıdır ("rover'ın hayatta kalması gereken en sıcak hal"). Ancak −89.5° enlemde bir Ay yılı boyunca hemen her bakı açısı benzer büyüklükte bir en-iyi-an yakalar; dolayısıyla bakı ekseni çöker (yayılım yalnızca 0-13 K) ve geriye sadece eğimin geometrik etkisi kalır — eğimli yüzey daha dik güneş geliş açısı yakalayabildiği için de işaret ters döner.

**Doğru düzeltme yönü** (uygulanmadı, öneri):
`nanmax` planlama maliyeti için yanlış istatistiktir. Doğrusu, **traversability sert sınırı için `nanmax`/`nanmin`** (hayatta kalma zarfı) ile **maliyet fonksiyonu için ortalama veya zaman-eşlenik sıcaklık** ayrımını yapmaktır. Ayrıca LUT'un `illumination_fraction` ile modüle edilmesi 3. sorunu doğrudan kapatır — çünkü o veri zaten üretiliyor.

### 2.3 🟠 İkincil doğruluk bulguları (bu analizde ilk kez tespit edildi)

**`simulation.py` ile `cost_engine.py` iki farklı enerji fiziği kullanıyor.**
Bu, mevcut review belgelerinde geçmiyor:

| | `cost_engine.edge_energy_wh` | `simulation.simulate_path` |
|---|---|---|
| Eğim çarpanı | `1 + 3.471·sin θ` (sürekli, türetilmiş) | Parçalı-doğrusal tablo, 2.5'te tavan |
| Hız modeli | `v_max · cos θ` | `v_max · max(0.2, 1 − θ/50)` |
| Kaynak | `μ = m·g/F_net` fiziği | "orijinal LPR-1 simülasyonundan korundu" |

Yani planlayıcının maliyetlendirdiği enerji ile simülasyonun raporladığı enerji **aynı modelden gelmiyor**. 25°'de: cost_engine μ = 2.47, simulation μ = 2.5 — sayısal olarak yakın, ama bu bir tesadüf; hız modelleri belirgin biçimde ayrışıyor (25°'de cos θ = 0.906 vs 1 − 25/50 = 0.5, **%81 fark**). Akademik bir raporda "enerji tüketimimiz X Wh" denildiğinde bu iki sayıdan hangisinin kastedildiği belirsizdir.

**`simulate_path`'te sihirli yeniden şarj.**
`if battery_wh <= 0: battery_wh = battery_capacity_wh` — batarya bitince anında dolduruluyor ve `recharge_count` artıyor. Fiziksel olarak bu, "sıfır süreli, sıfır maliyetli, güneşten bağımsız tam şarj" demektir. `wait_cost` fonksiyonu (`cost_cube.py`) doğru şarj fiziğini (`P_solar · illum_frac − P_idle − P_heater`) **zaten biliyor**; simülasyon onu kullanmıyor. Rapor edilen `final_battery_pct` ve `total_recharges` metrikleri bu yüzden fiziksel anlam taşımıyor.

**"AHP ağırlıkları" adlandırması yanlış.**
Referans belgesi ağırlıkları "gradyan-bazlı türetilmiş" diyor ve `[0.409, 0.259, 0.142, 0.190]` veriyor (toplam = 1.0 ✅). Ancak AHP'nin (Saaty) tanımı gereği bir **ikili karşılaştırma matrisi** ve bir **tutarlılık oranı (CR < 0.10)** gerektirir. Kod tabanında ve belgelerde ne matris ne CR var (grep ile doğrulandı). Bu ağırlıklar meşru olabilir, ama **"AHP ağırlıkları" akademik olarak yanlış bir etikettir**; jüri/hakem bunu sorar. Doğru adlandırma: "gradyan-normalize edilmiş uzman ağırlıkları".

**Sentetik termal fallback'te `T_base` elevasyondan.**
`thermal_grid.py` yüksekliği doğrudan sıcaklığa çeviriyor (−180 °C → +80 °C). Ay'da atmosfer olmadığı için **irtifa-sıcaklık ilişkisi (lapse rate) fiziksel olarak yoktur.** Bu yalnızca fallback yolu ve dürüstçe `SYNTHETIC` etiketli — ama bir sunumda savunulamaz, sadece "heat1d yoksa boru hattı durmasın" amaçlı olduğu net söylenmelidir.

**Grid çözünürlüğü ile ufuk menzili gerilimi.**
Sevk edilen grid 5 m/px (500×500 = 2.5 km). `horizon_map` varsayılanları `max_range_m=10000, max_steps=200` → 5 m'de efektif menzil **1 km**, nominal 10 km'nin onda biri. 2.5 km'lik bir pencerede pencere dışı topografya zaten görülemiyor; kutupta gölgeleri asıl belirleyen ise **onlarca km ötedeki krater duvarlarıdır.** Yani `shadow_ratio` katmanı `DERIVED` etiketli olsa da, fiziksel olarak eksik bir ufuk üzerinden hesaplanmıştır. Bu, belgelenmesi gereken bir sınırlamadır.

---

## 3. Mühendislik olgunluğu — burası projenin gerçek sermayesi

Fizikten ayrı olarak değerlendirilmesi gereken boyut. Burada proje **açıkça olağanüstüdür**.

| Gösterge | Ölçüm | Yorum |
|---|---|---|
| Test sayısı | **263 geçen test**, 7 dk 3 sn | 09 belgesinde 9 test dosyası vardı; şimdi 25 dosya |
| Test kalitesi | Gerçek grid üzerinde entegrasyon testleri (`test_plan_4d_real_grid.py`) | Review'un H2 bulgusu: "sadece 16×16 fixture'da test edilmiş" → düzeltilmiş |
| Kod boyutu | 4.786 satır kod, 23 modül, 25 test dosyası | Sağlıklı oran |
| Commit disiplini | 114 commit, tamamı Conventional Commits | `feat:`, `fix:`, `docs:`, `refactor:`, `test:` |
| Öz-denetim | 3 ayrı review raporu, bulgular H/M/L olarak sınıflandırılmış | **En nadir bulunan özellik** |
| Mimari katmanlama | Saf çekirdek (`rover_grids.py`) + iki kabuk (FastAPI, ROS 2) | Faz 4 H1 bulgusunun sonucu — doğru refaktör |
| Lisans denetimi | `DATA_LICENSES.md`, GPL taraması yapılmış | MIT projesi için doğru özen |

### 3.1 Özellikle dikkat çekici üç örnek

**1. Yorumlar "ne" değil, "neden" ve "neyin yanlış gidebileceğini" anlatıyor.**
`cost_cube.py`'deki şu invariant bir öğrenci projesinde değil, olgun bir mühendislik ekibinde görülür:

> *"Hangi katmanların zamanla değiştiği VARSAYILMIYOR, PROBE ediliyor: shadow_ratio'yu farklı bir isim altında okuyan bir katman aksi halde sessizce tek bir değerde donar ve doğru görünen ama zamandan bağımsız bir küp üretir."*

Katmanlar `zeros` ve `ones` ile prob edilip zamanla değişip değişmedikleri fiilen ölçülüyor — gelecekteki bir sessiz hatayı önlemek için.

**2. Bulunan hatalar sayısal kanıtla kapatılıyor.**
M2 bulgusu: "BEKLE ve HAREKET kenarları farklı birimde, bekleme ~6.500× ucuz." Ölçüm verilmiş (ortalama MOVE ~29, karanlık WAIT ~0.0045), düzeltme yapılmış, admissibility argümanı yeniden kurulmuş.

**3. Kendi hatasını düzeltirken ikinci bir hata bulup onu da kayda geçirmiş.**
H4 bulgusu ilk yazımında plan taslağındaki koda bakılmış, gerçek koda değil. Düzeltme geçişinde bu fark edilmiş ve belgede **açıkça "bu bir okuma hatasıydı"** diye düzeltilmiş, ölçüm kısmının neden hâlâ geçerli olduğu ayrıca gerekçelendirilmiş. Bu düzeydeki entelektüel dürüstlük yayınlanmış literatürde bile yaygın değildir.

### 3.2 Mühendislik tarafındaki açıklar

- **Belirsizlik nicelemesi yok.** Hiçbir çıktıda hata bandı, güven aralığı veya duyarlılık analizi yok. 09'un 5. boyutu (1/5) değişmedi.
- **Doğrulama (validation) sıfır.** Hiçbir katman bir ölçümle karşılaştırılmadı. Diviner ürünü indirilmedi, LOLA illumination indirilmedi.
- **Ablasyon çalışması yok.** "Termal katmanı çıkarsak rota ne kadar değişir?" sorusunun cevabı yok — ki H4 göz önüne alındığında bu **kritik** bir eksiktir: termal katman kaldırılırsa rota muhtemelen *iyileşecektir*.
- **`main.py` 846 satır.** Tek dosyada 14 endpoint; router'lara bölünmemiş. İşlevsel sorun değil, bakım borcu.
- **`compute_cost_grid` hücre hücre Python döngüsü.** 500×500 için `np.ndenumerate` üzerinde 250.000 iterasyon. Vektörleştirilebilir; `cost_cube` zaten `np.vectorize` maliyetinin farkında ve etrafından dolaşmış.

---

## 4. Sektörel karşılaştırma

### 4.1 Uçmuş / uçacak sistemlerle

| Boyut | LunaPath (bugün) | Yutu-2 | Pragyan | VIPER (2027 hedef) | CADRE |
|---|---|---|---|---|---|
| Konum | Yer katmanı, görev öncesi | Rover üzeri | Yer-döngülü | Rover üzeri | Rover üzeri, çoklu |
| Global rota planlama | 🟢 Çok kriterli + zaman | 🟢 | 🟢 (Dünya'da) | 🟢 | 🟢 |
| Yerel algı / engel kaçınma | ❌ Kapsam dışı (belgeli) | 🟢 Görsel SLAM | 🟡 Navcam→DEM | 🟢 | 🟢 Stereo + GPR |
| Termal/enerji kısıtlı planlama | 🟡 Model var, doğrulanmamış | 🟢 Donanım | ⚪ | 🟢 Referans senaryo | 🟡 |
| Gerçek uçuş kanıtı | ❌ | 🟢 6+ yıl | 🟢 Uçtu | ⏳ | ⏳ |

**Doğru okuma:** LunaPath bu sistemlerin **rakibi değil, tamamlayıcısıdır.** Pragyan'ın yer-döngülü modeli LunaPath'in konumlandırmasına en yakın operasyonel karşılıktır ve bu konumlandırma **gerçek ve savunulabilirdir** — ISRO tam olarak bunu yaptı.

### 4.2 Akademik literatürle — LunaPath'in gerçek rakipleri

| Çalışma | Onlarda olup LunaPath'te olmayan | LunaPath'te olup onlarda olmayan |
|---|---|---|
| **Lamarre, Malhotra, Kelly (IEEE AERO 2024)** — şans-kısıtlı, stokastik erişilebilirlik, çok günlük | 🔴 Stokastik formülasyon, arıza modeli, belirsizlik | 🟢 4 rover profilli platform duyarlılığı, hücre bazlı açıklanabilirlik |
| **Risk-Aware Coverage (arXiv 2404.18721)** — CLOVER 7 kg, gerçek arazi testi, MAE 0.32-0.41 m | 🔴 Gerçek donanım, saha doğrulaması, LiDAR SLAM | 🟢 SPICE efemeris, eğrilikli ufuk, provenance takibi |
| **Deep Learning Global Path Planning (Sensors 24(3), 844)** — zaman-değişken kısıtlar, bekleme izni, RL | 🟡 RL yaklaşımı | 🟢 Açıklanabilirlik (analitik maliyet vs. öğrenilmiş politika); **zaman ekseni artık LunaPath'te de var** |
| **Deep Probabilistic Traversability (arXiv 2409.00641)** | 🔴 Belirsizlik-farkında geçilebilirlik | 🟢 Deterministik açıklanabilirlik |

**Kritik gözlem:** 09 no'lu belge yazıldığında Sensors 24(3) çalışması "zaman ekseni ve bekleme kararı var, LunaPath'te ikisi de yok" diye işaretlenmişti. **Bu fark bugün kapanmıştır.** `pathfinder_4d.py`'nin WAIT kenarı tam olarak bu yeteneği sağlıyor ve `wait_cost` güneş şarjını doğru modelliyor.

### 4.3 Nerede gerçekten öndeler

Bu üç maddeyi karşılaştırılan çalışmaların hiçbiri birlikte yapmıyor:

1. **Platform duyarlılık analizi.** Aynı harita, aynı start/goal, 4 gerçek rover profili (VIPER, Yutu-2, LUVMI-M, LPR-1), yan yana sayısal karşılaştırma. Literatürde tek rover normdur.
2. **Provenance takibi bir birinci sınıf özellik olarak.** `layer_validity` + `weakest_validity()` — NASA-STD-7009'un Input Pedigree faktörünün doğrudan kod karşılığı. Akademik makalelerde bu "Yöntem" bölümünde bir cümledir; burada çalışan koddur.
3. **Öz-denetim kültürü.** Kendi bulgularını H/M/L sınıflayan, ölçen, bazılarını bilinçli olarak düzeltmeyip gerekçesini yazan bir ekip. **Bu, bir yayının "Limitations" bölümünü baştan yazmış olmak demektir.**

### 4.4 Nerede geridiler

1. **Validation sıfır.** Bu tek başına bir yayını hakem sürecinde durdurur.
2. **Belirsizlik yok.** Lamarre vd.'nin tüm katkısı bu eksende.
3. **Gerçek donanım / saha testi yok.**
4. **Termal katman fiziksel olarak kırık** (§2.2) — ve bu, projenin *öne çıkardığı* kriterlerden biri.

---

## 5. Güncellenmiş olgunluk skorkartı

09'un 10 boyutlu ölçeğiyle, bugünkü kod üzerinden yeniden puanlandı.

| # | Boyut | 09 (Ağu 27) | **Bugün** | Değişim | Gerekçe |
|---|---|---|---|---|---|
| 1 | Veri gerçekliği | 2/5 | **3/5** | ▲ +1 | Gölge artık DERIVED (SPICE+ufuk), termal MODEL (heat1d). Ama hâlâ tek DEM girdisi; Diviner/LOLA yok |
| 2 | Fizik modeli | 3/5 | **3/5** | = | Enerji ve geometri güçlendi (μ türetimi, eğrilik, CRS yakınsaması); termal katman kırık (§2.2) ve iki farklı enerji modeli var (§2.3) — kazanç ve kayıp dengeleniyor |
| 3 | Verification | 4/5 | **5/5** | ▲ +1 | 263 test, gerçek grid entegrasyon testleri, admissibility argümanı yazılı, 3 review raporu |
| 4 | Validation | 1/5 | **1/5** | = | Hiçbir katman hâlâ ölçümle karşılaştırılmadı |
| 5 | Belirsizlik | 1/5 | **1/5** | = | Değişmedi |
| 6 | Hesaplama olgunluğu | 2/5 | **4/5** | ▲ +2 | `auto_slice_hours`, invariant-katman probing, unique-değer tablolama, `bfs_move_count` ön-kontrolü, ölçülmüş optimizasyonlar (22 s → azaltıldı) |
| 7 | Zaman / dinamik | 1/5 | **4/5** | ▲ +3 | Zaman-genişletilmiş A\*, WAIT kenarı, güneş-şarjlı `wait_cost`, cost cube. **En büyük sıçrama** |
| 8 | Otonomi kapsamı | 2/5 | **3/5** | ▲ +1 | Corridor sözleşmesi, 6 replan tetikleyicisi, ROS 2 action server, sanal LiDAR arayüz provası. Perception hâlâ yok (bilinçli) |
| 9 | Açıklanabilirlik | 4/5 | **5/5** | ▲ +1 | `CostMap.explain()`, `/api/cell-telemetry`, `cost_breakdown`, nav2 baseline karşılaştırması |
| 10 | Belgeleme / tekrar-üretilebilirlik | 3/5 | **4/5** | ▲ +1 | `DATA_LICENSES.md`, provenance, 11 araştırma belgesi, review raporları. Veri sürümleme hâlâ yok |
| | **TOPLAM** | **23/50** | **33/50** | **▲ +10** | |

### 5.1 TRL ve model kredibilitesi

| | 09'daki beyan | Bugünkü savunulabilir beyan |
|---|---|---|
| TRL | 3 (analitik kavram kanıtı) | **3, üst sınırında** — TRL 4 eşiğine tek bir engel kaldı: validation |
| NASA-STD-7009 Verification | 🟢 İyi | 🟢 **Çok iyi** |
| NASA-STD-7009 Validation | 🔴 Yok | 🔴 **Hâlâ yok** |
| NASA-STD-7009 Input Pedigree | 🔴 Zayıf | 🟡 **Orta** (provenance sistemi var, kaynak çeşitliliği yok) |
| Results Uncertainty | 🔴 Yok | 🔴 Yok |
| M&S Management | 🟡 Orta | 🟢 **İyi** (114 commit, review süreci, lisans denetimi) |

**Önerilen beyan cümlesi:**
> *"LunaPath, TRL 3'ün üst sınırında bir analitik kavram kanıtıdır. NASA-STD-7009 çerçevesinde verification (kodun modeli doğru uygulaması) güçlü biçimde kanıtlanmıştır — 263 test, üç bağımsız denetim geçişi ve yazılı optimallik argümanlarıyla. Validation (modelin gerçeği doğru yansıtması) ise bilinçli olarak açık bir boşluktur ve TRL 4 iddiası için kapatılması gereken tek asıl engeldir."*

---

## 6. İddia denetimi — ne söylenebilir, ne söylenemez

| İddia | Durum | Not |
|---|---|---|
| "Gerçek SPICE efemerisi ve ray-cast topografik ufuk ile aydınlanma hesaplıyoruz" | ✅ **Evet** | Kodda var, testli, eğrilik dahil |
| "Zaman-genişletilmiş planlama yapıyoruz; rover 'bekle, güneş gelsin, sonra geç' kararı verebiliyor" | ✅ **Evet** | `pathfinder_4d.py` + `wait_cost` |
| "Enerji modelimiz her rover için `m·g/F_net` fiziğinden türetilmiştir" | ✅ **Evet** | 4/4 rover doğrulandı |
| "Veri kökeni (provenance) her katman için takip ediliyor" | ✅ **Evet** | `layer_validity` + `weakest_validity` |
| "4 gerçek rover platformunda platform duyarlılığı gösteriyoruz" | ✅ **Evet** | Projenin en özgün katkısı |
| "263 testle doğrulanmış bir implementasyon" | ✅ **Evet** | Bağımsız olarak koşuldu |
| "ROS 2 ile entegre" | ✅ **Evet** | Action server + grid_map publisher |
| "Termal katmanımız Hayne (2017) 1-D regolit difüzyon modeline dayanıyor" | 🟡 **Teknik olarak evet, ama** | Model doğru çağrılıyor; ancak `nanmax` seçimi yüzünden çıktı eğimin monoton fonksiyonuna çöküyor (ρ=0.98) ve işareti ters. **Bu cümleyi kurarken H4'ü de söyleyin** |
| "AHP ağırlıkları kullanıyoruz" | ❌ **Hayır** | İkili karşılaştırma matrisi ve tutarlılık oranı yok. "Gradyan-normalize uzman ağırlıkları" deyin |
| "Enerji tüketimini simüle ediyoruz" | 🟡 **Dikkatli** | İki farklı enerji modeli var (§2.3); `simulate_path`'teki anlık yeniden şarj fiziksel değil |
| "Gerçek NASA ölçüm verisi kullanıyoruz" | 🟡 **Kısmen** | DEM gerçek (MEASURED); termal MODEL, gölge DERIVED. Diviner/LOLA yok |
| "Modelimiz doğrulanmıştır" | ❌ **Hayır** | Validation sıfır |
| "Otonom navigasyon sistemi" | ❌ **Hayır** | README'de zaten doğru şekilde reddedilmiş |
| "Belirsizlik nicelenmiştir" | ❌ **Hayır** | — |

---

## 7. Öncelikli eylem sırası (analiz sonucu — bu belgede hiçbir kod değiştirilmedi)

Etki/maliyet oranına göre sıralanmış:

| # | İş | Neden ilk | Tahmini maliyet |
|---|---|---|---|
| **1** | **Termal `nanmax` → planlama-uygun istatistik ayrımı** (§2.2) | Tek düzeltme 4 kriterin bağımsızlığını geri getirir, işaret hatasını kapatır ve nav2 baseline sonucunu düzeltir. **Projenin en yüksek etkili tek değişikliği** | LUT yeniden üretimi ~15-45 dk + kod |
| **2** | **Ablasyon çalışması (A/B/C/D)** | Validation'ın en ucuz vekili. Ayrıca #1'in etkisini *ölçülebilir* kılar | 1-2 gün |
| **3** | **`simulation.py` ↔ `cost_engine.py` enerji modeli birleştirme** (§2.3) | "Enerji tüketimimiz X Wh" iddiasını tek anlamlı hale getirir | Yarım gün |
| **4** | "AHP" etiketini düzelt veya gerçek AHP matrisini yaz | Hakem/jüri sorusu; etiketi düzeltmek 5 dakika | 5 dk – 2 saat |
| **5** | Diviner termal ürününü indirip heat1d LUT'una karşı RMSE ölçmek | Validation'ı 1/5'ten 3/5'e çıkarır | 3-5 gün |
| **6** | Ufuk menzili sınırlamasını belgele (§2.3) veya pencereyi genişlet | Dürüstlük; `shadow_ratio`'nun DERIVED etiketi teknik olarak doğru ama eksik ufuk üzerinden hesaplanmış | 1 saat (belge) |
| **7** | `compute_cost_grid` vektörleştirme | Performans, doğruluk değil | Yarım gün |

**#1 ve #2 birlikte yapıldığında** skorkartın 2. boyutu (fizik) 3→4, 4. boyutu (validation) 1→3'e çıkar ⇒ toplam **33/50 → 37/50** ve TRL 4 iddiası savunulabilir hale gelir.

---

## 8. Sonuç

**Akademik olgunluk:** Bu backend, mühendislik disiplini bakımından **lisansüstü seviyenin üst çeyreğindedir** ve öz-denetim kültürü bakımından yayınlanmış birçok çalışmanın üzerindedir. `pathfinder_4d.py`'deki admissibility argümanı, `cost_cube.py`'deki invariant probing, `thermal_model.py`'deki API forensiği ve `weakest_validity()` provenance zinciri — bunların hiçbiri bir hackathon prototipinden beklenmez.

**Fiziksel doğruluk:** Geometri (SPICE, ufuk, eğrilik, CRS yakınsaması) ve enerji (`m·g/F_net`) tarafı **doğru ve türetilebilirdir**. Termal taraf ise **ölçülebilir biçimde kırıktır** (ρ=0.9845, ters işaret) ve bu kırıklık nav2 baseline sonucunda somut bir semptom üretmiştir. Ekip bunu kendisi bulmuş, ölçmüş ve düzeltmemeyi *gerekçeli* bir karar olarak belgelemiştir — bu, hatanın kendisinden daha önemli bir olgunluk göstergesidir.

**Sektörel konum:** Uçmuş sistemlerin (Yutu-2, Pragyan) rakibi değil, Pragyan'ın yer-döngülü modelinin yazılım karşılığıdır — ve bu konumlandırma gerçektir. Akademik rakiplerin (Lamarre vd., Risk-Aware Coverage) gerisinde olduğu tek eksen **belirsizlik ve doğrulama**; ilerde olduğu eksenler **platform duyarlılığı, provenance ve açıklanabilirliktir**.

**Tek cümlelik kapanış:** *Bu proje, "doğru şeyi ölçmediğini bilen ve bunu yazan" bir projedir — ve bilimsel olgunluğun tanımı büyük ölçüde budur. Kalan iş, ölçmeye başlamaktır.*

---

## Ek: Analizin doğrulama tabanı

```
pytest (backend/)                       263 passed, 3 warnings in 423.50s
Spearman(slope, thermal)                0.9845      [bağımsız, thermal_grid.npy'den]
Spearman(slope, shadow_ratio)           0.1504
Spearman(shadow_ratio, thermal)         0.1360
mu_coeff = m*g/F_net                    4/4 rover birebir doğrulandı
ağırlık toplamı                         1.000 ✅
Saaty matrisi / tutarlılık oranı        grep ile arandı, bulunamadı ❌
traversable oranı (sevk edilen grid)    0.8241
yalnızca termal yüzünden bloklanan      %0.060
backend kod boyutu                      4.786 satır, 23 modül
git commit sayısı                       114
```
