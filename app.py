import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

from utils.data_manager import load_watchlist, save_watchlist, fetch_stock_history, get_current_price_batch, fetch_fundamentals_safe
from utils.analysis import analyze_stock

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
st.sidebar.title("🛠️ Settings")

# 1. Manage Watchlist
watchlist = load_watchlist()
tickers = list(watchlist.keys())

st.sidebar.subheader("Manage Portfolio")
new_ticker = st.sidebar.text_input("Add Stock (Ticker)").upper()
if st.sidebar.button("Add"):
    if new_ticker and new_ticker not in watchlist:
        watchlist[new_ticker] = {"name": new_ticker, "sector": "Unknown", "buy_price": 0.0, "quantity": 0}
        save_watchlist(watchlist)
        st.sidebar.success(f"Added {new_ticker}")
        st.rerun()

# 2. Sector Filter
all_sectors = sorted(list(set([d.get("sector", "Unknown") for d in watchlist.values()])))
selected_sectors = st.sidebar.multiselect("Filter by Sector", all_sectors, default=all_sectors)

# 3. Notification Center (Simulated)
st.sidebar.subheader("🔔 Notifications")
notification_area = st.sidebar.empty()

# --- Main Page ---
st.title("📈 Pro Stock Tracker & AI Agent")

if not tickers:
    st.warning("No stocks in watchlist. Add one in the sidebar!")
    st.stop()

# Load Data
with st.spinner("Fetching Market Data..."):
    prices, history = load_data(tickers)

# Process Data for Table
table_data = []
alerts_log = []

for ticker in tickers:
    # Filter by Sector
    stock_info = watchlist[ticker]
    if stock_info.get("sector", "Unknown") not in selected_sectors:
        continue

    price_info = prices.get(ticker, {})
    current_price = price_info.get("price", 0.0)
    change_pct = price_info.get("change_pct", 0.0)

    # Get history for this ticker
    if isinstance(history.columns, pd.MultiIndex):
        if ticker in history.columns.get_level_values(0):
            ticker_hist = history[ticker]
        else:
            ticker_hist = pd.DataFrame()
    else:
        # If single ticker result
        ticker_hist = history

    # Analyze (Lightweight analysis for table)
    # We fetch fundamentals lazily or use cached?
    # For the table, we might need some fundamentals (ATH).
    # To speed up, we might skip full analysis for the table row unless we cached it.
    # Let's just do a quick calc based on history for ATH.

    high_52 = ticker_hist['High'].max() if not ticker_hist.empty else 0
    low_52 = ticker_hist['Low'].min() if not ticker_hist.empty else 0

    dist_ath = 0
    if high_52 > 0 and current_price > 0:
        dist_ath = ((high_52 - current_price) / high_52) * 100

    # Check Alerts
    if dist_ath < 2.0 and current_price > 0:
        alerts_log.append(f"🚨 **{ticker}** is near ATH ({dist_ath:.1f}%)")

    table_data.append({
        "Ticker": ticker,
        "Name": stock_info.get("name"),
        "Sector": stock_info.get("sector"),
        "Price": current_price,
        "Change %": change_pct,
        "ATH Dist %": dist_ath,
        "52W High": high_52,
        "Buy Price": stock_info.get("buy_price", 0),
        "Qty": stock_info.get("quantity", 0)
    })

# Display Alerts
if alerts_log:
    with st.expander("⚠️ Active Alerts", expanded=True):
        for alert in alerts_log:
            st.markdown(alert)
        # Update sidebar
        notification_area.error(f"{len(alerts_log)} Alerts Active!")
else:
    notification_area.info("No active alerts.")

# Display Main Table
df_table = pd.DataFrame(table_data)

# Format Table
st.dataframe(
    df_table,
    column_config={
        "Price": st.column_config.NumberColumn(format="$%.2f"),
        "Change %": st.column_config.NumberColumn(format="%.2f%%"),
        "ATH Dist %": st.column_config.NumberColumn(format="%.1f%%"),
        "52W High": st.column_config.NumberColumn(format="$%.2f"),
    },
    use_container_width=True,
    hide_index=True,
    selection_mode="single-row",
    on_select="rerun",
    key="stock_table"
)

# --- Detail View ---
selected_row = []
if "stock_table" in st.session_state and st.session_state.stock_table:
    selected_row = st.session_state.stock_table.get("selection", {}).get("rows", [])

