# ===========================================
# 🌍 Google Earth Engine + Mapbox Integration
# Proyecto: Sistema de Recomendaciones para Restaurar Ecosistemas de Floración
# ===========================================

import ee
import os
import folium
import pandas as pd
import geopandas as gpd
import webbrowser

# ===========================================
# 1️⃣ AUTENTICACIÓN GEE
# ===========================================
try:
    ee.Initialize(project='super-bloom')  # Reemplaza con tu proyecto
    print("✅ Google Earth Engine inicializado correctamente.")
except Exception as e:
    print("🪪 Autenticando con Google Earth Engine...")
    ee.Authenticate()
    ee.Initialize(project='super-bloom')
    print("✅ Autenticación completada e inicialización exitosa.")

# ===========================================
# 2️⃣ TOKEN MAPBOX
# ===========================================
os.environ["MAPBOX_TOKEN"] = "sk.eyJ1Ijoic2FtdW1hbXUiLCJhIjoiY21nY3pndHRsMHZjNzJsbzd3YmRnZ3k2aCJ9.IN5gKsMsEjaejKJEALxB_A"
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")

# ===========================================
# 3️⃣ PARÁMETROS GENERALES
# ===========================================
region = ee.Geometry.Rectangle([-118.6, 34.4, -117.8, 35.0])  # Antelope Valley (ejemplo)
start_date = '2023-01-01'
end_date = '2023-12-31'

# ===========================================
# 4️⃣ CARGAR Y PROCESAR DATOS SATELITALES (Sentinel-2 SR)
# ===========================================
s2 = ee.ImageCollection('COPERNICUS/S2_SR') \
    .filterBounds(region) \
    .filterDate(start_date, end_date) \
    .map(lambda img: img.updateMask(img.select('SCL').neq(3)))  # Quitar nubes (SCL=3)

# --- Calcular NDVI ---
def add_ndvi(img):
    ndvi = img.normalizedDifference(['B8', 'B4']).rename('NDVI')
    return img.addBands(ndvi)

s2_ndvi = s2.map(add_ndvi)

# --- Mediana mensual NDVI ---
months = ee.List.sequence(1, 12)
monthly_ndvi = ee.ImageCollection.fromImages([
    s2_ndvi.filterDate(
        ee.Date(start_date).advance(m-1, 'month'),
        ee.Date(start_date).advance(m, 'month')
    ).select('NDVI').median()
    .set('system:time_start', ee.Date(start_date).advance(m-1, 'month').millis())
    .clip(region)
    for m in months.getInfo()
])

# ===========================================
# 5️⃣ OBTENER DATOS NDVI PARA UN PUNTO EN MEMORIA
# ===========================================
pt = ee.Geometry.Point([-118.2, 34.7])
ndvi_data = []

# Convertir ImageCollection a lista de imágenes
monthly_list = monthly_ndvi.toList(monthly_ndvi.size())

for i in range(monthly_ndvi.size().getInfo()):
    img = ee.Image(monthly_list.get(i))
    date = ee.Date(img.get('system:time_start')).format('YYYY-MM-dd').getInfo()
    mean_ndvi = img.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=pt,
        scale=30
    ).get('NDVI').getInfo()
    ndvi_data.append({'date': date, 'ndvi': mean_ndvi})

# Convertir a DataFrame y GeoDataFrame
df = pd.DataFrame(ndvi_data)
gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy([-118.2]*len(df), [34.7]*len(df)))
geojson_file = "ndvi_point.geojson"
gdf.to_file(geojson_file, driver='GeoJSON')
print(f"✅ GeoJSON generado: {geojson_file}")

# ===========================================
# 6️⃣ CREAR MAPA INTERACTIVO CON MAPBOX
# ===========================================
m = folium.Map(
    location=[34.7, -118.2],
    zoom_start=10,
    tiles=f"https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/{{z}}/{{x}}/{{y}}?access_token={MAPBOX_TOKEN}",
    attr='Mapbox'
)

# Agregar capa GeoJSON con NDVI
folium.GeoJson(
    geojson_file,
    name="NDVI",
    tooltip=folium.GeoJsonTooltip(fields=['date', 'ndvi'])
).add_to(m)

# Guardar mapa
map_file = "ndvi_map.html"
m.save(map_file)
print(f"🗺️ Mapa guardado como '{map_file}'")

# ===========================================
# 7️⃣ ABRIR MAPA EN EL NAVEGADOR
# ===========================================
webbrowser.open(os.path.abspath(map_file))
