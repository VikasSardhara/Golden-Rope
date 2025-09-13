import os, time, json, feedparser, requests, sys
from datetime import datetime, timezone

def log(msg): print(msg, flush=True)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    log("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_KEY env")
    sys.exit(1)

ARTICLES_ENDPOINT = f"{SUPABASE_URL}/rest/v1/articles"
HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

FEEDS = [
    "https://www.businesswire.com/portal/site/home/news/subject/?vnsId=31373&rss=1",
    "https://www.prnewswire.com/rss/finance-latest-news.rss",
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "https://www.ft.com/companies?format=rss"
]

def ts(dt):
    if not dt: return None
    try:
        return datetime.fromtimestamp(time.mktime(dt), tz=timezone.utc).isoformat()
    except Exception:
        return None

def put_article(item, source):
    url = item.get("link") or item.get("id")
    if not url:
        return 0
    title = (item.get("title") or "")[:1000]
    summary = (item.get("summary") or "")[:5000]
    published = ts(item.get("published_parsed") or item.get("updated_parsed"))
    first_seen = datetime.now(timezone.utc).isoformat()

    payload = [{
        "source": source,
        "url": url,
        "title": title,
        "summary": summary,
        "published_at": published,
        "first_seen_at": first_seen,
        "raw_path": None,
        "language": "en"
    }]
    r = requests.post(ARTICLES_ENDPOINT, headers=HEADERS, data=json.dumps(payload), timeout=30)
    if r.status_code in (201,200,204,409):
        return 1
    # Log full error body for debugging
    log(f"⚠️ Insert failed {r.status_code}: {r.text[:300]}")
    return 0

def main():
    log(f"SUPABASE_URL endpoint: {ARTICLES_ENDPOINT}")
    total, errors = 0, 0
    for feed in FEEDS:
        log(f"Fetching: {feed}")
        f = feedparser.parse(feed)
        log(f"  Entries: {len(f.entries)}")
        for entry in f.entries[:30]:
            try:
                total += put_article(entry, source=feed)
            except Exception as e:
                errors += 1
                log(f"⚠️ Exception: {e}")
    log(f"Inserted_or_merged: {total}; errors: {errors}")
    # Exit 0 even if some errors, so cron continues; change to 1 if you want hard fail
    sys.exit(0)

if __name__ == "__main__":
    main()
