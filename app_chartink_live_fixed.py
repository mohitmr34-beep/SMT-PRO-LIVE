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
    # CSV UPLOAD — ORIGINAL CODE
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

    st.caption(
        "Uses the actual Chartink /screener/process request captured from your browser. "
        "Your old CSV analysis engine is not changed."
    )

    # IMPORTANT:
    # Do NOT put a real Chartink cookie in this source code.
    # On Streamlit Cloud, store it as Secrets:
    # CHARTINK_COOKIE = "your authorized browser Cookie header"
    #
    # Optional local use: enter it in the password box below.
    try:
        secret_cookie = st.secrets.get("CHARTINK_COOKIE", "")
    except Exception:
        secret_cookie = ""

    chartink_cookie = st.text_input(
        "Chartink authorized Cookie (optional if CHARTINK_COOKIE is in Secrets)",
        value=secret_cookie,
        type="password",
        help="Use your own authorized Chartink browser Cookie header. Never publish it."
    )

    refresh_seconds = st.number_input(
        "Refresh interval (seconds)",
        min_value=15, max_value=300, value=30, step=15
    )

    # This is the exact scan clause captured from the user's Chartink
    # Network request. It is independent of HTML scan-clause extraction.
    CHARTINK_SCAN_CLAUSE = (
        "( {cash} ( ( {cash} ( ( {cash} ( "
        " daily close >= daily max( 252 , daily high ) * 0.98 "
        "and daily volume > daily sma( daily volume , 20 ) * 1.5 "
        "and daily close > daily open ) ) "
        "or( {cash} ( daily high >= daily max( 252 , daily high ) "
        "and daily close < daily open "
        "and daily volume > daily sma( daily volume , 20 ) * 1.5 ) ) "
        "or( {cash} ( daily open > 1 day ago close * 1.02 "
        "and daily volume > daily sma( daily volume , 20 ) * 2 "
        "and daily close > daily open ) ) ) ) ) )"
    )

    CHARTINK_DEBUG_CLAUSE = (
        "groupcount( 1 where daily close >= daily max( 252 , daily high ) * 0.98),"
        "groupcount( 1 where daily volume > daily sma( daily volume , 20 ) * 1.5),"
        "groupcount( 1 where daily close > daily open),"
        "groupcount( 1 where daily high >= daily max( 252 , daily high )),"
        "groupcount( 1 where daily close < daily open),"
        "groupcount( 1 where daily volume > daily sma( daily volume , 20 ) * 1.5),"
        "groupcount( 1 where daily open > 1 day ago close * 1.02),"
        "groupcount( 1 where daily volume > daily sma( daily volume , 20 ) * 2),"
        "groupcount( 1 where daily close > daily open)"
    )

    CHARTINK_COLUMN_CLAUSE = (
        " Daily Close as 'scan-column-default-close',"
        " Daily close - 1 candle ago close / 1 candle ago close * 100"
        " as 'scan-column-default-percent-change',"
        " filternumber( daily close > 1 day ago close,1)"
        " as 'default-percent-change-conditional-filters-color',"
        " Daily Volume as 'scan-column-default-volume'"
    )

    def _cookie_value(cookie_header, name):
        if not cookie_header:
            return ""
        match = re.search(
            rf"(?:^|;\s*){re.escape(name)}=([^;]*)",
            cookie_header
        )
        return match.group(1) if match else ""

    @st.cache_data(ttl=15, show_spinner=False)
    def get_chartink_symbols(cookie_header, referer_url, scan_clause, debug_clause, column_clause):
        import json
        import requests
        from urllib.parse import unquote

        if not cookie_header.strip():
            raise RuntimeError(
                "Chartink Cookie is required for this scanner request. "
                "Add CHARTINK_COOKIE to Streamlit Secrets or paste your authorized Cookie."
            )

        session = requests.Session()

        # Browser-like headers matching the captured request.
        headers = {
            "Accept": "*/*",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
            "Content-Type": "application/json",
            "Origin": "https://chartink.com",
            "Referer": referer_url.strip(),
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/150.0.0.0 Safari/537.36"
            ),
            "X-Requested-With": "XMLHttpRequest",
        }

        # Chartink expects the XSRF token from the XSRF-TOKEN cookie.
        xsrf_raw = _cookie_value(cookie_header, "XSRF-TOKEN")
        xsrf_token = unquote(xsrf_raw)

        if xsrf_token:
            headers["X-XSRF-TOKEN"] = xsrf_token

        # Keep the browser's authorized cookie header exactly as supplied.
        headers["Cookie"] = cookie_header.strip()

        payload = {
            "scan_clause": scan_clause,
            "debug_clause": debug_clause,
            "column_clause": column_clause,
        }

        response = session.post(
            "https://chartink.com/screener/process",
            headers=headers,
            json=payload,
            timeout=30,
        )

        if response.status_code in (401, 403):
            raise RuntimeError(
                f"Chartink rejected the session (HTTP {response.status_code}). "
                "Log out/in to Chartink, capture a fresh authorized Cookie, "
                "then update CHARTINK_COOKIE."
            )

        response.raise_for_status()

        try:
            result = response.json()
        except Exception:
            raise RuntimeError(
                "Chartink returned a non-JSON response. "
                "Your browser session/cookie may have expired."
            )

        rows = result.get("data", [])

        if not isinstance(rows, list):
            raise RuntimeError(
                f"Unexpected Chartink response format: {type(rows).__name__}"
            )

        symbols_out = []

        for row in rows:
            if not isinstance(row, dict):
                continue

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

                if sym and sym not in symbols_out:
                    symbols_out.append(sym)

        if not symbols_out:
            # Give useful diagnostics without exposing cookies.
            keys = list(result.keys()) if isinstance(result, dict) else []
            raise RuntimeError(
                f"Chartink returned no NSE stocks. Response keys: {keys}"
            )

        return [s + ".NS" for s in symbols_out]

    col1, col2 = st.columns([1, 1])

    with col1:
        fetch_live = st.button("🔄 Get LIVE Chartink Stocks", type="primary")

    with col2:
        clear_live = st.button("🗑️ Clear LIVE Stocks")

    if clear_live:
        st.session_state.pop("chartink_symbols", None)
        st.cache_data.clear()
        st.rerun()

    if fetch_live:
        try:
            symbols = get_chartink_symbols(
                chartink_cookie,
                chartink_url,
                CHARTINK_SCAN_CLAUSE,
                CHARTINK_DEBUG_CLAUSE,
                CHARTINK_COLUMN_CLAUSE,
            )

            st.session_state["chartink_symbols"] = symbols
            st.success(f"Chartink LIVE returned {len(symbols)} stocks.")

        except Exception as e:
            st.error(f"Chartink LIVE fetch failed: {e}")
            st.stop()

    elif "chartink_symbols" in st.session_state:
        symbols = st.session_state["chartink_symbols"]
    else:
        st.info("Enter your authorized Chartink Cookie, then click 'Get LIVE Chartink Stocks'.")
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
