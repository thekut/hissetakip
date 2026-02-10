
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import pandas as pd
import asyncio
from utils.analysis import ask_gemini_analysis_async

class TestAsyncAnalysis(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.df = pd.DataFrame({"A": [1, 2, 3]})
        self.api_key = "dummy_key"

    @patch("utils.analysis.genai")
    async def test_ask_gemini_analysis_async_call(self, mock_genai):
        # Setup mock for async call
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model

        # Mock the async response
        mock_response = MagicMock()
        mock_response.text = "Mock Analysis Async"

        # Setup the async method on the mock
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)

        # Call the async function
        result = await ask_gemini_analysis_async(self.df, self.api_key)

        # Assertions
        mock_genai.configure.assert_called_with(api_key=self.api_key)
        mock_genai.GenerativeModel.assert_called_with('gemini-pro')
        mock_model.generate_content_async.assert_called_once()
        self.assertEqual(result, "Mock Analysis Async")

    @patch("utils.analysis.genai")
    async def test_ask_gemini_analysis_async_error(self, mock_genai):
        # Test error handling
        mock_genai.configure.side_effect = Exception("API Error")

        result = await ask_gemini_analysis_async(self.df, self.api_key)

        self.assertIn("❌ Gemini API Hatası", result)

if __name__ == '__main__':
    unittest.main()
