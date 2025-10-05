# ===========================================
# API Flask + Gemini + GEE NDVI + Bounding Box
# ===========================================

from flask import Flask, request, jsonify
import requests
import ee
import math

# Inicializar Earth Engine
ee.Initialize()

app = Flask(__name__)

# ===========================================
# Función para obtener coordenadas de Gemini
# ===========================================
def obtener_coordenadas(region_name):
    GEMINI_API_URL = "https://api.gemini.com/geocode"  # Cambiar por URL real
    params = {"q": region_name, "format": "json"}
    response = requests.get(GEMINI_API_URL, params=params)
    data = response.json()
    
    # Suponiendo que Gemini devuelve: {"lat": ..., "lon": ...}
    lat = data['lat']
    lon = data['lon']
    return lat, lon

# ===========================================
# Función para calcular un cuadrado alrededor del punto
# ===========================================
def calcular_cuadro(lat, lon, km=100):
    delta_lat = km / 111  # Aproximación en grados
    delta_lon = km / (111 * math.cos(math.radians(lat)))

    sw = [lon - delta_lon/2, lat - delta_lat/2]
    se = [lon + delta_lon/2, lat - delta_lat/2]
    ne = [lon + delta_lon/2, lat + delta_lat/2]
    nw = [lon - delta_lon/2, lat + delta_lat/2]

    return {"SW": sw, "SE": se, "NE": ne, "NW": nw}

# ===========================================
# Función para flujo NDVI
# ===========================================
def flujo_ndvi(cuadro):
    # Crear polígono
    geom = ee.Geometry.Polygon([
        [cuadro["SW"], cuadro["SE"], cuadro["NE"], cuadro["NW"], cuadro["SW"]]
    ])

    # Seleccionar colección MODIS NDVI
    collection = ee.ImageCollection("MODIS/006/MOD13A1") \
        .filterBounds(geom) \
        .filterDate('2025-01-01', '2025-12-31') \
        .select('NDVI')

    ndvi_image = collection.mean().clip(geom)

    stats = ndvi_image.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geom,
        scale=500
    ).getInfo()

    return stats

# ===========================================
# Ruta principal de la API
# ===========================================
@app.route('/ndvi', methods=['POST'])
def ndvi_api():
    data = request.get_json()
    region_name = data.get('region')

    if not region_name:
        return jsonify({"error": "Falta el nombre de la región"}), 400

    # Obtener coordenadas desde Gemini
    lat, lon = obtener_coordenadas(region_name)

    # Calcular bounding box de 100 km
    cuadro = calcular_cuadro(lat, lon)

    # Ejecutar flujo NDVI
    ndvi_stats = flujo_ndvi(cuadro)

    # Devolver JSON
    return jsonify({
        "region": region_name,
        "center_coordinates": {"lat": lat, "lon": lon},
        "bounding_box": cuadro,
        "ndvi": ndvi_stats
    })

# ===========================================
# Ejecutar API
# ===========================================
if __name__ == "__main__":
    app.run(debug=True)
