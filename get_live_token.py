import requests

client_id = "97749ef1-a57d-41b5-a5f7-812d4a97ca6e"
host = "https://apiportal.mkk.com.tr"
url = f"{host}/auth/generateToken"
params = {"apiKey": client_id}

r = requests.get(url, params=params, timeout=10, verify=False)
print("Status:", r.status_code)
print("Body:", r.text)
