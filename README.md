# LunaPath — ASTRO Hackathon

## Amaç

LunaPath, Ay yüzeyi yükseklik verisinden türetilen analiz katmanları üzerinde **çok kriterli rota planlama** yapan bir hackathon prototipidir. Hedef; eğim, enerji, gölge ve termal risk gibi faktörleri bir arada değerlendirerek rover için uygun yollar üretmek ve sonucu **API + web arayüzü** ile göstermektir.

---

## Özellikler

- DEM’den ızgara katmanları (yükseklik, eğim, bakı, gölge proxy’si, termal, geçilebilirlik, maliyet) ve metadata üretimi
- **A\*** tabanlı yol planlama ve rota üzerinde **basitleştirilmiş enerji / risk simülasyonu**
- Birden fazla **rover profili** ve **misyon ağırlıkları** (eğim, enerji, gölge, termal)
- **FastAPI** REST API (`/docs` ile denenebilir)
- **React + TypeScript + Vite** ön yüzü; geliştirmede API proxy ile backend’e bağlanır
- İsteğe bağlı **Matplotlib** panosu ile işlenmiş verinin görsel özeti
- **LiDAR yük bütçesi**: bir LiDAR taşımanın enerji/termal maliyetini ölçen karşılaştırma (`scripts/lidar_payload_comparison.py`)

---

## Kapsam — LiDAR ve otonomi

LunaPath **rover'ın üstünde çalışmaz**; yörünge verisinden **küresel rota planlayan**
bir yer katmanı aracıdır. Bu yüzden:

- **LiDAR yok, çünkü LunaPath rover'ın üstünde çalışmıyor.** Gerçek zamanlı algı,
  engel kaçınma ve yerel yeniden planlama kapsam dışıdır.
- LiDAR sisteme **algı olarak değil, bir kaynak bütçesi kalemi olarak** girer:
  `backend/app/sensor_payload.py` bir LiDAR taşımanın sürekli güç + ısıtıcı
  çekişini enerji bütçesine yansıtır.
- `lunapath/src/virtual_lidar.py` bir **algı simülatörü değildir**. 80 m/px'lik
  yörünge DEM'i gerçek bir LiDAR'ın gördüğü 30 cm'lik kayaları çözemez; bu modül
  yalnızca `Corridor` sözleşmesinin bir yerel-katman tüketicisine yettiğini
  kanıtlayan bir **arayüz provasıdır**.
- Proje bir **"otonom navigasyon sistemi" değildir** — bkz.
  [docs/research/09_olgunluk_kiyaslama.md](docs/research/09_olgunluk_kiyaslama.md).

## Kapsam — odometri ve konum belirleme (Faz 7)

**LunaPath odometri üretmez; odometri tüketir ve yörünge DEM'iyle doğrular.**
Hiçbir SLAM/VO algoritması içermez, hiçbir odometri kütüphanesine bağlanmaz:

- Giriş sözleşmesi `backend/app/pose.py` (`PoseEstimate`) — herhangi bir
  odometri yığınının (tekerlek EKF, KISS-ICP, stereo VO) LunaPath'e nasıl
  bağlanacağını tanımlar; ROS tarafında karşılığı `nav_msgs/Odometry` aboneliğidir.
- `backend/app/skyline.py` bir konum belirleme ürünü değil, **arayüz ve
  fizibilite kanıtıdır**: DEM ufuk küpü (`horizon_map`) gözlenen bir ufuk
  profiliyle eşlenerek drift'siz mutlak konumun bu veriden çıkabildiğini
  gösterir; düz arazide eşleşme güvenilir diye değil, `ambiguity_ratio`
  etiketiyle döner.
- `backend/app/slip_model.py` **MODEL** etiketlidir (C3): eğri VIPER'ın
  15°/%40 tasarım kısıtına (PSJ 2025, GRC-1) ve Yutu-2'nin Chang'e-4'te
  ölçülmüş slip aralığına (0 … −0,075, ≤ 8,86°; Nat. Comms 2024) bağlı,
  çapalar arası üstel ve kapı 0,9; `edge_travel_time_s` üzerinden tek
  noktadan süre ve enerjiye girer. **Kutup regolitinde ölçülmüş değildir**;
  aktarılan çapalar katalogda `assumption:` ile yazılıdır. Önce/sonra:
  [docs/research/slip_calibration_report.md](docs/research/slip_calibration_report.md).
- Koridorun gerçek bir odometri hata bütçesiyle uyumu sayıyla gösterilir:
  [docs/research/localization_budget.md](docs/research/localization_budget.md).

---

