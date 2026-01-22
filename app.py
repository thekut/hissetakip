import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import time

# Custom Modules
from utils.data_manager import (
    load_watchlist, save_watchlist, fetch_stock_history,
    fetch_fundamentals_safe, search_symbol_local, initialize_stock_entry, resolve_ticker
)
from utils.analysis import analyze_stock, ask_gemini_analysis

# --- PAGE CONFIG ---
st.set_page_config(page_title="Finansal Hafıza Pro", layout="wide", page_icon="🏦")

# --- SESSION STATE & DATA LOADING ---
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = load_watchlist()

def save_state():
    save_watchlist(st.session_state.portfolio)

def get_all_sectors():
    sectors = set()
    for item in st.session_state.portfolio.values():
        sectors.add(item.get('sector', 'Diğer'))
    return list(sorted(sectors))

def calculate_portfolio_metrics(transactions, current_price):
    total_qty = 0
    total_cost = 0
    realized_pl = 0
    
    for t in transactions:
        try:
            qty = float(t['qty'])
            price = float(t['price'])
            if t['type'] == 'ALIS':
                total_cost += qty * price
                total_qty += qty
            elif t['type'] == 'SATIS':
                if total_qty > 0:
                    avg_cost = total_cost / total_qty
                    # Realized gain on this chunk
                    realized_pl += (price - avg_cost) * qty
                    # Remove cost basis
                    total_cost -= avg_cost * qty
                    total_qty -= qty
                else:
                    # Selling without holding (Short?) - Ignore or handle simplified
                    pass
        except Exception:
            continue

    avg_price = (total_cost / total_qty) if total_qty > 0 else 0
    market_value = total_qty * current_price
    unrealized_pl = market_value - total_cost

    return total_qty, avg_price, realized_pl, unrealized_pl

# --- SIDEBAR ---
st.sidebar.title("⚙️ Kontrol Paneli")

# API Key
if 'api_key' not in st.session_state:
    st.session_state.api_key = ""
api_key_input = st.sidebar.text_input("Gemini API Key (AI Analiz için)", type="password", value=st.session_state.api_key)
if api_key_input:
    st.session_state.api_key = api_key_input

st.sidebar.markdown("---")
st.sidebar.subheader("Portföy Yönetimi")

# Add Stock
with st.sidebar.expander("➕ Hisse Ekle", expanded=False):
    add_query = st.text_input("Hisse Kodu veya Adı", placeholder="NVDA, Apple...").strip()

    # Sector Selection (Dynamic + Static)
    existing_sectors = get_all_sectors()
    default_sectors = ["Teknoloji", "Finans", "Sanayi", "Enerji", "Havacılık", "ETF", "Diğer"]
    all_sectors_opt = sorted(list(set(existing_sectors + default_sectors)))
    add_sector = st.selectbox("Sektör", all_sectors_opt)

    if st.button("Listeye Ekle"):
        if add_query:
            # 1. Try to resolve Name -> Ticker using Master List
            resolved_ticker = resolve_ticker(add_query)

            # 2. Check if already in portfolio
            if resolved_ticker in st.session_state.portfolio:
                st.warning(f"{resolved_ticker} zaten listenizde.")
            else:
                # 3. Add new entry
                st.session_state.portfolio[resolved_ticker] = initialize_stock_entry(resolved_ticker, add_sector)
                save_state()
                st.success(f"{resolved_ticker} eklendi!")
                st.rerun()

# Remove Stock
with st.sidebar.expander("🗑️ Hisse Çıkar", expanded=False):
    tickers_list = sorted(list(st.session_state.portfolio.keys()))
    rem_ticker = st.selectbox("Silinecek Hisse", ["Seçiniz..."] + tickers_list)
    if st.button("Sil"):
        if rem_ticker != "Seçiniz..." and rem_ticker in st.session_state.portfolio:
            del st.session_state.portfolio[rem_ticker]
            save_state()
            st.warning(f"{rem_ticker} silindi.")
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.info("Veriler Yahoo Finance'ten gecikmeli sağlanır. Yatırım tavsiyesi değildir.")

# --- MAIN PAGE ---
st.title("📈 Finansal Hafıza AI")

# 1. Sector Filter
sectors = get_all_sectors()
selected_sector = st.selectbox("Sektör Filtrele", ["Tümü"] + sectors)

# Filter Portfolio
filtered_portfolio = {}
if selected_sector == "Tümü":
    filtered_portfolio = st.session_state.portfolio
else:
    for t, data in st.session_state.portfolio.items():
        if data.get('sector') == selected_sector:
            filtered_portfolio[t] = data

tickers_to_fetch = list(filtered_portfolio.keys())

if not tickers_to_fetch:
    st.info("Gösterilecek hisse yok. Sol menüden ekleyin.")
    st.stop()

# 2. Fetch Data
with st.spinner("Piyasa verileri ve analizler yükleniyor..."):
    history_data = fetch_stock_history(tickers_to_fetch)

summary_data = []
active_alerts = []

# Progress bar
prog_bar = st.progress(0)
processed_count = 0

