from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from models.database import get_db_session

DBSessionDep = Annotated[AsyncSession, Depends(get_db_session)]