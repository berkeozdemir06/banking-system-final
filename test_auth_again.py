import requests, base64

client_id = "97749ef1-a57d-41b5-a5f7-812d4a97ca6e"
client_secret = "e03f99af-4396-40f8-bb98-78c4d03fb9a9"
b64_auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
headers = {"Authorization": f"Basic {b64_auth}", "Accept": "application/json"}

base_url = "https://apigwdev.mkk.com.tr/api/vyk"

# 1. Generate Token (Nasıl Kullanılır says it's required for Prod, let's see if it works on Dev)
token_url = "https://apigwdev.mkk.com.tr/auth/generateToken"
try:
    r_token = requests.get(token_url, params={"apiKey": client_id}, verify=False)
    print("Token Status:", r_token.status_code)
    if r_token.status_code == 200:
        token_data = r_token.json()
        token = token_data.get("token")
        print("Token obtained!")
        # Use Bearer token instead of Basic?
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
except Exception as e:
    print("Token Error:", e)

# 2. Check last index
res_idx = requests.get(f"{base_url}/lastDisclosureIndex", headers=headers, verify=False)
print("Last Index Status:", res_idx.status_code)
if res_idx.status_code == 200:
    last_idx = res_idx.json().get("lastDisclosureIndex")
    print("Last Index:", last_idx)
    # Check detail
    r = requests.get(f"{base_url}/disclosureDetail/{last_idx}", headers=headers, params={"fileType": "html"}, verify=False)
    if r.status_code == 200:
        print("Time for last index:", r.json().get("time"))