for ticker in tickers_to_fetch:
    try:
        # Extract Data
        if isinstance(history_data.columns, pd.MultiIndex):
            try:
                df = history_data[ticker]
            except KeyError:
                continue # No data for this ticker
        else:
            # If not MultiIndex, assume it's a single dataframe for the single requested ticker
            if len(tickers_to_fetch) == 1:
                df = history_data
            else:
                continue

        # Validate Data
        if df is None or df.empty or 'Close' not in df.columns:
            continue

        df = df.dropna(subset=['Close'])
        if df.empty: continue

        current_price = df['Close'].iloc[-1]

        # Fetch Fundamentals
        fund = fetch_fundamentals_safe(ticker)

        # Analyze
        analysis = analyze_stock(ticker, current_price, df, fund)
        tech = analysis.get("metrics", {})

        if not tech: continue

        # Collect Alerts
        if analysis.get('alerts'):
            for a in analysis['alerts']:
                active_alerts.append(f"**{ticker}**: {a}")

        # Portfolio Metrics
        transactions = st.session_state.portfolio[ticker].get('transactions', [])
        qty, avg_cost, realized_pl, unrealized_pl = calculate_portfolio_metrics(transactions, current_price)

        # Table Row
        summary_data.append({
            "Kod": ticker,
            "Şirket": st.session_state.portfolio[ticker].get('name', ticker),
            "Fiyat": current_price,
            "Değişim %": ((current_price - df['Close'].iloc[-2])/df['Close'].iloc[-2])*100,
            "Sinyal": tech.get('Sinyal', '-'),
            "RSI": tech.get('RSI', 0),
            "Pivot": tech.get('Pivot', 0),
            "Adet": qty,
            "Ort. Mal.": avg_cost,
            "Kar/Zarar (Açık)": unrealized_pl,
            "Kar (Realize)": realized_pl,
            "Score": tech.get('Score', 0),
            "full_analysis": analysis,
            "history": df,
            "fundamentals": fund
        })

    except Exception as e:
        # st.error(f"Error processing {ticker}: {e}")
        pass

    processed_count += 1
    prog_bar.progress(processed_count / len(tickers_to_fetch))

prog_bar.empty()

# 3. Alerts Section
if active_alerts:
    st.error("🔔 PİYASA ALARMLARI")
    for alert in active_alerts:
        st.markdown(f"- {alert}")

