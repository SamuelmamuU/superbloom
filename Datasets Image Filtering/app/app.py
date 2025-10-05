# app.py
from flask import Flask, render_template, request, jsonify
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


# --- INICIALIZACIÓN DE EARTH ENGINE (se hace una vez) ---
try:
    ee.Initialize(project='super-bloom') # Reemplaza con tu ID de proyecto
except Exception as e:
    # Si la inicialización falla la primera vez (ej. en un entorno sin credenciales),
    # intenta autenticar. En un servidor real, las credenciales se configuran de otra manera.
    print("Inicialización fallida, intentando autenticar...")
    ee.Authenticate()
    ee.Initialize(project='super-bloom')


# --- PEGA AQUÍ TODAS TUS FUNCIONES AUXILIARES Y LA FUNCIÓN PRINCIPAL ---
# (mask_s2_clouds, get_info_safe, interpretar_..., y la función analizar_region)

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

# ... (por brevedad, se asume que todo el código de análisis de la respuesta anterior está aquí)
# ... Asegúrate de tener la función analizar_region(...) definida en este archivo.

# --- CÓDIGO DE FLASK ---

app = Flask(__name__)

@app.route('/')
def home():
    """Ruta principal que muestra la página web al usuario."""
    return render_template('index.html')

@app.route('/analizar', methods=['POST'])
def analizar():
    """Ruta API que recibe los datos, procesa y devuelve los resultados."""
    try:
        # 1. Obtener los datos JSON enviados desde el frontend
        data = request.get_json()
        
        # 2. Extraer los parámetros
        coords = data.get('coords')
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        # Validación simple
        if not all([coords, start_date, end_date]):
            return jsonify({"error": "Faltan parámetros"}), 400

        # 3. Llamar a tu función de análisis de GEE
        print(f"Iniciando análisis para {coords} desde {start_date} hasta {end_date}")
        resultados = analizar_region(coords, start_date, end_date)
        print("Análisis completado, enviando resultados.")
        
        # 4. Devolver los resultados como JSON
        return jsonify(resultados)

    except Exception as e:
        print(f"Ocurrió un error en el servidor: {e}")
        return jsonify({"error": f"Error interno del servidor: {e}"}), 500

if __name__ == '__main__':
    app.run(debug=True)