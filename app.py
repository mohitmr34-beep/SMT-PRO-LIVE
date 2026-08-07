import io
import re
import requests
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="SMT PRO AI Scanner", layout="wide")
st.title("📊 SMT PRO AI Trading Scanner")
st.caption("TWO MODES ONLY • LIVE Chartink and OLD CSV. Both use the SAME analysis engine.")

# ============================================================
# SETTINGS
# ============================================================
DEFAULT_SCAN = "https://chartink.com/screener/master-scanner-18062057"

with st.sidebar:
    st.header("⚙️ Scanner")
    mode = st.radio(
        "Select Mode",
        ["🟢 LIVE — Chartink", "📂 CSV — OLD"],
        index=1
    )

    timeframe = st.selectbox("Select Timeframe", ["5m", "15m", "1d"], index=0)

    if mode.startswith("🟢"):
        scan_url = st.text_input("Chartink Scanner URL", value=DEFAULT_SCAN)
        cookie = st.text_input(
            "Chartink session cookie (optional)",
            value="",
            type="password",
            help="Only use your own authorized session. Never commit the cookie to source control."
        )

    run = st.button("🚀 RUN SCANNER", type="primary")

# ============================================================
# COMMON DATA ENGINE
# ============================================================
@st.cache_data(ttl=60, show_spinner=False)
def get_data(symbol, timeframe):
    try:
        df = yf.download(
            symbol,
            period="5d" if timeframe in ("5m", "15m") else "1y",
            interval=timeframe,
            progress=False,
            auto_adjust=False,
            threads=False
        )

        if df is None or df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        required = ["Open", "High", "Low", "Close"]
        if not all(c in df.columns for c in required):
            return None

        df = df.dropna(subset=required).copy()
        return df if len(df) >= 2 else None

    except Exception:
        return None

# ============================================================
# THIS IS THE ORIGINAL CSV ENGINE
# Preserved from your first app:
# ATH Breakout -> ATH Rejection -> Gap Momentum
# ============================================================
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

        # OLD LOGIC — DO NOT CHANGE
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
            target = (
                entry + (entry - sl) * 2
                if signal == "BUY"
                else entry - (sl - entry) * 2
            )

        return signal, entry, sl, target

    except Exception:
        return "ERROR", None, None, None

# ============================================================
# CHARTINK FETCH
# ============================================================
def chartink_headers(cookie_value=""):
    h = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://chartink.com/",
    }
    if cookie_value.strip():
        h["Cookie"] = cookie_value.strip()
    return h

def normalize_symbols(df):
    df = df.copy()
    symbol_col = None

    for c in df.columns:
        name = str(c).strip().lower()
        if name in ("symbol", "stock symbol") or "symbol" in name:
            symbol_col = c
            break

    if symbol_col is None:
        # Support the user's old CSV naming if Symbol is present exactly.
        if "Symbol" in df.columns:
            symbol_col = "Symbol"

    if symbol_col is None:
        raise ValueError("CSV/Chartink data must contain a Symbol column.")

    symbols = (
        df[symbol_col]
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
        .str.replace(".NS", "", regex=False)
    )

    return list(dict.fromkeys(symbols.tolist()))

def fetch_chartink(scan_url, cookie_value=""):
    r = requests.get(
        scan_url.strip(),
        headers=chartink_headers(cookie_value),
        timeout=25
    )
    r.raise_for_status()

    tables = pd.read_html(io.StringIO(r.text))
    if not tables:
        raise ValueError("No scanner result table found on the Chartink page.")

    for table in tables:
        try:
            symbols = normalize_symbols(table)
            if symbols:
                return symbols
        except Exception:
            pass

    raise ValueError(
        "Chartink page did not expose a Symbol table. "
        "Your scan may require an authenticated/session result request."
    )

# ============================================================
# RUN
# ============================================================
if not run:
    if mode.startswith("📂"):
        st.info("Upload your original Chartink CSV below, then click RUN SCANNER.")
        uploaded = st.file_uploader(
            "📂 Upload MASTER SCANNER CSV",
            type=["csv"]
        )
    else:
        st.info("LIVE mode will use your Chartink Master Scanner.")
    st.stop()

# Get source symbols
if mode.startswith("📂"):
    uploaded = st.file_uploader(
        "📂 Upload MASTER SCANNER CSV",
        type=["csv"],
        key="csv_run"
    )

    if uploaded is None:
        st.warning("Please upload your original MASTER SCANNER CSV.")
        st.stop()

    csv_df = pd.read_csv(uploaded)
    symbols = normalize_symbols(csv_df)
    source_name = "OLD CSV"

else:
    try:
        symbols = fetch_chartink(scan_url, cookie)
        source_name = "CHARTINK LIVE"
    except Exception as e:
        st.error(f"Chartink fetch failed: {e}")
        st.stop()

st.success(f"{source_name}: {len(symbols)} candidate stocks loaded.")

# ============================================================
# SAME ENGINE FOR BOTH MODES
# ============================================================
results = []

progress = st.progress(0)

for i, sym in enumerate(symbols):
    yahoo_symbol = sym + ".NS"

    df = get_data(yahoo_symbol, timeframe)
    signal, entry, sl, target = analyze_stock(df)

    results.append({
        "Stock": sym,
        "Signal": signal,
        "Entry": round(entry, 2) if entry is not None else None,
        "SL": round(sl, 2) if sl is not None else None,
        "Target": round(target, 2) if target is not None else None,
        "Data Rows": len(df) if df is not None else 0
    })

    progress.progress((i + 1) / len(symbols))

progress.empty()

results_df = pd.DataFrame(results)

# ============================================================
# EXACT OLD TOP-2 BEHAVIOUR
# ============================================================
best = results_df[
    results_df["Signal"].isin(["BUY", "SELL"])
].head(2)

st.subheader("📊 All Results")
st.dataframe(results_df, use_container_width=True)

st.subheader("🔥 TOP 2 TRADES")

if best.empty:
    st.warning("No BUY/SELL setup found.")
else:
    st.dataframe(best, use_container_width=True)

    cols = st.columns(len(best))
    for i, (_, row) in enumerate(best.iterrows()):
        with cols[i]:
            st.markdown(f"### #{i+1} {row['Stock']}")
            st.metric("Signal", row["Signal"])
            st.write(f"**Entry:** ₹{row['Entry']}")
            st.write(f"**SL:** ₹{row['SL']}")
            st.write(f"**Target:** ₹{row['Target']}")

st.download_button(
    "⬇️ Download Results CSV",
    results_df.to_csv(index=False).encode("utf-8"),
    "smt_pro_results.csv",
    "text/csv"
)

st.caption(
    "⚠️ Same analysis engine is used in LIVE and OLD CSV modes. "
    "The only intended difference is the source of the stock list. "
    "Educational use only; confirm live data before trading."
)
