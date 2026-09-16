# D6 — Enerji-erişilebilirlik izokronları (plan)

Tasarım: [2026-09-16-d6-enerji-izokronlari-design.md](../specs/2026-09-16-d6-enerji-izokronlari-design.md)
Dal: `tuna/backendEnhance` · Tek commit · Durum: **tamamlandı**

## 0. Önce ölç (kod yazmadan)

- [x] `move_battery_drain_wh` gerçekten negatife iniyor mu? Düz hücrede başabaş gölge
      oranını kapalı formda çıkar: LPR-1 **0,3908**, VIPER **0,2400**.
- [x] Site11'de kaç negatif kenar var? coarsen 4, 48 dilim, 8 yön, sekiz epoch.
      **2026-09-05'te sürüş kenarlarının %28,94'ü, bekleme kenarlarının %53,9'u negatif;
      2026-09-01'de tam olarak sıfır.** → Dijkstra elenir, ve elenme gerekçesi ölçülmüş
      olur.
- [x] Tompkins 2005'i gerçekten oku (192 s, PDF'ten tam metin). Dört düzeltme çıktı
      (bkz. spec §3), `REACHABILITY_CORRECTIONS`'a yazıldı.
- [x] arXiv 2509.15062'yi doğrula (softplus/SCP/NMPC **doğru**; erişilebilirlik kümesi
      hesaplamıyor). Sakayori & Ishigami 2021 ödeme duvarında — “Fast Marching” atfı
      **doğrulanamadı**, öyle yazıldı.
- [x] `dt` kaç farklı değer alıyor? Site11 coarsen 4'te **14** → gruplu vektörize
      saçılım uygulanabilir.

## 1. Modül

- [x] `backend/app/reachability.py`
  - [x] kimlik/iddia blokları: `REACHABILITY_MODEL_ID`, `_VALIDITY`, `_SCOPE`, `_CLAIM`,
        `_REFERENCES`, `_QUOTED`, `_CORRECTIONS`, `PLANNER_CONFIGURATION`,
        `GATES_REPLAYED` / `GATES_NOT_REPLAYED`, `CONSERVATISM`,
        `UNCERTAINTY_NOT_PROPAGATED`
  - [x] `coarse_shadow_cube` — parça parça (64 dilim) kur, hemen kabalaştır, **ilk**
        parçanın provenance'ını döndür
  - [x] `sweep` — ileri, zaman-genişletilmiş; `best_soc` + `min_dark`; halka tamponu
        (`max_dt + 1`); `(yön, açıklık)` grupları bir kez hesaplanıp her dilimde
        yeniden kullanılıyor; reddetme sayaçları; negatif kenar sayacı; ödenmemiş
        rölanti istatistiği
  - [x] `hold_times` + `hold_limit` — kendi ekseninde, üç saat, `hold_limited_by`
  - [x] `isochrone_bands` + `band_boundary_cells` — saf numpy, merdiven, yumuşatma yok
  - [x] `compare_fields` — “N saat sonra”, cevaplamadığı soruyu adıyla söyleyen
  - [x] `edge_group_count` — işi sınırlamak için
- [x] `ruff check backend/app/reachability.py` → 0

## 2. Uç

- [x] `backend/app/main.py`'ye `POST /api/reachable` (yalnızca ekleme)
  - [x] `ReachableRequest`, `extra="forbid"`, **`weights` alanı yok** (gerekçe
        docstring'de)
  - [x] `start_utc` **zorunlu**; `time_varying` değilse 422
  - [x] `_validate_start_goal` birebir (başlangıç iki rolde de veriliyor; “start”
        etiketi her zaman önce tetikleniyor)
  - [x] `_coarse_geometry` birebir (bölünebilirlik 422'si oradan)
  - [x] 422'ler: rezervin altında SOC, geçilemez kaba blok, dilim tavanı, blok tavanı,
        küp bütçesi, grup-adımı bütçesi, bant kenarları, `include_grids` yanıt tavanı,
        duruş ufku bütçesi
  - [x] `later_hours` tam dilime yuvarlanıyor ve yuvarlanmış değer yayımlanıyor
  - [x] JSON'a hiçbir `nan`/`inf` sızmıyor (`_reachable_grid_payload`, `_nan_min/max`)

## 3. Testler

- [x] `backend/test_reachability.py` — 30 test
  - [x] **kesinlik**: kaba kuvvetle bütün etiket dizileri sayılıp karşılaştırıldı
  - [x] **içerme**: `astar_4d`'in rota bulduğu her blok kümede
  - [x] drain aritmetiği planlayıcının satır içi ifadesiyle `==`
  - [x] `DARK_RATIO_THRESHOLD`, `OFFSETS`, `ENDURANCE_SLACK_H` planlayıcıyla eşit
  - [x] reddetme sayaçları, `energy_binds`, negatif kenarlar
  - [x] duruş saatleri, bantlar, sınır blokları, epoch kaydırma
- [x] `backend/test_reachability_api.py` — 18 test (her 422 + sözleşme)
- [x] `backend/test_reachability_real_grid.py` — 16 test (skip-korumalı)
  - [x] LPR-1 v5 digest kilidi + `COST_MODEL_ID`
  - [x] `/api/plan` ve `/api/plan-4d` değişmedi — **kontrol ölçülerek** (bkz. spec B9)
  - [x] Site11'de içerme, örneklenmiş
  - [x] VIPER coarsen 4 reddi + coarsen 2 cevabı
  - [x] JSON'da finite olmayan değer yok

## 4. Rapor

- [x] `scripts/reachability_report.py` (`--json`, `--from-json`, `--out`)
- [x] `docs/research/reachability_report.md` (265 s ölçüm)
- [x] `--from-json` raporu **birebir** yeniden üretiyor (SHA-256 `494c9a198dc36a29…`
      iki yolda da aynı)

## 5. Dokümanlar

- [x] spec + plan (bu dosyalar)
- [x] `docs/frontend/3b-veri-sozlesmesi.md` → “D6 eki”, `## Değişmeyenler`'den **önce**,
      yalnızca ekleme (`git diff --numstat` ile doğrulandı)
- [x] `README.md` bir satır
- [x] Araştırma belgesinde `## D6.` başlığına ✅ ve “Yapıldı” bloğu

## 6. Doğrulama

- [x] `cd backend && python -m pytest -q -p no:randomly`
- [x] `ruff check backend/app` taban 12'de kalıyor, yeni dosyalar 0
- [x] `lunapath/data/processed/metadata.json` commit'e alınmadı
