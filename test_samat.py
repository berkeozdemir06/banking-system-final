import requests, base64

client_id = "917b1aeb-5b01-437e-b5af-c2866c1b09dc"
client_secret = "2aefda15-da34-4fdb-9a58-fc9904d51ba6"
b64_auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
headers = {"Authorization": f"Basic {b64_auth}", "Accept": "application/json"}

base_url = "https://apigwdev.mkk.com.tr/api/vyk"

# 1. Get companyId for SAMAT
members_res = requests.get(f"{base_url}/members", headers=headers, verify=False)
m = next((m for m in members_res.json() if m.get("stockCode") == "SAMAT"), None)
print("Member:", m)

if m:
    cid = m.get("id")
    # 2. Get last index
    res_idx = requests.get(f"{base_url}/lastDisclosureIndex", headers=headers, verify=False)
    last_idx = int(res_idx.json().get("lastDisclosureIndex", 0))
    print("Last Index:", last_idx)

    # 3. Get disclosures for SAMAT
    # Try a very large range to see what they have
    r = requests.get(f"{base_url}/disclosures", headers=headers, params={"disclosureIndex": "0", "companyId": cid}, verify=False)
    print("Disclosures Count:", len(r.json()))
    if r.json():
        print("First 3 disclosures:", r.json()[:3])
        print("Last 3 disclosures:", r.json()[-3:])

