import ee
import json
import sys

# --- PASO 1: AUTENTICACIÓN E INICIALIZACIÓN (Hacer esto una sola vez al iniciar el backend) ---
# Descomenta y ejecuta la primera vez para autenticarte en tu cuenta de Google.
# ee.Authenticate() 
ee.Initialize(project='super-bloom') # Reemplaza con tu ID de proyecto de GEE

# --- Constantes globales que no cambian con la entrada del usuario ---
S2_COLLECTION = 'COPERNICUS/S2_SR_HARMONIZED'
LST_COLLECTION = 'MODIS/061/MOD11A1'
S2_BANDS = {'NIR': 'B8', 'RED': 'B4', 'GREEN': 'B3', 'BLUE': 'B2', 'QA': 'QA60'}
CALCULATION_SCALE = 100 # en metros
EVI_CONSTANTS = {
    "G": 2.5, "L": 1, "C1": 6, "C2": 7.5
}

# --- Funciones auxiliares (sin cambios) ---

def mask_s2_clouds(image):
    """Función para enmascarar nubes en imágenes de Sentinel-2."""
    qa = image.select(S2_BANDS['QA'])
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(
           qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    return image.updateMask(mask).divide(10000)

def get_info_safe(ee_object, default_value=None):
    """Función segura para obtener valores de GEE, manejando posibles errores."""
    try:
        return ee_object.getInfo()
    except ee.EEException as e:
        print(f"Error al obtener datos de GEE: {e}", file=sys.stderr)
        return default_value

def interpretar_ndvi(valor):
    if valor is None: return "No se pudo calcular."
    if valor < 0.1: return "Suelo desnudo, rocas o agua."
    if valor < 0.3: return "Vegetación escasa o estresada."
    if valor < 0.6: return "Vegetación moderada y saludable."
    return "Vegetación densa y muy saludable."

def interpretar_ndsi_floral(valor):
    if valor is None: return "No se pudo calcular."
    if valor < -0.1: return "Dominancia de follaje verde."
    if valor < 0.1: return "Mezcla de follaje y posible floración."
    return "Alta probabilidad de floración visible (colores no verdes dominantes)."

def interpretar_lst(valor):
    if valor is None: return "No se pudo calcular."
    if valor < 10: return "Temperatura fría."
    if valor < 25: return "Temperatura templada."
    if valor < 35: return "Temperatura cálida."
    return "Temperatura muy alta."


# --- FUNCIÓN PRINCIPAL PARA CONECTAR AL FRONTEND ---

def analizar_region(coords_rectangulo, start_date, end_date):
    """
    Ejecuta el análisis de imágenes satelitales para una región y fechas dadas.

    Args:
        coords_rectangulo (list): Una lista con las coordenadas [xmin, ymin, xmax, ymax].
        start_date (str): Fecha de inicio en formato 'YYYY-MM-DD'.
        end_date (str): Fecha de fin en formato 'YYYY-MM-DD'.

    Returns:
        dict: Un diccionario con los parámetros y resultados del análisis, listo para ser convertido a JSON.
    """
    
    # --- PASO 2: PARÁMETROS DE ANÁLISIS (AHORA DINÁMICOS) ---
    region = ee.Geometry.Rectangle(coords_rectangulo)

    # --- PASO 3: PREPARACIÓN DE DATOS (SENTINEL-2) ---
    s2_collection = ee.ImageCollection(S2_COLLECTION) \
        .filterDate(start_date, end_date) \
        .filterBounds(region) \
        .map(mask_s2_clouds)
    
    image = s2_collection.median()
    nir = image.select(S2_BANDS['NIR'])
    red = image.select(S2_BANDS['RED'])
    blue = image.select(S2_BANDS['BLUE'])

    # --- PASO 4: CÁLCULO DE ÍNDICES DE VEGETACIÓN ---
    ndvi = image.normalizedDifference([S2_BANDS['NIR'], S2_BANDS['RED']]).rename('NDVI')
    evi = image.expression(
        'G * ((NIR - RED) / (NIR + C1 * RED - C2 * BLUE + L))', {
            'NIR': nir, 'RED': red, 'BLUE': blue, **EVI_CONSTANTS
        }).rename('EVI')
    ndsi_floral = image.normalizedDifference([S2_BANDS['GREEN'], S2_BANDS['RED']]).rename('NDSI_floral')

    # --- PASO 5: CÁLCULO DE CONDICIONES AMBIENTALES (LST) ---
    lst_collection = ee.ImageCollection(LST_COLLECTION) \
        .filterDate(start_date, end_date) \
        .filterBounds(region) \
        .select('LST_Day_1km')
    
    lst_image = lst_collection.median() \
        .multiply(0.02) \
        .subtract(273.15) \
        .rename('LST_Celsius')

    # --- PASO 6: REDUCCIÓN DE DATOS Y EXTRACCIÓN DE VALORES ---
    reducer = ee.Reducer.mean()
    pixel_limit = 1e8
    
    mean_bands = image.reduceRegion(reducer=reducer, geometry=region, scale=CALCULATION_SCALE, maxPixels=pixel_limit)
    
    ndvi_val = get_info_safe(ndvi.reduceRegion(reducer=reducer, geometry=region, scale=CALCULATION_SCALE, maxPixels=pixel_limit).get('NDVI'))
    evi_val = get_info_safe(evi.reduceRegion(reducer=reducer, geometry=region, scale=CALCULATION_SCALE, maxPixels=pixel_limit).get('EVI'))
    ndsi_floral_val = get_info_safe(ndsi_floral.reduceRegion(reducer=reducer, geometry=region, scale=CALCULATION_SCALE, maxPixels=pixel_limit).get('NDSI_floral'))
    lst_val = get_info_safe(lst_image.reduceRegion(reducer=reducer, geometry=region, scale=1000).get('LST_Celsius'))

    # --- PASO 7: INTERPRETACIÓN Y ENSAMBLAJE DE RESULTADOS ---
    results = {
        'ndvi': {'valor': ndvi_val, 'interpretacion': interpretar_ndvi(ndvi_val)},
        'evi': {'valor': evi_val, 'interpretacion': "Similar al NDVI, mejora la sensibilidad en áreas de alta biomasa." if evi_val is not None else "No se pudo calcular."},
        'ndsi_floral': {'valor': ndsi_floral_val, 'interpretacion': interpretar_ndsi_floral(ndsi_floral_val)},
        'lst_celsius': {'valor': lst_val, 'interpretacion': interpretar_lst(lst_val)}
    }

    output_data = {
        "parametros_generales": {
            "region_coordenadas": get_info_safe(region.coordinates()),
            "fecha_inicio": start_date,
            "fecha_fin": end_date,
        },
        "variables_de_entrada": {
            "descripcion": "Valores medios de reflectancia de las bandas usadas en los cálculos.",
            "bandas_sentinel2": {
                "NIR_B8": get_info_safe(mean_bands.get(S2_BANDS['NIR'])),
                "ROJO_B4": get_info_safe(mean_bands.get(S2_BANDS['RED'])),
                "VERDE_B3": get_info_safe(mean_bands.get(S2_BANDS['GREEN'])),
                "AZUL_B2": get_info_safe(mean_bands.get(S2_BANDS['BLUE'])),
            },
            "constantes_formulas": {"EVI": EVI_CONSTANTS}
        },
        "resultados_calculados": {
            "descripcion": "Valores medios de los índices para la región y fechas especificadas.",
            "indices": results
        }
    }
    
    return output_data

# --- Ejemplo de cómo llamarías a esta función desde tu backend ---
if __name__ == '__main__':
    # 1. Obtén los datos del usuario (simulamos una entrada del frontend)
    coordenadas_usuario = [-118.6, 34.4, -117.8, 35.0] # [xmin, ymin, xmax, ymax]
    fecha_inicio_usuario = '2023-04-01'
    fecha_fin_usuario = '2023-04-30'
    
    # 2. Llama a la función de análisis
    resultados_json = analizar_region(
        coords_rectangulo=coordenadas_usuario,
        start_date=fecha_inicio_usuario,
        end_date=fecha_fin_usuario
    )
    
    # 3. Haz algo con los resultados (enviarlos al frontend, guardarlos, etc.)
    print("¡Análisis completado! Resultados listos para enviar al frontend:")
    print(json.dumps(resultados_json, indent=4))

    # Opcional: Guardar en un archivo como en tu script original
    output_filename = 'resultados_analisis_dinamico.json'
    with open(output_filename, 'w') as json_file:
        json.dump(resultados_json, json_file, indent=4)
    print(f"\nResultados también guardados en: {output_filename}")