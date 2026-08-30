# Backend bağımsız denetimi — tur 3

**Tarih:** 2026-08-30
**Dal:** `backend/physics`
**Kapsam:** `backend/app`, `scripts`, `lunapath_ros`, `lunapath/src`
**Yöntem:** Backend'in tamamı, önceki turların bulgu listelerine bakılmadan sıfırdan
okundu. Şüphelenilen her yapısal bulgu, `lunapath/data/processed/` altındaki
500×500 / 5 m-px üretim gridi üzerinde salt-okunur ölçümle doğrulandı ya da atıldı.

**Sonuç:** 35 bulgu — 4 yüksek, 12 orta, 19 düşük. **Tamamı düzeltildi.**
Her bulgu için davranışı sabitleyen bir regresyon testi yazıldı
(`backend/test_review3_fixes.py`) ve kapsamsız kalan altı modüle kendi test
dosyası eklendi.

Ayrıntılı, ölçümlü sürüm (paylaşılabilir sayfa):
<https://claude.ai/code/artifact/38c193e6-227b-4aee-b9de-efcab211ac9a>

---

## Denetimin ayırt edici bulgusu

En ağır dört bulgu **kod hatası değil**. Kod temiz, testli ve dürüstçe
etiketlenmiş. Sorun, *belgelenen sistem ile çalışan sistemin aynı sistem
olmaması*: spesifikasyonun vaat ettiği kısıtlar üretimde uygulanmıyordu ve dört
kriterli karar motorunun kriterleri birbirinden bağımsız değildi. Bunlar bir
dosyayı açıp görülebilecek şeyler değil; ancak ölçülerek görülüyor.

---

## Yüksek

### H-1 — Belgelenen maliyet fonksiyonu çalışmıyordu

`docs/lunapath_referans_belgesi_2.md:105` maliyet formülünü "4 penalty
bileşeninin AHP-ağırlıklı toplamı **artı log-barrier cezası**" olarak tanımlıyor
ve özet tabloda teslim edilmiş sayıyor. `cost_engine.total_edge_cost` ve
`log_barrier_penalty` üretimde hiç çağrılmıyordu. Sonuç: yanal eğim (devrilme)
limiti, SOC tabanı ve iç sıcaklık zarfı üründe hiçbir yerde kontrol edilmiyordu.
`slope_lateral_max_deg` ve `soc_min_pct` tüm kod tabanında birer kez geçiyordu —
o ölü fonksiyonun içinde.

**Düzeltme.** Barrier terimleri üç yerde çalışıyor:

| Terim | Nerede | Neden |
|---|---|---|
| `theta_along` | `pathfinder._astar_core`, her kenarda | Kenarın kendi geometrisi |
| `theta_lateral` | `pathfinder._astar_core`, her kenarda | Devrilme limiti seyahat yönüne bağlı |
| `T_inner` | `pathfinder._thermal_barrier_grid`, hücre başına | Zamanla değişmiyor |
| `soc` | `simulation.simulate_path` | Yol-bağımlı; statik grid değerlendiremez |

Termal sınırlar sabit −20/+95 yerine rover'ın kendi zarfına ve
`THERMAL_MIN_TRAVERSABLE_C`'ye çapalandı: **ölçüm — belgedeki sabitler bu termal
modelin ürettiği aralıkta gridin %36,2'sini sonsuz maliyete atıyordu.** Bölünme
spesifikasyona da yazıldı. `inner_to_surface` tersinir olmadığı için barrier her
geçerli ön-görüntüde değerlendirilip **en kötüsü** alınıyor.

### H-2 — Geçilebilirlik kapısı ile sürülen kenar farklı eğim tanımı kullanıyordu

`traversability` `np.gradient` eğimini kapı olarak kullanıyor (merkezi fark ⇒
efektif 10 m taban ⇒ yumuşatılmış); planlayıcı ise 1 hücrelik adımlarla
ilerliyor.

**Ölçüm (önce):** her iki ucu geçilebilir işaretli 920 kardinal komşu çiftinin
adım eğimi 25°'yi aşıyordu (yalnız kardinal, yani alt sınır). Varsayılan rota
25,08° raporluyordu; `w_thermal=2.0` ile **27,10°** — API'nin ve
`Corridor.max_slope_deg`'in güvenlik tavanı olarak yayınladığı limitin üstünde.

