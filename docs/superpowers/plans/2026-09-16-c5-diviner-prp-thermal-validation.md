# C5 — Diviner PRP termal doğrulama — Uygulama Planı

**Tasarım:** [2026-09-16-c5-diviner-prp-thermal-validation-design.md](../specs/2026-09-16-c5-diviner-prp-thermal-validation-design.md)
· **Dal:** `tuna/backendEnhance` · **Tarih:** 16 Eylül 2026

C5 bir **doğrulama** özelliğidir: hiçbir fizik eklemez, hiçbir planlayıcı sayısını
değiştirmez. Adımlar ona göre sıralı — önce referansı diske indir, sonra ölç, sonra
hiçbir şeyin kıpırdamadığını kanıtla.

---

## Adım 0 — Referans ölçümü (kod yazmadan)

Temiz HEAD'de (`e7f6cbe`) tam paketi koş ve FAILED listesini sakla. C2'nin dersi:
"önceden vardı" demeden önce ölç.

- [x] `cd backend && python -m pytest -q -p no:randomly`
- [x] Sonuç: **25 failed, 2 280 passed, 5 skipped** (33 dk 36 s), hepsi `*_real_grid.py`
- [x] `ruff check backend/app` → **12 hata** (C5 bu sayıyı artırmamalı)

---

## Adım 1 — Ürünü bul ve biçimini birinci elden oku

Araştırma belgesi ürün adını veriyor ama adres vermiyor; verdiği PDS3 yolu 404.

- [x] PDS Geosciences Diviner sayfasından gerçek koleksiyon yolunu çıkar
- [x] `dlre_prp_south.lbl`, `label/dlre_prp.fmt`, `catalog/prpds.cat` dosyalarını oku
- [x] Sütun anlamlarını ve birimleri **etiketten** doğrula (varsayma)
- [x] Aralıklı `GET` ile gerçek satırları gör, ayrıştırıcıyı kısmi dosyada prova et

**Çıktı:** spec'in "Kaynak notu" bölümü; üç kaynak-içi uyumsuzluk kayda geçti.

---

## Adım 2 — `.gitignore` (indirmeden ÖNCE)

605 MB'lık ham dosyanın bir an bile takip edilebilir olmaması için önce bu.

- [x] `lunapath/data/raw/dlre_prp_south.{tab,lbl}` ve
      `lunapath/data/processed/diviner_prp{.npz,_meta.json}` satırları
- [x] `git check-ignore -v` ile dördünü de doğrula

> Not: köke çapalı `data/raw/` deseni `lunapath/data/raw/` yolunu **kapsamıyor**;
> mevcut dosyalar yalnızca `*.tif`/`*.img` sayesinde kaçıyordu. C6'nın `.npz` için
> yaşadığı boşluğun aynısı.

---

## Adım 3 — `scripts/build_diviner_prp_cache.py`

C4'ün "indir → önbelleğe al → künye yaz" deseni.

- [x] `.part` üzerinden akıtarak indir; yarım dosya tam görünmesin
- [x] İndirilenin boyutunu etiketin `RECORD_BYTES × (FILE_RECORDS + 1)` değerine karşı
      doğrula, tutmuyorsa **ayrıştırma**
- [x] Tek geçişte ayrıştır (`np.fromstring`, metin kipi — pandas 10× hızlı ama
      `backend/requirements.txt`'te yok, bir doğrulama özelliği bağımlılık eklemek için
      zayıf bir gerekçe)
- [x] Üçgen normalinden **alan, eğim, gerçek-kuzeye göre bakı** türet
- [x] Köşeleri yalnız −88,5°'nin kutup tarafı için sakla (yoksa +104 MB)
- [x] Künye: URL'ler, **SHA-256**, bayt, satır, sütun anlamları, `validity: DERIVED`
- [x] İndirme başarısızsa **hiçbir şey yazmadan** çık ve nedenini söyle

**Ölçüldü:** 56 s; 2 880 000 üçgen; medyan alan 0,1279 km² (~544 m kenar);
enlem −89,992…−75,901; npz 66,6 MB.

---

## Adım 4 — `backend/app/thermal_validation.py` genişletmesi

- [x] `thermal_comparison` **aynen** korunur (yedi mevcut test kıpırdamaz)
- [x] `destination_transform` silinen betikten buraya taşınır (H-3 dersi korunur)
- [x] `spearman_rho`, `rmse_ci95`, `error_statistics`, `compare_candidates`
- [x] `triangle_areas_km2`, `assign_cells_to_facets`, `aggregate_to_facets`,
      `grid_cell_centres`, `kelvin_to_c`
- [x] `cold_trap_area_check` — Williams'ın sayısını kendi aritmetiğimizle üret
- [x] `PRP_QUOTED`, `WILLIAMS_QUOTED` — onların sayıları, bizimkinden ayrı

---

## Adım 5 — Konsolidasyon (spec'teki (a) kararı)

- [x] `scripts/diviner_validation.py` **silindi** (`git rm`)
- [x] `backend/test_review2_fixes.py`'deki iki H-3 testi `app.thermal_validation`'a
      yönlendirildi; **iddialar değişmedi**
