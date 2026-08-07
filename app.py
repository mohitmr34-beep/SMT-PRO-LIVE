import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import re

# -------------------------------
# APP CONFIG
# -------------------------------
st.set_page_config(page_title="SMT PRO AI Scanner", layout="wide")
st.title("📊 SMT PRO AI Trading Scanner")

# -------------------------------
# MODE
# -------------------------------
mode = st.radio(
    "Select Scanner Mode",
    ["📂 CSV — OLD APP", "🟢 LIVE — Chartink"],
    horizontal=True
)

# -------------------------------
# INPUT SOURCE
# -------------------------------
DEFAULT_SCAN_URL = "https://chartink.com/screener/master-scanner-18062057"

if mode == "📂 CSV — OLD APP":
    uploaded_file = st.file_uploader("📂 Upload Stock List CSV", type=["csv"])

    if uploaded_file:
        df_symbols = pd.read_csv(uploaded_file)

        if "Symbol" in df_symbols.columns:
            symbols = [s.strip().upper() + ".NS" for s in df_symbols["Symbol"].dropna()]
        else:
            st.error("CSV must contain 'Symbol' column")
            st.stop()
    else:
        # Original fallback preserved
        symbols = [
            "RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS","TCS.NS",
            "SBIN.NS","LT.NS","AXISBANK.NS","KOTAKBANK.NS","ITC.NS"
        ]
        st.info("No CSV uploaded — using the original fallback F&O list.")

else:
    scan_url = st.text_input(
        "Chartink Scanner URL",
        value=DEFAULT_SCAN_URL
    )
    cookie = st.text_input(
        "Chartink session cookie (optional)",
        type="password",
        help="Use only your own authorized Chartink session. Never commit the cookie to GitHub."
    )

    st.caption(
        "LIVE mode only changes the stock-list source. "
        "The Yahoo data engine and analyze_stock() logic below are the same as the old app."
    )

    def fetch_chartink_symbols(url, cookie_value=""):
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/150.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://chartink.com/",
        }

        if cookie_value.strip():
            headers["Cookie"] = cookie_value.strip()

        page = session.get(url.strip(), headers=headers, timeout=30)
        page.raise_for_status()
        html = page.text

        # Try to recover Chartink's scanner clause from the page.
        scan_clause = None

        patterns = [
            r'"scan_clause"\s*:\s*"((?:\\.|[^"\\])*)"',
            r"'scan_clause'\s*:\s*'((?:\\.|[^'\\])*)'",
            r'scan_clause\s*[:=]\s*["\']([^"\']+)["\']',
        ]

        for pattern in patterns:
            m = re.search(pattern, html, re.I | re.S)
            if m:
                scan_clause = m.group(1)
                break

        # Decode common JSON escaping.
        if scan_clause:
            scan_clause = (
                scan_clause
                .replace('\\"', '"')
                .replace("\\/", "/")
                .replace("\\n", "\n")
            )

        # CSRF token if present.
        csrf = None
        m = re.search(
            r'<meta[^>]+name=["\']csrf-token["\'][^>]+content=["\']([^"\']+)["\']',
            html,
            re.I
        )
        if m:
            csrf = m.group(1)

        # Chartink's result endpoint is dynamic; do not use read_html().
        if not scan_clause:
            raise RuntimeError(
                "Chartink page loaded, but the scanner clause was not exposed in the page. "
                "The LIVE connector needs the authenticated result request used by your "
                "Chartink session. CSV mode remains unchanged."
            )

        process_headers = dict(headers)
        process_headers.update({
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": url.strip(),
        })
        if csrf:
            process_headers["X-CSRF-TOKEN"] = csrf

        response = session.post(
            "https://chartink.com/screener/process",
            data={"scan_clause": scan_clause},
            headers=process_headers,
            timeout=30
        )
        response.raise_for_status()

        try:
            payload = response.json()
        except Exception:
            raise RuntimeError(
                "Chartink returned a non-JSON response from the scanner result endpoint."
            )

        rows = payload.get("data", payload if isinstance(payload, list) else [])
        if not rows:
            raise RuntimeError(
                "Chartink returned no scanner rows. Check the scanner URL, "
                "subscription/session access, and scan conditions."
            )

        found = []
        for row in rows:
            if not isinstance(row, dict):
                continue

            # Chartink commonly returns nsecode for NSE symbols.
            value = (
                row.get("nsecode")
                or row.get("NSECODE")
                or row.get("symbol")
                or row.get("Symbol")
            )

            if value:
                sym = str(value).strip().upper()
                if sym.endswith(".NS"):
                    sym = sym[:-3]
                if sym and sym not in found:
                    found.append(sym)

        if not found:
            raise RuntimeError(
                "Chartink returned rows, but no NSE symbols could be identified."
            )

        return [s + ".NS" for s in found]

    if st.button("🔄 Fetch Chartink Candidates"):
        try:
            symbols = fetch_chartink_symbols(scan_url, cookie)
            st.success(f"Chartink LIVE candidates: {len(symbols)}")
        except Exception as e:
            st.error(f"Chartink LIVE fetch failed: {e}")
            st.stop()
    else:
        st.info("Click **Fetch Chartink Candidates** to load the live scanner.")
        st.stop()

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

    # Top 2 trades — original behaviour preserved
    best = df_results[df_results["Signal"].isin(["BUY", "SELL"])].head(2)

    st.subheader("🔥 Top 2 Trades")
    st.dataframe(best, use_container_width=True)

    if best.empty:
        st.warning("No high-probability trades found. Stay disciplined.")

# -------------------------------
# FOOTER
# -------------------------------
st.caption("⚠️ Educational use only. Confirm with live market before trading.")
