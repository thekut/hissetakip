import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import json
import os
import google.generativeai as genai
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator, MACD
from ta.volatility import BollingerBands

# --- PAGE CONFIG ---
st.set_page_config(page_title="Finansal Hafıza Pro", layout="wide", page_icon="🏦")

# --- DATA MANAGEMENT MODULE (Embedded) ---
DATA_FILE = "data/stocks.json"

# Master list for name resolution
KNOWN_STOCKS = {
    "NVDA": "NVIDIA Corp.", "AAPL": "Apple Inc.", "GOOGL": "Alphabet Inc.",
    "AMZN": "Amazon.com Inc.", "MSFT": "Microsoft Corp.", "TSLA": "Tesla Inc.",
    "PLTR": "Palantir Technologies", "RKLB": "Rocket Lab USA", "SOFI": "SoFi Technologies",
    "RDDT": "Reddit Inc.", "JOBY": "Joby Aviation", "ACHR": "Archer Aviation",
    "OUST": "Ouster Inc.", "S": "SentinelOne", "IONQ": "IonQ Inc",
    "GEHC": "GE HealthCare", "OXY": "Occidental Petroleum", "RIO": "Rio Tinto",
    "CLF": "Cleveland-Cliffs", "QQQ": "Invesco QQQ", "SPY": "SPDR S&P 500",
    "SOXL": "Direxion Daily Semi Bull 3X", "TLT": "iShares 20+ Year Treasury",
    "EWZ": "iShares MSCI Brazil"
}

def load_watchlist():
    if not os.path.exists(DATA_FILE): return {}
    with open(DATA_FILE, "r") as f: return json.load(f)

def save_watchlist(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=4)

def resolve_ticker(query):
    query = query.strip()
    q_upper = query.upper()
    if q_upper in KNOWN_STOCKS: return q_upper
    for k, v in KNOWN_STOCKS.items():
        if v.upper().startswith(q_upper): return k
    for k, v in KNOWN_STOCKS.items():
        if q_upper in v.upper(): return k
    return q_upper

def initialize_stock_entry(ticker, sector="Diğer", name=None):
    if not name:
        if ticker in KNOWN_STOCKS: name = KNOWN_STOCKS[ticker]
        else:
            try: name = yf.Ticker(ticker).info.get('longName', ticker)
            except: name = ticker
    return {"name": name, "sector": sector, "transactions": []}

@st.cache_data(ttl=300, show_spinner=False)
def fetch_stock_history_cached(tickers):
    if not tickers: return pd.DataFrame()
    try:
        # threads=False improves stability on Streamlit Cloud
        data = yf.download(tickers, period="1y", group_by='ticker', auto_adjust=True, threads=False)
        return data
    except: return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_fundamentals_cached(ticker):
    try:
        t = yf.Ticker(ticker)
        info = t.info
        return {
            "longName": info.get("longName") or info.get("shortName") or ticker,
            "marketCap": info.get("marketCap"),
            "trailingPE": info.get("trailingPE"),
            "recommendationKey": info.get("recommendationKey"),
            "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
            "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow"),
            "currentPrice": info.get("currentPrice") or info.get("regularMarketPrice"),
            "sector": info.get("sector"),
            "beta": info.get("beta"),
            "dividendYield": info.get("dividendYield"),
            "profitMargins": info.get("profitMargins")
        }
    except: return {}

