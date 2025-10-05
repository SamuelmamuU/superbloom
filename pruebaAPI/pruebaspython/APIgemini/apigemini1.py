import requests

# ================================
# Configuración de la API Gemini
# ================================
GEMINI_API_URL = "https://api.gemini.com/SuperBloom"  # Reemplaza con la URL real
API_KEY = "AIzaSyAP3C2oaWSOyfKkn4NoCmsOg0fyzN87McM"  # Si Gemini requiere autenticación

# ================================
# Función para obtener coordenadas
# ================================
def obtener_coordenadas(region_name):
    """
    Envía el nombre de la región a la API de Gemini
    y retorna coordenadas (centro o bounding box).
    """
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "region": region_name
    }

    try:
        response = requests.post(GEMINI_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Suponiendo que Gemini devuelve algo como:
        # { "center": {"lat": ..., "lon": ...}, "bbox": [min_lon, min_lat, max_lon, max_lat] }
        return data
    
    except requests.exceptions.RequestException as e:
        print("Error al conectar con Gemini:", e)
        return None

# ================================
# Interfaz simple de selección
# ================================
def seleccionar_region():
    regiones = ["Monterrey", "Guadalajara", "CDMX", "Cancún"]
    print("Seleccione una región:")
    for i, region in enumerate(regiones):
        print(f"{i+1}. {region}")
    
    opcion = int(input("Número de la región: "))
    if 1 <= opcion <= len(regiones):
        return regiones[opcion-1]
    else:
        print("Opción no válida.")
        return None

# ================================
# Programa principal
# ================================
if __name__ == "__main__":
    region_seleccionada = seleccionar_region()
    if region_seleccionada:
        coordenadas = obtener_coordenadas(region_seleccionada)
        if coordenadas:
            print(f"Coordenadas obtenidas para {region_seleccionada}:")
            print(coordenadas)
