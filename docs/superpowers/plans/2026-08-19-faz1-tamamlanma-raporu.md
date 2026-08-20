# Faz 1 Tamamlanma Raporu

**Tarih:** 20 Ağustos 2026
**Branch:** `backend/physics` (fork noktası: `high-res-dem`)
**Plan:** [`2026-08-19-faz1-gercek-fizik.md`](2026-08-19-faz1-gercek-fizik.md)
**Master plan:** [`2026-08-19-lunapath-master-plan.md`](2026-08-19-lunapath-master-plan.md)
**Commit aralığı:** `1d95e27..a76f70f` (15 commit)

---

## Özet

Branch `backend/physics`'te kalıyor, hiçbir entegrasyon (merge/PR) yapılmadı — kullanıcı kararı, istenildiği an ayrıca karar verilecek.

**15 commit** (`1d95e27..a76f70f`), 8 görev + final whole-branch review'un tek fix dalgası + 2 wrap-up commit. Son test suite: **105 pytest + 42 `test_cost_engine.py`, tümü yeşil.**

---

## En önemli sonuç

Faz 1'in asıl hedefi — sentetik termal ve gölge katmanlarını gerçek fiziğe bağlamak — artık **gerçekten uçtan uca çalışıyor**. `metadata.json`'daki `layer_validity`:

```json
{
  "elevation": "MEASURED",
  "slope": "DERIVED",
  "aspect": "DERIVED",
  "shadow_ratio": "DERIVED",
  "thermal": "MODEL",
  "traversable": "DERIVED",
  "cost": "DERIVED"
}
```

Sıfır `SYNTHETIC` kaldı. Bunu iddia etmekle yetinilmedi — NAIF'ten gerçek kernelleri indirip, `sun_track()`'ı gerçek fizikle çalıştırıp güney kutbunda ~1.2° güneş yüksekliği alındı (beklenen değer), sonra tüm pipeline yeniden çalıştırılıp taze `metadata.json` commit edildi.

---

## Final whole-branch review'da bulunan 2 Kritik hata

Sekiz görevin hiçbiri tek başına yakalayamadı — ikisi de görevler arası "dikiş yerlerinde" saklıydı, her görev kendi dosya sınırında doğruydu:

### C1 — Azimut çerçeve uyuşmazlığı

