import streamlit as st
import yfinance as yf
import pandas as pd

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

if source == "📂 Manual CSV (OLD)":
    # -------------------------------
    # CSV UPLOAD
    # -------------------------------
    uploaded_file = st.file_uploader("📂 Upload Stock List CSV", type=["csv"])

    if uploaded_file:
        df_symbols = pd.read_csv(uploaded_file)
        
        if "Symbol" in df_symbols.columns:
           symbols = [s.strip().upper() + ".NS" for s in df_symbols["Symbol"].dropna()]
        else:
            st.error("CSV must contain 'Symbol' column")
            st.stop()
    else:
        # Default fallback (F&O stocks)
        symbols = [
            "RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS","TCS.NS",
            "SBIN.NS","LT.NS","AXISBANK.NS","KOTAKBANK.NS","ITC.NS"
        ]

else:
    st.subheader("🟢 Chartink LIVE Scanner")
    chartink_url = st.text_input(
        "Chartink Scanner URL",
        "https://chartink.com/screener/master-scanner-18062057"
    )
    refresh_seconds = st.number_input(
        "Auto-refresh interval (seconds)",
        min_value=15, max_value=300, value=30, step=15
    )

    import requests
    import re
    import html as html_lib

    @st.cache_data(ttl=20, show_spinner=False)
    def get_chartink_symbols(url):
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://chartink.com/"
        }

        page = session.get(url.strip(), headers=headers, timeout=20)
        page.raise_for_status()
        page_html = page.text

        scan_clause = None
        patterns = [
            r'"scan_clause"\s*:\s*"((?:\\.|[^"\\])*)"',
            r"'scan_clause'\s*:\s*'((?:\\.|[^'\\])*)'",
            r'"scan_clause"\s*:\s*\'((?:\\.|[^\'\\])*)\''
        ]

        for pattern in patterns:
            match = re.search(pattern, page_html, re.I | re.S)
            if match:
                scan_clause = match.group(1)
                break

        if not scan_clause:
            # Chartink may keep scanner data in HTML-escaped/script content.
            decoded = html_lib.unescape(page_html)
            for pattern in patterns:
                match = re.search(pattern, decoded, re.I | re.S)
                if match:
                    scan_clause = match.group(1)
                    break

        if not scan_clause:
            raise RuntimeError(
                "Chartink did not expose the scan clause. "
                "If the scanner is private/login-protected, use your authorized session cookie."
            )

        try:
            scan_clause = bytes(scan_clause, "utf-8").decode("unicode_escape")
        except Exception:
            scan_clause = scan_clause.replace("\\/", "/").replace('\\"', '"')

        process_headers = dict(headers)
        process_headers.update({
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": url.strip()
        })

        response = session.post(
            "https://chartink.com/screener/process",
            data={"scan_clause": scan_clause},
            headers=process_headers,
            timeout=20
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data", [])

        result = []
        for row in rows:
            raw = (
                row.get("nsecode")
                or row.get("NSECODE")
                or row.get("symbol")
                or row.get("Symbol")
            )
            if raw:
                sym = str(raw).strip().upper()
                if sym.endswith(".NS"):
                    sym = sym[:-3]
                if sym and sym not in result:
                    result.append(sym)

        if not result:
            raise RuntimeError("Chartink returned no NSE stocks.")

        return [s + ".NS" for s in result]

    if st.button("🔄 Get LIVE Chartink Stocks", type="primary"):
        try:
            symbols = get_chartink_symbols(chartink_url)
            st.session_state["chartink_symbols"] = symbols
            st.success(f"Chartink returned {len(symbols)} stocks.")
        except Exception as e:
            st.error(f"Chartink LIVE fetch failed: {e}")
            st.stop()
    elif "chartink_symbols" in st.session_state:
        symbols = st.session_state["chartink_symbols"]
    else:
        st.info("Click 'Get LIVE Chartink Stocks' to load current scanner stocks.")
        st.stop()

    st.dataframe(
        pd.DataFrame({"Chartink Stocks": symbols}),
        use_container_width=True,
        hide_index=True
    )

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

        required_cols = ["Open", "High", "Low", "Close"]
        if not all(col in df.columns for col in required_cols):
            return None

        return df

    except Exception:
        return None

# -------------------------------
# AI LOGIC
# -------------------------------
def analyze_stock(df):
    try:
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

    except Exception:
        return "ERROR", None, None, None

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

    # Top 2 trades
    best = df_results[df_results["Signal"].isin(["BUY", "SELL"])].head(2)

    st.subheader("🔥 Top 2 Trades")
    st.dataframe(best, use_container_width=True)

    if best.empty:
        st.warning("No high-probability trades found. Stay disciplined.")

# -------------------------------
# FOOTER
# -------------------------------
st.caption("⚠️ Educational use only. Confirm with live market before trading.")
