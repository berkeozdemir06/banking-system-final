import requests
import xml.etree.ElementTree as ET

ticker = "ASELS"
url = f"https://news.google.com/rss/search?q=site:kap.org.tr+{ticker}&hl=tr&gl=TR&ceid=TR:tr"
r = requests.get(url)
root = ET.fromstring(r.text)
items = root.findall(".//item")
for item in items[:5]:
    print(f"Title: {item.find('title').text}")
    print(f"Link: {item.find('link').text}")
