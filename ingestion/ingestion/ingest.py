import os, time, json, feedparser, requests
from datetime import datetime, timezone

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

ARTICLES_ENDPOINT = f"{SUPABASE_URL}/rest/v1/articles"
HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# Start with permitted/official feeds
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
    raise RuntimeError(f"Supabase insert failed {r.status_code}: {r.text}")

def main():
    inserted = 0
    for feed in FEEDS:
        f = feedparser.parse(feed)
        for entry in f.entries[:30]:
            inserted += put_article(entry, source=feed)
    print(f"Inserted_or_merged: {inserted}")

if __name__ == "__main__":
    main()
