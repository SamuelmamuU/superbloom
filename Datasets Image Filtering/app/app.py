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
# 2️⃣ FUNCIONES AUXILIARES
# ===========================================

def get_info_safe(ee_object, default_value=None):
    """Función segura para obtener valores de GEE, manejando posibles errores."""
    try:
        return ee_object.getInfo()
    except ee.EEException as e:
        print(f"Error al obtener datos de GEE: {e}", file=sys.stderr)
        return default_value

def interpretar_cambio_ndvi(valor):
    """Interpreta el cambio en el valor de NDVI."""
    if valor is None:
        return "No se pudo calcular."
    if valor > 0.1:
        return "Mejora significativa de la vegetación."
    if valor > 0.02:
        return "Ligera mejora de la vegetación."
    if valor < -0.1:
        return "Degradación significativa de la vegetación."
    if valor < -0.02:
        return "Ligera degradación de la vegetación."
    return "Cambio insignificante."

# ===========================================
# 3️⃣ FUNCIÓN PRINCIPAL DE ANÁLISIS
# ===========================================

def analizar_ecosistema(coords_rectangulo, historic_start, historic_end, current_start, current_end):
    """
    Analiza el NDVI de una región en dos períodos y devuelve los datos para el mapa y el dashboard.
    """
    # --- Parámetros y Región de Interés ---
    region = ee.Geometry.Rectangle(coords_rectangulo)
    # Calcula el centro para la vista del mapa en el frontend
    centroides = region.centroid().coordinates().getInfo()
    centro_mapa = [centroides[1], centroides[0]] # Lat, Lon

    # --- Cargar colección Sentinel-2 y añadir NDVI ---
    def add_ndvi(img):
        # Enmascara nubes y sombras usando la banda SCL (Scene Classification Layer)
        scl = img.select('SCL')
        # Píxeles a mantener: vegetación, suelo desnudo, agua, nieve
        good_quality = scl.eq(4).Or(scl.eq(5)).Or(scl.eq(6)).Or(scl.eq(11))
        
        ndvi = img.normalizedDifference(['B8', 'B4']).rename('NDVI')
        return img.addBands(ndvi).updateMask(good_quality)

    s2_collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
        .filterBounds(region)

    s2_ndvi = s2_collection.map(add_ndvi)

    # --- Calcular NDVI histórico, actual y la diferencia ---
    ndvi_historic = s2_ndvi.filterDate(historic_start, historic_end).select('NDVI').median().clip(region)
    ndvi_current = s2_ndvi.filterDate(current_start, current_end).select('NDVI').median().clip(region)
    ndvi_diff = ndvi_current.subtract(ndvi_historic).rename('NDVI_diff')

    # --- Obtener valores promedio para el Dashboard ---
    reducer = ee.Reducer.mean()
    scale = 100 # Escala en metros para el cálculo

    mean_historic = get_info_safe(ndvi_historic.reduceRegion(reducer, region, scale).get('NDVI'))
    mean_current = get_info_safe(ndvi_current.reduceRegion(reducer, region, scale).get('NDVI'))
    mean_diff = get_info_safe(ndvi_diff.reduceRegion(reducer, region, scale).get('NDVI_diff'))

    # --- Preparar URLs de las capas para el Mapa ---
    ndvi_palette = ['#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400', '#3E8601', '#207401', '#056201', '#004C00', '#023B01', '#012E01', '#011D01', '#011301']
    diff_palette = ['#d7191c', '#fdae61', '#ffffbf', '#abdda4', '#2b83ba'] # Rojo, Amarillo, Verde, Azul

    map_historic = ndvi_historic.getMapId({'min': 0, 'max': 1, 'palette': ndvi_palette})
    map_current = ndvi_current.getMapId({'min': 0, 'max': 1, 'palette': ndvi_palette})
    map_diff = ndvi_diff.getMapId({'min': -0.5, 'max': 0.5, 'palette': diff_palette})

    # --- Estructurar la salida en un diccionario ---
    output = {
        "dashboard_data": {
            "ndvi_historico": mean_historic,
            "ndvi_actual": mean_current,
            "cambio_ndvi": mean_diff,
            "interpretacion": interpretar_cambio_ndvi(mean_diff)
        },
        "map_data": {
            "centro": centro_mapa,
            "tile_urls": {
                "historico": map_historic['tile_fetcher'].url_format,
                "actual": map_current['tile_fetcher'].url_format,
                "diferencia": map_diff['tile_fetcher'].url_format
            }
        }
    }
    return output

# ===========================================
# 4️⃣ CONFIGURACIÓN DEL SERVIDOR FLASK
# ===========================================
app = Flask(__name__)

# Esta ruta principal servirá el archivo HTML del frontend.
# La crearemos en el siguiente paso.
@app.route('/')
def home():
    return render_template('index.html')

# Esta es la ruta API que el frontend llamará para obtener los datos.
@app.route('/analizar-ecosistema', methods=['POST'])
def analizar_ecosistema_endpoint():
    try:
        data = request.get_json()
        
        # Validación de parámetros de entrada
        required_keys = ['coords', 'historic_start', 'historic_end', 'current_start', 'current_end']
        if not all(key in data for key in required_keys):
            return jsonify({"error": "Faltan parámetros en la solicitud."}), 400

        print(f"Iniciando análisis para la región: {data['coords']}")
        
        resultados = analizar_ecosistema(
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