selected_ticker = None

if selected_row:
    selected_index = selected_row[0]
    selected_ticker = df_table.iloc[selected_index]["Ticker"]
else:
    # Default to first or user selection via selectbox
    selected_ticker = st.selectbox("Select Stock for Details", [d["Ticker"] for d in table_data])

if selected_ticker:
    st.divider()
    st.header(f"🔎 Deep Dive: {selected_ticker}")

    # Fetch Deep Data
    with st.spinner(f"Analyzing {selected_ticker}..."):
        fund = load_fundamental(selected_ticker)

        # Get history again (uncached or cached)
        if isinstance(history.columns, pd.MultiIndex):
            ticker_hist = history[selected_ticker]
        else:
            ticker_hist = history

        current_price = prices.get(selected_ticker, {}).get("price", 0)

        # Run Expert Analysis
        analysis = analyze_stock(selected_ticker, current_price, ticker_hist, fund)

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Fundamental Data")
        rsi_series = analysis['metrics'].get('RSI')
        rsi_val = rsi_series.iloc[-1] if rsi_series is not None and not rsi_series.empty else 0

        metrics = {
            "Market Cap": fund.get("marketCap", "N/A"),
            "P/E Ratio": fund.get("trailingPE", "N/A"),
            "Analyst Rec": fund.get("recommendationKey", "N/A").upper().replace("_", " "),
            "RSI (14)": f"{rsi_val:.1f}"
        }
        st.json(metrics)

        st.subheader("🤖 Expert Insight")
        st.info(analysis["expert_comment"])

        st.subheader("Your Position")
        # Edit Position
        c_buy = st.number_input("Buy Price", value=float(watchlist[selected_ticker].get("buy_price", 0)), key="buy_price_input")
        c_qty = st.number_input("Quantity", value=int(watchlist[selected_ticker].get("quantity", 0)), key="qty_input")

        if st.button("Update Position"):
            watchlist[selected_ticker]["buy_price"] = c_buy
            watchlist[selected_ticker]["quantity"] = c_qty
            save_watchlist(watchlist)
            st.success("Position Updated!")
            st.rerun()

        # P/L Calc
        if c_qty > 0:
            value = current_price * c_qty
            cost = c_buy * c_qty
            pl = value - cost
            pl_pct = (pl / cost) * 100 if cost > 0 else 0

            st.metric("Position Value", f"${value:,.2f}", f"{pl:,.2f} ({pl_pct:.1f}%)")

    with col2:
        st.subheader("Technical Charts")

        # Plotly Chart
        if not ticker_hist.empty:
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.7, 0.3])

            # Candlestick
            fig.add_trace(go.Candlestick(
                x=ticker_hist.index,
                open=ticker_hist['Open'],
                high=ticker_hist['High'],
                low=ticker_hist['Low'],
                close=ticker_hist['Close'],
                name="Price"
            ), row=1, col=1)

            # SMA
            sma_50_series = analysis['metrics'].get('SMA50')
            sma_200_series = analysis['metrics'].get('SMA200')

            fig.add_trace(go.Scatter(x=ticker_hist.index, y=sma_50_series, name="SMA 50", line=dict(color='orange')), row=1, col=1)
            fig.add_trace(go.Scatter(x=ticker_hist.index, y=sma_200_series, name="SMA 200", line=dict(color='blue')), row=1, col=1)

            # RSI
            rsi_series = analysis['metrics'].get('RSI')

            fig.add_trace(go.Scatter(x=ticker_hist.index, y=rsi_series, name="RSI", line=dict(color='purple')), row=2, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

            fig.update_layout(height=600, title_text=f"{selected_ticker} Price Action & Indicators")
            fig.update_xaxes(rangeslider_visible=False)

            st.plotly_chart(fig, use_container_width=True)

# Footer / Chat interface placeholder
st.divider()
st.caption("Jules AI Financial Assistant - Market Data Provided by Yahoo Finance. Alerts are based on end-of-day data approximations.")

with st.expander("💬 Ask Jules (AI Chat)"):
    user_q = st.text_input("Ask a question about your portfolio...")
    if user_q:
        st.write("Jules: That's a great question! Based on my current programming, I recommend focusing on the technical indicators shown above. (Integration with Gemini API would go here).")
