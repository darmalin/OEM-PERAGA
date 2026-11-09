import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require
from app.core.db import get_session
from app.core.pagination import Page
from app.modules.exhibitors import portal as exhibitors_portal
from app.modules.exhibitors.models import ExhibitorLead
from app.modules.exhibitors.portal import PortalContext, portal_account
from app.modules.exhibitors.schemas import (
    PaymentCreateIn,
    PaymentOut,
    PaymentReviewIn,
    PaymentsOut,
    PortalPaymentsOut,
)
from app.modules.orders import payments, portal, review, service
from app.modules.orders.rules import AttachmentPurpose
from app.modules.orders.schemas import (
    AllowancesIn,
    CopyFormsIn,
    CopyFormsOut,
    FormOptionsIn,
    FormOptionsOut,
    ItemImportOut,
    LeadOrdersOut,
    LinePriceIn,
    OrderCancelIn,
    OrderDraftIn,
    OrderExportParams,
    OrderFormCreateIn,
    OrderFormItemCreateIn,
    OrderFormItemListParams,
    OrderFormItemOut,
    OrderFormItemUpdateIn,
    OrderFormListParams,
    OrderFormOut,
    OrderFormUpdateIn,
    OrderReviewIn,
    OrdersSummaryOut,
    OrdersSummaryParams,
    OrderVersionIn,
    PortalOrderFormDetailOut,
    PortalOrderFormsOut,
    PortalOrderOut,
    StaffOrderListParams,
    StaffOrderOut,
    StaffOrderRowOut,
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


@router.get("/{form_id}/options", response_model=FormOptionsOut)
async def get_options(
    form_id: uuid.UUID, session: Session, ctx: AuthContext = Read
) -> FormOptionsOut:
    return await service.get_options(session, ctx, form_id)


@router.put("/{form_id}/options", response_model=FormOptionsOut)
async def set_options(
    form_id: uuid.UUID, data: FormOptionsIn, session: Session, ctx: AuthContext = Manage
) -> FormOptionsOut:
    return await service.set_options(session, ctx, form_id, data)


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


@router.put("/{form_id}/items/{item_id}/allowances", response_model=OrderFormItemOut)
async def set_allowances(
    form_id: uuid.UUID,
    item_id: uuid.UUID,
    data: AllowancesIn,
    session: Session,
    ctx: AuthContext = Manage,
) -> OrderFormItemOut:
    return await service.set_allowances(session, ctx, form_id, item_id, data)


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


# --- exhibitor portal --------------------------------------------------------------------

portal_router = APIRouter(prefix="/portal/exhibitors/{lead_id}", tags=["exhibitor-portal"])
PortalAccount = Depends(portal_account)
ORDER = "/orders/{order_id}"


async def _lead(session: AsyncSession, ctx: PortalContext, lead_id: uuid.UUID) -> ExhibitorLead:
    return await exhibitors_portal.own_exhibitor(session, ctx, lead_id)


@portal_router.get("/order-forms", response_model=PortalOrderFormsOut)
async def portal_forms(
    lead_id: uuid.UUID, session: Session, ctx: PortalContext = PortalAccount
) -> PortalOrderFormsOut:
    return await portal.list_forms(session, await _lead(session, ctx, lead_id))


@portal_router.get("/order-forms/{code}", response_model=PortalOrderFormDetailOut)
async def portal_form(
    lead_id: uuid.UUID, code: str, session: Session, ctx: PortalContext = PortalAccount
) -> PortalOrderFormDetailOut:
    return await portal.form_detail(session, await _lead(session, ctx, lead_id), code)


@portal_router.put("/order-forms/{code}/not-required", response_model=PortalOrderFormDetailOut)
async def portal_not_required(
    lead_id: uuid.UUID, code: str, session: Session, ctx: PortalContext = PortalAccount
) -> PortalOrderFormDetailOut:
    lead = await _lead(session, ctx, lead_id)
    return await portal.set_not_required(session, ctx.account_id, lead, code, True)


@portal_router.delete("/order-forms/{code}/not-required", response_model=PortalOrderFormDetailOut)
async def portal_required(
    lead_id: uuid.UUID, code: str, session: Session, ctx: PortalContext = PortalAccount
) -> PortalOrderFormDetailOut:
    lead = await _lead(session, ctx, lead_id)
    return await portal.set_not_required(session, ctx.account_id, lead, code, False)


@portal_router.get(
    "/order-forms/{code}/items/{item_id}/image",
    response_class=StreamingResponse,
    responses={200: {"content": {"image/jpeg": {}, "image/png": {}}}},
)
async def portal_item_image(
    lead_id: uuid.UUID,
    code: str,
    item_id: uuid.UUID,
    session: Session,
    ctx: PortalContext = PortalAccount,
) -> StreamingResponse:
    lead = await _lead(session, ctx, lead_id)
    return _inline(*await portal.item_image(session, lead, code, item_id))


@portal_router.post(
    "/order-forms/{code}/orders",
    response_model=PortalOrderOut,
    status_code=status.HTTP_201_CREATED,
)
async def portal_create_order(
    lead_id: uuid.UUID, code: str, session: Session, ctx: PortalContext = PortalAccount
) -> PortalOrderOut:
    lead = await _lead(session, ctx, lead_id)
    return await portal.create_order(session, ctx.account_id, lead, code)


@portal_router.patch(ORDER, response_model=PortalOrderOut)
async def portal_update_order(
    lead_id: uuid.UUID,
    order_id: uuid.UUID,
    data: OrderDraftIn,
    session: Session,
    ctx: PortalContext = PortalAccount,
) -> PortalOrderOut:
    lead = await _lead(session, ctx, lead_id)
    return await portal.update_order(session, ctx.account_id, lead, order_id, data)


@portal_router.delete(ORDER, status_code=status.HTTP_204_NO_CONTENT)
async def portal_delete_order(
    lead_id: uuid.UUID, order_id: uuid.UUID, session: Session, ctx: PortalContext = PortalAccount
) -> None:
    lead = await _lead(session, ctx, lead_id)
    await portal.delete_order(session, ctx.account_id, lead, order_id)


@portal_router.post(f"{ORDER}/quote", response_model=PortalOrderOut)
async def portal_quote_order(
    lead_id: uuid.UUID, order_id: uuid.UUID, session: Session, ctx: PortalContext = PortalAccount
) -> PortalOrderOut:
    return await portal.quote_order(session, await _lead(session, ctx, lead_id), order_id)


@portal_router.post(f"{ORDER}/submit", response_model=PortalOrderOut)
async def portal_submit_order(
    lead_id: uuid.UUID,
    order_id: uuid.UUID,
    data: OrderVersionIn,
    session: Session,
    ctx: PortalContext = PortalAccount,
) -> PortalOrderOut:
    lead = await _lead(session, ctx, lead_id)
    return await portal.submit_order(session, ctx.account_id, lead, order_id, data.version)


@portal_router.post(f"{ORDER}/lines/{{line_id}}/image", response_model=PortalOrderOut)
async def portal_line_image_upload(
    lead_id: uuid.UUID,
    order_id: uuid.UUID,
    line_id: uuid.UUID,
    session: Session,
    file: Annotated[UploadFile, File()],
    version: Annotated[int, Form()],
    ctx: PortalContext = PortalAccount,
) -> PortalOrderOut:
    lead = await _lead(session, ctx, lead_id)
    return await portal.set_line_image(
        session,
        ctx.account_id,
        lead,
        order_id,
        line_id,
        file_name=file.filename or "image",
        content_type=file.content_type,
        data=await file.read(portal.IMAGE_MAX_BYTES + 1),
        version=version,
    )


@portal_router.get(
    f"{ORDER}/lines/{{line_id}}/image",
    response_class=StreamingResponse,
    responses={200: {"content": {"image/jpeg": {}, "image/png": {}}}},
)
async def portal_line_image(
    lead_id: uuid.UUID,
    order_id: uuid.UUID,
    line_id: uuid.UUID,
    session: Session,
    ctx: PortalContext = PortalAccount,
) -> StreamingResponse:
    lead = await _lead(session, ctx, lead_id)
    return _inline(*await portal.line_image(session, lead, order_id, line_id))


@portal_router.post(f"{ORDER}/files", response_model=PortalOrderOut)
async def portal_add_file(
    lead_id: uuid.UUID,
    order_id: uuid.UUID,
    session: Session,
    file: Annotated[UploadFile, File()],
    purpose: Annotated[AttachmentPurpose, Form()],
    version: Annotated[int, Form()],
    ctx: PortalContext = PortalAccount,
) -> PortalOrderOut:
    lead = await _lead(session, ctx, lead_id)
    return await portal.add_file(
        session,
        ctx.account_id,
        lead,
        order_id,
        purpose=purpose,
        file_name=file.filename or "attachment",
        content_type=file.content_type,
        data=await file.read(portal.FILE_MAX_BYTES + 1),
        version=version,
    )


@portal_router.delete(f"{ORDER}/files/{{file_id}}", response_model=PortalOrderOut)
async def portal_remove_file(
    lead_id: uuid.UUID,
    order_id: uuid.UUID,
    file_id: uuid.UUID,
    session: Session,
    version: Annotated[int, Query()],
    ctx: PortalContext = PortalAccount,
) -> PortalOrderOut:
    lead = await _lead(session, ctx, lead_id)
    return await portal.remove_file(session, ctx.account_id, lead, order_id, file_id, version)


@portal_router.get(
    f"{ORDER}/files/{{file_id}}",
    response_class=StreamingResponse,
    responses={200: {"content": {"application/pdf": {}, "image/jpeg": {}, "image/png": {}}}},
)
async def portal_file(
    lead_id: uuid.UUID,
    order_id: uuid.UUID,
    file_id: uuid.UUID,
    session: Session,
    ctx: PortalContext = PortalAccount,
) -> StreamingResponse:
    lead = await _lead(session, ctx, lead_id)
    chunks, name, media_type = await portal.file_download(session, lead, order_id, file_id)
    return StreamingResponse(
        chunks,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Cache-Control": "no-store",
        },
    )


