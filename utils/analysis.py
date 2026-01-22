import pandas as pd
import numpy as np
import google.generativeai as genai
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator, MACD
from ta.volatility import BollingerBands

def calculate_technicals(df_history):
    """
    Calculates technical indicators and generates signals for a stock's history.
    Returns a dictionary with metrics and signal/score.
    """
    if df_history is None or df_history.empty or len(df_history) < 20:
        return None

    # Handle MultiIndex if necessary (though usually passed as single level here)
    if isinstance(df_history, pd.DataFrame):
        try:
            close = df_history['Close']
            high = df_history['High']
            low = df_history['Low']
        except KeyError:
            # Fallback if somehow just a Series or different structure
             return None
    else:
        return None

    # Fill missing values
    close = close.ffill()

    # --- INDICATORS ---

    # RSI (14)
    rsi_val = RSIIndicator(close=close, window=14).rsi().iloc[-1]

    # SMA (50, 200)
    sma50 = SMAIndicator(close=close, window=50).sma_indicator().iloc[-1]
    sma200 = SMAIndicator(close=close, window=200).sma_indicator().iloc[-1]

    # Bollinger Bands (20, 2)
    bb = BollingerBands(close=close, window=20, window_dev=2)
    bb_high = bb.bollinger_hband().iloc[-1]
    bb_low = bb.bollinger_lband().iloc[-1]

    # MACD
    macd = MACD(close=close)
    macd_line = macd.macd().iloc[-1]
    macd_signal = macd.macd_signal().iloc[-1]

    current_price = close.iloc[-1]

    # --- SCORING & SIGNALS ---
    score = 0
    reasons = []

    # RSI Logic
    if rsi_val < 30:
        score += 2
        reasons.append("RSI Oversold (<30)")
    elif rsi_val > 70:
        score -= 2
        reasons.append("RSI Overbought (>70)")
    else:
        reasons.append(f"RSI Neutral ({rsi_val:.1f})")

    # SMA Trend Logic
    if not np.isnan(sma200):
        if current_price > sma200:
            score += 1
            reasons.append("Price > SMA200 (Long-term Bullish)")
        else:
            score -= 1
            reasons.append("Price < SMA200 (Long-term Bearish)")

    # SMA Crossover
    if not np.isnan(sma50) and not np.isnan(sma200):
        if sma50 > sma200:
            score += 1
            reasons.append("Golden Cross (SMA50 > SMA200)")
        elif sma50 < sma200:
            score -= 1
            reasons.append("Death Cross (SMA50 < SMA200)")

    # Bollinger Bands
    if current_price <= bb_low * 1.01:
        score += 1
        reasons.append("Near Lower Bollinger Band")
    elif current_price >= bb_high * 0.99:
        score -= 1
        reasons.append("Near Upper Bollinger Band")

    # MACD
    if macd_line > macd_signal:
        score += 1
        reasons.append("MACD Bullish Crossover")
    else:
        score -= 1
        reasons.append("MACD Bearish Crossover")

    # Signal Text
    if score >= 3:
        signal_txt = "GÜÇLÜ AL 🟢"
    elif score >= 1:
        signal_txt = "AL 🟢"
    elif score <= -3:
        signal_txt = "GÜÇLÜ SAT 🔴"
    elif score <= -1:
        signal_txt = "SAT 🔴"
    else:
        signal_txt = "NÖTR ⚪"

    # --- PIVOTS & LEVELS ---
    # Standard Pivot Points based on previous candle (Daily)
    # If we are strictly using daily data, iloc[-1] is today (incomplete) or yesterday?
    # Usually for pivots we use the PREVIOUS completed day.
    # Let's assume the passed dataframe includes the latest data.
    # If it's live data, -1 might be "current". -2 is "yesterday".
    # For safety/consistency, let's use the last available row for Pivot calculation
    # but strictly speaking it should be yesterday's High/Low/Close for Today's pivots.

    if len(high) > 1:
        prev_high = high.iloc[-2]
        prev_low = low.iloc[-2]
        prev_close = close.iloc[-2]

        pivot = (prev_high + prev_low + prev_close) / 3
        r1 = (2 * pivot) - prev_low
        s1 = (2 * pivot) - prev_high
    else:
        # Fallback to current if only 1 row (unlikely)
        pivot = (high.iloc[-1] + low.iloc[-1] + close.iloc[-1]) / 3
        r1 = (2 * pivot) - low.iloc[-1]
        s1 = (2 * pivot) - high.iloc[-1]

    return {
        "Fiyat": current_price,
        "RSI": rsi_val,
        "SMA50": sma50,
        "SMA200": sma200,
        "BB_High": bb_high,
        "BB_Low": bb_low,
        "MACD": macd_line,
        "MACD_Signal": macd_signal,
        "Pivot": pivot,
        "Destek 1": s1,
        "Direnç 1": r1,
        "Sinyal": signal_txt,
        "Score": score,
        "Reasons": reasons
    }

def analyze_stock(ticker, current_price, history_df, fundamentals):
    """
    Higher level analysis combining technicals and fundamentals/alerts.
    """
    tech = calculate_technicals(history_df)
    if not tech:
        return {}

    alerts = []

    # ATH Check
    high_52 = fundamentals.get("fiftyTwoWeekHigh") or history_df['High'].max()
    low_52 = fundamentals.get("fiftyTwoWeekLow") or history_df['Low'].min()

    dist_to_ath_pct = 0.0
    if high_52 and high_52 > 0:
        dist_to_ath_pct = ((high_52 - current_price) / high_52) * 100
        if dist_to_ath_pct < 2.5:
            alerts.append(f"🚨 ATH Alarm: Zirveye çok yakın (%{dist_to_ath_pct:.1f})")

    if low_52 and low_52 > 0:
        dist_to_atl_pct = ((current_price - low_52) / low_52) * 100
        if dist_to_atl_pct < 2.5:
            alerts.append(f"⚠️ ATL Alarm: Dibe çok yakın (%{dist_to_atl_pct:.1f})")

    return {
        "metrics": tech,
        "alerts": alerts,
        "dist_to_ath": dist_to_ath_pct,
        "reasons": tech["Reasons"],
        "expert_comment": " ".join(tech["Reasons"])
    }

def ask_gemini_analysis(df_summary, api_key):
    """
    Uses Google Gemini to analyze the portfolio summary dataframe.
    """
    if not api_key:
        return "⚠️ AI Analizi için API Anahtarı gerekli (Sol Menü)."

    try:
        genai.configure(api_key=api_key)

        prompt = f"""
        Bir borsa uzmanı olarak şu portföy tablosunu yorumla:
        {df_summary.to_string()}

        Lütfen şunları sağla:
        1. **Risk Analizi**: Hangi hisseler aşırı alımda (RSI > 70) veya dirençte?
        2. **Fırsatlar**: Hangi hisseler aşırı satımda (RSI < 30) veya momentum kazanıyor?
        3. **Sektör Görünümü**: Sektör dağılımına göre kısa tavsiye.
        4. **Aksiyon Özeti**: Kullanıcı için 3 net madde.

        Yanıtı Türkçe, profesyonel ve Markdown formatında ver.
        """

        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ Gemini API Hatası: {str(e)}"
