# prueba12.py
import ee
import os
import json

# Inicializar GEE
try:
    ee.Initialize(project='super-bloom')
except Exception:
    ee.Authenticate()
    ee.Initialize(project='super-bloom')

MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN", "tu_mapbox_token_aqusk.eyJ1Ijoic2FtdW1hbXUiLCJhIjoiY21nY3pndHRsMHZjNzJsbzd3YmRnZ3k2aCJ9.IN5gKsMsEjaejKJEALxB_A")

# Funciones auxiliares (mask_s2_clouds, to_celsius, interpretar_cambio, interpretar_precipitacion, get_info_safe)
def mask_s2_clouds(img):
    scl = img.select('SCL')
    good_quality = scl.eq(4).Or(scl.eq(5)).Or(scl.eq(6)).Or(scl.eq(11))
    return img.updateMask(good_quality).divide(10000)

def to_celsius(img):
    lst = img.select('LST_Day_1km').multiply(0.02).subtract(273.15).rename('LST')
    return img.addBands(lst)

def get_info_safe(ee_object, default_value=None):
    try:
        return ee_object.getInfo()
    except ee.EEException:
        return default_value

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

# Función principal de análisis
def analizar_region(coords, historic_start, historic_end, current_start, current_end):
    region = ee.Geometry.Rectangle(coords)
    centro = [region.centroid().coordinates().get(1).getInfo(), region.centroid().coordinates().get(0).getInfo()]

    # Colecciones
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(region)
    s2_current = s2.filterDate(current_start, current_end).map(mask_s2_clouds)
    s2_historic = s2.filterDate(historic_start, historic_end).map(mask_s2_clouds)

    ndvi_current = s2_current.median().normalizedDifference(['B8','B4']).rename('NDVI')
    ndvi_historic = s2_historic.median().normalizedDifference(['B8','B4']).rename('NDVI')
    ndvi_diff = ndvi_current.subtract(ndvi_historic).rename('NDVI_diff')

    lst_collection = ee.ImageCollection('MODIS/061/MOD11A2').filterBounds(region).map(to_celsius)
    lst_current = lst_collection.filterDate(current_start, current_end).select('LST').mean().clip(region)
    lst_historic = lst_collection.filterDate(historic_start, historic_end).select('LST').mean().clip(region)
    lst_diff = lst_current.subtract(lst_historic).rename('LST_diff')

    gpm = ee.ImageCollection('NASA/GPM_L3/IMERG_V06').filterBounds(region)
    precip_current = gpm.filterDate(current_start, current_end).select('precipitationCal').sum().clip(region)
    precip_historic = gpm.filterDate(historic_start, historic_end).select('precipitationCal').sum().clip(region)
    precip_diff = precip_current.subtract(precip_historic).divide(precip_historic.add(1e-6)).rename('precip_diff_rel')

    # Reducir a valores numéricos
    scale = 100
    vals = {
        'ndvi_c': get_info_safe(ndvi_current.reduceRegion(ee.Reducer.mean(), region, scale).get('NDVI')),
        'ndvi_h': get_info_safe(ndvi_historic.reduceRegion(ee.Reducer.mean(), region, scale).get('NDVI')),
        'ndvi_d': get_info_safe(ndvi_diff.reduceRegion(ee.Reducer.mean(), region, scale).get('NDVI_diff')),
        'lst_c': get_info_safe(lst_current.reduceRegion(ee.Reducer.mean(), region, 1000).get('LST')),
        'lst_h': get_info_safe(lst_historic.reduceRegion(ee.Reducer.mean(), region, 1000).get('LST')),
        'lst_d': get_info_safe(lst_diff.reduceRegion(ee.Reducer.mean(), region, 1000).get('LST_diff')),
        'precip_c': get_info_safe(precip_current.reduceRegion(ee.Reducer.mean(), region, 1000).get('precipitationCal')),
        'precip_h': get_info_safe(precip_historic.reduceRegion(ee.Reducer.mean(), region, 1000).get('precipitationCal')),
        'precip_d': get_info_safe(precip_diff.reduceRegion(ee.Reducer.mean(), region, 1000).get('precip_diff_rel'))
    }

    # MapURLs para JS
    map_urls = {
        'ndvi': {
            'actual': ndvi_current.getMapId({'min':0,'max':0.8,'palette':['red','yellow','green']})['tile_fetcher'].url_format,
            'historico': ndvi_historic.getMapId({'min':0,'max':0.8,'palette':['red','yellow','green']})['tile_fetcher'].url_format,
            'diferencia': ndvi_diff.getMapId({'min':-0.3,'max':0.3,'palette':['red','white','green']})['tile_fetcher'].url_format
        },
        'temperatura': {
            'actual': lst_current.getMapId({'min':10,'max':45,'palette':['blue','cyan','yellow','red']})['tile_fetcher'].url_format,
            'historico': lst_historic.getMapId({'min':10,'max':45,'palette':['blue','cyan','yellow','red']})['tile_fetcher'].url_format,
            'diferencia': lst_diff.getMapId({'min':-5,'max':5,'palette':['blue','white','red']})['tile_fetcher'].url_format
        },
        'precipitacion': {
            'actual': precip_current.getMapId({'min':0,'max':50,'palette':['white','blue','purple']})['tile_fetcher'].url_format,
            'historico': precip_historic.getMapId({'min':0,'max':50,'palette':['white','blue','purple']})['tile_fetcher'].url_format,
            'diferencia': precip_diff.getMapId({'min':-1,'max':1,'palette':['red','white','blue']})['tile_fetcher'].url_format
        }
    }

    output = {
        "map_data": {"centro": centro, "tile_urls": map_urls},
        "dashboard_data": {
            "actual": {
                "ndvi": {"valor": vals['ndvi_c']},
                "temperatura": {"valor": vals['lst_c']},
                "precipitacion": {"valor": vals['precip_c'], "interpretacion": interpretar_precipitacion(vals['precip_c'])}
            },
            "comparativo": {
                "ndvi_historico": {"valor": vals['ndvi_h']},
                "cambio_ndvi": {"valor": vals['ndvi_d'], "interpretacion": interpretar_cambio(vals['ndvi_d'],0.1,0.02,'vegetación')},
                "temperatura_historica": {"valor": vals['lst_h']},
                "cambio_temperatura": {"valor": vals['lst_d'], "interpretacion": interpretar_cambio(vals['lst_d'],2,0.5,'temperatura')},
                "precipitacion_historica": {"valor": vals['precip_h']},
                "cambio_precipitacion_rel": {"valor": vals['precip_d'], "interpretacion": interpretar_cambio(vals['precip_d'],0.5,0.1,'precipitación')}
            }
        }
    }
    return output
