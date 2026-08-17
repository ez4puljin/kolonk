import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import async_session_factory
from app.redis_client import close_redis, get_redis

log = logging.getLogger("kolonk")

ROUTER_MODULES = [
    "auth",
    "users",
    "fuels",
    "tanks",
    "pumps",
    "shifts",
    "products",
    "inventory",
    "suppliers",
    "fuel_receipts",
    "purchases",
    "expenses",
    "bank",
    "payroll",
    "customers",
    "contracts",
    "vouchers",
    "prepaid_cards",
    "sales",
    "refunds",
    "price_changes",
    "accounting",
    "reports",
    "inventory_report",
    "report_center",
    "branches",
    "dashboards",
    "ebarimt",
    "audit",
    "settings",
    "backup",
    "ws",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.database import async_session_factory
    from app.hardware.pump_manager import PumpManager
    from app.services.rbac_service import sync_permissions

    # Кодод шинэ эрх нэмэгдсэн бол суусан систем дээр өөрөө үйлчилнэ
    # (seed зөвхөн хоосон санд ажилладаг тул шинэчлэлтэд хүрэлцэхгүй).
    try:
        async with async_session_factory() as session:
            await sync_permissions(session)
            await session.commit()
    except Exception:  # noqa: BLE001
        log.exception("Эрхийн синк амжилтгүй боллоо")

    manager = PumpManager()
    app.state.pump_manager = manager
    try:
        await manager.start()
    except Exception:  # noqa: BLE001
        log.exception("Насосны менежер асаахад алдаа гарлаа")
    yield
    await manager.stop()
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Колонк — ШТС POS & ERP",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    import importlib

    for name in ROUTER_MODULES:
        module = importlib.import_module(f"app.routers.{name}")
        app.include_router(module.router)

    @app.get("/api/health")
    async def health() -> JSONResponse:
        db_ok, redis_ok = False, False
        try:
            async with async_session_factory() as session:
                await session.execute(text("SELECT 1"))
            db_ok = True
        except Exception:  # noqa: BLE001
            log.exception("DB health check failed")
        try:
            await get_redis().ping()
            redis_ok = True
        except Exception:  # noqa: BLE001
            log.exception("Redis health check failed")

        status_code = 200 if (db_ok and redis_ok) else 503
        return JSONResponse(
            status_code=status_code,
            content={"status": "ok" if status_code == 200 else "degraded", "db": db_ok, "redis": redis_ok},
        )

    return app


app = create_app()
