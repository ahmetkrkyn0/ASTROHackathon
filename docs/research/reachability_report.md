# D6 — Enerji-erişilebilirlik izokronları: Site11 ölçümleri

`time_expanded_energy_reachability_v1`. Grid 500×500 @ 5 m, pencere ofseti {'row': 2400, 'col': 2500}. Tüm ölçüm 266.47 s.

Buradaki her sayı bu gridde gerçekten koşuldu. Literatürün kendi sayıları `app.reachability.REACHABILITY_QUOTED` içinde durur ve bu tablolara karıştırılmaz.

## 1. Dijkstra neden çalışmaz — negatif kenarları ölç

Araştırma belgesi D6 için “`cost_cube` üzerinde çok-kaynaklı Dijkstra (enerji bütçeli)” diyor. `cost_engine.move_battery_drain_wh` işaretlidir: aydınlık ve düz bir hücrede panel sürüşten fazla üretir ve kenar NEGATİF olur. Dijkstra negatif kenarla sessizce yanlış cevap verir.

**LPR-1 (Default)** (`lpr_1`) — düz hücrede başabaş gölge oranı **0.3908**; bunun altında sürmek bataryayı DOLDURUR. Dilim 0.03590 h, coarsen 4, 48 dilim.

| epoch | t0'da aydınlık blok | sürüş kenarı | negatif | % | en kötü (Wh) | bekleme kenarı | negatif | % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-09-01 | 0.0 % | 3,734,496 | 0 | 0.00 | +0.000 | 547,296 | 0 | 0.0 |
| 2026-09-05 | 48.3 % | 3,734,496 | 1,080,811 | 28.94 | -5.735 | 547,296 | 295,017 | 53.9 |
| 2026-09-09 | 43.4 % | 3,734,496 | 967,544 | 25.91 | -5.653 | 547,296 | 302,743 | 55.3 |
| 2026-09-13 | 0.0 % | 3,734,496 | 0 | 0.00 | +0.000 | 547,296 | 0 | 0.0 |
| 2026-09-17 | 0.0 % | 3,734,496 | 0 | 0.00 | +0.000 | 547,296 | 0 | 0.0 |
| 2026-09-21 | 35.2 % | 3,734,496 | 683,208 | 18.29 | -4.788 | 547,296 | 217,488 | 39.7 |
| 2026-09-25 | 31.2 % | 3,734,496 | 582,855 | 15.61 | -5.244 | 547,296 | 218,185 | 39.9 |
| 2026-09-29 | 0.0 % | 3,734,496 | 0 | 0.00 | +0.000 | 547,296 | 0 | 0.0 |

**NASA VIPER** (`nasa_viper`) — düz hücrede başabaş gölge oranı **0.2400**; bunun altında sürmek bataryayı DOLDURUR. Dilim 0.03363 h, coarsen 4, 48 dilim.

| epoch | t0'da aydınlık blok | sürüş kenarı | negatif | % | en kötü (Wh) | bekleme kenarı | negatif | % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-09-01 | 0.0 % | 1,980,864 | 0 | 0.00 | +0.000 | 348,864 | 0 | 0.0 |
| 2026-09-05 | 47.3 % | 1,980,864 | 205,714 | 10.39 | -3.219 | 348,864 | 189,287 | 54.3 |
| 2026-09-09 | 40.7 % | 1,980,864 | 125,145 | 6.32 | -3.103 | 348,864 | 194,238 | 55.7 |
| 2026-09-13 | 0.0 % | 1,980,864 | 0 | 0.00 | +0.000 | 348,864 | 0 | 0.0 |
| 2026-09-17 | 0.0 % | 1,980,864 | 0 | 0.00 | +0.000 | 348,864 | 0 | 0.0 |
| 2026-09-21 | 33.9 % | 1,980,864 | 39,826 | 2.01 | -1.845 | 348,864 | 134,629 | 38.6 |
| 2026-09-25 | 28.2 % | 1,980,864 | 34,851 | 1.76 | -2.514 | 348,864 | 127,793 | 36.6 |
| 2026-09-29 | 0.0 % | 1,980,864 | 0 | 0.00 | +0.000 | 348,864 | 0 | 0.0 |

