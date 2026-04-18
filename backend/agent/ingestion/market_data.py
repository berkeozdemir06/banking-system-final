import yfinance as yf
import pandas as pd
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MarketDataFetcher:
    """
    BIST hisse verilerini Yahoo Finance üzerinden çeker ve analiz eder.
    BIST 100 karşılaştırması ve getiri hesaplama işlerini yapar.
    """
    
    def __init__(self):
        self.index_ticker = "XU100.IS"

    def get_summary(self, ticker: str) -> dict:
        """
        Hisse için sayısal özet raporu oluşturur.
        """
        try:
            t_symbol = f"{ticker.upper()}.IS"
            logger.info(f"Fetching market data for {t_symbol}...")
            
            # Son 1 yıllık veriyi çek
            end_date = datetime.now()
            start_date = end_date - timedelta(days=380)
            
            # Hisse ve Endeks verilerini indir
            data = yf.download([t_symbol, self.index_ticker], start=start_date, end=end_date, interval="1d")
            
            if data.empty or t_symbol not in data["Close"]:
                logger.warning(f"No price data found for {ticker}")
                return {}

            price_data = data["Close"][t_symbol].dropna()
            volume_data = data["Volume"][t_symbol].dropna()
            index_data = data["Close"][self.index_ticker].dropna()

            last_price = float(price_data.iloc[-1])
            prev_price = float(price_data.iloc[-2]) if len(price_data) > 1 else last_price
            daily_change = ((last_price - prev_price) / prev_price) * 100

            # Getiriler (1H, 1A, 1Y)
            def calc_return(series, days):
                if len(series) < days: return 0.0
                start_val = series.iloc[-days]
                return ((series.iloc[-1] - start_val) / start_val) * 100

            # Trading günleri varsayımı: 1H=5, 1A=21, 1Y=252
            returns = {
                "1w": calc_return(price_data, 5),
                "1m": calc_return(price_data, 21),
                "1y": calc_return(price_data, 252)
            }

            # BIST 100 Karşılaştırması (Yılbaşından veya 1 Yıldan)
            index_return_1y = calc_return(index_data, 252)
            relative_performance = returns["1y"] - index_return_1y

            # 6 Aylık Hacim (Ortalama)
            avg_volume_6m = float(volume_data.iloc[-126:].mean()) if len(volume_data) > 126 else float(volume_data.mean())

            # İstikrar Analizi (Standart Sapma / Volatilite)
            daily_returns = price_data.pct_change().dropna()
            volatility = float(daily_returns.std() * (252**0.5)) * 100 # Annualized volatility
            
            stability_status = "YÜKSEK" if volatility < 25 else "ORTA" if volatility < 45 else "DÜŞÜK (Yüksek Volatilite)"

            return {
                "ticker": ticker.upper(),
                "last_price": round(last_price, 2),
                "daily_change": round(daily_change, 2),
                "returns": {k: round(v, 2) for k, v in returns.items()},
                "bist100_comparison_1y": round(relative_performance, 2),
                "avg_volume_6m": f"{avg_volume_6m:,.0f}",
                "volatility": round(volatility, 2),
                "stability": stability_status,
                "as_of": end_date.strftime("%Y-%m-%d %H:%M")
            }

        except Exception as e:
            logger.error(f"Market fetch error for {ticker}: {e}")
            return {}

    def get_price_after_event(self, ticker: str, event_date_str: str) -> dict:
        """
        Spesifik bir KAP tarihi sonrası piyasa tepkisini ölçer.
        """
        try:
            t_symbol = f"{ticker.upper()}.IS"
            event_date = datetime.strptime(event_date_str, "%Y-%m-%d")
            
            # O gün ve sonrasındaki 3 günü çek
            data = yf.download([t_symbol, self.index_ticker], 
                               start=event_date, 
                               end=event_date + timedelta(days=5), 
                               interval="1d")
            
            if data.empty: return {}
            
            prices = data["Close"]
            # İlk gün ve ertesi gün (borsa açıksa)
            p_day0 = prices[t_symbol].iloc[0]
            p_day1 = prices[t_symbol].iloc[1] if len(prices) > 1 else p_day0
            
            id_day0 = prices[self.index_ticker].iloc[0]
            id_day1 = prices[self.index_ticker].iloc[1] if len(prices) > 1 else id_day0
            
            stock_impact = ((p_day1 - p_day0) / p_day0) * 100
            index_impact = ((id_day1 - id_day0) / id_day0) * 100
            
            return {
                "stock_reaction": round(stock_impact, 2),
                "index_reaction": round(index_impact, 2),
                "relative_reaction": round(stock_impact - index_impact, 2)
            }
        except:
            return {}
