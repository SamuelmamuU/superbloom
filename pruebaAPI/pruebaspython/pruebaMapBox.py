# ===========================================
# 🌍 Google Earth Engine + Folium Integration
# Proyecto: Sistema de Recomendaciones para Restaurar Ecosistemas de Floración
# ===========================================

import ee
import folium
import pandas as pd
import geopandas as gpd
import webbrowser

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
# 2️⃣ Parámetros generales para Mexicali
# ===========================================
region = ee.Geometry.Rectangle([-115.5, 32.5, -114.5, 33.0])  # Mexicali y alrededores
start_date = '2023-01-01'
end_date = '2023-12-31'
pt = ee.Geometry.Point([-115.466, 32.624])  # Centro aproximado de Mexicali

# ===========================================
# 3️⃣ Cargar colección Sentinel-2 SR y calcular NDVI
# ===========================================
s2 = ee.ImageCollection('COPERNICUS/S2_SR') \
    .filterBounds(region) \
    .filterDate(start_date, end_date) \
    .map(lambda img: img.updateMask(img.select('SCL').neq(3)))  # Quitar nubes (SCL=3)

def add_ndvi(img):
    ndvi = img.normalizedDifference(['B8', 'B4']).rename('NDVI')
    return img.addBands(ndvi)

s2_ndvi = s2.map(add_ndvi)

# ===========================================
# 4️⃣ Mediana mensual NDVI (ejemplo: abril)
# ===========================================
apr_ndvi = s2_ndvi.filterDate('2023-04-01', '2023-05-01').select('NDVI').median().clip(region)

# ===========================================
# 5️⃣ Extraer valores de NDVI para el punto
# ===========================================
mean_ndvi = apr_ndvi.reduceRegion(
    reducer=ee.Reducer.mean(),
    geometry=pt,
    scale=30
).get('NDVI').getInfo()
print(f"📍 NDVI promedio en el punto para abril 2023 (Mexicali): {mean_ndvi:.3f}")

df = pd.DataFrame([{'date': '2023-04-01', 'ndvi': mean_ndvi}])
gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy([-115.466], [32.624]))
geojson_file = "ndvi_point_mexicali.geojson"
gdf.to_file(geojson_file, driver='GeoJSON')
print(f"✅ GeoJSON generado para el punto: {geojson_file}")

# ===========================================
# 6️⃣ Visualización en Folium con ráster NDVI
# ===========================================
ndvi_params = {'min': 0, 'max': 1, 'palette': ['brown','yellow','green']}
ndvi_map = apr_ndvi.getMapId(ndvi_params)

m = folium.Map(location=[32.624, -115.466], zoom_start=10, tiles=None)

# Agregar capa ráster NDVI
folium.TileLayer(
    tiles=ndvi_map['tile_fetcher'].url_format,
    attr='Google Earth Engine',
    overlay=True,
    name='NDVI Abril 2023',
    opacity=0.5
).add_to(m)

# Agregar capa GeoJSON del punto
folium.GeoJson(
    geojson_file,
    name="NDVI Point",
    tooltip=folium.GeoJsonTooltip(fields=['date','ndvi'])
).add_to(m)

# Control de capas
folium.LayerControl().add_to(m)

# Guardar y abrir mapa
map_file = "ndvi_raster_map_mexicali.html"
m.save(map_file)
webbrowser.open(map_file)
print(f"🗺️ Mapa guardado y abierto en navegador: {map_file}")
