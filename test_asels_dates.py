import requests, base64

client_id = "917b1aeb-5b01-437e-b5af-c2866c1b09dc"
client_secret = "2aefda15-da34-4fdb-9a58-fc9904d51ba6"
b64_auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
headers = {"Authorization": f"Basic {b64_auth}", "Accept": "application/json"}

base_url = "https://apigwdev.mkk.com.tr/api/vyk"

# 1. Get companyId for ASELS
members_res = requests.get(f"{base_url}/members", headers=headers, verify=False)
cid = next((m.get("id") for m in members_res.json() if m.get("stockCode") == "ASELS"), None)

# 2. Get disclosures
res_disc = requests.get(f"{base_url}/disclosures", headers=headers, params={"disclosureIndex": "0", "companyId": str(cid)}, verify=False)
data_list = res_disc.json()
if not isinstance(data_list, list): data_list = data_list.get("data", [])

print("Total disclosures for ASELS in Dev:", len(data_list))
for item in data_list[-5:]:
    idx = item.get("disclosureIndex")
    d_res = requests.get(f"{base_url}/disclosureDetail/{idx}", headers=headers, params={"fileType": "html"}, verify=False)
    if d_res.status_code == 200:
        print(f"Index {idx}: {d_res.json().get('time')}")
