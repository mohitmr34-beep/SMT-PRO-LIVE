import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import re
import html as html_lib

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
# CSV MODE
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
# CHARTINK LIVE MODE
# -------------------------------
else:

    st.subheader("🟢 Chartink LIVE Scanner")

    chartink_url = st.text_input(
        "Chartink Scanner URL",
        "https://chartink.com/screener/master-scanner-18062057"
    )

    # 🔥 NEW: COOKIE INPUT
    chartink_cookie = st.text_input(
        "🔐 Chartink Cookie (Recommended)",
        type="password",
        help="Paste browser cookie for accurate results"
    )

    @st.cache_data(ttl=20, show_spinner=False)
    def get_chartink_symbols(url, cookie=None):

        session = requests.Session()

        # ✅ Apply cookie if provided
        if cookie:
            for part in cookie.split(";"):
                if "=" in part:
                    k, v = part.strip().split("=", 1)
                    session.cookies.set(k, v, domain="chartink.com")

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html",
            "Referer": "https://chartink.com/"
        }

        # Step 1: Open page
        page = session.get(url.strip(), headers=headers, timeout=20)
        page.raise_for_status()

        html = page.text

        # Step 2: Extract scan_clause
        scan_clause = None
        patterns = [
            r'"scan_clause"\s*:\s*"((?:\\.|[^"\\])*)"',
            r"'scan_clause'\s*:\s*'((?:\\.|[^'\\])*)'"
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.I | re.S)
            if match:
                scan_clause = match.group(1)
                break

        if not scan_clause:
            decoded = html_lib.unescape(html)
            for pattern in patterns:
                match = re.search(pattern, decoded, re.I | re.S)
                if match:
                    scan_clause = match.group(1)
                    break

        if not scan_clause:
            raise RuntimeError("Scan clause not found (use cookie)")

        scan_clause = scan_clause.replace("\\/", "/").replace('\\"', '"')

        # Step 3: POST request
        process_headers = {
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": url.strip()
        }

        response = session.post(
            "https://chartink.com/screener/process",
            data={"scan_clause": scan_clause},
            headers=process_headers,
            timeout=20
        )

        response.raise_for_status()
        payload = response.json()

        rows = payload.get("data", [])

        symbols_out = []
        for row in rows:
            raw = (
                row.get("nsecode")
                or row.get("symbol")
                or row.get("Symbol")
            )

            if raw:
                sym = str(raw).strip().upper()
                if not sym.endswith(".NS"):
                    sym = sym + ".NS"

                if sym not in symbols_out:
                    symbols_out.append(sym)

        if not symbols_out:
            raise RuntimeError("No stocks returned from Chartink")

        return symbols_out

    if st.button("🔄 Get LIVE Chartink Stocks"):
        try:
            symbols = get_chartink_symbols(chartink_url, chartink_cookie)
            st.session_state["chartink_symbols"] = symbols
            st.success(f"Loaded {len(symbols)} stocks")
        except Exception as e:
            st.error(f"Chartink LIVE fetch failed: {e}")
            st.stop()

    elif "chartink_symbols" in st.session_state:
        symbols = st.session_state["chartink_symbols"]
    else:
        st.info("Click button to load Chartink stocks")
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

        if not all(col in df.columns for col in ["Open", "High", "Low", "Close"]):
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

    if close >= 0.98 * high_52 and close > open_:
        signal = "BUY"
        entry = high
        sl = low
        target = entry + (entry - sl) * 2

    elif high >= high_52 and close < open_:
        signal = "SELL"
        entry = low
        sl = high
        target = entry - (sl - entry) * 2

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

    best = df_results[df_results["Signal"].isin(["BUY", "SELL"])].head(2)

    st.subheader("🔥 Top 2 Trades")
    st.dataframe(best, use_container_width=True)

    if best.empty:
        st.warning("No high-probability trades found")

# -------------------------------
# FOOTER
# -------------------------------
st.caption("⚠️ Educational use only. Confirm with live market before trading.")
