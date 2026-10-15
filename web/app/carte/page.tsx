"use client";
import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { download, useApi } from "@/lib/api";
import { nf, pct, pf } from "@/lib/fmt";
import { Badge, Busy, Card, Gate, PageHead, Table, Tabs } from "@/components/ui";
import type { SEdge, SNode } from "@/components/Scene3D";

const Scene3D = dynamic(() => import("@/components/Scene3D"), { ssr: false, loading: () => <div className="loading">Chargement de la scène 3D…</div> });

type MNode = { id: string; label: string; tag: string; group: string; pos: [number, number, number] };
type MEdge = { source: string; target: string; kind: string; hypothesis: string | null; label: string; or: number | null; ci_low: number | null; ci_high: number | null; p: number | null; significant: boolean | null; expected: string | null; estimated: boolean };
type Model = { nodes: MNode[]; edges: MEdge[]; note: string };
type NNode = { id: string; label: string; construct: string; community: number; strength: number; closeness: number; betweenness: number; expected_influence: number; x: number; y: number; z: number };
type NEdge = { source: string; target: string; weight: number; abs: number; inclusion: number; ci_low: number; ci_high: number };
type Net = { available: boolean; status?: string; reason?: string; n: number; p: number; min_n: number; nodes?: NNode[]; edges?: NEdge[]; alpha?: number; stability?: { cs_strength: number; cs_min: number; cs_good: number; levels: { drop: number; share_ok: number }[] }; density?: number; note?: string };

const GROUP = { predictor: "#ff8a7a", moderator: "#a98bff", control: "#7f93b8", outcome: "#f4b94b" } as Record<string, string>;
const COMM = ["#6aa8ff", "#3fd29a", "#f4b94b", "#a98bff", "#ff8a7a", "#35d0d8"];

export default function Carte() {
  const [tab, setTab] = useState("modele");
  return (
    <>
      <PageHead title="Carte 3D des relations">Deux cartes à ne pas confondre : le <b>modèle conceptuel du protocole</b> (les relations testées, avec leurs effets estimés) et un <b>réseau exploratoire</b> (corrélations partielles entre items, qui ne teste aucune hypothèse). Faites tourner, zoomez, cliquez un nœud ou un lien.</PageHead>
      <Tabs value={tab} onChange={setTab} tabs={[["modele", "Modèle conceptuel (testé)"], ["reseau", "Réseau exploratoire"]]} />
      {tab === "modele" ? <ModelMap /> : <NetMap />}
    </>
  );
}

function Exports({ kind }: { kind: "modele" | "exploratoire" }) {
  return (
    <div className="row">{[["graphml", "GraphML (Gephi, Cytoscape)"], ["gexf", "GEXF (Gephi)"], ["csv-edges", "Arêtes CSV"], ["csv-nodes", "Nœuds CSV"], ["json", "JSON"]].map(([f, l]) => (
      <Busy key={f} cls="btn sm" action={() => download(`/analysis/graph/export?kind=${kind}&fmt=${f}`, `kizuna-${kind}-${f}.${f.startsWith("csv") ? "csv" : f}`).catch((e) => alert(e.message))}>{l}</Busy>))}</div>
  );
}

function snapshotPng(name: string) {
  const c = document.querySelector(".stage canvas") as HTMLCanvasElement | null; if (!c) return;
  const a = document.createElement("a"); a.href = c.toDataURL("image/png"); a.download = name; a.click();
}

