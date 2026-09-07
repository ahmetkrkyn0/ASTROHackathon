# Dunya gorunurlugu (DTE) dogrulama raporu

Referans: `lunapath\data\raw\AVGVISIB_85S_060M_201608_EARTH.TIF` -- NASA GSFC PGDA urun 69, `"AVGVISIB_85S_060M_201608_EARTH"` (LOLA, 60 m/px, uretim 2016-09-15T00:00:00), Mazarico vd. 2011.
Model: `lunapath\data\processed\earth_visibility_grid.npy` -- ufuk kupu + SPICE Dunya vektoru, 6798.4 gun / 1.0 saat adim, 163162 ornek, 2008-01-01T00:00:00Z -> 2026-08-12T10:00:00Z.

## 60 m karsilastirma (referansin kendi cozunurlugu, 12x12 blok ortalamasi)

| Metrik | Deger |
|---|---|
| rmse | 0.087394 |
| mae | 0.063246 |
| bias | -0.062272 |
| pearson_r | 0.959559 |
| n_compared | 1681 |
| disagreement_pct | 9.399 |
| model_mean | 0.281079 |
| reference_mean | 0.343351 |

## 5 m karsilastirma (referans modelin hucrelerine enterpole)

| Metrik | Deger |
|---|---|
| rmse | 0.101015 |
| mae | 0.063984 |
| bias | -0.061947 |
| pearson_r | 0.934465 |
| n_compared | 250000 |
| disagreement_pct | 9.437 |
| model_mean | 0.282598 |
| reference_mean | 0.344545 |

**Okuma:** `rmse`, `mae` ve `bias` gorunurluk kesri (0-1) birimindedir; `bias > 0`
modelin referanstan daha fazla Dunya gorunurlugu verdigini soyler. `pearson_r`
iki haritanin uzamsal deseninin ne kadar ortustugudur. `disagreement_pct`, iki
haritanin 0,5 esiginde ANLASMADIGI hucrelerin yuzdesidir -- planlama acisindan
en kritik sayi budur ("cogunlukla baglantili" / "cogunlukla degil").

Yontem ayni (ufuk acisi vs. gok cismi yuksekligi), girdiler farkli: referans
LOLA 60 m DEM'i ve 18,6 yillik saatlik ornekleme (PGDA urun sayfasi; PDS
etiketi START/STOP 2009-07-13T17:33:17.246 / 2013-07-18T14:12:13
yalnizca LOLA veri araligini verir), model ise bu pencerenin 5 m DEM'i, 10 km
isin menzili ve yukaridaki ornekleme. Kalan fark bu girdilerden gelir; 60 m
satiri fizigin, 5 m satiri ise ek yuzey ayrintisinin olcusudur.
