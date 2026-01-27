import unittest
import os
import pandas as pd
from utils.data_manager import load_watchlist, fetch_stock_history, get_current_price_batch
from utils.analysis import analyze_stock

class TestStockAppIntegration(unittest.TestCase):

    def test_1_watchlist_integrity(self):
        """Verify watchlist JSON is readable and contains tickers."""
        watchlist = load_watchlist()
        self.assertTrue(len(watchlist) > 0, "Watchlist should not be empty")
        self.assertIn("AAPL", watchlist)
        self.assertIn("name", watchlist["AAPL"])

    def test_2_data_fetch_and_analysis_flow(self):
        """Simulate the app's data flow for a single stock."""
        ticker = "AAPL"

        # 1. Fetch Price Batch
        prices = get_current_price_batch([ticker])
        self.assertIn(ticker, prices)
        self.assertGreater(prices[ticker]['price'], 0, "Price should be > 0")

        # 2. Fetch History
        history = fetch_stock_history([ticker])
        # Handle multiindex or single index return
        if isinstance(history.columns, pd.MultiIndex):
            hist_df = history[ticker]
        else:
            hist_df = history

        self.assertFalse(hist_df.empty, "History dataframe should not be empty")
        self.assertIn('Close', hist_df.columns)

        # 3. Analyze
        # Mock fundamentals for speed
        fundamentals = {
            "fiftyTwoWeekHigh": 300.0,
            "fiftyTwoWeekLow": 150.0,
            "trailingPE": 30.0,
            "marketCap": 3000000000000
        }

        current_price = prices[ticker]['price']
        result = analyze_stock(ticker, current_price, hist_df, fundamentals)

        self.assertIn("metrics", result)
        self.assertIn("expert_comment", result)
        self.assertIn("RSI", result["metrics"])
        self.assertIn("RSI_series", result["metrics"])
        self.assertIsInstance(result["metrics"]["RSI_series"], pd.Series)
        self.assertIn("SMA50_series", result["metrics"])
        self.assertIsInstance(result["metrics"]["SMA50_series"], pd.Series)
        self.assertIn("SMA200_series", result["metrics"])
        self.assertIsInstance(result["metrics"]["SMA200_series"], pd.Series)

if __name__ == '__main__':
    unittest.main()