# --- staff review ------------------------------------------------------------------------

orders_router = APIRouter(prefix="/exhibitor-orders", tags=["exhibitor-orders"])
LeadRead = Depends(require(review.READ))
Review = Depends(require(review.REVIEW))


@orders_router.get("", response_model=Page[StaffOrderRowOut])
async def list_orders(
    session: Session, params: Annotated[StaffOrderListParams, Query()], ctx: AuthContext = LeadRead
) -> Page[StaffOrderRowOut]:
    return await review.list_orders(session, ctx, params)


@orders_router.get("/summary", response_model=OrdersSummaryOut)
async def orders_summary(
    session: Session, params: Annotated[OrdersSummaryParams, Query()], ctx: AuthContext = LeadRead
) -> OrdersSummaryOut:
    return await payments.summary(session, ctx, params.edition_id)


# Before /{order_id}, which would take "export" as an id.
@orders_router.get("/export", response_class=Response, responses={200: {"content": {XLSX: {}}}})
async def export_orders(
    session: Session, params: Annotated[OrderExportParams, Query()], ctx: AuthContext = LeadRead
) -> Response:
    data, name = await review.export_form(session, ctx, params)
    return Response(
        data,
        media_type=XLSX,
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Cache-Control": "no-store",
        },
    )


@orders_router.get("/{order_id}", response_model=StaffOrderOut)
async def get_order(
    order_id: uuid.UUID, session: Session, ctx: AuthContext = LeadRead
) -> StaffOrderOut:
    return await review.get_order(session, ctx, order_id)


