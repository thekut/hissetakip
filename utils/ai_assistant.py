import google.generativeai as genai
import json

def get_ai_response(user_query, context, api_key):
    """
    Generates a response from the Gemini AI model.

    Args:
        user_query (str): The user's question.
        context (dict): Context data about the portfolio and market.
        api_key (str): The Google Gemini API key.

    Returns:
        str: The AI's response.
    """
    if not api_key:
        return "I need a valid Gemini API Key to answer that. Please set it in your environment variables or secrets."

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')

        # Construct the system prompt
        system_prompt = f"""
You are Jules, an AI Financial Assistant for a personal stock portfolio tracker.
Your goal is to provide helpful, accurate, and cautious financial insights based on the provided data.

CONTEXT DATA:
{json.dumps(context, indent=2, default=str)}

INSTRUCTIONS:
1. Answer the user's question using the provided context.
2. If the user asks about a specific stock, refer to the technical indicators and fundamental data in the context.
3. Be concise but informative.
4. Always include a standard disclaimer that this is not financial advice.
5. If the answer is not in the context, state that you don't have that information.
"""

        full_prompt = f"{system_prompt}\n\nUser Question: {user_query}"

        response = model.generate_content(full_prompt)
        return response.text

    except Exception as e:
        return f"Error communicating with Jules AI: {str(e)}"
