import requests, base64

client_id = "917b1aeb-5b01-437e-b5af-c2866c1b09dc"
client_secret = "2aefda15-da34-4fdb-9a58-fc9904d51ba6"
b64_auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
headers = {"Authorization": f"Basic {b64_auth}", "Accept": "application/json"}

base_url = "https://apigwdev.mkk.com.tr/api/vyk"

d_idx = "1182600" # from my previous THYAO test
r = requests.get(f"{base_url}/disclosureDetail/{d_idx}", headers=headers, params={"fileType": "html"}, verify=False)
if r.status_code == 200:
    print("Time:", r.json().get("time"))