## Proje yapısı

| Klasör | Rol |
|--------|-----|
| `backend/` | FastAPI uygulaması, planlama ve simülasyon mantığı |
| `frontend/` | Web arayüzü |
| `lunapath/` | DEM işleme script’leri ve `data/raw` · `data/processed` |
| `docs/` | Teknik referans ve tasarım notları |

---

## Gereksinimler

- **Python** 3.11+ (önerilir)
- **Node.js** 18+
- **rasterio** (GDAL bağımlılığı; kurulum işletim sistemine göre değişir)

---

## Kurulum

Depo kökünden (`ASTROHackathon/`):

**Backend**

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
pip install -r ../lunapath/requirements.txt
```

`process_lunar_data.py` backend modüllerini kullandığı için aynı ortamda her iki `requirements` dosyası pratikte birlikte kurulur.

**Frontend**

```bash
cd frontend
npm install
```

---

## Çalıştırma

1. **Backend** (varsayılan port `8000`):

   ```bash
   cd backend
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   Açıklık: `http://127.0.0.1:8000/docs`

2. **Frontend** (geliştirme; projede port `3000`, `/api` → `localhost:8000`):

   ```bash
   cd frontend
   npm run dev
   ```

3. **DEM → ızgara** (isteğe bağlı; önce uygun GeoTIFF’i `lunapath/data/raw` veya üst dizindeki `data/raw` içine koyun; varsayılan dosya adı script içinde tanımlıdır):

   ```bash
   cd lunapath/src
   python process_lunar_data.py
   ```

4. **Görsel özet** (işlenmiş `.npy` dosyaları hazırsa):

   ```bash
   cd lunapath/src
   python visualize_processed_data.py
   ```

Backend açılışta işlenmiş grid’leri bulursa yükler; bulamazsa API üzerinden `load-preprocessed` veya `load-dem` ile yükleme gerekir. Ayrıntılar için `http://127.0.0.1:8000/docs` ve `backend/app/main.py` içindeki uçlar yeterlidir.

---

## Veri

