# ===========================================
# Google Earth Engine + Mapbox + Folium + Gemini
# Sistema de Recomendaciones Ambiental
# ===========================================

import ee
import folium
import pandas as pd
import geopandas as gpd
import webbrowser
import google.generativeai as genai
import os
import json

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def get_coordinates_from_region(region_name):
    prompt = f"""
    Devuelve solo las coordenadas (latitud, longitud) del centro geográfico de {region_name},
    en formato JSON. Ejemplo: {{"lat": 32.624, "lon": -115.466}}
    """

    response = genai.generate_text(
        model="text-bison-001",
        prompt=prompt,
        temperature=0
    )

    try:
        data = json.loads(response.candidates[0].content)
        return data["lat"], data["lon"]
    except Exception as e:
        raise ValueError("❌ Gemini no devolvió un JSON válido.") from e


# ===========================================
# Inicializar GEE
# ===========================================
try:
    ee.Initialize(project='super-bloom')
    print("✅ Google Earth Engine inicializado correctamente.")
except Exception as e:
    print("🔐 Autenticando con Google Earth Engine...")
    ee.Authenticate()
    ee.Initialize(project='super-bloom')
    print("✅ Autenticación completada e inicialización exitosa.")

# ===========================================
# Configuración Mapbox
# ===========================================
os.environ["MAPBOX_TOKEN"] = "sk.eyJ1Ijoic2FtdW1hbXUiLCJhIjoiY21nY3pndHRsMHZjNzJsbzd3YmRnZ3k2aCJ9.IN5gKsMsEjaejKJEALxB_A"
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")

# ===========================================
# Solicitar zona al usuario y obtener coordenadas
# ===========================================
user_region = input("🌎 Escribe la ciudad o zona que deseas analizar: ")
lat_center, lon_center = get_coordinates_from_region(user_region)
pt = ee.Geometry.Point([lon_center, lat_center])
region = ee.Geometry.Rectangle([
    lon_center - 0.45,  # ~50 km aprox
    lat_center - 0.45,
    lon_center + 0.45,
    lat_center + 0.45
])
print(f"📍 Coordenadas detectadas: {lat_center}, {lon_center}")

# ===========================================
# Fechas de referencia
# ===========================================
historic_start = '2023-01-01'
historic_end   = '2023-03-31'
current_start  = '2023-04-01'
current_end    = '2023-04-30'

# ===========================================
# --- CAPA 1: Vegetación (NDVI - Sentinel-2) ---
# ===========================================
s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
    .filterBounds(region) \
    .filterDate(historic_start, current_end) \
    .map(lambda img: img.updateMask(img.select('SCL').neq(3)))

def add_ndvi(img):
    ndvi = img.normalizedDifference(['B8', 'B4']).rename('NDVI')
    return img.addBands(ndvi)

s2_ndvi = s2.map(add_ndvi)

ndvi_historic = s2_ndvi.filterDate(historic_start, historic_end).select('NDVI').median().clip(region)
ndvi_current  = s2_ndvi.filterDate(current_start, current_end).select('NDVI').median().clip(region)
ndvi_diff     = ndvi_current.subtract(ndvi_historic)

# ===========================================
# --- CAPA 2: Temperatura ---
# ===========================================
modis_lst = ee.ImageCollection('MODIS/061/MOD11A2') \
    .filterBounds(region) \
    .filterDate(historic_start, current_end)

def to_celsius(img):
    lst = img.select('LST_Day_1km').multiply(0.02).subtract(273.15).rename('LST')
    return img.addBands(lst)

modis_lst_c = modis_lst.map(to_celsius)

lst_historic = modis_lst_c.filterDate(historic_start, historic_end).select('LST').mean().clip(region)
lst_current  = modis_lst_c.filterDate(current_start, current_end).select('LST').mean().clip(region)
lst_diff     = lst_current.subtract(lst_historic)

# ===========================================
# --- CAPA 3: Precipitación ---
# ===========================================
gpm = ee.ImageCollection('NASA/GPM_L3/IMERG_V06') \
    .filterBounds(region) \
    .filterDate(historic_start, current_end)

def daily_precip(img):
    precip_mm = img.select('precipitationCal').multiply(0.5).rename('precip_mm')
    return precip_mm.copyProperties(img, img.propertyNames())

gpm_daily = gpm.map(daily_precip)

precip_historic = gpm_daily.filterDate(historic_start, historic_end).sum().clip(region)
precip_current  = gpm_daily.filterDate(current_start, current_end).sum().clip(region)

