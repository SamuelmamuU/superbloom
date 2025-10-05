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
    print("✅ Autenticación completada.")

# ===========================================
# 2️⃣ CONSTANTES Y FUNCIONES AUXILIARES
# ===========================================

# --- Constantes de Colecciones y Bandas ---
S2_COLLECTION = 'COPERNICUS/S2_SR_HARMONIZED'
LST_COLLECTION = 'MODIS/061/MOD11A2'
GPM_COLLECTION = 'NASA/GPM_L3/IMERG_V06'
S2_BANDS = {'NIR': 'B8', 'RED': 'B4', 'GREEN': 'B3', 'BLUE': 'B2', 'SCL': 'SCL'}
EVI_CONSTANTS = {"G": 2.5, "L": 1, "C1": 6, "C2": 7.5}

# --- Funciones de Procesamiento de Imágenes ---
def mask_s2_clouds(img):
    scl = img.select('SCL')
    good_quality = scl.eq(4).Or(scl.eq(5)).Or(scl.eq(6)).Or(scl.eq(11))
    return img.updateMask(good_quality).divide(10000)

def to_celsius(img):
    lst = img.select('LST_Day_1km').multiply(0.02).subtract(273.15).rename('LST')
    return img.addBands(lst)

# --- Funciones de Interpretación y Gráficas ---
def get_info_safe(ee_object, default_value=None):
    try: return ee_object.getInfo()
    except ee.EEException as e:
        print(f"Error GEE: {e}", file=sys.stderr)
        return default_value

def _normalize(value, min_val, max_val):
    """Normaliza un valor a una escala de 0 a 1."""
    if value is None:
        return 0
    # Asegura que el valor esté dentro del rango para evitar resultados > 1 o < 0
    value = max(min(value, max_val), min_val)
    return (value - min_val) / (max_val - min_val)

def interpretar_cambio(valor, umbral_alto=0.1, umbral_bajo=0.02, tipo=""):
    if valor is None: return "No se pudo calcular."
    if valor > umbral_alto: return f"Aumento significativo de {tipo}."
    if valor > umbral_bajo: return f"Ligero aumento de {tipo}."
    if valor < -umbral_alto: return f"Descenso significativo de {tipo}."
    if valor < -umbral_bajo: return f"Ligero descenso de {tipo}."
    return "Cambio insignificante."

def interpretar_precipitacion(valor):
    if valor is None: return "No se pudo calcular."
    if valor < 1: return "Precipitación muy baja o nula."
    if valor < 10: return "Precipitación baja."
    if valor < 50: return "Precipitación moderada."
    return "Precipitación alta."

