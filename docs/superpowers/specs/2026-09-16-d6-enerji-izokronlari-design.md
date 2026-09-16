# D6 — Enerji-erişilebilirlik izokronları (tasarım)

**Tarih:** 16 Eylül 2026 · **Dal:** `tuna/backendEnhance` · **Durum:** uygulandı

## 1. Soru

`/api/plan-4d` “A'dan B'ye gidebilir miyim?” sorusunu cevaplıyor. Operatörün ondan
önceki sorusu şu: **“şu an, bu şarjla, buradan nereye kadar gidebilirim?”** — ve gölge
hareket ettiğine göre **“altı saat sonra çıksam nereye kadar gidebilirdim?”**

Bu bir erişilebilirlik problemidir, en kısa yol problemi değil. Fark kozmetik değil.

## 2. Araştırma belgesinin algoritma öncülü yanlış — ölçüldü

Belge D6 için şunu yazıyor: “`cost_cube` üzerinde çok-kaynaklı Dijkstra (enerji
bütçeli)”. Bu depoda çalışmaz ve gerekçe ölçülmüştür, tartışılmamıştır.

`cost_engine.move_battery_drain_wh` **işaretlidir**; kendi docstring'i söylüyor:
“Positive drains, negative charges … NOT floored at zero”. Düz ve aydınlık bir hücrede
LPR-1'in paneli sürüşten fazla üretir: metre başına −0,245 Wh. Düz hücrede başabaş
gölge oranı **0,3908** (NASA VIPER **0,2400**).

Site11'de coarsen 4, 48 dilim, sekiz yön (tam tablo raporda):

| epoch | t0'da aydınlık | negatif sürüş kenarı | negatif bekleme kenarı |
|---|---:|---|---|
| 2026-09-01 | %0,0 | 0 / 3 734 496 (%0,00) | 0 / 547 296 (%0,0) |
| 2026-09-05 | %48,3 | **1 080 811 / 3 734 496 (%28,94)**, en kötü −5,735 Wh | **295 017 / 547 296 (%53,9)** |
| 2026-09-21 | %35,2 | 683 208 (%18,29) | 217 488 (%39,7) |

**Tuzak burada:** tamamen karanlık bir epoch'ta sayı sıfır. Test paketinin çoğunun
kullandığı 2026-09-01 tam olarak öyle bir epoch. Bir Dijkstra orada doğru görünür,
aydınlık bir epoch'ta sessizce yanlış cevap verir ve hiçbir test kırmızıya dönmez.

Tabanlanmış ikiz `net_energy_per_metre_wh` de kullanılamaz. `max(0, …)` olduğu için
“güneşte sürerek menzil kazanamazsın” der; bu modelde bu **yanlıştır** ve yalnızca tek
yönde yanlıştır — muhafazakârlığın en kötü türü, çünkü izokronu tek yönlü daraltır ve
kimse fark etmez.

## 3. Birinci kaynak gerçekten okundu — ve belgeyi düzeltti

Tompkins, *Mission-Directed Path Planning for Planetary Rover Exploration* (CMU 2005,
TEMPEST), 192 sayfa, yayımlanmış PDF'ten tam metin çıkarılarak 16 Eylül 2026'da okundu.

Bulunanlar:

1. **Tezde “Dijkstra” kelimesi hiç geçmiyor** (192 sayfada 0 kez). TEMPEST'in arayıcısı
   **ISE**: “In an initial search, ISE results are similar to those from A*. … ISE, like
   D*, can repair the search graph in the area of the changes.” Belgenin Tompkins'i
   Dijkstra için yöntem kaynağı göstermesi yanlış.
2. **§3.1.5** şarj edilebilir batarya enerjisini açıkça **NON-MONOTONIC RESOURCE
   PARAMETER** olarak sınıflıyor — yani bir DPARMS **durum değişkeni**, maliyet değil:
   “Rechargeable energy, thermal load, available computer memory or communications
   bandwidth are all examples of non-monotonic resources.” Bu, enerjiyi amaç
   fonksiyonuna koymanın tam tersidir.