- P1 hattı için DEM dosyası script’in beklediği isim ve klasörlerde olmalıdır (`lunapath/src/process_lunar_data.py` ve README üstündeki `data/raw` mantığı).
- API ile doğrudan DEM yüklerken dosya `backend/data/dem/` altına konur (klasör yoksa oluşturulur).
- Belirsizlik katmanları (B3) için NASA PGDA'nın Site11 DEM klonları: `python scripts/build_dem_clone_cache.py` (varsayılan 20 klon, 1 km yakın-alan dolgusu; `--n-clones 100` ile genişletilir; `horizon_map.npy` varsa klon ufuk küplerini de üretir). Ürün: https://pgda.gsfc.nasa.gov/products/78
- Formal güvenlik monitörü (D3): gereksinimler `docs/requirements/lunapath.fret.json` (FRETISH + STL), robustness `rtamt==0.3.5` ile (requirements.txt'te; kurulu değilse yerleşik değerlendirici aynı sonucu verir ve yanıt `monitor.engine` ile söyler). Rapor: `python scripts/safety_monitor_report.py`.
- Sürekli-aydınlık koridoru (A2, CMU'nun sun-synchronous x-y-t budaması): `/api/plan-4d` `require_continuous_illumination` + `lit_rule`, yanıtta `illumination_corridor` bloğu ve `metrics.max_dwell_hours`; küp `GET /api/illumination-corridor?...&format=f32`. Rapor: `python scripts/illumination_corridor_report.py` (ufuk küpü + çekirdek gerekir).
- Slip kalibrasyonu (C3, Yutu-2 ölçümü + VIPER tasarım kısıtı): `/api/rovers` her rover'da `slip_model` (çapalar, kaynaklar, 0–25° tablo, etiket `MODEL`) ve `declared_only.regolith`; `/api/plan`, `/api/plan-4d`, `/api/compare`, `/api/plan-multi` yanıtlarında `slip_model` bloğu (rotanın ortalama/maks slip'i, slip'in eklediği saat ve Wh). Önce/sonra raporu: `python scripts/slip_calibration_report.py` (ufuk küpü + çekirdek gerekir).
- Risk iştahı (B2, CVaR — JPL STEP / Keio Endo vd.): `/api/plan` ve `/api/plan-4d` isteklerinde isteğe bağlı `risk_alpha` (0,5–0,999; verilmezse bugünkü grid bit-eşit; **α = 0,5 ortalama değildir**, μ + 0,798σ): eğim ve enerji kriterleri slip (C3 σ ⊕ B3 eğim σ, delta yöntemi) ve eğim (NASA DEM klonları) dağılımlarının CVaR kuyruğunu okur, süre/batarya/marjlar/Monte Carlo ortalama fizikte kalır; yanıtlarda `risk` bloğu (`validity: MODEL`, σ kaynakları, rotanın CVaR slip'i ve risk-ayarlı saat/Wh); `POST /api/risk-sweep` aynı çifti birkaç α'da yan yana planlar ("risk iştahı sürgüsü"). Termal CVaR uygulanmadı (kanca; kaynaklı σ yok). Rapor: `python scripts/risk_sweep_report.py` (klon önbelleği; 4-B bölümü için ufuk küpü + çekirdek).
- Ölçülmüş pürüzlülük ve PSR maskesi (C4, NASA PGDA ürün 90 — Barker vd. 2023): `python scripts/build_roughness_cache.py` LOLA LDRM 100 m tabanlı pürüzlülüğün (50 m/px) ve LPSR PSR maskesinin (20 m/px) Site11 pencerelerini `/vsicurl/` ile tek COG tile olarak indirir, 5 m gride `nearest` ile ko-registre eder (CRS eşitliği ve NASA'nın 100 m eğimi ↔ bizim blok eğimimiz Spearman ≥ 0,9 sağlaması; geçmezse yazmaz), bölgesel (80–90°S) ECDF ölçeğini `roughness_meta.json`'a koyar. Yüklendiğinde `roughness` ve `psr` katmanları `MEASURED` olarak `/api/terrain` ve `/api/layers/{ad}?format=f32`'de; pürüzlülük **beşinci maliyet kriteri** `f_roughness` (`w_roughness`, varsayılan 0,15 — varsayım; ölçek MODEL: hücrenin bölgedeki persentil sırası; 5 m hücre onu kapsayan 50 m pikselin blok istatistiğini taşır, kendi pürüzlülüğünü değil) olarak gride girer (`COST_MODEL_ID` v5; katman yokken dört terim bit-eşit v4). PSR planlamaya girmez: `/api/cell-telemetry` `in_psr`, `GET /api/psr-validation` (PGDA maskesi ↔ `shadow_ratio ≥ 0,99` Jaccard). Rapor: `python scripts/roughness_psr_report.py` (önbellek; 4-B bölümü için ufuk küpü + çekirdek).
- Dış benchmark MoonPlanBench (D2, Chancán vd. 2025, arXiv 2512.21438; veri CC BY-NC-SA 4.0, depoya girmez): `python scripts/build_moonplanbench_cache.py` 36 occupancy haritasını (12 LOLA kutup LDEM ürünü × 10/15/20° eşik, 64× altörneklenmiş: hücre 320 m – 7,7 km) yazarların Google Drive klasöründen `lunapath/data/benchmarks/moonplanbench/` altına indirir (dosya başına SHA-256'lı meta JSON). `python scripts/moonplanbench_runner.py [--reference-dir <PlanetaryPathBench klonu>] [--memory]` her haritada benchmark'ın kendi başlangıç/hedef kuralıyla dört modu (saf mesafe Dijkstra köşe-kesmeli = benchmark'ın hareket modeli / kesmesiz = LunaPath kuralı, LunaPath A* tek kriter / çok kriter) PathBench'in metrik tanımlarıyla koşturup makalenin Tablo 1'i (alıntı) ile yan yana koyar → `docs/research/moonplanbench_report.md`. Köşe-kesmeli Dijkstra makalenin Dijkstra yol uzunluklarını üç varyantta aynen üretir (651,81 / 636,16 / 620,24 hücre); LunaPath'in köşe-kesme yasağıyla 10° varyantında 12 haritanın 8'i bağlantısızdır. Haritalar yalnız occupancy olduğundan çok kriterli maliyet gridi tek değerdir: gölge/termal kazancı bu benchmark'ta ölçülemez, Site11'de ölçülür.

---

## Daha fazla bilgi

- [docs/lunapath_referans_belgesi_2.md](docs/lunapath_referans_belgesi_2.md) — formüller, sabitler, maliyet modeli
- [docs/stitch_design_brief.md](docs/stitch_design_brief.md) — arayüz tasarım notları

**Testler** (backend): `cd backend && pytest`

---

## Ekip

Tuna DENİZ
Ahmet KARAKOYUN
Göktuğ TABAK
Oğuzhan TARHAN
Berke KUŞ

---

*Hackathon / demo amaçlıdır; gerçek görev analizi yerine geçmez. Uzay verilerinin lisans ve kullanım koşullarına uygun kullanın.*
