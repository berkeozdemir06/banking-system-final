import requests
url = "https://www.kap.org.tr/tr/api/disclosures"
# Try a mock post or get
try:
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
    print(resp.status_code)
except Exception as e:
    print(e)