**Tuzak budur:** tamamen karanlık bir epoch'ta sayı sıfırdır. Test paketinin çoğunun kullandığı 2026-09-01 tam olarak öyle bir epoch. Bir Dijkstra orada doğru görünür, aydınlık bir epoch'ta yanlış cevap verir ve hiçbir test kırmızıya dönmez.

Tabanlanmış ikiz `net_energy_per_metre_wh` de kullanılamaz: `max(0, …)` olduğu için “güneşte sürerek menzil kazanamazsın” der. Bu modelde bu yanlıştır ve yalnızca tek yönde yanlıştır — muhafazakârlığın en kötü türü.

## 2. Üç standart başlangıç

### LPR-1 gunduz — `lpr_1` (358, 494), coarsen 4

Dilim 0.03590 h × 84 = 2.979 h ufuk. Kaba grid 125×125, geçilebilir 11,402 blok.

**Erişilebilir: 2,086 blok (0.8344 km²)**, geçilebilirin %18.30'i. Süre 2.0426 s, 92 kenar grubu, 508,770 kenar gevşetildi (23,240 negatif).

| bant | saat | blok | km² |
|---|---|---:|---:|
| 0 | 0.000–0.497 | 80 | 0.0320 |
| 1 | 0.497–0.993 | 239 | 0.0956 |
| 2 | 0.993–1.490 | 355 | 0.1420 |
| 3 | 1.490–1.986 | 461 | 0.1844 |
| 4 | 1.986–2.483 | 397 | 0.1588 |
| 5 | 2.483–2.979 | 554 | 0.2216 |

Reddetmeler: `soc_floor` 0, `shadow_endurance` 0, `horizon` 34,580 → **energy_binds = false**.

> Bu ufukta ve bu şarjda enerji kuralları hiç tetiklenmedi: sınır saatin kendisi. Harita bu durumda bir **kapılı mesafe dönüşümü**dür, enerji izokronu değil. Doğru bir ifadedir, ama başlığın vaat ettiğinden farklı bir şeydir ve yanıt bunu `energy_binds` ile söyler.

Duruş saati (120 h ufuk, 0.5 h adım): `reserve` 0 blokta, `shadow_endurance` 1,641 blokta, sansürlü 445. En kısa 48 h, en uzun 117.5 h.

Ödenmemiş rölanti: hamle başına ortalama 0.0178 h — bir hamle saati `ceil(travel_h / slice_hours)` tam dilim ilerletir ama gücü yalnızca `travel_h` boyunca öder. Bu planlayıcının kendi konvansiyonudur ve kasten miras alınır (aksi hâlde küme planlayıcının gevşetmesi olmaktan çıkardı), ama yayımlanan her şarjı bu kadar saatlik housekeeping kadar İYİMSER yapar.

Kısmen aydınlık blok (ilk dilimde 0 < pozlama < 1): 734. Bu bloklarda pozlama, ikili bir maskenin blok ORTALAMASIDIR; rover tek bir ince hücrededir ve ya aydınlıktadır ya değil.

### Ay gecesi — `lpr_1` (186, 34), coarsen 4

Dilim 0.03590 h × 84 = 2.979 h ufuk. Kaba grid 125×125, geçilebilir 11,402 blok.

**Erişilebilir: 3,151 blok (1.2604 km²)**, geçilebilirin %27.64'i. Süre 1.9823 s, 92 kenar grubu, 873,518 kenar gevşetildi (456,627 negatif).

| bant | saat | blok | km² |
|---|---|---:|---:|
| 0 | 0.000–0.497 | 145 | 0.0580 |
| 1 | 0.497–0.993 | 470 | 0.1880 |
| 2 | 0.993–1.490 | 688 | 0.2752 |
| 3 | 1.490–1.986 | 710 | 0.2840 |
| 4 | 1.986–2.483 | 623 | 0.2492 |
| 5 | 2.483–2.979 | 515 | 0.2060 |

