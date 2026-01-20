import json
import yfinance as yf
import pandas as pd
import os

DATA_FILE = "data/stocks.json"

def load_watchlist():
    """Loads the watchlist from the JSON file."""
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_watchlist(data):
    """Saves the watchlist to the JSON file."""
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def fetch_stock_history(tickers):
    """
    Fetches historical data for a list of tickers.
    Returns a DataFrame with MultiIndex (Ticker, Price Fields).
    """
    if not tickers:
        return pd.DataFrame()

    # Download 1 year of data for ATH/ATL calculation and charts
    data = yf.download(tickers, period="1y", group_by='ticker', auto_adjust=True, threads=True)
    return data

def fetch_fundamentals_safe(ticker):
    """
    Fetches fundamental data for a single ticker safely.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info
        return {
            "marketCap": info.get("marketCap"),
            "trailingPE": info.get("trailingPE"),
            "forwardPE": info.get("forwardPE"),
            "recommendationKey": info.get("recommendationKey"), # Analyst Consensus
            "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
            "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow"),
            "allTimeHigh": info.get("allTimeHigh"),
            "allTimeLow": info.get("allTimeLow"),
            "currentPrice": info.get("currentPrice") or info.get("regularMarketPrice") # Fallback
        }
    except Exception as e:
        print(f"Error fetching fundamentals for {ticker}: {e}")
        return {}

def get_current_price_batch(tickers):
    """
    Fast fetch of current price and daily change using download (last row).
    """
    # Fetch 5 days to ensure we get the latest trading day even over weekends/holidays
    data = yf.download(tickers, period="5d", group_by='ticker', auto_adjust=True, threads=True)

    results = {}
    for ticker in tickers:
        try:
            if isinstance(data.columns, pd.MultiIndex):
                df = data[ticker]
            else:
                df = data

            if df.empty:
                continue

            last_close = df['Close'].iloc[-1]
            prev_close = df['Close'].iloc[-2] if len(df) > 1 else last_close
            change_pct = ((last_close - prev_close) / prev_close) * 100

            results[ticker] = {
                "price": last_close,
                "change_pct": change_pct,
                # Estimate 52W High/Low from history if we use the larger dataset,
                # but for this specific function we just want price.
            }
        except Exception as e:
            print(f"Error parsing batch data for {ticker}: {e}")
            results[ticker] = {"price": 0.0, "change_pct": 0.0}

    return results
