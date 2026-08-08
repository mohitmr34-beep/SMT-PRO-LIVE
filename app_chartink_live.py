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
# CHARTINK LIVE MODE
# -------------------------------
else:
    st.subheader("🟢 Chartink LIVE Scanner")

    chartink_url = st.text_input(
        "Chartink Scanner URL",
        "https://chartink.com/screener/master-scanner-18062057"
    )

    chartink_cookie = st.text_input("Chartink Cookie", type="password")

    @st.cache_data(ttl=20)
    def get_chartink_symbols(cookie, url):
        if not cookie:
            raise Exception("Cookie required")

        session = requests.Session()

        # Load cookie into session
        for part in cookie.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                session.cookies.set(k, v, domain="chartink.com")

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": url
        }

        # Step 1: open page
        session.get(url, headers=headers)

        xsrf = unquote(session.cookies.get("XSRF-TOKEN", ""))
        if not xsrf:
            raise Exception("XSRF token missing")

        headers.update({
            "X-Requested-With": "XMLHttpRequest",
            "X-XSRF-TOKEN": xsrf,
            "Content-Type": "application/json"
        })

        payload = {
            "scan_clause": "( {cash} ( daily close >= daily max(252,daily high)*0.98 ) )"
        }

        res = session.post(
            "https://chartink.com/screener/process",
            headers=headers,
            json=payload
        )

        # SAFE CHECK
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

    if st.button("🔄 Get LIVE Stocks"):
        try:
            symbols = get_chartink_symbols(chartink_cookie, chartink_url)
            st.session_state["symbols"] = symbols
            st.success(f"Loaded {len(symbols)} stocks")
        except Exception as e:
            st.error(f"Chartink LIVE fetch failed: {e}")
            st.stop()

    elif "symbols" in st.session_state:
        symbols = st.session_state["symbols"]
    else:
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

    close = latest["Close"]
    open_ = latest["Open"]
    high = latest["High"]
    low = latest["Low"]
    prev_close = prev["Close"]

    high_52 = df["High"].rolling(252).max().iloc[-1]

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
        signal = "BUY" if close > open_ else "SELL"
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
    st.dataframe(df_results)

    best = df_results[df_results["Signal"].isin(["BUY", "SELL"])].head(2)

    st.subheader("🔥 Top 2 Trades")
    st.dataframe(best)

# -------------------------------
# FOOTER
# -------------------------------
st.caption("⚠️ Educational use only")            "column_clause": CHARTINK_COLUMN_CLAUSE
    
        res = session.post(
            "https://chartink.com/screener/process",
            headers=headers,
            json=payload
        )

        if res.status_code == 419:
            raise Exception("Session expired (419). Use fresh cookie.")

        if res.status_code != 200:
            raise Exception(f"Chartink error {res.status_code}")

        data = res.json().get("data", [])

        symbols = []
        for row in data:
            sym = row.get("nsecode")
            if sym:
                symbols.append(sym.upper() + ".NS")

        if not symbols:
            raise Exception("No stocks returned from Chartink")

        return symbols

    if st.button("🔄 Get LIVE Stocks"):
        try:
            symbols = get_chartink_symbols(chartink_cookie, chartink_url)
            st.session_state["symbols"] = symbols
            st.success(f"Loaded {len(symbols)} stocks")
        except Exception as e:
            st.error(f"Chartink LIVE fetch failed: {e}")
            st.stop()

    elif "symbols" in st.session_state:
        symbols = st.session_state["symbols"]
    else:
        st.info("Enter cookie → Click 'Get LIVE Stocks'")
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

    close = latest["Close"]
    open_ = latest["Open"]
    high = latest["High"]
    low = latest["Low"]
    prev_close = prev["Close"]

    high_52 = df["High"].rolling(252).max().iloc[-1]

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
        signal = "BUY" if close > open_ else "SELL"
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
            "Entry": round(entry,2) if entry else None,
            "SL": round(sl,2) if sl else None,
            "Target": round(target,2) if target else None
        })

    df_results = pd.DataFrame(results)

    st.subheader("📊 All Results")
    st.dataframe(df_results, use_container_width=True)

    best = df_results[df_results["Signal"].isin(["BUY","SELL"])].head(2)

    st.subheader("🔥 Top 2 Trades")
    st.dataframe(best, use_container_width=True)

    if best.empty:
        st.warning("No high-probability trades found.")