Reddetmeler: `soc_floor` 0, `shadow_endurance` 0, `horizon` 44,453 → **energy_binds = false**.

> Bu ufukta ve bu şarjda enerji kuralları hiç tetiklenmedi: sınır saatin kendisi. Harita bu durumda bir **kapılı mesafe dönüşümü**dür, enerji izokronu değil. Doğru bir ifadedir, ama başlığın vaat ettiğinden farklı bir şeydir ve yanıt bunu `energy_binds` ile söyler.

Duruş saati (120 h ufuk, 0.5 h adım): `reserve` 0 blokta, `shadow_endurance` 620 blokta, sansürlü 2,531. En kısa 49 h, en uzun 116.5 h.

Ödenmemiş rölanti: hamle başına ortalama 0.0178 h — bir hamle saati `ceil(travel_h / slice_hours)` tam dilim ilerletir ama gücü yalnızca `travel_h` boyunca öder. Bu planlayıcının kendi konvansiyonudur ve kasten miras alınır (aksi hâlde küme planlayıcının gevşetmesi olmaktan çıkardı), ama yayımlanan her şarjı bu kadar saatlik housekeeping kadar İYİMSER yapar.

Kısmen aydınlık blok (ilk dilimde 0 < pozlama < 1): 734. Bu bloklarda pozlama, ikili bir maskenin blok ORTALAMASIDIR; rover tek bir ince hücrededir ve ya aydınlıktadır ya değil.

### VIPER kisa leg — `nasa_viper` (358, 494), coarsen 2

> coarsen 4'te **reddedilir**: start block (89, 123) is not traversable at coarsen=4. VIPER'ın 15° eğim sınırı, ince hücre geçilebilirken bloğun muhafazakâr AND'ini düşürüyor. Bu bir eksik değil, pencerenin gerçek bir özelliği; ölçüm coarsen 2'de.

Dilim 0.01681 h × 179 = 2.993 h ufuk. Kaba grid 250×250, geçilebilir 36,354 blok.

**Erişilebilir: 7,376 blok (0.7376 km²)**, geçilebilirin %20.29'i. Süre 4.0462 s, 16 kenar grubu, 3,115,010 kenar gevşetildi (310,161 negatif).

| bant | saat | blok | km² |
|---|---|---:|---:|
| 0 | 0.000–0.499 | 178 | 0.0178 |
| 1 | 0.499–0.998 | 178 | 0.0178 |
| 2 | 0.998–1.496 | 871 | 0.0871 |
| 3 | 1.496–1.995 | 1,923 | 0.1923 |
| 4 | 1.995–2.494 | 1,901 | 0.1901 |
| 5 | 2.494–2.993 | 2,325 | 0.2325 |

Reddetmeler: `soc_floor` 0, `shadow_endurance` 0, `horizon` 91,147 → **energy_binds = false**.

> Bu ufukta ve bu şarjda enerji kuralları hiç tetiklenmedi: sınır saatin kendisi. Harita bu durumda bir **kapılı mesafe dönüşümü**dür, enerji izokronu değil. Doğru bir ifadedir, ama başlığın vaat ettiğinden farklı bir şeydir ve yanıt bunu `energy_binds` ile söyler.

Duruş saati (120 h ufuk, 0.5 h adım): `reserve` 4,715 blokta, `shadow_endurance` 37 blokta, sansürlü 2,624. En kısa 24 h, en uzun 115.5 h.

Ödenmemiş rölanti: hamle başına ortalama 0.0086 h — bir hamle saati `ceil(travel_h / slice_hours)` tam dilim ilerletir ama gücü yalnızca `travel_h` boyunca öder. Bu planlayıcının kendi konvansiyonudur ve kasten miras alınır (aksi hâlde küme planlayıcının gevşetmesi olmaktan çıkardı), ama yayımlanan her şarjı bu kadar saatlik housekeeping kadar İYİMSER yapar.

