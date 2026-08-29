# Nav2 baseline karsilastirmasi

Start `(100, 101)` -> Goal `(400, 400)`, 5 m/px grid, 500x500.

| Planlayici | waypoints | length_km | max_slope_deg | mean_shadow_ratio | min_thermal_c | time_ms |
|---|---|---|---|---|---|---|
| SmacPlanner2D-equivalent (geometric) | 393 | 2.409 | 24.96 | 0.5391 | -129.25 | 564.6 |
| LunaPath multi-criteria A* | 426 | 2.498 | 24.99 | 0.5259 | -56.12 | 868.7 |

**Okuma:** Geometrik baseline en kisa gecilebilir yolu bulur ve arazinin
maliyetini bilmez. LunaPath'in rotasi daha uzun olabilir; karsiliginda
`max_slope_deg` ve `mean_shadow_ratio` degerleri dusuktur. Fark, cok
kriterli maliyet modelinin satin aldigi seydir.

Bu kosuda `mean_shadow_ratio` (0.5259 < 0.5391) ve `length_km` (2.498 >= 2.409)
beklenen yonde cikti, ancak `max_slope_deg` neredeyse esit ve hatta ters yonde
cikti (LunaPath 24.99 vs baseline 24.96 -- 0.03 derece, olcum gurultusu
mertebesinde ama beklenen yon degil). Bu, "duzeltilmesi gereken bir hata"
degil, Faz 1-2-3 review'unun H4 bulgusunun beklenen bir belirtisidir: termal
maliyet terimi egimle neredeyse mukemmel korele (Spearman 0.984) ve dik
araziyi cezalandirmak yerine odullendiriyor, bu da cok kriterli maliyetin
egimi baseline'a gore tutarli sekilde dusurme gucunu zayiflatiyor. Agirliklar
bu bulguyu "duzeltmek" icin degistirilmedi; H4 kendi kapsaminda (Faz 1-2-3)
ele alinacak bir bulgu.

Not: `--start 100 100` istenen hedef hucre (100, 100) gecilemez (traversable
degil) oldugu icin en yakin gecilebilir hucre olan `(100, 101)`'e kaydirildi
(`np.argwhere(traversable)` ile bulundu); `--goal 400 400` oldugu gibi
gecilebilir.

**Step 3 -- gercek Nav2 koşumu:** Gerçek Nav2 koşumu costmap köprüsü
gerektirdiği için ertelendi; buradaki geometrik baseline SmacPlanner2D'nin
amaç fonksiyonunu (en kısa geçilebilir yol) yeniden üretiyor.

```json
{
  "SmacPlanner2D-equivalent (geometric)": {
    "waypoints": 393,
    "length_km": 2.409,
    "max_slope_deg": 24.96,
    "mean_shadow_ratio": 0.5391,
    "min_thermal_c": -129.25,
    "time_ms": 564.6
  },
  "LunaPath multi-criteria A*": {
    "waypoints": 426,
    "length_km": 2.498,
    "max_slope_deg": 24.99,
    "mean_shadow_ratio": 0.5259,
    "min_thermal_c": -56.12,
    "time_ms": 868.7
  }
}
```
