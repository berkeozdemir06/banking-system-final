import requests, base64

token = "mcp_410f8a3d53db4a3e9027ab409da4b26c"
url = "https://apigwdev.mkk.com.tr/api/vyk/lastDisclosureIndex"

# 1. Bearer
r1 = requests.get(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}, verify=False)
print("1. Bearer:", r1.status_code)

# 2. Basic token
r2 = requests.get(url, headers={"Authorization": f"Basic {token}", "Accept": "application/json"}, verify=False)
print("2. Basic token:", r2.status_code)

# 3. Basic base64(token:)
b3 = base64.b64encode(f"{token}:".encode()).decode()
r3 = requests.get(url, headers={"Authorization": f"Basic {b3}", "Accept": "application/json"}, verify=False)
print("3. Basic base64(token:):", r3.status_code)

# 4. Token directly
r4 = requests.get(url, headers={"Authorization": token, "Accept": "application/json"}, verify=False)
print("4. Token directly:", r4.status_code)

