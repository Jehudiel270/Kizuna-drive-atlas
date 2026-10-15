"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "@/lib/api";

export default function Login() {
  const r = useRouter();
  const [email, setEmail] = useState(""); const [pw, setPw] = useState(""); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  async function go(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr("");
    try { const j = await api<{ token: string }>("/auth/login", { method: "POST", json: { email, password: pw } }); setToken(j.token); r.replace("/"); }
    catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  }
  return (
    <div className="login"><form className="card" onSubmit={go}>
      <div className="brand" style={{ padding: 0, marginBottom: 18 }}><div className="logo"><i /></div><div><b>Kizuna Atlas</b><small>Accès équipe de recherche</small></div></div>
      <label className="f">Adresse e-mail</label><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus required />
      <label className="f" style={{ marginTop: 12 }}>Mot de passe</label><input type="password" value={pw} onChange={(e) => setPw(e.target.value)} required />
      {err && <div className="callout bad" style={{ marginTop: 12 }}>{err}</div>}
      <button className="btn primary" style={{ marginTop: 16, width: "100%", justifyContent: "center" }} disabled={busy}>{busy ? "Connexion…" : "Se connecter"}</button>
      <p className="note" style={{ marginTop: 14 }}>Les données de l'enquête sont réservées à l'équipe. Les comptes sont créés par l'administrateur.</p>
    </form></div>
  );
}
