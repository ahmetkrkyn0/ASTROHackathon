# Safe Haven haritasi -- rover profiline ve Ay gunune gore olcum (A1)

Uretildi: `scripts/safe_haven_report.py`. Pencere: 2026-09-07T00:00:00 baslangic, 708,7 saat (29,5 gun, bir sinodik ay), adim 2,0 saat (355 ornek). Grid: 500x500 @ 5.0 m (Site11, de Gerlache rim), ufuk kubu iki olcekli (5 m yakin + LOLA 40 m uzak, 150 km).

Kural (NASA VIPER, Shirley & Balaban 2022; Ennico-Smith vd. 2023): *Dunya ufkun altindayken kesintisiz golge suresi rover'in dayanimini (`h_max_shadow_h`) asmayan ve pencere icinde en az bir kez aydinlanan, gecilebilir hucre*. Karanlik yalnizca Dunya'nin gorunmedigi adimlarda sayilir; Dunya gorunurken rover komutla baska yere tasinabilir.

## Ay gunu 2026-09-07 -- site

| Olcum | Deger |
|---|---|
| Dunya-yok adim kesri (tum hucreler, ortalama) | 71,7 % |
| Dunya-yok saat, gecilebilir hucreler (medyan / p90 / maks) | 470 / 710 / 710 h |

## Ay gunu 2026-09-07 -- rover profiline gore

| Rover | Dayanim (h) | Gecilebilir | Safe haven | Kesir | SH'a ulasabilen | tts medyan / p90 (h) | Dunya-yok karanlik min / medyan / p90 (h) | Dayanimi asan | Hic aydinlanmayan | Sure (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| LPR-1 (Varsayilan) | 50 | 210063 | 0 | 0,00 % | 0,0 % | - / - | 156 / 344 / 482 | 210063 | 1047 | 4,1 |
| LUVMI-M | 4 | 210063 | 0 | 0,00 % | 0,0 % | - / - | 156 / 344 / 482 | 210063 | 1047 | 3,3 |
| NASA VIPER | 96 | 198575 | 0 | 0,00 % | 0,0 % | - / - | 156 / 342 / 482 | 198575 | 585 | 3,3 |
| CNSA Yutu-2 | 2 | 198575 | 0 | 0,00 % | 0,0 % | - / - | 156 / 342 / 482 | 198575 | 585 | 3,3 |

Sutunlar: *Safe haven* = kurali saglayan gecilebilir hucre sayisi; *SH'a ulasabilen* = kapili surus grafi uzerinden (adim egimi, yanal egim, kose kesme) sonlu surede bir SH'a varabilen gecilebilir hucrelerin kesri; *tts* = en yakin SH'a surus suresi (`edge_travel_time_s`, egime bagli, aydinlanmadan bagimsiz); *Dayanimi asan* = Dunya-yok karanligi dayanimdan uzun olan gecilebilir hucreler; *Hic aydinlanmayan* = pencere boyunca hic Gunes gormeyen gecilebilir hucreler (kural geregi SH olamaz).

## Ay gunune gore tarama (13 sinodik ay)

Dunya'nin batis-dogus dongusu (~27,3 gun) ile Gunes'inki (29,5 gun) arasindaki faz her ay ~2 gun kayar; bu yuzden NASA safe haven haritalarini Ay gunu basina uretir. *Gerekli dayanim*: aydinlanan gecilebilir hucrelerin %1 / %10 / %50'sinin SH sayilmasi icin rover'in tasimasi gereken kesintisiz-golge dayanimi.

| Ay gunu | Dunya-yok kesri | Aydinlanan kesir | En kisa Dunya-yok karanlik (h) | Gerekli dayanim %1 / %10 / %50 (h) | SH LPR-1 (Varsayilan) (50 h) | SH LUVMI-M (4 h) | SH NASA VIPER (96 h) | SH CNSA Yutu-2 (2 h) |
|---|---|---|---|---|---|---|---|---|
| 2026-09-07 | 71,7 % | 99,5 % | 156 | 158 / 188 / 342 | 0,00 % | 0,00 % | 0,00 % | 0,00 % |
| 2026-10-06 | 74,8 % | 99,9 % | 88 | 100 / 222 / 310 | 0,00 % | 0,00 % | 0,26 % | 0,00 % |
| 2026-11-05 | 76,1 % | 100,0 % | 40 | 122 / 188 / 264 | 0,02 % | 0,00 % | 0,41 % | 0,00 % |
| 2026-12-04 | 75,9 % | 99,9 % | 60 | 128 / 176 / 234 | 0,00 % | 0,00 % | 0,16 % | 0,00 % |
| 2027-01-03 | 75,1 % | 99,3 % | 78 | 98 / 146 / 208 | 0,00 % | 0,00 % | 0,66 % | 0,00 % |
| 2027-02-01 | 74,4 % | 97,9 % | 98 | 110 / 178 / 250 | 0,00 % | 0,00 % | 0,00 % | 0,00 % |
| 2027-03-03 | 74,3 % | 95,8 % | 108 | 128 / 214 / 292 | 0,00 % | 0,00 % | 0,00 % | 0,00 % |
| 2027-04-01 | 72,3 % | 72,6 % | 186 | 232 / 232 / 382 | 0,00 % | 0,00 % | 0,00 % | 0,00 % |
| 2027-05-01 | 70,6 % | 62,3 % | 176 | 176 / 298 / 502 | 0,00 % | 0,00 % | 0,00 % | 0,00 % |
| 2027-05-30 | 69,3 % | 94,4 % | 62 | 64 / 82 / 380 | 0,00 % | 0,00 % | 10,71 % | 0,00 % |
| 2027-06-29 | 68,6 % | 97,2 % | 104 | 104 / 106 / 372 | 0,00 % | 0,00 % | 0,00 % | 0,00 % |
| 2027-07-28 | 68,8 % | 98,8 % | 146 | 148 / 156 / 360 | 0,00 % | 0,00 % | 0,00 % | 0,00 % |
| 2027-08-27 | 70,1 % | 99,7 % | 156 | 156 / 194 / 326 | 0,00 % | 0,00 % | 0,00 % | 0,00 % |

Yorum: bu sitede Dunya'nin ufkun altinda oldugu iki hafta, sitenin tamaminin gunlerce karanlik kaldigi Ay gecesiyle cakisir; bu yuzden safe haven **nadirdir** -- NASA'nin VIPER icin soyledigi gibi ("SH'lar misyonu uzatan asil kaynaktir ve azdir"). Dayanim kisaldikca harita buzulur; ayni site, ayni ay, dort farkli SH kumesi. Dis dogrulama urunu yoktur; kural ve esikler NASA belgelerinden birebir alinmistir.

Yeniden uretmek: `python scripts/safe_haven_report.py --start-utc 2026-09-07T00:00:00 --months 13` (ufuk kubu ve NAIF cekirdekleri gerekir).
