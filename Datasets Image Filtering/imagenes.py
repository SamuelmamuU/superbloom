import ee
import geemap

# --- PASO 0: Autenticación e Inicialización ---
# La primera vez que ejecutes esto, se abrirá una ventana del navegador
# para que inicies sesión con tu cuenta de Google y autorices el acceso.
try:
    ee.Initialize()
except Exception as e:
    ee.Authenticate()
    ee.Initialize(project = '')

# --- PASO 1: Cargar y Filtrar la Colección de Datos ---
# Define tu área de interés (AOI), por ejemplo, un rectángulo sobre el Desierto de Mojave.
aoi = ee.Geometry.Rectangle([-118.5, 34.5, -115.0, 35.8])

# Carga la colección de Sentinel-2 Surface Reflectance y la filtra.
s2_collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                 .filterBounds(aoi)
                 .filterDate('2023-03-01', '2023-05-30'))

print("Número de imágenes encontradas:", s2_collection.size().getInfo())

# --- PASO 2: Preprocesamiento (Limpieza de Nubes) ---
# Define una función para enmascarar nubes en las imágenes de Sentinel-2.
def maskS2clouds(image):
    qa = image.select('QA60')
    # Bits 10 y 11 son nubes y cirros, respectivamente.
    cloudBitMask = 1 << 10
    cirrusBitMask = 1 << 11
    # Ambos bits deben ser 0, lo que significa que no hay nubes ni cirros.
    mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(
           qa.bitwiseAnd(cirrusBitMask).eq(0))
    # Aplica la máscara y escala los valores de reflectancia a un rango de 0-1.
    return image.updateMask(mask).divide(10000)

# Aplica la función a cada imagen de la colección usando .map().
collection_sin_nubes = s2_collection.map(maskS2clouds)

# --- PASO 3: Cálculo de Índices de Vegetación (NDVI) ---
# Define una función para añadir la banda NDVI a cada imagen.
def addNDVI(image):
    # Calcula el NDVI usando las bandas B8 (NIR) y B4 (Rojo).
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    return image.addBands(ndvi)

# Aplica la función a la colección ya sin nubes.
collection_con_ndvi = collection_sin_nubes.map(addNDVI)

# Crea una imagen compuesta tomando el valor máximo de NDVI para cada píxel.
# Esto nos da una idea clara del pico de vegetación durante el período.
max_ndvi_image = collection_con_ndvi.select('NDVI').max()

# --- PASO 4: Identificar la "Firma Espectral" ---
# Para el análisis espectral, seleccionamos la imagen más representativa,
# que a menudo es la que tiene menos nubes y un alto verdor.
# 'qualityMosaic' elige los píxeles con el valor más alto de NDVI.
imagen_pico_floracion = collection_con_ndvi.qualityMosaic('NDVI')

# Selecciona las bandas que se usarán para la clasificación posterior.
bandas_espectrales = imagen_pico_floracion.select(['B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8'])

# --- VISUALIZACIÓN INTERACTIVA CON GEEMAP ---
# Crea un mapa interactivo centrado en tu área de interés.
Map = geemap.Map(center=[35.1, -117.0], zoom=8)

# Define los parámetros de visualización.
vis_params_ndvi = {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']}
vis_params_rgb = {'min': 0, 'max': 0.3, 'bands': ['B4', 'B3', 'B2']}

# Añade las capas al mapa.
Map.addLayer(imagen_pico_floracion, vis_params_rgb, 'Imagen Color Verdadero (Pico)')
Map.addLayer(max_ndvi_image, vis_params_ndvi, 'Máximo NDVI (2023)')
Map.add_colorbar(vis_params_ndvi, label="NDVI Máximo")

# Muestra el mapa en la salida de tu notebook.
Map