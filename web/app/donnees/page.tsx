"use client";
import { useRef, useState } from "react";
import { api, ApiError, useApi, useApp } from "@/lib/api";
import { pct } from "@/lib/fmt";
import { Badge, Busy, Card, ErrorBox, Gate, PageHead, Stat, Table, Tabs } from "@/components/ui";

type Status = { demo: boolean; form_id: string; form_url: string; n_submissions: number; n_excluded: number; by_source: Record<string, number>; api_key_configured: boolean; webhook_secret_configured: boolean; last_sync: { at: string; inserted: number; updated: number } | null; last_webhook: { at: string } | null; n_analysable: number; source_kind: string };
type Subs = { total: number; items: { id: string; submitted_at: string | null; source: string; excluded: boolean; exclusion_reason: string | null; issue: string | null; analysable: boolean; enqueteur: string | null; relais: string | null; n_answers: number }[] };
type Cov = { n: number; variables: { name: string; section: string; label: string; type: string; filled: number; pct: number; mapped: boolean }[]; never_seen: string[] };

export default function Donnees() {
  const [tab, setTab] = useState("tally");
  const st = useApi<Status>("/ingest/status");
  return (
    <>
      <PageHead title="Données & connexion Tally">Les réponses arrivent de trois façons (webhook en temps réel, synchronisation par l'API Tally, import CSV) et sont fusionnées sans doublon. Les e-mails sont hachés dès la réception.</PageHead>
      <Tabs value={tab} onChange={setTab} tabs={[["tally", "Connexion & import"], ["sub", "Soumissions & exclusions"], ["cov", "Couverture du questionnaire"], ["snap", "Instantanés figés"]]} />
      {tab === "tally" && <Gate loading={st.loading} error={st.error} data={st.data}>{st.data && <Connect st={st.data} reload={st.reload} />}</Gate>}
      {tab === "sub" && <Subs />}
      {tab === "cov" && <Coverage />}
      {tab === "snap" && <Snaps />}
    </>
  );
}

function Connect({ st, reload }: { st: Status; reload: () => void }) {
  const [msg, setMsg] = useState<string | null>(null); const [err, setErr] = useState<string | null>(null);
  const file = useRef<HTMLInputElement>(null);
  const run = async (fn: () => Promise<unknown>, ok: (r: any) => string) => { setErr(null); setMsg(null); try { setMsg(ok(await fn())); reload(); } catch (e) { setErr((e as ApiError).message); } };
  const apiUrl = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
  return (
    <div className="stack">
      <div className="grid g4">
        <Stat v={st.n_submissions} l="soumissions en base" /><Stat v={st.n_analysable} l="analysables" /><Stat v={st.n_excluded} l="exclues manuellement" />
        <div className="card"><div className="small" style={{ marginBottom: 6 }}>Formulaire</div><a href={st.form_url} target="_blank" rel="noreferrer" className="mono">{st.form_id}</a><div className="note" style={{ marginTop: 6 }}>{Object.entries(st.by_source).map(([k, v]) => `${k} : ${v}`).join(" · ") || "aucune donnée"}</div></div>
      </div>
      {!st.demo && st.n_submissions === 0 && <div className="callout warn"><strong>Aucune soumission n'est enregistrée.</strong> Les réponses déjà présentes dans Tally ne sont pas importées automatiquement : lancez la synchronisation avec une clé API configurée, ou exportez les réponses depuis Tally puis importez le CSV ci-dessous. Le webhook ne reçoit que les nouvelles réponses après sa configuration.</div>}
      {msg && <div className="callout ok">{msg}</div>}<ErrorBox error={err} />
      <div className="grid g3">
        <Card title="1 · Webhook (temps réel)" sub="Chaque réponse arrive dès qu'elle est envoyée.">
          <p><Badge cls={st.webhook_secret_configured ? "ok" : "warn"}>{st.webhook_secret_configured ? "secret configuré" : "secret manquant"}</Badge></p>
          <p className="small">URL à coller dans Tally → Intégrations → Webhooks :</p>
          <code style={{ wordBreak: "break-all" }}>{apiUrl}/ingest/webhook/tally</code>
          <p className="note" style={{ marginTop: 8 }}>Signature HMAC vérifiée avec TALLY_SIGNING_SECRET. {st.last_webhook ? `Dernière réception : ${new Date(st.last_webhook.at).toLocaleString("fr-FR")}` : "Aucune réception pour l'instant."}</p>
        </Card>
        <Card title="2 · Synchronisation API Tally" sub="Récupère tout l'historique (idempotent, sans doublon).">
          <p><Badge cls={st.api_key_configured ? "ok" : "warn"}>{st.api_key_configured ? "clé API configurée" : "clé API manquante"}</Badge></p>
          <Busy cls="btn primary" disabled={!st.api_key_configured || st.demo} action={() => run(() => api<any>("/ingest/sync", { method: "POST" }), (r) => `${r.received} réponses lues : ${r.inserted} nouvelles, ${r.updated} mises à jour.`)}>Synchroniser maintenant</Busy>
          <p className="note" style={{ marginTop: 8 }}>{st.last_sync ? `Dernière synchro : ${new Date(st.last_sync.at).toLocaleString("fr-FR")}` : "Jamais synchronisé."} À lancer en rattrapage si le webhook a été interrompu.</p>
        </Card>
        <Card title="3 · Import CSV" sub="Export Tally (Submissions → Export → CSV).">
          <input ref={file} type="file" accept=".csv,text/csv" style={{ display: "none" }} onChange={async (e) => {
            const f = e.target.files?.[0]; if (!f) return; const fd = new FormData(); fd.append("file", f);
            await run(() => api<any>("/ingest/csv", { method: "POST", body: fd }), (r) => `${r.received} lignes lues : ${r.inserted} nouvelles, ${r.updated} mises à jour.`); e.target.value = "";
          }} />
          <button className="btn primary" disabled={st.demo} onClick={() => file.current?.click()}>Choisir un fichier CSV</button>
          <p className="note" style={{ marginTop: 8 }}>Les colonnes sont reconnues par leur libellé ; les cases à cocher « une colonne par option » sont regroupées automatiquement.</p>
        </Card>
      </div>
      <Purge disabled={st.demo} done={reload} />
    </div>
  );
}

function Purge({ disabled, done }: { disabled: boolean; done: () => void }) {
  const [txt, setTxt] = useState(""); const [m, setM] = useState("");
  const { me } = useApp();
  if (me?.role !== "admin") return null;
  return (
    <Card title="Zone sensible : purger les réponses de test" sub="À faire une seule fois, juste avant de lancer la vraie collecte. Action irréversible, réservée aux administrateurs.">
      <div className="row"><input style={{ maxWidth: 220 }} type="text" placeholder="Saisir SUPPRIMER" value={txt} onChange={(e) => setTxt(e.target.value)} />
        <Busy cls="btn danger" disabled={disabled || txt !== "SUPPRIMER"} action={async () => { const r = await api<{ deleted: number }>("/ingest/purge", { method: "POST", json: { confirm: txt } }); setM(`${r.deleted} soumissions supprimées.`); setTxt(""); done(); }}>Supprimer toutes les soumissions</Busy>{m && <span className="note">{m}</span>}</div>
    </Card>
  );
}

function Subs() {
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useApi<Subs>(`/ingest/submissions?page=${page}&size=40`, [page]);
  const [err, setErr] = useState<string | null>(null);
  const toggle = async (id: string, excluded: boolean) => {
    let reason: string | undefined;
    if (excluded) { reason = window.prompt("Motif d'exclusion (obligatoire, journalisé) :") ?? undefined; if (!reason) return; }
    try { await api(`/ingest/submissions/${encodeURIComponent(id)}`, { method: "PATCH", json: { excluded, reason } }); reload(); } catch (e) { setErr((e as Error).message); }
  };
  return (
    <Gate loading={loading} error={error} data={data}>{data && (
      <Card title={`${data.total} soumissions`} sub="Exclure une réponse (doublon, test, réponse frauduleuse) nécessite un motif ; l'action est tracée dans le journal.">
        <ErrorBox error={err} />
        <Table head={["Reçue", "Source", "Issue", "Analysable", "Enquêteur", "Relais", "Champs", ""]} num={[6]}
          rows={data.items.map((r) => [r.submitted_at ? new Date(r.submitted_at).toLocaleString("fr-FR") : "—", r.source, r.issue ?? "—", r.excluded ? <Badge cls="bad" key="x">exclue : {r.exclusion_reason}</Badge> : r.analysable ? <Badge cls="ok" key="a">oui</Badge> : <Badge key="n">non</Badge>, r.enqueteur ?? "—", r.relais ?? "—", r.n_answers, <button key="b" className="btn sm" onClick={() => toggle(r.id, !r.excluded)}>{r.excluded ? "Réintégrer" : "Exclure"}</button>])} />
        <div className="row" style={{ marginTop: 12 }}><button className="btn sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Précédent</button><span className="note">page {page}</span><button className="btn sm" disabled={page * 40 >= data.total} onClick={() => setPage(page + 1)}>Suivant →</button></div>
      </Card>
    )}</Gate>
  );
}

function Coverage() {
  const { data, error, loading } = useApi<Cov>("/analysis/coverage");
  return (
    <Gate loading={loading} error={error} data={data}>{data && (
      <Card title="Le questionnaire est-il bien branché ?" sub="Pour chaque variable du codebook : part des soumissions où elle est renseignée. Une variable à 0 % (ou jamais vue) signale un libellé Tally modifié : corriger le codebook.">
        {data.never_seen.length > 0 && <div className="callout warn" style={{ marginBottom: 12 }}>{data.never_seen.length} variable(s) jamais reçue(s) : {data.never_seen.join(", ")}.</div>}
        <Table head={["Section", "Variable", "Question", "Renseignée"]} num={[3]} rows={data.variables.map((v) => [v.section, <code key="c">{v.name}</code>, v.label.length > 90 ? v.label.slice(0, 88) + "…" : v.label, <span key="p" style={{ color: v.pct === 0 ? "var(--bad)" : undefined }}>{pct(v.pct)}</span>])} />
      </Card>
    )}</Gate>
  );
}

function Snaps() {
  const { snapshots, reloadSnapshots, setSnapshot, snapshot, me } = useApp();
  const [name, setName] = useState(""); const [note, setNote] = useState(""); const [err, setErr] = useState<string | null>(null);
  return (
    <div className="stack">
      <Card title="Figer les données pour le rapport" sub="Un instantané copie les données + le plan d'analyse et en calcule l'empreinte SHA-256. Les chiffres du rapport restent ainsi reproductibles même si la collecte continue.">
        <div className="row"><input style={{ maxWidth: 280 }} type="text" placeholder="Nom (ex. Rapport final)" value={name} onChange={(e) => setName(e.target.value)} /><input style={{ maxWidth: 320 }} type="text" placeholder="Note (facultatif)" value={note} onChange={(e) => setNote(e.target.value)} />
          <Busy cls="btn primary" disabled={!name.trim() || me?.demo} action={async () => { setErr(null); try { await api("/snapshots", { method: "POST", json: { name, note } }); setName(""); setNote(""); reloadSnapshots(); } catch (e) { setErr((e as Error).message); } }}>Figer maintenant</Busy></div>
        <ErrorBox error={err} />
      </Card>
      <Card title="Instantanés existants">
        {snapshots.length === 0 ? <p className="note">Aucun instantané.</p> : <Table head={["Nom", "Créé", "Lignes", "SHA-256", ""]} num={[2]} rows={snapshots.map((s) => [s.name, new Date(s.created_at).toLocaleString("fr-FR"), s.n_rows, <code key="h">{s.sha256.slice(0, 16)}…</code>, <button key="b" className="btn sm" onClick={() => setSnapshot(String(s.id) === snapshot ? null : String(s.id))}>{String(s.id) === snapshot ? "Quitter" : "Analyser cet instantané"}</button>])} />}
      </Card>
    </div>
  );
}
