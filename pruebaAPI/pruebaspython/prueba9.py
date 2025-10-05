# ===========================================
# Google Earth Engine + Mapbox + Folium
# Sistema de Recomendaciones para Restaurar Ecosistemas
# ===========================================

import ee
import folium
import pandas as pd
import geopandas as gpd
import webbrowser
import os

# ===========================================
# Inicializar GEE
# ===========================================
try:
    ee.Initialize(project='super-bloom')
    print("Google Earth Engine inicializado correctamente.")
except Exception as e:
    print("Autenticando con Google Earth Engine...")
    ee.Authenticate()
    ee.Initialize(project='super-bloom')
    print("Autenticación completada e inicialización exitosa.")

# ===========================================
# Configuración Mapbox
# ===========================================
os.environ["MAPBOX_TOKEN"] = "TU_MAPBOX_TOKEN_AQUI"
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")

# ===========================================
# Parámetros generales
# ===========================================
region = ee.Geometry.Rectangle([-115.5, 32.5, -114.5, 33.0])  # California
lat_center, lon_center =  32.624, -115.466
pt = ee.Geometry.Point([lon_center, lat_center])

historic_start = '2023-01-01'
historic_end   = '2023-03-31'
current_start  = '2023-04-01'
current_end    = '2023-04-30'

# ===========================================
# Función para obtener valor promedio por punto
# ===========================================
def point_mean(image, point, scale):
    result = image.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=point,
        scale=scale
    ).getInfo()
    if result is None:
        return None
    return list(result.values())[0]

# ===========================================
# Cargar NDVI
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
# Cargar MODIS LST (temperatura)
# ===========================================
modis = ee.ImageCollection('MODIS/061/MOD11A2').filterBounds(region)
temp_h = modis.filterDate(historic_start, historic_end).select('LST_Day_1km').mean().clip(region)
temp_c = modis.filterDate(current_start, current_end).select('LST_Day_1km').mean().clip(region)
temp_d = temp_c.subtract(temp_h)

# ===========================================
# Cargar GPM IMERG (precipitación)
# ===========================================
gpm = ee.ImageCollection('NASA/GPM_L3/IMERG_V07').filterBounds(region)
precip_h = gpm.filterDate(historic_start, historic_end).select('precipitation').mean().clip(region)
precip_c = gpm.filterDate(current_start, current_end).select('precipitation').mean().clip(region)
precip_d = precip_c.subtract(precip_h)

# ===========================================
# Valores promedio en el punto
# ===========================================
ndvi_h_val = point_mean(ndvi_historic, pt, 30)
ndvi_c_val = point_mean(ndvi_current, pt, 30)
ndvi_d_val = point_mean(ndvi_diff, pt, 30)

temp_h_val = point_mean(temp_h, pt, 1000)
temp_c_val = point_mean(temp_c, pt, 1000)
temp_d_val = point_mean(temp_d, pt, 1000)

precip_h_val = point_mean(precip_h, pt, 1000)
precip_c_val = point_mean(precip_c, pt, 1000)
precip_d_val = point_mean(precip_d, pt, 1000)

def safe_fmt(val, fmt):
    return fmt.format(val) if val is not None else "Sin datos"

print("Valores promedio en el punto:")
print(f"NDVI Histórico: {safe_fmt(ndvi_h_val, '{:.3f}')}, NDVI Actual: {safe_fmt(ndvi_c_val, '{:.3f}')}, NDVI Cambio: {safe_fmt(ndvi_d_val, '{:.3f}')}")
print(f"Temperatura Histórico (K): {safe_fmt(temp_h_val, '{:.1f}')}, Actual (K): {safe_fmt(temp_c_val, '{:.1f}')}, Cambio: {safe_fmt(temp_d_val, '{:.1f}')}")
print(f"Precipitación Histórico (mm): {safe_fmt(precip_h_val, '{:.2f}')}, Actual (mm): {safe_fmt(precip_c_val, '{:.2f}')}, Cambio: {safe_fmt(precip_d_val, '{:.2f}')}")


# ===========================================
# Crear GeoDataFrame para el punto
# ===========================================
df = pd.DataFrame([{
    'ndvi_h': ndvi_h_val, 'ndvi_c': ndvi_c_val, 'ndvi_d': ndvi_d_val,
    'temp_h': temp_h_val, 'temp_c': temp_c_val, 'temp_d': temp_d_val,
    'precip_h': precip_h_val, 'precip_c': precip_c_val, 'precip_d': precip_d_val
}])
gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy([lon_center], [lat_center]))
geojson_file = "point_california.geojson"
gdf.to_file(geojson_file, driver='GeoJSON')

