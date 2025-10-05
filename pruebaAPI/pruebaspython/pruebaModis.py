# =============================
# Sistema de Recomendaciones de Floración con MODIS (NASA) + Visualización Sentinel-2
# =============================

import ee
import geemap
import pandas as pd

# Inicializar Earth Engine
ee.Initialize(project='super-bloom')

# =============================
# Parámetros dinámicos del usuario
# =============================
region = ee.Geometry.Rectangle([-118.6, 34.4, -117.8, 35.0])  # Cambiar según usuario
start_date = '2023-03-01'
end_date   = '2023-05-31'
index_type = 'NDVI'  # o 'EVI'

# =============================
# Colección MODIS (análisis de floración)MODIS/061/MOD13Q1
# =============================
collection = (
    ee.ImageCollection('MODIS/061/MOD13Q1')
    .filterBounds(region)
    .filterDate(start_date, end_date)
)

# Seleccionar índice NDVI o EVI (ya pre-calculados en MODIS)
if index_type == 'NDVI':
    index_collection = collection.select('NDVI')
elif index_type == 'EVI':
    index_collection = collection.select('EVI')
else:
    raise ValueError("index_type debe ser 'NDVI' o 'EVI'")

# Calcular mediana y escalar valores
median_index = index_collection.median().multiply(0.0001).clip(region)

# =============================
# Clasificación de floración
# =============================
thresholds = {'high': 0.6, 'medium': 0.4, 'low': 0.2}

flor_state = median_index.expression(
    f"(b('{index_type}') > {thresholds['high']}) ? 3" +
    f": (b('{index_type}') > {thresholds['medium']}) ? 2" +
    ": 1"
)

# =============================
# Colección Sentinel-2 (solo para visualización de alta resolución) COPERNICUS/S2_SR_HARMONIZED
# =============================
sentinel_rgb = (
    ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(region)
    .filterDate(start_date, end_date)
    .median()
    .select(['B4', 'B3', 'B2'])  # RGB
    .divide(10000)
)

# =============================
# Mapa interactivo con geemap
# =============================
Map = geemap.Map(center=[34.7, -118.2], zoom=10)

# Capa base de Sentinel-2 (alta resolución visual)
Map.addLayer(
    sentinel_rgb,
    {'min': 0, 'max': 0.3},
    'Sentinel-2 RGB (Alta Resolución)'
)

# Capa de floración (MODIS)
Map.addLayer(
    flor_state,
    {'min': 1, 'max': 3, 'palette': ['red', 'yellow', 'green']},
    'Estado de Floración (MODIS)'
)

# Capa del índice NDVI/EVI
Map.addLayer(
    median_index,
    {'min': 0, 'max': 1, 'palette': ['brown', 'yellow', 'green']},
    f'{index_type} (MODIS)'
)

# Exportar a HTML interactivo
Map.to_html("floracion_modis_sentinel.html")

# =============================
# Exportar recomendaciones a CSV
# =============================
coords = region.bounds().coordinates().get(0)
features = []

for coord in coords.getInfo():
    pt = ee.Geometry.Point(coord)
    index_val = median_index.reduceRegion(ee.Reducer.mean(), pt, 250).get(index_type)
    state_val = flor_state.reduceRegion(ee.Reducer.mean(), pt, 250).get('constant')
    features.append({
        'lon': coord[0],
        'lat': coord[1],
        'index_value': index_val.getInfo(),
        'flor_state': state_val.getInfo()
    })

# Guardar CSV con resultados
df = pd.DataFrame(features)
df.to_csv('Floracion_Recomendaciones_MODIS_Sentinel.csv', index=False)

print("Archivo CSV generado y mapa HTML creado con visualización Sentinel-2.")
