"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useCallback, useEffect, useState } from "react";
import { api, AppCtx, getSnap, getToken, Me, setSnapStore, setToken, SnapshotInfo } from "@/lib/api";

const NAV: { group: string; items: [string, string][] }[] = [
  { group: "Pilotage", items: [["/", "Synthèse"], ["/collecte", "Suivi de collecte"], ["/donnees", "Données & Tally"]] },
  { group: "Qualité des mesures", items: [["/fiabilite", "Fiabilité des échelles"], ["/descriptif", "Descriptif & comparaisons"]] },
  { group: "Questions de recherche", items: [["/hypotheses", "Vue d'ensemble H1–H5"], ["/hypotheses/H1", "H1 · Gouvernance"], ["/hypotheses/H2", "H2 · Compétences"], ["/hypotheses/H3", "H3 · Soutien de la direction"], ["/hypotheses/H4", "H4 · Formalisation"], ["/hypotheses/H5", "H5 · Communication"], ["/modeles", "Modèles & diagnostics"], ["/puissance", "Puissance statistique"]] },
  { group: "Exploration", items: [["/carte", "Carte 3D des relations"], ["/qualitatif", "Analyse qualitative"]] },
  { group: "Livrables", items: [["/rapport", "Rapport & exports"], ["/plan", "Plan d'analyse & codebook"]] },
];

export default function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);
  const [snapshot, setSnap] = useState<string | null>(null);
  const [snapshots, setSnapshots] = useState<SnapshotInfo[]>([]);
  const [menuOpen, setMenuOpen] = useState(false);
  const isLogin = path.startsWith("/login");

  const reloadSnapshots = useCallback(() => { api<SnapshotInfo[]>("/snapshots").then(setSnapshots).catch(() => {}); }, []);
  const setSnapshot = (s: string | null) => { setSnapStore(s); setSnap(s); };

  useEffect(() => {
    setSnap(getSnap());
    if (isLogin) { setReady(true); return; }
    api<Me>("/auth/me").then((m) => { setMe(m); setReady(true); reloadSnapshots(); }).catch(() => { setReady(true); if (!getToken()) router.replace("/login"); });
  }, [isLogin]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setMenuOpen(false);
  }, [path]);

  useEffect(() => {
    if (!menuOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("keydown", closeOnEscape);
    document.body.classList.add("nav-open");
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
      document.body.classList.remove("nav-open");
    };
  }, [menuOpen]);

  if (isLogin) return <>{children}</>;
  if (!ready) return <div className="loading" style={{ paddingTop: 120 }}><span className="spin" />Chargement…</div>;
  const active = (h: string) => (h === "/" ? path === "/" : path === h || (h === "/hypotheses" ? false : path.startsWith(h + "/")));
  const snapObj = snapshots.find((s) => String(s.id) === snapshot);

  return (
    <AppCtx.Provider value={{ me, snapshot, setSnapshot, snapshots, reloadSnapshots }}>
      <div className="shell">
        <button className={`nav-backdrop${menuOpen ? " visible" : ""}`} type="button" aria-label="Fermer le menu" onClick={() => setMenuOpen(false)} />
        <aside id="primary-navigation" className={`side${menuOpen ? " open" : ""}`}>
          <div className="brand"><div className="logo"><i /></div><div><b>Kizuna Atlas</b><small>ICPM Challenge 2026</small></div></div>
          <nav className="nav" aria-label="Navigation principale">
            {NAV.map((g) => (
              <div key={g.group}><div className="nav-group">{g.group}</div>
                {g.items.map(([h, l]) => <Link key={h} href={h} className={active(h) ? "on" : ""} aria-current={active(h) ? "page" : undefined}><span className="dot" />{l}</Link>)}</div>
            ))}
          </nav>
        </aside>
        <div className="main">
          {me?.demo && <div className="banner">Mode démonstration : toutes les données affichées sont <b>simulées</b> (effets plantés pour tester l'outil). Elles ne disent rien sur les PME réelles.</div>}
          {snapObj && <div className="banner" style={{ background: "#6aa8ff1a", color: "#b8d4ff", borderColor: "#6aa8ff44" }}>Instantané figé « {snapObj.name} » ({snapObj.n_rows} lignes, SHA-256 {snapObj.sha256.slice(0, 10)}…) — les chiffres ne changent plus.</div>}
          <header className="top">
            <button className="btn menu-toggle" type="button" aria-controls="primary-navigation" aria-expanded={menuOpen} onClick={() => setMenuOpen((open) => !open)}>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" /></svg>
              <span>Menu</span>
            </button>
            <div className="grow">Formulaire Tally <span className="mono">446dvO</span> · {me?.email}</div>
            <select style={{ width: 230 }} value={snapshot ?? ""} onChange={(e) => setSnapshot(e.target.value || null)} aria-label="Jeu de données">
              <option value="">Données courantes (en direct)</option>
              {snapshots.map((s) => <option key={s.id} value={s.id}>Instantané : {s.name}</option>)}
            </select>
            {!me?.demo && <button className="btn sm" onClick={() => { setToken(null); router.replace("/login"); }}>Déconnexion</button>}
          </header>
          <div className="page" key={path}>{children}</div>
        </div>
      </div>
    </AppCtx.Provider>
  );
}
