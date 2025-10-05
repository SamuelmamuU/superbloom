import requests

# URL de tu API
url = "http://127.0.0.1:8000/coordenadas/"

# Ciudad que quieres consultar
data = {"ciudad": "Monterrey"}

# Hacer la petición POST
response = requests.post(url, json=data)

# Verificar que salió bien y mostrar JSON
if response.status_code == 200:
    print(response.json())
else:
    print("Error:", response.status_code, response.text)
