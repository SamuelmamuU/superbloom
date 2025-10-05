# =============================
# Sistema de Recomendaciones de Floración
# =============================

import ee
import geemap
import pandas as pd

#  Inicializar Earth Engine
ee.Initialize(project='super-bloom')

#  Parámetros dinámicos de usuario
region = ee.Geometry.Rectangle([-118.6, 34.4, -117.8, 35.0])  # Cambiar según usuario
start_date = '2023-03-01'
end_date   = '2023-05-31'
index_type = 'NDVI'  # O 'EVI'

#  Cargar colección Sentinel-2
collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
              .filterBounds(region)
              .filterDate(start_date, end_date)
              .map(lambda img: img.updateMask(img.select('SCL').neq(3).And(img.select('SCL').neq(8))))
             )

#  Función para calcular índices
def add_indices(img):
    if index_type == 'NDVI':
        ndvi = img.normalizedDifference(['B8','B4']).rename('NDVI')
        return img.addBands(ndvi)
    elif index_type == 'EVI':
        evi = img.expression(
            '2.5 * ((NIR - RED) / (NIR + 6*RED - 7.5*BLUE + 1))',
            {
                'NIR': img.select('B8'),
                'RED': img.select('B4'),
                'BLUE': img.select('B2')
            }
        ).rename('EVI')
        return img.addBands(evi)

index_collection = collection.map(add_indices)

# Mediana del índice
median_index = index_collection.select(index_type).median().clip(region)

# Clasificación de floración
thresholds = {'high':0.6, 'medium':0.4, 'low':0.2}

flor_state = median_index.expression(
    f"(b('{index_type}') > {thresholds['high']}) ? 3" +
    f": (b('{index_type}') > {thresholds['medium']}) ? 2" +
    ": 1"
)

# Visualización interactiva con geemap
Map = geemap.Map(center=[34.7, -118.2], zoom=100)
Map.addLayer(flor_state, {'min':1, 'max':3, 'palette':['red','yellow','green']}, 'Estado de Floración')
Map.addLayer(median_index, {'min':0, 'max':1, 'palette':['brown','yellow','green']}, index_type)
Map.to_html("prueba.html")
# En Jupyter o Colab, el mapa será interactivo

# Exportar recomendaciones a CSV
# Creamos una grilla de puntos dentro de la región
coords = region.bounds().coordinates().get(0)
features = []
for coord in coords.getInfo():
    pt = ee.Geometry.Point(coord)
    index_val = median_index.reduceRegion(ee.Reducer.mean(), pt, 30).get(index_type)
    state_val = flor_state.reduceRegion(ee.Reducer.mean(), pt, 30).get('constant')
    features.append({'lon': coord[0], 'lat': coord[1], 'index_value': index_val.getInfo(), 'flor_state': state_val.getInfo()})

# Guardar CSV
df = pd.DataFrame(features)
df.to_csv('Floracion_Recomendaciones.csv', index=False)
print("Archivo CSV generado con recomendaciones.")
