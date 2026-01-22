import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator, MACD
from ta.volatility import BollingerBands
import json
import os
from datetime import datetime

# --- YAPILANDIRMA ---
st.set_page_config(page_title="Finansal Hafıza Pro", layout="wide", page_icon="🏦")

# --- VERİ YÖNETİMİ (JSON TABANLI) ---
PORTFOLIO_FILE = 'portfolio_db.json'

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, 'r') as f:
            return json.load(f)
    else:
        # Varsayılan Başlangıç Verisi
        return {
            "NVDA": {"transactions": [], "sector": "Teknoloji"},
            "AAPL": {"transactions": [], "sector": "Teknoloji"},
            "THYAO.IS": {"transactions": [], "sector": "Havacılık"} 
        }

def save_portfolio(data):
    with open(PORTFOLIO_FILE, 'w') as f:
        json.dump(data, f)

def calculate_portfolio_cost(transactions):
    """Maliyet ortalamasını ve elde kalan adedi hesaplar."""
    total_qty = 0
    total_cost = 0
    realized_pl = 0
    
    for t in transactions:
        qty = float(t['qty'])
        price = float(t['price'])
        if t['type'] == 'ALIS':
            total_cost += qty * price
            total_qty += qty
        elif t['type'] == 'SATIS':
            # Satışta maliyet düşülür, realize kar/zarar hesaplanır
            if total_qty > 0:
                avg_cost = total_cost / total_qty
                realized_pl += (price - avg_cost) * qty
                total_cost -= avg_cost * qty
                total_qty -= qty
            else:
                total_qty = 0
                total_cost = 0

    avg_price = (total_cost / total_qty) if total_qty > 0 else 0
    return total_qty, avg_price, realized_pl

# --- SIDEBAR & AYARLAR ---
st.sidebar.title("⚙️ Kontrol Merkezi")

# API Key
api_key = st.sidebar.text_input("Gemini API Anahtarı", type="password", help="AI Analizleri için gereklidir.")
if api_key:
    genai.configure(api_key=api_key)

# Portföy Yönetimi
st.sidebar.divider()
st.sidebar.subheader("🗂️ Portföy İşlemleri")

portfolio = load_portfolio()
portfolio_tickers = list(portfolio.keys())

# Hisse Ekleme
new_ticker = st.sidebar.text_input("Hisse Ekle (Kod)", placeholder="Örn: MSFT, GARAN.IS").strip().upper()
new_sector = st.sidebar.selectbox("Sektör Seç", ["Teknoloji", "Finans", "Enerji", "Sanayi", "Sağlık", "Diğer"])
if st.sidebar.button("Listeye Ekle"):
    if new_ticker and new_ticker not in portfolio:
        portfolio[new_ticker] = {"transactions": [], "sector": new_sector}
        save_portfolio(portfolio)
        st.success(f"{new_ticker} eklendi!")
        st.rerun()

# Hisse Çıkarma
remove_ticker = st.sidebar.selectbox("Hisse Çıkar", ["Seçiniz..."] + portfolio_tickers)
if st.sidebar.button("Listeden Sil"):
    if remove_ticker != "Seçiniz...":
        del portfolio[remove_ticker]
        save_portfolio(portfolio)
        st.warning(f"{remove_ticker} silindi!")
        st.rerun()

# --- ANALİZ MOTORU ---
@st.cache_data(ttl=300)
def fetch_market_data(tickers):
    if not tickers: return pd.DataFrame()
    # YFinance bazen toplu indirmede sorun çıkarabilir, string birleştiriyoruz
    tickers_str = " ".join(tickers)
    data = yf.download(tickers_str, period="1y", group_by='ticker', auto_adjust=True)
    return data

