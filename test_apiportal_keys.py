import requests, base64

client_id = "97749ef1-a57d-41b5-a5f7-812d4a97ca6e"
client_secret = "e03f99af-4396-40f8-bb98-78c4d03fb9a9"
b64_auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
headers = {"Authorization": f"Basic {b64_auth}", "Accept": "application/json"}

url = "https://apiportal.mkk.com.tr/api/vyk"
try:
    r = requests.get(f"{url}/lastDisclosureIndex", headers=headers, timeout=5, verify=False)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        print("Success on portal!")
        print(r.json())
    else:
        print(r.text)
except Exception as e:
    print(e)
