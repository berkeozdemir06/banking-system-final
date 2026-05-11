import requests, base64

client_id = "917b1aeb-5b01-437e-b5af-c2866c1b09dc"
client_secret = "2aefda15-da34-4fdb-9a58-fc9904d51ba6"
url = "https://apigwdev.mkk.com.tr/api/vyk/lastDisclosureIndex"

# Basic auth base64
auth_str = f"{client_id}:{client_secret}".encode()
b64_auth = base64.b64encode(auth_str).decode()

headers = {
    "Authorization": f"Basic {b64_auth}",
    "Accept": "application/json"
}

r = requests.get(url, headers=headers, verify=False)
print("Auth test:", r.status_code)
if r.status_code == 200:
    print(r.json())