def get_technical_signals(df_stock):
    """Bir hisse için teknik indikatörleri ve sinyalleri hesaplar."""
    if df_stock.empty or len(df_stock) < 200: return None
    
    close = df_stock['Close']
    
    # İndikatörler
    rsi = RSIIndicator(close).rsi().iloc[-1]
    macd = MACD(close).macd_diff().iloc[-1]
    sma50 = SMAIndicator(close, window=50).sma_indicator().iloc[-1]
    sma200 = SMAIndicator(close, window=200).sma_indicator().iloc[-1]
    bb = BollingerBands(close)
    bb_high = bb.bollinger_hband().iloc[-1]
    bb_low = bb.bollinger_lband().iloc[-1]
    
    current_price = close.iloc[-1]
    
    # Sinyal Üretimi (Basit Algoritma)
    score = 0
    signal_txt = "NÖTR"
    
    if rsi < 30: score += 2 # Aşırı Satım (Al Fırsatı)
    if rsi > 70: score -= 2 # Aşırı Alım (Sat Fırsatı)
    if current_price > sma200: score += 1 # Trend Pozitif
    if current_price < bb_low: score += 1 # Alt bandı deldi (Tepki gelebilir)
    
    if score >= 2: signal_txt = "GÜÇLÜ AL"
    elif score == 1: signal_txt = "AL"
    elif score <= -2: signal_txt = "SAT"
    elif score == -1: signal_txt = "ZAYIF"
    
    # Destek/Direnç (Pivotlar)
    high = df_stock['High'].iloc[-1]
    low = df_stock['Low'].iloc[-1]
    pivot = (high + low + current_price) / 3
    r1 = (2 * pivot) - low
    s1 = (2 * pivot) - high
    
    return {
        "Fiyat": current_price,
        "RSI": rsi,
        "SMA200": sma200,
        "Sinyal": signal_txt,
        "Pivot": pivot,
        "Destek 1": s1,
        "Direnç 1": r1,
        "ATH": df_stock['High'].max(),
        "ATL": df_stock['Low'].min()
    }

# --- ARAYÜZ ---
st.title("🚀 Finansal Hafıza & AI Trader")
st.markdown("*Profesyonel Piyasa Takip ve Portföy Yönetim Sistemi*")

