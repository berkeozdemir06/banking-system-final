import requests
from bs4 import BeautifulSoup
url = "https://finans.mynet.com/borsa/hisseler/asels-aselsan/"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
soup = BeautifulSoup(resp.text, 'html.parser')
for item in soup.select("ul.mb-6 li"):
    if "KAP" in item.text or True:
        a = item.select_one("a")
        if a: print(a.text.strip(), a.get("href"))
print("Done")
