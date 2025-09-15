import os, sys, json, time
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

EVENTS = f"{SUPABASE_URL}/rest/v1/events"

# ---------- MODEL ----------
USE_VADER_FALLBACK = False  # flip to True if transformers install is slow/blocked

if not USE_VADER_FALLBACK:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
    # FinBERT (finance-tuned sentiment)
    MODEL_NAME = "ProsusAI/finbert"
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
    clf = pipeline("text-classification", model=model, tokenizer=tokenizer, return_all_scores=True, truncation=True)
else:
    # VADER fallback (no ML downloads, fast)
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    clf = SentimentIntensityAnalyzer()

def map_finbert_scores(all_scores):
    """Map FinBERT raw scores -> standardized sentiment in [-1, +1] and confidence [0,1]."""
    # all_scores format: [[{'label':'positive','score':p}, {'label':'neutral','score':n}, {'label':'negative','score':q}]]
    s = {d['label'].lower(): d['score'] for d in all_scores[0]}
    # standard score = P(pos) - P(neg), confidence = 1 - P(neutral)
    pos, neg, neu = s.get('positive',0.0), s.get('negative',0.0), s.get('neutral',0.0)
    score = float(pos - neg)
    conf = float(1.0 - neu)
    return score, conf, {"positive":pos, "neutral":neu, "negative":neg}

def map_vader_scores(text):
    vs = clf.polarity_scores(text)
    # VADER compound is already in [-1,+1]; approximate confidence by |compound|
    return float(vs["compound"]), float(abs(vs["compound"])), vs

def fetch_events_to_score(limit=100):
    # Grab recent events where sentiment is NULL
    # order newest first to prioritize
    url = f"{EVENTS}?select=event_id,extracted,created_at,sentiment,confidence&sentiment=is.null&order=created_at.desc&limit={limit}"
    r = requests.get(url, headers=HEADERS, timeout=30); r.raise_for_status()
    return r.json()

def update_event_sentiment(event_id, sentiment, confidence, details):
    # PATCH the row
    body = {"sentiment": sentiment, "confidence": confidence}
    # keep any existing 'extracted'; only add 'sentiment_detail' if you want
    # Optionally: add details inside extracted JSON:
    # body["extracted"] = {**(existing_extracted), "sentiment_detail": details}
    url = f"{EVENTS}?event_id=eq.{event_id}"
    r = requests.patch(url, headers=JSON_HEADERS, data=json.dumps(body), timeout=30)
    if r.status_code not in (200,204):
        raise RuntimeError(f"Patch failed {r.status_code}: {r.text[:200]}")

def process_batch():
    rows = fetch_events_to_score()
    log(f"Found {len(rows)} events needing sentiment")
    done, errs = 0, 0
    for ev in rows:
        try:
            headline = (ev.get("extracted") or {}).get("headline","")
            if not headline.strip():
                continue
            if USE_VADER_FALLBACK:
                score, conf, detail = map_vader_scores(headline)
            else:
                all_scores = clf(headline)
                score, conf, detail = map_finbert_scores(all_scores)
            update_event_sentiment(ev["event_id"], score, conf, detail)
            done += 1
        except Exception as e:
            errs += 1
            log(f"⚠️ Failed on event {ev.get('event_id')}: {e}")
    log(f"Updated sentiment for {done} events; errors: {errs}")

if __name__ == "__main__":
    process_batch()
