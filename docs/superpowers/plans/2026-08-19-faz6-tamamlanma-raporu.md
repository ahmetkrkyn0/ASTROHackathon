# Faz 6 Tamamlanma Raporu

**Tarih:** 30 Ağustos 2026
**Branch:** `backend/physics`
**Plan:** [`2026-08-19-faz6-dogrulama.md`](2026-08-19-faz6-dogrulama.md)
**Master plan:** [`2026-08-19-lunapath-master-plan.md`](2026-08-19-lunapath-master-plan.md)
**Commit aralığı:** `09c90f6..4731978` (4 commit)

---

## Özet

Faz 6, altı fazlı entegrasyon planının sonuncusu. Dört görevin dördü de tamamlandı: **4 commit**, **33 yeni test**, hepsi yeşil.

Bu faz LunaPath'e yeni bir yetenek eklemiyor — mevcut rover kataloğunu ve termal modeli **dışarıdan doğrulanabilir** hâle getiriyor. Üç bağımsız katman:

| Görev | Modül | Test |
|---|---|---|
| 1 | `app/mission_reference.py` — kaynak künyeli gerçek misyon verisi | 9 |
| 2 | — (saf doğrulama) | 5 |
| 3 | `app/route_analysis.py` + `/api/plan` genişletmesi | 12 |
| 4 | `app/thermal_validation.py` + `scripts/diviner_validation.py` | 7 |

---

## Dürüstlük notu korundu

Bu fazdaki hiçbir test **nokta-doğruluk** iddiası kurmuyor. Yutu-2 altı yılı aşkın süredir Ay'da, zamanının çoğunu ay geceleri boyunca uykuda geçirerek; LunaPath görev-döngüsü (duty cycle) modellemiyor. Testler bu yüzden **gerekli koşul** kontrolleri: "gerçek misyon bu mesafeyi bu sürede aldıysa, rover sabitlerimiz bunu fiziksel olarak imkânsız kılmamalı."

Aynı ilke Diviner karşılaştırmasında da geçerli: gerçek referans veri repoda **yok**, indirme adımı otomatikleştirilmiyor. Script veri yokken ne yapılacağını yazdırıp **çıkış kodu 0** ile bitiyor ve rapor üretmiyor — sahte doğrulama verisi asla uydurulmuyor.

---

## Plandan sapmalar

Plan uygulanmadan önce satır satır doğrulandı. Dört gerçek hata bulundu; hepsi commit mesajlarında gerekçesiyle kayıtlı.

### 1. Task 2'nin üst sınır testi kendi verisiyle çelişiyordu (Kritik)

Plandaki `test_yutu2_profile_top_speed_is_not_absurdly_faster_than_reality`, `v_max`'i Yutu-2'nin oranı × `1e4` ile karşılaştırıyordu. Bu test **geçmez**:

```
Yutu-2 oranı (dormancy dahil) = 0.101 m/gün
Testin tavanı (0.101 × 1e4)   = 1012 m/gün
cnsa_yutu_2 v_max              = 4320 m/gün   ← tavanı 4.3× aşıyor
```

Sebep sabitte değil eşikte: 0.101 m/gün, yıllarca süren ay-gecesi uykusunu içeren bir takvim-günü ortalaması, sürüş hızını ~4 kat büyüklük mertebesi eksik gösteriyor.

Sınır **Pragyan'ın** 10.14 m/gün'ü üzerine yeniden kuruldu (tek kesintisiz on günlük pencere — planın kendi ifadesiyle "duty-cycle ambiguity here is small") ve çarpan `1e3` yapıldı. Yeni sınır doğru sabiti kabul ediyor, korunmaya değer birim hatalarını hâlâ yakalıyor:

| Senaryo | m/gün | Sonuç |
|---|---|---|
| Doğru (0.05 m/s) | 4 320 | geçer |
| km/h → m/s karışıklığı (×3.6) | 15 552 | **yakalanır** |
| Ondalık kayması (×10) | 43 200 | **yakalanır** |

Planın "testi gevşetme, sabiti incele" talimatına uyuldu: sabit doğru, eşik yanlıştı.

### 2. Histogram aralık dışı eğimleri sessizce düşürüyordu (Orta)

Planın binleme döngüsü, bin aralığı dışındaki değerleri hiçbir kovaya koymadan atlıyordu — özel bin seti veren bir çağrıda `count` toplamı `waypoint_count`'u tutmuyor, yani özet tarif ettiği rotayı eksik raporluyordu:

