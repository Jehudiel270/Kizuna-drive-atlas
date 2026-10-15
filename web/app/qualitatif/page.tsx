"use client";
import { useMemo, useState } from "react";
import { api, useApi, useApp } from "@/lib/api";
import { nf, pct, pf } from "@/lib/fmt";
import { Busy, Card, ErrorBox, Gate, PageHead, Table, Tabs } from "@/components/ui";
import { HBar } from "@/components/charts";

type Theme = { id: number; name: string; description: string; color: string; parent_dimension: string };
type Ans = { items: { submission_id: string; question: string; question_label: string; text: string; issue: string; codes: { theme_id: number; coder: string }[] }[]; me: string };
type Syn = { n_echec: number; n_succes: number; n_coded_projects: number; note: string; themes: { theme: Theme; n_echec: number; n_succes: number; pct_echec: number | null; pct_succes: number | null; odds_ratio: number | null; p_fisher: number | null }[] };
type Key = { group_a: { term: string; z: number; a: number; b: number; example: string | null }[]; group_b: { term: string; z: number; a: number; b: number; example: string | null }[]; n_echec: number; n_succes: number };
type Kap = { pairs: { coder_a: string; coder_b: string; n_units: number; kappa: number | null; interpretation: string | null }[]; coders: string[]; note: string };
const ISSUE: Record<string, string> = { succes: "Succès", echec_partiel: "Échec partiel", echec_total: "Échec total" };
const PALETTE = ["#6aa8ff", "#3fd29a", "#f4b94b", "#a98bff", "#ff8a7a", "#35d0d8", "#e58bd1", "#9bd16b"];

export default function Quali() {
  const [tab, setTab] = useState("codage");
  const themes = useApi<Theme[]>("/quali/themes");
  return (
    <>
      <PageHead title="Analyse qualitative">Analyse de contenu thématique des réponses ouvertes (protocole 5.4) : construire le codebook de thèmes, coder chaque réponse, puis comparer la fréquence des thèmes entre échecs et succès. Deux codeurs indépendants permettent de calculer l'accord (κ de Cohen).</PageHead>
      <Tabs value={tab} onChange={setTab} tabs={[["codage", "Codage"], ["themes", "Thèmes"], ["synthese", "Synthèse échec vs succès"], ["termes", "Termes saillants"], ["kappa", "Accord inter-codeurs"]]} />
      {tab === "codage" && <Coding themes={themes.data ?? []} />}
      {tab === "themes" && <Themes themes={themes.data ?? []} reload={themes.reload} />}
      {tab === "synthese" && <Synthese />}
      {tab === "termes" && <Termes />}
      {tab === "kappa" && <Kappa />}
    </>
  );
}

