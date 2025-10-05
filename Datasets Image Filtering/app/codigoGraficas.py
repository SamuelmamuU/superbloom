# -*- coding: utf-8 -*-
"""
Este script se encarga de obtener datos de series temporales de NDVI directamente desde
Google Earth Engine y generar las visualizaciones gráficas correspondientes.

El código para graficar LST y Precipitación se conserva pero está desactivado,
ya que la lógica para obtener esos datos no se encontró en los scripts de prueba.

Para que este script funcione, necesitas tener instaladas las siguientes librerías:
- earthengine-api: para interactuar con Google Earth Engine.
- matplotlib: para generar las gráficas.
- numpy: para realizar cálculos numéricos, como la regresión lineal.

Puedes instalarlas usando pip:
pip install earthengine-api matplotlib numpy
"""

import ee
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

# --- Configuración de Parámetros ---
# Coordenadas de ejemplo para la consulta.
LATITUD_EJEMPLO = 34.7
LONGITUD_EJEMPLO = -118.2

# --- Funciones de Interacción con Google Earth Engine ---

def obtener_serie_temporal_ndvi(lat, lon, anio_inicio=2020, anio_fin=2023):
    """
    Obtiene una serie temporal mensual de NDVI para una coordenada específica
    directamente desde Google Earth Engine.
    
    NOTA: Esta función solo obtiene NDVI. Los valores para LST y precipitación
    se devuelven como None.
    """
    print(f"Consultando datos de NDVI para lat={lat}, lon={lon}...")
    
    try:
        pt = ee.Geometry.Point([lon, lat])

        # Cargar colección Sentinel-2 y añadir NDVI
        def add_ndvi(img):
            scl = img.select('SCL')
            good_quality = scl.eq(4).Or(scl.eq(5)).Or(scl.eq(6)).Or(scl.eq(11))
            ndvi = img.normalizedDifference(['B8', 'B4']).rename('NDVI')
            return img.addBands(ndvi).updateMask(good_quality)

        s2_ndvi = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').map(add_ndvi)

        meses = ee.List.sequence(1, 12)
        anios = ee.List.sequence(anio_inicio, anio_fin)

        def generar_mediana_mensual(anio):
            def generar_mediana(mes):
                fecha_inicio = ee.Date.fromYMD(anio, mes, 1)
                mediana = s2_ndvi.filterDate(fecha_inicio, fecha_inicio.advance(1, 'month')).select('NDVI').median()
                return mediana.set('system:time_start', fecha_inicio.millis())
            return meses.map(generar_mediana)

        monthly_ndvi_collection = ee.ImageCollection.fromImages(anios.map(generar_mediana).flatten())

        def extraer_valor_ndvi(img):
            valor = img.reduceRegion(reducer=ee.Reducer.mean(), geometry=pt, scale=30).get('NDVI')
            return ee.Feature(None, {
                'date': ee.Date(img.get('system:time_start')).format('YYYY-MM-dd'),
                'ndvi': valor
            })

        feature_collection = monthly_ndvi_collection.map(extraer_valor_ndvi)
        
        info = feature_collection.getInfo()['features']
        
        # Limpiar datos y añadir campos nulos para LST y precipitación para mantener la estructura
        datos_limpios = []
        for f in info:
            props = f['properties']
            if props['ndvi'] is not None:
                props['lst'] = None
                props['precipitation'] = None
                datos_limpios.append(props)
        
        print("Datos de NDVI recibidos y procesados correctamente.")
        return {"timeseries": datos_limpios}

    except Exception as e:
        print(f"Error al procesar los datos con Earth Engine: {e}")
        return None

# --- Funciones de Generación de Gráficas ---

def graficar_serie_temporal_ndvi(datos_temporales):
    """
    Genera la gráfica de la serie temporal del NDVI.
    """
    if not datos_temporales or not datos_temporales.get('timeseries'):
        print("No hay datos para graficar.")
        return

    fechas = [datetime.strptime(item['date'], '%Y-%m-%d') for item in datos_temporales['timeseries']]
    valores_ndvi = [item['ndvi'] for item in datos_temporales['timeseries']]

    plt.figure(figsize=(12, 6))
    plt.plot(fechas, valores_ndvi, marker='o', linestyle='-', color='g')
    
    plt.title("Serie Temporal de Índices de Vegetación (NDVI)")
    plt.xlabel("Tiempo")
    plt.ylabel("Valor de NDVI")
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)
    plt.tight_layout()
    plt.show()

