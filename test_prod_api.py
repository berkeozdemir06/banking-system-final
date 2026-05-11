import requests, base64

client_id = "917b1aeb-5b01-437e-b5af-c2866c1b09dc"
client_secret = "2aefda15-da34-4fdb-9a58-fc9904d51ba6"
b64_auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
headers = {"Authorization": f"Basic {b64_auth}", "Accept": "application/json"}

# Try Production URL
prod_url = "https://apigw.mkk.com.tr/api/vyk"
try:
    r = requests.get(f"{prod_url}/members", headers=headers, timeout=10)
    print("Status:", r.status_code)
    if r.status_code == 200:
        print("PROD ACCESS SUCCESSFUL!")
        print(r.json()[:2])
    else:
        print("PROD ACCESS FAILED:", r.text)
except Exception as e:
    print("PROD ACCESS ERROR:", e)