**Düzeltme.** Her kenarda gerçek adım eğimi yükseklikten hesaplanıp reddediliyor;
gradyan seyahat yönüne dik bileşenine ayrıştırılıp yanal limit uygulanıyor.
Metrikler `max_segment_slope_deg` / `max_cell_slope_deg` olarak ayrıldı.

**Ölçüm (sonra):** varsayılan rota 24,69°; `w_thermal=2.0` de 24,69°.

### H-3 — Üretim termal gridi aydınlanma bilgisi taşımıyordu

`Heat1DModel` sabit enlemde bir (13 eğim × 16 bakı) lookup tablosu.

| | önce | sonra |
|---|---|---|
| farklı sıcaklık değeri | 165 / 250 000 | 5 252 |
| `corr(thermal, slope)` | +0,977 | +0,932 |
| `corr(thermal, shadow_ratio)` | +0,027 | **−0,246** |
| kalıcı gölge hücrelerinin sıcaklığı | −156,7 … **+42,6 °C** | −183,1 °C |
| termal yüzünden bloke | 150 hücre (%0,06) | 1 866 |
| geçilebilirlik | %82,4 | %81,7 |

**Düzeltme.** Stefan–Boltzmann dördüncü-kuvvet harmanı:
`T_eff = (f·T_güneşli⁴ + (1−f)·T_PSR⁴)^¼`, PSR tabanı 90 K (Diviner'ın güney
kutup soğuk tuzak yıllık maksimum bandının ortası, Paige ve ark. 2010). Hem P1
hattına hem yükleyiciye bağlandı; validity `weakest_validity` ile MODEL → DERIVED.

### H-4 — Dört AHP kriterinden ikisi aynı değişkendi

`f_slope(θ)` ve `f_energy_cell(θ)` yalnızca eğimi okuyordu.

**Ölçüm (önce):** `spearman(f_slope, f_energy_cell) = 1,000000`. Yani
`w_slope + w_energy = 0,668`'lik ağırlık tek bir sıralamayı ifade ediyordu;
`w_energy` maliyeti ölçekleyebiliyor ama iki hücreyi asla yeniden
sıralayamıyordu.

**Düzeltme.** Enerji kriteri artık *bataryanın kaybettiği net enerjiyi* ölçüyor:
çekiş + housekeeping − hücrenin sunduğu güneş girdisi. Düz ve aydınlık bir hücre
bataryaya hiçbir şeye mal olmuyor; düz ve karanlık olan en kötü durumun %39'una.

**Ölçüm (sonra):** `spearman = 0,955`, `corr(f_energy, shadow) = +0,318`.
`COST_MODEL_ID` → v3.

---

## Orta