# --- ANALYSIS MODULE (Embedded) ---
def calculate_technicals(df_history):
    if df_history is None or df_history.empty or len(df_history) < 20: return None

    # Handle MultiIndex
    if isinstance(df_history, pd.DataFrame):
        try: close = df_history['Close']
        except KeyError: return None
    else: return None

    close = close.ffill()
    current_price = close.iloc[-1]

    # Indicators
    rsi_val = RSIIndicator(close=close, window=14).rsi().iloc[-1]
    sma50 = SMAIndicator(close=close, window=50).sma_indicator().iloc[-1]
    sma200 = SMAIndicator(close=close, window=200).sma_indicator().iloc[-1]
    bb = BollingerBands(close=close, window=20, window_dev=2)
    bb_high = bb.bollinger_hband().iloc[-1]
    bb_low = bb.bollinger_lband().iloc[-1]
    macd = MACD(close=close)
    macd_line = macd.macd().iloc[-1]
    macd_sig = macd.macd_signal().iloc[-1]

    # Scoring
    score = 0
    reasons = []

    if rsi_val < 30: score += 2; reasons.append("RSI Aşırı Satım (<30)")
    elif rsi_val > 70: score -= 2; reasons.append("RSI Aşırı Alım (>70)")
    else: reasons.append(f"RSI Nötr ({rsi_val:.1f})")

    if not np.isnan(sma200):
        if current_price > sma200: score += 1; reasons.append("Fiyat > SMA200 (Boğa Trendi)")
        else: score -= 1; reasons.append("Fiyat < SMA200 (Ayı Trendi)")

    if not np.isnan(sma50) and not np.isnan(sma200):
        if sma50 > sma200: score += 1; reasons.append("Golden Cross (SMA50 > SMA200)")
        elif sma50 < sma200: score -= 1; reasons.append("Death Cross (SMA50 < SMA200)")

    if current_price <= bb_low * 1.01: score += 1; reasons.append("Bollinger Alt Bant (Alım Bölgesi)")
    if macd_line > macd_sig: score += 1; reasons.append("MACD Al Sinyali")

    # Signal Text
    if score >= 3: signal_txt = "GÜÇLÜ AL 🟢"
    elif score >= 1: signal_txt = "AL 🟢"
    elif score <= -3: signal_txt = "GÜÇLÜ SAT 🔴"
    elif score <= -1: signal_txt = "SAT 🔴"
    else: signal_txt = "NÖTR ⚪"

    # Pivots
    high = df_history['High']
    low = df_history['Low']
    if len(high) > 1:
        p = (high.iloc[-2] + low.iloc[-2] + close.iloc[-2]) / 3
        r1 = (2 * p) - low.iloc[-2]
        s1 = (2 * p) - high.iloc[-2]
    else:
        p = current_price; r1=p; s1=p

    # Strategy Backtest (SMA50)
    try:
        df_s = pd.DataFrame({'Close': close})
        df_s['SMA50'] = SMAIndicator(close=close, window=50).sma_indicator()
        df_s['Sig'] = np.where(df_s['Close'] > df_s['SMA50'], 1, 0)
        df_s['Ret'] = df_s['Close'].pct_change()
        df_s['Strat'] = df_s['Sig'].shift(1) * df_s['Ret']
        algo_ret = ((1 + df_s['Strat']).cumprod().iloc[-1] - 1) * 100
        bh_ret = ((1 + df_s['Ret']).cumprod().iloc[-1] - 1) * 100
        algo_comment = f"SMA50 Stratejisi: %{algo_ret:.1f} getiri (B&H: %{bh_ret:.1f})"
    except: algo_comment = ""

    return {
        "Fiyat": current_price, "RSI": rsi_val, "SMA50": sma50, "SMA200": sma200,
        "Sinyal": signal_txt, "Score": score, "Reasons": reasons,
        "Pivot": p, "Destek 1": s1, "Direnç 1": r1, "algo_comment": algo_comment,
        "expert_comment": " ".join(reasons)
    }

def analyze_stock_full(ticker, current_price, history_df, fundamentals):
    tech = calculate_technicals(history_df)
    if not tech: return {}

    alerts = []
    h52 = fundamentals.get("fiftyTwoWeekHigh")
    l52 = fundamentals.get("fiftyTwoWeekLow")

    if h52:
        dist = ((h52 - current_price) / h52) * 100
        if dist < 2.5: alerts.append(f"🚨 ATH Alarmı: Zirveye çok yakın (%{dist:.1f})")

    if l52:
        dist = ((current_price - l52) / l52) * 100
        if dist < 2.5: alerts.append(f"⚠️ ATL Alarmı: Dibe çok yakın (%{dist:.1f})")

    return {"metrics": tech, "alerts": alerts}

def ask_gemini(df_summary, api_key):
    if not api_key: return "⚠️ API Anahtarı girilmedi."
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"Finans uzmanı olarak şu tabloyu yorumla:\n{df_summary.to_string()}\nRiskler, Fırsatlar ve Aksiyon önerisi ver. Türkçe."
        return model.generate_content(prompt).text
    except Exception as e: return f"Hata: {e}"

