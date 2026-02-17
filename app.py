import streamlit as st
import yfinance as yf
# ... diğerleri ...
import requests # Bu kütüphane bazen kimlik doğrulamada işe yarar

# --- KONFİGÜRASYON ---
st.set_page_config(page_title="Kurgan AI - Finansal Terminal", layout="wide")

# --- VERİ ÇEKME FONKSİYONLARI ---
def fetch_financial_data(ticker_symbol):
    ticker_id = f"{ticker_symbol.upper()}.IS"
    
    # SUNUCU ENGELİNİ AŞMAK İÇİN ÖZEL AYAR (SESSION)
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'})
    
    ticker = yf.Ticker(ticker_id, session=session)
    
    try:
        # Önce hızlı veriyi deneyelim (Sunucuda daha az takılır)
        fast = ticker.fast_info
        price = fast.get('last_price')
        
        # Detaylı info'yu çekmeye çalışalım
        info = ticker.info
        
        if not info or len(info) < 5:
            if price: # Fiyat varsa ama diğerleri yoksa hata verme, kısıtlı göster
                return {
                    "symbol": ticker_symbol.upper(),
                    "price": price,
                    "eps": 0.0,
                    "book_value_ps": 0.0,
                    "pe": 0,
                    "pb": 0
                }, "⚠️ Yahoo sunucu yoğunluğu nedeniyle sadece fiyat çekilebildi."
            
            return None, "🚫 Yahoo şu an çok yoğun. Lütfen 1-2 dakika bekleyip tekrar deneyin."

        return {
            "symbol": ticker_symbol.upper(),
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "eps": info.get("trailingEps"),
            "book_value_ps": info.get("bookValue"),
            "pe": info.get("trailingPE"),
            "pb": info.get("priceToBook")
        }, None
    except Exception as e:
        return None, f"Hata: {str(e)}"

def calculate_graham(eps, bvps):
    if eps and bvps and eps > 0 and bvps > 0:
        return math.sqrt(22.5 * eps * bvps)
    return None

# --- ARAYÜZ ---
st.title("🛡️ Kurgan AI: BIST Değerleme & Tarama")

# Sekmeleri Oluşturma
tab1, tab2 = st.tabs(["🔍 Tekli Hisse Analizi", "📊 BIST 30 Ucuzluk Taraması"])

# --- SEKME 1: TEKLİ ANALİZ ---
with tab1:
    st.subheader("Nokta Atışı Analiz")
    ticker_input = st.text_input("Hisse Kodu Giriniz (Örn: EREGL, THYAO):", value="EREGL", key="single")
    if st.button("Analiz Et", key="btn_single"):
        data, err = fetch_financial_data(ticker_input)
        if err:
            st.warning(err)
            if not data: # Veri tamamen boşsa devam etme
                st.stop()
        
        # Veri varsa (veya kısıtlıysa) devam et
        graham_val = calculate_graham(data["eps"], data["book_value_ps"])
        c1, c2, c3 = st.columns(3)
        c1.metric("Güncel Fiyat", f"{data['price']} TL")
        c2.metric("Hisse Başı Kar (EPS)", f"{data['eps']:.2f}" if data['eps'] else "N/A")
        c3.metric("Defter Değeri (BVPS)", f"{data['book_value_ps']:.2f}" if data['book_value_ps'] else "N/A")

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
            st.error("Graham Değeri hesaplanamadı (Kâr veya Özsermaye negatif olabilir veya Yahoo veri vermiyor).")

# --- SEKME 2: TOPLU TARAMA ---
with tab2:
    st.subheader("BIST 30 İçindeki En Ucuz Hisseleri Bul")
    st.write("Bu işlem seçili hisselerin verilerini tek tek analiz eder.")
    
    bist30_list = ["AKBNK", "ARCLK", "ASELS", "BIMAS", "EKGYO", "ENKAI", "EREGL", "FROTO", "GARAN", "GUBRF", "HALKB", "HEKTS", "ISCTR", "KCHOL", "KOZAA", "KOZAL", "KRDMD", "PETKM", "PGSUS", "SAHOL", "SASA", "SISE", "TAVHL", "TCELL", "THYAO", "TKFEN", "TOASO", "TUPRS", "VAKBN", "YKBNK"]
    
    if st.button("Taramayı Başlat"):
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, s in enumerate(bist30_list):
            status_text.text(f"Analiz ediliyor: {s}")
            data, _ = fetch_financial_data(s)
            if data and data["eps"] and data["book_value_ps"]:
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
            time.sleep(0.05) # Yahoo'yu yormamak için çok kısa bekleme
        
        status_text.text("Analiz Tamamlandı!")
        if results:
            df = pd.DataFrame(results)
            df_sorted = df.sort_values(by="İskonto (%)", ascending=False)
            st.dataframe(df_sorted, use_container_width=True)
            st.info("💡 Not: İskonto oranı en yüksek olan hisseler, Graham modeline göre potansiyeli en yüksek olanlardır.")
        else:
            st.error("Hiçbir hisse için veri çekilemedi. Lütfen bir süre sonra tekrar deneyin.")
# --- SAYFA ALTI (SIDEBAR) ---
st.sidebar.markdown("---")
st.sidebar.write("🚀 **Geliştirici:**Dr. Yasin Cihan")
st.sidebar.caption("Kurgan AI v1.0 | © 2026")
st.sidebar.info("Bu uygulama eğitim amacıyla geliştirilmiştir. Yanlışlıklar ve hatalar olabilir lütfen bu uygulamaya güvenerek yatırım kararı almayınız")