from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.core.db import get_engine
from app.core.redis import get_redis

router = APIRouter(prefix="/health", tags=["health"])


class HealthOut(BaseModel):
    status: str
    checks: dict[str, str] = {}


@router.get("/live", response_model=HealthOut)
async def live() -> HealthOut:
    return HealthOut(status="ok")


@router.get("/ready", response_model=HealthOut, responses={503: {"model": HealthOut}})
async def ready() -> HealthOut | JSONResponse:
    checks: dict[str, str] = {}
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
    try:
        await get_redis().ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"
    if all(v == "ok" for v in checks.values()):
        return HealthOut(status="ok", checks=checks)
    return JSONResponse(HealthOut(status="error", checks=checks).model_dump(), status_code=503)
