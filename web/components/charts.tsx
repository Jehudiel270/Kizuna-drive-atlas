"use client";
import { ReactNode, useRef, useState } from "react";
import { nf, pf } from "@/lib/fmt";

export const COLORS = { accent: "#6aa8ff", teal: "#35d0d8", violet: "#a98bff", ok: "#3fd29a", warn: "#f4b94b", bad: "#ff6f7d", grid: "#22324f", ink: "#e7edf8", muted: "#93a3c0" };
export const OUTCOME_COLORS: Record<string, string> = { "Succès": COLORS.ok, "Échec partiel": COLORS.warn, "Échec total": COLORS.bad, succes: COLORS.ok, echec_partiel: COLORS.warn, echec_total: COLORS.bad };

/** Conteneur avec export SVG / PNG (norme « graphiques exportables » du rapport). */
export function Exportable({ name, children }: { name: string; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const svgText = () => {
    const svg = ref.current?.querySelector("svg"); if (!svg) return null;
    const c = svg.cloneNode(true) as SVGSVGElement;
    c.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    const vb = svg.viewBox.baseVal;
    c.setAttribute("width", String(vb.width)); c.setAttribute("height", String(vb.height));
    const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    bg.setAttribute("width", "100%"); bg.setAttribute("height", "100%"); bg.setAttribute("fill", "#0d1528"); c.insertBefore(bg, c.firstChild);
    c.querySelectorAll("text").forEach((t) => { (t as SVGElement).style.fontFamily = "Arial, sans-serif"; });
    return { text: new XMLSerializer().serializeToString(c), w: vb.width, h: vb.height };
  };
  const save = (blob: Blob, fn: string) => { const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = fn; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1500); };
  const toSvg = () => { const s = svgText(); if (s) save(new Blob([s.text], { type: "image/svg+xml" }), `${name}.svg`); };
  const toPng = () => {
    const s = svgText(); if (!s) return;
    const img = new Image();
    img.onload = () => { const k = 2; const cv = document.createElement("canvas"); cv.width = s.w * k; cv.height = s.h * k; const g = cv.getContext("2d")!; g.scale(k, k); g.drawImage(img, 0, 0); cv.toBlob((b) => b && save(b, `${name}.png`)); };
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(s.text);
  };
  return (
    <div className="chartbox" ref={ref}>
      <div className="tools"><button className="btn sm" onClick={toSvg}>SVG</button><button className="btn sm" onClick={toPng}>PNG</button></div>
      {children}
    </div>
  );
}

type Tip = { x: number; y: number; t: string } | null;
function useTip() {
  const [tip, setTip] = useState<Tip>(null);
  const on = (t: string) => (e: React.MouseEvent<SVGElement>) => { const r = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect(); setTip({ x: e.clientX - r.left, y: e.clientY - r.top, t }); };
  const off = () => setTip(null);
  const el = tip && <div style={{ position: "absolute", left: tip.x + 12, top: tip.y - 8, background: "#060b16", border: "1px solid #2c4062", borderRadius: 8, padding: "5px 9px", fontSize: 12, pointerEvents: "none", whiteSpace: "pre", zIndex: 5 }}>{tip.t}</div>;
  return { on, off, el };
}

