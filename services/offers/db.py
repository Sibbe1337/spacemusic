import os
from sqlmodel import create_engine, SQLModel, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Use DB_CONNECTION_STRING from environment variable, default to a local dev PG
DATABASE_URL = os.getenv("DB_CONNECTION_STRING", "postgresql+asyncpg://user:password@localhost/offers_db")

# Create an async engine instance
async_engine = create_async_engine(DATABASE_URL, echo=True, future=True)

async def init_db():
    async with async_engine.begin() as conn:
        # await conn.run_sync(SQLModel.metadata.drop_all) # Use with caution in dev
        await conn.run_sync(SQLModel.metadata.create_all)

async def get_session() -> AsyncSession:
    async_session = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session

# For synchronous operations if ever needed (e.g. certain Alembic contexts, though env.py handles it)
# SYNC_DATABASE_URL = os.getenv("SYNC_DB_CONNECTION_STRING", "postgresql://user:password@localhost/offers_db")
# sync_engine = create_engine(SYNC_DATABASE_URL, echo=True)

# def get_sync_session():
#     with Session(sync_engine) as session:
#         yield session 