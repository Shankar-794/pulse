"""
Database connection and session management.
PostgreSQL ready with async engine support.
"""
from typing import AsyncGenerator
from backend.app.core.config import settings

try:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy.orm import declarative_base

    Base = declarative_base()

    engine = None
    async_session_factory = None

    if not settings.USE_IN_MEMORY_STORE and settings.DATABASE_URL:
        try:
            # Ensure async dialect for SQLAlchemy async engine if needed
            async_url = settings.DATABASE_URL
            if async_url.startswith("postgresql://"):
                async_url = async_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif async_url.startswith("postgres://"):
                async_url = async_url.replace("postgres://", "postgresql+asyncpg://", 1)
            engine = create_async_engine(
                async_url,
                echo=settings.DEBUG,
                pool_pre_ping=True
            )
            async_session_factory = async_sessionmaker(
                engine,
                expire_on_commit=False,
                class_=AsyncSession
            )
        except Exception:
            engine = None
            async_session_factory = None

    async def get_db() -> AsyncGenerator[AsyncSession, None]:
        """Dependency for FastAPI endpoints requiring database session."""
        if async_session_factory is None:
            yield None
            return
        async with async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

except ImportError:
    class Base:
        pass

    async def get_db():
        yield None
