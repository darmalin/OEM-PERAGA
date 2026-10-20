import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require
from app.core.config import get_settings
from app.core.db import get_session
from app.core.pagination import Page
from app.modules.importexport import service
from app.modules.importexport.rules import ImportType
from app.modules.importexport.schemas import (
    DownloadOut,
    EditionParam,
    ImportErrorOut,
    ImportErrorParams,
    ImportJobOut,
    ImportListParams,
    JobAccepted,
    PreviewOut,
)

router = APIRouter(prefix="/visitor-leads/imports", tags=["imports"])
Session = Annotated[AsyncSession, Depends(get_session)]
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


async def _read_limited(file: UploadFile) -> bytes:
    # Read one byte past the limit so oversize files are detected without buffering them all.
    return await file.read(get_settings().import_max_bytes + 1)


@router.post("", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED)
async def start_import(
    session: Session,
    edition_id: Annotated[uuid.UUID, Form()],
    file: Annotated[UploadFile, File()],
    import_type: Annotated[ImportType, Form()] = ImportType.LEADS_ONLY,
    column_mapping: Annotated[str | None, Form(max_length=20_000)] = None,
    save_mapping: Annotated[bool, Form()] = False,
    ctx: AuthContext = Depends(require("visitor.import")),
) -> JobAccepted:
    return await service.start_import(
        session,
        ctx,
        edition_id=edition_id,
        file_name=file.filename or "upload.xlsx",
        content_type=file.content_type,
        data=await _read_limited(file),
        import_type=import_type,
        column_mapping=column_mapping,
        save_mapping=save_mapping,
    )


@router.post("/preview", response_model=PreviewOut)
async def preview_import(
    session: Session,
    edition_id: Annotated[uuid.UUID, Form()],
    file: Annotated[UploadFile, File()],
    ctx: AuthContext = Depends(require("visitor.import")),
) -> PreviewOut:
    return await service.preview(
        session,
        ctx,
        edition_id,
        file.filename or "upload.xlsx",
        file.content_type,
        await _read_limited(file),
    )


@router.get(
    "/template",
    response_class=Response,
    responses={200: {"content": {XLSX: {}}, "description": "Import template"}},
)
async def import_template(
    session: Session,
    params: Annotated[EditionParam, Query()],
    ctx: AuthContext = Depends(require("visitor.import")),
) -> Response:
    content = await service.template(session, ctx, params.edition_id)
    return Response(
        content,
        media_type=XLSX,
        headers={"Content-Disposition": 'attachment; filename="visitor-import-template.xlsx"'},
    )


@router.get("", response_model=Page[ImportJobOut])
async def list_imports(
    session: Session,
    params: Annotated[ImportListParams, Query()],
    ctx: AuthContext = Depends(require("visitor.import")),
) -> Page[ImportJobOut]:
    return await service.list_jobs(session, ctx, params)


@router.get("/{job_id}", response_model=ImportJobOut)
async def get_import(
    job_id: uuid.UUID, session: Session, ctx: AuthContext = Depends(require("visitor.import"))
) -> ImportJobOut:
    return await service.get_job(session, ctx, job_id)


@router.get("/{job_id}/errors", response_model=Page[ImportErrorOut])
async def import_errors(
    job_id: uuid.UUID,
    session: Session,
    params: Annotated[ImportErrorParams, Query()],
    ctx: AuthContext = Depends(require("visitor.import")),
) -> Page[ImportErrorOut]:
    return await service.list_errors(session, ctx, job_id, params)


@router.get("/{job_id}/errors.xlsx", response_model=DownloadOut)
async def import_errors_xlsx(
    job_id: uuid.UUID, session: Session, ctx: AuthContext = Depends(require("visitor.import"))
) -> DownloadOut:
    url = await service.error_report_url(session, ctx, job_id)
    return DownloadOut(url=url, expires_in=get_settings().presigned_url_ttl_seconds)
