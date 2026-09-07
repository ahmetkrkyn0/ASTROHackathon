# LunaPath ROS 2 Kabuğu — Ne İşe Yarar, Nasıl Kullanılır

Bu belge pratik bir kullanım kılavuzudur. Kurulumun ham teknik detayları (kurulu Nav2/GridMap arayüz çıktıları, hangi ROS dağıtımı seçildi ve neden) için [`docs/ROS2_SETUP.md`](ROS2_SETUP.md); tasarım kararları ve gerekçeleri için [`docs/superpowers/plans/2026-08-19-faz4-ros2.md`](superpowers/plans/2026-08-19-faz4-ros2.md); bu fazda gerçekte ne yapıldığının özeti için [`docs/superpowers/plans/2026-08-19-faz4-tamamlanma-raporu.md`](superpowers/plans/2026-08-19-faz4-tamamlanma-raporu.md).

---

## Ne işimize yarıyor?

FastAPI kabuğu (`backend/app/main.py`) zaten çalışıyordu ve kalkmadı — hiçbir işlevini kaybetmedi. ROS 2 kabuğu (`lunapath_ros`) **aynı planlama çekirdeğini** ikinci, bağımsız bir arayüzden servis ediyor. Somut olarak şunları kazandırıyor:

1. **Gerçek robotik yığınıyla konuşma.** Bir rover'ın gerçek yazılımı (Nav2, TF, sensör sürücüleri) ROS 2 API'si bekler. ROS kabuğu olmadan LunaPath'in rotası hiçbir gerçek robotik sisteme bağlanamaz — sadece bir web tarayıcısında görüntülenebilirdi.
2. **Hazır görselleştirme.** RViz2 (ve isteğe bağlı Foxglove) ile araziyi ve rotayı 3B görmek için hiçbir özel frontend kodu yazmaya gerek yok — `grid_map` standart mesaj formatı bunu bedavaya getiriyor.
3. **Tekrar-üretilebilir kayıt.** `rosbag2` ile her plan koşumu (girdi katmanları + istek + sonuç) zaman damgalı kaydedilip **birebir replay edilebiliyor**. Saha testi ya da demo sonrası "tam olarak ne olmuştu" sorusuna somut kanıt.
4. **Nav2'ye karşı objektif kıyas.** Aynı DEM üzerinde LunaPath'in çok-kriterli A*'ı ile Nav2'nin `SmacPlanner2D`'sinin amaç fonksiyonunu (en kısa geçilebilir yol) üreten geometrik bir taban çizgisi karşılaştırılıyor — çok-kriterli maliyet modelinin **gerçekte ne kazandırdığı** sayısal olarak gösteriliyor (`scripts/nav2_baseline.py`).
5. **Uçuş taşınabilirliği.** Space ROS, ROS 2 API'siyle uyumlu. Bu kabuk uçuş-nitelikli bir bağlama taşındığında **yeniden yazılmaz, yalnızca yeniden derlenir**.

**Mimari bir cümlede:** `backend/app/` saf Python çekirdeği (A*, fizik, maliyet modeli) hem FastAPI'den hem ROS 2'den çağrılıyor; iki kabuk birbirinden habersiz, biri diğerinin yerine geçmiyor.

---

## Bu makinede kurulum durumu

WSL2 Ubuntu-24.04 içinde ROS 2 Jazzy zaten kurulu (`grid_map`, `navigation2`, `rosbag2` dahil). Repo Windows'ta geliştiriliyor, WSL'den `/mnt/c/Users/Berke/TUAASTROHackathon` altında görünüyor. Python çekirdeği (FastAPI + A*) Windows'ta kalıyor — yalnızca ROS düğümleri Linux tarafında (WSL) koşuyor.

---

## Hızlı başlangıç — tek launch komutuyla ayağa kaldır

Bir WSL terminali aç (`wsl -d Ubuntu`):

```bash
cd /mnt/c/Users/Berke/TUAASTROHackathon
source /opt/ros/jazzy/setup.bash
colcon build --packages-select lunapath_msgs lunapath_ros
source install/setup.bash
ros2 launch lunapath_ros lunapath.launch.py
```

Bu tek komut üç düğümü birden ayağa kaldırıyor:

| Düğüm | Ne yapar |
|---|---|
| `map_to_moon_map` | `map` ↔ `moon_map` birim (identity) transform'u — RViz'in `map`'i sabit çerçeve olarak kullanabilmesi için |
| `lunapath_grid_publisher` | Arazi katmanlarını (`elevation`, `slope`, `aspect`, `temperature`, `illumination`, `traversability`, `cost`) `/lunapath/grid_map`'te latched olarak yayınlar |
| `lunapath_planner` | `/plan_traverse` action server'ı — rota isteklerini karşılar |

`PYTHONPATH`'i elle `export` etmene gerek yok — launch dosyası `backend/`'i kendi konumundan otomatik buluyor.

---

## Rota isteği gönderme