# -------------------------------
# FOOTER
# -------------------------------
st.caption("⚠️ Educational use only. Confirm with live market before trading.")
        if res.status_code != 200:
            raise Exception(f"Chartink error {res.status_code}")

        data = res.json()["data"]

        symbols = []
        for row in data:
            sym = row.get("nsecode")
            if sym:
                symbols.append(sym + ".NS")

        return symbols

    if st.button("🔄 Get LIVE Stocks"):
        try:
            symbols = get_chartink_symbols(chartink_cookie)
            st.session_state["symbols"] = symbols
        except Exception as e:
            st.error(f"Chartink LIVE fetch failed: {e}")
            st.stop()

    elif "symbols" in st.session_state:
        symbols = st.session_state["symbols"]
    else:
        st.stop()

    st.success(f"Loaded {len(symbols)} stocks")

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

    close = latest["Close"]
    open_ = latest["Open"]
    high = latest["High"]
    low = latest["Low"]
    prev_close = prev["Close"]

    high_52 = df["High"].rolling(252).max().iloc[-1]

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
        signal = "BUY" if close > open_ else "SELL"
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
            "Entry": round(entry,2) if entry else None,
            "SL": round(sl,2) if sl else None,
            "Target": round(target,2) if target else None
        })

    df_results = pd.DataFrame(results)

    st.subheader("📊 All Results")
    st.dataframe(df_results)

    best = df_results[df_results["Signal"].isin(["BUY","SELL"])].head(2)

    st.subheader("🔥 Top 2 Trades")
    st.dataframe(best)

