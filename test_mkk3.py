import requests, base64

token = "mcp_410f8a3d53db4a3e9027ab409da4b26c"
url = "https://apigwdev.mkk.com.tr/api/vyk/lastDisclosureIndex"

headers_to_test = [
    {"Authorization": f"Basic {base64.b64encode(token.encode()).decode()}"},
    {"Authorization": f"Bearer {base64.b64encode(token.encode()).decode()}"},
    {"Authorization": base64.b64encode(token.encode()).decode()},
    {"Token": token},
    {"x-api-key": token},
    {"Authorization": f"Basic {base64.b64encode(f'berke özdemir:{token}'.encode()).decode()}"},
]

for i, h in enumerate(headers_to_test):
    r = requests.get(url, headers=h, verify=False)
    print(f"Test {i+1}: {r.status_code}")
