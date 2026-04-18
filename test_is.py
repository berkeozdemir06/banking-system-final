import requests
import json
url = "https://www.isyatirim.com.tr/_Layouts/15/IsYatirim.Website/Common/Data.aspx/HaberGetir"
params = {"hisse": "ASELS", "sayfaNo": 1}
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest"
}
try:
    resp = requests.get(url, params=params, headers=headers)
    print(resp.json()["value"][:2])
except Exception as e:
    print("error:", e)
