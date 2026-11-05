import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require
from app.core.config import get_settings
from app.core.db import get_session
from app.core.pagination import Page
from app.modules.audit.schemas import AuditLogOut
from app.modules.exhibitors import portal, service
from app.modules.exhibitors.portal import PortalContext, portal_account
from app.modules.exhibitors.schemas import (
    AcceptInvitationIn,
    BoothAssignIn,
    BoothCreateIn,
    BoothListParams,
    BoothOut,
    BoothUpdateIn,
    ContractFieldsIn,
    ContractOut,
    ContractUpdateIn,
    ConvertIn,
    ConvertOut,
    ExhibitorLeadCreateIn,
    ExhibitorLeadListParams,
    ExhibitorLeadOut,
    ExhibitorLeadUpdateIn,
    InvitationInfoOut,
    InvitationOut,
    InvitationTokenIn,
    LeadOwnerParams,
    LeadOwnersOut,
    PaymentCreateIn,
    PaymentOut,
    PaymentReviewIn,
    PaymentsOut,
    PipelineOut,
    PipelineParams,
    PortalAccountOut,
    PortalAccountUpdateIn,
    PortalLoginIn,
    PortalMeOut,
    PortalPaymentsOut,
    StageChangeIn,
)

router = APIRouter(tags=["exhibitors"])
portal_router = APIRouter(prefix="/portal", tags=["exhibitor-portal"])
Session = Annotated[AsyncSession, Depends(get_session)]
PDF = "application/pdf"


# Before /exhibitor-leads/{lead_id}, which would take "owners" as an id.
@router.get("/exhibitor-leads/owners", response_model=LeadOwnersOut)
async def lead_owners(
    session: Session,
    params: Annotated[LeadOwnerParams, Query()],
    ctx: AuthContext = Depends(require("exhibitor_lead.read")),
) -> LeadOwnersOut:
    return await service.lead_owners(session, ctx, params.edition_id)


# Before /exhibitor-leads/{lead_id}, which would take "pipeline" as an id.
@router.get("/exhibitor-leads/pipeline", response_model=PipelineOut)
async def pipeline(
    session: Session,
    params: Annotated[PipelineParams, Query()],
    ctx: AuthContext = Depends(require("exhibitor_lead.read")),
) -> PipelineOut:
    return await service.pipeline(session, ctx, params.edition_id)


@router.get("/exhibitor-leads", response_model=Page[ExhibitorLeadOut])
async def list_leads(
    session: Session,
    params: Annotated[ExhibitorLeadListParams, Query()],
    ctx: AuthContext = Depends(require("exhibitor_lead.read")),
) -> Page[ExhibitorLeadOut]:
    return await service.list_leads(session, ctx, params)


@router.post(
    "/exhibitor-leads", response_model=ExhibitorLeadOut, status_code=status.HTTP_201_CREATED
)
async def create_lead(
    data: ExhibitorLeadCreateIn,
    session: Session,
    ctx: AuthContext = Depends(require("exhibitor_lead.create")),
) -> ExhibitorLeadOut:
    return await service.create_lead(session, ctx, data)


@router.get("/exhibitor-leads/{lead_id}", response_model=ExhibitorLeadOut)
async def get_lead(
    lead_id: uuid.UUID,
    session: Session,
    ctx: AuthContext = Depends(require("exhibitor_lead.read")),
) -> ExhibitorLeadOut:
    return await service.get_lead(session, ctx, lead_id)


@router.patch("/exhibitor-leads/{lead_id}", response_model=ExhibitorLeadOut)
async def update_lead(
    lead_id: uuid.UUID,
    data: ExhibitorLeadUpdateIn,
    session: Session,
    ctx: AuthContext = Depends(require("exhibitor_lead.update")),
) -> ExhibitorLeadOut:
    return await service.update_lead(session, ctx, lead_id, data)


@router.post("/exhibitor-leads/{lead_id}/stage", response_model=ExhibitorLeadOut)
async def change_stage(
    lead_id: uuid.UUID,
    data: StageChangeIn,
    session: Session,
    ctx: AuthContext = Depends(require("exhibitor_lead.update")),
) -> ExhibitorLeadOut:
    return await service.change_stage(session, ctx, lead_id, data)