# ===========================================
# Paletas y MapId para Folium
# ===========================================
ndvi_palette = ['red', 'yellow', 'green']
diff_palette = ['red', 'yellow', 'green']
lst_palette = ['blue', 'yellow', 'red']
precip_palette = ['white','blue','darkblue']

ndvi_h_map = ndvi_historic.getMapId({'min':0,'max':1,'palette':ndvi_palette})
ndvi_c_map = ndvi_current.getMapId({'min':0,'max':1,'palette':ndvi_palette})
ndvi_d_map = ndvi_diff.getMapId({'min':-0.5,'max':0.5,'palette':diff_palette})

temp_h_map = temp_h.getMapId({'min':13000,'max':16500,'palette':lst_palette})
temp_c_map = temp_c.getMapId({'min':13000,'max':16500,'palette':lst_palette})
temp_d_map = temp_d.getMapId({'min':-500,'max':500,'palette':lst_palette})

precip_h_map = precip_h.getMapId({'min':0,'max':20,'palette':precip_palette})
precip_c_map = precip_c.getMapId({'min':0,'max':20,'palette':precip_palette})
precip_d_map = precip_d.getMapId({'min':-5,'max':5,'palette':precip_palette})

# ===========================================
# Crear mapa Folium con Mapbox fijo
# ===========================================
m = folium.Map(location=[lat_center, lon_center], zoom_start=6, tiles=None)

# Mapbox base
folium.TileLayer(
    tiles=f"https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/{{z}}/{{x}}/{{y}}?access_token={MAPBOX_TOKEN}",
    attr='Mapbox',
    name='Mapbox Satellite',
    overlay=True,
    control=False
).add_to(m)

# NDVI capas
folium.TileLayer(tiles=ndvi_h_map['tile_fetcher'].url_format, attr='Google Earth Engine', name='NDVI Histórico', opacity=0.5, overlay=False, show=False).add_to(m)
folium.TileLayer(tiles=ndvi_c_map['tile_fetcher'].url_format, attr='Google Earth Engine', name='NDVI Actual', opacity=0.5, overlay=False, show=True).add_to(m)
folium.TileLayer(tiles=ndvi_d_map['tile_fetcher'].url_format, attr='Google Earth Engine', name='NDVI Cambio', opacity=0.5, overlay=False, show=False).add_to(m)

# Temperatura capas
folium.TileLayer(tiles=temp_h_map['tile_fetcher'].url_format, attr='Google Earth Engine', name='Temp Histórico', opacity=0.5, overlay=False, show=False).add_to(m)
folium.TileLayer(tiles=temp_c_map['tile_fetcher'].url_format, attr='Google Earth Engine', name='Temp Actual', opacity=0.5, overlay=False, show=False).add_to(m)
folium.TileLayer(tiles=temp_d_map['tile_fetcher'].url_format, attr='Google Earth Engine', name='Temp Cambio', opacity=0.5, overlay=False, show=False).add_to(m)

# Precipitación capas
folium.TileLayer(tiles=precip_h_map['tile_fetcher'].url_format, attr='Google Earth Engine', name='Precip Histórico', opacity=0.5, overlay=False, show=False).add_to(m)
folium.TileLayer(tiles=precip_c_map['tile_fetcher'].url_format, attr='Google Earth Engine', name='Precip Actual', opacity=0.5, overlay=False, show=False).add_to(m)
folium.TileLayer(tiles=precip_d_map['tile_fetcher'].url_format, attr='Google Earth Engine', name='Precip Cambio', opacity=0.5, overlay=False, show=False).add_to(m)

# GeoJSON del punto
folium.GeoJson(
    geojson_file,
    name="Punto de Referencia",
    tooltip=folium.GeoJsonTooltip(fields=df.columns.tolist()),
    show=False
).add_to(m)

# Control de capas
folium.LayerControl(collapsed=False).add_to(m)

# Guardar y abrir mapa
map_file = "california_eco_mapbox.html"
m.save(map_file)
webbrowser.open(map_file)
print(f"Mapa guardado y abierto: {map_file}")
