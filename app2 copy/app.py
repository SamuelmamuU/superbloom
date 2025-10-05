from flask import Flask, render_template, request, jsonify
from prueba12 import analizar_region
import sys

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
            return jsonify({"error":"Faltan parámetros."}), 400
        
        resultados = analizar_region(
            data['coords'],
            data['historic_start'], data['historic_end'],
            data['current_start'], data['current_end']
        )
        return jsonify(resultados)
    except Exception as e:
        print(f"Error en servidor: {e}", file=sys.stderr)
        return jsonify({"error": f"Error interno del servidor: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