function ModelMap() {
  const { data, error, loading } = useApi<Model>("/analysis/graph/modele");
  const [sel, setSel] = useState<string | null>(null); const [labels, setLabels] = useState(true); const [rot, setRot] = useState(true);
  const { nodes, edges } = useMemo(() => {
    if (!data) return { nodes: [] as SNode[], edges: [] as SEdge[] };
    const strength: Record<string, number> = {};
    const ns: SNode[] = data.nodes.map((n) => ({ id: n.id, label: n.label, tag: n.tag, pos: n.pos, color: GROUP[n.group] ?? "#aaa", size: n.group === "outcome" ? 0.62 : 0.44 }));
    const es: SEdge[] = data.edges.map((e, i) => {
      const supports = e.estimated && e.significant && ((e.expected === "+" && (e.or ?? 1) > 1) || (e.expected === "-" && (e.or ?? 1) < 1) || e.expected === null);
      const opposite = e.estimated && e.significant && !supports;
      const color = !e.estimated ? "#5a6c8f" : supports ? "#3fd29a" : opposite ? "#ff6f7d" : "#8fa3c7";
      const w = e.estimated ? 1.6 + Math.min(3.2, Math.abs(Math.log(e.or ?? 1)) * 2.4) : 1.2;
      return { id: `e${i}`, a: e.source, b: e.target, color, width: w, dash: e.kind === "moderation" || !e.estimated, arrow: e.kind === "direct", opacity: e.estimated && !e.significant ? 0.6 : 0.95, curve: e.kind === "moderation" ? 1.1 : 0, label: e.label };
    });
    void strength; return { nodes: ns, edges: es };
  }, [data]);
  const selEdge = sel?.startsWith("e") ? data?.edges[Number(sel.slice(1))] : null;
  const selNode = !selEdge && sel ? data?.nodes.find((n) => n.id === sel) : null;
  return (
    <Gate loading={loading} error={error} data={data}>{data && (
      <div className="stack">
        <div className="stage">
          <div className="hud"><button className="btn sm" onClick={() => setLabels(!labels)}>{labels ? "Masquer" : "Afficher"} les étiquettes</button><button className="btn sm" onClick={() => setRot(!rot)}>{rot ? "Pause" : "Rotation"}</button><button className="btn sm" onClick={() => snapshotPng("kizuna-modele-3d.png")}>Capturer PNG</button></div>
          <Scene3D nodes={nodes} edges={edges} labels={labels} rotate={rot} selected={sel} onSelect={setSel} />
          <div className="legend"><div><span style={{ color: "#3fd29a" }}>━</span> effet significatif dans le sens attendu · <span style={{ color: "#ff6f7d" }}>━</span> sens opposé · <span style={{ color: "#8fa3c7" }}>━</span> non significatif · <span style={{ color: "#5a6c8f" }}>╌</span> non estimé</div><div>Trait plein + flèche = effet direct · pointillé courbe = modération · épaisseur = |ln OR|</div></div>
          {(selEdge || selNode) && <div className="info">
            {selEdge && <><b>{selEdge.label}</b><div style={{ margin: "6px 0" }}>{selEdge.estimated ? <>OR <b className="mono">{nf(selEdge.or)}</b> [{nf(selEdge.ci_low)} ; {nf(selEdge.ci_high)}]<br />p = {pf(selEdge.p)} {selEdge.significant ? <Badge cls="ok">significatif</Badge> : <Badge>non significatif</Badge>}</> : "Relation non estimée (variables de contrôle regroupées)."}</div><div className="note">Sens attendu : {selEdge.expected === "+" ? "augmente l'échec" : selEdge.expected === "-" ? "réduit l'effet / l'échec" : "—"}{selEdge.hypothesis && <> · <a href={`/hypotheses/${selEdge.hypothesis}`}>voir {selEdge.hypothesis}</a></>}</div></>}
            {selNode && <><b>{selNode.label}</b><div className="note" style={{ marginTop: 4 }}>{selNode.tag}</div></>}
          </div>}
        </div>
        <Card title="Exporter le graphe" sub={data.note}><Exports kind="modele" /></Card>
      </div>
    )}</Gate>
  );
}

