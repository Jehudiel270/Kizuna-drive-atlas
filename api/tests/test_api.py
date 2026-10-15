import base64
import hashlib
import hmac
import json
from typing import cast

from fastapi import FastAPI
from app.core import plan as P
from app.core import synthetic as S

CB = P.get_codebook()


def sign(body: bytes, secret="whsec_test") -> str:
    return base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()


def test_health_and_auth_required(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/analysis/overview").status_code == 401
    assert client.post("/auth/login", json={"email": "admin@test.io", "password": "mauvais"}).status_code == 401


def test_cors_headers_are_kept_on_internal_errors():
    from app.main import create_app
    from fastapi.testclient import TestClient

    app = create_app()
    fastapi_app = cast(FastAPI, app.app)
    fastapi_app.add_api_route("/test-internal-error", lambda: 1 / 0)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/test-internal-error", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_webhook_requires_valid_signature(client, auth):
    body = json.dumps({"eventType": "FORM_RESPONSE", "data": {"formId": "446dvO", "submissionId": "wh-1", "createdAt": "2026-10-15T10:00:00Z", "fields": [
        {"key": "question_OJqGxA", "label": "J'accepte de participer à cette étude", "type": "MULTIPLE_CHOICE", "value": ["a"], "options": [{"id": "a", "text": "Oui"}]}]}}).encode()
    assert client.post("/ingest/webhook/tally", content=body).status_code == 401
    assert client.post("/ingest/webhook/tally", content=body, headers={"Tally-Signature": "bidon"}).status_code == 401
    r = client.post("/ingest/webhook/tally", content=body, headers={"Tally-Signature": sign(body), "Content-Type": "application/json"})
    assert r.status_code == 200 and r.json()["inserted"] == 1
    # idempotent
    r2 = client.post("/ingest/webhook/tally", content=body, headers={"Tally-Signature": sign(body), "Content-Type": "application/json"})
    assert r2.json()["updated"] == 1
    assert client.post("/ingest/purge", json={"confirm": "SUPPRIMER"}, headers=auth).json()["deleted"] >= 1


def test_full_flow_csv_analysis_exclusion_snapshot(client, auth):
    raw = S.generate(165, seed=7)
    csv = S.to_csv_text(raw, CB)
    r = client.post("/ingest/csv", files={"file": ("export.csv", csv.encode(), "text/csv")}, headers=auth)
    assert r.status_code == 200 and r.json()["inserted"] == 185
    ov = client.get("/analysis/overview", headers=auth).json()
    assert ov["n_analysable"] == 165 and len(ov["hypotheses"]) == 5
    h1 = next(h for h in ov["hypotheses"] if h["id"] == "H1")
    assert h1["primary"]["or"] > 1.5
    # exclusion avec motif obligatoire
    sid = client.get("/ingest/submissions?size=5", headers=auth).json()["items"][0]["id"]
    assert client.patch(f"/ingest/submissions/{sid}", json={"excluded": True}, headers=auth).status_code == 400
    assert client.patch(f"/ingest/submissions/{sid}", json={"excluded": True, "reason": "doublon"}, headers=auth).status_code == 200
    assert client.get("/analysis/collecte", headers=auth).json()["n_total"] == 184
    # instantané figé : reste identique même si les données changent ensuite
    snap = client.post("/snapshots", json={"name": "test"}, headers=auth).json()
    n_snap = client.get(f"/analysis/collecte?snapshot={snap['id']}", headers=auth).json()["n_total"]
    client.patch(f"/ingest/submissions/{sid}", json={"excluded": False}, headers=auth)
    assert client.get("/analysis/collecte", headers=auth).json()["n_total"] == 185
    assert client.get(f"/analysis/collecte?snapshot={snap['id']}", headers=auth).json()["n_total"] == n_snap == 184
    assert len(snap["sha256"]) == 64


def test_plan_update_changes_hash_and_is_audited(client, auth):
    h0 = client.get("/config/plan", headers=auth).json()["hash"]
    assert client.put("/config/plan", json={"text": "general: {alpha: 7}"}, headers=auth).status_code == 422
    assert client.put("/config/plan", json={"text": "general: {alpha: 0.10}", "note": "test"}, headers=auth).status_code == 200
    assert client.get("/config/plan", headers=auth).json()["hash"] != h0
    assert client.get("/analysis/hypotheses", headers=auth).json()["alpha"] == 0.10
    client.post("/config/plan/reset", headers=auth)
    assert client.get("/config/plan", headers=auth).json()["hash"] == h0
    acts = [a["action"] for a in client.get("/config/audit", headers=auth).json()]
    assert "plan.update" in acts and "plan.reset" in acts


def test_quali_flow(client, auth):
    t = client.post("/quali/themes", json={"name": "Tout sur le patron", "parent_dimension": "gouvernance"}, headers=auth).json()
    ans = client.get("/quali/answers", headers=auth).json()["items"]
    assert ans
    for a in ans[:40]:
        assert client.post("/quali/code", json={"submission_id": a["submission_id"], "question": a["question"], "theme_id": t["id"]}, headers=auth).status_code == 200
    syn = client.get("/quali/synthesis", headers=auth).json()
    assert syn["themes"] and syn["n_coded_projects"] > 0
    assert client.get("/quali/kappa", headers=auth).status_code == 200


def test_reports_and_exports(client, auth):
    assert client.get("/report/docx", headers=auth).content[:2] == b"PK"
    assert client.get("/report/xlsx", headers=auth).content[:2] == b"PK"
    z = client.get("/report/package", headers=auth).content
    import io, zipfile
    names = zipfile.ZipFile(io.BytesIO(z)).namelist()
    assert "rapport.md" in names and "plan_analyse.yaml" in names and "donnees_analysables_pseudonymisees.csv" in names
    assert b"<graphml" in client.get("/analysis/graph/export?kind=modele&fmt=graphml", headers=auth).content


def test_dashboard_routes_work_before_first_submission(client, auth):
    client.post("/ingest/purge", json={"confirm": "SUPPRIMER"}, headers=auth)
    for path in ("/ingest/status", "/analysis/overview", "/analysis/descriptif", "/analysis/fiabilite",
                 "/analysis/graph/modele", "/report/preview"):
        response = client.get(path, headers=auth)
        assert response.status_code == 200, f"{path}: {response.text}"


def test_tally_api_sync_with_mock(client, auth, monkeypatch):
    import httpx
    from app.routers import ingest
    raw = S.generate(12, seed=2)
    payload = S.to_tally_api_payload(raw, CB)
    payload["hasMore"] = False

    def handler(request):
        assert request.headers["authorization"] == "Bearer tly-test"
        return httpx.Response(200, json=payload)

    real = httpx.Client
    monkeypatch.setattr(ingest.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    client.post("/ingest/purge", json={"confirm": "SUPPRIMER"}, headers=auth)
    r = client.post("/ingest/sync", headers=auth)
    assert r.status_code == 200 and r.json()["inserted"] == len(payload["submissions"])
