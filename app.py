import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

from utils.data_manager import load_watchlist, save_watchlist, fetch_stock_history, get_current_price_batch, fetch_fundamentals_safe
from utils.analysis import analyze_stock, ask_gemini_analysis

# Page Config
st.set_page_config(page_title="Jules Stock Tracker", layout="wide", page_icon="📈")

# --- Helper Functions ---
@st.cache_data(ttl=300) # Cache for 5 minutes
def load_data(watchlist_tickers):
    """
    Fetches data for all stocks in the watchlist.
    Returns: prices_dict, history_df_multiindex
    """
    prices = get_current_price_batch(watchlist_tickers)
    history = fetch_stock_history(watchlist_tickers)
    return prices, history

@st.cache_data(ttl=3600) # Cache fundamentals longer
def load_fundamental(ticker):
    return fetch_fundamentals_safe(ticker)

# --- Sidebar ---
st.sidebar.title("⚙️ Kontrol Paneli")

# 0. API Key
api_key = st.sidebar.text_input("Gemini API Key (Opsiyonel)", type="password", help="Yapay zeka analizi için gereklidir.")

# 1. Manage Watchlist
watchlist = load_watchlist()

st.sidebar.subheader("Hisse Ekle")
# Bulk Add Option
bulk_tickers = st.sidebar.text_area("Hızlı Ekle (Virgülle Ayır)", placeholder="NVDA, AAPL, THYAO...")
if st.sidebar.button("Listeye Ekle"):
    if bulk_tickers:
        new_list = [t.strip().upper() for t in bulk_tickers.split(",") if t.strip()]
        count = 0
        for t in new_list:
            if t not in watchlist:
                watchlist[t] = {"name": t, "sector": "Unknown", "buy_price": 0.0, "quantity": 0}
                count += 1
        save_watchlist(watchlist)
        st.sidebar.success(f"{count} hisse eklendi!")
        time.sleep(1)
        st.rerun()

tickers = list(watchlist.keys())

# 2. Sector Filter
all_sectors = sorted(list(set([d.get("sector", "Unknown") for d in watchlist.values()])))
if all_sectors:
    selected_sectors = st.sidebar.multiselect("Sektör Filtresi", all_sectors, default=all_sectors)
else:
    selected_sectors = []

# 3. Notification Center (Simulated)
st.sidebar.subheader("🔔 Bildirimler")
notification_area = st.sidebar.empty()

# --- Main Page ---
st.title("🚀 Portföy Mimarı & AI Analisti")
st.markdown("---")

if not tickers:
    st.warning("Listeniz boş. Yan menüden hisse ekleyin!")
    st.stop()

# Load Data
with st.spinner("Piyasa verileri güncelleniyor..."):
    prices, history = load_data(tickers)

# Process Data for Table
table_data = []
alerts_log = []

for ticker in tickers:
    # Filter by Sector
    stock_info = watchlist[ticker]
    if selected_sectors and stock_info.get("sector", "Unknown") not in selected_sectors:
        continue

    price_info = prices.get(ticker, {})
    current_price = price_info.get("price", 0.0)
    change_pct = price_info.get("change_pct", 0.0)

    # Get history for this ticker
    ticker_hist = pd.DataFrame()
    if isinstance(history.columns, pd.MultiIndex):
        if ticker in history.columns.get_level_values(0):
            ticker_hist = history[ticker]
    else:
        # If single ticker result
        ticker_hist = history

    # Quick analysis for table
    high_52 = ticker_hist['High'].max() if not ticker_hist.empty else 0

    dist_ath = 0
    if high_52 > 0 and current_price > 0:
        dist_ath = ((high_52 - current_price) / high_52) * 100

    # Check Alerts
    if dist_ath < 2.0 and current_price > 0:
        alerts_log.append(f"🚨 **{ticker}** Zirveye (ATH) Çok Yakın! ({dist_ath:.1f}%)")

    table_data.append({
        "Ticker": ticker,
        "Name": stock_info.get("name"),
        "Fiyat": current_price,
        "Değişim %": change_pct,
        "ATH Fark %": dist_ath,
        "Alış": stock_info.get("buy_price", 0),
        "Adet": stock_info.get("quantity", 0)
    })

# Display Alerts
if alerts_log:
    with st.expander("⚠️ Kritik Uyarılar (ATH)", expanded=True):
        for alert in alerts_log:
            st.markdown(alert)
        notification_area.error(f"{len(alerts_log)} Alarm Aktif!")
else:
    notification_area.info("Aktif alarm yok.")

# Display Main Table
df_table = pd.DataFrame(table_data)

