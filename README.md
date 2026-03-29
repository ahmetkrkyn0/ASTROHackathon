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
