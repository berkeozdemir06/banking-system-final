import requests
from bs4 import BeautifulSoup
url = "https://html.duckduckgo.com/html/"
res = requests.post(url, data={'q': 'TRENJ yönetim değişikliği KAP'}, headers={"User-Agent": "Mozilla/5.0"})
soup = BeautifulSoup(res.text, 'html.parser')
for a in soup.select('.result__a')[:3]:
    print(a.text)
    print(a['href'])
