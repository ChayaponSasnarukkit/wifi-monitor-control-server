from database import Base, sessionmanager
import asyncio

async def create_empty_db():
    async with sessionmanager.connect() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    await sessionmanager.close()
    
asyncio.run(create_empty_db())