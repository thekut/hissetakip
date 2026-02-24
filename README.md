# ⚠️ PROJECT FROZEN / PROJE DONDURULDU ⚠️
Bu proje şu anda dondurulmuş durumdadır ve artık aktif olarak geliştirilmemektedir. Lütfen aşağıdaki eski README içeriğine dikkat edin. / This project is currently frozen and no longer actively developed. Please refer to the archived README content below.

---

# 📈 Hisse Takip & AI Portföy Analisti

Bu proje, Amerikan borsalarındaki (veya ekleyeceğiniz diğer) hisseleri takip etmenizi, teknik analiz yapmanızı ve **Google Gemini Yapay Zekası** ile portföy yorumu almanızı sağlayan bir Streamlit uygulamasıdır.

## 🚀 Özellikler

*   **Canlı Veri Takibi:** Yahoo Finance üzerinden anlık fiyat ve değişim takibi.
*   **Portföy Yönetimi:** Alış fiyatı ve adet girerek Kâr/Zarar durumu görüntüleme.
*   **Teknik Analiz:** Otomatik RSI ve Hareketli Ortalama (SMA) hesaplamaları.
*   **Yapay Zeka Desteği:** Portföy tablonuzu tek tuşla Google Gemini AI'a yorumlatın.
*   **Akıllı Uyarılar:** Hisse fiyatı Zirveye (ATH) veya Dibe (ATL) yaklaştığında otomatik alarm.
*   **İnteraktif Grafikler:** Plotly ile detaylı mum grafikleri.

## 🛠️ Kurulum (Kendi Bilgisayarınızda)

1.  Proje dosyalarını indirin.
2.  Gerekli kütüphaneleri yükleyin:
    ```bash
    pip install -r requirements.txt
    ```
3.  Uygulamayı çalıştırın:
    ```bash
    streamlit run app.py
    ```

## 🌐 İnternette Yayınlama (Streamlit Cloud)

Bu projeyi **ücretsiz** olarak internette yayınlamak için:

1.  Bu projeyi GitHub hesabınızda barındırın (Şu an zaten oradasınız!).
2.  [share.streamlit.io](https://share.streamlit.io/) adresine gidin.
3.  **"New App"** butonuna tıklayın.
4.  **Repository:** `KullanıcıAdınız/ProjeAdınız` seçin.
5.  **Main file path:** `app.py` yazın.
6.  **Deploy** butonuna basın.

## 🔑 API Anahtarı
Yapay zeka özelliklerini kullanmak için [Google AI Studio](https://aistudio.google.com/app/apikey) adresinden ücretsiz bir API anahtarı alıp, uygulama menüsüne girmeniz gerekmektedir.
