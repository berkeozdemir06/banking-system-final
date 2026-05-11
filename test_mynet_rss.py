import requests
import xml.etree.ElementTree as ET

url = "https://finans.mynet.com/rss/borsa/kap-haberleri/"
r = requests.get(url)
print(r.status_code)
if r.status_code == 200:
    root = ET.fromstring(r.text)
    items = root.findall(".//item")
    for item in items[:5]:
        print(f"Title: {item.find('title').text}")
