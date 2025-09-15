import os, sys, json, time
from datetime import datetime, timedelta, timezone
import requests
# ---------- utils ----------
def log(x: str) -> None:
    print(x, flush=True)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    log("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
    sys.exit(1)

HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
}
JSON_HEADERS = {**HEADERS, "Content-Type": "application/json"}

EVENTS = f"{SUPABASE_URL}/rest/v1/events"


# ---------- MODEL: auto-detect FinBERT; fallback to VADER ----------
ENGINE = "auto"  # options: "auto" | "finbert" | "vader"

def _try_load_finbert():
    """
    Try to load FinBERT via Hugging Face Transformers.
    Returns a pipeline object on success, or None on failure.
    """
    try:
        from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
        MODEL_NAME = "ProsusAI/finbert"
        tok = AutoTokenizer.from_pretrained(MODEL_NAME)
        mdl = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
        clf = pipeline(
            "text-classification",
            model=mdl,
            tokenizer=tok,
            return_all_scores=True,
            truncation=True
        )
        return clf
    except Exception as e:
        log(f"ℹ️ FinBERT not available ({e}); will use VADER fallback.")
        return None

def _load_vader():
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    return SentimentIntensityAnalyzer()

if ENGINE == "finbert":
    finbert = _try_load_finbert()
    if finbert is None:
        log("❌ ENGINE=finbert requested but unavailable.")
        sys.exit(1)
    vader = None
elif ENGINE == "vader":
    finbert = None
    vader = _load_vader()
else:  # "auto"
    finbert = _try_load_finbert()
    vader = None if finbert else _load_vader()
    log(f"✅ Sentiment engine: {'FinBERT' if finbert else 'VADER'}")


# ---------- mapping helpers ----------
def map_finbert_scores(all_scores):
    """
    Map FinBERT output -> (score, confidence, detail)
    all_scores looks like:
      [[{'label':'positive','score':p}, {'label':'neutral','score':n}, {'label':'negative','score':q}]]
    We use: score = P(pos) - P(neg) in [-1,+1], confidence = 1 - P(neutral) in [0,1].
    """
    if not all_scores or not isinstance(all_scores, list):
        return 0.0, 0.0, {}
    bucket = all_scores[0]
    s = {d["label"].lower(): float(d["score"]) for d in bucket}
    pos = s.get("positive", 0.0)
    neg = s.get("negative", 0.0)
    neu = s.get("neutral", 0.0)
    score = pos - neg
    conf = 1.0 - neu
    return float(score), float(conf), {"positive": pos, "neutral": neu, "negative": neg}

def map_vader_scores(text: str):
    """
    Map VADER output -> (score, confidence, detail)
    VADER returns 'compound' in [-1,+1]. We approximate confidence with |compound|.
    """
    vs = vader.polarity_scores(text)
    comp = float(vs.get("compound", 0.0))
    conf = abs(comp)
    return comp, conf, vs


# ---------- supabase i/o ----------
def fetch_events_to_score(limit: int = 100):
    """
    Pull events that still need sentiment.
    We intentionally only select needed fields to keep payloads small.
    """
    # ordered newest first
    url = (
        f"{EVENTS}"
        "?select=event_id,extracted,created_at,sentiment,confidence"
        "&sentiment=is.null"
        "&order=created_at.desc"
        f"&limit={limit}"
    )
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()

def update_event_sentiment(event_id: int, sentiment: float, confidence: float, details: dict | None):
    """
    PATCH event row with sentiment + confidence.
    Keeping it minimal; if you want to store detailed breakdowns, you can
    merge them into the 'extracted' JSON column as well.
    """
    body = {
        "sentiment": float(sentiment),
        "confidence": float(confidence),
        # Example if you want to persist more detail inside extracted JSON:
        # "extracted": { "sentiment_detail": details }
    }
    url = f"{EVENTS}?event_id=eq.{event_id}"
    r = requests.patch(url, headers=JSON_HEADERS, data=json.dumps(body), timeout=30)
    if r.status_code not in (200, 204):
        raise RuntimeError(f"Patch failed {r.status_code}: {r.text[:300]}")


# ---------- driver ----------
def process_batch():
    rows = fetch_events_to_score(limit=200)
    log(f"Found {len(rows)} events needing sentiment")

    done, errs = 0, 0
    for ev in rows:
        try:
            # headline lives inside extracted JSON
            extracted = ev.get("extracted") or {}
            headline = (extracted.get("headline") or "").strip()
            if not headline:
                continue

            if finbert:
                all_scores = finbert(headline)
                score, conf, detail = map_finbert_scores(all_scores)
            else:
                score, conf, detail = map_vader_scores(headline)

            update_event_sentiment(ev["event_id"], score, conf, detail)
            done += 1

        except Exception as e:
            errs += 1
            log(f"⚠️ Failed on event {ev.get('event_id')}: {e}")

    log(f"Updated sentiment for {done} events; errors: {errs}")


if __name__ == "__main__":
    process_batch()
