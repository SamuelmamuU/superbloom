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
import json
import re # Necesario para limpiar la respuesta de Gemini

# ===========================================
# 🚀 Integración con Gemini para detección de zona
# ===========================================
import google.generativeai as genai

# Configurar tu API key de Gemini (variable de entorno GEMINI_API_KEY)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Inicializar el modelo fuera de la función (Modelo 2.5 más reciente)
model = genai.GenerativeModel('gemini-2.5-flash') 

# Función para obtener coordenadas usando Gemini (Manejo de JSON con limpieza de Markdown)
def get_coordinates_from_region(region_name):
    prompt = f"""
    Devuelve solo las coordenadas (latitud, longitud) del centro geográfico de {region_name}, 
    en formato JSON estricto como: {{"lat": 32.624, "lon": -115.466}}
    """
    
    response = model.generate_content(prompt)
    content = response.text
    
    # Limpiar el contenido de bloques de código Markdown (```json)
    cleaned_content = content.strip()
    if cleaned_content.startswith('```'):
        cleaned_content = re.sub(r'```json\s*', '', cleaned_content, flags=re.IGNORECASE)
        cleaned_content = re.sub(r'```', '', cleaned_content)
        cleaned_content = cleaned_content.strip()
    
    try:
        data = json.loads(cleaned_content)
        return float(data["lat"]), float(data["lon"])
    except Exception as e:
        raise ValueError(f"❌ Gemini no devolvió un JSON válido. Contenido que falló: {cleaned_content[:100]}... Error JSON: {e}")

# 🧠 Simulación: el usuario selecciona su zona
user_region = input("🌎 Escribe la ciudad o zona que deseas analizar: ")

# Obtener coordenadas del centro
lat_center, lon_center = get_coordinates_from_region(user_region)
print(f"📍 Coordenadas detectadas: {lat_center}, {lon_center}")

# ===========================================
# 1️⃣ Inicializar GEE (¡MOVIMIENTO CLAVE! Se ejecuta antes de usar ee.Geometry)
# ===========================================
try:
    ee.Initialize(project='super-bloom')
    print("✅ Google Earth Engine inicializado correctamente.")
except Exception:
    print("🪪 Autenticando con Google Earth Engine...")
    ee.Authenticate()
    ee.Initialize(project='super-bloom')
    print("✅ Autenticación completada e inicialización exitosa.")

# ===========================================
# 2️⃣ Definir Geometrías GEE
# ===========================================
# Calcular un rectángulo de 100 km (~0.9° en lat/lon aprox)
lat_offset = 0.9
lon_offset = 0.9
region = ee.Geometry.Rectangle([
    lon_center - lon_offset,
    lat_center - lat_offset,
    lon_center + lon_offset,
    lat_center + lat_offset
])
pt = ee.Geometry.Point([lon_center, lon_center])
print(f"🗺️ Región establecida automáticamente alrededor de {user_region}.")

# ===========================================
# 3️⃣ Configuración Mapbox
# ===========================================
os.environ["MAPBOX_TOKEN"] = "sk.eyJ1Ijoic2FtdW1hbXUiLCJhIjoiY21nY3pndHRsMHZjNzJsbzd3YmRnZ3k2aCJ9.IN5gKsMsEjaejKJEALxB_A"
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")

# ===========================================
# 4️⃣ Rangos de fechas
# ===========================================
historic_start = '2023-01-01'
historic_end   = '2023-03-31'
current_start  = '2023-04-01'
current_end    = '2023-04-30'

# ===========================================
# 5️⃣ Cargar colección Sentinel-2 SR y calcular NDVI
# ===========================================
s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
    .filterBounds(region) \
    .filterDate(historic_start, current_end) \
    .map(lambda img: img.updateMask(img.select('SCL').neq(3)))   # Quitar nubes

def add_ndvi(img):
    ndvi = img.normalizedDifference(['B8', 'B4']).rename('NDVI')
    return img.addBands(ndvi)

s2_ndvi = s2.map(add_ndvi)

