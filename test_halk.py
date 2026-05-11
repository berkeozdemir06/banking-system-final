import requests
from bs4 import BeautifulSoup

url = "https://www.halkyatirim.com.tr/kap-haberleri"
headers = {"User-Agent": "Mozilla/5.0"}
r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, "html.parser")

# Look for table rows
rows = soup.find_all("tr")
for row in rows[:10]:
    cols = row.find_all("td")
    if len(cols) >= 3:
        print(f"Date: {cols[0].text.strip()} | Ticker: {cols[1].text.strip()} | Title: {cols[2].text.strip()}")
