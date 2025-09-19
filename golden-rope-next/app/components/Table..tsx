"use client";

export function Table<T extends Record<string, any>>({
  columns,
  rows,
  emptyText = "No data"
}: {
  columns: { key: string; label: string; format?: (v: any, row: T) => any }[];
  rows: T[];
  emptyText?: string;
}) {
  if (!rows?.length) return <div className="card">{emptyText}</div>;

  return (
    <div className="card">
      <table className="table">
        <thead>
          <tr>{columns.map(c => <th key={c.key}>{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {columns.map(c => (
                <td key={c.key}>
                  {c.format ? c.format(r[c.key], r) : (r[c.key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
