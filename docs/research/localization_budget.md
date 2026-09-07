# Lokalizasyon belirsizlik butcesi

*Uretim: `scripts/localization_budget.py` - 2026-08-30*

Rota: `(150, 150)` -> `(400, 400)`, lpr_1, 2.57 km, 408 segment.

Koridor yari genisligi: medyan **25.0 m**, minimum **5.0 m**.
Sifirlama sonrasi baslangic belirsizligi (sigma_0): 1.0 m.

`check_localization_uncertainty` tetikleyicisi, kovaryans koridor
yari genisligini astiginda ATES ALIR. Asagidaki mesafeler, her
kaynagin NOMINAL calisirken bile bu tetikleyiciyi garantiyle
atesleyecegi yol uzunlugudur - yani iki mutlak konum sifirlamasi
arasindaki azami mesafe butcesi.

## Medyan koridor genisligine gore

| Odometri kaynagi | Drift orani | Sifirlamasiz mesafe | Rota buna sigar mi? |
|---|---|---|---|
| dead_reckoning | %10 | 240 m | **hayir** |
| visual_odometry | %0.5 | 4.80 km | evet |
| lidar_odometry | %0.5 | 4.80 km | evet |
| skyline/sun-sensor sifirlamali | fix'ler arasinda birikir | her guvenilir fix'te sifirlanir | evet (fix araligina bagli) |

## En dar segmente gore (kotu durum)

| Odometri kaynagi | Sifirlamasiz mesafe |
|---|---|
| dead_reckoning | 40 m |
| visual_odometry | 800 m |
| lidar_odometry | 800 m |

## Kaynaklar

- MER wheel+IMU dead reckoning, ~10% of distance (Maimone et al.)
- M2020-class VO, 0.22-2.45% band, 0.5% taken as representative
- LiDAR odometry (KISS-ICP class), ~0.5% translational drift on structured terrain; quoted at the same order as VO because both are frame-to-frame registration against the world

## Sinirlar - bu tablo ne DEGILDIR

- Drift oranlari baska araclarin baska zeminlerdeki yayinlanmis
  degerleridir; bu rover ve bu regolit icin kalibre edilmemistir.
- Buyume modeli dogrusaldir (`sigma = sigma_0 + oran x mesafe`),
  cunku yayinlanan rakamlar 'mesafenin yuzdesi' bicimindedir;
  gercek hata buyumesi arazi bagimli ve kismen stokastiktir.
- 'Sifirlamasiz mesafe' bir garanti degil, tetikleyicinin nominal
  kosulda dahi atesleyecegi ust siniridir.
- Skyline sifirlamasi yalnizca `ambiguity_ratio` esigi gecen
  guvenilir eslesmelerde drift'i sifirlar; duz arazide fix
  reddedilir ve butce dead-reckoning/VO satirlarina geri duser
  (bkz. `backend/app/skyline.py`).
