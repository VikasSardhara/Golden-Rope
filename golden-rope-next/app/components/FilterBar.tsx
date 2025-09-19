"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";

export default function FilterBar() {
  const router = useRouter();
  const sp = useSearchParams();

  const state = useMemo(() => ({
    hours: sp.get("hours") ?? "48",
    ticker: sp.get("ticker") ?? "",
    types: (sp.get("types") ?? "CEO_CHANGE").split(",").filter(Boolean)
  }), [sp]);

  function apply(next: Partial<typeof state>) {
    const u = new URL(window.location.href);
    const hours = next.hours ?? state.hours;
    const ticker = (next.ticker ?? state.ticker).toUpperCase();
    const types = (next.types ?? state.types).filter(Boolean).join(",");
    u.searchParams.set("hours", hours);
    u.searchParams.set("types", types);
    if (ticker) u.searchParams.set("ticker", ticker); else u.searchParams.delete("ticker");
    router.push(u.toString());
  }

  function toggleType(t: string) {
    const set = new Set(state.types);
    if (set.has(t)) set.delete(t); else set.add(t);
    apply({ types: Array.from(set) });
  }

  return (
    <div className="card" style={{marginBottom: 16}}>
      <div className="row">
        <div style={{flex: "0 0 120px"}}>
          <label>Lookback (hrs)</label>
          <select className="input" value={state.hours} onChange={e => apply({hours: e.target.value})}>
            {["6","12","24","48","72","168"].map(h => <option key={h} value={h}>{h}</option>)}
          </select>
        </div>
        <div style={{flex: "0 0 180px"}}>
          <label>Ticker</label>
          <input className="input" placeholder="e.g. JPM" value={state.ticker}
                 onChange={e => apply({ticker: e.target.value})}/>
        </div>
        <div style={{display:"flex", gap:8, alignItems:"flex-end"}}>
          {["CEO_CHANGE","GUIDANCE","MNA","LEGAL","MACRO"].map(t => (
            <button key={t}
              onClick={() => toggleType(t)}
              className="badge"
              style={{background: state.types.includes(t) ? "#e2e8f0" : "transparent"}}
            >{t}</button>
          ))}
        </div>
      </div>
    </div>
  );
}