Kısmen aydınlık blok (ilk dilimde 0 < pozlama < 1): 1,265. Bu bloklarda pozlama, ikili bir maskenin blok ORTALAMASIDIR; rover tek bir ince hücrededir ve ya aydınlıktadır ya değil.

## 3. Bütçe eğrisi — SOC ve ufuk değiştikçe

Aynı başlangıç, aynı epoch, değişen şarj ve ufuk. `soc_floor` sütunu enerjinin gerçekten bağlayıp bağlamadığını gösterir.

| başlangıç | epoch | SOC | ufuk (h) | dilim | erişilebilir blok | km² | soc_floor red | horizon red | enerji bağlıyor mu | süre (s) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| LPR-1 gunduz | 2026-09-05 | 1.00 | 3 | 84 | 2,086 | 0.8344 | 0 | 34,580 | hayır | 1.998 |
| LPR-1 gunduz | 2026-09-05 | 1.00 | 6 | 168 | 7,453 | 2.9812 | 0 | 133,369 | hayır | 4.2811 |
| LPR-1 gunduz | 2026-09-05 | 1.00 | 12 | 335 | 11,156 | 4.4624 | 0 | 214,733 | hayır | 9.0351 |
| LPR-1 gunduz | 2026-09-05 | 0.50 | 3 | 84 | 2,086 | 0.8344 | 0 | 34,580 | hayır | 2.1297 |
| LPR-1 gunduz | 2026-09-05 | 0.50 | 6 | 168 | 6,950 | 2.7800 | 16,111 | 120,639 | evet | 4.3806 |
| LPR-1 gunduz | 2026-09-05 | 0.50 | 12 | 335 | 11,156 | 4.4624 | 50,880 | 214,733 | evet | 9.1464 |
| LPR-1 gunduz | 2026-09-05 | 0.25 | 3 | 84 | 182 | 0.0728 | 16,375 | 664 | evet | 1.7272 |
| LPR-1 gunduz | 2026-09-05 | 0.25 | 6 | 168 | 182 | 0.0728 | 18,900 | 0 | evet | 2.7018 |
| LPR-1 gunduz | 2026-09-05 | 0.25 | 12 | 335 | 182 | 0.0728 | 18,900 | 0 | evet | 2.7681 |
| LPR-1 gunduz | 2026-09-01 | 1.00 | 3 | 84 | 2,086 | 0.8344 | 0 | 34,580 | hayır | 1.9871 |
| LPR-1 gunduz | 2026-09-01 | 1.00 | 6 | 168 | 7,453 | 2.9812 | 0 | 133,369 | hayır | 4.406 |
| LPR-1 gunduz | 2026-09-01 | 1.00 | 12 | 335 | 11,153 | 4.4612 | 126 | 214,653 | evet | 9.1809 |
| LPR-1 gunduz | 2026-09-01 | 0.50 | 3 | 84 | 2,086 | 0.8344 | 0 | 34,580 | hayır | 2.1334 |
| LPR-1 gunduz | 2026-09-01 | 0.50 | 6 | 168 | 6,323 | 2.5292 | 35,210 | 104,376 | evet | 4.3664 |
| LPR-1 gunduz | 2026-09-01 | 0.50 | 12 | 335 | 6,323 | 2.5292 | 328,921 | 48,793 | evet | 9.1014 |
| LPR-1 gunduz | 2026-09-01 | 0.25 | 3 | 84 | 182 | 0.0728 | 16,375 | 664 | evet | 1.7877 |
| LPR-1 gunduz | 2026-09-01 | 0.25 | 6 | 168 | 182 | 0.0728 | 18,900 | 0 | evet | 2.6278 |
| LPR-1 gunduz | 2026-09-01 | 0.25 | 12 | 335 | 182 | 0.0728 | 18,900 | 0 | evet | 2.6621 |
| Ay gecesi | 2026-09-05 | 1.00 | 3 | 84 | 3,151 | 1.2604 | 0 | 44,453 | hayır | 1.9214 |
| Ay gecesi | 2026-09-05 | 1.00 | 6 | 168 | 7,363 | 2.9452 | 0 | 132,916 | hayır | 4.3036 |
| Ay gecesi | 2026-09-05 | 1.00 | 12 | 335 | 11,161 | 4.4644 | 0 | 214,890 | hayır | 9.0687 |
| Ay gecesi | 2026-09-05 | 0.50 | 3 | 84 | 3,151 | 1.2604 | 0 | 44,453 | hayır | 1.9725 |
| Ay gecesi | 2026-09-05 | 0.50 | 6 | 168 | 7,363 | 2.9452 | 0 | 132,916 | hayır | 4.383 |
| Ay gecesi | 2026-09-05 | 0.50 | 12 | 335 | 11,161 | 4.4644 | 11 | 214,890 | evet | 9.2346 |
| Ay gecesi | 2026-09-05 | 0.25 | 3 | 84 | 3,072 | 1.2288 | 1,105 | 43,702 | evet | 1.9521 |
| Ay gecesi | 2026-09-05 | 0.25 | 6 | 168 | 7,362 | 2.9448 | 1,939 | 132,893 | evet | 4.355 |
| Ay gecesi | 2026-09-05 | 0.25 | 12 | 335 | 11,155 | 4.4620 | 54,330 | 214,741 | evet | 9.104 |
| Ay gecesi | 2026-09-01 | 1.00 | 3 | 84 | 3,151 | 1.2604 | 0 | 44,453 | hayır | 2.0524 |
| Ay gecesi | 2026-09-01 | 1.00 | 6 | 168 | 7,363 | 2.9452 | 0 | 132,916 | hayır | 4.423 |
| Ay gecesi | 2026-09-01 | 1.00 | 12 | 335 | 11,161 | 4.4644 | 0 | 214,890 | hayır | 9.2022 |
| Ay gecesi | 2026-09-01 | 0.50 | 3 | 84 | 3,151 | 1.2604 | 0 | 44,453 | hayır | 2.028 |
| Ay gecesi | 2026-09-01 | 0.50 | 6 | 168 | 7,024 | 2.8096 | 29,065 | 118,380 | evet | 4.2891 |
| Ay gecesi | 2026-09-01 | 0.50 | 12 | 335 | 7,176 | 2.8704 | 355,637 | 64,644 | evet | 9.1165 |
| Ay gecesi | 2026-09-01 | 0.25 | 3 | 84 | 586 | 0.2344 | 30,601 | 1,133 | evet | 1.8252 |
| Ay gecesi | 2026-09-01 | 0.25 | 6 | 168 | 586 | 0.2344 | 34,718 | 0 | evet | 2.6325 |
| Ay gecesi | 2026-09-01 | 0.25 | 12 | 335 | 586 | 0.2344 | 34,718 | 0 | evet | 2.6074 |

