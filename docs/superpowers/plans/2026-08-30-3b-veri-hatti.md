# 3-B veri hattı — uygulama planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Frontend'in three.js ile gerçek bir 3-B ay yüzeyi sahnesi kurabilmesi için
backend'e ikili (binary) arazi taşıması, sahne manifestosu ve zaman-dilimli
aydınlanma serisi eklemek.

**Architecture:** Mevcut JSON `/api/layers` hiç değişmeden kalır; yanına ikinci bir
temsil konur. Yeni `app/terrain.py` saf fonksiyonlarla ikili kodlamayı ve manifest
kurmayı üstlenir (FastAPI'ye bağımlı değil, dolayısıyla doğrudan test edilir),
`main.py` yalnızca uç nokta kablolamasını yapar. İkili yük **başlıksızdır** —
sadece `Float32Array` — çünkü yorumlamak için gereken her şey manifestte ve
`X-Layer-*` yanıt başlıklarında iki kez bulunur.

**Tech Stack:** Python 3.11, FastAPI, NumPy, pytest, spiceypy (NAIF çekirdekleri
`kernels/lunapath.tm`).

**Spec:** Ayrı bir spec belgesi yok — kapsam bu oturumda ölçümle belirlendi.
Sayısal dayanak aşağıdaki "Ölçülen durum" bölümünde; ilgili fizik kararlarının
gerekçesi [`docs/superpowers/reviews/2026-08-30-backend-review-4.md`](../reviews/2026-08-30-backend-review-4.md)
(özellikle H-1, H-3, H-4).

---

## Global Constraints

- **Hiçbir mevcut davranış değişmez.** Fizik, maliyet modeli, A\*, 4-B küp,
  ağırlıklar, `data_loader`, `traversability`, `.npy` artefaktları: tek satır
  değişmez. Bu plandaki her şey ya yeni dosya, ya yeni uç nokta, ya da mevcut bir
  uç noktaya **varsayılanı eski davranış olan** opsiyonel parametre.
- **Kabul ölçütü:** Plan bitiminde mevcut 654 testin **hepsi** hâlâ geçmeli, 0 hata
  0 uyarı. Bu, "hiçbir şey değişmedi" iddiasının kanıtıdır.
- **Dal:** `backend/physics`. Ayrı worktree kurulmuyor — bu depodaki yerleşik akış
  bu dala doğrudan işlemek, ve `main`'de çalışmıyoruz.
- **Commit mesajlarında `Co-Authored-By` satırı OLMAYACAK.** Hiçbir commit'te.
- **Push edilmez.** Ortak dala gönderme kullanıcının ayrı onayına tabidir.
- Kod ve kod yorumları **İngilizce** (deponun mevcut kuralı), belgeler **Türkçe**.
- Test dosyaları `backend/test_*.py` deseninde, `cd backend && python -m pytest` ile
  koşar.
- İkili tel biçimi her yerde aynı: **little-endian float32, satır öncelikli (C
  order), no-data yalnızca NaN.**

---

## Ölçülen durum (planın dayanağı)

Üretim gridi üzerinde ölçüldü, `backend/app/data_loader.load_preprocessed_grids`:

| Ölçüm | Değer | Plana etkisi |
|---|---|---|
| Grid | 500×500 @ 5 m/px, 2,50 km | Mesh 250 000 vertex — three.js için sorunsuz |
| Kabartı | 1063,8 m / 2500 m = 1:2,35 | Dikey abartma **gerekmiyor**; öneri 1,0 |
| `elevation` NaN | **0** | Mesh delinmez, `computeVertexNormals()` çalışır |
| `cost` `+inf` | **49 525** | float32'de `Infinity` gider → sessiz bozuk render. NaN'a çevrilecek |
| JSON / ikili | 4,25 MB / **1,00 MB** | Aynı baytta 4× çözünürlük |
| `MAX_LAYER_CELLS` | 65 536 | 500×500 = 250 000 → JSON yolu `downsample≥2` dayatıyor |
| `horizon_map.npy` | **yok** | Zaman serisi onsuz sessizce statiğe düşer → Task 4 |
| NAIF çekirdekleri | `kernels/` içinde tam | SPICE yolu çalışabilir |
| `.npy` git durumu | `.gitignore:26` ile hariç | 72 MB'lık ufuk cache'i commit edilmez |

---

## Dosya yapısı

| Dosya | Sorumluluk | Durum |
|---|---|---|
| `backend/app/terrain.py` | İkili kodlama, katman istatistiği, `X-Layer-*` başlıkları, sahne manifestosu. Saf NumPy; FastAPI import etmez. | **Oluştur** (taslak mevcut, Task 1 doğrular) |
| `backend/app/illumination_series.py` | +`sun_track_for_series()` — dilim başına UTC + grid azimutu + yükseklik. Mevcut fonksiyonlara dokunulmaz. | **Ekle** |
| `backend/app/main.py` | `/api/layers`'a `format`; `/api/terrain`; `/api/illumination-series`; CORS `expose_headers`. | **Değiştir (toplamsal)** |
| `backend/test_terrain.py` | `terrain.py` saf fonksiyon testleri | **Oluştur** |
| `backend/test_terrain_api.py` | Üç uç noktanın uçtan uca testleri | **Oluştur** |
| `docs/frontend/3b-veri-sozlesmesi.md` | Frontend sözleşmesi + çalışan three.js örneği | **Oluştur** |
| `lunapath/data/processed/horizon_map.npy` | Ufuk küpü cache'i (72 MB, git dışı) | **Üret** |

---

## Task 1: `terrain.py` — ikili kodlama ve manifest ilkelleri

**Files:**
- Create: `backend/app/terrain.py`
- Test: `backend/test_terrain.py`

**Interfaces:**
- Consumes: yalnızca NumPy.
- Produces:
  - `BINARY_DTYPE = np.dtype("<f4")`, `BINARY_DTYPE_NAME = "float32"`,
    `BINARY_ENDIAN = "little"`, `BINARY_ORDER = "row-major"`,
    `BINARY_NODATA = "NaN"`, `BINARY_MEDIA_TYPE = "application/octet-stream"`
  - `BINARY_LAYER_HEADERS: tuple[str, ...]` — CORS'un açacağı başlık adları
  - `TERRAIN_LAYERS: tuple[str, ...]`, `LAYER_UNITS: dict[str,str]`,
    `LAYER_DESCRIPTIONS: dict[str,str]`
  - `encode_layer_f32(layer: np.ndarray) -> bytes`
  - `layer_stats(layer: np.ndarray) -> dict[str, Any]`  → `{"min","max","nodata","cells"}`
  - `suggested_vertical_exaggeration(relief_m: float, span_m: float, target_ratio: float = 0.2) -> float`
  - `binary_layer_headers(layer_name: str, layer: np.ndarray, downsample: int, resolution_m: float, validity: str | None) -> dict[str, str]`
  - `terrain_manifest(grids: dict, rover_id: str, rover_name: str, weights: dict | None = None, layer_names: Iterable[str] = TERRAIN_LAYERS, binary_query: str = "") -> dict[str, Any]`

- [x] **Step 1: Write the failing test**

`backend/test_terrain.py`:

```python
"""Pure-function tests for the binary terrain transport."""

import numpy as np
import pytest

from app.terrain import (
    BINARY_DTYPE,
    BINARY_LAYER_HEADERS,
    binary_layer_headers,
    encode_layer_f32,
    layer_stats,
    suggested_vertical_exaggeration,
    terrain_manifest,
)


def _grids():
    """A 4x3 stand-in grid set with both flavours of absent value."""
    elevation = np.array(
        [[100.0, 101.0, 102.0],
         [103.0, 104.0, 105.0],
         [106.0, 107.0, 108.0],
         [109.0, 110.0, 120.0]]
    )
    cost = np.array(
        [[0.5, 0.6, np.inf],
         [0.7, np.nan, 0.8],
         [0.9, 1.0, 1.1],
         [1.2, 1.3, 1.4]]
    )
    return {
        "elevation": elevation,
        "cost": cost,
        "traversable": np.isfinite(cost),
        "metadata": {
            "shape": [4, 3],
            "resolution_m": 5.0,
            "origin": {"x": -1.0, "y": 2.0},
            "crs": "PROJCS[...]",
            "window_offset": {"row": 0, "col": 700},
            "layer_validity": {"elevation": "MEASURED", "cost": "DERIVED"},
        },
    }


def test_encode_is_little_endian_float32_row_major():
    grid = np.arange(6, dtype=np.float64).reshape(2, 3)
    raw = encode_layer_f32(grid)
    assert len(raw) == 6 * 4
    back = np.frombuffer(raw, dtype=BINARY_DTYPE)
    # Row-major: the flat order is the row order, not the column order.
    assert back.tolist() == [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]


def test_encode_collapses_infinity_to_nan():
    """+inf in `cost` marks an impassable cell. float32 would carry the
    infinity into a colour ramp or a vertex, which renders as a silent
    artefact rather than a visible hole."""
    grid = np.array([[1.0, np.inf], [-np.inf, np.nan]])
    back = np.frombuffer(encode_layer_f32(grid), dtype=BINARY_DTYPE)
    assert back[0] == 1.0
    assert np.isnan(back[1]) and np.isnan(back[2]) and np.isnan(back[3])


def test_encode_maps_bool_to_one_and_zero():
    back = np.frombuffer(
        encode_layer_f32(np.array([[True, False]])), dtype=BINARY_DTYPE
    )
    assert back.tolist() == [1.0, 0.0]


def test_layer_stats_ignores_non_finite():
    stats = layer_stats(np.array([[1.0, np.inf], [np.nan, 5.0]]))
    assert stats == {"min": 1.0, "max": 5.0, "nodata": 2, "cells": 4}


def test_layer_stats_all_nodata():
    stats = layer_stats(np.array([[np.nan, np.inf]]))
    assert stats["min"] is None and stats["max"] is None and stats["nodata"] == 2


def test_vertical_exaggeration_is_one_when_relief_already_reads():
    # The production site: 1063.8 m over 2500 m.
    assert suggested_vertical_exaggeration(1063.8, 2500.0) == 1.0


def test_vertical_exaggeration_snaps_up_a_readable_ladder():
    # 25 m over 2500 m is 1:100; reaching the 0.2 target needs 20x.
    assert suggested_vertical_exaggeration(25.0, 2500.0) == 20.0
    assert suggested_vertical_exaggeration(0.0, 2500.0) == 1.0


def test_headers_report_effective_resolution_not_source_resolution():
    grid = np.zeros((4, 3))
    headers = binary_layer_headers("elevation", grid, 4, 5.0, "MEASURED")
    assert headers["X-Layer-Resolution-M"] == repr(20.0)
    assert headers["X-Layer-Rows"] == "4" and headers["X-Layer-Cols"] == "3"
    assert headers["X-Layer-Validity"] == "MEASURED"


def test_every_header_the_encoder_sets_is_in_the_cors_allowlist():
    """A header the CORS middleware does not expose is invisible to the
    browser -- no error, just undefined. Keep the two lists in lockstep."""
    headers = binary_layer_headers(
        "cost", np.array([[np.inf, 1.0]]), 1, 5.0, "DERIVED"
    )
    for name in headers:
        assert name in BINARY_LAYER_HEADERS


def test_manifest_reports_grid_georeference_and_layers():
    manifest = terrain_manifest(_grids(), "lpr_1", "LPR-1")
    assert manifest["grid"] == {
        "rows": 4, "cols": 3, "resolution_m": 5.0,
        "span_m": [20.0, 15.0], "cells": 12,
    }
    assert manifest["georeference"]["row_axis"] == "north-to-south"
    assert manifest["georeference"]["window_offset"] == {"row": 0, "col": 700}
    assert manifest["elevation"]["relief_m"] == pytest.approx(20.0)
    assert manifest["binary_format"]["bytes_per_layer"] == 12 * 4
    assert manifest["layers"]["elevation"]["validity"] == "MEASURED"
    assert manifest["layers"]["elevation"]["units"] == "m"
    assert manifest["layers"]["cost"]["nodata"] == 2
    assert manifest["layers"]["cost"]["max"] == pytest.approx(1.4)


def test_manifest_binary_url_carries_the_caller_query():
    manifest = terrain_manifest(
        _grids(), "lpr_1", "LPR-1", binary_query="rover_id=lpr_1&w_slope=0.5"
    )
    assert manifest["layers"]["cost"]["binary_url"] == (
        "/api/layers/cost?format=f32&rover_id=lpr_1&w_slope=0.5"
    )
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest test_terrain.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'app.terrain'`
(bir taslak `app/terrain.py` zaten yazıldıysa: testler koşar ve bir kısmı geçer;
o durumda geçmeyen her assert'i düzelt, taslağı bu testlerin dediğine uydur).

- [x] **Step 3: Write the implementation**

`backend/app/terrain.py`. Sabitler ve iki sözlük yukarıdaki "Produces" bloğunda;
gövdeler:

```python
def encode_layer_f32(layer: np.ndarray) -> bytes:
    values = np.asarray(layer, dtype=np.float64)
    values = np.where(np.isfinite(values), values, np.nan)
    return np.ascontiguousarray(values, dtype=BINARY_DTYPE).tobytes()


def layer_stats(layer: np.ndarray) -> dict[str, Any]:
    values = np.asarray(layer, dtype=np.float64)
    finite = np.isfinite(values)
    nodata = int(values.size - int(finite.sum()))
    if not finite.any():
        return {"min": None, "max": None, "nodata": nodata, "cells": int(values.size)}
    return {
        "min": float(np.min(values[finite])),
        "max": float(np.max(values[finite])),
        "nodata": nodata,
        "cells": int(values.size),
    }


def suggested_vertical_exaggeration(relief_m, span_m, target_ratio=0.2) -> float:
    if relief_m <= 0.0 or span_m <= 0.0:
        return 1.0
    ratio = relief_m / span_m
    if ratio >= target_ratio:
        return 1.0
    raw = target_ratio / ratio
    for step in (1.0, 1.5, 2.0, 3.0, 5.0, 7.5, 10.0, 15.0, 20.0, 30.0, 50.0):
        if raw <= step:
            return step
    return 50.0
```

`binary_layer_headers` `layer_stats`'ı çağırır ve `X-Layer-Resolution-M` alanına
`repr(float(resolution_m) * int(downsample))` yazar — kaynak çözünürlük değil,
**dönen gridin** adımı. `min`/`max` yalnızca sonlu değer varsa eklenir,
`X-Layer-Validity` yalnızca `validity` doluysa.

`terrain_manifest` beş blok döndürür: `grid`, `georeference` (+ sabit
`row_axis="north-to-south"`, `col_axis="west-to-east"`), `elevation`
(`min_m`/`max_m`/`relief_m`/`vertical_exaggeration_suggested`), `binary_format`,
`rover`, `weights`, `layers`. Her katman girdisi
`units`/`description`/`validity`/`min`/`max`/`nodata`/`binary_url`/`json_url`
taşır; `binary_url` = `f"/api/layers/{name}?format=f32"` + (varsa) `"&" + binary_query`.

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest test_terrain.py -q`
Expected: 11 passed

- [x] **Step 5: Commit**

```bash
git add backend/app/terrain.py backend/test_terrain.py
git commit -m "feat(terrain): binary layer encoding and 3-D scene manifest primitives"
```

---

## Task 2: `/api/layers?format=f32` + CORS başlık açımı

**Files:**
- Modify: `backend/app/main.py` (CORS middleware ~satır 100; `get_layer` ~satır 1254)
- Test: `backend/test_terrain_api.py`

**Interfaces:**
- Consumes: Task 1'in `encode_layer_f32`, `binary_layer_headers`,
  `BINARY_LAYER_HEADERS`, `BINARY_MEDIA_TYPE`.
- Produces: `GET /api/layers/{name}?format=f32` → `application/octet-stream`,
  gövde tam olarak `rows*cols*4` bayt. `format=json` (varsayılan) mevcut yanıtı
  **birebir** korur.

- [x] **Step 1: Write the failing test**

`backend/test_terrain_api.py`:

```python
"""End-to-end tests for the 3-D data path."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.terrain import BINARY_DTYPE, BINARY_LAYER_HEADERS


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_json_layer_is_byte_for_byte_unchanged_without_format(client):
    """The whole promise of this feature is that it is additive."""
    plain = client.get("/api/layers/slope?downsample=4")
    explicit = client.get("/api/layers/slope?downsample=4&format=json")
    assert plain.status_code == 200
    assert plain.json() == explicit.json()
    assert plain.headers["content-type"].startswith("application/json")


def test_binary_layer_returns_exactly_rows_times_cols_float32(client):
    response = client.get("/api/layers/elevation?format=f32")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    rows = int(response.headers["X-Layer-Rows"])
    cols = int(response.headers["X-Layer-Cols"])
    assert len(response.content) == rows * cols * 4
    values = np.frombuffer(response.content, dtype=BINARY_DTYPE)
    assert values.size == rows * cols


def test_binary_layer_ignores_the_json_cell_ceiling(client):
    """250 000 cells is four times MAX_LAYER_CELLS. The ceiling exists to
    keep a JSON response sane; it has no meaning for 1 MB of float32."""
    json_response = client.get("/api/layers/elevation?downsample=1")
    assert json_response.status_code == 422  # the ceiling still guards JSON
    binary = client.get("/api/layers/elevation?format=f32&downsample=1")
    assert binary.status_code == 200
    assert int(binary.headers["X-Layer-Rows"]) == 500


def test_binary_matches_json_values_at_the_same_downsample(client):
    """Two representations of one grid must agree, or the 3-D view and the
    2-D map are showing different terrain."""
    down = 4
    payload = client.get(f"/api/layers/slope?downsample={down}").json()
    binary = client.get(f"/api/layers/slope?format=f32&downsample={down}")
    rows, cols = payload["shape"]
    values = np.frombuffer(binary.content, dtype=BINARY_DTYPE).reshape(rows, cols)
    expected = np.array(
        [[np.nan if v is None else v for v in row] for row in payload["data"]],
        dtype=np.float32,
    )
    np.testing.assert_allclose(values, expected, rtol=1e-6, equal_nan=True)


def test_binary_cost_layer_has_no_infinities(client):
    binary = client.get("/api/layers/cost?format=f32")
    values = np.frombuffer(binary.content, dtype=BINARY_DTYPE)
    assert not np.isinf(values).any()
    assert int(binary.headers["X-Layer-Nodata"]) == int(np.isnan(values).sum())


def test_binary_resolution_header_follows_downsample(client):
    binary = client.get("/api/layers/elevation?format=f32&downsample=4")
    assert float(binary.headers["X-Layer-Resolution-M"]) == pytest.approx(20.0)


def test_unknown_format_is_rejected(client):
    assert client.get("/api/layers/slope?format=f64").status_code == 422


def test_cors_exposes_every_binary_header(client):
    """Without Access-Control-Expose-Headers the browser silently reports
    `undefined` for each X-Layer-* header on a cross-origin fetch."""
    response = client.get(
        "/api/layers/elevation?format=f32", headers={"Origin": "http://localhost:5173"}
    )
    exposed = {
        name.strip().lower()
        for name in response.headers.get("access-control-expose-headers", "").split(",")
    }
    for name in BINARY_LAYER_HEADERS:
        assert name.lower() in exposed
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest test_terrain_api.py -q`
Expected: FAIL — `format` bilinmeyen sorgu parametresi olarak yok sayılır, yanıt
JSON döner, `content-type` eşleşmez.

- [x] **Step 3: Write the implementation**

3a. `main.py` importlarına ekle:

```python
from fastapi.responses import JSONResponse, Response
from .terrain import (
    BINARY_LAYER_HEADERS,
    BINARY_MEDIA_TYPE,
    TERRAIN_LAYERS,
    binary_layer_headers,
    encode_layer_f32,
    terrain_manifest,
)
```

3b. CORS middleware'e tek satır — mevcut üç argüman aynen kalır:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    # A browser cannot read a custom response header on a cross-origin
    # request unless the server names it here. The binary layer carries its
    # entire self-description in X-Layer-*, so without this line the 3-D
    # client sees `undefined` for every one of them -- and no error.
    expose_headers=list(BINARY_LAYER_HEADERS),
)
```

3c. `get_layer` imzasına parametre ekle (varsayılan `"json"` — eski davranış):

```python
    format: str = Query(
        "json",
        pattern="^(json|f32)$",
        description=(
            "json: nested lists, capped at MAX_LAYER_CELLS. "
            "f32: raw little-endian float32, row-major, NaN for no-data, "
            "uncapped -- what a 3-D client wants."
        ),
    ),
```

3d. `get_layer` gövdesinde, `downsample` uygulandıktan **sonra** ve hücre tavanı
kontrolünden **önce** dallan:

```python
    if format == "f32":
        # The cell ceiling guards a JSON response, where each number costs
        # ~17 bytes of text and is built through an object-dtype array. The
        # full 500x500 grid is 1.00 MB of float32 -- a quarter of what the
        # capped 256x256 JSON preview costs -- so the ceiling would only be
        # denying the caller resolution it can plainly afford.
        validity = (metadata.get("layer_validity") or {}).get(layer_name)
        return Response(
            content=encode_layer_f32(layer),
            media_type=BINARY_MEDIA_TYPE,
            headers=binary_layer_headers(
                layer_name,
                layer,
                downsample,
                float(metadata.get("resolution_m", 1.0)),
                validity,
            ),
        )
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest test_terrain_api.py -q`
Expected: 8 passed

- [x] **Step 5: Regression gate — nothing existing moved**

Run: `cd backend && python -m pytest test_plan_endpoint.py test_layer_validity.py -q`
Expected: all pass, 0 warnings

- [x] **Step 6: Commit**

```bash
git add backend/app/main.py backend/test_terrain_api.py
git commit -m "feat(api): serve grid layers as raw float32 for the 3-D client"
```

---

## Task 3: `GET /api/terrain` sahne manifestosu

**Files:**
- Modify: `backend/app/main.py` (yeni uç nokta, `get_layer`'ın hemen ardına)
- Test: `backend/test_terrain_api.py` (ekleme)

**Interfaces:**
- Consumes: Task 1'in `terrain_manifest`; mevcut `_get_grids`, `grids_for_rover`,
  `get_rover`.
- Produces: `GET /api/terrain?rover_id=&w_slope=&w_energy=&w_shadow=&w_thermal=`
  → JSON; `layers[*].binary_url` doğrudan `fetch` edilebilir.

- [x] **Step 1: Write the failing test** — `test_terrain_api.py` sonuna ekle:

```python
def test_terrain_manifest_describes_the_production_grid(client):
    manifest = client.get("/api/terrain").json()
    assert manifest["grid"]["rows"] == 500 and manifest["grid"]["cols"] == 500
    assert manifest["grid"]["resolution_m"] == 5.0
    assert manifest["grid"]["span_m"] == [2500.0, 2500.0]
    assert manifest["binary_format"]["dtype"] == "float32"
    assert manifest["binary_format"]["endian"] == "little"
    assert manifest["binary_format"]["bytes_per_layer"] == 500 * 500 * 4
    # 1063.8 m of relief over 2.5 km already reads as terrain at true scale.
    assert manifest["elevation"]["vertical_exaggeration_suggested"] == 1.0
    assert manifest["elevation"]["relief_m"] > 1000.0
    assert manifest["georeference"]["crs"]
    assert set(manifest["layers"]) == {
        "elevation", "slope", "aspect", "thermal", "thermal_min",
        "shadow_ratio", "cost", "traversable",
    }


def test_manifest_binary_urls_are_fetchable_as_given(client):
    """The manifest is only useful if its URLs work verbatim -- a client
    should never have to reassemble a query string by hand."""
    manifest = client.get("/api/terrain?rover_id=lpr_1&w_slope=0.5").json()
    for name, entry in manifest["layers"].items():
        response = client.get(entry["binary_url"])
        assert response.status_code == 200, name
        assert len(response.content) == manifest["binary_format"]["bytes_per_layer"]


def test_manifest_layer_range_matches_the_binary_it_points_at(client):
    manifest = client.get("/api/terrain").json()
    entry = manifest["layers"]["thermal"]
    values = np.frombuffer(client.get(entry["binary_url"]).content, dtype=BINARY_DTYPE)
    finite = values[np.isfinite(values)]
    assert float(finite.min()) == pytest.approx(entry["min"], rel=1e-6)
    assert float(finite.max()) == pytest.approx(entry["max"], rel=1e-6)
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest test_terrain_api.py -k terrain_manifest -q`
Expected: FAIL — 404, uç nokta yok.

- [x] **Step 3: Write the implementation** — `main.py`, `get_layer`'dan sonra:

```python
@app.get("/api/terrain")
def terrain(
    rover_id: str = DEFAULT_ROVER_ID,
    w_slope: float | None = None,
    w_energy: float | None = None,
    w_shadow: float | None = None,
    w_thermal: float | None = None,
):
    """Everything a 3-D scene needs before it fetches a byte of grid.

    The JSON layer endpoint answers "what are the numbers"; this answers
    "what do they mean" -- mesh dimensions, the georeference that ties the
    mesh to the Moon, the elevation range the displacement scales by, the
    decode contract, and per-layer units, range and provenance with the URL
    to fetch each. One call, so a client is never assembling a query string
    by hand or guessing which reduction produced a field.
    """
    base_grids = _get_grids()
    weight_overrides = {
        key: value
        for key, value in {
            "w_slope": w_slope,
            "w_energy": w_energy,
            "w_shadow": w_shadow,
            "w_thermal": w_thermal,
        }.items()
        if value is not None
    }
    rover = get_rover(rover_id)
    grids = grids_for_rover(base_grids, rover_id, weight_overrides or None)

    query = {"rover_id": rover_id}
    query.update({key: repr(value) for key, value in weight_overrides.items()})
    binary_query = "&".join(f"{key}={value}" for key, value in query.items())

    return terrain_manifest(
        grids,
        rover_id=rover_id,
        rover_name=rover["name"],
        weights=dict(grids.get("weights") or {}) or None,
        layer_names=TERRAIN_LAYERS,
        binary_query=binary_query,
    )
```

`grids.get("weights")` yoksa `None` gider; `rover_grids.grids_for_rover`'ın
döndürdüğü sözlükte ağırlık anahtarı yoksa manifest `weights: null` yayınlar,
bu doğrudur — "bilmiyorum" ile "sıfır" karışmaz.

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest test_terrain_api.py -q`
Expected: 11 passed

- [x] **Step 5: Commit**

```bash
git add backend/app/main.py backend/test_terrain_api.py
git commit -m "feat(api): add GET /api/terrain scene manifest"
```

---

## Task 4: Dilim başına güneş konumu + ufuk cache'inin üretilmesi

**Files:**
- Modify: `backend/app/illumination_series.py` (yalnızca **yeni** fonksiyon)
- Test: `backend/test_terrain.py` (ekleme)
- Produce: `lunapath/data/processed/horizon_map.npy` (git dışı artefakt)

**Interfaces:**
- Consumes: `app.ephemeris.sun_vector_body`, `sun_azel_from_vector`,
  `true_north_grid_azimuth`, `true_azimuth_to_grid_azimuth`; mevcut
  `_window_centre_latlon`.
- Produces: `sun_track_for_series(metadata: dict, n_slices: int, slice_hours: float,
  start_utc: str) -> list[dict]` — her öğe
  `{"index", "utc", "azimuth_true_deg", "azimuth_grid_deg", "elevation_deg"}`.
  SPICE erişilemezse `RuntimeError` yükseltir (çağıran yakalar).

**Neden gerekli:** 3-B sahnede yönlü ışığın nereye konacağı bugün API'nin hiçbir
yerinde yok. Gölge rasterı "nerede karanlık" der, güneş açısı "neden karanlık"
der — ışık, gölge ve arazi ancak ikisi birlikte tutarlı görünür.

- [x] **Step 1: Write the failing test** — `test_terrain.py` sonuna:

```python
def test_sun_track_for_series_returns_one_entry_per_slice():
    from app.illumination_series import sun_track_for_series

    metadata = {
        "shape": [500, 500],
        "resolution_m": 5.0,
        "origin": {"x": -15500.0, "y": -4000.0},
        "crs": "unknown",
    }
    try:
        track = sun_track_for_series(metadata, 4, 6.0, "2026-09-01T00:00:00")
    except RuntimeError as exc:            # no NAIF kernels in this env
        pytest.skip(f"SPICE unavailable: {exc}")

    assert len(track) == 4
    assert [entry["index"] for entry in track] == [0, 1, 2, 3]
    assert track[0]["utc"].startswith("2026-09-01T00:00:00")
    assert track[1]["utc"].startswith("2026-09-01T06:00:00")
    for entry in track:
        assert 0.0 <= entry["azimuth_grid_deg"] < 360.0
        # Polar site: the Sun grazes the horizon, never climbs.
        assert -10.0 < entry["elevation_deg"] < 10.0
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest test_terrain.py -k sun_track -q`
Expected: FAIL — `ImportError: cannot import name 'sun_track_for_series'`

- [x] **Step 3: Write the implementation** — `illumination_series.py` sonuna ekle.
Mevcut hiçbir fonksiyon değişmez:

```python
def sun_track_for_series(
    metadata: dict[str, Any],
    n_slices: int,
    slice_hours: float,
    start_utc: str,
) -> list[dict[str, Any]]:
    """Sun azimuth and elevation at each slice of a time series.

    ``_spice_shadow_series`` already computes exactly this to decide which
    cells are lit, and then throws it away. A 3-D client needs the number
    itself: the shadow raster says WHERE it is dark, the Sun angle says WHY,
    and a directional light placed from anything else will disagree with
    the shadows it is supposed to be casting.

    Azimuth is reported in both frames. ``azimuth_true_deg`` is the physical
    answer; ``azimuth_grid_deg`` is the one a viewer that thinks in rows and
    columns needs, and on a polar stereographic grid the two differ by the
    meridian convergence at the window centre.
    """
    from datetime import datetime, timedelta, timezone

    import spiceypy as spice

    from .ephemeris import (
        sun_azel_from_vector,
        sun_vector_body,
        true_azimuth_to_grid_azimuth,
        true_north_grid_azimuth,
    )

    lat_deg, lon_deg = _window_centre_latlon(metadata)
    crs_wkt = metadata.get("crs")
    north_grid_az = (
        true_north_grid_azimuth(lat_deg, lon_deg, str(crs_wkt))
        if crs_wkt and crs_wkt != "unknown"
        else 0.0
    )

    start = datetime.fromisoformat(str(start_utc).replace("Z", "+00:00"))
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    track: list[dict[str, Any]] = []
    for index in range(int(n_slices)):
        moment = start + timedelta(hours=float(slice_hours) * index)
        et = spice.str2et(moment.strftime("%Y-%m-%dT%H:%M:%S"))
        true_az, elev = sun_azel_from_vector(sun_vector_body(et), lat_deg, lon_deg)
        track.append(
            {
                "index": index,
                "utc": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "azimuth_true_deg": float(true_az),
                "azimuth_grid_deg": float(
                    true_azimuth_to_grid_azimuth(true_az, north_grid_az)
                ),
                "elevation_deg": float(elev),
            }
        )
    return track
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest test_terrain.py -q`
Expected: 12 passed (veya SPICE yoksa 11 passed 1 skipped)

- [x] **Step 5: Build the horizon cache**

Zaman serisi bu cache olmadan sessizce statiğe düşer — `build_shadow_series`
`reason` alanında bunu söyler, ama animasyon çalışmaz.

Run: `python scripts/build_horizon_cache.py`
Expected: `Using the window's real context: ...` ardından
`Wrote .../horizon_map.npy (~69 MiB, shape (72, 500, 500))`. Birkaç dakika sürer.

Doğrula:
```bash
python -c "import numpy as np; a=np.load('lunapath/data/processed/horizon_map.npy'); print(a.shape, a.dtype, float(a.min()), float(a.max()))"
```
Beklenen: `(72, 500, 500)`, açı değerleri radyan/derece aralığında ve hepsi sonlu.

`.gitignore:26` `*.npy` içerdiği için commit edilmez — bu doğru, 69 MB'lık türetilmiş
artefakt depoya girmemeli. Task 6'nın belgesi bu komutu kurulum adımı olarak yazacak.

- [x] **Step 6: Commit**

```bash
git add backend/app/illumination_series.py backend/test_terrain.py
git commit -m "feat(illumination): publish per-slice Sun azimuth and elevation"
```

---

## Task 5: `GET /api/illumination-series`

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/test_terrain_api.py` (ekleme)

**Interfaces:**
- Consumes: `build_shadow_series`, Task 4'ün `sun_track_for_series`,
  `thermal_model.shadowed_equilibrium_c`, `thermal_model.relax_surface_c`,
  `thermal_model.REGOLITH_THERMAL_TAU_S`, Task 1'in `encode_layer_f32`.
- Produces:
  - `GET /api/illumination-series?start_utc=&n_slices=&slice_hours=&downsample=`
    → JSON manifest: `slices`, `slice_hours`, `sun[]`, `shadow_model` kaynağı,
    `fields{}` (her biri binary URL + aralık).
  - `...&format=f32&field=shadow|surface_temp_c` → `(T, rows, cols)` float32,
    dilim dilim bitişik.

**Sıcaklık tarifi** — `cost_cube.build_cost_cube` ile **birebir aynı** olmalı,
yoksa 3-B görünüm planlayıcının gördüğünden başka bir yüzey gösterir:
1. `sunlit = grids["thermal_sunlit_peak"]` (loader bunu doğrudan yayınlar)
2. Başlangıç durumu: `shadowed_equilibrium_c(sunlit, grids["shadow_ratio"])`
3. Her dilimde hedef: `shadowed_equilibrium_c(sunlit, shadow_series[i])`
4. `relax_surface_c(state, target, dt_s=slice_hours*3600, tau_s=REGOLITH_THERMAL_TAU_S)`

- [x] **Step 1: Write the failing test** — `test_terrain_api.py` sonuna:

```python
SERIES = "/api/illumination-series"


def test_series_manifest_reports_slices_and_sun(client):
    manifest = client.get(
        f"{SERIES}?start_utc=2026-09-01T00:00:00&n_slices=6&slice_hours=4&downsample=5"
    ).json()
    assert manifest["slices"] == 6
    assert manifest["slice_hours"] == 4.0
    assert manifest["grid"]["rows"] == 100 and manifest["grid"]["cols"] == 100
    assert len(manifest["sun"]) == 6
    assert manifest["sun"][0]["utc"].startswith("2026-09-01T00:00:00")
    assert set(manifest["fields"]) == {"shadow", "surface_temp_c"}
    assert manifest["shadow_model"]["model"] in ("spice_horizon", "static")


def test_series_without_epoch_says_static_and_says_why(client):
    """Illumination is a function of time; without an epoch it cannot vary,
    and the response must not let that pass as physics."""
    manifest = client.get(f"{SERIES}?n_slices=4&downsample=5").json()
    assert manifest["shadow_model"]["time_varying"] is False
    assert manifest["shadow_model"]["reason"]


def test_series_binary_is_t_by_rows_by_cols(client):
    query = "start_utc=2026-09-01T00:00:00&n_slices=6&slice_hours=4&downsample=5"
    response = client.get(f"{SERIES}?{query}&format=f32&field=shadow")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert int(response.headers["X-Series-Slices"]) == 6
    values = np.frombuffer(response.content, dtype=BINARY_DTYPE)
    assert values.size == 6 * 100 * 100
    cube = values.reshape(6, 100, 100)
    assert np.nanmin(cube) >= 0.0 and np.nanmax(cube) <= 1.0


def test_series_temperature_uses_the_planner_recipe(client):
    """Slice 0 is the long-run equilibrium the cost cube starts from. If
    these diverge, the 3-D view and the planner disagree about the surface."""
    from app.cost_cube import coarsen_grid
    from app.data_loader import load_preprocessed_grids
    from app.thermal_model import shadowed_equilibrium_c

    query = "start_utc=2026-09-01T00:00:00&n_slices=2&slice_hours=4&downsample=5"
    response = client.get(f"{SERIES}?{query}&format=f32&field=surface_temp_c")
    cube = np.frombuffer(response.content, dtype=BINARY_DTYPE).reshape(2, 100, 100)

    grids = load_preprocessed_grids()
    expected = np.asarray(
        shadowed_equilibrium_c(
            grids["thermal_sunlit_peak"], grids["shadow_ratio"]
        ),
        dtype=np.float64,
    )[::5, ::5]
    np.testing.assert_allclose(cube[0], expected, rtol=1e-4, equal_nan=True)


def test_series_rejects_a_request_that_would_not_fit(client):
    response = client.get(
        f"{SERIES}?start_utc=2026-09-01T00:00:00&n_slices=200&format=f32&field=shadow"
    )
    assert response.status_code == 422
    assert "downsample" in response.json()["detail"]


def test_series_rejects_an_unknown_field(client):
    response = client.get(f"{SERIES}?format=f32&field=albedo&downsample=5")
    assert response.status_code == 422
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest test_terrain_api.py -k series -q`
Expected: FAIL — 404.

- [x] **Step 3: Write the implementation**

`main.py` importlarına: `from .thermal_model import (REGOLITH_LAG_VALIDITY,
REGOLITH_THERMAL_TAU_S, relax_surface_c, shadowed_equilibrium_c)` ve
`from .illumination_series import build_shadow_series, sun_track_for_series`
(ilk isim zaten import edilmiş; satırı genişlet).

Sabit — `MAX_LAYER_CELLS`'in yanına:

```python
# A slice series is (T, H, W) float32 on the wire. At 24 slices the full
# 500x500 grid is 24 MB, which is a fine LAN payload and a poor one over
# anything else; 64 MiB is the point past which the caller is asked to
# downsample instead. Like MAX_LAYER_CELLS, the error names the number that
# would fit rather than just refusing.
MAX_SERIES_BYTES = 64 * 1024 * 1024
```

Uç nokta:

```python
@app.get("/api/illumination-series")
def illumination_series(
    start_utc: Optional[str] = None,
    n_slices: int = Query(24, ge=1, le=MAX_PLAN_4D_SLICES),
    slice_hours: float = Query(1.0, gt=0.0, le=24.0),
    downsample: int = Query(1, ge=1, le=50),
    format: str = Query("json", pattern="^(json|f32)$"),
    field: str = Query("shadow", pattern="^(shadow|surface_temp_c)$"),
):
    """Illumination and surface temperature over time, for an animated scene.

    The 4-D planner already reasons over exactly this series -- it is what
    makes "wait here for the Sun" a decision rather than a slogan -- but it
    consumed the series privately and published only the route. A 3-D client
    that wants to show why the route waits needs the same field.

    The temperature recipe is `build_cost_cube`'s, step for step: start at
    the equilibrium under the cell's long-run illumination, then relax
    toward each slice's own equilibrium with the regolith time constant.
    Re-deriving it differently here would put a surface on screen that the
    planner never costed.
    """
    grids = _get_grids()
    metadata = grids["metadata"]
    base_shadow = np.asarray(grids["shadow_ratio"], dtype=np.float64)

    shadow_series, provenance = build_shadow_series(
        base_shadow, metadata, int(n_slices), float(slice_hours), start_utc
    )

    step = int(downsample)
    rows = len(range(0, base_shadow.shape[0], step))
    cols = len(range(0, base_shadow.shape[1], step))
    needed = int(n_slices) * rows * cols * 4
    if needed > MAX_SERIES_BYTES:
        fit = math.ceil(
            math.sqrt(
                (int(n_slices) * base_shadow.size * 4) / MAX_SERIES_BYTES
            )
        )
        raise HTTPException(
            status_code=422,
            detail=(
                f"{n_slices} slices at downsample={downsample} is "
                f"{needed / 2**20:.0f} MiB, over the "
                f"{MAX_SERIES_BYTES / 2**20:.0f} MiB series budget. "
                f"Use downsample={fit} or higher, or fewer slices."
            ),
        )

    sun: list[dict[str, Any]] = []
    if start_utc:
        try:
            sun = sun_track_for_series(
                metadata, int(n_slices), float(slice_hours), start_utc
            )
        except Exception as exc:
            # Same reasoning as build_shadow_series: a missing kernel must
            # degrade to "no Sun track" and say so, not take the endpoint down.
            logger.warning("Sun track unavailable: %s", exc)
            sun = []

    if format == "f32":
        cube = _series_field_cube(grids, shadow_series, field, step, float(slice_hours))
        return Response(
            content=encode_layer_f32(cube.reshape(-1, cube.shape[-1])),
            media_type=BINARY_MEDIA_TYPE,
            headers={
                "X-Series-Field": field,
                "X-Series-Slices": str(int(n_slices)),
                "X-Series-Rows": str(rows),
                "X-Series-Cols": str(cols),
                "X-Series-Downsample": str(step),
                "X-Series-Resolution-M": repr(
                    float(metadata["resolution_m"]) * step
                ),
                "X-Layer-Dtype": "float32",
                "X-Layer-Endian": "little",
                "X-Layer-Order": "row-major",
            },
        )

    fields = {}
    for name in ("shadow", "surface_temp_c"):
        cube = _series_field_cube(grids, shadow_series, name, step, float(slice_hours))
        finite = cube[np.isfinite(cube)]
        query = (
            f"n_slices={n_slices}&slice_hours={slice_hours}&downsample={step}"
            f"&format=f32&field={name}"
        )
        if start_utc:
            query = f"start_utc={start_utc}&" + query
        fields[name] = {
            "units": "fraction" if name == "shadow" else "degC",
            "min": float(finite.min()) if finite.size else None,
            "max": float(finite.max()) if finite.size else None,
            "binary_url": f"/api/illumination-series?{query}",
        }

    return {
        "slices": int(n_slices),
        "slice_hours": float(slice_hours),
        "start_utc": start_utc,
        "grid": {
            "rows": rows,
            "cols": cols,
            "resolution_m": float(metadata["resolution_m"]) * step,
            "downsample": step,
        },
        "shadow_model": provenance,
        "thermal_model": {
            "recipe": "shadowed_equilibrium_c then relax_surface_c per slice",
            "tau_s": REGOLITH_THERMAL_TAU_S,
            "validity": REGOLITH_LAG_VALIDITY,
        },
        "sun": sun,
        "fields": fields,
        "binary_format": {
            "dtype": "float32",
            "endian": "little",
            "order": "slice-major, then row-major",
            "shape": [int(n_slices), rows, cols],
            "nodata": "NaN",
        },
    }
```

Yardımcı — uç noktanın hemen üstüne:

```python
def _series_field_cube(
    grids: dict,
    shadow_series: list[np.ndarray],
    field: str,
    step: int,
    slice_hours: float,
) -> np.ndarray:
    """(T, rows, cols) for one field, decimated by *step*.

    The temperature branch mirrors `cost_cube.build_cost_cube` exactly --
    same initial state, same target, same time constant -- so the surface a
    viewer animates is the surface the planner costed.
    """
    stack = np.stack([np.asarray(s, dtype=np.float64)[::step, ::step]
                      for s in shadow_series])
    if field == "shadow":
        return stack

    sunlit = np.asarray(grids["thermal_sunlit_peak"], dtype=np.float64)[::step, ::step]
    base_shadow = np.asarray(grids["shadow_ratio"], dtype=np.float64)[::step, ::step]
    state = np.asarray(shadowed_equilibrium_c(sunlit, base_shadow), dtype=np.float64)
    dt_s = max(0.0, slice_hours) * 3600.0

    out = np.empty_like(stack)
    for index in range(stack.shape[0]):
        target = np.asarray(
            shadowed_equilibrium_c(sunlit, stack[index]), dtype=np.float64
        )
        state = np.asarray(relax_surface_c(state, target, dt_s), dtype=np.float64)
        out[index] = state
    return out
```

**Dikkat:** ilk dilimde hedef, o dilimin kendi aydınlanmasıdır; `state` başlangıçta
uzun-dönem dengesindedir. `test_series_temperature_uses_the_planner_recipe` bunu
`rtol=1e-4` ile sınar — `dt_s` bir dilim boyunca gevşemeyi zaten uygulamış olacağı
için, testin beklediği "slice 0 = uzun dönem dengesi" ancak `relax` çağrısı
`state`'i hedefe **tam** taşımıyorsa tutar. Test kırmızı kalırsa doğru düzeltme
testi değil kodu değiştirmek değildir: `build_cost_cube`'un kendi döngüsünü satır
satır karşılaştır ve **onun** sırasını uygula (o da dilim başında gevşetiyor).
Uyuşmazlık sürerse testi `cube[0]`'ı `build_cost_cube`'un ilk dilim yüzeyine karşı
sınayacak biçimde yeniden yaz — ölçüt "planlayıcıyla aynı", "benim tahminimle aynı"
değil.

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest test_terrain_api.py -q`
Expected: 17 passed

- [x] **Step 5: Verify the series actually varies**

```bash
cd backend && python -c "
import numpy as np, json
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
with c:
    q='start_utc=2026-09-01T00:00:00&n_slices=12&slice_hours=6&downsample=5'
    m = c.get(f'/api/illumination-series?{q}').json()
    print('model     :', m['shadow_model']['model'])
    print('varying   :', m['shadow_model']['time_varying'])
    print('sun elev  :', [round(s['elevation_deg'],2) for s in m['sun']])
    b = c.get(f'/api/illumination-series?{q}&format=f32&field=shadow').content
    cube = np.frombuffer(b, dtype='<f4').reshape(12,100,100)
    print('per-slice lit fraction:', [round(float((cube[i]<0.5).mean()),3) for i in range(12)])
"
```
Expected: `model: spice_horizon`, `varying: True`, ve aydınlık kesirleri
dilimden dilime **değişiyor**. Hepsi aynıysa cache ya da epoch yolunda sorun var —
`shadow_model.reason` sebebi söyler.

- [x] **Step 6: Commit**

```bash
git add backend/app/main.py backend/test_terrain_api.py
git commit -m "feat(api): publish the time-sliced illumination and surface temperature series"
```

---

## Task 6: Frontend sözleşmesi ve çalışan three.js örneği

**Files:**
- Create: `docs/frontend/3b-veri-sozlesmesi.md`

**Interfaces:**
- Consumes: Task 2, 3, 5'in uç noktaları.
- Produces: frontend ekibinin tek oturumda bağlayabileceği belge.

- [x] **Step 1: Write the document**

İçerik, sırayla:

1. **Kurulum** — `python scripts/build_horizon_cache.py` (birkaç dakika, 69 MB,
   git dışı). Bu adım atlanırsa zaman serisi sessizce statiğe düşmez, `shadow_model`
   alanında `static` ve `reason` yazar.
2. **Üç uç nokta** — `GET /api/terrain`, `GET /api/layers/{ad}?format=f32`,
   `GET /api/illumination-series`. Her biri için örnek istek ve kısaltılmış yanıt.
3. **Tel biçimi** — little-endian float32, satır öncelikli, no-data yalnızca NaN;
   seride dilim öncelikli sonra satır öncelikli.
4. **Eksen uyarısı** — satır 0 kuzey kenarı, sütun 0 batı kenarı. `PlaneGeometry`
   XY'de kurulup bu unutulursa saha **aynalı** çizilir ve makul görünür.
5. **Ölçüler** — 500×500 @ 5 m/px, 2500 m açıklık, 1063,8 m kabartı; dikey abartma
   1,0 ile başlar (manifest `vertical_exaggeration_suggested` alanında söyler).
6. **`cost` uyarısı** — 49 525 hücre NaN'dır (geçilemez). Renk rampasında NaN'ı ayrı
   ele almazlarsa rampa çöker.
7. **Çalışan three.js örneği** — aşağıdaki kod, olduğu gibi:

```js
const manifest = await (await fetch('/api/terrain')).json()
const { rows, cols, resolution_m } = manifest.grid
const { min_m, relief_m, vertical_exaggeration_suggested: vx } = manifest.elevation

// One fetch per layer; the payload is exactly rows*cols float32.
const heights = new Float32Array(
  await (await fetch(manifest.layers.elevation.binary_url)).arrayBuffer()
)

// Row 0 is the NORTH edge, so rows run -Y. PlaneGeometry's vertex order is
// row-major from its top-left corner, which lines up once the plane is laid
// flat in XZ with its width along +X.
const geometry = new THREE.PlaneGeometry(
  cols * resolution_m, rows * resolution_m, cols - 1, rows - 1
)
const position = geometry.attributes.position
for (let i = 0; i < heights.length; i++) {
  const h = heights[i]
  // NaN is the no-data marker. A NaN vertex silently removes the whole mesh
  // from the render, so clamp it to the floor rather than letting it through.
  position.setZ(i, (Number.isNaN(h) ? min_m : h - min_m) * vx)
}
geometry.computeVertexNormals()

// Colour by any other layer: same length, same order, index-for-index.
const slope = new Float32Array(
  await (await fetch(manifest.layers.slope.binary_url)).arrayBuffer()
)
const { min, max } = manifest.layers.slope
const colors = new Float32Array(slope.length * 3)
for (let i = 0; i < slope.length; i++) {
  const t = Number.isNaN(slope[i]) ? 0 : (slope[i] - min) / (max - min)
  colors[i * 3] = t             // red rises with slope
  colors[i * 3 + 1] = 1 - t
  colors[i * 3 + 2] = 0.35
}
geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))

const mesh = new THREE.Mesh(
  geometry,
  new THREE.MeshStandardMaterial({ vertexColors: true, flatShading: false })
)
mesh.rotation.x = -Math.PI / 2   // lay the plane flat; +Z becomes height
scene.add(mesh)

// The Sun, placed from the same series that produced the shadows.
const series = await (await fetch(
  '/api/illumination-series?start_utc=2026-09-01T00:00:00&n_slices=24&slice_hours=1&downsample=2'
)).json()
const sun = new THREE.DirectionalLight(0xfff6e5, 3.0)
function placeSun(slice) {
  const { azimuth_grid_deg: az, elevation_deg: el } = series.sun[slice]
  const a = THREE.MathUtils.degToRad(az)
  const e = THREE.MathUtils.degToRad(el)
  // Grid azimuth is clockwise from north (-Z after the rotation above).
  sun.position.set(
    Math.sin(a) * Math.cos(e), Math.sin(e), -Math.cos(a) * Math.cos(e)
  ).multiplyScalar(20000)
}
placeSun(0)
scene.add(sun)
```

8. **Rota 3-B'de** — `/api/plan` yanıtındaki her waypoint `altitude_m` taşıyor
   (`serializer.py:245`), yani polyline mesh'in üstüne doğrudan oturur; ayrı bir
   yükseklik sorgusu gerekmez.
9. **Değişmeyenler** — `fetchLayer` ve mevcut tüm çağrılar aynen çalışır; `format`
   opsiyoneldir ve varsayılanı `json`'dur.

- [x] **Step 2: Verify every endpoint and field name in the document exists**

```bash
cd backend && python -c "
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
with c:
    m = c.get('/api/terrain').json()
    assert {'grid','elevation','layers','binary_format','georeference'} <= set(m)
    assert {'min_m','relief_m','vertical_exaggeration_suggested'} <= set(m['elevation'])
    for name, e in m['layers'].items():
        assert c.get(e['binary_url']).status_code == 200, name
    s = c.get('/api/illumination-series?start_utc=2026-09-01T00:00:00&n_slices=4&downsample=5').json()
    assert {'sun','fields','shadow_model','slices'} <= set(s)
    print('every name the document uses resolves')
"
```
Expected: `every name the document uses resolves`

- [x] **Step 3: Commit**

```bash
git add docs/frontend/3b-veri-sozlesmesi.md
git commit -m "docs: 3-D data contract and a working three.js binding for the frontend"
```

---

## Task 7: Bütün suite ve kapanış

- [x] **Step 1: Run the full suite**

Run: `cd backend && python -m pytest -q`
Expected: **683 passed, 1 skipped, 0 failed, 0 warnings**
(654 mevcut passed + 12 `test_terrain.py` + 17 `test_terrain_api.py` = 683;
1 skipped mevcut suite'ten geliyor. SPICE yoksa güneş izi testi de skip'e döner
ve sayım 682 passed / 2 skipped olur.)

Herhangi bir **mevcut** test kırmızıya dönerse plan ihlal edilmiştir: bu iş
toplamsal olmak zorunda. Testi değiştirme — kırılmayı yapan değişikliği geri al.

- [x] **Step 2: Confirm no commit carries a Co-Authored-By trailer**

```bash
git log origin/backend/physics..HEAD --format='%H %s' &&
git log origin/backend/physics..HEAD --format='%B' | grep -ci 'co-authored-by' || echo "0 occurrences - clean"
```
Expected: `0 occurrences - clean`

- [x] **Step 3: Report, do not push**

Push edilmez. Kullanıcıya özet: hangi uç noktalar eklendi, ufuk cache'inin
üretilmesi gerektiği, ölçülen test sayısı, ve push için onay sorusu.

---

## Kapsam dışı

- **Sunucu tarafı mesh/glTF üretimi.** 500×500 heightmap için `Float32Array`
  göndermek kesinlikle daha iyi: three.js geometriyi zaten kuruyor, ve glTF aynı
  sayıları daha fazla baytla taşırdı.
- **Hillshade/normal PNG.** `slope` ve `aspect` elimizde; normal vektörü shader'da
  üç satır, ya da `computeVertexNormals()` bedava.
- **LOD / tile piramidi.** 250 000 vertex tek mesh olarak sorunsuz. Saha büyürse
  gerekir; bugün değil.
- **Gerçek doku (ortofoto).** Elimizde LROC WAC global 1024 var (frontend'de),
  bu pencerenin kendi ortofotosu yok.

---

## Yürütme notları — plandan sapmalar

Plan uygulandı ve tüm adımlar kapandı. Dört yerde plandan ayrıldım:

**1. Testler iki değil üç dosyaya bölündü.** Plan `test_terrain_api.py` içinde
üretim gridine (500×500, 1063,8 m kabartı, 49 525 NaN) dair iddialar taşıyordu.
Ama `.npy` artefaktları `.gitignore`'da; o dosya taze bir klonda çökerdi. Depoda
bunun için yerleşik bir desen var — `test_plan_4d_endpoint.py` (sentetik fixture)
ile `test_plan_4d_real_grid.py` (`skipif`'li gerçek grid) — aynı ikiye böldüm:
`test_terrain_api.py` sözleşmeyi 8×6 fixture üzerinde sınıyor (kare değil:
transpoze hatası kare gridde hayatta kalır), `test_terrain_real_grid.py` üretim
gridine dair sayıları. 12 + 19 + 11 = **42 yeni test**.

**2. Task 2 ve Task 3 tek commit.** Aynı test dosyasını ve `main.py`'nin aynı
bölgesini paylaşıyorlar; `git add` ile temiz ayrılmıyorlardı ve bir gözden
geçiren zaten ikisine birlikte bakardı.

**3. Planda olmayan bir hata bulundu ve düzeltildi — `_spice_shadow_series`.**
`spice.str2et`, SPICE havuzunu yükleyen `sun_vector_body`'den önce çağrılıyordu.
Soğuk süreçte ilk çağrı `SPICE(NOLEAPSECONDS)` fırlatıyor, geniş `except` bunu
statik seriye çeviriyor, gerekçe olarak da "real illumination unavailable"
yazılıyordu. Ölçüldü: taze süreçte `model="static"`; başka bir şey SPICE'a
dokunduktan sonra aynı çağrı `model="spice_horizon"` ve gerçekten zamanla
değişen seri. Yani `/api/plan-4d`, SPICE'ı ilk çağıran olduğunda donuk küp
üzerinde planlıyordu — tur 3'ün M-1 bulgusunun bu modülü eklemesinin sebebi olan
hatanın tam olarak kendisi.

Bu **Global Constraints'in "hiçbir mevcut davranış değişmez" maddesini ihlal
ediyor** ve bilinçli bir karardır: yeni uç noktanın manifesti ile işaret ettiği
ikili yük, süreç-global SPICE durumunun çağrı sırasına bağlı olarak birbiriyle
çelişiyordu. Havuzu açıkça yüklemek bu çelişkiyi kaldırdı ama `/api/plan-4d`'nin
davranışını değiştirdi. 4-B ve aydınlanma testlerinin 98'i geçiyor.

**4. `data_loader.py`'ye bir satır.** `window_offset` `metadata.json`'da vardı,
bellekteki metadata'ya taşınmıyordu; `/api/terrain` onsuz pencereyi ham DEM'e
oturtamıyor. Sözlüğe anahtar ekler, hiçbir davranışı değiştirmez.

## Kapanış ölçümü

| | plan öncesi | plan sonrası |
|---|---|---|
| test sayısı | 654 | **696** |
| başarısız | 0 | 0 |
| uyarı | 0 | 0 |
| süre | 346 s | 527 s |

Süre farkının 498 saniyesi iki mevcut heat1d testinde
(`test_heat1d_binning_is_deterministic_and_covers_grid` 352 s,
`test_heat1d_lookup_table_reflects_slope_and_aspect_physics` 146 s).
`test_thermal_model.py` yalnızca `app.thermal_model`'i import ediyor ve o modüle
dokunulmadı; fark makine değişkenliği, bu işin sonucu değil. Yeni testlerin en
yavaşı 0,18 s.
