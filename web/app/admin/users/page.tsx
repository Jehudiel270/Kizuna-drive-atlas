"use client";
import { FormEvent, useState } from "react";
import { api, ApiError, useApi, useApp } from "@/lib/api";
import { Badge, Busy, Card, ErrorBox, Gate, PageHead, Table } from "@/components/ui";

type Account = { id: number; email: string; name: string; role: string; active: boolean };

export default function UserManagement() {
  const { me } = useApp();
  const accounts = useApi<Account[]>(me?.role === "admin" ? "/auth/users" : null);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("analyste");
  const [error, setError] = useState<ApiError | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  if (me?.role !== "admin") {
    return <><PageHead title="Gestion des accès" /><ErrorBox error="Cette page est réservée aux administrateurs." /></>;
  }

  const createAccount = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setMessage(null);
    setSaving(true);
    try {
      const account = await api<Account>("/auth/users", {
        method: "POST",
        json: { email, name, password, role },
      });
      setEmail("");
      setName("");
      setPassword("");
      setMessage(`Le compte ${account.email} a été créé.`);
      accounts.reload();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause : new ApiError(0, "La création du compte a échoué."));
    } finally {
      setSaving(false);
    }
  };

  const deactivateAccount = async (account: Account) => {
    if (!window.confirm(`Désactiver le compte de ${account.email} ?`)) return;
    setError(null);
    setMessage(null);
    try {
      await api(`/auth/users/${account.id}`, { method: "DELETE" });
      setMessage(`Le compte ${account.email} a été désactivé.`);
      accounts.reload();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause : new ApiError(0, "La désactivation du compte a échoué."));
    }
  };

  return (
    <>
      <PageHead title="Gestion des accès">Créez les comptes de l’équipe. Les mots de passe sont envoyés directement à l’API et ne sont jamais affichés dans la liste.</PageHead>
      {message && <div className="callout ok" role="status">{message}</div>}
      <ErrorBox error={error} />
      <Card title="Créer un compte" sub="Le mot de passe doit contenir au moins 5 caractères. Communiquez-le à son destinataire par un canal privé.">
        <form className="account-form" onSubmit={createAccount}>
          <div><label className="f" htmlFor="account-name">Nom</label><input id="account-name" type="text" autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} /></div>
          <div><label className="f" htmlFor="account-email">E-mail</label><input id="account-email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></div>
          <div><label className="f" htmlFor="account-role">Rôle</label><select id="account-role" value={role} onChange={(event) => setRole(event.target.value)}><option value="analyste">Analyste</option><option value="lecteur">Lecteur</option><option value="admin">Administrateur</option></select></div>
          <div><label className="f" htmlFor="account-password">Mot de passe initial</label><input id="account-password" type="password" autoComplete="new-password" minLength={5} required value={password} onChange={(event) => setPassword(event.target.value)} /></div>
          <button className="btn primary" type="submit" disabled={saving}>{saving && <span className="spin" />}Créer le compte</button>
        </form>
      </Card>
      <Gate loading={accounts.loading} error={accounts.error} data={accounts.data}>
        {accounts.data && <Card title={`${accounts.data.length} comptes`}>
          <Table
            head={["Nom", "E-mail", "Rôle", "État", ""]}
            rows={accounts.data.map((account) => [
              account.name || "—",
              account.email,
              account.role,
              <Badge key="status" cls={account.active ? "ok" : "bad"}>{account.active ? "Actif" : "Désactivé"}</Badge>,
              account.active && account.email !== me.email
                ? <Busy key="deactivate" cls="btn sm danger" action={() => deactivateAccount(account)}>Désactiver</Busy>
                : "",
            ])}
          />
        </Card>}
      </Gate>
    </>
  );
}
