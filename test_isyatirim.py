import requests
import json

headers = {"User-Agent": "Mozilla/5.0"}
# Is Yatirim
url = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/SirketHaberleri"
params = {"hisse": "ASELS"}
r = requests.get(url, params=params, headers=headers, timeout=10)
print("IsYatirim:", r.status_code)
if r.status_code == 200:
    print(r.text[:200])

