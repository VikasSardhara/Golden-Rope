import os, sys, json, requests
from datetime import datetime, timedelta, timezone

def log(x): print(x, flush=True)

SUPABASE_URL = os.environ.get("SUPABASE_URL","").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY","")

HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"
}
JSON_HEADERS = {**HEADERS, "Content-Type":"application/json"}

EVENTS   = f"{SUPABASE_URL}/rest/v1/events"
SIGNALS  = f"{SUPABASE_URL}/rest/v1/signals"

# toy priors for CEO_CHANGE events
PRIORS = {
    "CEO_CHANGE": {"1D": -0.01, "5D": -0.004, "20D": 0.0}
}

def recent_events(hours=12, limit=200):
    url = f"{EVENTS}?select=*&order=created_at.desc&limit={limit}"
    r = requests.get(url, headers=HEADERS, timeout=30); r.raise_for_status()
    rows = r.json()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    out = []
    for ev in rows:
        dt = datetime.fromisoformat(ev["created_at"].replace("Z","+00:00"))
        if dt >= cutoff:
            out.append(ev)
    return out

def already_have_signal(event_id):
    url = f"{SIGNALS}?select=signal_id&event_id=eq.{event_id}&limit=1"
    r = requests.get(url, headers=HEADERS, timeout=30); r.raise_for_status()
    return len(r.json()) > 0

def insert_signals(ev, priors):
    # scale the prior by sentiment in [-1,+1]
    alpha = 0.75  # sensitivity (tune later)
    s = ev.get("sentiment")
    scale = (1 + alpha * s) if s is not None else 1.0

    rows = []
    for horizon, base_pred in priors.items():
        adj = base_pred * scale
        # safety clamp ±5% to avoid crazy values
        adj = max(min(adj, 0.05), -0.05)
        rows.append({
            "event_id": ev["event_id"],
            "ticker": ev.get("primary_ticker"),
            "horizon": horizon,
            "predicted_return": adj,
            "uncertainty": 0.02,
            "direction": 1 if adj > 0 else -1 if adj < 0 else 0
        })

    r = requests.post(SIGNALS, headers=JSON_HEADERS, data=json.dumps(rows), timeout=30)
    if r.status_code not in (200,201,204,409):
        raise RuntimeError(f"Insert signals failed {r.status_code}: {r.text[:200]}")


def process():
    evs = recent_events()
    log(f"Fetched {len(evs)} recent events")
    made = 0
    for e in evs:
        if already_have_signal(e["event_id"]): continue
        if e["event_type"] in PRIORS:
            try:
                insert_signals(e, PRIORS[e["event_type"]])
                made += 1
            except Exception as ex:
                log(f"⚠️ Failed on event {e['event_id']}: {ex}")
    log(f"Created signals: {made}")

if __name__ == "__main__":
    process()
