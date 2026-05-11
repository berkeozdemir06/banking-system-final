import requests, base64

client_id = "917b1aeb-5b01-437e-b5af-c2866c1b09dc"
client_secret = "2aefda15-da34-4fdb-9a58-fc9904d51ba6"
b64_auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
headers = {"Authorization": f"Basic {b64_auth}", "Accept": "application/json"}

urls = [
    "https://apiportal.mkk.com.tr/api/vyk",
    "https://apigw.mkk.com.tr/api/vyk",
    "https://api.mkk.com.tr/api/vyk"
]

for url in urls:
    try:
        r = requests.get(f"{url}/members", headers=headers, timeout=5)
        print(f"URL: {url} | Status: {r.status_code}")
        if r.status_code == 200:
            print("SUCCESS on", url)
    except Exception as e:
        print(f"URL: {url} | Error: {e}")
