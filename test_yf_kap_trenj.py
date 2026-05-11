import yfinance as yf

ticker = yf.Ticker("TRENJ.IS")
news = ticker.news
for n in news[:5]:
    print(f"[{n.get('providerPublishTime')}] {n.get('title')}")
