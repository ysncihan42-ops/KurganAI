import streamlit as st
import yfinance as yf
import pandas as pd
import math
import time

# --- KONFİGÜRASYON ---
st.set_page_config(page_title="Kurgan AI - Finansal Terminal", layout="wide")

# --- VERİ ÇEKME FONKSİYONLARI ---
def fetch_financial_data(ticker_symbol):
    ticker_id = f"{ticker_symbol.upper()}.IS"
    ticker = yf.Ticker(ticker_id)
    try:
        info = ticker.info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if not price:
            return None, "Fiyat verisi alınamadı."

        eps = info.get("trailingEps")
        bvps = info.get("bookValue")

        # Bilançodan manuel BVPS hesaplama (Eğer Yahoo boş dönerse)
        if bvps is None:
            bs = ticker.balance_sheet
            if not bs.empty:
                total_equity = bs.iloc[0].get("Total Assets", 0) - bs.iloc[0].get("Total Liabilities Net Minority Interest", 0)
                shares = info.get("sharesOutstanding")
                if shares: bvps = total_equity / shares

        return {
            "symbol": ticker_symbol.upper(),
            "price": price,
            "eps": eps,
            "book_value_ps": bvps,
            "pe": info.get("trailingPE"),
            "pb": info.get("priceToBook"),
            "name": info.get("longName", ticker_symbol)
        }, None
    except:
        return None, "Veri çekme hatası."

def calculate_graham(eps, bvps):
    if eps and bvps and eps > 0 and bvps > 0:
        return math.sqrt(22.5 * eps * bvps)
    return None

# --- ARAYÜZ ---
st.title("🛡️ Kurgan AI: BIST Değerleme & Tarama")

# Sekmeleri Oluşturma
tab1, tab2 = st.tabs(["🔍 Tekli Hisse Analizi", "📊 BIST 30 Ucuzluk Taraması"])

# --- SEKME 1: TEKLİ ANALİZ (Mevcut Fonksiyon) ---
with tab1:
    st.subheader("Nokta Atışı Analiz")
    ticker_input = st.text_input("Hisse Kodu Giriniz (Örn: EREGL, THYAO):", value="EREGL", key="single")
    if st.button("Analiz Et", key="btn_single"):
        data, err = fetch_financial_data(ticker_input)
        if err: st.error(err)
        else:
            graham_val = calculate_graham(data["eps"], data["book_value_ps"])
            c1, c2, c3 = st.columns(3)
            c1.metric("Güncel Fiyat", f"{data['price']} TL")
            c2.metric("Hisse Başı Kar (EPS)", f"{data['eps']:.2f}")
            c3.metric("Defter Değeri (BVPS)", f"{data['book_value_ps']:.2f}")

            if graham_val:
                iskonto = ((graham_val - data['price']) / graham_val) * 100
                st.divider()
                res_c1, res_c2 = st.columns(2)
                res_c1.metric("Graham İçsel Değeri", f"{graham_val:.2f} TL", f"%{iskonto:.2f} İskonto")
                if iskonto > 0:
                    st.success(f"Bu hisse Graham modeline göre %{iskonto:.2f} oranında **İSKONTOLU** görünmektedir.")
                else:
                    st.warning(f"Bu hisse Graham modeline göre %{abs(iskonto):.2f} oranında **PRİMLİ** (pahalı) görünmektedir.")
            else:
                st.error("Graham Değeri hesaplanamadı (Kâr veya Özsermaye negatif olabilir).")

# --- SEKME 2: TOPLU TARAMA (Yeni Fonksiyon) ---
with tab2:
    st.subheader("BIST 30 İçindeki En Ucuz Hisseleri Bul")
    st.write("Bu işlem seçili hisselerin verilerini tek tek analiz eder.")
    
    bist30_list = ["AKBNK", "ARCLK", "ASELS", "BIMAS", "EKGYO", "ENKAI", "EREGL", "FROTO", "GARAN", "GUBRF", "HALKB", "HETSH", "ISCTR", "KCHOL", "KOZAA", "KOZAL", "KARDM", "PETKM", "PGSUS", "SAHOL", "SASA", "SISE", "TAVHL", "TCELL", "THYAO", "TKFEN", "TOASO", "TUPRS", "VAKBN", "YKBNK"]
    
    if st.button("Taramayı Başlat"):
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, s in enumerate(bist30_list):
            status_text.text(f"Analiz ediliyor: {s}")
            data, _ = fetch_financial_data(s)
            if data:
                gv = calculate_graham(data["eps"], data["book_value_ps"])
                if gv:
                    iskonto = ((gv - data["price"]) / gv) * 100
                    results.append({
                        "Hisse": s,
                        "Fiyat": data["price"],
                        "Graham Değeri": round(gv, 2),
                        "İskonto (%)": round(iskonto, 2)
                    })
            progress_bar.progress((idx + 1) / len(bist30_list))
            time.sleep(0.1) # Yahoo'yu yormamak için kısa bekleme
        
        status_text.text("Analiz Tamamlandı!")
        df = pd.DataFrame(results)
        # Sadece iskontolu olanları göster ve en yüksek iskontoya göre sırala
        df_sorted = df.sort_values(by="İskonto (%)", ascending=False)
        
        st.dataframe(df_sorted, use_container_width=True)
        st.info("💡 Not: İskonto oranı en yüksek olan hisseler, Graham modeline göre potansiyeli en yüksek olanlardır.")