import requests

url = "https://www.isyatirim.com.tr/_Layouts/15/IsYatirim.Website/Common/Data.aspx/HaberGetir"
params = {"hisse": "ASELS", "sayfaNo": "1"}
headers = {
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json"
}

resp = requests.post(url, json=params, headers=headers)
print(resp.status_code)
print(resp.text[:200])

