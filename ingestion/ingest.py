import os, time, json, sys, random
from datetime import datetime, timezone
import requests, feedparser

def log(msg): print(msg, flush=True)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    log("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_KEY env")
    sys.exit(1)

ARTICLES_ENDPOINT = f"{SUPABASE_URL}/rest/v1/articles"
HEADERS_DB = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# Start with permissive feeds; add BusinessWire/FT later
FEEDS = [
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",           # WSJ Markets (works on GH runners)
    "https://www.marketwatch.com/feeds/topstories",            # MarketWatch
    "https://www.globenewswire.com/RssFeed/subjectcode/3",     # Finance subject
    "https://www.globenewswire.com/RssFeed/subjectcode/44",    # Banking
    "https://www.globenewswire.com/RssFeed/subjectcode/35"     # M&A
]


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

session = requests.Session()
session.headers.update({"User-Agent": UA})

def ts(dt):
    if not dt: return None
    try:
        return datetime.fromtimestamp(time.mktime(dt), tz=timezone.utc).isoformat()
    except Exception:
        return None

def fetch_feed_bytes(url, tries=3, timeout=20):
    last_err = None
    for i in range(tries):
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code == 200:
                return r.content
            last_err = f"HTTP {r.status_code}"
        except Exception as e:
            last_err = str(e)
        time.sleep(1 + i)  # backoff
    log(f"⚠️ Could not fetch {url}: {last_err}")
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

    r = session.post(ARTICLES_ENDPOINT, headers=HEADERS_DB, data=json.dumps(payload), timeout=30)
    if r.status_code in (201, 200, 204, 409):
        return 1
    log(f"⚠️ Insert failed {r.status_code}: {r.text[:300]}")
    return 0

def main():
    log(f"SUPABASE_URL endpoint: {ARTICLES_ENDPOINT}")
    total, errors = 0, 0
    for feed in FEEDS:
        log(f"Fetching: {feed}")
        raw = fetch_feed_bytes(feed)
        if not raw:
            errors += 1
            continue
        f = feedparser.parse(raw)
        log(f"  Entries: {len(f.entries)}")
        for entry in f.entries[:30]:
            try:
                total += put_article(entry, source=feed)
            except Exception as e:
                errors += 1
                log(f"⚠️ Exception during insert: {e}")
        # small jitter to be polite
        time.sleep(random.uniform(0.5, 1.0))
    log(f"Inserted_or_merged: {total}; errors: {errors}")
    sys.exit(0)

if __name__ == "__main__":
    main()
