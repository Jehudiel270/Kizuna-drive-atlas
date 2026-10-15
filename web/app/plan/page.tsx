"use client";
import { useEffect, useState } from "react";
import { api, useApi, useApp } from "@/lib/api";
import { Badge, Busy, Card, ErrorBox, Gate, PageHead, Table, Tabs } from "@/components/ui";

type PlanRes = { plan: any; hash: string; customized: boolean; default_text: string; override_text: string };
type CbRes = { codebook: { variables: { name: string; tally_id?: string; type: string; section: string; label: string }[] }; customized: boolean; default_text: string };
type Audit = { at: string; actor: string; action: string; detail: any }[];

export default function Plan() {
  const [tab, setTab] = useState("hyp");
  const { me } = useApp();
  const p = useApi<PlanRes>("/config/plan");
  const c = useApi<CbRes>(tab === "cb" ? "/config/codebook" : null, [tab]);
  const a = useApi<Audit>(tab === "audit" ? "/config/audit" : null, [tab]);
  const [txt, setTxt] = useState(""); const [note, setNote] = useState(""); const [msg, setMsg] = useState<string | null>(null); const [err, setErr] = useState<string | null>(null);
  useEffect(() => { if (p.data) setTxt(p.data.override_text || "# Surcharges du plan (fusionnées avec le plan par défaut). Exemple :\n# general:\n#   alpha: 0.05\n# quotas:\n#   secteur_g:\n#     Commerce: 40\n"); }, [p.data]);
  const admin = me?.role === "admin" && !me?.demo;
  return (
    <>
      <PageHead title="Plan d'analyse & codebook">Le plan pré-enregistré fixe à l'avance les règles : définition de l'issue, construction des scores, seuils, modèles et décisions. Toute modification est journalisée avec l'empreinte du plan (traçabilité scientifique).</PageHead>
      <Tabs value={tab} onChange={setTab} tabs={[["hyp", "Plan & hypothèses"], ["edit", "Modifier le plan"], ["cb", "Codebook Tally"], ["audit", "Journal"]]} />
      {tab === "hyp" && <Gate loading={p.loading} error={p.error} data={p.data}>{p.data && (
        <div className="stack">
          <Card title="Empreinte du plan" right={<Badge cls={p.data.customized ? "warn" : "ok"}>{p.data.customized ? "modifié" : "plan par défaut"}</Badge>}><code>{p.data.hash}</code></Card>
          {p.data.plan.hypotheses.map((h: any) => <Card key={h.id} title={`${h.id} · ${h.qs} / ${h.os}`}><p>{h.statement}</p><p className="note">Test : {h.test}</p></Card>)}
          <Card title="Règles clés"><Table head={["Paramètre", "Valeur"]} rows={[
            ["Seuil α", String(p.data.plan.general.alpha)], ["Correction", (p.data.plan.general.multiple_testing ?? "holm").toUpperCase()], ["Cible", `${p.data.plan.general.target_n.min}–${p.data.plan.general.target_n.max} projets`],
            ["Ancienneté minimale d'usage", `${p.data.plan.general.min_months_use} mois`], ["EPV minimal avant Firth", String(p.data.plan.general.epv_min)], ["α de Cronbach minimal", String(p.data.plan.general.cronbach_min)],
            ["Seuils de formalisation", `informel < ${p.data.plan.formalisation.thresholds.informel_lt} ≤ semi-formel < ${p.data.plan.formalisation.thresholds.formel_ge} ≤ formel`], ["Graine aléatoire", String(p.data.plan.general.seed)]]} /></Card>
          <div className="callout warn">Points à valider par l'équipe avant la collecte (propositions de l'outil, non issues du protocole) : indice et seuils de formalisation, règle de classement « échec partiel », regroupement des secteurs et des tailles.</div>
        </div>)}</Gate>}
      {tab === "edit" && <div className="stack">
        {!admin && <div className="callout">Lecture seule : seuls les administrateurs peuvent modifier le plan.</div>}
        <Card title="Surcharges YAML / JSON" sub="Fusion profonde avec le plan par défaut. Le plan est validé avant enregistrement.">
          <textarea className="code" value={txt} onChange={(e) => setTxt(e.target.value)} readOnly={!admin} />
          <div className="row" style={{ marginTop: 10 }}><input type="text" style={{ maxWidth: 380 }} placeholder="Motif de la modification (journal)" value={note} onChange={(e) => setNote(e.target.value)} />
            <Busy cls="btn primary" disabled={!admin} action={async () => { setErr(null); setMsg(null); try { const r = await api<{ hash: string }>("/config/plan", { method: "PUT", json: { text: txt, note } }); setMsg("Plan enregistré. Nouvelle empreinte : " + r.hash.slice(0, 12)); p.reload(); } catch (e) { setErr((e as Error).message); } }}>Enregistrer</Busy>
            <Busy cls="btn danger" disabled={!admin || !p.data?.customized} action={async () => { await api("/config/plan/reset", { method: "POST" }); setMsg("Plan réinitialisé."); p.reload(); }}>Revenir au plan par défaut</Busy></div>
          {msg && <div className="callout ok" style={{ marginTop: 10 }}>{msg}</div>}<ErrorBox error={err} />
        </Card>
        <Card title="Plan par défaut (référence)"><textarea className="code" readOnly value={p.data?.default_text ?? ""} style={{ minHeight: 280 }} /></Card>
      </div>}
      {tab === "cb" && <Gate loading={c.loading} error={c.error} data={c.data}>{c.data && <Card title={`${c.data.codebook.variables.length} variables`} sub="Relie chaque question Tally à une variable. Si un libellé change dans Tally, l'appariement se fait quand même par l'identifiant de question ; vérifier la couverture dans Données → Couverture.">
        <Table head={["Variable", "Id Tally", "Type", "Section", "Question"]} rows={c.data.codebook.variables.map((v) => [<code key="n">{v.name}</code>, <code key="i">{v.tally_id ?? "—"}</code>, v.type, v.section, v.label.length > 100 ? v.label.slice(0, 98) + "…" : v.label])} /></Card>}</Gate>}
      {tab === "audit" && <Gate loading={a.loading} error={a.error} data={a.data}>{a.data && <Card title="Journal des actions sensibles"><Table head={["Date", "Acteur", "Action", "Détail"]} rows={a.data.map((r) => [new Date(r.at).toLocaleString("fr-FR"), r.actor, r.action, <code key="d" style={{ wordBreak: "break-all" }}>{JSON.stringify(r.detail)}</code>])} /></Card>}</Gate>}
    </>
  );
}
