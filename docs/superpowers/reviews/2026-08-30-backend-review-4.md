# Backend bağımsız denetimi — tur 4

**Tarih:** 2026-08-30
**Dal:** `backend/physics` (denetim tabanı `2bed703`)
**Kapsam:** `backend/app` (33 modül), tetiklediği ölçüde `scripts/` ve
`lunapath/src/process_lunar_data.py`
**Yöntem:** Backend'in tamamı, önceki turların bulgu listelerine bakılmadan
sıfırdan okundu. Her yapısal şüphe için ayrı bir ölçüm betiği yazıldı ve
`lunapath/data/processed/` altındaki 500×500 / 5 m-px üretim gridi üzerinde
çalıştırıldı; doğrulanmayan hipotezler rapora girmedi.

**Sonuç:** 23 bulgu — 4 yüksek, 7 orta, 12 düşük. **Tamamı düzeltildi.**
Her bulgu için davranışı sabitleyen bir regresyon testi yazıldı
(`backend/test_review4_fixes.py`, 34 test).

Ayrıntılı, ölçümlü sürüm (paylaşılabilir sayfa):
<https://claude.ai/code/artifact/3cc9c07d-936f-4e6e-ab8f-03e803a7e378>

---

## Denetimin çerçevesi

Tur 3 dört ağır bulguyu kapattı ve bunu 2-B planlayıcıda gerçekten yaptı.
Sorun, aynı düzeltmelerin *ikinci* planlayıcıya taşınma biçimindeydi — ve
bunların altında, dört kriterli maliyet modelinin dayandığı gölge katmanının
geçilebilir alanda neredeyse sabit olması vardı.

---

## Yüksek

### H-1 — Gölge–termal bağlaması 4-B maliyet küpünde ikinci kez uygulanıyordu

`data_loader` termal katmanı gölgeye bağlıyor, ardından `build_cost_cube`
*zaten bağlanmış* alana aynı Stefan–Boltzmann harmanını dilim başına yeniden
uyguluyordu.

| | önce | sonra |
|---|---|---|
| ortalama yüzey sıcaklığı (2-B / 4-B) | −50,1 / **−87,1 °C** | tek alan |
| 10 °C'den fazla soğuyan hücre | 248 671 (%99,5) | 0 |
| 2-B'ye göre geçilebilir, 4-B'ye göre değil | 3 494 | **0** |
| ortalama hücre maliyeti | +%20,1 | eşit |

**Düzeltme.** `thermal_grid.npy` artık **tek** istatistik tutuyor:
düzeltilmemiş güneşli tepe, `metadata["thermal_field"] = "sunlit_peak"` ile
damgalı. Aydınlanma bağımlı iki alan (`thermal`, `thermal_min`) yükleme
anında ondan türetiliyor, yani düzeltme tam olarak bir kez uygulanıyor ve
yapısal olarak iki kez uygulanamıyor. Eski bayrak `thermal_shadow_coupled`
"bir düzeltme uygulandı" diyordu ama *hangisini* söyleyemiyordu — küpün
yeniden uygulamasının nedeni buydu.

### H-2 — 4-B planlayıcının tek hata mesajı yanlış sebebi söylüyordu

Tur 3 sert kenar kısıtlarını `astar_4d`'ye ekledi, teşhis sayaçlarını
eklemedi. Varsayılan `coarsen=4`'te geçilebilir kaba hücrelerin %7'sinin hiç
geçerli kenarı yok; böyle bir başlangıçtan plan isteyen çağıran **800 dilimle
bile** "No path found within the time horizon" alıyordu.

**Düzeltme.** `astar_4d` yedi ayrı red sayacı tutuyor (`edges_rejected`),
`no_path_reason_4d` hangi kısıtın kaç kenar reddettiğini yazıyor, ve
`gated_move_count` ulaşılabilirliği planlayıcının *gerçekten arayacağı*
grafta ölçüyor — kenar kapıları dahil. `/api/plan-4d` artık küp kurmadan,
önden 422 döndürüyor:

> start (2, 50) and goal (498, 486) are not connected at coarsen=4 once
> LPR-1's 25 deg step-slope and 18 deg roll-over limits are applied to each
> edge … **No time horizon would have helped.**

