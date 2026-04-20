import yfinance as yf
import pandas as pd
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MarketDataFetcher:
    def __init__(self):
        self.index_ticker = "XU100.IS"

    def get_summary(self, ticker: str) -> dict:
        """Safe fetch with long timeouts for Render stability."""
        try:
            t_symbol = f"{ticker.upper()}.IS"
            # Fetch minimal data to speed up, using a longer timeout for Render
            data = yf.download(
                [t_symbol, self.index_ticker], 
                period="1y", 
                interval="1d", 
                progress=False, 
                timeout=30,
                threads=True
            )
            
            if data.empty or t_symbol not in data["Close"] or data["Close"][t_symbol].dropna().empty:
                logger.warning(f"Yahoo Finance returned empty data for {t_symbol}")
                return {
                    "last_price": "N/A", "daily_change": 0, 
                    "returns": {"1w": 0, "1m": 0, "1y": 0},
                    "bist100_comparison_1y": 0, "avg_volume_6m": "0", "stability": "BİLİNMİYOR", "volatility": 0
                }

            price_data = data["Close"][t_symbol].dropna()
            volume_data = data["Volume"][t_symbol].dropna()
            index_data = data["Close"][self.index_ticker].dropna()

            last_price = float(price_data.iloc[-1])
            prev_price = float(price_data.iloc[-2]) if len(price_data) > 1 else last_price
            daily_change = ((last_price - prev_price) / prev_price) * 100

            def calc_ret(series, d):
                if len(series) < d: return 0.0
                v0 = series.iloc[-d]
                return ((series.iloc[-1] - v0) / v0) * 100

            returns = {"1w": calc_ret(price_data, 5), "1m": calc_ret(price_data, 21), "1y": calc_ret(price_data, 252)}
            idx_1y = calc_ret(index_data, 252)
            
            # Stability
            vol = float(price_data.pct_change().std() * (252**0.5)) * 100
            stab = "YÜKSEK" if vol < 25 else "ORTA" if vol < 45 else "DÜŞÜK"

            return {
                "last_price": round(last_price, 2),
                "daily_change": round(daily_change, 2),
                "returns": {k: round(v, 2) for k, v in returns.items()},
                "bist100_comparison_1y": round(returns["1y"] - idx_1y, 2),
                "avg_volume_6m": f"{float(volume_data.iloc[-126:].mean()):,.0f}" if len(volume_data) > 10 else "0",
                "volatility": round(vol, 2),
                "stability": stab
            }
        except Exception as e:
            logger.error(f"Market fetch crash: {e}")
            return {
                "last_price": "N/A", "daily_change": 0, 
                "returns": {"1w": 0, "1m": 0, "1y": 0},
                "bist100_comparison_1y": 0, "avg_volume_6m": "0", "stability": "BİLİNMİYOR", "volatility": 0
            }

    def get_price_after_event(self, ticker: str, date_str: str) -> dict:
        try:
            t_symbol = f"{ticker.upper()}.IS"
            d0 = datetime.strptime(date_str, "%Y-%m-%d")
            data = yf.download([t_symbol, self.index_ticker], start=d0, end=d0 + timedelta(days=7), progress=False, timeout=5)
            if len(data) < 2: return {}
            p = data["Close"]
            s_ret = ((p[t_symbol].iloc[1] - p[t_symbol].iloc[0]) / p[t_symbol].iloc[0]) * 100
            i_ret = ((p[self.index_ticker].iloc[1] - p[self.index_ticker].iloc[0]) / p[self.index_ticker].iloc[0]) * 100
            return {"stock_reaction": round(s_ret, 2), "index_reaction": round(i_ret, 2), "relative_reaction": round(s_ret - i_ret, 2)}
        except: return {}
