from __future__ import annotations

from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..security import current_user
from ..service import Source, load_source


def get_source(snapshot: int | None = Query(None, description="Identifiant d'un instantané figé (sinon données courantes)"),
               db: Session = Depends(get_db), user=Depends(current_user)) -> Source:
    try:
        return load_source(db, snapshot)
    except KeyError:
        raise HTTPException(404, "Instantané introuvable")


def forbid_in_demo() -> None:
    if get_settings().demo_mode:
        raise HTTPException(403, "Action désactivée en mode démonstration")
