import unittest
from unittest.mock import patch, MagicMock
from utils.ai_assistant import get_ai_response

class TestAIAssistant(unittest.TestCase):

    @patch('utils.ai_assistant.genai')
    def test_get_ai_response_success(self, mock_genai):
        # Setup mock
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "This is a mock response from Jules."
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        # Inputs
        query = "How is my portfolio?"
        context = {"portfolio_summary": [{"Ticker": "AAPL", "Price": 150}]}
        api_key = "fake_key"

        # Execute
        response = get_ai_response(query, context, api_key)

        # Assertions
        self.assertEqual(response, "This is a mock response from Jules.")
        mock_genai.configure.assert_called_with(api_key="fake_key")
        mock_model.generate_content.assert_called_once()

        # Check that context is in the prompt
        args, _ = mock_model.generate_content.call_args
        prompt = args[0]
        self.assertIn("AAPL", prompt)
        self.assertIn("150", prompt)

    def test_get_ai_response_no_key(self):
        response = get_ai_response("Hello", {}, None)
        self.assertIn("need a valid Gemini API Key", response)

    @patch('utils.ai_assistant.genai')
    def test_get_ai_response_error(self, mock_genai):
        # Simulate an exception
        mock_genai.configure.side_effect = Exception("API Error")

        response = get_ai_response("Hello", {}, "key")
        self.assertIn("Error communicating with Jules AI", response)

if __name__ == '__main__':
    unittest.main()