/* ------------------------------------------------------------------ Forest plot (OR + IC, axe log) */
export type ForestRow = { label: string; or: number | null; ci_low: number | null; ci_high: number | null; p?: number | null; group?: string };
export function Forest({ rows, name = "forest", height }: { rows: ForestRow[]; name?: string; height?: number }) {
  const { on, off, el } = useTip();
  const clean = rows.filter((r) => r.or != null && r.ci_low != null && r.ci_high != null && r.or > 0);
  if (!clean.length) return <div className="note">Aucune estimation.</div>;
  const W = 760, rowH = 30, top = 26, left = 260, right = 40;
  const H = height ?? top + clean.length * rowH + 36;
  const lo = Math.min(0.2, ...clean.map((r) => r.ci_low!)), hi = Math.max(5, ...clean.map((r) => r.ci_high!));
  const L = Math.log(Math.max(lo, 0.05)), U = Math.log(Math.min(hi, 60));
  const X = (v: number) => left + ((Math.log(Math.min(Math.max(v, 0.05), 60)) - L) / (U - L)) * (W - left - right);
  const ticks = [0.1, 0.25, 0.5, 1, 2, 4, 10, 25].filter((t) => Math.log(t) >= L && Math.log(t) <= U);
  return (
    <Exportable name={name}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Diagramme en forêt des rapports de cotes">
        {ticks.map((t) => <g key={t}><line x1={X(t)} x2={X(t)} y1={top - 8} y2={H - 30} stroke={t === 1 ? "#4a5d84" : COLORS.grid} strokeDasharray={t === 1 ? "" : "3 4"} /><text x={X(t)} y={H - 12} fontSize="11" textAnchor="middle">{t}</text></g>)}
        <text x={X(1)} y={12} fontSize="10.5" textAnchor="middle">pas d'effet (OR = 1)</text>
        {clean.map((r, i) => {
          const y = top + i * rowH + rowH / 2, sig = r.p != null && r.p < 0.05, c = r.or! > 1 ? COLORS.bad : COLORS.ok;
          return (
            <g key={i} onMouseMove={on(`${r.label}\nOR ${nf(r.or)} [${nf(r.ci_low)} ; ${nf(r.ci_high)}]\np = ${pf(r.p)}`)} onMouseLeave={off} style={{ cursor: "default" }}>
              <rect x={0} y={y - rowH / 2} width={W} height={rowH} fill="transparent" />
              <text x={left - 12} y={y + 4} fontSize="12.5" textAnchor="end" style={{ fill: "#e7edf8" }}>{r.label.length > 40 ? r.label.slice(0, 38) + "…" : r.label}</text>
              <line x1={X(r.ci_low!)} x2={X(r.ci_high!)} y1={y} y2={y} stroke={sig ? c : "#7083a8"} strokeWidth="2" strokeLinecap="round" />
              <rect x={X(r.or!) - 5} y={y - 5} width="10" height="10" rx="2" fill={sig ? c : "#0d1528"} stroke={sig ? c : "#7083a8"} strokeWidth="2" />
            </g>
          );
        })}
      </svg>
      {el}
    </Exportable>
  );
}

/* ------------------------------------------------------------------ Barres horizontales */
export function HBar({ rows, name = "barres", valueFmt = (v: number) => String(v), color = COLORS.accent, max }: { rows: { label: string; value: number; target?: number | null; color?: string }[]; name?: string; valueFmt?: (v: number) => string; color?: string; max?: number }) {
  const { on, off, el } = useTip();
  const W = 640, rh = 28, left = 190, H = rows.length * rh + 8;
  const m = max ?? Math.max(1, ...rows.map((r) => Math.max(r.value, r.target ?? 0)));
  return (
    <Exportable name={name}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img">
        {rows.map((r, i) => {
          const y = i * rh + 4, w = (r.value / m) * (W - left - 70);
          return (
            <g key={i} onMouseMove={on(`${r.label}\n${valueFmt(r.value)}${r.target != null ? `\ncible ${r.target}` : ""}`)} onMouseLeave={off}>
              <text x={left - 10} y={y + 15} fontSize="12.5" textAnchor="end" style={{ fill: "#e7edf8" }}>{r.label.length > 28 ? r.label.slice(0, 26) + "…" : r.label}</text>
              <rect x={left} y={y + 3} width={Math.max(w, 2)} height={16} rx="4" fill={r.color || color} />
              {r.target != null && <line x1={left + (r.target / m) * (W - left - 70)} x2={left + (r.target / m) * (W - left - 70)} y1={y} y2={y + 22} stroke="#fff" strokeWidth="2" strokeDasharray="3 2" />}
              <text x={left + Math.max(w, 2) + 8} y={y + 16} fontSize="12" style={{ fill: "#e7edf8" }}>{valueFmt(r.value)}</text>
            </g>
          );
        })}
      </svg>
      {el}
    </Exportable>
  );
}

