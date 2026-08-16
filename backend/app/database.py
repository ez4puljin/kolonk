from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    # updated_at нь server-side onupdate (func.now()) тул UPDATE-ийн дараа
    # SQLAlchemy уг баганыг expire болгож, дараа нь уншихад sync IO хийхийг
    # оролддог (MissingGreenlet). eager_defaults нь RETURNING ашиглан шинэ
    # утгыг тэр даруй авчирдаг тул async горимд аюулгүй болно.
    __mapper_args__ = {"eager_defaults": True}


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Request-scoped session. Business services never commit — the router
    dependency owns the single commit so a whole business event is atomic."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
