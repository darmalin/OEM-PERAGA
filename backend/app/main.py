from fastapi import APIRouter, FastAPI

from app.core import health
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import install_middleware
from app.modules.audit import router as audit
from app.modules.checkin import router as checkin
from app.modules.exhibitions import router as exhibitions
from app.modules.identity import router as identity
from app.modules.importexport import router as importexport
from app.modules.mail import router as mail
from app.modules.registrations import router as registrations
from app.modules.reporting import router as reporting
from app.modules.telemarketing import router as telemarketing
from app.modules.visitors import router as visitors

API_PREFIX = "/api/v1"


def build_api_router() -> APIRouter:
    router = APIRouter(prefix=API_PREFIX)
    router.include_router(health.router)
    router.include_router(identity.auth_router)
    router.include_router(identity.router)
    router.include_router(audit.router)
    router.include_router(exhibitions.router)
    router.include_router(importexport.router)  # before /visitor-leads/{lead_id}
    router.include_router(telemarketing.router)
    router.include_router(visitors.router)
    router.include_router(registrations.router)
    router.include_router(mail.router)
    router.include_router(registrations.public_router)
    router.include_router(checkin.router)
    router.include_router(checkin.device_router)
    router.include_router(reporting.router)
    router.include_router(importexport.export_router)
    return router


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="EMS Visitor CRM",
        version="1.0.0",
        openapi_url=f"{API_PREFIX}/openapi.json" if settings.openapi_enabled else None,
        docs_url=f"{API_PREFIX}/docs" if settings.openapi_enabled else None,
        redoc_url=None,
    )
    install_error_handlers(app)
    install_middleware(app)
    app.include_router(build_api_router())
    return app


app = create_app()
