# ===========================================
# 🌍 Google Earth Engine + Mapbox + Folium
# Proyecto: Sistema de Recomendaciones para Restaurar Ecosistemas de Floración
# ===========================================

import ee
import folium
import pandas as pd
import geopandas as gpd
import webbrowser
import os

# ===========================================
# 1️⃣ Inicializar GEE
# ===========================================
try:
    ee.Initialize(project='super-bloom')
    print("✅ Google Earth Engine inicializado correctamente.")
except Exception as e:
    print("🪪 Autenticando con Google Earth Engine...")
    ee.Authenticate()
    ee.Initialize(project='super-bloom')
    print("✅ Autenticación completada e inicialización exitosa.")

# ===========================================
# 2️⃣ Configuración Mapbox
# ===========================================
os.environ["MAPBOX_TOKEN"] = "sk.eyJ1Ijoic2FtdW1hbXUiLCJhIjoiY21nY3pndHRsMHZjNzJsbzd3YmRnZ3k2aCJ9.IN5gKsMsEjaejKJEALxB_A"
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")

# ===========================================
# 3️⃣ Parámetros generales
# ===========================================
region = ee.Geometry.Rectangle([-115.5, 32.5, -114.5, 33.0])  # Mexicali
lat_center, lon_center = 32.624, -115.466
pt = ee.Geometry.Point([lon_center, lat_center])

# Rangos de fechas
historic_start = '2023-01-01'
historic_end   = '2023-03-31'
current_start  = '2023-04-01'
current_end    = '2023-04-30'

# ===========================================
# 4️⃣ Cargar colección Sentinel-2 SR y calcular NDVI
# ===========================================
s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
    .filterBounds(region) \
    .filterDate(historic_start, current_end) \
    .map(lambda img: img.updateMask(img.select('SCL').neq(3)))  # Quitar nubes (SCL=3)

def add_ndvi(img):
    ndvi = img.normalizedDifference(['B8', 'B4']).rename('NDVI')
    return img.addBands(ndvi)

s2_ndvi = s2.map(add_ndvi)

# ===========================================
# 5️⃣ NDVI histórico y actual
# ===========================================
ndvi_historic = s2_ndvi.filterDate(historic_start, historic_end).select('NDVI').median().clip(region)
ndvi_current  = s2_ndvi.filterDate(current_start, current_end).select('NDVI').median().clip(region)
ndvi_diff     = ndvi_current.subtract(ndvi_historic)

# ===========================================
# 6️⃣ Valores NDVI para el punto
# ===========================================
mean_historic = ndvi_historic.reduceRegion(ee.Reducer.mean(), pt, 30).get('NDVI').getInfo()
mean_current  = ndvi_current.reduceRegion(ee.Reducer.mean(), pt, 30).get('NDVI').getInfo()
mean_diff     = ndvi_diff.reduceRegion(ee.Reducer.mean(), pt, 30).get('NDVI').getInfo()

print(f"📍 NDVI promedio en punto Histórico: {mean_historic:.3f}")
print(f"📍 NDVI promedio en punto Actual: {mean_current:.3f}")
print(f"📍 Cambio NDVI (Actual-Histórico): {mean_diff:.3f}")

# Crear GeoDataFrame para el punto
df = pd.DataFrame([{
    'historic': mean_historic,
    'current': mean_current,
    'diff': mean_diff
}])
gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy([lon_center], [lat_center]))
geojson_file = "ndvi_point_mexicali.geojson"
gdf.to_file(geojson_file, driver='GeoJSON')
print(f"✅ GeoJSON generado: {geojson_file}")

# ===========================================
# 7️⃣ Paletas y MapId para Folium
# ===========================================
ndvi_palette = ['red', 'yellow', 'green']
diff_palette = ['red', 'yellow', 'green']

ndvi_historic_map = ndvi_historic.getMapId({'min':0,'max':1,'palette':ndvi_palette})
ndvi_current_map  = ndvi_current.getMapId({'min':0,'max':1,'palette':ndvi_palette})
ndvi_diff_map     = ndvi_diff.getMapId({'min':-0.5,'max':0.5,'palette':diff_palette})

# ===========================================
# 8️⃣ Crear mapa Folium con Mapbox fijo
# ===========================================
# Crear mapa Folium con Mapbox fijo (siempre visible)
m = folium.Map(
    location=[lat_center, lon_center],
    zoom_start=10,
    tiles=None  # No usamos tiles predefinidos
)

# Mapbox como capa base fija
folium.TileLayer(
    tiles=f"https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/{{z}}/{{x}}/{{y}}?access_token={MAPBOX_TOKEN}",
    attr='Mapbox',
    name='Mapbox Satellite',
    overlay=False,   # Base layer
    control=False    # No aparece en LayerControl
).add_to(m)

# Capas GEE como overlays
folium.TileLayer(
    tiles=ndvi_historic_map['tile_fetcher'].url_format,
    attr='GEE',
    name='NDVI Histórico',
    opacity=0.5,
    overlay=True,
    show=False
).add_to(m)

folium.TileLayer(
    tiles=ndvi_current_map['tile_fetcher'].url_format,
    attr='GEE',
    name='NDVI Actual',
    opacity=0.5,
    overlay=True,
    show=False
).add_to(m)

folium.TileLayer(
    tiles=ndvi_diff_map['tile_fetcher'].url_format,
    attr='GEE',
    name='Contraste NDVI',
    opacity=0.5,
    overlay=True,
    show=False
).add_to(m)

# GeoJSON del punto
folium.GeoJson(
    geojson_file,
    name="NDVI Point",
    tooltip=folium.GeoJsonTooltip(fields=['historic','current','diff']),
    show=False
).add_to(m)

# Control de capas solo para overlays
folium.LayerControl(collapsed=False).add_to(m)


# Guardar y abrir mapa
map_file = "ndvi_semaforo_mexicali_mapbox.html"
m.save(map_file)
webbrowser.open(map_file)
print(f"🗺️ Mapa guardado y abierto en navegador: {map_file}")
