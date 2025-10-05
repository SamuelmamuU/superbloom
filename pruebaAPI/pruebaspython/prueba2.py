import ee
ee.Authenticate()  # Solo la primera vez
ee.Initialize(project='super-bloom')
#MAPBOX_TOKEN = "sk.eyJ1Ijoic2FtdW1hbXUiLCJhIjoiY21nY3pndHRsMHZjNzJsbzd3YmRnZ3k2aCJ9.IN5gKsMsEjaejKJEALxB_A"
import geemap
import geopandas as gpd
import pandas as pd
import folium
import os

# Opción segura
os.environ["MAPBOX_TOKEN"] = "sk.eyJ1Ijoic2FtdW1hbXUiLCJhIjoiY21nY3pndHRsMHZjNzJsbzd3YmRnZ3k2aCJ9.IN5gKsMsEjaejKJEALxB_A"

MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")


# Definir región y fechas
region = ee.Geometry.Rectangle([-118.6,34.4,-117.8,35.0])
start_date = '2023-01-01'
end_date = '2023-12-31'

# Cargar colección Sentinel-2 SR
s2 = ee.ImageCollection('COPERNICUS/S2_SR') \
    .filterBounds(region) \
    .filterDate(start_date, end_date) \
    .map(lambda img: img.updateMask(img.select('SCL').neq(3)))  # Ej. SCL=3 -> nube

# Función NDVI
def add_ndvi(img):
    ndvi = img.normalizedDifference(['B8', 'B4']).rename('NDVI')
    return img.addBands(ndvi)

s2_ndvi = s2.map(add_ndvi)

# Crear mediana mensual
months = ee.List.sequence(1, 12)
monthly_ndvi = ee.ImageCollection.fromImages([
    s2_ndvi.filterDate(
        ee.Date(start_date).advance(m-1, 'month'),
        ee.Date(start_date).advance(m, 'month')
    ).select('NDVI').median().clip(region)
    for m in months.getInfo()
])

# Exportar CSV de NDVI para un punto
pt = ee.Geometry.Point([-118.2, 34.7])
feature_collection = ee.FeatureCollection(
    monthly_ndvi.map(lambda img: ee.Feature(None, {
        'date': ee.Date(img.get('system:time_start')).format('YYYY-MM-dd'),
        'ndvi': img.reduceRegion(ee.Reducer.mean(), pt, 30).get('NDVI')
    }))
)
ee.batch.Export.table.toDrive(
    collection=feature_collection,
    description='monthly_ndvi_point',
    fileFormat='CSV'
).start()

# Leer CSV exportado desde GEE
df = pd.read_csv('monthly_ndvi_point.csv')
gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy([-118.2]*len(df), [34.7]*len(df)))
gdf.to_file("ndvi_point.geojson", driver='GeoJSON')

# Crear mapa base con Mapbox
m = folium.Map(
    location=[34.7, -118.2],
    zoom_start=10,
    tiles=f"https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/{{z}}/{{x}}/{{y}}?access_token={MAPBOX_TOKEN}",
    attr='Mapbox'
)

# Agregar capa GeoJSON con NDVI
folium.GeoJson(
    "ndvi_point.geojson",
    name="NDVI",
    tooltip=folium.GeoJsonTooltip(fields=['date','ndvi'])
).add_to(m)

# Mostrar mapa
m.save("ndvi_map.html")
