"""Normalisation, issue du projet, indice de formalisation, fiabilité, Firth, Holm, Khi²."""
import base64
import hashlib
import hmac
import json

import numpy as np
import pandas as pd

from app.core import constructs as C
from app.core import normalize as NZ
from app.core import plan as P
from app.core import synthetic as S
from app.stats import descriptives as D
from app.stats import hypotheses as H
from app.stats import logit as L
from app.stats import reliability as R

PLAN = P.get_plan()
CB = P.get_codebook()


def test_codebook_unique_ids_and_names():
    names = [v["name"] for v in CB["variables"]]
    ids = [v["tally_id"] for v in CB["variables"] if v.get("tally_id")]
    assert len(names) == len(set(names)) and len(ids) == len(set(ids))


def test_plan_valid():
    assert P.validate_plan(PLAN) == []
    assert [h["id"] for h in PLAN["hypotheses"]] == ["H1", "H2", "H3", "H4", "H5"]


def test_api_csv_roundtrip_equivalent():
    raw = S.generate(60, seed=3)
    a = NZ.answers_rows_to_frame(NZ.normalize_api_payload(S.to_tally_api_payload(raw, CB), NZ.Codebook(CB), "s"))
    c = NZ.answers_rows_to_frame(NZ.normalize_csv(S.to_csv_text(raw, CB), NZ.Codebook(CB), "s"))
    da, dc = C.build_dataset(a, PLAN), C.build_dataset(c, PLAN)
    assert da["analysable"].sum() == dc["analysable"].sum() > 20
    assert (da["issue"].fillna("na").values == dc["issue"].fillna("na").values).all()
    np.testing.assert_allclose(da["gouvernance"].astype(float), dc["gouvernance"].astype(float), equal_nan=True)


def test_email_is_hashed_not_stored():
    raw = S.generate(10, seed=1)
    raw["email"] = ["a@b.com"] + [None] * (len(raw) - 1)
    rows = NZ.normalize_api_payload(S.to_tally_api_payload(raw, CB), NZ.Codebook(CB), "salt")
    em = rows[0]["answers"].get("email")
    assert em and "@" not in em and em == NZ.hash_email("a@b.com", "salt")


def test_webhook_matches_by_label():
    payload = {"eventType": "FORM_RESPONSE", "data": {"submissionId": "w1", "respondentId": "r1", "createdAt": "2026-10-15T10:00:00Z", "fields": [
        {"key": "question_OJqGxA", "label": "x", "type": "MULTIPLE_CHOICE", "value": ["a1"], "options": [{"id": "a1", "text": "Oui, j'accepte"}]},
        {"key": "question_zzz", "label": "Depuis combien d'années votre entreprise est-elle en activité ?", "type": "INPUT_NUMBER", "value": 7}]}}
    r = NZ.normalize_webhook(payload, NZ.Codebook(CB), "s")
    assert r["id"] == "w1" and r["answers"]["consent"].startswith("Oui") and r["answers"]["anciennete"] == 7


def _row(**kw):
    return pd.Series(kw)


def test_outcome_rules():
    o = PLAN["outcome"]
    ok = o["usage_success_startswith"]
    assert C.classify_outcome(_row(usage_actuel=ok + " tout à fait", arrete="Non", retour_ancien="Non", usage_taux="75 à 100 %"), PLAN)[0] == "succes"
    assert C.classify_outcome(_row(usage_actuel=o["usage_ongoing_startswith"] + " x"), PLAN)[0] == "en_cours"
    assert C.classify_outcome(_row(usage_actuel=ok + " x", arrete="Oui", retour_ancien="Non", usage_taux="75 à 100 %"), PLAN)[0] == "echec_total"
    assert C.classify_outcome(_row(usage_actuel=ok + " x", arrete="Non", retour_ancien="Oui", usage_taux="75 à 100 %"), PLAN)[0] == "echec_partiel"
    assert C.classify_outcome(_row(arrete="Non"), PLAN)[0] != "succes"


def test_dataset_flags_and_ongoing_excluded():
    df = C.build_dataset(S.generate(120, seed=5, extra_rate=0.3), PLAN)
    assert not df.loc[df["issue"] == "en_cours", "analysable"].any()
    assert not df.loc[~df["consent_ok"], "analysable"].any()
    assert df["echec"].dropna().isin([0, 1]).all()
    assert 0 <= df["formalisation_idx"].dropna().min() and df["formalisation_idx"].dropna().max() <= 1


def test_cronbach_known_value():
    rng = np.random.default_rng(0)
    t = rng.normal(size=500)
    M = np.column_stack([t + rng.normal(scale=0.7, size=500) for _ in range(4)])
    a = R.cronbach_alpha(M)
    k, r = 4, 1 / (1 + 0.49)
    assert abs(a - k * r / (1 + (k - 1) * r)) < 0.04
    assert np.isnan(R.cronbach_alpha(M[:, :1]))


def test_holm_monotone_and_bounded():
    p = {"H1": 0.01, "H2": 0.02, "H3": 0.5, "H4": 0.03, "H5": 0.04}
    adj = H.holm(p)
    assert adj["H1"] == 0.05 and all(adj[k] >= p[k] for k in p) and max(adj.values()) <= 1
    assert adj["H4"] >= adj["H2"] >= adj["H1"]


def test_firth_finite_under_separation_and_close_to_ml_otherwise():
    rng = np.random.default_rng(1)
    x = rng.normal(size=300)
    y = (rng.random(300) < 1 / (1 + np.exp(-(0.4 + 0.8 * x)))).astype(float)
    d = pd.DataFrame({"y": y, "x": x})
    ml, fi = L.fit_binary("y ~ x", d, method="ml"), L.fit_binary("y ~ x", d, method="firth")
    assert abs(ml.params.iloc[1] - fi.params.iloc[1]) < 0.1
    sep = pd.DataFrame({"y": [0] * 10 + [1] * 10, "x": list(range(10)) + list(range(11, 21))})
    f = L.fit_binary("y ~ x", sep, method="firth")
    assert np.isfinite(f.params.to_numpy()).all()


def test_cramers_v_corrected_zero_for_independence():
    tab = np.array([[20, 20], [20, 20]])
    from scipy import stats
    chi2 = stats.chi2_contingency(tab, correction=False)[0]
    assert D.cramers_v_corrected(chi2, 80, 2, 2) == 0.0
    assert D.cramers_v_corrected(30.0, 80, 2, 2) > 0.5


def test_planted_effects_recovered_and_null_not_found():
    df = C.build_dataset(S.generate(500, seed=11), PLAN)
    res = H.run_hypotheses(df, PLAN, with_robustness=False)
    by = {h["id"]: h for h in res["hypotheses"]}
    assert by["H1"]["verdict"] in ("supported", "partial") and by["H1"]["primary"]["or"] > 1.3
    assert by["H2"]["primary"]["or"] > 1.2
    null = C.build_dataset(S.generate(400, seed=12, effects=S.NULL_EFFECTS), PLAN)
    rn = H.run_hypotheses(null, PLAN, with_robustness=False)
    assert sum(h["verdict"] == "supported" for h in rn["hypotheses"]) <= 1