# -------------------------------
# FOOTER
# -------------------------------
st.caption("⚠️ Educational use only")        " Daily Close as 'scan-column-default-close',"
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

        # Parse the browser cookie into the requests cookie jar.
        # This is more reliable than sending a static Cookie header because
        # Chartink/Laravel can refresh the session and XSRF cookies.
        for part in cookie_header.split(";"):
            if "=" in part:
                name, value = part.strip().split("=", 1)
                session.cookies.set(name, value, domain="chartink.com", path="/")

        base_headers = {
            "Accept": "*/*",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
            "Origin": "https://chartink.com",
            "Referer": referer_url.strip(),
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/150.0.0.0 Safari/537.36"
            ),
        }

        # FIRST: open the scanner page with the authorized session.
        # This lets Chartink refresh/validate ci_session and XSRF-TOKEN
        # before the POST. A 419 normally means CSRF/session mismatch.
        page = session.get(
            referer_url.strip(),
            headers=base_headers,
            timeout=30,
        )

        if page.status_code in (401, 403):
            raise RuntimeError(
                f"Chartink rejected the browser session while opening the scanner "
                f"(HTTP {page.status_code}). Capture a fresh authorized cookie."
            )

        page.raise_for_status()

        # Use the CURRENT XSRF cookie from the refreshed requests session.
        xsrf_token = session.cookies.get("XSRF-TOKEN", "")
        xsrf_token = unquote(xsrf_token)

        if not xsrf_token:
            raise RuntimeError(
                "Chartink did not return a fresh XSRF-TOKEN after opening the scanner."
            )

        post_headers = {
            **base_headers,
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "X-XSRF-TOKEN": xsrf_token,
        }

        payload = {
            "scan_clause": scan_clause,
            "debug_clause": debug_clause,
            "column_clause": column_clause,
        }

        response = session.post(
            "https://chartink.com/screener/process",
            headers=post_headers,
            json=payload,
            timeout=30,
        )

        if response.status_code == 419:
            raise RuntimeError(
                "Chartink returned HTTP 419 (CSRF/session mismatch). "
                "The app now refreshes the scanner page before POSTing, but "
                "your authorized Chartink session may still be expired or "
                "bound to the browser session. Capture a fresh Cookie and "
                "update CHARTINK_COOKIE."
            )

        if response.status_code in (401, 403):
            raise RuntimeError(
                f"Chartink rejected the session (HTTP {response.status_code}). "
                "Capture a fresh authorized Cookie from the same logged-in browser."
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

        # Parse the browser cookie into the requests cookie jar.
        # This is more reliable than sending a static Cookie header because
        # Chartink/Laravel can refresh the session and XSRF cookies.
        for part in cookie_header.split(";"):
            if "=" in part:
                name, value = part.strip().split("=", 1)
                session.cookies.set(name, value, domain="chartink.com", path="/")

        base_headers = {
            "Accept": "*/*",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
            "Origin": "https://chartink.com",
            "Referer": referer_url.strip(),
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/150.0.0.0 Safari/537.36"
            ),
        }

        # FIRST: open the scanner page with the authorized session.
        # This lets Chartink refresh/validate ci_session and XSRF-TOKEN
        # before the POST. A 419 normally means CSRF/session mismatch.
        page = session.get(
            referer_url.strip(),
            headers=base_headers,
            timeout=30,
        )

        if page.status_code in (401, 403):
            raise RuntimeError(
                f"Chartink rejected the browser session while opening the scanner "
                f"(HTTP {page.status_code}). Capture a fresh authorized cookie."
            )

        page.raise_for_status()

        # Use the CURRENT XSRF cookie from the refreshed requests session.
        xsrf_token = session.cookies.get("XSRF-TOKEN", "")
        xsrf_token = unquote(xsrf_token)

        if not xsrf_token:
            raise RuntimeError(
                "Chartink did not return a fresh XSRF-TOKEN after opening the scanner."
            )

        post_headers = {
            **base_headers,
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "X-XSRF-TOKEN": xsrf_token,
        }

        payload = {
            "scan_clause": scan_clause,
            "debug_clause": debug_clause,
            "column_clause": column_clause,
        }

        response = session.post(
            "https://chartink.com/screener/process",
            headers=post_headers,
            json=payload,
            timeout=30,
        )

        if response.status_code == 419:
            raise RuntimeError(
                "Chartink returned HTTP 419 (CSRF/session mismatch). "
                "The app now refreshes the scanner page before POSTing, but "
                "your authorized Chartink session may still be expired or "
                "bound to the browser session. Capture a fresh Cookie and "
                "update CHARTINK_COOKIE."
            )

        if response.status_code in (401, 403):
            raise RuntimeError(
                f"Chartink rejected the session (HTTP {response.status_code}). "
                "Capture a fresh authorized Cookie from the same logged-in browser."
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

        # Parse the browser cookie into the requests cookie jar.
        # This is more reliable than sending a static Cookie header because
        # Chartink/Laravel can refresh the session and XSRF cookies.
        for part in cookie_header.split(";"):
            if "=" in part:
                name, value = part.strip().split("=", 1)
                session.cookies.set(name, value, domain="chartink.com", path="/")

        base_headers = {
            "Accept": "*/*",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
            "Origin": "https://chartink.com",
            "Referer": referer_url.strip(),
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/150.0.0.0 Safari/537.36"
            ),
        }

        # FIRST: open the scanner page with the authorized session.
        # This lets Chartink refresh/validate ci_session and XSRF-TOKEN
        # before the POST. A 419 normally means CSRF/session mismatch.
        page = session.get(
            referer_url.strip(),
            headers=base_headers,
            timeout=30,
        )

        if page.status_code in (401, 403):
            raise RuntimeError(
                f"Chartink rejected the browser session while opening the scanner "
                f"(HTTP {page.status_code}). Capture a fresh authorized cookie."
            )

        page.raise_for_status()

        # Use the CURRENT XSRF cookie from the refreshed requests session.
        xsrf_token = session.cookies.get("XSRF-TOKEN", "")
        xsrf_token = unquote(xsrf_token)

        if not xsrf_token:
            raise RuntimeError(
                "Chartink did not return a fresh XSRF-TOKEN after opening the scanner."
            )

        post_headers = {
            **base_headers,
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "X-XSRF-TOKEN": xsrf_token,
        }

        payload = {
            "scan_clause": scan_clause,
            "debug_clause": debug_clause,
            "column_clause": column_clause,
        }

        response = session.post(
            "https://chartink.com/screener/process",
            headers=post_headers,
            json=payload,
            timeout=30,
        )

        if response.status_code == 419:
            raise RuntimeError(
                "Chartink returned HTTP 419 (CSRF/session mismatch). "
                "The app now refreshes the scanner page before POSTing, but "
                "your authorized Chartink session may still be expired or "
                "bound to the browser session. Capture a fresh Cookie and "
                "update CHARTINK_COOKIE."
            )

        if response.status_code in (401, 403):
            raise RuntimeError(
                f"Chartink rejected the session (HTTP {response.status_code}). "
                "Capture a fresh authorized Cookie from the same logged-in browser."
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

    # EXACT old selection behavior.
    best = df_results[df_results["Signal"].isin(["BUY", "SELL"])].head(2)

    st.subheader("🔥 Top 2 Trades")
    st.dataframe(best, use_container_width=True)

    if best.empty:
        st.warning("No high-probability trades found. Stay disciplined.")

st.caption("⚠️ Educational use only. Confirm with live market before trading.")