# 4. Main Table
if summary_data:
    df_summary = pd.DataFrame(summary_data)

    # Display Columns
    display_cols = ["Kod", "Şirket", "Fiyat", "Değişim %", "Sinyal", "RSI", "Adet", "Ort. Mal.", "Kar/Zarar (Açık)", "Kar (Realize)"]
    
    def color_signal(val):
        if 'GÜÇLÜ AL' in str(val): return 'background-color: #2E8B57; color: white'
        if 'AL' in str(val): return 'background-color: #90EE90; color: black'
        if 'SAT' in str(val): return 'background-color: #CD5C5C; color: white'
        return ''

    def color_pl(val):
        if val > 0: return 'color: green'
        if val < 0: return 'color: red'
        return ''

    st.subheader(f"📊 Piyasa Özeti ({selected_sector})")

    st.dataframe(
        df_summary[display_cols].style
        .map(color_signal, subset=['Sinyal'])
        .map(color_pl, subset=['Kar/Zarar (Açık)', 'Kar (Realize)', 'Değişim %'])
        .format({
            "Fiyat": "{:.2f}",
            "Değişim %": "{:+.2f}%",
            "RSI": "{:.1f}",
            "Ort. Mal.": "{:.2f}",
            "Kar/Zarar (Açık)": "{:+.2f}",
            "Kar (Realize)": "{:+.2f}",
            "Adet": "{:.0f}"
        }),
        use_container_width=True,
        selection_mode="single-row",
        on_select="rerun",
        key="main_table"
    )

    # 5. Details View
    selected_rows = st.session_state.main_table.get("selection", {}).get("rows", [])
    if selected_rows:
        idx = selected_rows[0]
        sel_data = summary_data[idx]
        sel_ticker = sel_data["Kod"]
        
        st.divider()
        st.header(f"🔍 {sel_ticker} - {sel_data['Şirket']}")
        
        tab1, tab2, tab3, tab4 = st.tabs(["📉 Teknik & Grafik", "🏢 Temel Analiz", "💵 İşlemler", "🤖 AI Yorumu"])
        
        # --- TAB 1: Technicals ---
        with tab1:
            col1, col2 = st.columns([3, 1])
            with col1:
                # Chart
                df_hist = sel_data["history"]
                
                # Resample option
                p_opt = st.radio("Grafik", ["Günlük", "Haftalık", "Aylık"], horizontal=True, key="p_opt")
                
                # Copy to avoid mutation issues
                chart_data = df_hist.copy()
                
                if p_opt == "Haftalık":
                    chart_data = chart_data.resample('W').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'})
                elif p_opt == "Aylık":
                    # Use 'ME' if pandas >= 2.2, else 'M'
                    try:
                        chart_data = chart_data.resample('ME').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'})
                    except:
                        chart_data = chart_data.resample('M').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'})

                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.1)
                
                # Candle
                fig.add_trace(go.Candlestick(x=chart_data.index, open=chart_data['Open'], high=chart_data['High'],
                                low=chart_data['Low'], close=chart_data['Close'], name="Fiyat"), row=1, col=1)
                
                # SMAs (Only meaningful on Daily usually, or re-calc for others)
                if p_opt == "Günlük":
                    metrics = sel_data["full_analysis"]["metrics"]
                    sma50 = chart_data['Close'].rolling(50).mean()
                    sma200 = chart_data['Close'].rolling(200).mean()
                    fig.add_trace(go.Scatter(x=chart_data.index, y=sma50, line=dict(color='orange'), name="SMA 50"), row=1, col=1)
                    fig.add_trace(go.Scatter(x=chart_data.index, y=sma200, line=dict(color='blue'), name="SMA 200"), row=1, col=1)

                    # BB
                    bb_h = chart_data['Close'].rolling(20).mean() + 2 * chart_data['Close'].rolling(20).std()
                    bb_l = chart_data['Close'].rolling(20).mean() - 2 * chart_data['Close'].rolling(20).std()
                    fig.add_trace(go.Scatter(x=chart_data.index, y=bb_h, line=dict(color='gray', width=1, dash='dot'), name="BB Üst"), row=1, col=1)
                    fig.add_trace(go.Scatter(x=chart_data.index, y=bb_l, line=dict(color='gray', width=1, dash='dot'), name="BB Alt"), row=1, col=1)

                # RSI
                delta = chart_data['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                rsi_s = 100 - (100 / (1 + rs))
                
                fig.add_trace(go.Scatter(x=chart_data.index, y=rsi_s, line=dict(color='purple'), name="RSI"), row=2, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
                
                fig.update_layout(height=500, xaxis_rangeslider_visible=False, title=f"{sel_ticker} {p_opt}")
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                # Levels & Indicators
                m = sel_data["full_analysis"]["metrics"]
                st.subheader("Seviyeler")
                st.metric("Sinyal", m["Sinyal"], delta=m["Score"])
                st.metric("Pivot", f"{m['Pivot']:.2f}")
                st.metric("Direnç 1", f"{m['Direnç 1']:.2f}")
                st.metric("Destek 1", f"{m['Destek 1']:.2f}")

                st.markdown("---")
                st.markdown("**Analiz Nedenleri:**")
                for r in m.get("Reasons", []):
                    st.caption(f"• {r}")

        # --- TAB 2: Fundamentals ---
        with tab2:
            f = sel_data["fundamentals"]
            if f:
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Piyasa Değeri", f"${f.get('marketCap', 0)/1e9:.2f}B" if f.get('marketCap') else "-")
                    st.metric("F/K (Trailing)", f"{f.get('trailingPE', 0):.2f}" if f.get('trailingPE') else "-")
                with c2:
                    st.metric("52H Yüksek", f"{f.get('fiftyTwoWeekHigh', 0):.2f}")
                    st.metric("52H Düşük", f"{f.get('fiftyTwoWeekLow', 0):.2f}")
                with c3:
                    st.metric("Analist Önerisi", f.get('recommendationKey', '-').upper().replace('_', ' '))
                    st.metric("Sektör", f.get('sector', '-'))
            else:
                st.warning("Temel veriler alınamadı.")

        # --- TAB 3: Transactions ---
        with tab3:
            c1, c2 = st.columns([1, 2])
            with c1:
                st.subheader("Yeni İşlem")
                with st.form("tr_form"):
                    tr_type = st.selectbox("Tip", ["ALIS", "SATIS"])
                    tr_qty = st.number_input("Adet", min_value=0.01, step=1.0)
                    tr_price = st.number_input("Fiyat", min_value=0.01, value=float(sel_data["Fiyat"]))
                    tr_date = st.date_input("Tarih", datetime.now())
                    
                    if st.form_submit_button("Kaydet"):
                        st.session_state.portfolio[sel_ticker]['transactions'].append({
                            "date": str(tr_date),
                            "type": tr_type,
                            "qty": tr_qty,
                            "price": tr_price
                        })
                        save_state()
                        st.success("İşlem eklendi!")
                        st.rerun()
            
            with c2:
                st.subheader("İşlem Geçmişi")
                trs = st.session_state.portfolio[sel_ticker].get('transactions', [])
                if trs:
                    st.dataframe(pd.DataFrame(trs))
                else:
                    st.info("Henüz işlem yok.")

        # --- TAB 4: AI ---
        with tab4:
            st.markdown("### 🧠 AI Görüşü")
            if st.button("Analiz Et (Gemini)"):
                with st.spinner("Yapay zeka analiz ediyor..."):
                    # Construct a mini summary for AI
                    ai_input = pd.DataFrame([sel_data])
                    response = ask_gemini_analysis(ai_input, st.session_state.api_key)
                    st.markdown(response)

else:
    st.write("Veri yok.")
