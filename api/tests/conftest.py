import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.update({"DATABASE_URL": "sqlite:///:memory:", "JWT_SECRET": "test-secret", "ADMIN_EMAIL": "admin@test.io", "ADMIN_PASSWORD": "motdepasse-test-123",
                   "TALLY_SIGNING_SECRET": "whsec_test", "TALLY_API_KEY": "tly-test", "TALLY_FORM_ID": "446dvO", "EMAIL_SALT": "salt", "DEMO_MODE": "false"})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from app import config, db
    config.reset_settings()
    db.init_engine("sqlite:///:memory:")
    from app.main import create_app
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def token(client):
    r = client.post("/auth/login", json={"email": "admin@test.io", "password": "motdepasse-test-123"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def auth(token):
    return {"Authorization": f"Bearer {token}"}
