import requests, base64

client_id = "97749ef1-a57d-41b5-a5f7-812d4a97ca6e"
client_secret = "e03f99af-4396-40f8-bb98-78c4d03fb9a9"
b64_auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
headers = {"Authorization": f"Basic {b64_auth}", "Accept": "application/json"}

# Try Production URL with long timeout
prod_url = "https://apigw.mkk.com.tr/api/vyk"
print("Testing PROD with 30s timeout...")
try:
    r = requests.get(f"{prod_url}/lastDisclosureIndex", headers=headers, timeout=30, verify=False)
    print("Status:", r.status_code)
    if r.status_code == 200:
        print("Success!", r.json())
    else:
        print(r.text)
except Exception as e:
    print("Error:", e)
