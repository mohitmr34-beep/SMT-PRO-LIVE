import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from urllib.parse import unquote

# -------------------------------
# APP CONFIG
# -------------------------------
st.set_page_config(page_title="SMT PRO AI Scanner", layout="wide")
st.title("📊 SMT PRO AI Trading Scanner (CSV Enabled)")

# -------------------------------
# STOCK SOURCE
# -------------------------------
source = st.radio(
    "📡 Stock Source",
    ["📂 Manual CSV (OLD)", "🟢 Chartink LIVE"],
    horizontal=True
)

# -------------------------------
# CSV MODE (UNCHANGED)
# -------------------------------
if source == "📂 Manual CSV (OLD)":

    uploaded_file = st.file_uploader("📂 Upload Stock List CSV", type=["csv"])

    if uploaded_file:
        df_symbols = pd.read_csv(uploaded_file)

        if "Symbol" in df_symbols.columns:
            symbols = [s.strip().upper() + ".NS" for s in df_symbols["Symbol"].dropna()]
        else:
            st.error("CSV must contain 'Symbol' column")
            st.stop()
    else:
        symbols = [
            "RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS","TCS.NS",
            "SBIN.NS","LT.NS","AXISBANK.NS","KOTAKBANK.NS","ITC.NS"
        ]

# -------------------------------
# CHARTINK LIVE MODE (FINAL FIX)
# -------------------------------
else:

    st.subheader("🟢 Chartink LIVE Scanner")

    chartink_cookie = st.text_input(
        "🔐 Chartink Cookie (REQUIRED)",
        type="password"
    )

    @st.cache_data(ttl=20)
    def get_chartink_symbols(cookie):

        if not cookie:
            raise Exception("Chartink cookie required")

        session = requests.Session()

        # Load cookie
        for part in cookie.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                session.cookies.set(k, v, domain="chartink.com")

        # Step 1: refresh session
        session.get("https://chartink.com")

        xsrf = unquote(session.cookies.get("XSRF-TOKEN", ""))

        if not xsrf:
            raise Exception("XSRF token missing → refresh cookie")

        headers = {
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
            "X-XSRF-TOKEN": xsrf,
            "Content-Type": "application/json",
            "Referer": "https://chartink.com/"
        }

        # 🔥 YOUR EXACT SCAN LOGIC (WORKING)
        payload = {
            "scan_clause": "( {cash} ( ( {cash} ( ( {cash} (  daily close >= daily max( 252 , daily high ) * 0.98 and daily volume > daily sma( daily volume , 20 ) * 1.5 and daily close > daily open ) ) or ( {cash} ( daily high >= daily max( 252 , daily high ) and daily close < daily open and daily volume > daily sma( daily volume , 20 ) * 1.5 ) ) or ( {cash} ( daily open > 1 day ago close * 1.02 and daily volume > daily sma( daily volume , 20 ) * 2 and daily close > daily open ) ) ) ) ) )"
        }

        res = session.post(
            "https://chartink.com/screener/process",
            headers=headers,
            json=payload
        )

        if res.status_code == 419:
            raise Exception("Session expired → update cookie")

        if res.status_code != 200:
            raise Exception(f"Chartink error {res.status_code}")

        data = res.json().get("data", [])

        symbols = []
        for row in data:
            sym = row.get("nsecode")
            if sym:
                symbols.append(sym.upper() + ".NS")

        if not symbols:
            raise Exception("No stocks returned")

        return symbols

    if st.button("🔄 Get LIVE Chartink Stocks"):
        try:
            symbols = get_chartink_symbols(chartink_cookie)
            st.session_state["symbols"] = symbols
            st.success(f"Loaded {len(symbols)} stocks")
        except Exception as e:
            st.error(f"Chartink LIVE fetch failed: {e}")
            st.stop()

    elif "symbols" in st.session_state:
        symbols = st.session_state["symbols"]
    else:
        st.info("Enter cookie → Click button")
        st.stop()

    st.dataframe(pd.DataFrame({"Stocks": symbols}), use_container_width=True)

# -------------------------------
# TIMEFRAME
# -------------------------------
timeframe = st.selectbox("Select Timeframe", ["5m", "15m", "1d"])

# -------------------------------
# DATA FETCH
# -------------------------------
@st.cache_data
def get_data(symbol, timeframe):
    try:
        df = yf.download(symbol, period="5d", interval=timeframe, progress=False)

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.dropna()

        if not all(col in df.columns for col in ["Open","High","Low","Close"]):
            return None

        return df
    except:
        return None

# -------------------------------
# AI LOGIC (UNCHANGED)
# -------------------------------
def analyze_stock(df):

    if df is None or len(df) < 50:
        return "NO DATA", None, None, None

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    close = float(latest["Close"])
    open_ = float(latest["Open"])
    high = float(latest["High"])
    low = float(latest["Low"])
    prev_close = float(prev["Close"])

    high_52 = float(df["High"].rolling(252).max().iloc[-1])

    signal = "WAIT"
    entry = sl = target = None

    # ATH Breakout
    if close >= 0.98 * high_52 and close > open_:
        signal = "BUY"
        entry = high
        sl = low
        target = entry + (entry - sl) * 2

    # ATH Rejection
    elif high >= high_52 and close < open_:
        signal = "SELL"
        entry = low
        sl = high
        target = entry - (sl - entry) * 2

    # Gap Momentum
    elif open_ > prev_close * 1.02:
        if close > open_:
            signal = "BUY"
        else:
            signal = "SELL"

        entry = high if signal == "BUY" else low
        sl = low if signal == "BUY" else high
        target = entry + (entry - sl) * 2 if signal == "BUY" else entry - (sl - entry) * 2

    return signal, entry, sl, target

# -------------------------------
# RUN SCANNER
# -------------------------------
if st.button("🚀 Run AI Scanner"):

    results = []

    for sym in symbols:
        df = get_data(sym, timeframe)
        signal, entry, sl, target = analyze_stock(df)

        results.append({
            "Stock": sym,
            "Signal": signal,
            "Entry": round(entry, 2) if entry else None,
            "SL": round(sl, 2) if sl else None,
            "Target": round(target, 2) if target else None
        })

    df_results = pd.DataFrame(results)

    st.subheader("📊 All Results")
    st.dataframe(df_results, use_container_width=True)

    best = df_results[df_results["Signal"].isin(["BUY","SELL"])].head(2)

    st.subheader("🔥 Top 2 Trades")
    st.dataframe(best, use_container_width=True)

    if best.empty:
        st.warning("No high-probability trades found")

# -------------------------------
# FOOTER
# -------------------------------
st.caption("⚠️ Educational use only. Confirm with live market before trading.")
