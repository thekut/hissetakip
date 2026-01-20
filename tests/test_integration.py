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

    def test_3_batch_price_fetch_optimization(self):
        """Verify batch price fetching works with multiple tickers (testing vectorized optimization)."""
        tickers = ["AAPL", "MSFT", "GOOG", "AMZN"]
        prices = get_current_price_batch(tickers)

        self.assertEqual(len(prices), len(tickers), "Should return results for all tickers")

        for ticker in tickers:
            self.assertIn(ticker, prices)
            self.assertIn("price", prices[ticker])
            self.assertIn("change_pct", prices[ticker])
            # Prices should be positive numbers (unless data is totally missing/market crashed to 0)
            # We assume major tech stocks are > 0
            self.assertGreater(prices[ticker]['price'], 0, f"Price for {ticker} should be > 0")

        # Test with an invalid ticker mixed in
        mixed_tickers = ["AAPL", "INVALID_TICKER_XYZ"]
        mixed_prices = get_current_price_batch(mixed_tickers)

        self.assertIn("AAPL", mixed_prices)
        self.assertGreater(mixed_prices["AAPL"]['price'], 0)

        self.assertIn("INVALID_TICKER_XYZ", mixed_prices)
        # Should be 0.0 or NaN for invalid (depending on yfinance return behavior)
        # Original implementation returned NaN because yfinance returns NaNs for failed tickers in the dataframe.
        price = mixed_prices["INVALID_TICKER_XYZ"]['price']
        self.assertTrue(pd.isna(price) or price == 0.0, f"Price should be NaN or 0.0, got {price}")

if __name__ == '__main__':
    unittest.main()
