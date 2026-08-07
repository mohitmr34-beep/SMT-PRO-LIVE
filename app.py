import io
import json
import re
import html
import requests
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
from bs4 import BeautifulSoup

st.set_page_config(page_title="SMT PRO LIVE", layout="wide")
st.title("📊 SMT PRO LIVE")
st.caption("Chartink LIVE + OLD CSV • SAME Chartink-condition engine")

DEFAULT_SCAN_URL = "https://chartink.com/screener/master-scanner-18062057"

# ============================================================
# MODE
# ============================================================
with st.sidebar:
    st.header("⚙️ Scanner")
    mode = st.radio(
        "Mode",
        ["🟢 LIVE — Chartink", "📂 CSV — OLD"],
        index=1
    )

    st.info(
        "The Master Scanner shown by the user uses DAILY conditions. "
        "The validation engine therefore uses daily Yahoo data for the scan logic."
    )

    if mode.startswith("🟢"):
        scan_url = st.text_input("Chartink Scanner URL", DEFAULT_SCAN_URL)
        cookie = st.text_input(
            "Chartink Cookie (optional)",
            type="password",
            help="Use only your own authorized session. Never share or commit the value."
        )

    run = st.button("🚀 RUN SCANNER", type="primary")

# ============================================================
# YAHOO DAILY DATA
# ============================================================
@st.cache_data(ttl=120, show_spinner=False)
def get_daily(symbol):
    try:
        ticker = symbol if symbol.endswith(".NS") else symbol + ".NS"
        df = yf.download(
            ticker,
            period="2y",
            interval="1d",
            progress=False,
            auto_adjust=False,
            threads=False
        )

        if df is None or df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        needed = ["Open", "High", "Low", "Close", "Volume"]
        if not all(c in df.columns for c in needed):
            return None

        df = df[needed].dropna().copy()
        return df if len(df) >= 30 else None
    except Exception:
        return None

# ============================================================
# EXACT CONDITIONS FROM THE USER'S CHARTINK SCREENSHOT
#
# Root: passes ANY 1 of these groups
#
# GROUP 1:
# Daily Close >= Daily Max(252, Daily High) * 0.98
# AND Daily Volume > Daily SMA(Daily Volume,20) * 1.5
# AND Daily Close > Daily Open
#
# GROUP 2:
# Daily High >= Daily Max(252, Daily High)
# AND Daily Close < Daily Open
# AND Daily Volume > Daily SMA(Daily Volume,20) * 1.5
#
# GROUP 3:
# Daily Open > 1 day ago Close * 1.02
# AND Daily Volume > Daily SMA(Daily Volume,20) * 2
# AND Daily Close > Daily Open
#
# Root operator is OR / "passes any 1".
# ============================================================
def evaluate_chartink_conditions(df):
    if df is None or len(df) < 252:
        return {
            "Matched": False,
            "Signal": "NO DATA",
            "Setup": "",
            "VolumeRatio": None,
            "High252": None
        }

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    close = float(latest["Close"])
    open_ = float(latest["Open"])
    high = float(latest["High"])
    volume = float(latest["Volume"])
    prev_close = float(prev["Close"])

    # Chartink's Daily Max(252, Daily High), evaluated on the current daily bar.
    high252 = float(df["High"].rolling(252, min_periods=252).max().iloc[-1])

    # Daily SMA(Daily Volume, 20)
    vol_sma20 = float(df["Volume"].rolling(20, min_periods=20).mean().iloc[-1])

    if not np.isfinite(high252) or not np.isfinite(vol_sma20) or vol_sma20 <= 0:
        return {
            "Matched": False,
            "Signal": "NO DATA",
            "Setup": "",
            "VolumeRatio": None,
            "High252": high252
        }

    volume_ratio = volume / vol_sma20

    group1 = (
        close >= high252 * 0.98
        and volume > vol_sma20 * 1.5
        and close > open_
    )

    group2 = (
        high >= high252
        and close < open_
        and volume > vol_sma20 * 1.5
    )

    group3 = (
        open_ > prev_close * 1.02
        and volume > vol_sma20 * 2
        and close > open_
    )

    setups = []
    if group1:
        setups.append("G1: 98% of 252D High + 1.5x Vol + Green")
    if group2:
        setups.append("G2: 252D High Rejection + 1.5x Vol + Red")
    if group3:
        setups.append("G3: +2% Gap + 2x Vol + Green")

    # This scanner is a candidate generator. Direction comes from the matched group.
    if group2 and not (group1 or group3):
        signal = "SELL"
    elif group1 or group3:
        signal = "BUY"
    else:
        signal = "WAIT"

    return {
        "Matched": bool(setups),
        "Signal": signal,
        "Setup": " | ".join(setups),
        "VolumeRatio": round(volume_ratio, 2),
        "High252": round(high252, 2)
    }