@router.get("/exhibitor-leads/{lead_id}/activity", response_model=list[AuditLogOut])
async def lead_activity(
    lead_id: uuid.UUID,
    session: Session,
    ctx: AuthContext = Depends(require("exhibitor_lead.read")),
) -> list[AuditLogOut]:
    return await service.activity(session, ctx, lead_id)


@router.put("/exhibitor-leads/{lead_id}/booth", response_model=ExhibitorLeadOut)
async def assign_booth(
    lead_id: uuid.UUID,
    data: BoothAssignIn,
    session: Session,
    ctx: AuthContext = Depends(require("exhibitor_lead.update")),
) -> ExhibitorLeadOut:
    return await service.assign_booth(session, ctx, lead_id, data)


@router.get("/booths", response_model=Page[BoothOut])
async def list_booths(
    session: Session,
    params: Annotated[BoothListParams, Query()],
    ctx: AuthContext = Depends(require("booth.manage", "exhibitor_lead.read")),
) -> Page[BoothOut]:
    return await service.list_booths(session, ctx, params)


@router.post("/booths", response_model=BoothOut, status_code=status.HTTP_201_CREATED)
async def create_booth(
    data: BoothCreateIn, session: Session, ctx: AuthContext = Depends(require("booth.manage"))
) -> BoothOut:
    return await service.create_booth(session, ctx, data)


@router.patch("/booths/{booth_id}", response_model=BoothOut)
async def update_booth(
    booth_id: uuid.UUID,
    data: BoothUpdateIn,
    session: Session,
    ctx: AuthContext = Depends(require("booth.manage")),
) -> BoothOut:
    return await service.update_booth(session, ctx, booth_id, data)


@router.post("/exhibitor-leads/{lead_id}/convert", response_model=ConvertOut)
async def convert(
    lead_id: uuid.UUID,
    data: ConvertIn,
    session: Session,
    ctx: AuthContext = Depends(require("exhibitor.invite")),
) -> ConvertOut:
    return await service.convert(session, ctx, lead_id, data)


@router.post("/exhibitor-leads/{lead_id}/portal-invitation", response_model=InvitationOut)
async def reissue_invitation(
    lead_id: uuid.UUID,
    session: Session,
    ctx: AuthContext = Depends(require("exhibitor.invite")),
) -> InvitationOut:
    return await service.reissue_invitation(session, ctx, lead_id)


@router.get("/exhibitor-leads/{lead_id}/contract", response_model=ContractOut)
async def get_contract(
    lead_id: uuid.UUID,
    session: Session,
    ctx: AuthContext = Depends(require("exhibitor_lead.read")),
) -> ContractOut:
    return await service.get_contract(session, ctx, lead_id)


@router.patch("/exhibitor-leads/{lead_id}/contract", response_model=ContractOut)
async def update_contract(
    lead_id: uuid.UUID,
    data: ContractUpdateIn,
    session: Session,
    ctx: AuthContext = Depends(require("exhibitor_lead.update")),
) -> ContractOut:
    return await service.update_contract(session, ctx, lead_id, data)


@router.post("/exhibitor-leads/{lead_id}/contract/signed-copy", response_model=ContractOut)
async def upload_signed_contract(
    lead_id: uuid.UUID,
    session: Session,
    file: Annotated[UploadFile, File()],
    version: Annotated[int, Form()],
    ctx: AuthContext = Depends(require("exhibitor_lead.update")),
) -> ContractOut:
    return await service.upload_signed_contract(
        session,
        ctx,
        lead_id,
        file_name=file.filename or "signed.pdf",
        content_type=file.content_type,
        data=await _read_limited(file),
        version=version,
    )


@router.get(
    "/exhibitor-leads/{lead_id}/contract/signed-copy",
    response_class=StreamingResponse,
    responses={200: {"content": {PDF: {}}, "description": "Signed contract"}},
)
async def contract_file(
    lead_id: uuid.UUID,
    session: Session,
    ctx: AuthContext = Depends(require("exhibitor_lead.read")),
) -> StreamingResponse:
    return _download(*await service.contract_file(session, ctx, lead_id))


