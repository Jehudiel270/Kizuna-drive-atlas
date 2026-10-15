export const nf = (v: number | null | undefined, d = 2) =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : v.toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d });
export const pf = (p: number | null | undefined) => (p === null || p === undefined ? "—" : p < 0.001 ? "< 0,001" : p.toLocaleString("fr-FR", { minimumFractionDigits: 3, maximumFractionDigits: 3 }));
export const pct = (v: number | null | undefined, d = 0) => (v === null || v === undefined ? "—" : (v * 100).toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d }) + " %");
export const orf = (r: { or?: number | null; ci_low?: number | null; ci_high?: number | null } | null | undefined) =>
  r && r.or != null ? `${nf(r.or)} [${nf(r.ci_low)} ; ${nf(r.ci_high)}]` : "—";
export const VERDICT: Record<string, { label: string; cls: string }> = {
  supported: { label: "Soutenue", cls: "ok" },
  partial: { label: "Partiellement soutenue", cls: "warn" },
  not_supported: { label: "Non soutenue", cls: "muted" },
  contradicted: { label: "Contredite", cls: "bad" },
  untestable: { label: "Non testable", cls: "muted" },
};