Grid geometrisi asla sabitlenmiyor (bkz. master planın Global Constraints'i) — bu yüzden istek koordinatlarını elle yazmak yerine gerçek grid'den geçilebilir iki nokta türet:

```bash
python - <<'PY'
import json, pathlib, numpy as np, sys
sys.path.insert(0, "backend")
from app.grid_frame import pixel_to_map_xy
d = pathlib.Path("lunapath/data/processed")
m = json.loads((d / "metadata.json").read_text())
tr = np.load(d / "traversability_grid.npy").astype(bool)
idx = np.argwhere(tr)
start, goal = tuple(idx[len(idx)//4]), tuple(idx[3*len(idx)//4])
sx, sy = pixel_to_map_xy(*start, m)
gx, gy = pixel_to_map_xy(*goal, m)
print(f"""ros2 action send_goal /plan_traverse lunapath_msgs/action/PlanTraverse \\
'{{start: {{header: {{frame_id: "moon_map"}}, pose: {{position: {{x: {sx}, y: {sy}}}}}}},
  goal:  {{header: {{frame_id: "moon_map"}}, pose: {{position: {{x: {gx}, y: {gy}}}}}}},
  rover_id: "lpr_1",
  weights: {{w_slope: 0.409, w_energy: 0.259, w_shadow: 0.142, w_thermal: 0.19}},
  use_start: true}}' --feedback""")
PY
```

Yazdırılan komutu çalıştır. Başarılı bir yanıt: `error_code=0`, dolu bir `path` (`nav_msgs/Path`), dolu bir `corridor` (yerel planlayıcıya devredilecek güvenlik koridoru) ve sıfırdan farklı `metrics` (mesafe, enerji, batarya, süre).

**Kullanılabilir rover'lar:** `lpr_1` (varsayılan), `luvmi_m`, `nasa_viper`, `cnsa_yutu_2` — her birinin kendi eğim limiti var; `rover_id` değiştirildiğinde hem geçilebilirlik maskesi hem maliyet grid'i o rover'a göre yeniden hesaplanıyor (`backend/app/rover_grids.py` — FastAPI ve ROS kabukları aynı mantığı paylaşıyor).

### Hata kodları (Nav2 ile birebir aynı semantik)

| Kod | Anlamı |
|---|---|
| `0` (NONE) | Başarılı |
| `200` (UNKNOWN) | Beklenmedik sunucu hatası |
| `201` (INVALID_PLANNER) | Bilinmeyen `rover_id`, aralık dışı ağırlık, ya da sıfırdan farklı `epoch` (bu faz 4B planlamayı desteklemiyor) |
| `202` (TF_ERROR) | `use_start: false` gönderildi — bu düğümün TF'den robot pozu okuyan bir yolu yok |
| `203` / `204` | Başlangıç / hedef grid dışında |
| `205` / `206` | Başlangıç / hedef geçilemez (istenen rover için) |
| `208` (NO_VALID_PATH) | Grid içinde ama rota bulunamadı |

---

## RViz'de görselleştirme

```bash
rviz2 -d lunapath_ros/config/lunapath.rviz
```

Fixed Frame `moon_map`, `GridMap` display'i `/lunapath/grid_map`'e bağlı (`elevation` katmanı varsayılan, `cost` da denenebilir). Not: planlanan rota şu an sürekli bir topic'te değil, yalnızca action Result'ın içinde döndüğü için RViz'in Path display'inin canlı bir kaynağı yok — bir bag'i replay ederken (aşağıya bak) rotayı görebilirsin.

---

## Bir koşumu kaydetme / tekrar oynatma

```bash
./scripts/record_plan.sh bags/demo     # ayrı bir terminalde, launch çalışırken başlat
# ... rota isteğini gönder (yukarıdaki adım) ...
# Ctrl+C ile kaydı durdur

ros2 bag info bags/demo                # her topic için sıfırdan büyük mesaj sayısı göstermeli
ros2 bag play bags/demo                # kaydı birebir tekrar oynatır
```

`/lunapath/grid_map`, `/plan_traverse/_action/feedback`, `/plan_traverse/_action/status` ve `/tf_static` kaydediliyor. (`send_goal`/`get_result` birer servis, ROS 2'nin standart introspection'ı açık olmadığı için şu an kayıt kapsamı dışında — bkz. plan dosyasının "Bilinen sınırlar" tablosu.)

---

## Nav2'ye karşı kıyaslama

```bash
python scripts/nav2_baseline.py --start <r> <c> --goal <r> <c>
```

(ROS gerektirmez — sadece `backend/app` çekirdeğini kullanır, Windows'ta da çalışır.) `docs/research/nav2_baseline.md`'yi üretir: LunaPath'in çok-kriterli A*'ı ile geometrik/SmacPlanner2D-eşdeğeri taban çizgisini yan yana koyan bir tablo.

---

## Bilinen sınırlar (özet)

- `epoch` alanı okunmuyor — bu faz yalnızca 2B planlamayı servis ediyor (4B için Faz 6+).
- `use_start: false` desteklenmiyor — düğümün TF'den robot pozu okuyan bir yolu yok.
- Feedback yalnızca 0.0 ve 1.0 (başlangıç/bitiş) — `astar` bölünemez tek bir çağrı.
- Cancel yalnızca plan başlamadan önce etkili.
- Ayrı bir `corridor_publisher.py` yok — koridor, action Result'ın bir alanı.

Tam liste ve gerekçeleri: plan dosyasının "Bilinen sınırlar" tablosu.