def graficar_factores_ambientales(datos_temporales):
    """
    Genera una gráfica comparativa de NDVI, LST y Precipitación.
    NOTA: Esta función no se ejecutará si faltan los datos de LST o precipitación.
    """
    if not datos_temporales or not datos_temporales.get('timeseries'):
        print("No hay datos para graficar.")
        return

    # Comprobar si los datos necesarios existen
    primer_dato = datos_temporales['timeseries'][0]
    if primer_dato['lst'] is None or primer_dato['precipitation'] is None:
        print("ADVERTENCIA: Faltan datos de LST o precipitación. No se puede generar la gráfica de factores ambientales.")
        return

    fechas = [datetime.strptime(item['date'], '%Y-%m-%d') for item in datos_temporales['timeseries']]
    valores_ndvi = [item['ndvi'] for item in datos_temporales['timeseries']]
    valores_lst = [item['lst'] for item in datos_temporales['timeseries']]
    valores_precip = [item['precipitation'] for item in datos_temporales['timeseries']]

    fig, ax1 = plt.subplots(figsize=(14, 7))

    ax1.set_xlabel('Tiempo')
    ax1.set_ylabel('NDVI', color='g')
    ax1.plot(fechas, valores_ndvi, 'g-', marker='o', label='NDVI')
    ax1.tick_params(axis='y', labelcolor='g')

    ax2 = ax1.twinx()
    ax2.set_ylabel('Temperatura (°C) y Precipitación (mm)', color='b')
    ax2.plot(fechas, valores_lst, 'r-', marker='s', alpha=0.7, label='Temperatura (LST)')
    ax2.plot(fechas, valores_precip, 'b-', marker='^', alpha=0.7, label='Precipitación')
    ax2.tick_params(axis='y', labelcolor='b')

    fig.tight_layout()
    plt.title('Análisis Comparativo de Factores Ambientales')
    fig.legend(loc="upper right", bbox_to_anchor=(1,1), bbox_transform=ax1.transAxes)
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)
    plt.show()

def graficar_ndvi_con_tendencia(datos_temporales):
    """
    Genera la gráfica de NDVI y superpone la línea de tendencia de regresión lineal.
    """
    if not datos_temporales or not datos_temporales.get('timeseries'):
        print("No hay datos para graficar.")
        return

    fechas = [datetime.strptime(item['date'], '%Y-%m-%d') for item in datos_temporales['timeseries']]
    valores_ndvi = [item['ndvi'] for item in datos_temporales['timeseries']]
    
    if len(fechas) < 2:
        print("Se necesitan al menos dos puntos de datos para calcular una tendencia.")
        return

    fechas_ord = [d.toordinal() for d in fechas]
    
    coeficientes = np.polyfit(fechas_ord, valores_ndvi, 1)
    polinomio = np.poly1d(coeficientes)
    tendencia = polinomio(fechas_ord)
    
    plt.figure(figsize=(12, 6))
    plt.plot(fechas, valores_ndvi, marker='o', linestyle='-', color='g', label='NDVI Real')
    plt.plot(fechas, tendencia, linestyle='--', color='r', linewidth=2, label='Línea de Tendencia')
    
    plt.title("Serie Temporal de NDVI con Línea de Tendencia")
    plt.xlabel("Tiempo")
    plt.ylabel("Valor de NDVI")
    plt.legend()
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)
    plt.tight_layout()
    plt.show()

# --- Bloque de Ejecución Principal ---

if __name__ == "__main__":
    # 1. Inicializar Google Earth Engine
    try:
        ee.Initialize(project='super-bloom')
        print("Google Earth Engine inicializado correctamente.")
    except Exception as e:
        print("Autenticando con Google Earth Engine...")
        ee.Authenticate()
        ee.Initialize(project='super-bloom')
        print("Autenticación completada e inicialización exitosa.")

    # 2. Obtener los datos directamente desde GEE
    datos_para_graficar = obtener_serie_temporal_ndvi(LATITUD_EJEMPLO, LONGITUD_EJEMPLO)
    
    if datos_para_graficar:
        # 3. Generar y mostrar todas las gráficas.
        # La gráfica de factores ambientales mostrará una advertencia y no se generará.
        
        print("\n--- Generando Gráfica 1: Serie Temporal de NDVI ---")
        graficar_serie_temporal_ndvi(datos_para_graficar)
        
        print("\n--- Intentando generar Gráfica 2: Factores Ambientales Comparativos ---")
        graficar_factores_ambientales(datos_para_graficar)
        
        print("\n--- Generando Gráfica 3: NDVI con Línea de Tendencia ---")
        graficar_ndvi_con_tendencia(datos_para_graficar)