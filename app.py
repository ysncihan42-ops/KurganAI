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
        # requests ve session kısımlarını sildik, işlemi YF'ye bıraktık:
        ticker = yf.Ticker(ticker_id)

        # Fiyat Çekimi
        price = None
        try:
            fast = ticker.fast_info
            price = fast.get("last_price") or fast.get("regular_market_price")
        except:
            pass

        if not price:
            try:
                info = ticker.get_info()
                price = info.get("currentPrice") or info.get("regularMarketPrice")
            except:
                info = {}

        if not price:
            hist = ticker.history(period="1d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])

        if not price:
            return None, "🚫 Fiyat verisi alınamadı."

        # Finansallar
        try:
            if 'info' not in locals():
                info = ticker.get_info()
        except:
            info = {}

        eps = info.get("trailingEps")
        bvps = info.get("bookValue")
        pe = info.get("trailingPE")
        pb = info.get("priceToBook")
        roe = info.get("returnOnEquity")
        payout_ratio = info.get("payoutRatio")
        ev_ebitda = info.get("enterpriseToEbitda")

        roa = info.get("returnOnAssets")
        ocf = info.get("operatingCashflow")
        net_income = info.get("netIncomeToCommon")
        dte = info.get("debtToEquity")
        current_ratio = info.get("currentRatio")
        quick_ratio = info.get("quickRatio")
        op_margins = info.get("operatingMargins")
        fcf = info.get("freeCashflow")

        eps = float(eps) if eps and eps > 0 else None
        bvps = float(bvps) if bvps and bvps > 0 else None

        return {
            "symbol": ticker_symbol.upper(),
            "price": float(price),
            "eps": eps,
            "book_value_ps": bvps,
            "pe": pe,
            "pb": pb,
            "roe": roe,
            "payout_ratio": payout_ratio,
            "ev_ebitda": ev_ebitda,
            "roa": roa,
            "ocf": ocf,
            "net_income": net_income,
            "dte": dte,
            "current_ratio": current_ratio,
            "quick_ratio": quick_ratio,
            "op_margins": op_margins,
            "fcf": fcf
        }, None

    except Exception as e:
        return None, f"Veri Hatası: {str(e)}"

# --- HESAPLAMA FONKSİYONLARI ---
def calculate_graham(eps, bvps):
    try:
        if eps is None or bvps is None or eps <= 0 or bvps <= 0: return None
        return math.sqrt(22.5 * eps * bvps)
    except: return None

def calculate_graham_intrinsic(eps, growth_rate, current_yield):
    try:
        if eps is None or eps <= 0 or current_yield is None or current_yield <= 0: return None
        if growth_rate is None: growth_rate = 0
        return (eps * (8.5 + 1 * growth_rate) * 4.4) / current_yield
    except: return None

def calculate_sgr(roe, payout_ratio):
    try:
        if roe is None: return None
        pr = payout_ratio if payout_ratio is not None else 0.0
        sgr = roe * (1 - pr) * 100
        return max(sgr, 0)
    except: return None

def calculate_peg(pe, growth_rate):
    try:
        if pe is None or growth_rate is None or growth_rate <= 0 or pe <= 0: return None
        return pe / growth_rate
    except: return None

def calculate_health_score(data):
    score = 0
    try:
        if data.get("roa") and data["roa"] > 0: score += 1
        if data.get("roe") and data["roe"] > 0: score += 1
        if data.get("ocf") and data["ocf"] > 0: score += 1
        if data.get("ocf") and data.get("net_income") and data["ocf"] > data["net_income"]: score += 1
        if data.get("dte") is not None and data["dte"] < 100: score += 1
        if data.get("current_ratio") and data["current_ratio"] > 1.2: score += 1
        if data.get("quick_ratio") and data["quick_ratio"] > 0.9: score += 1
        if data.get("op_margins") and data["op_margins"] > 0.10: score += 1
        if data.get("fcf") and data["fcf"] > 0: score += 1
        return score
    except: return None

def format_number(val):
    if val is None: return "N/A"
    return f"{val:.2f}"

# --- TABLO RENKLENDİRME ---
def highlight_anomalies(row):
    styles = [''] * len(row)
    
    if 'FD/FAVÖK' in row.index:
        ev_val = row['FD/FAVÖK']
        ev_idx = row.index.get_loc('FD/FAVÖK')
        if pd.notna(ev_val):
            if ev_val < 0 or ev_val > 20: styles[ev_idx] = 'background-color: #ffcccc; color: #a00000;'
            elif ev_val < 8: styles[ev_idx] = 'background-color: #ccffcc; color: #006000;'
                
    if 'PEG Rasyosu' in row.index:
        peg_val = row['PEG Rasyosu']
        peg_idx = row.index.get_loc('PEG Rasyosu')
        if pd.notna(peg_val):
            if peg_val < 0 or peg_val > 3: styles[peg_idx] = 'background-color: #ffcccc; color: #a00000;'
            elif peg_val <= 1: styles[peg_idx] = 'background-color: #ccffcc; color: #006000;'
                
    if 'Sağlık (9)' in row.index:
        health_val = row['Sağlık (9)']
        health_idx = row.index.get_loc('Sağlık (9)')
        if pd.notna(health_val):
            if health_val >= 7: styles[health_idx] = 'background-color: #ccffcc; color: #006000;'
            elif health_val <= 3: styles[health_idx] = 'background-color: #ffcccc; color: #a00000;'
                
    return styles

# --- OTONOM YORUMLAMA MOTORU ---
def generate_ai_commentary(peg, ev_ebitda, sgr, graham, price, health_score):
    comments = []
    
    if health_score is not None:
        if health_score >= 7: comments.append(f"🛡️ **FİNANSAL KALE (Skor: {health_score}/9):** Şirketin bilançosu, nakit akışı ve kârlılık rasyoları mükemmel seviyede. İflas veya finansal sıkıntı riski oldukça düşük.")
        elif health_score <= 3: comments.append(f"🆘 **FİNANSAL RİSK (Skor: {health_score}/9):** Şirketin finansal sağlığı alarm veriyor! Likidite sorunları, yüksek borçluluk veya zayıf nakit akışı var. Bu bir 'Değer Tuzağı' (Value Trap) olabilir.")
        else: comments.append(f"⚖️ **ORTALAMA SAĞLIK (Skor: {health_score}/9):** Şirket finansal olarak ayakta ancak likidite veya nakit akışında bazı zayıflıklar barındırıyor.")

    if peg is not None and ev_ebitda is not None:
        if peg <= 1.0 and ev_ebitda > 20: comments.append("🚨 **DEĞER TUZAĞI:** Hissenin PEG rasyosu çok ucuz görünse de, FD/FAVÖK oranı muazzam yüksek. Açıklanan kâr muhtemelen ana faaliyetlerinden gelmiyor.")
        elif peg <= 1.0 and ev_ebitda < 8: comments.append("✅ **ALTIN FIRSAT:** Şirket hem büyüme potansiyeline göre iskontolu (PEG < 1) hem de operasyonel olarak çok ucuz (FD/FAVÖK < 8).")
        elif peg > 2.0 and ev_ebitda > 12: comments.append("⚠️ **AŞIRI PRİMLİ:** Piyasa bu şirketin büyüme beklentisini fazlasıyla satın almış durumda. Pahalı fiyatlanıyor.")

    if sgr is not None:
        if sgr < 5: comments.append("ℹ️ **ZAYIF İÇSEL BÜYÜME:** Şirketin kendi özkaynaklarıyla büyüme kapasitesi %5'in altında. Agresif büyüme için dış finansmana ihtiyaç duyabilir.")

    if graham and price:
        iskonto = ((graham - price) / graham) * 100
        if iskonto > 30: comments.append(f"🎯 **GÜVENLİK MARJI:** Graham varlık modeline göre şirket şu an %{iskonto:.1f} iskontolu işlem görüyor.")

    if not comments: comments.append("📊 Kurgan AI bu hisse için nötr veya ortalama değerler tespit etti. Ekstrem bir anomali görünmüyor.")
        
    return comments

# --- ARAYÜZ ---
st.title("🛡️ Kurgan AI: BIST Finansal Röntgen & Değerleme")
st.caption("Gelişmiş Değerleme, Çarpan Analizi ve Yapay Zeka Yorumlama Motoru")

# SEKME TANIMLAMALARI (3 SEKME)
tab1, tab2, tab3 = st.tabs(["🔍 Tekli Hisse Analizi", "📊 BIST 30 Ucuzluk & Sağlık Taraması", "📖 Rehber & Metodoloji"])

# --- SEKME 1: TEKLİ ANALİZ ---
with tab1:
    st.subheader("Nokta Atışı Hisse Analizi")

    col_input1, col_input2, col_input3 = st.columns(3)
    with col_input1: ticker_input = st.text_input("Hisse Kodu (Örn: THYAO):", value="THYAO")
    with col_input2: g_input = st.number_input("Beklenen Büyüme Oranı (%)", value=10.0, step=1.0)
    with col_input3: y_input = st.number_input("Beklenen Reel Faiz (%)", value=5.0, step=1.0)

    if st.button("Analiz Et", type="primary"):
        with st.spinner("Bilanço taranıyor, metrikler hesaplanıyor..."):
            data, err = fetch_financial_data(ticker_input)

        if err: st.warning(err)
        if not data: st.stop()

        calculated_sgr = calculate_sgr(data["roe"], data["payout_ratio"])
        graham_number = calculate_graham(data["eps"], data["book_value_ps"])
        graham_intrinsic_manual = calculate_graham_intrinsic(data["eps"], g_input, y_input)
        health_score = calculate_health_score(data)
        
        graham_intrinsic_sgr = None
        peg_sgr = None
        peg_manual = calculate_peg(data["pe"], g_input)
        
        if calculated_sgr is not None:
            graham_intrinsic_sgr = calculate_graham_intrinsic(data["eps"], calculated_sgr, y_input)
            peg_sgr = calculate_peg(data["pe"], calculated_sgr)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("💰 Güncel Fiyat", format_number(data["price"]) + " TL")
        col2.metric("📉 F/K", format_number(data["pe"]))
        sgr_text = f"%{calculated_sgr:.2f}" if calculated_sgr is not None else "N/A"
        col3.metric("🌱 SGR (Kapasite)", sgr_text)
        health_text = f"{health_score} / 9" if health_score is not None else "N/A"
        col4.metric("🏥 Sağlık Skoru", health_text)

        st.divider()

        st.subheader("Modern Değerleme Metrikleri (Lynch & Çarpanlar)")
        m1, m2, m3 = st.columns(3)
        ev_ebitda_val = format_number(data["ev_ebitda"])
        m1.metric("🏢 FD/FAVÖK", ev_ebitda_val)
        m2.metric(f"🎯 PEG (SGR {sgr_text} ile)", format_number(peg_sgr))
        m3.metric(f"🎯 PEG (Manuel %{g_input} ile)", format_number(peg_manual))

        st.divider()
        
        st.subheader("🤖 Kurgan AI Otonom Analiz")
        with st.container(border=True):
            comments = generate_ai_commentary(peg_sgr, data["ev_ebitda"], calculated_sgr, graham_number, data["price"], health_score)
            for comment in comments: st.markdown(comment)

        st.divider()

        st.subheader("Klasik İçsel Değer Modelleri (Graham)")
        r1, r2, r3 = st.columns(3)
        r1.metric("🛡️ Defansif Graham", format_number(graham_number) + " TL")
        r2.metric(f"🚀 İçsel Değer (Manuel %{g_input})", format_number(graham_intrinsic_manual) + " TL")
        r3.metric(f"🤖 İçsel Değer (SGR {sgr_text})", format_number(graham_intrinsic_sgr) + " TL")

# --- SEKME 2: TOPLU TARAMA ---
with tab2:
    st.subheader("BIST 30 Gelişmiş Ucuzluk & Sağlık Taraması")
    
    y_input_scan = st.number_input("Taramada Kullanılacak Reel Faiz Oranı (%)", value=5.0, step=1.0)

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
                gv = calculate_graham(data["eps"], data["book_value_ps"])
                sgr = calculate_sgr(data["roe"], data["payout_ratio"])
                peg = calculate_peg(data["pe"], sgr)
                ev_ebitda = data.get("ev_ebitda")
                health = calculate_health_score(data)

                iskonto = ((gv - data["price"]) / gv) * 100 if gv and data["price"] else None

                results.append({
                    "Hisse": symbol,
                    "Fiyat (TL)": round(data["price"], 2),
                    "Sağlık (9)": health,
                    "FD/FAVÖK": round(ev_ebitda, 2) if ev_ebitda else None,
                    "PEG Rasyosu": round(peg, 2) if peg else None,
                    "SGR (%)": round(sgr, 2) if sgr is not None else None,
                    "Defansif Graham": round(gv, 2) if gv else None,
                    "İskonto (%)": round(iskonto, 2) if iskonto else None
                })

            progress.progress((i + 1) / len(bist30_list))
            time.sleep(0.1)

        status.text("Analiz Tamamlandı!")

        if results:
            df = pd.DataFrame(results)
            df = df.sort_values(by="PEG Rasyosu", ascending=True)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Sonuçları CSV (Excel) Olarak İndir",
                data=csv,
                file_name='kurgan_ai_tarama_sonuclari.csv',
                mime='text/csv',
            )
            
            styled_df = df.style.apply(highlight_anomalies, axis=1)
            st.dataframe(styled_df, use_container_width=True)

        else:
            st.error("Veri çekilemedi. Yahoo Finance rate limit olabilir.")