# --- APP LOGIC ---
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = load_watchlist()

def calculate_pl(transactions, current_price):
    total_qty = 0; total_cost = 0; realized_pl = 0
    for t in transactions:
        try:
            q = float(t['qty']); p = float(t['price'])
            if t['type'] == 'ALIS':
                total_cost += q * p; total_qty += q
            elif t['type'] == 'SATIS':
                if total_qty > 0:
                    avg = total_cost / total_qty
                    realized_pl += (p - avg) * q
                    total_cost -= avg * q
                    total_qty -= q
        except: continue
    avg_cost = (total_cost / total_qty) if total_qty > 0 else 0
    return total_qty, avg_cost, realized_pl, (total_qty * current_price) - total_cost

# Sidebar
st.sidebar.title("⚙️ Kontrol Paneli")
api_key = st.sidebar.text_input("Gemini API Key", type="password")
if api_key: st.session_state.api_key = api_key
elif 'api_key' not in st.session_state: st.session_state.api_key = ""

st.sidebar.markdown("---")
with st.sidebar.expander("➕ Hisse Ekle", expanded=True):
    add_q = st.text_input("Kod veya İsim").strip()
    add_s = st.selectbox("Sektör", ["Teknoloji", "Finans", "Enerji", "ETF", "Diğer"])
    if st.button("Ekle"):
        if add_q:
            tick = resolve_ticker(add_q)
            if tick not in st.session_state.portfolio:
                st.session_state.portfolio[tick] = initialize_stock_entry(tick, add_s)
                save_watchlist(st.session_state.portfolio)
                st.success(f"{tick} eklendi!")
                st.rerun()
            else: st.warning("Zaten listede.")

with st.sidebar.expander("🗑️ Hisse Çıkar"):
    rem_t = st.selectbox("Seç", [""] + sorted(list(st.session_state.portfolio.keys())))
    if st.button("Sil") and rem_t:
        del st.session_state.portfolio[rem_t]
        save_watchlist(st.session_state.portfolio)
        st.rerun()

# Main
st.title("📈 Finansal Hafıza AI")
tickers = list(st.session_state.portfolio.keys())
if not tickers: st.stop()

with st.spinner("Veriler güncelleniyor..."):
    hist_data = fetch_stock_history_cached(tickers)

summary = []
alerts = []

for t in tickers:
    try:
        # Data Extraction
        if isinstance(hist_data.columns, pd.MultiIndex):
            try: df = hist_data[t]
            except: continue
        else:
            if len(tickers) == 1: df = hist_data
            else: continue

        df = df.dropna(subset=['Close'])
        if df.empty: continue

        curr = df['Close'].iloc[-1]
        fund = fetch_fundamentals_cached(t)
        res = analyze_stock_full(t, curr, df, fund)
        tech = res.get("metrics", {})
        if not tech: continue

        if res.get('alerts'): alerts.extend([f"**{t}**: {a}" for a in res['alerts']])

        q, avg, r_pl, u_pl = calculate_pl(st.session_state.portfolio[t]['transactions'], curr)

        summary.append({
            "Kod": t, "Fiyat": curr, "Sinyal": tech['Sinyal'], "RSI": tech['RSI'],
            "Adet": q, "Ort.Maliyet": avg, "Kar(Açık)": u_pl, "Kar(Realize)": r_pl,
            "history": df, "fundamentals": fund, "full_analysis": res, "Score": tech['Score']
        })
    except: continue

if alerts:
    st.error("🔔 ALARMLAR: " + " | ".join(alerts))

