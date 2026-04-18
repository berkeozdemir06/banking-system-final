from curl_cffi import requests
url = "https://www.kap.org.tr/tr/api/disclosures"
resp = requests.get(url, impersonate="chrome110")
print(resp.status_code)
