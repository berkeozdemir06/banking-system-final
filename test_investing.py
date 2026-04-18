import requests
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html"
}
url = "https://tr.investing.com/equities/aselsan-news"
resp = requests.get(url, headers=headers)
soup = BeautifulSoup(resp.text, 'html.parser')
for art in soup.select("article"):
    title = art.select_one("a.title") or art.select_one('[data-test="article-title"]')
    if title:
        print(title.text)