@orders_router.patch("/{order_id}/lines/{line_id}", response_model=StaffOrderOut)
async def price_line(
    order_id: uuid.UUID,
    line_id: uuid.UUID,
    data: LinePriceIn,
    session: Session,
    ctx: AuthContext = Review,
) -> StaffOrderOut:
    return await review.price_line(session, ctx, order_id, line_id, data)


@orders_router.post("/{order_id}/review", response_model=StaffOrderOut)
async def review_order(
    order_id: uuid.UUID, data: OrderReviewIn, session: Session, ctx: AuthContext = Review
) -> StaffOrderOut:
    return await review.review_order(session, ctx, order_id, data)


@orders_router.post("/{order_id}/cancel", response_model=StaffOrderOut)
async def cancel_order(
    order_id: uuid.UUID, data: OrderCancelIn, session: Session, ctx: AuthContext = Review
) -> StaffOrderOut:
    return await review.cancel_order(session, ctx, order_id, data)


@orders_router.get(
    "/{order_id}/lines/{line_id}/image",
    response_class=StreamingResponse,
    responses={200: {"content": {"image/jpeg": {}, "image/png": {}}}},
)
async def staff_line_image(
    order_id: uuid.UUID, line_id: uuid.UUID, session: Session, ctx: AuthContext = LeadRead
) -> StreamingResponse:
    return _inline(*await review.line_image(session, ctx, order_id, line_id))


