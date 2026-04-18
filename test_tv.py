import requests
import json
url = "https://news-headlines.tradingview.com/v2/headlines"
params = {
    "category": "tr",
    "client": "web",
    "lang": "tr",
    "symbol": "BIST:ASELS"
}
try:
    resp = requests.get(url, params=params)
    print(json.dumps(resp.json()[:2], indent=2))
except Exception as e:
    print(e)