Okunacak şey: tam şarjda sınır saattir (`horizon` reddi büyük, `soc_floor` sıfır); şarj düştükçe `soc_floor` devreye girer ve erişilebilir alan çöker. Bir izokronu “enerji izokronu” diye sunmadan önce hangi kuralın bağladığına bakılmalıdır.

## 4. “Şimdi” ile “N saat sonra”

İki sweep de AYNI bloktan, AYNI şarjla başlar; yalnızca epoch değişir. Yani `lost`, arazinin kaybolması değil, *o saatte yola çıkan* bir rover'ın oraya gidememesidir. “Burada N saat beklersem ne kazanırım?” sorusunun cevabı bu değildir — o soru zaten temel sweep'in kendi bekleme kenarlarının içindedir ve bekleyen rover oraya daha az şarjla varır.

| başlangıç | epoch | N (h) | dilim | t0 aydınlık | t0+N aydınlık | şimdi | sonra | ortak | kazanılan | kaybedilen | Jaccard |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Ay gecesi | 2026-09-05 | 5.995 | 167 | 48.30 % | 48.00 % | 7,362 | 7,362 | 7,362 | 0 | 0 | 1.0 |
| Ay gecesi | 2026-09-05 | 24.015 | 669 | 48.30 % | 47.89 % | 7,362 | 7,362 | 7,362 | 0 | 0 | 1.0 |
| Ay gecesi | 2026-09-05 | 95.989 | 2674 | 48.30 % | 43.44 % | 7,362 | 7,211 | 7,211 | 0 | 151 | 0.979489 |
| Ay gecesi | 2026-09-05 | 240.008 | 6686 | 48.30 % | 0.00 % | 7,362 | 586 | 586 | 0 | 6,776 | 0.079598 |
| Ay gecesi | 2026-09-01 | 5.995 | 167 | 0.00 % | 0.00 % | 586 | 586 | 586 | 0 | 0 | 1.0 |
| Ay gecesi | 2026-09-01 | 24.015 | 669 | 0.00 % | 32.11 % | 586 | 586 | 586 | 0 | 0 | 1.0 |
| Ay gecesi | 2026-09-01 | 95.989 | 2674 | 0.00 % | 48.30 % | 586 | 7,362 | 586 | 6,776 | 0 | 0.079598 |
| Ay gecesi | 2026-09-01 | 240.008 | 6686 | 0.00 % | 42.12 % | 586 | 7,110 | 586 | 6,524 | 0 | 0.082419 |

