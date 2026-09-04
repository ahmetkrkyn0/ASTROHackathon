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

- Operasyonel planlayıcı rover'ın üstünde çalışmaz; gerçek zamanlı engel kaçınma
  ve yerel yeniden planlama hâlâ kapsam dışıdır. Ancak 3B görünüm, bu sınırı
  görünür ve test edilebilir kılmak için metre ölçekli kayalar üzerinde 360°,
  16 kanallı bir **yerel LiDAR algı simülasyonu** çalıştırır
  (`frontend/src/lidarSimulation.ts`). Bu nokta bulutu global rotayı değiştirmez.
- LiDAR planlayıcıya algı olarak değil, bir kaynak bütçesi kalemi olarak girer:
  `backend/app/sensor_payload.py` bir LiDAR taşımanın sürekli güç + ısıtıcı
  çekişini enerji bütçesine yansıtır.
- `lunapath/src/virtual_lidar.py`, çözünürlüğü metadata'dan alan yörünge-DEM
  tarayıcısıdır. Şu an kullanılan Site11 verisi 5 m/px'tir; onlarca metrelik
  taramada eğim ve sırtları ölçebilir fakat gerçek bir LiDAR'ın gördüğü metre-altı
  kayaları çözemez. Bu yerel engeller 3B sahnede açık kaya mesh'leriyle simüle
  edilir; DEM taraması ayrıca `Corridor` sözleşmesinin tüketicisi olarak kalır.
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

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r lunapath\requirements.txt
```

`process_lunar_data.py` backend modüllerini kullandığı için aynı ortamda her iki `requirements` dosyası pratikte birlikte kurulur.

**Frontend**

```bash
cd frontend
npm install
```

**Analiz asistanı (isteğe bağlı)**

Asistan olmadan da uygulamanın tamamı çalışır; yalnızca sohbet paneli
yapılandırılmamış olduğunu bildirir.

```bash
cp .env.example .env      # Windows: copy .env.example .env
```

`.env` içinde `LUNAPATH_OPENAI_API_KEY` alanını kendi anahtarınızla doldurun.
`LUNAPATH_OPENAI_MODEL` ve `LUNAPATH_AI_PROVIDER` örnekteki değerlerle bırakılabilir;
sağlayıcı olarak `stub` seçilirse gerçek model hiç çağrılmaz.

- `.env` sürüm kontrolüne **girmez** ve `.gitignore` tarafından yok sayılır;
  yalnızca `.env.example` izlenir.
- Anahtar yalnızca sunucu sürecinde okunur. Tarayıcıya gönderilen pakette ne
  anahtar ne de OpenAI istemcisi bulunur; sayfa yalnızca LunaPath backend'i ile
  konuşur.
- Dosya kendiliğinden yüklenmez; backend başlatılırken aşağıdaki `--env-file`
  bayrağı gerekir.

---

## Çalıştırma

1. **Backend** (varsayılan port `8000`):

   ```powershell
   cd backend
   ..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   Analiz asistanı için kökte `.env` oluşturduysanız komutun sonuna
   `--env-file ../.env` ekleyin. Proje venv'inin Python'unu açıkça kullanmak,
   sistem Python'undaki uyumsuz FastAPI/Starlette sürümlerinin devreye
   girmesini önler.

   Açıklık: `http://127.0.0.1:8000/docs`

   `--env-file` yalnızca analiz asistanı için gereklidir: uygulama `.env`
   dosyasını **kendiliğinden okumaz**, bu yüzden bayrak olmadan `/api/ai/chat`
   yapılandırma hatası döner. Planlama, harita ve telemetri bayraksız da normal
   çalışır.

2. **Frontend** (geliştirme; projede port `3000`, `/api` → `localhost:8000`):

   ```powershell
   cd frontend
   npm.cmd run dev
   ```

3. **DEM → ızgara** (isteğe bağlı; önce uygun GeoTIFF’i `lunapath/data/raw` veya üst dizindeki `data/raw` içine koyun; varsayılan dosya adı script içinde tanımlıdır):

   ```powershell
   cd lunapath/src
   ..\..\.venv\Scripts\python.exe process_lunar_data.py
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
