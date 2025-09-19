import { getArticles, getEvents, getSignals } from "@lib/supabaseFetch";
import FilterBar from "./components/FilterBar";
import { Table } from "./components/Table";
import { SignalCard, EventCard, ArticleCard } from "./components/Cards";

function pct(x: any) { if (typeof x !== "number") return "—"; return `${(x * 100).toFixed(2)}%`; }
function withinHours(iso: string | null, hours: number) {
  if (!iso) return false; const t = new Date(iso); return Date.now() - t.getTime() <= hours * 3600 * 1000;
}

export default async function Page({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const hours = Number(searchParams.hours ?? 48);
  const ticker = (searchParams.ticker as string | undefined)?.toUpperCase() || "";
  const types = ((searchParams.types as string | undefined) ?? "CEO_CHANGE").split(",").filter(Boolean);

  // Fetch in parallel
  const [articlesRaw, eventsRaw, signalsRaw] = await Promise.all([
    getArticles(200),
    getEvents(200),
    getSignals(400),
  ]);

  // Filter server-side (SSR) to keep client light
  const filterByTicker = (x: any) => !ticker || (x.ticker ?? "").toUpperCase().includes(ticker);
  const within = (x: any, key: string) => {
    const ts = x[key] ?? x.ts ?? x.created_at ?? x.generated_at;
    return withinHours(ts, hours);
  };
  const hasType = (x: any) => !types.length || types.includes(x.type);

  const articles = articlesRaw.filter(filterByTicker).filter(a => within(a, "ts"));
  const events = eventsRaw.filter(filterByTicker).filter(e => within(e, "when"));
  const signals = signalsRaw.filter(filterByTicker).filter(hasType).filter(s => within(s, "generated_at"));

  const up = signals.filter((s: any) => typeof s.impact === "number" && s.impact > 0).length;
  const down = signals.filter((s: any) => typeof s.impact === "number" && s.impact < 0).length;

  return (
    <main style={{ padding: 16, display: "grid", gap: 16 }}>
      <h1 style={{ fontSize: 24, fontWeight: 700 }}>Golden Rope — Market Monitor</h1>

      <FilterBar />

      {/* KPIs */}
      <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
        <div className="card"><div className="card-title">Signals</div><div style={{ fontSize: 28, fontWeight: 700 }}>{signals.length}</div></div>
        <div className="card"><div className="card-title">Events</div><div style={{ fontSize: 28, fontWeight: 700 }}>{events.length}</div></div>
        <div className="card"><div className="card-title">Articles</div><div style={{ fontSize: 28, fontWeight: 700 }}>{articles.length}</div></div>
        <div className="card">
          <div className="card-title">Signal Skew</div>
          <div className="muted">Up {up} • Down {down}</div>
        </div>
      </div>

      {/* Signals grid */}
      <section>
        <h2 className="section-title">Signals</h2>
        {signals.length === 0 ? (
          <div className="card">No signals in the last {hours}h</div>
        ) : (
          <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" }}>
            {signals.map((s: any) => <SignalCard key={s.id ?? JSON.stringify(s)} s={s} />)}
          </div>
        )}
      </section>

      {/* Events grid */}
      <section>
        <h2 className="section-title">Events</h2>
        {events.length === 0 ? (
          <div className="card">No events in the last {hours}h</div>
        ) : (
          <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" }}>
            {events.map((e: any) => <EventCard key={e.id ?? JSON.stringify(e)} e={e} />)}
          </div>
        )}
      </section>

      {/* Articles grid */}
      <section>
        <h2 className="section-title">Articles</h2>
        {articles.length === 0 ? (
          <div className="card">No articles in the last {hours}h</div>
        ) : (
          <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" }}>
            {articles.map((a: any) => <ArticleCard key={a.id ?? JSON.stringify(a)} a={a} />)}
          </div>
        )}
      </section>
    </main>
  );
}
