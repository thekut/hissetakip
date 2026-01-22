import json
import yfinance as yf
import pandas as pd
import os

DATA_FILE = "data/stocks.json"

# Master list for name resolution (Backup dictionary)
KNOWN_STOCKS = {
    "NVDA": "NVIDIA Corp.",
    "AAPL": "Apple Inc.",
    "GOOGL": "Alphabet Inc.",
    "AMZN": "Amazon.com Inc.",
    "MSFT": "Microsoft Corp.",
    "TSLA": "Tesla Inc.",
    "PLTR": "Palantir Technologies",
    "RKLB": "Rocket Lab USA",
    "SOFI": "SoFi Technologies",
    "RDDT": "Reddit Inc.",
    "JOBY": "Joby Aviation",
    "ACHR": "Archer Aviation",
    "OUST": "Ouster Inc.",
    "S": "SentinelOne",
    "IONQ": "IonQ Inc",
    "GEHC": "GE HealthCare",
    "OXY": "Occidental Petroleum",
    "RIO": "Rio Tinto",
    "CLF": "Cleveland-Cliffs",
    "QQQ": "Invesco QQQ",
    "SPY": "SPDR S&P 500",
    "SOXL": "Direxion Daily Semi Bull 3X",
    "TLT": "iShares 20+ Year Treasury",
    "EWZ": "iShares MSCI Brazil"
}

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
    Returns a DataFrame. If multiple tickers, it's a MultiIndex.
    """
    if not tickers:
        return pd.DataFrame()

    try:
        # group_by='ticker' ensures we usually get (Ticker, Price) structure
        data = yf.download(tickers, period="1y", group_by='ticker', auto_adjust=True, threads=True)
        return data
    except Exception as e:
        print(f"Error fetching history: {e}")
        return pd.DataFrame()

def fetch_fundamentals_safe(ticker):
    """
    Fetches fundamental data for a single ticker safely.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info
        return {
            "longName": info.get("longName") or info.get("shortName") or ticker,
            "marketCap": info.get("marketCap"),
            "trailingPE": info.get("trailingPE"),
            "forwardPE": info.get("forwardPE"),
            "recommendationKey": info.get("recommendationKey"), # Analyst Consensus
            "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
            "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow"),
            "currentPrice": info.get("currentPrice") or info.get("regularMarketPrice"),
            "sector": info.get("sector")
        }
    except Exception as e:
        print(f"Error fetching fundamentals for {ticker}: {e}")
        return {}

def get_current_price_batch(tickers):
    """
    Fast fetch of current price and daily change.
    Returns a dict: {ticker: {price, change_pct}}
    """
    if not tickers:
        return {}

    try:
        data = yf.download(tickers, period="5d", group_by='ticker', auto_adjust=True, threads=True)
    except Exception:
        return {}

    results = {}

    # Helper to extract DF for a ticker
    def get_ticker_df(d, t):
        # Case 1: MultiIndex columns with Ticker at top level
        if isinstance(d.columns, pd.MultiIndex):
            try:
                return d[t]
            except KeyError:
                # Might be single ticker result where yf didn't use MultiIndex properly
                if len(tickers) == 1 and t == tickers[0]:
                    return d
                return pd.DataFrame()
        # Case 2: Single Index (only Price columns) -> Assume it belongs to the single ticker requested
        elif len(tickers) == 1 and t == tickers[0]:
            return d
        return pd.DataFrame()

    for ticker in tickers:
        try:
            df = get_ticker_df(data, ticker)

            if df.empty or 'Close' not in df.columns:
                continue

            df_close = df['Close'].dropna()
            if len(df_close) < 1:
                continue

            last_close = df_close.iloc[-1]
            prev_close = df_close.iloc[-2] if len(df_close) > 1 else last_close
            change_pct = ((last_close - prev_close) / prev_close) * 100 if prev_close != 0 else 0

            results[ticker] = {
                "price": last_close,
                "change_pct": change_pct,
            }
        except Exception as e:
            print(f"Error parsing batch data for {ticker}: {e}")
            results[ticker] = {"price": 0.0, "change_pct": 0.0}

    return results

def resolve_ticker(query):
    """
    Resolves a query (Name or Ticker) to a Ticker Symbol using KNOWN_STOCKS.
    Returns the Ticker if resolved, else the query uppercased.
    """
    query = query.strip()
    q_upper = query.upper()

    # Check exact ticker
    if q_upper in KNOWN_STOCKS:
        return q_upper

    # Check name (partial match)
    # Prioritize exact start matches
    for k, v in KNOWN_STOCKS.items():
        if v.upper().startswith(q_upper):
            return k

    # Then loose containment
    for k, v in KNOWN_STOCKS.items():
        if q_upper in v.upper():
            return k

    return q_upper

def search_symbol_local(query, watchlist):
    """
    Searches for a stock in the local watchlist.
    """
    query = query.strip().upper()
    if query in watchlist:
        return query
    for ticker, data in watchlist.items():
        name = data.get('name', '').upper()
        if query in name:
            return ticker
    return None

def initialize_stock_entry(ticker, sector="Diğer", name=None):
    # Try to get name from KNOWN_STOCKS first
    if not name:
        if ticker in KNOWN_STOCKS:
            name = KNOWN_STOCKS[ticker]
        else:
            try:
                name = yf.Ticker(ticker).info.get('longName', ticker)
            except:
                name = ticker

    return {
        "name": name,
        "sector": sector,
        "transactions": []
    }
