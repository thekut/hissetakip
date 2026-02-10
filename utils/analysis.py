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

    # Handle MultiIndex if necessary
    if isinstance(df_history, pd.DataFrame):
        try:
            close = df_history['Close']
            high = df_history['High']
            low = df_history['Low']
        except KeyError:
             return None
    else:
        return None

    # Fill missing values
    close = close.ffill()

    # --- INDICATORS ---
    
    # RSI (14)
    rsi_val = RSIIndicator(close=close, window=14).rsi().iloc[-1]

    # SMA (50, 200)
    sma50_series = SMAIndicator(close=close, window=50).sma_indicator()
    sma50 = sma50_series.iloc[-1]
    sma200_series = SMAIndicator(close=close, window=200).sma_indicator()
    sma200 = sma200_series.iloc[-1]

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
        reasons.append("RSI Aşırı Satım (<30) - Tepki Yükselişi Beklentisi")
    elif rsi_val > 70:
        score -= 2
        reasons.append("RSI Aşırı Alım (>70) - Düzeltme Riski")
    else:
        reasons.append(f"RSI Nötr ({rsi_val:.1f})")

    # SMA Trend Logic
    if not np.isnan(sma200):
        if current_price > sma200:
            score += 1
            reasons.append("Fiyat > SMA200 (Uzun Vadeli Yükseliş Trendi)")
        else:
            score -= 1
            reasons.append("Fiyat < SMA200 (Uzun Vadeli Düşüş Trendi)")

    # SMA Crossover
    if not np.isnan(sma50) and not np.isnan(sma200):
        if sma50 > sma200:
            score += 1
            reasons.append("Golden Cross (SMA50 > SMA200) - Güçlü Al Sinyali")
        elif sma50 < sma200:
            score -= 1
            reasons.append("Death Cross (SMA50 < SMA200) - Güçlü Sat Sinyali")

    # Bollinger Bands
    if current_price <= bb_low * 1.01:
        score += 1
        reasons.append("Bollinger Alt Bandına Yakın (Alım Fırsatı Olabilir)")
    elif current_price >= bb_high * 0.99:
        score -= 1
        reasons.append("Bollinger Üst Bandına Yakın (Direnç Bölgesi)")

    # MACD
    if macd_line > macd_signal:
        score += 1
        reasons.append("MACD Al Sinyali (Pozitif Kesişim)")
    else:
        score -= 1
        reasons.append("MACD Sat Sinyali (Negatif Kesişim)")

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
    if len(high) > 1:
        prev_high = high.iloc[-2]
        prev_low = low.iloc[-2]
        prev_close = close.iloc[-2]
        
        pivot = (prev_high + prev_low + prev_close) / 3
        r1 = (2 * pivot) - prev_low
        s1 = (2 * pivot) - prev_high
    else:
        pivot = (high.iloc[-1] + low.iloc[-1] + close.iloc[-1]) / 3
        r1 = (2 * pivot) - low.iloc[-1]
        s1 = (2 * pivot) - high.iloc[-1]
        
    # --- STRATEGY PERFORMANCE (Backtest Simulation) ---
    # Simple Strategy: Buy if Price > SMA50, Sell if Price < SMA50
    try:
        df_strat = pd.DataFrame(index=close.index)
        df_strat['Price'] = close
        df_strat['SMA50'] = sma50_series
        df_strat['Signal'] = np.where(df_strat['Price'] > df_strat['SMA50'], 1, 0)
        df_strat['Returns'] = df_strat['Price'].pct_change()
        df_strat['Strat_Returns'] = df_strat['Signal'].shift(1) * df_strat['Returns']
        
        cum_strat_return = (1 + df_strat['Strat_Returns']).cumprod().iloc[-1] - 1
        cum_buy_hold = (1 + df_strat['Returns']).cumprod().iloc[-1] - 1
        
        strat_perf = {
            "Algo_Return": cum_strat_return * 100,
            "BuyHold_Return": cum_buy_hold * 100,
            "Algo_Name": "SMA 50 Trend Takipçisi"
        }
    except:
        strat_perf = {"Algo_Return": 0, "BuyHold_Return": 0, "Algo_Name": "Veri Yetersiz"}

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
        "Reasons": reasons,
        "Strategy": strat_perf
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

    # Basic Algo Comment
    algo_comment = "Veri yok."
    if tech.get("Strategy"):
        s = tech["Strategy"]
        diff = s["Algo_Return"] - s["BuyHold_Return"]
        algo_comment = f"{s['Algo_Name']} stratejisi son 1 yılda %{s['Algo_Return']:.1f} getiri sağladı. (Buy&Hold farkı: %{diff:+.1f})"

    return {
        "metrics": tech,
        "alerts": alerts,
        "dist_to_ath": dist_to_ath_pct,
        "reasons": tech["Reasons"],
        "expert_comment": " ".join(tech["Reasons"]),
        "algo_comment": algo_comment
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
