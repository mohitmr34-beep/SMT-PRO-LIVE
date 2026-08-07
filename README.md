# SMT PRO — EXACT CHARTINK CONDITIONS / TWO MODES

## Modes

1. 🟢 LIVE — Chartink
2. 📂 CSV — OLD

There is no manual-symbol mode.

## Exact scanner logic from the supplied Chartink screenshot

The root group is **passes any 1** (OR).

### Group 1 — BUY
- Daily Close >= Daily Max(252, Daily High) × 0.98
- Daily Volume > Daily SMA(Daily Volume, 20) × 1.5
- Daily Close > Daily Open

### Group 2 — SELL
- Daily High >= Daily Max(252, Daily High)
- Daily Close < Daily Open
- Daily Volume > Daily SMA(Daily Volume, 20) × 1.5

### Group 3 — BUY
- Daily Open > 1 day ago Close × 1.02
- Daily Volume > Daily SMA(Daily Volume, 20) × 2
- Daily Close > Daily Open

The app evaluates these conditions on Yahoo **daily** data. This is deliberate because the supplied Chartink scanner conditions are Daily, not 5-minute conditions.

## LIVE Chartink retrieval

Chartink scanner result pages load their stock table dynamically. The app therefore does NOT use `pandas.read_html()`.

It:
1. GETs the scanner page.
2. Gets the CSRF token.
3. Attempts to recover the scanner's `scan_clause`.
4. POSTs to Chartink `/screener/process`.
5. Reads the JSON `data` response.
6. Sends only the symbols into the same common engine.

If automatic scan_clause recovery fails, the LIVE troubleshooting box lets you paste the scan_clause from:
Chrome → F12 → Network → Fetch/XHR → process → Payload.

Use only your own authorized session cookie.

## CSV mode

Your original Chartink CSV is used only as the candidate list. The same daily-condition engine is then applied to those symbols.

## Why this version is different from the earlier build

The earlier build invented a second scoring system (VWAP/RSI/RVOL/EMA), which is why it could produce MARINE while the original scanner produced ALLCARGO/NAVINFLUOR.

This version removes that second scoring system. Both modes use the same Chartink-condition engine.

## Important data difference

Even with identical logic, Chartink and Yahoo can disagree because of:
- different data feeds
- intraday update timing
- corporate-action adjustments
- trading-session timing
- Chartink subscription/realtime mode

Therefore the first validation should be done with the same CSV and same market date.
