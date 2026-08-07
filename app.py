import io
import os
import re
import requests
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="SMT PRO AI Scanner", layout="wide")
st.title("📊 SMT PRO AI — Chartink → TOP 2 Scanner")
st.caption("Chartink generates candidates; SMT PRO independently ranks them. No profit is guaranteed.")

# -----------------------------
# SETTINGS
# -----------------------------
with st.sidebar:
    st.header("⚙️ Scanner Settings")
    source = st.radio("Candidate source", ["Chartink Live", "CSV (Old Scanner)"])
    scan_url = st.text_input(
        "Chartink scanner URL",
        placeholder="https://chartink.com/screener/your-scan"
    )
    cookie = st.text_input(
        "Chartink session cookie (optional)",
        type="password",
        help="Use only your own authorized session. Do not commit this value to GitHub."
    )
    timeframe = st.selectbox("Analysis timeframe", ["5m", "15m", "1d"])
    min_score = st.slider("Minimum probability score", 60, 95, 80)
    top_n = st.number_input("Show TOP N", 1, 10, 2)
    fno_only = st.checkbox("F&O candidates only", value=True)

# -----------------------------
# CHARTINK
# -----------------------------
def chartink_headers(cookie_value=""):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://chartink.com/",
    }
    if cookie_value:
        headers["Cookie"] = cookie_value
    return headers

def normalize_chartink(df):
    df = df.copy()
    rename = {}
    for c in df.columns:
        x = str(c).strip().lower()
        if x in {"symbol", "stock", "stock symbol", "name"} or "symbol" in x:
            rename[c] = "Symbol"
        elif x in {"close", "ltp"} or "price" in x:
            rename[c] = "Price"
        elif "volume" in x:
            rename[c] = "Volume"
    df = df.rename(columns=rename)
    if "Symbol" not in df.columns:
        raise ValueError("Chartink result did not contain a Symbol column.")
    df["Symbol"] = (
        df["Symbol"].astype(str).str.strip().str.upper()
        .str.replace(".NS", "", regex=False)
    )
    return df.drop_duplicates("Symbol")

def fetch_chartink(url, cookie_value=""):
    if not url.strip():
        raise ValueError("Enter your Chartink scanner URL.")
    r = requests.get(url.strip(), headers=chartink_headers(cookie_value), timeout=25)
    r.raise_for_status()
    tables = pd.read_html(io.StringIO(r.text))
    if not tables:
        raise ValueError(
            "No result table was found. The scan may require an authenticated "
            "session or a result endpoint not exposed in the page HTML."
        )
    for table in tables:
        try:
            x = normalize_chartink(table)
            if len(x):
                return x
        except Exception:
            continue
    raise ValueError("Could not identify a Chartink Symbol column.")

# -----------------------------
# MARKET DATA
# -----------------------------
@st.cache_data(ttl=60)
def get_data(symbol, interval):
    try:
        ticker = symbol if symbol.endswith(".NS") else symbol + ".NS"
        period = "5d" if interval in ("5m", "15m") else "1y"
        df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        required = ["Open", "High", "Low", "Close", "Volume"]
        if not all(c in df.columns for c in required):
            return None
        df = df[required].dropna().copy()
        return df if len(df) >= 20 else None
    except Exception:
        return None

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def add_features(df):
    x = df.copy()
    x["VWAP"] = (x["Close"] * x["Volume"]).cumsum() / x["Volume"].replace(0, np.nan).cumsum()
    x["RSI"] = rsi(x["Close"])
    x["VolSMA20"] = x["Volume"].rolling(20).mean()
    x["RVOL"] = x["Volume"] / x["VolSMA20"].replace(0, np.nan)
    x["EMA20"] = x["Close"].ewm(span=20, adjust=False).mean()
    x["EMA50"] = x["Close"].ewm(span=50, adjust=False).mean()
    x["Range"] = (x["High"] - x["Low"]).replace(0, np.nan)
    return x