**Ölçülen bulgu:** saat ölçeğinde küme kıpırdamıyor. 6 ve 24 saatlik kaydırmalarda aydınlık blok oranı ölçülebilir biçimde değişiyor (tablodaki iki aydınlık sütunu bunu gösteriyor) ama erişilebilir kümede TEK blok bile değişmiyor. Sebebi fizik: kutupta aydınlanma ~708 saatlik sinodik döngüyle döner, yani bir gün döngünün %3'üdür ve terminatör neredeyse hiç yürümez. Etki gün ölçeğinde geliyor: +96 saatte aydınlık epoch'tan 151 blok kaybediliyor (Jaccard 0.979) ve +240 saatte pencere tamamen karanlığa giriyor — 7 362 blok 586'ya düşüyor (Jaccard 0.080). Karanlık epoch'tan bakıldığında aynı şey ters yönde: +96 saatte 586 blok 7 362'ye çıkıyor. Site11'de “N saat sonra” sorusunun anlamlı hâli GÜN ölçeğindedir.

Bu tabloyu yalnızca Jaccard sütunuyla yayımlamak, “küme zamanla sabittir” gibi okunurdu — ve bu, güneşin hiç modellenmediği durumdan ayırt edilemezdi. İki aydınlık sütunu tam olarak o ayrımı yapmak için var: gölge gerçekten hareket etti, küme hareket etmedi.

`later_hours` tam dilim sayısına yuvarlanır ve yuvarlanmış değer yayımlanır: yuvarlanmamış bir kaydırma ikinci sweep'in dilimlerini birincininkilerin arasına düşürür ve her fark, hareket eden gölgeden ayrılamayan bir örnekleme artefaktı taşır.

## 5. Gevşetme ne kadar gevşek — planlayıcıyla örneklem karşılaştırması

Ay gecesi, 2026-09-05. Sweep'in erişilebilir dediği 11 blok örneklendi ve her biri için 4-B planlayıcı gerçekten koşuldu (aynı coarsen, aynı dilim, aynı epoch, aynı ufuk, her opsiyonel kısıt kapalı): **11/11 = %100** rota buldu. 13.717 s.

| blok | sweep ilk dilim | planlayıcı rota buldu mu | planlayıcı varış dilimi |
|---|---:|---|---:|
| (47, 18) | 18 | evet | 19 |
| (59, 6) | 25 | evet | 25 |
| (37, 26) | 31 | evet | 32 |
| (28, 22) | 37 | evet | 38 |
| (73, 12) | 42 | evet | 43 |
| (69, 30) | 47 | evet | 48 |
| (14, 19) | 52 | evet | 58 |
| (10, 0) | 57 | evet | 59 |
| (18, 38) | 62 | evet | 63 |
| (14, 41) | 69 | evet | 74 |
| (72, 3) | 76 | evet | 76 |

