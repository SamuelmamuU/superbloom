from flask import Flask, render_template, request, jsonify, send_file
import subprocess
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generar-imagen', methods=['POST'])
def generar_imagen():
    # Obtener datos del formulario
    fecha = request.form.get('fecha')
    tipo = request.form.get('tipo')
    
    # Validar datos
    if not fecha or not tipo:
        return jsonify({'error': 'Faltan datos'}), 400
    
    # Ejecutar script de Python
    try:
        subprocess.run(['python', 'generar_imagen.py', fecha, tipo], check=True)
        return send_file('imagen_generada.png', mimetype='image/png')
    except subprocess.CalledProcessError as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)