st.dataframe(
    df_table,
    column_config={
        "Fiyat": st.column_config.NumberColumn(format="$%.2f"),
        "Değişim %": st.column_config.NumberColumn(format="%.2f%%"),
        "ATH Fark %": st.column_config.NumberColumn(format="%.1f%%"),
        "Alış": st.column_config.NumberColumn(format="$%.2f"),
    },
    use_container_width=True,
    hide_index=True,
    selection_mode="single-row",
    on_select="rerun",
    key="stock_table"
)

# AI Analysis Button
st.markdown("---")
if st.button("✨ Yapay Zeka ile Portföyü Yorumla (Gemini)"):
    if not api_key:
        st.warning("Lütfen önce sol menüden Gemini API anahtarınızı girin.")
    else:
        with st.spinner("Gemini piyasayı analiz ediyor..."):
            ai_comment = ask_gemini_analysis(df_table, api_key)
            st.success("Analiz Tamamlandı!")
            st.markdown(ai_comment)

# --- Detail View ---
selected_row = []
if "stock_table" in st.session_state and st.session_state.stock_table:
    selected_row = st.session_state.stock_table.get("selection", {}).get("rows", [])

selected_ticker = None

if selected_row:
    selected_index = selected_row[0]
    selected_ticker = df_table.iloc[selected_index]["Ticker"]

if selected_ticker:
    st.divider()
    st.header(f"🔎 Detay Analiz: {selected_ticker}")

    # Fetch Deep Data
    with st.spinner(f"{selected_ticker} verileri inceleniyor..."):
        fund = load_fundamental(selected_ticker)

        # Get history again
        if isinstance(history.columns, pd.MultiIndex):
            ticker_hist = history[selected_ticker] if selected_ticker in history.columns.get_level_values(0) else pd.DataFrame()
        else:
            ticker_hist = history

        current_price = prices.get(selected_ticker, {}).get("price", 0)

        # Run Expert Analysis
        analysis = analyze_stock(selected_ticker, current_price, ticker_hist, fund)

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Temel Veriler")
        metrics = {
            "Piyasa Değeri": fund.get("marketCap", "N/A"),
            "F/K Oranı": fund.get("trailingPE", "N/A"),
            "Analist Tavsiyesi": fund.get("recommendationKey", "N/A").upper().replace("_", " "),
            "RSI (14)": f"{analysis['metrics'].get('RSI', 0):.1f}"
        }
        st.json(metrics)

        st.info(analysis["expert_comment"])

        st.subheader("Pozisyon Yönetimi")
        # Edit Position
        c_buy = st.number_input("Ortalama Alış Fiyatı", value=float(watchlist[selected_ticker].get("buy_price", 0)), key="buy_price_input")
        c_qty = st.number_input("Adet", value=int(watchlist[selected_ticker].get("quantity", 0)), key="qty_input")

        if st.button("Pozisyonu Güncelle"):
            watchlist[selected_ticker]["buy_price"] = c_buy
            watchlist[selected_ticker]["quantity"] = c_qty
            save_watchlist(watchlist)
            st.success("Kaydedildi!")
            st.rerun()

        # P/L Calc
        if c_qty > 0:
            value = current_price * c_qty
            cost = c_buy * c_qty
            pl = value - cost
            pl_pct = (pl / cost) * 100 if cost > 0 else 0

            color = "green" if pl >= 0 else "red"
            st.metric("Toplam Değer", f"${value:,.2f}", f"{pl:,.2f} ({pl_pct:.1f}%)")

    with col2:
        st.subheader("Teknik Grafik")

        if not ticker_hist.empty:
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.7, 0.3])

            # Candlestick
            fig.add_trace(go.Candlestick(
                x=ticker_hist.index,
                open=ticker_hist['Open'],
                high=ticker_hist['High'],
                low=ticker_hist['Low'],
                close=ticker_hist['Close'],
                name="Fiyat"
            ), row=1, col=1)

            # SMA
            sma50 = analysis['metrics'].get('SMA50')
            sma_50_series = ticker_hist['Close'].rolling(window=50).mean()
            sma_200_series = ticker_hist['Close'].rolling(window=200).mean()

            fig.add_trace(go.Scatter(x=ticker_hist.index, y=sma_50_series, name="SMA 50", line=dict(color='orange')), row=1, col=1)
            fig.add_trace(go.Scatter(x=ticker_hist.index, y=sma_200_series, name="SMA 200", line=dict(color='blue')), row=1, col=1)

            # RSI
            delta = ticker_hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi_series = 100 - (100 / (1 + rs))

            fig.add_trace(go.Scatter(x=ticker_hist.index, y=rsi_series, name="RSI", line=dict(color='purple')), row=2, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

            fig.update_layout(height=600, title_text=f"{selected_ticker} Grafiği")
            fig.update_xaxes(rangeslider_visible=False)

            st.plotly_chart(fig, use_container_width=True)

st.divider()
st.caption("Veriler Yahoo Finance'den 15dk gecikmeli gelebilir. Yatırım tavsiyesi değildir.")