epsilon = 1e-6
precip_diff_ponderada = precip_current.subtract(precip_historic).divide(
    precip_historic.add(epsilon)
).rename('precip_diff_rel')

# ===========================================
# Valores en punto central
# ===========================================
def get_mean(image, band):
    return image.reduceRegion(ee.Reducer.mean(), pt, 1000).get(band).getInfo()

print("\n📊 Promedios en punto central:")
print(f"🌿 NDVI Histórico: {get_mean(ndvi_historic, 'NDVI'):.3f}")
print(f"🌿 NDVI Actual: {get_mean(ndvi_current, 'NDVI'):.3f}")
print(f"🔥 Temp. Histórica: {get_mean(lst_historic, 'LST'):.2f} °C")
print(f"🔥 Temp. Actual: {get_mean(lst_current, 'LST'):.2f} °C")
print(f"💧 Precip. Histórica: {get_mean(precip_historic, 'precip_mm'):.2f} mm/h")
print(f"💧 Precip. Actual: {get_mean(precip_current, 'precip_mm'):.2f} mm/h")

# ===========================================
# Paletas y MapIDs
# ===========================================
ndvi_palette = ['red','yellow','green']
lst_palette  = ['blue','cyan','yellow','orange','red']
precip_palette = ['white','blue','purple']

ndvi_historic_map = ndvi_historic.getMapId({'min':0,'max':1,'palette':ndvi_palette})
ndvi_current_map  = ndvi_current.getMapId({'min':0,'max':1,'palette':ndvi_palette})
ndvi_diff_map     = ndvi_diff.getMapId({'min':-0.5,'max':0.5,'palette':['red','white','green']})

lst_historic_map = lst_historic.getMapId({'min':10,'max':45,'palette':lst_palette})
lst_current_map  = lst_current.getMapId({'min':10,'max':45,'palette':lst_palette})
lst_diff_map     = lst_diff.getMapId({'min':-5,'max':5,'palette':['blue','white','red']})

precip_historic_map = precip_historic.getMapId({'min':0,'max':10,'palette':precip_palette})
precip_current_map  = precip_current.getMapId({'min':0,'max':10,'palette':precip_palette})
precip_diff_map     = precip_diff_ponderada.getMapId({'min':-1,'max':1,'palette':['red','white','blue']})

# ===========================================
# Crear mapa Folium
# ===========================================
m = folium.Map(location=[lat_center, lon_center], zoom_start=8, tiles=None)

# Mapbox
folium.TileLayer(
    tiles=f"https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/{{z}}/{{x}}/{{y}}?access_token={MAPBOX_TOKEN}",
    attr='Mapbox', name='Mapbox Satellite', overlay=False, control=False
).add_to(m)

# Capas NDVI
folium.TileLayer(tiles=ndvi_historic_map['tile_fetcher'].url_format, name='🌿 NDVI Histórico', opacity=0.6, show=False).add_to(m)
folium.TileLayer(tiles=ndvi_current_map['tile_fetcher'].url_format, name='🌿 NDVI Actual', opacity=0.6, show=False).add_to(m)
folium.TileLayer(tiles=ndvi_diff_map['tile_fetcher'].url_format, name='🌿 NDVI Diferencia', opacity=0.6, show=False).add_to(m)

# Capas Temperatura
folium.TileLayer(tiles=lst_historic_map['tile_fetcher'].url_format, name='🔥 Temp. Histórica', opacity=0.6, show=False).add_to(m)
folium.TileLayer(tiles=lst_current_map['tile_fetcher'].url_format, name='🔥 Temp. Actual', opacity=0.6, show=False).add_to(m)
folium.TileLayer(tiles=lst_diff_map['tile_fetcher'].url_format, name='🔥 Temp. Diferencia', opacity=0.6, show=False).add_to(m)

# Capas Precipitación
folium.TileLayer(tiles=precip_historic_map['tile_fetcher'].url_format, name='💧 Precipitación Histórica', opacity=0.6, show=False).add_to(m)
folium.TileLayer(tiles=precip_current_map['tile_fetcher'].url_format, name='💧 Precipitación Actual', opacity=0.6, show=False).add_to(m)
folium.TileLayer(tiles=precip_diff_map['tile_fetcher'].url_format, name='💧 Precipitación Diferencia', opacity=0.6, show=False).add_to(m)

# Control de capas
folium.LayerControl(collapsed=True).add_to(m)

# Guardar y abrir mapa
map_file = "gee_mapbox_ambiente_gemini.html"
m.save(map_file)
webbrowser.open(map_file)
print(f"🌍 Mapa generado y abierto: {map_file}")
