import time
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator
from utils.analysis import analyze_stock

# Mock data generation
def generate_mock_data(n_rows=1000):
    dates = pd.date_range(start="2020-01-01", periods=n_rows, freq="D")
    df = pd.DataFrame(index=dates)
    df['Open'] = np.random.uniform(100, 200, n_rows)
    df['High'] = df['Open'] * 1.05
    df['Low'] = df['Open'] * 0.95
    df['Close'] = np.random.uniform(100, 200, n_rows)
    df['Volume'] = np.random.randint(1000, 100000, n_rows)
    return df

def old_redundant_calculations(ticker_hist):
    # This simulates the code that was removed from app.py
    sma_50_series = ticker_hist['Close'].rolling(window=50).mean()
    sma_200_series = ticker_hist['Close'].rolling(window=200).mean()

    delta = ticker_hist['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi_series = 100 - (100 / (1 + rs))
    return sma_50_series, sma_200_series, rsi_series

def run_benchmark():
    n_rows = 2000
    ticker_hist = generate_mock_data(n_rows)
    ticker = "MOCK"
    current_price = 150.0
    fund = {"fiftyTwoWeekHigh": 200, "fiftyTwoWeekLow": 100}

    iterations = 100

    # Measure Baseline (What it was before: analyze_stock + redundant calcs)
    # Note: analyze_stock is now slightly different (returns series), but the computation cost is identical
    # to before (it always computed series using 'ta'). The overhead of returning series is negligible.
    start_time_baseline = time.time()
    for _ in range(iterations):
        _ = analyze_stock(ticker, current_price, ticker_hist, fund)
        _ = old_redundant_calculations(ticker_hist)
    end_time_baseline = time.time()
    avg_time_baseline = (end_time_baseline - start_time_baseline) / iterations

    # Measure Optimized (What it is now: just analyze_stock)
    start_time_opt = time.time()
    for _ in range(iterations):
        _ = analyze_stock(ticker, current_price, ticker_hist, fund)
    end_time_opt = time.time()
    avg_time_opt = (end_time_opt - start_time_opt) / iterations

    print(f"Average execution time (Baseline): {avg_time_baseline*1000:.4f} ms")
    print(f"Average execution time (Optimized): {avg_time_opt*1000:.4f} ms")
    print(f"Improvement: {(avg_time_baseline - avg_time_opt)*1000:.4f} ms ({(avg_time_baseline - avg_time_opt)/avg_time_baseline*100:.1f}%)")

if __name__ == "__main__":
    run_benchmark()
