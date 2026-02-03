import time
from utils.data_manager import fetch_fundamentals_safe, fetch_fundamentals_batch

TICKERS = ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN"]

def sequential_fetch(tickers):
    start = time.time()
    results = {}
    for t in tickers:
        results[t] = fetch_fundamentals_safe(t)
    end = time.time()
    return end - start

def batch_fetch(tickers):
    start = time.time()
    results = fetch_fundamentals_batch(tickers)
    end = time.time()
    return end - start

if __name__ == "__main__":
    print(f"Benchmarking with {len(TICKERS)} tickers: {TICKERS}")

    print("Running sequential fetch...")
    seq_time = sequential_fetch(TICKERS)
    print(f"Sequential time: {seq_time:.2f}s")

    print("Running batch fetch (new implementation)...")
    batch_time = batch_fetch(TICKERS)
    print(f"Batch time: {batch_time:.2f}s")

    improvement = seq_time / batch_time if batch_time > 0 else 0
    print(f"Speedup: {improvement:.2f}x")