# ============================================================
# CHARTINK LIVE FETCH
#
# Chartink results are loaded dynamically through POST /screener/process.
# The public page does not contain a normal HTML result table.
# We first obtain CSRF and session cookies, then try to recover the
# scanner's scan_clause from the page. If the page doesn't expose it,
# the user can paste the scan_clause from DevTools Network -> process.
# ============================================================
def get_csrf(html_text):
    soup = BeautifulSoup(html_text, "lxml")
    meta = soup.select_one('meta[name="csrf-token"]')
    if meta and meta.get("content"):
        return meta["content"]

    m = re.search(
        r'<meta[^>]+name=["\']csrf-token["\'][^>]+content=["\']([^"\']+)["\']',
        html_text,
        re.I
    )
    return m.group(1) if m else None

def recover_scan_clause(html_text):
    candidates = []

    # Common HTML/JS forms.
    patterns = [
        r'"scan_clause"\s*:\s*"((?:\\.|[^"\\])*)"',
        r"'scan_clause'\s*:\s*'((?:\\.|[^'\\])*)'",
        r'"scan_clause"\s*:\s*`([^`]*)`',
        r"scan_clause\s*=\s*['\"]([^'\"]+)['\"]",
    ]

    for pattern in patterns:
        for m in re.finditer(pattern, html_text, re.I | re.S):
            value = m.group(1)
            try:
                value = json.loads('"' + value + '"')
            except Exception:
                value = html.unescape(value)
            value = value.replace("\\/", "/").replace("\\'", "'")
            value = value.replace("+", " ").strip()
            if "scan_clause" not in value.lower() and len(value) > 10:
                candidates.append(value)

    # Some pages expose a URL-encoded form.
    if not candidates:
        m = re.search(r'name=["\']scan_clause["\'][^>]*value=["\']([^"\']+)', html_text, re.I)
        if m:
            candidates.append(html.unescape(m.group(1)).replace("+", " ").strip())

    # Prefer a Chartink clause containing a segment and latest/daily terms.
    ranked = sorted(
        set(candidates),
        key=lambda x: (
            "{cash}" in x or "{futures}" in x or "{nifty" in x,
            "daily" in x.lower() or "latest" in x.lower(),
            len(x)
        ),
        reverse=True
    )
    return ranked[0] if ranked else None

def fetch_chartink_live(url, cookie_value="", manual_clause=""):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Referer": "https://chartink.com/",
    })

    if cookie_value.strip():
        # User-provided authorized cookie string.
        for part in cookie_value.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                session.cookies.set(k.strip(), v.strip(), domain="chartink.com")

    page = session.get(url, timeout=25)
    page.raise_for_status()

    csrf = get_csrf(page.text)
    if not csrf:
        raise RuntimeError("Could not obtain Chartink CSRF token from the scanner page.")

    scan_clause = manual_clause.strip() or recover_scan_clause(page.text)
    if not scan_clause:
        raise RuntimeError(
            "Chartink page did not expose its scan_clause automatically. "
            "Use DevTools → Network → Fetch/XHR → process → Payload and paste the "
            "scan_clause into the optional field in the sidebar."
        )

    headers = {
        "X-CSRF-TOKEN": csrf,
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": url,
    }

    response = session.post(
        "https://chartink.com/screener/process",
        headers=headers,
        data={"scan_clause": scan_clause},
        timeout=30
    )
    response.raise_for_status()

    try:
        payload = response.json()
    except Exception:
        raise RuntimeError(
            f"Chartink returned non-JSON data (HTTP {response.status_code}). "
            "Your session/cookie may have expired or the scanner may require access."
        )

    data = payload.get("data", [])
    if not data:
        raise RuntimeError(
            "Chartink returned zero stocks. Check the scan, session, subscription/data mode, "
            "or the scan_clause."
        )

    df = pd.DataFrame(data)

    possible = ["nsecode", "symbol", "name"]
    col = next((c for c in possible if c in df.columns), None)
    if col is None:
        raise RuntimeError(f"Chartink response did not contain a stock-symbol field. Columns: {list(df.columns)}")

    symbols = (
        df[col].astype(str).str.strip().str.upper()
        .str.replace(".NS", "", regex=False)
        .tolist()
    )
    symbols = list(dict.fromkeys([s for s in symbols if s and s != "NAN"]))

    return symbols, scan_clause

