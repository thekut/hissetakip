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
from datetime import datetime
import time

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Finansal Hafıza Pro", layout="wide", page_icon="🏦")

# --- BAŞLANGIÇ VERİLERİ (DEMO) ---
# Streamlit Cloud dosyaları sildiği için, boş kaldığında burayı yükleyecek.
DEFAULT_PORTFOLIO = {
    "NVDA": {"transactions": [{"date": "2024-01-15", "type": "ALIS", "qty": 10, "price": 450.0}], "sector": "Teknoloji"},
    "AAPL": {"transactions": [], "sector": "Teknoloji"},
    "THYAO.IS": {"transactions": [], "sector": "Havacılık"},
    "GOOGL": {"transactions": [], "sector": "Teknoloji"}
}

# --- SESSION STATE (OTURUM HAFIZASI) ---
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = DEFAULT_PORTFOLIO

def get_portfolio():
    return st.session_state.portfolio

def save_portfolio_state(new_data):
    st.session_state.portfolio = new_data

# --- HESAPLAMA FONKSİYONLARI ---
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

@st.cache_data(ttl=60) # 1 dk cache
def fetch_market_data(tickers):
    if not tickers: return pd.DataFrame()
    try:
        # Tekli veya çoklu indirme için string birleştirme
        tickers_str = " ".join(tickers)
        # auto_adjust=True ile bölünmeleri vs ayarlar
        data = yf.download(tickers_str, period="1y", group_by='ticker', auto_adjust=True, threads=True)
        return data
    except Exception as e:
        st.error(f"Veri çekme hatası: {e}")
        return pd.DataFrame()

def get_technical_signals(df_stock):
    """Teknik Analiz ve Sinyal Motoru"""
    try:
        if df_stock is None or df_stock.empty: return None
        # Veri yeterli mi kontrolü (en az 50 gün)
        if len(df_stock) < 50: return None 
        
        # Sadece Close sütunu varsa (Series) veya DataFrame ise ayır
        if isinstance(df_stock, pd.Series):
            close = df_stock
            high = df_stock # High yoksa close kullan
            low = df_stock # Low yoksa close kullan
        else:
            close = df_stock['Close']
            high = df_stock['High']
            low = df_stock['Low']

        # Boş verileri doldur
        close = close.ffill()

        # İndikatörler
        rsi_val = RSIIndicator(close).rsi().iloc[-1]
        
        # SMA (Hata önleyici: Veri uzunluğuna göre pencere ayarla)
        window_200 = 200 if len(close) > 200 else len(close)
        sma200 = SMAIndicator(close, window=window_200).sma_indicator().iloc[-1]
        
        bb = BollingerBands(close)
        bb_high = bb.bollinger_hband().iloc[-1]
        bb_low = bb.bollinger_lband().iloc[-1]
        
        current_price = close.iloc[-1]
        
        # Puanlama Algoritması
        score = 0
        
        if rsi_val < 30: score += 2
        elif rsi_val > 70: score -= 2
        
        if current_price > sma200: score += 1
        else: score -= 1
        
        if current_price <= bb_low * 1.01: score += 1 # Alt banda yakın
        if current_price >= bb_high * 0.99: score -= 1 # Üst banda yakın

        if score >= 2: signal_txt = "GÜÇLÜ AL 🟢"
        elif score == 1: signal_txt = "AL 🟢"
        elif score <= -2: signal_txt = "GÜÇLÜ SAT 🔴"
        elif score == -1: signal_txt = "SAT 🔴"
        else: signal_txt = "NÖTR ⚪"
        
        # Pivotlar
        pivot = (high.iloc[-1] + low.iloc[-1] + current_price) / 3
        r1 = (2 * pivot) - low.iloc[-1]
        s1 = (2 * pivot) - high.iloc[-1]
        
        ath = high.max()
        atl = low.min()
        
        return {
            "Fiyat": current_price,
            "RSI": rsi_val,
            "SMA200": sma200,
            "Sinyal": signal_txt,
            "Pivot": pivot,
            "Destek 1": s1,
            "Direnç 1": r1,
            "ATH": ath,
            "ATL": atl
        }
    except Exception as e:
        # st.error(f"Teknik analiz hatası: {e}") # Hata ayıklama için açılabilir
        return None

# --- SIDEBAR (KONTROL PANELİ) ---
st.sidebar.title("⚙️ Kontrol Paneli")

# API
api_key = st.sidebar.text_input("Gemini API Key (Opsiyonel)", type="password")
if api_key: genai.configure(api_key=api_key)

st.sidebar.markdown("---")
st.sidebar.subheader("Portföy Yönetimi")

current_portfolio = get_portfolio()
tickers_list = list(current_portfolio.keys())

