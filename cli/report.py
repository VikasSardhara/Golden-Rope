import os, sys, json, requests
from datetime import datetime, timedelta, timezone
from dateutil import tz
from tabulate import tabulate

def log(x): print(x, flush=True)

SUPABASE_URL = os.environ.get("SUPABASE_URL","").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY","")
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    log("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_KEY"); sys.exit(1)

HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
}
JSON_HEADERS = {**HEADERS, "Content-Type":"application/json"}

ARTICLES = f"{SUPABASE_URL}/rest/v1/articles"
EVENTS   = f"{SUPABASE_URL}/rest/v1/events"
SIGNALS  = f"{SUPABASE_URL}/rest/v1/signals"

# Minimal ticker->sector map (expand later)
SECTOR = {
    "JPM":"Financials","GS":"Financials","MS":"Financials","C":"Financials","BAC":"Financials","WFC":"Financials",
    "BLK":"Financials","BX":"Financials",
    "AAPL":"Information Technology","MSFT":"Information Technology","NVDA":"Information Technology",
    "GOOGL":"Communication Services","META":"Communication Services","AMZN":"Consumer Discretionary","TSLA":"Consumer Discretionary"
}

# Historical priors for event types (toy; expand later)
PRIORS = {
    ("CEO_CHANGE","Financials"): {"1D": -0.012, "5D": -0.004, "20D": 0.000},
    ("CEO_CHANGE","Information Technology"): {"1D": -0.008, "5D": -0.003, "20D": 0.000},
    ("CEO_CHANGE","Communication Services"): {"1D": -0.010, "5D": -0.003, "20D": 0.000},
    ("CEO_CHANGE","Consumer Discretionary"): {"1D": -0.010, "5D": -0.004, "20D": 0.000},
}

def fmt_pct(x):
    if x is None: return "-"
    return f"{x*100:.2f}%"

def get_recent_events(hours=12, limit=100):
    url = f"{EVENTS}?select=*,articles(title,summary,source,url)&order=created_at.desc&limit={limit}"
    r = requests.get(url, headers=HEADERS, timeout=30); r.raise_for_status()
    rows = r.json()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    out = []
    for ev in rows:
        created = ev.get("created_at")
        if not created: continue
        ts = datetime.fromisoformat(created.replace("Z","+00:00"))
        if ts >= cutoff:
            out.append(ev)
    return out

def get_signals_for_event(event_id):
    url = f"{SIGNALS}?select=*&event_id=eq.{event_id}"
    r = requests.get(url, headers=HEADERS, timeout=30); r.raise_for_status()
    return r.json()

def suggest_trade(ticker, horizon_pred):
    """
    Simple narration + hedge suggestion.
    horizon_pred is dict like {"1D": -0.012, "5D": -0.004, "20D": 0.0}
    """
    one_d = horizon_pred.get("1D")
    if one_d is None: return "No suggestion."
    if one_d < -0.002:
        return f"SHORT {ticker}, hedge sector via XLF (beta ≈ 1.1) to isolate idiosyncratic move."
    elif one_d > 0.002:
        return f"LONG {ticker}, hedge with short XLF (beta ≈ 1.1)."
    return "Small/neutral edge; monitor for follow-ups (successor named, guidance)."

def scale_priors_with_sentiment(event):
    et = event.get("event_type")
    tkr = event.get("primary_ticker")
    sector = SECTOR.get(tkr, "Unknown")
    base = PRIORS.get((et, sector))
    if not base:
        return None, sector

    s = event.get("sentiment")
    if s is None:
        return base, sector

    alpha = 0.75  # sensitivity
    scale = 1 + alpha * s
    scaled = {}
    for k, v in base.items():
        adj = v * scale
        # clamp to +/-5% for sanity
        if adj > 0.05: adj = 0.05
        if adj < -0.05: adj = -0.05
        scaled[k] = adj
    return scaled, sector

def main():
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"[GRMM REPORT @ {now_utc}]\n")

    events = get_recent_events(hours=24, limit=200)

    if not events:
        print("No recent events. Ingestion/extraction may still be populating. ✅")
        return

    # Only show supported event types for now
    shown = 0
    for ev in events:
        if ev.get("event_type") != "CEO_CHANGE":  # extend with more types later
            continue

        shown += 1
        eid = ev["event_id"]
        tkr = ev.get("primary_ticker") or "-"
        headline = ((ev.get("extracted") or {}).get("headline") or "").strip()
        sentiment = ev.get("sentiment")
        conf = ev.get("confidence")

        scaled, sector = scale_priors_with_sentiment(ev)
        base = PRIORS.get((ev.get("event_type"), sector))

        print(f"{shown}) {ev.get('event_type')} — {tkr} ({headline[:80] + ('…' if len(headline)>80 else '')})")
        print(f"   Sentiment: {sentiment if sentiment is not None else '-'} "
              f"(conf {conf if conf is not None else '-'})")

        if base:
            print(f"   Historical prior ({sector}, {ev.get('event_type')}): "
                  f"1D: {fmt_pct(base['1D'])}, 5D: {fmt_pct(base['5D'])}, 20D: {fmt_pct(base['20D'])}")
        else:
            print(f"   Historical prior: (none for sector={sector})")

        if scaled:
            print(f"   Forecast (sentiment-adjusted): "
                  f"1D: {fmt_pct(scaled.get('1D'))}, "
                  f"5D: {fmt_pct(scaled.get('5D'))}, "
                  f"20D: {fmt_pct(scaled.get('20D'))}")
            print(f"   Suggested trade idea: {suggest_trade(tkr, scaled)}")
        else:
            print("   Forecast: not available (missing priors for this sector/ticker).")

        # Also show any stored signals (if your signals job already wrote them)
        sigs = get_signals_for_event(eid)
        if sigs:
            table = []
            for srow in sorted(sigs, key=lambda r: r["horizon"]):
                table.append([srow["horizon"], fmt_pct(srow["predicted_return"]), srow.get("direction")])
            print(tabulate(table, headers=["Horizon","Predicted Return","Dir"], tablefmt="github"))
        print()

    if shown == 0:
        print("No supported events in the last 24h (looking for CEO_CHANGE).")
        print("Tip: insert a dummy CEO headline to test the full narrative output.\n")

if __name__ == "__main__":
    main()