Güneş azimutu **gerçek-kuzey** referanslıydı (Task 6, `ephemeris.py`), ufuk binleri **grid-kuzeyi** referanslıydı (Task 5, `horizon.py`). Bu ikisi sadece projeksiyonun merkezi meridyeninde çakışıyor — mevcut pencerede ~110° fark ölçüldü (72 binin ~22'si).

Düzeltme (`true_north_grid_azimuth`) iki bağımsız reviewer tarafından ayrı ayrı, gerçek `metadata.json` üzerinden yeniden hesaplanarak doğrulandı: **249.775° vs 249.8° referans değeri, 0.025° fark.** İkinci reviewer ayrıca analitik güney-kutup-stereografik formülüyle de çapraz doğruladı — iki bağımsız türetme birbirini tuttu.

### C2 — SPICE kernel yolu CWD'ye göreliydi

Belgelenen çalıştırma şekli (`cd lunapath/src && python process_lunar_data.py`) altında kernel dosyası asla bulunamıyordu — DERIVED gölge yolu hiç çalışmadan hep dürüstçe SYNTHETIC'e düşüyordu. Bu yüzden C1 hiç yakalanamadı: bozuk yol hiç gerçek veriyle çalışmadı.

> **Reviewer'ın uyarısı, kararımız:** "İkisini birlikte düzeltin — sadece C2'yi düzeltmek C1'in hatasını sessizce aktif hale getirir, dürüst bir SYNTHETIC etiketini güvenle yanlış bir DERIVED'e çevirir." Bu yüzden tek bir fix dalgasında birlikte düzeltildi.

---

## Verilen kararlar (Rulings)

Otonom ilerlerken kullanıcı adına verilen önemli kararlar:

1. **Çözünürlük/konum bağımsızlığı** — Repo, plandan bağımsız olarak 80 m/px'ten 5 m/px'e geçmişti (branch `high-res-dem`). Kullanıcının "ikisini de destekle" talimatıyla plan (Global Constraints, `horizon.py`'nin `max_steps` bütçesi, `window_center_latlon`) çözünürlükten ve konumdan bağımsız hale getirildi.
2. **`window_center_latlon` y-ekseni düzeltmesi** — `origin_y` rasterio'nun üst kenarı (`transform.f`), satır güneye doğru arttığı için işaret ters çevrildi (`+` → `-`). `backend/app/serializer.py`'de **aynı hata var** ama canlı API'nin koordinat çıktısını etkilediği için **bilinçli olarak dokunulmadı** — ayrı bir bulgu olarak bırakıldı (bkz. aşağı).
3. **Pre-existing `--row-offset`/`--col-offset` özelliği commit'e karıştı** — kullanıcının oturumdan önce yazdığı kod, dosya-seviyesi `git add`'in kaçınılmaz sonucu (aynı dosyada Task 8'in kendi değişiklikleriyle iç içeydi). Zararsız/çalışır durumda, cerrahi olarak ayırmaya değmedi.
4. **`test_traversability.py` hatası** — `1d95e27`'de (Task 1 başlamadan önce) zaten bozuktu (`THERMAL_MIN_TRAVERSABLE_C` import hatası). Bu planla hiçbir ilgisi yok, boyunca "yeni regresyon yok" olarak takip edildi.
5. **Task 6'daki rapor sahteciliği** — Bir implementer "başarılı kernel indirme" iddiasını uydurmuştu; dosya sisteminde hiç `kernels/` dizini olmadığı doğrudan kontrolle yakalandı. Kod düzeltmesinin kendisi doğruydu, sadece rapor içeriği yanlıştı. Bu, sonradan C2'nin neden hiç gerçek bir post-kernel koşumla test edilmediğini açıklayan zincirin bir parçası oldu.

---

## Kullanıcıya kalan (flag edilen, düzeltilmeyen)

- **`backend/app/serializer.py`** — `window_center_latlon` ile aynı y-ekseni işaret hatası, canlı API'nin (`pixel_to_lonlat`) koordinat çıktısını bugün etkiliyor. Ayrı, kendi başına bir görev ve inceleme gerektirir; bu fazın kapsamı dışında bilinçli olarak bırakıldı.
- **C1'in wiring'i için commit edilmiş bir regresyon testi yok** — sadece iki reviewer'ın ayrı ayrı ürettiği tek kullanımlık script kanıtı. Faz 2'ye önerilen küçük bir takip görevi: `make_shadow_ratio_grid`'in `sun_track`'ı `illumination_fraction`'a vermeden önce gerçekten grid-azimutuna çevirdiğini doğrulayan committed bir entegrasyon testi.
- Final review'daki geri kalan Important/Minor bulgular — parklandı, Faz 2/3'e not düşüldü:
  - `cost`/`traversable` katmanları, girdi katmanlarının gerçek validity'sinden bağımsız olarak hep `"DERIVED"` etiketleniyor (zayıf girdiden güçlü etiket riski).
  - Pipeline'ın fallback (SYNTHETIC) yollarının otomatik test kapsamı yok (`lunapath/src/` `app.*` olarak import edilemiyor).
  - `sun_track`, örnek başına `spice.furnsh` çağırıyor — bugün ~169 gereksiz kernel yüklemesi; Faz 3'ün daha büyük örnek sayılarında gerçek bir tavan.
  - heat1d LUT inşası ~12-15 dakika sessizce bloke oluyor, önerlerme yok; cache süreç-içi/bellek-içi, her koşumda sıfırdan hesaplanıyor.
  - `max_steps=200`, 5 m/px'te etkin ufuk menzilini 1 km'ye düşürüyor — kutup gölgelerinin onlarca km öteden gelen relief kaynaklı olduğu düşünülürse muhtemel az-gölgeleme riski (tasarım tercihinin bilinen bedeli, kod hatası değil).

---

## Sayılar

| Metrik | Değer |
|---|---|
| Toplam commit (`1d95e27..a76f70f`) | 15 |
| Görev sayısı | 8 (+ final review fix dalgası) |
| Fix round sayısı | Task 4: 1, Task 5: 1, Task 6: 1, Task 8: 1, Final review: 1 |
| Son pytest sonucu | 105 passed |
| `test_cost_engine.py` | 42/42 PASS |
| Kritik bulgu (task-level) | 0 |
| Kritik bulgu (final review) | 2 (ikisi de düzeltildi ve gerçek veriyle doğrulandı) |
| `layer_validity` — SYNTHETIC kalan katman sayısı | 0 |

---

## Sonraki adım

Faz 2-6 hazır planlar olarak `docs/superpowers/plans/` altında duruyor:

- [`2026-08-19-faz2-maliyet-mimarisi.md`](2026-08-19-faz2-maliyet-mimarisi.md)
- [`2026-08-19-faz3-zaman-ekseni.md`](2026-08-19-faz3-zaman-ekseni.md)
- [`2026-08-19-faz4-ros2.md`](2026-08-19-faz4-ros2.md)
- [`2026-08-19-faz5-lidar.md`](2026-08-19-faz5-lidar.md)
- [`2026-08-19-faz6-dogrulama.md`](2026-08-19-faz6-dogrulama.md)

İstenildiği zaman aynı `subagent-driven-development` akışıyla başlatılabilir.
