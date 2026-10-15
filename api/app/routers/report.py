from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from .. import report as RP
from ..db import get_db
from ..service import Source
from .deps import get_source
from .quali import synthesis
from ..security import current_user

router = APIRouter(prefix="/report", tags=["rapport"])


def _quali(src: Source, db: Session, user) -> dict:
    return synthesis(None, src, db, user)


@router.get("/preview")
def preview(src: Source = Depends(get_source), db: Session = Depends(get_db), user=Depends(current_user)):
    bl = RP.blocks(src, _quali(src, db, user))
    return {"blocks": [{"type": t, "content": rest} for t, *rest in bl], "markdown": RP.to_markdown(bl)}


@router.get("/markdown")
def markdown(src: Source = Depends(get_source), db: Session = Depends(get_db), user=Depends(current_user)):
    md = RP.to_markdown(RP.blocks(src, _quali(src, db, user)))
    return PlainTextResponse(md, headers={"Content-Disposition": 'attachment; filename="kizuna-rapport.md"'})


@router.get("/docx")
def docx(src: Source = Depends(get_source), db: Session = Depends(get_db), user=Depends(current_user)):
    data = RP.to_docx(RP.blocks(src, _quali(src, db, user)))
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": 'attachment; filename="kizuna-rapport.docx"'})


@router.get("/xlsx")
def xlsx(src: Source = Depends(get_source), user=Depends(current_user)):
    return Response(RP.to_xlsx(src), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="kizuna-tableaux.xlsx"'})


@router.get("/package")
def package(src: Source = Depends(get_source), db: Session = Depends(get_db), user=Depends(current_user)):
    data = RP.package_zip(src, _quali(src, db, user))
    return Response(data, media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="kizuna-reproductibilite.zip"'})
