# SMT PRO AI Scanner — Old CSV + Chartink LIVE

This build uses the uploaded original `app (1).py` as the reference.

## ONLY TWO MODES

### 1. CSV — OLD APP
The original CSV workflow is preserved:
CSV -> Yahoo Finance -> original `get_data()` -> original `analyze_stock()` -> original Top 2 selection.

The original fallback F&O list is also retained if no CSV is uploaded.

### 2. LIVE — Chartink
Only the candidate-stock source is added. The same Yahoo Finance `get_data()` and the same `analyze_stock()` function are used afterward.

Default scanner:
https://chartink.com/screener/master-scanner-18062057

The LIVE connector attempts Chartink's dynamic `/screener/process` endpoint instead of `pandas.read_html()`.

## Important
- No VWAP/RSI/EMA replacement.
- No new AI score.
- No changed entry/SL/target formulas.
- No changed Top-2 ranking logic.
- Timeframe selector remains 5m, 15m, 1d exactly as in the original app.
- Chartink cookies, passwords and tokens must never be committed to GitHub.

If LIVE fails because Chartink does not expose the scanner clause to the request, use the exact authenticated Network request from your browser; the CSV mode remains fully independent.