@router.get("/exhibitor-leads/{lead_id}/payments", response_model=PaymentsOut)
async def list_payments(
    lead_id: uuid.UUID,
    session: Session,
    ctx: AuthContext = Depends(require("exhibitor_lead.read")),
) -> PaymentsOut:
    return await service.list_payments(session, ctx, lead_id)


@router.post(
    "/exhibitor-leads/{lead_id}/payments",
    response_model=PaymentOut,
    status_code=status.HTTP_201_CREATED,
)
async def record_payment(
    lead_id: uuid.UUID,
    data: PaymentCreateIn,
    session: Session,
    ctx: AuthContext = Depends(require("exhibitor_payment.record")),
) -> PaymentOut:
    return await service.record_payment(session, ctx, lead_id, data)


@router.post("/exhibitor-leads/{lead_id}/payments/{payment_id}/proof", response_model=PaymentOut)
async def attach_payment_proof(
    lead_id: uuid.UUID,
    payment_id: uuid.UUID,
    session: Session,
    file: Annotated[UploadFile, File()],
    version: Annotated[int, Form()],
    ctx: AuthContext = Depends(require("exhibitor_payment.record")),
) -> PaymentOut:
    return await service.attach_payment_proof(
        session,
        ctx,
        lead_id,
        payment_id,
        file_name=file.filename or "proof",
        content_type=file.content_type,
        data=await _read_limited(file),
        version=version,
    )


@router.get(
    "/exhibitor-leads/{lead_id}/payments/{payment_id}/proof",
    response_class=StreamingResponse,
    responses={200: {"content": {PDF: {}, "image/jpeg": {}, "image/png": {}}}},
)
async def payment_proof(
    lead_id: uuid.UUID,
    payment_id: uuid.UUID,
    session: Session,
    ctx: AuthContext = Depends(require("exhibitor_lead.read")),
) -> StreamingResponse:
    chunks, name, media_type = await service.payment_proof(session, ctx, lead_id, payment_id)
    return _download(chunks, name, media_type)


@router.post("/exhibitor-leads/{lead_id}/payments/{payment_id}/review", response_model=PaymentOut)
async def review_payment(
    lead_id: uuid.UUID,
    payment_id: uuid.UUID,
    data: PaymentReviewIn,
    session: Session,
    ctx: AuthContext = Depends(require("exhibitor_payment.verify")),
) -> PaymentOut:
    return await service.review_payment(session, ctx, lead_id, payment_id, data)


async def _read_limited(file: UploadFile) -> bytes:
    # One byte past the limit so an oversize file is detected without buffering all of it.
    return await file.read(get_settings().contract_file_max_bytes + 1)


