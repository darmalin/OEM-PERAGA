import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require
from app.core.db import get_session
from app.core.pagination import Page
from app.modules.orders import service
from app.modules.orders.schemas import (
    CopyFormsIn,
    CopyFormsOut,
    ItemImportOut,
    OrderFormCreateIn,
    OrderFormItemCreateIn,
    OrderFormItemListParams,
    OrderFormItemOut,
    OrderFormItemUpdateIn,
    OrderFormListParams,
    OrderFormOut,
    OrderFormUpdateIn,
)

router = APIRouter(prefix="/order-forms", tags=["order-forms"])
Session = Annotated[AsyncSession, Depends(get_session)]
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
Manage = Depends(require(service.MANAGE))
Read = Depends(require(*service.READ_PERMISSIONS))


@router.get("", response_model=Page[OrderFormOut])
async def list_forms(
    session: Session, params: Annotated[OrderFormListParams, Query()], ctx: AuthContext = Read
) -> Page[OrderFormOut]:
    return await service.list_forms(session, ctx, params)


@router.post("", response_model=OrderFormOut, status_code=status.HTTP_201_CREATED)
async def create_form(
    data: OrderFormCreateIn, session: Session, ctx: AuthContext = Manage
) -> OrderFormOut:
    return await service.create_form(session, ctx, data)


# Before /{form_id}, which would take these words as an id.
@router.post("/copy", response_model=CopyFormsOut)
async def copy_forms(
    data: CopyFormsIn, session: Session, ctx: AuthContext = Manage
) -> CopyFormsOut:
    return await service.copy_forms(session, ctx, data)


@router.get(
    "/item-import-template",
    response_class=Response,
    responses={200: {"content": {XLSX: {}}}},
)
async def item_import_template(ctx: AuthContext = Manage) -> Response:
    return Response(
        service.import_template(),
        media_type=XLSX,
        headers={
            "Content-Disposition": 'attachment; filename="order-form-catalog-template.xlsx"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/{form_id}", response_model=OrderFormOut)
async def get_form(form_id: uuid.UUID, session: Session, ctx: AuthContext = Read) -> OrderFormOut:
    return await service.get_form(session, ctx, form_id)


@router.patch("/{form_id}", response_model=OrderFormOut)
async def update_form(
    form_id: uuid.UUID, data: OrderFormUpdateIn, session: Session, ctx: AuthContext = Manage
) -> OrderFormOut:
    return await service.update_form(session, ctx, form_id, data)


@router.get("/{form_id}/items", response_model=Page[OrderFormItemOut])
async def list_items(
    form_id: uuid.UUID,
    session: Session,
    params: Annotated[OrderFormItemListParams, Query()],
    ctx: AuthContext = Read,
) -> Page[OrderFormItemOut]:
    return await service.list_items(session, ctx, form_id, params)


@router.post(
    "/{form_id}/items", response_model=OrderFormItemOut, status_code=status.HTTP_201_CREATED
)
async def create_item(
    form_id: uuid.UUID, data: OrderFormItemCreateIn, session: Session, ctx: AuthContext = Manage
) -> OrderFormItemOut:
    return await service.create_item(session, ctx, form_id, data)


# Before /{form_id}/items/{item_id}.
@router.post("/{form_id}/items/import", response_model=ItemImportOut)
async def import_items(
    form_id: uuid.UUID,
    session: Session,
    file: Annotated[UploadFile, File()],
    ctx: AuthContext = Manage,
) -> ItemImportOut:
    data = await file.read(service.IMPORT_MAX_BYTES + 1)
    return await service.import_items(session, ctx, form_id, data=data)


@router.patch("/{form_id}/items/{item_id}", response_model=OrderFormItemOut)
async def update_item(
    form_id: uuid.UUID,
    item_id: uuid.UUID,
    data: OrderFormItemUpdateIn,
    session: Session,
    ctx: AuthContext = Manage,
) -> OrderFormItemOut:
    return await service.update_item(session, ctx, form_id, item_id, data)


@router.post("/{form_id}/items/{item_id}/image", response_model=OrderFormItemOut)
async def set_item_image(
    form_id: uuid.UUID,
    item_id: uuid.UUID,
    session: Session,
    file: Annotated[UploadFile, File()],
    version: Annotated[int, Form()],
    ctx: AuthContext = Manage,
) -> OrderFormItemOut:
    return await service.set_item_image(
        session,
        ctx,
        form_id,
        item_id,
        file_name=file.filename or "image",
        content_type=file.content_type,
        # One byte past the limit so an oversize file is detected without buffering all of it.
        data=await file.read(service.IMAGE_MAX_BYTES + 1),
        version=version,
    )


@router.get(
    "/{form_id}/items/{item_id}/image",
    response_class=StreamingResponse,
    responses={200: {"content": {"image/jpeg": {}, "image/png": {}}}},
)
async def item_image(
    form_id: uuid.UUID, item_id: uuid.UUID, session: Session, ctx: AuthContext = Read
) -> StreamingResponse:
    chunks, name, media_type = await service.item_image(session, ctx, form_id, item_id)
    return _inline(chunks, name, media_type)


def _inline(chunks: Iterator[bytes], filename: str, media_type: str) -> StreamingResponse:
    """Shown in an <img>; the name comes from the server, never from the upload."""
    return StreamingResponse(
        chunks,
        media_type=media_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
