import requests, base64

client_id = "917b1aeb-5b01-437e-b5af-c2866c1b09dc"
client_secret = "2aefda15-da34-4fdb-9a58-fc9904d51ba6"
url = "https://apigwdev.mkk.com.tr/api/vyk/lastDisclosureIndex"

# Basic auth base64
auth_str = f"{client_id}:{client_secret}".encode()
b64_auth = base64.b64encode(auth_str).decode()
headers = {"Authorization": f"Basic {b64_auth}", "Accept": "application/json"}

r = requests.get(url, headers=headers, verify=False)
last_idx = int(r.json().get("lastDisclosureIndex", 0))

start_idx = last_idx - 100
r2 = requests.get("https://apigwdev.mkk.com.tr/api/vyk/disclosures", headers=headers, params={"disclosureIndex": str(start_idx)}, verify=False)
disclosures = r2.json()
data_list = disclosures if isinstance(disclosures, list) else disclosures.get("data", [])
for item in data_list[:5]:
    print(item)
