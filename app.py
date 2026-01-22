import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator
from ta.volatility import BollingerBands
from datetime import datetime

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Hisse Takip & AI Analist", layout="wide", page_icon="📈")

# --- BAŞLANGIÇ VERİLERİ VE HAFIZA (SESSION STATE) ---
# Streamlit Cloud'da sayfa yenilenince verilerin gitmemesi için bu yapı şarttır.
DEFAULT_PORTFOLIO = {
    "NVDA": {"transactions": [], "sector": "Teknoloji"},
    "AAPL": {"transactions": [], "sector": "Teknoloji"},
    "THYAO.IS": {"transactions": [], "sector": "Havacılık"}
}

if 'portfolio' not in st.session_state:
    st.session_state.portfolio = DEFAULT_PORTFOLIO

def get_portfolio():
    return st.session_state.portfolio

def save_portfolio_state(new_data):
    st.session_state.portfolio = new_data

# --- HESAPLAMA MOTORU ---
def calculate_portfolio_cost(transactions):
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
                    realized_pl += (price - avg_cost) * qty
                    total_cost -= avg_cost * qty
                    total_qty -= qty
                else:
                    total_qty = 0
                    total_cost = 0
        except:
            continue

    avg_price = (total_cost / total_qty) if total_qty > 0 else 0
    return total_qty, avg_price, realized_pl

@st.cache_data(ttl=60)
def fetch_market_data(tickers):
    if not tickers: return pd.DataFrame()
    try:
        tickers_str = " ".join(tickers)
        # Hata önleyici: threads=False bazen cloud ortamında daha stabil çalışır
        data = yf.download(tickers_str, period="1y", group_by='ticker', auto_adjust=True, threads=False)
        return data
    except Exception as e:
        return pd.DataFrame()

def get_technical_signals(df_stock):
    """Gelişmiş Teknik Analiz Motoru"""
    try:
        if df_stock is None or df_stock.empty: return None
        if len(df_stock) < 50: return None # Yetersiz veri
        
        # Veri formatı kontrolü (Series vs DataFrame)
        if isinstance(df_stock, pd.Series):
            close = df_stock
            high = df_stock
            low = df_stock
        else:
            close = df_stock['Close']
            high = df_stock['High']
            low = df_stock['Low']

        # Veri boşluklarını doldur
        close = close.ffill()

        # İndikatörler
        rsi_val = RSIIndicator(close).rsi().iloc[-1]
        
        window_200 = 200 if len(close) > 200 else len(close)
        sma200 = SMAIndicator(close, window=window_200).sma_indicator().iloc[-1]
        
        bb = BollingerBands(close)
        bb_high = bb.bollinger_hband().iloc[-1]
        bb_low = bb.bollinger_lband().iloc[-1]
        
        current_price = close.iloc[-1]
        
        # Sinyal Algoritması
        score = 0
        if rsi_val < 30: score += 2
        elif rsi_val > 70: score -= 2
        
        if current_price > sma200: score += 1
        else: score -= 1
        
        if current_price <= bb_low * 1.02: score += 1
        if current_price >= bb_high * 0.98: score -= 1

        if score >= 2: signal_txt = "GÜÇLÜ AL 🟢"
        elif score == 1: signal_txt = "AL 🟢"
        elif score <= -2: signal_txt = "GÜÇLÜ SAT 🔴"
        elif score == -1: signal_txt = "SAT 🔴"
        else: signal_txt = "NÖTR ⚪"
        
        # Pivot Hesaplama
        pivot = (high.iloc[-1] + low.iloc[-1] + current_price) / 3
        r1 = (2 * pivot) - low.iloc[-1]
        s1 = (2 * pivot) - high.iloc[-1]
        
        return {
            "Fiyat": current_price,
            "RSI": rsi_val,
            "SMA200": sma200,
            "Sinyal": signal_txt,
            "Destek": s1,
            "Direnç": r1,
            "ATH": high.max()
        }
    except:
        return None

