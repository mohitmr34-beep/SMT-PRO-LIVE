import streamlit as st
import yfinance as yf
import pandas as pd

# -------------------------------
# APP CONFIG
# -------------------------------
st.set_page_config(page_title="SMT PRO AI Scanner", layout="wide")
st.title("📊 SMT PRO AI Trading Scanner (CSV Enabled)")

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
