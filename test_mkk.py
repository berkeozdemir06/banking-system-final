import os, requests, base64
from dotenv import load_dotenv
load_dotenv()

key = os.getenv("KAP_API_KEY")
url = "https://apigwdev.mkk.com.tr/api/vyk/lastDisclosureIndex"

# Try 1: Basic base64(key:)
b1 = base64.b64encode(f"{key}:".encode()).decode()
r1 = requests.get(url, headers={"Authorization": f"Basic {b1}", "Accept": "application/json"}, verify=False)
print("1. Basic base64(key:)", r1.status_code)

# Try 2: Basic key
r2 = requests.get(url, headers={"Authorization": f"Basic {key}", "Accept": "application/json"}, verify=False)
print("2. Basic key", r2.status_code)

# Try 3: Bearer key
r3 = requests.get(url, headers={"Authorization": f"Bearer {key}", "Accept": "application/json"}, verify=False)
print("3. Bearer key", r3.status_code)

# Try 4: Base64 key
b4 = base64.b64encode(key.encode()).decode()
r4 = requests.get(url, headers={"Authorization": f"Basic {b4}", "Accept": "application/json"}, verify=False)
print("4. Basic base64(key)", r4.status_code)