# -----------------------------
# F&O FILTER
# -----------------------------
# This is a configurable starter list. For production, replace it with
# an exchange/broker-maintained F&O universe or upload your own current list.
DEFAULT_FNO = set("""
ABB AARTIIND ABCAPITAL ABFRL ACC ADANIENT ADANIPORTS ALKEM AMBUJACEM APOLLOHOSP APOLLOTYRE ASHOKLEY ASIANPAINT ASTRAL ATUL AUROPHARMA AXISBANK BAJAJ-AUTO BAJAJFINSV BAJFINANCE BALKRISIND BANDHANBNK BANKBARODA BEL BHARATFORG BHEL BIOCON BOSCHLTD BPCL BRITANNIA BSE CANBK CESC CGPOWER CHAMBLFERT CHOLAFIN CIPLA COALINDIA COFORGE COLPAL CONCOR CROMPTON CUB CUMMINS DABUR DALBHARAT DEEPAKNTR DELHIVERY DELTACORP DIVISLAB DIXON DLF DMART DRREDDY EICHERMOT ESCORTS EXIDEIND FEDERALBNK GAIL GLENMARK GODREJCP GODREJPROP GRASIM HAL HAVELLS HCLTECH HDFCAMC HDFCBANK HDFCLIFE HEROMOTOCO HINDALCO HINDCOPPER HINDPETRO HINDUNILVR HUDCO ICICIBANK ICICIGI ICICIPRULI IDEA IDFCFIRSTB IGL INDHOTEL INDIACEM INDIAMART INDIANB INDIANENERGY INDIGO INDUSINDBANK INDUSTOWER INFY IRCTC IREDA IRFC ITC JINDALSTEL JIOFIN JSWENERGY JSWSTEEL JUBLFOOD KALYANKJIL KAYNES KEI KFINTECH KOTAKBANK LALPATHLAB LAURUSLABS LICHSGFIN LICI LT LUPIN M&M M&MFIN MANAPPURAM MARICO MARUTI MAXHEALTH MCX MFSL MGL MOTHERSON MPHASIS MRF MUTHOOTFIN NATIONALUM NAUKRI NAVINFLUOR NBCC NESTLEIND NHPC NMDC NTPC NYKAA OBEROIRLTY ONGC PAGEIND PAYTM PEL PERSISTENT PETRONET PFC PGEL PIDILITIND PIIND PNB POLICYBZR POLYCAB POWERGRID POWERINDIA PPLPHARMA PRESTIGE PVRINOX RBLBANK RECLTD RELIANCE RVNL SAIL SBICARD SBILIFE SBIN SHREECEM SHRIRAMFIN SIEMENS SJVN SOLARINDS SONACOMS SRF SRTRANSFIN STAR SUZLON SYNGENE TATACHEM TATACONSUM TATAMOTORS TATAPOWER TATASTEEL TCS TECHM TIINDIA TITAN TORNTPHARM TRENT TVSMOTOR UBL ULTRACEMCO UNIONBANK UNITDSPR UPL VBL VEDL VOLTAS WIPRO YESBANK ZYDUSLIFE
""".split())

def is_fno(symbol):
    return symbol.replace(".NS", "").upper() in DEFAULT_FNO

