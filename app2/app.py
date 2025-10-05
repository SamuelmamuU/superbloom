# app.py
from flask import Flask, render_template, request, jsonify
import ee
import sys

# ===========================================
# 1️⃣ INICIALIZACIÓN DE EARTH ENGINE
# ===========================================
try:
    ee.Initialize(project='super-bloom')
    print("✅ Google Earth Engine inicializado correctamente.")
except Exception as e:
    print("🪪 Autenticando con Google Earth Engine...")
    ee.Authenticate()
    ee.Initialize(project='super-bloom')
    print("✅ Autenticación completada e inicialización exitosa.")

# ===========================================
# 2️⃣ CONSTANTES Y FUNCIONES AUXILIARES
# ===========================================

# --- Constantes de Colecciones y Bandas ---
S2_COLLECTION = 'COPERNICUS/S2_SR_HARMONIZED'
LST_COLLECTION = 'MODIS/061/MOD11A1'
S2_BANDS = {'NIR': 'B8', 'RED': 'B4', 'GREEN': 'B3', 'BLUE': 'B2', 'QA': 'QA60', 'SCL': 'SCL'}
EVI_CONSTANTS = {"G": 2.5, "L": 1, "C1": 6, "C2": 7.5}

# --- Funciones de Procesamiento de Imágenes ---
def mask_s2_clouds(img):
    """Enmascara nubes y sombras de Sentinel-2 usando la banda SCL."""
    scl = img.select('SCL')
    # Píxeles buenos: vegetación, suelo desnudo, agua, nieve
    good_quality = scl.eq(4).Or(scl.eq(5)).Or(scl.eq(6)).Or(scl.eq(11))
    return img.updateMask(good_quality).divide(10000)

# --- Funciones de Interpretación ---
def get_info_safe(ee_object, default_value=None):
    """Obtiene información de un objeto GEE de forma segura."""
    try:
        return ee_object.getInfo()
    except ee.EEException as e:
        print(f"Error al obtener datos de GEE: {e}", file=sys.stderr)
        return default_value

def interpretar_ndvi(valor):
    if valor is None: return "No se pudo calcular."
    if valor < 0.1: return "Suelo desnudo, rocas o agua."
    if valor < 0.3: return "Vegetación escasa o estresada."
    return "Vegetación moderada a densa y saludable."

def interpretar_ndsi_floral(valor):
    if valor is None: return "No se pudo calcular."
    if valor < 0.1: return "Dominancia de follaje verde."
    return "Alta probabilidad de floración visible."

def interpretar_lst(valor):
    if valor is None: return "No se pudo calcular."
    if valor < 15: return "Temperatura fría."
    if valor < 30: return "Temperatura templada."
    return "Temperatura cálida a muy alta."

def interpretar_cambio_ndvi(valor):
    """Interpreta el cambio en el valor de NDVI."""
    if valor is None: return "No se pudo calcular."
    if valor > 0.1: return "Mejora significativa de la vegetación."
    if valor > 0.02: return "Ligera mejora de la vegetación."
    if valor < -0.1: return "Degradación significativa de la vegetación."
    if valor < -0.02: return "Ligera degradación de la vegetación."
    return "Cambio insignificante."

