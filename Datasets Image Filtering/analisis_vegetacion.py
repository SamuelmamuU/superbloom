import ee
import geemap
import json

# --- PASO 1: AUTENTICACIÓN E INICIALIZACIÓN ---
# Descomenta y ejecuta la primera vez para autenticarte en tu cuenta de Google.
# ee.Authenticate() 
ee.Initialize(project='super-bloom') # Reemplaza con tu ID de proyecto de GEE

# --- PASO 2: PARÁMETROS DE ANÁLISIS ---
# Define la región de interés (ROI) y el rango de fechas.
region = ee.Geometry.Rectangle([-118.6, 34.4, -117.8, 35.0])
start_date = '2023-04-01'
end_date = '2023-04-30'

# Constantes para las fórmulas que se incluirán en el JSON
EVI_CONSTANTS = {
    "G": 2.5,  # Factor de ganancia
    "L": 1,    # Corrección de fondo
    "C1": 6,   # Coeficiente atmosférico
    "C2": 7.5  # Coeficiente atmosférico
}

# --- PASO 3: PREPARACIÓN DE DATOS (SENTINEL-2) ---

# Función para enmascarar nubes en imágenes de Sentinel-2
def mask_s2_clouds(image):
    qa = image.select('QA60')
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(
           qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    return image.updateMask(mask).divide(10000)

# Cargar y pre-procesar la colección de imágenes Sentinel-2
s2_collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
    .filterDate(start_date, end_date) \
    .filterBounds(region) \
    .map(mask_s2_clouds)

# Crear una imagen compuesta (mediana)
image = s2_collection.median()

# Definir las bandas para facilitar la lectura
nir = image.select('B8')
red = image.select('B4')
green = image.select('B3')
blue = image.select('B2')

# --- PASO 4: CÁLCULO DE ÍNDICES DE VEGETACIÓN ---

# 1. NDVI (Normalized Difference Vegetation Index)
ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')

# 2. EVI (Enhanced Vegetation Index)
evi = image.expression(
    'G * ((NIR - RED) / (NIR + C1 * RED - C2 * BLUE + L))', {
        'NIR': nir, 'RED': red, 'BLUE': blue,
        'G': EVI_CONSTANTS['G'], 'L': EVI_CONSTANTS['L'],
        'C1': EVI_CONSTANTS['C1'], 'C2': EVI_CONSTANTS['C2']
    }).rename('EVI')

# 3. NDSI Floral (Índice simple para detectar flores)
ndsi_floral = image.normalizedDifference(['B3', 'B4']).rename('NDSI_floral')

# --- PASO 5: CÁLCULO DE CONDICIONES AMBIENTALES (LST) ---

lst_collection = ee.ImageCollection("MODIS/061/MOD11A1") \
    .filterDate(start_date, end_date) \
    .filterBounds(region) \
    .select('LST_Day_1km')

lst_image = lst_collection.median() \
    .multiply(0.02) \
    .subtract(273.15) \
    .rename('LST_Celsius')
# --- PASO 6: REDUCCIÓN DE DATOS Y EXTRACCIÓN DE VALORES ---
reducer = ee.Reducer.mean()
# Mantenemos un límite de pixeles por si acaso, pero el cambio clave es la 'scale'.
pixel_limit = 60000000 

# NOTA: Cambiamos la escala de 30 a 100 para reducir el número de píxeles
# en regiones muy grandes. Esto es mucho más eficiente.
escala_de_calculo = 100

# Calcular el valor medio de las bandas de entrada
mean_bands = image.reduceRegion(
    reducer=reducer,
    geometry=region,
    scale=escala_de_calculo, # Usamos la nueva escala
    maxPixels=pixel_limit
)

# Calcular el valor medio de los índices
ndvi_val = ndvi.reduceRegion(reducer=reducer, geometry=region, scale=escala_de_calculo, maxPixels=pixel_limit).get('NDVI').getInfo()
evi_val = evi.reduceRegion(reducer=reducer, geometry=region, scale=escala_de_calculo, maxPixels=pixel_limit).get('EVI').getInfo()
ndsi_floral_val = ndsi_floral.reduceRegion(reducer=reducer, geometry=region, scale=escala_de_calculo, maxPixels=pixel_limit).get('NDSI_floral').getInfo()
# Para LST, la escala original de 1000m ya es eficiente, así que la dejamos.
lst_val = lst_image.reduceRegion(reducer=reducer, geometry=region, scale=1000).get('LST_Celsius').getInfo()
# --- PASO 7: INTERPRETACIÓN AUTOMÁTICA DE RESULTADOS ---

def interpretar_ndvi(valor):
    if valor < 0.1: return "Suelo desnudo, rocas o agua."
    if valor < 0.3: return "Vegetacion escasa o estresada."
    if valor < 0.6: return "Vegetacion moderada y saludable."
    return "Vegetación densa y muy saludable."

def interpretar_ndsi_floral(valor):
    if valor < -0.1: return "Dominancia de follaje verde."
    if valor < 0.1: return "Mezcla de follaje y posible floracion."
    return "Alta probabilidad de floracion visible (colores no verdes dominantes)."

def interpretar_lst(valor):
    if valor < 10: return "Temperatura fria."
    if valor < 25: return "Temperatura templada."
    if valor < 35: return "Temperatura calida."
    return "Temperatura muy alta."

# Crear el diccionario de resultados finales
results = {
    'ndvi': {
        'valor': ndvi_val,
        'interpretacion': interpretar_ndvi(ndvi_val)
    },
    'evi': {
        'valor': evi_val,
        'interpretacion': "Similar al NDVI, mejora la sensibilidad en areas de alta biomasa."
    },
    'ndsi_floral': {
        'valor': ndsi_floral_val,
        'interpretacion': interpretar_ndsi_floral(ndsi_floral_val)
    },
    'lst_celsius': {
        'valor': lst_val,
        'interpretacion': interpretar_lst(lst_val)
    }
}

# --- PASO 8: CREACIÓN Y EXPORTACIÓN DEL ARCHIVO JSON ---

output_data = {
    "parametros_generales": {
        "region_coordenadas": region.getInfo()['coordinates'],
        "fecha_inicio": start_date,
        "fecha_fin": end_date,
    },
    "variables_de_entrada": {
        "descripcion": "Valores medios de reflectancia de las bandas usadas en los calculos.",
        "bandas_sentinel2": {
            "NIR_B8": mean_bands.get('B8').getInfo(),
            "ROJO_B4": mean_bands.get('B4').getInfo(),
            "VERDE_B3": mean_bands.get('B3').getInfo(),
            "AZUL_B2": mean_bands.get('B2').getInfo(),
        },
        "constantes_formulas": {
            "EVI": EVI_CONSTANTS
        }
    },
    "resultados_calculados": {
        "descripcion": "Valores medios de los indices para la region y fechas especificadas.",
        "indices": results
    }
}

# Nombre del archivo de salida
output_filename = 'Datasets Image Filtering/resultados_analisis_completo.json'

# Escribir el diccionario al archivo JSON con formato legible
with open(output_filename, 'w') as json_file:
    json.dump(output_data, json_file, indent=4)

print(f"¡Éxito! Los resultados han sido guardados en el archivo: {output_filename}")
print("\nContenido del JSON generado:")
print(json.dumps(output_data, indent=4))