```
slope 30°, varsayılan binler → counts [0,0,0,0,0], waypoint_count 1
```

Aralık dışı değerler artık uç kovalara sıkıştırılıyor. Varsayılan binler zaten etkilenmiyordu (geçilebilirlik eğimi üst kenarda, 25°'de sınırlıyor); koruma kendi binlerini veren çağıranlar için. Tek kenarlı dejenere bin tanımı da artık boş histogram üretmek yerine hata veriyor.

### 3. Endpoint testi gerçek 500×500 grid'e karşı planlıyordu (Orta)

Planın testi sentetik grid'i `TestClient` context'ine **girmeden önce** enjekte ediyordu. Context'e giriş startup lifespan'ini çalıştırıyor, o da gerçek 500×500 işlenmiş grid'i üstüne yüklüyor — istek gerçek araziye karşı planlanıyor, seçilen başlangıç hücresi orada geçilebilir değil ve endpoint 422 dönüyor.

Enjeksiyon context'in içine alındı; önceki `app.state.grids` `finally` bloğuyla geri konuluyor, böylece test başka testlerin durumunu bozmuyor.

### 4. Diviner script'i `.npy` dosyasını rasterio ile açıyordu (Orta)

Plandaki script, model grid'ini kendi yorumunun "placeholder guard removed below" dediği bir blokta `rasterio.open` ile açıyordu — `.npy` rasterio ile okunabilir bir format değil, karşılaştırma başlamadan hata veriyordu. Georeferans, o yorumun amaçladığı gibi `metadata.json`'dan okunuyor.

Ek olarak script artık **model** grid'ini de kontrol ediyor: `thermal_grid.npy` şu an işlenmiş sette yok, bu kontrol olmadan gerçek Diviner verisi edinen bir kullanıcı çıplak `FileNotFoundError` alırdı. Her iki eksik-girdi yolu da ne yapılacağını yazdırıp rapor yazmadan çıkış 0 veriyor.

---

## Kabul kriterleri

| Kriter | Durum |
|---|---|
| `pytest` — tüm testler geçiyor | ✅ (aşağıya bakınız) |
| `python test_cost_engine.py` çıkış 0 | ✅ |
| `python test_traversability.py` çıkış 0 | ✅ |
| `test_rover_validation.py` gerçek Yutu-2/Pragyan verisine karşı geçiyor | ✅ 5/5 |
| `POST /api/plan` yanıtında `route_statistics` dolu | ✅ `slope_histogram` + `risk_breakdown_pct` doğrulandı |
| `scripts/diviner_validation.py` veri olmadan çökmeden çalışıyor | ✅ çıkış 0, rapor üretilmiyor |
| `mission_reference.py`'deki her rakamın satır içi kaynak atıfı var | ✅ 3/3 |

`route_statistics` canlı endpoint çıktısı (30×30 sentetik grid, 24 waypoint):

```json
{
  "waypoint_count": 24,
  "slope_histogram": [{"bin_low_deg": 0.0, "bin_high_deg": 5.0, "count": 24, "pct": 100.0}, ...],
  "risk_breakdown_pct": {"LOW": 100.0},
  "min_surface_temp_c": -60.0,
  "max_surface_temp_c": -60.0
}
```

Diviner hattı, sentetik bir referans raster'la uçtan uca da doğrulandı (model −60 °C, referans −55 °C → `bias_c` −5.0, `rmse_c` 5.0, `n_compared` 400) — yani reproject yolu yalnızca veri-yok dalında değil, gerçekten çalışıyor.

---

## Bilinen sınır

Bu faz **nokta-doğruluk** değil **gerekli koşul** doğrulaması yapıyor. Tam A/B/C/D ablasyon protokolü ve NASA-STD-7009 tarzı kredibilite skorkartı kapsam dışı — planın kendi "Sonraki aşamaya bırakılanlar" tablosunda [03](../../research/03_sentetik_minimum_veri.md) ve [09](../../research/09_olgunluk_kiyaslama.md)'a atıfla belirtildiği gibi.

Gerçek Diviner karşılaştırması **henüz yapılmadı**: referans veri manuel indirme gerektiriyor ve repoda yok. Kurulan hat, veri edinildiği an tek komutla çalışacak durumda.

---

## Sonraki adım

Yok — bu, altı fazlı entegrasyon planının sonuncusu. Branch `backend/physics`'te kalıyor; entegrasyon (merge/PR) kararı ayrıca verilecek.