function NetMap() {
  const { data, error, loading } = useApi<Net>("/analysis/graph/exploratoire");
  const [sel, setSel] = useState<string | null>(null); const [labels, setLabels] = useState(true); const [rot, setRot] = useState(true);
  const { nodes, edges } = useMemo(() => {
    if (!data?.available || !data.nodes || !data.edges) return { nodes: [] as SNode[], edges: [] as SEdge[] };
    const maxS = Math.max(...data.nodes.map((n) => n.strength), 0.001);
    const c = [0, 1, 2].map((k) => data.nodes!.reduce((a, n) => a + [n.x, n.y, n.z][k], 0) / data.nodes!.length);
    const R = Math.max(...data.nodes.map((n) => Math.hypot(n.x - c[0], n.y - c[1], n.z - c[2])), 0.001);
    const sc = 6.2 / R;
    const ns: SNode[] = data.nodes.map((n) => ({ id: n.id, label: n.label, pos: [(n.x - c[0]) * sc, (n.y - c[1]) * sc, (n.z - c[2]) * sc], color: n.id === "echec" ? "#ffd166" : COMM[n.community % COMM.length], size: 0.17 + 0.2 * (n.strength / maxS), tag: n.id === "echec" ? "Issue" : undefined }));
    const es: SEdge[] = data.edges.map((e, i) => ({ id: `n${i}`, a: e.source, b: e.target, color: e.weight >= 0 ? "#6aa8ff" : "#ff8a7a", width: 0.8 + e.abs * 9, opacity: 0.35 + 0.6 * e.inclusion, label: `${e.source}–${e.target}` }));
    return { nodes: ns, edges: es };
  }, [data]);
  const selNode = data?.nodes?.find((n) => n.id === sel);
  const selEdge = sel?.startsWith("n") ? data?.edges?.[Number(sel.slice(1))] : null;
  const st = data?.stability;
  const badge = data?.status === "interpretable" ? <Badge cls="ok">stable · interprétable</Badge> : data?.status === "exploratoire" ? <Badge cls="warn">stabilité modérée : exploratoire</Badge> : <Badge cls="bad">verrouillé</Badge>;
  return (
    <Gate loading={loading} error={error} data={data}>{data && (!data.available ? (
      <div className="callout warn"><b>Réseau verrouillé.</b> {data.reason ?? "Données insuffisantes."} <div className="note" style={{ marginTop: 6 }}>Un réseau de {data.p} nœuds estimé sur trop peu de projets produirait des liens instables : l'outil refuse de l'afficher plutôt que de produire un joli graphique trompeur (minimum du plan : {data.min_n} projets complets).</div></div>
    ) : (
      <div className="stack">
        <div className="row">{badge}<span className="note">n = {data.n} · {data.nodes?.length} nœuds · {data.edges?.length} liens · densité {pct(data.density)} · CS-coefficient = {nf(st?.cs_strength)} (seuils {nf(st?.cs_min)} / {nf(st?.cs_good)})</span></div>
        {data.status !== "interpretable" && <div className="callout warn">Le coefficient de stabilité est inférieur à 0,5 : lire ce réseau comme une aide à l'exploration (quelles relations explorer ?), jamais comme une preuve. Ne pas commenter les centralités.</div>}
        <div className="stage">
          <div className="hud"><button className="btn sm" onClick={() => setLabels(!labels)}>{labels ? "Masquer" : "Afficher"} les étiquettes</button><button className="btn sm" onClick={() => setRot(!rot)}>{rot ? "Pause" : "Rotation"}</button><button className="btn sm" onClick={() => snapshotPng("kizuna-reseau-3d.png")}>Capturer PNG</button></div>
          <Scene3D nodes={nodes} edges={edges} labels={labels} rotate={rot} selected={sel} onSelect={setSel} extent={7} />
          <div className="legend"><div>Couleur = communauté (Louvain) · taille = force du nœud · <span style={{ color: "#6aa8ff" }}>━</span> corrélation partielle positive · <span style={{ color: "#ff8a7a" }}>━</span> négative · opacité = fréquence de l'arête sur 100 rééchantillonnages</div></div>
          {(selNode || selEdge) && <div className="info">
            {selNode && <><b>{selNode.label}</b><div className="small" style={{ marginTop: 6 }}>Force {nf(selNode.strength)} · Proximité {nf(selNode.closeness)} · Intermédiarité {nf(selNode.betweenness)} · Influence attendue {nf(selNode.expected_influence)}<br />Construit : {selNode.construct} · Communauté {selNode.community + 1}</div></>}
            {selEdge && <><b>{selEdge.source} — {selEdge.target}</b><div className="small" style={{ marginTop: 6 }}>Corrélation partielle {nf(selEdge.weight, 3)} (IC bootstrap [{nf(selEdge.ci_low, 3)} ; {nf(selEdge.ci_high, 3)}])<br />Présente dans {pct(selEdge.inclusion)} des rééchantillonnages</div></>}
          </div>}
        </div>
        <div className="grid g2">
          <Card title="Centralités" sub={data.status === "interpretable" ? "Les nœuds les plus connectés du réseau." : "À titre indicatif seulement (réseau instable)."}>
            <Table head={["Item", "Force", "Intermédiarité", "Communauté"]} num={[1, 2]} rows={[...(data.nodes ?? [])].sort((a, b) => b.strength - a.strength).map((n) => [n.label, nf(n.strength), nf(n.betweenness), n.community + 1])} />
          </Card>
          <Card title="Stabilité (suppression de cas)" sub="Part des sous-échantillons où les forces restent corrélées à r > 0,7 avec celles de l'échantillon complet.">
            <Table head={["Cas retirés", "Part stable"]} num={[0, 1]} rows={(st?.levels ?? []).map((l) => [pct(l.drop), pct(l.share_ok)])} />
            <div style={{ height: 12 }} /><Exports kind="exploratoire" />
          </Card>
        </div>
        <p className="note">{data.note}</p>
      </div>
    ))}</Gate>
  );
}