# --- SEKME 3: REHBER VE METODOLOJİ ---
with tab3:
    st.markdown("""
    ## 🛡️ Kurgan AI: Kullanıcı Rehberi ve Metodoloji Notu

    Kurgan AI, klasik değer yatırımı felsefesini modern finansal çarpanlar ve algoritmik bilanço analizleriyle birleştiren analitik bir terminaldir. Ekranda gördüğünüz verilerin ne anlama geldiğini ve nasıl hesaplandığını aşağıda bulabilirsiniz.

    ---

    ### 1. Veri Kaynağı ve Zamanlama
    * **Veri Sağlayıcı:** Tüm finansal veriler ve anlık fiyatlar **Yahoo Finance (yfinance)** altyapısından çekilmektedir.
    * **Fiyat Güncelliği:** Borsa İstanbul işlem saatleri içerisinde fiyatlar 15-20 dakikalık gecikmeli olarak, piyasa kapalıyken ise son kapanış fiyatı üzerinden hesaplanır.
    * **Bilanço Güncelliği:** Ekranda kullanılan kâr, defter değeri, borç ve nakit akışı gibi veriler **Son 12 Aylık (TTM)** dönemi veya açıklanan **en güncel çeyreklik bilançoyu** baz alır. Yeni bir bilanço açıklandığında sistem otomatik güncellenir.

    ---

    ### 2. Büyüme ve Kalite Metrikleri

    **🌱 Sürdürülebilir Büyüme Oranı (SGR)**
    * **Ne Anlama Gelir?** Bir şirketin dışarıdan borç almadan, sadece kendi elde ettiği kârı içeride tutarak matematiksel olarak maksimum ne kadar büyüyebileceğini gösterir.
    * **Nasıl Hesaplanır?** Özsermaye Kârlılığı ile şirketin içeride tuttuğu kâr oranı çarpılır. SGR'nin %10'un üzerinde olması güçlü bir içsel büyüme motoruna işaret eder.

    **🏥 Finansal Sağlık Skoru (9 Üzerinden)**
    * **Ne Anlama Gelir?** Şirketin iflas riskini ve bilançosunun kalitesini ölçen algoritmik bir röntgendir (Piotroski F-Skoru mantığı).
    * **Nasıl Okunur?** * **7 - 9 Puan:** Finansal olarak çok sağlam, nakit üreten şirket.
      * **4 - 6 Puan:** Ortalama, kabul edilebilir risk seviyesi.
      * **0 - 3 Puan:** Yüksek risk barındıran, likidite veya borç sorunu yaşayan şirket. (Değer Tuzaklarına dikkat!)

    ---

    ### 3. Modern Değerleme Çarpanları

    **🎯 PEG Rasyosu (Peter Lynch Modeli)**
    * **Ne Anlama Gelir?** Şirketin mevcut F/K oranının, büyüme hızına bölünmesiyle bulunur. "Bu şirketin büyümesi için ne kadar fiyat ödüyorum?" sorusunun cevabıdır.
    * **Nasıl Okunur?** PEG değeri **1.0'ın altındaysa** şirket büyüme potansiyeline göre **ucuzdur**. 1.0 adil değer, 1.5 ve üzeri ise pahalıdır.

    **🏢 FD/FAVÖK (EV/EBITDA)**
    * **Ne Anlama Gelir?** Tek seferlik vergi veya finansman gelirleriyle şişen suni net kârları filtreler, ana faaliyet kârına odaklanır.
    * **Nasıl Okunur?** Genellikle **8'in altı ucuz** kabul edilir. Kurgan AI, bu değer 20'nin üzerindeyse şirketin operasyonel olarak aşırı pahalı olduğuna işaret eder.

    ---

    ### 4. Klasik İçsel Değer Modelleri (Benjamin Graham)

    **🛡️ Defansif Graham Rakamı**
    * **Ne Anlama Gelir?** Gelecekteki büyüme hayallerine kapılmaz; sadece geçmiş kâra ve şirketin sahip olduğu somut varlıklara (Defter Değeri) odaklanır. Güncel fiyat bu rakamın altındaysa "Güvenlik Marjı" yüksektir. Yüksek enflasyonda tek başına kullanılmamalıdır.

    **🚀 Büyüme Odaklı İçsel Değer**
    * **Ne Anlama Gelir?** Graham'ın büyüme faktörünü ve piyasadaki "fırsat maliyetini" (faiz oranlarını) denkleme kattığı revize edilmiş formülüdür. 
    * **Nasıl Okunur?** Yüksek enflasyonlu piyasalarda banka faizi yerine **"Beklenen Reel Faiz"** (Örn: %5 - %10) kullanılarak hesaplanması gerekir. Borsa İstanbul dinamikleri gereği büyüme çarpanı Kurgan AI tarafından daha muhafazakar (defansif) hale getirilmiştir.
    """)

# --- SIDEBAR (YASAL UYARI VE VERSİYON) ---
st.sidebar.markdown("---")
st.sidebar.caption("Kurgan AI v2.5")
st.sidebar.markdown("**Geliştirici:** Dr. Yasin CİHAN")

st.sidebar.warning(
    "⚠️ **YASAL UYARI**\n\n"
    "Bu program **Dr. Yasin CİHAN** tarafından tamamen akademik analiz ve eğitim amacıyla geliştirilmiştir.\n\n"
    "Burada yer alan hiçbir hesaplama, otonom yorum veya değerleme **kesinlikle yatırım tavsiyesi değildir.** "
    "Veri sağlayıcılardan (Yahoo Finance) kaynaklı anlık hatalar, gecikmeler veya eksik bilançolar olabilir. "
    "Lütfen herhangi bir işlem yapmadan önce verilerin doğruluğunu resmi kaynaklardan teyit ediniz."
)