### H-3 — Harman bir *tepe* alanına *zaman ortalaması* uyguluyordu

`Heat1DModel` bir lunar yıl boyunca `np.nanmax` saklıyor — yıllık **tepe**.
`shadow_ratio` bir **zaman kesri**. Tur 3 ikisinin dördüncü-kuvvet zaman
ortalamasını alıp tepe alanının adı altında saklıyordu.

| aydınlanma | tur 3 raporu | gerçek tepe |
|---|---|---|
| %75 | −18,7 °C | 0 °C |
| %50 | −42,8 °C | 0 °C |
| %25 | −78,3 °C | 0 °C |
| %10 | −115,6 °C | 0 °C |

Anlık dilimlerde daha sertti: gölge geçtiği *an* hücre, önceki sıcaklığı ne
olursa olsun −183,1 °C'ye, yani geçilebilirlik eşiğinin altına düşüyordu.
Bu gridin %75'i `shadow_ratio > 0.5` bandında.

**Düzeltme.** İki istatistik ayrıldı (`annual_peak_c`,
`shadowed_equilibrium_c`); geçilebilirlik kapısı **soğuk uca**, barrier'ın
her duvarı kendi ucuna, `f_thermal` ise **zarfa** (ikisinin kötüsü)
bağlandı. Anlık dinamikler için `REGOLITH_THERMAL_TAU_S` (~1 saat,
`UNCALIBRATED` etiketli, Diviner tutulma gözlemlerine dayalı büyüklük
mertebesi) ile birinci mertebe gecikme eklendi: bir saatlik gölge −115,7 °C
veriyor, sürekli gölge tabana iniyor.

### H-4 — Gölge katmanı geçilebilir alanda neredeyse sabitti

250 000 hücrenin %92,9'u iki histogram kutusunda; tam aydınlık hücre
sayısı 1. İki gerçek kusur bulundu:

1. `horizon_map`'in adım sayacı 5 m/px'te aramayı nominal 10 km yerine
   **1 km**'ye kısıyordu.
2. Daha büyüğü: ufuk, planlama penceresinin **kırpılmış kopyası** üzerinde
   hesaplanıyordu. Ham DEM 16 km; pencere 2,5 km. Her ışın birkaç yüz metrede
   DEM'i terk edip "engel yok" diyordu — ki bu "engel bulunamadı" ile aynı
   şey değil.

**Düzeltme.** Işın yürüyüşü yakın alanda hücre hücre, uzakta geometrik
aralıklarla; menzil artık `max_range_m`'in kendisi. `horizon_map` bir `roi`
alıyor: açı yalnız pencere hücreleri için döndürülüyor ama ışınlar tüm
bağlam üzerinde yürüyor.

| | önce | sonra |
|---|---|---|
| `shadow_ratio` σ | 0,0600 | **0,0822** |
| kalıcı gölge hücresi | 1 076 | **1 336** |
| en yoğun iki kutu | %92,9 | %87,0 |
| `spearman(f_slope, f_energy)` | 0,9684 | **0,9498** |
| ufuk hesabı süresi | 188 s (1 km) | **117 s (10 km)** |

Dürüstçe: kalan yoğunlaşma bu sitenin fiziği. Seçilen 28 günlük güneş izinde
Güneş elevasyonu hep +1,05° ile +1,96° arasında; kutupta azimut süpürmesi
boyunca soru "azimutların kaçında engel var"a dönüşüyor ve cevabı çoğu
hücrede ~0,5. Bu bir kod hatası değil, ama gölge kriterinin bu sitede
ayırt etme gücünün neden düşük olduğunun cevabı.

---

## Orta