# ===========================================
# 3️⃣ FUNCIÓN PRINCIPAL DE ANÁLISIS (AVANZADA)
# ===========================================
def analizar_ecosistema_avanzado(coords, h_start, h_end, c_start, c_end):
    region = ee.Geometry.Rectangle(coords)
    centro_mapa = [region.centroid().coordinates().get(1).getInfo(), region.centroid().coordinates().get(0).getInfo()]

    # --- CÁLCULOS PRINCIPALES ---
    # 1. VEGETACIÓN (NDVI)
    s2_collection = ee.ImageCollection(S2_COLLECTION).filterBounds(region)
    s2_current_col = s2_collection.filterDate(c_start, c_end).map(mask_s2_clouds)
    s2_historic_col = s2_collection.filterDate(h_start, h_end).map(mask_s2_clouds)
    
    img_current = s2_current_col.median().clip(region)
    ndvi_current = img_current.normalizedDifference(['B8', 'B4']).rename('NDVI')
    ndvi_historic = s2_historic_col.median().normalizedDifference(['B8', 'B4']).rename('NDVI').clip(region)
    ndvi_diff = ndvi_current.subtract(ndvi_historic).rename('NDVI_diff')

    # 2. TEMPERATURA (LST)
    lst_collection = ee.ImageCollection(LST_COLLECTION).filterBounds(region).map(to_celsius)
    lst_current = lst_collection.filterDate(c_start, c_end).select('LST').mean().clip(region)
    lst_historic = lst_collection.filterDate(h_start, h_end).select('LST').mean().clip(region)
    lst_diff = lst_current.subtract(lst_historic).rename('LST_diff')
    
    # 3. PRECIPITACIÓN (GPM)
    gpm_collection = ee.ImageCollection(GPM_COLLECTION).filterBounds(region)
    precip_current = gpm_collection.filterDate(c_start, c_end).select('precipitationCal').sum().clip(region)
    precip_historic = gpm_collection.filterDate(h_start, h_end).select('precipitationCal').sum().clip(region)
    precip_diff_rel = precip_current.subtract(precip_historic).divide(precip_historic.add(1e-6)).rename('precip_diff_rel')

    # 4. ÍNDICES ADICIONALES (Solo para el dashboard actual)
    evi_current = img_current.expression('G * ((NIR - RED) / (NIR + C1 * RED - C2 * BLUE + L))', {'NIR': img_current.select('B8'), 'RED': img_current.select('B4'), 'BLUE': img_current.select('B2'), **EVI_CONSTANTS}).rename('EVI')
    ndsi_floral_current = img_current.normalizedDifference(['B3', 'B4']).rename('NDSI_floral')

    # --- REDUCCIÓN DE DATOS (Obtener valores numéricos) ---
    reducer_mean = ee.Reducer.mean()
    scale = 100
    
    vals = {
        'ndvi_c': get_info_safe(ndvi_current.reduceRegion(reducer_mean, region, scale).get('NDVI')),
        'ndvi_h': get_info_safe(ndvi_historic.reduceRegion(reducer_mean, region, scale).get('NDVI')),
        'ndvi_d': get_info_safe(ndvi_diff.reduceRegion(reducer_mean, region, scale).get('NDVI_diff')),
        'lst_c': get_info_safe(lst_current.reduceRegion(reducer_mean, region, 1000).get('LST')),
        'lst_h': get_info_safe(lst_historic.reduceRegion(reducer_mean, region, 1000).get('LST')),
        'lst_d': get_info_safe(lst_diff.reduceRegion(reducer_mean, region, 1000).get('LST_diff')),
        'precip_c': get_info_safe(precip_current.reduceRegion(reducer_mean, region, 1000).get('precipitationCal')),
        'precip_h': get_info_safe(precip_historic.reduceRegion(reducer_mean, region, 1000).get('precipitationCal')),
        'precip_d': get_info_safe(precip_diff_rel.reduceRegion(reducer_mean, region, 1000).get('precip_diff_rel')),
        'evi_c': get_info_safe(evi_current.reduceRegion(reducer_mean, region, scale).get('EVI')),
        'ndsi_c': get_info_safe(ndsi_floral_current.reduceRegion(reducer_mean, region, scale).get('NDSI_floral'))
    }

    # --- GENERACIÓN DE MAP IDs ---
    map_urls = {
        'ndvi': {
            'actual': ndvi_current.getMapId({'min': 0, 'max': 0.8, 'palette': ['red', 'yellow', 'green']})['tile_fetcher'].url_format,
            'historico': ndvi_historic.getMapId({'min': 0, 'max': 0.8, 'palette': ['red', 'yellow', 'green']})['tile_fetcher'].url_format,
            'diferencia': ndvi_diff.getMapId({'min': -0.3, 'max': 0.3, 'palette': ['red', 'yellow', 'green']})['tile_fetcher'].url_format
        },
        'temperatura': {
            'actual': lst_current.getMapId({'min': 10, 'max': 45, 'palette': ['blue', 'cyan', 'yellow', 'red']})['tile_fetcher'].url_format,
            'historico': lst_historic.getMapId({'min': 10, 'max': 45, 'palette': ['blue', 'cyan', 'yellow', 'red']})['tile_fetcher'].url_format,
            'diferencia': lst_diff.getMapId({'min': -5, 'max': 5, 'palette': ['blue', 'white', 'red']})['tile_fetcher'].url_format
        },
        'precipitacion': {
            'actual': precip_current.getMapId({'min': 0, 'max': 100, 'palette': ['white', 'blue', 'purple']})['tile_fetcher'].url_format,
            'historico': precip_historic.getMapId({'min': 0, 'max': 100, 'palette': ['white', 'blue', 'purple']})['tile_fetcher'].url_format,
            'diferencia': precip_diff_rel.getMapId({'min': -1, 'max': 1, 'palette': ['red', 'white', 'blue']})['tile_fetcher'].url_format
        }
    }
    
    # --- 📊 PREPARACIÓN DE DATOS PARA GRÁFICAS ---
    chart_data = {
        "bar_charts": {
            "ndvi": {
                "labels": ["Histórico", "Actual"],
                "datasets": [{
                    "label": "NDVI",
                    "data": [vals.get('ndvi_h') or 0, vals.get('ndvi_c') or 0],
                    "backgroundColor": ["rgba(255, 159, 64, 0.5)", "rgba(75, 192, 192, 0.5)"],
                    "borderColor": ["rgb(255, 159, 64)", "rgb(75, 192, 192)"],
                    "borderWidth": 1
                }]
            },
            "temperatura": {
                "labels": ["Histórico", "Actual"],
                "datasets": [{
                    "label": "Temperatura (°C)",
                    "data": [vals.get('lst_h') or 0, vals.get('lst_c') or 0],
                    "backgroundColor": ["rgba(54, 162, 235, 0.5)", "rgba(255, 99, 132, 0.5)"],
                    "borderColor": ["rgb(54, 162, 235)", "rgb(255, 99, 132)"],
                    "borderWidth": 1
                }]
            },
            "precipitacion": {
                "labels": ["Histórico", "Actual"],
                "datasets": [{
                    "label": "Precipitación Acumulada (mm)",
                    "data": [vals.get('precip_h') or 0, vals.get('precip_c') or 0],
                    "backgroundColor": ["rgba(201, 203, 207, 0.5)", "rgba(153, 102, 255, 0.5)"],
                    "borderColor": ["rgb(201, 203, 207)", "rgb(153, 102, 255)"],
                    "borderWidth": 1
                }]
            }
        },
        "radar_chart": {
            "labels": ["Vegetación (NDVI)", "Temperatura", "Precipitación"],
            "datasets": [
                {
                    "label": "Histórico",
                    "data": [
                        _normalize(vals.get('ndvi_h'), -0.2, 1),
                        _normalize(vals.get('lst_h'), 0, 50),
                        _normalize(vals.get('precip_h'), 0, 500)
                    ],
                    "fill": True,
                    "backgroundColor": "rgba(255, 159, 64, 0.2)",
                    "borderColor": "rgb(255, 159, 64)",
                },
                {
                    "label": "Actual",
                    "data": [
                        _normalize(vals.get('ndvi_c'), -0.2, 1),
                        _normalize(vals.get('lst_c'), 0, 50),
                        _normalize(vals.get('precip_c'), 0, 500)
                    ],
                    "fill": True,
                    "backgroundColor": "rgba(75, 192, 192, 0.2)",
                    "borderColor": "rgb(75, 192, 192)",
                }
            ]
        }
    }

    # --- ESTRUCTURAR LA SALIDA FINAL ---
    output = {
        "map_data": {"centro": centro_mapa, "tile_urls": map_urls},
        "dashboard_data": {
            "actual": {
                "ndvi": {"valor": vals['ndvi_c']},
                "evi": {"valor": vals['evi_c']},
                "ndsi_floral": {"valor": vals['ndsi_c']},
                "temperatura": {"valor": vals['lst_c']},
                "precipitacion": {"valor": vals['precip_c'], "interpretacion": interpretar_precipitacion(vals['precip_c'])}
            },
            "comparativo": {
                "ndvi_historico": {"valor": vals['ndvi_h']},
                "cambio_ndvi": {"valor": vals['ndvi_d'], "interpretacion": interpretar_cambio(vals['ndvi_d'], 0.1, 0.02, 'vegetación')},
                "temperatura_historica": {"valor": vals['lst_h']},
                "cambio_temperatura": {"valor": vals['lst_d'], "interpretacion": interpretar_cambio(vals['lst_d'], 2, 0.5, 'temperatura')},
                "precipitacion_historica": {"valor": vals['precip_h']},
                "cambio_precipitacion_rel": {"valor": vals['precip_d'], "interpretacion": interpretar_cambio(vals['precip_d'], 0.5, 0.1, 'precipitación')}
            }
        },
        "chart_data": chart_data
    }
    return output

# ===========================================
# 4️⃣ CONFIGURACIÓN DEL SERVIDOR FLASK
# ===========================================
app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/analizar-avanzado', methods=['POST'])
def analizar_endpoint():
    try:
        data = request.get_json()
        required_keys = ['coords', 'historic_start', 'historic_end', 'current_start', 'current_end']
        if not all(key in data for key in required_keys):
            return jsonify({"error": "Faltan parámetros."}), 400
        
        resultados = analizar_ecosistema_avanzado(
            data['coords'], data['historic_start'], data['historic_end'],
            data['current_start'], data['current_end']
        )
        return jsonify(resultados)
    except Exception as e:
        print(f"Error en servidor: {e}", file=sys.stderr)
        return jsonify({"error": f"Error interno del servidor: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)