# ===========================================
# 3️⃣ FUNCIÓN PRINCIPAL DE ANÁLISIS (UNIFICADA)
# ===========================================
def analizar_ecosistema_completo(coords_rectangulo, historic_start, historic_end, current_start, current_end):
    region = ee.Geometry.Rectangle(coords_rectangulo)
    centroides = region.centroid().coordinates().getInfo()
    centro_mapa = [centroides[1], centroides[0]] # Lat, Lon
    
    # --- Preparación de la colección base Sentinel-2 ---
    s2_collection = ee.ImageCollection(S2_COLLECTION).filterBounds(region)

    # --- ANÁLISIS DEL PERÍODO ACTUAL (PARA EL DASHBOARD Y MAPA) ---
    s2_current = s2_collection.filterDate(current_start, current_end).map(mask_s2_clouds)
    image_current = s2_current.median().clip(region)

    # Calcular todos los índices para el período actual
    nir = image_current.select(S2_BANDS['NIR'])
    red = image_current.select(S2_BANDS['RED'])
    green = image_current.select(S2_BANDS['GREEN'])
    blue = image_current.select(S2_BANDS['BLUE'])
    
    ndvi_current = image_current.normalizedDifference(['B8', 'B4']).rename('NDVI')
    evi_current = image_current.expression('G * ((NIR - RED) / (NIR + C1 * RED - C2 * BLUE + L))', {'NIR': nir, 'RED': red, 'BLUE': blue, **EVI_CONSTANTS}).rename('EVI')
    ndsi_floral_current = image_current.normalizedDifference(['B3', 'B4']).rename('NDSI_floral')
    
    lst_current = ee.ImageCollection(LST_COLLECTION).filterDate(current_start, current_end).filterBounds(region).select('LST_Day_1km').median().multiply(0.02).subtract(273.15).rename('LST_Celsius').clip(region)

    # --- ANÁLISIS DEL PERÍODO HISTÓRICO (SOLO PARA NDVI Y MAPA) ---
    s2_historic = s2_collection.filterDate(historic_start, historic_end).map(mask_s2_clouds)
    ndvi_historic = s2_historic.median().normalizedDifference(['B8', 'B4']).rename('NDVI').clip(region)
    
    # --- CÁLCULO DE LA DIFERENCIA (PARA MAPA Y DASHBOARD) ---
    ndvi_diff = ndvi_current.subtract(ndvi_historic).rename('NDVI_diff')

    # --- REDUCCIÓN DE DATOS: Obtener valores promedio para el Dashboard ---
    reducer = ee.Reducer.mean()
    scale = 100

    current_values = {
        'ndvi': get_info_safe(ndvi_current.reduceRegion(reducer, region, scale).get('NDVI')),
        'evi': get_info_safe(evi_current.reduceRegion(reducer, region, scale).get('EVI')),
        'ndsi_floral': get_info_safe(ndsi_floral_current.reduceRegion(reducer, region, scale).get('NDSI_floral')),
        'lst_celsius': get_info_safe(lst_current.reduceRegion(reducer, region, 1000).get('LST_Celsius'))
    }
    
    historic_ndvi_val = get_info_safe(ndvi_historic.reduceRegion(reducer, region, scale).get('NDVI'))
    diff_ndvi_val = get_info_safe(ndvi_diff.reduceRegion(reducer, region, scale).get('NDVI_diff'))

    # --- GENERACIÓN DE URLs PARA EL MAPA ---
    ndvi_palette = ['#CE7E45', '#FCD163', '#99B718', '#74A901', '#207401', '#056201']
    diff_palette = ['#d7191c', '#fdae61', '#ffffbf', '#abdda4', '#2b83ba']

    map_urls = {
        'actual': ndvi_current.getMapId({'min': 0, 'max': 0.8, 'palette': ndvi_palette})['tile_fetcher'].url_format,
        'historico': ndvi_historic.getMapId({'min': 0, 'max': 0.8, 'palette': ndvi_palette})['tile_fetcher'].url_format,
        'diferencia': ndvi_diff.getMapId({'min': -0.3, 'max': 0.3, 'palette': diff_palette})['tile_fetcher'].url_format
    }
    
    # --- ESTRUCTURAR LA SALIDA FINAL ---
    output = {
        "map_data": {
            "centro": centro_mapa,
            "tile_urls": map_urls
        },
        "dashboard_data": {
            "actual": {
                "ndvi": {"valor": current_values['ndvi'], "interpretacion": interpretar_ndvi(current_values['ndvi'])},
                "evi": {"valor": current_values['evi'], "interpretacion": "Índice mejorado, sensible en alta vegetación."},
                "ndsi_floral": {"valor": current_values['ndsi_floral'], "interpretacion": interpretar_ndsi_floral(current_values['ndsi_floral'])},
                "lst_celsius": {"valor": current_values['lst_celsius'], "interpretacion": interpretar_lst(current_values['lst_celsius'])}
            },
            "comparativo": {
                "ndvi_historico": {"valor": historic_ndvi_val},
                "cambio_ndvi": {"valor": diff_ndvi_val, "interpretacion": interpretar_cambio_ndvi(diff_ndvi_val)}
            }
        }
    }
    return output

# ===========================================
# 4️⃣ CONFIGURACIÓN DEL SERVIDOR FLASK
# ===========================================
app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/analizar-completo', methods=['POST'])
def analizar_endpoint():
    try:
        data = request.get_json()
        required_keys = ['coords', 'historic_start', 'historic_end', 'current_start', 'current_end']
        if not all(key in data for key in required_keys):
            return jsonify({"error": "Faltan parámetros en la solicitud."}), 400
        
        print(f"Iniciando análisis completo para la región: {data['coords']}")
        resultados = analizar_ecosistema_completo(
            coords_rectangulo=data['coords'],
            historic_start=data['historic_start'],
            historic_end=data['historic_end'],
            current_start=data['current_start'],
            current_end=data['current_end']
        )
        print("Análisis completado. Enviando resultados al frontend.")
        return jsonify(resultados)
    except Exception as e:
        print(f"Ocurrió un error en el servidor: {e}", file=sys.stderr)
        return jsonify({"error": f"Error interno del servidor: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)