3. **§3.1.7:** “Non-monotonic parameters cannot be optimized directly using the
   incremental search approach. … In cases where negative cost arcs are consistently
   reachable, the search will never terminate.” Dikkat: bu cümle **kendi artımlı
   sezgisel aramasıyla** ilgilidir, Dijkstra'nın label-setting optimalliğiyle değil.
   Negatif kenarda Dijkstra'nın bozulması **bizim** iddiamızdır, Tompkins'in değil ve
   modül bunu ona söyletmez.
4. **Doyum kuralı (eş. 3-1/3-2):** `e_{i+1} = max(e_i + Δe, e_min)`, `e_{i+1} > e_max`
   ise reddet. Bu, `pathfinder_4d.astar_4d`'in ileri yönde zaten yaptığının aynadaki
   hâli: `min(e_cap_wh, battery_wh − drain_wh)` artı rezerv tabanı.
5. **Tez hiçbir uzamsal erişilebilirlik haritası hesaplamıyor.** “Reachable State Space”
   (Şek. 4-6b) mesafe–zaman düzleminde maksimum hız doğrusuyla sınırlı bir kama, yani
   skaler bir varış-zamanı aralığı. “isochron” kelimesi 0 kez geçiyor. Yani buradaki
   izokron Tompkins'in bir uygulaması değildir.

İkinci kaynak (arXiv 2509.15062) doğrulandı: belgenin “softplus ceza + SCP + NMPC”
tarifi **doğru** (§III-E softplus hinge, §III-F augmented-Lagrangian SCP, §IV NMPC).
Belgenin söylemediği şey, makalenin hiç erişilebilirlik kümesi hesaplamadığı — yani D6
için bağlamdır, yöntem değil. Sayıları (198,9 W / 200 W = %0,55; rakipler 235,8 W ve
234,7 W) `REACHABILITY_QUOTED` içinde.

Üçüncü kaynak (Sakayori & Ishigami 2021) **doğrulanamadı**. Belge ona “Fast Marching ile
enerji haritaları” atfediyor; tam metin ödeme duvarının arkasında (tandfonline ve
ResearchGate HTTP 403) ve indekslenmiş özeti hiçbir Fast Marching'den söz etmiyor —
dinamik simülasyondan yaklaşıklanan bir güç tüketimi modeli ve panelin üretimi anlatıyor.
D6 onu yöntem kaynağı olarak göstermiyor ve algoritması hakkında hiçbir şey iddia
etmiyor.

Bu dört düzeltme `REACHABILITY_CORRECTIONS` içinde, okunma tarihleriyle birlikte.

## 4. Seçilen yöntem

**İleri, zaman-genişletilmiş erişilebilirlik sweep'i.** Dijkstra değil, `survival.py`'ın
(x, y, SOC) binlenmiş değer iterasyonu da değil.

Durum: `(dilim t, kaba blok (r, c))`. Blok başına iki alan yayılır:

* `best_soc_wh` — o blokta o dilimde ulaşılabilecek **en yüksek** şarj;
* `min_dark_h` — o blokta o dilimde ulaşılabilecek **en düşük** sürekli karanlık saati.

Bir `(dilim, blok)` **canlı**dır ⟺ birincisi rezervin üstünde **ve** ikincisi dayanımın
altında — `astar_4d.envelope_after`'ın uyguladığı iki zarf kuralı. Yayılım yalnızca canlı
durumlardan, dilimler artan sırada taranarak.

Kenarlar birebir `astar_4d`'inkiler (`survival.direction_tables`: aynı kapılar, aynı
`edge_travel_time_s_array`) artı WAIT:

```
MOVE: dt = max(1, ceil(travel_h / slice_hours)); arrival = t + dt; arrival >= n_slices ise red
      mean_e = 0.5*(shadow[t,r,c] + shadow[arrival,nr,nc])
      drain  = (traction_w + (p_idle + mean_e*shadow_extra) - p_solar*(1-mean_e)) * travel_h
      new_b  = min(e_cap_wh, b - drain);  new_b < reserve_wh ise red
      karanlık: e_arr >= 0.5 ise dark + travel_h*e_arr, değilse 0
WAIT: drain = (p_idle + e*shadow_extra - p_solar*(1-e)) * slice_hours,  e = shadow[t,r,c]
```