# EKLEME
add_ticker = st.sidebar.text_input("Hisse Ekle (Kod)", placeholder="AAPL, THYAO.IS").strip().upper()
add_sector = st.sidebar.selectbox("Sektör", ["Teknoloji", "Finans", "Sanayi", "Enerji", "Emtia", "Diğer"])
if st.sidebar.button("➕ Listeye Ekle"):
    if add_ticker and add_ticker not in current_portfolio:
        current_portfolio[add_ticker] = {"transactions": [], "sector": add_sector}
        save_portfolio_state(current_portfolio)
        st.success(f"{add_ticker} eklendi.")
        st.rerun()

# ÇIKARMA
if tickers_list:
    rem_ticker = st.sidebar.selectbox("Hisse Çıkar", ["Seçiniz..."] + tickers_list)
    if st.sidebar.button("🗑️ Sil"):
        if rem_ticker != "Seçiniz..." and rem_ticker in current_portfolio:
            del current_portfolio[rem_ticker]
            save_portfolio_state(current_portfolio)
            st.warning(f"{rem_ticker} silindi.")
            st.rerun()

# --- ANA EKRAN ---
st.title("📈 Finansal Hafıza AI")
st.caption("Otomatik Teknik Analiz, Portföy Takibi ve Yapay Zeka Danışmanı")

if not tickers_list:
    st.warning("Portföy boş! Sol menüden hisse ekleyin.")
    st.stop()

# VERİ ÇEKME MODÜLÜ
with st.spinner("Piyasa verileri analiz ediliyor..."):
    raw_data = fetch_market_data(tickers_list)

summary_list = []
active_alerts = []

if not raw_data.empty:
    for t in tickers_list:
        try:
            # Veri Seçimi (DataFrame Karmaşasını Önleme)
            if len(tickers_list) == 1:
                # Tek hisse varsa yfinance doğrudan o hissenin verisini döner
                stock_data = raw_data
            else:
                # Çok hisse varsa MultiIndex döner, hisseyi seçmemiz lazım
                try:
                    stock_data = raw_data[t]
                except KeyError:
                    continue # Veri gelmediyse atla

            # Veri Temizliği
            stock_data = stock_data.dropna(subset=['Close'])
            if stock_data.empty: continue

            # Analiz
            tech = get_technical_signals(stock_data)
            
            if tech:
                # Portföy Hesapla
                qty, avg_cost, realized = calculate_portfolio_cost(current_portfolio[t]['transactions'])
                current_val = qty * tech['Fiyat']
                unrealized_pl = current_val - (qty * avg_cost)
                
                # ATH Alarmı
                ath_dist = ((tech['ATH'] - tech['Fiyat']) / tech['ATH']) * 100
                if ath_dist < 2.5: # %2.5 yakınlıktaysa
                    active_alerts.append(f"🚨 **{t}** Zirveye (ATH) çok yakın! (Fark: %{ath_dist:.1f})")
                
                # Tablo Verisi
                summary_list.append({
                    "Kod": t,
                    "Sektör": current_portfolio[t]['sector'],
                    "Fiyat": tech['Fiyat'],
                    "Değişim %": ((tech['Fiyat'] - stock_data['Close'].iloc[-2])/stock_data['Close'].iloc[-2])*100,
                    "Sinyal": tech['Sinyal'],
                    "RSI": tech['RSI'],
                    "Adet": qty,
                    "Ort. Mal.": avg_cost,
                    "Kar/Zarar": unrealized_pl
                })
        except Exception as e:
            # st.error(f"{t} analiz hatası: {e}") 
            continue

# ALARMLAR
if active_alerts:
    with st.expander("🔔 AKTİF PİYASA ALARMLARI", expanded=True):
        for alert in active_alerts:
            st.markdown(alert)