# ============================================================
# RUN
# ============================================================
if not run:
    if mode.startswith("📂"):
        st.info("Upload your original Chartink CSV, then click RUN SCANNER.")
        st.stop()
    st.info("LIVE mode is ready. Click RUN SCANNER.")
    st.stop()

# Source candidates
if mode.startswith("📂"):
    uploaded = st.file_uploader(
        "📂 Upload MASTER SCANNER CSV",
        type=["csv"],
        key="old_csv"
    )
    if uploaded is None:
        st.warning("Please upload your original MASTER SCANNER CSV.")
        st.stop()

    source_df = pd.read_csv(uploaded)

    if "Symbol" not in source_df.columns:
        st.error("CSV must contain a Symbol column.")
        st.stop()

    symbols = (
        source_df["Symbol"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
        .str.replace(".NS", "", regex=False)
    )
    symbols = list(dict.fromkeys(symbols.tolist()))
    scan_clause = "CSV source — no Chartink request"
    source_label = "OLD CSV"

else:
    # Optional clause override is shown only after button, so the normal path stays simple.
    with st.expander("🔧 LIVE troubleshooting / scan_clause override", expanded=False):
        clause_override = st.text_area(
            "Optional Chartink scan_clause",
            value="",
            height=130,
            help="Normally leave blank. If auto-detection fails, paste ONLY scan_clause from Network → process → Payload."
        )

    try:
        symbols, scan_clause = fetch_chartink_live(
            scan_url,
            cookie,
            clause_override
        )
        source_label = "CHARTINK LIVE"
    except Exception as e:
        st.error(f"Chartink LIVE fetch failed: {e}")
        st.stop()

st.success(f"{source_label}: {len(symbols)} candidates loaded.")

# ============================================================
# COMMON ENGINE
# ============================================================
rows = []
progress = st.progress(0)

for i, symbol in enumerate(symbols):
    df = get_daily(symbol)
    verdict = evaluate_chartink_conditions(df)

    rows.append({
        "Stock": symbol,
        "Signal": verdict["Signal"],
        "Matched": "YES" if verdict["Matched"] else "NO",
        "Setup": verdict["Setup"],
        "Volume / SMA20": verdict["VolumeRatio"],
        "252D High": verdict["High252"],
    })

    progress.progress((i + 1) / max(len(symbols), 1))

progress.empty()

results = pd.DataFrame(rows)

# ============================================================
# TOP 2
#
# Preserve source order rather than silently inventing a new ranking.
# This is important for validating the old CSV result against LIVE.
# ============================================================
qualified = results[
    (results["Matched"] == "YES") &
    (results["Signal"].isin(["BUY", "SELL"]))
].head(2)

st.subheader("📊 All Results")
st.dataframe(results, use_container_width=True)

st.subheader("🔥 TOP 2")
if qualified.empty:
    st.warning("No candidate matched the exact three Chartink conditions using Yahoo daily data.")
else:
    st.dataframe(qualified, use_container_width=True)

    cards = st.columns(len(qualified))
    for i, (_, row) in enumerate(qualified.iterrows()):
        with cards[i]:
            st.markdown(f"### #{i+1} {row['Stock']}")
            st.metric("Signal", row["Signal"])
            st.write(f"**Volume/SMA20:** {row['Volume / SMA20']}x")
            st.write(f"**Setup:** {row['Setup']}")

st.download_button(
    "⬇️ Download Results",
    results.to_csv(index=False).encode("utf-8"),
    "smt_pro_chartink_results.csv",
    "text/csv"
)

st.caption(
    "⚠️ This reproduces the visible Chartink conditions as closely as possible using Yahoo daily data. "
    "Chartink and Yahoo may differ in feed timing/data, so exact real-time parity is not guaranteed. "
    "Educational use only."
)
