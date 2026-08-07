# SMT PRO — SIMPLE TWO-MODE BUILD

## The rule

The uploaded old app is the trading engine.

The Chartink CSV is already the filtered candidate list.

No Chartink conditions are duplicated in Python.

No VWAP, RSI, EMA, volume scoring, AI probability or new ranking logic is added.

## Two modes

### CSV OLD
Your existing:
CSV -> Yahoo -> original analyze_stock() -> original Top 2

### LIVE
Chartink -> candidate symbols -> the exact same original Yahoo/analyze_stock/Top-2 engine.

The LIVE connector is intentionally isolated from the old CSV path.

## Important

If Chartink does not expose the scanner clause in its page response, LIVE will stop with a clear message rather than silently inventing a different candidate list.

Do not put real Chartink cookies or credentials in source control.
