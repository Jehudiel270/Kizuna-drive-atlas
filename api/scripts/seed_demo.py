"""Remplit la base avec des réponses SIMULÉES (n, graine) pour tester le site. Usage : python -m scripts.seed_demo 165"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core import synthetic as S  # noqa: E402
from app.core.normalize import Codebook, normalize_api_payload  # noqa: E402
from app.core.plan import get_codebook  # noqa: E402
from app.db import create_all, session_scope  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.routers.ingest import upsert_rows  # noqa: E402

n = int(sys.argv[1]) if len(sys.argv) > 1 else 165
create_all()
cb = get_codebook()
rows = normalize_api_payload(S.to_tally_api_payload(S.generate(n, seed=7), cb), Codebook(cb), get_settings().email_salt)
with session_scope() as db:
    print(upsert_rows(db, rows, "demo", get_settings().tally_form_id))
