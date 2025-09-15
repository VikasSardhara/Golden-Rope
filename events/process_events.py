import os, sys, json, time, regex as re
from datetime import datetime, timedelta, timezone
import requests

def log(x): print(x, flush=True)

SUPABASE_URL = os.environ.get("SUPABASE_URL","").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY","")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    log("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_KEY"); sys.exit(1)

HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"
}
JSON_HEADERS = {**HEADERS, "Content-Type":"application/json"}

ARTICLES = f"{SUPABASE_URL}/rest/v1/articles"
EVENTS   = f"{SUPABASE_URL}/rest/v1/events"

# Minimal alias map (extend over time)
ALIASES = {
    "JPMorgan": "JPM", "JP Morgan": "JPM", "JPMorgan Chase": "JPM", "JPM": "JPM",
    "Goldman Sachs": "GS", "Morgan Stanley": "MS", "Citigroup": "C", "Bank of America": "BAC",
    "Wells Fargo": "WFC", "BlackRock": "BLK", "Blackstone": "BX",
    "Apple": "AAPL", "Microsoft": "MSFT", "Alphabet": "GOOGL", "Google": "GOOGL", "Meta": "META",
    "Amazon": "AMZN", "Tesla": "TSLA", "Nvidia": "NVDA"
}

CEO_PATTERNS = [
    r"(?i)\b(steps?\s+down|resign(?:ed|s)?|to\s+resign)\b.*\bas\s+CEO\b",
    r"(?i)\b(retire(?:s|ment))\b.*\bas\s+CEO\b",
    r"(?i)\bappoint(?:ed|s)\b.*\bas\s+CEO\b"
]

def is_ceo_change(text: str) -> bool:
    return any(re.search(p, text) for p in CEO_PATTERNS)

def find_ticker(text: str):
    for alias, tkr in ALIASES.items():
        if alias.lower() in text.lower():
            return tkr
    return None

def recent_articles(hours=6, limit=300):
    url = f"{ARTICLES}?select=*&order=first_seen_at.desc&limit={limit}"
    r = requests.get(url, headers=HEADERS, timeout=30); r.raise_for_status()
    rows = r.json()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    out = []
    for a in rows:
        fs = a.get("first_seen_at")
        if not fs: continue
        dt = datetime.fromisoformat(fs.replace("Z","+00:00"))
        if dt >= cutoff: out.append(a)
    return out

def already_have_event(article_id):
    url = f"{EVENTS}?select=event_id&article_id=eq.{article_id}&limit=1"
    r = requests.get(url, headers=HEADERS, timeout=30); r.raise_for_status()
    return len(r.json()) > 0

def insert_event(article, extracted):
    body = [{
        "article_id": article["article_id"],
        "event_type": "CEO_CHANGE",
        "primary_ticker": extracted.get("primary_ticker"),
        "affected_tickers": extracted.get("affected_tickers", []),
        "sentiment": extracted.get("sentiment", 0.0),
        "novelty": extracted.get("novelty", 0.0),
        "confidence": extracted.get("confidence", 0.6),
        "extracted": extracted,
        "occurred_at": article.get("published_at") or article.get("first_seen_at")
    }]
    r = requests.post(EVENTS, headers=JSON_HEADERS, data=json.dumps(body), timeout=30)
    if r.status_code not in (201,200,204,409):
        raise RuntimeError(f"Insert event failed {r.status_code}: {r.text[:300]}")

def process():
    arts = recent_articles(hours=6, limit=300)
    log(f"Fetched {len(arts)} recent articles")
    made = 0
    for a in arts:
        if already_have_event(a["article_id"]):
            continue
        headline = f"{a.get('title','')}. {a.get('summary','')}"
        if not headline.strip(): continue
        if is_ceo_change(headline):
            tkr = find_ticker(headline)
            extracted = {"headline": headline, "primary_ticker": tkr}
            try:
                insert_event(a, extracted); made += 1
            except Exception as e:
                log(f"⚠️ Failed to insert event: {e}")
    log(f"Created events: {made}")
    return 0

if __name__ == "__main__":
    sys.exit(process())