def _download(chunks: Iterator[bytes], filename: str, media_type: str = PDF) -> StreamingResponse:
    """Names come from the server (contract numbers, payment ids), never from the upload."""
    return StreamingResponse(
        chunks,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/exhibitor-leads/{lead_id}/portal-account", response_model=PortalAccountOut)
async def get_portal_account(
    lead_id: uuid.UUID,
    session: Session,
    ctx: AuthContext = Depends(require("exhibitor_lead.read")),
) -> PortalAccountOut:
    return await service.get_portal_account(session, ctx, lead_id)


@router.put("/exhibitor-leads/{lead_id}/portal-account", response_model=PortalAccountOut)
async def set_portal_account_active(
    lead_id: uuid.UUID,
    data: PortalAccountUpdateIn,
    session: Session,
    ctx: AuthContext = Depends(require("exhibitor.invite")),
) -> PortalAccountOut:
    return await service.set_portal_account_active(session, ctx, lead_id, data)


# --- exhibitor portal --------------------------------------------------------------------


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _set_portal_cookie(response: Response, session_id: str) -> None:
    s = get_settings()
    # Host-only cookie: on the portal subdomain in production; on the desk host in dev it sits
    # beside the staff cookie under another name and another Redis namespace.
    response.set_cookie(
        s.portal_session_cookie_name,
        session_id,
        httponly=True,
        secure=s.session_cookie_secure,
        samesite="lax",
        path="/",
        max_age=s.session_absolute_timeout_seconds,
    )


@portal_router.post("/invitations/inspect", response_model=InvitationInfoOut)
async def inspect_invitation(
    data: InvitationTokenIn, request: Request, session: Session
) -> InvitationInfoOut:
    email, purpose = await portal.invitation_info(session, data.token, _client_ip(request))
    return InvitationInfoOut(email=email, purpose=purpose)


@portal_router.post("/invitations/accept", response_model=PortalMeOut)
async def accept_invitation(
    data: AcceptInvitationIn, request: Request, response: Response, session: Session
) -> PortalMeOut:
    account, sess = await portal.accept_invitation(
        session, data.token, data.password, _client_ip(request)
    )
    _set_portal_cookie(response, sess.session_id)
    return await portal.me(session, account.id, sess.csrf_token)


@portal_router.post("/auth/login", response_model=PortalMeOut)
async def portal_login(
    data: PortalLoginIn, request: Request, response: Response, session: Session
) -> PortalMeOut:
    account, sess = await portal.login(session, data.email, data.password, _client_ip(request))
    _set_portal_cookie(response, sess.session_id)
    return await portal.me(session, account.id, sess.csrf_token)


@portal_router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def portal_logout(response: Response, ctx: PortalContext = Depends(portal_account)) -> None:
    await portal.logout(ctx)
    response.delete_cookie(get_settings().portal_session_cookie_name, path="/")


@portal_router.get("/auth/me", response_model=PortalMeOut)
async def portal_me(session: Session, ctx: PortalContext = Depends(portal_account)) -> PortalMeOut:
    return await portal.me(session, ctx.account_id, ctx.session.csrf_token)


@portal_router.get("/exhibitors/{lead_id}/contract", response_model=ContractOut)
async def portal_contract(
    lead_id: uuid.UUID, session: Session, ctx: PortalContext = Depends(portal_account)
) -> ContractOut:
    return await service.view_contract(session, await portal.own_exhibitor(session, ctx, lead_id))


@portal_router.patch("/exhibitors/{lead_id}/contract", response_model=ContractOut)
async def portal_fill_contract(
    lead_id: uuid.UUID,
    data: ContractFieldsIn,
    session: Session,
    ctx: PortalContext = Depends(portal_account),
) -> ContractOut:
    lead = await portal.own_exhibitor(session, ctx, lead_id)
    changes = data.model_dump(exclude_unset=True, exclude={"version"})
    return await service.fill_contract(session, lead, changes, data.version, ctx.account_id)


@portal_router.post("/exhibitors/{lead_id}/contract/signed-copy", response_model=ContractOut)
async def portal_sign_contract(
    lead_id: uuid.UUID,
    session: Session,
    file: Annotated[UploadFile, File()],
    version: Annotated[int, Form()],
    ctx: PortalContext = Depends(portal_account),
) -> ContractOut:
    return await service.sign_contract(
        session,
        await portal.own_exhibitor(session, ctx, lead_id),
        file_name=file.filename or "signed.pdf",
        content_type=file.content_type,
        data=await _read_limited(file),
        version=version,
        portal_account_id=ctx.account_id,
    )


@portal_router.get(
    "/exhibitors/{lead_id}/contract/signed-copy",
    response_class=StreamingResponse,
    responses={200: {"content": {PDF: {}}, "description": "Signed contract"}},
)
async def portal_contract_file(
    lead_id: uuid.UUID, session: Session, ctx: PortalContext = Depends(portal_account)
) -> StreamingResponse:
    lead = await portal.own_exhibitor(session, ctx, lead_id)
    return _download(*await service.signed_copy(session, lead))


@portal_router.get("/exhibitors/{lead_id}/payments", response_model=PortalPaymentsOut)
async def portal_payments(
    lead_id: uuid.UUID, session: Session, ctx: PortalContext = Depends(portal_account)
) -> PortalPaymentsOut:
    return await service.portal_payments(session, await portal.own_exhibitor(session, ctx, lead_id))
