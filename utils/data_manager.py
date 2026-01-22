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

    # Vectorized implementation for MultiIndex (multiple tickers)
    # This avoids looping through tickers and creating Series for each, which is slow.
    vectorized_success = False
    if isinstance(data.columns, pd.MultiIndex) and not data.empty:
        try:
            if 'Close' in data.columns.get_level_values('Price'):
                close_df = data.xs('Close', level='Price', axis=1)

                if not close_df.empty:
                    last_closes = close_df.iloc[-1]
                    prev_closes = close_df.iloc[-2] if len(close_df) > 1 else last_closes

                    changes_pct = ((last_closes - prev_closes) / prev_closes) * 100

                    last_closes_dict = last_closes.to_dict()
                    changes_pct_dict = changes_pct.to_dict()

                    for ticker in tickers:
                        if ticker in last_closes_dict:
                            results[ticker] = {
                                "price": last_closes_dict[ticker],
                                "change_pct": changes_pct_dict[ticker]
                            }
                        else:
                            # Ticker requested but not in data (e.g. invalid ticker)
                            results[ticker] = {"price": 0.0, "change_pct": 0.0}
                    vectorized_success = True
        except Exception as e:
            print(f"Vectorized batch processing failed, falling back to loop: {e}")
            results = {}

    if vectorized_success:
        return results

    # Fallback to original loop implementation
    for ticker in tickers:
        try:
            if isinstance(data.columns, pd.MultiIndex):
                # Check if ticker exists in columns level 0 before accessing
                if ticker in data.columns.get_level_values(0):
                    df = data[ticker]
                else:
                    # Ticker not in data, raise KeyError to trigger exception handler
                    raise KeyError(f"Ticker {ticker} not found in data")
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
