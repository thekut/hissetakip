import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator

def calculate_technicals(df_history):
    """
    Calculates technical indicators for a single stock's history dataframe.
    """
    if df_history.empty or len(df_history) < 14:
        return {}

    # Ensure Close is a Series
    close = df_history['Close']

    # RSI
    rsi_series = RSIIndicator(close=close, window=14).rsi()

    # SMA 50 and 200
    sma50_series = SMAIndicator(close=close, window=50).sma_indicator()
    sma200_series = SMAIndicator(close=close, window=200).sma_indicator()

    return {
        "RSI_series": rsi_series,
        "SMA50_series": sma50_series,
        "SMA200_series": sma200_series,
        "RSI": rsi_series.iloc[-1] if not rsi_series.empty else None,
        "SMA50": sma50_series.iloc[-1] if not sma50_series.empty else None,
        "SMA200": sma200_series.iloc[-1] if not sma200_series.empty else None,
    }

def analyze_stock(ticker, current_price, history_df, fundamentals):
    """
    Generates expert analysis and alerts for a stock.
    """
    alerts = []
    analysis_text = []
    technicals = calculate_technicals(history_df)

    # 1. ATH/ATL Analysis
    high_52 = fundamentals.get("fiftyTwoWeekHigh") or history_df['High'].max()
    low_52 = fundamentals.get("fiftyTwoWeekLow") or history_df['Low'].min()

    dist_to_ath_pct = 0.0
    if high_52 and high_52 > 0:
        dist_to_ath_pct = ((high_52 - current_price) / high_52) * 100

        if dist_to_ath_pct < 2.0:
            alerts.append("🚨 Near All-Time High (ATH)")
            analysis_text.append(f"Price is very close ({dist_to_ath_pct:.1f}%) to 52-Week High. Watch for breakout or resistance.")
        elif dist_to_ath_pct < 5.0:
            analysis_text.append(f"Approaching 52-Week High ({dist_to_ath_pct:.1f}% away).")

    if low_52 and low_52 > 0:
        dist_to_atl_pct = ((current_price - low_52) / low_52) * 100
        if dist_to_atl_pct < 2.0:
            alerts.append("⚠️ Near 52-Week Low")
            analysis_text.append("Price is testing the 52-Week Low support.")

    # 2. Technical Analysis
    rsi = technicals.get("RSI")
    if rsi:
        if rsi > 70:
            analysis_text.append(f"RSI is Overbought ({rsi:.1f}). Potential pullback.")
        elif rsi < 30:
            analysis_text.append(f"RSI is Oversold ({rsi:.1f}). Potential bounce.")
        else:
            analysis_text.append(f"RSI is Neutral ({rsi:.1f}).")

    sma50 = technicals.get("SMA50")
    sma200 = technicals.get("SMA200")

    if sma50 and sma200:
        if sma50 > sma200:
            analysis_text.append("Trend: Bullish (50 SMA > 200 SMA).")
        else:
            analysis_text.append("Trend: Bearish (50 SMA < 200 SMA).")

    if sma200 and current_price > sma200:
        analysis_text.append("Price is above 200-day moving average (Long-term Uptrend).")
    elif sma200:
        analysis_text.append("Price is below 200-day moving average (Long-term Downtrend).")

    # 3. Recommendation (Hybrid of Technicals + Analyst)
    analyst_rec = fundamentals.get("recommendationKey", "").upper().replace("_", " ")
    if analyst_rec:
        analysis_text.append(f"Analyst Consensus: {analyst_rec}.")

    summary = " ".join(analysis_text)

    return {
        "metrics": technicals,
        "alerts": alerts,
        "expert_comment": summary,
        "dist_to_ath": dist_to_ath_pct
    }
