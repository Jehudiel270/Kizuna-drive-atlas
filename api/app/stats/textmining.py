"""Aide à l'analyse de contenu thématique (protocole 5.4) : termes saillants échec vs succès, extraits."""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

import pandas as pd

STOP = set("""
a à au aux avec ce ces cet cette ceux chaque comme dans de des du donc dont elle elles en est et été étaient était être eux il ils j je l la le les leur leurs
lui ma mais me même mes moi mon ne ni nos notre nous on ou où par pas plus pour qu que quel quelle quels qui sa sans se ses si son sur ta te tes toi ton tu un une
vos votre vous y ai as avons avez ont avait avaient aussi alors ainsi après avant bien car cela celle celui encore entre fait faire fois peu peut sont tous tout
toute toutes très trop avoir sous vers puis lors ça c d s t n m ceci cependant déjà depuis dès doit être étant jamais moins nos non parce pendant peu plusieurs
sera seront soit tant tel telle toujours seulement quand quelques rien sans soi
""".split())


def tokenize(text: str) -> list[str]:
    t = unicodedata.normalize("NFC", str(text).lower().replace("’", "'"))
    toks = re.findall(r"[a-zàâäçéèêëîïôöùûüÿœæ]{3,}", t)
    return [w for w in toks if w not in STOP]


def keyness(docs_a: list[str], docs_b: list[str], min_df: int = 2, top: int = 15) -> dict:
    """Log-rapport de cotes avec a priori de Dirichlet informatif (Monroe, Colaresi & Quinn, 2008), z-score signé.
    z > 0 : terme plus caractéristique du groupe A (ex. échecs) ; z < 0 : du groupe B (ex. succès)."""
    ca, cb = Counter(), Counter()
    dfc: Counter = Counter()
    for d in docs_a:
        toks = tokenize(d)
        ca.update(toks)
        dfc.update(set(toks))
    for d in docs_b:
        toks = tokenize(d)
        cb.update(toks)
        dfc.update(set(toks))
    vocab = [w for w in dfc if dfc[w] >= min_df]
    na, nb = sum(ca[w] for w in vocab) or 1, sum(cb[w] for w in vocab) or 1
    a0 = 0.5 * (na + nb) / max(len(vocab), 1) * len(vocab) / 100 + 1.0
    total = {w: ca[w] + cb[w] for w in vocab}
    tot_n = sum(total.values()) or 1
    rows = []
    for w in vocab:
        aw = a0 * total[w] / tot_n
        la = math.log((ca[w] + aw) / (na + a0 - ca[w] - aw))
        lb = math.log((cb[w] + aw) / (nb + a0 - cb[w] - aw))
        var = 1 / (ca[w] + aw) + 1 / (cb[w] + aw)
        rows.append({"term": w, "z": (la - lb) / math.sqrt(var), "a": ca[w], "b": cb[w]})
    rows.sort(key=lambda r: -r["z"])
    return {"group_a": [r for r in rows[:top] if r["z"] > 0], "group_b": [r for r in rows[::-1][:top] if r["z"] < 0]}


def kwic(text: str, term: str, width: int = 60) -> str | None:
    m = re.search(re.escape(term), text, flags=re.I)
    if not m:
        return None
    s, e = max(0, m.start() - width), min(len(text), m.end() + width)
    return ("…" if s > 0 else "") + text[s:e] + ("…" if e < len(text) else "")


def open_answers(df: pd.DataFrame, cols: tuple[str, ...] = ("txt_facteur", "txt_autre")) -> list[dict]:
    out = []
    for _, r in df[df["analysable"]].iterrows():
        for c in cols:
            v = r.get(c)
            if isinstance(v, str) and v.strip():
                out.append({"submission_id": r["_id"], "question": c, "text": v.strip(), "issue": r.get("issue")})
    return out
