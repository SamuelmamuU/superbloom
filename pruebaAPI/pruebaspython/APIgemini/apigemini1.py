import requests
import json
import re

API_KEY = "AIzaSyCp_k7LhNFNopatr20S_vdzYSTP0iVqCqI"
MODEL = "models/text-bison-001"  # modelo de texto válido
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/{MODEL}:generate?key={API_KEY}"


def obtener_coordenadas(ciudad):
    prompt = f"Dame las coordenadas (latitud y longitud) de {ciudad} en JSON con claves 'lat' y 'lon'. Solo responde el JSON."
    
    payload = {
        "prompt": {
            "text": prompt
        },
        "temperature": 0,
        "maxOutputTokens": 100
    }

    try:
        r = requests.post(GEMINI_URL, json=payload)
        r.raise_for_status()
        respuesta = r.json()
        text = respuesta['candidates'][0]['output']
        
        # Extraer JSON
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            coords = json.loads(match.group(0))
            return {"lat": float(coords["lat"]), "lon": float(coords["lon"])}
        else:
            return {"error": "No se pudo extraer JSON.", "respuesta": text}

    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    ciudad = input("Ingresa el nombre de la ciudad: ")
    resultado = obtener_coordenadas(ciudad)
    print("Resultado:", resultado)
