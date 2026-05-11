import requests
from bs4 import BeautifulSoup

ticker = "ASELS"
url = f"https://duckduckgo.com/html/?q=site:kap.org.tr+{ticker}"
headers = {"User-Agent": "Mozilla/5.0"}
r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, "html.parser")

results = soup.find_all("div", class_="result")
for res in results[:5]:
    title = res.find("a", class_="result__a")
    snippet = res.find("a", class_="result__snippet")
    if title:
        print(f"Title: {title.text.strip()}")
        print(f"Url: {title['href']}")
