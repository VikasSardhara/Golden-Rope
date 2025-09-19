import { getArticles, getEvents, getSignals } from "@lib/supabaseFetch";
import FilterBar from "./components/FilterBar";
import { Table } from "@components/Table"; 

function pct(x: any) {
  if (typeof x !== "number") return "—";
  return `${(x * 100).toFixed(2)}%`;
}
function withinHours(iso: string | null, hours: number) {
  if (!iso) return false;
  const t = new Date(iso);
  return Date.now() - t.getTime() <= hours * 3600 * 1000;
}

export default async function Page({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const hours = Number(searchParams.hours ?? 48);
  const ticker = (searchParams.ticker as string | undefined)?.toUpperCase() || "";
  const types = ((searchParams.types as string | undefined) ?? "CEO_CHANGE").split(",").filter(Boolean);

  // Server-side fetch (service key never hits the browser)
  const [articlesRaw, eventsRaw, signalsRaw] = await Promise.all([
    getArticles(200), getEvents(400), getSignals(400)
  ]);

  // Filter in server component (simple & safe)
  const articles = articlesRaw.filter((a: any) =>
    withinHours(a.first_seen_at, hours) &&
    (!ticker || (a.title?.toUpperCase().includes(ticker) || a.summary?.toUpperCase().includes(ticker)))
  );

  const events = eventsRaw.filter((e: any) =>
    withinHours(e.created_at, hours) &&
    (types.includes(e.event_type)) &&
    (!ticker || (e.primary_ticker?.toUpperCase() === ticker))
  ).map((e: any) => ({
    ...e,
    headline: e.extracted?.headline ?? null
  }));

  const signals = signalsRaw.filter((s: any) =>
    (!ticker || s.ticker?.toUpperCase() === ticker)
  );

  return (
    <>
      <h1>🪢 Golden Rope — Live Dashboard</h1>
      <p className="muted">Articles → Events (with sentiment) → Signals (predicted returns). Server-rendered, fast on Vercel.</p>

      <FilterBar />

      <div className="grid grid-3" style={{margin: "16px 0"}}>
        <div className="kpi">
          <span className="muted">Articles (window)</span>
          <span className="big">{articles.length}</span>
        </div>
        <div className="kpi">
          <span className="muted">Events (window)</span>
          <span className="big">{events.length}</span>
        </div>
        <div className="kpi">
          <span className="muted">Signals (total)</span>
          <span className="big">{signals.length}</span>
        </div>
      </div>

      <div className="grid grid-2" style={{marginTop: 16}}>
        <section>
          <h2>Articles</h2>
          <Table
            columns={[
              { key: "first_seen_at", label: "First Seen" },
              { key: "source", label: "Source" },
              { key: "title", label: "Title", format: (v) => v },
              { key: "url", label: "Link", format: (v) => v ? <a href={v} target="_blank">open</a> : "—" }
            ]}
            rows={articles}
            emptyText="No articles in range."
          />
        </section>

        <section>
          <h2>Events</h2>
          <Table
            columns={[
              { key: "created_at", label: "Time" },
              { key: "event_type", label: "Type" },
              { key: "primary_ticker", label: "Ticker" },
              { key: "headline", label: "Headline" },
              { key: "sentiment", label: "Sentiment", format: (v) => typeof v === "number" ? v.toFixed(2) : "—" },
              { key: "confidence", label: "Conf.", format: (v) => typeof v === "number" ? v.toFixed(2) : "—" }
            ]}
            rows={events}
            emptyText="No events match filters."
          />
        </section>
      </div>

      <section style={{marginTop: 16}}>
        <h2>Signals</h2>
        <Table
          columns={[
            { key: "generated_at", label: "Time" },
            { key: "event_id", label: "Event" },
            { key: "ticker", label: "Ticker" },
            { key: "horizon", label: "Horizon" },
            { key: "predicted_return", label: "Predicted", format: (v) => pct(v) },
            { key: "direction", label: "Dir" },
            { key: "uncertainty", label: "Unc.", format: (v) => typeof v === "number" ? v.toFixed(2) : "—" }
          ]}
          rows={signals}
          emptyText="No signals yet."
        />
      </section>
    </>
  );
}
