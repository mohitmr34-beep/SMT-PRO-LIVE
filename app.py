import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from urllib.parse import unquote
import time

# -------------------------------
# APP CONFIG
# -------------------------------
st.set_page_config(page_title="SMT PRO AI Scanner", layout="wide")

st.markdown("<h2 style='text-align:center;'>SMT PRO AI Trading Terminal</h2><hr>", unsafe_allow_html=True)

# -------------------------------
# AUTO REFRESH
# -------------------------------
auto_refresh = st.checkbox("Auto Refresh (5 min)", value=False)

if auto_refresh:
    time.sleep(300)
    st.rerun()

# -------------------------------
# STOCK SOURCE
# -------------------------------
source = st.radio("Stock Source", ["Manual CSV", "Chartink LIVE"], horizontal=True)

# ===============================
# CSV MODE
# ===============================
if source == "Manual CSV":

    uploaded_file = st.file_uploader("Upload Stock CSV", type=["csv"])

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

# ===============================
# CHARTINK LIVE MODE
# ===============================
else:

    st.subheader("Chartink LIVE Scanner")
    chartink_cookie = st.text_input("Enter Chartink Cookie", type="password")

    @st.cache_data(ttl=30)
    def get_chartink_symbols(cookie):

        if not cookie:
            raise Exception("Cookie required")

        session = requests.Session()

        for part in cookie.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                session.cookies.set(k, v, domain="chartink.com")

        session.get("https://chartink.com")

        xsrf = unquote(session.cookies.get("XSRF-TOKEN", ""))

        if not xsrf:
            raise Exception("Invalid Cookie / XSRF missing")

        headers = {
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
            "X-XSRF-TOKEN": xsrf,
            "Content-Type": "application/json",
            "Referer": "https://chartink.com/"
        }

        payload = {
            "scan_clause": "( {cash} ( ( {cash} ( ( {cash} ( daily close >= daily max(252, daily high)*0.98 and daily volume > daily sma(daily volume,20)*1.5 and daily close > daily open ) ) or ( {cash} ( daily high >= daily max(252, daily high) and daily close < daily open and daily volume > daily sma(daily volume,20)*1.5 ) ) or ( {cash} ( daily open > 1 day ago close*1.02 and daily volume > daily sma(daily volume,20)*2 and daily close > daily open ) ) ) ) ) )"
        }

        res = session.post("https://chartink.com/screener/process", headers=headers, json=payload)

        if res.status_code != 200:
            raise Exception("Chartink fetch failed")

        data = res.json().get("data", [])

        symbols = []
        for row in data:
            sym = row.get("nsecode")
            if sym:
                symbols.append(sym.upper() + ".NS")

        if not symbols:
            raise Exception("No stocks returned")

        return symbols

    if st.button("Get LIVE Stocks"):
        try:
            symbols = get_chartink_symbols(chartink_cookie)
            st.session_state["symbols"] = symbols
            st.success(f"{len(symbols)} stocks loaded")
        except Exception as e:
            st.error(str(e))
            st.stop()

    elif "symbols" in st.session_state:
        symbols = st.session_state["symbols"]
    else:
        st.info("Enter cookie and click button")
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
# AI SCORE ENGINE
# -------------------------------
def calculate_ai_score(df, signal):

    if df is None or len(df) < 50:
        return 0

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    score = 0

    # Trend
    if latest["Close"] > df["Close"].rolling(20).mean().iloc[-1]:
        score += 20

    # Volume
    if "Volume" in df:
        avg_vol = df["Volume"].rolling(20).mean().iloc[-1]
        if latest["Volume"] > 1.5 * avg_vol:
            score += 20

    # Breakout
    high_52 = df["High"].rolling(252).max().iloc[-1]

    if signal == "BUY" and latest["Close"] >= 0.98 * high_52:
        score += 20

    if signal == "SELL" and latest["High"] >= high_52:
        score += 20

    # Candle strength
    body = abs(latest["Close"] - latest["Open"])
    range_ = latest["High"] - latest["Low"]

    if range_ > 0 and body / range_ > 0.6:
        score += 20

    # Gap
    if latest["Open"] > prev["Close"] * 1.02:
        score += 20

    return min(score, 100)

# -------------------------------
# AI LOGIC
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
        signal = "BUY" if close > open_ else "SELL"
        entry = high if signal == "BUY" else low
        sl = low if signal == "BUY" else high
        target = entry + (entry - sl) * 2 if signal == "BUY" else entry - (sl - entry) * 2

    return signal, entry, sl, target

# -------------------------------
# RUN SCANNER
# -------------------------------
if st.button("Run AI Scanner"):

    results = []

    for sym in symbols:
        df = get_data(sym, timeframe)
        signal, entry, sl, target = analyze_stock(df)
        score = calculate_ai_score(df, signal)

        if signal in ["BUY","SELL"]:
            results.append({
                "Stock": sym,
                "Signal": signal,
                "Score": score,
                "Entry": round(entry, 2) if entry else None,
                "SL": round(sl, 2) if sl else None,
                "Target": round(target, 2) if target else None
            })

    df_results = pd.DataFrame(results)

    if df_results.empty:
        st.warning("No trade found")
        st.stop()

    # SORT
    df_results = df_results.sort_values(by="Score", ascending=False).reset_index(drop=True)

    # METRICS
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Trades", len(df_results))
    c2.metric("Best Score", df_results.iloc[0]["Score"])
    c3.metric("Top Signal", df_results.iloc[0]["Signal"])

    # BEST TRADE
    best = df_results.iloc[0]

    color = "green" if best["Signal"] == "BUY" else "red"

    st.markdown(f"""
    <div style='padding:20px;border-radius:12px;background:{color};color:white'>
    <h3>{best['Stock']} - {best['Signal']}</h3>
    <p><b>AI Score:</b> {best['Score']} / 100</p>
    <p><b>Entry:</b> {best['Entry']}</p>
    <p><b>SL:</b> {best['SL']}</p>
    <p><b>Target:</b> {best['Target']}</p>
    </div>
    """, unsafe_allow_html=True)

    # FULL RANKED LIST
    st.subheader("Ranked Trades")
    st.data_editor(df_results, use_container_width=True)

# -------------------------------
# FOOTER
# -------------------------------
st.caption("Educational use only. Confirm before trading.")