# ===========================================
# 6️⃣ NDVI histórico y actual
# ===========================================
ndvi_historic = s2_ndvi.filterDate(historic_start, historic_end).select('NDVI').median().clip(region)
ndvi_current  = s2_ndvi.filterDate(current_start, current_end).select('NDVI').median().clip(region)
ndvi_diff     = ndvi_current.subtract(ndvi_historic)

# ===========================================
# 7️⃣ Valores NDVI para el punto
# ===========================================
mean_historic_result = ndvi_historic.reduceRegion(ee.Reducer.mean(), pt, 30).get('NDVI')
mean_current_result  = ndvi_current.reduceRegion(ee.Reducer.mean(), pt, 30).get('NDVI')
mean_diff_result     = ndvi_diff.reduceRegion(ee.Reducer.mean(), pt, 30).get('NDVI')

mean_historic = mean_historic_result.getInfo() if mean_historic_result else 0.0
mean_current  = mean_current_result.getInfo() if mean_current_result else 0.0
mean_diff     = mean_diff_result.getInfo() if mean_diff_result else 0.0


print(f"📍 NDVI promedio en punto Histórico: {mean_historic:.3f}")
print(f"📍 NDVI promedio en punto Actual: {mean_current:.3f}")
print(f"📍 Cambio NDVI (Actual-Histórico): {mean_diff:.3f}")

# ===========================================
# 8️⃣ Crear GeoDataFrame para el punto
# ===========================================
df = pd.DataFrame([{
    'historic': mean_historic,
    'current': mean_current,
    'diff': mean_diff
}])
gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy([lon_center], [lat_center]))
geojson_file = "ndvi_point.geojson"
gdf.to_file(geojson_file, driver='GeoJSON')
print(f"✅ GeoJSON generado: {geojson_file}")

# ===========================================
# 9️⃣ Paletas y MapId para Folium
# ===========================================
ndvi_palette = ['red', 'yellow', 'green']
diff_palette = ['red', 'yellow', 'green']

ndvi_historic_map = ndvi_historic.getMapId({'min':0,'max':1,'palette':ndvi_palette})
ndvi_current_map  = ndvi_current.getMapId({'min':0,'max':1,'palette':ndvi_palette})
ndvi_diff_map     = ndvi_diff.getMapId({'min':-0.5,'max':0.5,'palette':diff_palette})

# ===========================================
# 🔟 Crear mapa Folium
# ===========================================
m = folium.Map(location=[lat_center, lon_center], zoom_start=10, tiles=None)

# Base Mapbox Satellite
folium.TileLayer(
    tiles=f"https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/{{z}}/{{x}}/{{y}}?access_token={MAPBOX_TOKEN}",
    attr='Mapbox', name='Mapbox Satellite', overlay=False, control=False
).add_to(m)

# Capas de Google Earth Engine
folium.TileLayer(tiles=ndvi_historic_map['tile_fetcher'].url_format, attr='GEE', name='NDVI Histórico', opacity=0.5, show=False).add_to(m)
folium.TileLayer(tiles=ndvi_current_map['tile_fetcher'].url_format, attr='GEE', name='NDVI Actual', opacity=0.5, show=False).add_to(m)
folium.TileLayer(tiles=ndvi_diff_map['tile_fetcher'].url_format, attr='GEE', name='Contraste NDVI (Delta)', opacity=0.5, show=True).add_to(m)

# GeoJSON del punto con Tooltip
folium.GeoJson(
    geojson_file,
    name="NDVI Point Data",
    tooltip=folium.GeoJsonTooltip(fields=['historic','current','diff']),
    style_function=lambda x: {'fillColor': 'blue', 'color': 'black', 'weight': 1, 'fillOpacity': 0.8},
    show=True
).add_to(m)

folium.LayerControl(collapsed=False).add_to(m)

# Guardar y abrir mapa
map_file = "ndvi_semaforo_mapbox.html"
m.save(map_file)
webbrowser.open(map_file)
print(f"🗺️ Mapa guardado y abierto en navegador: {map_file}")