# --- SIDEBAR ---
st.sidebar.title("⚙️ Kontrol Paneli")

api_key = st.sidebar.text_input("Gemini API Anahtarı", type="password")
if api_key: genai.configure(api_key=api_key)

st.sidebar.divider()
st.sidebar.subheader("Portföy Yönetimi")

current_portfolio = get_portfolio()
tickers_list = list(current_portfolio.keys())

# EKLEME
with st.sidebar.form("add_stock"):
    new_ticker = st.text_input("Hisse Kodu (Örn: GARAN.IS)").strip().upper()
    new_sector = st.selectbox("Sektör", ["Teknoloji", "Finans", "Sanayi", "Enerji", "Diğer"])
    if st.form_submit_button("Listeye Ekle"):
        if new_ticker and new_ticker not in current_portfolio:
            current_portfolio[new_ticker] = {"transactions": [], "sector": new_sector}
            save_portfolio_state(current_portfolio)
            st.success(f"{new_ticker} eklendi.")
            st.rerun()

# ÇIKARMA (Talebin üzerine eklendi)
if tickers_list:
    rem_ticker = st.sidebar.selectbox("Hisse Çıkar", ["Seçiniz..."] + tickers_list)
    if st.sidebar.button("🗑️ Sil"):
        if rem_ticker != "Seçiniz..." and rem_ticker in current_portfolio:
            del current_portfolio[rem_ticker]
            save_portfolio_state(current_portfolio)
            st.warning(f"{rem_ticker} silindi.")
            st.rerun()

# --- ANA EKRAN ---
st.title("📈 Hisse Takip & AI Analist")

if not tickers_list:
    st.info("Listeniz boş. Sol menüden hisse ekleyin.")
    st.stop()

# Verileri Çek
with st.spinner("Piyasa verileri alınıyor..."):
    raw_data = fetch_market_data(tickers_list)

summary_data = []
alerts = []

if not raw_data.empty:
    for t in tickers_list:
        try:
            # MultiIndex vs SingleIndex kontrolü
            if len(tickers_list) > 1:
                try: stock_df = raw_data[t]
                except: continue
            else:
                stock_df = raw_data
            
            stock_df = stock_df.dropna(subset=['Close'])
            if stock_df.empty: continue

            tech = get_technical_signals(stock_df)
            
            if tech:
                # Portföy Maliyet
                qty, avg_cost, realized = calculate_portfolio_cost(current_portfolio[t]['transactions'])
                val = qty * tech['Fiyat']
                p_l = val - (qty * avg_cost)
                
                # ATH Alarmı (%2)
                ath_diff = ((tech['ATH'] - tech['Fiyat']) / tech['ATH']) * 100
                if ath_diff < 2.0:
                    alerts.append(f"🚨 **{t}** Zirveye (ATH) çok yakın! (Fark: %{ath_diff:.1f})")

                summary_data.append({
                    "Kod": t,
                    "Sektör": current_portfolio[t]['sector'],
                    "Fiyat": tech['Fiyat'],
                    "Sinyal": tech['Sinyal'],
                    "RSI": tech['RSI'],
                    "Adet": qty,
                    "Ort. Mal.": avg_cost,
                    "Kâr/Zarar": p_l
                })
        except:
            continue

# Alarmlar
if alerts:
    st.error("\n".join(alerts))

