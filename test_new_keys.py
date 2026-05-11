import requests, base64

client_id = "97749ef1-a57d-41b5-a5f7-812d4a97ca6e"
client_secret = "e03f99af-4396-40f8-bb98-78c4d03fb9a9"
b64_auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
headers = {"Authorization": f"Basic {b64_auth}", "Accept": "application/json"}

urls = ["https://apigwdev.mkk.com.tr/api/vyk", "https://apigw.mkk.com.tr/api/vyk"]

for url in urls:
    try:
        r = requests.get(f"{url}/lastDisclosureIndex", headers=headers, timeout=5, verify=False)
        print(f"URL: {url} | Status: {r.status_code}")
        if r.status_code == 200:
            last_idx = r.json().get("lastDisclosureIndex")
            print(f"Last Index on {url}: {last_idx}")
            # Check date of last index
            detail = requests.get(f"{url}/disclosureDetail/{last_idx}", headers=headers, params={"fileType": "html"}, verify=False)
            if detail.status_code == 200:
                print(f"Time for last index: {detail.json().get('time')}")
    except Exception as e:
        print(f"URL: {url} | Error: {e}")
