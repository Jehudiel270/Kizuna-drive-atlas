"use client";
import { ReactNode, useState } from "react";
import { ApiError } from "@/lib/api";
import { VERDICT } from "@/lib/fmt";

export function PageHead({ title, children, right }: { title: string; children?: ReactNode; right?: ReactNode }) {
  return (
    <div className="pagehead row space" style={{ alignItems: "flex-end" }}>
      <div><h1>{title}</h1>{children && <p>{children}</p>}</div>
      {right}
    </div>
  );
}
export const Card = ({ title, sub, children, right, style }: { title?: string; sub?: ReactNode; children: ReactNode; right?: ReactNode; style?: React.CSSProperties }) => (
  <section className="card" style={style}>
    {(title || right) && <div className="row space" style={{ alignItems: "flex-start" }}><div>{title && <h2>{title}</h2>}{sub && <div className="sub">{sub}</div>}</div>{right}</div>}
    {children}
  </section>
);
export const Stat = ({ v, l, tone }: { v: ReactNode; l: string; tone?: string }) => (
  <div className="card stat"><div className="v" style={tone ? { color: `var(--${tone})` } : undefined}>{v}</div><div className="l">{l}</div></div>
);
export const Badge = ({ children, cls = "" }: { children: ReactNode; cls?: string }) => <span className={`badge ${cls}`}>{children}</span>;
export const VerdictBadge = ({ v }: { v: string }) => { const x = VERDICT[v] || VERDICT.untestable; return <Badge cls={x.cls}>{x.label}</Badge>; };
export const Loading = ({ text = "Calcul en cours…" }: { text?: string }) => <div className="loading"><span className="spin" />{text}</div>;
export function ErrorBox({ error }: { error: ApiError | Error | string | null }) {
  if (!error) return null;
  return <div className="callout bad"><b>Erreur.</b> {typeof error === "string" ? error : error.message}</div>;
}
export const Alerts = ({ items }: { items: { level: string; text: string }[] }) => (
  <div className="stack">{items.map((a, i) => <div key={i} className={`callout ${a.level === "warn" ? "warn" : ""}`}>{a.text}</div>)}</div>
);
export function Tabs({ tabs, value, onChange }: { tabs: [string, string][]; value: string; onChange: (v: string) => void }) {
  return <div className="tabs">{tabs.map(([k, l]) => <button key={k} className={k === value ? "on" : ""} onClick={() => onChange(k)}>{l}</button>)}</div>;
}
export function Table({ head, rows, num = [] }: { head: ReactNode[]; rows: ReactNode[][]; num?: number[] }) {
  return (
    <div className="scroll"><table className="t"><thead><tr>{head.map((h, i) => <th key={i} className={num.includes(i) ? "n" : ""}>{h}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className={num.includes(j) ? "n" : ""}>{c}</td>)}</tr>)}</tbody></table></div>
  );
}
export function Gate({ loading, error, data, children }: { loading: boolean; error: ApiError | null; data: unknown; children: ReactNode }) {
  if (error) return <ErrorBox error={error} />;
  if (loading || !data) return <Loading />;
  return <>{children}</>;
}
export function Busy({ action, children, cls = "btn", ...rest }: { action: () => Promise<unknown>; children: ReactNode; cls?: string } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const [b, setB] = useState(false);
  return <button {...rest} className={cls} disabled={b || rest.disabled} onClick={async () => { setB(true); try { await action(); } finally { setB(false); } }}>{b && <span className="spin" />}{children}</button>;
}
