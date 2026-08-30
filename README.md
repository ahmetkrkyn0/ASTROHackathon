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
- `backend/app/slip_model.py` **UNCALIBRATED** etiketlidir: yön iddiası
  (eğimde enerji artar) taşır, büyüklük iddiası taşımaz.
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
