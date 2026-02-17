import streamlit as st
import yfinance as yf
import pandas as pd
import math
import time

# --- KONFİGÜRASYON ---
st.set_page_config(
    page_title="Kurgan AI - Finansal Terminal",
    layout="wide",
    page_icon="🛡️"
)

# --- CACHE (HIZ + RATE LIMIT KORUMA) ---
@st.cache_data(ttl=600)
def fetch_financial_data(ticker_symbol):
    ticker_id = f"{ticker_symbol.upper()}.IS"

    try:
        ticker = yf.Ticker(ticker_id)

        # 1️⃣ FİYAT - ÇOK KAYNAKLI (EN STABİL YÖNTEM)
        price = None

        # Önce fast_info
        try:
            fast = ticker.fast_info
            price = fast.get("last_price") or fast.get("regular_market_price")
        except:
            pass

        # 2. fallback -> info
        if not price:
            try:
                info = ticker.get_info()
                price = info.get("currentPrice") or info.get("regularMarketPrice")
            except:
                info = {}

        # 3. fallback -> history (EN GÜVENİLİR)
        if not price:
            hist = ticker.history(period="1d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])

        # Hâlâ yoksa veri gerçekten yok
        if not price:
            return None, "🚫 Fiyat verisi alınamadı (Yahoo BIST verisini boş döndürdü)."

        # Finansallar (ayrı çekiyoruz çünkü bazen crash yapıyor)
        try:
            if 'info' not in locals():
                info = ticker.get_info()
        except:
            info = {}

        eps = info.get("trailingEps")
        bvps = info.get("bookValue")
        pe = info.get("trailingPE")
        pb = info.get("priceToBook")

        # Güvenli dönüşüm
        eps = float(eps) if eps and eps > 0 else None
        bvps = float(bvps) if bvps and bvps > 0 else None

        return {
            "symbol": ticker_symbol.upper(),
            "price": float(price),
            "eps": eps,
            "book_value_ps": bvps,
            "pe": pe,
            "pb": pb
        }, None

    except Exception as e:
        return None, f"Veri Hatası: {str(e)}"


def calculate_graham(eps, bvps):
    """Graham Intrinsic Value (defensive safe)"""
    try:
        if eps is None or bvps is None:
            return None
        if eps <= 0 or bvps <= 0:
            return None
        return math.sqrt(22.5 * eps * bvps)
    except:
        return None


def format_number(val):
    """None güvenli format"""
    if val is None:
        return "N/A"
    return f"{val:.2f}"


# --- ARAYÜZ ---
st.title("🛡️ Kurgan AI: BIST Değerleme & Tarama")
st.caption("Profesyonel Graham Değerleme Terminali")

# Sekmeler
tab1, tab2 = st.tabs(["🔍 Tekli Hisse Analizi", "📊 BIST 30 Ucuzluk Taraması"])

# --- SEKME 1 ---
with tab1:
    st.subheader("Nokta Atışı Hisse Analizi")

    ticker_input = st.text_input(
        "Hisse Kodu Giriniz (Örn: EREGL, THYAO):",
        value="EREGL"
    )

    if st.button("Analiz Et", type="primary"):
        with st.spinner("Veri çekiliyor..."):
            data, err = fetch_financial_data(ticker_input)

        if err:
            st.warning(err)

        if not data:
            st.stop()

        graham_val = calculate_graham(
            data["eps"],
            data["book_value_ps"]
        )

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("💰 Güncel Fiyat", format_number(data["price"]) + " TL")
        col2.metric("📊 EPS", format_number(data["eps"]))
        col3.metric("📚 BVPS", format_number(data["book_value_ps"]))
        col4.metric("📉 F/K", format_number(data["pe"]))

        st.divider()

        if graham_val:
            iskonto = ((graham_val - data["price"]) / graham_val) * 100

            r1, r2 = st.columns(2)
            r1.metric(
                "🧠 Graham İçsel Değeri",
                f"{graham_val:.2f} TL"
            )
            r2.metric(
                "📊 İskonto Oranı",
                f"%{iskonto:.2f}"
            )

            if iskonto > 30:
                st.success("🟢 Çok Ucuz (Deep Value)")
            elif iskonto > 0:
                st.info("🟡 İskontolu (Undervalued)")
            else:
                st.error("🔴 Pahalı (Overvalued)")
        else:
            st.error(
                "Graham hesaplanamadı. (EPS veya Defter Değeri negatif / veri yok)"
            )

# --- SEKME 2 ---
with tab2:
    st.subheader("BIST 30 Graham Ucuzluk Taraması")

    bist30_list = [
        "AKBNK", "ARCLK", "ASELS", "BIMAS", "EKGYO", "ENKAI", "EREGL",
        "FROTO", "GARAN", "GUBRF", "HALKB", "HEKTS", "ISCTR", "KCHOL",
        "KOZAA", "KOZAL", "KRDMD", "PETKM", "PGSUS", "SAHOL", "SASA",
        "SISE", "TAVHL", "TCELL", "THYAO", "TKFEN", "TOASO", "TUPRS",
        "VAKBN", "YKBNK"
    ]

    if st.button("🚀 Taramayı Başlat"):
        results = []
        progress = st.progress(0)
        status = st.empty()

        for i, symbol in enumerate(bist30_list):
            status.text(f"Analiz ediliyor: {symbol}")

            data, _ = fetch_financial_data(symbol)

            if data:
                gv = calculate_graham(
                    data["eps"],
                    data["book_value_ps"]
                )

                if gv and data["price"]:
                    iskonto = ((gv - data["price"]) / gv) * 100

                    results.append({
                        "Hisse": symbol,
                        "Fiyat (TL)": round(data["price"], 2),
                        "Graham Değeri": round(gv, 2),
                        "İskonto (%)": round(iskonto, 2),
                        "F/K": data["pe"]
                    })

            progress.progress((i + 1) / len(bist30_list))
            time.sleep(0.1)  # Rate limit koruma

        status.text("Analiz Tamamlandı!")

        if results:
            df = pd.DataFrame(results)
            df = df.sort_values(by="İskonto (%)", ascending=False)
            st.dataframe(df, use_container_width=True)

            st.success("En üstteki hisseler Graham modeline göre en ucuz olanlardır.")
        else:
            st.error("Veri çekilemedi. Yahoo Finance rate limit olabilir.")

# --- SIDEBAR ---
st.sidebar.markdown("---")
st.sidebar.write("🚀 **Geliştirici:** Dr. Yasin Cihan")
st.sidebar.caption("Kurgan AI v2.0 | © 2026")
st.sidebar.info(
    "Bu uygulama eğitim amaçlıdır. Yatırım tavsiyesi değildir."
)