### 4.1 Kesinlik (alan başına)

Her kenar saati **en az bir dilim** ilerletir, dolayısıyla zaman-genişletilmiş graf `t`
ile sıralı bir **DAG**'dır. `b ↦ min(cap, b − drain)` geçişi `b`'de azalmayandır ve
`b' ≥ reserve` testi `b`'de monotondur; karanlık geçişi de gelen karanlıkta azalmayandır
(sıfıra sıfırlama bir sabittir) ve testi monotondur. O hâlde dilim sırasında ileri bir
tarama, alan başına **kesin**dir: öncelik kuyruğu yok, SOC bini yok, sabit nokta yok.
**Dijkstra'yı bozan negatif kenarlar tam da bu yüzden zararsızdır — taramanın bozulacak
bir öncelik sırası yoktur.**

Birim testi bunu **kaba kuvvetle** doğruluyor: küçük bir gridde bütün etiket dizileri
sayılıyor ve sweep'in alan optimumları birebir tutuyor.

### 4.2 İçerme (birlikte)

İki alan **bağımsız** optimize edilir: bir bloğun şarjı maksimize eden öncülü ile
karanlığı minimize eden öncülü aynı blok olmak zorunda değildir. Canlı küme bu yüzden bir
**gevşetmedir**. Dilimler üzerinden tümevarımla: planlayıcının gerçekten uçabileceği her
rota için her adımda `best_soc ≥ o rotanın şarjı` ve `min_dark ≤ o rotanın karanlığı`,
dolayısıyla gerçek bir etiket canlıyken gevşetilmiş durum da canlıdır. Yani:

> canlı küme, aynı coarsen, aynı dilim, aynı epoch ve aynı ufukta
> `/api/plan-4d`'in kabul edeceğini **içerir**.

Güvenli yön tek yöndür: **kümenin dışındaki bir blok, bu enerji modelinin “oraya
gidemezsin” dediği bloktur.** İçindeki bir blok adaydır, söz değildir.

