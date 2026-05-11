import requests
from bs4 import BeautifulSoup

url = "https://finans.mynet.com/borsa/hisseler/samat-saray-matbaacilik/kap-haberleri/"
headers = {"User-Agent": "Mozilla/5.0"}
r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, "html.parser")

# Mynet KAP news are usually in a list
items = soup.find_all("li", class_="flex-column")
for item in items[:5]:
    date = item.find("span", class_="date")
    title = item.find("h3")
    if date and title:
        print(f"[{date.text.strip()}] {title.text.strip()}")