if summary:
    df_sum = pd.DataFrame(summary)
    
    def color_row(row):
        return ['background-color: #d4edda' if 'AL' in row['Sinyal'] else 'background-color: #f8d7da' if 'SAT' in row['Sinyal'] else '' for _ in row]

    st.dataframe(
        df_sum[["Kod", "Fiyat", "Sinyal", "RSI", "Adet", "Ort.Maliyet", "Kar(Açık)", "Kar(Realize)"]].style.format({"Fiyat":"{:.2f}", "RSI":"{:.1f}", "Ort.Maliyet":"{:.2f}", "Kar(Açık)":"{:.2f}", "Kar(Realize)":"{:.2f}"}),
        use_container_width=True, selection_mode="single-row", on_select="rerun", key="main_table"
    )

    sel = st.session_state.main_table.get("selection", {}).get("rows", [])
    if sel:
        sel_row = df_sum.iloc[sel[0]]
        sel_code = sel_row["Kod"]
        sel_item = next(x for x in summary if x["Kod"] == sel_code)

        st.divider()
        st.header(f"🔍 {sel_code} Detayları")
        t1, t2, t3, t4 = st.tabs(["Grafik", "Temel", "İşlemler", "AI"])

        with t1:
            p_opt = st.radio("Periyot", ["Günlük", "Haftalık", "Aylık"], horizontal=True)
            df_c = sel_item["history"].copy()
            if p_opt == "Haftalık": df_c = df_c.resample('W').agg({'Open':'first','High':'max','Low':'min','Close':'last'})
            elif p_opt == "Aylık":
                try: df_c = df_c.resample('ME').agg({'Open':'first','High':'max','Low':'min','Close':'last'})
                except: df_c = df_c.resample('M').agg({'Open':'first','High':'max','Low':'min','Close':'last'})

            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(x=df_c.index, open=df_c['Open'], high=df_c['High'], low=df_c['Low'], close=df_c['Close'], name="Fiyat"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_c.index, y=df_c['Close'].rolling(50).mean(), line=dict(color='orange'), name="SMA50"), row=1, col=1)

            delta = df_c['Close'].diff()
            gain = (delta.where(delta>0, 0)).rolling(14).mean(); loss = (-delta.where(delta<0, 0)).rolling(14).mean()
            rsi = 100 - (100/(1+(gain/loss)))
            fig.add_trace(go.Scatter(x=df_c.index, y=rsi, line=dict(color='purple'), name="RSI"), row=2, col=1)
            fig.add_hline(y=70, row=2, col=1, line_dash="dash", line_color="red")
            fig.add_hline(y=30, row=2, col=1, line_dash="dash", line_color="green")
            st.plotly_chart(fig, use_container_width=True)

            m = sel_item["full_analysis"]["metrics"]
            c1, c2, c3 = st.columns(3)
            c1.metric("Pivot", f"{m['Pivot']:.2f}")
            c2.metric("Destek 1", f"{m['Destek 1']:.2f}")
            c3.metric("Direnç 1", f"{m['Direnç 1']:.2f}")
            st.info(f"💡 {m['expert_comment']}")
            if m.get('algo_comment'): st.success(m['algo_comment'])

        with t2:
            f = sel_item["fundamentals"]
            if f:
                c1, c2, c3 = st.columns(3)
                c1.metric("Piyasa Değ.", f"${f.get('marketCap',0)/1e9:.1f}B")
                c1.metric("F/K", f"{f.get('trailingPE',0):.2f}")
                c2.metric("Beta", f"{f.get('beta',0):.2f}")
                c2.metric("Temettü", f"%{f.get('dividendYield',0)*100:.2f}" if f.get('dividendYield') else "-")
                c3.metric("Öneri", f.get('recommendationKey','-').upper())
                c3.metric("Kâr Marjı", f"%{f.get('profitMargins',0)*100:.1f}" if f.get('profitMargins') else "-")
            else: st.warning("Veri yok.")

        with t3:
            with st.form("add_tr"):
                c1, c2, c3, c4 = st.columns(4)
                tt = c1.selectbox("Tip", ["ALIS", "SATIS"])
                tq = c2.number_input("Adet", 1.0)
                tp = c3.number_input("Fiyat", value=float(sel_item["Fiyat"]))
                td = c4.date_input("Tarih", datetime.now())
                if st.form_submit_button("İşlemi Kaydet"):
                    st.session_state.portfolio[sel_code]['transactions'].append({"date":str(td), "type":tt, "qty":tq, "price":tp})
                    save_watchlist(st.session_state.portfolio)
                    st.success("Kaydedildi!")
                    st.rerun()

            trs = st.session_state.portfolio[sel_code].get('transactions', [])
            if trs: st.dataframe(pd.DataFrame(trs))

        with t4:
            if st.button("Yapay Zeka Yorumla"):
                with st.spinner("Analiz ediliyor..."):
                    res = ask_gemini(pd.DataFrame([sel_item]), st.session_state.api_key)
                    st.markdown(res)
