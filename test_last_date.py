import requests, base64

client_id = "917b1aeb-5b01-437e-b5af-c2866c1b09dc"
client_secret = "2aefda15-da34-4fdb-9a58-fc9904d51ba6"
b64_auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
headers = {"Authorization": f"Basic {b64_auth}", "Accept": "application/json"}

base_url = "https://apigwdev.mkk.com.tr/api/vyk"

# Get last index
res_idx = requests.get(f"{base_url}/lastDisclosureIndex", headers=headers, verify=False)
last_idx = res_idx.json().get("lastDisclosureIndex")
print("Last Index:", last_idx)

# Get detail
r = requests.get(f"{base_url}/disclosureDetail/{last_idx}", headers=headers, params={"fileType": "html"}, verify=False)
if r.status_code == 200:
    print("Time for last index:", r.json().get("time"))