- [x] `backend/app/slip_model.py`'deki iki atıf yeni betiğe güncellendi
- [x] Aynı docstring'lerdeki **bayat etiket** düzeltildi: "`thermal_grid.npy` is
      SYNTHETIC" doğru değil — `metadata.json` termal katmanı `DERIVED` diyor ve grid
      `Heat1DModel` çıktısı; SYNTHETIC yalnız heat1d yokken geçerli (C2'nin
      "etiketin yalan söylemesine izin verme" dersi)

---

## Adım 6 — `scripts/validate_thermal.py`

- [x] Üç aday da ölçülür ve **üçünün de** RMSE'si yayımlanır
- [x] Karşılaştırma **kabanın çözünürlüğünde**: 5 m gridimiz her üçgenin ayak izinde
      toplulaştırılır; PRP 5 m'e interpolasyon **yapılmaz**
- [x] Ortalama **ve** maksimum toplulaştırma yan yana; hangisinin dürüst eşdeğer
      olduğu gerekçesiyle yazılır
- [x] Enlem eşlenmiş LUT bölümü (n ~ 5 000), bakı marjinalleştirilmiş **ve** çözümlenmiş
- [x] Bakı çerçevesi için tanısal döndürme taraması (5° adım)
- [x] `cold_trap_area_check`
- [x] Williams gece minimumu yoksa `unavailable` + gerekçe
- [x] `--json` / `--from-json`; önbellek yoksa **yazmadan** çıkar (exit 2)

---

## Adım 7 — Testler

- [x] `backend/test_thermal_validation.py`: 17 yeni birim testi (toplam 24)
- [x] `backend/test_thermal_validation_real_grid.py`: 17 skip-korumalı gerçek-grid testi
- [x] Bit-eşitlik kilidi **LPR-1'e** kurulu (VIPER özeti C5'ten önce de tutmuyordu —
      4af6989'un `slope_max_deg` 20°→15° düzeltmesi; kovalanmadı, gerekçesi yazıldı)
- [x] `COST_MODEL_ID` hâlâ `…_v5`
- [x] `layer_validity` yükselmedi (C4'ün kararı korundu)

---

## Adım 8 — Belgeler

- [x] `docs/research/thermal_validation_report.md` (betiğin ürettiği)
- [x] `docs/frontend/3b-veri-sozlesmesi.md` → "C5 eki", `## Değişmeyenler` başlığından
      ÖNCE, **yalnızca ekleme** (`git diff --numstat` ile doğrulanacak: silme 0)
- [x] `README.md`'ye bir satır (önbellek yoksa devre dışı olduğunu söyleyerek)
- [x] Araştırma belgesinde `## C5.` başlığına ✅ + "Yapıldı" bloğu
- [x] Spec'in "Uygulama sırasında bulunanlar ve ölçümler" bölümü

---

## Adım 9 — Doğrulama

- [x] Tam paket, C5 ile; FAILED listesi adım 0'ınkiyle `comm` ile karşılaştırılır
- [x] `ruff check backend/app` hâlâ 12; yeni dosyalar 0
- [x] Önbellek yokken: betik yazmadan çıkar, gerçek-grid testleri atlar
- [x] Rapor `--from-json` ile birebir yeniden üretilir
- [x] `git status` temiz — `lunapath/data/` commit'e girmez

---

## Sapmalar

Uygulama sırasında tasarımdan ayrılan noktalar:

1. **LUT karşılaştırması için heat1d yeniden koşulmadı.** Tablo gönderilen gridden
   geri kazanıldı (her hücre zaten bir tablo girdisi; kutu başına mod alındı). 12–15
   dakikalık bir yeniden kurulum yerine bedava, ve **planlayıcının gerçekten okuduğu**
   tabloyu verir. Sadakati ölçüldü ve rapora yazıldı (%22,96 hücre tutmuyor, en büyük
   fark 5,89 °C, hep komşu kutu).
2. **Enlem şeridi pencerenin kendi enlem aralığına kilitlendi** (±0,05° değil, tam
   pencere aralığı). Gerekçe: −88,9°'de Güneş'in maksimum yüksekliği enlemle hızla
   değişiyor; geniş bir şerit tabloyu başka bir aydınlanmaya karşı koyardı.
3. **Döndürme taraması 15° yerine 5° adımla.** 15°'te minimum 285–300 arasında
   belirsizdi; 5° onu 295°'e oturttu ve öngörülen daldan 7,7° uzakta olduğunu gösterdi.
4. **Yakınsamanın işareti tarama tarafından seçildi.** Büyüklük geometriden geliyor
   (72,67°) ama işaret CRS'in eksen konvansiyonuna bağlı; iki dal da yazıldı ve
   hangisinin olduğunu ölçümün söylemesine izin verildi.
5. **Bir API ucu eklenmedi.** Tasarımda "isteğe bağlı" olarak duruyordu; C5'in ürettiği
   şey bir rapor, bir çalışma zamanı katmanı değil. Uç eklemek `layer_validity`
   yüzeyine dokunmayı gerektirirdi ve bu, bit-eşitlik iddiasını gereksizce
   genişletirdi.
6. **`test_review2_fixes.py`'nin iki testi silinmedi, yönlendirildi.** Spec "yönlendir"
   diyordu; uygulamada bu, `_diviner_module()` yardımcısının gövdesini bir `import`'a
   indirmek oldu — iddialar tek karakter değişmedi.