| # | Bulgu | Düzeltme |
|---|---|---|
| M-1 | `total_weighted_cost` barrier'ı atlıyordu (gerçek amacın %14,75'i) | Rapor edilen değer artık A*'ın kendi g-skoru; `total_weighted_cost_cells_only` ve `barrier_share` ayrı alanlar |
| M-2 | Her başarısız planda `nodes_expanded` atılıyordu | `_empty_result`/`_empty` sayıyı taşıyor; ölçüm: 0 → 19 |
| M-3 | Mahsur traverse tek yanıtta iki farklı rota döndürüyordu | Koridor yürütülebilir önekten kuruluyor; yanıt `execution` bloğu taşıyor |
| M-4 | Profiller dört kısıt yayınlayıp birini uyguluyordu | `constraint_handling` etiketi + `/api/compare` ve `/api/plan-multi`'de simülasyonlu `constraint_check` |
| M-5 | Barrier'ın dört ayrı kopyası; testler üretimde çalışmayanı doğruluyordu | `geometric_barrier_terms` tek kaynak; tablo ondan örnekleniyor, iki planlayıcı `lateral_slope_tan`'ı paylaşıyor |
| M-6 | `astar_metrics` sabit sıfır enerji yayınlıyordu | `None` (API'nin mevcut "değerim yok" sözleşmesi) |
| M-7 | Sıcak duvar bağlayıcı olmayan limite çapalıydı | Bildirilen tüm bileşen tavanlarının en darı: lpr_1 80 → **75 °C**, yutu-2 85 → **60 °C** |

---

## Düşük

L-1 `explain()` sıfır-ağırlık × sonsuz koruması (tur 3'te yalnız `total()`'a
girmişti) · L-2 yanal barrier reddi `step_slope` sayılıyordu · L-3 A* hâlâ
float32 maliyet okuyordu · L-4 simülatör hücre eğimiyle sürüyordu ·
L-5 4-B seyahat süresi yalnız hedef hücreden · L-6 sıfırlanmamış odometre
replan döngüsü tetikliyordu · L-7 `auto_slice_hours` blok maksimumlarının
medyanını alıyordu · L-8 iki geçilebilirlik formu farklı kural uyguluyordu ·
L-9 `mission_reference` hiçbir yerden okunmuyordu (`/api/reference-missions`) ·
L-10 ufuk menzili (H-4 ile birlikte) · L-11 4-B kapısı blok-ortalama
yükseklikte ölçüyordu (`how="center"`) · L-12 termal kapı `>=`, barrier `>`
kullanıyordu.

Hepsi düzeltildi; ayrıntılar `test_review4_fixes.py` içindeki ilgili testte ve
düzeltmenin yanındaki yorumda.

---

## Davranış değişikliği — bilinçli

Yeni gölge katmanı 260 kalıcı gölge hücresi daha buluyor ve geçilebilirlik
soğuk uca bağlandı, dolayısıyla geçilebilir alan %81,7'den **%80,2**'ye
düştü. Kaybedilen 3 837 hücre, hiç aydınlanmayan ve önceki katmanın
göremediği soğuk tuzaklar — gerileme değil, düzeltme.

`f_thermal` artık zarfı okuduğu için termal kriterin ortalama maliyetteki
payı %15,2'den %29,5'e çıktı. Rota seçimini gerçekten etkiliyor.

## Kapsam dışı bırakılan

Ham DEM ve NAIF çekirdekleri mevcut olduğu için sevk edilen `.npy`
artefaktları `scripts/refresh_processed_grids.py --rebuild-shadow` ile
yenilendi. Tam P1 yeniden çalıştırması yapılmadı: heat1d arama tablosunu
15 dakikada yeniden kurar ve pencereyi yeniden seçer; termal alan
`sunlit_peak_from_equilibrium_c` ile tam tersinir biçimde geri
kazanıldı (round-trip farkı 0,0).

## Test durumu

| | tur 3 sonu | tur 4 sonu |
|---|---|---|
| test sayısı | 618 | **654** |
| başarısız | 0 | 0 |
| uyarı | 0 | 0 |
| süre | 357 s | 351 s |

Tur 3'ün suite'i bu 23 bulgunun hiçbirini yakalamıyordu — beklenen durum:
bulguların hiçbiri tek bir fonksiyonun kendi sözleşmesini ihlal etmesinden
kaynaklanmıyor. Her biri iki bileşenin *birlikte* ne yaptığıyla ya da bir
katmanın gerçek veri dağılımıyla ilgili.
