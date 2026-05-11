import requests, base64

client_id = "917b1aeb-5b01-437e-b5af-c2866c1b09dc"
client_secret = "2aefda15-da34-4fdb-9a58-fc9904d51ba6"
b64_auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
headers = {"Authorization": f"Basic {b64_auth}", "Accept": "application/json"}

base_url = "https://apigwdev.mkk.com.tr/api/vyk"

# 1. Get companyId for THYAO
members_res = requests.get(f"{base_url}/members", headers=headers, verify=False)
company_id = next((m.get("id") for m in members_res.json() if m.get("stockCode") == "THYAO"), None)
print("CompanyId:", company_id)

# 2. Get last index
res_idx = requests.get(f"{base_url}/lastDisclosureIndex", headers=headers, verify=False)
last_idx = int(res_idx.json().get("lastDisclosureIndex", 0))

# 3. Get disclosures
start_idx = max(0, last_idx - 100000)
res_disc = requests.get(f"{base_url}/disclosures", headers=headers, params={"disclosureIndex": str(start_idx), "companyId": str(company_id)}, verify=False)

disclosures = res_disc.json()
data_list = disclosures if isinstance(disclosures, list) else disclosures.get("data", [])

if data_list:
    item = data_list[-1]
    d_idx = item.get("disclosureIndex")
    print("Fetching index:", d_idx)
    detail_res = requests.get(f"{base_url}/disclosureDetail/{d_idx}", headers=headers, params={"fileType": "html"}, verify=False)
    if detail_res.status_code == 200:
        detail = detail_res.json()
        html_msgs = detail.get("htmlMessages", [{}])
        content_str = html_msgs[0].get("tr", "") if html_msgs else ""
        print("Content starts with:", content_str[:100])
