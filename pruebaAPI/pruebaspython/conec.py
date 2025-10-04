import ee
import geemap


# Inicializar

ee.Authenticate()
ee.Initialize(project='super-bloom')

# Probar si funciona
# Definir región y fecha
region = ee.Geometry.Rectangle([-118.6,34.4,-117.8,35.0])
start = '2023-04-01'
end = '2023-04-30'

# Colección Sentinel-2
collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
    .filterDate(start, end) \
    .filterBounds(region)

# Mediana de todas las imágenes en el periodo
image = collection.median()

# Calcular NDVI
ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')

# Crear mapa con geemap
Map = geemap.Map(center=[34.7, -118.2], zoom=10)

# Añadir NDVI al mapa
ndvi_params = {'min': 0, 'max': 1, 'palette': ['brown','yellow','green']}
Map.addLayer(ndvi, ndvi_params, 'NDVI Abril')

# Mostrar mapa interactivo
Map.to_html('NDVI_Abril.html')