| # | Bulgu | Düzeltme |
|---|---|---|
| M-1 | 4-B planlayıcıda zamanla değişen fizik yoktu (`[base_shadow] * n_slices`) | `app/illumination_series.py` + `scripts/build_horizon_cache.py`; yanıtta `shadow_model.time_varying` |
| M-2 | WAIT kenarında zaman terimi yoktu; aydınlıkta maliyet tam 0,0 | WAIT artık `dt × (1 + …)`; MOVE ile aynı birim |
| M-3 | Ufuk en kısa hamle sayısına göre boyutlanıp fazlası sessizce kırpılıyordu | `horizon_truncated` / `edges_dropped_at_horizon` |
| M-4 | `slip_accumulation` slip ölçmüyordu (ROS'ta iki taraf da aynı kestiriciden) | Yalnız `dead_reckoning` için çalışıyor; diğerleri nedeniyle `skipped` |
| M-5 | Sıfır kovaryanslı Odometry "mükemmel kesinlik" oluyordu | Sıfır matris de "bilinmiyor"; fallback yoksa reddediliyor |
| M-6 | İki planlayıcı farklı amaç fonksiyonu optimize ediyor, alanlar benzer adlı | `cost_units`: `weighted_metres` / `weighted_hours` |
| M-7 | Görev profili kısıtları yayınlanıp hiç uygulanmıyordu | `astar` `max_slope_deg`'i uyguluyor; `constraints_applied` raporlanıyor |
| M-8 | Yedi rover alanı yayınlanıp hiç okunmuyordu | Dördü bağlandı; kalanı `declared_only` altında ayrıldı |
| M-9 | Simülasyon ve maliyet motoru çelişen iki fizik modeli (20°'de %47 fark) | Simülasyon `cost_engine`'i çağırıyor; parçalı tablo silindi |
| M-10 | SOC tabanı yok sayılıyor, şarj süresi sınırsız (~618 yıl mümkün) | Rezervde şarj, bir ay günüyle sınırlı, aşılırsa `stranded` + kesme |
| M-11 | `sun > 0` tabanı meşru negatif horizonları atıyordu | Taban yalnız nöbetçi hücrelere uygulanıyor |
| M-12 | `clearance_map` harita kenarını açık arazi sayıyordu | Maske geçilemez halkayla dolduruluyor |

---

## Düşük

L-1 NaN eğim skaler formda 0,0 (fail-open) · L-2 nodata filtrelemeden sonra
maskeleniyordu · L-3 pencere-göreli termal normalizasyon · L-4 sentetik modelde
"güneş grid kuzeyinden" varsayımı · L-5 yeniden hesaplanan grid bayat damgalanıyordu ·
L-6 diskteki artefaktlar kodla uyumsuz · L-7 serializer fallback'i var olmayan bir
pencereyi tarif ediyordu · L-8 replan eşikleri rover'dan bağımsız · L-9 lokalizasyon
1σ ile karşılaştırıyordu · L-10 `slip_accumulation` tetikleyici sözlüğünde yoktu ·
L-11 güvenlik anahtarı `/25.0` sabitliyordu · L-12 endpoint'ler farklı hata sözleşmesi ·
L-13 `/api/layers` yanıt boyutu sınırsız · L-14 `pydantic` pinlenmemiş · L-15
`lidar_odometry` drift satırı yok · L-16 tek koridor slotu yarışıyor · L-17 SPICE
kernel önbelleği bayatlayabilir · L-18 `along_track_m` gereksiz O(n) · L-19 altı
modülün kendi testi yok.

Hepsi düzeltildi; ayrıntılar `test_review3_fixes.py` içindeki ilgili testte ve
düzeltmenin yanındaki yorumda.

---

## Davranış değişikliği — bilinçli

Yeni yanal eğim kısıtı bu sitede ciddi sonuç doğuruyor. Sitenin medyan eğimi 21°,
hücrelerin yalnız %27'si 15° altında. Bu yüzden 15°'lik devrilme limitine sahip
roverlar (LUVMI-M, VIPER, Yutu-2) uzak nokta çiftleri için artık çözüm bulamıyor:
geçilebilir alan birbirine bağlı olmayan küçük bileşenlere ayrılıyor. Bu bir
gerileme değil, doğru cevap — ve hata mesajı hangi kısıtın kaç kenarı reddettiğini
yazıyor. LPR-1 (18° limit) için geçilebilir alanın %92,7'si bağlı kalıyor.

## Beklenmedik kazanç

H-3'ü 4-B maliyet küpüne de bağlayınca WAIT kenarı ilk kez anlamlı oldu. Adil
fiyatlanmış bir bekleme, yalnızca pahalı bir hücreyi ucuzlatmak için asla kârlı
değil (bir dilim beklemek bir dilim sürmekle aynı zamana mal olurken gölge cezası
farkı bunun çok altında). Ama karanlıkta *geçilemez* olan bir hücrenin Güneş
gelince açılması için beklemek kârlı. Testler bunu artık "beklemek daha ucuz"
yerine "beklemeden yol yok" diye ifade ediyor.

## Test durumu

| | önce | sonra |
|---|---|---|
| test sayısı | 511 | 621 |
| süre | 411 s | 245 s |
| uyarı | 1 (`RuntimeWarning`, costmap.py:70) | 0 |

Süre düşüşü A*'ın sıcak dizilerini NumPy görünümü yerine Python listesine
çevirmekten geliyor; bu aynı zamanda `g_score`'un float32 nicemlemesini de
kaldırdı.