# -----------------------------
# SCORING
# -----------------------------
def analyze(symbol, interval):
    df = get_data(symbol, interval)
    if df is None:
        return None

    x = add_features(df)
    last = x.iloc[-1]
    prev = x.iloc[-2]

    close = float(last.Close)
    high = float(last.High)
    low = float(last.Low)
    open_ = float(last.Open)
    prev_close = float(prev.Close)

    score_buy = 0
    score_sell = 0
    reasons_buy = []
    reasons_sell = []

    # Trend: 15 pts
    if last.EMA20 > last.EMA50:
        score_buy += 15
        reasons_buy.append("EMA20 > EMA50")
    elif last.EMA20 < last.EMA50:
        score_sell += 15
        reasons_sell.append("EMA20 < EMA50")

    # VWAP: 15 pts
    if close > last.VWAP:
        score_buy += 15
        reasons_buy.append("Above VWAP")
    elif close < last.VWAP:
        score_sell += 15
        reasons_sell.append("Below VWAP")

    # Relative volume: 15 pts
    rvol = float(last.RVOL) if pd.notna(last.RVOL) else 0
    if rvol >= 2:
        score_buy += 15
        score_sell += 15
        reasons_buy.append(f"RVOL {rvol:.1f}x")
        reasons_sell.append(f"RVOL {rvol:.1f}x")
    elif rvol >= 1.3:
        score_buy += 9
        score_sell += 9
        reasons_buy.append(f"RVOL {rvol:.1f}x")
        reasons_sell.append(f"RVOL {rvol:.1f}x")

    # RSI: 10 pts
    rv = float(last.RSI) if pd.notna(last.RSI) else 50
    if 55 <= rv <= 70:
        score_buy += 10
        reasons_buy.append(f"RSI {rv:.0f}")
    if 30 <= rv <= 45:
        score_sell += 10
        reasons_sell.append(f"RSI {rv:.0f}")

    # Candle strength: 10 pts
    if close > open_ and close >= high - 0.25 * (high - low):
        score_buy += 10
        reasons_buy.append("Strong bullish candle")
    if close < open_ and close <= low + 0.25 * (high - low):
        score_sell += 10
        reasons_sell.append("Strong bearish candle")

    # Breakout / breakdown: 20 pts
    lookback = x.iloc[:-1].tail(20)
    prev_high = float(lookback.High.max()) if len(lookback) else high
    prev_low = float(lookback.Low.min()) if len(lookback) else low
    if close > prev_high:
        score_buy += 20
        reasons_buy.append("20-bar breakout")
    if close < prev_low:
        score_sell += 20
        reasons_sell.append("20-bar breakdown")

    # Gap momentum: 5 pts
    gap = (open_ / prev_close - 1) * 100 if prev_close else 0
    if gap >= 1 and close > open_:
        score_buy += 5
        reasons_buy.append(f"Gap +{gap:.1f}%")
    if gap <= -1 and close < open_:
        score_sell += 5
        reasons_sell.append(f"Gap {gap:.1f}%")

    # Market-data quality / risk: 10 pts
    if rvol >= 1.3 and (high - low) > 0:
        score_buy += 5
        score_sell += 5

    if score_buy >= score_sell:
        direction = "BUY"
        score = min(100, score_buy)
        entry = high
        sl = low
        reason = ", ".join(reasons_buy[:5])
        risk = max(entry - sl, entry * 0.003)
        target = entry + 2 * risk
    else:
        direction = "SELL"
        score = min(100, score_sell)
        entry = low
        sl = high
        reason = ", ".join(reasons_sell[:5])
        risk = max(sl - entry, entry * 0.003)
        target = entry - 2 * risk

    return {
        "Stock": symbol.replace(".NS", ""),
        "Signal": direction if score >= 70 else "WAIT",
        "Score": int(round(score)),
        "Entry": round(entry, 2),
        "SL": round(sl, 2),
        "Target": round(target, 2),
        "VWAP": round(float(last.VWAP), 2),
        "RSI": round(rv, 1),
        "RVOL": round(rvol, 2),
        "Setup": reason or "Insufficient confluence",
        "F&O": "YES" if is_fno(symbol) else "NO",
    }

# -----------------------------
# 9:20 / 9:25 CONFIRMATION
# -----------------------------
def opening_confirmation(symbol):
    df = get_data(symbol, "5m")
    if df is None or len(df) < 10:
        return "N/A"
    x = df.copy()
    try:
        idx = pd.to_datetime(x.index)
        if idx.tz is None:
            idx = idx.tz_localize("UTC").tz_convert("Asia/Kolkata")
        else:
            idx = idx.tz_convert("Asia/Kolkata")
        x.index = idx
        today = x[x.index.date == pd.Timestamp.now(tz="Asia/Kolkata").date()]
        if today.empty:
            return "N/A"
        c920 = today.between_time("09:20", "09:24")
        c925 = today.between_time("09:25", "09:29")
        if c920.empty or c925.empty:
            return "WAIT"
        a, b = c920.iloc[-1], c925.iloc[-1]
        if b.Close > a.High and b.Volume > a.Volume:
            return "BUY CONFIRMED"
        if b.Close < a.Low and b.Volume > a.Volume:
            return "SELL CONFIRMED"
        return "WAIT"
    except Exception:
        return "N/A"

