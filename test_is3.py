import requests
from bs4 import BeautifulSoup
url = "https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse=ASELS"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
soup = BeautifulSoup(resp.text, 'html.parser')
for h in soup.find_all(text=lambda x: x and "KAP" in x):
    print(h.parent.text[:100])