/* ------------------------------------------------------------------ Entonnoir */
export function Funnel({ steps }: { steps: { step: string; n: number }[] }) {
  const m = Math.max(1, steps[0]?.n || 1);
  return (
    <div className="stack">
      {steps.map((s, i) => (
        <div key={i}>
          <div className="row space small"><span>{s.step}</span><b className="mono">{s.n}{i > 0 && steps[i - 1].n > 0 ? <span className="note"> · {Math.round((s.n / steps[i - 1].n) * 100)} %</span> : null}</b></div>
          <div className="bar"><i style={{ width: `${(s.n / m) * 100}%`, opacity: 1 - i * 0.08 }} /></div>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ Likert empilé (1–5) */
const LIK = ["#ff6f7d", "#f7a07a", "#4c5f86", "#6fc4d8", "#3fd29a"];
export function Likert({ rows, name = "likert" }: { rows: { label: string; counts: number[]; reversed?: boolean }[]; name?: string }) {
  const { on, off, el } = useTip();
  const W = 760, rh = 28, left = 300, H = rows.length * rh + 40, bw = W - left - 20;
  return (
    <Exportable name={name}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img">
        {rows.map((r, i) => {
          const tot = r.counts.reduce((a, b) => a + b, 0) || 1, y = i * rh + 6; let x = left;
          return (
            <g key={i}>
              <text x={left - 10} y={y + 15} fontSize="12" textAnchor="end" style={{ fill: "#e7edf8" }}>{(r.reversed ? "↺ " : "") + (r.label.length > 46 ? r.label.slice(0, 44) + "…" : r.label)}</text>
              {r.counts.map((c, k) => { const w = (c / tot) * bw; const rx = x; x += w;
                return <rect key={k} x={rx} y={y + 2} width={Math.max(w - 1.5, 0)} height={18} fill={LIK[k]} onMouseMove={on(`${r.label}\nNote ${k + 1} : ${c} (${Math.round((c / tot) * 100)} %)`)} onMouseLeave={off} />; })}
            </g>
          );
        })}
        {LIK.map((c, k) => <g key={k}><rect x={left + k * 92} y={H - 26} width="12" height="12" rx="3" fill={c} /><text x={left + k * 92 + 17} y={H - 16} fontSize="11">{["1 pas du tout", "2", "3", "4", "5 tout à fait"][k]}</text></g>)}
      </svg>
      {el}
    </Exportable>
  );
}

/* ------------------------------------------------------------------ Histogramme */
export function Hist({ edges, counts, name = "histogramme", color = COLORS.accent }: { edges: number[]; counts: number[]; name?: string; color?: string }) {
  const { on, off, el } = useTip();
  const W = 380, H = 130, p = 22, m = Math.max(1, ...counts), bw = (W - 2 * p) / Math.max(counts.length, 1);
  return (
    <Exportable name={name}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%">
        <line x1={p} x2={W - p} y1={H - 22} y2={H - 22} stroke={COLORS.grid} />
        {counts.map((c, i) => <rect key={i} x={p + i * bw + 1} y={H - 22 - (c / m) * (H - 40)} width={bw - 2} height={(c / m) * (H - 40)} rx="2" fill={color} onMouseMove={on(`${nf(edges[i], 1)} – ${nf(edges[i + 1], 1)} : ${c}`)} onMouseLeave={off} />)}
        {edges.length > 0 && <><text x={p} y={H - 6} fontSize="10.5">{nf(edges[0], 1)}</text><text x={W - p} y={H - 6} fontSize="10.5" textAnchor="end">{nf(edges[edges.length - 1], 1)}</text></>}
      </svg>
      {el}
    </Exportable>
  );
}

/* ------------------------------------------------------------------ Courbes (interaction / ROC) */
export type Series = { name: string; color: string; points: { x: number; y: number }[]; dash?: string };
export function Lines({ series, xLabel, yLabel, name = "courbes", yMax = 1, xDomain, diag, yFmt }: { series: Series[]; xLabel: string; yLabel: string; name?: string; yMax?: number; xDomain?: [number, number]; diag?: boolean; yFmt?: (v: number) => string }) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 520, H = 300, l = 48, r = 16, t = 14, b = 44;
  const xs = series.flatMap((s) => s.points.map((p) => p.x));
  const [x0, x1] = xDomain ?? [Math.min(...xs), Math.max(...xs)];
  const X = (v: number) => l + ((v - x0) / (x1 - x0 || 1)) * (W - l - r), Y = (v: number) => H - b - (v / yMax) * (H - t - b);
  const path = (s: Series) => s.points.map((p, i) => `${i ? "L" : "M"}${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`).join("");
  const grid = [0, 0.25, 0.5, 0.75, 1].map((g) => g * yMax);
  const first = series[0]?.points ?? [];
  const idx = hover != null ? hover : null;
  return (
    <Exportable name={name}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => { const rc = e.currentTarget.getBoundingClientRect(); const px = ((e.clientX - rc.left) / rc.width) * W; let best = 0, bd = 1e9; first.forEach((p, i) => { const d = Math.abs(X(p.x) - px); if (d < bd) { bd = d; best = i; } }); setHover(best); }}>
        {grid.map((g) => <g key={g}><line x1={l} x2={W - r} y1={Y(g)} y2={Y(g)} stroke={COLORS.grid} strokeDasharray="3 4" /><text x={l - 8} y={Y(g) + 4} fontSize="11" textAnchor="end">{(yFmt ?? ((v: number) => yMax === 1 ? Math.round(v * 100) + " %" : nf(v, 1)))(g)}</text></g>)}
        {diag && <line x1={X(0)} y1={Y(0)} x2={X(1)} y2={Y(1)} stroke="#4a5d84" strokeDasharray="4 4" />}
        {series.map((s) => <path key={s.name} d={path(s)} fill="none" stroke={s.color} strokeWidth="2.2" strokeLinecap="round" strokeDasharray={s.dash} />)}
        {idx != null && first[idx] && <g><line x1={X(first[idx].x)} x2={X(first[idx].x)} y1={t} y2={H - b} stroke="#4a5d84" />
          {series.map((s) => s.points[idx] && <circle key={s.name} cx={X(s.points[idx].x)} cy={Y(s.points[idx].y)} r="4.5" fill={s.color} stroke="#0d1528" strokeWidth="2" />)}</g>}
        <text x={(l + W - r) / 2} y={H - 8} fontSize="11.5" textAnchor="middle">{xLabel}</text>
        <text transform={`translate(13 ${(t + H - b) / 2}) rotate(-90)`} fontSize="11.5" textAnchor="middle">{yLabel}</text>
      </svg>
      <div className="row small" style={{ gap: 16, marginTop: 4 }}>{series.map((s) => <span key={s.name} className="row" style={{ gap: 6 }}><i style={{ width: 16, height: 3, background: s.color, display: "inline-block", borderRadius: 2 }} />{s.name}{idx != null && s.points[idx] ? <b className="mono"> {(yFmt ?? ((v: number) => yMax === 1 ? Math.round(v * 100) + " %" : nf(v)))(s.points[idx].y)}</b> : null}</span>)}{idx != null && first[idx] && <span className="note">x = {nf(first[idx].x, 2)}</span>}</div>
    </Exportable>
  );
}

/* ------------------------------------------------------------------ Série temporelle cumulée */
export function Timeline({ data, target }: { data: { day: string; cum_total: number; cum_analysable: number }[]; target?: { min: number; max: number } }) {
  if (!data.length) return <div className="note">Pas encore de dates de soumission.</div>;
  const s1: Series = { name: "Soumissions cumulées", color: COLORS.accent, points: data.map((d, i) => ({ x: i, y: d.cum_total })) };
  const s2: Series = { name: "Projets analysables cumulés", color: COLORS.teal, points: data.map((d, i) => ({ x: i, y: d.cum_analysable })) };
  const ymax = Math.max(target?.min ?? 0, ...data.map((d) => d.cum_total), 10);
  const sc = (s: Series): Series => ({ ...s, points: s.points.map((p) => ({ x: p.x, y: p.y / ymax })) });
  const series = [sc(s1), sc(s2)];
  if (target) series.push({ name: `Cible min (${target.min})`, color: COLORS.warn, dash: "5 4", points: [{ x: 0, y: target.min / ymax }, { x: data.length - 1 || 1, y: target.min / ymax }] });
  return <div><Lines series={series} xLabel={`${data[0].day} → ${data[data.length - 1].day} (jours de collecte)`} yLabel="réponses" name="collecte-cumul" yFmt={(v) => String(Math.round(v * ymax))} /></div>;
}
