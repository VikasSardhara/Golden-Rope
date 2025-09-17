import os, json, requests, pandas as pd, streamlit as st
from datetime import datetime, timedelta, timezone
import yfinance as yf  # <<< ADDED

# ----------------- Config & Secrets -----------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    st.error("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in Streamlit secrets.")
    st.stop()

HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"
}
JSON_HEADERS = {**HEADERS, "Content-Type": "application/json"}

ARTICLES = f"{SUPABASE_URL}/rest/v1/articles"
EVENTS   = f"{SUPABASE_URL}/rest/v1/events"
SIGNALS  = f"{SUPABASE_URL}/rest/v1/signals"

# ----------------- Helpers -----------------
@st.cache_data(ttl=60)
def fetch_articles(limit=100, text=None, hours=24):
    url = f"{ARTICLES}?select=*&order=first_seen_at.desc&limit={limit}"
    r = requests.get(url, headers=HEADERS, timeout=30); r.raise_for_status()
    rows = r.json()
    if hours:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        rows = [a for a in rows if a.get("first_seen_at") and datetime.fromisoformat((a["first_seen_at"].replace("Z","+00:00"))) >= cutoff]
    if text:
        t = text.lower()
        rows = [a for a in rows if (a.get("title") or "").lower().find(t) >= 0 or (a.get("summary") or "").lower().find(t) >= 0]
    df = pd.DataFrame(rows)
    return df

@st.cache_data(ttl=60)
def fetch_events(limit=200, since_hours=72, event_types=None, ticker=None):
    url = f"{EVENTS}?select=*&order=created_at.desc&limit={limit}"
    r = requests.get(url, headers=HEADERS, timeout=30); r.raise_for_status()
    rows = r.json()
    if since_hours:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        rows = [e for e in rows if e.get("created_at") and datetime.fromisoformat((e["created_at"].replace("Z","+00:00"))) >= cutoff]
    if event_types:
        rows = [e for e in rows if e.get("event_type") in set(event_types)]
    if ticker:
        rows = [e for e in rows if (e.get("primary_ticker") or "").upper() == ticker.upper()]
    # flatten extracted JSON a little
    for e in rows:
        ex = e.get("extracted") or {}
        e["headline"] = ex.get("headline")
    df = pd.DataFrame(rows)
    return df

@st.cache_data(ttl=60)
def fetch_signals(limit=400, ticker=None, event_id=None):
    url = f"{SIGNALS}?select=*&order=generated_at.desc&limit={limit}"
    r = requests.get(url, headers=HEADERS, timeout=30); r.raise_for_status()
    rows = r.json()
    if ticker:
        rows = [s for s in rows if (s.get("ticker") or "").upper() == ticker.upper()]
    if event_id:
        rows = [s for s in rows if s.get("event_id") == event_id]
    df = pd.DataFrame(rows)
    return df

def pctfmt(x):
    try:
        return f"{100*x:.2f}%"
    except Exception:
        return x

# ----------------- UI -----------------
st.set_page_config(page_title="Golden Rope — Live", layout="wide")
st.title("🪢 Golden Rope — Live Monitor")

with st.sidebar:
    st.header("Filters")
    hours = st.slider("Lookback window (hours)", 1, 168, 48)
    ticker = st.text_input("Ticker filter (e.g., JPM, AAPL)").strip() or None
    event_types = st.multiselect("Event types", ["CEO_CHANGE","GUIDANCE","MNA","LEGAL","MACRO"], default=["CEO_CHANGE"])
    st.caption("Tip: click the refresh button (top-right) to force new data.")
    st.markdown("---")
    st.subheader("About keys & safety")
    st.caption("This app uses your Supabase Service Key on the server (Streamlit secrets). Do **not** hardcode keys in the repo.")

tab1, tab2, tab3 = st.tabs(["Articles", "Events", "Signals"])

with tab1:
    st.subheader("Latest Articles")
    q = st.text_input("Search articles (headline/summary contains…)", key="art_search")
    a_df = fetch_articles(limit=200, text=q, hours=hours)
    if not a_df.empty:
        show_cols = ["first_seen_at","source","title","url","published_at","language"]
        for c in show_cols:
            if c not in a_df.columns: a_df[c] = None
        st.dataframe(a_df[show_cols], use_container_width=True, hide_index=True)
    else:
        st.info("No articles in this window.")

with tab2:
    st.subheader("Detected Events")
    e_df = fetch_events(limit=400, since_hours=hours, event_types=event_types, ticker=ticker)
    if not e_df.empty:
        # Order + computed columns
        for c in ["created_at","event_type","primary_ticker","headline","sentiment","confidence"]:
            if c not in e_df.columns: e_df[c] = None
        e_df = e_df.sort_values("created_at", ascending=False)
        st.dataframe(e_df[["created_at","event_type","primary_ticker","headline","sentiment","confidence"]], use_container_width=True, hide_index=True)

        st.markdown("#### Event details")
        sel = st.selectbox("Select an event to inspect", options=e_df["event_id"].tolist())
        if sel:
            ev_row = e_df[e_df["event_id"]==sel].iloc[0].to_dict()
            st.json(ev_row)
            st.markdown("**Related signals for this event:**")
            s_df = fetch_signals(limit=200, event_id=sel)
            if not s_df.empty:
                s_df = s_df.sort_values("horizon")
                if "predicted_return" in s_df.columns:
                    s_df["predicted_return_pct"] = s_df["predicted_return"].apply(pctfmt)
                st.dataframe(s_df[["generated_at","ticker","horizon","predicted_return","predicted_return_pct","direction","uncertainty"]], use_container_width=True, hide_index=True)
            else:
                st.info("No signals yet for this event.")
    else:
        st.info("No events in this window (or filters too tight).")

with tab3:
    st.subheader("Latest Signals")
    s_df = fetch_signals(limit=400, ticker=ticker)
    if not s_df.empty:
        # Add pretty %
        if "predicted_return" in s_df.columns:
            s_df["predicted_return_pct"] = s_df["predicted_return"].apply(pctfmt)
        st.dataframe(
            s_df[["generated_at","event_id","ticker","horizon","predicted_return","predicted_return_pct","direction","uncertainty"]]
            .sort_values("generated_at", ascending=False),
            use_container_width=True, hide_index=True
        )

        # <<< ADDED: simple price chart for the selected ticker
        if ticker:
            st.markdown("#### Price (last 1y)")
            try:
                data = yf.Ticker(ticker.upper()).history(period="1y")
                if not data.empty:
                    st.line_chart(data["Close"])
                else:
                    st.info("No price data for this ticker.")
            except Exception as e:
                st.warning(f"Could not load price data: {e}")
        # >>> END ADDED

    else:
        st.info("No signals generated yet.")