# Ana Tablo
if summary_data:
    df_sum = pd.DataFrame(summary_data)
    
    def color_sig(val):
        if 'GÜÇLÜ AL' in val: return 'background-color: #28a745; color: white'
        if 'AL' in val: return 'background-color: #90ee90; color: black'
        if 'SAT' in val: return 'background-color: #dc3545; color: white'
        return ''

    st.subheader("Piyasa Özeti")
    st.dataframe(
        df_sum.style.applymap(color_sig, subset=['Sinyal'])
        .format({"Fiyat": "{:.2f}", "RSI": "{:.1f}", "Ort. Mal.": "{:.2f}", "Kâr/Zarar": "{:.2f}"}),
        use_container_width=True,
        selection_mode="single-row",
        on_select="rerun",
        key="main_table"
    )

    # DETAY PANELİ
    sel_rows = st.session_state.main_table.get("selection", {}).get("rows", [])
    if sel_rows:
        idx = sel_rows[0]
        sel_ticker = df_sum.iloc[idx]["Kod"]
        
        st.divider()
        st.header(f"🔎 Detay: {sel_ticker}")
        
        tab1, tab2, tab3 = st.tabs(["📉 Grafik", "🤖 AI Yorum", "💰 İşlemler"])
        
        with tab1:
            # Grafik Çizimi
            if len(tickers_list) > 1: df_chart = raw_data[sel_ticker]
            else: df_chart = raw_data
            
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], name="Fiyat"), row=1, col=1)
            
            # SMA
            sma = df_chart['Close'].rolling(window=50).mean()
            fig.add_trace(go.Scatter(x=df_chart.index, y=sma, line=dict(color='orange'), name="SMA 50"), row=1, col=1)
            
            # RSI
            delta = df_chart['Close'].diff()
            gain = (delta.where(delta>0, 0)).rolling(14).mean()
            loss = (-delta.where(delta<0, 0)).rolling(14).mean()
            rs = gain/loss
            rsi_s = 100 - (100/(1+rs))
            
            fig.add_trace(go.Scatter(x=df_chart.index, y=rsi_s, line=dict(color='purple'), name="RSI"), row=2, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Destek Direnç Bilgisi
            t_sig = get_technical_signals(df_chart)
            c1, c2, c3 = st.columns(3)
            c1.metric("Destek (S1)", f"{t_sig['Destek']:.2f}")
            c2.metric("Pivot", f"{(t_sig['Destek']+t_sig['Direnç'])/2:.2f}")
            c3.metric("Direnç (R1)", f"{t_sig['Direnç']:.2f}")

        with tab2:
            st.subheader("Yapay Zeka Analizi")
            user_q = st.text_area("Soru Sor:", placeholder=f"{sel_ticker} için kısa vadeli beklenti nedir?")
            if st.button("Analiz Et"):
                if api_key:
                    with st.spinner("Gemini düşünüyor..."):
                        t_sig = get_technical_signals(df_chart)
                        prompt = f"""
                        Finans uzmanı olarak {sel_ticker} hissesini yorumla.
                        Veriler: Fiyat {t_sig['Fiyat']}, RSI {t_sig['RSI']}, Sinyal {t_sig['Sinyal']}.
                        Kullanıcı Sorusu: {user_q if user_q else 'Genel teknik görünüm nedir?'}
                        """
                        try:
                            model = genai.GenerativeModel('gemini-pro')
                            res = model.generate_content(prompt)
                            st.markdown(res.text)
                        except Exception as e:
                            st.error(f"Hata: {e}")
                else:
                    st.warning("API Anahtarı girilmedi.")

        with tab3:
            st.subheader("Al/Sat İşlemleri")
            c1, c2 = st.columns(2)
            with c1:
                with st.form("trade"):
                    tt = st.selectbox("İşlem", ["ALIS", "SATIS"])
                    td = st.date_input("Tarih", datetime.now())
                    tq = st.number_input("Adet", min_value=1.0)
                    tp = st.number_input("Fiyat", value=float(df_chart['Close'].iloc[-1]))
                    if st.form_submit_button("Kaydet"):
                        current_portfolio[sel_ticker]['transactions'].append({
                            "date": str(td), "type": tt, "qty": tq, "price": tp
                        })
                        save_portfolio_state(current_portfolio)
                        st.success("Kaydedildi!")
                        st.rerun()
            with c2:
                tr_hist = current_portfolio[sel_ticker]['transactions']
                if tr_hist:
                    st.dataframe(pd.DataFrame(tr_hist))
                else:
                    st.info("İşlem yok.")
