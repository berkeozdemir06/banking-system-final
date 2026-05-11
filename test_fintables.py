import requests
from bs4 import BeautifulSoup

url = "https://fintables.com/kap"
headers = {"User-Agent": "Mozilla/5.0"}
r = requests.get(url, headers=headers)
print("Status:", r.status_code)
if r.status_code == 200:
    print(r.text[:500])