function Coding({ themes }: { themes: Theme[] }) {
  const { data, error, loading, reload } = useApi<Ans>("/quali/answers");
  const [f, setF] = useState("all"); const [q, setQ] = useState(""); const [err, setErr] = useState<string | null>(null);
  const items = useMemo(() => (data?.items ?? []).filter((a) => (f === "all" || (f === "echec" ? a.issue !== "succes" : a.issue === "succes") ) && (!q || a.text.toLowerCase().includes(q.toLowerCase()))), [data, f, q]);
  const toggle = async (a: Ans["items"][number], tid: number, on: boolean) => {
    setErr(null);
    try {
      if (on) await api(`/quali/code?submission_id=${encodeURIComponent(a.submission_id)}&question=${a.question}&theme_id=${tid}`, { method: "DELETE" });
      else await api("/quali/code", { method: "POST", json: { submission_id: a.submission_id, question: a.question, theme_id: tid } });
      reload();
    } catch (e) { setErr((e as Error).message); }
  };
  return (
    <Gate loading={loading} error={error} data={data}>{data && (
      <div className="stack">
        {themes.length === 0 && <div className="callout warn">Créez d'abord quelques thèmes (onglet « Thèmes »), par exemple : « décision centralisée », « manque de formation », « outil inadapté ».</div>}
        <div className="row"><select style={{ width: 200 }} value={f} onChange={(e) => setF(e.target.value)}><option value="all">Toutes les réponses</option><option value="echec">Échecs seulement</option><option value="succes">Succès seulement</option></select><input type="text" style={{ maxWidth: 280 }} placeholder="Rechercher un mot…" value={q} onChange={(e) => setQ(e.target.value)} /><span className="note">{items.length} réponse(s) · codeur : {data.me}</span></div>
        <ErrorBox error={err} />
        {items.map((a) => (
          <Card key={a.submission_id + a.question}>
            <div className="row space small"><span className="note">{a.question_label} · {ISSUE[a.issue] ?? a.issue}</span><span className="mono note">{a.submission_id.slice(0, 10)}</span></div>
            <p style={{ margin: "8px 0 10px" }}>« {a.text} »</p>
            <div className="row" style={{ gap: 6 }}>{themes.map((t) => { const on = a.codes.some((c) => c.theme_id === t.id && c.coder === data.me); const others = a.codes.filter((c) => c.theme_id === t.id && c.coder !== data.me).length;
              return <button key={t.id} className="theme-chip" style={{ color: t.color, borderColor: on ? t.color : "#2c4062", background: on ? t.color + "22" : "transparent" }} onClick={() => toggle(a, t.id, on)}>{on ? "✓ " : ""}{t.name}{others > 0 && <span className="note"> (+{others})</span>}</button>; })}</div>
          </Card>))}
      </div>
    )}</Gate>
  );
}

function Themes({ themes, reload }: { themes: Theme[]; reload: () => void }) {
  const [name, setName] = useState(""); const [desc, setDesc] = useState(""); const [dim, setDim] = useState("gouvernance"); const [err, setErr] = useState<string | null>(null);
  const { me } = useApp();
  return (
    <div className="stack">
      <Card title="Nouveau thème" sub="Un thème = une idée récurrente, définie assez précisément pour que deux codeurs l'appliquent de la même façon.">
        <div className="grid g3"><div><label className="f">Nom</label><input type="text" value={name} onChange={(e) => setName(e.target.value)} /></div>
          <div><label className="f">Dimension du cadre conceptuel</label><select value={dim} onChange={(e) => setDim(e.target.value)}>{["gouvernance", "compétences", "communication", "soutien de la direction", "formalisation", "outil / contexte", "autre"].map((d) => <option key={d}>{d}</option>)}</select></div>
          <div><label className="f">Définition</label><input type="text" value={desc} onChange={(e) => setDesc(e.target.value)} /></div></div>
        <div style={{ marginTop: 12 }}><Busy cls="btn primary" disabled={!name.trim()} action={async () => { setErr(null); try { await api("/quali/themes", { method: "POST", json: { name, description: desc, parent_dimension: dim, color: PALETTE[themes.length % PALETTE.length] } }); setName(""); setDesc(""); reload(); } catch (e) { setErr((e as Error).message); } }}>Ajouter</Busy></div>
        <ErrorBox error={err} />
      </Card>
      <Card title="Codebook des thèmes"><Table head={["", "Thème", "Dimension", "Définition", ""]} rows={themes.map((t) => [<span key="c" style={{ color: t.color }}>●</span>, t.name, t.parent_dimension, t.description || "—", me?.role !== "lecteur" ? <Busy key="d" cls="btn sm danger" action={async () => { if (confirm(`Supprimer « ${t.name} » et tous ses codages ?`)) { await api(`/quali/themes/${t.id}`, { method: "DELETE" }); reload(); } }}>Supprimer</Busy> : ""])} /></Card>
    </div>
  );
}

function Synthese() {
  const { data, error, loading } = useApi<Syn>("/quali/synthesis");
  return (
    <Gate loading={loading} error={error} data={data}>{data && (
      <div className="stack">
        <div className="callout">{data.n_coded_projects} projets codés sur {data.n_echec} échecs et {data.n_succes} succès. {data.note}</div>
        {data.themes.length === 0 ? <p className="note">Aucun codage pour l'instant.</p> : <>
          <Card title="Part des projets mentionnant chaque thème"><HBar name="themes-echec" valueFmt={(v) => pct(v)} max={1} rows={data.themes.flatMap((t) => [{ label: `${t.theme.name} — échecs`, value: t.pct_echec ?? 0, color: "#ff6f7d" }, { label: `${t.theme.name} — succès`, value: t.pct_succes ?? 0, color: "#3fd29a" }])} /></Card>
          <Card><Table head={["Thème", "Échecs", "Succès", "% échecs", "% succès", "OR", "p Fisher"]} num={[1, 2, 3, 4, 5, 6]} rows={data.themes.map((t) => [t.theme.name, t.n_echec, t.n_succes, pct(t.pct_echec), pct(t.pct_succes), nf(t.odds_ratio), pf(t.p_fisher)])} /></Card></>}
      </div>
    )}</Gate>
  );
}

function Termes() {
  const { data, error, loading } = useApi<Key>("/analysis/keyness");
  return (
    <Gate loading={loading} error={error} data={data}>{data && (
      <div className="grid g2">
        <Card title="Mots propres aux échecs" sub={`${data.n_echec} réponses · log-rapport de cotes avec a priori informatif (z)`}><Table head={["Terme", "z", "Échecs", "Succès", "Extrait"]} num={[1, 2, 3]} rows={data.group_a.map((r) => [<b key="t">{r.term}</b>, nf(r.z, 1), r.a, r.b, <span key="e" className="note">{r.example ?? ""}</span>])} /></Card>
        <Card title="Mots propres aux succès" sub={`${data.n_succes} réponses`}><Table head={["Terme", "z", "Échecs", "Succès", "Extrait"]} num={[1, 2, 3]} rows={data.group_b.map((r) => [<b key="t">{r.term}</b>, nf(r.z, 1), r.a, r.b, <span key="e" className="note">{r.example ?? ""}</span>])} /></Card>
        <p className="note" style={{ gridColumn: "1 / -1" }}>Aide à repérer des thèmes à coder, pas un résultat en soi : |z| &gt; 1,96 ≈ différence notable, sans correction pour les comparaisons multiples.</p>
      </div>
    )}</Gate>
  );
}

function Kappa() {
  const { data, error, loading } = useApi<Kap>("/quali/kappa");
  return (
    <Gate loading={loading} error={error} data={data}>{data && (
      <Card title="κ de Cohen entre codeurs" sub={data.note}>
        {data.pairs.length === 0 ? <p className="note">Il faut au moins deux codeurs (comptes différents) ayant codé les mêmes réponses. Codeurs actuels : {data.coders.join(", ") || "aucun"}.</p> :
          <Table head={["Codeur A", "Codeur B", "Unités", "κ", "Interprétation"]} num={[2, 3]} rows={data.pairs.map((p) => [p.coder_a, p.coder_b, p.n_units, nf(p.kappa), p.interpretation ?? "—"])} />}
      </Card>
    )}</Gate>
  );
}
