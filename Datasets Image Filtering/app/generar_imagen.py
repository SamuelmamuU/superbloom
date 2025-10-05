import sys
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

def generar_imagen(fecha, tipo):
    # Convertir fecha a objeto datetime
    fecha_obj = datetime.strptime(fecha, '%Y-%m-%d')
    
    # Crear figura
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Configurar según el tipo
    if tipo == 'lineal':
        ax.plot([fecha_obj], [5], 'ro-')
        ax.set_title('Gráfico Lineal')
    elif tipo == 'barras':
        ax.bar([fecha_obj], [5], color='green')
        ax.set_title('Gráfico de Barras')
    elif tipo == 'dispersion':
        ax.scatter([fecha_obj], [5], color='purple')
        ax.set_title('Gráfico de Dispersión')
    else:
        ax.text(0.5, 0.5, 'Tipo no válido', ha='center', va='center')
        ax.set_title('Error')
    
    # Formatear fecha en eje X
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    fig.autofmt_xdate()
    
    # Guardar imagen
    plt.savefig('imagen_generada.png')
    plt.close()

if __name__ == '__main__':
    if len(sys.argv) == 3:
        generar_imagen(sys.argv[1], sys.argv[2])