Gerçek grid testi bunu `astar_4d`'i örneklenmiş bloklarda gerçekten koşarak doğruluyor;
rapor gevşekliği ölçüyor (11/11 = %100, ve planlayıcının varış dilimi her satırda
sweep'in ilk diliminden büyük ya da eşit).

### 4.3 İçerme hangi yapılandırmaya karşı

Bu ayrım bilgiçlik değil. `astar_4d`'in opsiyonel anahtarları ikiye ayrılır:

* **KISITLAR** (`require_earth_visibility`, `require_safe_haven`,
  `require_continuous_illumination`, `require_thermal_dwell`,
  `max_failure_probability`) planlayıcının kabul ettiğini yalnızca **daraltır**;
  kapalı bırakmak sweep'i üst sınır olarak tutar.
* **YETENEKLER** (`allow_hibernate`, `battery_model`, `heater_power_model`,
  `panel_model`) **genişletebilir**. Hibernasyon üçüncü bir kenar ailesidir:
  `p_hibernate_w` ile boşalır ve uyanışta karanlık saatini **sıfırlar**
  (`pathfinder_4d` satır 1625). `allow_hibernate=True` ile koşan bir plan bu kümenin
  dışına meşru biçimde çıkabilir — ve o zaman negatif iddia GÜVENSİZ yönde yanlış olur.

Bu yüzden iddia **yapılandırmayla birlikte** kurulur, yanıt `planner_configuration` ile
onu yayımlar ve sweep yeteneklerin hiçbirini modellemez.

### 4.4 Neden 422: rezervin altında başlamak

`astar_4d`, rezervin altında biten bir geçişe **ŞARJ EDİYORSA** izin verir
(`new_battery < battery_wh`). Bu istisna 4.1'in dayandığı monotonluğu kırar. Uç,
`initial_soc_pct < soc_min_pct` isteğini reddeder; `battery_model="constant"` altında
(bu uç ona sabitlenmiştir) rezervin üstünden başlayan bir geçiş rezervin altına ancak
boşalarak inebilir, yani istisna kanıtlanabilir biçimde hiç tetiklenmez ve iki kural
birebir çakışır.

## 5. Neler hesaplanmıyor

* **Maliyet küpü yok**, dolayısıyla ağırlık vektörü okunmuyor ve `astar_4d`'in
  `cost_infinite` kapısı replay edilmiyor. Bu modelde erişilebilirliği sert kapılar ve
  batarya belirler; kriter ağırlıkları yalnızca bir sürüşün ne kadar **tatsız** olduğunu
  fiyatlar. İstek gövdesinde `weights` alanı **yok** — kabul edip yok saymak reddetmekten
  kötü olurdu. Replay edilmeyen altı kapı `gates_not_replayed` içinde, her biri hangi
  yöne ittiğiyle birlikte.
* **Yumuşatma yok, `skimage` yok.** Belge `skimage.measure.find_contours` öneriyor;
  scikit-image bu makinede kurulu (0.26.0) ama `backend/requirements.txt`'te **yok** —
  yani yeni bir bağımlılık olurdu. Bantlar blok başına bir bant indisi artı her bandın
  sınır bloklarıyla, yalnızca numpy ile yayımlanır. **Konvansiyon:** sınır, kaba blok
  kafesinin merdivenidir; yumuşatmak modelin hiç değerlendirmediği araziden geçen bir
  hat çizerdi. Bantlar zamanda da kuantize: `band_time_quantum_h = slice_hours`.
* **Belirsizlik yayılmıyor.** Kayma, DEM hatası, batarya sıcaklığı ve konumlandırma
  kayması bu depoda **modelleniyor** ve burada yayılmıyor; `uncertainty_not_propagated`
  her birini nerede modellendiğiyle ve hangi yöne ittiğiyle adlandırıyor. Sınırı ne kadar
  oynattıklarına dair **sayı yayımlanmıyor**, çünkü ölçülmedi.

## 6. Var olanı yeniden yazmadıklarımız

* `survival.direction_tables` — sekiz hamle, aynı kapılar, aynı süre. Sweep kendi kenar
  tablosunu kurmuyor.
* `cost_cube.coarsen_grid` / `coarsen_traversable` / `auto_slice_hours` — kaba geometri
  ve dilim uzunluğu `/api/plan-4d` ile aynı çağrıdan.
* `illumination_series.build_shadow_series` — gölge serisi, parça parça çağrılıp hemen
  kabalaştırılıyor.
* `main._coarse_geometry`, `main._validate_start_goal` — 422'ler birebir aynı yerden.

`safe_haven._gated_edges` + `time_to_safe_haven_hours` **kullanılmadı** ve sebebi şu: o
makine kenar ağırlığı SAAT olan bir grafta `scipy.sparse.csgraph.dijkstra(min_only=True)`
koşuyor. Saat pozitiftir, Wh değildir (§2). Aynı iskelet, farklı ağırlık — ve farklı olan
şey tam olarak Dijkstra'yı geçersiz kılan şey.

`survival.py`'ın (x, y, SOC) değer iterasyonu da kullanılmadı: o geriye doğru, sabit bir
zaman ızgarasında, arıza modeliyle ve SOC **binleriyle** çalışıyor. D6'nın sorusu ileri,
arızasız ve binsiz olduğu için ondan hem daha kesin hem daha ucuz.

## 7. Uç

`POST /api/reachable` — sadece ekleme. Girdi: başlangıç hücresi, `rover_id`, **zorunlu**
`start_utc`, ufuk, dilim, coarsen, başlangıç SOC, bant kenarları, `later_hours`, duruş
ufku/adımı. Çıktı: erişilebilir maske ve büyüme eğrisi, izokron bantları ve merdiven
sınırları, blok başına duruş saatleri ve hangi saatin bağladığı, “N saat sonra”
karşılaştırması, `energy_binds` + `refusals`, `conservatism`, `gates_*`,
`planner_configuration`, `claim`/`scope`/`references`/`corrections`/`quoted`.

`start_utc` **zorunlu** (`/api/plan-4d`'in aksine): epoch olmadan `build_shadow_series`
uzun dönem gölge **kesrine** düşer — bir iklimoloji, gökyüzü değil. Onun üstüne çizilen
izokron araziyi ve bataryayı ölçer ama bugünün haritası gibi görünür, ve “N saat sonra”
farkı **tam olarak sıfır** çıkar. `/api/plan-4d` statik seriye düşebilir çünkü yine de
bir rota döndürür; burada geri düşülecek dürüst bir mod yok.

## 8. Bit-eşitlik

D6 saf ekleme. Kilit LPR-1'in checked-in v5 maliyet-gridi SHA-256'sı
`55e1bb3cd3b9fb93403140b283cfa38fef8b93836a28512bc95f38db5ed893db` ve `COST_MODEL_ID`
`…_v5`'te kalıyor. `nasa_viper` özeti 4af6989'dan beri bayat, bayat kilide iddia
bağlanmaz — testin yanında yazılı.

---

# Uygulama sırasında bulunanlar ve ölçümler

## B1. Düşmanca inceleme (tek geçiş, dört mercek) gerçek kusurlar buldu

**B1.1 — İçerme iddiası `allow_hibernate` karşısında yanlıştı.** İlk taslak “her
opsiyonel kısıt kapalı” diyordu. Hibernasyon bir kısıt değil, bir **kenar ailesidir**;
kapatmak yeteneği kaldırır, kısıtlamayı değil. Yutu-2'de (`h_max_shadow_h = 2 h`,
`p_hibernate_w = 5 W`, `p_shadow_w = 60 W`) karanlık saati dormansi boyunca on ikide bir
hızla işler ve uyanışta sıfırlanır; hibernasyonlu bir plan sweep'in “erişilemez” dediği
bloğa meşru biçimde varır. Düzeltme: iddia yapılandırmayla kuruldu, `PLANNER_CONFIGURATION`
yanıtta yayımlanıyor, §4.3 yazıldı.

**B1.2 — Dayanım testinde `+1e-9` payı eksikti.** `astar_4d` yalnızca
`new_dark > endurance + 1e-9` iken reddediyor. Payı olmayan bir sweep,
`h_max + 5e-10`'da planlayıcının tuttuğu bir durumu öldürürdü — kıl payı, ama negatif
iddiayı yanlış yapan yönde. `ENDURANCE_SLACK_H = 1e-9` eklendi, testle kilitlendi.

**B1.3 — `cost_engine.move_battery_drain_wh` planlayıcının satır içi ifadesiyle
bit-eşit değil.** İkisi cebirsel olarak aynı, IEEE-754'te değil: o fonksiyon çekişi
`gross_energy_per_metre_wh` üzerinden (metre başına süre × mesafe) geçiriyor ve güneş
terimini çarpımdan **sonra** çıkarıyor; planlayıcı güçleri **önce** çıkarıp bir kez
çarpıyor. D6 planlayıcıyı içerdiğini iddia ettiği için planlayıcının ifadesini birebir
satır içine alıyor; test ikisinin farkını `pytest.approx` ile, planlayıcıyla eşitliği ise
`==` ile kontrol ediyor.

**B1.4 — `np.ceil(inf).astype(int64)` INT64_MIN verir.** `direction_tables` kapatılmış
kenarları `inf` ile dolduruyor; maskelenmeden tam sayıya çevrilirse `arrival = t + dt`
negatife düşer, gölge indisi sarmalar ve tarama **kapanmış bir dilime geriye yazar** —
kesinlik kanıtının dayandığı DAG sırasını bozarak, ve fark edecek bir öncelik kuyruğu
olmadan. Kod zaten `finite` maskesini önce uyguluyordu; artık `span < 1` için açık bir
`ValueError` ve maskeyi doğrulayan bir test de var.

**B1.5 — Blok başına SOC/duruş skalerleri gevşetmeyi kayıtsız devralıyordu.** Maske
“aday kümesi” diye dürüstçe etiketliyken, aynı satırdaki şarj ve duruş süresi ölçüm gibi
duruyordu — ve her zaman İYİMSER yönde. Düzeltme: yayımlanan alan adları `_upper` ile
bitiyor, `fields_are_independently_optimised: true` ve
`no_single_trajectory_realises_a_row` yanıtta, `CONSERVATISM` her alan için yönü
adlandırıyor.

**B1.6 — İki başlık alan ters yönde yanılıyor.** `reachable` fazla **büyük**
(gevşetme + replay edilmeyen kapılar), `earliest_hours` fazla **geç** (hamle başına bir
dilime kadar yukarı yuvarlama). Birbirlerini götürmezler, zıt operasyonel kararlara
işaret ederler. `conservatism` bloğu bunun için var.

**B1.7 — Statik seriyle izokron savunulamaz.** `build_shadow_series` her istisnayı
yutup uzun dönem gölge kesrini döndürüyor. O serinin üstünde “N saat sonra” farkı tam
sıfır çıkar ve bu, mümkün olan en güçlü yanlış iddiadır: “erişilebilir küme zamanla
sabittir”. Düzeltme: `start_utc` zorunlu, `time_varying` değilse 422.

## B2. Ödenmemiş rölanti — planlayıcıdan devralınan, ölçülen ve yayımlanan yanlılık

Bir hamle saati `ceil(travel_h / slice_hours)` **tam dilim** ilerletir ama gücü yalnızca
`travel_h` boyunca öder; aradaki fark hiç kimsenin ödemediği duvar saatidir. Bu
`astar_4d`'in kendi konvansiyonu ve D6 onu **kasten** devralıyor — kalanı ücretlendirmek
kümeyi planlayıcının gevşetmesi olmaktan çıkarırdı ve §4.2'deki içerme kanıtı düşerdi.
Ama yayımlanan her şarjı İYİMSER yapar, o yüzden büyüklüğü ölçülüp
`edges.unpaid_idle_mean_h` / `unpaid_idle_max_h` ile yayımlanıyor. Site11 LPR-1 coarsen 4:
hamle başına ortalama **0,0178 h**, en fazla **0,0359 h** (tam bir dilim).

## B3. Enerji her zaman bağlamıyor — ve yanıt bunu söylemek zorunda

En değerli inceleme bulgusu: kısa bir ufukta ve dolu bataryayla **hiçbir zarf kuralı
tetiklenmez**, sınır saatin kendisidir ve harita bir **kapılı mesafe dönüşümü**dür.
Bunu ima etmek yerine ölçmek gerekiyordu. Sweep artık `astar_4d`'in kendi reddetme
sözlüğüyle sayaç tutuyor ve `energy_binds` yayımlıyor.

Site11, LPR-1 gündüz (358, 494), coarsen 4, 2026-09-05:

| SOC | ufuk (h) | erişilebilir blok | `soc_floor` red | `horizon` red | enerji bağlıyor mu |
|---:|---:|---:|---:|---:|---|
| 1,00 | 3 | 2 086 | 0 | 34 580 | **hayır** |
| 1,00 | 12 | 11 156 | 0 | 214 733 | **hayır** |
| 0,50 | 6 | 6 950 | 16 111 | 120 639 | evet |
| 0,25 | 3 | **182** | 16 375 | 664 | evet |
| 0,25 | 12 | **182** | 18 900 | 0 | evet |

Bütçe eğrisi burada: tam şarjda sınır saat, çeyrek şarjda enerji — ve erişilebilir alan
11 156 bloktan 182'ye çöküyor (%98,4 düşüş), ufuk dört katına çıksa bile 182'de kalıyor.

## B4. Duruş saati sürüş ufkuyla sınırlanamaz

İlk sürüm duruş sürelerini sweep'in ufkunda kesiyordu. 3 saatlik bir ufukta Site11'de
erişilebilir **2 086 bloğun 2 086'sı** sansürlendi: dolu bataryayla LPR-1 onlarca saat
oturur. Duruşa kendi ekseni verildi — kendi ufku (varsayılan: yayımlanan dayanımın iki
katı) ve kendi, çok daha kaba adımı (varsayılan 0,5 h; sürüş dilimi 0,036 h olduğu için
100 saatlik bir duruş 2 785 tam dilim ederdi).

## B5. Yanlış saat bağlıyor — `time-to-0-SOC` tek başına yanıltıcı

Tam karanlıkta duran LPR-1 rezerve **66,7 h**'te, sıfıra **83,4 h**'te iner; ama
yayımlanan sürekli-karanlık dayanımı **50 h**'tir. Yani saf enerji sayısı, bu API'nin
geri kalanının görev başarısızlığı saydığı bir durumu tarif eder. Yayımlananlar:
`to_reserve`, `to_zero` **ve** `to_endurance`, artı işletme sayısı olarak
`hold_limit = min(rezerv, dayanım)` ve hangisinin bağladığını söyleyen
`hold_limited_by`. `to_zero` minimuma **dahil değil**: rezervin altında bu modelde hiç
geçiş yoktur.

## B6. Karanlık saati “saat” değil — gerçek gridde ölçüldü

`astar_4d`'in saati **pozlamayla ağırlıklıdır**: `dark += hours × exposure`. Pozlaması
0,5 olan bir blok saati yarı hızda harcar. Gerçek sonucu: dayanımın bağladığı bloklarda
duruş süresi **49,5 h ile 56,0 h** arasında çıkıyor, yayımlanan `h_max_shadow_h` ise
50 h. İlk yazdığım gerçek-grid testi “duruş ≤ 50 h” diye iddia ediyordu ve haklı olarak
düştü (56,0 ≰ 50,0); test düzeltildi ve artık ilişkiyi ters yönde — duvar saati
dayanımdan **kısa olamaz** — kilitliyor. Yanıt `scope` içinde saatin semantiğini
yazıyor.

## B7. Site11'de “N saat sonra” saat ölçeğinde hiçbir şey değiştirmiyor

6 ve 24 saatlik kaydırmalarda aydınlık blok oranı ölçülebilir biçimde değişiyor
(%48,30 → %48,00 → %47,89) ama erişilebilir kümede **tek blok bile** değişmiyor. Sebebi
fizik: kutupta aydınlanma ~708 saatlik sinodik döngüyle döner, bir gün döngünün %3'üdür.
Etki **gün** ölçeğinde geliyor:

| kaydırma | t0 aydınlık | t0+N aydınlık | şimdi | sonra | Jaccard |
|---:|---:|---:|---:|---:|---:|
| +6 h | %48,30 | %48,00 | 7 362 | 7 362 | 1,000 |
| +24 h | %48,30 | %47,89 | 7 362 | 7 362 | 1,000 |
| +96 h | %48,30 | %43,44 | 7 362 | 7 211 | 0,979 |
| +240 h | %48,30 | **%0,00** | 7 362 | **586** | **0,080** |
| (karanlıktan) +96 h | %0,00 | %48,30 | 586 | **7 362** | 0,080 |

Bu tabloyu yalnızca Jaccard sütunuyla yayımlamak “küme zamanla sabittir” gibi okunurdu —
ve bu, güneşin hiç modellenmediği durumdan ayırt edilemezdi. İki aydınlık sütunu tam
olarak o ayrımı yapmak için var: **gölge gerçekten hareket etti, küme hareket etmedi.**

## B8. VIPER'ın standart başlangıcı coarsen 4'te reddediliyor

`nasa_viper` (358, 494) ince hücrede geçilebilir ama coarsen 4'teki bloğu (89, 123)
geçilebilir **değil**: 15°'lik eğim sınırı bloğun muhafazakâr AND'ini düşürüyor. Bu bir
eksik değil, pencerenin gerçek bir özelliği. Uç 422 veriyor ve sebebini söylüyor; ölçüm
coarsen 2'de yapıldı (250×250, 36 354 geçilebilir blok, 7 376 erişilebilir). Gerçek grid
testi **hem** reddi hem de coarsen 2'deki cevabı kilitliyor.

## B9. “Bit-eşit” yanlış iddiaydı — kontrol ölçüldü

İlk yazdığım gerçek-grid testi `/api/plan` ve `/api/plan-4d` yanıtlarının sweep öncesi
ve sonrası **birebir aynı** olmasını istiyordu ve düştü. Geçiştirmeden önce **kontrol
koşuldu**: arada hiç D6 olmadan, iki özdeş çağrı zaten farklı çıkıyor.

* `/api/plan`: 2 yaprak — `astar_metrics.computation_time_ms` (109,1 ≠ 107,9) ve
  `corridor.corridor_id`.
* `/api/plan-4d`: 8 yaprak — altısı `illumination_corridor.timings_ms.*`, biri
  `metrics.computation_time_ms`, biri `thermal_dwell.dwell_model.compute_ms`.

Arada D6 varken **tam olarak aynı** yapraklar oynuyor, başkası oynamıyor. Test bu hâle
getirildi: kontrolü kendisi ölçüyor, sonra sweep'li farkın kontrol kümesinin **alt
kümesi** olmasını istiyor ve dışına çıkan yaprağı adıyla rapor ediyor. Ayrıca üçüncü bir
test kontrolün tolere ettiği her yaprağın gerçekten bir milisaniye sayacı ya da bir
çağrı kimliği olduğunu doğruluyor. Kronometreye takılan bir test değil, gerçek bir
regresyonu yakalayan bir test.

## B10. Ölçülen maliyet ve konan tavanlar

Site11 coarsen 4 (125×125), otomatik dilim 0,03590 h:

| ufuk | dilim | sweep süresi |
|---:|---:|---:|
| 3 h | 84 | 2,0 s |
| 6 h | 168 | 4,4 s |
| 12 h | 335 | 9,3 s |
| 24 h | 669 | 19,0 s |

Yani kenar-grubu adımı başına ~0,31 ms. Tavanlar buradan boyutlandı:

* `MAX_REACHABLE_SLICES = 1000` (planlayıcının kendi tavanı);
* `MAX_REACHABLE_BLOCKS = 70 000` (coarsen 2'ye yer bırakır, ince gridi reddeder);
* `MAX_REACHABLE_CUBE_BYTES = 512 MiB`, `later_hours` ile iki sweep üzerinden;
* `MAX_REACHABLE_GROUP_STEPS = 150 000` ≈ tek sweep için ~45 s. Bu tavan **işi**
  sınırlar, çarpanlarından birini değil: bir hamle `ceil(travel_h / slice_hours)` dilim
  ettiği için çok kısa bir `slice_hours` grup sayısını çarpar ve dilim/blok/bayt
  cinsinden yazılmış hiçbir tavana takılmaz. Otomatik dilimde Site11'de 92 grup var
  (14 farklı `dt`), `slice_hours = 1e-4`'te binlerce;
* yayımlanan blok gridleri `MAX_LAYER_CELLS = 65 536` ile sınırlı — `/api/layers`'ın
  zaten kullandığı tavan, aynı “işte sığan coarsen” mesajıyla.

Gölge küpü `SHADOW_CHUNK_SLICES = 64` parça parça kuruluyor ve her parça hemen
kabalaştırılıyor, yani ince çalışma kümesi ufukla büyümüyor — 500×500 float64 bir
anlık görüntü 2 MB, 669 dilim tek seferde 1,3 GB ederdi.

## B11. Test tabanı

64 yeni test: 30 birim (`test_reachability.py`) + 18 API (`test_reachability_api.py`) +
16 skip-korumalı gerçek grid (`test_reachability_real_grid.py`). Hepsi yeşil.
`ruff check backend/app` 12'de kalıyor (taban), `reachability.py` 0 veriyor.
