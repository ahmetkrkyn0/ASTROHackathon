

# LunaPath — ASTRO Hackathon

## Objetivo

LunaPath es un prototipo de hackathon que realiza **planificación de rutas multicriterio** sobre capas de análisis derivadas de datos de elevación de la superficie lunar. El objetivo es generar rutas adecuadas para el rover evaluando conjuntamente factores como la pendiente, la energía, la sombra y el riesgo térmico, y mostrar el resultado mediante una **API + interfaz web**.

---

## Características

- Generación de capas de cuadrícula a partir del DEM (elevación, pendiente, orientación, proxy de sombra, térmico, transitabilidad, coste) y metadatos
- Planificación de rutas basada en **A\*** y **simulación simplificada de energía / riesgo** a lo largo de la ruta
- Múltiples **perfiles de rover** y **ponderaciones de misión** (pendiente, energía, sombra, térmico)
- API REST con **FastAPI** (probable con `/docs`)
- Interfaz frontal con **React + TypeScript + Vite**; se conecta al backend mediante un proxy de API durante el desarrollo
- Resumen visual opcional de los datos procesados mediante un panel de **Matplotlib**

---

## Estructura del proyecto

| Carpeta | Rol |
|--------|-----|
| `backend/` | Aplicación FastAPI, lógica de planificación y simulación |
| `frontend/` | Interfaz web |
| `lunapath/` | Scripts de procesamiento del DEM y `data/raw` · `data/processed` |
| `docs/` | Referencia técnica y notas de diseño |

---

## Requisitos

- **Python** 3.11+ (recomendado)
- **Node.js** 18+
- **rasterio** (dependencia de GDAL; la instalación varía según el sistema operativo)

---

## Instalación

Desde la raíz del repositorio (`ASTROHackathon/`):

**Backend**

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
pip install -r ../lunapath/requirements.txt
```

Dado que `process_lunar_data.py` utiliza módulos del backend, en la práctica ambos archivos `requirements` se instalan juntos en el mismo entorno.

**Frontend**

```bash
cd frontend
npm install
```

---

## Ejecución

1. **Backend** (puerto por defecto `8000`):

   ```bash
   cd backend
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   Disponible en: `http://127.0.0.1:8000/docs`

2. **Frontend** (desarrollo; puerto `3000` en el proyecto, `/api` → `localhost:8000`):

   ```bash
   cd frontend
   npm run dev
   ```

3. **DEM → cuadrícula** (opcional; primero coloque el GeoTIFF correspondiente en `lunapath/data/raw` o en `data/raw` en el directorio superior; el nombre de archivo por defecto está definido en el script):

   ```bash
   cd lunapath/src
   python process_lunar_data.py
   ```

4. **Resumen visual** (si los archivos `.npy` procesados están listos):

   ```bash
   cd lunapath/src
   python visualize_processed_data.py
   ```

Si el backend encuentra las cuadrículas procesadas al iniciar, las cargará; en caso contrario, será necesario cargarlas a través de la API con `load-preprocessed` o `load-dem`. Para más detalles, los endpoints en `http://127.0.0.1:8000/docs` y `backend/app/main.py` son suficientes.

---

## Datos

- El archivo DEM para la ruta P1 debe estar en las carpetas y con los nombres que espera el script (`lunapath/src/process_lunar_data.py` y la lógica `data/raw` mencionada anteriormente en el README).
- Al cargar un DEM directamente a través de la API, el archivo se coloca bajo `backend/data/dem/` (se crea la carpeta si no existe).

---

## Más información

- [docs/lunapath_referans_belgesi_2.md](docs/lunapath_referans_belgesi_2.md) — fórmulas, constantes, modelo de costes
- [docs/stitch_design_brief.md](docs/stitch_design_brief.md) — notas de diseño de la interfaz

**Pruebas** (backend): `cd backend && pytest`

---

## Equipo

Tuna DENİZ
Ahmet KARAKOYUN
Göktuğ TABAK
Oğuzhan TARHAN
Berke KUŞ

---

*Destinado a hackathon / demostración; no sustituye al análisis de misiones reales. Utilice los datos espaciales de acuerdo con sus condiciones de licencia y uso.*