# Verileri Çek
if portfolio_tickers:
    with st.spinner("Piyasa taranıyor..."):
        market_data = fetch_market_data(portfolio_tickers)

    # Özet Tablo Hazırlığı
    summary_data = []
    alerts = []

    for ticker in portfolio_tickers:
        # Veri Ayrıştırma
        if len(portfolio_tickers) > 1:
            stock_df = market_data[ticker]
        else:
            stock_df = market_data # Tek hisse varsa yapı farklıdır
            
        stock_df = stock_df.dropna()
        tech = get_technical_signals(stock_df)
        
        if tech:
            # Portföy Durumu
            qty, avg_cost, realized = calculate_portfolio_cost(portfolio[ticker]['transactions'])
            current_val = qty * tech['Fiyat']
            unrealized_pl = current_val - (qty * avg_cost)
            
            # ATH Kontrolü (%2 bandı)
            ath_dist = ((tech['ATH'] - tech['Fiyat']) / tech['ATH']) * 100
            if ath_dist < 2:
                alerts.append(f"🚨 **{ticker}** Zirveye Çok Yakın (ATH)! Kar Realizasyonu Düşün.")
            
            summary_data.append({
                "Kod": ticker,
                "Sinyal": tech['Sinyal'],
                "Fiyat": tech['Fiyat'],
                "RSI": tech['RSI'],
                "Adet": qty,
                "Ort. Maliyet": avg_cost,
                "Anlık Değer": current_val,
                "Kar/Zarar": unrealized_pl,
                "ATH Fark %": ath_dist
            })

    # 1. ALARMLAR
    if alerts:
        st.error("\n".join(alerts))

    # 2. ANA TABLO
    st.subheader("📊 Piyasa Görünümü")
    df_summary = pd.DataFrame(summary_data)
    
    if not df_summary.empty:
        # Renklendirme Fonksiyonu
        def highlight_signal(val):
            color = 'white'
            if 'AL' in val: color = '#90ee90' # Yeşil
            elif 'SAT' in val: color = '#ffcccb' # Kırmızı
            return f'background-color: {color}; color: black'

        st.dataframe(
            df_summary.style.applymap(highlight_signal, subset=['Sinyal'])
            .format({
                "Fiyat": "{:.2f}", 
                "RSI": "{:.1f}", 
                "Ort. Maliyet": "{:.2f}",
                "Anlık Değer": "{:.2f}", 
                "Kar/Zarar": "{:.2f}",
                "ATH Fark %": "%{:.1f}"
            }),
            use_container_width=True,
            selection_mode="single-row",
            on_select="rerun",
            key="dashboard_table"
        )
    
    # 3. DETAY EKRANI (Seçime Göre)
    selected_row = st.session_state.dashboard_table.get("selection", {}).get("rows", [])
    if selected_row:
        selected_index = selected_row[0]
        selected_ticker = df_summary.iloc[selected_index]["Kod"]
        
        st.divider()
        st.header(f"🔎 Detay Analiz: {selected_ticker}")
        
        # Sekmeli Yapı
        tab1, tab2, tab3 = st.tabs(["📈 Teknik & Grafik", "🤖 AI & Temel", "💰 İşlemlerim"])
        
        # --- TAB 1: GRAFİK & TEKNİK ---
        with tab1:
            col_chart, col_levels = st.columns([3, 1])
            
            with col_chart:
                timeframe = st.radio("Zaman Dilimi:", ["Günlük", "Haftalık"], horizontal=True)
                # Grafik verisi hazırlama
                if len(portfolio_tickers) > 1:
                    chart_df = market_data[selected_ticker].copy()
                else:
                    chart_df = market_data.copy()
                
                if timeframe == "Haftalık":
                    chart_df = chart_df.resample('W').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'})

                # Candlestick
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=chart_df.index, open=chart_df['Open'], high=chart_df['High'], 
                                            low=chart_df['Low'], close=chart_df['Close'], name='Fiyat'), row=1, col=1)
                
                # SMA Ekle
                chart_df['SMA50'] = chart_df['Close'].rolling(window=50).mean()
                fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['SMA50'], line=dict(color='orange', width=1), name='SMA 50'), row=1, col=1)
                
                # RSI Ekle
                delta = chart_df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                chart_df['RSI'] = 100 - (100 / (1 + rs))
                
                fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['RSI'], line=dict(color='purple', width=1), name='RSI'), row=2, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
                
                fig.update_layout(height=500, xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
            
            with col_levels:
                st.subheader("Destek / Direnç")
                tech_data = get_technical_signals(market_data[selected_ticker] if len(portfolio_tickers)>1 else market_data)
                st.metric("Pivot", f"{tech_data['Pivot']:.2f}")
                st.metric("Direnç (R1)", f"{tech_data['Direnç 1']:.2f}", delta_color="normal")
                st.metric("Destek (S1)", f"{tech_data['Destek 1']:.2f}", delta_color="inverse")
                st.info(f"SMA 200: {tech_data['SMA200']:.2f}\n(Uzun Vadeli Trend Hattı)")

        # --- TAB 2: AI & TEMEL ---
        with tab2:
            st.subheader(f"🤖 Gemini Uzman Görüşü: {selected_ticker}")
            if st.button("Analizi Başlat (AI)"):
                if api_key:
                    with st.spinner("Piyasa verileri taranıyor, makro ekonomik verilerle birleştiriliyor..."):
                        prompt = f"""
                        Sen dünyanın en iyi finans analistisin. {selected_ticker} hissesi için şu teknik verilere bak:
                        Fiyat: {tech_data['Fiyat']}, RSI: {tech_data['RSI']}, Sinyal: {tech_data['Sinyal']}.
                        
                        Lütfen şunları yap:
                        1. Hissenin temel analiz özetini yap (Sektör durumu, şirket ne iş yapar).
                        2. Makro ekonomik koşullar altında (Faizler, enflasyon vb.) bu hissenin görünümü nedir?
                        3. Teknik verilere dayanarak kısa ve orta vade strateji önerisi ver.
                        
                        Cevabı Türkçe, profesyonel, maddeler halinde ve yatırımcı dostu bir dille ver.
                        """
                        try:
                            model = genai.GenerativeModel('gemini-pro')
                            response = model.generate_content(prompt)
                            st.markdown(response.text)
                        except Exception as e:
                            st.error(f"Hata: {e}")
                else:
                    st.warning("Lütfen sol menüden API anahtarını girin.")

        # --- TAB 3: İŞLEMLER & MALİYET ---
        with tab3:
            st.subheader("💰 İşlem Geçmişi & Maliyet Yönetimi")
            
            c1, c2 = st.columns(2)
            with c1:
                # Yeni İşlem Ekleme
                with st.form("transaction_form"):
                    tr_type = st.selectbox("İşlem Tipi", ["ALIS", "SATIS"])
                    tr_date = st.date_input("Tarih", datetime.now())
                    tr_qty = st.number_input("Adet", min_value=1.0, step=1.0)
                    tr_price = st.number_input("Birim Fiyat", min_value=0.0, step=0.1)
                    
                    if st.form_submit_button("İşlemi Kaydet"):
                        portfolio[selected_ticker]['transactions'].append({
                            "date": str(tr_date),
                            "type": tr_type,
                            "qty": tr_qty,
                            "price": tr_price
                        })
                        save_portfolio(portfolio)
                        st.success("İşlem eklendi!")
                        st.rerun()

            with c2:
                # Geçmiş Listesi
                tr_list = portfolio[selected_ticker]['transactions']
                if tr_list:
                    st.table(pd.DataFrame(tr_list))
                    qty, avg, realized = calculate_portfolio_cost(tr_list)
                    st.metric("Toplam Adet", f"{qty}")
                    st.metric("Ortalama Maliyet", f"{avg:.2f}")
                    st.metric("Realize Edilmiş (Cepteki) Kar/Zarar", f"{realized:.2f}", delta=realized)
                else:
                    st.info("Henüz işlem girişi yapılmadı.")

else:
    st.info("Portföy boş. Soldan hisse ekleyerek başlayın.")
