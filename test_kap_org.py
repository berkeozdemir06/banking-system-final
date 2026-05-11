import requests

url = "https://www.kap.org.tr/tr/api/memberDisclosureQuery"
payload = {
    "fromDate": "2023-01-01",
    "toDate": "2026-05-11",
    "memberOid": "4028328c3118ab5d013118ac064c0001", # I need to find ASELS oid, or use stock code
    "stock": "ASELS",
    "disclosureClass": "FR"
}

# Let's try simpler API first, is there a search API?
search_url = "https://www.kap.org.tr/tr/api/disclosures"
# Kap's actual endpoint for "Son Bildirimler"
r = requests.get("https://www.kap.org.tr/tr/api/disclosures")
print(r.status_code)
if r.status_code == 200:
    print(len(r.json()))
