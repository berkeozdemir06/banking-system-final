import requests
from bs4 import BeautifulSoup

url = "https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse=SAMAT"
headers = {"User-Agent": "Mozilla/5.0"}
r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, "html.parser")

# The KAP news are usually in a table inside a div with id like "ctl00_ctl44_g_52702787_16e3_449f_8e70_2f6d28929e06"
# Or just look for any table with rows containing dates
rows = soup.find_all("tr")
found = 0
for row in rows:
    cols = row.find_all("td")
    if len(cols) >= 2:
        date_text = cols[0].text.strip()
        # check if it looks like a date dd.mm.yyyy
        if len(date_text) == 10 and date_text[2] == "." and date_text[5] == ".":
            print(f"[{date_text}] {cols[1].text.strip()}")
            found += 1
            if found >= 5: break