Planlayıcının varış dilimi her satırda sweep'in ilk diliminden büyük ya da ona eşit. Bu, içerme özelliğinin ikinci yüzüdür: sweep'in “en erken varış”ı planlayıcının varışı için bir ALT sınırdır, çünkü sweep aynı kenarları aynı saat kuralıyla gevşetir ve hiçbir ek kısıt uygulamaz.

%100'ün altındaki her şey gevşetmenin gevşekliğidir ve beklenir: iki zarf alanı BAĞIMSIZ optimize edilir, yani bir blok için yayımlanan şarj ile karanlık saati farklı öncüllerden gelebilir ve tek bir yörünge ikisini birden gerçekleştirmek zorunda değildir. İddianın neden negatif yönde kurulduğu tam olarak budur.

## 6. İddia sınırı

* **Güvenli yön tek yöndür.** Kümenin DIŞINDAKİ bir blok, bu enerji modelinin “oraya gidemezsin” dediği bloktur. İÇİNDEKİ bir blok adaydır, söz değildir.
* **İçerme hangi yapılandırmaya karşı?** `planner_configuration` yanıtta yayımlanır. `allow_hibernate=True` ile koşan bir plan bu kümenin dışına meşru biçimde çıkabilir: hibernasyon üçüncü bir kenar ailesidir, `p_hibernate_w` ile boşalır ve uyanışta karanlık saatini sıfırlar.
* **İki başlık ters yönde yanılır.** `reachable` fazla büyüktür (gevşetme + replay edilmeyen altı kapı), `earliest_hours` fazla geçtir (hamle başına bir dilime kadar yukarı yuvarlama). Birbirlerini götürmezler; zıt operasyonel kararlara işaret ederler ve yanıt her alan için yönü `conservatism` ile söyler.
* **Karanlık saati saat değildir.** `astar_4d`'in kendi konvansiyonu: saat `hours × exposure` ile ilerler. Pozlaması 0.5 olan bir blok saati yarı hızda harcar, yani duvar saatiyle 50 h'lik dayanım 100 h'e kadar uzayabilir. Gerçek gridde ölçüldü: dayanımın bağladığı bloklarda duruş süresi 49.5 h ile 56.0 h arasında, yayımlanan `h_max_shadow_h` 50 h.
* **`time-to-0-SOC` bir işletme payı değildir.** Rezervin altında bu modelde hiç geçiş yoktur; sayı batarya fiziğidir. İşletme sayısı `hold_limit` = min(rezerv saati, dayanım saati) ve hangisinin bağladığı `hold_limited_by` ile birlikte yayımlanır.
* **Epoch zorunludur.** `start_utc` olmadan `build_shadow_series` uzun dönem gölge KESRİNE düşer — bir iklimoloji, gökyüzü değil. Onun üstüne çizilen izokron araziyi ve bataryayı ölçer, bugünü değil; ve “N saat sonra” farkı tam olarak sıfır çıkar. Bu yüzden 422'dir, `/api/plan-4d`'in aksine geri düşecek anlamlı bir mod yok.
* **Yumuşatma yok, `skimage` yok.** Bant sınırı kaba blok kafesinin merdivenidir. Araştırma belgesinin önerdiği `skimage.measure.find_contours` yeni bir bağımlılık olurdu (`backend/requirements.txt`'te yok) ve bir blok kafesinin çevresine daha güzel bir çizgi çizmek için modelin hiç değerlendirmediği araziden geçen bir hat üretirdi.
* **Yayılmayan belirsizlik.** Kayma, DEM hatası, batarya sıcaklığı ve konumlandırma kayması bu depoda MODELLENİYOR ve burada yayılmıyor. Sınırı ne kadar oynattıklarına dair sayı yayımlanmıyor, çünkü ölçülmedi.

Literatür yöntem kaynağıdır. Tompkins'in ve arXiv 2509.15062'nin kendi sayıları `REACHABILITY_QUOTED` sözlüğündedir, bu tablolarda değil; araştırma belgesinin kendi iddialarında bulunan düzeltmeler `REACHABILITY_CORRECTIONS` içinde durur.