# ANA TABLO
if summary_list:
    df_sum = pd.DataFrame(summary_list)
    
    # Stil Fonksiyonları
    def color_signal(val):
        color = ''
        if 'GÜÇLÜ AL' in val: color = '#2E8B57' # Koyu Yeşil
        elif 'AL' in val: color = '#90EE90' # Açık Yeşil
        elif 'SAT' in val: color = '#CD5C5C' # Kırmızı
        return f'background-color: {color}; color: black'

    st.subheader("📊 Canlı Piyasa Özeti")
    st.dataframe(
        df_sum.style.applymap(color_signal, subset=['Sinyal'])
        .format({
            "Fiyat": "{:.2f}",
            "Değişim %": "%{:.2f}",
            "RSI": "{:.1f}",
            "Ort. Mal.": "{:.2f}",
            "Kar/Zarar": "{:.2f}"
        }),
        use_container_width=True,
        selection_mode="single-row",
        on_select="rerun",
        key="main_table"
    )
    
    # DETAY GÖRÜNÜMÜ
    selected_rows = st.session_state.main_table.get("selection", {}).get("rows", [])
    if selected_rows:
        sel_idx = selected_rows[0]
        sel_ticker = df_sum.iloc[sel_idx]["Kod"]
        
        st.divider()
        st.header(f"🔍 Detaylar: {sel_ticker}")
        
        # Sekmeler
        tab1, tab2, tab3 = st.tabs(["📉 Grafik & Analiz", "🧠 AI Yorumu", "💵 Al/Sat İşlemleri"])
        
        # --- TAB 1: GRAFİK ---
        with tab1:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                # Veriyi tekrar al (temiz)
                if len(tickers_list) == 1: s_data = raw_data
                else: s_data = raw_data[sel_ticker]
                
                # Grafik Tipi
                period_opt = st.radio("Periyot", ["Günlük", "Haftalık"], horizontal=True)
                if period_opt == "Haftalık":
                    s_data = s_data.resample('W').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'})
                
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.1)
                
                # Mum Grafiği
                fig.add_trace(go.Candlestick(x=s_data.index, open=s_data['Open'], high=s_data['High'],
                                low=s_data['Low'], close=s_data['Close'], name="Fiyat"), row=1, col=1)
                
                # SMA
                sma50 = s_data['Close'].rolling(window=50).mean()
                sma200 = s_data['Close'].rolling(window=200).mean()
                fig.add_trace(go.Scatter(x=s_data.index, y=sma50, line=dict(color='orange', width=1), name="SMA 50"), row=1, col=1)
                fig.add_trace(go.Scatter(x=s_data.index, y=sma200, line=dict(color='blue', width=2), name="SMA 200"), row=1, col=1)
                
                # RSI
                delta = s_data['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi_series = 100 - (100 / (1 + rs))
                
                fig.add_trace(go.Scatter(x=s_data.index, y=rsi_series, line=dict(color='purple'), name="RSI"), row=2, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
                
                fig.update_layout(height=500, xaxis_rangeslider_visible=False, title=f"{sel_ticker} Teknik Görünüm")
                st.plotly_chart(fig, use_container_width=True)
                
            with col2:
                st.subheader("Seviyeler")
                # Tekrar hesapla veya cacheden al
                t_sig = get_technical_signals(s_data)
                if t_sig:
                    st.metric("Sinyal", t_sig['Sinyal'])
                    st.metric("Pivot", f"{t_sig['Pivot']:.2f}")
                    st.metric("Direnç 1", f"{t_sig['Direnç 1']:.2f}")
                    st.metric("Destek 1", f"{t_sig['Destek 1']:.2f}")
                    st.info(f"SMA 200 Trendi: {'YÜKSELİŞ' if t_sig['Fiyat'] > t_sig['SMA200'] else 'DÜŞÜŞ'}")

        # --- TAB 2: AI ---
        with tab2:
            st.subheader("Yapay Zeka Asistanı")
            user_q = st.text_area("Hisse ile ilgili sorunuz:", placeholder=f"{sel_ticker} için kısa vadeli beklenti nedir?")
            if st.button("AI'ya Sor"):
                if api_key:
                    with st.spinner("Gemini analiz ediyor..."):
                        t_sig = get_technical_signals(s_data) # Güncel veriyi al
                        prompt = f"""
                        Finans uzmanı olarak şu hisseyi yorumla: {sel_ticker}.
                        Fiyat: {t_sig['Fiyat']}, RSI: {t_sig['RSI']}, Sinyal Durumu: {t_sig['Sinyal']}.
                        Soru: {user_q if user_q else 'Genel teknik ve temel değerlendirme yap.'}
                        """
                        try:
                            model = genai.GenerativeModel('gemini-pro')
                            resp = model.generate_content(prompt)
                            st.markdown(resp.text)
                        except Exception as e:
                            st.error(f"API Hatası: {e}")
                else:
                    st.warning("API Anahtarı gerekli.")

        # --- TAB 3: İŞLEMLER ---
        with tab3:
            st.subheader("Al/Sat İşlemi Gir")
            c1, c2 = st.columns(2)
            with c1:
                with st.form("trade_form"):
                    t_type = st.selectbox("İşlem", ["ALIS", "SATIS"])
                    t_date = st.date_input("Tarih", datetime.now())
                    t_qty = st.number_input("Adet", min_value=1.0)
                    t_price = st.number_input("Fiyat", min_value=0.0, value=float(s_data['Close'].iloc[-1]))
                    
                    if st.form_submit_button("Kaydet"):
                        current_portfolio[sel_ticker]['transactions'].append({
                            "date": str(t_date), "type": t_type, "qty": t_qty, "price": t_price
                        })
                        save_portfolio_state(current_portfolio)
                        st.success("İşlem kaydedildi!")
                        st.rerun()
            
            with c2:
                st.write("Geçmiş İşlemler")
                tr_hist = current_portfolio[sel_ticker]['transactions']
                if tr_hist:
                    st.dataframe(pd.DataFrame(tr_hist))
                else:
                    st.info("İşlem yok.")

else:
    st.error("Veri alınamadı. Hisse kodlarını kontrol edin.")