# -----------------------------
# -----------------------------
# LOAD CANDIDATES
# -----------------------------
if source == "Chartink Live":
    st.subheader("🟢 LIVE — Chartink MASTER SCANNER")
    st.caption("Chartink candidates → SMT PRO market-data validation → ranked TOP 2.")
    if not scan_url:
        st.info("Paste your Chartink scanner URL in the sidebar.")
        st.stop()

    if st.button("🔄 Fetch Chartink + Run SMT PRO", type="primary"):
        try:
            candidates = fetch_chartink(scan_url, cookie)
        except Exception as e:
            st.error(f"Chartink fetch failed: {e}")
            st.info("If your scan requires an authenticated session, provide your own authorized session cookie or use CSV mode.")
            st.stop()
    else:
        st.info("Click **Fetch Chartink + Run SMT PRO**.")
        st.stop()

else:
    st.subheader("📂 CSV — OLD SCANNER")
    st.caption("Original workflow preserved: CSV → Yahoo Finance → BUY/SELL → TOP 2.")
    uploaded = st.file_uploader("📂 Upload Chartink CSV", type=["csv"])
    if not uploaded:
        st.info("Upload your existing Chartink CSV.")
        st.stop()
    candidates = normalize_chartink(pd.read_csv(uploaded))

symbols = candidates["Symbol"].tolist()
if fno_only:
    symbols = [s for s in symbols if is_fno(s)]

st.write(f"**Chartink candidates:** {len(candidates)}  |  **After F&O filter:** {len(symbols)}")

if not symbols:
    st.warning("No candidates remain after the F&O filter.")
    st.stop()

with st.spinner("Analysing price action, VWAP, volume and momentum..."):
    rows = []
    for s in symbols:
        result = analyze(s, timeframe)
        if result:
            if timeframe in ("5m", "15m"):
                result["9:20/9:25"] = opening_confirmation(s)
            else:
                result["9:20/9:25"] = "N/A"
            rows.append(result)

results = pd.DataFrame(rows)
if results.empty:
    st.error("No market data returned. Try during market hours or use a supported interval.")
    st.stop()

results = results.sort_values(["Score", "RVOL"], ascending=False)
qualified = results[(results.Score >= min_score) & (results.Signal.isin(["BUY", "SELL"]))].head(int(top_n))

st.subheader("🔥 TOP HIGH-PROBABILITY SETUPS")
if qualified.empty:
    st.warning("No setup crossed your minimum score. Stay disciplined.")
else:
    cols = st.columns(min(2, len(qualified)))
    for i, (_, r) in enumerate(qualified.iterrows()):
        with cols[i % len(cols)]:
            st.markdown(f"### #{i+1} {r.Stock}")
            st.metric("SMT PRO Score", f"{r.Score}/100")
            st.write(f"**Signal:** {r.Signal}")
            st.write(f"**Entry:** ₹{r.Entry}")
            st.write(f"**SL:** ₹{r.SL}")
            st.write(f"**Target:** ₹{r.Target}")
            st.write(f"**VWAP:** ₹{r.VWAP}")
            st.write(f"**RSI:** {r.RSI} | **RVOL:** {r.RVOL}x")
            st.write(f"**9:20/9:25:** {r['9:20/9:25']}")
            st.caption(r.Setup)

st.subheader("📊 All Ranked Results")
st.dataframe(results, use_container_width=True)

st.download_button(
    "⬇️ Download ranked results",
    results.to_csv(index=False).encode("utf-8"),
    "smt_pro_ranked_results.csv",
    "text/csv",
)

st.caption("⚠️ Educational use only. A high score is not a guarantee of profit. Confirm live price, liquidity and risk before trading.")