@orders_router.get(
    "/{order_id}/files/{file_id}",
    response_class=StreamingResponse,
    responses={200: {"content": {"application/pdf": {}, "image/jpeg": {}, "image/png": {}}}},
)
async def staff_file(
    order_id: uuid.UUID, file_id: uuid.UUID, session: Session, ctx: AuthContext = LeadRead
) -> StreamingResponse:
    chunks, name, media_type = await review.file_download(session, ctx, order_id, file_id)
    return StreamingResponse(
        chunks,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Cache-Control": "no-store",
        },
    )


# On the lead, next to its contract and payments.
lead_orders_router = APIRouter(tags=["exhibitor-orders"])


@lead_orders_router.get("/exhibitor-leads/{lead_id}/orders", response_model=LeadOrdersOut)
async def lead_orders(
    lead_id: uuid.UUID, session: Session, ctx: AuthContext = LeadRead
) -> LeadOrdersOut:
    return await review.lead_orders(session, ctx, lead_id)


# --- payments of orders (Phase 7) --------------------------------------------------------

PAYMENTS = "/{order_id}/payments"


@orders_router.get(PAYMENTS, response_model=PaymentsOut)
async def order_payments(
    order_id: uuid.UUID, session: Session, ctx: AuthContext = LeadRead
) -> PaymentsOut:
    return await payments.list_payments(session, ctx, order_id)


@orders_router.post(PAYMENTS, response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
async def record_order_payment(
    order_id: uuid.UUID,
    data: PaymentCreateIn,
    session: Session,
    ctx: AuthContext = Depends(require(payments.RECORD)),
) -> PaymentOut:
    return await payments.record_payment(session, ctx, order_id, data)


@orders_router.post(f"{PAYMENTS}/{{payment_id}}/proof", response_model=PaymentOut)
async def attach_order_payment_proof(
    order_id: uuid.UUID,
    payment_id: uuid.UUID,
    session: Session,
    file: Annotated[UploadFile, File()],
    version: Annotated[int, Form()],
    ctx: AuthContext = Depends(require(payments.RECORD)),
) -> PaymentOut:
    return await payments.attach_proof(
        session,
        ctx,
        order_id,
        payment_id,
        file_name=file.filename or "proof",
        content_type=file.content_type,
        data=await file.read(payments.PROOF_MAX_BYTES + 1),
        version=version,
    )


@orders_router.get(
    f"{PAYMENTS}/{{payment_id}}/proof",
    response_class=StreamingResponse,
    responses={200: {"content": {"application/pdf": {}, "image/jpeg": {}, "image/png": {}}}},
)
async def order_payment_proof(
    order_id: uuid.UUID, payment_id: uuid.UUID, session: Session, ctx: AuthContext = LeadRead
) -> StreamingResponse:
    chunks, name, media_type = await payments.proof(session, ctx, order_id, payment_id)
    return StreamingResponse(
        chunks,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Cache-Control": "no-store",
        },
    )


@orders_router.post(f"{PAYMENTS}/{{payment_id}}/review", response_model=PaymentOut)
async def review_order_payment(
    order_id: uuid.UUID,
    payment_id: uuid.UUID,
    data: PaymentReviewIn,
    session: Session,
    ctx: AuthContext = Depends(require(payments.VERIFY)),
) -> PaymentOut:
    return await payments.review_payment(session, ctx, order_id, payment_id, data)


@portal_router.get(f"{ORDER}/payments", response_model=PortalPaymentsOut)
async def portal_order_payments(
    lead_id: uuid.UUID, order_id: uuid.UUID, session: Session, ctx: PortalContext = PortalAccount
) -> PortalPaymentsOut:
    return await payments.portal_payments(session, await _lead(session, ctx, lead_id), order_id)
